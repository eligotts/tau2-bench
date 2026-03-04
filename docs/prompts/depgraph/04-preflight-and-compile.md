# Prompt 04: Runtime Enrichment + Preflight + Compile

## Instruction

Start from sampled structural intents (`task_specs.sampled.yaml`), then enrich runtime payloads and compile.

Inputs to review before authoring:

- `data/tau2/domains/<domain>/task_specs.sampled.yaml`
- `data/tau2/domains/<domain>/graph_contract.yaml`
- `data/tau2/domains/<domain>/stop_gate_map.yaml`
- `data/tau2/domains/<domain>/domain_scope.md` (especially `Known risks`)
- `src/tau2/domains/<domain>/{data_model.py,user_data_model.py,tools.py,user_tools.py,environment.py}`

1. Create `data/tau2/domains/<domain>/task_specs.runtime.yaml` by adding `runtime` blocks per task.
2. Each `runtime` block must include:
   - user prompt fields (`domain`, `reason_for_call`, `task_instructions`, optional `known_info`, `unknown_info`, `persona`)
   - `initialization_actions` (break/init)
   - `env_assertions` (goal checks)
   - `reward_basis`
3. Inject strict stop-gate criteria from sampled goals by adding:
   - one `user.set_stop_gate(criteria=[...])` initialization action per task
   - strict checker-based stop text in `task_instructions`
4. Keep structural provenance intact:
   - do not modify sampled `required_actions`, `required_precedence`, `start_world`, `goal_world`, `goal_bindings`
   - only author runtime semantic fields and concrete context binding.

User-sim completion rule (required in `task_instructions`):

1. Include an explicit completion criterion sentence:
   - `You will consider the issue resolved when <concrete observable condition>.`
2. Include explicit stop behavior tied to that condition:
   - `When that condition is met, reply with ###STOP###.`
3. Require tool-grounded reporting:
   - user should ground status answers in tool results and avoid guessing.
4. When stop-gates are used, require:
   - `Only emit ###STOP### when check_resolution_status returns resolved=true.`
   - `If resolved=false, report unmet items and ask for the next step.`

Recommended canonical stop block (copy/adapt):

- `Before deciding the issue is resolved, call check_resolution_status.`
- `Only emit ###STOP### when check_resolution_status returns resolved=true.`
- `If resolved=false, report unmet items and ask for the next step.`

How to derive the completion criterion (required):

1. Start from sampled `goal_world` (and `goal_bindings` if relevant).
2. Choose one or more user-observable success conditions implied by those goals.
3. Write the criterion sentence using those observable conditions, not vague wording.
4. Add explicit STOP instruction:
   - `When that condition is met, reply with ###STOP###.`

How to derive and inject stop-gates (required):

1. Map each `goal_world` equality to a user-observable checker criterion using `stop_gate_map.yaml`.
2. Build `criteria` entries with:
   - `check_field`, `op`, `expected`, optional `unmet_reason`, optional `observed_from`.
3. Inject stop-gates:

```bash
uv run python -m tau2.generators.depgraph.run_stop_gate_inject \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml
```

Rule:

- if stop-gate injection fails, fix `stop_gate_map.yaml` (or sampled goals) instead of hand-editing criteria directly in runtime YAML.

Target code path:

- `/Users/eligottlieb/Documents/tau2-bench/src/tau2/generators/depgraph/`

Required checks per task:

1. `SAT_full` must be true.
2. For each required action `d`: `SAT_without_d` must be false.
3. Contradiction checks must pass (no conflicting start/goal world assignments).
4. Runtime instruction checks must pass:
   - non-empty `task_instructions`
   - explicit completion criterion (`... resolved when ...`)
   - explicit `###STOP###` instruction
   - checker-based stop text when `set_stop_gate` is present

Consistency audit before compile (required):

1. `start_world` -> `initialization_actions` mapping is complete and exact.
2. `goal_world`/`goal_bindings` -> `env_assertions` coverage is complete and exact.
3. `required_actions` remain unchanged from sampled specs.
4. Action/tool translation is explicit when names differ:
   - use `graph_contract.yaml` mapping (`action_id -> requestor/tool_name/tool_arg_bindings`).
5. Ticket and instructions use concrete DB entities (context-slot binding resolved to IDs).
6. Review `domain_scope.md` `Known risks` and include mitigations in runtime text/assertions where relevant.
7. No narrative shortcuts that imply unavailable tools or hidden state.
8. Exactly one `user.set_stop_gate` initialization action exists per runtime task.
9. Task instructions explicitly forbid early STOP on partial progress.

Validation command sequence (required):

```bash
uv run python -m tau2.generators.depgraph.run_preflight \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --strict-tool-coverage
```

Then:

Compile command:

```bash
uv run python -m tau2.generators.depgraph.run_compile \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --out data/tau2/domains/<domain>/tasks.depgraph.json
```

Compilation output must satisfy:

- `Task.initial_state.initialization_actions` from start/break world state design
- `Task.evaluation_criteria.env_assertions` from goal world/binding intent design
- Optional action assertions only when explicitly required
- Runtime alignment checks must pass against actual tau2 environment:
  - contract action/binding-source tools exist
  - runtime `initialization_actions` and `env_assertions` callables exist and arguments are valid
  - `bindings[].extraction_path` passes sanity/schema checks where available
  - binding-gated actions map required bindings to concrete tool params (`tool_arg_bindings`)

Report format:

- pass/fail per task
- failing check type
- minimal fix suggestion
- risk-closure notes: for each `Known risk`, state whether mitigated or still open
- provenance note: confirm sampled structural fields remained unchanged
