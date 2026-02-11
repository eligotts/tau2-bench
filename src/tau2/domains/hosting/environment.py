from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.hosting.data_model import HostingDB
from tau2.domains.hosting.tools import HostingTools
from tau2.domains.hosting.user_data_model import HostingUserDB
from tau2.domains.hosting.user_tools import HostingUserTools
from tau2.domains.hosting.utils import (
    HOSTING_DB_PATH,
    HOSTING_POLICY_PATH,
    HOSTING_TASK_SET_PATH,
    HOSTING_USER_DB_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


class HostingEnvironment(Environment):
    tools: HostingTools
    user_tools: HostingUserTools

    def __init__(
        self,
        domain_name: str,
        policy: str,
        tools: HostingTools,
        user_tools: HostingUserTools,
    ):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """
        Synchronize user-side (browser) state with agent-side (infrastructure) state.

        Sync rules (order matters):
        1. DNS check: If A record value != account.server_ip -> dns_resolves=False, site doesn't load
        2. SSL check: If SSL status != "valid" -> ssl_warning=True
        3. Server check: If web server not "running" -> site doesn't load (502/503)
        4. Database check: If database not "running" -> error_code="500"
        5. Deployment check: If deployment status == "failed" -> error_code="500"
        6. All healthy: If all checks pass -> site loads, fast response, correct content
        7. Cache/DNS staleness: browser_cache_stale and local_dns_stale are NOT cleared by sync
        """
        account = self.db.account
        website = self.user_tools.db.website

        # Determine infrastructure health
        dns_ok = True
        ssl_ok = True
        server_ok = True
        database_ok = True
        deployment_ok = True
        error_code = None

        # Rule 1: DNS check
        a_record = None
        for record in self.db.dns_records:
            if record.record_type == "A" and record.domain == account.domain:
                a_record = record
                break

        if a_record is None or a_record.value != account.server_ip:
            dns_ok = False
            error_code = "dns_error"
            self.user_tools.db.dns_resolves = False
        else:
            self.user_tools.db.dns_resolves = True

        # Rule 2: SSL check
        ssl_cert = None
        for cert in self.db.ssl_certificates:
            if cert.domain == account.domain:
                ssl_cert = cert
                break

        if ssl_cert is None or ssl_cert.status != "valid":
            ssl_ok = False

        # Rule 3: Server check
        server = self.db.servers[0] if self.db.servers else None
        if server is None or server.status not in ("running",):
            server_ok = False
            if error_code is None:
                if server and server.status == "crashed":
                    error_code = "502"
                else:
                    error_code = "503"

        # Rule 4: Database check
        database = self.db.databases[0] if self.db.databases else None
        if database is None or database.status != "running":
            database_ok = False
            if error_code is None:
                error_code = "500"

        # Also check connection limits
        if database and database.status == "running" and database.current_connections >= database.max_connections:
            database_ok = False
            if error_code is None:
                error_code = "500"

        # Rule 5: Deployment check
        deployment = self.db.deployments[0] if self.db.deployments else None
        if deployment and deployment.status == "failed":
            deployment_ok = False
            if error_code is None:
                error_code = "500"

        # Rule 6: Determine final state
        all_ok = dns_ok and ssl_ok and server_ok and database_ok and deployment_ok

        if all_ok:
            website.loads_successfully = True
            website.response_time_ms = 250
            website.error_code = None
            website.ssl_warning = False
            website.page_content_correct = True
        elif not dns_ok:
            website.loads_successfully = False
            website.response_time_ms = -1
            website.error_code = "dns_error"
            website.ssl_warning = False
            website.page_content_correct = False
        elif not server_ok:
            website.loads_successfully = False
            website.response_time_ms = -1
            website.error_code = error_code
            website.ssl_warning = False
            website.page_content_correct = False
        elif not database_ok or not deployment_ok:
            website.loads_successfully = False
            website.response_time_ms = -1
            website.error_code = "500"
            website.ssl_warning = False
            website.page_content_correct = False
        elif not ssl_ok:
            # Site loads but with SSL warning
            website.loads_successfully = True
            website.response_time_ms = 250
            website.error_code = None
            website.ssl_warning = True
            website.page_content_correct = True

        # Post-fix: server error_log causes slow response even when running
        server = self.db.servers[0] if self.db.servers else None
        if server and server.status == "running" and server.error_log and website.loads_successfully:
            website.response_time_ms = 5000

        # Post-fix: server_cache_stale causes incorrect content even when running
        if self.db.server_cache_stale and website.loads_successfully:
            website.page_content_correct = False

        # Check MX record for email (value must be non-empty)
        mx_record = None
        for record in self.db.dns_records:
            if record.record_type == "MX" and record.domain == account.domain and record.value:
                mx_record = record
                break
        self.user_tools.db.email_working = (mx_record is not None and dns_ok and server_ok)

        # Rule 7: browser_cache_stale and local_dns_stale are NOT cleared by sync

    @property
    def db(self) -> HostingDB:
        return self.tools.db


def get_environment(
    db: Optional[HostingDB] = None,
    user_db: Optional[HostingUserDB] = None,
    solo_mode: bool = False,
) -> HostingEnvironment:
    if db is None:
        db = HostingDB.load(HOSTING_DB_PATH)
    tools = HostingTools(db)
    if user_db is None:
        user_db = HostingUserDB.load(HOSTING_USER_DB_PATH)
    user_tools = HostingUserTools(user_db)
    policy = load_file(HOSTING_POLICY_PATH)
    env = HostingEnvironment(
        domain_name="hosting",
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def load_tasks(path: str) -> list[Task]:
    """Load tasks from a JSON file."""
    tasks = load_file(path)
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    return [Task.model_validate(task) for task in tasks]


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    if not HOSTING_TASK_SET_PATH.exists():
        return []
    tasks = load_tasks(HOSTING_TASK_SET_PATH)
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_splits is None or task_split_name not in task_splits:
        return tasks
    return [task for task in tasks if task.id in task_splits[task_split_name]]


def get_tasks_split() -> Optional[dict[str, list[str]]]:
    split_file = Path(HOSTING_TASK_SET_PATH).parent / f"split_{Path(HOSTING_TASK_SET_PATH).stem}.json"
    if split_file.exists():
        return load_file(split_file)
    return None
