"""Helpers for capturing emitted goal state from solved terminal worlds."""

from __future__ import annotations

from typing import Any, Iterable

from tau2.generators.depgraph.types import WorldPredicateSpec


def path_matches_capture(path: str, capture_paths: list[str]) -> bool:
    """Return True when a projection path is covered by one capture prefix."""
    for prefix in capture_paths:
        if path == prefix or path.startswith(f"{prefix}."):
            return True
    return False


def capture_goal_world(
    *,
    start_world: dict[str, Any],
    end_world: dict[str, Any],
    capture_paths: list[str],
    projected_paths: Iterable[str],
) -> list[WorldPredicateSpec]:
    """Capture changed end-state predicates under the configured goal-capture paths."""
    predicates: list[WorldPredicateSpec] = []
    seen_paths: set[str] = set()
    for path in projected_paths:
        if path in seen_paths or not path_matches_capture(path, capture_paths):
            continue
        seen_paths.add(path)
        if start_world.get(path) == end_world.get(path):
            continue
        predicates.append(
            WorldPredicateSpec(op="eq", path=path, value=end_world.get(path))
        )
    return predicates


def explicit_start_world_map(start_world_effects: list[Any]) -> dict[str, Any]:
    """Build the authored explicit start-state map from task/seed world effects."""
    return {effect.path: effect.set for effect in start_world_effects}
