"""Fan-out sampler for generating candidate depgraph task intents."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from tau2.generators.depgraph.goal_capture import capture_goal_world
from tau2.generators.depgraph.preflight import (
    TaskPreflightReport,
    run_task_preflight,
    stable_goal_bindings,
    terminal_profile_map,
    world_matches_terminal_profile,
)
from tau2.generators.depgraph.semantics import (
    apply_action,
    index_binding_sources,
    is_action_enabled,
    materialize_world,
    world_state_key,
)
from tau2.generators.depgraph.types import (
    GraphContractSpec,
    SamplingRequestDoc,
    TaskIntent,
    TaskSpecsDoc,
    WorldPredicateSpec,
)


@dataclass
class _Node:
    world: dict[str, Any]
    bindings: frozenset[str]
    plan: list[str]


@dataclass
class SampledTask:
    """Sampled task plus preflight report."""

    task: TaskIntent
    report: TaskPreflightReport


def _ordered_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _plan_precedence(plan: list[str]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for idx in range(len(plan) - 1):
        edge = (plan[idx], plan[idx + 1])
        if edge not in edges:
            edges.append(edge)
    return edges


def _goal_signature(goal_world: list[WorldPredicateSpec], goal_bindings: list[str]) -> tuple:
    world_part = tuple(sorted((goal.path, repr(goal.value)) for goal in goal_world))
    return (world_part, tuple(sorted(goal_bindings)))


def sample_task_intents(
    contract: GraphContractSpec,
    request: SamplingRequestDoc,
) -> list[SampledTask]:
    """Generate candidate task intents by fan-out and keep only preflight-passing ones."""
    sampled: list[SampledTask] = []
    seen_signatures: set[tuple[tuple, tuple[str, ...]]] = set()
    binding_sources_by_id = index_binding_sources(contract.bindings)
    terminal_profiles_by_id = terminal_profile_map(request.terminal_profiles)
    task_counter = 0

    for seed in request.seeds:
        goal_capture_paths = request.goal_capture_paths_for_seed(seed)
        allowed_terminal_profiles = [
            terminal_profiles_by_id[profile_id]
            for profile_id in seed.allowed_terminal_profiles
        ]
        start_world, seed_issues = materialize_world(
            seed.start_world,
            sync_rules=contract.sync_rules,
        )
        if seed_issues:
            continue
        start_bindings = frozenset(seed.start_bindings)

        root = _Node(world=start_world, bindings=start_bindings, plan=[])
        queue: deque[_Node] = deque([root])
        visited: set[tuple[tuple[tuple[str, Any], ...], frozenset[str]]] = {
            (world_state_key(root.world), root.bindings)
        }

        while queue:
            node = queue.popleft()
            if len(node.plan) >= seed.max_depth:
                continue

            for action in contract.actions:
                if not is_action_enabled(action, node.world, node.bindings, binding_sources_by_id):
                    continue
                next_world, next_bindings = apply_action(
                    action,
                    node.world,
                    node.bindings,
                    sync_rules=contract.sync_rules,
                    binding_specs=contract.bindings,
                )
                if next_world == node.world and next_bindings == node.bindings:
                    continue
                next_plan = node.plan + [action.action_id]
                state_key = (world_state_key(next_world), next_bindings)
                if state_key in visited:
                    continue
                visited.add(state_key)

                matched_terminal_profile = next(
                    (
                        profile
                        for profile in allowed_terminal_profiles
                        if world_matches_terminal_profile(next_world, profile)
                    ),
                    None,
                )
                if matched_terminal_profile is None:
                    queue.append(
                        _Node(world=next_world, bindings=next_bindings, plan=next_plan)
                    )

                depth = len(next_plan)
                if depth < seed.min_depth or matched_terminal_profile is None:
                    continue
                goal_world = capture_goal_world(
                    start_world=start_world,
                    end_world=next_world,
                    capture_paths=goal_capture_paths,
                    projected_paths=contract.projection_fields,
                )
                if not goal_world:
                    continue

                # Canonicalize sampled tasks around the minimal plan for the terminal goal_world
                # rather than the exploratory BFS trace that happened to hit it first. This avoids
                # emitting duplicate tasks that differ only by optional extra reads/bindings.
                canonical_probe = TaskIntent(
                    task_id="__probe__",
                    start_world=seed.start_world,
                    start_bindings=seed.start_bindings,
                    goal_world=goal_world,
                    goal_capture_paths=goal_capture_paths,
                    goal_bindings=[],
                    terminal_profile_id=matched_terminal_profile.profile_id,
                    required_actions=[],
                    required_precedence=[],
                    min_plan_length=0,
                    runtime=None,
                )
                canonical_probe_report = run_task_preflight(
                    contract,
                    canonical_probe,
                    max_depth=seed.max_depth,
                    terminal_profiles=terminal_profiles_by_id,
                    require_terminal_profile=True,
                )
                if not canonical_probe_report.passed:
                    continue

                canonical_plan = canonical_probe_report.sat_full.plan
                canonical_depth = len(canonical_plan)
                if canonical_depth < seed.min_depth:
                    continue

                canonical_end_world = canonical_probe_report.sat_full.end_world
                if canonical_end_world is None:
                    continue
                goal_world = capture_goal_world(
                    start_world=start_world,
                    end_world=canonical_end_world,
                    capture_paths=goal_capture_paths,
                    projected_paths=contract.projection_fields,
                )
                if not goal_world:
                    continue

                goal_bindings = stable_goal_bindings(
                    contract,
                    sorted(
                        set(canonical_probe_report.sat_full.end_bindings or frozenset())
                        - set(start_bindings)
                    ),
                )
                required_actions = _ordered_unique(canonical_plan)
                signature = (
                    _goal_signature(goal_world, goal_bindings),
                    tuple(required_actions),
                    matched_terminal_profile.profile_id,
                )
                if signature in seen_signatures:
                    continue

                task_id = f"{seed.seed_id}_d{canonical_depth}_{task_counter:03d}"
                task_counter += 1
                candidate = TaskIntent(
                    task_id=task_id,
                    start_world=seed.start_world,
                    start_bindings=seed.start_bindings,
                    goal_world=goal_world,
                    goal_capture_paths=goal_capture_paths,
                    goal_bindings=goal_bindings,
                    terminal_profile_id=matched_terminal_profile.profile_id,
                    required_actions=required_actions,
                    required_precedence=_plan_precedence(canonical_plan),
                    min_plan_length=canonical_depth,
                    runtime=None,
                )
                report = run_task_preflight(
                    contract,
                    candidate,
                    max_depth=seed.max_depth,
                    terminal_profiles=terminal_profiles_by_id,
                    require_terminal_profile=True,
                )
                if report.passed:
                    seen_signatures.add(signature)
                    sampled.append(SampledTask(task=candidate, report=report))
                    if len(sampled) >= request.max_tasks:
                        return sampled

    return sampled


def sampled_to_task_specs(sampled: list[SampledTask]) -> TaskSpecsDoc:
    """Convert sampled task wrappers to TaskSpecsDoc."""
    return TaskSpecsDoc(version=1, tasks=[entry.task for entry in sampled])
