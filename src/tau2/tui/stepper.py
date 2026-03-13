"""Instrumented BFS stepper for interactive exploration of the depgraph sampler."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from tau2.generators.depgraph.preflight import (
    terminal_profile_map,
    world_matches_terminal_profile,
)
from tau2.generators.depgraph.semantics import (
    apply_action,
    binding_source_satisfiable,
    index_binding_sources,
    is_action_enabled,
    materialize_world,
    predicate_holds,
    world_state_key,
)
from tau2.generators.depgraph.types import (
    ActionContract,
    BindingPredicateSpec,
    BindingSourceSpec,
    GraphContractSpec,
    SamplingRequestDoc,
    SamplingSeedSpec,
    TerminalProfileSpec,
    WorldPredicateSpec,
)


@dataclass
class ActionProbe:
    """Diagnostic result of probing one action against a BFS node."""

    action: ActionContract
    enabled: bool
    # Why disabled (empty if enabled)
    failed_world_predicates: list[tuple[WorldPredicateSpec, Any]] = field(
        default_factory=list
    )
    failed_binding_predicates: list[tuple[BindingPredicateSpec, bool]] = field(
        default_factory=list
    )
    knowledge_source_ok: bool = True
    # If enabled and applied:
    next_world: dict[str, Any] | None = None
    next_bindings: frozenset[str] | None = None
    world_diff: list[tuple[str, Any, Any]] = field(default_factory=list)  # (path, old, new)
    binding_diff: tuple[set[str], set[str]] = field(
        default_factory=lambda: (set(), set())
    )  # (gained, lost)
    is_stutter: bool = False
    is_visited: bool = False
    matched_terminal: TerminalProfileSpec | None = None


@dataclass
class BFSStepResult:
    """One step of BFS expansion: a node popped from the queue with full diagnostics."""

    node_id: int
    parent_id: int | None
    depth: int
    action_taken: str | None  # action_id that produced this node (None for root)
    world: dict[str, Any]
    bindings: frozenset[str]
    plan: list[str]
    action_probes: list[ActionProbe]
    children_added: list[int]
    terminal_match: TerminalProfileSpec | None


@dataclass
class _QueueEntry:
    node_id: int
    parent_id: int | None
    action_taken: str | None
    world: dict[str, Any]
    bindings: frozenset[str]
    plan: list[str]


class BFSStepper:
    """Explicit state-machine wrapper around the depgraph BFS sampler."""

    def __init__(
        self,
        contract: GraphContractSpec,
        request: SamplingRequestDoc,
    ) -> None:
        self.contract = contract
        self.request = request
        self.binding_sources_by_id = index_binding_sources(contract.bindings)
        self.terminal_profiles_by_id = terminal_profile_map(request.terminal_profiles)

        # Per-seed state
        self._queue: deque[_QueueEntry] = deque()
        self._visited: set[tuple[tuple[tuple[str, Any], ...], frozenset[str]]] = set()
        self._nodes: list[BFSStepResult] = []
        self._next_node_id: int = 0
        self._current_seed: SamplingSeedSpec | None = None
        self._allowed_terminal_profiles: list[TerminalProfileSpec] = []
        self._tasks_found: int = 0

    @property
    def seed_ids(self) -> list[str]:
        return [seed.seed_id for seed in self.request.seeds]

    @property
    def current_seed(self) -> SamplingSeedSpec | None:
        return self._current_seed

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def visited_count(self) -> int:
        return len(self._visited)

    @property
    def nodes_explored(self) -> int:
        return len(self._nodes)

    @property
    def tasks_found(self) -> int:
        return self._tasks_found

    @property
    def is_complete(self) -> bool:
        return len(self._queue) == 0 and len(self._nodes) > 0

    @property
    def peek_next_id(self) -> int | None:
        """Return the node_id of the next entry that step() will process."""
        if not self._queue:
            return None
        return self._queue[0].node_id

    def get_node(self, node_id: int) -> BFSStepResult | None:
        if 0 <= node_id < len(self._nodes):
            return self._nodes[node_id]
        return None

    def select_seed(self, seed_id: str) -> BFSStepResult:
        """Initialize BFS from a seed. Returns the root node step result."""
        seed = next(s for s in self.request.seeds if s.seed_id == seed_id)
        self._current_seed = seed
        self._allowed_terminal_profiles = [
            self.terminal_profiles_by_id[pid] for pid in seed.allowed_terminal_profiles
        ]

        start_world, issues = materialize_world(
            seed.start_world, sync_rules=self.contract.sync_rules
        )
        if issues:
            raise ValueError(f"Seed '{seed_id}' materialization failed: {issues}")

        start_bindings = frozenset(seed.start_bindings)

        # Reset state
        self._queue.clear()
        self._visited.clear()
        self._nodes.clear()
        self._next_node_id = 0
        self._tasks_found = 0

        root_id = self._alloc_id()
        state_key = (world_state_key(start_world), start_bindings)
        self._visited.add(state_key)

        # Probe all actions for the root
        probes = self._probe_all_actions(start_world, start_bindings)

        # Check terminal match for root
        terminal_match = self._check_terminal(start_world)

        root_result = BFSStepResult(
            node_id=root_id,
            parent_id=None,
            depth=0,
            action_taken=None,
            world=start_world,
            bindings=start_bindings,
            plan=[],
            action_probes=probes,
            children_added=[],
            terminal_match=terminal_match,
        )
        self._nodes.append(root_result)

        # Enqueue children from enabled, non-stutter, non-visited probes
        if terminal_match is None:
            children = self._enqueue_children(root_id, start_world, start_bindings, [], probes)
            root_result.children_added = children

        if terminal_match is not None:
            self._tasks_found += 1

        return root_result

    def step(self) -> BFSStepResult | None:
        """Process next node from BFS queue. Returns None if queue is empty."""
        if not self._queue:
            return None

        entry = self._queue.popleft()
        seed = self._current_seed
        assert seed is not None

        if len(entry.plan) >= seed.max_depth:
            # Depth limit reached, skip but still record as explored
            probes = self._probe_all_actions(entry.world, entry.bindings)
            terminal_match = self._check_terminal(entry.world)
            result = BFSStepResult(
                node_id=entry.node_id,
                parent_id=entry.parent_id,
                depth=len(entry.plan),
                action_taken=entry.action_taken,
                world=entry.world,
                bindings=entry.bindings,
                plan=entry.plan,
                action_probes=probes,
                children_added=[],
                terminal_match=terminal_match,
            )
            self._nodes.append(result)
            if terminal_match is not None:
                self._tasks_found += 1
            return result

        probes = self._probe_all_actions(entry.world, entry.bindings)
        terminal_match = self._check_terminal(entry.world)

        result = BFSStepResult(
            node_id=entry.node_id,
            parent_id=entry.parent_id,
            depth=len(entry.plan),
            action_taken=entry.action_taken,
            world=entry.world,
            bindings=entry.bindings,
            plan=entry.plan,
            action_probes=probes,
            children_added=[],
            terminal_match=terminal_match,
        )
        self._nodes.append(result)

        if terminal_match is not None:
            self._tasks_found += 1
            # Don't expand children of terminal nodes (matches sampler behavior)
        else:
            children = self._enqueue_children(
                entry.node_id, entry.world, entry.bindings, entry.plan, probes
            )
            result.children_added = children

        return result

    def _alloc_id(self) -> int:
        nid = self._next_node_id
        self._next_node_id += 1
        return nid

    def _check_terminal(self, world: dict[str, Any]) -> TerminalProfileSpec | None:
        for profile in self._allowed_terminal_profiles:
            if world_matches_terminal_profile(world, profile):
                return profile
        return None

    def _probe_all_actions(
        self,
        world: dict[str, Any],
        bindings: frozenset[str],
    ) -> list[ActionProbe]:
        probes: list[ActionProbe] = []
        for action in self.contract.actions:
            probe = self._probe_one_action(action, world, bindings)
            probes.append(probe)
        return probes

    def _probe_one_action(
        self,
        action: ActionContract,
        world: dict[str, Any],
        bindings: frozenset[str],
    ) -> ActionProbe:
        # Check world predicates individually
        failed_world: list[tuple[WorldPredicateSpec, Any]] = []
        for pred in action.requires_world:
            if not predicate_holds(pred, world):
                failed_world.append((pred, world.get(pred.path)))

        # Check binding predicates individually
        failed_bindings: list[tuple[BindingPredicateSpec, bool]] = []
        for pred in action.requires_bindings:
            is_acquired = pred.binding_id in bindings
            if pred.acquired and not is_acquired:
                failed_bindings.append((pred, is_acquired))
            elif not pred.acquired and is_acquired:
                failed_bindings.append((pred, is_acquired))

        # Check knowledge source
        knowledge_ok = True
        if action.classification == "knowledge-only":
            if not action.effects_bindings:
                knowledge_ok = False
            else:
                for binding_id in action.effects_bindings:
                    if binding_id in bindings:
                        knowledge_ok = False
                        break
                    sources = self.binding_sources_by_id.get(binding_id, [])
                    tool_sources = [s for s in sources if s.source_tool == action.tool_name]
                    candidates = tool_sources if tool_sources else sources
                    if not any(binding_source_satisfiable(s, world) for s in candidates):
                        knowledge_ok = False
                        break

        enabled = (not failed_world) and (not failed_bindings) and knowledge_ok

        if not enabled:
            return ActionProbe(
                action=action,
                enabled=False,
                failed_world_predicates=failed_world,
                failed_binding_predicates=failed_bindings,
                knowledge_source_ok=knowledge_ok,
            )

        # Apply action to get next state
        next_world, next_bindings = apply_action(
            action,
            world,
            bindings,
            sync_rules=self.contract.sync_rules,
            binding_specs=self.contract.bindings,
        )

        # Compute diffs
        world_diff: list[tuple[str, Any, Any]] = []
        all_paths = set(world.keys()) | set(next_world.keys())
        for path in sorted(all_paths):
            old_val = world.get(path)
            new_val = next_world.get(path)
            if old_val != new_val:
                world_diff.append((path, old_val, new_val))

        gained = set(next_bindings) - set(bindings)
        lost = set(bindings) - set(next_bindings)

        is_stutter = next_world == world and next_bindings == bindings

        # Check if visited
        state_key = (world_state_key(next_world), next_bindings)
        is_visited = state_key in self._visited

        # Check terminal match
        matched_terminal = self._check_terminal(next_world) if not is_stutter else None

        return ActionProbe(
            action=action,
            enabled=True,
            knowledge_source_ok=True,
            next_world=next_world,
            next_bindings=next_bindings,
            world_diff=world_diff,
            binding_diff=(gained, lost),
            is_stutter=is_stutter,
            is_visited=is_visited,
            matched_terminal=matched_terminal,
        )

    def _enqueue_children(
        self,
        parent_id: int,
        world: dict[str, Any],
        bindings: frozenset[str],
        plan: list[str],
        probes: list[ActionProbe],
    ) -> list[int]:
        children: list[int] = []
        for probe in probes:
            if not probe.enabled or probe.is_stutter or probe.is_visited:
                continue
            assert probe.next_world is not None
            assert probe.next_bindings is not None

            state_key = (world_state_key(probe.next_world), probe.next_bindings)
            self._visited.add(state_key)

            child_id = self._alloc_id()
            next_plan = plan + [probe.action.action_id]
            self._queue.append(
                _QueueEntry(
                    node_id=child_id,
                    parent_id=parent_id,
                    action_taken=probe.action.action_id,
                    world=probe.next_world,
                    bindings=probe.next_bindings,
                    plan=next_plan,
                )
            )
            children.append(child_id)
        return children
