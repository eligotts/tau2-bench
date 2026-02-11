from typing import Any, Dict, List, Optional

from tau2.domains.smart_home.data_model import Device, SmartHomeDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class SmartHomeTools(ToolKitBase):
    """Tools available to the assistant for smart home support."""

    db: SmartHomeDB

    def __init__(self, db: SmartHomeDB):
        super().__init__(db)

    # --- Public tools (agent-facing) ---

    @is_tool(ToolType.READ)
    def get_user_by_name(self, name: str) -> Dict[str, Any]:
        """
        Look up a user by their name.

        Args:
            name: The full name of the user (e.g., 'Alice Johnson').

        Returns:
            User details including user_id and device_ids.
        """
        user = self._find_user_by_name(name)
        if user is None:
            raise ValueError(f"User with name '{name}' not found.")
        return user.model_dump()

    @is_tool(ToolType.READ)
    def get_device(self, device_id: str) -> Dict[str, Any]:
        """
        Get details of a specific smart home device.

        Args:
            device_id: The unique identifier of the device.

        Returns:
            Device details including status and settings.
        """
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        return device.model_dump()

    @is_tool(ToolType.READ)
    def list_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all devices for a given user.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            List of device details.
        """
        user = self._find_user(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found.")
        devices = [
            d.model_dump() for d in self.db.devices if d.device_id in user.device_ids
        ]
        return devices

    @is_tool(ToolType.WRITE)
    def update_device_setting(
        self, device_id: str, setting_name: str, setting_value: Any
    ) -> str:
        """
        Update a setting on a smart home device.

        Args:
            device_id: The unique identifier of the device.
            setting_name: The name of the setting to update (e.g., 'mode', 'target_temp', 'on', 'brightness').
            setting_value: The new value for the setting.

        Returns:
            Confirmation message.
        """
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        if device.status != "online":
            raise ValueError(f"Device {device_id} is {device.status}. Cannot update settings.")
        device.settings[setting_name] = setting_value
        return f"Updated {setting_name} to {setting_value} on device {device_id}."

    @is_tool(ToolType.WRITE)
    def reboot_device(self, device_id: str) -> str:
        """
        Reboot a smart home device. This will bring an offline device back online if possible.

        Args:
            device_id: The unique identifier of the device to reboot.

        Returns:
            Result of the reboot attempt.
        """
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        # Reboot sets device online (whether sync respects this depends on responsiveness)
        device.status = "online"
        return f"Device {device_id} rebooted successfully."

    @is_tool(ToolType.WRITE)
    def transfer_to_human(self, summary: str) -> str:
        """
        Transfer the conversation to a human agent.

        Args:
            summary: A summary of the issue for the human agent.

        Returns:
            Confirmation of transfer.
        """
        return f"Transferred to human agent. Summary: {summary}"

    @is_tool(ToolType.READ)
    def check_device_logs(self, device_id: str) -> Dict[str, Any]:
        """
        Check diagnostic logs for a device. Returns connection history, error codes, and last reboot time.

        Args:
            device_id: The unique identifier of the device.

        Returns:
            Diagnostic information including connection history, errors, and firmware version.
        """
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        errors = []
        if device.status == "offline":
            errors.append("CONNECTION_LOST")
        if device.status == "updating":
            errors.append("FIRMWARE_UPDATE_IN_PROGRESS")
        if device.firmware_version < "2.1.0":
            errors.append("OUTDATED_FIRMWARE")
        if not device.connected_to_hub:
            errors.append("HUB_DISCONNECTED")
        return {
            "device_id": device.device_id,
            "status": device.status,
            "firmware_version": device.firmware_version,
            "connected_to_hub": device.connected_to_hub,
            "error_codes": errors,
            "last_reboot": "2024-01-15T10:30:00Z",
            "connection_history": [
                {"event": "connected", "timestamp": "2024-01-15T10:30:00Z"},
            ],
        }

    @is_tool(ToolType.WRITE)
    def update_device_firmware(self, device_id: str) -> str:
        """
        Update firmware on a device. The device will enter 'updating' status and become
        unresponsive until the user physically power-cycles it.

        Args:
            device_id: The unique identifier of the device to update.

        Returns:
            Status message with instructions for the user.
        """
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        device.status = "updating"
        device.firmware_version = "2.2.0"
        return (
            f"Firmware update initiated on device {device_id}. "
            f"Device is now updating. Please ask the user to power-cycle the device "
            f"once the update indicator light stops blinking."
        )

    @is_tool(ToolType.WRITE)
    def reset_device_to_defaults(self, device_id: str) -> str:
        """
        Factory reset a device to its default settings. This wipes all custom configuration.

        Args:
            device_id: The unique identifier of the device to reset.

        Returns:
            Confirmation message.
        """
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        if device.device_type == "thermostat":
            device.settings = {"mode": "heat", "target_temp": 72, "fan": "auto"}
        elif device.device_type == "light":
            device.settings = {"on": True, "brightness": 100, "color": "warm_white"}
        else:
            device.settings = {}
        device.status = "online"
        device.connected_to_hub = True
        return f"Device {device_id} has been reset to factory defaults."

    @is_tool(ToolType.READ)
    def check_home_network(self, user_id: str) -> Dict[str, Any]:
        """
        Check the home network status including WiFi and smart hub.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            Network health information.
        """
        user = self._find_user(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found.")
        devices_online = sum(1 for d in self.db.devices if d.status == "online" and d.device_id in user.device_ids)
        devices_total = sum(1 for d in self.db.devices if d.device_id in user.device_ids)
        return {
            "hub_status": self.db.hub_status,
            "devices_online": devices_online,
            "devices_total": devices_total,
            "network_health": "good" if self.db.hub_status == "online" and devices_online == devices_total else "degraded",
        }

    @is_tool(ToolType.WRITE)
    def restart_hub(self) -> str:
        """
        Restart the smart home hub from the backend. The hub will briefly go to 'restarting'
        then come back 'online'.

        Returns:
            Result of the hub restart.
        """
        self.db.hub_status = "online"
        # Reconnect all hub-connected devices
        for device in self.db.devices:
            if device.connected_to_hub and device.status == "offline":
                device.status = "online"
        return "Smart hub has been restarted successfully. All hub-connected devices are reconnecting."

    # --- Assertion methods (not tools) ---

    def assert_device_setting(
        self, device_id: str, setting_name: str, expected_value: Any
    ) -> bool:
        """Assert that a device setting matches the expected value."""
        device = self._find_device(device_id)
        if device is None:
            return False
        actual = device.settings.get(setting_name)
        return actual == expected_value

    def assert_device_status(self, device_id: str, expected_status: str) -> bool:
        """Assert that a device has the expected status."""
        device = self._find_device(device_id)
        if device is None:
            return False
        return device.status == expected_status

    def assert_hub_status(self, expected: str) -> bool:
        """Assert that the hub has the expected status."""
        return self.db.hub_status == expected

    def assert_device_firmware(self, device_id: str, expected: str) -> bool:
        """Assert that a device has the expected firmware version."""
        device = self._find_device(device_id)
        if device is None:
            return False
        return device.firmware_version == expected

    # --- Internal helpers (not tools) ---

    def set_device_status(self, device_id: str, status: str) -> None:
        """Set device status directly (for scenario setup)."""
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        device.status = status

    def set_device_setting(
        self, device_id: str, setting_name: str, setting_value: Any
    ) -> None:
        """Set a device setting directly (for scenario setup)."""
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        device.settings[setting_name] = setting_value

    def set_hub_status(self, status: str) -> None:
        """Set hub status directly (for scenario setup)."""
        self.db.hub_status = status

    def set_device_firmware(self, device_id: str, version: str) -> None:
        """Set device firmware version directly (for scenario setup)."""
        device = self._find_device(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found.")
        device.firmware_version = version

    def _find_device(self, device_id: str) -> Optional[Device]:
        for d in self.db.devices:
            if d.device_id == device_id:
                return d
        return None

    def _find_user(self, user_id: str):
        for u in self.db.users:
            if u.user_id == user_id:
                return u
        return None

    def _find_user_by_name(self, name: str):
        for u in self.db.users:
            if u.name == name:
                return u
        return None
