"""Generate sampling_request.yaml for cloud_incident_response domain.

Key design principles for HARD tasks:
1. Cascading sync rules: db_unhealthy→cache_stale, app_unhealthy→lb_backend_unhealthy,
   canary+app_healthy→app_high_latency. Single faults cascade to multi-system incidents.
2. Repair side-effects: failover_db→dlq_has_messages, break_crash_loop→vacuum_needs_vacuum.
   Repairs create new problems that must also be resolved.
3. Canary trap: app can't stay healthy while canary is deployed. Must rollback first.
4. Multiple triage paths: cascading means multiple systems are broken, so different
   investigation+triage paths produce structurally distinct tasks from the same seed.

Run: python data/tau2/domains/cloud_incident_response/generate_sampling_request.py
"""
import yaml

# ── Healthy baseline (19 fields — excludes dashboard_checked/logs_tailed
#    which are owned by the knowledge dimension to avoid merge conflicts) ──
BASELINE = [
    ("agent.incident[active_incident].status", "investigating"),
    ("agent.incident[active_incident].scope", "unknown"),
    ("agent.incident[active_incident].comms_state", "none"),
    ("agent.incident[active_incident].triage_state", "not_run"),
    ("agent.app[active_app].app_health", "healthy"),
    ("agent.app[active_app].deploy_version", "current"),
    ("agent.db[active_db].db_health", "healthy"),
    ("agent.db[active_db].vacuum_state", "clean"),
    ("agent.cache[active_cache].cache_health", "healthy"),
    ("agent.auth[active_auth].auth_health", "healthy"),
    ("agent.lb[active_lb].lb_health", "healthy"),
    ("agent.queue[active_queue].queue_health", "healthy"),
    ("agent.queue[active_queue].dlq_state", "empty"),
    ("agent.queue[active_queue].consumer_state", "running"),
    ("agent.dns[active_dns].resolution_state", "correct"),
    ("agent.dns[active_dns].ttl_state", "normal"),
    # NOTE: dashboard_checked and logs_tailed are set by knowledge dimension
    ("user.actions.smoke_test_state", "not_run"),
    ("user.actions.dns_flushed_locally", "not_done"),
    ("user.actions.connectivity_verified", "not_verified"),
]


def make_world(overrides: dict) -> list:
    """Build start_world from baseline + overrides dict."""
    world = []
    overrides_map = dict(overrides) if isinstance(overrides, list) else overrides
    for path, default_val in BASELINE:
        val = overrides_map.get(path, default_val)
        world.append({"path": path, "set": val})
    return world


def make_variant(variant_id, overrides, depth_delta=(0, 0)):
    v = {"variant_id": variant_id, "start_world": make_world(overrides)}
    if depth_delta[0] != 0:
        v["min_depth_delta"] = depth_delta[0]
    if depth_delta[1] != 0:
        v["max_depth_delta"] = depth_delta[1]
    return v


