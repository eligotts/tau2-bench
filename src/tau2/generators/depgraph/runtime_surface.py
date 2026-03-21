"""Strict checks for the runtime authoring surface between scaffold and authored specs."""

from __future__ import annotations

from typing import Any

from tau2.generators.depgraph.types import RuntimeTaskSpec, TaskIntent, TaskSpecsDoc

_ALLOWED_RUNTIME_FIELDS = {"reason_for_call", "known_info", "ticket"}
_PLACEHOLDER_TOKEN = "__AUTHOR_ME__"


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return _PLACEHOLDER_TOKEN in value
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    return False


def _task_index(task_doc: TaskSpecsDoc) -> tuple[dict[str, TaskIntent], list[str]]:
    index: dict[str, TaskIntent] = {}
    issues: list[str] = []
    for task in task_doc.tasks:
        if task.task_id in index:
            issues.append(f"duplicate task_id '{task.task_id}'")
            continue
        index[task.task_id] = task
    return index, issues


def _strip_injected_stop_gate(initialization_actions: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not initialization_actions:
        return []
    return [
        call
        for call in initialization_actions
        if not (call.get("env_type") == "user" and call.get("func_name") == "set_stop_gate")
    ]


def _normalized_runtime_dump(runtime: RuntimeTaskSpec) -> dict[str, Any]:
    runtime_dump = runtime.model_dump(mode="python")
    runtime_dump["initialization_actions"] = _strip_injected_stop_gate(
        runtime_dump.get("initialization_actions")
    )
    return runtime_dump


def _compare_non_runtime_fields(scaffold: TaskIntent, authored: TaskIntent) -> list[str]:
    issues: list[str] = []
    for field_name in (
        "start_world",
        "start_bindings",
        "goal_world",
        "required_actions",
        "min_plan_length",
    ):
        if getattr(scaffold, field_name) != getattr(authored, field_name):
            issues.append(
                f"task '{scaffold.task_id}' changed non-runtime field '{field_name}'"
            )
    return issues


def _compare_runtime(
    scaffold: RuntimeTaskSpec,
    authored: RuntimeTaskSpec,
    *,
    task_id: str,
) -> list[str]:
    issues: list[str] = []

    scaffold_dump = _normalized_runtime_dump(scaffold)
    authored_dump = _normalized_runtime_dump(authored)

    for field_name, scaffold_value in scaffold_dump.items():
        authored_value = authored_dump.get(field_name)
        if field_name in _ALLOWED_RUNTIME_FIELDS:
            continue
        if authored_value != scaffold_value:
            issues.append(
                f"task '{task_id}' changed disallowed runtime field '{field_name}'"
            )

    for field_name in sorted(_ALLOWED_RUNTIME_FIELDS):
        authored_value = authored_dump.get(field_name)
        if not isinstance(authored_value, str) or not authored_value.strip():
            issues.append(
                f"task '{task_id}' runtime.{field_name} must be a non-empty authored string"
            )
            continue
        if _PLACEHOLDER_TOKEN in authored_value:
            issues.append(
                f"task '{task_id}' runtime.{field_name} still contains placeholder token"
            )

    return issues


def check_runtime_author_surface(
    scaffold_doc: TaskSpecsDoc,
    authored_doc: TaskSpecsDoc,
) -> list[str]:
    """Validate that authored runtime specs only modify the allowed narrative fields."""
    issues: list[str] = []

    if scaffold_doc.version != authored_doc.version:
        issues.append(
            "task spec version changed between scaffold and authored files: "
            f"{scaffold_doc.version} -> {authored_doc.version}"
        )

    scaffold_index, scaffold_index_issues = _task_index(scaffold_doc)
    authored_index, authored_index_issues = _task_index(authored_doc)
    issues.extend(scaffold_index_issues)
    issues.extend(authored_index_issues)

    missing = sorted(set(scaffold_index) - set(authored_index))
    extra = sorted(set(authored_index) - set(scaffold_index))
    if missing:
        issues.append(f"authored file missing tasks: {missing}")
    if extra:
        issues.append(f"authored file has unknown tasks: {extra}")

    for task_id in sorted(set(scaffold_index) & set(authored_index)):
        scaffold_task = scaffold_index[task_id]
        authored_task = authored_index[task_id]

        issues.extend(_compare_non_runtime_fields(scaffold_task, authored_task))

        if scaffold_task.runtime is None:
            issues.append(f"scaffold task '{task_id}' is missing runtime block")
            continue
        if authored_task.runtime is None:
            issues.append(f"authored task '{task_id}' is missing runtime block")
            continue

        issues.extend(
            _compare_runtime(scaffold_task.runtime, authored_task.runtime, task_id=task_id)
        )

    authored_dump = authored_doc.model_dump(mode="python")
    if _contains_placeholder(authored_dump):
        issues.append("authored runtime file still contains __AUTHOR_ME__ placeholder text")

    return issues
