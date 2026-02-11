from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.smart_home.data_model import SmartHomeDB
from tau2.domains.smart_home.tools import SmartHomeTools
from tau2.domains.smart_home.user_data_model import SmartHomeUserDB
from tau2.domains.smart_home.user_tools import SmartHomeUserTools
from tau2.domains.smart_home.utils import (
    SMART_HOME_DB_PATH,
    SMART_HOME_POLICY_PATH,
    SMART_HOME_TASK_SET_PATH,
    SMART_HOME_USER_DB_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


class SmartHomeEnvironment(Environment):
    tools: SmartHomeTools
    user_tools: SmartHomeUserTools

    def __init__(
        self,
        domain_name: str,
        policy: str,
        tools: SmartHomeTools,
        user_tools: SmartHomeUserTools,
    ):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """
        Synchronize user-side (physical world) state with agent-side (device) state.

        Sync rules (order matters):
        1. WiFi down → all WiFi-connected devices become unresponsive
        2. Hub offline → all hub-connected devices become unresponsive
        3. Device updating → device unresponsive, indicator blinking
        4. WiFi restored + hub online → devices regain responsiveness
        5. Online + responsive thermostat → room temp matches target_temp
        6. Online + responsive light → room light state matches light settings
        7. Offline or unresponsive → user can't interact
        """
        # Rule 1: WiFi down → all devices unresponsive
        if not self.user_tools.db.wifi_connected:
            for device in self.tools.db.devices:
                self.user_tools.db.device_responsiveness[device.device_id] = False
                self.user_tools.db.device_indicator[device.device_id] = "red"
            return  # No further sync when WiFi is down

        # Sync hub_online user-side state with hub_status (before early returns)
        self.user_tools.db.hub_online = (self.tools.db.hub_status == "online")

        # Rule 2: Hub offline → hub-connected devices unresponsive
        if self.tools.db.hub_status != "online":
            for device in self.tools.db.devices:
                if device.connected_to_hub:
                    self.user_tools.db.device_responsiveness[device.device_id] = False
                    self.user_tools.db.device_indicator[device.device_id] = "red"
                    device.status = "offline"
            return  # No further sync when hub is down

        # Rule 3: Device updating → unresponsive, indicator blinking
        for device in self.tools.db.devices:
            if device.status == "updating":
                self.user_tools.db.device_responsiveness[device.device_id] = False
                self.user_tools.db.device_indicator[device.device_id] = "blinking"

        # Rule 4: WiFi + hub online → online hub-connected devices auto-restore
        for device in self.tools.db.devices:
            if device.status == "updating":
                continue  # Don't restore updating devices
            if device.connected_to_hub and device.status == "online":
                self.user_tools.db.device_indicator[device.device_id] = "green"
                self.user_tools.db.device_responsiveness[device.device_id] = True

        # Rules 5-7: Per-device sync
        for device in self.tools.db.devices:
            responsive = self.user_tools.db.device_responsiveness.get(
                device.device_id, True
            )

            if device.status == "online" and responsive:
                if device.device_type == "thermostat":
                    self._sync_thermostat(device)
                elif device.device_type == "light":
                    self._sync_light(device)
                self.user_tools.db.device_indicator[device.device_id] = "green"
            elif device.status == "offline":
                self.user_tools.db.device_responsiveness[device.device_id] = False
                self.user_tools.db.device_indicator[device.device_id] = "red"
            elif not responsive:
                self.user_tools.db.device_responsiveness[device.device_id] = False

    def _sync_thermostat(self, device):
        """Sync thermostat: only 'heat' mode actively heats the room to target.
        'cool' mode won't raise temp (simulating winter: AC can't heat).
        'off' mode does nothing."""
        room = self.user_tools.db.rooms.get(device.room)
        if room is None:
            return
        mode = device.settings.get("mode", "off")
        target_temp = device.settings.get("target_temp", 72)
        if mode == "heat":
            room.temperature = float(target_temp)
        elif mode == "cool":
            # In cool mode, temp can only go down, not up
            room.temperature = min(room.temperature, float(target_temp))

    def _sync_light(self, device):
        """Sync light: on/off and brightness."""
        room = self.user_tools.db.rooms.get(device.room)
        if room is None:
            return
        is_on = device.settings.get("on", False)
        brightness = device.settings.get("brightness", 100)
        room.lights_on = is_on
        room.light_brightness = brightness


def get_environment(
    db: Optional[SmartHomeDB] = None,
    user_db: Optional[SmartHomeUserDB] = None,
    solo_mode: bool = False,
) -> SmartHomeEnvironment:
    if db is None:
        db = SmartHomeDB.load(SMART_HOME_DB_PATH)
    tools = SmartHomeTools(db)
    if user_db is None:
        user_db = SmartHomeUserDB.load(SMART_HOME_USER_DB_PATH)
    user_tools = SmartHomeUserTools(user_db)
    policy = load_file(SMART_HOME_POLICY_PATH)
    env = SmartHomeEnvironment(
        domain_name="smart_home",
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def load_tasks(path: str) -> list[Task]:
    """Load tasks from a JSON file."""
    tasks = load_file(path)
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    return [Task.model_validate(task) for task in tasks]


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    if not SMART_HOME_TASK_SET_PATH.exists():
        return []
    tasks = load_tasks(SMART_HOME_TASK_SET_PATH)
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_splits is None or task_split_name not in task_splits:
        # No splits defined — return all tasks
        return tasks
    return [task for task in tasks if task.id in task_splits[task_split_name]]


def get_tasks_split() -> Optional[dict[str, list[str]]]:
    split_file = Path(SMART_HOME_TASK_SET_PATH).parent / f"split_{Path(SMART_HOME_TASK_SET_PATH).stem}.json"
    if split_file.exists():
        return load_file(split_file)
    return None
