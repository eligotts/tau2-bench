"""Fan-out sampler for generating candidate depgraph task intents."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from tau2.generators.depgraph.goal_capture import capture_goal_world
from tau2.generators.depgraph.preflight import (
    TaskPreflightReport,
    compute_volatile_binding_ids,
    run_task_preflight,
    stable_goal_bindings,
    terminal_profile_map,
    world_matches_terminal_profile,
)
from tau2.generators.depgraph.solver import SearchResult
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


def _goal_key(goal_world: list[WorldPredicateSpec]) -> tuple:
    return tuple(sorted((g.path, g.op, repr(g.value)) for g in goal_world))


def sample_task_intents(
    contract: GraphContractSpec,
    request: SamplingRequestDoc,
) -> list[SampledTask]:
    """Generate candidate task intents by BFS fan-out.

    Deduplicates by goal_world signature during BFS — different terminal states
    that collapse to the same goal are kept only once (first/shortest BFS hit).
    No solver calls needed: BFS traces are correct-by-construction proofs of SAT.
    """
    sampled: list[SampledTask] = []
    binding_sources_by_id = index_binding_sources(contract.bindings)
    volatile_binding_ids = compute_volatile_binding_ids(contract)
    terminal_profiles_by_id = terminal_profile_map(request.terminal_profiles)
    task_counter = 0
    # Fair share per seed: spread the budget evenly so late seeds aren't starved.
    n_seeds = len(request.seeds)
    per_seed_budget = max(1, request.max_tasks // n_seeds) if n_seeds > 0 else request.max_tasks

    for seed in request.seeds:
        seed_count = 0
        goal_capture_paths = request.goal_capture_paths_for_seed(seed)
        allowed_terminal_profiles = [
            terminal_profiles_by_id[profile_id]
            for profile_id in seed.allowed_terminal_profiles
        ]
        # Per-seed dedup by (goal_world, terminal_profile). First BFS hit
        # wins (shortest path to that goal from this seed's start state).
        seen_goals: set[tuple] = set()
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

        while queue and seed_count < per_seed_budget:
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

                # Dedup: same goal_world + terminal profile = same task.
                gk = (_goal_key(goal_world), matched_terminal_profile.profile_id)
                if gk in seen_goals:
                    continue
                seen_goals.add(gk)

                plan = next_plan
                plan_depth = depth
                goal_bindings = stable_goal_bindings(
                    contract,
                    sorted(set(next_bindings) - set(start_bindings)),
                    volatile_binding_ids=volatile_binding_ids,
                )
                required_actions = _ordered_unique(plan)

                task_id = f"{seed.seed_id}_d{plan_depth}_{task_counter:03d}"
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
                    required_precedence=_plan_precedence(plan),
                    min_plan_length=plan_depth,
                    runtime=None,
                )
                # BFS trace is the proof of SAT — pass directly to preflight.
                bfs_sat = SearchResult(
                    sat=True,
                    plan=plan,
                    explored_states=0,
                    end_world=dict(next_world),
                    end_bindings=frozenset(next_bindings),
                )
                report = run_task_preflight(
                    contract,
                    candidate,
                    max_depth=seed.max_depth,
                    terminal_profiles=terminal_profiles_by_id,
                    require_terminal_profile=True,
                    check_required_action_necessity=False,
                    binding_sources_by_id=binding_sources_by_id,
                    sat_result=bfs_sat,
                )
                if report.passed:
                    sampled.append(SampledTask(task=candidate, report=report))
                    seed_count += 1
                    if len(sampled) >= request.max_tasks:
                        return sampled
                    if seed_count >= per_seed_budget:
                        break  # move to next seed

    return sampled


def cap_per_schema(
    sampled: list[SampledTask],
    request: SamplingRequestDoc,
    max_per_schema: int,
) -> list[SampledTask]:
    """Subsample tasks so no single schema dominates.

    Maps each task back to its source schema via seed_id prefix matching,
    then keeps up to *max_per_schema* tasks per schema (preserving BFS
    order, i.e. shortest-first).
    """
    # Build prefix → schema_id mapping from seed templates.
    prefix_map: dict[str, str] = {}
    for schema in request.seed_schemas:
        # Template like 'dc_{care_fate}_{transport}_{knowledge}'
        # Prefix is everything before the first '{'.
        prefix = schema.seed_id_template.split("{")[0]
        prefix_map[prefix] = schema.schema_id

    # Sort prefixes longest-first so 'cch2_' matches before 'cch_'.
    sorted_prefixes = sorted(prefix_map, key=len, reverse=True)

    schema_counts: dict[str, int] = {}
    result: list[SampledTask] = []
    for entry in sampled:
        # Strip _d{depth}_{counter} suffix to get seed_id.
        seed_id = entry.task.task_id.rsplit("_d", 1)[0]
        schema_id = "unknown"
        for prefix in sorted_prefixes:
            if seed_id.startswith(prefix):
                schema_id = prefix_map[prefix]
                break
        count = schema_counts.get(schema_id, 0)
        if count < max_per_schema:
            result.append(entry)
            schema_counts[schema_id] = count + 1
    return result


def sampled_to_task_specs(sampled: list[SampledTask]) -> TaskSpecsDoc:
    """Convert sampled task wrappers to TaskSpecsDoc."""
    return TaskSpecsDoc(version=1, tasks=[entry.task for entry in sampled])