# ── Single-fault definitions ─────────────────────────────────────────────
# NOTE: With cascading sync rules:
#   - App faults also break LB (sync_app_breaks_lb → lb=backend_unhealthy)
#   - DB faults also break cache (sync_db_breaks_cache → cache=stale)
#   - So "single fault" seeds produce multi-system tasks!
# Side-effects:
#   - break_crash_loop → vacuum_needs_vacuum (must vacuum DB after)
#   - failover_db → dlq_has_messages (must replay DLQ after)
SINGLE_FAULTS = {
    # App faults (cascade: lb→backend_unhealthy)
    "app_crashing": {"agent.app[active_app].app_health": "crashing"},
    "app_memory_leak": {"agent.app[active_app].app_health": "memory_leak"},
    "app_high_latency": {"agent.app[active_app].app_health": "high_latency"},
    "app_crash_loop": {"agent.app[active_app].app_health": "crash_loop"},
    "app_unreachable": {"agent.app[active_app].app_health": "unreachable"},
    # DB faults (cascade: cache→stale; corrupted also side-effects dlq→has_messages)
    "db_degraded": {"agent.db[active_db].db_health": "degraded"},
    "db_locked": {"agent.db[active_db].db_health": "locked"},
    "db_corrupted": {"agent.db[active_db].db_health": "corrupted"},
    "db_replication_lag": {"agent.db[active_db].db_health": "replication_lag"},
    "db_disk_full": {"agent.db[active_db].db_health": "disk_full"},
    "db_degraded_vacuum": {
        "agent.db[active_db].db_health": "degraded",
        "agent.db[active_db].vacuum_state": "needs_vacuum",
    },
    # Cache faults (no cascade, but warm_cache needs db healthy)
    "cache_stale": {"agent.cache[active_cache].cache_health": "stale"},
    "cache_cold": {"agent.cache[active_cache].cache_health": "cold"},
    "cache_eviction_storm": {"agent.cache[active_cache].cache_health": "eviction_storm"},
    "cache_conn_refused": {"agent.cache[active_cache].cache_health": "connection_refused"},
    # Auth faults
    "auth_cert_invalid": {"agent.auth[active_auth].auth_health": "cert_invalid"},
    "auth_token_expired": {"agent.auth[active_auth].auth_health": "token_expired"},
    "auth_rate_limited": {"agent.auth[active_auth].auth_health": "rate_limited"},
    "auth_misconfigured": {"agent.auth[active_auth].auth_health": "misconfigured"},
    # LB faults
    "lb_misconfigured": {"agent.lb[active_lb].lb_health": "misconfigured"},
    "lb_overloaded": {"agent.lb[active_lb].lb_health": "overloaded"},
    "lb_draining": {"agent.lb[active_lb].lb_health": "draining"},
    "lb_backend_unhealthy": {"agent.lb[active_lb].lb_health": "backend_unhealthy"},
    # Queue faults
    "queue_consumer_dead": {"agent.queue[active_queue].queue_health": "consumer_dead"},
    "queue_poison_pill": {"agent.queue[active_queue].queue_health": "poison_pill"},
    "queue_backpressure": {"agent.queue[active_queue].queue_health": "backpressure"},
    "queue_split_brain": {"agent.queue[active_queue].queue_health": "split_brain"},
    "queue_consumer_dead_dlq": {
        "agent.queue[active_queue].queue_health": "consumer_dead",
        "agent.queue[active_queue].dlq_state": "has_messages",
    },
    # DNS faults
    "dns_stale_cache": {
        "agent.dns[active_dns].resolution_state": "stale_cache",
        "agent.dns[active_dns].ttl_state": "normal",
    },
    "dns_misconfigured": {
        "agent.dns[active_dns].resolution_state": "misconfigured",
        "agent.dns[active_dns].ttl_state": "normal",
    },
    "dns_propagating": {
        "agent.dns[active_dns].resolution_state": "propagating",
        "agent.dns[active_dns].ttl_state": "flushed",
    },
}

