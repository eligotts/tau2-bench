"""Custom widgets for the BFS Explorer TUI."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from rich.text import Text as RichText
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Label,
    OptionList,
    Static,
    Tree,
)
from textual.widgets.option_list import Option
from textual.widgets.tree import TreeNode

from tau2.generators.depgraph.goal_capture import capture_goal_world, path_matches_capture
from tau2.generators.depgraph.types import TerminalProfileSpec

from .stepper import ActionProbe, BFSStepResult


def _short_path(path: str) -> str:
    """Shorten long paths: keep last two segments."""
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


# ---------------------------------------------------------------------------
# Graph panel — the main star
# ---------------------------------------------------------------------------


class GraphPanel(Container):
    """Full-width tree that grows as BFS expands."""

    class NodeSelected(Message):
        def __init__(self, node_id: int) -> None:
            super().__init__()
            self.node_id = node_id

    def compose(self) -> ComposeResult:
        tree: Tree[int] = Tree("BFS", id="bfs-tree")
        tree.root.expand()
        tree.guide_depth = 3
        yield tree

    @property
    def tree(self) -> Tree[int]:
        return self.query_one("#bfs-tree", Tree)

    def reset(self, seed_id: str) -> None:
        tree = self.tree
        tree.clear()
        label = Text()
        label.append(" SEED ", style="bold reverse #61afef")
        label.append(f" {seed_id}", style="bold #61afef")
        tree.root.set_label(label)
        tree.root.data = 0
        tree.root.expand()
        self._node_map: dict[int, TreeNode[int]] = {0: tree.root}
        self._base_labels: dict[int, Text] = {0: label.copy()}
        self._prev_bfs_source_id: int | None = None
        self._programmatic_select: int | None = None
        self._marked_node_id: int | None = None

    def _build_label(self, result: BFSStepResult) -> Text:
        """Build the label for a node."""
        action_label = result.action_taken or "?"
        if action_label.startswith("action_"):
            action_label = action_label[7:]

        label = Text()

        # Depth badge
        label.append(f" d{result.depth} ", style="bold reverse #3a3a5e")
        label.append(" ", style="")

        # Terminal badge
        if result.terminal_match is not None:
            label.append(" GOAL ", style="bold reverse #e06c75")
            label.append(" ", style="")

        # Action name
        label.append(action_label, style="bold #eee8d5")

        # Child count summary [enabled/stutter/disabled]
        enabled = sum(
            1 for p in result.action_probes
            if p.enabled and not p.is_stutter and not p.is_visited
        )
        disabled = sum(1 for p in result.action_probes if not p.enabled)
        stutter = sum(
            1 for p in result.action_probes
            if p.enabled and (p.is_stutter or p.is_visited)
        )

        label.append(f"  [{enabled}", style="#98c379")
        if stutter:
            label.append(f"/{stutter}", style="#5c6370")
        label.append(f"/{disabled}]", style="#d19a66")

        return label

    def add_step(self, result: BFSStepResult) -> None:
        """Add a node to the tree."""
        if not hasattr(self, "_node_map"):
            self.reset("?")

        if result.node_id == 0:
            return

        parent_tree_node = self._node_map.get(result.parent_id)
        if parent_tree_node is None:
            parent_tree_node = self.tree.root

        label = self._build_label(result)
        self._base_labels[result.node_id] = label.copy()
        node = parent_tree_node.add(label, data=result.node_id)
        node.expand()
        self._node_map[result.node_id] = node

    def select_node(self, node_id: int) -> None:
        """Move the tree cursor to a node (suppressing re-entrant events)."""
        tree_node = self._node_map.get(node_id)
        if tree_node is None:
            return
        self._ensure_visible(tree_node)
        self._programmatic_select = node_id
        self.tree.select_node(tree_node)

    def mark_current(self, node_id: int | None) -> None:
        """Add a visible marker to the current node label, restore the previous one."""
        # Restore previous
        if self._marked_node_id is not None and self._marked_node_id != node_id:
            prev_node = self._node_map.get(self._marked_node_id)
            prev_label = self._base_labels.get(self._marked_node_id)
            if prev_node is not None and prev_label is not None:
                prev_node.set_label(prev_label)

        self._marked_node_id = node_id

        # Mark new
        if node_id is not None:
            tree_node = self._node_map.get(node_id)
            base_label = self._base_labels.get(node_id)
            if tree_node is not None and base_label is not None:
                marked = Text()
                marked.append("► ", style="bold #61afef")
                marked.append_text(base_label)
                tree_node.set_label(marked)

    def focus_bfs_source(self, source_parent_id: int | None) -> None:
        """Auto-collapse previous BFS source's children and expand the new one."""
        prev = self._prev_bfs_source_id
        self._prev_bfs_source_id = source_parent_id

        # Collapse previous source's children (but not root)
        if prev is not None and prev != source_parent_id and prev != 0:
            prev_node = self._node_map.get(prev)
            if prev_node is not None:
                prev_node.collapse()

        # Expand new source and ensure it's visible
        if source_parent_id is not None:
            new_node = self._node_map.get(source_parent_id)
            if new_node is not None:
                new_node.expand()
                self._ensure_visible(new_node)

    def _ensure_visible(self, node: TreeNode[int]) -> None:
        """Expand all ancestors so this node is visible."""
        parent = node.parent
        while parent is not None:
            parent.expand()
            parent = parent.parent

    def on_tree_node_selected(self, event: Tree.NodeSelected[int]) -> None:
        if event.node.data is not None:
            if event.node.data == self._programmatic_select:
                self._programmatic_select = None
                return
            self._programmatic_select = None
            self.post_message(self.NodeSelected(event.node.data))


