# Prompt 02: Co-Author Contract + Runtime Semantics

## Instruction

Author contract and runtime semantics together so `action.tool_name` is immediately real.

Target files:

- `data/tau2/domains/<domain>/graph_contract.yaml`
- `data/tau2/domains/<domain>/personas.yaml`
- `data/tau2/domains/<domain>/runtime_defaults.yaml`
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
6. Bindings are monotonic (once acquired, never revoked).
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

## Graph Topology Requirements

These requirements ensure the graph produces structurally diverse tasks rather than
shorter/longer versions of one chain. Review against these BEFORE finalizing the contract.

### Multiple bindings

The contract must define at least 2 bindings with different `source_tool` values. Each
binding represents a distinct piece of information the agent must discover mid-conversation.

- Different assistant actions should require different bindings — not every action gated
  by the same single binding.
- At least one action should require 2+ bindings simultaneously (a multi-binding gate).

Why: A single binding produces tasks where the agent always gathers the same information
and passes it uniformly. Multiple bindings force the agent to reason about what information
is needed for which tool.

### Value-dependent branching

At least one pair of actions should be **value-gated**: enabled by different values of the
same world path. This creates genuine branching where the resolution path depends on what
the agent discovers.

- Use `requires_world` with specific values (e.g., `{path: fault_class, value: "billing"}`)
  on one action and a different value on another action that produces the same downstream
  effect.
- The branching discriminator should itself be a binding or the result of a discovery
  action, so the agent must diagnose before choosing a path.

Why: Without value-gating, the graph has one topology and tasks vary only in how much of
it is pre-solved. With value-gating, different starting states activate structurally
different subgraphs.

### User action ordering

User-side causal actions must have at least one cross-dependency between them (one user
action's effect is another user action's precondition). A set of N independent user actions
is a flat basket — the agent doesn't need to reason about ordering.

Why: If all user actions are independent, the agent can instruct "do all of these" in any
order. Cross-dependencies force the agent to sequence user instructions correctly.

### Early convergence

At least one action in the middle of the graph (not the final gate) should require
preconditions from 2+ different upstream paths. This creates a mid-graph convergence point
where the agent must coordinate across lanes before continuing.

Why: If the only multi-prerequisite action is the final gate, all reasoning about
coordination is deferred to the end. Early convergence forces ongoing coordination.

## Companion Artifacts

16. Author concrete persona pool in `personas.yaml` for runtime-stage assignment:
   - include 2-5 personas with stable `persona_id`
   - each persona has concise `display_name` + `profile_text`
   - optional style tags (for example `low_tech`, `high_urgency`, `detail_oriented`)
   - keep personas domain-relevant but avoid leaking solution steps or backend internals
17. Author `runtime_defaults.yaml` for deterministic scaffold generation:
   - include `domain`
   - include one shared `task_instructions` template (do not vary per task)
   - include default `reward_basis`
   - include `initialization_actions_prefix` for static per-task setup that every task needs
     (for example `set_user_context(...)` for active-slot binding).

Acceptance checks:

1. No unclassified action.
2. No required/produced binding id without a declared binding source.
3. At least one transition chain of length >= 4 to reach goal.
4. No trivial shortcut action to final goal.
5. No unknown projection path/binding references across actions/bindings.
6. **Topology diversity checks** (from Graph Topology Requirements above):
   - `bindings` list has >= 2 entries with different `source_tool` values.
   - At least one action has `requires_bindings` with 2+ entries.
   - At least one pair of actions uses value-gating on the same world path.
   - User causal actions have at least one cross-dependency (one user action's
     `effects_world` path appears in another user action's `requires_world`).
   - At least one non-terminal action has `requires_world` entries from 2+ upstream
     producers (early convergence).
7. Contract/runtime linkage check passes:

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

8. No contract action should rely on prompt-only assumptions to enforce gating; gates must be in tool/runtime logic.
9. `personas.yaml` parses and has unique `persona_id` values.
10. `runtime_defaults.yaml` parses and has non-empty `task_instructions`.

Persona file quick check:

```bash
uv run python - <<'PY'
import yaml
from pathlib import Path
p = Path("data/tau2/domains/<domain>/personas.yaml")
doc = yaml.safe_load(p.read_text())
ids = [x["persona_id"] for x in doc.get("personas", [])]
assert len(ids) >= 2, "need at least 2 personas"
assert len(ids) == len(set(ids)), "duplicate persona_id values"
print("personas", len(ids), "ok")
PY
```

Runtime defaults quick check:

```bash
uv run python - <<'PY'
import yaml
from pathlib import Path
p = Path("data/tau2/domains/<domain>/runtime_defaults.yaml")
doc = yaml.safe_load(p.read_text())
assert (doc.get("domain") or "").strip(), "runtime_defaults.domain required"
assert (doc.get("task_instructions") or "").strip(), "task_instructions required"
assert doc.get("reward_basis"), "reward_basis required"
print("runtime_defaults ok")
PY
```
