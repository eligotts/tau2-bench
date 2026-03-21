# Prompt 02v: Co-Author Contract + Tool Functions (Verifiers Path)

> Use this step instead of `02-graph-contract.md` when building for the **verifiers** adapter
> (agent-only `StatefulToolEnv`, no user simulator).

## Instruction

Author the graph contract and tool functions together so `action.tool_name` is immediately
real. Because verifiers environments are agent-only, there are no user tools, no personas,
no user data model, and no sync rules.

Target files:

- `data/tau2/domains/<domain>/graph_contract.yaml`
- `src/tau2/domains/<domain>/tools.py`

### What is different from the tau2 path (Step 02)

| Concept | tau2 path | Verifiers path |
|---|---|---|
| User simulator | `user_tools.py`, personas, `user_data_model.py` | None — agent-only |
| Sync rules | `sync_rules` in contract + `sync_tools()` in `environment.py` | None — single DB, no split |
| DB location | `self.db` on Environment class | `state["db"]` on verifiers State dict |
| Tool signature | `(self, ..., db=None)` style on Environment | Standalone `def tool_name(db, ...)` |
| Policy | `policy.md` agent-facing document | System prompt string |
| Stop condition | `check_resolution_status` user tool + `###STOP###` | Built-in `no_tools_called` from `StatefulToolEnv` |
| Runtime scaffold | 8-step deterministic pipeline | Single `compile_for_verifiers()` call |

### What is the same

The graph contract (`graph_contract.yaml`) uses **identical primitives** on both paths:

- `ActionContract` with `requires_world`, `effects_world`, `requires_bindings`, `effects_bindings`
- `BindingSourceSpec` for knowledge acquisition
- `TerminalProfileSpec` for valid end states over world state only
- BFS solver, preflight, and sampler all work unchanged
- `SamplingRequestDoc` and `SeedSchemaSpec` for fan-out

The contract is the shared artifact. Only the "last mile" — how tasks are compiled into
runnable environments — differs between tau2 and verifiers.

## Requirements

### Graph Contract (`graph_contract.yaml`)

1. Every callable action has classification: `causal`, `knowledge-only`, or `stutter-only`.
2. Define `projection_fields` covering task-relevant world paths.
3. Every action defines:
   - `requires_world` using explicit predicate ops (`eq`, `neq`, `gt`, `lt`, `gte`, `lte`)
   - `requires_bindings` using `{binding_id, acquired}` predicates
   - `effects_world`, `effects_bindings`
4. All actions use `requestor: assistant` — there is no user requestor in agent-only domains.
5. Include `bindings` entries for every produced/required binding id.
6. Every binding must declare a canonical `world_path` listed in `projection_fields`.
7. Every binding must flow into at least one downstream non-knowledge action via `tool_arg_bindings`.
8. Bindings are invalidated automatically when their `world_path` changes value.
9. If one conceptual tool has a finite enum/route/mode input, prefer one runtime tool plus an
   `action_schemas` entry that expands into concrete actions, instead of hand-authoring
   near-duplicate actions that differ only by literal tool args.

### Tool Functions (`tools.py`)

8. For every action in the contract, implement a matching standalone function:

```python
def my_tool(db: dict, some_param: str) -> str:
    """Tool description visible to the agent."""
    # Read/mutate db as needed
    db["some_path"] = new_value
    return f"Result: {db['some_path']}"
```

9. Every tool function MUST accept `db: dict` as its first parameter. This parameter is
   hidden from the agent's tool schema and injected at call time by `DepgraphToolEnv.update_tool_args`.
10. The `db` dict IS the world state. Tool functions read and mutate it directly — this is
    the concrete implementation of what the contract models abstractly in `effects_world`.
11. Tool functions return strings that the agent sees as tool call results. Return real data
    from the DB, not templates or placeholders.
12. Keep a `TOOL_FUNCTIONS` dict at module level mapping tool names to callables:

```python
TOOL_FUNCTIONS = {
    "my_tool": my_tool,
    "another_tool": another_tool,
    # ...
}
```

13. Do NOT include `db` in type hints that become agent-visible. The `args_to_skip=["db"]`
    mechanism in `DepgraphToolEnv.add_tool` handles hiding it from the schema.
14. If a tool has additional parameters beyond `db`, type them with `Literal[...]` or `Enum`
    for finite values so the agent schema exposes valid options.
15. Tool precondition guards should mirror contract `requires_world`:
    - unmet preconditions return explicit error/no-op message strings
    - no hidden state mutation on guard failure

### Consistency Rule

16. **Abstract model ↔ concrete implementation consistency**: For every `ActionContract`, the
    tool function's actual DB mutations must be consistent with `effects_world`. The contract
    is the BFS model; the tool function is the real implementation. They don't need to be
    identical (the tool can do richer things), but the contract must be a sound abstraction
    of what the tool does.

## Graph Topology Requirements

These are identical to the tau2 path — the graph contract is shared.

### Multiple bindings
At least 2 bindings with different `source_tool` values.

### Value-dependent branching
At least one pair of actions value-gated on the same world path.

### Early convergence
At least one non-terminal action requires preconditions from 2+ upstream paths.

Note: the tau2 path also requires user-action cross-dependencies. In agent-only domains,
replace this with: at least one pair of assistant actions where one's `effects_world` is
the other's `requires_world` precondition, creating ordering constraints the agent must
reason about.

## Acceptance Checks

1. No unclassified action.
2. No required/produced binding id without a declared binding source.
3. At least one transition chain of length >= 4 to reach goal.
4. No trivial shortcut action to final goal.
5. No unknown projection path/binding references across actions/bindings.
6. **Topology diversity checks**:
   - `bindings` list has >= 2 entries with different `source_tool` values.
   - At least one action has `requires_bindings` with 2+ entries.
   - At least one pair of actions uses value-gating on the same world path.
   - At least one non-terminal action has `requires_world` entries from 2+ upstream producers.
7. All actions have `requestor: assistant` (no user tools in verifiers path).
8. Every contract action has a matching function in `TOOL_FUNCTIONS`.
9. Every tool function accepts `db` as first parameter.
10. No contract action should rely on prompt-only assumptions to enforce gating; gates must
    be in tool function logic.

Tool linkage quick check:

```bash
uv run python - <<'PY'
import inspect
from tau2.generators.depgraph.loaders import load_graph_contract
from tau2.domains.<domain>.tools import TOOL_FUNCTIONS

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")

issues = []
tool_names_in_contract = set()
for action in contract.actions:
    tool_names_in_contract.add(action.tool_name)
    if action.tool_name not in TOOL_FUNCTIONS:
        issues.append(f"Action '{action.action_id}' references tool '{action.tool_name}' not in TOOL_FUNCTIONS")

for name, func in TOOL_FUNCTIONS.items():
    sig = inspect.signature(func)
    if "db" not in sig.parameters:
        issues.append(f"Tool '{name}' missing 'db' parameter")

for issue in issues:
    print(" -", issue)
raise SystemExit(1 if issues else 0)
PY
```
