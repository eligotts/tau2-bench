import unittest

from tau2.domains.smart_home.user_data_model import SmartHomeUserDB
from tau2.domains.smart_home.user_tools import SmartHomeUserTools
from tau2.domains.smart_home.utils import SMART_HOME_USER_DB_PATH


class TestSmartHomeUserTools(unittest.TestCase):
    def setUp(self):
        self.db = SmartHomeUserDB.load(SMART_HOME_USER_DB_PATH)
        self.tools = SmartHomeUserTools(self.db)

    def test_check_room_temperature(self):
        result = self.tools.check_room_temperature("living_room")
        self.assertIn("72.0", result)

    def test_check_room_temperature_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_room_temperature("garage")

    def test_check_light_on(self):
        result = self.tools.check_light("living_room")
        self.assertIn("on", result)
        self.assertIn("100%", result)

    def test_check_light_off(self):
        self.tools.set_light_state("living_room", False, 0)
        result = self.tools.check_light("living_room")
        self.assertIn("off", result)

    def test_press_device_button_responsive(self):
        result = self.tools.press_device_button("D001")
        self.assertIn("Button pressed", result)

    def test_press_device_button_unresponsive(self):
        self.tools.set_device_responsive("D001", False)
        result = self.tools.press_device_button("D001")
        self.assertIn("not responding", result)

    def test_set_user_info(self):
        self.tools.set_user_info("Test User", "UTEST")
        self.assertEqual(self.db.user_name, "Test User")
        self.assertEqual(self.db.user_id, "UTEST")

    def test_set_room_temperature(self):
        self.tools.set_room_temperature("living_room", 55.0)
        room = self.db.rooms["living_room"]
        self.assertEqual(room.temperature, 55.0)

    def test_set_light_state(self):
        self.tools.set_light_state("bedroom", False, 0)
        room = self.db.rooms["bedroom"]
        self.assertFalse(room.lights_on)
        self.assertEqual(room.light_brightness, 0)

    def test_set_device_responsive(self):
        self.tools.set_device_responsive("D001", False)
        self.assertFalse(self.db.device_responsiveness["D001"])

    def test_assert_room_temp_in_range(self):
        self.assertTrue(self.tools.assert_room_temp_in_range("living_room", 70.0, 75.0))
        self.assertFalse(self.tools.assert_room_temp_in_range("living_room", 75.0, 80.0))

    def test_assert_light_state(self):
        self.assertTrue(self.tools.assert_light_state("living_room", True, 100))
        self.assertFalse(self.tools.assert_light_state("living_room", False))

    # --- New tool tests ---

    def test_power_cycle_device(self):
        self.tools.set_device_indicator("D001", "red")
        self.tools.set_device_responsive("D001", False)
        result = self.tools.power_cycle_device("D001")
        self.assertIn("power cycled successfully", result)
        self.assertIn("green", result)
        self.assertEqual(self.db.device_indicator["D001"], "green")
        self.assertTrue(self.db.device_responsiveness["D001"])

    def test_power_cycle_device_no_power(self):
        self.tools.set_device_power("D001", False)
        result = self.tools.power_cycle_device("D001")
        self.assertIn("no power", result)

    def test_power_cycle_device_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.power_cycle_device("DXXX")

    def test_restart_router(self):
        self.tools.set_wifi_connected(False)
        result = self.tools.restart_router()
        self.assertIn("WiFi router restarted", result)
        self.assertTrue(self.db.wifi_connected)

    def test_check_device_indicator_green(self):
        result = self.tools.check_device_indicator("D001")
        self.assertIn("green", result)
        self.assertIn("OK", result)

    def test_check_device_indicator_red(self):
        self.tools.set_device_indicator("D001", "red")
        result = self.tools.check_device_indicator("D001")
        self.assertIn("red", result)
        self.assertIn("Error", result)

    def test_check_device_indicator_blinking(self):
        self.tools.set_device_indicator("D001", "blinking")
        result = self.tools.check_device_indicator("D001")
        self.assertIn("blinking", result)
        self.assertIn("Updating", result)

    def test_check_device_indicator_no_power(self):
        self.tools.set_device_power("D001", False)
        result = self.tools.check_device_indicator("D001")
        self.assertIn("off", result)
        self.assertIn("no power", result)

    def test_check_device_indicator_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_device_indicator("DXXX")

    def test_run_system_diagnostic_healthy(self):
        result = self.tools.run_system_diagnostic()
        self.assertTrue(result["wifi_connected"])
        self.assertTrue(result["hub_online"])
        self.assertEqual(result["devices_online"], 6)
        self.assertEqual(result["devices_total"], 6)
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["status"], "healthy")

    def test_run_system_diagnostic_wifi_down(self):
        self.tools.set_wifi_connected(False)
        result = self.tools.run_system_diagnostic()
        self.assertFalse(result["wifi_connected"])
        self.assertIn("WiFi disconnected", result["alerts"])
        self.assertEqual(result["status"], "issues_detected")

    def test_run_system_diagnostic_hub_offline(self):
        self.tools.set_hub_online(False)
        result = self.tools.run_system_diagnostic()
        self.assertIn("Smart hub offline", result["alerts"])

    def test_run_system_diagnostic_device_unresponsive(self):
        self.tools.set_device_responsive("D001", False)
        result = self.tools.run_system_diagnostic()
        self.assertEqual(result["devices_online"], 5)
        self.assertAny_alert_contains(result["alerts"], "D001")

    def assertAny_alert_contains(self, alerts, text):
        self.assertTrue(any(text in a for a in alerts), f"No alert contains '{text}': {alerts}")

    def test_run_system_diagnostic_red_device(self):
        self.tools.set_device_indicator("D001", "red")
        result = self.tools.run_system_diagnostic()
        self.assertAny_alert_contains(result["alerts"], "D001")

    def test_verify_room_comfort_pass(self):
        result = self.tools.verify_room_comfort("living_room")
        self.assertIn("PASS", result)

    def test_verify_room_comfort_fail_temp(self):
        self.tools.set_room_temperature("living_room", 55.0)
        result = self.tools.verify_room_comfort("living_room")
        self.assertIn("FAIL", result)
        self.assertIn("Temperature", result)

    def test_verify_room_comfort_fail_lights(self):
        self.tools.set_light_state("living_room", False, 0)
        result = self.tools.verify_room_comfort("living_room")
        self.assertIn("FAIL", result)
        self.assertIn("Lights are off", result)

    def test_verify_room_comfort_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.verify_room_comfort("garage")

    def test_verify_room_comfort_normalizes_name(self):
        result = self.tools.verify_room_comfort("living room")
        self.assertIn("PASS", result)

    def test_set_wifi_connected(self):
        self.tools.set_wifi_connected(False)
        self.assertFalse(self.db.wifi_connected)
        self.tools.set_wifi_connected(True)
        self.assertTrue(self.db.wifi_connected)

    def test_set_hub_online(self):
        self.tools.set_hub_online(False)
        self.assertFalse(self.db.hub_online)
        self.tools.set_hub_online(True)
        self.assertTrue(self.db.hub_online)

    def test_set_device_power(self):
        self.tools.set_device_power("D001", False)
        self.assertFalse(self.db.device_power_state["D001"])

    def test_set_device_indicator(self):
        self.tools.set_device_indicator("D001", "red")
        self.assertEqual(self.db.device_indicator["D001"], "red")

    def test_assert_wifi_connected(self):
        self.assertTrue(self.tools.assert_wifi_connected(True))
        self.assertFalse(self.tools.assert_wifi_connected(False))

    def test_assert_hub_online(self):
        self.assertTrue(self.tools.assert_hub_online(True))
        self.assertFalse(self.tools.assert_hub_online(False))

    def test_assert_system_healthy(self):
        self.assertTrue(self.tools.assert_system_healthy())

    def test_assert_system_healthy_wifi_down(self):
        self.tools.set_wifi_connected(False)
        self.assertFalse(self.tools.assert_system_healthy())

    def test_assert_system_healthy_hub_down(self):
        self.tools.set_hub_online(False)
        self.assertFalse(self.tools.assert_system_healthy())

    def test_assert_system_healthy_red_indicator(self):
        self.tools.set_device_indicator("D001", "red")
        self.assertFalse(self.tools.assert_system_healthy())

    def test_user_db_has_new_fields(self):
        """Verify the user DB loads with new fields."""
        self.assertTrue(self.db.wifi_connected)
        self.assertTrue(self.db.hub_online)
        self.assertEqual(len(self.db.device_power_state), 6)
        self.assertEqual(len(self.db.device_indicator), 6)
        for did in ["D001", "D002", "D003", "D004", "D005", "D006"]:
            self.assertTrue(self.db.device_power_state[did])
            self.assertEqual(self.db.device_indicator[did], "green")

    def test_room_has_humidity(self):
        """Verify rooms have humidity field."""
        for room in self.db.rooms.values():
            self.assertEqual(room.humidity, 45.0)


if __name__ == "__main__":
    unittest.main()
