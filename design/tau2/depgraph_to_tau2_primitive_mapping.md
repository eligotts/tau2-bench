# Depgraph to Tau2 Primitive Mapping

This document is the concrete bridge from depgraph authoring artifacts to executable tau2 runtime artifacts.

Use this together with:

- `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md`
- `/Users/eligottlieb/Documents/tau2-bench/src/tau2/generators/depgraph/`

## 1. What Exists Today

Current depgraph artifacts:

- `domain_scope.md`
- `graph_contract.yaml`
- `stop_gate_map.yaml`
- `sampling_request.yaml`
- generated `task_specs.sampled.yaml`
- authored `task_specs.runtime.yaml`
- compiled `tasks.depgraph.json`

Current tau2 runtime primitives:

- task schema: `src/tau2/data_model/tasks.py`
- execution environment: `src/tau2/environment/environment.py`
- domain runtime files:
  - `src/tau2/domains/<domain>/data_model.py`
  - `src/tau2/domains/<domain>/user_data_model.py`
  - `src/tau2/domains/<domain>/tools.py`
  - `src/tau2/domains/<domain>/user_tools.py`
  - `src/tau2/domains/<domain>/environment.py`
  - `data/tau2/domains/<domain>/{db.*, user_db.*, policy.md, tasks.*}`

## 2. Canonical State Mapping

Depgraph node state:

- `S = (agent, user.causal, K)`

tau2 storage mapping:

- `agent.*` facts -> assistant DB fields in `data_model.py` + `db.*`
- `user.causal.*` facts -> user DB causal fields in `user_data_model.py` + `user_db.*`
- `K.*` facts -> not stored in DB by default; modeled in preflight solver and runtime prompt/ticket shaping

Important:

- Projection-only user fields remain in user DB if useful for UX, but must not appear in depgraph causal contracts.
- `sync_tools()` must encode causal bridges between assistant/user DBs so runtime behavior matches contract effects.

## 3. Action Mapping

Depgraph action contract -> tau2 runtime implementation:

- `requestor=assistant`, `tool_name=t` -> `t` must exist in `tools.py` as callable tool.
- `requestor=user`, `tool_name=t` -> `t` must exist in `user_tools.py` as callable tool.
- `classification=causal` -> runtime call can change assistant DB and/or user causal DB (directly or via `sync_tools()`).
- `classification=knowledge-only` -> solver-level `K` change produced by an explicit callable tool action (typically a user read/discovery tool).
- `classification=stutter-only` -> should return data/text only; no causal DB deltas.

Knowledge action mapping:

- No macro tool names; `tool_name` must always be a real runtime callable.
- Typical pattern:
  - user runs read/discovery tool (`requestor=user`, `classification=knowledge-only`)
  - action effect adds binding/fact to `K`
  - downstream assistant tools consume that binding via `tool_arg_bindings`.

## 4. Task Mapping (Intent -> Task JSON)

`TaskIntent` fields map to tau2 `Task` as follows:

- `task_id` -> `Task.id`
- `runtime.reason_for_call / known_info / unknown_info / task_instructions / persona`
  -> `Task.user_scenario`
- `runtime.ticket` -> `Task.ticket`
- `runtime.initialization_actions` -> `Task.initial_state.initialization_actions`
- `runtime.env_assertions` -> `Task.evaluation_criteria.env_assertions`
- `runtime.actions` -> `Task.evaluation_criteria.actions` (optional)
- `runtime.reward_basis` -> `Task.evaluation_criteria.reward_basis`

Implementation path:

- `src/tau2/generators/depgraph/compiler.py`

## 5. Start/Goal Fact Realization Rules

The critical conversion is:

- `start_true_facts` -> concrete `initialization_actions`
- `goal_facts` -> concrete `env_assertions`

This must be explicit per domain via helper functions in tools/user_tools:

- setter functions (`set_*`) for initialization
- assertion functions (`assert_*`) for goal checks

Rule:

- every start fact used by tasks should be realizable by at least one init function call
- every goal fact used by tasks should be checkable by at least one env assertion function

## 6. Sync Mapping Rules

`sync_tools()` is where cross-DB causality is implemented at runtime.

Expected pattern:

1. user tool mutates `user.causal.*` fields
2. `Environment.sync_tools()` projects causal consequences to assistant DB fields
3. assistant tools can then observe gated state and act accordingly

Example pattern (generic):

- user tool sets `user.causal.connector_reseated=true`
- `sync_tools()` sets `agent.connector_health=healthy` when prerequisites hold
- assistant tool `reprovision_*` requires healthy connector state

Constraint:

- `sync_tools()` logic must match depgraph contract effects for causal correctness.

## 7. Runtime Alignment Gates (Fail-Closed)

Before compile/release:

1. Contract alignment (`--domain <registered_domain>`):
   - action tools exist
   - fact source tools exist
   - extraction path is syntactically valid and schema-compatible when typed
2. Runtime alignment:
   - `initialization_actions` callables exist and arguments are valid
   - `env_assertions` callables exist, arguments are valid, and return bool when annotated
3. SAT checks:
   - `SAT_full`
   - `SAT_without_d` for each required action
   - contradiction/mutex/invariant checks
4. Stop-gate checks (when enabled):
   - `goal_world` entries map through `stop_gate_map.yaml`
   - runtime task contains exactly one `user.set_stop_gate(criteria=[...])`
   - instructions require `check_resolution_status` before STOP

Code paths:

- `src/tau2/generators/depgraph/runtime_checks.py`
- `src/tau2/generators/depgraph/stop_gate.py`
- `src/tau2/generators/depgraph/preflight.py`
- CLIs:
  - `run_preflight.py`
  - `run_stop_gate_inject.py`
  - `run_compile.py`

## 8. What Is Still Manual Today

Not yet fully programmatic:

- generating `runtime.initialization_actions` from `start_true_facts`
- generating `runtime.env_assertions` from `goal_facts`
- generating user-facing ticket/instructions from sampled structure
- generating actual domain runtime files (`tools.py`, `user_tools.py`, `environment.py`, DB schemas/data)

Current stance:

- keep these hand-authored during pilot iteration
- keep solver/compile fail-closed so non-runnable tasks never ship

## 9. Recommended Next Implementation Units

To reduce manual work while staying safe, add these in order:

1. `fact_binding.yaml` per domain
   - maps each fact to:
     - init setter call spec
     - assertion call spec
2. deterministic runtime autofill utility
   - input: sampled task intents + fact bindings
   - output: candidate runtime blocks (human-editable)
3. runtime dry-run verifier
   - instantiate environment
   - apply init actions
   - replay required action witness (if provided)
   - verify env assertions pass
4. domain scaffold template for depgraph-native domains
   - minimal `data_model.py`, `user_data_model.py`, `tools.py`, `user_tools.py`, `environment.py`
   - includes explicit `set_*`, `assert_*`, and sync bridge stubs

## 10. Definition of Done for “Ported to Tau2”

A depgraph domain is considered fully ported when all are true:

1. Domain runtime exists under `src/tau2/domains/<domain>/` with working tools and sync.
2. Domain is registered in `src/tau2/registry.py`.
3. `run_preflight --domain <domain>` passes (contract + runtime alignment + SAT).
4. `run_compile --domain <domain>` emits `tasks.depgraph.json` with zero failures.
5. Running task execution in tau2 for sampled tasks confirms init/actions/assertion behavior matches solver semantics.
