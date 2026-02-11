from typing import Dict, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class RoomState(BaseModelNoExtra):
    room_name: str
    temperature: float
    lights_on: bool
    light_brightness: int
    humidity: float = 45.0


class SmartHomeUserDB(DB):
    rooms: Dict[str, RoomState]
    device_responsiveness: Dict[str, bool]
    wifi_connected: bool = True
    hub_online: bool = True
    device_power_state: Dict[str, bool] = {}
    device_indicator: Dict[str, str] = {}
    device_needs_reset: Dict[str, bool] = {}
    user_name: Optional[str] = None
    user_id: Optional[str] = None
