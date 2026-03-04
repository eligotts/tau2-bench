"""Task-level preflight checks for dependency-graph contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from tau2.generators.depgraph.semantics import world_from_effects
from tau2.generators.depgraph.solver import SearchResult, find_plan
from tau2.generators.depgraph.types import GraphContractSpec, TaskIntent


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
    _, start_issues = world_from_effects(task.start_world)
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
    start_world, _ = world_from_effects(task.start_world)
    start_bindings = set(task.start_bindings)

    world_producers: set[tuple[str, object]] = set()
    binding_producers: set[str] = set()
    for action in contract.actions:
        for effect in action.effects_world:
            world_producers.add((effect.path, effect.set))
        for binding_id in action.effects_bindings:
            binding_producers.add(binding_id)

    for predicate in task.goal_world:
        if start_world.get(predicate.path, None) == predicate.value:
            continue
        if (predicate.path, predicate.value) not in world_producers:
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


def run_task_preflight(
    contract: GraphContractSpec,
    task: TaskIntent,
    *,
    max_depth: int = 20,
) -> TaskPreflightReport:
    """Run SAT and dependency necessity checks for a task intent."""
    issues = _check_refs(contract, task)
    issues.extend(_check_precedence_cycle(task))
    issues.extend(_check_goal_producers(contract, task))
    issues.extend(_check_knowledge_edges(contract))
    issues.extend(_check_goal_contradictions(task))

    sat_full = find_plan(
        contract.actions,
        task.start_world,
        task.start_bindings,
        task.goal_world,
        task.goal_bindings,
        binding_sources=contract.bindings,
        max_depth=max_depth,
    )

    if sat_full.issues:
        issues.extend(sat_full.issues)

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

    # Required action necessity via ablation: remove each action and expect UNSAT.
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
            forbidden_actions={required},
            max_depth=max_depth,
        )
        report.required_action_unsat[required] = not res.sat

    # required_precedence is retained as optional metadata for trace narration.
    # Solvability checks are state-based only and do not enforce history order.

    return report
