from typing import List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class WebServer(BaseModelNoExtra):
    server_id: str
    hostname: str
    status: str  # "running", "stopped", "crashed", "restarting"
    server_software: str  # "nginx"
    document_root: str  # "/var/www/html"
    php_version: str  # "8.2"
    port: int  # 443
    error_log: List[str] = []
    hardware_failure: bool = False


class DatabaseServer(BaseModelNoExtra):
    db_id: str
    db_type: str  # "mysql"
    status: str  # "running", "stopped", "crashed"
    host: str
    port: int  # 3306
    max_connections: int  # 100
    current_connections: int  # 5


class DNSRecord(BaseModelNoExtra):
    record_id: str
    domain: str
    record_type: str  # "A", "CNAME", "MX"
    value: str
    ttl: int  # 3600


class SSLCertificate(BaseModelNoExtra):
    cert_id: str
    domain: str
    status: str  # "valid", "expired", "revoked", "misconfigured"
    issuer: str
    valid_until: str


class Deployment(BaseModelNoExtra):
    deployment_id: str
    version: str
    status: str  # "active", "failed", "rolled_back"
    deployed_at: str
    previous_version: str


class HostingAccount(BaseModelNoExtra):
    account_id: str
    owner_name: str
    email: str
    plan: str
    domain: str
    server_ip: str
    server_id: str
    db_id: str


class HostingDB(DB):
    servers: List[WebServer]
    databases: List[DatabaseServer]
    dns_records: List[DNSRecord]
    ssl_certificates: List[SSLCertificate]
    deployments: List[Deployment]
    account: HostingAccount
    firewall_enabled: bool = True
    server_cache_stale: bool = False
