# Pilot Domain Scope (v2): cloud_incident_response

## 1. Pilot domain

Cloud production incident response where an SRE assistant helps an on-call engineer diagnose
and resolve a multi-system outage. The assistant has backend tooling to inspect and repair
infrastructure; the user (on-call engineer) has local observability tools (dashboards, CLI)
and can perform actions like restarting local services, confirming rollbacks, and running
smoke tests.

Pilot slice:

- One active incident affecting one primary service and 1-3 dependent systems per task.
- Six root-cause categories with distinct resolution topologies:
  - `app_bug` — application-layer crash/panic requiring rollback or hotfix + restart
  - `db_failure` — database primary degraded/locked/corrupted requiring repair + replication fix
  - `cache_cascade` — cache failure causing thundering herd; requires cache + DB coordination
  - `auth_outage` — authentication service broken (certs, tokens, or rate limits)
  - `config_drift` — bad deploy or feature flag causing failures; needs rollback + validation
  - `network_partition` — load balancer/DNS/queue issues causing connectivity failures
- Each category ends only at a true terminal state where the incident is marked resolved,
  affected services are healthy, comms have been sent, and a user smoke test passes.

## 2. Agent DB schema sketch

Entity: `Incident`

- `incident_id: str`
- `severity: enum[sev1, sev2, sev3]`
- `status: enum[investigating, identified, mitigating, resolved]`
- `root_cause: enum[unknown, app_bug, db_failure, cache_cascade, auth_outage, config_drift, network_partition]`
- `comms_state: enum[none, internal_sent, external_sent, all_sent]`
- `postmortem_state: enum[not_started, drafted]`

Entity: `AppService`

- `service_id: str`
- `status: enum[healthy, degraded, crashing, unreachable]`
- `deploy_version: enum[current, previous, canary]`
- `feature_flags: enum[all_on, partial, kill_switched]`
- `restart_count: enum[zero, one, multiple]`

Entity: `Database`

- `db_id: str`
- `status: enum[healthy, degraded, locked, corrupted]`
- `replication_state: enum[synced, lagging, broken]`
- `connection_pool: enum[normal, saturated, drained]`
- `vacuum_state: enum[clean, needs_vacuum]`

Entity: `CacheLayer`

- `cache_id: str`
- `status: enum[healthy, stale, cold, unreachable]`
- `hit_rate: enum[normal, degraded, zero]`
- `ttl_config: enum[default, extended, shortened]`

Entity: `AuthService`

- `auth_id: str`
- `status: enum[healthy, token_expired, cert_invalid, rate_limited]`
- `cert_state: enum[valid, expiring, expired, renewed]`
- `token_pool: enum[valid, refreshed, invalid]`
- `rate_limit_state: enum[normal, elevated, cleared]`

Entity: `LoadBalancer`

- `lb_id: str`
- `status: enum[healthy, misconfigured, overloaded]`
- `routing_mode: enum[normal, failover, draining]`
- `health_check_state: enum[passing, failing, disabled]`

Entity: `MessageQueue`

- `queue_id: str`
- `status: enum[healthy, backed_up, consumer_dead, poison_pill]`
- `dlq_state: enum[empty, has_messages, replayed]`
- `consumer_state: enum[running, stopped, restarted]`

Entity: `DNSRecord`

- `dns_id: str`
- `resolution_state: enum[correct, stale_cache, propagating]`
- `ttl_state: enum[normal, flushed]`

## 3. User DB schema sketch

Entity: `UserContext`

- `user_id: str | null`
- `name: str | null`
- `incident_id: str | null`
- `oncall_role: str | null`

Entity: `LocalObservability`

- `dashboard_checked: enum[not_checked, checked]`
- `logs_tailed: enum[not_tailed, tailed]`
- `traces_checked: enum[not_checked, checked]`
- `metrics_snapshot_taken: enum[not_taken, taken]`

Entity: `LocalActions`

- `local_service_restarted: enum[not_done, done]`
- `rollback_confirmed: enum[not_confirmed, confirmed]`
- `feature_flag_toggled: enum[not_done, done]`
- `smoke_test_state: enum[not_run, running, passed, failed]`
- `cache_warmed_locally: enum[not_done, done]`
- `dns_flushed_locally: enum[not_done, done]`
- `connectivity_verified: enum[not_verified, verified]`

Entity: `ViewState`

