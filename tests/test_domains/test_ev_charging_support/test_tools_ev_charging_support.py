import unittest

from tau2.domains.ev_charging_support.data_model import (
    AllowlistSyncState,
    BackendLinkState,
    CertState,
    ChargeState,
    ClockSyncState,
    DiagnosticsState,
    ErrorClass,
    FirmwareState,
    FraudLockState,
    HandshakeState,
    HoldStatus,
    PaymentTokenStatus,
    ProfileState,
    ReachabilityState,
    ReservationLockState,
    RetryState,
    SessionAuthState,
    TariffProfileState,
    VehicleAuthState,
)
from tau2.domains.ev_charging_support.environment import get_environment
from tau2.domains.ev_charging_support.user_data_model import (
    AppRefreshState,
    AppLoginState,
    CableInspectionState,
    ConnectorReseatState,
    ConnectorLatchState,
    StationPowerCycleState,
    VehicleReadyState,
)


class TestEVChargingSupportTools(unittest.TestCase):
    def test_reprovision_tool_schema_exposes_branch_enum(self):
        env = get_environment()

        schema = env.tools.get_tools()["reprovision"].openai_schema
        branch_schema = schema["function"]["parameters"]["properties"]["branch"]

        self.assertEqual(branch_schema["type"], "string")
        self.assertEqual(
            branch_schema["enum"],
            ["billing", "connectivity", "full_system"],
        )

    def test_clear_entitlement_blocker_tool_schema_exposes_blocker_enum(self):
        env = get_environment()

        schema = env.tools.get_tools()["clear_entitlement_blocker"].openai_schema
        blocker_schema = schema["function"]["parameters"]["properties"]["blocker"]

        self.assertEqual(blocker_schema["type"], "string")
        self.assertEqual(
            blocker_schema["enum"],
            ["allowlist_sync", "tariff_profile", "reservation_lock"],
        )

    def test_check_resolution_status_returns_minimal_stop_surface(self):
        env = get_environment()
        env.user_tools.set_stop_gate(
            [
                {
                    "check_field": "fault_code",
                    "op": "eq",
                    "expected": "NONE",
                    "unmet_reason": "Station still reports an unresolved fault code.",
                }
            ]
        )
        env.user_tools.db.view.display_fault_code = "RETRY-301"

        result = env.user_tools.check_resolution_status()

        self.assertEqual(
            result.model_dump(),
            {
                "resolved": False,
                "unmet": ["Station still reports an unresolved fault code."],
            },
        )

    def test_billing_backend_fixes_advance_fault_stages_without_stale_args(self):
        env = get_environment()
        account = env.tools.db.accounts[0]
        station = env.tools.db.stations[0]
        network = env.tools.db.network_paths[0]
        session = env.tools.db.sessions[0]

        account.hold_status = HoldStatus.PRESENT
        account.payment_token_status = PaymentTokenStatus.INVALID
        account.fraud_lock_state = FraudLockState.ON
        station.reachability_state = ReachabilityState.REACHABLE
        station.firmware_state = FirmwareState.CURRENT
        station.diagnostics_state = DiagnosticsState.IDLE
        network.backend_link_state = BackendLinkState.UP
        network.cert_state = CertState.FRESH
        session.error_class = ErrorClass.BILLING
        session.profile_state = ProfileState.NOT_READY
        session.session_auth_state = SessionAuthState.VALID
        session.vehicle_auth_state = VehicleAuthState.VALIDATED
        session.retry_state = RetryState.NOT_READY
        session.charge_state = ChargeState.INACTIVE
        station.clock_sync_state = ClockSyncState.SYNCED
        network.handshake_state = HandshakeState.ESTABLISHED

        env.sync_tools()
        self.assertEqual(env.user_tools.check_station_screen().fault_code, "BH-101")

        diag = env.tools.run_backend_diagnostics("BH-101", "billing")
        self.assertEqual(diag["status"], "success")
        self.assertEqual(env.tools.clear_billing_hold()["status"], "success")
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "PAY-201")

        self.assertEqual(env.tools.refresh_payment_token()["status"], "success")
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "FRD-301")

        self.assertEqual(env.tools.release_fraud_lock()["status"], "success")
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "PROFILE-201")

    def test_reprovision_and_retry_reset_require_fresh_screen_fault_code(self):
        env = get_environment()
        account = env.tools.db.accounts[0]
        station = env.tools.db.stations[0]
        network = env.tools.db.network_paths[0]
        session = env.tools.db.sessions[0]
        user = env.user_tools.db

        account.hold_status = HoldStatus.CLEARED
        account.payment_token_status = PaymentTokenStatus.VALID
        account.fraud_lock_state = FraudLockState.OFF
        station.reachability_state = ReachabilityState.REACHABLE
        station.firmware_state = FirmwareState.CURRENT
        station.diagnostics_state = DiagnosticsState.RAN
        network.backend_link_state = BackendLinkState.UP
        network.cert_state = CertState.FRESH
        network.handshake_state = HandshakeState.ESTABLISHED
        session.error_class = ErrorClass.BILLING
        session.profile_state = ProfileState.NOT_READY
        session.session_auth_state = SessionAuthState.VALID
        session.vehicle_auth_state = VehicleAuthState.VALIDATED
        session.retry_state = RetryState.NOT_READY
        session.charge_state = ChargeState.INACTIVE
        station.clock_sync_state = ClockSyncState.SYNCED
        user.physical.vehicle_ready_state = VehicleReadyState.READY
        user.physical.app_refresh_state = AppRefreshState.REFRESHED

        env.sync_tools()
        self.assertEqual(session.last_fault_code, "PROFILE-201")
        self.assertEqual(
            env.tools.reprovision("billing", "BH-101")["status"],
            "error",
        )
        self.assertEqual(
            env.tools.reprovision("billing", "PROFILE-201")["status"],
            "success",
        )

        env.sync_tools()
        self.assertEqual(session.last_fault_code, "RETRY-301")
        self.assertEqual(
            env.tools.reset_retry_path("PROFILE-201")["status"],
            "error",
        )
        self.assertEqual(
            env.tools.reset_retry_path("RETRY-301")["status"],
            "success",
        )

    def test_billing_charge_activation_does_not_require_hardware_steps(self):
        env = get_environment()
        account = env.tools.db.accounts[0]
        station = env.tools.db.stations[0]
        network = env.tools.db.network_paths[0]
        session = env.tools.db.sessions[0]
        user = env.user_tools.db

        account.hold_status = HoldStatus.CLEARED
        account.payment_token_status = PaymentTokenStatus.VALID
        account.fraud_lock_state = FraudLockState.OFF
        station.reachability_state = ReachabilityState.REACHABLE
        station.firmware_state = FirmwareState.CURRENT
        station.diagnostics_state = DiagnosticsState.RAN
        network.backend_link_state = BackendLinkState.UP
        network.cert_state = CertState.FRESH
        network.handshake_state = HandshakeState.ESTABLISHED
        session.error_class = ErrorClass.BILLING
        session.profile_state = ProfileState.READY
        session.session_auth_state = SessionAuthState.VALID
        session.vehicle_auth_state = VehicleAuthState.VALIDATED
        session.retry_state = RetryState.READY
        session.charge_state = ChargeState.INACTIVE
        station.clock_sync_state = ClockSyncState.SYNCED
        user.physical.cable_inspection_state = CableInspectionState.NOT_CHECKED
        user.physical.connector_reseat_state = ConnectorReseatState.NOT_RESEATED
        user.physical.station_power_cycle_state = StationPowerCycleState.NOT_DONE
        user.physical.vehicle_ready_state = VehicleReadyState.READY
        user.physical.app_refresh_state = AppRefreshState.REFRESHED
        user.physical.app_login_state = AppLoginState.ACTIVE
        user.physical.connector_latch_state = ConnectorLatchState.CONFIRMED

        env.user_tools.run_test_charge()
        env.sync_tools()

        self.assertEqual(session.charge_state, ChargeState.ACTIVE)
        self.assertEqual(session.last_fault_code, "NONE")

    def test_secure_transport_lane_is_stage_gated(self):
        env = get_environment()
        station = env.tools.db.stations[0]
        network = env.tools.db.network_paths[0]
        session = env.tools.db.sessions[0]

        station.reachability_state = ReachabilityState.REACHABLE
        station.diagnostics_state = DiagnosticsState.RAN
        station.clock_sync_state = ClockSyncState.SKEWED
        network.backend_link_state = BackendLinkState.DOWN
        network.cert_state = CertState.STALE
        network.handshake_state = HandshakeState.BROKEN
        session.error_class = ErrorClass.CONNECTIVITY
        session.profile_state = ProfileState.NOT_READY
        session.session_auth_state = SessionAuthState.VALID

        env.sync_tools()
        self.assertEqual(session.last_fault_code, "NET-410")

        self.assertEqual(env.tools.restore_backend_link()["status"], "success")
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "TIME-405")

        self.assertEqual(env.tools.sync_station_clock()["status"], "success")
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "CERT-409")

        self.assertEqual(env.tools.rotate_station_certificate()["status"], "success")
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "OCPP-411")

        self.assertEqual(env.tools.reestablish_station_handshake()["status"], "success")
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "PROFILE-201")

    def test_session_and_vehicle_auth_lanes_gate_late_stage_recovery(self):
        env = get_environment()
        account = env.tools.db.accounts[0]
        station = env.tools.db.stations[0]
        network = env.tools.db.network_paths[0]
        session = env.tools.db.sessions[0]
        user = env.user_tools.db

        account.hold_status = HoldStatus.CLEARED
        account.payment_token_status = PaymentTokenStatus.VALID
        account.fraud_lock_state = FraudLockState.OFF
        station.reachability_state = ReachabilityState.REACHABLE
        station.firmware_state = FirmwareState.CURRENT
        station.clock_sync_state = ClockSyncState.SYNCED
        station.diagnostics_state = DiagnosticsState.RAN
        network.backend_link_state = BackendLinkState.UP
        network.cert_state = CertState.FRESH
        network.handshake_state = HandshakeState.ESTABLISHED
        session.error_class = ErrorClass.BILLING
        session.profile_state = ProfileState.NOT_READY
        session.session_auth_state = SessionAuthState.STALE
        session.vehicle_auth_state = VehicleAuthState.PENDING
        session.retry_state = RetryState.NOT_READY
        user.physical.vehicle_ready_state = VehicleReadyState.READY
        user.physical.app_refresh_state = AppRefreshState.REFRESHED
        user.physical.app_login_state = AppLoginState.EXPIRED
        user.physical.connector_latch_state = ConnectorLatchState.UNCONFIRMED

        env.sync_tools()
        self.assertEqual(session.last_fault_code, "AUTH-220")
        self.assertEqual(
            env.tools.reprovision("billing", "PROFILE-201")["status"],
            "error",
        )
        self.assertEqual(
            env.tools.refresh_session_authorization()["status"],
            "error",
        )

        env.user_tools.re_authenticate_charging_app()
        self.assertEqual(
            env.tools.refresh_session_authorization()["status"],
            "success",
        )
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "PROFILE-201")

        self.assertEqual(
            env.tools.reprovision("billing", "PROFILE-201")["status"],
            "success",
        )
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "VEH-230")
        self.assertEqual(
            env.tools.reset_retry_path("VEH-230")["status"],
            "error",
        )

        env.user_tools.confirm_connector_latch()
        self.assertEqual(
            env.tools.refresh_vehicle_authorization()["status"],
            "success",
        )
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "RETRY-301")

    def test_entitlement_lane_advances_through_visible_stage_codes(self):
        env = get_environment()
        account = env.tools.db.accounts[0]
        station = env.tools.db.stations[0]
        network = env.tools.db.network_paths[0]
        session = env.tools.db.sessions[0]
        user = env.user_tools.db

        account.hold_status = HoldStatus.CLEARED
        account.payment_token_status = PaymentTokenStatus.VALID
        account.fraud_lock_state = FraudLockState.OFF
        station.reachability_state = ReachabilityState.REACHABLE
        station.firmware_state = FirmwareState.CURRENT
        station.clock_sync_state = ClockSyncState.SYNCED
        station.diagnostics_state = DiagnosticsState.RAN
        network.backend_link_state = BackendLinkState.UP
        network.cert_state = CertState.FRESH
        network.handshake_state = HandshakeState.ESTABLISHED
        session.error_class = ErrorClass.BILLING
        session.session_auth_state = SessionAuthState.STALE
        session.allowlist_sync_state = AllowlistSyncState.STALE
        session.tariff_profile_state = TariffProfileState.MISSING
        session.reservation_lock_state = ReservationLockState.PRESENT
        session.profile_state = ProfileState.NOT_READY
        session.vehicle_auth_state = VehicleAuthState.PENDING
        session.retry_state = RetryState.NOT_READY
        user.physical.app_login_state = AppLoginState.ACTIVE

        env.sync_tools()
        self.assertEqual(session.last_fault_code, "ENT-210")

        self.assertEqual(
            env.tools.clear_entitlement_blocker("allowlist_sync", "ENT-210")["status"],
            "success",
        )
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "ENT-220")

        self.assertEqual(
            env.tools.clear_entitlement_blocker("tariff_profile", "ENT-220")["status"],
            "success",
        )
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "ENT-230")

        self.assertEqual(
            env.tools.clear_entitlement_blocker("reservation_lock", "ENT-230")["status"],
            "success",
        )
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "AUTH-220")

        self.assertEqual(env.tools.refresh_session_authorization()["status"], "success")
        env.sync_tools()
        self.assertEqual(session.last_fault_code, "PROFILE-201")
