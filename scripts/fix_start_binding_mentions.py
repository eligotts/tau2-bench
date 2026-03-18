"""Fix runtime known_info and ticket to include literal start_binding values.

The narrative quality checker does a simple substring check:
  if value and value not in known_info
So the text MUST contain the exact string value (e.g. 'flat_tire' not 'flat tire').

This script:
1. Reads narrative briefs to find which tasks have start_bindings and their values
2. Reads the runtime file
3. For each task with start_bindings, checks if binding values appear in known_info/ticket
4. If not, appends a parenthetical tag with the literal binding value
5. Also checks for goal_binding_do_not_disclose leaks (conflicts)
6. Writes back the runtime file
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


BRIEFS_PATH = Path("data/tau2/domains/daily_planner/task_narrative_briefs.yaml")
RUNTIME_PATH = Path("data/tau2/domains/daily_planner/task_specs.runtime.yaml")

# Map binding values to a natural parenthetical label
LABEL_MAP = {
    "flat_tire": "car issue: flat_tire",
    "has_conflict": "calendar status: has_conflict",
    "reported": "maintenance status: reported",
    "True": "pre-known: True",
    "False": "pre-known: False",
    "broke": "budget: broke",
    "tight": "budget: tight",
    "plenty": "budget: plenty",
}


def get_label(value: str) -> str:
    return LABEL_MAP.get(value, f"status: {value}")


def extract_start_binding_values(brief: dict) -> list[str]:
    summary = brief.get("start_state_summary", {})
    bindings = summary.get("bindings", [])
    values = []
    for b in bindings:
        if isinstance(b, dict) and "value" in b:
            v = str(b["value"])
            if v:
                values.append(v)
    return values


def extract_goal_binding_do_not_disclose(brief: dict) -> set[str]:
    vals = brief.get("goal_binding_do_not_disclose", []) or []
    return {str(v) for v in vals if v is not None}


def main():
    briefs = yaml.safe_load(BRIEFS_PATH.read_text())
    brief_index = {t["task_id"]: t for t in briefs["tasks"]}

    runtime = yaml.safe_load(RUNTIME_PATH.read_text())

    fixed_known = 0
    fixed_ticket = 0
    briefs_fixed = 0

    # Phase 1: Fix structural conflicts in briefs --
    # If a value is both a start_binding and in goal_binding_do_not_disclose,
    # remove it from do_not_disclose (start_binding = "user knows this" takes priority).
    for brief in briefs["tasks"]:
        start_vals = set(extract_start_binding_values(brief))
        dnd = brief.get("goal_binding_do_not_disclose")
        if not dnd or not start_vals:
            continue
        # Remove conflicting values from do_not_disclose
        new_dnd = [v for v in dnd if str(v) not in start_vals]
        if len(new_dnd) < len(dnd):
            removed = [str(v) for v in dnd if str(v) in start_vals]
            print(f"  briefs fix: {brief['task_id']}: removed {removed} from goal_binding_do_not_disclose")
            brief["goal_binding_do_not_disclose"] = new_dnd if new_dnd else []
            briefs_fixed += 1

    # Rebuild index after brief fixes
    brief_index = {t["task_id"]: t for t in briefs["tasks"]}

    # Phase 2: Fix runtime text to include start_binding values
    for task in runtime["tasks"]:
        tid = task["task_id"]
        brief = brief_index.get(tid)
        if brief is None:
            continue

        start_vals = extract_start_binding_values(brief)
        if not start_vals:
            continue

        dnd = extract_goal_binding_do_not_disclose(brief)
        rt = task["runtime"]
        known_info = rt.get("known_info") or ""
        ticket = rt.get("ticket") or ""

        for val in start_vals:
            # After phase 1, there should be no conflicts, but guard anyway
            if val in dnd:
                print(f"  WARNING: unresolved conflict {tid}: '{val}' in both start_binding and do_not_disclose")
                continue

            tag = f"({get_label(val)})"

            if val not in known_info:
                known_info = known_info.rstrip() + " " + tag
                fixed_known += 1

            if val not in ticket:
                ticket = ticket.rstrip() + " " + tag
                fixed_ticket += 1

        rt["known_info"] = known_info
        rt["ticket"] = ticket

    # Write back both files
    BRIEFS_PATH.write_text(yaml.dump(briefs, default_flow_style=False, allow_unicode=True, width=120, sort_keys=False))
    RUNTIME_PATH.write_text(yaml.dump(runtime, default_flow_style=False, allow_unicode=True, width=120, sort_keys=False))

    print(f"\nFixed {briefs_fixed} brief entries (removed conflicting do_not_disclose values)")
    print(f"Fixed {fixed_known} known_info fields, {fixed_ticket} ticket fields in runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