# ── Two-fault pairs ──────────────────────────────────────────────────────
# Removed pairs that are now REDUNDANT with cascading sync rules:
#   - app_X + lb_backend_unhealthy → sync already cascades app→lb
#   - db_X + cache_stale → sync already cascades db→cache
# Kept pairs with NON-CASCADE faults (different from what sync produces).
# Added new pairs that create interesting interactions WITH cascading.
TWO_FAULT_PAIRS = [
    # ── App + DB (cascade: lb=backend_unhealthy + cache=stale from sync!) ──
    # These are now 4-system incidents from 2 faults!
    ("app_crashing", "db_locked"),
    ("app_crashing", "db_degraded"),
    ("app_crash_loop", "db_corrupted"),  # side-effects: vacuum + dlq!
    ("app_memory_leak", "db_disk_full"),
    ("app_unreachable", "db_replication_lag"),
    ("app_high_latency", "db_degraded_vacuum"),
    # ── App + Cache (cascade: lb=backend_unhealthy; cache NOT from sync since db is healthy) ──
    ("app_crashing", "cache_eviction_storm"),
    ("app_crash_loop", "cache_conn_refused"),
    ("app_high_latency", "cache_cold"),
    ("app_unreachable", "cache_stale"),
    # ── App + LB (non-backend faults; cascade would set backend_unhealthy but LB is already broken differently) ──
    ("app_crash_loop", "lb_overloaded"),
    ("app_unreachable", "lb_misconfigured"),
    ("app_crashing", "lb_draining"),
    # ── App + Queue (relieve_backpressure needs app healthy → order matters!) ──
    ("app_crashing", "queue_backpressure"),
    ("app_unreachable", "queue_split_brain"),
    ("app_memory_leak", "queue_consumer_dead"),
    ("app_crash_loop", "queue_poison_pill"),
    # ── App + Auth ──
    ("app_crashing", "auth_cert_invalid"),
    ("app_crash_loop", "auth_token_expired"),
    ("app_unreachable", "auth_misconfigured"),
    # ── App + DNS (cascade: lb=backend_unhealthy) ──
    ("app_crashing", "dns_stale_cache"),
    ("app_unreachable", "dns_misconfigured"),
    # ── DB + Cache (non-stale cache faults; sync produces stale but these are different) ──
    ("db_locked", "cache_eviction_storm"),
    ("db_corrupted", "cache_conn_refused"),  # side-effect: dlq!
    ("db_disk_full", "cache_cold"),  # cache is cold not stale, so sync doesn't fire
    ("db_degraded", "cache_conn_refused"),
    # ── DB + Auth (cascade: cache=stale) ──
    ("db_locked", "auth_misconfigured"),
    ("db_corrupted", "auth_rate_limited"),  # side-effect: dlq!
    ("db_disk_full", "auth_cert_invalid"),
    # ── DB + Queue (cascade: cache=stale) ──
    ("db_degraded", "queue_consumer_dead_dlq"),
    ("db_disk_full", "queue_split_brain"),
    ("db_corrupted", "queue_backpressure"),  # dlq side-effect + backpressure needs app healthy
    # ── DB + LB (cascade: cache=stale) ──
    ("db_locked", "lb_overloaded"),
    ("db_corrupted", "lb_draining"),
    ("db_disk_full", "lb_misconfigured"),
    # ── DB + DNS (cascade: cache=stale) ──
    ("db_locked", "dns_stale_cache"),
    ("db_corrupted", "dns_misconfigured"),  # dlq side-effect + 3-step DNS
    # ── Cache + Auth ──
    ("cache_stale", "auth_cert_invalid"),
    ("cache_eviction_storm", "auth_token_expired"),
    ("cache_conn_refused", "auth_misconfigured"),
    # ── Cache + LB ──
    ("cache_stale", "lb_misconfigured"),
    ("cache_conn_refused", "lb_overloaded"),
    # ── Cache + Queue ──
    ("cache_stale", "queue_poison_pill"),
    ("cache_cold", "queue_backpressure"),
    ("cache_eviction_storm", "queue_split_brain"),
    # ── Cache + DNS ──
    ("cache_stale", "dns_stale_cache"),
    ("cache_cold", "dns_misconfigured"),
    # ── Auth + LB ──
    ("auth_cert_invalid", "lb_misconfigured"),
    ("auth_misconfigured", "lb_overloaded"),
    # ── Auth + Queue ──
    ("auth_token_expired", "queue_consumer_dead"),
    ("auth_rate_limited", "queue_split_brain"),
    # ── Auth + DNS ──
    ("auth_cert_invalid", "dns_stale_cache"),
    ("auth_misconfigured", "dns_misconfigured"),
    # ── LB + Queue ──
    ("lb_overloaded", "queue_consumer_dead"),
    ("lb_misconfigured", "queue_poison_pill"),
    ("lb_draining", "queue_split_brain"),
    # ── LB + DNS ──
    ("lb_misconfigured", "dns_stale_cache"),
    ("lb_overloaded", "dns_misconfigured"),
    # ── Queue + DNS ──
    ("queue_consumer_dead", "dns_stale_cache"),
    ("queue_split_brain", "dns_misconfigured"),
    ("queue_backpressure", "dns_stale_cache"),
]

