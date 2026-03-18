# Depgraph Review Bundle: `daily_planner`

Use this bundle with `docs/prompts/depgraph/05-gap-review.md` in authoring-audit mode.

## Reviewer Input Files
- `domain_scope`: `data/tau2/domains/daily_planner/domain_scope.md`
- `graph_contract`: `data/tau2/domains/daily_planner/graph_contract.yaml`
- `policy`: `data/tau2/domains/daily_planner/policy.md`
- `runtime_defaults`: `data/tau2/domains/daily_planner/runtime_defaults.yaml`
- `sampling_request`: `data/tau2/domains/daily_planner/sampling_request.yaml`
- `stop_gate_map`: `data/tau2/domains/daily_planner/stop_gate_map.yaml`
- `task_specs`: `data/tau2/domains/daily_planner/task_specs.runtime.yaml`
- `task_specs_sampled`: `data/tau2/domains/daily_planner/task_specs.sampled.yaml`
- `task_context_bindings`: `data/tau2/domains/daily_planner/task_context_bindings.yaml`
- `task_narrative_briefs`: `data/tau2/domains/daily_planner/task_narrative_briefs.yaml`
- `tasks_compiled`: `data/tau2/domains/daily_planner/tasks.depgraph.json`
- `tools_py`: `src/tau2/domains/daily_planner/tools.py`
- `user_tools_py`: `src/tau2/domains/daily_planner/user_tools.py`
- `environment_py`: `src/tau2/domains/daily_planner/environment.py`

## Review Rubric Targets

- policy/contract parity
- volatile-binding discipline
- sync-rule/runtime fidelity
- branch-specific consistency
- terminal end-state discipline
- stop-gate clarity
- reward/eval fit
- task realism and teachability from policy alone

## Contract Snapshot

- projection fields: 61
- bindings: 12
- sync rules: 10
- assistant actions: 61
- user actions: 11
- terminal profiles in sampling_request: ['errands_done', 'rescheduled_paid', 'rescheduled_deferred', 'cancelled_paid', 'cancelled_deferred', 'care_done', 'household_done', 'errands_care_done', 'rescheduled_care_household', 'cancelled_care_household']

### Bindings
- `calendar_state` via `check_calendar` (world_path=agent.calendar.conflict_status, volatile=True, consumers=['none'])
- `transport_situation` via `check_car_status` (world_path=agent.transport.car_issue, volatile=False, consumers=['none'])
- `transport_options` via `check_transport_options` (world_path=agent.transport.rideshare_result, volatile=True, consumers=['none'])
- `account_balances` via `check_account_balances` (world_path=agent.finance.sufficient_funds, volatile=True, consumers=['none'])
- `budget_status` via `check_budget` (world_path=agent.finance.available_funds, volatile=True, consumers=['none'])
- `errand_a_options` via `check_errand_status` (world_path=agent.errand_a.delivery_available, volatile=False, consumers=['none'])
- `errand_b_options` via `check_errand_status` (world_path=agent.errand_b.delivery_available, volatile=False, consumers=['none'])
- `delegate_a_response` via `check_messages` (world_path=agent.dependent_care.delegate_a_availability, volatile=True, consumers=['none'])
- `delegate_b_response` via `check_messages` (world_path=agent.dependent_care.delegate_b_availability, volatile=True, consumers=['none'])
- `delegate_eta` via `check_delegate_eta` (world_path=none, volatile=False, consumers=['none'])
- `maintenance_info` via `check_maintenance_status` (world_path=agent.household.maintenance_status, volatile=True, consumers=['none'])
- `maintenance_quotes` via `check_maintenance_quotes` (world_path=agent.household.quote_count, volatile=True, consumers=['none'])

### Volatile Binding Focus
- `calendar_state` changes with `agent.calendar.conflict_status` and is consumed by ['no tool args']
- `transport_options` changes with `agent.transport.rideshare_result` and is consumed by ['no tool args']
- `account_balances` changes with `agent.finance.sufficient_funds` and is consumed by ['no tool args']
- `budget_status` changes with `agent.finance.available_funds` and is consumed by ['no tool args']
- `delegate_a_response` changes with `agent.dependent_care.delegate_a_availability` and is consumed by ['no tool args']
- `delegate_b_response` changes with `agent.dependent_care.delegate_b_availability` and is consumed by ['no tool args']
- `maintenance_info` changes with `agent.household.maintenance_status` and is consumed by ['no tool args']
- `maintenance_quotes` changes with `agent.household.quote_count` and is consumed by ['no tool args']

## Task Set Snapshot

- tasks: 547
- families: 67
- tasks with `start_bindings`: 199
- tasks with `goal_bindings`: 346
- task counts by `terminal_profile_id`: {'cancelled_care_household': 80, 'cancelled_deferred': 16, 'cancelled_paid': 18, 'care_done': 134, 'errands_care_done': 74, 'errands_done': 103, 'household_done': 32, 'rescheduled_care_household': 79, 'rescheduled_deferred': 5, 'rescheduled_paid': 6}
- `min_plan_length` stats: min=3, avg=11.27, max=20
- `required_actions` stats: min=3, avg=11.23, max=20