- `display_incident_status: str | null`
- `display_severity: str | null`
- `display_root_cause: str | null`
- `display_app_status: str | null`
- `display_db_status: str | null`
- `display_cache_status: str | null`
- `display_auth_status: str | null`
- `display_lb_status: str | null`
- `display_queue_status: str | null`
- `display_dns_status: str | null`
- `display_comms_state: str | null`

Entity: `StopGateState`

- `criteria: list[StopCriterion]`

## 4. Field projection table

| field_path | owner_db | type_or_domain | projected_for_solver | update_source | notes |
| --- | --- | --- | --- | --- | --- |
| `agent.incident[active_incident].severity` | agent | enum | yes | init_only | task difficulty axis |
| `agent.incident[active_incident].status` | agent | enum | yes | assistant_tool | incident lifecycle |
| `agent.incident[active_incident].root_cause` | agent | enum | yes | assistant_tool | branch discriminator, set by triage |
| `agent.incident[active_incident].comms_state` | agent | enum | yes | assistant_tool | comms lane |
| `agent.incident[active_incident].postmortem_state` | agent | enum | yes | assistant_tool | late-stage documentation |
| `agent.app[active_app].status` | agent | enum | yes | assistant_tool + sync | app health |
| `agent.app[active_app].deploy_version` | agent | enum | yes | assistant_tool | rollback state |
| `agent.app[active_app].feature_flags` | agent | enum | yes | assistant_tool | config drift lane |
| `agent.app[active_app].restart_count` | agent | enum | yes | assistant_tool | tracks restart attempts |
| `agent.db[active_db].status` | agent | enum | yes | assistant_tool | db health |
| `agent.db[active_db].replication_state` | agent | enum | yes | assistant_tool | db replication lane |
| `agent.db[active_db].connection_pool` | agent | enum | yes | assistant_tool + sync | pool state |
| `agent.db[active_db].vacuum_state` | agent | enum | yes | assistant_tool | cleanup prerequisite |
| `agent.cache[active_cache].status` | agent | enum | yes | assistant_tool + sync | cache health |
| `agent.cache[active_cache].hit_rate` | agent | enum | yes | sync | derived from cache status + warm state |
| `agent.cache[active_cache].ttl_config` | agent | enum | yes | assistant_tool | cache tuning |
| `agent.auth[active_auth].status` | agent | enum | yes | assistant_tool | auth health |
| `agent.auth[active_auth].cert_state` | agent | enum | yes | assistant_tool | cert lifecycle |
| `agent.auth[active_auth].token_pool` | agent | enum | yes | assistant_tool | token lane |
| `agent.auth[active_auth].rate_limit_state` | agent | enum | yes | assistant_tool | rate limit lane |
| `agent.lb[active_lb].status` | agent | enum | yes | assistant_tool | lb health |
| `agent.lb[active_lb].routing_mode` | agent | enum | yes | assistant_tool | routing state |
| `agent.lb[active_lb].health_check_state` | agent | enum | yes | sync | derived from downstream health |
| `agent.queue[active_queue].status` | agent | enum | yes | assistant_tool | queue health |
| `agent.queue[active_queue].dlq_state` | agent | enum | yes | assistant_tool | dead letter lane |
| `agent.queue[active_queue].consumer_state` | agent | enum | yes | assistant_tool | consumer lifecycle |
| `agent.dns[active_dns].resolution_state` | agent | enum | yes | assistant_tool + sync | dns resolution |
| `agent.dns[active_dns].ttl_state` | agent | enum | yes | assistant_tool | dns cache |
| `user.observability.dashboard_checked` | user | enum | yes | user_tool | user investigation |
| `user.observability.logs_tailed` | user | enum | yes | user_tool | user investigation |
| `user.observability.traces_checked` | user | enum | yes | user_tool | user investigation |
| `user.observability.metrics_snapshot_taken` | user | enum | yes | user_tool | user investigation |
| `user.actions.local_service_restarted` | user | enum | yes | user_tool | user-side restart |
| `user.actions.rollback_confirmed` | user | enum | yes | user_tool | deployment lane |
| `user.actions.feature_flag_toggled` | user | enum | yes | user_tool | config drift lane |
| `user.actions.smoke_test_state` | user | enum | yes | user_tool | terminal validation |
| `user.actions.cache_warmed_locally` | user | enum | yes | user_tool | cache recovery |
| `user.actions.dns_flushed_locally` | user | enum | yes | user_tool | dns recovery |
| `user.actions.connectivity_verified` | user | enum | yes | user_tool | network lane |
| `user.view.display_*` observables | user | strings | yes | sync | stop-gate observable surface |
| `user.stop_gate.criteria` | user | list | no | init_only | runtime-only stop checker input |

