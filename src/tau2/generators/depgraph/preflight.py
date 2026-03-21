"""Task-level preflight checks for dependency-graph contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

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
    """Return True when all world predicates in the profile hold."""
    return all(predicate_holds(predicate, world) for predicate in profile.requires_world)


def _check_refs(contract: GraphContractSpec, task: TaskIntent) -> list[str]:
    issues: list[str] = []
    action_ids = {a.action_id for a in contract.actions}
    projected_paths = set(contract.projection_fields)
    binding_ids = {b.binding_id for b in contract.bindings}

    for action_id in task.required_actions:
        if action_id not in action_ids:
            issues.append(f"Unknown required_action '{action_id}'")

    for effect in task.start_world:
        if effect.path not in projected_paths:
            issues.append(f"Unknown start_world path '{effect.path}' (not projected)")
    for predicate in task.goal_world:
        if predicate.path not in projected_paths:
            issues.append(f"Unknown goal_world path '{predicate.path}' (not projected)")

    for binding_id in task.start_bindings:
        if binding_id not in binding_ids:
            issues.append(f"Unknown start binding '{binding_id}'")

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
            resolved_name = action.resolved_tool_name
            if resolved_name is not None and resolved_name not in tools:
                issues.append(
                    f"Knowledge-only action '{action.action_id}' tool '{resolved_name}' "
                    f"does not match binding source tool(s) for '{binding_id}': {tools}"
                )
    return issues


def _check_binding_self_invalidation(contract: GraphContractSpec) -> list[str]:
    """Warn if a non-knowledge action writes the canonical world path of a binding it produces.

    Knowledge-only actions are expected to both acquire a binding and set the
    world_path that tracks it (the "acquisition write" pattern).  A second
    invocation of the same action will find the world_path already at its
    settled value so the binding survives invalidation.  We therefore only flag
    causal/stutter actions where the write is likely unintentional.
    """
    issues: list[str] = []
    binding_paths = {
        spec.binding_id: spec.world_path for spec in contract.bindings if spec.world_path
    }
    for action in contract.actions:
        # Knowledge-only actions intentionally set the world state they track.
        if action.classification == "knowledge-only":
            continue
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
    """Run SAT and structural checks for a task intent.

    Args:
        sat_result: If provided, skip the find_plan SAT check and use this
            pre-computed result instead. Useful when the caller (e.g. BFS sampler)
            has already proven reachability.
    """
    terminal_profiles_by_id = terminal_profile_map(terminal_profiles)
    issues = _check_refs(contract, task)
    issues.extend(_check_knowledge_edges(contract))
    issues.extend(_check_binding_self_invalidation(contract))
    issues.extend(
        _check_terminal_profile_reference(
            task,
            terminal_profiles=terminal_profiles_by_id,
            require_terminal_profile=require_terminal_profile,
        )
    )

    # SAT check
    if sat_result is not None:
        sat_full = sat_result
    else:
        sat_full = find_plan(
            contract.actions,
            task.start_world,
            task.start_bindings,
            task.goal_world,
            binding_sources=contract.bindings,
            sync_rules=contract.sync_rules,
            max_depth=max_depth,
            binding_sources_by_id=binding_sources_by_id,
        )

    if sat_full.issues:
        issues.extend(sat_full.issues)

    # Verify terminal state matches declared profile
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

    report = TaskPreflightReport(
        task_id=task.task_id,
        sat_full=sat_full,
        issues=issues,
    )

    # Check plan contains required actions
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

    # Strict dependency-necessity checking (expensive, opt-in only)
    if check_required_action_necessity:
        action_ids = {a.action_id for a in contract.actions}
        for required in task.required_actions:
            if required not in action_ids:
                continue
            res = find_plan(
                contract.actions,
                task.start_world,
                task.start_bindings,
                task.goal_world,
                binding_sources=contract.bindings,
                sync_rules=contract.sync_rules,
                forbidden_actions={required},
                max_depth=max_depth,
                binding_sources_by_id=binding_sources_by_id,
            )
            report.required_action_unsat[required] = not res.sat

    return report
