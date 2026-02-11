from typing import Dict, Optional

from tau2.domains.smart_home.user_data_model import SmartHomeUserDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class SmartHomeUserTools(ToolKitBase):
    """Tools available to the user (physical world interactions)."""

    db: SmartHomeUserDB

    def __init__(self, db: SmartHomeUserDB):
        super().__init__(db)

    def _normalize_room_name(self, room_name: str) -> str:
        """Normalize room name: 'living room' -> 'living_room'."""
        return room_name.strip().replace(" ", "_").lower()

    # --- Public tools (user-facing) ---

    @is_tool(ToolType.READ)
    def check_room_temperature(self, room_name: str) -> str:
        """
        Check the current temperature in a room.

        Args:
            room_name: The name of the room to check (e.g., 'living_room', 'bedroom', 'kitchen').

        Returns:
            Current temperature reading.
        """
        room_name = self._normalize_room_name(room_name)
        room = self.db.rooms.get(room_name)
        if room is None:
            raise ValueError(f"Room {room_name} not found. Available rooms: {list(self.db.rooms.keys())}")
        return f"The temperature in {room_name} is {room.temperature} degrees."

    @is_tool(ToolType.READ)
    def check_light(self, room_name: str) -> str:
        """
        Check the current light state in a room.

        Args:
            room_name: The name of the room to check (e.g., 'living_room', 'bedroom', 'kitchen').

        Returns:
            Current light state (on/off and brightness).
        """
        room_name = self._normalize_room_name(room_name)
        room = self.db.rooms.get(room_name)
        if room is None:
            raise ValueError(f"Room {room_name} not found. Available rooms: {list(self.db.rooms.keys())}")
        if not room.lights_on:
            return f"The lights in {room_name} are off."
        return f"The lights in {room_name} are on at {room.light_brightness}% brightness."

    @is_tool(ToolType.WRITE)
    def press_device_button(self, device_id: str) -> str:
        """
        Press a physical button on a device (e.g., manual override).

        Args:
            device_id: The device to interact with.

        Returns:
            Result of pressing the button.
        """
        responsive = self.db.device_responsiveness.get(device_id)
        if responsive is None:
            raise ValueError(f"Device {device_id} not found.")
        if not responsive:
            return f"Device {device_id} is not responding to physical input."
        return f"Button pressed on device {device_id}."

    @is_tool(ToolType.WRITE)
    def power_cycle_device(self, device_id: str) -> str:
        """
        Physically unplug and replug a device (power cycle). Returns the new indicator light color.
        Only works if the device has physical power (device_power_state is True).

        Args:
            device_id: The device to power cycle.

        Returns:
            Result of power cycling including new indicator color.
        """
        powered = self.db.device_power_state.get(device_id)
        if powered is None:
            raise ValueError(f"Device {device_id} not found.")
        if not powered:
            return f"Device {device_id} has no power. Cannot power cycle."
        # Power cycling resets the device indicator to green and makes it responsive
        self.db.device_indicator[device_id] = "green"
        self.db.device_responsiveness[device_id] = True
        self.db.device_needs_reset[device_id] = False
        return f"Device {device_id} power cycled successfully. Indicator light is now green."

    @is_tool(ToolType.WRITE)
    def restart_router(self) -> str:
        """
        Physically restart the WiFi router. This restores WiFi connectivity.

        Returns:
            Confirmation and diagnostic summary.
        """
        self.db.wifi_connected = True
        # Count devices that are now reachable
        online_count = sum(1 for v in self.db.device_responsiveness.values() if v)
        total_count = len(self.db.device_responsiveness)
        return (
            f"WiFi router restarted successfully. WiFi is now connected. "
            f"{online_count}/{total_count} devices responsive."
        )

    @is_tool(ToolType.READ)
    def check_device_indicator(self, device_id: str) -> str:
        """
        Check the LED indicator light on a physical device.

        Args:
            device_id: The device to check.

        Returns:
            Indicator color: green (OK), red (error), off (no power), blinking (updating).
        """
        powered = self.db.device_power_state.get(device_id)
        if powered is None:
            raise ValueError(f"Device {device_id} not found.")
        if not powered:
            return f"Device {device_id} indicator light is off (no power)."
        color = self.db.device_indicator.get(device_id, "green")
        color_meanings = {
            "green": "OK - device is functioning normally",
            "red": "Error - device has an issue",
            "blinking": "Updating - firmware update in progress",
            "off": "No power",
        }
        meaning = color_meanings.get(color, "Unknown status")
        return f"Device {device_id} indicator light is {color} ({meaning})."

    @is_tool(ToolType.READ)
    def run_system_diagnostic(self) -> Dict[str, object]:
        """
        Run a diagnostic from the phone app. Shows WiFi status, hub status,
        device counts, and any alerts.

        Returns:
            Diagnostic summary with WiFi status, hub status, device counts, and alerts.
        """
        alerts = []
        if not self.db.wifi_connected:
            alerts.append("WiFi disconnected")
        if not self.db.hub_online:
            alerts.append("Smart hub offline")
        offline_devices = [
            did for did, resp in self.db.device_responsiveness.items() if not resp
        ]
        if offline_devices:
            alerts.append(f"Unresponsive devices: {', '.join(offline_devices)}")
        red_devices = [
            did for did, color in self.db.device_indicator.items() if color == "red"
        ]
        if red_devices:
            alerts.append(f"Devices with errors: {', '.join(red_devices)}")

        online_count = sum(1 for v in self.db.device_responsiveness.values() if v)
        total_count = len(self.db.device_responsiveness)

        return {
            "wifi_connected": self.db.wifi_connected,
            "hub_online": self.db.hub_online,
            "devices_online": online_count,
            "devices_total": total_count,
            "alerts": alerts,
            "status": "healthy" if not alerts else "issues_detected",
        }

    @is_tool(ToolType.READ)
    def verify_room_comfort(self, room_name: str) -> str:
        """
        Check if a room meets comfort criteria: temperature between 68-76 degrees
        and lights on. Returns pass/fail with details.

        Args:
            room_name: The name of the room to verify.

        Returns:
            Comfort verification result with pass/fail and details.
        """
        room_name = self._normalize_room_name(room_name)
        room = self.db.rooms.get(room_name)
        if room is None:
            raise ValueError(f"Room {room_name} not found. Available rooms: {list(self.db.rooms.keys())}")
        issues = []
        if room.temperature < 68 or room.temperature > 76:
            issues.append(f"Temperature is {room.temperature} (expected 68-76)")
        if not room.lights_on:
            issues.append("Lights are off")
        if issues:
            return f"FAIL - {room_name} comfort check: {'; '.join(issues)}"
        return f"PASS - {room_name} is comfortable: {room.temperature} degrees, lights on at {room.light_brightness}% brightness."

    # --- Setup helpers (not tools) ---

    def set_user_info(self, name: str, user_id: str) -> None:
        """Set the user's identity info."""
        self.db.user_name = name
        self.db.user_id = user_id

    def set_room_temperature(self, room_name: str, temperature: float) -> None:
        """Set the temperature in a room."""
        room = self.db.rooms.get(room_name)
        if room is None:
            raise ValueError(f"Room {room_name} not found.")
        room.temperature = temperature

    def set_light_state(
        self, room_name: str, lights_on: bool, brightness: int = 100
    ) -> None:
        """Set the light state in a room."""
        room = self.db.rooms.get(room_name)
        if room is None:
            raise ValueError(f"Room {room_name} not found.")
        room.lights_on = lights_on
        room.light_brightness = brightness

    def set_device_responsive(self, device_id: str, responsive: bool) -> None:
        """Set whether a device is responsive to physical input."""
        self.db.device_responsiveness[device_id] = responsive

    def set_wifi_connected(self, connected: bool) -> None:
        """Set WiFi connection status."""
        self.db.wifi_connected = connected

    def set_hub_online(self, online: bool) -> None:
        """Set smart hub online status."""
        self.db.hub_online = online

    def set_device_power(self, device_id: str, powered: bool) -> None:
        """Set physical power state for a device."""
        self.db.device_power_state[device_id] = powered

    def set_device_indicator(self, device_id: str, color: str) -> None:
        """Set LED indicator color for a device."""
        self.db.device_indicator[device_id] = color

    def set_device_needs_reset(self, device_id: str, needs_reset: bool) -> None:
        """Set whether a device needs physical reset (power cycle)."""
        self.db.device_needs_reset[device_id] = needs_reset

    # --- Assertion methods (not tools) ---

    def assert_room_temp_in_range(
        self, room_name: str, min_temp: float, max_temp: float
    ) -> bool:
        """Assert that room temperature is within the expected range."""
        room = self.db.rooms.get(room_name)
        if room is None:
            return False
        return min_temp <= room.temperature <= max_temp

    def assert_light_state(
        self, room_name: str, expected_on: bool, expected_brightness: Optional[int] = None
    ) -> bool:
        """Assert that the light state matches expectations."""
        room = self.db.rooms.get(room_name)
        if room is None:
            return False
        if room.lights_on != expected_on:
            return False
        if expected_brightness is not None and room.light_brightness != expected_brightness:
            return False
        return True

    def assert_wifi_connected(self, expected: bool) -> bool:
        """Assert WiFi connection status."""
        return self.db.wifi_connected == expected

    def assert_hub_online(self, expected: bool) -> bool:
        """Assert smart hub online status."""
        return self.db.hub_online == expected

    def assert_system_healthy(self) -> bool:
        """Assert the system is healthy: WiFi up, hub online, all devices green, none need reset."""
        if not self.db.wifi_connected:
            return False
        if not self.db.hub_online:
            return False
        for device_id, color in self.db.device_indicator.items():
            if color != "green":
                return False
        for device_id, needs_reset in self.db.device_needs_reset.items():
            if needs_reset:
                return False
        return True