# ---------------------------------------------------------------------------
# Detail panel — shows on node click
# ---------------------------------------------------------------------------


class DetailPanel(Container):
    """Compact side panel showing world state + action details for selected node."""

    def compose(self) -> ComposeResult:
        yield VerticalScroll(
            Static("Click a node to inspect.", id="detail-content"),
            id="detail-scroll",
        )

    def show_node(
        self,
        result: BFSStepResult,
        prev_world: dict[str, Any] | None = None,
        prev_bindings: frozenset[str] | None = None,
    ) -> None:
        widget = self.query_one("#detail-content", Static)
        text = Text()

        # Header
        action = result.action_taken or "(root)"
        text.append(f"Node n{result.node_id}", style="bold #e2c07c")
        text.append(f"  depth {result.depth}", style="#a89984")
        text.append(f"\nvia: {action}\n", style="#61afef")

        if result.terminal_match:
            text.append(
                f"TERMINAL: {result.terminal_match.profile_id}\n",
                style="bold #e06c75",
            )

        # World state — only show changed fields first, then rest
        text.append("\n--- World State ---\n", style="bold #e2c07c")

        changed_paths: list[str] = []
        unchanged_paths: list[str] = []
        for path in sorted(result.world.keys()):
            if prev_world is not None and prev_world.get(path) != result.world[path]:
                changed_paths.append(path)
            else:
                unchanged_paths.append(path)

        if changed_paths:
            for path in changed_paths:
                val = result.world[path]
                text.append(f"  {_short_path(path)}: ", style="bold #e5c07b")
                if prev_world is not None:
                    text.append(
                        f"{_format_value(prev_world.get(path))}",
                        style="dim strike #a89984",
                    )
                    text.append(" -> ", style="#5c6370")
                text.append(f"{_format_value(val)}\n", style="bold #e5c07b")

        if unchanged_paths:
            if changed_paths:
                text.append("\n", style="")
            for path in unchanged_paths:
                val = result.world[path]
                text.append(f"  {_short_path(path)}: ", style="#5c6370")
                text.append(f"{_format_value(val)}\n", style="#a89984")

        # Bindings
        text.append("\n--- Bindings ---\n", style="bold #e2c07c")
        if result.bindings:
            gained = result.bindings - (prev_bindings or frozenset())
            kept = result.bindings & (prev_bindings or frozenset())
            for bid in sorted(gained):
                text.append(f"  +{bid}\n", style="bold #98c379")
            for bid in sorted(kept):
                text.append(f"  {bid}\n", style="#a89984")
            if prev_bindings:
                lost = prev_bindings - result.bindings
                for bid in sorted(lost):
                    text.append(f"  -{bid}\n", style="strike #e06c75")
        else:
            text.append("  (none)\n", style="dim #5c6370")

        # Actions summary
        text.append("\n--- Actions ---\n", style="bold #e2c07c")
        enabled_probes = [
            p for p in result.action_probes
            if p.enabled and not p.is_stutter and not p.is_visited
        ]
        stutter_probes = [
            p for p in result.action_probes
            if p.enabled and (p.is_stutter or p.is_visited)
        ]
        disabled_probes = [p for p in result.action_probes if not p.enabled]

        if enabled_probes:
            text.append(f"  Enabled ({len(enabled_probes)}):\n", style="#98c379")
            for p in enabled_probes:
                aid = p.action.action_id
                short = aid[7:] if aid.startswith("action_") else aid
                text.append(f"    ", style="")
                if p.matched_terminal:
                    text.append("* ", style="bold #e06c75")
                else:
                    text.append("+ ", style="#98c379")
                text.append(f"{short}", style="#eee8d5")
                text.append(f" [{p.action.classification}]", style="dim #a89984")
                if p.world_diff:
                    text.append(f" ({len(p.world_diff)} changes)", style="dim #e5c07b")
                text.append("\n", style="")

                # Show diff inline
                for path, old, new in p.world_diff:
                    text.append(f"      {_short_path(path)}: ", style="dim #5c6370")
                    text.append(f"{_format_value(old)}", style="dim #a89984")
                    text.append(" -> ", style="dim #5c6370")
                    text.append(f"{_format_value(new)}\n", style="#e5c07b")
                g, l = p.binding_diff
                for bid in sorted(g):
                    text.append(f"      +{bid}\n", style="dim #98c379")
                for bid in sorted(l):
                    text.append(f"      -{bid}\n", style="dim #e06c75")

        if stutter_probes:
            text.append(
                f"\n  Stutter/Visited ({len(stutter_probes)}):\n", style="dim #5c6370"
            )
            for p in stutter_probes:
                aid = p.action.action_id
                short = aid[7:] if aid.startswith("action_") else aid
                tag = "stutter" if p.is_stutter else "visited"
                text.append(f"    ~ {short} ({tag})\n", style="dim #5c6370")

        if disabled_probes:
            text.append(
                f"\n  Disabled ({len(disabled_probes)}):\n", style="dim #d19a66"
            )
            for p in disabled_probes:
                aid = p.action.action_id
                short = aid[7:] if aid.startswith("action_") else aid
                text.append(f"    x {short}", style="dim #d19a66")
                # Show first failure reason
                if p.failed_world_predicates:
                    pred, actual = p.failed_world_predicates[0]
                    text.append(
                        f"  {_short_path(pred.path)}={_format_value(actual)}"
                        f" need {pred.op} {_format_value(pred.value)}",
                        style="dim #5c6370",
                    )
                elif p.failed_binding_predicates:
                    pred, actual = p.failed_binding_predicates[0]
                    state = "have" if actual else "missing"
                    text.append(f"  {pred.binding_id} {state}", style="dim #5c6370")
                text.append("\n", style="")

        # Plan trace
        if result.plan:
            text.append("\n--- Path from Root ---\n", style="bold #e2c07c")
            for i, action_id in enumerate(result.plan):
                short = action_id[7:] if action_id.startswith("action_") else action_id
                text.append(f"  {i + 1}. {short}\n", style="#a89984")

        widget.update(text)

    def clear_detail(self) -> None:
        widget = self.query_one("#detail-content", Static)
        widget.update("Click a node to inspect.")


