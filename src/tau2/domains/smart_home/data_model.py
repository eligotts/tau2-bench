from typing import Any, Dict, List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class Device(BaseModelNoExtra):
    device_id: str
    name: str
    device_type: str  # thermostat, light, lock, camera
    room: str
    status: str  # online, offline, updating
    settings: Dict[str, Any]
    firmware_version: str = "2.1.0"
    connected_to_hub: bool = True


class HomeUser(BaseModelNoExtra):
    user_id: str
    name: str
    phone: str
    device_ids: List[str]


class SmartHomeDB(DB):
    devices: List[Device]
    users: List[HomeUser]
    hub_status: str = "online"
