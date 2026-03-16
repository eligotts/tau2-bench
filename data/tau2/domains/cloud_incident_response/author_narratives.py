"""Batch-author runtime narratives for cloud_incident_response tasks.

Reads narrative briefs + runtime yaml, fills reason_for_call / known_info / ticket,
writes updated runtime yaml.
"""

import re
import yaml
from pathlib import Path


def _parse_broken_systems(world_lines: list[str]) -> dict[str, str]:
    """Parse start_world lines to find broken systems and their states."""
    broken = {}
    for line in world_lines:
        m = re.match(r"agent\.(\w+)\[.*?\]\.\w+_health\s*=\s*'(\w+)'", line)
        if m:
            system, status = m.group(1), m.group(2)
            if status != "healthy":
                broken[system] = status
        # Special: dns
        m = re.match(r"agent\.dns\[.*?\]\.resolution_state\s*=\s*'(\w+)'", line)
        if m and m.group(1) != "correct":
            broken["dns"] = m.group(1)
        # Special: deploy_version
        m = re.match(r"agent\.app\[.*?\]\.deploy_version\s*=\s*'(\w+)'", line)
        if m and m.group(1) == "canary":
            broken["deploy"] = "canary"
        # Special: vacuum
        m = re.match(r"agent\.db\[.*?\]\.vacuum_state\s*=\s*'(\w+)'", line)
        if m and m.group(1) == "needs_vacuum":
            broken["vacuum"] = "needs_vacuum"
        # Special: dlq
        m = re.match(r"agent\.queue\[.*?\]\.dlq_state\s*=\s*'(\w+)'", line)
        if m and m.group(1) == "has_messages":
            broken["dlq"] = "has_messages"
    return broken


SYSTEM_NAMES = {
    "app": "application",
    "db": "database",
    "cache": "cache layer",
    "auth": "authentication service",
    "lb": "load balancer",
    "queue": "message queue",
    "dns": "DNS",
}

STATUS_DESCRIPTIONS = {
    # App
    "crashing": "crashing with repeated panics",
    "memory_leak": "experiencing a memory leak",
    "high_latency": "showing high latency",
    "crash_loop": "stuck in a crash loop",
    "unreachable": "completely unreachable",
    "degraded": "degraded and responding slowly",
    # DB
    "locked": "locked by a long-running transaction",
    "corrupted": "showing data corruption",
    "replication_lag": "suffering from replication lag",
    "disk_full": "out of disk space",
    # Cache
    "stale": "serving stale data",
    "cold": "completely cold with zero hit rate",
    "eviction_storm": "in an eviction storm",
    "connection_refused": "refusing connections",
    # Auth
    "token_expired": "reporting expired tokens",
    "cert_invalid": "showing invalid certificates",
    "rate_limited": "rate-limited from excessive retries",
    "misconfigured": "misconfigured",
    # LB
    "misconfigured": "misconfigured",
    "overloaded": "overloaded and dropping connections",
    "draining": "stuck in drain mode",
    "backend_unhealthy": "reporting unhealthy backends",
    # Queue
    "consumer_dead": "has dead consumers",
    "poison_pill": "blocked by a poison pill message",
    "backpressure": "under backpressure",
    "split_brain": "in a split-brain state",
    # DNS
    "stale_cache": "has stale cached records",
    "misconfigured": "misconfigured",
    "propagating": "still propagating changes",
}


def _describe_broken(broken: dict[str, str]) -> str:
    """Create a natural description of broken systems."""
    parts = []
    for sys, status in broken.items():
        if sys in ("deploy", "vacuum", "dlq"):
            continue  # handled separately
        name = SYSTEM_NAMES.get(sys, sys)
        desc = STATUS_DESCRIPTIONS.get(status, f"in {status} state")
        parts.append(f"the {name} is {desc}")
    if "deploy" in broken:
        parts.append("a canary deployment is active")
    return parts


def _primary_symptom(broken: dict[str, str]) -> str:
    """Pick the most user-visible symptom for reason_for_call."""
    # Priority: app > lb > dns > db > cache > auth > queue
    priority = ["app", "lb", "dns", "db", "cache", "auth", "queue"]
    for sys in priority:
        if sys in broken:
            status = broken[sys]
            name = SYSTEM_NAMES.get(sys, sys)
            desc = STATUS_DESCRIPTIONS.get(status, f"in {status} state")
            return f"the {name} is {desc}"
    if "deploy" in broken:
        return "something is wrong after a canary deployment"
    return "multiple systems are showing alerts"