### Family Counts
- `cc_has_funds_plenty_both_known`: 1
- `cc_has_funds_plenty_budget_known`: 2
- `cc_has_funds_plenty_calendar_known`: 1
- `cc_has_funds_plenty_cold`: 2
- `cc_has_funds_tight_both_known`: 1
- `cc_has_funds_tight_budget_known`: 2
- `cc_has_funds_tight_calendar_known`: 1
- `cc_has_funds_tight_cold`: 2
- `cc_no_funds_defer_both_known`: 1
- `cc_no_funds_defer_budget_known`: 2
- `cc_no_funds_defer_calendar_known`: 1
- `cc_no_funds_defer_cold`: 2
- `cch2_delegate_a_ok_plenty_cold`: 56
- `cch2_delegate_a_ok_plenty_partial`: 24
- `cch_delegate_a_ok_plenty_cold`: 56
- `cch_delegate_a_ok_plenty_partial`: 23
- `cfd_budget_known`: 4
- `cfd_calendar_known`: 3
- `cfd_cold`: 4
- `cfp_has_funds_plenty_balances_known`: 1
- `cfp_has_funds_plenty_calendar_known`: 1
- `cfp_has_funds_plenty_cold`: 2
- `cfp_has_funds_tight_balances_known`: 1
- `cfp_has_funds_tight_calendar_known`: 1
- `cfp_has_funds_tight_cold`: 2
- `cfp_needs_transfer_balances_known`: 2
- `cfp_needs_transfer_both_known`: 2
- `cfp_needs_transfer_calendar_known`: 2
- `cfp_needs_transfer_cold`: 2
- `dc_delegate_a_accepts_available_cold`: 4
- `dc_delegate_a_accepts_broken_flat_cold`: 27
- `dc_delegate_a_fails_b_accepts_available_cold`: 7
- `dc_delegate_a_fails_b_accepts_broken_flat_cold`: 18
- `df_available_a_fails_b_pickup_cold`: 1
- `df_available_a_fails_b_pickup_errand_known`: 1
- `df_available_both_fail_cold`: 1
- `df_available_both_fail_errand_known`: 1
- `df_flat_tire_rs_ok_a_fails_b_pickup_cold`: 5
- `df_flat_tire_rs_ok_a_fails_b_pickup_errand_known`: 5
- `df_flat_tire_rs_ok_both_fail_cold`: 4
- `df_flat_tire_rs_ok_both_fail_errand_known`: 5
- `dfc_delegate_a_ok_rs_fail_cold`: 20
- `dfc_delegate_a_ok_rs_fail_transport_known`: 19
- `dfc_delegate_b_ok_rs_fail_cold`: 32
- `dfc_delegate_b_ok_rs_fail_transport_known`: 7
- `ec_flat_tire_rs_ok_delegate_a_ok_succeed_plenty_cold`: 34
- `ec_flat_tire_rs_ok_delegate_a_ok_succeed_plenty_partial`: 31
- `ec_flat_tire_rs_ok_delegate_a_ok_succeed_tight_cold`: 9
- `hh_plenty_funds_cold`: 8
- `hh_plenty_funds_maintenance_known`: 8
- `hh_tight_funds_cold`: 8
- `hh_tight_funds_maintenance_known`: 8
- `te_flat_tire_rs_ok_a_deliver_b_pickup_a_delivery_fails_cold`: 5
- `te_flat_tire_rs_ok_a_deliver_b_pickup_a_delivery_fails_transport_known`: 5
- `te_flat_tire_rs_ok_a_deliver_b_pickup_all_succeed_cold`: 5
- `te_flat_tire_rs_ok_a_deliver_b_pickup_all_succeed_transport_known`: 5
- `te_flat_tire_rs_ok_a_deliver_b_pickup_tight_budget_cold`: 5
- `te_flat_tire_rs_ok_a_deliver_b_pickup_tight_budget_transport_known`: 5
- `te_flat_tire_rs_ok_both_deliver_a_delivery_fails_cold`: 5
- `te_flat_tire_rs_ok_both_deliver_a_delivery_fails_transport_known`: 5
- `te_flat_tire_rs_ok_both_deliver_all_succeed_cold`: 8
- `te_flat_tire_rs_ok_both_deliver_all_succeed_transport_known`: 8
- `te_flat_tire_rs_ok_both_pickup_a_delivery_fails_cold`: 5
- `te_flat_tire_rs_ok_both_pickup_a_delivery_fails_transport_known`: 5
- `te_flat_tire_rs_ok_both_pickup_all_succeed_cold`: 5
- `te_flat_tire_rs_ok_both_pickup_all_succeed_transport_known`: 5
- `te_flat_tire_rs_ok_both_pickup_tight_budget_cold`: 4

### Hardest Tasks
- `cch2_delegate_a_ok_plenty_cold_d20_1275`: min_plan_length=20, required_actions=20
- `cch2_delegate_a_ok_plenty_cold_d19_1272`: min_plan_length=19, required_actions=19
- `cch2_delegate_a_ok_plenty_cold_d19_1273`: min_plan_length=19, required_actions=19
- `cch2_delegate_a_ok_plenty_cold_d19_1274`: min_plan_length=19, required_actions=19
- `cch_delegate_a_ok_plenty_cold_d19_724`: min_plan_length=19, required_actions=19

## Representative Tasks By Family

These tasks include SAT plans so the reviewer can compare what the policy teaches against what the solver/runtime actually requires.

### `cc_has_funds_plenty_both_known`
#### `cc_has_funds_plenty_both_known_d4_963`
- `min_plan_length`: 4
- `start_bindings`: ['calendar_state', 'budget_status']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (4): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_plenty']
- `required_precedence` count: 3
- `SAT_full`: True
- `SAT_full plan` (4): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_plenty

### `cc_has_funds_plenty_budget_known`
#### `cc_has_funds_plenty_budget_known_d5_962`
- `min_plan_length`: 5
- `start_bindings`: ['budget_status']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (5): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_plenty']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_plenty

### `cc_has_funds_plenty_calendar_known`
#### `cc_has_funds_plenty_calendar_known_d4_959`
- `min_plan_length`: 4
- `start_bindings`: ['calendar_state']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (4): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_plenty']
- `required_precedence` count: 3
- `SAT_full`: True
- `SAT_full plan` (4): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_plenty

