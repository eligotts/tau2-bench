"""BFS Explorer TUI application."""

from __future__ import annotations

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.theme import Theme
from textual.timer import Timer
from textual.widgets import Footer, Static

from tau2.generators.depgraph.goal_capture import capture_goal_world
from tau2.generators.depgraph.types import GraphContractSpec, SamplingRequestDoc

from .stepper import BFSStepper, BFSStepResult
from .widgets import DetailPanel, GoalSummary, GraphPanel, SeedSelector

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
    """Interactive BFS sampling explorer — watch the graph grow."""

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

    #graph-panel {
        width: 1fr;
        min-width: 40;
    }

    #bfs-tree {
        height: 1fr;
        padding: 0 1;
    }

    Tree {
        background: #1a1a2e;
        scrollbar-size: 1 1;
    }

    Tree > .tree--cursor {
        background: #2a2a4e;
    }

    Tree > .tree--highlight {
        background: #2a2a4e;
    }

    #detail-panel {
        width: 50;
        border-left: solid #3a3a5e;
        display: block;
    }

    #detail-panel.hidden {
        display: none;
    }

    #detail-scroll {
        height: 1fr;
        padding: 0 1;
    }

    #detail-content {
        padding: 0;
    }

    .panel-title {
        color: #e2c07c;
        text-style: bold;
    }

    #seed-modal {
        width: 60;
        height: auto;
        max-height: 24;
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
        max-height: 18;
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

    GoalSummary {
        align: center middle;
    }

    #goal-modal {
        width: 120;
        height: 40;
        background: #16213e;
        border: solid #98c379;
        padding: 1 2;
    }

    #goal-modal-title {
        text-align: center;
        margin-bottom: 1;
        color: #98c379;
    }

    #goal-layout {
        height: 1fr;
    }

    #goal-options {
        width: 35;
        height: 1fr;
        border-right: solid #3a3a5e;
    }

    #goal-detail-scroll {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }

    #goal-detail {
        padding: 0;
    }

    #goal-empty {
        text-align: center;
        color: #d19a66;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("space,enter", "next", "Next"),
        Binding("g", "go", "Go"),
        Binding("a", "toggle_auto", "Auto"),
        Binding("plus,equal", "speed_up", "+Spd", show=False),
        Binding("minus", "slow_down", "-Spd", show=False),
        Binding("r", "reset", "Reset"),
        Binding("s", "pick_seed", "Seed"),
        Binding("d", "toggle_detail", "Detail"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        contract: GraphContractSpec,
        request: SamplingRequestDoc,
    ) -> None:
        super().__init__()
        self.request = request
        self.stepper = BFSStepper(contract, request)
        self._auto_timer: Timer | None = None
        self._auto_interval: float = 0.2
        self._current_node: BFSStepResult | None = None
        self._detail_visible: bool = True
        self._go_mode: bool = False
        self._goal_nodes: list[BFSStepResult] = []
        self._seen_goal_sigs: set[tuple] = set()
        self.register_theme(WARM_DARK_THEME)
        self.theme = "warm-dark"

    def compose(self) -> ComposeResult:
        yield Static(id="header-bar")
        with Horizontal(id="main-layout"):
            yield GraphPanel(id="graph-panel")
            yield DetailPanel(id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._update_header()
        if self.stepper.seed_ids:
            self._start_seed(self.stepper.seed_ids[0])

    # ---- Core ----

    def _start_seed(self, seed_id: str) -> None:
        if self._auto_timer:
            self._auto_timer.stop()
            self._auto_timer = None
        self._go_mode = False
        self._goal_nodes = []
        self._seen_goal_sigs = set()

        root = self.stepper.select_seed(seed_id)
        graph = self.query_one("#graph-panel", GraphPanel)
        graph.reset(seed_id)
        self._select_node(root)
        self._update_header()

    def _select_node(self, result: BFSStepResult, *, is_bfs_step: bool = False) -> None:
        self._current_node = result

        # Show detail
        prev_world = None
        prev_bindings = None
        if result.parent_id is not None:
            parent = self.stepper.get_node(result.parent_id)
            if parent:
                prev_world = parent.world
                prev_bindings = parent.bindings

        detail = self.query_one("#detail-panel", DetailPanel)
        detail.show_node(result, prev_world, prev_bindings)

        # Update tree marker and auto-collapse/expand on BFS steps
        self._update_markers(is_bfs_step=is_bfs_step)

    def _update_header(self) -> None:
        header = self.query_one("#header-bar", Static)
        text = Text()
        text.append(" BFS EXPLORER ", style="bold reverse #e2c07c")

        seed = self.stepper.current_seed
        if seed:
            text.append("  ", style="")
            text.append(seed.seed_id, style="bold #61afef")
            text.append(
                f"  d{seed.min_depth}-{seed.max_depth}", style="dim #a89984"
            )

        text.append("  |  ", style="#3a3a5e")
        text.append(f"{self.stepper.nodes_explored}", style="bold #eee8d5")
        text.append(" nodes  ", style="dim #a89984")
        text.append(f"{self.stepper.queue_size}", style="#eee8d5")
        text.append(" queued  ", style="dim #a89984")
        text.append(f"{self.stepper.tasks_found}", style="bold #98c379")
        text.append(" goals", style="dim #a89984")

        if self._auto_timer:
            text.append("  ", style="")
            text.append(
                f" AUTO {self._auto_interval:.1f}s ",
                style="bold reverse #e06c75",
            )

        if self.stepper.is_complete:
            text.append("  ", style="")
            text.append(" DONE ", style="bold reverse #98c379")

        header.update(text)

    def _update_markers(self, is_bfs_step: bool = False) -> None:
        graph = self.query_one("#graph-panel", GraphPanel)

        # Mark the current node with a visible indicator
        if self._current_node is not None:
            graph.mark_current(self._current_node.node_id)

        # On BFS step: collapse previous source, expand new source
        if is_bfs_step and self._current_node is not None:
            graph.focus_bfs_source(self._current_node.parent_id)

    def _try_collect_goal(self, result: BFSStepResult) -> None:
        """Dedup and collect a terminal node, matching the real sampler's signature logic."""
        if result.terminal_match is None:
            return

        root = self.stepper.get_node(0)
        if root is None:
            return

        seed = self.stepper.current_seed
        goal_capture_paths = self.request.goal_capture_paths_for_seed(seed) if seed else []
        projected_paths = list(self.stepper.contract.projection_fields)

        captured = capture_goal_world(
            start_world=root.world,
            end_world=result.world,
            capture_paths=goal_capture_paths,
            projected_paths=projected_paths,
        )

        # Signature: (captured_goal, required_actions, profile_id)
        goal_part = tuple(sorted((p.path, repr(p.value)) for p in captured))
        required_actions = tuple(dict.fromkeys(result.plan))  # ordered unique
        sig = (goal_part, required_actions, result.terminal_match.profile_id)

        if sig not in self._seen_goal_sigs:
            self._seen_goal_sigs.add(sig)
            self._goal_nodes.append(result)

    # ---- Actions ----

    def action_next(self) -> None:
        """Expand next node in BFS queue — all eligible actions fire at once."""
        result = self.stepper.step()
        if result:
            graph = self.query_one("#graph-panel", GraphPanel)
            graph.add_step(result)
            self._select_node(result, is_bfs_step=True)
            self._try_collect_goal(result)
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
            graph = self.query_one("#graph-panel", GraphPanel)
            graph.add_step(result)
            self._select_node(result, is_bfs_step=True)
            self._try_collect_goal(result)
        else:
            if self._auto_timer:
                self._auto_timer.stop()
                self._auto_timer = None
            if self._go_mode:
                self._go_mode = False
                self._show_goal_summary()
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

    def action_toggle_detail(self) -> None:
        panel = self.query_one("#detail-panel", DetailPanel)
        self._detail_visible = not self._detail_visible
        if self._detail_visible:
            panel.remove_class("hidden")
        else:
            panel.add_class("hidden")

    def action_go(self) -> None:
        """Run BFS to completion, then show goal summary."""
        if self._auto_timer:
            self._auto_timer.stop()
            self._auto_timer = None
        self._go_mode = True
        self._auto_timer = self.set_interval(0.02, self._auto_step)
        self._update_header()

    def _show_goal_summary(self) -> None:
        def on_goal_selected(node_id: int | None) -> None:
            if node_id is not None:
                node = self.stepper.get_node(node_id)
                if node:
                    graph = self.query_one("#graph-panel", GraphPanel)
                    graph.mark_current(node_id)
                    graph.focus_bfs_source(node.parent_id)
                    self._select_node(node)

        # Get start world from root node
        root = self.stepper.get_node(0)
        start_world = root.world if root else {}

        # Get goal capture paths
        seed = self.stepper.current_seed
        goal_capture_paths = self.request.goal_capture_paths_for_seed(seed) if seed else []
        projected_paths = list(self.stepper.contract.projection_fields)

        self.push_screen(
            GoalSummary(
                self._goal_nodes,
                start_world=start_world,
                goal_capture_paths=goal_capture_paths,
                projected_paths=projected_paths,
            ),
            on_goal_selected,
        )

    # ---- Tree click ----

    def on_graph_panel_node_selected(self, event: GraphPanel.NodeSelected) -> None:
        node = self.stepper.get_node(event.node_id)
        if node is None:
            return
        try:
            self._select_node(node)
        except Exception:
            pass  # Can fire during teardown
