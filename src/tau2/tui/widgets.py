"""Custom widgets for the BFS Explorer TUI."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Label,
    ListItem,
    ListView,
    OptionList,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.widgets.option_list import Option
from textual.widgets.tree import TreeNode

from tau2.generators.depgraph.types import TerminalProfileSpec

from .stepper import ActionProbe, BFSStepResult


def _short_path(path: str) -> str:
    """Shorten long paths for display: keep last two segments."""
    parts = path.split(".")
    if len(parts) <= 2:
        return path
    return "..." + ".".join(parts[-2:])


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


class BFSTreePanel(Container):
    """Left panel: tree view of BFS exploration."""

    class NodeSelected(Message):
        def __init__(self, node_id: int) -> None:
            super().__init__()
            self.node_id = node_id

    def compose(self) -> ComposeResult:
        tree: Tree[int] = Tree("BFS Root", id="bfs-tree")
        tree.root.expand()
        yield tree

    @property
    def tree(self) -> Tree[int]:
        return self.query_one("#bfs-tree", Tree)

    def reset(self, seed_id: str) -> None:
        tree = self.tree
        tree.clear()
        tree.root.set_label(Text(f"seed: {seed_id}", style="bold #61afef"))
        tree.root.data = 0
        tree.root.expand()
        self._node_map: dict[int, TreeNode[int]] = {0: tree.root}

    def add_step(self, result: BFSStepResult) -> None:
        if not hasattr(self, "_node_map"):
            self._node_map = {}

        if result.node_id == 0:
            # Root already added in reset()
            return

        parent_tree_node = self._node_map.get(result.parent_id)
        if parent_tree_node is None:
            parent_tree_node = self.tree.root

        action_label = result.action_taken or "?"
        # Strip common prefix for readability
        if action_label.startswith("action_"):
            action_label = action_label[7:]

        label = Text()
        if result.terminal_match is not None:
            label.append("* ", style="bold #e06c75")
        label.append(f"{action_label}", style="#eee8d5")
        label.append(f" n{result.node_id}", style="dim #a89984")
        label.append(f" d{result.depth}", style="dim #5c6370")

        node = parent_tree_node.add(label, data=result.node_id)
        node.expand()
        self._node_map[result.node_id] = node

    def on_tree_node_selected(self, event: Tree.NodeSelected[int]) -> None:
        if event.node.data is not None:
            self.post_message(self.NodeSelected(event.node.data))


class WorldStatePanel(Container):
    """Right-top panel: world state table + bindings."""

    def compose(self) -> ComposeResult:
        yield Label("World State", id="world-title", classes="panel-title")
        table = DataTable(id="world-table", zebra_stripes=True)
        table.cursor_type = "row"
        table.add_columns("Path", "Value")
        yield table
        yield Label("Bindings", id="bindings-title", classes="panel-title")
        yield Static("(none)", id="bindings-display")

    def update_state(
        self,
        world: dict[str, Any],
        bindings: frozenset[str],
        prev_world: dict[str, Any] | None = None,
        prev_bindings: frozenset[str] | None = None,
    ) -> None:
        table = self.query_one("#world-table", DataTable)
        table.clear()

        for path in sorted(world.keys()):
            value = world[path]
            changed = prev_world is not None and prev_world.get(path) != value

            path_text = Text(_short_path(path))
            if changed:
                path_text.stylize("bold #e5c07b")

            if changed and prev_world is not None:
                old_val = _format_value(prev_world.get(path))
                new_val = _format_value(value)
                val_text = Text()
                val_text.append(old_val, style="dim strike #a89984")
                val_text.append(" -> ", style="#5c6370")
                val_text.append(new_val, style="bold #e5c07b")
            else:
                val_text = Text(_format_value(value))

            table.add_row(path_text, val_text)

        # Bindings display
        bindings_widget = self.query_one("#bindings-display", Static)
        if not bindings and (prev_bindings is None or not prev_bindings):
            bindings_widget.update("(none)")
            return

        text = Text()
        all_bindings = sorted(set(bindings) | (prev_bindings or frozenset()))
        gained = set(bindings) - (prev_bindings or frozenset())
        lost = (prev_bindings or frozenset()) - set(bindings)

        for i, bid in enumerate(all_bindings):
            if i > 0:
                text.append("  ")
            if bid in gained:
                text.append(f"+{bid}", style="bold #98c379")
            elif bid in lost:
                text.append(f"-{bid}", style="strike #e06c75")
            else:
                text.append(bid, style="#a89984")

        bindings_widget.update(text)


class ActionPanel(Container):
    """Right-bottom panel: action probes with tabs."""

    class ActionSelected(Message):
        def __init__(self, probe: ActionProbe) -> None:
            super().__init__()
            self.probe = probe

    def compose(self) -> ComposeResult:
        yield Label("Actions", id="actions-title", classes="panel-title")
        with TabbedContent(id="action-tabs"):
            with TabPane("Enabled", id="tab-enabled"):
                yield ListView(id="enabled-list")
            with TabPane("Disabled", id="tab-disabled"):
                yield ListView(id="disabled-list")
            with TabPane("Diff", id="tab-diff"):
                yield VerticalScroll(
                    Static("Select an action to preview its effect.", id="diff-content"),
                    id="diff-scroll",
                )

    _update_gen: int = 0

    def update_probes(self, probes: list[ActionProbe]) -> None:
        self._update_gen += 1
        gen = self._update_gen
        self._probes_by_index: dict[str, ActionProbe] = {}
        enabled_list = self.query_one("#enabled-list", ListView)
        disabled_list = self.query_one("#disabled-list", ListView)
        enabled_list.clear()
        disabled_list.clear()

        enabled_count = 0
        disabled_count = 0

        for probe in probes:
            aid = probe.action.action_id
            short_aid = aid[7:] if aid.startswith("action_") else aid

            if probe.enabled:
                label = Text()
                if probe.is_stutter:
                    label.append("~ ", style="#5c6370")
                    label.append(short_aid, style="dim #5c6370")
                    label.append(" (stutter)", style="dim #5c6370")
                elif probe.is_visited:
                    label.append("~ ", style="#5c6370")
                    label.append(short_aid, style="dim #5c6370")
                    label.append(" (visited)", style="dim #5c6370")
                else:
                    if probe.matched_terminal:
                        label.append("* ", style="bold #e06c75")
                    else:
                        label.append("+ ", style="#98c379")
                    label.append(short_aid, style="#eee8d5")
                    cls_tag = f" [{probe.action.classification}]"
                    label.append(cls_tag, style="dim #a89984")
                    if probe.world_diff:
                        label.append(f" ({len(probe.world_diff)} changes)", style="dim #e5c07b")

                key = f"e_{gen}_{enabled_count}"
                self._probes_by_index[key] = probe
                item = ListItem(Static(label), name=key)
                enabled_list.append(item)
                enabled_count += 1
            else:
                label = Text()
                label.append("x ", style="#d19a66")
                label.append(short_aid, style="dim #d19a66")

                # Show first failure reason
                if probe.failed_world_predicates:
                    pred, actual = probe.failed_world_predicates[0]
                    reason = f" {_short_path(pred.path)} {pred.op} {_format_value(pred.value)}, got {_format_value(actual)}"
                    label.append(reason, style="dim #5c6370")
                elif probe.failed_binding_predicates:
                    pred, actual = probe.failed_binding_predicates[0]
                    state = "acquired" if actual else "not acquired"
                    need = "needs acquired" if pred.acquired else "needs not acquired"
                    label.append(f" {pred.binding_id}: {state}, {need}", style="dim #5c6370")
                elif not probe.knowledge_source_ok:
                    label.append(" (knowledge source unsatisfiable)", style="dim #5c6370")

                key = f"d_{gen}_{disabled_count}"
                self._probes_by_index[key] = probe
                item = ListItem(Static(label), name=key)
                disabled_list.append(item)
                disabled_count += 1

        # Update tab labels
        tabs = self.query_one("#action-tabs", TabbedContent)
        active_enabled = sum(1 for p in probes if p.enabled and not p.is_stutter and not p.is_visited)
        try:
            tabs.get_tab("tab-enabled").label = f"Enabled ({active_enabled})"
            tabs.get_tab("tab-disabled").label = f"Disabled ({disabled_count})"
        except Exception:
            pass

    def show_diff(self, probe: ActionProbe) -> None:
        diff_widget = self.query_one("#diff-content", Static)

        if not probe.enabled:
            text = Text()
            text.append("Action is disabled\n\n", style="bold #d19a66")
            for pred, actual in probe.failed_world_predicates:
                text.append(f"  {pred.path} ", style="#eee8d5")
                text.append(f"{pred.op} {_format_value(pred.value)}", style="#98c379")
                text.append(f"  actual: {_format_value(actual)}\n", style="#e06c75")
            for pred, actual in probe.failed_binding_predicates:
                state = "acquired" if actual else "not acquired"
                need = "acquired" if pred.acquired else "not acquired"
                text.append(f"  {pred.binding_id}: ", style="#eee8d5")
                text.append(f"need {need}", style="#98c379")
                text.append(f"  actual: {state}\n", style="#e06c75")
            diff_widget.update(text)
            return

        if probe.is_stutter:
            diff_widget.update(Text("No state change (stutter)", style="dim #5c6370"))
            return

        text = Text()
        aid = probe.action.action_id
        text.append(f"{aid}\n", style="bold #61afef")
        text.append(f"  classification: {probe.action.classification}\n", style="#a89984")
        text.append(f"  requestor: {probe.action.requestor}\n", style="#a89984")
        text.append(f"  tool: {probe.action.tool_name}\n\n", style="#a89984")

        if probe.world_diff:
            text.append("World Changes:\n", style="bold #e5c07b")
            for path, old, new in probe.world_diff:
                text.append(f"  {_short_path(path)}: ", style="#eee8d5")
                text.append(f"{_format_value(old)}", style="dim strike #a89984")
                text.append(" -> ", style="#5c6370")
                text.append(f"{_format_value(new)}\n", style="bold #e5c07b")
        else:
            text.append("No world changes\n", style="dim #5c6370")

        gained, lost = probe.binding_diff
        if gained or lost:
            text.append("\nBinding Changes:\n", style="bold #98c379")
            for bid in sorted(gained):
                text.append(f"  +{bid}\n", style="#98c379")
            for bid in sorted(lost):
                text.append(f"  -{bid}\n", style="#e06c75")

        if probe.matched_terminal:
            text.append(f"\nTerminal Match: {probe.matched_terminal.profile_id}\n", style="bold #e06c75")

        if probe.is_visited:
            text.append("\n(state already visited — not enqueued)\n", style="dim #5c6370")

        diff_widget.update(text)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None and event.item.name:
            probe = self._probes_by_index.get(event.item.name)
            if probe:
                self.show_diff(probe)
                # Switch to diff tab
                tabs = self.query_one("#action-tabs", TabbedContent)
                tabs.active = "tab-diff"


class SeedSelector(ModalScreen[str]):
    """Modal for selecting a BFS seed."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, seed_ids: list[str]) -> None:
        super().__init__()
        self.seed_ids = seed_ids

    def compose(self) -> ComposeResult:
        with Container(id="seed-modal"):
            yield Label("Select Seed", id="seed-modal-title", classes="panel-title")
            yield OptionList(
                *[Option(sid, id=sid) for sid in self.seed_ids],
                id="seed-options",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.prompt))

    def action_cancel(self) -> None:
        self.dismiss("")
