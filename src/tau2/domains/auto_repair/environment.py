import random
from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.auto_repair.data_model import AutoRepairDB
from tau2.domains.auto_repair.tools import AutoRepairTools
from tau2.domains.auto_repair.user_data_model import (
    AutoRepairUserDB,
    InvoiceSummary,
    ServiceOrderSummary,
    VehicleSummary,
)
from tau2.domains.auto_repair.user_tools import AutoRepairUserTools
from tau2.domains.auto_repair.utils import (
    AUTO_REPAIR_DB_PATH,
    AUTO_REPAIR_POLICY_PATH,
    AUTO_REPAIR_TASK_SET_PATH,
    AUTO_REPAIR_USER_DB_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


class AutoRepairEnvironment(Environment):
    tools: AutoRepairTools
    user_tools: AutoRepairUserTools

    def __init__(
        self,
        domain_name: str,
        policy: str,
        tools: AutoRepairTools,
        user_tools: AutoRepairUserTools,
    ):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """Synchronize agent-side DB state into user-visible summaries.

        Projects:
        1. Vehicle summaries (basic info — no diagnostic fields)
        2. Service order summaries
        3. Invoice summaries
        4. Bridges user payment_made back to agent invoices
        """
        if self.user_tools.db.customer_id is None:
            return

        customer_id = self.user_tools.db.customer_id

        # 1. Sync vehicle summaries
        self.user_tools.db.my_vehicles = [
            VehicleSummary(
                vehicle_id=v.vehicle_id,
                make=v.make,
                model=v.model,
                year=v.year,
            )
            for v in self.tools.db.vehicles
            if v.customer_id == customer_id
        ]

        # 2. Sync service order summaries
        customer_vehicles = {
            v.vehicle_id for v in self.tools.db.vehicles
            if v.customer_id == customer_id
        }
        self.user_tools.db.my_orders = [
            ServiceOrderSummary(
                order_id=o.order_id,
                service_type=o.service_type,
                scheduled_date=o.scheduled_date,
                status=o.status,
            )
            for o in self.tools.db.service_orders
            if o.vehicle_id in customer_vehicles
        ]

        # 3. Sync invoice summaries
        self.user_tools.db.my_invoices = [
            InvoiceSummary(
                invoice_id=i.invoice_id,
                total=i.total,
                status=i.status,
                description=i.description,
            )
            for i in self.tools.db.invoices
            if i.customer_id == customer_id
        ]

        # 4. Bridge user payments back to agent DB
        for inv in self.tools.db.invoices:
            if inv.customer_id == customer_id:
                if self.user_tools.db.payment_made.get(inv.invoice_id, False):
                    inv.status = "paid"


def get_environment(
    db: Optional[AutoRepairDB] = None,
    user_db: Optional[AutoRepairUserDB] = None,
    solo_mode: bool = False,
) -> AutoRepairEnvironment:
    """Factory function to create the auto repair environment."""
    if db is None:
        db = AutoRepairDB.load(AUTO_REPAIR_DB_PATH)
    tools = AutoRepairTools(db)
    if user_db is None:
        user_db = AutoRepairUserDB.load(AUTO_REPAIR_USER_DB_PATH)
    user_tools = AutoRepairUserTools(user_db)
    policy = load_file(AUTO_REPAIR_POLICY_PATH)
    env = AutoRepairEnvironment(
        domain_name="auto_repair",
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


def get_tasks(task_split_name: Optional[str] = "base") -> list[Task]:
    """Get tasks for the domain, shuffled for representative sampling."""
    if not AUTO_REPAIR_TASK_SET_PATH.exists():
        return []
    tasks = load_tasks(AUTO_REPAIR_TASK_SET_PATH)
    if task_split_name is None:
        pass
    else:
        task_splits = get_tasks_split()
        if task_splits is not None and task_split_name in task_splits:
            tasks = [task for task in tasks if task.id in task_splits[task_split_name]]
    rng = random.Random(42)
    rng.shuffle(tasks)
    return tasks


def get_tasks_split() -> Optional[dict[str, list[str]]]:
    """Load task splits from JSON if they exist."""
    split_file = (
        Path(AUTO_REPAIR_TASK_SET_PATH).parent
        / f"split_{Path(AUTO_REPAIR_TASK_SET_PATH).stem}.json"
    )
    if split_file.exists():
        return load_file(split_file)
    return None
