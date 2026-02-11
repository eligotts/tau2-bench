import unittest

from tau2.domains.smart_home.environment import SmartHomeEnvironment, get_environment


class TestSmartHomeEnvironment(unittest.TestCase):
    def setUp(self):
        self.env = get_environment()

    def test_environment_creation(self):
        self.assertIsInstance(self.env, SmartHomeEnvironment)
        self.assertEqual(self.env.domain_name, "smart_home")

    def test_sync_thermostat_to_room(self):
        """Thermostat target_temp should sync to room temperature."""
        self.env.tools.set_device_setting("D001", "target_temp", 75)
        self.env.sync_tools()
        room = self.env.user_tools.db.rooms["living_room"]
        self.assertEqual(room.temperature, 75.0)

    def test_sync_thermostat_off_no_change(self):
        """Thermostat in 'off' mode should not change room temp during sync."""
        self.env.tools.set_device_setting("D001", "mode", "off")
        # Manually set room temp to something different
        self.env.user_tools.set_room_temperature("living_room", 58.0)
        self.env.sync_tools()
        room = self.env.user_tools.db.rooms["living_room"]
        # Should remain 58 since thermostat is off
        self.assertEqual(room.temperature, 58.0)

    def test_sync_light_on(self):
        """Light on/brightness should sync to room state."""
        self.env.tools.set_device_setting("D002", "brightness", 50)
        self.env.sync_tools()
        room = self.env.user_tools.db.rooms["living_room"]
        self.assertEqual(room.light_brightness, 50)
        self.assertTrue(room.lights_on)

    def test_sync_light_off(self):
        """Light turned off should sync to room state."""
        self.env.tools.set_device_setting("D002", "on", False)
        self.env.sync_tools()
        room = self.env.user_tools.db.rooms["living_room"]
        self.assertFalse(room.lights_on)

    def test_offline_device_no_sync(self):
        """Offline device should not affect room state."""
        self.env.tools.set_device_status("D001", "offline")
        self.env.tools.set_device_setting("D001", "target_temp", 99)
        self.env.user_tools.set_room_temperature("living_room", 60.0)
        self.env.sync_tools()
        room = self.env.user_tools.db.rooms["living_room"]
        # Room temp should NOT change to 99 since device is offline
        self.assertEqual(room.temperature, 60.0)

    def test_offline_device_gets_red_indicator(self):
        """Offline device should get red indicator from sync."""
        self.env.tools.set_device_status("D001", "offline")
        self.env.sync_tools()
        self.assertEqual(self.env.user_tools.db.device_indicator["D001"], "red")
        self.assertFalse(self.env.user_tools.db.device_responsiveness["D001"])

    def test_reboot_brings_device_online_and_syncs(self):
        """Rebooting an offline device brings it online and syncs."""
        self.env.tools.set_device_status("D001", "offline")
        self.env.user_tools.set_room_temperature("living_room", 58.0)
        self.env.sync_tools()
        # Room should still be 58 since device is offline
        self.assertEqual(self.env.user_tools.db.rooms["living_room"].temperature, 58.0)

        # Reboot
        self.env.tools.reboot_device("D001")
        self.env.sync_tools()
        # Now room should sync to thermostat target (72)
        self.assertEqual(self.env.user_tools.db.rooms["living_room"].temperature, 72.0)

    def test_tool_call_via_environment(self):
        """Test making tool calls through the environment interface."""
        result = self.env.use_tool("get_device", device_id="D001")
        self.assertEqual(result["device_id"], "D001")

    def test_user_tool_call_via_environment(self):
        """Test making user tool calls through the environment interface."""
        result = self.env.use_user_tool("check_room_temperature", room_name="living_room")
        self.assertIn("72.0", result)

    # --- WiFi sync tests ---

    def test_wifi_down_all_devices_unresponsive(self):
        """When WiFi is down, all devices should become unresponsive."""
        self.env.user_tools.set_wifi_connected(False)
        self.env.sync_tools()
        for device in self.env.tools.db.devices:
            self.assertFalse(
                self.env.user_tools.db.device_responsiveness[device.device_id],
                f"Device {device.device_id} should be unresponsive when WiFi is down",
            )
            self.assertEqual(
                self.env.user_tools.db.device_indicator[device.device_id], "red",
                f"Device {device.device_id} indicator should be red when WiFi is down",
            )

    def test_wifi_down_no_room_sync(self):
        """When WiFi is down, thermostat changes should not sync to room."""
        self.env.user_tools.set_wifi_connected(False)
        self.env.tools.set_device_setting("D001", "target_temp", 99)
        self.env.user_tools.set_room_temperature("living_room", 60.0)
        self.env.sync_tools()
        room = self.env.user_tools.db.rooms["living_room"]
        self.assertEqual(room.temperature, 60.0)

    def test_wifi_restored_devices_auto_recover(self):
        """When WiFi is restored, online devices should auto-recover."""
        self.env.user_tools.set_wifi_connected(False)
        self.env.sync_tools()
        # All devices should be unresponsive with red indicators
        for device in self.env.tools.db.devices:
            self.assertFalse(self.env.user_tools.db.device_responsiveness[device.device_id])

        # Restore WiFi - devices should auto-recover via Rule 4
        self.env.user_tools.set_wifi_connected(True)
        self.env.sync_tools()
        for device in self.env.tools.db.devices:
            if device.status == "online" and device.connected_to_hub:
                self.assertTrue(
                    self.env.user_tools.db.device_responsiveness[device.device_id],
                )
                self.assertEqual(
                    self.env.user_tools.db.device_indicator[device.device_id], "green",
                )

    # --- Hub sync tests ---

    def test_hub_offline_devices_unresponsive(self):
        """When hub is offline, hub-connected devices should become unresponsive."""
        self.env.tools.set_hub_status("offline")
        self.env.sync_tools()
        for device in self.env.tools.db.devices:
            if device.connected_to_hub:
                self.assertFalse(
                    self.env.user_tools.db.device_responsiveness[device.device_id],
                )
                self.assertEqual(
                    self.env.user_tools.db.device_indicator[device.device_id], "red",
                )

    def test_hub_offline_sets_devices_offline(self):
        """When hub is offline, hub-connected devices should be set to offline status."""
        self.env.tools.set_hub_status("offline")
        self.env.sync_tools()
        for device in self.env.tools.db.devices:
            if device.connected_to_hub:
                self.assertEqual(device.status, "offline")

    def test_hub_restored_devices_recover(self):
        """When hub comes back online, devices should auto-recover."""
        self.env.tools.set_hub_status("offline")
        self.env.sync_tools()
        # Restart hub - brings devices back online
        self.env.tools.restart_hub()
        self.env.sync_tools()
        # Rule 4: online devices auto-restore
        for device in self.env.tools.db.devices:
            if device.connected_to_hub and device.status == "online":
                self.assertTrue(
                    self.env.user_tools.db.device_responsiveness[device.device_id],
                )
                self.assertEqual(
                    self.env.user_tools.db.device_indicator[device.device_id], "green",
                )

    def test_hub_online_syncs_to_user_db(self):
        """Hub status should sync to user_tools.db.hub_online."""
        self.env.tools.set_hub_status("offline")
        self.env.sync_tools()
        self.assertFalse(self.env.user_tools.db.hub_online)
        self.env.tools.set_hub_status("online")
        # Bring devices back online
        for device in self.env.tools.db.devices:
            device.status = "online"
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.hub_online)

    # --- Device updating sync tests ---

    def test_updating_device_unresponsive(self):
        """Device in 'updating' status should become unresponsive with blinking indicator."""
        self.env.tools.update_device_firmware("D001")
        self.env.sync_tools()
        self.assertFalse(self.env.user_tools.db.device_responsiveness["D001"])
        self.assertEqual(self.env.user_tools.db.device_indicator["D001"], "blinking")

    def test_updating_device_no_room_sync(self):
        """Updating device should not sync to room."""
        self.env.user_tools.set_room_temperature("living_room", 60.0)
        self.env.tools.update_device_firmware("D001")
        self.env.sync_tools()
        room = self.env.user_tools.db.rooms["living_room"]
        self.assertEqual(room.temperature, 60.0)

    def test_reboot_after_update_restores(self):
        """After firmware update, rebooting should restore the device."""
        self.env.tools.update_device_firmware("D001")
        self.env.sync_tools()
        # Reboot brings device back to online
        self.env.tools.reboot_device("D001")
        self.env.sync_tools()
        # Rule 4: online device auto-restores
        self.assertTrue(self.env.user_tools.db.device_responsiveness["D001"])
        self.assertEqual(self.env.user_tools.db.device_indicator["D001"], "green")

    # --- Online device auto-restore tests ---

    def test_online_device_auto_restores(self):
        """Online hub-connected device should automatically get green indicator."""
        self.env.sync_tools()
        self.assertEqual(self.env.user_tools.db.device_indicator["D001"], "green")
        self.assertTrue(self.env.user_tools.db.device_responsiveness["D001"])


if __name__ == "__main__":
    unittest.main()
