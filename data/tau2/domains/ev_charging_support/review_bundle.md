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

- tasks: 111
- families: 111
- tasks with `start_bindings`: 74
- tasks with `goal_bindings`: 74
- task counts by `terminal_profile_id`: {'billing_resolved': 42, 'connectivity_resolved': 39, 'full_system_resolved': 30}
- `min_plan_length` stats: min=14, avg=17.87, max=25
- `required_actions` stats: min=12, avg=15.91, max=23

### Family Counts
- `billing_allowlist_only_app_known`: 1
- `billing_allowlist_only_base`: 1
- `billing_allowlist_only_screen_known`: 1
- `billing_allowlist_reservation_app_known`: 1
- `billing_allowlist_reservation_base`: 1
- `billing_allowlist_reservation_screen_known`: 1
- `billing_allowlist_tariff_app_known`: 1
- `billing_allowlist_tariff_base`: 1
- `billing_allowlist_tariff_screen_known`: 1
- `billing_auth_stack_full_app_known`: 1
- `billing_auth_stack_full_base`: 1
- `billing_auth_stack_full_screen_known`: 1
- `billing_entitlement_stack_only_app_known`: 1
- `billing_entitlement_stack_only_base`: 1
- `billing_entitlement_stack_only_screen_known`: 1
- `billing_fraud_and_auth_app_known`: 1
- `billing_fraud_and_auth_base`: 1
- `billing_fraud_and_auth_screen_known`: 1
- `billing_hold_and_auth_app_known`: 1
- `billing_hold_and_auth_base`: 1
- `billing_hold_and_auth_screen_known`: 1
- `billing_hold_and_fraud_auth_app_known`: 1
- `billing_hold_and_fraud_auth_base`: 1
- `billing_hold_and_fraud_auth_screen_known`: 1
- `billing_hold_and_payment_auth_app_known`: 1
- `billing_hold_and_payment_auth_base`: 1
- `billing_hold_and_payment_auth_screen_known`: 1
- `billing_payment_and_auth_app_known`: 1
- `billing_payment_and_auth_base`: 1
- `billing_payment_and_auth_screen_known`: 1
- `billing_payment_and_fraud_auth_app_known`: 1
- `billing_payment_and_fraud_auth_base`: 1
- `billing_payment_and_fraud_auth_screen_known`: 1
- `billing_reservation_only_app_known`: 1
- `billing_reservation_only_base`: 1
- `billing_reservation_only_screen_known`: 1
- `billing_tariff_only_app_known`: 1
- `billing_tariff_only_base`: 1
- `billing_tariff_only_screen_known`: 1
- `billing_tariff_reservation_app_known`: 1
- `billing_tariff_reservation_base`: 1
- `billing_tariff_reservation_screen_known`: 1
- `connectivity_allowlist_only_app_known`: 1
- `connectivity_allowlist_only_base`: 1
- `connectivity_allowlist_only_screen_known`: 1
- `connectivity_cert_clock_auth_app_known`: 1
- `connectivity_cert_clock_auth_base`: 1
- `connectivity_cert_clock_auth_screen_known`: 1
- `connectivity_cert_handshake_auth_app_known`: 1
- `connectivity_cert_handshake_auth_base`: 1
- `connectivity_cert_handshake_auth_screen_known`: 1
- `connectivity_cert_only_app_known`: 1
- `connectivity_cert_only_base`: 1
- `connectivity_cert_only_screen_known`: 1
- `connectivity_clock_handshake_auth_app_known`: 1
- `connectivity_clock_handshake_auth_base`: 1
- `connectivity_clock_handshake_auth_screen_known`: 1
- `connectivity_clock_only_app_known`: 1
- `connectivity_clock_only_base`: 1
- `connectivity_clock_only_screen_known`: 1
- `connectivity_entitlement_stack_only_app_known`: 1
- `connectivity_entitlement_stack_only_base`: 1
- `connectivity_entitlement_stack_only_screen_known`: 1
- `connectivity_handshake_only_app_known`: 1
- `connectivity_handshake_only_base`: 1
- `connectivity_handshake_only_screen_known`: 1
- `connectivity_link_handshake_auth_app_known`: 1
- `connectivity_link_handshake_auth_base`: 1
- `connectivity_link_handshake_auth_screen_known`: 1
- `connectivity_link_only_app_known`: 1
- `connectivity_link_only_base`: 1
- `connectivity_link_only_screen_known`: 1
- `connectivity_reservation_only_app_known`: 1
- `connectivity_reservation_only_base`: 1
- `connectivity_reservation_only_screen_known`: 1
- `connectivity_secure_transport_full_app_known`: 1
- `connectivity_secure_transport_full_base`: 1
- `connectivity_secure_transport_full_screen_known`: 1
- `connectivity_tariff_only_app_known`: 1
- `connectivity_tariff_only_base`: 1
- `connectivity_tariff_only_screen_known`: 1
- `full_system_all_lanes_app_known`: 1
- `full_system_all_lanes_base`: 1
- `full_system_all_lanes_screen_known`: 1
- `full_system_allowlist_only_app_known`: 1
- `full_system_allowlist_only_base`: 1
- `full_system_allowlist_only_screen_known`: 1
- `full_system_billing_entitlement_app_known`: 1
- `full_system_billing_entitlement_base`: 1
- `full_system_billing_entitlement_screen_known`: 1
- `full_system_billing_firmware_app_known`: 1
- `full_system_billing_firmware_base`: 1
- `full_system_billing_firmware_fraud_app_known`: 1
- `full_system_billing_firmware_fraud_base`: 1
- `full_system_billing_firmware_fraud_screen_known`: 1
- `full_system_billing_firmware_screen_known`: 1
- `full_system_billing_transport_app_known`: 1
- `full_system_billing_transport_base`: 1
- `full_system_billing_transport_screen_known`: 1
- `full_system_cert_clock_firmware_app_known`: 1
- `full_system_cert_clock_firmware_base`: 1
- `full_system_cert_clock_firmware_screen_known`: 1
- `full_system_link_handshake_firmware_app_known`: 1
- `full_system_link_handshake_firmware_base`: 1
- `full_system_link_handshake_firmware_screen_known`: 1
- `full_system_transport_entitlement_app_known`: 1
- `full_system_transport_entitlement_base`: 1
- `full_system_transport_entitlement_screen_known`: 1
- `full_system_transport_firmware_app_known`: 1
- `full_system_transport_firmware_base`: 1
- `full_system_transport_firmware_screen_known`: 1

