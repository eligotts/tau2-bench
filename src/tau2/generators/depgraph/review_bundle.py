"""Generate a compact authoring-review bundle for rubric-driven LLM audits."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from statistics import mean

from tau2.generators.depgraph.loaders import load_sampling_request
from tau2.generators.depgraph.preflight import binding_is_volatile, run_task_preflight
from tau2.generators.depgraph.types import (
    ActionContract,
    GraphContractSpec,
    TerminalProfileSpec,
    TaskIntent,
    TaskSpecsDoc,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_TASK_FAMILY_RE = re.compile(r"^(?P<family>.+)_d\d+_.+$")


@dataclass(frozen=True)
class ReviewSourcePaths:
    """Files the reviewer should inspect alongside the generated bundle."""

    domain_scope: Path | None = None
    graph_contract: Path | None = None
    policy: Path | None = None
    runtime_defaults: Path | None = None
    sampling_request: Path | None = None
    stop_gate_map: Path | None = None
    task_specs: Path | None = None
    task_specs_sampled: Path | None = None
    task_context_bindings: Path | None = None
    task_narrative_briefs: Path | None = None
    tasks_compiled: Path | None = None
    tools_py: Path | None = None
    user_tools_py: Path | None = None
    environment_py: Path | None = None

    def existing_items(self) -> list[tuple[str, Path]]:
        items: list[tuple[str, Path]] = []
        for label, value in self.__dict__.items():
            if value is not None and value.exists():
                items.append((label, value))
        return items


def infer_task_family(task_id: str) -> str:
    """Infer a stable family prefix from depgraph task ids."""
    match = _TASK_FAMILY_RE.match(task_id)
    if match:
        return match.group("family")
    return task_id


def infer_review_source_paths(
    *,
    domain: str,
    graph_contract_path: str | Path,
    task_specs_path: str | Path,
    policy_path: str | Path | None = None,
    domain_scope_path: str | Path | None = None,
    runtime_defaults_path: str | Path | None = None,
    sampling_request_path: str | Path | None = None,
    stop_gate_map_path: str | Path | None = None,
) -> ReviewSourcePaths:
    """Infer the standard depgraph/domain files a reviewer should inspect."""
    contract_path = Path(graph_contract_path).resolve()
    domain_dir = contract_path.parent
    src_domain_dir = _PROJECT_ROOT / "src" / "tau2" / "domains" / domain

    def _path_or_none(value: str | Path | None, fallback: Path) -> Path | None:
        if value is None:
            return fallback
        return Path(value).resolve()

    return ReviewSourcePaths(
        domain_scope=_path_or_none(domain_scope_path, domain_dir / "domain_scope.md"),
        graph_contract=contract_path,
        policy=_path_or_none(policy_path, domain_dir / "policy.md"),
        runtime_defaults=_path_or_none(runtime_defaults_path, domain_dir / "runtime_defaults.yaml"),
        sampling_request=_path_or_none(sampling_request_path, domain_dir / "sampling_request.yaml"),
        stop_gate_map=_path_or_none(stop_gate_map_path, domain_dir / "stop_gate_map.yaml"),
        task_specs=Path(task_specs_path).resolve(),
        task_specs_sampled=domain_dir / "task_specs.sampled.yaml",
        task_context_bindings=domain_dir / "task_context_bindings.yaml",
        task_narrative_briefs=domain_dir / "task_narrative_briefs.yaml",
        tasks_compiled=domain_dir / "tasks.depgraph.json",
        tools_py=src_domain_dir / "tools.py",
        user_tools_py=src_domain_dir / "user_tools.py",
        environment_py=src_domain_dir / "environment.py",
    )


def _action_stage_label(action: ActionContract, world_path: str | None) -> str:
    if world_path is None:
        return "generic"
    values = sorted(
        repr(predicate.value)
        for predicate in action.requires_world
        if predicate.path == world_path and predicate.op == "eq"
    )
    if not values:
        return "generic"
    return "/".join(values)


def _binding_consumers(contract: GraphContractSpec, binding_id: str) -> list[ActionContract]:
    return [
        action
        for action in contract.actions
        if binding_id in action.tool_arg_bindings.values()
    ]


def select_representative_tasks(
    task_doc: TaskSpecsDoc,
    *,
    samples_per_family: int = 1,
) -> dict[str, list[TaskIntent]]:
    """Pick the hardest-looking tasks per family for review."""
    grouped: dict[str, list[TaskIntent]] = defaultdict(list)
    for task in task_doc.tasks:
        grouped[infer_task_family(task.task_id)].append(task)

    selected: dict[str, list[TaskIntent]] = {}
    for family, tasks in sorted(grouped.items()):
        ordered = sorted(
            tasks,
            key=lambda task: (
                -task.min_plan_length,
                -len(task.required_actions),
                task.task_id,
            ),
        )
        selected[family] = ordered[: max(1, samples_per_family)]
    return selected


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(_PROJECT_ROOT))
    except ValueError:
        return str(path)


def _summarize_task(
    contract: GraphContractSpec,
    task: TaskIntent,
    *,
    max_depth: int,
    terminal_profiles: dict[str, TerminalProfileSpec] | None = None,
    require_terminal_profile: bool = False,
) -> list[str]:
    report = run_task_preflight(
        contract,
        task,
        max_depth=max_depth,
        terminal_profiles=terminal_profiles,
        require_terminal_profile=require_terminal_profile,
        check_required_action_necessity=False,
    )
    plan = report.sat_full.plan
    repeated = [
        f"{action_id} x{count}"
        for action_id, count in sorted(Counter(plan).items())
        if count > 1
    ]

    lines = [
        f"#### `{task.task_id}`",
        f"- `min_plan_length`: {task.min_plan_length}",
        f"- `start_bindings`: {task.start_bindings or '[]'}",
        f"- `goal_capture_paths`: {task.goal_capture_paths or '[]'}",
        f"- `goal_bindings`: {task.goal_bindings or '[]'}",
        f"- `terminal_profile_id`: {task.terminal_profile_id!r}",
        f"- `required_actions` ({len(task.required_actions)}): {task.required_actions or '[]'}",
        f"- `required_precedence` count: {len(task.required_precedence)}",
        f"- `SAT_full`: {report.sat_full.sat}",
    ]
    if plan:
        lines.append(f"- `SAT_full plan` ({len(plan)}): {' -> '.join(plan)}")
    if repeated:
        lines.append(f"- repeated plan actions: {', '.join(repeated)}")
    if report.issues:
        lines.append(f"- preflight issues: {report.issues}")
    return lines


def build_review_bundle_markdown(
    *,
    domain: str,
    contract: GraphContractSpec,
    task_doc: TaskSpecsDoc,
    source_paths: ReviewSourcePaths,
    samples_per_family: int = 1,
    max_depth: int = 32,
) -> str:
    """Render a compact review bundle for an LLM/code-review pass."""
    task_count = len(task_doc.tasks)
    family_counts = Counter(infer_task_family(task.task_id) for task in task_doc.tasks)
    plan_lengths = [task.min_plan_length for task in task_doc.tasks]
    action_counts = [len(task.required_actions) for task in task_doc.tasks]
    avg_plan_length = mean(plan_lengths) if plan_lengths else 0.0
    avg_action_count = mean(action_counts) if action_counts else 0.0
    start_binding_tasks = sum(1 for task in task_doc.tasks if task.start_bindings)
    goal_binding_tasks = sum(1 for task in task_doc.tasks if task.goal_bindings)
    terminal_profile_counts = Counter(
        task.terminal_profile_id or "<missing>" for task in task_doc.tasks
    )
    volatile_bindings = [
        binding for binding in contract.bindings if binding_is_volatile(contract, binding.binding_id)
    ]

    assistant_actions = [a for a in contract.actions if a.requestor == "assistant"]
    user_actions = [a for a in contract.actions if a.requestor == "user"]
    representatives = select_representative_tasks(
        task_doc,
        samples_per_family=samples_per_family,
    )
    sampling_request_profiles: list[str] = []
    terminal_profiles_by_id: dict[str, TerminalProfileSpec] | None = None
    if source_paths.sampling_request is not None and source_paths.sampling_request.exists():
        sampling_request = load_sampling_request(source_paths.sampling_request)
        sampling_request_profiles = [
            profile.profile_id for profile in sampling_request.terminal_profiles
        ]
        terminal_profiles_by_id = {
            profile.profile_id: profile for profile in sampling_request.terminal_profiles
        }

    lines: list[str] = [
        f"# Depgraph Review Bundle: `{domain}`",
        "",
        "Use this bundle with `docs/prompts/depgraph/05-gap-review.md` in authoring-audit mode.",
        "",
        "## Reviewer Input Files",
    ]
    for label, path in source_paths.existing_items():
        lines.append(f"- `{label}`: `{_display_path(path)}`")

    lines.extend(
        [
            "",
            "## Review Rubric Targets",
            "",
            "- policy/contract parity",
            "- volatile-binding discipline",
            "- sync-rule/runtime fidelity",
            "- branch-specific consistency",
            "- terminal end-state discipline",
            "- stop-gate clarity",
            "- reward/eval fit",
            "- task realism and teachability from policy alone",
            "",
            "## Contract Snapshot",
            "",
            f"- projection fields: {len(contract.projection_fields)}",
            f"- bindings: {len(contract.bindings)}",
            f"- sync rules: {len(contract.sync_rules)}",
            f"- assistant actions: {len(assistant_actions)}",
            f"- user actions: {len(user_actions)}",
            f"- terminal profiles in sampling_request: {sampling_request_profiles or '[]'}",
            "",
            "### Bindings",
        ]
    )
    for binding in contract.bindings:
        consumers = _binding_consumers(contract, binding.binding_id)
        consumer_labels = [
            f"{action.action_id}[{_action_stage_label(action, binding.world_path)}]"
            for action in consumers
        ]
        lines.append(
                "- "
                f"`{binding.binding_id}` via `{binding.source_tool}` "
                f"(world_path={binding.world_path or 'none'}, "
                f"volatile={binding_is_volatile(contract, binding.binding_id)}, "
                f"consumers={consumer_labels or ['none']})"
            )

    if volatile_bindings:
        lines.extend(["", "### Volatile Binding Focus"])
        for binding in volatile_bindings:
            consumers = _binding_consumers(contract, binding.binding_id)
            lines.append(
                "- "
                f"`{binding.binding_id}` changes with `{binding.world_path}` and is consumed by "
                f"{[action.action_id for action in consumers] or ['no tool args']}"
            )

    lines.extend(
        [
            "",
            "## Task Set Snapshot",
            "",
            f"- tasks: {task_count}",
            f"- families: {len(family_counts)}",
            f"- tasks with `start_bindings`: {start_binding_tasks}",
            f"- tasks with `goal_bindings`: {goal_binding_tasks}",
            f"- task counts by `terminal_profile_id`: {dict(sorted(terminal_profile_counts.items()))}",
            f"- `min_plan_length` stats: min={min(plan_lengths, default=0)}, "
            f"avg={avg_plan_length:.2f}, "
            f"max={max(plan_lengths, default=0)}",
            f"- `required_actions` stats: min={min(action_counts, default=0)}, "
            f"avg={avg_action_count:.2f}, "
            f"max={max(action_counts, default=0)}",
            "",
            "### Family Counts",
        ]
    )
    for family, count in sorted(family_counts.items()):
        lines.append(f"- `{family}`: {count}")

    hardest = sorted(
        task_doc.tasks,
        key=lambda task: (-task.min_plan_length, -len(task.required_actions), task.task_id),
    )[:5]
    lines.extend(["", "### Hardest Tasks"])
    for task in hardest:
        lines.append(
            f"- `{task.task_id}`: min_plan_length={task.min_plan_length}, "
            f"required_actions={len(task.required_actions)}"
        )

    lines.extend(
        [
            "",
            "## Representative Tasks By Family",
            "",
            "These tasks include SAT plans so the reviewer can compare what the policy teaches "
            "against what the solver/runtime actually requires.",
        ]
    )
    for family, tasks in representatives.items():
        lines.extend(["", f"### `{family}`"])
        for task in tasks:
            lines.extend(
                _summarize_task(
                    contract,
                    task,
                    max_depth=max_depth,
                    terminal_profiles=terminal_profiles_by_id,
                    require_terminal_profile=terminal_profiles_by_id is not None,
                )
            )

    lines.extend(
        [
            "",
            "## Reviewer Notes",
            "",
            "- `required_actions` is deduped and may not show repeated reacquisition.",
            "- Treat repeated steps in `SAT_full plan` as the best clue for policy teaching gaps.",
            "- Findings should cite exact files/lines, not just this bundle.",
        ]
    )
    return "\n".join(lines) + "\n"