## 5. Context slots

- `active_incident -> Incident`
- `active_app -> AppService`
- `active_db -> Database`
- `active_cache -> CacheLayer`
- `active_auth -> AuthService`
- `active_lb -> LoadBalancer`
- `active_queue -> MessageQueue`
- `active_dns -> DNSRecord`

## 6. Projected world paths

Projected causal and observable paths used by solver state:

- incident lifecycle: severity, status, root_cause, comms_state, postmortem_state
- app gates: status, deploy_version, feature_flags, restart_count
- db gates: status, replication_state, connection_pool, vacuum_state
- cache gates: status, hit_rate, ttl_config
- auth gates: status, cert_state, token_pool, rate_limit_state
- lb gates: status, routing_mode, health_check_state
- queue gates: status, dlq_state, consumer_state
- dns gates: resolution_state, ttl_state
- user observability: dashboard_checked, logs_tailed, traces_checked, metrics_snapshot_taken
- user actions: local_service_restarted, rollback_confirmed, feature_flag_toggled, smoke_test_state, cache_warmed_locally, dns_flushed_locally, connectivity_verified
- user-visible projections consumed by `check_incident_dashboard` and `check_resolution_status`

## 7. Assistant toolset (rough)

Investigation tools (READ):

- `check_app_logs(service_id)` -> returns error patterns, stack traces
- `check_app_metrics(service_id)` -> returns latency, error rate, throughput
- `run_db_diagnostic(db_id)` -> returns db health, lock contention, replication lag
- `check_cache_metrics(cache_id)` -> returns hit rate, eviction rate, memory usage
- `check_auth_logs(auth_id)` -> returns auth failures, cert expiry, rate limit data
- `check_lb_status(lb_id)` -> returns routing table, backend health, connection counts
- `check_queue_depth(queue_id)` -> returns queue depth, consumer lag, DLQ count
- `check_dns_resolution(dns_id)` -> returns resolution results, TTL, propagation status

Triage tool (WRITE — sets root cause):

- `correlate_and_triage(error_pattern, db_diagnostic, additional_signal)` -> determines root_cause, sets incident.root_cause and incident.status=identified
  - requires 2+ investigation bindings to call
  - `additional_signal` accepts one of: `cache_metrics`, `auth_detail`, `lb_status`, `queue_depth`
  - different binding combinations + additional_signal values → different root_cause assignments

App repair tools (WRITE):

- `restart_app_service(service_id)` -> restarts app, resets status based on underlying cause
- `rollback_deploy(service_id, target_version)` -> rolls back to previous version
- `toggle_feature_flag(service_id, flag_name, state)` -> toggles specific feature flag
- `scale_app_instances(service_id, direction)` -> scale up/down

DB repair tools (WRITE):

- `restart_db_primary(db_id)` -> restarts primary, resets status
- `failover_to_replica(db_id)` -> promotes replica to primary
- `repair_replication(db_id)` -> fixes broken replication
- `run_db_vacuum(db_id)` -> cleans up degraded state
- `drain_connection_pool(db_id)` -> resets saturated connections

Cache repair tools (WRITE):

- `flush_cache(cache_id)` -> evicts all entries (makes cold)
- `reconfigure_cache_ttl(cache_id, strategy)` -> adjusts TTL strategy
- `warm_cache(cache_id)` -> pre-populates cache (requires db.healthy)

Auth repair tools (WRITE):

- `rotate_auth_certs(auth_id)` -> replaces expired/invalid certs
- `refresh_auth_tokens(auth_id)` -> refreshes token pool
- `reset_rate_limits(auth_id)` -> clears rate limit state
- `restart_auth_service(auth_id)` -> full auth service restart

LB/Network repair tools (WRITE):

- `reconfigure_lb(lb_id, mode)` -> fixes misconfiguration, sets routing mode
- `drain_and_rebalance(lb_id)` -> drains overloaded backends, rebalances
- `flush_dns_cache(dns_id)` -> forces DNS cache flush
- `force_dns_propagation(dns_id)` -> triggers immediate propagation

Queue repair tools (WRITE):

