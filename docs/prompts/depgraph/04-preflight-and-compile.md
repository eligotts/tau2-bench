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
- `runtime.env_assertions` (from captured `goal_world` plus unchanged authored `start_world` paths)
- `runtime.actions` (from required action chain)
- `runtime.reward_basis`

Per-task authored (only 3 fields):

- `runtime.reason_for_call`
- `runtime.known_info`
- `runtime.ticket`

Hard rules:

1. Never edit sampled structural fields:
   - `start_world`, `start_bindings`, `goal_world`, `goal_capture_paths`, `goal_bindings`, `terminal_profile_id`, `required_actions`, `required_precedence`.
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
in the OpenAI schema sent to the LLM — if a docstring says "for the active station", the agent
will ask the user for a station ID. Use neutral phrasing like "for the current charging session"
instead.

**Bindings** (`fault_code`, etc.) are **discovered information**. They represent knowledge facts
the user can observe or provide (e.g. an error code on a screen). Bindings are defined in
`graph_contract.yaml` with a `source_tool` and `extraction_path`.

Bindings split into two categories with opposite authoring rules:

- **`start_bindings`**: The user knows the value at task start. The concrete value MUST appear
  in `known_info` and `ticket`.
- **`goal_bindings`**: The value must be **discovered mid-conversation** via a tool call
  (e.g. the agent asks the user to read their screen, triggering `check_station_screen`).
  The concrete value must NEVER appear in any authored field. The narrative brief emits a
  `goal_binding_do_not_disclose` list for these values; the narrative check hard-fails if
  any appear in authored text.

Important nuance: a goal binding may need to be reacquired multiple times if its `world_path`
is volatile and the visible value changes during recovery. `goal_bindings` only says the task
depends on discovering that binding type; it does not encode how many rereads the live run may
need. Do not pre-disclose later-stage values just because the same binding source is used again.

Why this matters: if a goal-binding value (e.g. fault code `BH-101`) is pre-disclosed in
`reason_for_call` or `known_info`, the agent already has the information and never triggers
the discovery tool call, causing the required action to fail evaluation.

Also note: `required_actions` is a deduped structural coverage list. It may contain
`check_station_screen` once even when a valid live run must reacquire the screen code three
times. Treat `required_actions` as coverage context, not as the full literal runtime trace.

Summary:

| | Entity slot IDs | start_bindings | goal_bindings |
|---|---|---|---|
| Example | `A1001`, `ST1001` | plan name, promo code | `BH-101`, `CERT-409` |
| Purpose | Select active entity | User-known facts | Mid-conversation discovery |
| In authored text? | **Never** | **Required** in known_info + ticket | **Never** |
| Tools need them? | No (context-scoped) | Yes (`tool_arg_bindings`) | Yes (discovered via tool call) |

## How to Use `task_narrative_briefs.yaml`

For each task brief:

1. Use `entity_context.name` (name only) to identify the customer in `known_info` and `ticket`. Entity slot IDs (`account_id`, `station_id`, `session_id`) are plumbing — never include them.
2. Use `start_state_summary` to write the user-experienced symptom for `reason_for_call`.
3. Use `start_state_summary.bindings` to include start-binding values (e.g. error codes, plan names) in `known_info` when present. These are user-observable facts, not internal state.
4. Check `goal_binding_do_not_disclose` — if any values are listed, those must NOT appear anywhere in `reason_for_call`, `known_info`, or `ticket`. These are goal-binding values that the user must discover mid-conversation via a tool call. Pre-disclosing them prevents the discovery action from firing.
5. Use `goal_state_summary` + `completion_cues` to write ONE natural, observable success criterion in `ticket` — not a state-by-state checklist.
6. Use `required_action_chain` only as internal author context; do not leak this sequence into user or agent text.

Writing constraints and voice:

1. `reason_for_call` — **first person, conversational**.
   - Describe what the user is experiencing and what they want fixed.
   - Include frustration or urgency when natural.
   - Never mention internal paths, tool names, or solution steps.
   - Good: `"My charging session won't start. The screen is showing some kind of error and I need to charge my car before a long drive."`
   - Bad: `"Charging fault BH-101 is active. Backend link is down. Need fraud lock removed and billing hold cleared."` (leaks goal-binding value + internal state)

2. `known_info` — **second person, factual context**.
   - Start with `"You are [name]"` using only the name from `entity_context`.
   - Add situational context the user would naturally know (where they are, what they observe, what they were doing).
   - Include concrete start-binding values (error codes, plan names) when present — these are user-observable facts.
   - Do NOT include entity slot IDs (account, station, session). Do NOT list internal state.
   - Good: `"You are Jordan Lee. You are at a charging station and your session won't start. The station screen is showing an error."`
   - Bad: `"Name: Jordan Lee. Account: A1001. Station: ST1001. Session: S1001. Fault code: BH-101."` (leaks entity IDs + goal-binding value)

