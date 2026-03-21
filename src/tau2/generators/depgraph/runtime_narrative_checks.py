"""Narrative-content checks for authored runtime fields."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from tau2.generators.depgraph.types import TaskSpecsDoc

_PLACEHOLDER_TOKEN = "__AUTHOR_ME__"
_INTERNAL_PATH_RE = re.compile(r"\b(?:agent|user)\.[A-Za-z_][A-Za-z0-9_.\[\]]*")


def load_narrative_briefs(path: str | Path) -> dict[str, Any]:
    """Load narrative briefs YAML as a dict."""
    payload = yaml.safe_load(Path(path).read_text())
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML object at root for {path}")
    return payload


def _task_brief_index(briefs: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    issues: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    tasks = briefs.get("tasks")
    if not isinstance(tasks, list):
        return {}, ["narrative briefs missing top-level 'tasks' list"]
    for entry in tasks:
        if not isinstance(entry, dict):
            issues.append("narrative brief task entry must be a YAML object")
            continue
        task_id = entry.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            issues.append("narrative brief task entry missing non-empty task_id")
            continue
        if task_id in index:
            issues.append(f"narrative briefs duplicate task_id '{task_id}'")
            continue
        index[task_id] = entry
    return index, issues


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _contains_internal_path(text: str) -> bool:
    return bool(_INTERNAL_PATH_RE.search(text))



def _extract_start_binding_values(brief: dict[str, Any]) -> list[str]:
    # New brief format: start_bindings at top level
    bindings = brief.get("start_bindings")
    if not isinstance(bindings, list):
        # Fallback: old format with start_state_summary.bindings
        summary = brief.get("start_state_summary")
        if isinstance(summary, dict):
            bindings = summary.get("bindings", [])
        else:
            return []
    values: list[str] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        value = binding.get("value")
        if value is None:
            continue
        values.append(str(value))
    return values


def _extract_undisclosed_binding_values(brief: dict[str, Any]) -> list[str]:
    values = brief.get("undisclosed_binding_values")
    if not isinstance(values, list):
        return []
    return [str(v) for v in values if v is not None]


def _extract_required_actions(brief: dict[str, Any]) -> list[str]:
    chain = brief.get("required_actions") or brief.get("required_action_chain")
    if not isinstance(chain, list):
        return []
    actions: list[str] = []
    for item in chain:
        if isinstance(item, str) and item.strip():
            actions.append(item.strip())
    return actions


def check_runtime_narratives(
    runtime_doc: TaskSpecsDoc,
    narrative_briefs: dict[str, Any],
) -> list[str]:
    """Check authored runtime narrative fields follow prompt constraints."""
    issues: list[str] = []
    brief_index, brief_issues = _task_brief_index(narrative_briefs)
    issues.extend(brief_issues)

    for task in runtime_doc.tasks:
        if task.runtime is None:
            issues.append(f"task '{task.task_id}' missing runtime block")
            continue

        brief = brief_index.get(task.task_id)
        if brief is None:
            issues.append(f"task '{task.task_id}' missing narrative brief entry")
            continue

        reason_for_call = _to_text(task.runtime.reason_for_call).strip()
        known_info = _to_text(task.runtime.known_info).strip()
        ticket = _to_text(task.runtime.ticket).strip()

        field_map = {
            "reason_for_call": reason_for_call,
            "known_info": known_info,
            "ticket": ticket,
        }
        for field_name, text in field_map.items():
            if not text:
                issues.append(
                    f"task '{task.task_id}' runtime.{field_name} must be a non-empty authored string"
                )
                continue
            if _PLACEHOLDER_TOKEN in text:
                issues.append(
                    f"task '{task.task_id}' runtime.{field_name} still contains placeholder token"
                )
            if _contains_internal_path(text):
                issues.append(
                    f"task '{task.task_id}' runtime.{field_name} should not expose internal world paths"
                )

        required_actions = _extract_required_actions(brief)
        all_text = " ".join(field_map.values()).lower()
        for action_id in required_actions:
            if action_id.lower() in all_text:
                issues.append(
                    f"task '{task.task_id}' authored text leaks required action id '{action_id}'"
                )

        for action in task.runtime.actions:
            tool_name = action.name.strip()
            if not tool_name:
                continue
            if tool_name.lower() in all_text:
                issues.append(
                    f"task '{task.task_id}' authored text leaks tool name '{tool_name}'"
                )

        start_binding_values = _extract_start_binding_values(brief)
        for value in start_binding_values:
            if value and value not in known_info:
                issues.append(
                    f"task '{task.task_id}' known_info missing start-binding value '{value}'"
                )
            if value and value not in ticket:
                issues.append(
                    f"task '{task.task_id}' ticket missing start-binding value '{value}'"
                )

        start_binding_value_set = set(start_binding_values)
        for value in _extract_undisclosed_binding_values(brief):
            if value in start_binding_value_set:
                continue
            for field_name, text in field_map.items():
                if value and value in text:
                    issues.append(
                        f"task '{task.task_id}' runtime.{field_name} leaks undisclosed binding "
                        f"value '{value}' — this must be acquired during task execution, "
                        f"not pre-disclosed"
                    )

    runtime_task_ids = {task.task_id for task in runtime_doc.tasks}
    extra_brief_ids = sorted(set(brief_index) - runtime_task_ids)
    if extra_brief_ids:
        issues.append(
            "narrative briefs contain task IDs not present in runtime specs: "
            + ", ".join(extra_brief_ids)
        )

    return issues
