"""State-level SAT solver for dependency-graph task preflight."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from tau2.generators.depgraph.semantics import (
    apply_action,
    index_binding_sources,
    is_action_enabled,
    materialize_world,
    predicate_holds,
    world_state_key,
)
from tau2.generators.depgraph.types import (
    ActionContract,
    BindingSourceSpec,
    SyncRuleSpec,
    WorldEffectSpec,
    WorldPredicateSpec,
)


@dataclass
class SearchResult:
    """Solver result for one task query."""

    sat: bool
    plan: list[str]
    explored_states: int
    pruned_states: int = 0
    end_world: dict[str, Any] | None = None
    end_bindings: frozenset[str] | None = None
    issues: list[str] | None = None


@dataclass
class _Node:
    world: dict[str, Any]
    bindings: frozenset[str]
    plan: list[str]


def find_plan(
    actions: list[ActionContract],
    start_world_effects: list[WorldEffectSpec],
    start_bindings: list[str],
    goal_world: list[WorldPredicateSpec],
    goal_bindings: list[str],
    *,
    binding_sources: Optional[list[BindingSourceSpec]] = None,
    sync_rules: Optional[list[SyncRuleSpec]] = None,
    forbidden_actions: Optional[set[str]] = None,
    max_depth: int = 20,
) -> SearchResult:
    """Find a plan using BFS over (world, bindings) states."""
    forbidden_actions = forbidden_actions or set()
    binding_sources = binding_sources or []
    sync_rules = sync_rules or []
    binding_sources_by_id = index_binding_sources(binding_sources)

    start_world, start_world_issues = materialize_world(
        start_world_effects,
        sync_rules=sync_rules,
    )
    if start_world_issues:
        return SearchResult(
            sat=False,
            plan=[],
            explored_states=1,
            pruned_states=1,
            issues=start_world_issues,
        )
    start_bindings_set = frozenset(start_bindings)
    goal_bindings_set = set(goal_bindings)

    def goal_satisfied(world: dict[str, Any], bindings: frozenset[str]) -> bool:
        if not all(predicate_holds(predicate, world) for predicate in goal_world):
            return False
        if not goal_bindings_set.issubset(bindings):
            return False
        return True

    start_node = _Node(
        world=start_world,
        bindings=start_bindings_set,
        plan=[],
    )
    if goal_satisfied(start_node.world, start_node.bindings):
        return SearchResult(
            sat=True,
            plan=[],
            explored_states=1,
            end_world=start_node.world,
            end_bindings=start_node.bindings,
        )

    queue: deque[_Node] = deque([start_node])
    visited: set[tuple[tuple[tuple[str, Any], ...], frozenset[str]]] = {
        (world_state_key(start_node.world), start_node.bindings)
    }

    explored = 0
    pruned = 0

    while queue:
        node = queue.popleft()
        explored += 1

        if len(node.plan) >= max_depth:
            continue

        for action in actions:
            if action.action_id in forbidden_actions:
                continue

            if not is_action_enabled(action, node.world, node.bindings, binding_sources_by_id):
                continue

            next_world, next_bindings = apply_action(
                action,
                node.world,
                node.bindings,
                sync_rules=sync_rules,
                binding_specs=binding_sources,
            )

            # Exclude stutter transitions from causal search.
            if next_world == node.world and next_bindings == node.bindings:
                continue

            state_key = (world_state_key(next_world), next_bindings)
            if state_key in visited:
                continue
            visited.add(state_key)

            next_plan = node.plan + [action.action_id]
            if goal_satisfied(next_world, next_bindings):
                return SearchResult(
                    sat=True,
                    plan=next_plan,
                    explored_states=explored,
                    pruned_states=pruned,
                    end_world=next_world,
                    end_bindings=next_bindings,
                )

            queue.append(
                _Node(
                    world=next_world,
                    bindings=next_bindings,
                    plan=next_plan,
                )
            )

    return SearchResult(
        sat=False,
        plan=[],
        explored_states=explored,
        pruned_states=pruned,
    )