# ── Three-fault triples (cascading failures) ─────────────────────────────
# With cascading sync rules, these can produce 5-7 system incidents!
THREE_FAULT_TRIPLES = [
    # ── App + DB + non-cascade-cache (cascade adds lb=backend_unhealthy; db→cache sync
    #    doesn't fire because cache is already broken with a non-stale fault) ──
    ("app_crash_loop", "db_locked", "cache_eviction_storm"),  # 5 systems, side-effect: vacuum
    ("app_crashing", "db_corrupted", "cache_conn_refused"),  # 5 systems, side-effect: dlq
    ("app_memory_leak", "db_disk_full", "cache_cold"),
    ("app_unreachable", "db_degraded", "cache_conn_refused"),
    # ── App + LB + Queue (cascade: lb might be overridden; app→lb sync fires if lb was healthy
    #    but lb is already broken differently, so sync doesn't fire) ──
    ("app_crashing", "lb_overloaded", "queue_backpressure"),
    ("app_crash_loop", "lb_misconfigured", "queue_split_brain"),
    ("app_unreachable", "lb_draining", "queue_consumer_dead"),
    # ── DB + non-cascade-cache + Auth (cascade: cache would go stale from sync,
    #    but cache is already broken differently) ──
    ("db_locked", "cache_eviction_storm", "auth_cert_invalid"),
    ("db_corrupted", "cache_conn_refused", "auth_misconfigured"),
    ("db_disk_full", "cache_cold", "auth_token_expired"),
    # ── App + Auth + DNS (cascade: lb=backend_unhealthy from app) ──
    ("app_crash_loop", "auth_cert_invalid", "dns_misconfigured"),  # 5 systems
    ("app_crashing", "auth_rate_limited", "dns_stale_cache"),
    ("app_unreachable", "auth_misconfigured", "dns_stale_cache"),
    # ── DB + Queue + DNS (cascade: cache=stale from db) ──
    ("db_locked", "queue_split_brain", "dns_misconfigured"),  # 5 systems
    ("db_corrupted", "queue_consumer_dead_dlq", "dns_stale_cache"),
    ("db_disk_full", "queue_backpressure", "dns_stale_cache"),
    # ── LB + Auth + Queue ──
    ("lb_overloaded", "auth_misconfigured", "queue_poison_pill"),
    ("lb_misconfigured", "auth_cert_invalid", "queue_consumer_dead"),
    # ── 4-system failures (longest chains, cascade makes 5-6 systems) ──
    ("app_crash_loop", "db_locked", "cache_eviction_storm", "auth_cert_invalid"),
    ("app_crashing", "db_corrupted", "lb_overloaded", "queue_backpressure"),
    ("db_disk_full", "cache_conn_refused", "auth_misconfigured", "dns_misconfigured"),
    ("app_unreachable", "lb_misconfigured", "queue_split_brain", "dns_stale_cache"),
    # ── 5-system failures (extreme) ──
    ("app_crash_loop", "db_corrupted", "auth_cert_invalid", "queue_split_brain", "dns_misconfigured"),
    ("app_unreachable", "db_disk_full", "cache_eviction_storm", "auth_misconfigured", "lb_overloaded"),
]