def _scope_description(world_lines: list[str]) -> str:
    """Get the scope from start_world."""
    for line in world_lines:
        m = re.match(r"agent\.incident\[.*?\]\.scope\s*=\s*'(\w+)'", line)
        if m:
            scope = m.group(1)
            return {
                "single_app": "application-level",
                "single_infra": "infrastructure",
                "multi_system": "multi-system",
                "cascading": "cascading failure",
            }.get(scope, scope)
    return ""


def author_narratives(briefs_path: str, runtime_path: str, out_path: str) -> None:
    briefs_doc = yaml.safe_load(Path(briefs_path).read_text())
    runtime_doc = yaml.safe_load(Path(runtime_path).read_text())

    briefs_by_id = {b["task_id"]: b for b in briefs_doc["tasks"]}

    for task in runtime_doc["tasks"]:
        task_id = task["task_id"]
        brief = briefs_by_id.get(task_id)
        if brief is None:
            continue

        name = brief["entity_context"]["name"]
        world = brief["start_state_summary"]["world"]
        broken = _parse_broken_systems(world)
        broken_descs = _describe_broken(broken)
        primary = _primary_symptom(broken)
        scope_desc = _scope_description(world)
        num_broken = len([s for s in broken if s not in ("deploy", "vacuum", "dlq")])

        # reason_for_call: first person, conversational
        if num_broken == 1:
            reason = f"I'm getting paged — {primary}. Our monitoring is lighting up and I need help figuring out what's going on and getting it fixed."
        elif num_broken == 2:
            reason = f"We have a production incident — {primary} and there seem to be other issues too. Multiple alerts firing. Can you help me investigate and resolve this?"
        elif "deploy" in broken:
            reason = f"Things went sideways after our canary deployment — {primary}. I'm seeing cascading alerts and need help stabilizing everything."
        else:
            reason = f"Major production incident — {primary} and multiple other systems are affected. This looks like a {scope_desc} incident. I need help triaging and getting everything back to normal."

        # known_info: second person, factual
        known_parts = [f"You are {name}, an on-call engineer responding to a production incident."]
        if num_broken == 1:
            known_parts.append(f"Monitoring shows {broken_descs[0]}.")
        elif num_broken <= 3:
            known_parts.append(f"Monitoring shows: {', '.join(broken_descs[:3])}.")
        else:
            known_parts.append(f"Monitoring shows widespread issues: {', '.join(broken_descs[:3])}, and {num_broken - 3} more system(s) affected.")
        if "deploy" in broken:
            known_parts.append("A canary deployment is currently active on the application.")
        # If dashboard is pre-known (start_bindings includes K.dashboard_overview),
        # include the incident status value "investigating" for preflight visibility.
        start_bindings = task.get("start_bindings", [])
        if "K.dashboard_overview" in start_bindings:
            known_parts.append("The incident is currently investigating — dashboard has been checked.")
        else:
            known_parts.append("Investigation has not started yet.")

        known_info = " ".join(known_parts)

        # ticket: third person, agent-facing
        if num_broken == 1:
            sys_name = list(broken.keys())[0]
            if sys_name not in ("deploy", "vacuum", "dlq"):
                ticket_problem = f"Production incident: {SYSTEM_NAMES.get(sys_name, sys_name)} {STATUS_DESCRIPTIONS.get(broken[sys_name], 'unhealthy')}."
            else:
                ticket_problem = f"Production incident affecting application systems."
        else:
            affected = [SYSTEM_NAMES.get(s, s) for s in broken if s not in ("deploy", "vacuum", "dlq")]
            ticket_problem = f"Production incident affecting {', '.join(affected[:3])}{'and more' if len(affected) > 3 else ''}."

        if "K.dashboard_overview" in start_bindings:
            ticket = f"{ticket_problem} On-call engineer: {name}. Incident status: investigating — dashboard already reviewed. They will consider the issue resolved when all affected systems are healthy, incident communications have been sent, and the smoke test passes."
        else:
            ticket = f"{ticket_problem} On-call engineer: {name}. They will consider the issue resolved when all affected systems are healthy, incident communications have been sent, and the smoke test passes."

        task["runtime"]["reason_for_call"] = reason
        task["runtime"]["known_info"] = known_info
        task["runtime"]["ticket"] = ticket

    Path(out_path).write_text(yaml.safe_dump(runtime_doc, sort_keys=False, allow_unicode=True, width=200))
    print(f"[PASS] Authored narratives for {len(runtime_doc['tasks'])} tasks -> {out_path}")


if __name__ == "__main__":
    author_narratives(
        "data/tau2/domains/cloud_incident_response/task_narrative_briefs.yaml",
        "data/tau2/domains/cloud_incident_response/task_specs.runtime.yaml",
        "data/tau2/domains/cloud_incident_response/task_specs.runtime.yaml",
    )
