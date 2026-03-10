# Pilot Domain Scope (v2): ev_charging_support

## 1. Pilot domain

EV charging recovery for blocked charge-start sessions where backend controls and user
physical/app actions must be coordinated across long, value-gated dependency chains.

Pilot slice:

- One active account, station, network path, and charging session per task.
- Three recovery branches:
  - `billing`
  - `connectivity`
  - `full_system`
- The final success condition is an observable successful test charge, checked through
  strict stop-gating rather than prompt-only instructions.

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
- `diagnostics_state: enum[idle, ran]`

Entity: `EVNetworkPath`

- `station_id: str`
- `backend_link_state: enum[down, up]`
- `cert_state: enum[stale, fresh]`

Entity: `EVChargeSession`

- `session_id: str`
- `account_id: str`
- `station_id: str`
- `error_class: enum[billing, connectivity, full_system]`
- `profile_state: enum[not_ready, ready]`
- `retry_state: enum[not_ready, ready]`
- `charge_state: enum[inactive, active]`
- `last_fault_code: str`

## 3. User DB schema sketch

Entity: `UserContext`

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
- `test_charge_state: enum[not_run, run]`

Entity: `ViewState`

- `display_fault_code: str | null`
- `display_charge_status: str`
- `display_hold_status: str | null`
- `display_payment_token_status: str | null`
- `display_fraud_lock_state: str | null`
- `display_reachability_state: str | null`
- `display_firmware_state: str | null`
- `display_profile_state: str | null`
- `display_retry_state: str | null`
- `display_backend_link_state: str | null`
- `display_cert_state: str | null`
- `display_diagnostics_state: str | null`
- `display_error_class: str | null`

Entity: `StopGateState`

- `criteria: list[StopCriterion]`

## 4. Field projection table

| field_path | owner_db | type_or_domain | projected_for_solver | update_source | notes |
| --- | --- | --- | --- | --- | --- |
| `agent.accounts[active_account].hold_status` | agent | enum | yes | assistant_tool | billing gate |
| `agent.accounts[active_account].payment_token_status` | agent | enum | yes | assistant_tool | billing gate |
| `agent.accounts[active_account].fraud_lock_state` | agent | enum | yes | assistant_tool | billing gate |
| `agent.stations[active_station].reachability_state` | agent | enum | yes | assistant_tool | connectivity gate |
| `agent.stations[active_station].firmware_state` | agent | enum | yes | assistant_tool | firmware gate |
| `agent.stations[active_station].diagnostics_state` | agent | enum | yes | assistant_tool | establishes stable repair context |
| `agent.network_paths[active_station].backend_link_state` | agent | enum | yes | assistant_tool | connectivity gate |
| `agent.network_paths[active_station].cert_state` | agent | enum | yes | assistant_tool | connectivity gate |
| `agent.sessions[active_session].error_class` | agent | enum | yes | init_only | branch discriminator |
| `agent.sessions[active_session].profile_state` | agent | enum | yes | assistant_tool | reprovision target |
| `agent.sessions[active_session].retry_state` | agent | enum | yes | assistant_tool | retry-reset target |
| `agent.sessions[active_session].charge_state` | agent | enum | yes | sync | final success state |
| `agent.sessions[active_session].last_fault_code` | agent | str | yes | sync | canonical current visible fault |
| `user.physical.*` readiness fields | user | enums/bool | yes | user_tool | physical/app prerequisites |
| `user.view.display_*` observables | user | strings | yes | sync | stop-gate observable surface |
| `user.stop_gate.criteria` | user | list | no | init_only | runtime-only stop checker input |

## 5. Context slots

- `active_account -> EVAccount`
- `active_station -> EVStation`
- `active_session -> EVChargeSession`

## 6. Projected world paths

Projected causal and observable paths used by the solver/runtime contract:

- account gates: hold, payment token, fraud lock
- station gates: reachability, firmware, diagnostics
- network gates: backend link, certificate
- session gates: error class, profile, retry, charge state, last fault code
- user physical/app steps: screen accessibility, cable inspect, connector reseat, power cycle,
  vehicle ready, app refresh, test charge
- user view observables used by `check_resolution_status`: fault code, charge status, hold,
  payment token, fraud lock, reachability, firmware, profile, retry, backend link,
  certificate, diagnostics, error class

## 7. Assistant toolset (rough)

Observation-driven tools:

- `run_backend_diagnostics(fault_code, app_error_class)`
- `reprovision_billing(fault_code)`
- `reprovision_connectivity(fault_code)`
- `reprovision_full_system(fault_code)`
- `reset_retry_path(fault_code)`

