import unittest

from tau2.domains.hosting.environment import HostingEnvironment, get_environment


class TestHostingEnvironment(unittest.TestCase):
    def setUp(self):
        self.env = get_environment()

    def test_environment_creation(self):
        self.assertIsInstance(self.env, HostingEnvironment)
        self.assertEqual(self.env.domain_name, "hosting")

    # --- DNS sync tests ---

    def test_sync_dns_correct_site_loads(self):
        """When DNS A record is correct, site should load."""
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertTrue(ws.loads_successfully)
        self.assertIsNone(ws.error_code)

    def test_sync_dns_wrong_ip_site_fails(self):
        """When DNS A record points to wrong IP, site should fail with dns_error."""
        self.env.tools.set_dns_value("DNS001", "198.51.100.99")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertFalse(ws.loads_successfully)
        self.assertEqual(ws.error_code, "dns_error")
        self.assertFalse(self.env.user_tools.db.dns_resolves)

    def test_sync_dns_fixed_restores_site(self):
        """Fixing DNS should restore the site."""
        self.env.tools.set_dns_value("DNS001", "198.51.100.99")
        self.env.sync_tools()
        self.assertFalse(self.env.user_tools.db.website.loads_successfully)

        self.env.tools.set_dns_value("DNS001", "203.0.113.10")
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.website.loads_successfully)
        self.assertTrue(self.env.user_tools.db.dns_resolves)

    # --- SSL sync tests ---

    def test_sync_ssl_expired_shows_warning(self):
        """Expired SSL should show warning but site still loads."""
        self.env.tools.set_ssl_status("mybusiness.com", "expired")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertTrue(ws.loads_successfully)
        self.assertTrue(ws.ssl_warning)

    def test_sync_ssl_valid_no_warning(self):
        """Valid SSL should show no warning."""
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertFalse(ws.ssl_warning)

    def test_sync_ssl_renewed_clears_warning(self):
        """Renewing SSL should clear the warning."""
        self.env.tools.set_ssl_status("mybusiness.com", "expired")
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.website.ssl_warning)

        self.env.tools.renew_ssl_certificate("mybusiness.com")
        self.env.sync_tools()
        self.assertFalse(self.env.user_tools.db.website.ssl_warning)

    # --- Server sync tests ---

    def test_sync_server_crashed_502(self):
        """Crashed server should produce 502."""
        self.env.tools.set_server_status("SRV001", "crashed")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertFalse(ws.loads_successfully)
        self.assertEqual(ws.error_code, "502")

    def test_sync_server_stopped_503(self):
        """Stopped server should produce 503."""
        self.env.tools.set_server_status("SRV001", "stopped")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertFalse(ws.loads_successfully)
        self.assertEqual(ws.error_code, "503")

    def test_sync_server_restarted_restores(self):
        """Restarting a crashed server should restore the site."""
        self.env.tools.set_server_status("SRV001", "crashed")
        self.env.sync_tools()
        self.assertFalse(self.env.user_tools.db.website.loads_successfully)

        self.env.tools.restart_web_server("SRV001")
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.website.loads_successfully)

    # --- Database sync tests ---

    def test_sync_database_crashed_500(self):
        """Crashed database should produce 500."""
        self.env.tools.set_database_status("DB001", "crashed")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertFalse(ws.loads_successfully)
        self.assertEqual(ws.error_code, "500")

    def test_sync_database_restarted_restores(self):
        """Restarting database should restore the site."""
        self.env.tools.set_database_status("DB001", "crashed")
        self.env.sync_tools()
        self.assertFalse(self.env.user_tools.db.website.loads_successfully)

        self.env.tools.restart_database("DB001")
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.website.loads_successfully)

    def test_sync_database_max_connections_500(self):
        """Max connections reached should produce 500."""
        self.env.tools.set_database_connections("DB001", 100, 100)
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertFalse(ws.loads_successfully)
        self.assertEqual(ws.error_code, "500")

    # --- Deployment sync tests ---

    def test_sync_deployment_failed_500(self):
        """Failed deployment should produce 500."""
        self.env.tools.set_deployment_status("DEP001", "failed")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertFalse(ws.loads_successfully)
        self.assertEqual(ws.error_code, "500")

    def test_sync_deployment_rollback_restores(self):
        """Rolling back deployment should restore the site."""
        self.env.tools.set_deployment_status("DEP001", "failed")
        self.env.sync_tools()
        self.assertFalse(self.env.user_tools.db.website.loads_successfully)

        self.env.tools.rollback_deployment("DEP001")
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.website.loads_successfully)

    # --- Email sync tests ---

    def test_sync_email_working_with_mx_record(self):
        """Email should work when MX record exists and server is up."""
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.email_working)

    def test_sync_email_broken_without_dns(self):
        """Email should fail when DNS is wrong."""
        self.env.tools.set_dns_value("DNS001", "198.51.100.99")
        self.env.sync_tools()
        self.assertFalse(self.env.user_tools.db.email_working)

    # --- Cache staleness tests ---

    def test_browser_cache_stale_not_cleared_by_sync(self):
        """browser_cache_stale should NOT be cleared by sync."""
        self.env.user_tools.set_browser_cache_stale(True)
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.browser_cache_stale)

    def test_local_dns_stale_not_cleared_by_sync(self):
        """local_dns_stale should NOT be cleared by sync."""
        self.env.user_tools.set_local_dns_stale(True)
        self.env.sync_tools()
        self.assertTrue(self.env.user_tools.db.local_dns_stale)

    def test_user_clears_browser_cache(self):
        """User clearing browser cache should clear the flag."""
        self.env.user_tools.set_browser_cache_stale(True)
        self.env.user_tools.clear_browser_cache()
        self.assertFalse(self.env.user_tools.db.browser_cache_stale)

    def test_user_flushes_local_dns(self):
        """User flushing local DNS should clear the flag."""
        self.env.user_tools.set_local_dns_stale(True)
        self.env.user_tools.flush_local_dns()
        self.assertFalse(self.env.user_tools.db.local_dns_stale)

    # --- Tool call via environment ---

    def test_tool_call_via_environment(self):
        """Test making tool calls through the environment interface."""
        result = self.env.use_tool("check_server_status", server_id="SRV001")
        self.assertEqual(result["server_id"], "SRV001")

    def test_user_tool_call_via_environment(self):
        """Test making user tool calls through the environment interface."""
        result = self.env.use_user_tool("test_website", url="https://mybusiness.com")
        self.assertIn("SUCCESS", result)

    # --- Priority/order tests ---

    def test_dns_error_takes_priority_over_server(self):
        """DNS error should take priority over server issues."""
        self.env.tools.set_dns_value("DNS001", "198.51.100.99")
        self.env.tools.set_server_status("SRV001", "crashed")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertEqual(ws.error_code, "dns_error")

    def test_server_error_takes_priority_over_database(self):
        """Server error should take priority over database issues."""
        self.env.tools.set_server_status("SRV001", "crashed")
        self.env.tools.set_database_status("DB001", "crashed")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertEqual(ws.error_code, "502")

    def test_ssl_warning_with_healthy_infrastructure(self):
        """SSL issues show as warnings only when infrastructure is otherwise healthy."""
        self.env.tools.set_ssl_status("mybusiness.com", "expired")
        self.env.sync_tools()
        ws = self.env.user_tools.db.website
        self.assertTrue(ws.loads_successfully)
        self.assertTrue(ws.ssl_warning)
        self.assertIsNone(ws.error_code)


if __name__ == "__main__":
    unittest.main()
