"""BFS Explorer TUI application."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.theme import Theme
from textual.timer import Timer
from textual.widgets import Footer, Static

from tau2.generators.depgraph.types import GraphContractSpec, SamplingRequestDoc

from .stepper import BFSStepper, BFSStepResult
from .widgets import ActionPanel, BFSTreePanel, SeedSelector, WorldStatePanel

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

WARM_DARK_THEME = Theme(
    name="warm-dark",
    primary="#e2c07c",
    secondary="#a89984",
    accent="#e06c75",
    warning="#d19a66",
    error="#e06c75",
    success="#98c379",
    background="#1a1a2e",
    surface="#16213e",
    panel="#16213e",
)


class BFSExplorerApp(App):
    """Interactive BFS sampling explorer for tau2 depgraph contracts."""

    TITLE = "tau2 BFS Explorer"

    CSS = """
    Screen {
        background: #1a1a2e;
        color: #eee8d5;
    }

    #header-bar {
        dock: top;
        height: 3;
        background: #16213e;
        color: #eee8d5;
        padding: 1 2;
        border-bottom: solid #e2c07c;
    }

    #main-layout {
        height: 1fr;
    }

    #tree-panel {
        width: 35%;
        border-right: solid #e2c07c;
        padding: 0 1;
    }

    #right-panels {
        width: 65%;
    }

    #world-panel {
        height: 50%;
        border-bottom: solid #3a3a5e;
        padding: 0 1;
        overflow-y: auto;
    }

    #action-panel {
        height: 50%;
        padding: 0 1;
    }

    .panel-title {
        color: #e2c07c;
        text-style: bold;
        padding: 0 0 0 0;
        margin: 0 0 0 0;
    }

    #world-table {
        height: 1fr;
    }

    #bindings-display {
        padding: 0 1;
        margin: 0 0 1 0;
    }

    #bfs-tree {
        height: 1fr;
    }

    #enabled-list, #disabled-list {
        height: 1fr;
    }

    #diff-scroll {
        height: 1fr;
        padding: 0 1;
    }

    #diff-content {
        padding: 0;
    }

    #seed-modal {
        width: 50;
        height: auto;
        max-height: 20;
        background: #16213e;
        border: solid #e2c07c;
        padding: 1 2;
    }

    #seed-modal-title {
        text-align: center;
        margin-bottom: 1;
    }

    #seed-options {
        height: auto;
        max-height: 14;
    }

    DataTable {
        background: #1a1a2e;
    }

    DataTable > .datatable--header {
        background: #16213e;
        color: #e2c07c;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #2a2a4e;
    }

    Tree {
        background: #1a1a2e;
    }

    Tree > .tree--cursor {
        background: #2a2a4e;
    }

    ListView {
        background: #1a1a2e;
    }

    ListView > .list-view--highlight {
        background: #2a2a4e;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 0;
    }

    OptionList {
        background: #1a1a2e;
    }

    Footer {
        background: #16213e;
    }

    SeedSelector {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("space", "step", "Step"),
        Binding("a", "toggle_auto", "Auto"),
        Binding("plus,equal", "speed_up", "+Speed", show=False),
        Binding("minus", "slow_down", "-Speed", show=False),
        Binding("r", "reset", "Reset"),
        Binding("s", "pick_seed", "Seed"),
        Binding("1", "focus_tree", "Tree", show=False),
        Binding("2", "focus_world", "World", show=False),
        Binding("3", "focus_actions", "Actions", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        contract: GraphContractSpec,
        request: SamplingRequestDoc,
    ) -> None:
        super().__init__()
        self.stepper = BFSStepper(contract, request)
        self._auto_timer: Timer | None = None
        self._auto_interval: float = 0.3
        self._current_node: BFSStepResult | None = None
        self.register_theme(WARM_DARK_THEME)
        self.theme = "warm-dark"

    def compose(self) -> ComposeResult:
        yield Static(id="header-bar")
        with Horizontal(id="main-layout"):
            yield BFSTreePanel(id="tree-panel")
            with Vertical(id="right-panels"):
                yield WorldStatePanel(id="world-panel")
                yield ActionPanel(id="action-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._update_header()
        # Auto-select first seed
        if self.stepper.seed_ids:
            self._start_seed(self.stepper.seed_ids[0])

    def _start_seed(self, seed_id: str) -> None:
        if self._auto_timer:
            self._auto_timer.stop()
            self._auto_timer = None

        root = self.stepper.select_seed(seed_id)
        tree_panel = self.query_one("#tree-panel", BFSTreePanel)
        tree_panel.reset(seed_id)
        self._show_node(root)
        self._update_header()

    def _show_node(self, result: BFSStepResult) -> None:
        self._current_node = result

        # Update tree
        tree_panel = self.query_one("#tree-panel", BFSTreePanel)
        tree_panel.add_step(result)

        # Get parent for diff display
        prev_world = None
        prev_bindings = None
        if result.parent_id is not None:
            parent = self.stepper.get_node(result.parent_id)
            if parent:
                prev_world = parent.world
                prev_bindings = parent.bindings

        # Update world state
        world_panel = self.query_one("#world-panel", WorldStatePanel)
        world_panel.update_state(result.world, result.bindings, prev_world, prev_bindings)

        # Update actions
        action_panel = self.query_one("#action-panel", ActionPanel)
        action_panel.update_probes(result.action_probes)

        self._update_header()

    def _update_header(self) -> None:
        header = self.query_one("#header-bar", Static)
        text = Text()
        text.append("tau2 BFS Explorer", style="bold #e2c07c")

        seed = self.stepper.current_seed
        if seed:
            text.append("  |  ", style="#5c6370")
            text.append(f"Seed: {seed.seed_id}", style="#61afef")

        text.append("  |  ", style="#5c6370")
        text.append(f"Nodes: {self.stepper.nodes_explored}", style="#eee8d5")
        text.append(f"  Q: {self.stepper.queue_size}", style="#a89984")
        text.append(f"  Visited: {self.stepper.visited_count}", style="#a89984")
        text.append(f"  Tasks: {self.stepper.tasks_found}", style="#98c379")

        if self._auto_timer:
            text.append(f"  AUTO ({self._auto_interval:.1f}s)", style="bold #e06c75")

        if self.stepper.is_complete:
            text.append("  COMPLETE", style="bold #98c379")

        header.update(text)

    # ---- Actions ----

    def action_step(self) -> None:
        result = self.stepper.step()
        if result:
            self._show_node(result)
        else:
            self._update_header()

    def action_toggle_auto(self) -> None:
        if self._auto_timer:
            self._auto_timer.stop()
            self._auto_timer = None
        else:
            self._auto_timer = self.set_interval(
                self._auto_interval, self._auto_step
            )
        self._update_header()

    def _auto_step(self) -> None:
        result = self.stepper.step()
        if result:
            self._show_node(result)
        else:
            if self._auto_timer:
                self._auto_timer.stop()
                self._auto_timer = None
            self._update_header()

    def action_speed_up(self) -> None:
        self._auto_interval = max(0.05, self._auto_interval * 0.6)
        if self._auto_timer:
            self._auto_timer.stop()
            self._auto_timer = self.set_interval(
                self._auto_interval, self._auto_step
            )
        self._update_header()

    def action_slow_down(self) -> None:
        self._auto_interval = min(5.0, self._auto_interval * 1.5)
        if self._auto_timer:
            self._auto_timer.stop()
            self._auto_timer = self.set_interval(
                self._auto_interval, self._auto_step
            )
        self._update_header()

    def action_reset(self) -> None:
        seed = self.stepper.current_seed
        if seed:
            self._start_seed(seed.seed_id)

    def action_pick_seed(self) -> None:
        def on_seed_selected(seed_id: str) -> None:
            if seed_id:
                self._start_seed(seed_id)

        self.push_screen(SeedSelector(self.stepper.seed_ids), on_seed_selected)

    def action_focus_tree(self) -> None:
        self.query_one("#bfs-tree").focus()

    def action_focus_world(self) -> None:
        self.query_one("#world-table").focus()

    def action_focus_actions(self) -> None:
        try:
            self.query_one("#enabled-list").focus()
        except Exception:
            pass

    # ---- Tree node selection ----

    def on_bfs_tree_panel_node_selected(self, event: BFSTreePanel.NodeSelected) -> None:
        node = self.stepper.get_node(event.node_id)
        if node:
            # Get parent for diff
            prev_world = None
            prev_bindings = None
            if node.parent_id is not None:
                parent = self.stepper.get_node(node.parent_id)
                if parent:
                    prev_world = parent.world
                    prev_bindings = parent.bindings

            self._current_node = node
            world_panel = self.query_one("#world-panel", WorldStatePanel)
            world_panel.update_state(node.world, node.bindings, prev_world, prev_bindings)
            action_panel = self.query_one("#action-panel", ActionPanel)
            action_panel.update_probes(node.action_probes)
