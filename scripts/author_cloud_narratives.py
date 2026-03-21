#!/usr/bin/env python3
"""Author narrative fields for cloud_incident_response runtime tasks.

Reads narrative briefs, generates reason_for_call / known_info / ticket
for every task, writes them back into task_specs.runtime.yaml.
"""

import hashlib
import re
from pathlib import Path

import yaml

DOMAIN_DIR = Path("data/tau2/domains/cloud_incident_response")
RUNTIME_PATH = DOMAIN_DIR / "task_specs.runtime.yaml"
BRIEFS_PATH = DOMAIN_DIR / "task_narrative_briefs.yaml"


# Maps terminal_profile to a human-readable scope phrase
SCOPE_PHRASES = {
    "single_app_resolved": "application service",
    "single_infra_resolved": "infrastructure component",
    "multi_system_resolved": "multiple systems",
    "cascading_resolved": "multiple interconnected systems",
}

# ---------------------------------------------------------------------------
# Reason-for-call variant templates (4 variants, cycled)
# ---------------------------------------------------------------------------

REASON_COLD_VARIANTS = [
    "We have an active incident and I need help investigating. Our monitoring triggered an alert and we're seeing service disruption. I'm the {oncall_role} and need to work through the triage and resolution process.",
    "I'm reaching out because we got paged on an incident. Services are impacted and I need to coordinate the response. Can you help me work through diagnosis and remediation?",
    "We've got an ongoing incident affecting our production environment. I'm the {oncall_role} and need assistance triaging the issue, identifying the root cause, and driving it to resolution.",
    "There's a production incident in progress and I need support working through it. Our alerting fired and I can see service impact. Let's figure out what's going on and get things stabilized.",
]

REASON_DASHBOARD_VARIANTS = [
    "We have an active incident and I've already pulled up the monitoring dashboard. I can see some anomalies in the metrics. I'm the {oncall_role} and need help working through the rest of the triage and resolution.",
    "I'm the {oncall_role} on a production incident. I've checked the dashboard and there are clear signs of trouble in the metrics. Can you help me dig deeper and drive this to resolution?",
    "We got paged and I've already reviewed the monitoring overview. The dashboard is showing issues. I need help with the next steps to diagnose the root cause and remediate.",
    "There's an incident in progress. I pulled up our dashboards and can see service impact in the metrics. Let's work through the diagnosis and get this resolved.",
]

REASON_CANARY_COLD_VARIANTS = [
    "We have an active incident related to a recent canary deployment. Our monitoring fired and I'm seeing service disruption. I'm the {oncall_role} and need to work through the response.",
    "I'm reaching out because we got paged on an incident tied to our latest canary release. Services are impacted and I need help investigating and resolving it.",
    "We've got an ongoing production incident. It looks like it may be related to a canary deployment we pushed recently. I'm the {oncall_role} and need help with triage and resolution.",
    "There's a production incident and we recently rolled out a canary. I need support figuring out if the canary is the issue and getting things back to normal.",
]

REASON_CANARY_DASHBOARD_VARIANTS = [
    "We have an incident related to a recent canary deployment and I've already checked the monitoring dashboard. The metrics are showing problems. I'm the {oncall_role} and need help with the remaining triage and fix.",
    "I'm the {oncall_role} on a canary-related production incident. I've pulled up the dashboard and there are anomalies in the metrics. Can you help me work through diagnosis and resolution?",
    "We got paged on an incident after a canary deployment. I've reviewed the monitoring overview and the dashboard shows issues. I need help figuring out next steps.",
    "There's a canary-related incident in progress. I've checked the dashboards and can see service issues. Let's work through the root cause analysis and remediation.",
]


def _stable_variant_index(task_id: str, n_variants: int = 4) -> int:
    """Deterministic variant index from task_id hash."""
    h = int(hashlib.sha256(task_id.encode()).hexdigest(), 16)
    return h % n_variants


def _is_canary(task_id: str) -> bool:
    return task_id.startswith("canary_")


def _has_dashboard_binding(brief: dict) -> bool:
    """Check if the brief has a start_binding with value 'checked' (dashboard was reviewed)."""
    bindings = brief.get("start_bindings", [])
    if not isinstance(bindings, list):
        return False
    for b in bindings:
        if isinstance(b, dict) and b.get("value") == "checked":
            return True
    return False


def _get_start_binding_values(brief: dict) -> list[str]:
    """Get all start_binding values that must appear in known_info and ticket."""
    bindings = brief.get("start_bindings", [])
    if not isinstance(bindings, list):
        return []
    return [str(b["value"]) for b in bindings if isinstance(b, dict) and b.get("value") is not None]


def _get_undisclosed_values(brief: dict) -> set[str]:
    """Get undisclosed binding values that must NOT appear in authored text."""
    vals = brief.get("undisclosed_binding_values", [])
    if not isinstance(vals, list):
        return set()
    # Also exclude start_binding values from the undisclosed set
    start_vals = set(_get_start_binding_values(brief))
    return {str(v) for v in vals if v is not None} - start_vals


