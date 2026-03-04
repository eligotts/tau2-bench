"""Core transition semantics for depgraph v2 preflight/search."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from tau2.generators.depgraph.types import ActionContract, BindingSourceSpec, WorldEffectSpec, WorldPredicateSpec


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return ("json", json.dumps(value, sort_keys=True))


def world_state_key(world: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Return a hashable, deterministic key for projected world assignments."""
    return tuple(sorted((path, _normalize_value(value)) for path, value in world.items()))


def world_from_effects(effects: list[WorldEffectSpec]) -> tuple[dict[str, Any], list[str]]:
    """Build world assignment map from effects and return conflict diagnostics."""
    world: dict[str, Any] = {}
    issues: list[str] = []
    for effect in effects:
        if effect.path in world and world[effect.path] != effect.set:
            issues.append(
                f"Conflicting assignments for path '{effect.path}': "
                f"{world[effect.path]!r} vs {effect.set!r}"
            )
            continue
        world[effect.path] = effect.set
    return world, issues


def predicate_holds(predicate: WorldPredicateSpec, world: dict[str, Any]) -> bool:
    if predicate.op != "eq":
        return False
    return world.get(predicate.path, None) == predicate.value


def index_binding_sources(
    bindings: list[BindingSourceSpec],
) -> dict[str, list[BindingSourceSpec]]:
    """Index binding sources by produced binding id."""
    by_binding: dict[str, list[BindingSourceSpec]] = defaultdict(list)
    for source in bindings:
        by_binding[source.binding_id].append(source)
    return dict(by_binding)


def binding_source_satisfiable(source: BindingSourceSpec, world: dict[str, Any]) -> bool:
    """Return True if source observability predicates are satisfied in the world state."""
    all_ok = all(predicate_holds(predicate, world) for predicate in source.observability_all_of)
    any_clause = source.observability_any_of
    any_ok = True if not any_clause else any(
        predicate_holds(predicate, world) for predicate in any_clause
    )
    return all_ok and any_ok


def _knowledge_source_ok(
    action: ActionContract,
    world: dict[str, Any],
    bindings: frozenset[str],
    binding_sources_by_id: dict[str, list[BindingSourceSpec]],
) -> bool:
    if action.classification != "knowledge-only":
        return True
    if not action.effects_bindings:
        return False
    for binding_id in action.effects_bindings:
        if binding_id in bindings:
            return False
        sources = binding_sources_by_id.get(binding_id, [])
        if not sources:
            return False
        tool_scoped_sources = [source for source in sources if source.source_tool == action.tool_name]
        candidates = tool_scoped_sources if tool_scoped_sources else sources
        if not any(binding_source_satisfiable(source, world) for source in candidates):
            return False
    return True


def is_action_enabled(
    action: ActionContract,
    world: dict[str, Any],
    bindings: frozenset[str],
    binding_sources_by_id: dict[str, list[BindingSourceSpec]],
) -> bool:
    """Eligibility predicate for fan-out over (world, bindings)."""
    if not all(predicate_holds(predicate, world) for predicate in action.requires_world):
        return False
    if any(predicate_holds(predicate, world) for predicate in action.requires_absent_world):
        return False
    if not set(action.requires_bindings).issubset(bindings):
        return False
    if set(action.requires_absent_bindings) & set(bindings):
        return False
    if not _knowledge_source_ok(action, world, bindings, binding_sources_by_id):
        return False
    return True


def apply_action(
    action: ActionContract,
    world: dict[str, Any],
    bindings: frozenset[str],
) -> tuple[dict[str, Any], frozenset[str]]:
    """Apply forward effects of one action."""
    next_world = dict(world)
    for effect in action.effects_world:
        next_world[effect.path] = effect.set
    next_bindings = set(bindings)
    next_bindings.update(action.effects_bindings)
    return next_world, frozenset(next_bindings)
