from enum import StrEnum
from typing import List

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class HoldStatus(StrEnum):
    PRESENT = "present"
    CLEARED = "cleared"


class ReachabilityState(StrEnum):
    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"


class ConnectorHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class ProfileState(StrEnum):
    NOT_READY = "not_ready"
    READY = "ready"


class RetryState(StrEnum):
    NOT_READY = "not_ready"
    READY = "ready"


class ChargeState(StrEnum):
    INACTIVE = "inactive"
    ACTIVE = "active"


class EVAccount(BaseModelNoExtra):
    account_id: str
    customer_name: str
    hold_status: HoldStatus = HoldStatus.CLEARED


class EVStation(BaseModelNoExtra):
    station_id: str
    site_id: str
    reachability_state: ReachabilityState = ReachabilityState.REACHABLE
    connector_health: ConnectorHealth = ConnectorHealth.HEALTHY


class EVChargeSession(BaseModelNoExtra):
    session_id: str
    account_id: str
    station_id: str
    profile_state: ProfileState = ProfileState.NOT_READY
    retry_state: RetryState = RetryState.NOT_READY
    charge_state: ChargeState = ChargeState.INACTIVE
    last_fault_code: str = "NONE"


class EVChargingSupportDB(DB):
    accounts: List[EVAccount]
    stations: List[EVStation]
    sessions: List[EVChargeSession]