3. `ticket` — **third person, agent-facing case summary**.
   - Start with the problem description, then customer name (no entity slot IDs).
   - End with `"They will consider the issue resolved when..."` followed by a natural description of the end state.
   - The ticket gives the agent direction — it does not need to be mechanically precise because `check_resolution_status` handles the actual resolution gate. But it should be specific enough that the agent knows what kind of task this is (e.g. "get charging started" vs "update account settings").
   - Keep the ticket on the surface of the case. It may include user-observable start-binding facts, but it must NOT enumerate latent blockers, internal branch/lane names, or predicted next-stage failures that the agent has not yet discovered.
   - Do NOT enumerate every state change as a checklist. The ticket should read like a support case note, not an answer sheet.
   - Good: `"The user reports their EV charging session failed to start with an error displayed on the station screen. Customer name: Jordan Lee. They will consider the issue resolved when charging begins successfully."`
   - Bad: `"Customer Jordan Lee (account A1001) at station ST1001, session S1001, reports charging failure with fault code BH-101. Likely blockers include stale session authorization, missing profile, pending vehicle authorization, and retry-path failure. Resolve when: fraud lock is off, billing hold is cleared, payment token is valid, backend link is up, station certificate is fresh, fault code reads NONE, charging profile is ready, diagnostics have run, and firmware is current."` (leaks entity IDs + latent blockers + goal-binding value + state checklist)

Persona rule:

- `personas.yaml` must NOT contain customer names — only personality traits.
- The scaffold automatically prepends the entity name from context bindings to the persona text.
- This ensures persona identity always matches the assigned entity triple.

Narrative self-review (required):

1. confirm authored text does not include internal path syntax (for example `agent.*`, `user.*`),
2. confirm authored text does not leak action ids or tool names,
3. confirm authored text does not include entity slot IDs (account_id, station_id, session_id) — these are plumbing, never user-visible,
4. confirm ticket ends with a single natural completion condition, not a state checklist,
5. confirm the ticket's completion condition gives the agent clear direction about what kind of task this is — read `completion_cues` to understand what "resolved" means, then verify that the "They will consider the issue resolved when..." sentence describes a concrete, observable outcome (e.g. "charging begins successfully", "the error is cleared"). The exact field names from the cues do not need to appear verbatim. If the ticket says something fully generic like "when the issue is fixed" with no indication of what the task is about, rewrite it to be more specific.
6. confirm start-binding values are present in both `known_info` and `ticket` when applicable — these are user-observable facts (error codes, plan names), not entity slot IDs,
7. confirm goal-binding values (listed in `goal_binding_do_not_disclose`) do NOT appear anywhere in authored text — these must be discovered mid-conversation,
8. confirm `known_info` and `ticket` use the customer name from `entity_context`, not a hardcoded or guessed name.
9. confirm `ticket` and `known_info` do NOT name internal branch labels, lane labels, latent blocker lists, or predicted later-stage faults unless those are already directly user-observable start-binding facts.

## Start-Binding Visibility Rule

When `start_bindings` is non-empty, the concrete binding value must appear in:

1. `runtime.ticket` (agent-visible)
2. `runtime.known_info` (user-visible)

These are user-observable facts (error codes, plan names, etc.) — not entity slot IDs.

`run_preflight` fails this with `check_start_bindings_visibility` if missing.

## Goal-Binding Non-Disclosure Rule

When `goal_bindings` is non-empty, the concrete binding values must NOT appear in any authored
field (`reason_for_call`, `known_info`, `ticket`). These values must be discovered
mid-conversation via a tool call (e.g. the agent asks the user to check their screen).

The narrative brief emits `goal_binding_do_not_disclose: [...]` listing the concrete values.
`run_runtime_narrative_check` hard-fails if any of these values appear in authored text.

Why: if the user pre-discloses a goal-binding value, the agent already has the information
and never triggers the discovery tool call, causing the required action to fail evaluation.

## ACTION Reward Note

If a domain uses volatile bindings that can invalidate and require reacquisition, `ACTION`
should not be the sole correctness signal. Keep `ACTION` as optional weak coverage if you want
visibility into tool usage, but drive pass/fail from `ENV_ASSERTION` and strict stop-gates.

## Stop and Completion Discipline

`run_stop_gate_inject` enforces strict stop-gate criteria for the user-observable subset of
each task's captured `goal_world`, as defined by `stop_gate_map.yaml`. Full terminal-state
correctness still comes from terminal-profile validity plus env assertions, including unchanged
authored `start_world` paths outside the captured goal.

Task instructions must keep strict stop behavior:

1. call `check_resolution_status` before stopping,
2. emit `###STOP###` only when `resolved=true`,
3. if unresolved, report unmet criteria and continue.

## Report Format (required)

After running all commands, report:

1. pass/fail per task,
2. failing check type,
3. minimal fix,
4. risk-closure notes vs `domain_scope.md` known risks,
5. provenance note that only allowed runtime fields were authored.