def _build_known_info(brief: dict, task_id: str) -> str:
    """Build known_info from the brief. Must include entity name and start_binding values."""
    name = brief["entity_context"]["name"]
    incident_id = brief["entity_context"]["incident_id"]
    has_dashboard = _has_dashboard_binding(brief)

    parts = [f"You are {name}."]
    parts.append(f"There is an active incident ({incident_id}) that you are investigating.")

    if has_dashboard:
        parts.append("You have already checked the monitoring dashboard and can see anomalies in the service metrics.")
    elif "_cold_" in task_id:
        parts.append("You have not yet checked any dashboards or diagnostic tools.")

    if _is_canary(task_id):
        parts.append("A canary deployment was recently pushed to the environment.")

    return " ".join(parts)


def _safe_fault_phrase(brief: dict) -> str:
    """Return a generic fault phrase that does NOT contain any undisclosed binding value."""
    # Always safe: "service disruption" contains none of the undisclosed values
    return "service disruption"


def _build_ticket(brief: dict, task_id: str) -> str:
    """Build ticket string. Must include entity name and start_binding values."""
    name = brief["entity_context"]["name"]
    incident_id = brief["entity_context"]["incident_id"]
    oncall_role = brief["entity_context"].get("oncall_role", "on-call engineer")
    terminal_profile = brief.get("terminal_profile", "")
    has_dashboard = _has_dashboard_binding(brief)

    scope = SCOPE_PHRASES.get(terminal_profile, "production service")
    fault_desc = _safe_fault_phrase(brief)

    resolved_parts = []
    for cond in brief.get("resolved_when", []):
        unmet = cond.get("unmet_reason", "")
        if unmet:
            resolved_parts.append(unmet.rstrip("."))

    ticket_parts = [
        f"Production incident {incident_id} reported by {oncall_role} {name}.",
        f"Alert triggered for {scope} — initial indicators suggest {fault_desc}.",
    ]

    if has_dashboard:
        ticket_parts.append("Reporter has already checked the monitoring dashboard.")

    if _is_canary(task_id):
        ticket_parts.append("A canary deployment is active in the environment.")

    resolution_desc = " and ".join(resolved_parts) if resolved_parts else "full incident resolution"
    ticket_parts.append(
        f"Incident will be considered resolved when: {resolution_desc}."
    )

    return " ".join(ticket_parts)


def _build_reason_for_call(brief: dict, task_id: str) -> str:
    """Build reason_for_call using variant cycling."""
    oncall_role = brief["entity_context"].get("oncall_role", "on-call engineer")
    idx = _stable_variant_index(task_id)
    has_dashboard = _has_dashboard_binding(brief)
    canary = _is_canary(task_id)

    if canary and has_dashboard:
        template = REASON_CANARY_DASHBOARD_VARIANTS[idx]
    elif canary:
        template = REASON_CANARY_COLD_VARIANTS[idx]
    elif has_dashboard:
        template = REASON_DASHBOARD_VARIANTS[idx]
    else:
        template = REASON_COLD_VARIANTS[idx]

    return template.format(oncall_role=oncall_role)


def _validate_no_leaks(task_id: str, brief: dict, reason: str, known: str, ticket: str) -> list[str]:
    """Pre-write validation: check that undisclosed values don't appear in authored text."""
    issues = []
    undisclosed = _get_undisclosed_values(brief)
    fields = {"reason_for_call": reason, "known_info": known, "ticket": ticket}
    for val in undisclosed:
        for field_name, text in fields.items():
            if val and val in text:
                issues.append(f"{task_id} {field_name} leaks undisclosed value '{val}'")
    return issues


def main():
    print("Loading briefs...")
    briefs_data = yaml.safe_load(BRIEFS_PATH.read_text())
    brief_index = {t["task_id"]: t for t in briefs_data["tasks"]}

    print("Loading runtime specs...")
    runtime_data = yaml.safe_load(RUNTIME_PATH.read_text())

    tasks = runtime_data["tasks"]
    authored = 0
    skipped = 0
    all_issues = []

    for task in tasks:
        task_id = task["task_id"]
        brief = brief_index.get(task_id)
        if brief is None:
            print(f"  WARNING: no brief for {task_id}")
            skipped += 1
            continue

        runtime = task.get("runtime", {})
        if runtime is None:
            print(f"  WARNING: no runtime block for {task_id}")
            skipped += 1
            continue

        reason = _build_reason_for_call(brief, task_id)
        known = _build_known_info(brief, task_id)
        ticket = _build_ticket(brief, task_id)

        # Validate before writing
        issues = _validate_no_leaks(task_id, brief, reason, known, ticket)
        all_issues.extend(issues)

        runtime["reason_for_call"] = reason
        runtime["known_info"] = known
        runtime["ticket"] = ticket
        authored += 1

    if all_issues:
        print(f"\nWARNING: {len(all_issues)} leak issues detected:")
        for issue in all_issues[:20]:
            print(f"  - {issue}")
        if len(all_issues) > 20:
            print(f"  ... and {len(all_issues) - 20} more")

    print(f"\nAuthored {authored} tasks, skipped {skipped}")

    print("Writing runtime specs...")
    with open(RUNTIME_PATH, "w") as f:
        yaml.dump(runtime_data, f, default_flow_style=False, allow_unicode=True, width=200, sort_keys=False)

    print("Done.")


if __name__ == "__main__":
    main()