### Hardest Tasks
- `full_system_all_lanes_base_d25_000`: min_plan_length=25, required_actions=23
- `full_system_transport_entitlement_base_d25_000`: min_plan_length=25, required_actions=21
- `full_system_all_lanes_screen_known_d24_000`: min_plan_length=24, required_actions=23
- `full_system_all_lanes_app_known_d24_000`: min_plan_length=24, required_actions=22
- `full_system_transport_entitlement_screen_known_d24_000`: min_plan_length=24, required_actions=21

## Representative Tasks By Family

These tasks include SAT plans so the reviewer can compare what the policy teaches against what the solver/runtime actually requires.

### `billing_allowlist_only_app_known`
#### `billing_allowlist_only_app_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (12): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_allowlist_only_base`
#### `billing_allowlist_only_base_d15_000`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_allowlist_only_screen_known`
#### `billing_allowlist_only_screen_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_allowlist_reservation_app_known`
#### `billing_allowlist_reservation_app_known_d16_000`
- `min_plan_length`: 16
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_allowlist_reservation_base`
#### `billing_allowlist_reservation_base_d17_000`
- `min_plan_length`: 17
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_allowlist_reservation_screen_known`
#### `billing_allowlist_reservation_screen_known_d16_000`
- `min_plan_length`: 16
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'acquire_screen_fault_code_from_user', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_allowlist_tariff_app_known`
#### `billing_allowlist_tariff_app_known_d16_000`
- `min_plan_length`: 16
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_allowlist_tariff_base`
#### `billing_allowlist_tariff_base_d17_000`
- `min_plan_length`: 17
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_allowlist_tariff_screen_known`
#### `billing_allowlist_tariff_screen_known_d16_000`
- `min_plan_length`: 16
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'acquire_screen_fault_code_from_user', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_auth_stack_full_app_known`
#### `billing_auth_stack_full_app_known_d16_000`
- `min_plan_length`: 16
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_auth_stack_full_base`
#### `billing_auth_stack_full_base_d17_000`
- `min_plan_length`: 17
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_auth_stack_full_screen_known`
#### `billing_auth_stack_full_screen_known_d16_000`
- `min_plan_length`: 16
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (15): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_entitlement_stack_only_app_known`
#### `billing_entitlement_stack_only_app_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x5

