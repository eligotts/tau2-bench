# Prompt 08: Runtime Environment + Sync Wiring (Refine Pass)

## Instruction

Refine the environment authored in Step 02.
Do not allow `sync_tools()` semantics to drift from contract effects/gates.

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
5. Name every contract-visible tool explicitly so the prompt surface matches the runtime surface.
6. If any binding is a volatile stage token, explicitly name the reread points where the agent must reacquire it.
7. If `check_resolution_status` exists, explicitly tell the agent to continue when it returns `resolved=false` and to stop only on `resolved=true`.
8. Prefer sections like observables, available repair tools, customer-side actions, and stop rules over numbered "first do X, then do Y" trajectories.
9. If the domain truly needs a detailed troubleshooting manual, keep it as a separate artifact and make sure the benchmark intent still relies on agent reasoning rather than rote prompt following.

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
2. `sync_tools()` must implement only the declared `sync_rules` from `graph_contract.yaml`.
3. Keep sync logic declarative in shape:
   - unconditional projections copy from one projected path to another
   - conditional sync logic is expressed as explicit prereqs + literal effects
   - no hidden sync-only cascades that are absent from the contract
4. `sync_tools()` must project every stop-gate observable field needed by `check_resolution_status`.
5. Implement `get_environment(...)` that loads DB/user DB + policy and returns environment.
6. Implement `get_tasks(...)` and optional task split loader using current task file.
7. Keep loader compatible with tau2 `Task` model.
8. Keep `sync_tools()` idempotent: repeated calls without intervening tool actions should not create new deltas.
9. `sync_tools()` must produce the same derived state when run against the initial start world as it does after later tool calls; do not rely on post-init-only fixes.

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
