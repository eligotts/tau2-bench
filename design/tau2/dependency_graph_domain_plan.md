# Tau2 Dependency-Graph Domain Plan

This document captures the current target architecture for building tau2-compatible domains with graph-based solvability guarantees.

## 1. Goals

1. Stay fully compatible with tau2 runtime and task schema.
2. Keep task construction in a graph world so solvability can be checked before task release.
3. Make dependencies first-class so tasks are long-horizon chains, not baskets of independent fixes.
4. Support both agent-heavy and user-heavy interaction patterns (including telecom-style user tool execution).

## 2. Core State Model

Each search node is a causal state tuple:

`S = (agent, user.causal, K)`

- `agent`: assistant/world state (agent DB and assistant-observed environment truth).
- `user.causal`: causal user state only (user-side flags that affect transitions, sync, or gates).
- `K`: agent knowledge state (facts known by the agent).

### 2.1 What is excluded from node state

- Pure user projection/view fields that do not affect transitions.
- User read-only actions with no effect on `agent`, `user.causal`, or `K`.

Those can be captured in a separate trace layer but are not part of causal solvability.

### 2.2 Causal user fields vs projection-only user fields

The `user.causal` namespace must contain only user fields that can change what transitions are enabled or what effects occur.

Examples:

- Causal user field: `user.causal.phone_restarted`
  - Used by preconditions (for example, assistant reprovision action requires restart).
  - Used by sync bridges to update assistant state.
- Projection-only user field: `user_view.connection_status_text`
  - Display label for user UX.
  - Not used in `requires`, `produces`, `invalidates`, invariants, or sync guards.

Rule:

- If a field appears in transition contracts, invariants, or sync bridge logic, it is causal.
- Otherwise it should be treated as projection-only and excluded from node state.

## 3. Transition Contract (Dependencies as Data)

Each action is represented by a contract, not just executable code:

- `action_id`
- `requestor` (`assistant` or `user`)
- `tool_name` (real runtime callable name)
- `requires: set[Fact]`
- `requires_absent: set[Fact]` (negative preconditions)
- `produces: set[Fact]`
- `invalidates: set[Fact]` (optional)
- `apply(S, args) -> S'`
- `stutter_on_fail: bool` (true in most cases)

Every callable tool/action must also have a contract classification:

- `causal`: may change `agent` and/or `user.causal` (including sync-mediated effects).
- `knowledge-only`: changes `K` but not `agent`/`user.causal`.
- `stutter-only`: never changes `agent`/`user.causal`/`K` for solvability.

This classification applies to both assistant and user tools.

Practical policy:

- Assistant tools should normally be `causal` or `knowledge-only`.
- Assistant `stutter-only` tools are exceptional and must be allowlisted.

A fan-out edge is eligible only when:

1. `requires(action) \subseteq Facts(S)`
2. arguments are groundable and valid
3. invariants/guards hold

The edge is included in the causal graph only if state changes (`delta(agent,user.causal,K) != empty`).

Validation rules:

- No callable tool may be unclassified.
- Any tool marked `stutter-only` must be verified to never change `agent`/`user.causal`/`K`.
- Any tool marked `knowledge-only` must map to explicit `K` fact effects.

## 4. Gate Semantics

Gates are encoded by transition preconditions (tool guards). They do not require a separate artifact as long as guards are explicit in contracts.

Examples:

- Knowledge gate: `reprovision_esim` requires `K.iccid_known`.
- User-action gate: `reprovision_esim` requires `user.causal.phone_restarted`.
- State gate: `run_data_test` requires `agent.profile_state == reprovisioned`.

This makes ordering causal: later actions are enabled only when upstream actions produce required facts.

## 5. Knowledge Acquisition from User

Model user-provided knowledge as normal, tool-backed transitions:

- `requestor = user`
- `classification = knowledge-only`
- `tool_name = <real user read/discovery tool>`

Preconditions:

- binding not already in `K`
- source tool observability is satisfiable in current `(agent, user.causal)`

Effects:

- binding is added to `K`

Conversation micro-steps (assistant asks, user responds) are still outside the causal graph; the causal edge is the tool-backed knowledge transition.

### 5.1 FactSource specifications

To avoid magical knowledge edges, each user-supplied fact needs one or more explicit `FactSource` declarations:

- `fact_id` (for example `K.iccid_known`)
- `source_tool` (for example `get_sim_info`)
- `extraction_path` (for example `result.iccid`)
- `observability_predicate(agent,user.causal)` (when user can actually obtain the fact)

The corresponding `knowledge-only` action is enabled only if at least one `FactSource` for its produced binding is currently satisfiable.

### 5.2 Example

Fact: `K.iccid_known`

- source tool: `get_sim_info`
- extraction path: `result.iccid`
- observability predicate: `user.causal.phone_powered_on == true` and `agent.line_exists == true`

Consequences:

- If phone is off, the `knowledge-only` action using `get_sim_info` is disabled.
- After phone is on (or other enabling steps), the same knowledge edge becomes enabled.

## 6. Two Graph Layers

1. **Causal solvability graph**
   - Nodes: `S=(agent,user.causal,K)`
   - Edges: enabled, state-changing transitions only
   - Purpose: SAT/UNSAT solvability proof

2. **Interaction trace graph (optional)**
   - Includes no-op and conversational micro-steps
   - Purpose: gold-path narration, UX realism, training trace richness

Only the causal graph determines solvability.

## 7. Task Representation

A task is authored as:

- Start state constructor (break/init operations)
- Goal facts / goal predicate
- Optional required dependency steps (for necessity checks)
- Optional trace precedence metadata (descriptive only)

tau2 output remains the existing `Task` schema.

## 8. Solvability and Dependency Checks

Run these checks before emitting each task:

1. `SAT_full`
   - Search for any path from `S0` to goal in causal graph.
2. `SAT_without_d` for each intended required dependency step `d`
   - Disable `d`; require UNSAT.
3. chain-depth checks (recommended)
   - Require minimum path length / dependency depth to avoid basket tasks.

If any check fails, task is rejected or revised.

## 8.1 User STOP Gating (telecom-style, stricter)

Keep STOP instruction-led, but make it fail-closed with one checker tool.

- Add a domain `stop_gate_map.yaml` mapping each `goal_world` equality to a user-observable checker field.
- Inject one runtime init action per task:
  - `user.set_stop_gate(criteria=[...])`
- Implement a user read tool:
  - `check_resolution_status() -> {resolved, unmet, observed}`
- Task instructions must require:
  - call `check_resolution_status` before stopping,
  - emit `###STOP###` only when `resolved=true`,
  - report unmet items and continue when `resolved=false`.

This keeps telecom's natural-language STOP control while grounding it in a deterministic, multi-field checker.

## 9. Contradiction Checks

Contradictions are checked in three layers.

### 9.1 Static fact/invariant checks

- Goal mutex checks (cannot require mutually exclusive facts).
- Start-state invariant checks.
- Domain invariants (for example: `data_active => sim_state == ready`).

### 9.2 Static dependency graph checks

- Every goal fact has a producer.
- No impossible dependency cycles.
- Detect destructive interference where required facts are invalidated with no recovery producer.

### 9.3 Dynamic SAT checks

- If `SAT_full` fails, the task is unsatisfiable under current transition semantics.
- Use ablations (`SAT_without_d`) to validate necessity of intended dependencies.

## 10. Tau2 Engine Integration

This design maps directly to tau2 runtime pieces:

- `initialization_actions` <- break/init operations used to construct `S0`
- `env_assertions` <- goal predicate compiled into assertion calls
- `evaluation_criteria.actions` <- optional behavioral checks (use sparingly)
- `sync_tools()` <- must be mirrored in transition effects (especially `user.causal -> agent` bridges)

Detailed primitive-by-primitive mapping and implementation checklist:

- `/Users/eligottlieb/Documents/tau2-bench/design/tau2/depgraph_to_tau2_primitive_mapping.md`

Notes:

- Action assertions should not be the primary mechanism for order enforcement.
- Order should arise causally from transition preconditions and state changes.
- Solver state is fact-only (`agent`, `user.causal`, `K`); prior action history is not part of node identity.
- Runtime alignment should verify callable existence/signatures for both contract tools and runtime `initialization_actions`/`env_assertions`.
- `FactSource.extraction_path` should be validated syntactically and against typed return schemas when available.

`sync_tools()` mapping detail:

