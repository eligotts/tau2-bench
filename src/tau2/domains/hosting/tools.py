from typing import Any, Dict, List, Optional

from tau2.domains.hosting.data_model import (
    DatabaseServer,
    DNSRecord,
    Deployment,
    HostingDB,
    SSLCertificate,
    WebServer,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class HostingTools(ToolKitBase):
    """Tools available to the assistant for web hosting support."""

    db: HostingDB

    def __init__(self, db: HostingDB):
        super().__init__(db)

    # --- READ tools ---

    @is_tool(ToolType.READ)
    def get_account_info(self, account_id: str) -> Dict[str, Any]:
        """
        Look up hosting account details by account ID.

        Args:
            account_id: The hosting account identifier.

        Returns:
            Account details including owner, plan, domain, and server IP.
        """
        if self.db.account.account_id != account_id:
            raise ValueError(f"Account {account_id} not found.")
        return self.db.account.model_dump()

    @is_tool(ToolType.READ)
    def check_server_status(self, server_id: str) -> Dict[str, Any]:
        """
        Get web server status, configuration, and recent errors.

        Args:
            server_id: The server identifier.

        Returns:
            Server details including status, software, port, and recent errors.
        """
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        return server.model_dump()

    @is_tool(ToolType.READ)
    def check_server_logs(self, server_id: str) -> Dict[str, Any]:
        """
        Get detailed error logs and diagnostics for a web server.

        Args:
            server_id: The server identifier.

        Returns:
            Diagnostic information including status, error log, and configuration.
        """
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        diagnostics = {
            "server_id": server.server_id,
            "status": server.status,
            "server_software": server.server_software,
            "port": server.port,
            "document_root": server.document_root,
            "php_version": server.php_version,
            "error_log": server.error_log,
        }
        if server.status == "crashed":
            diagnostics["recommendation"] = "Server has crashed. Restart recommended."
        elif server.status == "stopped":
            diagnostics["recommendation"] = "Server is stopped. Start required."
        if server.port != 443:
            diagnostics["warning"] = f"Server listening on non-standard port {server.port}."
        return diagnostics

    @is_tool(ToolType.READ)
    def check_database_status(self, db_id: str) -> Dict[str, Any]:
        """
        Get database server status and connection information.

        Args:
            db_id: The database server identifier.

        Returns:
            Database details including status, connections, and capacity.
        """
        database = self._find_database(db_id)
        if database is None:
            raise ValueError(f"Database {db_id} not found.")
        result = database.model_dump()
        if database.current_connections >= database.max_connections:
            result["warning"] = "Connection limit reached."
        return result

    @is_tool(ToolType.READ)
    def check_dns_records(self, domain: str) -> List[Dict[str, Any]]:
        """
        List all DNS records for a domain.

        Args:
            domain: The domain name to check.

        Returns:
            List of DNS records for the domain.
        """
        records = [r.model_dump() for r in self.db.dns_records if r.domain == domain]
        if not records:
            raise ValueError(f"No DNS records found for {domain}.")
        return records

    @is_tool(ToolType.READ)
    def check_ssl_status(self, domain: str) -> Dict[str, Any]:
        """
        Get SSL certificate status for a domain.

        Args:
            domain: The domain name to check.

        Returns:
            SSL certificate details including status, issuer, and expiration.
        """
        cert = self._find_ssl_cert(domain)
        if cert is None:
            raise ValueError(f"No SSL certificate found for {domain}.")
        return cert.model_dump()

    @is_tool(ToolType.READ)
    def check_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """
        Get deployment information.

        Args:
            deployment_id: The deployment identifier.

        Returns:
            Deployment details including version, status, and previous version.
        """
        deployment = self._find_deployment(deployment_id)
        if deployment is None:
            raise ValueError(f"Deployment {deployment_id} not found.")
        return deployment.model_dump()

    # --- WRITE tools ---

    @is_tool(ToolType.WRITE)
    def restart_web_server(self, server_id: str) -> str:
        """
        Restart a crashed or stopped web server.

        Args:
            server_id: The server identifier.

        Returns:
            Result of the restart attempt.
        """
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        if server.hardware_failure:
            return f"FAILED: Web server {server_id} restart failed due to hardware error. Server remains in '{server.status}' state. Escalation to data center operations required."
        server.status = "running"
        server.error_log = []
        return f"Web server {server_id} restarted successfully. Status: running."

    @is_tool(ToolType.WRITE)
    def restart_database(self, db_id: str) -> str:
        """
        Restart a crashed or stopped database server.

        Args:
            db_id: The database server identifier.

        Returns:
            Result of the restart attempt.
        """
        database = self._find_database(db_id)
        if database is None:
            raise ValueError(f"Database {db_id} not found.")
        database.status = "running"
        database.current_connections = 0
        return f"Database {db_id} restarted successfully. Status: running."

    @is_tool(ToolType.WRITE)
    def update_dns_record(self, record_id: str, value: str) -> str:
        """
        Update the value of a DNS record.

        Args:
            record_id: The DNS record identifier.
            value: The new value for the record (e.g., IP address).

        Returns:
            Confirmation message.
        """
        record = self._find_dns_record(record_id)
        if record is None:
            raise ValueError(f"DNS record {record_id} not found.")
        old_value = record.value
        record.value = value
        return f"DNS record {record_id} updated from {old_value} to {value}. TTL: {record.ttl}s."

    @is_tool(ToolType.WRITE)
    def renew_ssl_certificate(self, domain: str) -> str:
        """
        Renew an expired or misconfigured SSL certificate for a domain.

        Args:
            domain: The domain to renew the certificate for.

        Returns:
            Confirmation message.
        """
        cert = self._find_ssl_cert(domain)
        if cert is None:
            raise ValueError(f"No SSL certificate found for {domain}.")
        cert.status = "valid"
        cert.valid_until = "2026-12-31"
        return f"SSL certificate for {domain} renewed successfully. Valid until 2026-12-31."

    @is_tool(ToolType.WRITE)
    def rollback_deployment(self, deployment_id: str) -> str:
        """
        Roll back a deployment to the previous version.

        Args:
            deployment_id: The deployment identifier.

        Returns:
            Confirmation message with version info.
        """
        deployment = self._find_deployment(deployment_id)
        if deployment is None:
            raise ValueError(f"Deployment {deployment_id} not found.")
        old_version = deployment.version
        deployment.version = deployment.previous_version
        deployment.previous_version = old_version
        deployment.status = "active"
        return f"Deployment {deployment_id} rolled back from {old_version} to {deployment.version}."

    @is_tool(ToolType.WRITE)
    def update_server_config(self, server_id: str, setting_name: str, setting_value: Any) -> str:
        """
        Update a web server configuration setting.

        Args:
            server_id: The server identifier.
            setting_name: The setting to update (e.g., 'port', 'document_root', 'php_version').
            setting_value: The new value for the setting.

        Returns:
            Confirmation message.
        """
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        if setting_name not in ("port", "document_root", "php_version"):
            raise ValueError(f"Invalid setting: {setting_name}. Must be one of: port, document_root, php_version.")
        setattr(server, setting_name, setting_value)
        return f"Server {server_id} config updated: {setting_name} = {setting_value}."

    @is_tool(ToolType.WRITE)
    def increase_db_connections(self, db_id: str, new_max: int) -> str:
        """
        Increase the maximum number of database connections.

        Args:
            db_id: The database server identifier.
            new_max: The new maximum connection limit.

        Returns:
            Confirmation message.
        """
        database = self._find_database(db_id)
        if database is None:
            raise ValueError(f"Database {db_id} not found.")
        old_max = database.max_connections
        database.max_connections = new_max
        return f"Database {db_id} max connections increased from {old_max} to {new_max}."

    @is_tool(ToolType.WRITE)
    def clear_server_cache(self, server_id: str) -> str:
        """
        Clear the server-side cache.

        Args:
            server_id: The server identifier.

        Returns:
            Confirmation message.
        """
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        if server.status != "running":
            return f"FAILED: Server {server_id} is {server.status}. Cannot clear cache while server is not running."
        self.db.server_cache_stale = False
        return f"Server cache cleared on {server_id}."

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

    # --- Helper methods (not tools, for scenario setup) ---

    def set_server_status(self, server_id: str, status: str) -> None:
        """Set server status directly (for scenario setup)."""
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        server.status = status

    def set_server_error_log(self, server_id: str, errors: List[str]) -> None:
        """Set server error log directly (for scenario setup)."""
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        server.error_log = errors

    def set_server_port(self, server_id: str, port: int) -> None:
        """Set server port directly (for scenario setup)."""
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        server.port = port

    def set_database_status(self, db_id: str, status: str) -> None:
        """Set database status directly (for scenario setup)."""
        database = self._find_database(db_id)
        if database is None:
            raise ValueError(f"Database {db_id} not found.")
        database.status = status

    def set_database_connections(self, db_id: str, current: int, max_conn: int) -> None:
        """Set database connection counts directly (for scenario setup)."""
        database = self._find_database(db_id)
        if database is None:
            raise ValueError(f"Database {db_id} not found.")
        database.current_connections = current
        database.max_connections = max_conn

    def set_dns_value(self, record_id: str, value: str) -> None:
        """Set DNS record value directly (for scenario setup)."""
        record = self._find_dns_record(record_id)
        if record is None:
            raise ValueError(f"DNS record {record_id} not found.")
        record.value = value

    def set_ssl_status(self, domain: str, status: str) -> None:
        """Set SSL certificate status directly (for scenario setup)."""
        cert = self._find_ssl_cert(domain)
        if cert is None:
            raise ValueError(f"No SSL certificate found for {domain}.")
        cert.status = status

    def set_deployment_status(self, deployment_id: str, status: str) -> None:
        """Set deployment status directly (for scenario setup)."""
        deployment = self._find_deployment(deployment_id)
        if deployment is None:
            raise ValueError(f"Deployment {deployment_id} not found.")
        deployment.status = status

    def set_server_hardware_failure(self, server_id: str, failed: bool) -> None:
        """Set server hardware failure flag (for scenario setup)."""
        server = self._find_server(server_id)
        if server is None:
            raise ValueError(f"Server {server_id} not found.")
        server.hardware_failure = failed

    def set_server_cache_stale(self, stale: bool) -> None:
        """Set server cache staleness flag (for scenario setup)."""
        self.db.server_cache_stale = stale

    # --- Assertion methods (not tools) ---

    def assert_server_running(self, server_id: str) -> bool:
        """Assert that a server is running."""
        server = self._find_server(server_id)
        if server is None:
            return False
        return server.status == "running"

    def assert_database_running(self, db_id: str) -> bool:
        """Assert that a database is running."""
        database = self._find_database(db_id)
        if database is None:
            return False
        return database.status == "running"

    def assert_dns_correct(self, record_id: str, expected_value: str) -> bool:
        """Assert that a DNS record has the expected value."""
        record = self._find_dns_record(record_id)
        if record is None:
            return False
        return record.value == expected_value

    def assert_ssl_valid(self, domain: str) -> bool:
        """Assert that an SSL certificate is valid."""
        cert = self._find_ssl_cert(domain)
        if cert is None:
            return False
        return cert.status == "valid"

    def assert_deployment_active(self, deployment_id: str) -> bool:
        """Assert that a deployment is active."""
        deployment = self._find_deployment(deployment_id)
        if deployment is None:
            return False
        return deployment.status == "active"

    def assert_server_port(self, server_id: str, expected_port: int) -> bool:
        """Assert that a server is on the expected port."""
        server = self._find_server(server_id)
        if server is None:
            return False
        return server.port == expected_port

    # --- Internal helpers ---

    def _find_server(self, server_id: str) -> Optional[WebServer]:
        for s in self.db.servers:
            if s.server_id == server_id:
                return s
        return None

    def _find_database(self, db_id: str) -> Optional[DatabaseServer]:
        for d in self.db.databases:
            if d.db_id == db_id:
                return d
        return None

    def _find_dns_record(self, record_id: str) -> Optional[DNSRecord]:
        for r in self.db.dns_records:
            if r.record_id == record_id:
                return r
        return None

    def _find_ssl_cert(self, domain: str) -> Optional[SSLCertificate]:
        for c in self.db.ssl_certificates:
            if c.domain == domain:
                return c
        return None

    def _find_deployment(self, deployment_id: str) -> Optional[Deployment]:
        for d in self.db.deployments:
            if d.deployment_id == deployment_id:
                return d
        return None
