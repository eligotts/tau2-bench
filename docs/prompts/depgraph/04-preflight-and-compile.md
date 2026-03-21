# Prompt 04: Runtime Scaffold Authoring + Preflight + Compile

## Instruction

Do not hand-build `task_specs.runtime.yaml` from scratch.
Use scaffold-first runtime authoring with a strict edit surface.

Exact execution contract:

1. run each command in order,
2. check pass status/output,
3. if any command fails: fix the reported issue before continuing,
4. never skip validation steps.

Inputs to review before authoring:

- `data/tau2/domains/<domain>/task_specs.sampled.yaml`
- `data/tau2/domains/<domain>/task_context_bindings.yaml`
- `data/tau2/domains/<domain>/graph_contract.yaml`
- `data/tau2/domains/<domain>/sampling_request.yaml` (especially `terminal_profiles`)
- `data/tau2/domains/<domain>/personas.yaml`
- `data/tau2/domains/<domain>/runtime_defaults.yaml`
- `data/tau2/domains/<domain>/stop_gate_map.yaml`
- `data/tau2/domains/<domain>/domain_scope.md` (especially `Known risks`)
- `src/tau2/domains/<domain>/{data_model.py,user_data_model.py,tools.py,user_tools.py,environment.py}`

## Required Step Order

Gate policy (hard): do not proceed to step `N+1` until step `N` exits successfully.

1. Generate deterministic runtime scaffold + narrative briefs:

```bash
uv run python -m tau2.generators.depgraph.run_context_bindings \
  --domain <domain> \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs-sampled data/tau2/domains/<domain>/task_specs.sampled.yaml \
  --db-json data/tau2/domains/<domain>/db.json \
  --out-context-bindings data/tau2/domains/<domain>/task_context_bindings.yaml

uv run python -m tau2.generators.depgraph.run_runtime_scaffold \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs-sampled data/tau2/domains/<domain>/task_specs.sampled.yaml \
  --personas data/tau2/domains/<domain>/personas.yaml \
  --runtime-defaults data/tau2/domains/<domain>/runtime_defaults.yaml \
  --context-bindings data/tau2/domains/<domain>/task_context_bindings.yaml \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --out-runtime-scaffold data/tau2/domains/<domain>/task_specs.runtime.scaffold.yaml \
  --out-narrative-briefs data/tau2/domains/<domain>/task_narrative_briefs.yaml
```

2. Initialize runtime file from scaffold:

```bash
uv run python -m tau2.generators.depgraph.run_runtime_init \
  --scaffold data/tau2/domains/<domain>/task_specs.runtime.scaffold.yaml \
  --out-runtime data/tau2/domains/<domain>/task_specs.runtime.yaml
```

3. Author runtime narratives:
   - edit only these per-task fields in `task_specs.runtime.yaml`:
     - `runtime.reason_for_call`
     - `runtime.known_info`
     - `runtime.ticket`

4. Hard-gate authored surface:

```bash
uv run python -m tau2.generators.depgraph.run_runtime_surface_check \
  --scaffold data/tau2/domains/<domain>/task_specs.runtime.scaffold.yaml \
  --runtime data/tau2/domains/<domain>/task_specs.runtime.yaml
```

Note: `run_runtime_surface_check` now tolerates the expected injected `user.set_stop_gate`
in `initialization_actions`, so it can be run on either the pre-stop-gate authored file or
the final post-injection runtime file. Other runtime mutations still fail.

5. Validate authored narrative quality against briefs:

```bash
uv run python -m tau2.generators.depgraph.run_runtime_narrative_check \
  --runtime data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --narrative-briefs data/tau2/domains/<domain>/task_narrative_briefs.yaml
```

6. Inject strict stop-gates:

```bash
uv run python -m tau2.generators.depgraph.run_stop_gate_inject \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml
```

7. Run preflight:

```bash
uv run python -m tau2.generators.depgraph.run_preflight \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --sampling-request data/tau2/domains/<domain>/sampling_request.yaml \
  --policy data/tau2/domains/<domain>/policy.md \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --strict-tool-coverage
```

