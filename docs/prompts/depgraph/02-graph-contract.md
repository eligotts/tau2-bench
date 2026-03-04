# Prompt 02: Co-Author Contract + Runtime Semantics

## Instruction

Author contract and runtime semantics together so `action.tool_name` is immediately real.

Target files:

- `data/tau2/domains/<domain>/graph_contract.yaml`
- `src/tau2/domains/<domain>/tools.py`
- `src/tau2/domains/<domain>/user_tools.py`
- `src/tau2/domains/<domain>/environment.py`

Requirements:

1. Every callable action has classification: `causal`, `knowledge-only`, or `stutter-only`.
2. Define context slots (for example `active_customer`, `active_line`) and project only task-relevant world paths into `projection_fields`.
3. Every action defines:
   - `requires_world`, `requires_absent_world`
   - `requires_bindings`, `requires_absent_bindings`
   - `effects_world`, `effects_bindings`
   - `tool_arg_bindings` when bindings gate runtime tool calls
4. Model user-supplied knowledge as normal tool-backed actions:
   - `requestor=user`
   - `classification=knowledge-only`
   - `tool_name=<real user read tool>`
   - `effects_bindings` includes produced binding ids.
5. Include `bindings` entries for every produced/required binding id.
6. Keep bindings monotonic for now (no stale-binding invalidation model).
7. Include only causal user fields in world predicates/effects (`user.*` projected causal paths).
8. Exclude projection-only user fields from causal contracts.
9. Ensure each binding `extraction_path` is syntactically valid and schema-consistent where typed return schemas exist.
10. For every action in contract, implement matching runtime tool callable now:
   - `requestor=assistant` -> callable in `tools.py`
   - `requestor=user` -> callable in `user_tools.py`
11. Ensure binding-gated actions expose concrete tool parameters matching `tool_arg_bindings` keys.
12. Implement `sync_tools()` now to mirror contract-side causal bridges/effects.
13. If using strict checker-based STOP:
   - include a user `stutter-only` action for `check_resolution_status`
   - implement matching user tool callable now
   - keep checker tool non-causal (no world/binding effects).
14. Runtime guard behavior must mirror contract preconditions:
   - unmet preconditions return explicit error/no-op message
   - no hidden state mutation on guard failure (`stutter_on_fail` semantics).
15. Keep naming explicit:
   - `action_id` is stable semantic unit
   - `tool_name` is executable callable
   - avoid implicit aliasing; if aliasing is unavoidable, document it in contract comments.

Acceptance checks:

1. No unclassified action.
2. No required/produced binding id without a declared binding source.
3. At least one transition chain of length >= 4 to reach goal.
4. No trivial shortcut action to final goal.
5. No unknown projection path/binding references across actions/bindings.
6. Contract/runtime linkage check passes:

```bash
uv run python - <<'PY'
from tau2.generators.depgraph.loaders import load_graph_contract
from tau2.generators.depgraph.runtime_checks import check_contract_against_environment
from tau2.domains.<domain>.environment import get_environment

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")
issues = check_contract_against_environment(contract, get_environment, strict_full_coverage=False)
print("issues", len(issues))
for issue in issues:
    print(" -", issue)
raise SystemExit(1 if issues else 0)
PY
```

7. No contract action should rely on prompt-only assumptions to enforce gating; gates must be in tool/runtime logic.