### `billing_entitlement_stack_only_base`
#### `billing_entitlement_stack_only_base_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x5

### `billing_entitlement_stack_only_screen_known`
#### `billing_entitlement_stack_only_screen_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (15): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'acquire_screen_fault_code_from_user', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_fraud_and_auth_app_known`
#### `billing_fraud_and_auth_app_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (12): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_fraud_and_auth_base`
#### `billing_fraud_and_auth_base_d15_000`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_fraud_and_auth_screen_known`
#### `billing_fraud_and_auth_screen_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_hold_and_auth_app_known`
#### `billing_hold_and_auth_app_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (12): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_auth_base`
#### `billing_hold_and_auth_base_d15_000`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_auth_screen_known`
#### `billing_hold_and_auth_screen_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_hold_and_fraud_auth_app_known`
#### `billing_hold_and_fraud_auth_app_known_d15_000`
- `min_plan_length`: 15
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_fraud_auth_base`
#### `billing_hold_and_fraud_auth_base_d16_000`
- `min_plan_length`: 16
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_fraud_auth_screen_known`
#### `billing_hold_and_fraud_auth_screen_known_d15_000`
- `min_plan_length`: 15
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_hold_and_payment_auth_app_known`
#### `billing_hold_and_payment_auth_app_known_d15_000`
- `min_plan_length`: 15
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_payment_auth_base`
#### `billing_hold_and_payment_auth_base_d16_000`
- `min_plan_length`: 16
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_hold_and_payment_auth_screen_known`
#### `billing_hold_and_payment_auth_screen_known_d15_000`
- `min_plan_length`: 15
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_payment_and_auth_app_known`
#### `billing_payment_and_auth_app_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (12): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_payment_and_auth_base`
#### `billing_payment_and_auth_base_d15_000`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_payment_and_auth_screen_known`
#### `billing_payment_and_auth_screen_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_payment_and_fraud_auth_app_known`
#### `billing_payment_and_fraud_auth_app_known_d15_000`
- `min_plan_length`: 15
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_payment_and_fraud_auth_base`
#### `billing_payment_and_fraud_auth_base_d16_000`
- `min_plan_length`: 16
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_payment_and_fraud_auth_screen_known`
#### `billing_payment_and_fraud_auth_screen_known_d15_000`
- `min_plan_length`: 15
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_reservation_only_app_known`
#### `billing_reservation_only_app_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (12): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_reservation_only_base`
#### `billing_reservation_only_base_d15_000`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_reservation_only_screen_known`
#### `billing_reservation_only_screen_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_tariff_only_app_known`
#### `billing_tariff_only_app_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (12): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_tariff_only_base`
#### `billing_tariff_only_base_d15_000`
- `min_plan_length`: 15
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 14
- `SAT_full`: True
- `SAT_full plan` (15): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `billing_tariff_only_screen_known`
#### `billing_tariff_only_screen_known_d14_000`
- `min_plan_length`: 14
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 13
- `SAT_full`: True
- `SAT_full plan` (14): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `billing_tariff_reservation_app_known`
#### `billing_tariff_reservation_app_known_d16_000`
- `min_plan_length`: 16
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (13): ['acquire_screen_fault_code_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_screen_fault_code_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_tariff_reservation_base`
#### `billing_tariff_reservation_base_d17_000`
- `min_plan_length`: 17
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `billing_tariff_reservation_screen_known`
#### `billing_tariff_reservation_screen_known_d16_000`
- `min_plan_length`: 16
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station].diagnostics_state', 'agent.sessions[active_session]', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'billing_resolved'
- `required_actions` (14): ['acquire_error_class_from_user', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'acquire_screen_fault_code_from_user', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_billing', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_billing']
- `required_precedence` count: 15
- `SAT_full`: True
- `SAT_full plan` (16): acquire_error_class_from_user -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_billing -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_billing
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_allowlist_only_app_known`
#### `connectivity_allowlist_only_app_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_allowlist_only_base`
#### `connectivity_allowlist_only_base_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_allowlist_only_screen_known`
#### `connectivity_allowlist_only_screen_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_cert_clock_auth_app_known`
#### `connectivity_cert_clock_auth_app_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_cert_clock_auth_base`
#### `connectivity_cert_clock_auth_base_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_cert_clock_auth_screen_known`
#### `connectivity_cert_clock_auth_screen_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_cert_handshake_auth_app_known`
#### `connectivity_cert_handshake_auth_app_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_cert_handshake_auth_base`
#### `connectivity_cert_handshake_auth_base_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_cert_handshake_auth_screen_known`
#### `connectivity_cert_handshake_auth_screen_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_cert_only_app_known`
#### `connectivity_cert_only_app_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_cert_only_base`
#### `connectivity_cert_only_base_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_cert_only_screen_known`
#### `connectivity_cert_only_screen_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_rotate_station_certificate', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_rotate_station_certificate -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_clock_handshake_auth_app_known`
#### `connectivity_clock_handshake_auth_app_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_clock_handshake_auth_base`
#### `connectivity_clock_handshake_auth_base_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_clock_handshake_auth_screen_known`
#### `connectivity_clock_handshake_auth_screen_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_clock_only_app_known`
#### `connectivity_clock_only_app_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_clock_only_base`
#### `connectivity_clock_only_base_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_clock_only_screen_known`
#### `connectivity_clock_only_screen_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_entitlement_stack_only_app_known`
#### `connectivity_entitlement_stack_only_app_known_d21_000`
- `min_plan_length`: 21
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 20
- `SAT_full`: True
- `SAT_full plan` (21): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x5

