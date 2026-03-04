# Pilot Domain Scope (v2): ev_charging_support

## 1. Pilot domain

EV charging recovery for failed charge-start sessions where backend remediation and user physical actions must both occur.

Pilot slice:

- Public station support for one active account/station/session context.
- Focus on hold clearance, profile reprovision, and user retry workflow.
- Exclude payments, reservations, and network-wide incident management.

## 2. Agent DB schema sketch

Entity: `Account`

- `account_id: str` (pk)
- `customer_name: str`
- `hold_status: enum[present, cleared]`

Entity: `Station`

- `station_id: str` (pk)
- `site_id: str`
- `reachability_state: enum[reachable, unreachable]`
- `connector_health: enum[healthy, degraded, blocked]`

Entity: `ChargeSession`

- `session_id: str` (pk)
- `account_id: str` (fk -> Account.account_id)
- `station_id: str` (fk -> Station.station_id)
- `profile_state: enum[not_ready, ready]`
- `retry_state: enum[not_ready, ready]`
- `charge_state: enum[inactive, active]`
- `last_fault_code: str`

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
- `test_charge_state: enum[not_run, run]`

Entity: `ViewState` (projection-only display fields)

- `display_fault_code: str | null`
- `display_station_message: str | null`
- `display_charge_status: str`
- `display_next_step_hint: str | null`
- `display_hold_status: str | null`
- `display_profile_state: str | null`
- `display_retry_state: str | null`

Entity: `StopGateState` (runtime stop criteria, projection-only)

- `criteria: list[StopCriterion]`

## 4. Field projection table

| field_path | owner_db | type_or_domain | projected_for_solver | update_source | notes |
| --- | --- | --- | --- | --- | --- |
| `agent.accounts[active_account].hold_status` | agent | `enum[present,cleared]` | yes | `assistant_tool` | backend gate for reprovision |
| `agent.stations[active_station].reachability_state` | agent | `enum[reachable,unreachable]` | yes | `assistant_tool/init_only` | physical actions require reachable station |
| `agent.stations[active_station].connector_health` | agent | `enum[healthy,degraded,blocked]` | no | `sync` | retained for runtime realism, not needed in v1 solver projection |
| `agent.sessions[active_session].profile_state` | agent | `enum[not_ready,ready]` | yes | `assistant_tool` | required before test charge succeeds |
| `agent.sessions[active_session].retry_state` | agent | `enum[not_ready,ready]` | yes | `assistant_tool/sync` | retry gate after reprovision |
| `agent.sessions[active_session].charge_state` | agent | `enum[inactive,active]` | yes | `sync` | becomes active after successful user test |
| `agent.sessions[active_session].last_fault_code` | agent | `str` | yes | `assistant_tool/sync` | used for user-visible diagnosis and debugging |
| `user.context.account_id` | user | `str` | no | `init_only` | context wiring only |
| `user.context.station_id` | user | `str` | no | `init_only` | context wiring only |
| `user.context.session_id` | user | `str` | no | `init_only` | context wiring only |
| `user.physical.screen_accessible` | user | `bool` | yes | `user_tool/init_only` | enables binding acquisition source tool |
| `user.physical.station_power_cycle_state` | user | `enum[not_done,done]` | yes | `user_tool` | causal prereq for reprovision |
| `user.physical.connector_reseat_state` | user | `enum[not_reseated,reseated]` | yes | `user_tool` | causal prereq for reprovision |
| `user.physical.test_charge_state` | user | `enum[not_run,run]` | yes | `user_tool` | final user execution step |
| `user.view.display_fault_code` | user | `str|null` | no | `sync/view_only` | display only, source for user read tool output |
| `user.view.display_station_message` | user | `str|null` | no | `sync/view_only` | display only |
| `user.view.display_charge_status` | user | `str` | no | `sync/view_only` | display only |
| `user.view.display_next_step_hint` | user | `str|null` | no | `sync/view_only` | display only |
| `user.view.display_hold_status` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_profile_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.view.display_retry_state` | user | `str|null` | no | `sync/view_only` | stop-gate observable |
| `user.stop_gate.criteria` | user | `list[StopCriterion]` | no | `init_only` | task-specific stop criteria injected post-sampling |

World-modeling stance:

- Runtime truth is split across agent DB + user DB (tau2-native).
- Solver world state is a projected union of selected fields from both DBs.

## 5. Context slots

Task template role slots:

- `active_account` -> `Account`
- `active_station` -> `Station`
- `active_session` -> `ChargeSession`

Task instances bind these slots to concrete ids later (for example via init selection).

## 6. Projected world paths

Projected paths used by the solver in this pilot:

- `agent.accounts[active_account].hold_status`
- `agent.stations[active_station].reachability_state`
- `agent.sessions[active_session].profile_state`
- `agent.sessions[active_session].retry_state`
- `agent.sessions[active_session].charge_state`
- `agent.sessions[active_session].last_fault_code`
- `user.physical.screen_accessible`
- `user.physical.station_power_cycle_state`
- `user.physical.connector_reseat_state`
- `user.physical.test_charge_state`

## 7. Assistant toolset (rough)

- `get_recovery_state()` read status summary (must avoid leaking dependency shortcuts)
- `clear_billing_hold(fault_code: str)` gated write
- `reprovision_charging_profile(fault_code: str)` gated write

Helper callables:

- init helpers: `set_*`
- env assertion helpers: `assert_*`

## 8. User toolset (rough)

- `check_station_screen()` read/discovery tool (binding source)
- `check_resolution_status()` stutter/read-only stop checker
- `power_cycle_station()` causal write
- `reseat_connector()` causal write
- `run_test_charge()` causal write

## 9. World/sync logic

`user -> agent` bridge:

- `station_power_cycle_state=done` contributes to agent-side readiness checks.
- `connector_reseat_state=reseated` contributes to agent-side readiness checks.
- `test_charge_state=run` sets `charge_state=active` only when backend/session gates are satisfied.

`agent -> user` projection:

- `last_fault_code` drives `user.view.display_fault_code`.
- session readiness and charge status drive user hints/messages.

## 10. Dependency patterns to support

Binding dependency:

- Assistant must acquire binding `fault_code` from `check_station_screen` before gated backend writes.

World gate dependency:

- Reprovision requires `hold_status=cleared` and both physical prereqs completed.

Long-horizon chain:

- acquire binding -> user power cycle -> user reseat -> clear hold -> reprovision -> user test charge.

## 11. Known risks

- Shortcut risk: assistant read tool exposes fault code directly, bypassing binding dependency.
- Ambiguity risk: contracts that omit context slots on multi-entity DB.
- Drift risk: sync logic diverges from projected/effected contract fields.
- Runtime mismatch risk: tool signatures do not enforce required bindings.

## 12. Stop-gate observables (candidate)

- `fault_code` <- `user.view.display_fault_code`
- `charge_status` <- `user.view.display_charge_status`
- `hold_status` <- `user.view.display_hold_status`
- `profile_state` <- `user.view.display_profile_state`
- `retry_state` <- `user.view.display_retry_state`
- `test_charge_state` <- `user.physical.test_charge_state`