### `cc_has_funds_plenty_cold`
#### `cc_has_funds_plenty_cold_d5_958`
- `min_plan_length`: 5
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (5): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_plenty']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_plenty

### `cc_has_funds_tight_both_known`
#### `cc_has_funds_tight_both_known_d4_971`
- `min_plan_length`: 4
- `start_bindings`: ['calendar_state', 'budget_status']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (4): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_tight']
- `required_precedence` count: 3
- `SAT_full`: True
- `SAT_full plan` (4): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_tight

### `cc_has_funds_tight_budget_known`
#### `cc_has_funds_tight_budget_known_d5_970`
- `min_plan_length`: 5
- `start_bindings`: ['budget_status']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (5): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_tight']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_tight

### `cc_has_funds_tight_calendar_known`
#### `cc_has_funds_tight_calendar_known_d4_967`
- `min_plan_length`: 4
- `start_bindings`: ['calendar_state']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (4): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_tight']
- `required_precedence` count: 3
- `SAT_full`: True
- `SAT_full plan` (4): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_tight

### `cc_has_funds_tight_cold`
#### `cc_has_funds_tight_cold_d5_966`
- `min_plan_length`: 5
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (5): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_tight']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_tight

### `cc_no_funds_defer_both_known`
#### `cc_no_funds_defer_both_known_d5_980`
- `min_plan_length`: 5
- `start_bindings`: ['calendar_state', 'budget_status']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_deferred'
- `required_actions` (5): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'defer_bill']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> defer_bill

### `cc_no_funds_defer_budget_known`
#### `cc_no_funds_defer_budget_known_d6_978`
- `min_plan_length`: 6
- `start_bindings`: ['budget_status']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_deferred'
- `required_actions` (6): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'defer_bill']
- `required_precedence` count: 5
- `SAT_full`: True
- `SAT_full plan` (6): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> defer_bill

### `cc_no_funds_defer_calendar_known`
#### `cc_no_funds_defer_calendar_known_d5_976`
- `min_plan_length`: 5
- `start_bindings`: ['calendar_state']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_deferred'
- `required_actions` (5): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'defer_bill']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> defer_bill

### `cc_no_funds_defer_cold`
#### `cc_no_funds_defer_cold_d6_974`
- `min_plan_length`: 6
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_deferred'
- `required_actions` (6): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'defer_bill']
- `required_precedence` count: 5
- `SAT_full`: True
- `SAT_full plan` (6): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> defer_bill

### `cch2_delegate_a_ok_plenty_cold`
#### `cch2_delegate_a_ok_plenty_cold_d20_1275`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta']
- `terminal_profile_id`: 'cancelled_care_household'
- `required_actions` (20): ['acquire_calendar_state', 'acquire_budget_status', 'acquire_maintenance_info', 'cancel_flexible_meeting', 'send_apology_message', 'contact_delegate_a_success', 'acquire_delegate_a_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_a_pickup', 'user_confirm_delegate_pickup', 'request_maintenance_quotes', 'acquire_maintenance_quotes', 'select_maintenance_provider', 'schedule_maintenance', 'pay_maintenance_cost_plenty', 'arrange_building_access', 'schedule_post_repair_inspection', 'user_confirm_technician_arrived', 'user_verify_repair']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_calendar_state -> acquire_budget_status -> acquire_maintenance_info -> cancel_flexible_meeting -> send_apology_message -> contact_delegate_a_success -> acquire_delegate_a_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_a_pickup -> user_confirm_delegate_pickup -> request_maintenance_quotes -> acquire_maintenance_quotes -> select_maintenance_provider -> schedule_maintenance -> pay_maintenance_cost_plenty -> arrange_building_access -> schedule_post_repair_inspection -> user_confirm_technician_arrived -> user_verify_repair

### `cch2_delegate_a_ok_plenty_partial`
#### `cch2_delegate_a_ok_plenty_partial_d13_1289`
- `min_plan_length`: 13
- `start_bindings`: ['calendar_state', 'maintenance_info']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_care_household'
- `required_actions` (13): ['acquire_budget_status', 'cancel_flexible_meeting', 'send_apology_message', 'assign_user_pickup', 'contact_delegate_a_success', 'user_confirm_dependent_picked_up', 'request_maintenance_quotes', 'acquire_maintenance_quotes', 'select_maintenance_provider', 'schedule_maintenance', 'pay_maintenance_cost_plenty', 'user_confirm_technician_arrived', 'user_verify_repair']
- `required_precedence` count: 12
- `SAT_full`: True
- `SAT_full plan` (13): acquire_budget_status -> cancel_flexible_meeting -> send_apology_message -> assign_user_pickup -> contact_delegate_a_success -> user_confirm_dependent_picked_up -> request_maintenance_quotes -> acquire_maintenance_quotes -> select_maintenance_provider -> schedule_maintenance -> pay_maintenance_cost_plenty -> user_confirm_technician_arrived -> user_verify_repair

### `cch_delegate_a_ok_plenty_cold`
#### `cch_delegate_a_ok_plenty_cold_d19_724`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta']
- `terminal_profile_id`: 'rescheduled_care_household'
- `required_actions` (19): ['acquire_calendar_state', 'acquire_budget_status', 'acquire_maintenance_info', 'reschedule_meeting', 'contact_delegate_a_success', 'acquire_delegate_a_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_a_pickup', 'user_confirm_delegate_pickup', 'request_maintenance_quotes', 'acquire_maintenance_quotes', 'select_maintenance_provider', 'schedule_maintenance', 'pay_maintenance_cost_plenty', 'arrange_building_access', 'schedule_post_repair_inspection', 'user_confirm_technician_arrived', 'user_verify_repair']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_calendar_state -> acquire_budget_status -> acquire_maintenance_info -> reschedule_meeting -> contact_delegate_a_success -> acquire_delegate_a_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_a_pickup -> user_confirm_delegate_pickup -> request_maintenance_quotes -> acquire_maintenance_quotes -> select_maintenance_provider -> schedule_maintenance -> pay_maintenance_cost_plenty -> arrange_building_access -> schedule_post_repair_inspection -> user_confirm_technician_arrived -> user_verify_repair

