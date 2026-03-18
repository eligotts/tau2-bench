from pathlib import Path


DAILY_PLANNER_DATA_DIR = (
    Path(__file__).resolve().parents[4] / "data" / "tau2" / "domains" / "daily_planner"
)
DAILY_PLANNER_DB_PATH = DAILY_PLANNER_DATA_DIR / "db.json"
DAILY_PLANNER_USER_DB_PATH = DAILY_PLANNER_DATA_DIR / "user_db.json"
DAILY_PLANNER_POLICY_PATH = DAILY_PLANNER_DATA_DIR / "policy.md"
DAILY_PLANNER_TASK_SET_PATH = DAILY_PLANNER_DATA_DIR / "tasks.depgraph.json"
