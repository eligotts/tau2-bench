# Prompt 08: Runtime Environment + Sync Wiring (Refine Pass)

## Instruction

Refine the environment authored in Step 02.
Sync rules in the graph contract are the single source of truth.
`sync_tools()` must delegate to `run_contract_sync()` from the `runtime_sync` module.

Inputs:

- `src/tau2/domains/<domain>/data_model.py`
- `src/tau2/domains/<domain>/user_data_model.py`
- `src/tau2/domains/<domain>/tools.py`
- `src/tau2/domains/<domain>/user_tools.py`
- `src/tau2/domains/<domain>/utils.py`
- `data/tau2/domains/<domain>/graph_contract.yaml`
- `data/tau2/domains/<domain>/stop_gate_map.yaml`
- `data/tau2/domains/<domain>/task_specs.runtime.yaml`

Author in this order, one minimal file at a time.

## Step 08.1: Policy File

Create:

- `data/tau2/domains/<domain>/policy.md`

Requirements:

1. Write `policy.md` as a behavioral contract and tool-affordance guide, not as a fixed step-by-step solve script.
2. Include user-guidance behavior aligned with task patterns.
3. Mention that user should run tools only when instructed (if this is your design choice).
4. Keep policy consistent with tool capabilities and constraints.
5. **Do NOT list agent tool names in the policy.** Agent tools are injected into the LLM API call with their names, descriptions (from docstrings), and parameter schemas. The agent already knows what tools it has. The policy should teach *when* and *why* to act (domain knowledge, ordering constraints, principles), not *what tools exist*. Duplicating the tool catalog in the policy adds no information and creates maintenance drift.
6. **Do NOT list user tool names in the policy.** The agent does not need to know the user's toolkit. Describe what information or actions the agent needs from the user in natural language (e.g., "ask the user for a dashboard overview" not "ask the user to run `check_dashboard`"). The user discovers their own tools; the agent asks for outcomes.
7. If any binding is a volatile stage token, describe the reread points where the agent must reacquire it in domain terms, not tool names.
8. If `check_resolution_status` exists, tell the agent to ask the user to check whether resolution criteria are met, to continue when unmet, and to stop only when all criteria are confirmed met.
9. Prefer sections like domain principles, dependency ordering, side-effect warnings, and resolution criteria over numbered "first do X, then do Y" trajectories.
10. If the domain truly needs a detailed troubleshooting manual, keep it as a separate artifact and make sure the benchmark intent still relies on agent reasoning rather than rote prompt following.
11. **Write good tool docstrings instead.** The tool docstring is the right place to describe what a tool does, what state it applies to, and what prerequisites it has. The policy teaches domain reasoning; the tool list teaches tool affordances.

Validation:

```bash
uv run python - <<'PY'
from pathlib import Path
p = Path("data/tau2/domains/<domain>/policy.md")
print("exists", p.exists(), "chars", len(p.read_text()))
PY
```

Pass condition:

- Policy exists and is non-empty.

## Step 08.2: Environment Implementation

Create:

- `src/tau2/domains/<domain>/environment.py`

Requirements:

1. Define `<Domain>Environment(Environment)` with `sync_tools()`.
2. `sync_tools()` must call `run_contract_sync()` from `tau2.generators.depgraph.runtime_sync`. This is the single source of truth for sync logic. Do not reimplement contract sync rules as hand-written Python in the environment.
3. To wire `run_contract_sync()`:
   - Load the graph contract's `sync_rules` and `projection_fields` (typically at environment construction time or from a module-level constant).
   - Create `ToolKitFieldAccessor` instances wrapping the assistant and user toolkits.
   - Call `run_contract_sync(sync_rules, projection_fields, agent_accessor, user_accessor)`.
4. Toolkits must expose `get_<field>()` methods alongside their existing `set_<field>()` methods. The `ToolKitFieldAccessor` adapter reads via `get_<field>()` and writes via `set_<field>()`.
5. View projections (`display_*` fields, formatted summaries) stay as adapter Python code in the environment or toolkit. These are presentation logic, not contract sync rules.
6. `sync_tools()` must project every stop-gate observable field needed by `check_resolution_status`.
7. Implement `get_environment(...)` that loads DB/user DB + policy and returns environment.
8. Implement `get_tasks(...)` and optional task split loader using current task file.
9. Keep loader compatible with tau2 `Task` model.
10. `sync_tools()` must be idempotent: repeated calls without intervening tool actions should not create new deltas.
11. `sync_tools()` must produce the same derived state when run against the initial start world as it does after later tool calls; do not rely on post-init-only fixes.

Example `sync_tools()` wiring:

```python
from tau2.generators.depgraph.runtime_sync import run_contract_sync, ToolKitFieldAccessor

class MyEnvironment(Environment):
    def __init__(self, ...):
        # Load sync_rules and projection_fields from graph contract
        self._sync_rules = contract.sync_rules
        self._projection_fields = contract.projection_fields

    def sync_tools(self):
        agent_accessor = ToolKitFieldAccessor(self.tools)
        user_accessor = ToolKitFieldAccessor(self.user_tools)
        run_contract_sync(
            self._sync_rules,
            self._projection_fields,
            agent_accessor,
            user_accessor,
        )
        # View projections (display_* fields) can follow here as plain Python
```

Validation:

```bash
uv run python - <<'PY'
import importlib
mod = importlib.import_module("tau2.domains.<domain>.environment")
env = mod.get_environment()
print("domain", env.get_domain_name())
print("assistant_tools", len(env.get_tools()) if env.tools else 0)
print("user_tools", len(env.get_user_tools()) if env.user_tools else 0)
env.sync_tools()
print("sync ok")
PY
```

Pass condition:

- Environment constructs and `sync_tools()` runs with no exception.

## Step 08.3: Direct Alignment Check (Pre-Registry)

Run depgraph runtime alignment checks directly against `get_environment` (without registry).

```bash
uv run python - <<'PY'
from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs
from tau2.generators.depgraph.runtime_checks import (
    check_contract_against_environment,
    check_runtime_against_environment,
    check_stop_gate_runtime,
)
from tau2.domains.<domain>.environment import get_environment

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")
tasks = load_task_specs("data/tau2/domains/<domain>/task_specs.runtime.yaml")
stop_gate_issues = check_stop_gate_runtime(tasks, "data/tau2/domains/<domain>/stop_gate_map.yaml")

contract_issues = check_contract_against_environment(contract, get_environment)
runtime_issues = check_runtime_against_environment(tasks, get_environment)

print("contract_issues", len(contract_issues))
for x in contract_issues:
    print(" -", x)
print("runtime_issues", len(runtime_issues))
for x in runtime_issues:
    print(" -", x)
print("stop_gate_issues", len(stop_gate_issues))
for x in stop_gate_issues:
    print(" -", x)
PY
```

Pass condition:

- All issue lists are empty.