### `cch_delegate_a_ok_plenty_partial`
#### `cch_delegate_a_ok_plenty_partial_d12_738`
- `min_plan_length`: 12
- `start_bindings`: ['calendar_state', 'maintenance_info']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'rescheduled_care_household'
- `required_actions` (12): ['acquire_budget_status', 'reschedule_meeting', 'assign_user_pickup', 'contact_delegate_a_success', 'user_confirm_dependent_picked_up', 'request_maintenance_quotes', 'acquire_maintenance_quotes', 'select_maintenance_provider', 'schedule_maintenance', 'pay_maintenance_cost_plenty', 'user_confirm_technician_arrived', 'user_verify_repair']
- `required_precedence` count: 11
- `SAT_full`: True
- `SAT_full plan` (12): acquire_budget_status -> reschedule_meeting -> assign_user_pickup -> contact_delegate_a_success -> user_confirm_dependent_picked_up -> request_maintenance_quotes -> acquire_maintenance_quotes -> select_maintenance_provider -> schedule_maintenance -> pay_maintenance_cost_plenty -> user_confirm_technician_arrived -> user_verify_repair

### `cfd_budget_known`
#### `cfd_budget_known_d6_159`
- `min_plan_length`: 6
- `start_bindings`: ['budget_status']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_deferred'
- `required_actions` (6): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'defer_bill']
- `required_precedence` count: 5
- `SAT_full`: True
- `SAT_full plan` (6): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> defer_bill

### `cfd_calendar_known`
#### `cfd_calendar_known_d5_155`
- `min_plan_length`: 5
- `start_bindings`: ['calendar_state']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_deferred'
- `required_actions` (5): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'defer_bill']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> defer_bill

### `cfd_cold`
#### `cfd_cold_d6_151`
- `min_plan_length`: 6
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_deferred'
- `required_actions` (6): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'defer_bill']
- `required_precedence` count: 5
- `SAT_full`: True
- `SAT_full plan` (6): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> defer_bill

