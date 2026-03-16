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
7. Include only causal user fields in world predicates/effects (`user.*` projected causal paths).
8. Exclude projection-only user fields from causal contracts.
9. Ensure each binding `extraction_path` is syntactically valid and schema-consistent where typed return schemas exist.
10. For every concrete action in contract, implement matching runtime tool callable now:
   - `requestor=assistant` -> callable in `tools.py`
   - `requestor=user` -> callable in `user_tools.py`
11. Ensure binding-gated actions expose concrete tool parameters matching `tool_arg_bindings` keys.
12. If one conceptual tool has a finite enum/route/mode input, prefer one runtime tool plus an
    `action_schemas` entry that expands into concrete actions, instead of hand-authoring several
    near-duplicate actions that differ only by literal tool args.
    Annotate that runtime tool parameter as `Literal[...]` or an `Enum`, not plain `str`, so the
    agent-visible tool schema exposes the valid values.
13. If a binding has `world_path` and that path is rewritten by actions or `sync_rules`, treat it as volatile:
   - only the immediate observation-driven tool, or clearly mutually-exclusive stage-specific tools, may map it through `tool_arg_bindings`
   - the longer repair chain should run from stable world predicates established by prior actions
14. Define `sync_rules` in the contract for every runtime sync behavior:
   - unconditional projections via `{path, from_path}`
   - conditional bridges/derived updates via `requires_world` + `{path, set}`
   - no hidden sync behavior outside the declared rules
15. Implement `sync_tools()` now to mirror the declared `sync_rules` exactly, both for the initial start world and after every tool call.
16. If using strict checker-based STOP:
   - include a user `stutter-only` action for `check_resolution_status`
   - implement matching user tool callable now
   - keep checker tool non-causal (no world/binding effects).
17. Runtime guard behavior must mirror contract preconditions:
   - unmet preconditions return explicit error/no-op message
   - no hidden state mutation on guard failure (`stutter_on_fail` semantics).
18. Keep naming explicit:
   - `action_id` is stable semantic unit
   - `tool_name` is executable callable
   - `action_schemas` are authoring sugar only; after expansion, concrete `action_id`s still need clear semantic names
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

If you want a real difficulty jump with minimal surface-area growth, add one shared downstream
lane that multiple branches must clear, and expose its finite blocker choices through one
enum-typed runtime tool plus an `action_schemas` expansion.

Why: If the only multi-prerequisite action is the final gate, all reasoning about
coordination is deferred to the end. Early convergence forces ongoing coordination.

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
