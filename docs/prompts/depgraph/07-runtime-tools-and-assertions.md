# Prompt 07: Runtime Tools + Setters/Assertions (Refine Pass)

## Instruction

Refine assistant and user toolkits authored in Step 02.
Keep action contracts and tool callables in strict lockstep.

Note: Init setters (`set_<name>`), env assertions (`assert_<name>`), `set_user_context`,
and `bind_agent_db`/`_get_agent_derived` should already exist from Step 02 authoring.
This step is for refinement, coverage gaps, and the callable coverage audit — not for
introducing these methods from scratch.

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
2. Verify/refine init setter functions (`set_*`) authored in Step 02 — ensure all runtime init actions resolve.
3. Verify/refine env assertion functions (`assert_*`) authored in Step 02 — ensure all runtime env assertions resolve with bool returns.
4. Use `ToolKitBase` and `@is_tool` for LLM-visible tools.
5. For actions with `requires_bindings`, enforce binding usage at runtime via concrete tool params and guards.
6. If contract actions use finite literal tool args for a runtime tool param (for example via
   `tool_arg_literals` or `action_schemas` variants), annotate that Python parameter as
   `Literal[...]` or an `Enum`, not plain `str`, so the generated tool schema exposes the valid
   values to the agent.
7. For binding-source read tools, use typed return models (Pydantic/dataclass-style) so extraction-path checks are meaningful.
8. If a binding is tied to a volatile `world_path`, keep its runtime guard narrow:
   - immediate observation-driven steps may validate the current bound value
   - the longer repair chain should run from stable world state established by earlier tools
   - do not require the agent to keep replaying a moving screen code through every repair call
9. **Docstring rule**: Tool docstrings become the `description` field in the OpenAI function-calling schema sent to the agent LLM. They must NOT reference entity type names (e.g. "station", "account", "session") because the agent will interpret these as information it needs to gather from the user. All entity resolution is context-scoped (via `set_user_context`), so the agent never needs entity identifiers. Use neutral phrasing like "Run backend diagnostics for the current charging session" instead of "Run backend diagnostics for the active station context."
10. **Guard audit rule.** For every tool method, enumerate every `if` condition that
   gates an early return (noop, error). For each guarded field, verify: (a) the
   field is in `projection_fields`, and (b) the field appears in the corresponding
   action's `requires_world` with the enabling value. If a tool must check a
   sub-field for correctness (e.g. idempotency on a secondary field like
   `token_pool`), either add it to the contract or restructure the guard so the
   contract's declared preconditions are sufficient. Common violation pattern: a
   tool checks `if sub_field == DEFAULT: return noop` where `sub_field` is not in
   the contract — the scaffold never sets it away from the default, so the tool
   always noops.
11. Implement helper coverage for generated runtime, not just for the examples you expect to
   hand-test. If an expanded sampled task can set or assert a field, the proper toolkit must
   expose the matching deterministic helper.
12. Stable replacements for formerly volatile values need full helper coverage. If you promote
   an ID or selected object into stable world state, expect runtime init actions to set it.
13. Tools exercised by completeness checks should tolerate contract-shaped serialized values.
   If a validator passes a numeric or enum-like value through a binding, coerce it safely
   instead of raising a type error from the Python annotation mismatch.

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
2. Implement any user-side read/discovery tools referenced by `bindings[].source_tool` (source tools can live in either the assistant or user toolkit — put them wherever makes most sense for the domain).
3. Verify/refine user-side setter/assertion helpers authored in Step 02 — ensure all runtime specs resolve.
4. Ensure stutter-only read tools do not mutate causal fields.
5. Implement strict stop-gate callables:
   - init helper `set_stop_gate(criteria=[...])`
   - read tool `check_resolution_status()` that evaluates all criteria and returns `{resolved, unmet}`.
   - `criteria` come from the user-observable subset of terminal `goal_world`, not necessarily every terminal predicate.
6. `check_resolution_status()` must be deterministic and side-effect free (stutter-only semantics).
7. Keep `check_resolution_status()` minimal:
   - `unmet` should use human-readable unmet reasons from stop-gate rules
   - do not return a broad structured `observed` snapshot or raw internal field/value dumps
   - the checker is for stop confirmation, not for giving the agent a rich progress oracle
8. Expect runtime env assertions to enforce both:
   - captured changed end-state values from `goal_world`
   - unchanged authored `start_world` paths outside that captured goal
   The stop gate remains a user-observable subset only; it is not the full frame checker.
9. User-tool deterministic helpers matter too. If generated init/assert actions touch `user.*`
   state (for example confirmation flags), implement the matching `set_<...>` / `assert_<...>`
   callables on `user_tools.py`.

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
    # source_tool can be in either toolkit; check actions to determine requestor
    source_tool_name = src["source_tool"]
    # Default to user if ambiguous; the runtime check validates against both toolkits
    if any(a["tool_name"] == source_tool_name and a["requestor"] == "assistant" for a in contract["actions"]):
        assistant_needed.add(source_tool_name)
    else:
        user_needed.add(source_tool_name)

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
- The checklist covers helper callables generated from expanded seed/task combinations, not only
  the smallest hand-inspected examples.

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

## Action Checks vs Env Assertions — Argument Comparison Pitfall

Action checks (`compare_args`) verify that a tool was called during the conversation.
Env assertions verify the final DB state after the conversation ends.

**Rule: always use `compare_args: []` for action expectations.** This checks only that the
tool was called by name, without comparing argument values.

Why: binding values (like `fault_code`) are resolved from the *initial* world state, but
the environment's state machine may shift argument values during execution. For example,
sync-rule recomputation can change the canonical `last_fault_code` after a repair step,
invalidating the earlier binding and requiring the agent to reacquire it before a later
tool call. The agent correctly uses the updated code, the env assertion passes (correct
final state), but the action check fails because it compared against the stale initial value.

Env assertions are the correct mechanism for verifying that the right outcome was achieved.
Action checks should only confirm the tool was invoked, not police its arguments.

The scaffold generator (`runtime_scaffold.py`) enforces this by always emitting
`compare_args: []`.

If the domain can require repeated binding reacquisition, `ACTION` should usually be treated as
coverage only, not as the primary reward basis. Use `ENV_ASSERTION` and stop-gate checks for
actual task correctness.

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

## Step 07.5: Guard Completeness Gate

Verify that every causal tool succeeds when all contract-declared preconditions
are met. Catches hidden guards on fields not in `requires_world`.

```bash
uv run python - <<'PY'
from tau2.generators.depgraph.loaders import load_graph_contract
from tau2.generators.depgraph.runtime_checks import check_tool_guard_completeness
from tau2.domains.<domain>.environment import get_environment

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")
issues = check_tool_guard_completeness(contract, get_environment)
print("issues", len(issues))
for issue in issues:
    print(" -", issue)
raise SystemExit(1 if issues else 0)
PY
```

If this check fails, either:
- Add the missing field to `projection_fields` and the action's `requires_world`, or
- Remove the hidden guard from the tool so the contract's preconditions are sufficient.
