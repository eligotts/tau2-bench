#!/usr/bin/env python3
"""Author narrative fields for all cloud_incident_response runtime tasks.

IMPORTANT: Symptom descriptions must NEVER contain any undisclosed binding values.
Banned words (exact substring match): backend_unhealthy, backpressure, cert_invalid,
cold, connection_refused, consumer_dead, correct, corrupted, crash_loop, crashing,
degraded, disk_full, draining, eviction_storm, healthy, high_latency, locked,
memory_leak, misconfigured, not_checked, overloaded, poison_pill, propagating,
rate_limited, replication_lag, split_brain, stale, stale_cache, token_expired,
unreachable.
"""

import hashlib
import re
import sys
from pathlib import Path

import yaml


RUNTIME_PATH = Path("data/tau2/domains/cloud_incident_response/task_specs.runtime.yaml")
BRIEFS_PATH = Path("data/tau2/domains/cloud_incident_response/task_narrative_briefs.yaml")

# All undisclosed binding values that must never appear as substrings
BANNED_WORDS = {
    "backend_unhealthy", "backpressure", "cert_invalid", "cold",
    "connection_refused", "consumer_dead", "correct", "corrupted",
    "crash_loop", "crashing", "degraded", "disk_full", "draining",
    "eviction_storm", "healthy", "high_latency", "locked",
    "memory_leak", "misconfigured", "not_checked", "overloaded",
    "poison_pill", "propagating", "rate_limited", "replication_lag",
    "split_brain", "stale", "stale_cache", "token_expired",
    "unreachable",
}

# ---------------------------------------------------------------------------
# Fault-label -> safe human-readable symptom (no banned words as substrings)
# ---------------------------------------------------------------------------
FAULT_SYMPTOMS = {
    # App faults
    "app_crashing": "the application keeps going down unexpectedly",
    "app_crash_loop": "the application cannot stay running and keeps restarting",
    "app_memory_leak": "the application is using more and more memory over time",
    "app_high_latency": "the application response times are way too slow",
    "app_unreachable": "the application is not responding to any requests",
    # DB faults
    "db_corrupted": "the database has data integrity problems",
    "db_degraded": "the database is performing much worse than normal",
    "db_degraded_vacuum": "the database is slow and appears to need maintenance",
    "db_disk_full": "the database server is running out of storage space",
    "db_locked": "the database seems stuck and queries are not completing",
    "db_replication_lag": "the database replica is falling further and further behind",
    # Cache faults
    "cache_cold": "the cache is not serving any hits right now",
    "cache_conn_refused": "the cache service is rejecting new connections",
    "cache_eviction_storm": "the cache is thrashing and entries keep getting removed",
    "cache_stale": "the cache appears to be serving outdated information",
    # Auth faults
    "auth_cert_invalid": "authentication is failing due to certificate problems",
    "auth_misconfigured": "the authentication service has a configuration problem",
    "auth_rate_limited": "the authentication service is throttling requests",
    "auth_token_expired": "authentication tokens are being rejected",
    # LB faults
    "lb_backend_unhealthy": "the load balancer is reporting problems with its targets",
    "lb_draining": "the load balancer is shedding connections unexpectedly",
    "lb_misconfigured": "the load balancer routing seems wrong",
    "lb_overloaded": "the load balancer is saturated and dropping traffic",
    # Queue faults
    "queue_backpressure": "the message queue is building up and cannot keep pace",
    "queue_consumer_dead": "queue messages are piling up because nothing is processing them",
    "queue_consumer_dead_dlq": "queue processing has stopped and failed messages are accumulating",
    "queue_poison_pill": "the queue is jammed on bad messages",
    "queue_split_brain": "the queue cluster is in a partitioned, inconsistent state",
    # DNS faults
    "dns_misconfigured": "DNS resolution is returning wrong addresses",
    "dns_propagating": "recent DNS changes have not fully taken effect yet",
    "dns_stale_cache": "DNS responses appear to be out of date",
}

# Canary prefixes: app symptom with canary deploy context
CANARY_APP_SYMPTOMS = {
    "canary_crashing": "the app started going down right after a canary deploy",
    "canary_crash_loop": "the app cannot stay running since a canary deploy went out",
    "canary_memory_leak": "the app started using too much memory after a canary deploy",
    "canary_high_latency": "app response times spiked after a canary deploy",
    "canary_unreachable": "the app stopped responding after a canary deploy",
}

CANARY_INFRA_LABELS = {
    "auth_cert": "authentication is failing on certificate problems",
    "auth_expired": "authentication tokens are being rejected",
    "cache_eviction": "the cache is thrashing and entries keep getting removed",
    "cache_stale": "the cache appears to be serving outdated information",
    "db_corrupted": "the database has data integrity problems",
    "db_degraded": "the database is performing much worse than normal",
    "db_locked": "the database seems stuck and queries are not completing",
    "dns_misconfigured": "DNS resolution is returning wrong addresses",
    "dns_stale": "DNS responses appear to be out of date",
    "queue_backpressure": "the message queue is building up and cannot keep pace",
    "queue_dead": "queue messages are piling up because nothing is processing them",
}


