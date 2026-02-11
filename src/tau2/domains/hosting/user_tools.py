from typing import Dict, Optional

from tau2.domains.hosting.user_data_model import HostingUserDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class HostingUserTools(ToolKitBase):
    """Tools available to the user (browser/computer interactions)."""

    db: HostingUserDB

    def __init__(self, db: HostingUserDB):
        super().__init__(db)

    # --- READ tools ---

    @is_tool(ToolType.READ)
    def test_website(self, url: str) -> str:
        """
        Load the website and report its status, errors, and speed.

        Args:
            url: The URL to test (e.g., 'https://mybusiness.com').

        Returns:
            Website status including load time, errors, and content correctness.
        """
        ws = self.db.website
        if not ws.loads_successfully:
            error_descriptions = {
                "502": "Bad Gateway - the server returned a 502 error",
                "503": "Service Unavailable - the server returned a 503 error",
                "500": "Internal Server Error - the server returned a 500 error",
                "ssl_error": "SSL certificate error - your browser shows a security warning",
                "dns_error": "DNS resolution failed - the domain could not be found",
            }
            error_desc = error_descriptions.get(ws.error_code, f"Unknown error: {ws.error_code}")
            return f"FAILED to load {url}. Error: {error_desc}."
        if ws.ssl_warning:
            return f"WARNING: {url} loaded but your browser shows an SSL security warning. Response time: {ws.response_time_ms}ms."
        if not ws.page_content_correct:
            return f"ISSUE: {url} loaded but the page content appears incorrect or outdated. Response time: {ws.response_time_ms}ms."
        return f"SUCCESS: {url} loaded correctly. Response time: {ws.response_time_ms}ms. No errors detected."

    @is_tool(ToolType.READ)
    def check_ssl_in_browser(self, url: str) -> str:
        """
        Check for SSL certificate warnings in the browser.

        Args:
            url: The URL to check.

        Returns:
            SSL status as seen in the browser.
        """
        ws = self.db.website
        if ws.ssl_warning:
            return f"WARNING: Your browser shows an SSL security warning for {url}. The connection is not secure."
        return f"OK: No SSL warnings for {url}. The connection is secure (padlock icon visible)."

    @is_tool(ToolType.READ)
    def check_email_delivery(self) -> str:
        """
        Test if email delivery is working for the domain.

        Returns:
            Email delivery status.
        """
        if self.db.email_working:
            self.db.needs_email_verification = False
            return "Email delivery is working. Test email was received successfully."
        return "Email delivery is NOT working. Test email was not received."

    @is_tool(ToolType.READ)
    def check_dns_resolution(self, domain: str) -> str:
        """
        Check if the domain name resolves from the user's computer.

        Args:
            domain: The domain to check.

        Returns:
            DNS resolution status.
        """
        if self.db.dns_resolves and not self.db.local_dns_stale:
            return f"OK: {domain} resolves correctly from your computer."
        if self.db.local_dns_stale:
            return f"STALE: {domain} resolves to an old/cached address. Try flushing your local DNS cache."
        return f"FAILED: {domain} does not resolve. DNS lookup returned no results."

    @is_tool(ToolType.READ)
    def run_speed_test(self, url: str) -> str:
        """
        Measure page load time for the website.

        Args:
            url: The URL to test.

        Returns:
            Speed test results.
        """
        ws = self.db.website
        if not ws.loads_successfully:
            return f"FAILED: Could not run speed test - {url} is not loading."
        time_ms = ws.response_time_ms
        if time_ms < 500:
            rating = "FAST"
        elif time_ms < 2000:
            rating = "ACCEPTABLE"
        else:
            rating = "SLOW"
        return f"Speed test for {url}: {time_ms}ms ({rating})."

    # --- WRITE tools ---

    @is_tool(ToolType.WRITE)
    def clear_browser_cache(self) -> str:
        """
        Clear the browser cache. This removes any cached/stale page content.

        Returns:
            Confirmation message.
        """
        self.db.browser_cache_stale = False
        return "Browser cache cleared successfully."

    @is_tool(ToolType.WRITE)
    def flush_local_dns(self) -> str:
        """
        Flush the local DNS cache. This forces DNS to re-resolve on next request.

        Returns:
            Confirmation message.
        """
        self.db.local_dns_stale = False
        return "Local DNS cache flushed successfully."

    @is_tool(ToolType.WRITE)
    def hard_refresh_page(self, url: str) -> str:
        """
        Force-refresh the page bypassing browser cache, then verify the site loads.

        Args:
            url: The URL to hard-refresh.

        Returns:
            Result of the hard refresh including site status.
        """
        self.db.browser_cache_stale = False
        ws = self.db.website
        if not ws.loads_successfully:
            error_descriptions = {
                "502": "Bad Gateway error (502)",
                "503": "Service Unavailable error (503)",
                "500": "Internal Server Error (500)",
                "ssl_error": "SSL certificate error",
                "dns_error": "DNS resolution failed",
            }
            error_desc = error_descriptions.get(ws.error_code, f"Error: {ws.error_code}")
            return f"Hard refresh of {url}: STILL FAILING. {error_desc}."
        if ws.ssl_warning:
            return f"Hard refresh of {url}: Page loaded but SSL warning persists. Response time: {ws.response_time_ms}ms."
        self.db.user_verified_working = True
        if self.db.email_working:
            self.db.needs_email_verification = False
        return f"Hard refresh of {url}: SUCCESS. Page loaded correctly. Response time: {ws.response_time_ms}ms."

    @is_tool(ToolType.WRITE)
    def confirm_site_working(self) -> str:
        """
        User confirms that the website is working correctly after troubleshooting.

        Returns:
            Confirmation message.
        """
        ws = self.db.website
        if not ws.loads_successfully:
            return "Cannot confirm - website is still not loading."
        self.db.user_verified_working = True
        if self.db.email_working:
            self.db.needs_email_verification = False
        return "Confirmed: website is working correctly. Thank you for verifying."

    # --- Setup helpers (not tools) ---

    def set_website_status(
        self,
        loads: bool,
        response_time: int = 250,
        error_code: Optional[str] = None,
        ssl_warning: bool = False,
        content_correct: bool = True,
    ) -> None:
        """Set website status directly (for scenario setup)."""
        self.db.website.loads_successfully = loads
        self.db.website.response_time_ms = response_time
        self.db.website.error_code = error_code
        self.db.website.ssl_warning = ssl_warning
        self.db.website.page_content_correct = content_correct

    def set_email_working(self, working: bool) -> None:
        """Set email delivery status."""
        self.db.email_working = working

    def set_dns_resolves(self, resolves: bool) -> None:
        """Set DNS resolution status."""
        self.db.dns_resolves = resolves

    def set_browser_cache_stale(self, stale: bool) -> None:
        """Set browser cache staleness flag."""
        self.db.browser_cache_stale = stale

    def set_local_dns_stale(self, stale: bool) -> None:
        """Set local DNS staleness flag."""
        self.db.local_dns_stale = stale

    def set_user_verified_working(self, verified: bool) -> None:
        """Set user verification flag."""
        self.db.user_verified_working = verified

    def set_user_info(self, name: str, email: str, account_id: str) -> None:
        """Set the user's identity info."""
        self.db.user_name = name
        self.db.user_email = email
        self.db.account_id = account_id

    def set_needs_email_verification(self, needs: bool) -> None:
        """Set the needs_email_verification flag (for scenario setup)."""
        self.db.needs_email_verification = needs

    # --- Assertion methods (not tools) ---

    def assert_website_loads(self) -> bool:
        """Assert that the website loads successfully."""
        return self.db.website.loads_successfully

    def assert_no_ssl_warning(self) -> bool:
        """Assert there are no SSL warnings."""
        return not self.db.website.ssl_warning

    def assert_email_working(self) -> bool:
        """Assert email delivery is working."""
        return self.db.email_working

    def assert_dns_resolves(self) -> bool:
        """Assert DNS resolves correctly."""
        return self.db.dns_resolves

    def assert_site_healthy(self) -> bool:
        """Master check: site loads, no SSL warning, DNS resolves, no stale cache, user verified, no pending email fix."""
        ws = self.db.website
        if not ws.loads_successfully:
            return False
        if ws.ssl_warning:
            return False
        if ws.error_code is not None:
            return False
        if not ws.page_content_correct:
            return False
        if not self.db.dns_resolves:
            return False
        if self.db.browser_cache_stale:
            return False
        if self.db.local_dns_stale:
            return False
        if not self.db.user_verified_working:
            return False
        if self.db.needs_email_verification:
            return False
        return True
