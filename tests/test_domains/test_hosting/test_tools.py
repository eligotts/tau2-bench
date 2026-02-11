import unittest

from tau2.domains.hosting.data_model import HostingDB
from tau2.domains.hosting.tools import HostingTools
from tau2.domains.hosting.utils import HOSTING_DB_PATH


class TestHostingTools(unittest.TestCase):
    def setUp(self):
        self.db = HostingDB.load(HOSTING_DB_PATH)
        self.tools = HostingTools(self.db)

    # --- READ tool tests ---

    def test_get_account_info(self):
        result = self.tools.get_account_info("ACC001")
        self.assertEqual(result["account_id"], "ACC001")
        self.assertEqual(result["owner_name"], "Maria Chen")
        self.assertEqual(result["domain"], "mybusiness.com")

    def test_get_account_info_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.get_account_info("ACCXXX")

    def test_check_server_status(self):
        result = self.tools.check_server_status("SRV001")
        self.assertEqual(result["server_id"], "SRV001")
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["server_software"], "nginx")
        self.assertEqual(result["port"], 443)

    def test_check_server_status_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_server_status("SRVXXX")

    def test_check_server_logs(self):
        result = self.tools.check_server_logs("SRV001")
        self.assertEqual(result["server_id"], "SRV001")
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["error_log"], [])

    def test_check_server_logs_crashed(self):
        self.tools.set_server_status("SRV001", "crashed")
        result = self.tools.check_server_logs("SRV001")
        self.assertIn("recommendation", result)
        self.assertIn("crashed", result["recommendation"].lower())

    def test_check_server_logs_wrong_port(self):
        self.tools.set_server_port("SRV001", 8080)
        result = self.tools.check_server_logs("SRV001")
        self.assertIn("warning", result)

    def test_check_server_logs_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_server_logs("SRVXXX")

    def test_check_database_status(self):
        result = self.tools.check_database_status("DB001")
        self.assertEqual(result["db_id"], "DB001")
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["max_connections"], 100)

    def test_check_database_status_connection_limit(self):
        self.tools.set_database_connections("DB001", 100, 100)
        result = self.tools.check_database_status("DB001")
        self.assertIn("warning", result)

    def test_check_database_status_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_database_status("DBXXX")

    def test_check_dns_records(self):
        records = self.tools.check_dns_records("mybusiness.com")
        self.assertEqual(len(records), 2)
        record_types = {r["record_type"] for r in records}
        self.assertIn("A", record_types)
        self.assertIn("MX", record_types)

    def test_check_dns_records_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_dns_records("unknown.com")

    def test_check_ssl_status(self):
        result = self.tools.check_ssl_status("mybusiness.com")
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["issuer"], "Let's Encrypt")

    def test_check_ssl_status_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_ssl_status("unknown.com")

    def test_check_deployment_status(self):
        result = self.tools.check_deployment_status("DEP001")
        self.assertEqual(result["version"], "3.2.1")
        self.assertEqual(result["status"], "active")

    def test_check_deployment_status_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.check_deployment_status("DEPXXX")

    # --- WRITE tool tests ---

    def test_restart_web_server(self):
        self.tools.set_server_status("SRV001", "crashed")
        result = self.tools.restart_web_server("SRV001")
        self.assertIn("restarted", result)
        server = self.tools.check_server_status("SRV001")
        self.assertEqual(server["status"], "running")

    def test_restart_web_server_clears_errors(self):
        self.tools.set_server_error_log("SRV001", ["error1", "error2"])
        self.tools.restart_web_server("SRV001")
        server = self.tools.check_server_status("SRV001")
        self.assertEqual(server["error_log"], [])

    def test_restart_database(self):
        self.tools.set_database_status("DB001", "crashed")
        result = self.tools.restart_database("DB001")
        self.assertIn("restarted", result)
        db = self.tools.check_database_status("DB001")
        self.assertEqual(db["status"], "running")
        self.assertEqual(db["current_connections"], 0)

    def test_update_dns_record(self):
        result = self.tools.update_dns_record("DNS001", "198.51.100.99")
        self.assertIn("updated", result)
        records = self.tools.check_dns_records("mybusiness.com")
        a_record = [r for r in records if r["record_type"] == "A"][0]
        self.assertEqual(a_record["value"], "198.51.100.99")

    def test_update_dns_record_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.update_dns_record("DNSXXX", "1.2.3.4")

    def test_renew_ssl_certificate(self):
        self.tools.set_ssl_status("mybusiness.com", "expired")
        result = self.tools.renew_ssl_certificate("mybusiness.com")
        self.assertIn("renewed", result)
        ssl = self.tools.check_ssl_status("mybusiness.com")
        self.assertEqual(ssl["status"], "valid")

    def test_renew_ssl_certificate_not_found(self):
        with self.assertRaises(ValueError):
            self.tools.renew_ssl_certificate("unknown.com")

    def test_rollback_deployment(self):
        self.tools.set_deployment_status("DEP001", "failed")
        result = self.tools.rollback_deployment("DEP001")
        self.assertIn("rolled back", result)
        dep = self.tools.check_deployment_status("DEP001")
        self.assertEqual(dep["status"], "active")
        self.assertEqual(dep["version"], "3.2.0")

    def test_update_server_config_port(self):
        result = self.tools.update_server_config("SRV001", "port", 8080)
        self.assertIn("updated", result)
        server = self.tools.check_server_status("SRV001")
        self.assertEqual(server["port"], 8080)

    def test_update_server_config_invalid_setting(self):
        with self.assertRaises(ValueError):
            self.tools.update_server_config("SRV001", "invalid", "value")

    def test_increase_db_connections(self):
        result = self.tools.increase_db_connections("DB001", 200)
        self.assertIn("increased", result)
        db = self.tools.check_database_status("DB001")
        self.assertEqual(db["max_connections"], 200)

    def test_clear_server_cache(self):
        result = self.tools.clear_server_cache("SRV001")
        self.assertIn("cleared", result)

    def test_clear_server_cache_not_running(self):
        self.tools.set_server_status("SRV001", "stopped")
        with self.assertRaises(ValueError):
            self.tools.clear_server_cache("SRV001")

    def test_transfer_to_human(self):
        result = self.tools.transfer_to_human("Server issue")
        self.assertIn("Transferred", result)
        self.assertIn("Server issue", result)

    # --- Assertion tests ---

    def test_assert_server_running(self):
        self.assertTrue(self.tools.assert_server_running("SRV001"))
        self.tools.set_server_status("SRV001", "crashed")
        self.assertFalse(self.tools.assert_server_running("SRV001"))

    def test_assert_database_running(self):
        self.assertTrue(self.tools.assert_database_running("DB001"))
        self.tools.set_database_status("DB001", "crashed")
        self.assertFalse(self.tools.assert_database_running("DB001"))

    def test_assert_dns_correct(self):
        self.assertTrue(self.tools.assert_dns_correct("DNS001", "203.0.113.10"))
        self.assertFalse(self.tools.assert_dns_correct("DNS001", "1.2.3.4"))

    def test_assert_ssl_valid(self):
        self.assertTrue(self.tools.assert_ssl_valid("mybusiness.com"))
        self.tools.set_ssl_status("mybusiness.com", "expired")
        self.assertFalse(self.tools.assert_ssl_valid("mybusiness.com"))

    def test_assert_deployment_active(self):
        self.assertTrue(self.tools.assert_deployment_active("DEP001"))
        self.tools.set_deployment_status("DEP001", "failed")
        self.assertFalse(self.tools.assert_deployment_active("DEP001"))

    def test_assert_server_port(self):
        self.assertTrue(self.tools.assert_server_port("SRV001", 443))
        self.assertFalse(self.tools.assert_server_port("SRV001", 8080))

    # --- Helper tests ---

    def test_set_server_status(self):
        self.tools.set_server_status("SRV001", "stopped")
        self.assertTrue(self.tools.assert_server_running("SRV001") is False)

    def test_set_server_error_log(self):
        self.tools.set_server_error_log("SRV001", ["err1"])
        logs = self.tools.check_server_logs("SRV001")
        self.assertEqual(logs["error_log"], ["err1"])

    def test_set_server_port(self):
        self.tools.set_server_port("SRV001", 8080)
        server = self.tools.check_server_status("SRV001")
        self.assertEqual(server["port"], 8080)

    def test_set_database_connections(self):
        self.tools.set_database_connections("DB001", 50, 200)
        db = self.tools.check_database_status("DB001")
        self.assertEqual(db["current_connections"], 50)
        self.assertEqual(db["max_connections"], 200)

    def test_set_dns_value(self):
        self.tools.set_dns_value("DNS001", "1.2.3.4")
        self.assertTrue(self.tools.assert_dns_correct("DNS001", "1.2.3.4"))

    def test_set_ssl_status(self):
        self.tools.set_ssl_status("mybusiness.com", "expired")
        self.assertFalse(self.tools.assert_ssl_valid("mybusiness.com"))

    def test_set_deployment_status(self):
        self.tools.set_deployment_status("DEP001", "failed")
        self.assertFalse(self.tools.assert_deployment_active("DEP001"))


if __name__ == "__main__":
    unittest.main()