# ---------------------------------------------------------------------------
# Scope -> human-readable scope description
# ---------------------------------------------------------------------------
SCOPE_DESC = {
    "single_app": "a single application",
    "single_infra": "an infrastructure component",
    "multi_system": "multiple systems",
    "cascading": "a failure spreading across multiple systems",
}


# ---------------------------------------------------------------------------
# 4 reason_for_call variant templates - cycled via hash
# ---------------------------------------------------------------------------
COLD_REASON_VARIANTS = [
    "Hey, we have a production incident -- {symptoms}. Alerts started firing and no one has begun investigating yet. Can you help us get this resolved?",
    "Production incident just came in. {symptoms_cap}. Our monitoring lit up and we need someone to take point on investigation and resolution.",
    "We are seeing a production issue -- {symptoms}. Alerts are going off and we have not started digging in yet. Can you walk us through getting this fixed?",
    "Urgent -- {symptoms} in production. Pager went off, alerts are active, and investigation has not started. Need your help to triage and resolve this.",
]

DASHBOARD_KNOWN_REASON_VARIANTS = [
    "We have a production incident. I already pulled up the dashboard and confirmed {symptoms}. Need help figuring out next steps and getting to resolution.",
    "Production issue here -- I pulled up the monitoring dashboard and can see {symptoms}. What should we do to get this sorted out?",
    "Incident in progress. I have looked at the dashboard and confirmed {symptoms}. Can you guide us through the rest of the investigation and fix?",
    "Hey, production alert fired and I have already reviewed the dashboard. Confirmed that {symptoms}. Ready for your guidance on resolution.",
]


def _get_scope(brief: dict) -> str:
    for ns in brief.get("notable_start_state", []):
        if "scope" in ns:
            return ns.split("=")[1].strip().strip("'")
    return "single_app"


def _is_canary(task_id: str) -> bool:
    return task_id.startswith("canary_")


def _get_task_type(task_id: str) -> str:
    """Return cold, dashboard_known, diag_known, or partial.

    Uses regex anchored to the suffix to avoid false positives like
    'cache_cold_dashboard_known_d7_037' matching '_cold_'.
    """
    m = re.search(r"_(cold|dashboard_known|diag_known|partial)_d\d+_\d{3}$", task_id)
    if m:
        return m.group(1)
    return "cold"


def _extract_fault_labels(task_id: str) -> list[str]:
    """Extract fault labels from the task_id prefix."""
    prefix = re.sub(r"_(cold|dashboard_known|diag_known|partial)_d\d+_\d{3}$", "", task_id)

    if prefix.startswith("canary_"):
        return _extract_canary_fault_labels(prefix)

    # Split on double-underscore for multi-fault
    parts = prefix.split("__")
    return parts


def _extract_canary_fault_labels(prefix: str) -> list[str]:
    """Extract fault labels from canary task id prefix."""
    return [prefix]


def _describe_faults(task_id: str, fault_labels: list[str]) -> str:
    """Turn fault labels into a human-readable symptom string."""
    if _is_canary(task_id):
        return _describe_canary_faults(fault_labels[0])

    symptoms = []
    for label in fault_labels:
        desc = FAULT_SYMPTOMS.get(label)
        if desc:
            symptoms.append(desc)
        else:
            symptoms.append(label.replace("_", " ") + " issue detected")

    if len(symptoms) == 1:
        return symptoms[0]
    elif len(symptoms) == 2:
        return f"{symptoms[0]}, and {symptoms[1]}"
    else:
        return ", ".join(symptoms[:-1]) + f", and {symptoms[-1]}"


def _describe_canary_faults(prefix: str) -> str:
    """Describe canary fault symptoms."""
    if "_clean" in prefix:
        app_part = prefix.replace("canary_", "").replace("_clean", "")
        canary_key = f"canary_{app_part}"
        return CANARY_APP_SYMPTOMS.get(canary_key, "application issue after a canary deploy")
    elif "_plus_" in prefix:
        parts = prefix.split("_plus_")
        app_part = parts[0].replace("canary_", "")
        infra_part = parts[1]
        canary_key = f"canary_{app_part}"
        app_desc = CANARY_APP_SYMPTOMS.get(canary_key, "application issue after a canary deploy")
        infra_desc = CANARY_INFRA_LABELS.get(infra_part, infra_part.replace("_", " ") + " issue detected")
        return f"{app_desc}, and {infra_desc}"
    return "application issue after a canary deploy"


