import random
from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.online_shopping.data_model import OnlineShoppingDB
from tau2.domains.online_shopping.tools import OnlineShoppingTools
from tau2.domains.online_shopping.user_data_model import (
    OnlineShoppingUserDB,
    OrderSummary,
    ReturnSummary,
)
from tau2.domains.online_shopping.user_tools import OnlineShoppingUserTools
from tau2.domains.online_shopping.utils import (
    ONLINE_SHOPPING_DB_PATH,
    ONLINE_SHOPPING_POLICY_PATH,
    ONLINE_SHOPPING_TASK_SET_PATH,
    ONLINE_SHOPPING_USER_DB_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


class OnlineShoppingEnvironment(Environment):
    tools: OnlineShoppingTools
    user_tools: OnlineShoppingUserTools

    def __init__(
        self,
        domain_name: str,
        policy: str,
        tools: OnlineShoppingTools,
        user_tools: OnlineShoppingUserTools,
    ):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """Synchronize agent-side DB state into user-visible summaries.

        Projects:
        1. Order summaries (basic info for user view)
        2. Return summaries
        3. Bridges user payment_info_updated back to agent payment methods
        """
        if self.user_tools.db.customer_id is None:
            return

        customer_id = self.user_tools.db.customer_id

        # 1. Sync order summaries
        self.user_tools.db.my_orders = [
            OrderSummary(
                order_id=o.order_id,
                product_name=o.product_name,
                total=o.total,
                status=o.status,
                shipping_method=o.shipping_method,
            )
            for o in self.tools.db.orders
            if o.customer_id == customer_id
        ]

        # 2. Sync return summaries
        self.user_tools.db.my_returns = [
            ReturnSummary(
                return_id=r.return_id,
                product_name=r.product_name,
                status=r.status,
                refund_amount=r.refund_amount,
            )
            for r in self.tools.db.return_requests
            if r.customer_id == customer_id
        ]

        # 3. Bridge user payment updates back to agent DB
        for pm in self.tools.db.payment_methods:
            if pm.customer_id == customer_id:
                if self.user_tools.db.payment_info_updated.get(pm.payment_id, False):
                    pm.status = "active"


def get_environment(
    db: Optional[OnlineShoppingDB] = None,
    user_db: Optional[OnlineShoppingUserDB] = None,
    solo_mode: bool = False,
) -> OnlineShoppingEnvironment:
    """Factory function to create the online shopping environment."""
    if db is None:
        db = OnlineShoppingDB.load(ONLINE_SHOPPING_DB_PATH)
    tools = OnlineShoppingTools(db)
    if user_db is None:
        user_db = OnlineShoppingUserDB.load(ONLINE_SHOPPING_USER_DB_PATH)
    user_tools = OnlineShoppingUserTools(user_db)
    policy = load_file(ONLINE_SHOPPING_POLICY_PATH)
    env = OnlineShoppingEnvironment(
        domain_name="online_shopping",
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
    if not ONLINE_SHOPPING_TASK_SET_PATH.exists():
        return []
    tasks = load_tasks(ONLINE_SHOPPING_TASK_SET_PATH)
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
        Path(ONLINE_SHOPPING_TASK_SET_PATH).parent
        / f"split_{Path(ONLINE_SHOPPING_TASK_SET_PATH).stem}.json"
    )
    if split_file.exists():
        return load_file(split_file)
    return None