Default preflight proves that tasks are solvable and structurally aligned with terminal
profiles, runtime/tool coverage, and stop-gates. If you also want to prove
that every `required_action` is individually indispensable, add:

```bash
  --strict-required-action-necessity
```

8. Compile tasks:

```bash
uv run python -m tau2.generators.depgraph.run_compile \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --sampling-request data/tau2/domains/<domain>/sampling_request.yaml \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --out data/tau2/domains/<domain>/tasks.depgraph.json
```

`run_compile` has the same optional strict necessity mode:

```bash
  --strict-required-action-necessity
```

Canonical command sequence (copy/paste in order):

```bash
uv run python -m tau2.generators.depgraph.run_context_bindings \
  --domain <domain> \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs-sampled data/tau2/domains/<domain>/task_specs.sampled.yaml \
  --db-json data/tau2/domains/<domain>/db.json \
  --out-context-bindings data/tau2/domains/<domain>/task_context_bindings.yaml

uv run python -m tau2.generators.depgraph.run_runtime_scaffold \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs-sampled data/tau2/domains/<domain>/task_specs.sampled.yaml \
  --personas data/tau2/domains/<domain>/personas.yaml \
  --runtime-defaults data/tau2/domains/<domain>/runtime_defaults.yaml \
  --context-bindings data/tau2/domains/<domain>/task_context_bindings.yaml \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --out-runtime-scaffold data/tau2/domains/<domain>/task_specs.runtime.scaffold.yaml \
  --out-narrative-briefs data/tau2/domains/<domain>/task_narrative_briefs.yaml

uv run python -m tau2.generators.depgraph.run_runtime_init \
  --scaffold data/tau2/domains/<domain>/task_specs.runtime.scaffold.yaml \
  --out-runtime data/tau2/domains/<domain>/task_specs.runtime.yaml

# author only reason_for_call / known_info / ticket

uv run python -m tau2.generators.depgraph.run_runtime_surface_check \
  --scaffold data/tau2/domains/<domain>/task_specs.runtime.scaffold.yaml \
  --runtime data/tau2/domains/<domain>/task_specs.runtime.yaml

uv run python -m tau2.generators.depgraph.run_runtime_narrative_check \
  --runtime data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --narrative-briefs data/tau2/domains/<domain>/task_narrative_briefs.yaml

uv run python -m tau2.generators.depgraph.run_stop_gate_inject \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml

uv run python -m tau2.generators.depgraph.run_preflight \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --sampling-request data/tau2/domains/<domain>/sampling_request.yaml \
  --policy data/tau2/domains/<domain>/policy.md \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --strict-tool-coverage

uv run python -m tau2.generators.depgraph.run_compile \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --sampling-request data/tau2/domains/<domain>/sampling_request.yaml \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --strict-tool-coverage \
  --out data/tau2/domains/<domain>/tasks.depgraph.json
```

## Deterministic vs Authored Fields

Deterministic (from scaffold; do not edit):

