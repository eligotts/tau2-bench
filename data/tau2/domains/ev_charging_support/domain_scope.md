# Pilot Domain Scope (v2): ev_charging_support

## 1. Pilot domain

EV charging recovery for blocked charge-start sessions where backend controls and user physical/app actions must be combined in long dependency chains.

Pilot slice:

- Public charging support for one active account/station/session context per task.
- Focus on recoveries involving account gates, station gates, and user-side readiness gates.
- Goal is to support both assistant-heavy and user-heavy recovery paths.

## 2. Agent DB schema sketch

Entity: `Account`

- `account_id: str` (pk)
- `customer_name: str`
- `hold_status: enum[present, cleared]`
- `payment_token_status: enum[invalid, valid]`
- `fraud_lock_state: enum[on, off]`

Entity: `Station`

- `station_id: str` (pk)
- `site_id: str`
- `reachability_state: enum[reachable, unreachable]`
- `firmware_state: enum[outdated, current]`
- `diagnostics_state: enum[idle, ran]`

Entity: `ChargeSession`

- `session_id: str` (pk)
- `account_id: str` (fk -> Account.account_id)
- `station_id: str` (fk -> Station.station_id)
- `profile_state: enum[not_ready, ready]`
- `retry_state: enum[not_ready, ready]`
- `charge_state: enum[inactive, active]`
- `last_fault_code: str`

Entity: `NetworkPath`

- `station_id: str` (fk -> Station.station_id)
- `backend_link_state: enum[down, up]`
- `cert_state: enum[stale, fresh]`

## 3. User DB schema sketch

Entity: `UserContext`

- `user_id: str` (pk)
- `name: str`
- `account_id: str` (fk -> Account.account_id)
- `station_id: str` (fk -> Station.station_id)
- `session_id: str` (fk -> ChargeSession.session_id)

Entity: `PhysicalState`

- `screen_accessible: bool`
- `station_power_cycle_state: enum[not_done, done]`
- `connector_reseat_state: enum[not_reseated, reseated]`
- `cable_inspection_state: enum[not_checked, checked_ok]`
- `vehicle_ready_state: enum[not_ready, ready]`
- `app_refresh_state: enum[stale, refreshed]`
- `test_charge_state: enum[not_run, run]`

Entity: `ViewState` (projection-only display fields)

- `display_fault_code: str | null`
- `display_station_message: str | null`
- `display_charge_status: str`
- `display_next_step_hint: str | null`
- `display_hold_status: str | null`
- `display_payment_token_status: str | null`
- `display_fraud_lock_state: str | null`
- `display_reachability_state: str | null`
- `display_firmware_state: str | null`
- `display_profile_state: str | null`
- `display_retry_state: str | null`

Entity: `StopGateState` (runtime stop criteria, projection-only)

- `criteria: list[StopCriterion]`

## 4. Field projection table

| field_path | owner_db | type_or_domain | projected_for_solver | update_source | notes |
| --- | --- | --- | --- | --- | --- |
| `agent.accounts[active_account].hold_status` | agent | `enum[present,cleared]` | yes | `assistant_tool` | backend gate |
| `agent.accounts[active_account].payment_token_status` | agent | `enum[invalid,valid]` | yes | `assistant_tool` | backend auth gate |
| `agent.accounts[active_account].fraud_lock_state` | agent | `enum[on,off]` | yes | `assistant_tool` | backend risk gate |
| `agent.stations[active_station].reachability_state` | agent | `enum[reachable,unreachable]` | yes | `assistant_tool/sync` | station online/offline gate |
| `agent.stations[active_station].firmware_state` | agent | `enum[outdated,current]` | yes | `assistant_tool` | reprovision gate |
| `agent.stations[active_station].diagnostics_state` | agent | `enum[idle,ran]` | yes | `assistant_tool` | required precondition for hold-clear gate |
| `agent.network_paths[active_station].backend_link_state` | agent | `enum[down,up]` | yes | `assistant_tool` | connectivity gate |
| `agent.network_paths[active_station].cert_state` | agent | `enum[stale,fresh]` | yes | `assistant_tool` | connectivity gate |
| `agent.sessions[active_session].profile_state` | agent | `enum[not_ready,ready]` | yes | `assistant_tool` | must be ready before final success |
| `agent.sessions[active_session].retry_state` | agent | `enum[not_ready,ready]` | yes | `assistant_tool` | must be ready before final success |
| `agent.sessions[active_session].charge_state` | agent | `enum[inactive,active]` | yes | `sync` | final success state |
| `agent.sessions[active_session].last_fault_code` | agent | `str` | yes | `assistant_tool/sync` | user-visible diagnostic anchor |
| `user.context.account_id` | user | `str` | no | `init_only` | context wiring only |
| `user.context.station_id` | user | `str` | no | `init_only` | context wiring only |
| `user.context.session_id` | user | `str` | no | `init_only` | context wiring only |
| `user.physical.screen_accessible` | user | `bool` | yes | `user_tool/init_only` | required for fault-code discovery |
| `user.physical.station_power_cycle_state` | user | `enum[not_done,done]` | yes | `user_tool` | reprovision prereq |
| `user.physical.connector_reseat_state` | user | `enum[not_reseated,reseated]` | yes | `user_tool` | reprovision prereq |
| `user.physical.cable_inspection_state` | user | `enum[not_checked,checked_ok]` | yes | `user_tool` | reprovision prereq |
| `user.physical.vehicle_ready_state` | user | `enum[not_ready,ready]` | yes | `user_tool` | reprovision prereq |
| `user.physical.app_refresh_state` | user | `enum[stale,refreshed]` | yes | `user_tool` | reprovision prereq |
| `user.physical.test_charge_state` | user | `enum[not_run,run]` | yes | `user_tool` | final user step |
| `user.view.display_fault_code` | user | `str|null` | no | `sync/view_only` | user-facing status |
| `user.view.display_station_message` | user | `str|null` | no | `sync/view_only` | user-facing status |
| `user.view.display_charge_status` | user | `str` | no | `sync/view_only` | user-facing status |
| `user.view.display_next_step_hint` | user | `str|null` | no | `sync/view_only` | user-facing hint |
| `user.view.display_hold_status` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_payment_token_status` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_fraud_lock_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_reachability_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_firmware_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_profile_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_retry_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_backend_link_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_cert_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_diagnostics_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.stop_gate.criteria` | user | `list[StopCriterion]` | no | `init_only` | task-specific stop criteria |

