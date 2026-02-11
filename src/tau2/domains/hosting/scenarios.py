from typing import Optional

from tau2.data_model.message import ToolCall
from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall
from tau2.domains.hosting.environment import HostingEnvironment
from tau2.generators.types import Persona, Scenario, ScenarioGroup, UserTemplate

# === Personas ===

PERSONAS = [
    Persona(name="None", description=None),
    Persona(
        name="non_technical",
        description="You are a 55-year-old small business owner who runs a bakery. You built your website using a website builder and have very limited technical knowledge. You may not understand terms like DNS, SSL, or server. You prefer simple explanations.",
    ),
    Persona(
        name="developer",
        description="You are a 28-year-old freelance web developer who built the client's site. You are very technical and may suggest your own troubleshooting ideas or ask about specific server configurations.",
    ),
]

# === User Template ===

USER_TEMPLATE = UserTemplate(
    domain="hosting",
    reason_for_call="Your website is having problems. It may be down, showing errors, loading slowly, showing security warnings, or email may not be working. You need the hosting provider's support to investigate and fix the issue.",
    known_info="You are {name} (account ID: {account_id}). Your website is {domain}.",
    task_instructions="If the agent asks you to check something on your end (like testing the website, checking for SSL warnings, or testing email), use your tools to check and report back. If the agent asks you to do something on your computer (like clearing your browser cache, flushing DNS, or doing a hard refresh), use your tools to do so. You will consider the issue resolved only when your website loads correctly with no errors or warnings. If the issue cannot be fixed remotely, you expect the agent to escalate to a human technician.",
    ticket="Customer {name} (account: {account_id}, domain: {domain}) is reporting issues with their website. The site may be down, showing errors, have SSL problems, DNS issues, or email delivery failures. The customer expects the website to load correctly with no errors or warnings.",
    purpose="Test resolution of web hosting issues including DNS, SSL, server, database, deployment, and performance problems.",
)


# === Environment setup ===

def set_surrounding(*args, **kwargs) -> list[EnvFunctionCall]:
    """Set user identity for the scenario."""
    return [
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_info",
            arguments={"name": "Maria Chen", "email": "maria@mybusiness.com", "account_id": "ACC001"},
        )
    ]


def get_template_vars(env: HostingEnvironment) -> dict[str, str]:
    """Get template variables from the environment state."""
    return {
        "name": env.user_tools.db.user_name or "Unknown",
        "account_id": env.user_tools.db.account_id or "Unknown",
        "domain": env.db.account.domain,
    }


# === Env Assertions ===

def get_env_assertions(expected_success: bool) -> list[EnvAssertion]:
    """Get environment assertions to check if the hosting is in a good state."""
    if expected_success:
        return [
            EnvAssertion(
                env_type="user",
                func_name="assert_website_loads",
                arguments={},
                message="Website should load successfully.",
            ),
            EnvAssertion(
                env_type="user",
                func_name="assert_no_ssl_warning",
                arguments={},
                message="No SSL warnings should be present.",
            ),
            EnvAssertion(
                env_type="user",
                func_name="assert_dns_resolves",
                arguments={},
                message="DNS should resolve correctly.",
            ),
            EnvAssertion(
                env_type="user",
                func_name="assert_email_working",
                arguments={},
                message="Email delivery should be working.",
            ),
            EnvAssertion(
                env_type="user",
                func_name="assert_site_healthy",
                arguments={},
                message="Site should be fully healthy (loads, no SSL, DNS ok, no stale cache, user verified).",
            ),
        ]
    else:
        return [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_server_running",
                arguments={"server_id": "SRV001"},
                assert_value=False,
                message="Server should still be down (unfixable).",
            ),
        ]


def is_fixed(env: HostingEnvironment) -> bool:
    """Check if the hosting environment is in a fully working state."""
    assertions = get_env_assertions(expected_success=True)
    success = True
    for assertion in assertions:
        success = success and env.run_env_assertion(
            assertion, raise_assertion_error=False
        )
    return success


# === Task Validator ===

def make_task_validator(min_scenarios: int = 2, max_scenarios: Optional[int] = None):
    """Create a validator that filters by scenario count."""
    def task_validator(scenarios: list[Optional[Scenario]]) -> bool:
        active = [s for s in scenarios if s is not None]
        if len(active) < min_scenarios:
            return False
        if max_scenarios is not None and len(active) > max_scenarios:
            return False
        return True
    return task_validator


task_validator = make_task_validator(min_scenarios=2)


# === Init functions (create issues) ===

# --- Group 1: DNS Issues ---