- `restart_queue_consumers(queue_id)` -> restarts dead consumers
- `purge_poison_pill(queue_id)` -> removes poison pill messages
- `replay_dead_letters(queue_id)` -> replays DLQ (requires consumers running + app healthy)

Incident management tools (WRITE):

- `set_incident_status(status)` -> advances incident lifecycle
- `send_comms(audience)` -> sends internal or external communications
- `draft_postmortem()` -> creates postmortem draft

Helper callables:

- context setters and per-field init helpers
- env assertions on agent-side state

## 8. User toolset (rough)

Discovery tools (knowledge sources):

- `check_dashboard()` -> observes overall system health panel, produces `K.dashboard_summary`
- `tail_app_logs()` -> observes local log stream, produces `K.local_error_pattern`
- `check_traces()` -> observes distributed traces, produces `K.trace_signal`
- `take_metrics_snapshot()` -> captures current metrics, produces `K.metrics_snapshot`

Customer-side (on-call) causal actions:

- `restart_local_service()` -> restarts service on local node (user-side action)
- `confirm_rollback()` -> user confirms deploy rollback is safe to proceed
- `toggle_local_feature_flag()` -> user toggles flag from their admin panel
- `run_smoke_test()` -> runs end-to-end validation (requires affected systems healthy)
- `warm_cache_locally()` -> user warms cache from local tooling (requires cache cold + db healthy)
- `flush_local_dns()` -> user flushes local DNS resolver cache
- `verify_connectivity()` -> user verifies network path from their vantage point

Stutter-only checker:

- `check_resolution_status()` -> checks all stop-gate criteria, returns resolved/unresolved + unmet reasons

## 9. World/sync logic

Sync rules (reactive, fire after every action until fixed point):

1. **LB health check sync**: When all backend app instances healthy → lb.health_check_state = passing.
   When app.status in {crashing, unreachable} → lb.health_check_state = failing.

2. **Cache hit rate sync**: When cache.status == healthy AND user.actions.cache_warmed_locally == done
   → cache.hit_rate = normal. When cache.status == cold → cache.hit_rate = zero.
   When cache.status == stale → cache.hit_rate = degraded.

3. **DB connection pool sync**: When db.status == healthy AND db.connection_pool == saturated
   → db.connection_pool = normal (auto-recovery after fix). When db.status in {locked, corrupted}
   → db.connection_pool = saturated.

4. **DNS propagation sync**: When dns.ttl_state == flushed AND user.actions.dns_flushed_locally == done
   → dns.resolution_state = correct.

5. **Incident status advancement**: When incident.root_cause != unknown → incident.status >= identified
   (sync enforces minimum). When all affected system statuses == healthy AND
   user.actions.smoke_test_state == passed → incident.status = resolved.

Design rules:

- `incident.root_cause` transitions from `unknown` to a specific value exactly once via
  `correlate_and_triage`. It is init-stable after that (never reverts to unknown).
- `incident.status` is sync-mediated: it advances based on world state but never retreats.
- System status fields (`app.status`, `db.status`, etc.) are the canonical health sources.
  Restarting a system may or may not fix it depending on the root cause (value-gated effects).
- `user.view.display_*` fields are pure projections of agent state, mirrored every sync pass.
- Knowledge bindings from investigation tools are volatile on the corresponding system status:
  restarting a service invalidates its investigation binding because the logs/state have changed.

## 10. Dependency patterns to support

### Bindings (6 bindings, 5 source tools, 4 volatile)

- `K.error_pattern` from assistant `check_app_logs` — volatile on `agent.app.status`
- `K.db_diagnostic` from assistant `run_db_diagnostic` — volatile on `agent.db.status`
- `K.cache_metrics` from assistant `check_cache_metrics` — volatile on `agent.cache.status`
- `K.auth_detail` from assistant `check_auth_logs` — volatile on `agent.auth.status`
- `K.local_error_pattern` from user `tail_app_logs` — volatile on `agent.app.status`
- `K.trace_signal` from user `check_traces` — stable (traces are immutable snapshots)

### Value-gated branches

- `incident.root_cause` (6 values) activates completely different resolution subgraphs:
  - `app_bug` → app restart/rollback + feature flag lane
  - `db_failure` → db repair + replication + vacuum lane
  - `cache_cascade` → cache flush + db check + warm lane (cross-system)
  - `auth_outage` → cert rotation OR token refresh OR rate limit clear (3 sub-branches)
  - `config_drift` → rollback deploy + toggle flags + restart (ordered)
  - `network_partition` → LB reconfig + DNS fix + queue recovery (3 parallel sub-lanes)