### `connectivity_entitlement_stack_only_base`
#### `connectivity_entitlement_stack_only_base_d22_000`
- `min_plan_length`: 22
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 21
- `SAT_full`: True
- `SAT_full plan` (22): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x5

### `connectivity_entitlement_stack_only_screen_known`
#### `connectivity_entitlement_stack_only_screen_known_d21_000`
- `min_plan_length`: 21
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (18): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'acquire_screen_fault_code_from_user', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 20
- `SAT_full`: True
- `SAT_full plan` (21): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `connectivity_handshake_only_app_known`
#### `connectivity_handshake_only_app_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_handshake_only_base`
#### `connectivity_handshake_only_base_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_handshake_only_screen_known`
#### `connectivity_handshake_only_screen_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_link_handshake_auth_app_known`
#### `connectivity_link_handshake_auth_app_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_link_handshake_auth_base`
#### `connectivity_link_handshake_auth_base_d19_000`
- `min_plan_length`: 19
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_link_handshake_auth_screen_known`
#### `connectivity_link_handshake_auth_screen_known_d18_000`
- `min_plan_length`: 18
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (17): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_link_only_app_known`
#### `connectivity_link_only_app_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_link_only_base`
#### `connectivity_link_only_base_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_link_only_screen_known`
#### `connectivity_link_only_screen_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_reservation_only_app_known`
#### `connectivity_reservation_only_app_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_reservation_only_base`
#### `connectivity_reservation_only_base_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_reservation_only_screen_known`
#### `connectivity_reservation_only_screen_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_secure_transport_full_app_known`
#### `connectivity_secure_transport_full_app_known_d20_000`
- `min_plan_length`: 20
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_secure_transport_full_base`
#### `connectivity_secure_transport_full_base_d21_000`
- `min_plan_length`: 21
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (19): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 20
- `SAT_full`: True
- `SAT_full plan` (21): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_secure_transport_full_screen_known`
#### `connectivity_secure_transport_full_screen_known_d20_000`
- `min_plan_length`: 20
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (19): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `connectivity_tariff_only_app_known`
#### `connectivity_tariff_only_app_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_tariff_only_base`
#### `connectivity_tariff_only_base_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `connectivity_tariff_only_screen_known`
#### `connectivity_tariff_only_screen_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'connectivity_resolved'
- `required_actions` (16): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_connectivity', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_connectivity -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `full_system_all_lanes_app_known`
#### `full_system_all_lanes_app_known_d24_000`
- `min_plan_length`: 24
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (22): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 23
- `SAT_full`: True
- `SAT_full plan` (24): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_all_lanes_base`
#### `full_system_all_lanes_base_d25_000`
- `min_plan_length`: 25
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (23): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 24
- `SAT_full`: True
- `SAT_full plan` (25): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_all_lanes_screen_known`
#### `full_system_all_lanes_screen_known_d24_000`
- `min_plan_length`: 24
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (23): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_release_fraud_lock', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 23
- `SAT_full`: True
- `SAT_full plan` (24): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_release_fraud_lock -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `full_system_allowlist_only_app_known`
#### `full_system_allowlist_only_app_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (15): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_allowlist_only_base`
#### `full_system_allowlist_only_base_d18_000`
- `min_plan_length`: 18
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (16): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 17
- `SAT_full`: True
- `SAT_full plan` (18): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_allowlist_only_screen_known`
#### `full_system_allowlist_only_screen_known_d17_000`
- `min_plan_length`: 17
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (16): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 16
- `SAT_full`: True
- `SAT_full plan` (17): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_entitlement_blocker_allowlist_sync -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `full_system_billing_entitlement_app_known`
#### `full_system_billing_entitlement_app_known_d22_000`
- `min_plan_length`: 22
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 21
- `SAT_full`: True
- `SAT_full plan` (22): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x5

### `full_system_billing_entitlement_base`
#### `full_system_billing_entitlement_base_d23_000`
- `min_plan_length`: 23
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (19): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 22
- `SAT_full`: True
- `SAT_full plan` (23): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x5

### `full_system_billing_entitlement_screen_known`
#### `full_system_billing_entitlement_screen_known_d22_000`
- `min_plan_length`: 22
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (19): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'acquire_screen_fault_code_from_user', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_clear_entitlement_blocker_reservation_lock', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 21
- `SAT_full`: True
- `SAT_full plan` (22): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_reservation_lock -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `full_system_billing_firmware_app_known`
#### `full_system_billing_firmware_app_known_d19_000`
- `min_plan_length`: 19
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_firmware_base`
#### `full_system_billing_firmware_base_d20_000`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_firmware_fraud_app_known`
#### `full_system_billing_firmware_fraud_app_known_d19_000`
- `min_plan_length`: 19
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_firmware_fraud_base`
#### `full_system_billing_firmware_fraud_base_d20_000`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_firmware_fraud_screen_known`
#### `full_system_billing_firmware_fraud_screen_known_d19_000`
- `min_plan_length`: 19
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_release_fraud_lock', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_release_fraud_lock -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `full_system_billing_firmware_screen_known`
#### `full_system_billing_firmware_screen_known_d19_000`
- `min_plan_length`: 19
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `full_system_billing_transport_app_known`
#### `full_system_billing_transport_app_known_d22_000`
- `min_plan_length`: 22
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (20): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 21
- `SAT_full`: True
- `SAT_full plan` (22): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_transport_base`
#### `full_system_billing_transport_base_d23_000`
- `min_plan_length`: 23
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (21): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 22
- `SAT_full`: True
- `SAT_full plan` (23): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_billing_transport_screen_known`
#### `full_system_billing_transport_screen_known_d22_000`
- `min_plan_length`: 22
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (21): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_clear_backend_hold', 'assistant_refresh_payment_token', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 21
- `SAT_full`: True
- `SAT_full plan` (22): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_clear_backend_hold -> assistant_refresh_payment_token -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `full_system_cert_clock_firmware_app_known`
#### `full_system_cert_clock_firmware_app_known_d19_000`
- `min_plan_length`: 19
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_cert_clock_firmware_base`
#### `full_system_cert_clock_firmware_base_d20_000`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_cert_clock_firmware_screen_known`
#### `full_system_cert_clock_firmware_screen_known_d19_000`
- `min_plan_length`: 19
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `full_system_link_handshake_firmware_app_known`
#### `full_system_link_handshake_firmware_app_known_d19_000`
- `min_plan_length`: 19
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (17): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_link_handshake_firmware_base`
#### `full_system_link_handshake_firmware_base_d20_000`
- `min_plan_length`: 20
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 19
- `SAT_full`: True
- `SAT_full plan` (20): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_link_handshake_firmware_screen_known`
#### `full_system_link_handshake_firmware_screen_known_d19_000`
- `min_plan_length`: 19
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (18): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 18
- `SAT_full`: True
- `SAT_full plan` (19): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

