"""Stop-gate mapping and runtime injection utilities for depgraph tasks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from tau2.generators.depgraph.types import EnvFunctionCallSpec, TaskIntent, TaskSpecsDoc


def _stable_value_key(value: Any) -> str:
    if isinstance(value, (str, int, float, bool, type(None))):
        return repr(value)
    return json.dumps(value, sort_keys=True)


class StopGateRule(BaseModel):
    """Map one goal-world equality to one user-observable checker field."""

    goal_path: str
    goal_value: Any
    check_field: str
    check_op: Literal["eq"] = "eq"
    expected: Any
    unmet_reason: str

    @model_validator(mode="after")
    def validate_rule(self) -> "StopGateRule":
        if not self.goal_path.strip():
            raise ValueError("stop-gate goal_path cannot be empty")
        if not self.check_field.strip():
            raise ValueError("stop-gate check_field cannot be empty")
        if not self.unmet_reason.strip():
            raise ValueError("stop-gate unmet_reason cannot be empty")
        return self


class StopGateMapDoc(BaseModel):
    """Domain-level mapping from sampled goals to checker criteria."""

    version: int = 1
    rules: list[StopGateRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_doc(self) -> "StopGateMapDoc":
        if self.version != 1:
            raise ValueError(f"Unsupported stop-gate map version: {self.version}")
        seen: set[tuple[str, str]] = set()
        for rule in self.rules:
            key = (rule.goal_path, _stable_value_key(rule.goal_value))
            if key in seen:
                raise ValueError(
                    "Duplicate stop-gate rule for goal "
                    f"{rule.goal_path} == {rule.goal_value!r}"
                )
            seen.add(key)
        return self


def load_stop_gate_map(path: str | Path) -> StopGateMapDoc:
    """Load stop-gate map YAML."""
    payload = yaml.safe_load(Path(path).read_text())
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML object at root for stop-gate map: {path}")
    return StopGateMapDoc.model_validate(payload)


def _criteria_from_task_goal(
    task: TaskIntent,
    stop_gate_map: StopGateMapDoc,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Map the user-observable subset of goal_world into stop-gate criteria.

    `goal_world` may be the full terminal state for env assertions and compile-time
    validation. `stop_gate_map` intentionally covers only the subset that a user-facing
    checker like `check_resolution_status` can observe and report.
    """
    index = {
        (rule.goal_path, _stable_value_key(rule.goal_value)): rule
        for rule in stop_gate_map.rules
    }
    criteria: list[dict[str, Any]] = []
    issues: list[str] = []
    mapped_any = False
    for goal in task.goal_world:
        if goal.op != "eq":
            issues.append(
                f"Task '{task.task_id}' has unsupported goal op '{goal.op}' "
                "(stop gate supports eq only)."
            )
            continue
        key = (goal.path, _stable_value_key(goal.value))
        rule = index.get(key)
        if rule is None:
            continue
        mapped_any = True
        criteria.append(
            {
                "check_field": rule.check_field,
                "op": rule.check_op,
                "expected": rule.expected,
                "unmet_reason": rule.unmet_reason,
            }
        )
    if not mapped_any:
        issues.append(
            f"Task '{task.task_id}' has no user-observable stop-gate criteria mapped from goal_world"
        )
    return criteria, issues


def _upsert_set_stop_gate(
    task: TaskIntent,
    criteria: list[dict[str, Any]],
) -> None:
    assert task.runtime is not None
    call = EnvFunctionCallSpec(
        env_type="user",
        func_name="set_stop_gate",
        arguments={"criteria": criteria},
    )
    for idx, existing in enumerate(task.runtime.initialization_actions):
        if existing.env_type == "user" and existing.func_name == "set_stop_gate":
            task.runtime.initialization_actions[idx] = call
            break
    else:
        task.runtime.initialization_actions.append(call)


def _ensure_instruction_gate(instructions: str) -> str:
    lower = instructions.lower()
    additions: list[str] = []
    if "check_resolution_status" not in lower:
        additions.append(
            "Before deciding the issue is resolved, call check_resolution_status."
        )
    if "resolved=true" not in lower and "resolved = true" not in lower:
        additions.append(
            "Only emit ###STOP### when check_resolution_status returns resolved=true."
        )
    if "if resolved=false" not in lower and "if resolved = false" not in lower:
        additions.append(
            "If resolved=false, report the unmet items and ask the assistant for the next step."
        )
    if not additions:
        return instructions
    spacer = "" if instructions.endswith(" ") else " "
    return instructions + spacer + " ".join(additions)


def inject_stop_gates(
    task_doc: TaskSpecsDoc,
    stop_gate_map: StopGateMapDoc,
    *,
    update_instructions: bool = True,
) -> list[str]:
    """Inject stop-gate init action and strict instruction text into runtime tasks."""
    issues: list[str] = []
    for task in task_doc.tasks:
        if task.runtime is None:
            issues.append(f"Task '{task.task_id}' missing runtime block for stop-gate injection")
            continue
        criteria, criteria_issues = _criteria_from_task_goal(task, stop_gate_map)
        issues.extend(criteria_issues)
        if criteria_issues:
            continue
        _upsert_set_stop_gate(task, criteria)
        if update_instructions:
            task.runtime.task_instructions = _ensure_instruction_gate(
                task.runtime.task_instructions.strip()
            )
    return issues


def validate_stop_gates(task_doc: TaskSpecsDoc, stop_gate_map: StopGateMapDoc) -> list[str]:
    """Validate runtime tasks have a complete stop-gate mapping and strict stop instructions."""
    issues: list[str] = []
    expected_by_task: dict[str, list[dict[str, Any]]] = {}
    for task in task_doc.tasks:
        criteria, criteria_issues = _criteria_from_task_goal(task, stop_gate_map)
        issues.extend(criteria_issues)
        expected_by_task[task.task_id] = criteria

    for task in task_doc.tasks:
        if task.runtime is None:
            issues.append(f"Task '{task.task_id}' missing runtime block")
            continue

        gate_calls = [
            call
            for call in task.runtime.initialization_actions
            if call.env_type == "user" and call.func_name == "set_stop_gate"
        ]
        if not gate_calls:
            issues.append(f"Task '{task.task_id}' is missing user.set_stop_gate initialization action")
            continue
        if len(gate_calls) > 1:
            issues.append(f"Task '{task.task_id}' has multiple user.set_stop_gate initialization actions")
            continue

        actual = gate_calls[0].arguments.get("criteria")
        expected = expected_by_task.get(task.task_id, [])
        if actual != expected:
            issues.append(
                f"Task '{task.task_id}' set_stop_gate criteria do not match mapped goal criteria"
            )

        lowered = task.runtime.task_instructions.lower()
        if "check_resolution_status" not in lowered:
            issues.append(
                f"Task '{task.task_id}' instructions must require check_resolution_status before stop"
            )
        if "###stop###" not in lowered:
            issues.append(
                f"Task '{task.task_id}' instructions must include ###STOP### token"
            )

    return issues