- `auth.status` (4 values) enables different auth repair tools:
  - `token_expired` → `refresh_auth_tokens`
  - `cert_invalid` → `rotate_auth_certs`
  - `rate_limited` → `reset_rate_limits`
  - `healthy` → no auth repair needed

- `db.status` (4 values) enables different db repair tools:
  - `degraded` → `run_db_vacuum` (if vacuum_state == needs_vacuum)
  - `locked` → `drain_connection_pool` then `restart_db_primary`
  - `corrupted` → `failover_to_replica` (if replication not broken)

- `queue.status` (4 values) enables different queue repair:
  - `consumer_dead` → `restart_queue_consumers`
  - `poison_pill` → `purge_poison_pill` (requires K.error_pattern for identification)
  - `backed_up` → `restart_queue_consumers` + `replay_dead_letters` after app healthy

### User-side ordering (DAG, not basket)

- Investigation mini-DAG:
  - `check_dashboard` must precede `tail_app_logs` (dashboard gives you context for which logs to tail)
  - `tail_app_logs` must precede `check_traces` (error pattern helps target trace search)
  - `take_metrics_snapshot` is independent (can happen anytime)

- Recovery action ordering:
  - `confirm_rollback` requires assistant to have initiated `rollback_deploy` first
  - `toggle_local_feature_flag` requires assistant `toggle_feature_flag` to have set server-side first
  - `run_smoke_test` requires ALL affected systems healthy (terminal gate, not early)
  - `warm_cache_locally` requires cache.status == cold AND db.status == healthy (cross-lane!)
  - `flush_local_dns` requires assistant `flush_dns_cache` to have cleared server-side first
  - `verify_connectivity` requires lb.status == healthy AND dns.resolution_state == correct

### Early convergence points (mid-graph, not just terminal)

1. **`correlate_and_triage`** requires 2+ of {K.error_pattern, K.db_diagnostic, K.cache_metrics, K.auth_detail}
   plus K.local_error_pattern or K.trace_signal. This is the primary mid-graph convergence — the agent
   MUST investigate multiple systems before it can identify root cause and proceed to resolution.

2. **`warm_cache`** (assistant) requires cache.status == cold AND db.status == healthy — cross-lane
   convergence between cache lane and DB lane. For cache_cascade incidents, you must fix DB first.

3. **`replay_dead_letters`** requires queue.consumer_state == restarted AND app.status == healthy —
   cross-lane convergence between queue lane and app lane.

4. **`drain_and_rebalance`** requires lb.status == overloaded AND app.status != crashing —
   must stabilize app before rebalancing load.

### Shared final funnel

All branches must clear these before terminal:

1. All directly-affected system statuses == healthy
2. `incident.root_cause` != unknown (must be identified)
3. `incident.comms_state` == all_sent (must notify stakeholders)
4. `user.actions.smoke_test_state` == passed (user validates fix)
5. `incident.status` == resolved (sync-mediated from above)

This means even after fixing the primary system, the agent must:
- Send internal + external comms (ordered: internal first, then external)
- Ask user to run smoke test
- Verify incident status resolved

### Non-uniform binding usage

| Tool/action | Requires K.error_pattern | Requires K.db_diagnostic | Requires K.cache_metrics | Requires K.auth_detail | Requires K.local_error_pattern | Requires K.trace_signal |
| --- | --- | --- | --- | --- | --- | --- |
| `correlate_and_triage` | 1 of 2+ required | 1 of 2+ required | optional additional | optional additional | 1 of 2+ required | alt for local_error |
| `restart_app_service` | yes (to know if restart will help) | no | no | no | no | no |
| `purge_poison_pill` | yes (to identify poison message) | no | no | no | no | no |
| `reconfigure_cache_ttl` | no | no | yes | no | no | no |
| `rotate_auth_certs` | no | no | no | yes | no | no |
| `repair_replication` | no | yes | no | no | no | no |

### Volatile binding discipline

- `K.error_pattern` invalidates when app.status changes (restart clears logs)
- `K.db_diagnostic` invalidates when db.status changes (repair changes diagnostic state)
- `K.cache_metrics` invalidates when cache.status changes (flush changes metrics)
- `K.auth_detail` invalidates when auth.status changes (cert rotation changes error surface)