# ---------------------------------------------------------------------------
# Seed selector modal
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Goal summary modal — shown after "Go" completes
# ---------------------------------------------------------------------------


class GoalSummary(ModalScreen[int | None]):
    """Modal showing all goal paths found by BFS with world diff and env assertions."""

    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(
        self,
        goal_nodes: list[BFSStepResult],
        start_world: dict[str, Any],
        goal_capture_paths: list[str],
        projected_paths: list[str],
    ) -> None:
        super().__init__()
        self.goal_nodes = goal_nodes
        self.start_world = start_world
        self.goal_capture_paths = goal_capture_paths
        self.projected_paths = projected_paths

    def compose(self) -> ComposeResult:
        with Container(id="goal-modal"):
            yield Label(
                f"Goal Paths ({len(self.goal_nodes)} found)",
                id="goal-modal-title",
                classes="panel-title",
            )
            if not self.goal_nodes:
                yield Static("No goal states found.", id="goal-empty")
            else:
                with Horizontal(id="goal-layout"):
                    options: list[Option] = []
                    for i, node in enumerate(self.goal_nodes):
                        profile_id = (
                            node.terminal_match.profile_id
                            if node.terminal_match
                            else "?"
                        )
                        label = Text()
                        label.append(f" {profile_id} ", style="bold reverse #e06c75")
                        label.append(f" d{node.depth} ", style="dim #a89984")
                        label.append(
                            f" path {i + 1}", style="#eee8d5"
                        )
                        options.append(Option(label, id=f"goal_{node.node_id}"))
                    yield OptionList(*options, id="goal-options")
                    yield VerticalScroll(
                        Static(
                            "Select a goal to see details.",
                            id="goal-detail",
                        ),
                        id="goal-detail-scroll",
                    )

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        opt_id = str(event.option.id)
        if opt_id.startswith("goal_"):
            node_id = int(opt_id[5:])
            node = next((n for n in self.goal_nodes if n.node_id == node_id), None)
            if node:
                self._show_goal_detail(node)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        opt_id = str(event.option.id)
        if opt_id.startswith("goal_"):
            self.dismiss(int(opt_id[5:]))
        else:
            self.dismiss(None)

    def _show_goal_detail(self, node: BFSStepResult) -> None:
        widget = self.query_one("#goal-detail", Static)
        text = Text()

        profile_id = (
            node.terminal_match.profile_id if node.terminal_match else "?"
        )
        text.append(f" {profile_id} ", style="bold reverse #e06c75")
        text.append(f"  depth {node.depth}  ", style="dim #a89984")
        text.append(f"node n{node.node_id}\n\n", style="#a89984")

        # Action path
        text.append("Action Path\n", style="bold #e2c07c")
        for i, action_id in enumerate(node.plan):
            short = action_id[7:] if action_id.startswith("action_") else action_id
            text.append(f"  {i + 1}. ", style="dim #a89984")
            text.append(f"{short}\n", style="#eee8d5")

        # World diff: start vs end
        text.append("\nWorld Diff (start -> end)\n", style="bold #e2c07c")
        all_paths = sorted(set(self.start_world.keys()) | set(node.world.keys()))
        has_diff = False
        for path in all_paths:
            old_val = self.start_world.get(path)
            new_val = node.world.get(path)
            if old_val != new_val:
                has_diff = True
                text.append(f"  {_short_path(path)}: ", style="#a89984")
                text.append(f"{_format_value(old_val)}", style="dim strike #a89984")
                text.append(" -> ", style="#5c6370")
                text.append(f"{_format_value(new_val)}\n", style="bold #e5c07b")
        if not has_diff:
            text.append("  (no changes)\n", style="dim #5c6370")

        # Goal capture / env assertions
        text.append("\nEnv Assertions (goal capture)\n", style="bold #e2c07c")
        if self.goal_capture_paths:
            captured = capture_goal_world(
                start_world=self.start_world,
                end_world=node.world,
                capture_paths=self.goal_capture_paths,
                projected_paths=self.projected_paths,
            )
            if captured:
                for pred in captured:
                    path = pred.path
                    leaf = path.rsplit(".", 1)[-1] if "." in path else path
                    env_type = "assistant" if path.startswith("agent.") else "user"
                    text.append(f"  [{env_type}] ", style="dim #61afef")
                    text.append(f"assert_{leaf}", style="bold #98c379")
                    text.append(f"(expected=", style="#a89984")
                    text.append(f"{_format_value(pred.value)}", style="bold #e5c07b")
                    text.append(")\n", style="#a89984")
                    text.append(f"    {path}\n", style="dim #5c6370")
            else:
                text.append("  (no captured changes)\n", style="dim #5c6370")
        else:
            text.append("  (no goal_capture_paths configured)\n", style="dim #d19a66")

        # Bindings at goal
        text.append("\nBindings at Goal\n", style="bold #e2c07c")
        if node.bindings:
            for bid in sorted(node.bindings):
                text.append(f"  {bid}\n", style="#98c379")
        else:
            text.append("  (none)\n", style="dim #5c6370")

        widget.update(text)

    def action_cancel(self) -> None:
        self.dismiss(None)
