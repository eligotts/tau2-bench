# Prompt 07: Runtime Tools + Setters/Assertions (Refine Pass)

## Instruction

Refine assistant and user toolkits authored in Step 02.
Keep action contracts and tool callables in strict lockstep.

Inputs:

- `data/tau2/domains/<domain>/graph_contract.yaml`
- `data/tau2/domains/<domain>/stop_gate_map.yaml`
- `data/tau2/domains/<domain>/task_specs.runtime.yaml`
- `src/tau2/domains/<domain>/data_model.py`
- `src/tau2/domains/<domain>/user_data_model.py`

Author in this order, one minimal file at a time.

## Step 07.1: Assistant Toolkit

Create:

- `src/tau2/domains/<domain>/tools.py`

Requirements:

1. Implement assistant action tools referenced by contract actions where `requestor=assistant`.
2. Implement helper setter functions referenced by runtime init actions (`set_*` on assistant side).
3. Implement helper assertion functions referenced by runtime env assertions (`assert_*` on assistant side) with bool returns.
4. Use `ToolKitBase` and `@is_tool` for LLM-visible tools.
5. For actions with `requires_bindings`, enforce binding usage at runtime via concrete tool params and guards.
6. For binding-source read tools, use typed return models (Pydantic/dataclass-style) so extraction-path checks are meaningful.

Validation:

```bash
uv run python - <<'PY'
import importlib
mod = importlib.import_module("tau2.domains.<domain>.tools")
print("loaded", mod.__name__)
PY
```

Pass condition:

- Module imports successfully.

## Step 07.2: User Toolkit

Create:

- `src/tau2/domains/<domain>/user_tools.py`

Requirements:

1. Implement user action tools referenced by contract actions where `requestor=user`.
2. Implement read/discovery tools required by `bindings[].source_tool`.
3. Implement user-side setter/assertion helpers referenced by runtime specs.
4. Ensure stutter-only read tools do not mutate causal fields.
5. Implement strict stop-gate callables:
   - init helper `set_stop_gate(criteria=[...])`
   - read tool `check_resolution_status()` that evaluates all criteria and returns `{resolved, unmet, observed}`.
6. `check_resolution_status()` must be deterministic and side-effect free (stutter-only semantics).

Validation:

```bash
uv run python - <<'PY'
import importlib
mod = importlib.import_module("tau2.domains.<domain>.user_tools")
print("loaded", mod.__name__)
PY
```

Pass condition:

- Module imports successfully.

## Step 07.3: Callable Coverage Check (Without Environment)

Run a direct coverage audit against contract/runtime names.

```bash
uv run python - <<'PY'
import yaml
from pathlib import Path

contract = yaml.safe_load(Path("data/tau2/domains/<domain>/graph_contract.yaml").read_text())
runtime_doc = yaml.safe_load(Path("data/tau2/domains/<domain>/task_specs.runtime.yaml").read_text())

assistant_needed = set()
user_needed = set()

for a in contract["actions"]:
    tn = a["tool_name"]
    if a["requestor"] == "assistant":
        assistant_needed.add(tn)
    else:
        user_needed.add(tn)

for src in contract.get("bindings", []):
    user_needed.add(src["source_tool"])

for t in runtime_doc["tasks"]:
    rt = t.get("runtime", {})
    for c in rt.get("initialization_actions", []):
        (assistant_needed if c["env_type"] == "assistant" else user_needed).add(c["func_name"])
    for c in rt.get("env_assertions", []):
        (assistant_needed if c["env_type"] == "assistant" else user_needed).add(c["func_name"])

print("assistant callables needed:", sorted(assistant_needed))
print("user callables needed:", sorted(user_needed))
PY
```

Pass condition:

- You have an explicit checklist of required callables before environment wiring.

Optional but recommended checker sanity test:

```bash
uv run python - <<'PY'
from tau2.domains.<domain>.environment import get_environment
env = get_environment()
before = env.user_tools.db.model_dump()
_ = getattr(env.user_tools, "check_resolution_status")()
after = env.user_tools.db.model_dump()
print("stutter_ok", before == after)
PY
```

## Step 07.4: Contract/Tool Linkage Gate

Run strict linkage check and fail closed.

```bash
uv run python - <<'PY'
from tau2.generators.depgraph.loaders import load_graph_contract
from tau2.generators.depgraph.runtime_checks import check_contract_against_environment
from tau2.domains.<domain>.environment import get_environment

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")
issues = check_contract_against_environment(contract, get_environment, strict_full_coverage=True)
print("issues", len(issues))
for issue in issues:
    print(" -", issue)
raise SystemExit(1 if issues else 0)
PY
```