Stable-state repair tools after diagnostics:

- `clear_billing_hold()`
- `refresh_payment_token()`
- `release_fraud_lock()`
- `restore_backend_link()`
- `rotate_station_certificate()`
- `update_station_firmware()`

Helper callables:

- context setters (`set_user_context`, etc.)
- env assertions (`assert_*`)

## 8. User toolset (rough)

Discovery tools:

- `check_station_screen()` -> produces `screen_fault_code`
- `check_app_status()` -> produces `app_error_class`

Causal user actions:

- `inspect_cable_path()`
- `reseat_connector()`
- `power_cycle_station()`
- `set_vehicle_ready_mode()`
- `refresh_charging_app_session()`
- `run_test_charge()`

Stutter-only checker:

- `check_resolution_status()`

## 9. World/sync logic

Canonical fault-code priority, high to low:

1. `STATION_UNREACHABLE`
2. `NET-410`
3. `CERT-409`
4. `BH-101`
5. `PAY-201`
6. `FRD-301`
7. `FW-410`
8. `PROFILE-201`
9. `RETRY-301`
10. `NONE`

Design rules:

- `last_fault_code` is a sync-owned projection of the current world state, not a stable
  incident identifier.
- `screen_fault_code` is therefore a volatile binding. It is only used at stages where
  “what the screen shows right now” is the real contract:
  diagnostics, reprovision, and retry reset.
- Once diagnostics has run, the repair chain is expressed in stable world predicates
  (`hold_status`, `payment_token_status`, `fraud_lock_state`, `backend_link_state`,
  `cert_state`, `firmware_state`) rather than replaying screen codes through every tool.
- `check_station_screen()` formats the user-facing message locally from projected fields.
  Hidden display text is not authored inside `sync_tools()`.
- Charge activation is split:
  - `billing` requires backend readiness plus vehicle/app readiness
  - `connectivity` and `full_system` additionally require cable inspect, connector reseat,
    and station power cycle

## 10. Dependency patterns to support

Multiple bindings:

- `screen_fault_code` from `check_station_screen`
- `app_error_class` from `check_app_status`

Value-dependent branching:

- `error_class` selects billing vs connectivity vs full-system reprovision path

User action ordering:

- `inspect_cable_path -> reseat_connector -> power_cycle_station`

Early convergence:

- `run_backend_diagnostics` requires both discovered values
- reprovision requires branch-specific backend clearance plus user readiness steps

Volatile-stage discipline:

- the same `screen_fault_code` binding may be reacquired multiple times
- the policy must tell the agent that the screen code is volatile and must be reread
  when reprovision or retry-reset decisions depend on the current visible value,
  without prescribing a full repair script

## 11. Known risks

- Policy drift: if `policy.md` omits a tool, volatile reread constraint, or stop rule,
  the live agent behavior will diverge from the contract even when SAT/preflight pass.
- Over-prescriptive policy: if `policy.md` encodes a fixed tool trajectory, the benchmark
  stops testing agent reasoning and starts testing prompt obedience.
- Volatile-binding overuse: if repair tools take `fault_code` directly, the current visible
  code can advance mid-turn and invalidate otherwise-correct recovery calls.
- Sync drift: if `sync_tools()` invents display logic not declared in `sync_rules`, start
  worlds and runtime behavior will diverge.
- Branch contamination: billing tasks must not accidentally inherit hardware-only
  prerequisites.
- Reward confusion: repeated binding reacquisition is not fully represented in deduped
  `required_actions`, so correctness must come from env assertions and stop-gates.

## 12. Stop-gate observables (candidate)

Primary:

- `fault_code`
- `charge_status`

Supporting branch observables:

- `hold_status`
- `payment_token_status`
- `fraud_lock_state`
- `backend_link_state`
- `cert_state`
- `firmware_state`
- `profile_state`
- `retry_state`
- `diagnostics_state`
- `error_class`

## 13. Persona strategy (candidate)

- `hurried_commuter`: urgent, concise, less patient with repeated steps
- `detail_oriented_driver`: careful, reports tool outputs accurately
- `low_tech_user`: needs tighter sequencing and simpler instructions
- `experienced_ev_user`: comfortable with app and vehicle-readiness steps

Easy tasks should skew toward cooperative/detail-oriented personas.
Harder long-horizon tasks should still vary persona style without leaking backend knowledge.

## 14. Out of scope (pilot)

- Payments/refunds outside the charging-session recovery flow
- Creating accounts, adding cards, or changing plan settings
- Hardware replacement or dispatch workflows
- Multi-session or multi-station coordination
- General station-unreachable recovery beyond surfacing the current blocker and escalating