def _variant_index(task_id: str) -> int:
    """Deterministic variant index from task_id hash."""
    h = hashlib.sha256(task_id.encode()).hexdigest()
    return int(h, 16) % 4


def _build_reason_for_call(task_id: str, task_type: str, symptoms: str) -> str:
    idx = _variant_index(task_id)
    symptoms_cap = symptoms[0].upper() + symptoms[1:]

    if task_type == "cold":
        template = COLD_REASON_VARIANTS[idx]
    else:
        template = DASHBOARD_KNOWN_REASON_VARIANTS[idx]

    return template.format(symptoms=symptoms, symptoms_cap=symptoms_cap)


def _build_known_info(name: str, task_type: str, scope: str, is_canary: bool) -> str:
    """Build known_info string. Must include start_binding values for non-cold."""
    scope_desc = SCOPE_DESC.get(scope, scope)

    if task_type == "cold":
        base = (
            f"You are {name}. There is a production incident affecting {scope_desc}. "
            f"Alerts have fired but investigation has not started."
        )
        if is_canary:
            base = (
                f"You are {name}. There is a production incident affecting {scope_desc}. "
                f"A recent canary deployment may be involved. Alerts have fired but investigation has not started."
            )
        return base
    else:
        # dashboard_known, diag_known, partial -- dashboard has been checked
        # Must include the binding value "checked" for start_binding validation
        base = (
            f"You are {name}. There is a production incident affecting {scope_desc}. "
            f"You have already checked the monitoring dashboard and confirmed there are active issues."
        )
        if is_canary:
            base = (
                f"You are {name}. There is a production incident affecting {scope_desc}. "
                f"A recent canary deployment may be involved. "
                f"You have already checked the monitoring dashboard and confirmed there are active issues."
            )
        return base


def _build_ticket(name: str, scope: str, task_type: str) -> str:
    scope_desc = SCOPE_DESC.get(scope, scope)
    if task_type == "cold":
        return (
            f"Production incident reported affecting {scope_desc}. "
            f"Reporter: {name}. The incident will be considered resolved when "
            f"the root cause is addressed and a smoke test confirms recovery."
        )
    else:
        # Must include 'checked' for start_binding validation
        return (
            f"Production incident reported affecting {scope_desc}. "
            f"Reporter: {name}. Reporter has checked the monitoring dashboard and confirmed issues. "
            f"The incident will be considered resolved when "
            f"the root cause is addressed and a smoke test confirms recovery."
        )


def _check_banned(text: str, undisclosed: set[str], disclosed: set[str]) -> list[str]:
    """Check for leaked undisclosed values in text."""
    leaks = []
    for val in undisclosed:
        if val in disclosed:
            continue
        if val in text:
            leaks.append(val)
    return leaks


def author_narratives():
    runtime_doc = yaml.safe_load(RUNTIME_PATH.read_text())
    briefs_doc = yaml.safe_load(BRIEFS_PATH.read_text())
    brief_index = {t["task_id"]: t for t in briefs_doc["tasks"]}

    authored = 0
    total_leaks = 0
    for task in runtime_doc["tasks"]:
        tid = task["task_id"]
        brief = brief_index[tid]
        rt = task["runtime"]

        name = brief["entity_context"]["name"]
        scope = _get_scope(brief)
        task_type = _get_task_type(tid)
        canary = _is_canary(tid)
        fault_labels = _extract_fault_labels(tid)
        symptoms = _describe_faults(tid, fault_labels)

        rt["reason_for_call"] = _build_reason_for_call(tid, task_type, symptoms)
        rt["known_info"] = _build_known_info(name, task_type, scope, canary)
        rt["ticket"] = _build_ticket(name, scope, task_type)

        # Verify no undisclosed values leaked
        undisclosed = set(brief.get("undisclosed_binding_values", []))
        disclosed = set()
        for b in brief.get("start_bindings", []):
            if isinstance(b, dict):
                v = b.get("value")
                if v is not None:
                    disclosed.add(str(v))

        all_text = f"{rt['reason_for_call']} {rt['known_info']} {rt['ticket']}"
        leaks = _check_banned(all_text, undisclosed, disclosed)
        for val in leaks:
            print(f"WARNING: {tid} leaks undisclosed value '{val}'", file=sys.stderr)
            total_leaks += 1

        authored += 1

    # Write back
    RUNTIME_PATH.write_text(yaml.dump(runtime_doc, default_flow_style=False, allow_unicode=True, width=120, sort_keys=False))
    print(f"Authored {authored} tasks.")
    if total_leaks:
        print(f"TOTAL LEAKS: {total_leaks}", file=sys.stderr)
        sys.exit(1)
    else:
        print("No undisclosed value leaks detected.")


if __name__ == "__main__":
    author_narratives()
