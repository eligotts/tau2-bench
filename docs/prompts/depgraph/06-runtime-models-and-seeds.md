# Prompt 06: Runtime Models + Seed Data (Refine Pass)

## Instruction

Refine runtime data primitives after Step 02 co-authoring.
Do not introduce drift from `graph_contract.yaml`.

Inputs:

- `data/tau2/domains/<domain>/domain_scope.md`
- `data/tau2/domains/<domain>/graph_contract.yaml`
- `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md`

Author in this order, one minimal file at a time.

## Step 06.1: Agent DB Schema

Create:

- `src/tau2/domains/<domain>/data_model.py`

Requirements:

1. Define typed entity models for assistant/world state.
2. Include all fields referenced by projected world paths in `graph_contract.yaml`.
3. Preserve any tool-coupled fields already introduced in Step 02 unless deliberately removed with matching contract update.
4. Define top-level DB model extending `DB`.
5. Keep schema minimal and causal-first (no conversational knowledge fields).
6. Use finite enums for gate-critical fields whenever feasible (avoid free-text state drift).
7. If you promote a previously transient observation into stable agent world state (for example a
   conflict meeting ID, active ticket ID, reservation code, or currently selected object), that
   field becomes part of the generated runtime surface: expect `set_<...>` init actions and
   possibly `assert_<...>` env assertions for it.

Validation:

```bash
uv run python - <<'PY'
import importlib
mod = importlib.import_module("tau2.domains.<domain>.data_model")
print("loaded", mod.__name__)
PY
```

Pass condition:

- Module imports successfully.

## Step 06.2: User DB Schema

Create:

- `src/tau2/domains/<domain>/user_data_model.py`

Requirements:

1. Define user DB model extending `DB`.
2. Include causal user fields for every projected `user.*` world path in contract/tasks.
3. Include projection-only fields needed for stop-gate observability (for example `user.view.*`).
4. Include stop-gate state container (for example `user.stop_gate.criteria`) used by `set_stop_gate`.
5. Optional projection fields are allowed, but keep them separate from causal fields.

Validation:

```bash
uv run python - <<'PY'
import importlib
mod = importlib.import_module("tau2.domains.<domain>.user_data_model")
print("loaded", mod.__name__)
PY
```

Pass condition:

- Module imports successfully.

## Step 06.3: Data Paths

Create:

- `src/tau2/domains/<domain>/utils.py`

Requirements:

1. Define absolute/derived constants for:
   - `db.json` or `db.toml`
   - `user_db.json` or `user_db.toml`
   - `policy.md`
   - task file path (`tasks.depgraph.json` during pilot)
2. Reuse project conventions used by existing domains.

Validation:

```bash
uv run python - <<'PY'
import importlib
mod = importlib.import_module("tau2.domains.<domain>.utils")
print("loaded", mod.__name__)
for name in dir(mod):
    if name.endswith("_PATH"):
        print(name, getattr(mod, name))
PY
```

Pass condition:

- Module imports and exposes expected path constants.

## Step 06.4: Seed Data Files

Create:

- `data/tau2/domains/<domain>/db.json`
- `data/tau2/domains/<domain>/user_db.json`

Requirements:

1. Seed records must support tool arguments used in runtime specs.
2. Initial values should represent baseline clean world, not task-broken states.
3. Include IDs and references needed for task init/actions.
4. `user_db.json` is required for tau2-path domains. Do not rely on in-code defaults alone.
5. Include baseline empty stop-gate config in `user_db.json` (for example `stop_gate.criteria: []`).
6. Seeds should be clean-base defaults; all task breakage should come from runtime init actions.
7. Clean-base files must still include every structural field used by the runtime models, even if
   task-specific values are later injected through init actions.

Validation:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
for p in [
    Path("data/tau2/domains/<domain>/db.json"),
    Path("data/tau2/domains/<domain>/user_db.json"),
]:
    obj = json.loads(p.read_text())
    print(p, "ok", type(obj).__name__)
PY
```

Pass condition:

- Both files parse as valid JSON.

Additional load check (required):

```bash
uv run python - <<'PY'
from tau2.domains.<domain>.environment import get_environment
env = get_environment()
print(env.get_domain_name(), "loaded")
PY
```