- `runtime.domain`
- `runtime.task_instructions` (shared template)
- `runtime.persona` (entity name from context bindings + personality from persona pool)
- `runtime.unknown_info` (null)
- `runtime.initialization_actions` (from start state + context bindings + runtime defaults prefix)
- `runtime.env_assertions` (from `goal_world` -- the terminal profile's requires_world predicates)
- `runtime.actions` (from required action chain)
- `runtime.reward_basis`

Per-task authored (only 3 fields):

- `runtime.reason_for_call`
- `runtime.known_info`
- `runtime.ticket`

Hard rules:

1. Never edit sampled structural fields:
   - `start_world`, `start_bindings`, `goal_world`, `terminal_profile_id`, `required_actions`.
2. Never edit deterministic runtime fields listed above.
3. Remove all `__AUTHOR_ME__` placeholders.
4. Run both runtime author checks on the authored runtime file:
   - `run_runtime_surface_check`
   - `run_runtime_narrative_check`

## Entity Slot IDs vs Bindings

Understanding this distinction is critical for authoring natural text.

**Entity slot IDs** (`active_account`, `active_station`, `active_session`) are **plumbing**.
They select which entity instance a task operates on. The pipeline assigns concrete IDs
(e.g. `A1001`, `ST1001`) via `run_context_bindings`, then wires them into `initialization_actions`
via `set_user_context(...)`. At runtime, every tool resolves the active entity from context
(e.g. `_active_account_id()`). No tool takes entity IDs as explicit parameters.

Entity slot IDs must NEVER appear in authored text (`reason_for_call`, `known_info`, `ticket`).
They are invisible to users and agents. Only the customer **name** from `entity_context` is
user-facing.

Entity type names (e.g. "station", "account") must also not appear in tool docstrings in a way
that implies the agent needs to identify them. Tool docstrings become the `description` field
in the OpenAI schema sent to the LLM -- if a docstring says "for the active station", the agent
will ask the user for a station ID. Use neutral phrasing like "for the current charging session"
instead.

**Bindings** (`fault_code`, etc.) are **discovered information**. They represent knowledge facts
the user can observe or provide (e.g. an error code on a screen). Bindings are defined in
`graph_contract.yaml` with a `source_tool`, `extraction_path`, and `world_path`.

Bindings split into two authoring categories:

- **`start_bindings`**: The user knows the value at task start. The concrete value MUST appear
  in `known_info` and `ticket`.
- **Undisclosed bindings**: Any binding whose canonical value exists in `start_world` but is
  not listed in `start_bindings`. These values must be acquired during task execution via tool
  calls and must NEVER appear in authored text. The narrative brief emits
  `undisclosed_binding_values` for these values; the narrative check hard-fails if any appear
  in authored text.

Important nuance: an undisclosed binding may need to be reacquired multiple times if its
`world_path` changes during recovery. The contract only says the task depends on acquiring that
binding type before some downstream consuming action; it does not encode how many rereads the
live run may need. Do not pre-disclose later-stage values just because the same binding source
is used again.

Why this matters: if an undisclosed binding value (e.g. fault code `BH-101`) is pre-disclosed
in `reason_for_call` or `known_info`, the agent already has the information and never triggers
the discovery tool call, causing the downstream action dependency to collapse.

Also note: `required_actions` is a deduped structural coverage list. It may contain
`check_station_screen` once even when a valid live run must reacquire the screen code three
times. Treat `required_actions` as coverage context, not as the full literal runtime trace.

Summary:

| | Entity slot IDs | start_bindings | undisclosed bindings |
|---|---|---|---|
| Example | `A1001`, `ST1001` | plan name, promo code | `BH-101`, `CERT-409` |
| Purpose | Select active entity | User-known facts | Mid-task discovery before a consuming action |
| In authored text? | **Never** | **Required** in known_info + ticket | **Never** |
| Tools need them? | No (context-scoped) | Yes (`tool_arg_bindings`) | Yes (`tool_arg_bindings`) |

## How to Use `task_narrative_briefs.yaml`

### Family-based authoring

Tasks cluster into families by `(terminal_profile, seed_schema)`. Tasks in the same family
share the same user experience — only the customer name and minor state details vary.
Author ONE template per family, then apply it to all tasks in that family with name
substitution. Do not author each task individually.

To identify families: group briefs by `terminal_profile`. Within each profile group,
tasks from the same seed schema share the same `broken_state` pattern.

### Per-task brief fields

Each brief contains:

- `entity_context.name` — customer name to use (ONLY the name, never slot IDs)
- `start_bindings` — pre-known binding values that MUST appear in `known_info` + `ticket`
- `undisclosed_binding_values` — values that must NEVER appear in authored text
- `notable_start_state` — what distinguishes this task's starting world (author context, not for user text)
- `resolved_when` — what "resolved" means (drives the ticket's completion sentence)
- `required_actions` — internal context only, do not leak

Writing constraints and voice:

1. `reason_for_call` -- **first person, conversational**.
   - Describe what the user is experiencing and what they want fixed.
   - Include frustration or urgency when natural.
   - Never mention internal paths, tool names, or solution steps.
   - Good: `"My charging session won't start. The screen is showing some kind of error and I need to charge my car before a long drive."`
   - Bad: `"Charging fault BH-101 is active. Backend link is down. Need fraud lock removed and billing hold cleared."` (leaks undisclosed binding value + internal state)

2. `known_info` -- **second person, factual context**.
   - Start with `"You are [name]"` using only the name from `entity_context`.
   - Add situational context the user would naturally know (where they are, what they observe, what they were doing).
   - Include concrete start-binding values (error codes, plan names) when present -- these are user-observable facts.
   - Do NOT include entity slot IDs (account, station, session). Do NOT list internal state.
   - Good: `"You are Jordan Lee. You are at a charging station and your session won't start. The station screen is showing an error."`
   - Bad: `"Name: Jordan Lee. Account: A1001. Station: ST1001. Session: S1001. Fault code: BH-101."` (leaks entity IDs + undisclosed binding value)

3. `ticket` -- **third person, agent-facing case summary**.
   - Start with the problem description, then customer name (no entity slot IDs).
   - End with `"They will consider the issue resolved when..."` followed by a natural description of the end state.
   - The ticket gives the agent direction -- it does not need to be mechanically precise because `check_resolution_status` handles the actual resolution gate. But it should be specific enough that the agent knows what kind of task this is (e.g. "get charging started" vs "update account settings").
   - Keep the ticket on the surface of the case. It may include user-observable start-binding facts, but it must NOT enumerate latent blockers, internal branch/lane names, or predicted next-stage failures that the agent has not yet discovered.
   - Do NOT enumerate every state change as a checklist. The ticket should read like a support case note, not an answer sheet.
   - Good: `"The user reports their EV charging session failed to start with an error displayed on the station screen. Customer name: Jordan Lee. They will consider the issue resolved when charging begins successfully."`
   - Bad: `"Customer Jordan Lee (account A1001) at station ST1001, session S1001, reports charging failure with fault code BH-101. Likely blockers include stale session authorization, missing profile, pending vehicle authorization, and retry-path failure. Resolve when: fraud lock is off, billing hold is cleared, payment token is valid, backend link is up, station certificate is fresh, fault code reads NONE, charging profile is ready, diagnostics have run, and firmware is current."` (leaks entity IDs + latent blockers + undisclosed binding value + state checklist)

Persona rule:

- `personas.yaml` must NOT contain customer names -- only personality traits.
- The scaffold automatically prepends the entity name from context bindings to the persona text.
- This ensures persona identity always matches the assigned entity triple.

Narrative self-review (required):

1. confirm authored text does not include internal path syntax (for example `agent.*`, `user.*`),
2. confirm authored text does not leak action ids or tool names,
3. confirm authored text does not include entity slot IDs (account_id, station_id, session_id) -- these are plumbing, never user-visible,
4. confirm ticket ends with a single natural completion condition, not a state checklist,
5. confirm the ticket's completion condition gives the agent clear direction about what kind of task this is -- read `resolved_when` to understand what "resolved" means, then verify that the "They will consider the issue resolved when..." sentence describes a concrete, observable outcome (e.g. "charging begins successfully", "the error is cleared"). The exact field names do not need to appear verbatim. If the ticket says something fully generic like "when the issue is fixed" with no indication of what the task is about, rewrite it to be more specific.
6. confirm start-binding values are present in both `known_info` and `ticket` when applicable -- these are user-observable facts (error codes, plan names), not entity slot IDs,
7. confirm undisclosed binding values (listed in `undisclosed_binding_values`) do NOT appear anywhere in authored text -- these must be acquired during task execution,
8. confirm `known_info` and `ticket` use the customer name from `entity_context`, not a hardcoded or guessed name.
9. confirm `ticket` and `known_info` do NOT name internal branch labels, lane labels, latent blocker lists, or predicted later-stage faults unless those are already directly user-observable start-binding facts.

## Start-Binding Visibility Rule

When `start_bindings` is non-empty, the concrete binding value must appear in:

1. `runtime.ticket` (agent-visible)
2. `runtime.known_info` (user-visible)

These are user-observable facts (error codes, plan names, etc.) -- not entity slot IDs.

`run_preflight` fails this with `check_start_bindings_visibility` if missing.

## Undisclosed-Binding Non-Disclosure Rule

When `undisclosed_binding_values` is non-empty, the concrete values must NOT appear in any
authored field (`reason_for_call`, `known_info`, `ticket`). These values must be acquired
during task execution via a tool call.

The narrative brief emits `undisclosed_binding_values: [...]` listing the concrete values.
`run_runtime_narrative_check` hard-fails if any of these values appear in authored text.

Why: if the user pre-discloses an undisclosed binding value, the agent already has the
information and never triggers the discovery tool call, causing the downstream dependency
structure to collapse.

## ACTION Reward Note

If a domain uses volatile bindings that can invalidate and require reacquisition, `ACTION`
should not be the sole correctness signal. Keep `ACTION` as optional weak coverage if you want
visibility into tool usage, but drive pass/fail from `ENV_ASSERTION` and strict stop-gates.

## Stop and Completion Discipline

`run_stop_gate_inject` enforces strict stop-gate criteria for the user-observable subset of
each task's `goal_world`, as defined by `stop_gate_map.yaml`. Full terminal-state
correctness comes from terminal-profile validity plus env assertions, which check the
`goal_world` predicates (the terminal profile's requires_world). This avoids penalizing
agents for reasonable actions beyond the minimal plan.

Task instructions must keep strict stop behavior:

1. call `check_resolution_status` before stopping,
2. emit `###STOP###` only when `resolved=true`,
3. if unresolved, report unmet criteria and continue.

## Init Setters and Env Assertions on Toolkits

The runtime scaffold generates `initialization_actions` (calling `set_<name>`) and
`env_assertions` (calling `assert_<name>`) that must exist as methods on the domain's
`tools.py` (assistant) and `user_tools.py` (user) toolkits.

**Naming convention**: method names are derived from world paths. For paths with 3+
plain segments (e.g. `agent.errand_a.status`), the method name includes the section:
`set_errand_a_status`, `assert_errand_a_status`. For paths with bracket notation
(e.g. `agent.accounts[active_account].hold_status`), only the leaf is used:
`set_hold_status`. This avoids ambiguity when multiple DB sections share field names
like `status` or `active`.

**Init setters** (`set_<name>(value)`) assign a value to the DB field. Use typed enum
constructors for enum fields (e.g. `ErrandStatus(value)`), direct assignment for booleans.

**Env assertions** (`assert_<name>(expected) -> bool`) compare the current DB field
value against the expected value and return a boolean. Use `.value` for enum comparisons.

These methods are NOT decorated with `@is_tool` -- they are internal helpers called only
by the runtime initialization and assertion machinery.

**Compound naming rule**: For `user.physical.test_charge_state`, the scaffold generates
`set_physical_test_charge_state` (not `set_test_charge_state`). If your toolkit uses the
short leaf name, add an alias: `set_physical_test_charge_state = set_test_charge_state`.
Same pattern for `get_*` and `assert_*`. This applies to ALL 3+ segment non-bracket paths
on both agent and user toolkits.

**Get methods** (`get_<name>() -> str`) are required alongside `set_<name>()` for every
projected field. These are used by `run_contract_sync()` to read current state. Return
`.value` for enum fields, `str(value)` for booleans.

**User-side `set_user_context`** must accept all parameters generated by context bindings
(typically `user_id` and `name`).

**Stop-gate derived fields**: When `stop_gate_map.yaml` maps agent-side goal paths to
user-observable check_fields, `user_tools.py` must be able to read agent DB state.
Add `bind_agent_db(agent_db)` to user tools, call it from the environment constructor,
and implement `_get_agent_derived(field)` to translate agent state into boolean check values.

## BFS Skip Option

Both `run_preflight` and `run_compile` support `--skip-bfs` to skip the expensive per-task
BFS solvability search. Use this when tasks are correct by construction from the sampler
and you only need the cheap structural checks (contract alignment, runtime fields, stop gates,
narrative quality, binding visibility). The BFS is O(thousands of states x hundreds of tasks)
and can take many minutes on large task sets.

## Report Format (required)

After running all commands, report:

1. pass/fail per task,
2. failing check type,
3. minimal fix,
4. risk-closure notes vs `domain_scope.md` known risks,
5. provenance note that only allowed runtime fields were authored.
