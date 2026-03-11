# Depgraph Session Contract (v2): ev_charging_support

- Step goal:
  - Keep EV charging support aligned to depgraph v2 with sync-rule-owned derived state, volatile screen-fault bindings, stable post-diagnostics repair state, and explicit terminal-only task endings.
  - Add cheap task variety through new early-ticket lane combinations or knowledge variants, not by starting midway through the domain's own repair funnel.
  - Keep agent-visible runtime narratives on the case surface: `reason_for_call`, `known_info`, and `ticket` may include user-observable start facts, but must not enumerate latent blocker sets or internal recovery lanes.

- Files to keep aligned as one unit:
  - `data/tau2/domains/ev_charging_support/domain_scope.md`
  - `data/tau2/domains/ev_charging_support/graph_contract.yaml`
  - `data/tau2/domains/ev_charging_support/policy.md`
  - `data/tau2/domains/ev_charging_support/runtime_defaults.yaml`
  - `data/tau2/domains/ev_charging_support/sampling_request.yaml`
  - `src/tau2/domains/ev_charging_support/tools.py`
  - `src/tau2/domains/ev_charging_support/user_tools.py`
  - `src/tau2/domains/ev_charging_support/environment.py`

- Acceptance checks:
  - Use `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md` as source of truth.
  - Use depgraph v2 contract shape (`version: 2`) from `src/tau2/generators/depgraph/types.py`.
  - `screen_fault_code` tracks the current visible `last_fault_code` and invalidates when that value changes.
  - Only immediate observation-driven assistant tools consume `screen_fault_code`: diagnostics, reprovision, and retry reset.
  - The long repair chain (`clear_billing_hold`, `refresh_payment_token`, `release_fraud_lock`, `restore_backend_link`, `sync_station_clock`, `rotate_station_certificate`, `reestablish_station_handshake`, `update_station_firmware`, `refresh_session_authorization`, `refresh_vehicle_authorization`) runs from stable world state after diagnostics, not from stale screen-code args.
  - `sync_rules` are the single source of truth for `last_fault_code` and projected `user.view.*` observables.
  - Any sync-owned field recomputed by runtime `sync_tools()` in both positive and negative directions must have exhaustive sync rules; no runtime-only fallback branches.
  - Billing recovery has its own no-hardware charge path, while connectivity and full-system branches additionally require hardware recovery before successful test charge.
  - Late-stage shared gates (`session_auth_state`, `vehicle_auth_state`, `retry_state`) are part of terminal resolution rather than ad hoc optional cleanup.
  - `sampling_request.yaml` declares only terminal end states; shorter tasks come from easier starts, not from partial repair goals.
  - New EV seeds should keep `diagnostics_state = idle`, `profile_state = not_ready`, `retry_state = not_ready`, and `charge_state = inactive` unless the scenario is explicitly modeling an externally-caused later entrypoint.
  - Preflight and validate-domain must include policy/contract alignment.

- Out of scope for future EV edits:
  - prompt-only gating that is not enforced in tool/runtime logic
  - hidden sync-only display logic outside `graph_contract.yaml` sync rules and `check_station_screen`
  - using `ACTION` reward as the sole correctness signal for volatile-binding tasks

- Rollback criteria:
  - If preflight, compile, or `validate_domain` fails, fix contract/runtime/policy drift before sampling or simulation.
  - If a volatile screen code is required beyond the immediate observation stage, move that gate into stable world state or split the stage explicitly.
