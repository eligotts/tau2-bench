from typing import Any, Dict, Optional

from tau2.domains.ev_charging_support.data_model import (
    ChargeState,
    EVAccount,
    EVChargeSession,
    EVChargingSupportDB,
    EVStation,
    HoldStatus,
    ProfileState,
    ReachabilityState,
    RetryState,
)
from tau2.domains.ev_charging_support.user_data_model import (
    ConnectorReseatState,
    EVChargingSupportUserDB,
    StationPowerCycleState,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class EVChargingSupportTools(ToolKitBase):
    """Assistant tools for EV charging recovery workflows."""

    db: EVChargingSupportDB
    _user_db: Optional[EVChargingSupportUserDB]

    def __init__(self, db: EVChargingSupportDB):
        super().__init__(db)
        self._user_db = None

    def bind_user_db(self, user_db: EVChargingSupportUserDB) -> None:
        self._user_db = user_db

    def _active_account_id(self) -> Optional[str]:
        return self._user_db.context.account_id if self._user_db else None

    def _active_station_id(self) -> Optional[str]:
        return self._user_db.context.station_id if self._user_db else None

    def _active_session_id(self) -> Optional[str]:
        return self._user_db.context.session_id if self._user_db else None

    def _get_account(self) -> EVAccount:
        active_id = self._active_account_id()
        if active_id:
            for account in self.db.accounts:
                if account.account_id == active_id:
                    return account
        if not self.db.accounts:
            raise ValueError("No EV accounts found in database.")
        return self.db.accounts[0]

    def _get_station(self) -> EVStation:
        active_id = self._active_station_id()
        if active_id:
            for station in self.db.stations:
                if station.station_id == active_id:
                    return station
        if not self.db.stations:
            raise ValueError("No EV stations found in database.")
        return self.db.stations[0]

    def _get_session(self) -> EVChargeSession:
        active_id = self._active_session_id()
        if active_id:
            for session in self.db.sessions:
                if session.session_id == active_id:
                    return session
        if not self.db.sessions:
            raise ValueError("No EV charge sessions found in database.")
        return self.db.sessions[0]

    def _fault_code_guard(self, provided_fault_code: str) -> Optional[str]:
        session = self._get_session()
        if not provided_fault_code:
            return "fault_code is required."
        if session.last_fault_code != "NONE" and provided_fault_code != session.last_fault_code:
            return (
                f"fault_code mismatch. expected '{session.last_fault_code}', "
                f"got '{provided_fault_code}'."
            )
        return None

    @is_tool(ToolType.WRITE)
    def clear_billing_hold(self, fault_code: str) -> Dict[str, Any]:
        """Clear backend hold when a valid fault code is supplied."""
        station = self._get_station()
        account = self._get_account()

        if station.reachability_state != ReachabilityState.REACHABLE:
            return {"status": "error", "message": "Station unreachable; hold clear blocked."}

        error = self._fault_code_guard(fault_code)
        if error is not None:
            return {"status": "error", "message": error}

        if account.hold_status == HoldStatus.CLEARED:
            return {"status": "noop", "message": "Hold already cleared."}

        account.hold_status = HoldStatus.CLEARED
        return {"status": "success", "message": "Billing hold cleared."}

    @is_tool(ToolType.WRITE)
    def reprovision_charging_profile(self, fault_code: str) -> Dict[str, Any]:
        """Reprovision charging profile once backend and user-side gates are satisfied."""
        account = self._get_account()
        session = self._get_session()

        error = self._fault_code_guard(fault_code)
        if error is not None:
            return {"status": "error", "message": error}

        if account.hold_status != HoldStatus.CLEARED:
            return {"status": "error", "message": "Hold must be cleared before reprovision."}
        if session.profile_state != ProfileState.NOT_READY:
            return {"status": "noop", "message": "Profile already reprovisioned."}
        if self._user_db is None:
            return {"status": "error", "message": "User context unavailable."}
        if (
            self._user_db.physical.station_power_cycle_state
            != StationPowerCycleState.DONE
        ):
            return {
                "status": "error",
                "message": "User has not completed station power cycle.",
            }
        if self._user_db.physical.connector_reseat_state != ConnectorReseatState.RESEATED:
            return {"status": "error", "message": "User has not reseated connector."}

        session.profile_state = ProfileState.READY
        session.retry_state = RetryState.READY
        session.last_fault_code = "NONE"
        return {"status": "success", "message": "Charging profile reprovisioned."}

    # ------------------------------------------------------------------
    # Init helpers (runtime initialization actions)
    # ------------------------------------------------------------------

    def set_hold_status(self, value: str) -> None:
        self._get_account().hold_status = HoldStatus(value)

    def set_reachability_state(self, value: str) -> None:
        self._get_station().reachability_state = ReachabilityState(value)

    def set_profile_state(self, value: str) -> None:
        self._get_session().profile_state = ProfileState(value)

    def set_retry_state(self, value: str) -> None:
        self._get_session().retry_state = RetryState(value)

    def set_charge_state(self, value: str) -> None:
        self._get_session().charge_state = ChargeState(value)

    def set_last_fault_code(self, value: str) -> None:
        self._get_session().last_fault_code = value

    # ------------------------------------------------------------------
    # Assertion helpers (runtime env assertions)
    # ------------------------------------------------------------------

    def assert_hold_status(self, expected: str) -> bool:
        return self._get_account().hold_status == HoldStatus(expected)

    def assert_profile_state(self, expected: str) -> bool:
        return self._get_session().profile_state == ProfileState(expected)

    def assert_retry_state(self, expected: str) -> bool:
        return self._get_session().retry_state == RetryState(expected)

    def assert_charge_state(self, expected: str) -> bool:
        return self._get_session().charge_state == ChargeState(expected)

    def assert_last_fault_code(self, expected: str) -> bool:
        return self._get_session().last_fault_code == expected
