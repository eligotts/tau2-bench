# Depgraph Review Bundle: `ev_charging_support`

Use this bundle with `docs/prompts/depgraph/05-gap-review.md` in authoring-audit mode.

## Reviewer Input Files
- `domain_scope`: `data/tau2/domains/ev_charging_support/domain_scope.md`
- `graph_contract`: `data/tau2/domains/ev_charging_support/graph_contract.yaml`
- `policy`: `data/tau2/domains/ev_charging_support/policy.md`
- `runtime_defaults`: `data/tau2/domains/ev_charging_support/runtime_defaults.yaml`
- `sampling_request`: `data/tau2/domains/ev_charging_support/sampling_request.yaml`
- `stop_gate_map`: `data/tau2/domains/ev_charging_support/stop_gate_map.yaml`
- `task_specs`: `data/tau2/domains/ev_charging_support/task_specs.runtime.yaml`
- `task_specs_sampled`: `data/tau2/domains/ev_charging_support/task_specs.sampled.yaml`
- `task_context_bindings`: `data/tau2/domains/ev_charging_support/task_context_bindings.yaml`
- `task_narrative_briefs`: `data/tau2/domains/ev_charging_support/task_narrative_briefs.yaml`
- `tasks_compiled`: `data/tau2/domains/ev_charging_support/tasks.depgraph.json`
- `tools_py`: `src/tau2/domains/ev_charging_support/tools.py`
- `user_tools_py`: `src/tau2/domains/ev_charging_support/user_tools.py`
- `environment_py`: `src/tau2/domains/ev_charging_support/environment.py`

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

- projection fields: 33
- bindings: 2
- sync rules: 25
- assistant actions: 11
- user actions: 10
- terminal profiles in sampling_request: ['billing_resolved', 'connectivity_resolved', 'full_system_resolved']

### Bindings
- `screen_fault_code` via `check_station_screen` (world_path=agent.sessions[active_session].last_fault_code, volatile=True, consumers=['assistant_run_backend_diagnostics[generic]', "assistant_reprovision_billing['PROFILE-201']", "assistant_reprovision_connectivity['PROFILE-201']", "assistant_reprovision_full_system['PROFILE-201']", "assistant_reset_retry_path['RETRY-301']"])
- `app_error_class` via `check_app_status` (world_path=agent.sessions[active_session].error_class, volatile=False, consumers=['assistant_run_backend_diagnostics[generic]'])

### Volatile Binding Focus
- `screen_fault_code` changes with `agent.sessions[active_session].last_fault_code` and is consumed by ['assistant_run_backend_diagnostics', 'assistant_reprovision_billing', 'assistant_reprovision_connectivity', 'assistant_reprovision_full_system', 'assistant_reset_retry_path']

## Task Set Snapshot

- tasks: 12
- families: 12
- tasks with `start_bindings`: 1
- tasks with `goal_bindings`: 12
- task counts by `terminal_profile_id`: {'billing_resolved': 7, 'connectivity_resolved': 4, 'full_system_resolved': 1}
- `min_plan_length` stats: min=7, avg=12.42, max=19
- `required_actions` stats: min=6, avg=10.58, max=17

### Family Counts
- `billing_fraud_only`: 1
- `billing_full`: 1
- `billing_hold_and_fraud`: 1
- `billing_hold_only`: 1
- `billing_partial_knowledge`: 1
- `billing_payment_only`: 1
- `billing_ready_to_reprovision`: 1
- `connectivity_cert_only`: 1
- `connectivity_full`: 1
- `connectivity_link_only`: 1
- `connectivity_physical_partial`: 1
- `full_system`: 1

### Hardest Tasks
- `full_system_d19_028`: min_plan_length=19, required_actions=17
- `connectivity_full_d15_024`: min_plan_length=15, required_actions=13
- `connectivity_cert_only_d14_026`: min_plan_length=14, required_actions=12
- `connectivity_link_only_d14_025`: min_plan_length=14, required_actions=12
- `billing_full_d13_000`: min_plan_length=13, required_actions=11

## Representative Tasks By Family

These tasks include SAT plans so the reviewer can compare what the policy teaches against what the solver/runtime actually requires.

### `billing_fraud_only`
#### `billing_fraud_only_d11_010`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (9): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_release_fraud_lock', 'assistant_reprovision_billing', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_release_fraud_lock -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_full`
#### `billing_full_d13_000`
- `min_plan_length`: 13
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (11): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_reprovision_billing', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 12
- `SAT_full`: True
- `SAT_full plan` (13): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_fraud`
#### `billing_hold_and_fraud_d12_013`
- `min_plan_length`: 12
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (10): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_reprovision_billing', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 11
- `SAT_full`: True
- `SAT_full plan` (12): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_only`
#### `billing_hold_only_d11_004`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (9): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_reprovision_billing', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_partial_knowledge`
#### `billing_partial_knowledge_d11_020`
- `min_plan_length`: 11
- `start_bindings`: ['screen_fault_code']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (10): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_payment_only`
#### `billing_payment_only_d11_007`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (9): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_reprovision_billing', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_ready_to_reprovision`
#### `billing_ready_to_reprovision_d7_016`
- `min_plan_length`: 7
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (6): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'assistant_run_backend_diagnostics', 'assistant_reprovision_billing', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 6
- `SAT_full`: True
- `SAT_full plan` (7): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> assistant_run_backend_diagnostics -> assistant_reprovision_billing -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_cert_only`
#### `connectivity_cert_only_d14_026`
- `min_plan_length`: 14
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (12): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_reprovision_connectivity', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_full`
#### `connectivity_full_d15_024`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_rotate_station_certificate', 'assistant_reprovision_connectivity', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_rotate_station_certificate -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_link_only`
#### `connectivity_link_only_d14_025`
- `min_plan_length`: 14
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (12): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reprovision_connectivity', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_physical_partial`
#### `connectivity_physical_partial_d11_027`
- `min_plan_length`: 11
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (9): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_power_cycle_station', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_rotate_station_certificate', 'assistant_reprovision_connectivity', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 10
- `SAT_full`: True
- `SAT_full plan` (11): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_power_cycle_station -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_rotate_station_certificate -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system`
#### `full_system_d19_028`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_restore_backend_link', 'assistant_rotate_station_certificate', 'assistant_update_station_firmware', 'assistant_reprovision_full_system', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_restore_backend_link -> assistant_rotate_station_certificate -> assistant_update_station_firmware -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

## Reviewer Notes

- `required_actions` is deduped and may not show repeated reacquisition.
- Treat repeated steps in `SAT_full plan` as the best clue for policy teaching gaps.
- Findings should cite exact files/lines, not just this bundle.