# ── Config drift cases ───────────────────────────────────────────────────
# Canary sync: deploy=canary + app=healthy → app=high_latency.
# This means you CANNOT fix app without rollback first. The sync creates a "trap"
# where restart/tune_latency immediately bounces back to high_latency.
# Also: app unhealthy → cascade to lb=backend_unhealthy.
CONFIG_DRIFT_CASES = {
    "canary_crashing": {
        "agent.app[active_app].app_health": "crashing",
        "agent.app[active_app].deploy_version": "canary",
    },
    "canary_memory_leak": {
        "agent.app[active_app].app_health": "memory_leak",
        "agent.app[active_app].deploy_version": "canary",
    },
    "canary_high_latency": {
        "agent.app[active_app].app_health": "high_latency",
        "agent.app[active_app].deploy_version": "canary",
    },
    "canary_crash_loop": {
        "agent.app[active_app].app_health": "crash_loop",
        "agent.app[active_app].deploy_version": "canary",
    },
    "canary_unreachable": {
        "agent.app[active_app].app_health": "unreachable",
        "agent.app[active_app].deploy_version": "canary",
    },
}

CONFIG_DRIFT_SECONDARY = {
    "clean": {},
    "plus_cache_stale": {"agent.cache[active_cache].cache_health": "stale"},
    "plus_cache_eviction": {"agent.cache[active_cache].cache_health": "eviction_storm"},
    "plus_db_degraded": {"agent.db[active_db].db_health": "degraded"},
    "plus_db_locked": {"agent.db[active_db].db_health": "locked"},
    "plus_db_corrupted": {"agent.db[active_db].db_health": "corrupted"},
    "plus_auth_expired": {"agent.auth[active_auth].auth_health": "token_expired"},
    "plus_auth_cert": {"agent.auth[active_auth].auth_health": "cert_invalid"},
    "plus_queue_dead": {"agent.queue[active_queue].queue_health": "consumer_dead"},
    "plus_queue_backpressure": {"agent.queue[active_queue].queue_health": "backpressure"},
    "plus_dns_stale": {
        "agent.dns[active_dns].resolution_state": "stale_cache",
        "agent.dns[active_dns].ttl_state": "normal",
    },
    "plus_dns_misconfigured": {
        "agent.dns[active_dns].resolution_state": "misconfigured",
        "agent.dns[active_dns].ttl_state": "normal",
    },
}


def merge_faults(*fault_ids):
    """Merge multiple fault overrides, checking for conflicts."""
    merged = {}
    for fid in fault_ids:
        overrides = SINGLE_FAULTS[fid]
        for k, v in overrides.items():
            if k in merged and merged[k] != v:
                raise ValueError(f"Conflict on {k}: {merged[k]} vs {v} in {fault_ids}")
            merged[k] = v
    return merged


def build_terminal_profiles():
    """Build 4 terminal profiles gated by scope."""
    common_requires = [
        ("agent.incident[active_incident].status", "resolved"),
        ("agent.incident[active_incident].triage_state", "ran"),
        ("agent.incident[active_incident].comms_state", "all_sent"),
        ("agent.app[active_app].app_health", "healthy"),
        ("agent.db[active_db].db_health", "healthy"),
        ("agent.db[active_db].vacuum_state", "clean"),
        ("agent.cache[active_cache].cache_health", "healthy"),
        ("agent.auth[active_auth].auth_health", "healthy"),
        ("agent.lb[active_lb].lb_health", "healthy"),
        ("agent.queue[active_queue].queue_health", "healthy"),
        ("agent.dns[active_dns].resolution_state", "correct"),
        ("user.actions.smoke_test_state", "passed"),
    ]

    profiles = []
    for scope_val, profile_id, desc, extra in [
        (
            "single_app",
            "single_app_resolved",
            "Single app fault fully resolved (including cascade damage).",
            [],
        ),
        (
            "single_infra",
            "single_infra_resolved",
            "Single infrastructure fault fully resolved (including cascade damage).",
            [],
        ),
        (
            "multi_system",
            "multi_system_resolved",
            "Multi-system incident fully resolved.",
            [],
        ),
        (
            "cascading",
            "cascading_resolved",
            "Cascading failure fully resolved.",
            [],
        ),
    ]:
        requires = [{"path": "agent.incident[active_incident].scope", "op": "eq", "value": scope_val}]
        for path, val in common_requires:
            requires.append({"path": path, "op": "eq", "value": val})
        for path, val in extra:
            requires.append({"path": path, "op": "eq", "value": val})
        profiles.append({
            "profile_id": profile_id,
            "description": desc,
            "requires_world": requires,
        })
    return profiles


