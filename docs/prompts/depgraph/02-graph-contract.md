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
3. Every action or action-schema variant defines:
   - `requires_world` using explicit predicate ops (`eq`, `neq`, `gt`, `lt`, `gte`, `lte`)
   - `requires_bindings` using `{binding_id, acquired}` predicates
   - `effects_world`, `effects_bindings`
   - `tool_arg_bindings` when bindings gate runtime tool calls
   - `tool_arg_literals` for finite literal params on the runtime tool call
4. Model user-supplied knowledge as normal tool-backed actions:
   - `requestor=user`
   - `classification=knowledge-only`
   - `tool_name=<real user read tool>`
   - `effects_bindings` includes produced binding ids.
5. Include `bindings` entries for every produced/required binding id.
6. Bindings are invalidated automatically when their `world_path` changes value; do not assume monotonic binding knowledge.
7. **Every binding MUST have at least one `tool_arg_bindings` consumer.** A binding that is only
   referenced in `requires_bindings` but never mapped through `tool_arg_bindings` to a
   downstream tool parameter is an **unenforceable ordering constraint** — it shapes the
   solver's plans but is invisible at runtime. The agent can skip the discovery step because
   no downstream tool requires the discovered value as a parameter.
   - `requires_world` preconditions are enforced at runtime by tool guards (DB state checks).
   - `requires_bindings` preconditions have NO runtime enforcement mechanism UNLESS the
     binding value flows through `tool_arg_bindings` into a required tool parameter.
   - The tool parameter is the enforcement: the agent literally cannot call the downstream
     tool without having first discovered the value.
   - Example: `check_calendar` produces binding `calendar_state` with extraction_path
     `result.conflict_meeting_id`. Downstream `cancel_meeting` has
     `tool_arg_bindings: {meeting_id: calendar_state}`. The agent must call `check_calendar`
     to get the meeting ID before it can call `cancel_meeting(meeting_id=...)`.
   - Anti-pattern: binding used only in `requires_bindings` with empty `tool_arg_bindings: {}`
     on all consuming actions. This binding is a ghost — the solver enforces it, runtime does not.
8. Include only causal user fields in world predicates/effects (`user.*` projected causal paths).
9. Exclude projection-only user fields from causal contracts.
10. Ensure each binding `extraction_path` is syntactically valid and schema-consistent where typed return schemas exist. The extracted value must be something the downstream tool needs as an **input parameter** (e.g. an ID, a name, a measured quantity) — not a status flag or boolean that mirrors world state. If the extraction_path only captures a status enum, the binding will have no natural `tool_arg_bindings` consumer.
11. For every concrete action in contract, implement matching runtime tool callable now:
   - `requestor=assistant` -> callable in `tools.py`
   - `requestor=user` -> callable in `user_tools.py`
12. Ensure binding-gated actions expose concrete tool parameters matching `tool_arg_bindings` keys.
13. If one conceptual tool has a finite enum/route/mode input, prefer one runtime tool plus an
    `action_schemas` entry that expands into concrete actions, instead of hand-authoring several
    near-duplicate actions that differ only by literal tool args.
    Annotate that runtime tool parameter as `Literal[...]` or an `Enum`, not plain `str`, so the
    agent-visible tool schema exposes the valid values.
14. If a binding has `world_path` and that path is rewritten by actions or `sync_rules`, treat it as volatile:
   - only the immediate observation-driven tool, or clearly mutually-exclusive stage-specific tools, may map it through `tool_arg_bindings`
   - the longer repair chain should run from stable world predicates established by prior actions
14a. If two or more alternative actions legitimately need the same value as a real tool
   argument across multiple stages, that value probably should not remain a volatile binding.
   Promote it into stable world state and gate the alternatives with normal `requires_world`
   predicates instead of fanning one volatile binding across same-stage alternatives.
14b. **`world_path` selection rule.** A binding's `world_path` should be a field whose value
   the binding semantically tracks — i.e., if the field changes, the binding's extracted
   value is genuinely stale. Do not bind to a field that changes as a *side-effect* of the
   consuming action (e.g. binding a dashboard summary to `incident.status` when triage
   changes status). If the binding captures a static observation that never goes stale,
   omit `world_path` entirely.
15. Define `sync_rules` in the contract for every runtime sync behavior:
   - unconditional projections via `{path, from_path}`
   - conditional bridges/derived updates via `requires_world` + `{path, set}`
   - no hidden sync behavior outside the declared rules
16. Implement `sync_tools()` now to mirror the declared `sync_rules` exactly, both for the initial start world and after every tool call.
17. If using strict checker-based STOP:
   - include a user `stutter-only` action for `check_resolution_status`
   - implement matching user tool callable now
   - keep checker tool non-causal (no world/binding effects).
