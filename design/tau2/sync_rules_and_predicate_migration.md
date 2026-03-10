# Migration Plan: Sync Rules, Unified Predicates, and Binding Invalidation

**Status:** Ready for implementation
**Author:** Eli Gottlieb
**Date:** 2026-03-09

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [The Bug That Motivated This Work](#3-the-bug-that-motivated-this-work)
4. [Design Decisions](#4-design-decisions)
5. [Migration Step 1: Unified Predicates](#5-migration-step-1-unified-predicates)
6. [Migration Step 2: Sync Rules Schema](#6-migration-step-2-sync-rules-schema)
7. [Migration Step 3: BFS Integration](#7-migration-step-3-bfs-integration)
8. [Migration Step 4: Binding Invalidation](#8-migration-step-4-binding-invalidation)
9. [Migration Step 5: Validation and Authoring Guides](#9-migration-step-5-validation-and-authoring-guides)
10. [Migration Step 6: EV Domain Migration](#10-migration-step-6-ev-domain-migration)
11. [File Reference Index](#11-file-reference-index)

---

## 1. Executive Summary

The depgraph system generates evaluation tasks by walking a dependency graph (BFS over
world state + bindings). The runtime (tau2) then executes those tasks with real tools,
real DBs, and a `sync_tools()` callback that propagates state between the agent and user
databases after every tool call.

**The problem:** The BFS sampler has zero awareness of `sync_tools()`. It applies action
effects and moves on. But at runtime, `sync_tools()` can:
- Copy agent fields to user display fields (projections)
- Trigger cross-DB effects when conditions are met (causal bridges)
- Compute derived values from multiple fields (cascades)

This gap means the sampler can generate tasks that are theoretically solvable in its
simplified world model but fail at runtime because sync_tools changes state the sampler
didn't anticipate. We discovered this through a concrete bug (Section 3).

**The fix** is three changes:
1. **Unified predicates** — collapse `requires_world` / `requires_absent_world` into one
   list with `eq`/`neq`/`gt`/`lt` operators
2. **Sync rules** — declare the sync_tools behavior in the graph contract so the BFS can
   apply it after every action
3. **Binding invalidation** — if a sync rule or action effect overwrites a field that a
   binding reads from, that binding is invalidated and must be re-acquired

---

## 2. System Overview

### 2.1 Architecture: Two Worlds That Must Agree

```
                AUTHORING TIME                           RUNTIME
           ┌──────────────────────┐            ┌──────────────────────┐
           │   graph_contract.yaml │            │   tau2 Environment   │
           │                      │            │                      │
           │  actions:            │            │  tools.py            │
           │    requires_world    │ ◄──must──► │    tool guards       │
           │    effects_world     │   match    │    tool side-effects │
           │                      │            │                      │
           │  bindings:           │            │  user_tools.py       │
           │    source_tool       │ ◄──must──► │    read tools        │
           │    world_path        │   match    │    causal tools      │
           │                      │            │                      │
           │  (NO sync logic)     │ ◄──GAP!──► │  environment.py      │
           │                      │            │    sync_tools()      │
           └──────────────────────┘            └──────────────────────┘
                    │                                     │
                    ▼                                     ▼
           ┌──────────────────────┐            ┌──────────────────────┐
           │  BFS Sampler/Solver  │            │  Evaluator           │
           │                      │            │                      │
           │  State: (world, bindings)         │  Checks: action      │
           │  apply_action → new state         │    expectations vs   │
           │  NO post-action propagation       │    actual tool calls │
           └──────────────────────┘            └──────────────────────┘
```

### 2.2 Key Files

**Depgraph engine** (the BFS/solver/sampler):
- `src/tau2/generators/depgraph/types.py` — Schema: `WorldPredicateSpec`, `ActionContract`, `GraphContractSpec`, `BindingSourceSpec`
- `src/tau2/generators/depgraph/semantics.py` — Core functions: `predicate_holds()`, `is_action_enabled()`, `apply_action()`
- `src/tau2/generators/depgraph/sampler.py` — BFS fan-out that generates candidate tasks from seeds
- `src/tau2/generators/depgraph/solver.py` — SAT solver (`find_plan()`) used by preflight
- `src/tau2/generators/depgraph/preflight.py` — Solvability + ablation checks
- `src/tau2/generators/depgraph/runtime_checks.py` — Contract-to-environment alignment validation
- `src/tau2/generators/depgraph/loaders.py` — YAML loading into Pydantic models

**Runtime** (tau2 execution engine):
- `src/tau2/environment/environment.py` — Base `Environment` class; `sync_tools()` called after every tool call (lines 180, 403) and at init (line 63)
- `src/tau2/evaluator/evaluator.py` + `evaluator_action.py` — Action matching; `compare_with_tool_call()` checks tool name + filtered args
- `src/tau2/data_model/tasks.py` — `Action.compare_with_tool_call()` (line 166): if `compare_args=[]`, only checks tool name was called; if `compare_args=["fault_code"]`, checks that arg value matches

**EV domain** (the first domain to migrate):
- `src/tau2/domains/ev_charging_support/tools.py` — Assistant tools (diagnostics, billing, connectivity, reprovision)
- `src/tau2/domains/ev_charging_support/user_tools.py` — User tools (physical actions, screen check, resolution status)
- `src/tau2/domains/ev_charging_support/environment.py` — `sync_tools()` with 1-1 projections + causal bridge + fault code cascade
- `src/tau2/domains/ev_charging_support/data_model.py` — Agent DB schema (enums, entities)
- `src/tau2/domains/ev_charging_support/user_data_model.py` — User DB schema (physical state, view state, stop gate)
- `data/tau2/domains/ev_charging_support/graph_contract.yaml` — The contract (23 actions, 2 bindings, 20 projection fields)
- `data/tau2/domains/ev_charging_support/sampling_request.yaml` — 11 seeds generating 38 tasks

**Authoring guides** (prompts for Claude Code):
- `docs/prompts/depgraph/01-domain-scope.md` — World scope design
- `docs/prompts/depgraph/02-graph-contract.md` — Contract + tools co-authoring
- `docs/prompts/depgraph/08-runtime-environment-and-sync.md` — Environment + sync_tools
- `docs/prompts/depgraph/CHECKLIST.md` — Quick reference

### 2.3 How the BFS Works Today

The BFS state is `(world: dict[str, Any], bindings: frozenset[str])`.

`world` is a flat dictionary mapping projected paths to values:
```python
{
    "agent.accounts[active_account].hold_status": "present",
    "agent.sessions[active_session].profile_state": "not_ready",
    "user.physical.vehicle_ready_state": "not_ready",
    ...
}
```

`bindings` is a set of string IDs (e.g., `{"fault_code", "app_error_class"}`). Bindings
are boolean: acquired or not. The BFS does not track binding values.

Each BFS step:
1. Check `is_action_enabled(action, world, bindings)` — all `requires_world` predicates
   hold, no `requires_absent_world` predicates hold, required bindings present, absent
   bindings not present
2. `apply_action(action, world, bindings)` — apply `effects_world` assignments, add
   `effects_bindings` to set
3. **Nothing else** — no sync propagation, no binding invalidation
4. Check if new state was already visited; if not, add to BFS queue

### 2.4 How sync_tools() Works Today

In the EV domain (`src/tau2/domains/ev_charging_support/environment.py:91-194`),
`sync_tools()` runs after every tool call and does three things:

**1. Causal bridge (user → agent), lines 107-125:**
```python
if (
    user.physical.test_charge_state == TestChargeState.RUN
    and account.hold_status == HoldStatus.CLEARED
    and account.payment_token_status == PaymentTokenStatus.VALID
    # ... 12 more conditions
):
    session.charge_state = ChargeState.ACTIVE
```
This is modeled in the contract as `effects_world` on the `user_run_test_charge` action,
so the BFS already accounts for it. But the runtime implements it here, not in the tool.

**2. 1-1 projections (agent → user), lines 128-139:**
```python
user.view.display_hold_status = account.hold_status.value
user.view.display_payment_token_status = account.payment_token_status.value
# ... 10 more
```
These are simple copies. Not modeled in the BFS at all — the BFS doesn't know
`display_hold_status` exists.

**3. Computed fault code cascade (agent → user), lines 141-193:**
```python
if station.reachability_state == ReachabilityState.UNREACHABLE:
    user.view.display_fault_code = "STATION_UNREACHABLE"
    return
if network.backend_link_state == BackendLinkState.DOWN:
    user.view.display_fault_code = "NET-410"
    return
# ... priority chain continues
```
This is a many-to-one computed derivation. Not modeled in the BFS. This is the
problematic part — it creates a runtime-only field (`display_fault_code`) that the
solver doesn't know about, and tools use it as a fallback.

### 2.5 How Bindings Work Today

A binding in the contract:
```yaml
bindings:
  - binding_id: fault_code
    source_tool: check_station_screen
    extraction_path: result.fault_code
    world_path: agent.sessions[active_session].last_fault_code
    observability_all_of:
      - op: eq
        path: user.physical.screen_accessible
        value: true
```

- `source_tool`: the user tool that discovers this value
- `extraction_path`: how to extract the value from the tool's return
- `world_path`: the field in the world state where this value lives
- `observability_all_of`: conditions that must be true for the binding to be acquirable

In the BFS, bindings are just presence/absence checks. `requires_bindings: [fault_code]`
means "fault_code must have been acquired." `effects_bindings: [fault_code]` means "this
action produces the fault_code binding."

At scaffold time (`run_runtime_scaffold.py`), binding values are resolved from `start_world`
via `world_path` and baked into `compare_args` for the evaluator.

### 2.6 How Actions Are Evaluated at Runtime

The evaluator (`src/tau2/evaluator/evaluator_action.py`) checks whether the agent called
the expected tools. For each golden action:

```python
def compare_with_tool_call(self, tool_call: ToolCall) -> bool:
    if self.name != tool_call.name:
        return False
    if len(self.compare_args) == 0:
        return True                          # just check name
    tool_args = {k: v for k, v in tool_call.arguments.items() if k in self.compare_args}
    action_args = {k: v for k, v in self.arguments.items() if k in self.compare_args}
    return tool_args == action_args
```

If `compare_args = []`, only the tool name is checked. If `compare_args = ["fault_code"]`,
the argument value must also match.

Currently the scaffold sets `compare_args = []` for most actions to avoid false negatives
from binding value shifts. But this means argument correctness is never verified.

---

## 3. The Bug That Motivated This Work

**Task:** `billing_partial_knowledge_d13_482`
**Simulation file:** `data/simulations/2026-03-04T23:08:56.079486_ev_charging_support_llm_agent_gpt-5.2_user_simulator_gpt-5.2.json`

### What happened

1. User reads station screen → sees `BH-101` (fault code binding acquired)
2. Agent runs diagnostics with `fault_code="BH-101"` ✓
3. Agent fixes billing issues ✓
4. Agent calls `reprovision_billing(fault_code="BH-101")` ✓
5. **Inside `_do_reprovision()`** (tools.py:~299): `session.last_fault_code = "NONE"`
6. **sync_tools() runs.** The cascade (environment.py:141-185) looks at current state.
   Billing is fixed, but `retry_state == not_ready`. Cascade sets
   `display_fault_code = "RETRY-301"`.
7. Agent calls `reset_retry_path(fault_code=...)`. The tool's `_fault_code_guard()`
   (tools.py:95-108) checks current state:
   - `session.last_fault_code` = `"NONE"` (overwritten in step 5)
   - `display_fault_code` = `"RETRY-301"` (computed in step 6)
   - Neither matches `"BH-101"`.
   Agent correctly uses `fault_code="RETRY-301"`.
8. **Evaluator** checks `reset_retry_path`. The scaffold baked `fault_code="BH-101"` from
   the binding's `world_path`. Agent used `"RETRY-301"`. **Action check fails.**

### Root causes

1. **Binding-world coupling:** The `fault_code` binding reads from
   `agent.sessions[active_session].last_fault_code`. Reprovision overwrites that same path
   via `effects_world: [{path: ..., set: NONE}]`. The contract treats bindings as immutable
   knowledge, but the runtime mutates the backing field.

2. **Unmodeled sync logic:** `display_fault_code` is computed by sync_tools from multiple
   agent fields via a priority cascade. The BFS doesn't know this field exists. The tool's
   `_fault_code_guard()` accepts it as a valid fault code, so the agent uses a value the
   evaluator never expected.

3. **No invalidation primitive:** The contract has no way to say "this action invalidates
   the fault_code binding." The BFS assumes all bindings are permanently valid once acquired.

---

## 4. Design Decisions

### 4.1 Bindings stay tied to world fields

Bindings represent real values in the world. The `world_path` stays — it grounds the
binding in something concrete. The fix is not to disconnect bindings from the world but
to properly handle what happens when the world changes under them.

### 4.2 Sync rules are prereqs + effects (same shape as actions)

Instead of allowing arbitrary Python in sync_tools, we declare sync behavior in the
contract using the same primitives as actions: `requires_world` (preconditions) and
`effects_world` (state changes). Two kinds of effects:
- `{path, set: literal}` — set to a fixed value (same as actions)
- `{path, from_path: source}` — copy value from another field (new, for projections)

If you can't express it as prereqs + effects, it must be a contract action, not sync logic.

### 4.3 The BFS applies sync rules after every action

This makes the BFS see the same state the runtime sees. The BFS step becomes:
1. Apply action effects
2. Evaluate sync rules (fixed-point)
3. Check binding invalidation
4. Record new node

### 4.4 Binding invalidation is automatic

If any action effect or sync rule writes to a path that matches an acquired binding's
`world_path`, and the new value differs from what was there when the binding was acquired,
the binding is removed from the acquired set. The BFS must find a re-acquisition edge.

### 4.5 Unified predicates replace requires/requires_absent split

No more separate `requires_world` / `requires_absent_world`. One list with `op` field
supporting `eq`, `neq`, `gt`, `lt`, `gte`, `lte`.

### 4.6 The fault code cascade must die

The priority cascade in sync_tools that computes `display_fault_code` from multiple agent
fields violates the "prereqs + effects" constraint. It's replaced by per-subsystem
observable fields that users read through separate gated tools. Progressive disclosure
comes from tool preconditions, not computed projections.

---

## 5. Migration Step 1: Unified Predicates

### 5.1 Schema change in `types.py`

**File:** `src/tau2/generators/depgraph/types.py`

**Current** (line 37):
```python
class WorldPredicateSpec(BaseModel):
    op: Literal["eq"] = "eq"
    path: str
    value: Any
```

**New:**
```python
class WorldPredicateSpec(BaseModel):
    op: Literal["eq", "neq", "gt", "lt", "gte", "lte"] = "eq"
    path: str
    value: Any

    @model_validator(mode="after")
    def validate_predicate(self) -> "WorldPredicateSpec":
        if not self.path.strip():
            raise ValueError("world predicate path cannot be empty")
        if self.op in ("gt", "lt", "gte", "lte"):
            if not isinstance(self.value, (int, float)):
                raise ValueError(
                    f"Comparison operator '{self.op}' requires numeric value, "
                    f"got {type(self.value).__name__}"
                )
        return self
```

### 5.2 Collapse ActionContract fields

**File:** `src/tau2/generators/depgraph/types.py`

**Current** (lines 88-94):
```python
class ActionContract(BaseModel):
    # ...
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)
    requires_absent_world: list[WorldPredicateSpec] = Field(default_factory=list)
    requires_bindings: list[str] = Field(default_factory=list)
    requires_absent_bindings: list[str] = Field(default_factory=list)
```

**New:**
```python
class BindingPredicateSpec(BaseModel):
    """Predicate over binding acquisition state."""
    binding_id: str
    acquired: bool = True   # True = must be acquired, False = must NOT be acquired

class ActionContract(BaseModel):
    # ...
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)
    requires_bindings: list[BindingPredicateSpec] = Field(default_factory=list)
    # Remove requires_absent_world and requires_absent_bindings
```

**Migration path for existing contracts:** `requires_absent_world` entries become
`requires_world` entries with `op: neq`. `requires_absent_bindings` entries become
`requires_bindings` entries with `acquired: false`.

### 5.3 Update `predicate_holds()` in semantics.py

**File:** `src/tau2/generators/depgraph/semantics.py`

**Current** (lines 38-42):
```python
def predicate_holds(predicate: WorldPredicateSpec, world: dict[str, Any]) -> bool:
    if predicate.op != "eq":
        return False
    return world.get(predicate.path, None) == predicate.value
```

**New:**
```python
def predicate_holds(predicate: WorldPredicateSpec, world: dict[str, Any]) -> bool:
    value = world.get(predicate.path, None)
    if predicate.op == "eq":
        return value == predicate.value
    elif predicate.op == "neq":
        return value != predicate.value
    elif predicate.op == "gt":
        return value is not None and value > predicate.value
    elif predicate.op == "lt":
        return value is not None and value < predicate.value
    elif predicate.op == "gte":
        return value is not None and value >= predicate.value
    elif predicate.op == "lte":
        return value is not None and value <= predicate.value
    return False
```

### 5.4 Update `is_action_enabled()` in semantics.py

**File:** `src/tau2/generators/depgraph/semantics.py`

**Current** (lines 87-104):
```python
def is_action_enabled(action, world, bindings, binding_sources_by_id):
    if not all(predicate_holds(p, world) for p in action.requires_world):
        return False
    if any(predicate_holds(p, world) for p in action.requires_absent_world):
        return False
    if not set(action.requires_bindings).issubset(bindings):
        return False
    if set(action.requires_absent_bindings) & set(bindings):
        return False
    if not _knowledge_source_ok(action, world, bindings, binding_sources_by_id):
        return False
    return True
```

**New:**
```python
def is_action_enabled(action, world, bindings, binding_sources_by_id):
    if not all(predicate_holds(p, world) for p in action.requires_world):
        return False
    for bp in action.requires_bindings:
        if bp.acquired and bp.binding_id not in bindings:
            return False
        if not bp.acquired and bp.binding_id in bindings:
            return False
    if not _knowledge_source_ok(action, world, bindings, binding_sources_by_id):
        return False
    return True
```

### 5.5 Update GraphContractSpec validation

**File:** `src/tau2/generators/depgraph/types.py`

In `GraphContractSpec.validate_contract()` (line 261), update the binding reference check
to use the new `BindingPredicateSpec.binding_id` instead of raw string lists:
```python
unknown_refs = (
    {bp.binding_id for bp in action.requires_bindings}
    | set(action.effects_bindings)
    | set(action.tool_arg_bindings.values())
) - binding_id_set
```

### 5.6 Update `_knowledge_source_ok()` in semantics.py

**File:** `src/tau2/generators/depgraph/semantics.py`

This function (lines 64-85) currently reads `action.requires_absent_bindings` indirectly
through `action.effects_bindings` and checks `binding_id in bindings`. Ensure it works
with the new `BindingPredicateSpec` — the core logic doesn't change since it operates on
`effects_bindings` (still a `list[str]`), but verify the `binding_id in bindings` check
still correctly reflects that knowledge-only actions shouldn't fire if the binding is
already acquired.

### 5.7 Nothing else changes

The sampler (`sampler.py`), solver (`solver.py`), and preflight (`preflight.py`) all
delegate to `is_action_enabled()` and `predicate_holds()`. They don't need changes.

---

## 6. Migration Step 2: Sync Rules Schema

### 6.1 New types in `types.py`

**File:** `src/tau2/generators/depgraph/types.py`

Add after `WorldEffectSpec`:

```python
class SyncEffectSpec(BaseModel):
    """One sync output: either copy from another path or set a literal."""
    path: str
    set: Optional[Any] = None          # literal value (mutually exclusive with from_path)
    from_path: Optional[str] = None    # copy current value from this path

    @model_validator(mode="after")
    def validate_sync_effect(self) -> "SyncEffectSpec":
        if not self.path.strip():
            raise ValueError("sync effect path cannot be empty")
        if self.set is None and self.from_path is None:
            raise ValueError("sync effect must have either 'set' or 'from_path'")
        if self.set is not None and self.from_path is not None:
            raise ValueError("sync effect cannot have both 'set' and 'from_path'")
        if self.from_path is not None and not self.from_path.strip():
            raise ValueError("from_path cannot be blank when provided")
        return self


class SyncRuleSpec(BaseModel):
    """Reactive rule that fires after every action, like sync_tools().

    If all requires_world predicates are met in the current world state,
    the effects_world are applied. Unconditional rules have empty requires_world.
    """
    rule_id: str
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)
    effects_world: list[SyncEffectSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sync_rule(self) -> "SyncRuleSpec":
        if not self.rule_id.strip():
            raise ValueError("sync rule rule_id cannot be empty")
        if not self.effects_world:
            raise ValueError(f"Sync rule '{self.rule_id}' must have at least one effect")
        return self
```

### 6.2 Add sync_rules to GraphContractSpec

**File:** `src/tau2/generators/depgraph/types.py`

Add to `GraphContractSpec` (after `actions`):
```python
class GraphContractSpec(BaseModel):
    version: int = 2
    context_slots: list[ContextSlotSpec] = Field(default_factory=list)
    projection_fields: list[str] = Field(default_factory=list)
    bindings: list[BindingSourceSpec] = Field(default_factory=list)
    actions: list[ActionContract] = Field(default_factory=list)
    sync_rules: list[SyncRuleSpec] = Field(default_factory=list)    # NEW
```

### 6.3 Validation in GraphContractSpec

Add to `validate_contract()`:
```python
# Validate sync rules
sync_rule_ids = [r.rule_id for r in self.sync_rules]
_check_unique(sync_rule_ids, label="sync_rules.rule_id")

projection_set = set(self.projection_fields)
for rule in self.sync_rules:
    for pred in rule.requires_world:
        if pred.path not in projection_set:
            raise ValueError(
                f"Sync rule '{rule.rule_id}' requires_world references "
                f"unknown projection path '{pred.path}'"
            )
    for effect in rule.effects_world:
        if effect.path not in projection_set:
            raise ValueError(
                f"Sync rule '{rule.rule_id}' effect writes to "
                f"unknown projection path '{effect.path}'"
            )
        if effect.from_path is not None and effect.from_path not in projection_set:
            raise ValueError(
                f"Sync rule '{rule.rule_id}' effect copies from "
                f"unknown projection path '{effect.from_path}'"
            )
```

### 6.4 What the contract YAML looks like

```yaml
sync_rules:
  # === Unconditional 1-1 projections (agent → user) ===
  - rule_id: project_hold_status
    requires_world: []
    effects_world:
      - path: user.view.display_hold_status
        from_path: agent.accounts[active_account].hold_status

  - rule_id: project_payment_token_status
    requires_world: []
    effects_world:
      - path: user.view.display_payment_token_status
        from_path: agent.accounts[active_account].payment_token_status

  # ... one rule per 1-1 projection

  # === Conditional causal bridge (user → agent) ===
  - rule_id: activate_charge_on_test
    requires_world:
      - op: eq
        path: user.physical.test_charge_state
        value: run
      - op: eq
        path: agent.accounts[active_account].hold_status
        value: cleared
      - op: eq
        path: agent.sessions[active_session].profile_state
        value: ready
      - op: eq
        path: agent.sessions[active_session].retry_state
        value: ready
      # ... all other prereqs from environment.py:107-123
    effects_world:
      - path: agent.sessions[active_session].charge_state
        set: active
```

---

## 7. Migration Step 3: BFS Integration

### 7.1 New function: `apply_sync_rules()` in semantics.py

**File:** `src/tau2/generators/depgraph/semantics.py`

```python
_MAX_SYNC_ITERATIONS = 10

def apply_sync_rules(
    sync_rules: list[SyncRuleSpec],
    world: dict[str, Any],
) -> dict[str, Any]:
    """Apply all eligible sync rules until fixed-point (no changes).

    Iterates up to _MAX_SYNC_ITERATIONS times. If not converged, raises
    ValueError indicating a cycle in sync rules (contract bug).
    """
    for iteration in range(_MAX_SYNC_ITERATIONS):
        changed = False
        for rule in sync_rules:
            if not all(predicate_holds(p, world) for p in rule.requires_world):
                continue
            for effect in rule.effects_world:
                if effect.from_path is not None:
                    new_val = world.get(effect.from_path)
                else:
                    new_val = effect.set
                if world.get(effect.path) != new_val:
                    world[effect.path] = new_val
                    changed = True
        if not changed:
            break
    else:
        raise ValueError(
            f"Sync rules did not converge after {_MAX_SYNC_ITERATIONS} iterations. "
            "Check for cycles in sync rule dependencies."
        )
    return world
```

### 7.2 Modify `apply_action()` in semantics.py

**File:** `src/tau2/generators/depgraph/semantics.py`

**Current** (lines 107-119):
```python
def apply_action(action, world, bindings):
    next_world = dict(world)
    for effect in action.effects_world:
        next_world[effect.path] = effect.set
    next_bindings = set(bindings)
    next_bindings.update(action.effects_bindings)
    return next_world, frozenset(next_bindings)
```

**New:**
```python
def apply_action(
    action: ActionContract,
    world: dict[str, Any],
    bindings: frozenset[str],
    *,
    sync_rules: list[SyncRuleSpec] | None = None,
    binding_specs: list[BindingSourceSpec] | None = None,
) -> tuple[dict[str, Any], frozenset[str]]:
    """Apply forward effects of one action, then sync rules, then binding invalidation."""
    next_world = dict(world)

    # Step 1: Apply action effects
    for effect in action.effects_world:
        next_world[effect.path] = effect.set

    # Step 2: Apply sync rules (fixed-point)
    if sync_rules:
        next_world = apply_sync_rules(sync_rules, next_world)

    # Step 3: Binding invalidation
    next_bindings = set(bindings)
    next_bindings.update(action.effects_bindings)
    if binding_specs:
        next_bindings = _invalidate_bindings(world, next_world, next_bindings, binding_specs)

    return next_world, frozenset(next_bindings)
```

(The `_invalidate_bindings` function is defined in Step 4 below.)

### 7.3 Update callers: sampler.py and solver.py

Both files call `apply_action()`. They need to pass `sync_rules` and `binding_specs`.

**File:** `src/tau2/generators/depgraph/sampler.py` (line 112)

**Current:**
```python
next_world, next_bindings = apply_action(action, node.world, node.bindings)
```

**New:**
```python
next_world, next_bindings = apply_action(
    action, node.world, node.bindings,
    sync_rules=contract.sync_rules,
    binding_specs=contract.bindings,
)
```

**File:** `src/tau2/generators/depgraph/solver.py` (line 108)

Same change — pass `sync_rules` and `binding_specs` from the contract/binding_sources.
Note: `find_plan()` receives `binding_sources` as a parameter (line 52) and `actions`
(line 48). It needs access to the full contract or at least the sync_rules. Either:
- Add `sync_rules` parameter to `find_plan()`
- Or pass the full contract

Recommended: add `sync_rules: list[SyncRuleSpec] | None = None` parameter to `find_plan()`.

---

## 8. Migration Step 4: Binding Invalidation

### 8.1 New function: `_invalidate_bindings()` in semantics.py

**File:** `src/tau2/generators/depgraph/semantics.py`

```python
def _invalidate_bindings(
    old_world: dict[str, Any],
    new_world: dict[str, Any],
    bindings: set[str],
    binding_specs: list[BindingSourceSpec],
) -> set[str]:
    """Remove bindings whose world_path was written to with a different value.

    After action effects + sync rules have been applied, compare old_world
    and new_world. For each acquired binding, if its world_path changed,
    the binding is invalidated (removed from the acquired set).
    """
    for spec in binding_specs:
        if spec.world_path is None:
            continue
        if spec.binding_id not in bindings:
            continue
        old_val = old_world.get(spec.world_path)
        new_val = new_world.get(spec.world_path)
        if old_val != new_val:
            bindings.discard(spec.binding_id)
    return bindings
```

### 8.2 How this solves the original bug

Consider the task `billing_partial_knowledge_d13_482`:

1. BFS state starts with `fault_code` not acquired (it's not a start binding for this seed).
2. Action `user_check_station_screen` fires → `effects_bindings: [fault_code]`. Binding
   acquired. `world_path` value is `"BH-101"`.
3. Agent fixes billing issues, calls `reprovision_billing`.
4. **`reprovision_billing` has `effects_world: [{path: ..., set: NONE}]`** on
   `agent.sessions[active_session].last_fault_code`.
5. After applying effects, `_invalidate_bindings()` sees that `last_fault_code` changed
   from `"BH-101"` to `"NONE"`. **Binding `fault_code` is invalidated.**
6. Now `reset_retry_path` has `requires_bindings: [{binding_id: fault_code, acquired: true}]`.
   The BFS sees the binding is gone. It must re-acquire via `user_check_station_screen`.
7. After sync rules run, the screen now shows `"RETRY-301"` (computed by projection rules
   from current agent state — but wait, we eliminated the cascade). Actually, with the new
   system, the user reads the retry status through a dedicated tool, not through the fault
   code cascade. The `fault_code` binding is re-acquired with whatever `last_fault_code` is
   now (after sync rules copy it). The evaluator expects the re-acquired value.

### 8.3 Binding invalidation in preflight

**File:** `src/tau2/generators/depgraph/preflight.py`

Add a check that no action simultaneously produces and invalidates the same binding:

```python
def _check_binding_self_invalidation(
    contract: GraphContractSpec,
) -> list[str]:
    """Warn if an action's effects_world overwrites a binding it just produced."""
    issues = []
    binding_paths = {
        spec.binding_id: spec.world_path
        for spec in contract.bindings
        if spec.world_path
    }
    for action in contract.actions:
        produced = set(action.effects_bindings)
        written_paths = {e.path for e in action.effects_world}
        for binding_id in produced:
            if binding_id in binding_paths and binding_paths[binding_id] in written_paths:
                issues.append(
                    f"Action '{action.action_id}' produces binding '{binding_id}' but "
                    f"also writes to its world_path '{binding_paths[binding_id]}' — "
                    f"the binding would be immediately invalidated"
                )
    return issues
```

Call this in `run_task_preflight()` alongside existing checks.

---

## 9. Migration Step 5: Validation and Authoring Guides

### 9.1 Runtime checks update

**File:** `src/tau2/generators/depgraph/runtime_checks.py`

Add sync rule validation in `check_contract_against_environment()`:

```python
# Validate sync rules reference valid projection paths
for rule in contract.sync_rules:
    for pred in rule.requires_world:
        if pred.path not in projection_set:
            issues.append(
                f"Sync rule '{rule.rule_id}' references unknown path '{pred.path}'"
            )
    for effect in rule.effects_world:
        if effect.path not in projection_set:
            issues.append(
                f"Sync rule '{rule.rule_id}' writes to unknown path '{effect.path}'"
            )
        if effect.from_path and effect.from_path not in projection_set:
            issues.append(
                f"Sync rule '{rule.rule_id}' copies from unknown path '{effect.from_path}'"
            )
```

### 9.2 Authoring guide updates

**File:** `docs/prompts/depgraph/01-domain-scope.md`

Add to requirements (after line 20):
> Fields with `update_source: sync` must name the single agent-side field they mirror.
> Sync is either a 1-1 copy or a conditional with explicit prereqs and effects. If a
> user-visible value depends on multiple agent fields in a way that can't be expressed as
> prereqs + effects, it must be modeled as a separate tool-backed action, not a sync rule.

**File:** `docs/prompts/depgraph/02-graph-contract.md`

Add new requirement (after line 39):
> 13. Define `sync_rules` in the contract for every cross-DB propagation:
>     - 1-1 projections: `{from_path: agent.X, path: user.Y}`, no prereqs
>     - Conditional bridges: prereqs + literal set effects
>     - No computed cascades. If you can't express it as prereqs + effects, model it as an
>       action in the contract.
>     - sync_tools() must implement exactly what sync_rules declares.

**File:** `docs/prompts/depgraph/08-runtime-environment-and-sync.md`

Replace lines 55-61 with:
> 1. `sync_tools()` must implement exactly two things:
>    a. **Sync rules** declared in `graph_contract.yaml` — 1-1 copies and conditional bridges
>    b. **Nothing else** — no computed values, no priority cascades, no derived state
> 2. For each `sync_rule` in the contract:
>    - If `requires_world` is empty: unconditional copy (always runs)
>    - If `requires_world` is non-empty: conditional bridge (only runs when prereqs met)
> 3. A verifier will check that `sync_tools()` implements exactly the declared rules.
> 4. Keep `sync_tools()` idempotent: repeated calls should not create new deltas.

### 9.3 Checklist update

**File:** `docs/prompts/depgraph/CHECKLIST.md`

Add:
> 5. All sync_rules reference valid projection_fields paths.
> 6. sync_tools() implements exactly the declared sync_rules — no extra logic.
> 7. No binding world_path is overwritten by an action that doesn't intend to invalidate it.
> 8. No computed/cascaded projections in sync_tools().

---

## 10. Migration Step 6: EV Domain Migration

### 10.1 Contract changes

**File:** `data/tau2/domains/ev_charging_support/graph_contract.yaml`

**a) Replace all `requires_absent_world` with `op: neq`:**

Example — current:
```yaml
  - action_id: user_inspect_cable
    requires_world: []
    requires_absent_world:
      - op: eq
        path: user.physical.cable_inspection_state
        value: checked_ok
```

New:
```yaml
  - action_id: user_inspect_cable
    requires_world:
      - op: neq
        path: user.physical.cable_inspection_state
        value: checked_ok
```

**b) Replace all `requires_absent_bindings` with binding predicates:**

Example — current:
```yaml
  - action_id: user_check_station_screen
    requires_bindings: []
    requires_absent_bindings:
      - fault_code
```

New:
```yaml
  - action_id: user_check_station_screen
    requires_bindings:
      - binding_id: fault_code
        acquired: false
```

**c) Add `sync_rules` section:**

Port lines 128-139 of `environment.py` (1-1 projections) and lines 107-125 (causal bridge)
as sync rules. The 12 unconditional projections become 12 rules with empty `requires_world`.
The test_charge bridge becomes 1 rule with ~15 prereqs.

**d) Remove `display_fault_code` from projections.**

The fault code cascade (environment.py:141-193) is NOT ported as a sync rule. It's
replaced by per-subsystem status fields that users read through separate tools. Add
`display_fault_code` removal to the user_data_model cleanup.

**e) Projection fields:** Add the `user.view.display_*` fields to `projection_fields`
so the sync rules can reference them.

### 10.2 Environment changes

**File:** `src/tau2/domains/ev_charging_support/environment.py`

Rewrite `sync_tools()` to implement only what the contract's `sync_rules` declare:
- Lines 128-139 (1-1 projections): keep as-is, these are the declared sync rules
- Lines 107-125 (causal bridge): keep as-is, this is the declared conditional bridge
- Lines 141-193 (fault code cascade): **DELETE ENTIRELY**

### 10.3 Tool changes

**File:** `src/tau2/domains/ev_charging_support/tools.py`

The `_fault_code_guard()` (line 95-108) currently accepts `display_fault_code` as a
fallback. With the cascade removed:
- `_fault_code_guard()` should only check `session.last_fault_code`
- Or better: accept the `fault_code` parameter as-is since it comes from a binding that
  the BFS has already validated

Consider whether `_do_reprovision()` should still set `last_fault_code = "NONE"`. If it
does, binding invalidation will require re-acquisition. If it doesn't, the original fault
code stays valid and downstream tools can use it. This is a domain design choice — either
way the system now handles it correctly.

### 10.4 Re-run pipeline

After making these changes:
```bash
# 1. Run sampler
uv run python -m tau2.generators.depgraph.run_sampler \
  --graph-contract data/tau2/domains/ev_charging_support/graph_contract.yaml \
  --sampling-request data/tau2/domains/ev_charging_support/sampling_request.yaml \
  --out-task-specs data/tau2/domains/ev_charging_support/task_specs.sampled.yaml

# 2. Context bindings
uv run python -m tau2.generators.depgraph.run_context_bindings \
  --graph-contract data/tau2/domains/ev_charging_support/graph_contract.yaml \
  --task-specs data/tau2/domains/ev_charging_support/task_specs.sampled.yaml \
  --db data/tau2/domains/ev_charging_support/db.json \
  --out data/tau2/domains/ev_charging_support/task_context_bindings.yaml

# 3. Scaffold
uv run python -m tau2.generators.depgraph.run_runtime_scaffold \
  --graph-contract data/tau2/domains/ev_charging_support/graph_contract.yaml \
  --task-specs data/tau2/domains/ev_charging_support/task_specs.sampled.yaml \
  --personas data/tau2/domains/ev_charging_support/personas.yaml \
  --runtime-defaults data/tau2/domains/ev_charging_support/runtime_defaults.yaml \
  --context-bindings data/tau2/domains/ev_charging_support/task_context_bindings.yaml \
  --out-runtime data/tau2/domains/ev_charging_support/task_specs.runtime.scaffold.yaml \
  --out-briefs data/tau2/domains/ev_charging_support/task_narrative_briefs.yaml

# 4. Init runtime (then author 3 narrative fields per task)
uv run python -m tau2.generators.depgraph.run_runtime_init \
  --scaffold data/tau2/domains/ev_charging_support/task_specs.runtime.scaffold.yaml \
  --out data/tau2/domains/ev_charging_support/task_specs.runtime.yaml --force

# 5. Author runtime fields: reason_for_call, known_info, ticket

# 6. Surface check
uv run python -m tau2.generators.depgraph.run_runtime_surface_check \
  --scaffold data/tau2/domains/ev_charging_support/task_specs.runtime.scaffold.yaml \
  --runtime data/tau2/domains/ev_charging_support/task_specs.runtime.yaml

# 7. Narrative check
uv run python -m tau2.generators.depgraph.run_runtime_narrative_check \
  --graph-contract data/tau2/domains/ev_charging_support/graph_contract.yaml \
  --runtime data/tau2/domains/ev_charging_support/task_specs.runtime.yaml

# 8. Stop gate inject
uv run python -m tau2.generators.depgraph.run_stop_gate_inject \
  --runtime data/tau2/domains/ev_charging_support/task_specs.runtime.yaml \
  --stop-gate-map data/tau2/domains/ev_charging_support/stop_gate_map.yaml

# 9. Preflight
uv run python -m tau2.generators.depgraph.run_preflight \
  --graph-contract data/tau2/domains/ev_charging_support/graph_contract.yaml \
  --task-specs data/tau2/domains/ev_charging_support/task_specs.runtime.yaml \
  --strict-tool-coverage

# 10. Compile
uv run python -m tau2.generators.depgraph.run_compile \
  --graph-contract data/tau2/domains/ev_charging_support/graph_contract.yaml \
  --task-specs data/tau2/domains/ev_charging_support/task_specs.runtime.yaml \
  --out data/tau2/domains/ev_charging_support/tasks.depgraph.json
```

### 10.5 Verification

After pipeline completes:
1. All preflight checks pass (SAT solvable, ablation confirms necessity)
2. Tasks involving reprovision now include binding re-acquisition steps (new edges)
3. No tasks reference `display_fault_code` or the cascade logic
4. Surface check and narrative check pass
5. Run 2-3 tasks in simulation to confirm the evaluator no longer fails on stale binding
   values

---

## 11. File Reference Index

### Files to modify (engine):

| File | Changes |
|------|---------|
| `src/tau2/generators/depgraph/types.py` | Expand `WorldPredicateSpec.op`, add `BindingPredicateSpec`, add `SyncEffectSpec`, add `SyncRuleSpec`, add `sync_rules` to `GraphContractSpec`, remove `requires_absent_*` fields from `ActionContract` |
| `src/tau2/generators/depgraph/semantics.py` | Expand `predicate_holds()`, simplify `is_action_enabled()`, add `apply_sync_rules()`, add `_invalidate_bindings()`, modify `apply_action()` signature |
| `src/tau2/generators/depgraph/sampler.py` | Pass `sync_rules` + `binding_specs` to `apply_action()` |
| `src/tau2/generators/depgraph/solver.py` | Add `sync_rules` param to `find_plan()`, pass to `apply_action()` |
| `src/tau2/generators/depgraph/preflight.py` | Add `_check_binding_self_invalidation()`, pass sync_rules through |
| `src/tau2/generators/depgraph/runtime_checks.py` | Add sync rule validation |

### Files to modify (EV domain):

| File | Changes |
|------|---------|
| `data/tau2/domains/ev_charging_support/graph_contract.yaml` | Replace `requires_absent_*` with unified predicates, add `sync_rules` section, remove cascade-dependent logic |
| `src/tau2/domains/ev_charging_support/environment.py` | Rewrite `sync_tools()` to match declared sync rules only, delete cascade |
| `src/tau2/domains/ev_charging_support/tools.py` | Simplify `_fault_code_guard()`, review `_do_reprovision()` |
| `src/tau2/domains/ev_charging_support/user_data_model.py` | Remove `display_fault_code` and related cascade fields if no longer needed |

### Files to modify (guides):

| File | Changes |
|------|---------|
| `docs/prompts/depgraph/01-domain-scope.md` | Constrain `update_source: sync` to 1-1 or conditional |
| `docs/prompts/depgraph/02-graph-contract.md` | Add sync_rules requirement, ban cascades |
| `docs/prompts/depgraph/08-runtime-environment-and-sync.md` | Restrict sync_tools to declared rules only |
| `docs/prompts/depgraph/CHECKLIST.md` | Add sync rule checks |

### Files that need NO changes:

| File | Why |
|------|-----|
| `src/tau2/generators/depgraph/loaders.py` | Uses Pydantic — auto-handles new fields |
| `src/tau2/generators/depgraph/run_sampler.py` | CLI wrapper, delegates to sampler |
| `src/tau2/generators/depgraph/run_runtime_scaffold.py` | CLI wrapper |
| `src/tau2/environment/environment.py` | Base class unchanged; domains override sync_tools() |
| `src/tau2/evaluator/evaluator.py` | Evaluation logic unchanged |
| `src/tau2/evaluator/evaluator_action.py` | Action matching unchanged |

### Key design document:

| File | Role |
|------|------|
| `design/tau2/dependency_graph_domain_plan.md` | Source of truth for state model — update sync_tools section |
