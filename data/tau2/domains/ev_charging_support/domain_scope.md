# Pilot Domain Scope (v2): ev_charging_support

## 1. Pilot domain

EV charging recovery for blocked charge-start sessions where assistant-side backend repair,
customer-side physical/app actions, and late-stage authorization gates must converge before
charging can actually start.

Pilot slice:

- One active account, station, network path, and charge session per task.
- Three recovery branches:
  - `billing`
  - `connectivity`
  - `full_system`
- Each branch ends only at a true terminal state where the visible station fault is gone,
  retry is ready, and a real test charge has been run.

## 2. Agent DB schema sketch

Entity: `EVAccount`

- `account_id: str`
- `customer_name: str`
- `hold_status: enum[present, cleared]`
- `payment_token_status: enum[invalid, valid]`
- `fraud_lock_state: enum[on, off]`

Entity: `EVStation`

- `station_id: str`
- `site_id: str`
- `reachability_state: enum[reachable, unreachable]`
- `firmware_state: enum[outdated, current]`
- `clock_sync_state: enum[skewed, synced]`
- `diagnostics_state: enum[idle, ran]`

Entity: `EVNetworkPath`

- `station_id: str`
- `backend_link_state: enum[down, up]`
- `cert_state: enum[stale, fresh]`
- `handshake_state: enum[broken, established]`

Entity: `EVChargeSession`

- `session_id: str`
- `account_id: str`
- `station_id: str`
- `error_class: enum[billing, connectivity, full_system]`
- `allowlist_sync_state: enum[stale, synced]`
- `tariff_profile_state: enum[missing, ready]`
- `reservation_lock_state: enum[present, cleared]`
- `session_auth_state: enum[stale, valid]`
- `profile_state: enum[not_ready, ready]`
- `vehicle_auth_state: enum[pending, validated]`
- `retry_state: enum[not_ready, ready]`
- `charge_state: enum[inactive, active]`
- `last_fault_code: str`

## 3. User DB schema sketch

Entity: `UserContext`

- `user_id: str | null`
- `name: str | null`
- `account_id: str | null`
- `station_id: str | null`
- `session_id: str | null`

Entity: `PhysicalState`

- `screen_accessible: bool`
- `station_power_cycle_state: enum[not_done, done]`
- `connector_reseat_state: enum[not_reseated, reseated]`
- `cable_inspection_state: enum[not_checked, checked_ok]`
- `vehicle_ready_state: enum[not_ready, ready]`
- `app_refresh_state: enum[stale, refreshed]`
- `app_login_state: enum[expired, active]`
- `connector_latch_state: enum[unconfirmed, confirmed]`
- `test_charge_state: enum[not_run, run]`

Entity: `ViewState`

- `display_fault_code: str | null`
- `display_charge_status: str`
- `display_hold_status: str | null`
- `display_payment_token_status: str | null`
- `display_fraud_lock_state: str | null`
- `display_reachability_state: str | null`
- `display_firmware_state: str | null`
- `display_clock_sync_state: str | null`
- `display_profile_state: str | null`
- `display_session_auth_state: str | null`
- `display_vehicle_auth_state: str | null`
- `display_retry_state: str | null`
- `display_backend_link_state: str | null`
- `display_cert_state: str | null`
- `display_handshake_state: str | null`
- `display_diagnostics_state: str | null`
- `display_error_class: str | null`

Entity: `StopGateState`

- `criteria: list[StopCriterion]`

## 4. Field projection table