World-modeling stance:

- Runtime truth is split across agent DB + user DB (tau2-native).
- Solver world state is a projected union of selected causal fields from both DBs.

## 5. Context slots

Task template role slots:

- `active_account` -> `Account`
- `active_station` -> `Station`
- `active_session` -> `ChargeSession`

## 6. Projected world paths

Projected paths used by solver state in this pilot:

- `agent.accounts[active_account].hold_status`
- `agent.accounts[active_account].payment_token_status`
- `agent.accounts[active_account].fraud_lock_state`
- `agent.stations[active_station].reachability_state`
- `agent.stations[active_station].firmware_state`
- `agent.stations[active_station].diagnostics_state`
- `agent.network_paths[active_station].backend_link_state`
- `agent.network_paths[active_station].cert_state`
- `agent.sessions[active_session].profile_state`
- `agent.sessions[active_session].retry_state`
- `agent.sessions[active_session].charge_state`
- `agent.sessions[active_session].last_fault_code`
- `user.physical.screen_accessible`
- `user.physical.station_power_cycle_state`
- `user.physical.connector_reseat_state`
- `user.physical.cable_inspection_state`
- `user.physical.vehicle_ready_state`
- `user.physical.app_refresh_state`
- `user.physical.test_charge_state`

## 7. Assistant toolset (rough)

- `clear_billing_hold(fault_code)` write
- `run_backend_diagnostics(fault_code)` write
- `refresh_payment_token(fault_code)` write
- `release_fraud_lock(fault_code)` write
- `restore_backend_link(fault_code)` write
- `rotate_station_certificate(fault_code)` write
- `update_station_firmware(fault_code)` write
- `reprovision_charging_profile(fault_code)` write
- `reset_retry_path(fault_code)` write

Helper callables:

- init helpers: `set_*`
- env assertion helpers: `assert_*`

## 8. User toolset (rough)

- `check_station_screen()` read/discovery tool (binding source)
- `power_cycle_station()` causal write
- `reseat_connector()` causal write
- `inspect_cable_path()` causal write
- `set_vehicle_ready_mode()` causal write
- `refresh_charging_app_session()` causal write
- `run_test_charge()` causal write
- `check_resolution_status()` stutter/read-only stop checker

## 9. World/sync logic

`user -> agent` bridge:

- `run_test_charge` can set `charge_state=active`, but only if all backend and user prereqs are satisfied.

`agent -> user` projection:

- Account/session/station/network statuses are mirrored into `user.view.*`.
- `last_fault_code` and readiness states drive screen message + next-step hint.

Fault-code projection priority (high -> low):

1. network/backend path down -> network fault
2. hold/payment/fraud account gates
3. firmware/profile/retry readiness gates
4. no faults (`NONE`) when all readiness gates clear

## 10. Dependency patterns to support

Binding dependency:

- Assistant backend actions require `fault_code` acquired through user `check_station_screen`.

User-action gate dependency:

- Reprovision path requires multiple user-side prerequisites:
  `power_cycle + reseat + cable inspect + vehicle ready + app refresh`.

Backend gate dependency:

- Recovery often requires ordered backend gates:
  `diagnostics -> clear hold -> refresh payment token -> release fraud lock -> backend link -> certificate -> firmware -> reprovision -> retry reset`.

Long-horizon chain target:

- 8-12 action dependencies in full-recovery tasks, plus optional shorter partial-recovery tasks.

## 11. Known risks

- Shortcut risk: assistant tooling accidentally clears multiple backend gates in one action.
- Ambiguity risk: action/tool naming drift (`action_id` vs callable names) can break runtime checks.
- Sync drift risk: projected `user.view.*` fields diverge from true world state.
- Over-gating risk: impossible chains if tool guards are stricter than contract preconditions.
- Narrative drift risk: user prompt asks for actions that have no corresponding user tools.

## 12. Stop-gate observables (candidate)

- `fault_code` <- `user.view.display_fault_code`
- `charge_status` <- `user.view.display_charge_status`
- `hold_status` <- `user.view.display_hold_status`
- `payment_token_status` <- `user.view.display_payment_token_status`
- `fraud_lock_state` <- `user.view.display_fraud_lock_state`
- `reachability_state` <- `user.view.display_reachability_state`
- `firmware_state` <- `user.view.display_firmware_state`
- `profile_state` <- `user.view.display_profile_state`
- `retry_state` <- `user.view.display_retry_state`
- `backend_link_state` <- `user.view.display_backend_link_state`
- `cert_state` <- `user.view.display_cert_state`
- `diagnostics_state` <- `user.view.display_diagnostics_state`
- `test_charge_state` <- `user.physical.test_charge_state`

## 13. Out of scope (pilot)

- Payment amount disputes/refunds and billing plan changes.
- Reservation/queueing systems across multiple stations.
- Route planning or external map integrations.
- Hardware replacement dispatch workflows.
