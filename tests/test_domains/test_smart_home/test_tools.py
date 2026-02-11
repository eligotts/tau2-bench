import unittest

from tau2.domains.smart_home.data_model import SmartHomeDB
from tau2.domains.smart_home.tools import SmartHomeTools
from tau2.domains.smart_home.utils import SMART_HOME_DB_PATH


class TestSmartHomeTools(unittest.TestCase):
    def setUp(self):
        self.db = SmartHomeDB.load(SMART_HOME_DB_PATH)
        self.tools = SmartHomeTools(self.db)

    def test_get_device(self):
        result = self.tools.get_device("D001")
        self.assertEqual(result["device_id"], "D001")
        self.assertEqual(result["device_type"], "thermostat")
        self.assertEqual(result["room"], "living_room")

    def test_get_device_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.get_device("DXXX")

    def test_list_devices(self):
        devices = self.tools.list_devices("U001")
        self.assertEqual(len(devices), 6)

    def test_list_devices_subset(self):
        devices = self.tools.list_devices("U002")
        self.assertEqual(len(devices), 2)

    def test_list_devices_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.list_devices("UXXX")

    def test_update_device_setting(self):
        result = self.tools.update_device_setting("D001", "target_temp", 75)
        self.assertIn("Updated", result)
        device = self.tools.get_device("D001")
        self.assertEqual(device["settings"]["target_temp"], 75)

    def test_update_device_setting_offline(self):
        self.tools.set_device_status("D001", "offline")
        with self.assertRaises(ValueError):
            self.tools.update_device_setting("D001", "target_temp", 75)

    def test_reboot_device(self):
        self.tools.set_device_status("D001", "offline")
        result = self.tools.reboot_device("D001")
        self.assertIn("rebooted", result)
        device = self.tools.get_device("D001")
        self.assertEqual(device["status"], "online")

    def test_transfer_to_human(self):
        result = self.tools.transfer_to_human("Device broken")
        self.assertIn("Transferred", result)
        self.assertIn("Device broken", result)

    def test_assert_device_setting(self):
        self.assertTrue(
            self.tools.assert_device_setting("D001", "mode", "heat")
        )
        self.assertFalse(
            self.tools.assert_device_setting("D001", "mode", "cool")
        )

    def test_assert_device_status(self):
        self.assertTrue(self.tools.assert_device_status("D001", "online"))
        self.assertFalse(self.tools.assert_device_status("D001", "offline"))

    def test_set_device_setting_helper(self):
        self.tools.set_device_setting("D001", "target_temp", 55)
        device = self.tools.get_device("D001")
        self.assertEqual(device["settings"]["target_temp"], 55)

    def test_set_device_status_helper(self):
        self.tools.set_device_status("D001", "offline")
        self.assertTrue(self.tools.assert_device_status("D001", "offline"))

    # --- New tool tests ---

    def test_check_device_logs_online(self):
        result = self.tools.check_device_logs("D001")
        self.assertEqual(result["device_id"], "D001")
        self.assertEqual(result["status"], "online")
        self.assertEqual(result["firmware_version"], "2.1.0")
        self.assertTrue(result["connected_to_hub"])
        self.assertEqual(result["error_codes"], [])

    def test_check_device_logs_offline(self):
        self.tools.set_device_status("D001", "offline")
        result = self.tools.check_device_logs("D001")
        self.assertIn("CONNECTION_LOST", result["error_codes"])

    def test_check_device_logs_outdated_firmware(self):
        self.tools.set_device_firmware("D001", "1.0.0")
        result = self.tools.check_device_logs("D001")
        self.assertIn("OUTDATED_FIRMWARE", result["error_codes"])

    def test_check_device_logs_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_device_logs("DXXX")

    def test_update_device_firmware(self):
        result = self.tools.update_device_firmware("D001")
        self.assertIn("Firmware update initiated", result)
        device = self.tools.get_device("D001")
        self.assertEqual(device["status"], "updating")
        self.assertEqual(device["firmware_version"], "2.2.0")

    def test_update_device_firmware_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.update_device_firmware("DXXX")

    def test_reset_device_to_defaults_thermostat(self):
        self.tools.set_device_setting("D001", "mode", "cool")
        self.tools.set_device_setting("D001", "target_temp", 55)
        result = self.tools.reset_device_to_defaults("D001")
        self.assertIn("reset to factory defaults", result)
        device = self.tools.get_device("D001")
        self.assertEqual(device["settings"]["mode"], "heat")
        self.assertEqual(device["settings"]["target_temp"], 72)
        self.assertEqual(device["status"], "online")

    def test_reset_device_to_defaults_light(self):
        self.tools.set_device_setting("D002", "on", False)
        result = self.tools.reset_device_to_defaults("D002")
        self.assertIn("reset to factory defaults", result)
        device = self.tools.get_device("D002")
        self.assertTrue(device["settings"]["on"])
        self.assertEqual(device["settings"]["brightness"], 100)

    def test_check_home_network(self):
        result = self.tools.check_home_network("U001")
        self.assertEqual(result["hub_status"], "online")
        self.assertEqual(result["devices_total"], 6)
        self.assertEqual(result["devices_online"], 6)
        self.assertEqual(result["network_health"], "good")

    def test_check_home_network_degraded(self):
        self.tools.set_device_status("D001", "offline")
        result = self.tools.check_home_network("U001")
        self.assertEqual(result["network_health"], "degraded")

    def test_check_home_network_user_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_home_network("UXXX")

    def test_restart_hub(self):
        self.tools.set_hub_status("offline")
        self.tools.set_device_status("D001", "offline")
        result = self.tools.restart_hub()
        self.assertIn("restarted successfully", result)
        self.assertEqual(self.db.hub_status, "online")
        # Hub-connected offline devices should come back online
        device = self.tools.get_device("D001")
        self.assertEqual(device["status"], "online")

    def test_assert_hub_status(self):
        self.assertTrue(self.tools.assert_hub_status("online"))
        self.assertFalse(self.tools.assert_hub_status("offline"))

    def test_assert_device_firmware(self):
        self.assertTrue(self.tools.assert_device_firmware("D001", "2.1.0"))
        self.assertFalse(self.tools.assert_device_firmware("D001", "1.0.0"))

    def test_set_hub_status(self):
        self.tools.set_hub_status("offline")
        self.assertEqual(self.db.hub_status, "offline")

    def test_set_device_firmware(self):
        self.tools.set_device_firmware("D001", "1.0.0")
        device = self.tools.get_device("D001")
        self.assertEqual(device["firmware_version"], "1.0.0")

    def test_device_has_firmware_version(self):
        device = self.tools.get_device("D001")
        self.assertEqual(device["firmware_version"], "2.1.0")

    def test_device_has_connected_to_hub(self):
        device = self.tools.get_device("D001")
        self.assertTrue(device["connected_to_hub"])

    def test_db_has_hub_status(self):
        self.assertEqual(self.db.hub_status, "online")


if __name__ == "__main__":
    unittest.main()