def _scope_for_fault(fault_id):
    """Determine scope based on which system is broken."""
    if fault_id.startswith("app_") or fault_id.startswith("canary_"):
        return "single_app"
    return "single_infra"


def build_single_fault_schema():
    """Schema 1: single-fault cases.

    With cascading sync rules, app faults cascade to LB, DB faults cascade to cache.
    With repair side-effects, crash_loop adds vacuum, corrupted adds DLQ.
    So "single fault" tasks are actually multi-system!
    """
    case_variants = []
    for fault_id, overrides in SINGLE_FAULTS.items():
        scope = _scope_for_fault(fault_id)
        case_overrides = {**overrides, "agent.incident[active_incident].scope": scope}
        case_variants.append(make_variant(fault_id, case_overrides))

    knowledge_variants = [
        {
            "variant_id": "cold",
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "not_checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
        },
        {
            "variant_id": "dashboard_known",
            "start_bindings": ["K.dashboard_overview"],
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
            "min_depth_delta": -1,
            "max_depth_delta": -1,
        },
        {
            "variant_id": "diag_known",
            "start_bindings": ["K.dashboard_overview"],
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
            "min_depth_delta": -1,
            "max_depth_delta": -1,
        },
    ]

    return {
        "schema_id": "single_fault_cases",
        "seed_id_template": "{case}_{knowledge}",
        "allowed_terminal_profiles": ["single_app_resolved", "single_infra_resolved"],
        "goal_capture_paths": [],
        # Increased depths: cascading adds 2-4 actions, side-effects add 1-2 more
        "min_depth": 7,
        "max_depth": 16,
        "dimensions": [
            {"dimension_id": "case", "variants": case_variants},
            {"dimension_id": "knowledge", "variants": knowledge_variants},
        ],
    }


def build_two_fault_schema():
    """Schema 2: two-fault cases.

    With cascading, app+db pairs break 4 systems (app+db+lb+cache cascades).
    Side-effects from crash_loop and corrupted add even more.
    """
    case_variants = []
    for pair in TWO_FAULT_PAIRS:
        fault_a, fault_b = pair
        try:
            overrides = merge_faults(fault_a, fault_b)
        except ValueError as e:
            print(f"SKIPPING pair {pair}: {e}")
            continue
        overrides["agent.incident[active_incident].scope"] = "multi_system"
        vid = f"{fault_a}__{fault_b}"
        case_variants.append(make_variant(vid, overrides))

    knowledge_variants = [
        {
            "variant_id": "cold",
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "not_checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
        },
        {
            "variant_id": "partial",
            "start_bindings": ["K.dashboard_overview"],
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
            "min_depth_delta": -1,
            "max_depth_delta": -1,
        },
    ]

    return {
        "schema_id": "two_fault_cases",
        "seed_id_template": "{case}_{knowledge}",
        "allowed_terminal_profiles": ["multi_system_resolved"],
        "goal_capture_paths": [],
        "min_depth": 9,
        "max_depth": 20,
        "dimensions": [
            {"dimension_id": "case", "variants": case_variants},
            {"dimension_id": "knowledge", "variants": knowledge_variants},
        ],
    }