18. Runtime guard behavior must mirror contract preconditions:
   - unmet `requires_world` preconditions return explicit error/no-op message
   - unmet `requires_bindings` preconditions are enforced structurally via `tool_arg_bindings`
     (the agent cannot supply a parameter it hasn't discovered)
   - no hidden state mutation on guard failure (`stutter_on_fail` semantics).
18a. **Guard completeness rule.** Every `if` branch in a tool that leads to an early
   return (noop, error, or guard failure) must check ONLY fields declared in that
   action's `requires_world`. If a tool reads a sub-field (e.g. `auth.token_pool`)
   as a guard, that sub-field must be: (a) a projection field, AND (b) listed in
   the action's `requires_world` with the value that enables the tool to proceed.
   A tool guard on a field invisible to the contract creates unsolvable tasks: the
   contract says the action can fire, the scaffold initializes only contracted fields,
   but the tool silently refuses because a hidden default blocks it. The automated
   guard completeness check (`check_tool_guard_completeness`) catches this class of
   bug — run it as part of preflight.
18b. **Default-value trap.** When adding a sub-field guard to the contract, check
   the data model's default value for that field. If the default IS the guard's
   noop/skip value (e.g. `token_pool` defaults to `VALID` and the tool noops on
   `VALID`), the scaffold must explicitly initialize the field away from its default
   for every task that needs the action to fire. Declare the field in
   `requires_world` with a `neq` predicate excluding the noop value, so the
   sampler/compiler knows to set a non-default value in `start_world`.
19. Keep naming explicit:
   - `action_id` is stable semantic unit
   - `tool_name` is executable callable
   - `action_schemas` are authoring sugar only; after expansion, concrete `action_id`s still need clear semantic names
   - avoid implicit aliasing; if aliasing is unavoidable, document it in contract comments.
20. Implement **init setter** methods on both toolkits for every projection field that tasks
    may set during initialization or assert at evaluation time:
    - `set_<name>(value)` — assign a value to the DB field. Use typed enum constructors for
      enum fields (e.g. `ErrandStatus(value)`), direct assignment for booleans/strings.
    - `assert_<name>(expected) -> bool` — compare current DB field value against expected,
      return boolean. Use `.value` for enum comparisons.
    - These are NOT `@is_tool` decorated — they are internal helpers called only by the
      runtime initialization and assertion machinery.
    - **Naming convention**: for paths with 3+ plain segments (e.g. `agent.errand_a.status`),
      include the section: `set_errand_a_status`, `assert_errand_a_status`. For bracket
      notation paths (e.g. `agent.accounts[active_account].hold_status`), use only the leaf:
      `set_hold_status`. This avoids ambiguity when multiple DB sections share field names.
    - Place assistant-env-type setters/assertions in `tools.py`, user-env-type in `user_tools.py`.
    - Do not limit this to the obvious headline fields. Expanded sampled tasks can require
      setters/assertions for stable IDs, availability booleans, reservation-hold fields,
      cost-paid flags, confirmation flags, and other fields that only appear once the full
      seed schema is expanded.
21. Implement `set_user_context` on `user_tools.py` accepting all parameters generated by
    context bindings (typically `user_id` and `name`).
22. When `stop_gate_map.yaml` maps agent-side goal paths to user-observable check_fields,
    `user_tools.py` must read agent DB state. Implement `bind_agent_db(agent_db)` and
    `_get_agent_derived(field)` to translate agent state into boolean check values. Call
    `bind_agent_db` from the environment constructor.

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

If you want a real difficulty jump with minimal surface-area growth, add one shared downstream
lane that multiple branches must clear, and expose its finite blocker choices through one
enum-typed runtime tool plus an `action_schemas` expansion.

Why: If the only multi-prerequisite action is the final gate, all reasoning about
coordination is deferred to the end. Early convergence forces ongoing coordination.

## Action Granularity and Splitting

### Expand conceptual operations into sub-steps

The most impactful decision in contract authoring is action granularity. Every real-world
operation has intermediate steps that create meaningful decision points. If your contract
has actions like "complete_errand" or "handle_care", the resulting tasks will be shallow
(depth 3-5) and test nothing beyond basic tool-following.

**Split every coarse action into its constituent steps:**

| Coarse action | Split into |
|---------------|------------|
| "do errand" | reserve_item → confirm_reservation → arrange_delivery → confirm_receipt |
| "delegate task" | contact_delegate → check_response → check_eta → notify_facility → assign_delegate |
| "get maintenance" | request_quotes → select_provider → schedule_visit → arrange_access → verify_completion |
| "arrange transport" | diagnose_issue → call_roadside → check_repair → confirm_fixed |

Each sub-step has its own `requires_world` preconditions that enforce ordering. The agent
must complete each step before proceeding, creating realistic multi-step reasoning chains.

### Fate-flag action splitting

When an action can succeed or fail (rideshare booking, delivery attempt, delegate contact),
model both outcomes as separate actions gated by an `init_only` fate flag:

```yaml
# Fate flag in projection_fields (init_only — never changed by actions)
- agent.transport.rideshare_will_succeed  # bool

# Success variant
- action_id: book_rideshare_success
  requires_world:
    - path: agent.transport.rideshare_will_succeed
      value: true
  effects_world:
    - path: agent.transport.rideshare_result
      set: booked

# Failure variant
- action_id: book_rideshare_fail
  requires_world:
    - path: agent.transport.rideshare_will_succeed
      value: false
  effects_world:
    - path: agent.transport.rideshare_result
      set: no_drivers
```

The BFS selects exactly one variant per seed (determined by the fate flag value in
`start_world`). Different seeds with different fate flag values produce structurally
different task paths.

**Design at least 2-3 fate-flagged action pairs per domain.** Each creates a binary
branch point. Combined with different seed configurations, N fate flags create up to 2^N
structural path variants.

### Fallback-gated actions

When an action can fail, the fallback action should be gated on the failure having
occurred. This prevents the BFS from short-circuiting directly to the fallback:

```yaml
# Pickup only available AFTER delivery was attempted and failed
- action_id: arrange_pickup_after_delivery_fail
  requires_world:
    - path: agent.errand.delivery_result
      value: unavailable  # must have tried delivery first

# Pickup available when delivery was never an option
- action_id: arrange_pickup_no_delivery
  requires_world:
    - path: agent.errand.delivery_available
      value: false  # delivery was never possible
```

Without this gating, BFS will always pick the shorter path (direct pickup) and never
exercise the delivery→failure→recovery chain.

### Degradable resource variants

When a shared resource degrades with use (money, capacity, quota), each consuming action
needs variants per resource level since effects must be concrete values:

```yaml
- action_id: pay_bill_plenty
  requires_world:
    - path: agent.finance.available_funds
      value: plenty
  effects_world:
    - path: agent.finance.bill_status
      set: paid
    - path: agent.finance.available_funds
      set: tight  # plenty → tight

- action_id: pay_bill_tight
  requires_world:
    - path: agent.finance.available_funds
      value: tight
  effects_world:
    - path: agent.finance.bill_status
      set: paid
    - path: agent.finance.available_funds
      set: broke  # tight → broke
```

Actions requiring the resource gate on the current level. When the resource is exhausted,
the agent must switch to free alternatives.

## Difficulty Engineering

These patterns increase the cognitive difficulty of generated tasks. Apply them when the
domain goal is to challenge strong agents, not just test basic tool-following.

### When to use each pattern

Not every domain needs every pattern. Apply them in order of impact:

| Pattern | Impact | When to use | Watch out for |
|---------|--------|-------------|---------------|
| **Cascading sync rules** | Highest — multiplies tasks from same seed pool | Always for Tier 3+. A single fault becomes a multi-system task automatically. | Cycles (ensure intermediate repair states don't re-trigger cascades). BFS explosion if too many systems cascade. |
| **Repair side-effects** | High — forces discovery of non-obvious damage | When cascading alone isn't enough. Creates work the agent must discover from tool output, not from diagnostics. | Must pair with resolution gates or the damage is "free." |
| **Multi-step repair chains** | Medium — increases plan depth per system | When single-action repairs are too easy. `locked → degraded → healthy` is harder than `locked → healthy`. | Depth adds up fast with multi-fault seeds. Keep chains to 2-3 steps max per system. |
| **Cross-system prerequisites** | Medium — forces repair ordering reasoning | When the agent should reason about dependencies. `warm_cache` needs DB healthy first. | Creates hard dependencies that reduce BFS parallelism — use sparingly (3-5 per domain). |
| **Sync-rule traps (bouncing)** | Very high — punishes pattern-matching | Only for Tier 4 / frontier targets. Agent tries obvious fix, it bounces back, must reason about root cause. | Easy to make tasks unsolvable. Always verify BFS can find the correct path. Use at most 1-2 traps per domain. |

**Proportionality rule of thumb:** For a domain targeting 100+ tasks:
- 60-70% of difficulty should come from cascading + value-gated branching (structural diversity)
- 20-30% from side-effects + multi-step chains (discovery difficulty)
- 0-10% from sync-rule traps (causal reasoning difficulty)

### Cascading sync rules

Add sync rules that model real-world system interdependencies: when one system fails, it
damages downstream systems.

```yaml
# DB failure takes out cache (cache depends on DB for reads)
- rule_id: sync_db_breaks_cache
  requires_world:
    - path: agent.db.health
      op: neq
      value: healthy
    - path: agent.cache.health
      value: healthy  # only fires once; won't re-fire when cache is already broken
  effects_world:
    - path: agent.cache.health
      set: stale
```

Why this works: A single-fault seed becomes a multi-system task automatically. The agent
must discover ALL broken systems (including cascade damage it didn't expect) and fix them
in the right order. This multiplies both task count and difficulty from the same seed pool.

Cycle safety: Cascading sync rules are safe from BFS cycles when the target system's
intermediate repair states (e.g., `cold`, `crashing`) don't match the sync rule's trigger
condition (e.g., `healthy`). The final repair action that sets `healthy` typically requires
the root cause system to already be fixed, preventing re-triggering.

### Repair side-effects

Make certain repair actions create new problems in OTHER systems:

```yaml
- action_id: assistant_failover_db
  effects_world:
    - path: agent.db.health
      set: healthy
    - path: agent.queue.dlq_state
      set: has_messages  # transactions lost during failover
```

The agent must notice collateral damage from its own repairs and address it. Pair
side-effects with resolution gate requirements (see below) to force cleanup.

### Sync-rule traps (bouncing state)

A sync rule that undoes a repair when the root cause hasn't been addressed:

```yaml
# Canary deploy destabilizes app — repairs bounce back until rollback
- rule_id: sync_canary_destabilizes_app
  requires_world:
    - path: agent.app.deploy_version
      value: canary
    - path: agent.app.health
      value: healthy
  effects_world:
    - path: agent.app.health
      set: high_latency
```

The BFS correctly discovers that rollback must come BEFORE app repair. But an LLM at
runtime will likely try the obvious fix first, see it bounce back, and need to reason
about the root cause. This is the highest-difficulty pattern because it punishes
pattern-matching and rewards causal reasoning.

BFS handles this correctly: the "fix then bounce" state was already visited, so BFS
prunes it and explores the rollback-first path instead.

### Resolution gate tightening

When adding side-effects, ensure the resolution sync rule (or terminal profiles) requires
the side-effect damage to be cleaned up:

```yaml
- rule_id: sync_incident_resolved
  requires_world:
    - path: agent.queue.dlq_state
      op: neq
      value: has_messages  # must replay DLQ before resolution
    - path: agent.db.vacuum_state
      value: clean  # must vacuum after crash loop
    # ... plus all system health checks
```

Without this, side-effect damage is "free" — nobody has to clean it up, and the tasks
don't get harder. Always pair side-effects with resolution gates.

### Policy de-prescriptification

If the policy maps faults directly to fixes (e.g., "locked → drain + restart"), it becomes
an answer key that any LLM can follow mechanically. For hard domains:

- Give **principles** ("fix root causes before symptoms", "check downstream systems after
  repairs") instead of **recipes** ("for db_failure, do X then Y").
- Mention that repairs may have side-effects without specifying which ones.
- Tell the agent to check ALL systems before resolution, not just the ones it repaired.
- Hint at dependency ordering without giving the exact order.
- **Do not list tool names in the policy.** Agent tools are injected into the API call
  with their names and docstrings — the agent already knows what tools it has. User tools
  are the user's to discover — describe what information or actions the agent needs from
  the user in natural language. Listing tool names in the policy creates two problems:
  (1) it duplicates information already in the tool schema, creating maintenance drift, and
  (2) listing both agent and user tool names in the same document creates ambiguity about
  who calls what, causing agents to delegate their own tools to the user.
- **Write good tool docstrings instead.** Each tool's docstring should describe what it does,
  what state it applies to, and what prerequisites it has. This is the right place for tool
  affordance information — not the policy.

The difficulty comes from the agent needing to reason from diagnostic output and its
tool definitions rather than pattern-matching against the policy.

## Companion Artifacts

18. Author concrete persona pool in `personas.yaml` for runtime-stage assignment:
   - include 2-5 personas with stable `persona_id`
   - each persona has concise `display_name` + `profile_text`
   - optional style tags (for example `low_tech`, `high_urgency`, `detail_oriented`)
   - keep personas domain-relevant but avoid leaking solution steps or backend internals
19. Author `runtime_defaults.yaml` for deterministic scaffold generation:
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