Policy must instruct:
- Acquire investigation bindings BEFORE attempting repairs (repairs invalidate them)
- If a repair fails or partially succeeds, RE-ACQUIRE the relevant binding before next attempt
- `K.trace_signal` is stable — traces are immutable historical snapshots, safe to use throughout

### Terminal profiles and task length strategy

Shorter/easier tasks:
- Start with root_cause already identified + some systems pre-repaired
- Only need to fix 1-2 remaining systems + comms + smoke test

Medium tasks:
- Start with root_cause unknown but only 1 system broken
- Need: investigate → triage → fix → comms → smoke test

Hard tasks:
- Start with root_cause unknown + 2-3 systems broken + cascading failures
- Need: investigate multiple systems → triage → fix in correct order (cross-lane deps) → comms → smoke test

### Late-stage shared gates every branch must clear

- `send_comms(internal)` requires incident.root_cause != unknown
- `send_comms(external)` requires incident.comms_state == internal_sent (ordered!)
- `draft_postmortem` requires incident.status == resolved
- `run_smoke_test` requires all affected systems healthy
- `check_resolution_status` confirms all stop-gate criteria met

## 11. Known risks

- **Combinatorial explosion**: 6 root cause categories × 4 severity/knowledge axes × secondary failures
  could produce 500+ tasks. Use `max_tasks` cap and ensure dedup catches topological duplicates.
- **Cross-lane complexity**: Deep cross-system dependencies could make some seeds unsolvable within
  max_depth. Preflight SAT checks will catch this, but seed design must keep longest paths ≤ 14 steps.
- **Volatile binding chains**: If agent restarts a service to fix it, then needs the binding from that
  service to triage, we have a circular dependency. Design: triage MUST happen before repairs. Repairs
  invalidate bindings but triage is already complete (root_cause is stable post-triage).
- **Sync rule complexity**: 5 sync rules with cross-system dependencies. Must verify no oscillation
  (fixed-point convergence in ≤ 2 passes).
- **False breadth from independent fixes**: If 3 broken systems require 3 independent fixes with no
  interaction, that's a basket task. Cross-lane dependencies (warm_cache needs db.healthy, replay_dlq
  needs app.healthy) prevent this.
- **Policy drift**: SRE domain has many plausible resolution strategies. Policy must constrain to
  contract-valid paths without prescribing a single sequence.

## 12. Stop-gate observables (candidate)

Primary:

- `incident_status` — must reach `resolved`
- `smoke_test_state` — must reach `passed`

Supporting (per-system health):

- `app_status`
- `db_status`
- `cache_status`
- `auth_status`
- `lb_status`
- `queue_status`
- `dns_resolution_state`

Comms:

- `comms_state` — must reach `all_sent`

System-specific detail:

- `deploy_version`
- `replication_state`
- `cert_state`
- `token_pool`
- `routing_mode`
- `consumer_state`

## 13. Persona strategy (candidate)

- `senior_sre`: Experienced, concise, knows the infrastructure well. Proactively runs diagnostics
  and reports results precisely. Good for hard tasks — won't need hand-holding on observability steps.
- `junior_oncall`: First rotation, nervous, needs clear step-by-step guidance. May report vague
  symptoms instead of structured data. Good for medium tasks — tests the agent's ability to guide.
- `platform_engineer`: Deep knowledge of one system (e.g., database) but unfamiliar with others.
  Excellent at DB diagnostics but needs help with auth or networking. Good for cross-lane tasks.
- `manager_escalation`: Non-technical, escalated because the on-call didn't resolve it. Focused on
  business impact and comms. Can run smoke tests but can't interpret logs. Good for easy tasks where
  the resolution path is short.

Behavioral axes:

- Technical depth: how much system detail the user provides unprompted
- Urgency: how much pressure to resolve quickly (sev1 personas are more urgent)
- Compliance: how well the user follows the agent's instructions vs doing their own thing
- Verbosity: terse CLI output vs narrative descriptions

## 14. Out of scope (pilot)

- Multi-region failover or cross-datacenter coordination
- Kubernetes pod-level orchestration (abstracted to service-level)
- CI/CD pipeline repair (deploys are assumed already built, just need rollback)
- Cost optimization or capacity planning
- Security incident response (breach investigation, forensics)
- Multi-incident coordination (one incident at a time)
- Infrastructure provisioning (new servers, new databases)
- Monitoring/alerting configuration changes
- Customer-facing status page management (abstracted to comms_state)
