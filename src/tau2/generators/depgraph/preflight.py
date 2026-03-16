"""Task-level preflight checks for dependency-graph contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from tau2.generators.depgraph.goal_capture import (
    capture_goal_world,
    explicit_start_world_map,
    path_matches_capture,
)
from tau2.generators.depgraph.semantics import materialize_world, predicate_holds
from tau2.generators.depgraph.solver import SearchResult, find_plan
from tau2.generators.depgraph.types import (
    GraphContractSpec,
    TaskIntent,
    TerminalProfileSpec,
)


@dataclass
class TaskPreflightReport:
    """Structured preflight outcome for one task intent."""

    task_id: str
    sat_full: SearchResult
    required_action_unsat: dict[str, bool] = field(default_factory=dict)
    plan_contains_required_actions: bool = True
    min_plan_length_ok: bool = True
    issues: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        if not self.sat_full.sat:
            return False
        if any(not ok for ok in self.required_action_unsat.values()):
            return False
        if not self.plan_contains_required_actions:
            return False
        if not self.min_plan_length_ok:
            return False
        return len(self.issues) == 0


def compute_volatile_paths(contract: GraphContractSpec) -> set[str]:
    """Pre-compute the set of world paths that any action or sync rule can change."""
    volatile: set[str] = set()
    for action in contract.actions:
        for effect in action.effects_world:
            volatile.add(effect.path)
    for rule in contract.sync_rules:
        for effect in rule.effects_world:
            volatile.add(effect.path)
    return volatile


def compute_volatile_binding_ids(contract: GraphContractSpec) -> set[str]:
    """Pre-compute binding IDs whose world_path is volatile."""
    volatile_paths = compute_volatile_paths(contract)
    return {
        spec.binding_id
        for spec in contract.bindings
        if spec.world_path is not None and spec.world_path in volatile_paths
    }


def world_path_is_volatile(contract: GraphContractSpec, world_path: str | None) -> bool:
    """Return True when a projected world path can change after acquisition."""
    if world_path is None:
        return False
    for action in contract.actions:
        for effect in action.effects_world:
            if effect.path == world_path:
                return True
    for rule in contract.sync_rules:
        for effect in rule.effects_world:
            if effect.path == world_path:
                return True
    return False


def binding_is_volatile(contract: GraphContractSpec, binding_id: str) -> bool:
    """Return True when a binding tracks a world path that can change over time."""
    binding = next((spec for spec in contract.bindings if spec.binding_id == binding_id), None)
    if binding is None:
        return False
    return world_path_is_volatile(contract, binding.world_path)


def stable_goal_bindings(
    contract: GraphContractSpec,
    binding_ids: list[str],
    volatile_binding_ids: set[str] | None = None,
) -> list[str]:
    """Keep only stable bindings in goal state requirements."""
    if volatile_binding_ids is not None:
        return [bid for bid in binding_ids if bid not in volatile_binding_ids]
    return [binding_id for binding_id in binding_ids if not binding_is_volatile(contract, binding_id)]


def terminal_profile_map(
    terminal_profiles: list[TerminalProfileSpec] | dict[str, TerminalProfileSpec] | None,
) -> dict[str, TerminalProfileSpec]:
    """Normalize terminal profiles into a dictionary keyed by profile_id."""
    if terminal_profiles is None:
        return {}
    if isinstance(terminal_profiles, dict):
        return terminal_profiles
    return {profile.profile_id: profile for profile in terminal_profiles}


def world_matches_terminal_profile(
    world: dict[str, object],
    profile: TerminalProfileSpec,
) -> bool:
    """Return True when all predicates in the terminal profile hold."""
    return all(predicate_holds(predicate, world) for predicate in profile.requires_world)


def _check_refs(contract: GraphContractSpec, task: TaskIntent) -> list[str]:
    issues: list[str] = []
    action_ids = {a.action_id for a in contract.actions}
    projected_paths = set(contract.projection_fields)
    binding_ids = {b.binding_id for b in contract.bindings}

    for action_id in task.required_actions:
        if action_id not in action_ids:
            issues.append(f"Unknown required_action '{action_id}'")

    for before, after in task.required_precedence:
        if before not in action_ids or after not in action_ids:
            issues.append(f"Unknown precedence action in ({before}, {after})")

    for effect in task.start_world:
        if effect.path not in projected_paths:
            issues.append(f"Unknown start_world path '{effect.path}' (not projected)")
    for predicate in task.goal_world:
        if predicate.path not in projected_paths:
            issues.append(f"Unknown goal_world path '{predicate.path}' (not projected)")

    for binding_id in task.start_bindings:
        if binding_id not in binding_ids:
            issues.append(f"Unknown start binding '{binding_id}'")
    for binding_id in task.goal_bindings:
        if binding_id not in binding_ids:
            issues.append(f"Unknown goal binding '{binding_id}'")

    return issues


def _check_precedence_cycle(task: TaskIntent) -> list[str]:
    """Return cycle issues in required precedence DAG."""
    adjacency: dict[str, set[str]] = {}
    for before, after in task.required_precedence:
        adjacency.setdefault(before, set()).add(after)

    visiting: set[str] = set()
    visited: set[str] = set()
    issues: list[str] = []

    def dfs(node: str) -> None:
        if node in visited or issues:
            return
        if node in visiting:
            issues.append("required_precedence has a cycle")
            return
        visiting.add(node)
        for nxt in adjacency.get(node, set()):
            dfs(nxt)
            if issues:
                return
        visiting.remove(node)
        visited.add(node)

    for node in list(adjacency.keys()):
        dfs(node)
        if issues:
            break

    return issues


def _check_goal_contradictions(task: TaskIntent) -> list[str]:
    """Detect contradictory assignments in start/goal world declarations."""
    issues: list[str] = []
    _, start_issues = materialize_world(task.start_world)
    for issue in start_issues:
        issues.append(f"Start-state contradiction: {issue}")

    goal_by_path: dict[str, object] = {}
    for predicate in task.goal_world:
        existing = goal_by_path.get(predicate.path)
        if existing is None:
            goal_by_path[predicate.path] = predicate.value
            continue
        if existing != predicate.value:
            issues.append(
                f"Goal contradiction: path '{predicate.path}' has multiple target values "
                f"{existing!r} and {predicate.value!r}"
            )

    return issues


def _check_goal_producers(contract: GraphContractSpec, task: TaskIntent) -> list[str]:
    """Ensure every goal assignment has a producer action or is already true at start."""
    issues: list[str] = []
    start_world, _ = materialize_world(task.start_world, sync_rules=contract.sync_rules)
    start_bindings = set(task.start_bindings)

    world_producers: set[tuple[str, object]] = set()
    binding_producers: set[str] = set()
    for action in contract.actions:
        for effect in action.effects_world:
            world_producers.add((effect.path, effect.set))
        for binding_id in action.effects_bindings:
            binding_producers.add(binding_id)

    sync_literal_producers = {
        (effect.path, effect.set)
        for rule in contract.sync_rules
        for effect in rule.effects_world
        if effect.from_path is None
    }
    sync_target_paths = {
        effect.path for rule in contract.sync_rules for effect in rule.effects_world
    }

    for predicate in task.goal_world:
        if start_world.get(predicate.path, None) == predicate.value:
            continue
        if (
            (predicate.path, predicate.value) not in world_producers
            and (predicate.path, predicate.value) not in sync_literal_producers
            and predicate.path not in sync_target_paths
        ):
            issues.append(
                f"Goal world predicate '{predicate.path} == {predicate.value!r}' "
                "has no producer action"
            )

    for binding_id in task.goal_bindings:
        if binding_id in start_bindings:
            continue
        if binding_id not in binding_producers:
            issues.append(f"Goal binding '{binding_id}' has no producer action")

    return issues


def _check_knowledge_edges(contract: GraphContractSpec) -> list[str]:
    """Validate knowledge-only actions are grounded by binding source definitions."""
    issues: list[str] = []
    sources_by_binding: dict[str, list[str]] = {}
    for source in contract.bindings:
        sources_by_binding.setdefault(source.binding_id, []).append(source.source_tool)

    for action in contract.actions:
        if action.classification != "knowledge-only":
            continue
        if not action.effects_bindings:
            issues.append(
                f"Knowledge-only action '{action.action_id}' must produce at least one binding"
            )
            continue
        for binding_id in action.effects_bindings:
            tools = sources_by_binding.get(binding_id, [])
            if not tools:
                issues.append(
                    f"Knowledge-only action '{action.action_id}' produces binding "
                    f"'{binding_id}' with no binding source spec"
                )
                continue
            if action.tool_name not in tools:
                issues.append(
                    f"Knowledge-only action '{action.action_id}' tool '{action.tool_name}' "
                    f"does not match binding source tool(s) for '{binding_id}': {tools}"
                )
    return issues


def _check_binding_self_invalidation(contract: GraphContractSpec) -> list[str]:
    """Warn if an action writes the canonical world path of a binding it produces."""
    issues: list[str] = []
    binding_paths = {
        spec.binding_id: spec.world_path for spec in contract.bindings if spec.world_path
    }
    for action in contract.actions:
        produced = set(action.effects_bindings)
        written_paths = {effect.path for effect in action.effects_world}
        for binding_id in produced:
            binding_path = binding_paths.get(binding_id)
            if binding_path is None or binding_path not in written_paths:
                continue
            issues.append(
                f"Action '{action.action_id}' produces binding '{binding_id}' but also "
                f"writes to its world_path '{binding_path}'"
            )
    return issues


def _check_volatile_goal_bindings(contract: GraphContractSpec, task: TaskIntent) -> list[str]:
    """Fail tasks that keep moving observation bindings as terminal requirements."""
    issues: list[str] = []
    binding_by_id = {binding.binding_id: binding for binding in contract.bindings}
    goal_world_paths = {predicate.path for predicate in task.goal_world}

    for binding_id in task.goal_bindings:
        binding = binding_by_id.get(binding_id)
        if binding is None or not binding_is_volatile(contract, binding_id):
            continue

        world_path_note = ""
        if binding.world_path and binding.world_path in goal_world_paths:
            world_path_note = (
                f" Its world_path '{binding.world_path}' is already modeled in goal_world."
            )

        issues.append(
            f"Goal binding '{binding_id}' is volatile and should not be a terminal task goal."
            f"{world_path_note} Move the terminal check into stable world state, stop-gate "
            "observability, or an explicit final user observation step instead."
        )

    return issues


def _check_terminal_profile_reference(
    task: TaskIntent,
    *,
    terminal_profiles: dict[str, TerminalProfileSpec],
    require_terminal_profile: bool,
) -> list[str]:
    """Validate that the task references a known terminal profile when required."""
    issues: list[str] = []
    if task.terminal_profile_id is None:
        if require_terminal_profile:
            issues.append(
                "Task is missing terminal_profile_id. Terminal tasks must declare which "
                "terminal profile they are sampled against."
            )
        return issues
    if task.terminal_profile_id not in terminal_profiles:
        issues.append(
            f"Task references unknown terminal_profile_id '{task.terminal_profile_id}'"
        )
    return issues


def _check_goal_capture_reference(task: TaskIntent) -> list[str]:
    """Require goal-capture metadata for terminal-profile tasks."""
    if task.terminal_profile_id is None:
        return []
    if task.goal_capture_paths:
        return []
    return [
        "Task is missing goal_capture_paths. Terminal-profile tasks must declare which "
        "captured end-state paths define goal_world/env assertions."
    ]


def _check_terminal_profile_goal_conflicts(
    task: TaskIntent,
    profile: TerminalProfileSpec,
) -> list[str]:
    """Catch explicit authored goal predicates that contradict the declared terminal profile."""
    issues: list[str] = []
    goal_values = {
        predicate.path: predicate.value
        for predicate in task.goal_world
        if predicate.op == "eq"
    }
    for predicate in profile.requires_world:
        authored = goal_values.get(predicate.path)
        if authored is None:
            continue
        if authored != predicate.value:
            issues.append(
                f"Task goal contradicts terminal profile '{profile.profile_id}' on "
                f"path '{predicate.path}': goal={authored!r}, profile={predicate.value!r}"
            )
    return issues


def run_task_preflight(
    contract: GraphContractSpec,
    task: TaskIntent,
    *,
    max_depth: int = 20,
    terminal_profiles: list[TerminalProfileSpec] | dict[str, TerminalProfileSpec] | None = None,
    require_terminal_profile: bool = False,
    check_required_action_necessity: bool = False,
    binding_sources_by_id: dict[str, list] | None = None,
    sat_result: SearchResult | None = None,
) -> TaskPreflightReport:
    """Run SAT and dependency necessity checks for a task intent.

    Args:
        sat_result: If provided, skip the find_plan SAT check and use this
            pre-computed result instead. Useful when the caller (e.g. BFS sampler)
            has already proven reachability.
    """
    terminal_profiles_by_id = terminal_profile_map(terminal_profiles)
    issues = _check_refs(contract, task)
    issues.extend(_check_goal_producers(contract, task))
    issues.extend(_check_knowledge_edges(contract))
    issues.extend(_check_goal_contradictions(task))
    issues.extend(_check_binding_self_invalidation(contract))
    issues.extend(_check_volatile_goal_bindings(contract, task))
    issues.extend(
        _check_terminal_profile_reference(
            task,
            terminal_profiles=terminal_profiles_by_id,
            require_terminal_profile=require_terminal_profile,
        )
    )
    issues.extend(_check_goal_capture_reference(task))
    if task.terminal_profile_id is not None:
        profile = terminal_profiles_by_id.get(task.terminal_profile_id)
        if profile is not None:
            issues.extend(_check_terminal_profile_goal_conflicts(task, profile))

    if sat_result is not None:
        sat_full = sat_result
    else:
        sat_full = find_plan(
            contract.actions,
            task.start_world,
            task.start_bindings,
            task.goal_world,
            task.goal_bindings,
            binding_sources=contract.bindings,
            sync_rules=contract.sync_rules,
            max_depth=max_depth,
            binding_sources_by_id=binding_sources_by_id,
        )

    if sat_full.issues:
        issues.extend(sat_full.issues)
    if sat_full.sat and task.terminal_profile_id is not None:
        profile = terminal_profiles_by_id.get(task.terminal_profile_id)
        if profile is not None and (
            sat_full.end_world is None
            or not world_matches_terminal_profile(sat_full.end_world, profile)
        ):
            issues.append(
                f"SAT_full terminal state does not satisfy terminal profile "
                f"'{task.terminal_profile_id}'"
            )
    if sat_full.sat and sat_full.end_world is not None and task.goal_capture_paths:
        start_world, start_issues = materialize_world(
            task.start_world,
            sync_rules=contract.sync_rules,
        )
        if start_issues:
            issues.extend(start_issues)
        else:
            authored_goal_paths = {predicate.path for predicate in task.goal_world}
            for predicate in task.goal_world:
                if not path_matches_capture(predicate.path, task.goal_capture_paths):
                    issues.append(
                        f"Goal predicate '{predicate.path}' falls outside goal_capture_paths"
                    )

            expected_goal_world = capture_goal_world(
                start_world=start_world,
                end_world=sat_full.end_world,
                capture_paths=task.goal_capture_paths,
                projected_paths=contract.projection_fields,
            )
            expected_goal_signature = {
                (predicate.path, predicate.op, repr(predicate.value))
                for predicate in expected_goal_world
            }
            authored_goal_signature = {
                (predicate.path, predicate.op, repr(predicate.value))
                for predicate in task.goal_world
            }
            if authored_goal_signature != expected_goal_signature:
                issues.append(
                    "goal_world does not match the captured end-state diff under "
                    "goal_capture_paths"
                )

            explicit_start_map = explicit_start_world_map(task.start_world)
            for path, start_value in sorted(explicit_start_map.items()):
                if path in authored_goal_paths:
                    continue
                # Paths outside goal_capture_paths were intentionally excluded
                # from goal capture (e.g. non-monotonic page.type) — don't flag them.
                if not path_matches_capture(path, task.goal_capture_paths):
                    continue
                if sat_full.end_world.get(path) != start_value:
                    issues.append(
                        f"SAT_full changed protected start-world path '{path}' outside goal_world "
                        f"(start={start_value!r}, end={sat_full.end_world.get(path)!r})"
                    )

    report = TaskPreflightReport(
        task_id=task.task_id,
        sat_full=sat_full,
        issues=issues,
    )

    action_ids = {a.action_id for a in contract.actions}
    plan_actions = set(sat_full.plan)
    if sat_full.sat and not set(task.required_actions).issubset(plan_actions):
        report.plan_contains_required_actions = False
        missing = sorted(set(task.required_actions) - plan_actions)
        report.issues.append(
            f"SAT_full plan does not include required actions: {missing}"
        )
    report.min_plan_length_ok = (
        not sat_full.sat or len(sat_full.plan) >= max(task.min_plan_length, 0)
    )
    if sat_full.sat and not report.min_plan_length_ok:
        report.issues.append(
            f"Plan length {len(sat_full.plan)} is below min_plan_length={task.min_plan_length}"
        )

    # Strict dependency-necessity checking is expensive and not needed for ordinary
    # solvability validation. Use it only when we explicitly want to audit whether
    # every required action is truly indispensable.
    if check_required_action_necessity:
        for required in task.required_actions:
            if required not in action_ids:
                continue
            res = find_plan(
                contract.actions,
                task.start_world,
                task.start_bindings,
                task.goal_world,
                task.goal_bindings,
                binding_sources=contract.bindings,
                sync_rules=contract.sync_rules,
                forbidden_actions={required},
                max_depth=max_depth,
                binding_sources_by_id=binding_sources_by_id,
            )
            report.required_action_unsat[required] = not res.sat

    # required_precedence is retained as optional metadata for trace narration.
    # Solvability checks are state-based only and do not enforce history order.

    return report