### `full_system_transport_entitlement_app_known`
#### `full_system_transport_entitlement_app_known_d24_000`
- `min_plan_length`: 24
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (20): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 23
- `SAT_full`: True
- `SAT_full plan` (24): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x5

### `full_system_transport_entitlement_base`
#### `full_system_transport_entitlement_base_d25_000`
- `min_plan_length`: 25
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (21): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 24
- `SAT_full`: True
- `SAT_full plan` (25): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x5

### `full_system_transport_entitlement_screen_known`
#### `full_system_transport_entitlement_screen_known_d24_000`
- `min_plan_length`: 24
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (21): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'acquire_screen_fault_code_from_user', 'assistant_clear_entitlement_blocker_allowlist_sync', 'assistant_clear_entitlement_blocker_tariff_profile', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 23
- `SAT_full`: True
- `SAT_full plan` (24): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_allowlist_sync -> acquire_screen_fault_code_from_user -> assistant_clear_entitlement_blocker_tariff_profile -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x4

### `full_system_transport_firmware_app_known`
#### `full_system_transport_firmware_app_known_d21_000`
- `min_plan_length`: 21
- `start_bindings`: ['app_error_class']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: []
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (19): ['acquire_screen_fault_code_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 20
- `SAT_full`: True
- `SAT_full plan` (21): acquire_screen_fault_code_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_transport_firmware_base`
#### `full_system_transport_firmware_base_d22_000`
- `min_plan_length`: 22
- `start_bindings`: []
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (20): ['acquire_screen_fault_code_from_user', 'acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 21
- `SAT_full`: True
- `SAT_full plan` (22): acquire_screen_fault_code_from_user -> acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x3

### `full_system_transport_firmware_screen_known`
#### `full_system_transport_firmware_screen_known_d21_000`
- `min_plan_length`: 21
- `start_bindings`: ['screen_fault_code']
- `goal_capture_paths`: ['agent.accounts[active_account]', 'agent.stations[active_station]', 'agent.network_paths[active_station]', 'agent.sessions[active_session]', 'user.physical.cable_inspection_state', 'user.physical.connector_reseat_state', 'user.physical.station_power_cycle_state', 'user.physical.vehicle_ready_state', 'user.physical.app_refresh_state', 'user.physical.app_login_state', 'user.physical.connector_latch_state', 'user.physical.test_charge_state']
- `goal_bindings`: ['app_error_class']
- `terminal_profile_id`: 'full_system_resolved'
- `required_actions` (20): ['acquire_error_class_from_user', 'user_inspect_cable_path', 'user_reseat_connector', 'user_power_cycle_station', 'user_set_vehicle_ready_mode', 'user_refresh_charging_app_session', 'user_re_authenticate_charging_app', 'user_confirm_connector_latch', 'assistant_run_backend_diagnostics', 'assistant_restore_backend_link', 'assistant_sync_station_clock', 'assistant_rotate_station_certificate', 'assistant_reestablish_station_handshake', 'assistant_update_station_firmware', 'assistant_refresh_session_authorization', 'acquire_screen_fault_code_from_user', 'assistant_reprovision_full_system', 'assistant_refresh_vehicle_authorization', 'assistant_reset_retry_path', 'user_run_test_charge_hardware']
- `required_precedence` count: 20
- `SAT_full`: True
- `SAT_full plan` (21): acquire_error_class_from_user -> user_inspect_cable_path -> user_reseat_connector -> user_power_cycle_station -> user_set_vehicle_ready_mode -> user_refresh_charging_app_session -> user_re_authenticate_charging_app -> user_confirm_connector_latch -> assistant_run_backend_diagnostics -> assistant_restore_backend_link -> assistant_sync_station_clock -> assistant_rotate_station_certificate -> assistant_reestablish_station_handshake -> assistant_update_station_firmware -> assistant_refresh_session_authorization -> acquire_screen_fault_code_from_user -> assistant_reprovision_full_system -> assistant_refresh_vehicle_authorization -> acquire_screen_fault_code_from_user -> assistant_reset_retry_path -> user_run_test_charge_hardware
- repeated plan actions: acquire_screen_fault_code_from_user x2

## Reviewer Notes

- `required_actions` is deduped and may not show repeated reacquisition.
- Treat repeated steps in `SAT_full plan` as the best clue for policy teaching gaps.
- Findings should cite exact files/lines, not just this bundle.