### `cfp_has_funds_plenty_balances_known`
#### `cfp_has_funds_plenty_balances_known_d4_131`
- `min_plan_length`: 4
- `start_bindings`: ['account_balances']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (4): ['acquire_calendar_state', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_plenty']
- `required_precedence` count: 3
- `SAT_full`: True
- `SAT_full plan` (4): acquire_calendar_state -> cancel_flexible_meeting -> send_apology_message -> pay_bill_plenty

### `cfp_has_funds_plenty_calendar_known`
#### `cfp_has_funds_plenty_calendar_known_d4_129`
- `min_plan_length`: 4
- `start_bindings`: ['calendar_state']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (4): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_plenty']
- `required_precedence` count: 3
- `SAT_full`: True
- `SAT_full plan` (4): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_plenty

### `cfp_has_funds_plenty_cold`
#### `cfp_has_funds_plenty_cold_d5_127`
- `min_plan_length`: 5
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (5): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_plenty']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_plenty

### `cfp_has_funds_tight_balances_known`
#### `cfp_has_funds_tight_balances_known_d4_138`
- `min_plan_length`: 4
- `start_bindings`: ['account_balances']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (4): ['acquire_calendar_state', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_tight']
- `required_precedence` count: 3
- `SAT_full`: True
- `SAT_full plan` (4): acquire_calendar_state -> cancel_flexible_meeting -> send_apology_message -> pay_bill_tight

### `cfp_has_funds_tight_calendar_known`
#### `cfp_has_funds_tight_calendar_known_d4_136`
- `min_plan_length`: 4
- `start_bindings`: ['calendar_state']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (4): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_tight']
- `required_precedence` count: 3
- `SAT_full`: True
- `SAT_full plan` (4): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_tight

### `cfp_has_funds_tight_cold`
#### `cfp_has_funds_tight_cold_d5_134`
- `min_plan_length`: 5
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (5): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'pay_bill_tight']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> pay_bill_tight

### `cfp_needs_transfer_balances_known`
#### `cfp_needs_transfer_balances_known_d6_145`
- `min_plan_length`: 6
- `start_bindings`: ['account_balances']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (6): ['acquire_calendar_state', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'acquire_account_balances', 'pay_bill_plenty']
- `required_precedence` count: 5
- `SAT_full`: True
- `SAT_full plan` (6): acquire_calendar_state -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> acquire_account_balances -> pay_bill_plenty

### `cfp_needs_transfer_both_known`
#### `cfp_needs_transfer_both_known_d5_147`
- `min_plan_length`: 5
- `start_bindings`: ['calendar_state', 'account_balances']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (5): ['cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'acquire_account_balances', 'pay_bill_plenty']
- `required_precedence` count: 4
- `SAT_full`: True
- `SAT_full plan` (5): cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> acquire_account_balances -> pay_bill_plenty

### `cfp_needs_transfer_calendar_known`
#### `cfp_needs_transfer_calendar_known_d6_143`
- `min_plan_length`: 6
- `start_bindings`: ['calendar_state']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (5): ['acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'pay_bill_plenty']
- `required_precedence` count: 5
- `SAT_full`: True
- `SAT_full plan` (6): acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> acquire_account_balances -> pay_bill_plenty
- repeated plan actions: acquire_account_balances x2

### `cfp_needs_transfer_cold`
#### `cfp_needs_transfer_cold_d7_141`
- `min_plan_length`: 7
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'cancelled_paid'
- `required_actions` (6): ['acquire_calendar_state', 'acquire_account_balances', 'cancel_flexible_meeting', 'send_apology_message', 'initiate_transfer', 'pay_bill_plenty']
- `required_precedence` count: 6
- `SAT_full`: True
- `SAT_full plan` (7): acquire_calendar_state -> acquire_account_balances -> cancel_flexible_meeting -> send_apology_message -> initiate_transfer -> acquire_account_balances -> pay_bill_plenty
- repeated plan actions: acquire_account_balances x2

### `dc_delegate_a_accepts_available_cold`
#### `dc_delegate_a_accepts_available_cold_d6_166`
- `min_plan_length`: 6
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta']
- `terminal_profile_id`: 'care_done'
- `required_actions` (6): ['contact_delegate_a_success', 'acquire_delegate_a_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_a_pickup', 'user_confirm_delegate_pickup']
- `required_precedence` count: 5
- `SAT_full`: True
- `SAT_full plan` (6): contact_delegate_a_success -> acquire_delegate_a_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_a_pickup -> user_confirm_delegate_pickup

### `dc_delegate_a_accepts_broken_flat_cold`
#### `dc_delegate_a_accepts_broken_flat_cold_d11_203`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta', 'transport_situation']
- `terminal_profile_id`: 'care_done'
- `required_actions` (11): ['acquire_transport_situation', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'contact_delegate_a_success', 'acquire_delegate_a_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_a_pickup', 'user_confirm_delegate_pickup']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_transport_situation -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> contact_delegate_a_success -> acquire_delegate_a_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_a_pickup -> user_confirm_delegate_pickup

### `dc_delegate_a_fails_b_accepts_available_cold`
#### `dc_delegate_a_fails_b_accepts_available_cold_d8_213`
- `min_plan_length`: 8
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta']
- `terminal_profile_id`: 'care_done'
- `required_actions` (8): ['contact_delegate_a_fail', 'acquire_delegate_a_response', 'contact_delegate_b_success', 'acquire_delegate_b_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_b_pickup', 'user_confirm_delegate_pickup']
- `required_precedence` count: 7
- `SAT_full`: True
- `SAT_full plan` (8): contact_delegate_a_fail -> acquire_delegate_a_response -> contact_delegate_b_success -> acquire_delegate_b_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_b_pickup -> user_confirm_delegate_pickup

### `dc_delegate_a_fails_b_accepts_broken_flat_cold`
#### `dc_delegate_a_fails_b_accepts_broken_flat_cold_d9_238`
- `min_plan_length`: 9
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['transport_situation']
- `terminal_profile_id`: 'care_done'
- `required_actions` (9): ['acquire_transport_situation', 'schedule_roadside_assistance', 'user_check_repair_status', 'user_confirm_car_fixed', 'assign_user_pickup', 'contact_delegate_a_fail', 'acquire_delegate_a_response', 'contact_delegate_b_success', 'user_confirm_dependent_picked_up']
- `required_precedence` count: 8
- `SAT_full`: True
- `SAT_full plan` (9): acquire_transport_situation -> schedule_roadside_assistance -> user_check_repair_status -> user_confirm_car_fixed -> assign_user_pickup -> contact_delegate_a_fail -> acquire_delegate_a_response -> contact_delegate_b_success -> user_confirm_dependent_picked_up

### `df_available_a_fails_b_pickup_cold`
#### `df_available_a_fails_b_pickup_cold_d12_981`
- `min_plan_length`: 12
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (12): ['acquire_errand_a_options', 'acquire_errand_b_options', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 11
- `SAT_full`: True
- `SAT_full plan` (12): acquire_errand_a_options -> acquire_errand_b_options -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `df_available_a_fails_b_pickup_errand_known`
#### `df_available_a_fails_b_pickup_errand_known_d11_982`
- `min_plan_length`: 11
- `start_bindings`: ['errand_a_options']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (11): ['acquire_errand_b_options', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_errand_b_options -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `df_available_both_fail_cold`
#### `df_available_both_fail_cold_d14_983`
- `min_plan_length`: 14
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (14): ['acquire_errand_a_options', 'acquire_errand_b_options', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_delivery_fail', 'recover_errand_b_to_pickup', 'arrange_errand_b_pickup_after_fail', 'user_confirm_errand_b_complete']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_errand_a_options -> acquire_errand_b_options -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_delivery_fail -> recover_errand_b_to_pickup -> arrange_errand_b_pickup_after_fail -> user_confirm_errand_b_complete

### `df_available_both_fail_errand_known`
#### `df_available_both_fail_errand_known_d13_984`
- `min_plan_length`: 13
- `start_bindings`: ['errand_a_options']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (13): ['acquire_errand_b_options', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_delivery_fail', 'recover_errand_b_to_pickup', 'arrange_errand_b_pickup_after_fail', 'user_confirm_errand_b_complete']
- `required_precedence` count: 12
- `SAT_full`: True
- `SAT_full plan` (13): acquire_errand_b_options -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_delivery_fail -> recover_errand_b_to_pickup -> arrange_errand_b_pickup_after_fail -> user_confirm_errand_b_complete

### `df_flat_tire_rs_ok_a_fails_b_pickup_cold`
#### `df_flat_tire_rs_ok_a_fails_b_pickup_cold_d17_989`
- `min_plan_length`: 17
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (17): ['acquire_transport_situation', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_transport_situation -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `df_flat_tire_rs_ok_a_fails_b_pickup_errand_known`
#### `df_flat_tire_rs_ok_a_fails_b_pickup_errand_known_d16_994`
- `min_plan_length`: 16
- `start_bindings`: ['errand_a_options']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (16): ['acquire_transport_situation', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_transport_situation -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `df_flat_tire_rs_ok_both_fail_cold`
#### `df_flat_tire_rs_ok_both_fail_cold_d18_997`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (18): ['acquire_transport_situation', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_delivery_fail', 'recover_errand_b_to_pickup', 'arrange_errand_b_pickup_after_fail', 'user_confirm_errand_b_complete']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_transport_situation -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_delivery_fail -> recover_errand_b_to_pickup -> arrange_errand_b_pickup_after_fail -> user_confirm_errand_b_complete

### `df_flat_tire_rs_ok_both_fail_errand_known`
#### `df_flat_tire_rs_ok_both_fail_errand_known_d18_1003`
- `min_plan_length`: 18
- `start_bindings`: ['errand_a_options']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (18): ['acquire_transport_situation', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_delivery_fail', 'recover_errand_b_to_pickup', 'arrange_errand_b_pickup_after_fail', 'user_confirm_errand_b_complete']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_transport_situation -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_delivery_fail -> recover_errand_b_to_pickup -> arrange_errand_b_pickup_after_fail -> user_confirm_errand_b_complete

### `dfc_delegate_a_ok_rs_fail_cold`
#### `dfc_delegate_a_ok_rs_fail_cold_d11_1023`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta', 'transport_situation']
- `terminal_profile_id`: 'care_done'
- `required_actions` (11): ['acquire_transport_situation', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_fail', 'user_confirm_car_fixed', 'contact_delegate_a_success', 'acquire_delegate_a_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_a_pickup', 'user_confirm_delegate_pickup']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_transport_situation -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_fail -> user_confirm_car_fixed -> contact_delegate_a_success -> acquire_delegate_a_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_a_pickup -> user_confirm_delegate_pickup

### `dfc_delegate_a_ok_rs_fail_transport_known`
#### `dfc_delegate_a_ok_rs_fail_transport_known_d10_1043`
- `min_plan_length`: 10
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta']
- `terminal_profile_id`: 'care_done'
- `required_actions` (10): ['schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_fail', 'user_confirm_car_fixed', 'contact_delegate_a_success', 'acquire_delegate_a_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_a_pickup', 'user_confirm_delegate_pickup']
- `required_precedence` count: 9
- `SAT_full`: True
- `SAT_full plan` (10): schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_fail -> user_confirm_car_fixed -> contact_delegate_a_success -> acquire_delegate_a_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_a_pickup -> user_confirm_delegate_pickup

### `dfc_delegate_b_ok_rs_fail_cold`
#### `dfc_delegate_b_ok_rs_fail_cold_d13_1075`
- `min_plan_length`: 13
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta', 'transport_situation']
- `terminal_profile_id`: 'care_done'
- `required_actions` (13): ['acquire_transport_situation', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_fail', 'user_confirm_car_fixed', 'contact_delegate_a_fail', 'acquire_delegate_a_response', 'contact_delegate_b_success', 'acquire_delegate_b_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_b_pickup', 'user_confirm_delegate_pickup']
- `required_precedence` count: 12
- `SAT_full`: True
- `SAT_full plan` (13): acquire_transport_situation -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_fail -> user_confirm_car_fixed -> contact_delegate_a_fail -> acquire_delegate_a_response -> contact_delegate_b_success -> acquire_delegate_b_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_b_pickup -> user_confirm_delegate_pickup

### `dfc_delegate_b_ok_rs_fail_transport_known`
#### `dfc_delegate_b_ok_rs_fail_transport_known_d7_1080`
- `min_plan_length`: 7
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'care_done'
- `required_actions` (7): ['schedule_roadside_assistance', 'user_check_repair_status', 'user_confirm_car_fixed', 'assign_user_pickup', 'contact_delegate_a_fail', 'notify_facility', 'user_confirm_dependent_picked_up']
- `required_precedence` count: 6
- `SAT_full`: True
- `SAT_full plan` (7): schedule_roadside_assistance -> user_check_repair_status -> user_confirm_car_fixed -> assign_user_pickup -> contact_delegate_a_fail -> notify_facility -> user_confirm_dependent_picked_up

### `ec_flat_tire_rs_ok_delegate_a_ok_succeed_plenty_cold`
#### `ec_flat_tire_rs_ok_delegate_a_ok_succeed_plenty_cold_d16_487`
- `min_plan_length`: 16
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta', 'errand_a_options', 'transport_situation']
- `terminal_profile_id`: 'errands_care_done'
- `required_actions` (16): ['acquire_transport_situation', 'acquire_errand_a_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_pickup_no_delivery', 'user_confirm_errand_a_complete', 'contact_delegate_a_success', 'acquire_delegate_a_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_a_pickup', 'user_confirm_delegate_pickup']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_transport_situation -> acquire_errand_a_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_pickup_no_delivery -> user_confirm_errand_a_complete -> contact_delegate_a_success -> acquire_delegate_a_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_a_pickup -> user_confirm_delegate_pickup

### `ec_flat_tire_rs_ok_delegate_a_ok_succeed_plenty_partial`
#### `ec_flat_tire_rs_ok_delegate_a_ok_succeed_plenty_partial_d15_522`
- `min_plan_length`: 15
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['delegate_eta', 'errand_a_options']
- `terminal_profile_id`: 'errands_care_done'
- `required_actions` (15): ['acquire_errand_a_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_pickup_no_delivery', 'user_confirm_errand_a_complete', 'contact_delegate_a_success', 'acquire_delegate_a_response', 'acquire_delegate_eta', 'notify_facility', 'assign_delegate_a_pickup', 'user_confirm_delegate_pickup']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_errand_a_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_pickup_no_delivery -> user_confirm_errand_a_complete -> contact_delegate_a_success -> acquire_delegate_a_response -> acquire_delegate_eta -> notify_facility -> assign_delegate_a_pickup -> user_confirm_delegate_pickup

### `ec_flat_tire_rs_ok_delegate_a_ok_succeed_tight_cold`
#### `ec_flat_tire_rs_ok_delegate_a_ok_succeed_tight_cold_d11_527`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'transport_situation']
- `terminal_profile_id`: 'errands_care_done'
- `required_actions` (11): ['acquire_transport_situation', 'acquire_errand_a_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_pickup_no_delivery', 'user_confirm_errand_a_complete', 'assign_user_pickup', 'user_confirm_dependent_picked_up']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_transport_situation -> acquire_errand_a_options -> schedule_roadside_assistance -> user_check_repair_status -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_pickup_no_delivery -> user_confirm_errand_a_complete -> assign_user_pickup -> user_confirm_dependent_picked_up

### `hh_plenty_funds_cold`
#### `hh_plenty_funds_cold_d11_428`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'household_done'
- `required_actions` (11): ['acquire_budget_status', 'acquire_maintenance_info', 'request_maintenance_quotes', 'acquire_maintenance_quotes', 'select_maintenance_provider', 'schedule_maintenance', 'pay_maintenance_cost_plenty', 'arrange_building_access', 'schedule_post_repair_inspection', 'user_confirm_technician_arrived', 'user_verify_repair']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_budget_status -> acquire_maintenance_info -> request_maintenance_quotes -> acquire_maintenance_quotes -> select_maintenance_provider -> schedule_maintenance -> pay_maintenance_cost_plenty -> arrange_building_access -> schedule_post_repair_inspection -> user_confirm_technician_arrived -> user_verify_repair

### `hh_plenty_funds_maintenance_known`
#### `hh_plenty_funds_maintenance_known_d10_436`
- `min_plan_length`: 10
- `start_bindings`: ['maintenance_info']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'household_done'
- `required_actions` (10): ['acquire_budget_status', 'request_maintenance_quotes', 'acquire_maintenance_quotes', 'select_maintenance_provider', 'schedule_maintenance', 'pay_maintenance_cost_plenty', 'arrange_building_access', 'schedule_post_repair_inspection', 'user_confirm_technician_arrived', 'user_verify_repair']
- `required_precedence` count: 9
- `SAT_full`: True
- `SAT_full plan` (10): acquire_budget_status -> request_maintenance_quotes -> acquire_maintenance_quotes -> select_maintenance_provider -> schedule_maintenance -> pay_maintenance_cost_plenty -> arrange_building_access -> schedule_post_repair_inspection -> user_confirm_technician_arrived -> user_verify_repair

### `hh_tight_funds_cold`
#### `hh_tight_funds_cold_d11_444`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'household_done'
- `required_actions` (11): ['acquire_budget_status', 'acquire_maintenance_info', 'request_maintenance_quotes', 'acquire_maintenance_quotes', 'select_maintenance_provider', 'schedule_maintenance', 'pay_maintenance_cost_tight', 'arrange_building_access', 'schedule_post_repair_inspection', 'user_confirm_technician_arrived', 'user_verify_repair']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_budget_status -> acquire_maintenance_info -> request_maintenance_quotes -> acquire_maintenance_quotes -> select_maintenance_provider -> schedule_maintenance -> pay_maintenance_cost_tight -> arrange_building_access -> schedule_post_repair_inspection -> user_confirm_technician_arrived -> user_verify_repair

### `hh_tight_funds_maintenance_known`
#### `hh_tight_funds_maintenance_known_d10_452`
- `min_plan_length`: 10
- `start_bindings`: ['maintenance_info']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: []
- `terminal_profile_id`: 'household_done'
- `required_actions` (10): ['acquire_budget_status', 'request_maintenance_quotes', 'acquire_maintenance_quotes', 'select_maintenance_provider', 'schedule_maintenance', 'pay_maintenance_cost_tight', 'arrange_building_access', 'schedule_post_repair_inspection', 'user_confirm_technician_arrived', 'user_verify_repair']
- `required_precedence` count: 9
- `SAT_full`: True
- `SAT_full plan` (10): acquire_budget_status -> request_maintenance_quotes -> acquire_maintenance_quotes -> select_maintenance_provider -> schedule_maintenance -> pay_maintenance_cost_tight -> arrange_building_access -> schedule_post_repair_inspection -> user_confirm_technician_arrived -> user_verify_repair

### `te_flat_tire_rs_ok_a_deliver_b_pickup_a_delivery_fails_cold`
#### `te_flat_tire_rs_ok_a_deliver_b_pickup_a_delivery_fails_cold_d17_040`
- `min_plan_length`: 17
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (17): ['acquire_transport_situation', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_transport_situation -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_a_deliver_b_pickup_a_delivery_fails_transport_known`
#### `te_flat_tire_rs_ok_a_deliver_b_pickup_a_delivery_fails_transport_known_d16_045`
- `min_plan_length`: 16
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (16): ['acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_a_deliver_b_pickup_all_succeed_cold`
#### `te_flat_tire_rs_ok_a_deliver_b_pickup_all_succeed_cold_d15_030`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (15): ['acquire_transport_situation', 'acquire_budget_status', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_success_plenty', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_transport_situation -> acquire_budget_status -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_success_plenty -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_a_deliver_b_pickup_all_succeed_transport_known`
#### `te_flat_tire_rs_ok_a_deliver_b_pickup_all_succeed_transport_known_d14_035`
- `min_plan_length`: 14
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (14): ['acquire_budget_status', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_success_plenty', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_budget_status -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_success_plenty -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_a_deliver_b_pickup_tight_budget_cold`
#### `te_flat_tire_rs_ok_a_deliver_b_pickup_tight_budget_cold_d15_050`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (15): ['acquire_transport_situation', 'acquire_budget_status', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_success_tight', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_transport_situation -> acquire_budget_status -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_success_tight -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_a_deliver_b_pickup_tight_budget_transport_known`
#### `te_flat_tire_rs_ok_a_deliver_b_pickup_tight_budget_transport_known_d14_055`
- `min_plan_length`: 14
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (14): ['acquire_budget_status', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_success_tight', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_budget_status -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_success_tight -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_both_deliver_a_delivery_fails_cold`
#### `te_flat_tire_rs_ok_both_deliver_a_delivery_fails_cold_d17_020`
- `min_plan_length`: 17
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (17): ['acquire_transport_situation', 'acquire_budget_status', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_delivery_success_plenty']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_transport_situation -> acquire_budget_status -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_delivery_success_plenty

### `te_flat_tire_rs_ok_both_deliver_a_delivery_fails_transport_known`
#### `te_flat_tire_rs_ok_both_deliver_a_delivery_fails_transport_known_d16_025`
- `min_plan_length`: 16
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (16): ['acquire_budget_status', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_fail', 'recover_errand_a_to_pickup', 'arrange_errand_a_pickup_after_fail', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_delivery_success_plenty']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_budget_status -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_fail -> recover_errand_a_to_pickup -> arrange_errand_a_pickup_after_fail -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_delivery_success_plenty

### `te_flat_tire_rs_ok_both_deliver_all_succeed_cold`
#### `te_flat_tire_rs_ok_both_deliver_all_succeed_cold_d15_007`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (14): ['acquire_transport_situation', 'acquire_budget_status', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_success_plenty', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_delivery_success_tight']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_transport_situation -> acquire_budget_status -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_success_plenty -> acquire_budget_status -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_delivery_success_tight
- repeated plan actions: acquire_budget_status x2

### `te_flat_tire_rs_ok_both_deliver_all_succeed_transport_known`
#### `te_flat_tire_rs_ok_both_deliver_all_succeed_transport_known_d14_015`
- `min_plan_length`: 14
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (13): ['acquire_budget_status', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_delivery_success_plenty', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_delivery_success_tight']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_budget_status -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_delivery_success_plenty -> acquire_budget_status -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_delivery_success_tight
- repeated plan actions: acquire_budget_status x2

### `te_flat_tire_rs_ok_both_pickup_a_delivery_fails_cold`
#### `te_flat_tire_rs_ok_both_pickup_a_delivery_fails_cold_d15_070`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (15): ['acquire_transport_situation', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_pickup_no_delivery', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_transport_situation -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_pickup_no_delivery -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_both_pickup_a_delivery_fails_transport_known`
#### `te_flat_tire_rs_ok_both_pickup_a_delivery_fails_transport_known_d14_075`
- `min_plan_length`: 14
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (14): ['acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_pickup_no_delivery', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_pickup_no_delivery -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_both_pickup_all_succeed_cold`
#### `te_flat_tire_rs_ok_both_pickup_all_succeed_cold_d15_060`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (15): ['acquire_transport_situation', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_pickup_no_delivery', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_transport_situation -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_pickup_no_delivery -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_both_pickup_all_succeed_transport_known`
#### `te_flat_tire_rs_ok_both_pickup_all_succeed_transport_known_d14_065`
- `min_plan_length`: 14
- `start_bindings`: ['transport_situation']
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (14): ['acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'book_rideshare_success', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_pickup_no_delivery', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> book_rideshare_success -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_pickup_no_delivery -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

### `te_flat_tire_rs_ok_both_pickup_tight_budget_cold`
#### `te_flat_tire_rs_ok_both_pickup_tight_budget_cold_d14_078`
- `min_plan_length`: 14
- `start_bindings`: []
- `goal_capture_paths`: ['agent.calendar', 'agent.transport', 'agent.errand_a.status', 'agent.errand_b.status', 'agent.finance', 'agent.dependent_care', 'agent.household', 'user.errand_a', 'user.errand_b', 'user.dependent_care', 'user.home', 'user.transport']
- `goal_bindings`: ['errand_a_options', 'errand_b_options', 'transport_situation']
- `terminal_profile_id`: 'errands_done'
- `required_actions` (14): ['acquire_transport_situation', 'acquire_errand_a_options', 'acquire_errand_b_options', 'schedule_roadside_assistance', 'user_check_repair_status', 'user_confirm_car_fixed', 'reserve_errand_a', 'confirm_errand_a_reservation', 'arrange_errand_a_pickup_no_delivery', 'user_confirm_errand_a_complete', 'reserve_errand_b', 'confirm_errand_b_reservation', 'arrange_errand_b_pickup_no_delivery', 'user_confirm_errand_b_complete']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_transport_situation -> acquire_errand_a_options -> acquire_errand_b_options -> schedule_roadside_assistance -> user_check_repair_status -> user_confirm_car_fixed -> reserve_errand_a -> confirm_errand_a_reservation -> arrange_errand_a_pickup_no_delivery -> user_confirm_errand_a_complete -> reserve_errand_b -> confirm_errand_b_reservation -> arrange_errand_b_pickup_no_delivery -> user_confirm_errand_b_complete

## Reviewer Notes

- `required_actions` is deduped and may not show repeated reacquisition.
- Treat repeated steps in `SAT_full plan` as the best clue for policy teaching gaps.
- Findings should cite exact files/lines, not just this bundle.