def build_cascading_schema():
    """Schema 3: 3-5 fault cascading failures.

    These are the hardest tasks. With sync cascading, a 3-fault seed can
    become a 5-6 system incident. Repair side-effects add more damage.
    """
    case_variants = []
    for faults in THREE_FAULT_TRIPLES:
        try:
            overrides = merge_faults(*faults)
        except ValueError as e:
            print(f"SKIPPING triple {faults}: {e}")
            continue
        overrides["agent.incident[active_incident].scope"] = "cascading"
        vid = "__".join(faults)
        case_variants.append(make_variant(vid, overrides))

    knowledge_variants = [
        {
            "variant_id": "cold",
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "not_checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
        },
        {
            "variant_id": "partial",
            "start_bindings": ["K.dashboard_overview"],
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
            "min_depth_delta": -1,
            "max_depth_delta": -1,
        },
    ]

    return {
        "schema_id": "cascading_cases",
        "seed_id_template": "{case}_{knowledge}",
        "allowed_terminal_profiles": ["cascading_resolved"],
        "goal_capture_paths": [],
        "min_depth": 13,
        "max_depth": 24,
        "dimensions": [
            {"dimension_id": "case", "variants": case_variants},
            {"dimension_id": "knowledge", "variants": knowledge_variants},
        ],
    }


def build_config_drift_schema():
    """Schema 4: config drift (canary deploy) + optional secondary fault.

    The canary sync trap: deploy=canary + app=healthy → app=high_latency.
    The LLM CANNOT fix the app without rollback first. Restart/tune bounces back.
    Combined with secondary faults and cascading (app→lb), these are tricky.
    """
    case_variants = []
    for drift_id, drift_overrides in CONFIG_DRIFT_CASES.items():
        for sec_id, sec_overrides in CONFIG_DRIFT_SECONDARY.items():
            merged = {**drift_overrides, **sec_overrides}
            if sec_overrides:
                merged["agent.incident[active_incident].scope"] = "multi_system"
            else:
                merged["agent.incident[active_incident].scope"] = "single_app"
            vid = f"{drift_id}_{sec_id}"
            delta = (0, 0)
            if sec_overrides:
                delta = (2, 4)
            case_variants.append(make_variant(vid, merged, depth_delta=delta))

    knowledge_variants = [
        {
            "variant_id": "cold",
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "not_checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
        },
        {
            "variant_id": "dashboard_known",
            "start_bindings": ["K.dashboard_overview"],
            "start_world": [
                {"path": "user.observability.dashboard_checked", "set": "checked"},
                {"path": "user.observability.logs_tailed", "set": "not_tailed"},
            ],
            "min_depth_delta": -1,
            "max_depth_delta": -1,
        },
    ]

    return {
        "schema_id": "config_drift_cases",
        "seed_id_template": "{case}_{knowledge}",
        "allowed_terminal_profiles": ["single_app_resolved", "multi_system_resolved"],
        "goal_capture_paths": [],
        "min_depth": 8,
        "max_depth": 18,
        "dimensions": [
            {"dimension_id": "case", "variants": case_variants},
            {"dimension_id": "knowledge", "variants": knowledge_variants},
        ],
    }


def main():
    goal_capture_paths = [
        "agent.incident[active_incident]",
        "agent.app[active_app]",
        "agent.db[active_db]",
        "agent.cache[active_cache]",
        "agent.auth[active_auth]",
        "agent.lb[active_lb]",
        "agent.queue[active_queue]",
        "agent.dns[active_dns]",
        "user.observability",
        "user.actions",
    ]

    doc = {
        "version": 1,
        "max_tasks": 500,
        "goal_capture_paths": goal_capture_paths,
        "terminal_profiles": build_terminal_profiles(),
        "seed_schemas": [
            build_single_fault_schema(),
            build_two_fault_schema(),
            build_cascading_schema(),
            build_config_drift_schema(),
        ],
    }

    # Count seeds
    total = 0
    for schema in doc["seed_schemas"]:
        n = 1
        for dim in schema["dimensions"]:
            n *= len(dim["variants"])
        total += n
        print(f"  {schema['schema_id']}: {n} seeds")
    print(f"  TOTAL: {total} seeds")

    out_path = "data/tau2/domains/cloud_incident_response/sampling_request.yaml"
    with open(out_path, "w") as f:
        yaml.dump(doc, f, default_flow_style=False, sort_keys=False, width=120)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