1. User tool executes and updates `user.causal`.
2. `sync_tools()` projects causal effects into `agent` (and may update projection fields).
3. `K` does not update automatically from sync; `K` only changes via explicit knowledge acquisition edges.

This keeps world causality (`agent/user.causal`) separate from agent epistemic state (`K`).

Initial knowledge (`K0`) mapping detail:

- `K0` must be compiled from structured task inputs (ticket fields, known_info templates), not inferred ad hoc from prose.
- Facts intended for discovery later must be excluded from `K0`.
- Add leak checks to ensure hidden facts are not accidentally included in ticket, policy, or initial user-known fields.

## 11. How User-Heavy Domains (Telecom Pattern) Fit

Telecom-like tasks often have user tools as the main operational actions.

Modeling rule:

- User tool with physical/causal effect: include as normal transition (`delta user.causal` and often `delta agent` after sync).
- User read-only discovery with no causal effect: stutter (exclude from causal graph).
- Agent knowledge gain from user report: explicit user `knowledge-only` tool action (`delta K`).

This preserves solvability logic while avoiding graph explosion from non-causal interactions.

## 12. Authoring Pipeline (LLM One File at a Time)

The authoring route remains progressive with strong gates.

Prompt-first execution rule:

- The pipeline is driven by prompt files that instruct coding agents what to author at each step.
- Prompt pack location: `/Users/eligottlieb/Documents/tau2-bench/docs/prompts/depgraph/`
- Deterministic transformation code lives under: `/Users/eligottlieb/Documents/tau2-bench/src/tau2/generators/depgraph/`

1. `domain_scope.md` (agent/user DB entities + projection + context slots)
2. Co-author in one step:
   - `graph_contract.yaml`
   - `tools.py`
   - `user_tools.py`
   - `environment.py` (including `sync_tools`)
3. `data_model.py`, `user_data_model.py`, `db.json`, `user_db.json` (or refine if already authored in step 2)
4. `sampling_request.yaml`
5. generated `task_specs.sampled.yaml`
6. authored `task_specs.runtime.yaml`
7. compiled `tasks.depgraph.json` after preflight/alignment gates

At each step:

- edit one minimal file
- run targeted verification
- fix until green
- then advance

Recommended concrete artifact flow:

1. `graph_contract.yaml` (projection paths, bindings, action contracts)
2. `sampling_request.yaml` (seed starts + depth bounds)
3. generated `task_specs.sampled.yaml` (fan-out sampled structural intents)
4. authored `task_specs.runtime.yaml` (add tau2 runtime payloads)
5. compiled `tasks.depgraph.json` (only preflight+runtime passing tasks)

## 13. Required Properties of the Final System

1. **Tau2 compatibility**: emits valid tau2 tasks and runs in existing engine.
2. **Correctness by construction**: every emitted task has SAT witness.
3. **Dependency realism**: long-horizon behavior is required by stateful prerequisites.
4. **No hidden shortcuts**: ablation checks enforce necessity of key steps.
5. **Progressive disclosure support**: knowledge and gate unlocking modeled explicitly.
6. **User/agent parity in transitions**: both can produce required facts; only causal state is modeled.

## 14. Anti-Patterns to Avoid

1. Basket tasks where all fixes are independent and parallelizable.
2. Enforcing sequence only via action-order assertions.
3. Modeling full user projection state in nodes (state explosion, little value).
4. Treating no-op discovery calls as causal edges.
5. Allowing shortcut tools that set deep goal state directly.

## 15. Minimal Practical Example (Shape)

Start:

- `agent.data_status = stuck`
- `user.causal.phone_restarted = false`
- `K.iccid_known = false`

Goal:

- `agent.data_status = active`

Transitions:

1. `user_get_iccid` (knowledge-only, `tool_name=get_sim_info`) -> produces `K.iccid_known`
2. `user_restart_phone` -> produces `user.causal.phone_restarted`
3. `agent_reprovision_esim` requires 1+2 -> produces `agent.profile_ready`
4. `user_run_data_test` requires 3 -> produces `agent.data_status = active`

Checks:

- `SAT_full` = true
- without step 1 = UNSAT
- without step 2 = UNSAT
- force step 4 before step 3 = UNSAT

This certifies a real dependency chain, not a bag of independent actions.