def init_dns_wrong_ip(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """A record points to wrong IP address."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_dns_value",
            arguments={"record_id": "DNS001", "value": "198.51.100.99"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": False, "response_time": -1, "error_code": "dns_error"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_dns_resolves",
            arguments={"resolves": False},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_local_dns_stale",
            arguments={"stale": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


def init_dns_missing_mx(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """MX record value cleared, email broken."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_dns_value",
            arguments={"record_id": "DNS002", "value": ""},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_needs_email_verification",
            arguments={"needs": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


# --- Group 2: SSL Issues ---

def init_ssl_expired(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """SSL certificate expired, browser shows warnings."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_ssl_status",
            arguments={"domain": "mybusiness.com", "status": "expired"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": True, "response_time": 250, "ssl_warning": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


def init_ssl_misconfigured(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """SSL certificate for wrong domain, needs renewal."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_ssl_status",
            arguments={"domain": "mybusiness.com", "status": "misconfigured"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": True, "response_time": 250, "ssl_warning": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_browser_cache_stale",
            arguments={"stale": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


# --- Group 3: Web Server Issues ---

def init_server_crashed(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Web server crashed, returning 502."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_status",
            arguments={"server_id": "SRV001", "status": "crashed"},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_error_log",
            arguments={"server_id": "SRV001", "errors": ["[error] worker process exited on signal 11", "[crit] out of memory"]},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": False, "response_time": -1, "error_code": "502"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


def init_persistent_server_failure(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Server has hardware failure, cannot be restarted remotely."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_hardware_failure",
            arguments={"server_id": "SRV001", "failed": True},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_status",
            arguments={"server_id": "SRV001", "status": "crashed"},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_error_log",
            arguments={"server_id": "SRV001", "errors": ["[crit] hardware error: disk I/O failure", "[emerg] system halted"]},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": False, "response_time": -1, "error_code": "502"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


def init_server_wrong_port(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Server listening on wrong port after config change."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_port",
            arguments={"server_id": "SRV001", "port": 8080},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": False, "response_time": -1, "error_code": "503"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


# --- Group 4: Database Issues ---

def init_database_crashed(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Database is down, causing 500 errors."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_database_status",
            arguments={"db_id": "DB001", "status": "crashed"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": False, "response_time": -1, "error_code": "500"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


def init_database_max_connections(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Too many database connections, intermittent 500s."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_database_connections",
            arguments={"db_id": "DB001", "current": 100, "max_conn": 100},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": False, "response_time": -1, "error_code": "500"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


# --- Group 5: Deployment Issues ---

def init_bad_deployment(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Latest deployment broke the site."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_deployment_status",
            arguments={"deployment_id": "DEP001", "status": "failed"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": False, "response_time": -1, "error_code": "500"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_browser_cache_stale",
            arguments={"stale": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


def init_deployment_config_error(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Deployment changed server config incorrectly."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_port",
            arguments={"server_id": "SRV001", "port": 8443},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_status",
            arguments={"server_id": "SRV001", "status": "stopped"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": False, "response_time": -1, "error_code": "503"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


# --- Group 6: Performance Issues ---

def init_server_cache_full(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Server cache causing stale content."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_cache_stale",
            arguments={"stale": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_browser_cache_stale",
            arguments={"stale": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


def init_slow_response(env: HostingEnvironment) -> list[EnvFunctionCall]:
    """Server overloaded, slow responses."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_server_error_log",
            arguments={"server_id": "SRV001", "errors": ["[warn] high load average detected", "[warn] request queue full"]},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_website_status",
            arguments={"loads": True, "response_time": 5000},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_verified_working",
            arguments={"verified": False},
        ),
    ]


# === Fix functions ===

# --- Group 1: DNS Fixes ---

def fix_dns_wrong_ip(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent updates DNS record, user flushes local DNS, user hard-refreshes."""
    return [
        ToolCall(
            requestor="assistant",
            name="update_dns_record",
            arguments={"record_id": "DNS001", "value": "203.0.113.10"},
        ),
        ToolCall(
            requestor="user",
            name="flush_local_dns",
            arguments={},
        ),
        ToolCall(
            requestor="user",
            name="hard_refresh_page",
            arguments={"url": "https://mybusiness.com"},
        ),
    ]


def fix_dns_missing_mx(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent restores MX record value, user verifies email delivery."""
    return [
        ToolCall(
            requestor="assistant",
            name="update_dns_record",
            arguments={"record_id": "DNS002", "value": "mail.mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="check_email_delivery",
            arguments={},
        ),
        ToolCall(
            requestor="user",
            name="confirm_site_working",
            arguments={},
        ),
    ]


# --- Group 2: SSL Fixes ---

def fix_ssl_expired(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent renews cert, user checks SSL in browser."""
    return [
        ToolCall(
            requestor="assistant",
            name="renew_ssl_certificate",
            arguments={"domain": "mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="check_ssl_in_browser",
            arguments={"url": "https://mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="confirm_site_working",
            arguments={},
        ),
    ]


def fix_ssl_misconfigured(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent renews cert, user clears cache, user checks SSL."""
    return [
        ToolCall(
            requestor="assistant",
            name="renew_ssl_certificate",
            arguments={"domain": "mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="clear_browser_cache",
            arguments={},
        ),
        ToolCall(
            requestor="user",
            name="check_ssl_in_browser",
            arguments={"url": "https://mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="confirm_site_working",
            arguments={},
        ),
    ]


# --- Group 3: Web Server Fixes ---

def fix_persistent_server_failure(env: HostingEnvironment) -> list[ToolCall]:
    """Unfixable: agent checks logs, attempts restart (fails), escalates to human."""
    return [
        ToolCall(
            requestor="assistant",
            name="check_server_logs",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="assistant",
            name="restart_web_server",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="assistant",
            name="transfer_to_human",
            arguments={"summary": "Server SRV001 has hardware failure. Restart failed. Requires data center intervention."},
        ),
    ]


def fix_server_crashed(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent checks logs, restarts server, user hard-refreshes."""
    return [
        ToolCall(
            requestor="assistant",
            name="check_server_logs",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="assistant",
            name="restart_web_server",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="user",
            name="hard_refresh_page",
            arguments={"url": "https://mybusiness.com"},
        ),
    ]


def fix_server_wrong_port(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent updates config, restarts server, user tests."""
    return [
        ToolCall(
            requestor="assistant",
            name="update_server_config",
            arguments={"server_id": "SRV001", "setting_name": "port", "setting_value": 443},
        ),
        ToolCall(
            requestor="assistant",
            name="restart_web_server",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="user",
            name="test_website",
            arguments={"url": "https://mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="confirm_site_working",
            arguments={},
        ),
    ]


# --- Group 4: Database Fixes ---

def fix_database_crashed(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent restarts DB, user hard-refreshes."""
    return [
        ToolCall(
            requestor="assistant",
            name="restart_database",
            arguments={"db_id": "DB001"},
        ),
        ToolCall(
            requestor="user",
            name="hard_refresh_page",
            arguments={"url": "https://mybusiness.com"},
        ),
    ]


def fix_database_max_connections(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent increases max connections, restarts DB, user tests."""
    return [
        ToolCall(
            requestor="assistant",
            name="increase_db_connections",
            arguments={"db_id": "DB001", "new_max": 200},
        ),
        ToolCall(
            requestor="assistant",
            name="restart_database",
            arguments={"db_id": "DB001"},
        ),
        ToolCall(
            requestor="user",
            name="test_website",
            arguments={"url": "https://mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="confirm_site_working",
            arguments={},
        ),
    ]


# --- Group 5: Deployment Fixes ---

def fix_bad_deployment(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent checks deployment, rolls back, user clears cache, user confirms."""
    return [
        ToolCall(
            requestor="assistant",
            name="check_deployment_status",
            arguments={"deployment_id": "DEP001"},
        ),
        ToolCall(
            requestor="assistant",
            name="rollback_deployment",
            arguments={"deployment_id": "DEP001"},
        ),
        ToolCall(
            requestor="user",
            name="clear_browser_cache",
            arguments={},
        ),
        ToolCall(
            requestor="user",
            name="confirm_site_working",
            arguments={},
        ),
    ]


def fix_deployment_config_error(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent updates server config, restarts server, user tests."""
    return [
        ToolCall(
            requestor="assistant",
            name="update_server_config",
            arguments={"server_id": "SRV001", "setting_name": "port", "setting_value": 443},
        ),
        ToolCall(
            requestor="assistant",
            name="restart_web_server",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="user",
            name="test_website",
            arguments={"url": "https://mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="confirm_site_working",
            arguments={},
        ),
    ]


# --- Group 6: Performance Fixes ---

def fix_server_cache_full(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent clears server cache, user clears browser cache, user hard-refreshes."""
    return [
        ToolCall(
            requestor="assistant",
            name="clear_server_cache",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="user",
            name="clear_browser_cache",
            arguments={},
        ),
        ToolCall(
            requestor="user",
            name="hard_refresh_page",
            arguments={"url": "https://mybusiness.com"},
        ),
    ]


def fix_slow_response(env: HostingEnvironment) -> list[ToolCall]:
    """Fix: agent checks logs, restarts server, user runs speed test."""
    return [
        ToolCall(
            requestor="assistant",
            name="check_server_logs",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="assistant",
            name="restart_web_server",
            arguments={"server_id": "SRV001"},
        ),
        ToolCall(
            requestor="user",
            name="run_speed_test",
            arguments={"url": "https://mybusiness.com"},
        ),
        ToolCall(
            requestor="user",
            name="confirm_site_working",
            arguments={},
        ),
    ]


# === Scenario Definitions ===

# Group 1: DNS Issues (2 scenarios)
dns_wrong_ip_scenario = Scenario(
    name="dns_wrong_ip",
    description="DNS A record points to wrong IP, site unreachable",
    init_funcs=[init_dns_wrong_ip],
    fix_funcs=[fix_dns_wrong_ip],
)

dns_missing_mx_scenario = Scenario(
    name="dns_missing_mx",
    description="MX record issue, email delivery broken",
    init_funcs=[init_dns_missing_mx],
    fix_funcs=[fix_dns_missing_mx],
)

dns_group = ScenarioGroup(
    scenarios=[dns_wrong_ip_scenario, dns_missing_mx_scenario]
)

# Group 2: SSL Issues (2 scenarios)
ssl_expired_scenario = Scenario(
    name="ssl_expired",
    description="SSL certificate expired, browser shows security warnings",
    init_funcs=[init_ssl_expired],
    fix_funcs=[fix_ssl_expired],
)

ssl_misconfigured_scenario = Scenario(
    name="ssl_misconfigured",
    description="SSL certificate misconfigured for wrong domain",
    init_funcs=[init_ssl_misconfigured],
    fix_funcs=[fix_ssl_misconfigured],
)

ssl_group = ScenarioGroup(
    scenarios=[ssl_expired_scenario, ssl_misconfigured_scenario]
)

# Group 3: Web Server Issues (3 scenarios, 1 unfixable)
server_crashed_scenario = Scenario(
    name="server_crashed",
    description="Web server crashed, returning 502 Bad Gateway",
    init_funcs=[init_server_crashed],
    fix_funcs=[fix_server_crashed],
)

persistent_server_failure_scenario = Scenario(
    name="persistent_server_failure",
    description="Server hardware failure, cannot restart remotely, requires escalation",
    init_funcs=[init_persistent_server_failure],
    fix_funcs=[fix_persistent_server_failure],
)

server_wrong_port_scenario = Scenario(
    name="server_wrong_port",
    description="Server listening on wrong port after config change",
    init_funcs=[init_server_wrong_port],
    fix_funcs=[fix_server_wrong_port],
)

server_group = ScenarioGroup(
    scenarios=[server_crashed_scenario, persistent_server_failure_scenario, server_wrong_port_scenario]
)

# Group 4: Database Issues (2 scenarios)
database_crashed_scenario = Scenario(
    name="database_crashed",
    description="Database server crashed, causing 500 errors",
    init_funcs=[init_database_crashed],
    fix_funcs=[fix_database_crashed],
)

database_max_connections_scenario = Scenario(
    name="database_max_connections",
    description="Database connection limit reached, intermittent 500 errors",
    init_funcs=[init_database_max_connections],
    fix_funcs=[fix_database_max_connections],
)

database_group = ScenarioGroup(
    scenarios=[database_crashed_scenario, database_max_connections_scenario]
)

# Group 5: Deployment Issues (2 scenarios)
bad_deployment_scenario = Scenario(
    name="bad_deployment",
    description="Latest deployment failed and broke the site",
    init_funcs=[init_bad_deployment],
    fix_funcs=[fix_bad_deployment],
)

deployment_config_error_scenario = Scenario(
    name="deployment_config_error",
    description="Deployment changed server config incorrectly",
    init_funcs=[init_deployment_config_error],
    fix_funcs=[fix_deployment_config_error],
)

deployment_group = ScenarioGroup(
    scenarios=[bad_deployment_scenario, deployment_config_error_scenario]
)

# Group 6: Performance Issues (2 scenarios)
server_cache_full_scenario = Scenario(
    name="server_cache_full",
    description="Server cache causing stale/incorrect page content",
    init_funcs=[init_server_cache_full],
    fix_funcs=[fix_server_cache_full],
)

slow_response_scenario = Scenario(
    name="slow_response",
    description="Server overloaded, very slow page load times",
    init_funcs=[init_slow_response],
    fix_funcs=[fix_slow_response],
)

performance_group = ScenarioGroup(
    scenarios=[server_cache_full_scenario, slow_response_scenario]
)

# All scenario groups - ORDER MATTERS: infrastructure first, then application-level
SCENARIO_GROUPS = [
    dns_group,          # Group 1: DNS fixes first (foundation)
    ssl_group,          # Group 2: SSL fixes second (security layer)
    server_group,       # Group 3: Web server fixes third (application layer)
    database_group,     # Group 4: Database fixes fourth (data layer)
    deployment_group,   # Group 5: Deployment fixes fifth (code layer)
    performance_group,  # Group 6: Performance fixes last (capacity)
]
