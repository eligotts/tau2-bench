# Step 9: Environment (environment.py)

Generate the environment module — the glue that connects agent tools, user tools, DB loading, and state synchronization.

## Reference

- Read `docs/domain-authoring-guide.md` lines 462-552 (Environment) and 1172-1257 (Gotchas)
- Read `src/tau2/domains/library/environment.py` for the exact pattern

## Context

- Read `src/tau2/domains/<domain_name>/utils.py` (already created by scaffold — import path constants from here)
- Read `src/tau2/domains/<domain_name>/data_model.py`
- Read `src/tau2/domains/<domain_name>/user_data_model.py`
- Read `src/tau2/domains/<domain_name>/tools.py`
- Read `src/tau2/domains/<domain_name>/user_tools.py`
- Read `data/tau2/domains/<domain_name>/domain_spec.json` — especially `sync_rules`

## Output

Write to `src/tau2/domains/<domain_name>/environment.py`.

## Requirements

### Imports

```python
import random
from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.<domain_name>.data_model import <DomainClass>DB
from tau2.domains.<domain_name>.tools import <DomainClass>Tools
from tau2.domains.<domain_name>.user_data_model import <DomainClass>UserDB, <SummaryClass1>, ...
from tau2.domains.<domain_name>.user_tools import <DomainClass>UserTools
from tau2.domains.<domain_name>.utils import (
    <UPPER>_DB_PATH,
    <UPPER>_POLICY_PATH,
    <UPPER>_TASK_SET_PATH,
    <UPPER>_USER_DB_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file
```

**CRITICAL:** Do NOT define your own path constants. Import them from `utils.py`.

### Environment Class

```python
class <DomainClass>Environment(Environment):
    tools: <DomainClass>Tools
    user_tools: <DomainClass>UserTools

    def __init__(self, domain_name, policy, tools, user_tools):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """Synchronize agent-side DB state into user-visible summaries."""
        ...
```

### sync_tools() Requirements

CRITICAL: `sync_tools()` is called after EVERY `run_env_function_call`. This means during init, sync happens between each step. Design it to be idempotent and resilient.

1. **Early return** if identity is not set: `if self.user_tools.db.patron_id is None: return`
2. **Project agent DB → user summaries** for each sync rule in the domain spec
3. **Bridge user actions back to agent DB** (the bridging pattern):
   - When a user WRITE tool modifies user_db state that an agent tool depends on, sync_tools MUST bridge that state from user_db to agent_db
   - Without this bridge, the agent tool cannot detect whether the user has acted

### Factory Function

```python
def get_environment(
    db=None, user_db=None, solo_mode=False
) -> <DomainClass>Environment:
    """Factory function to create the environment."""
    if db is None:
        db = <DomainClass>DB.load(<UPPER>_DB_PATH)
    tools = <DomainClass>Tools(db)
    if user_db is None:
        user_db = <DomainClass>UserDB.load(<UPPER>_USER_DB_PATH)
    user_tools = <DomainClass>UserTools(user_db)
    policy = load_file(<UPPER>_POLICY_PATH)
    env = <DomainClass>Environment(
        domain_name="<domain_name>",
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env
```

### Task Loading Functions

Include `load_tasks(path)`, `get_tasks(task_split_name="base")`, and `get_tasks_split()` — follow the library example exactly.

## Validation

The validator will:
- Check for no self-defined path constants (must import from utils)
- Check Python syntax
- Import the module
- Check `get_environment()` exists and returns an `Environment` instance
- Check `get_environment(solo_mode=True)` works
- Check `env.tools.get_tools()` works
- Check `env.sync_tools()` works without error
