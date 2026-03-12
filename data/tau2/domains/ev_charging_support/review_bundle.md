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

- projection fields: 46
- bindings: 2
- sync rules: 38
- assistant actions: 18
- user actions: 12
- terminal profiles in sampling_request: ['billing_resolved', 'connectivity_resolved', 'full_system_resolved']

### Bindings
- `screen_fault_code` via `check_station_screen` (world_path=agent.sessions[active_session].last_fault_code, volatile=True, consumers=['assistant_run_backend_diagnostics[generic]', "assistant_reset_retry_path['RETRY-301']", "assistant_clear_entitlement_blocker_allowlist_sync['ENT-210']", "assistant_clear_entitlement_blocker_tariff_profile['ENT-220']", "assistant_clear_entitlement_blocker_reservation_lock['ENT-230']", "assistant_reprovision_billing['PROFILE-201']", "assistant_reprovision_connectivity['PROFILE-201']", "assistant_reprovision_full_system['PROFILE-201']"])
- `app_error_class` via `check_app_status` (world_path=agent.sessions[active_session].error_class, volatile=False, consumers=['assistant_run_backend_diagnostics[generic]'])

### Volatile Binding Focus
- `screen_fault_code` changes with `agent.sessions[active_session].last_fault_code` and is consumed by ['assistant_run_backend_diagnostics', 'assistant_reset_retry_path', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_reprovision_billing', 'assistant_reprovision_connectivity', 'assistant_reprovision_full_system']

## Task Set Snapshot

- tasks: 72
- families: 32
- tasks with `start_bindings`: 6
- tasks with `goal_bindings`: 66
- task counts by `terminal_profile_id`: {'billing_resolved': 54, 'connectivity_resolved': 10, 'full_system_resolved': 8}
- `min_plan_length` stats: min=15, avg=17.86, max=25
- `required_actions` stats: min=13, avg=15.72, max=23

### Family Counts
- `billing_allowlist_only`: 4
- `billing_allowlist_reservation`: 4
- `billing_allowlist_tariff`: 4
- `billing_auth_stack_full`: 4
- `billing_fraud_and_auth`: 4
- `billing_hold_and_auth`: 4
- `billing_hold_and_fraud_auth`: 4
- `billing_hold_and_payment_auth`: 4
- `billing_partial_knowledge`: 4
- `billing_payment_and_auth`: 4
- `billing_payment_and_fraud_auth`: 4
- `billing_reservation_only`: 4
- `billing_tariff_only`: 4
- `billing_tariff_reservation`: 2
- `connectivity_cert_clock_auth`: 1
- `connectivity_cert_handshake_auth`: 1
- `connectivity_cert_only`: 1
- `connectivity_clock_handshake_auth`: 1
- `connectivity_clock_only`: 1
- `connectivity_handshake_only`: 1
- `connectivity_link_handshake_auth`: 1
- `connectivity_link_only`: 1
- `connectivity_partial_knowledge`: 1
- `connectivity_secure_transport_full`: 1
- `full_system_all_lanes`: 1
- `full_system_billing_firmware`: 1
- `full_system_billing_firmware_fraud`: 1
- `full_system_billing_transport`: 1
- `full_system_cert_clock_firmware`: 1
- `full_system_link_handshake_firmware`: 1
- `full_system_partial_knowledge`: 1
- `full_system_transport_firmware`: 1

### Hardest Tasks
- `full_system_all_lanes_d25_000`: min_plan_length=25, required_actions=23
- `full_system_billing_transport_d23_000`: min_plan_length=23, required_actions=21
- `full_system_transport_firmware_d22_000`: min_plan_length=22, required_actions=20
- `connectivity_secure_transport_full_d21_000`: min_plan_length=21, required_actions=19
- `full_system_partial_knowledge_d21_000`: min_plan_length=21, required_actions=19

## Representative Tasks By Family

These tasks include SAT plans so the reviewer can compare what the policy teaches against what the solver/runtime actually requires.

### `billing_allowlist_only`
#### `billing_allowlist_only_d18_003`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_allowlist_reservation`
#### `billing_allowlist_reservation_d20_003`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_allowlist_tariff`
#### `billing_allowlist_tariff_d20_003`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_auth_stack_full`
#### `billing_auth_stack_full_d20_003`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_fraud_and_auth`
#### `billing_fraud_and_auth_d18_003`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_auth`
#### `billing_hold_and_auth_d18_003`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_fraud_auth`
#### `billing_hold_and_fraud_auth_d19_003`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_payment_auth`
#### `billing_hold_and_payment_auth_d19_003`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_partial_knowledge`
#### `billing_partial_knowledge_d18_003`
- `min_plan_length`: 18
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_payment_and_auth`
#### `billing_payment_and_auth_d18_003`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_payment_and_fraud_auth`
#### `billing_payment_and_fraud_auth_d19_003`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_reservation_only`
#### `billing_reservation_only_d18_003`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_tariff_only`
#### `billing_tariff_only_d18_003`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_tariff_reservation`
#### `billing_tariff_reservation_d18_001`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `connectivity_cert_clock_auth`
#### `connectivity_cert_clock_auth_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_cert_handshake_auth`
#### `connectivity_cert_handshake_auth_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_cert_only`
#### `connectivity_cert_only_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_clock_handshake_auth`
#### `connectivity_clock_handshake_auth_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_clock_only`
#### `connectivity_clock_only_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_handshake_only`
#### `connectivity_handshake_only_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_link_handshake_auth`
#### `connectivity_link_handshake_auth_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_link_only`
#### `connectivity_link_only_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_partial_knowledge`
#### `connectivity_partial_knowledge_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_secure_transport_full`
#### `connectivity_secure_transport_full_d21_000`
- `min_plan_length`: 21
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (19): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 20
- `SAT_full`: True
- `SAT_full plan` (21): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_all_lanes`
#### `full_system_all_lanes_d25_000`
- `min_plan_length`: 25
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (23): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 24
- `SAT_full`: True
- `SAT_full plan` (25): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_firmware`
#### `full_system_billing_firmware_d20_000`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_firmware_fraud`
#### `full_system_billing_firmware_fraud_d20_000`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_transport`
#### `full_system_billing_transport_d23_000`
- `min_plan_length`: 23
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (21): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 22
- `SAT_full`: True
- `SAT_full plan` (23): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_cert_clock_firmware`
#### `full_system_cert_clock_firmware_d20_000`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_link_handshake_firmware`
#### `full_system_link_handshake_firmware_d20_000`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_partial_knowledge`
#### `full_system_partial_knowledge_d21_000`
- `min_plan_length`: 21
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (19): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 20
- `SAT_full`: True
- `SAT_full plan` (21): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_transport_firmware`
#### `full_system_transport_firmware_d22_000`
- `min_plan_length`: 22
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (20): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 21
- `SAT_full`: True
- `SAT_full plan` (22): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

## Reviewer Notes

- `required_actions` is deduped and may not show repeated reacquisition.
- Treat repeated steps in `SAT_full plan` as the best clue for policy teaching gaps.
- Findings should cite exact files/lines, not just this bundle.
