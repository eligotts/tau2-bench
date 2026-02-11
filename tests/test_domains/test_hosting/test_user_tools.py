import unittest

from tau2.domains.hosting.user_data_model import HostingUserDB
from tau2.domains.hosting.user_tools import HostingUserTools
from tau2.domains.hosting.utils import HOSTING_USER_DB_PATH


class TestHostingUserTools(unittest.TestCase):
    def setUp(self):
        self.db = HostingUserDB.load(HOSTING_USER_DB_PATH)
        self.tools = HostingUserTools(self.db)

    # --- READ tool tests ---

    def test_test_website_success(self):
        result = self.tools.test_website("https://mybusiness.com")
        self.assertIn("SUCCESS", result)
        self.assertIn("250ms", result)

    def test_test_website_error_502(self):
        self.tools.set_website_status(loads=False, error_code="502")
        result = self.tools.test_website("https://mybusiness.com")
        self.assertIn("FAILED", result)
        self.assertIn("502", result)

    def test_test_website_dns_error(self):
        self.tools.set_website_status(loads=False, error_code="dns_error")
        result = self.tools.test_website("https://mybusiness.com")
        self.assertIn("FAILED", result)
        self.assertIn("DNS", result)

    def test_test_website_ssl_warning(self):
        self.tools.set_website_status(loads=True, ssl_warning=True)
        result = self.tools.test_website("https://mybusiness.com")
        self.assertIn("WARNING", result)
        self.assertIn("SSL", result)

    def test_test_website_content_incorrect(self):
        self.tools.set_website_status(loads=True, content_correct=False)
        result = self.tools.test_website("https://mybusiness.com")
        self.assertIn("ISSUE", result)
        self.assertIn("incorrect", result)

    def test_check_ssl_in_browser_ok(self):
        result = self.tools.check_ssl_in_browser("https://mybusiness.com")
        self.assertIn("OK", result)
        self.assertIn("secure", result)

    def test_check_ssl_in_browser_warning(self):
        self.tools.set_website_status(loads=True, ssl_warning=True)
        result = self.tools.check_ssl_in_browser("https://mybusiness.com")
        self.assertIn("WARNING", result)

    def test_check_email_delivery_working(self):
        result = self.tools.check_email_delivery()
        self.assertIn("working", result)

    def test_check_email_delivery_broken(self):
        self.tools.set_email_working(False)
        result = self.tools.check_email_delivery()
        self.assertIn("NOT working", result)

    def test_check_dns_resolution_ok(self):
        result = self.tools.check_dns_resolution("mybusiness.com")
        self.assertIn("OK", result)

    def test_check_dns_resolution_failed(self):
        self.tools.set_dns_resolves(False)
        result = self.tools.check_dns_resolution("mybusiness.com")
        self.assertIn("FAILED", result)

    def test_check_dns_resolution_stale(self):
        self.tools.set_local_dns_stale(True)
        result = self.tools.check_dns_resolution("mybusiness.com")
        self.assertIn("STALE", result)

    def test_run_speed_test_fast(self):
        result = self.tools.run_speed_test("https://mybusiness.com")
        self.assertIn("FAST", result)
        self.assertIn("250ms", result)

    def test_run_speed_test_slow(self):
        self.tools.set_website_status(loads=True, response_time=5000)
        result = self.tools.run_speed_test("https://mybusiness.com")
        self.assertIn("SLOW", result)

    def test_run_speed_test_not_loading(self):
        self.tools.set_website_status(loads=False, error_code="502")
        result = self.tools.run_speed_test("https://mybusiness.com")
        self.assertIn("FAILED", result)

    # --- WRITE tool tests ---

    def test_clear_browser_cache(self):
        self.tools.set_browser_cache_stale(True)
        result = self.tools.clear_browser_cache()
        self.assertIn("cleared", result)
        self.assertFalse(self.db.browser_cache_stale)

    def test_flush_local_dns(self):
        self.tools.set_local_dns_stale(True)
        result = self.tools.flush_local_dns()
        self.assertIn("flushed", result)
        self.assertFalse(self.db.local_dns_stale)

    def test_hard_refresh_page_success(self):
        result = self.tools.hard_refresh_page("https://mybusiness.com")
        self.assertIn("SUCCESS", result)
        self.assertFalse(self.db.browser_cache_stale)
        self.assertTrue(self.db.user_verified_working)

    def test_hard_refresh_page_still_failing(self):
        self.tools.set_website_status(loads=False, error_code="502")
        result = self.tools.hard_refresh_page("https://mybusiness.com")
        self.assertIn("STILL FAILING", result)

    def test_hard_refresh_page_ssl_warning(self):
        self.tools.set_website_status(loads=True, ssl_warning=True)
        result = self.tools.hard_refresh_page("https://mybusiness.com")
        self.assertIn("SSL warning", result)

    def test_confirm_site_working(self):
        self.tools.set_user_verified_working(False)
        result = self.tools.confirm_site_working()
        self.assertIn("Confirmed", result)
        self.assertTrue(self.db.user_verified_working)

    def test_confirm_site_working_still_broken(self):
        self.tools.set_website_status(loads=False, error_code="500")
        result = self.tools.confirm_site_working()
        self.assertIn("Cannot confirm", result)

    # --- Helper tests ---

    def test_set_user_info(self):
        self.tools.set_user_info("Test User", "test@test.com", "ACC999")
        self.assertEqual(self.db.user_name, "Test User")
        self.assertEqual(self.db.user_email, "test@test.com")
        self.assertEqual(self.db.account_id, "ACC999")

    def test_set_website_status(self):
        self.tools.set_website_status(loads=False, response_time=-1, error_code="503")
        self.assertFalse(self.db.website.loads_successfully)
        self.assertEqual(self.db.website.response_time_ms, -1)
        self.assertEqual(self.db.website.error_code, "503")

    def test_set_email_working(self):
        self.tools.set_email_working(False)
        self.assertFalse(self.db.email_working)

    def test_set_dns_resolves(self):
        self.tools.set_dns_resolves(False)
        self.assertFalse(self.db.dns_resolves)

    def test_set_browser_cache_stale(self):
        self.tools.set_browser_cache_stale(True)
        self.assertTrue(self.db.browser_cache_stale)

    def test_set_local_dns_stale(self):
        self.tools.set_local_dns_stale(True)
        self.assertTrue(self.db.local_dns_stale)

    def test_set_user_verified_working(self):
        self.tools.set_user_verified_working(False)
        self.assertFalse(self.db.user_verified_working)

    # --- Assertion tests ---

    def test_assert_website_loads(self):
        self.assertTrue(self.tools.assert_website_loads())
        self.tools.set_website_status(loads=False, error_code="502")
        self.assertFalse(self.tools.assert_website_loads())

    def test_assert_no_ssl_warning(self):
        self.assertTrue(self.tools.assert_no_ssl_warning())
        self.tools.set_website_status(loads=True, ssl_warning=True)
        self.assertFalse(self.tools.assert_no_ssl_warning())

    def test_assert_email_working(self):
        self.assertTrue(self.tools.assert_email_working())
        self.tools.set_email_working(False)
        self.assertFalse(self.tools.assert_email_working())

    def test_assert_dns_resolves(self):
        self.assertTrue(self.tools.assert_dns_resolves())
        self.tools.set_dns_resolves(False)
        self.assertFalse(self.tools.assert_dns_resolves())

    def test_assert_site_healthy(self):
        self.assertTrue(self.tools.assert_site_healthy())

    def test_assert_site_healthy_not_loading(self):
        self.tools.set_website_status(loads=False, error_code="502")
        self.assertFalse(self.tools.assert_site_healthy())

    def test_assert_site_healthy_ssl_warning(self):
        self.tools.set_website_status(loads=True, ssl_warning=True)
        self.assertFalse(self.tools.assert_site_healthy())

    def test_assert_site_healthy_stale_cache(self):
        self.tools.set_browser_cache_stale(True)
        self.assertFalse(self.tools.assert_site_healthy())

    def test_assert_site_healthy_stale_dns(self):
        self.tools.set_local_dns_stale(True)
        self.assertFalse(self.tools.assert_site_healthy())

    def test_assert_site_healthy_not_verified(self):
        self.tools.set_user_verified_working(False)
        self.assertFalse(self.tools.assert_site_healthy())

    def test_assert_site_healthy_dns_not_resolving(self):
        self.tools.set_dns_resolves(False)
        self.assertFalse(self.tools.assert_site_healthy())

    def test_user_db_loads_defaults(self):
        """Verify the user DB loads with correct defaults."""
        self.assertTrue(self.db.website.loads_successfully)
        self.assertEqual(self.db.website.response_time_ms, 250)
        self.assertIsNone(self.db.website.error_code)
        self.assertFalse(self.db.website.ssl_warning)
        self.assertTrue(self.db.email_working)
        self.assertTrue(self.db.dns_resolves)
        self.assertFalse(self.db.browser_cache_stale)
        self.assertFalse(self.db.local_dns_stale)
        self.assertTrue(self.db.user_verified_working)


if __name__ == "__main__":
    unittest.main()