| field_path | owner_db | type_or_domain | projected_for_solver | update_source | notes |
| --- | --- | --- | --- | --- | --- |
| `agent.accounts[active_account].hold_status` | agent | enum | yes | assistant_tool | billing lane |
| `agent.accounts[active_account].payment_token_status` | agent | enum | yes | assistant_tool | billing lane |
| `agent.accounts[active_account].fraud_lock_state` | agent | enum | yes | assistant_tool | billing lane |
| `agent.stations[active_station].reachability_state` | agent | enum | yes | assistant_tool | top-level station reachability |
| `agent.stations[active_station].firmware_state` | agent | enum | yes | assistant_tool | firmware lane |
| `agent.stations[active_station].clock_sync_state` | agent | enum | yes | assistant_tool | secure-transport prerequisite |
| `agent.stations[active_station].diagnostics_state` | agent | enum | yes | assistant_tool | establishes stable repair context |
| `agent.network_paths[active_station].backend_link_state` | agent | enum | yes | assistant_tool | secure-transport lane |
| `agent.network_paths[active_station].cert_state` | agent | enum | yes | assistant_tool | secure-transport lane |
| `agent.network_paths[active_station].handshake_state` | agent | enum | yes | assistant_tool | secure-transport lane |
| `agent.sessions[active_session].error_class` | agent | enum | yes | init_only | branch discriminator |
| `agent.sessions[active_session].session_auth_state` | agent | enum | yes | assistant_tool | late-stage auth lane |
| `agent.sessions[active_session].profile_state` | agent | enum | yes | assistant_tool | reprovision target |
| `agent.sessions[active_session].vehicle_auth_state` | agent | enum | yes | assistant_tool | post-profile auth lane |
| `agent.sessions[active_session].retry_state` | agent | enum | yes | assistant_tool | retry-reset lane |
| `agent.sessions[active_session].charge_state` | agent | enum | yes | sync | final success state |
| `agent.sessions[active_session].last_fault_code` | agent | str | yes | sync | canonical current visible station code |
| `user.physical.*` readiness fields | user | enums/bool | yes | user_tool | customer-side prerequisites |
| `user.view.display_*` observables | user | strings | yes | sync | stop-gate observable surface |
| `user.stop_gate.criteria` | user | list | no | init_only | runtime-only stop checker input |

## 5. Context slots

- `active_account -> EVAccount`
- `active_station -> EVStation`
- `active_session -> EVChargeSession`

## 6. Projected world paths

Projected causal and observable paths used by solver state:

- billing gates: hold, payment token, fraud lock
- station gates: reachability, firmware, clock sync, diagnostics
- network gates: backend link, certificate, handshake
- session gates: error class, session auth, profile, vehicle auth, retry, charge state, last fault code
- customer readiness: screen accessibility, cable inspection, connector reseat, power cycle,
  vehicle ready, app refresh, app login, connector latch, test charge
- user-visible projections consumed by `check_station_screen` and `check_resolution_status`

## 7. Assistant toolset (rough)

Observation-driven stage tools:

- `run_backend_diagnostics(fault_code, app_error_class)`
- `reprovision(branch, fault_code)`
- `reset_retry_path(fault_code)`

Stable-state repair tools after diagnosis:

- `clear_billing_hold()`
- `refresh_payment_token()`
- `release_fraud_lock()`
- `restore_backend_link()`
- `sync_station_clock()`
- `rotate_station_certificate()`
- `reestablish_station_handshake()`
- `update_station_firmware()`
- `clear_entitlement_blocker(blocker, fault_code)`
- `refresh_session_authorization()`
- `refresh_vehicle_authorization()`

Helper callables:

- context setters and per-field init helpers
- env assertions on agent-side state

## 8. User toolset (rough)

Discovery tools:

- `check_station_screen()` -> produces `screen_fault_code`
- `check_app_status()` -> produces `app_error_class`

Customer-side causal actions:

- `inspect_cable_path()`
- `reseat_connector()`
- `power_cycle_station()`
- `set_vehicle_ready_mode()`
- `refresh_charging_app_session()`
- `re_authenticate_charging_app()`
- `confirm_connector_latch()`
- `run_test_charge()`

Stutter-only checker:

- `check_resolution_status()`

## 9. World/sync logic

Canonical visible-fault priority, high to low:

1. `STATION_UNREACHABLE`
2. `NET-410`
3. `TIME-405`
4. `CERT-409`
5. `OCPP-411`
6. `BH-101`
7. `PAY-201`
8. `FRD-301`
9. `FW-410`
10. `ENT-210`
11. `ENT-220`
12. `ENT-230`
13. `AUTH-220`
14. `PROFILE-201`
15. `VEH-230`
16. `RETRY-301`
17. `NONE`

Design rules:

- `last_fault_code` is sync-owned. It reflects the current visible stage, not a stable incident id.
- `screen_fault_code` is therefore a volatile binding. It is only consumed at immediate
  observation-driven stage transitions: diagnostics, reprovision, and retry reset.
- The long middle of the repair path runs on stable world predicates after diagnostics rather
  than replaying a moving screen code through every tool.
- `charge_state` is sync-owned and fully recomputed from the world every sync pass. The
  contract must therefore declare both inactive defaults and active terminal conditions,
  not rely on runtime-only `else` branches.
- `user.view.display_*` fields are pure projections of projected agent/user state.

## 10. Dependency patterns to support

Bindings:

- `screen_fault_code` from `check_station_screen`
- `app_error_class` from `check_app_status`

Value-gated branches:

- `error_class` selects billing vs connectivity vs full-system reprovision path

User-side ordering:

- hardware lane: `inspect_cable_path -> reseat_connector -> power_cycle_station`
- late-stage auth lane: `set_vehicle_ready_mode` supports `confirm_connector_latch`,
  which supports `refresh_vehicle_authorization`
- app auth lane: `re_authenticate_charging_app` may be required before `refresh_session_authorization`

Early convergence:

- `run_backend_diagnostics` requires both discovered bindings
- `refresh_session_authorization` sits after branch-specific backend cleanup and before reprovision
- reprovision requires both stable backend readiness and customer readiness

Shared final funnel:

- branch repair -> session auth -> reprovision -> vehicle auth -> retry reset -> test charge

Structural diversity target:

- harder tasks add interacting lanes before the same final funnel
- easier tasks start later in the funnel with more prerequisites already satisfied
- shorter tasks never stop at partial milestone states under a full-resolution policy

## 11. Known risks

- Policy drift: if `policy.md` names an incomplete tool surface or misses volatile reread rules,
  live agent behavior will diverge from the authored contract.
- Sync drift: if `sync_tools()` recomputes a field in ways the contract cannot reproduce from
  `sync_rules`, sampler/preflight/runtime will disagree.
- False breadth: adding many independent fixes with no shared downstream gate would make EV look
  larger without adding real reasoning depth.
- Hidden prerequisites: if a terminal profile depends on a lane that is not exposed through tools
  or policy, tasks become unfair instead of hard.
- Reward confusion: repeated binding reacquisition is not faithfully represented by deduped
  `required_actions`, so correctness must come from env assertions and stop-gates.

## 12. Stop-gate observables (candidate)

Primary:

- `fault_code`
- `charge_status`

Supporting:

- `hold_status`
- `payment_token_status`
- `fraud_lock_state`
- `firmware_state`
- `clock_sync_state`
- `backend_link_state`
- `cert_state`
- `handshake_state`
- `session_auth_state`
- `profile_state`
- `vehicle_auth_state`
- `retry_state`
- `diagnostics_state`

## 13. Persona strategy (candidate)

- `hurried_commuter`: concise, impatient with redundant checks
- `detail_oriented_driver`: reports tool outputs cleanly and follows ordering well
- `low_tech_user`: needs simpler instructions and stricter sequencing
- `experienced_ev_user`: comfortable with app and physical troubleshooting

Easy tasks should still vary persona style without leaking backend knowledge.
Hard tasks should mix deeper branch interaction with personas that may require clearer sequencing.

## 14. Out of scope (pilot)

- creating or editing payment methods
- refunds, plan changes, or account-management workflows outside current session recovery
- dispatching field technicians or replacing station hardware
- multi-session or multi-station coordination
- recovering truly unreachable stations beyond surfacing the blocker and escalating
