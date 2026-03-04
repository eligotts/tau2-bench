# tau2-bench System Walkthrough

## Layer 1: The tau2 Engine

The engine is the runtime that runs conversations between an AI agent and a simulated user. It has four core abstractions:

**Environment** (`src/tau2/environment/environment.py`) — The world the conversation happens in. It holds:
- A `domain_name` (e.g. "library")
- A `policy` string (the agent's instruction manual)
- An agent `tools` toolkit and a `user_tools` toolkit
- A `sync_tools()` method that projects agent-side DB state to user-visible summaries

The key runtime loop: after every tool call during evaluation, `sync_tools()` runs automatically. This means the user's view of the world stays in sync with the agent's mutations.

**ToolKitBase** (`src/tau2/environment/toolkit.py`) — Base class for toolkits. Methods decorated with `@is_tool(ToolType.READ)` or `@is_tool(ToolType.WRITE)` or `@is_tool(ToolType.GENERIC)` become LLM-callable tools. Non-decorated methods are internal helpers (setup functions, assertion functions). Each toolkit holds a reference to a `DB` object — a Pydantic model with `load()` and `dump()` methods.

**DB** (`src/tau2/environment/db.py`) — Pydantic `BaseModel` subclass that serves as the state store. Each domain defines its own DB schema (e.g. `LibraryDB` with patrons, books, checkouts, holds, fines, events, interlibrary_loans). The DB has a `load(path)` classmethod to read from JSON and a `dump(path)` to write.

**Task** (`src/tau2/data_model/tasks.py`) — The unit of evaluation. A task has:
- `id` — unique identifier
- `ticket` — what the agent sees (the support ticket)
- `user_scenario` — what the user simulator gets:
  - `persona` — behavioral instructions (cooperative, anxious, etc.)
  - `instructions.known_info` — facts the user knows about their situation
  - `instructions.reason_for_call` — why they're calling
  - `instructions.task_instructions` — directives to the simulator (e.g. "when the agent tells you to make a payment, use the make_fine_payment tool")
- `initial_state.initialization_actions` — list of `EnvFunctionCall`s that run before the conversation starts, injecting faults into the DB
- `evaluation_criteria` — what we check after the conversation:
  - `actions` — the expected tool calls (both agent and user)
  - `env_assertions` — post-condition checks (boolean functions on the DB)
  - `reward_basis` — which evaluators to use: `ACTION`, `ENV_ASSERTION`, `COMMUNICATE`

## Layer 2: How Evaluation Works

After a conversation runs, the evaluator checks two things:

1. **ACTION score** — Did the agent (and user) call the right tools? Each expected `Action` is compared against the conversation transcript. `compare_args` controls strictness:
   - `None` = all arguments must match exactly
   - `["checkout_id"]` = only check that specific arg
   - `[]` = name-only match (just called the tool)

2. **ENV_ASSERTION score** — Is the post-state correct? Each `EnvAssertion` is a method on the toolkit that returns `bool`. It's called with resolved arguments and compared to `assert_value` (default `True`). Example: `assert_checkout_due_date(checkout_id="CK001", expected_date="2025-03-15")` checks `db.checkouts["CK001"].due_date == "2025-03-15"`.

The final reward is the average across all reward_basis components.

## Layer 3: What a Domain Author Creates

For each domain, you author 10 files:

| File | Purpose |
|------|---------|
| `data_model.py` | Pydantic models for entities (Patron, Book, Checkout, Hold, Fine, etc.) and the DB class |
| `user_data_model.py` | Pydantic model for user-side state (summary projections, confirmation flags) |
| `db.json` | Sample data — 15-20 entities with realistic relationships |
| `user_db.json` | User DB template (identity fields null until set at runtime) |
| `policy.md` | Natural language rules the agent must follow |
| `tools.py` | Agent toolkit — READ tools (lookup), WRITE tools (mutations), GENERIC tools (transfer_to_human), plus non-decorated helpers: `set_*` (init functions that break things) and `assert_*` (post-condition checks) |
| `user_tools.py` | User toolkit — tools the simulated user can call (confirm_hold_pickup, make_fine_payment, etc.) |
| `utils.py` | Path constants for data files |
| `environment.py` | Domain-specific Environment subclass with `sync_tools()` implementation |
| `scenarios.py` | The **RecipeBook** — declarative fault definitions that the engine expands into thousands of tasks |

## Layer 4: The Recipe Engine (Declarative Task Generation)

This is the core innovation — instead of writing tasks by hand, you declare **what can go wrong** and the engine generates every valid combination.

### Task Archetypes

The engine supports four distinct task archetypes, controlled by three primitives on atoms and layers:

| Archetype | Pattern | Key Primitives |
|-----------|---------|----------------|
| **A: Sequential Diagnostic** | Fix blocker → unlock downstream faults | `gate_tier` across layers |
| **B: Branching Troubleshooter** | User diagnoses → user fixes → agent confirms | `phase` + `step_type="diagnostic"` |
| **C: Transaction Processor** | Agent fixes DB state, user confirms | Default (no special primitives) |
| **D: Triage/Classification** | Agent classifies → agent routes | `phase` for sequential agent actions |

### Building Blocks (bottom-up)

**FaultAtom** — The smallest unit. One `(init, fix, check)` triple with ordering and role metadata:
```python
FaultAtom(
    init = InitCall("assistant", "set_checkout_due_date",
                    {"checkout_id": "{checkout_id}", "due_date": "2024-01-01"}),
    fix  = ActionSpec("renew_checkout",
                      {"checkout_id": "{checkout_id}", "new_due_date": "{date}"}),
    check = AssertionSpec("assert_checkout_due_date",
                          {"checkout_id": "{checkout_id}", "expected_date": "{date}"}),
    phase = 0,             # execution order within layer (lower runs first)
    step_type = "fix",     # "fix" | "diagnostic" | "confirm"
)
```

The structural bundling means init/fix/check can never disagree — they're authored as one unit.

**Atom patterns:**
- `init + fix + check` — primary fault (break → fix → verify)
- `None + fix + check` — consequence action (no separate init, but needed to complete the fix)
- `None + fix + None` — terminal follow-up (e.g. reboot, no independent assertion)

**Ordering fields on FaultAtom:**
- **`phase: int = 0`** — Execution order *within* a layer. Lower phases run first. Within the same phase, requestor is a tiebreaker (user=0, agent=1). Phases enable multi-step sequences: phase 0 = diagnose, phase 1 = fix, phase 2 = verify.
- **`step_type: str = "fix"`** — Declares the atom's role:
  - `"fix"` — state-changing WRITE action (default)
  - `"diagnostic"` — information-gathering READ action. Part of the golden path but doesn't change DB state. Verification skips no-op checks for diagnostic atoms.
  - `"confirm"` — user acknowledgment action that records acceptance.

**FaultLayer** — A single injectable fault, composed of one or more atoms. Example: "channel congestion" has two atoms at different phases:
1. Agent optimizes channel (phase 0, step_type="fix")
2. User switches WiFi band (phase 1, step_type="fix")

A layer also has:
- `known_info_fragment` — what the user says about this fault ("my WiFi keeps dropping")
- `completion_fragment` — user-observable half-sentence describing "fixed" state ("your WiFi channel has been optimized")
- `predicate_field` — entity filter (only apply if `entity.has_checkout == True`)
- `resource_scope` — conflict detection key (e.g. `"checkout:{checkout_id}"`)
- `unfixable=True` — the fault can't be resolved, agent must transfer to human
- **`gate_tier: int = 0`** — Execution order *across* composed layers. All tier-0 actions complete before tier-1 actions begin.

**FaultLayerGroup** — Mutually exclusive layers. You pick 0 or 1 from each group. Example: "checkout_issues" group contains `overdue_checkout` and `lost_book_record` — you can't have both simultaneously. Each group has a `resolution_category` semantic tag (e.g. `"account"`, `"connection"`, `"billing"`) used by `verify_resolution_instruction()` to check coverage.

**FaultLayerConfig** — The cartesian product engine. It takes:
- `entity_query` — function returning entities from the DB
- `groups` — list of FaultLayerGroups
- `base_init_calls` — normalization that runs for every task (set user identity, etc.)
- `base_known_info_template` — template with `{fault_descriptions}` placeholder
- `min_faults` / `max_faults` — bounds on simultaneous faults
- `tool_grounding_block` — domain-level constant appended to user task instructions. Two patterns: **verification loop** (`"After each step, use your check_my_connection tool to verify progress"`) when a composite verification tool exists, or **grounding-only** (`"Ground your responses on tool call results"`) otherwise.

The engine then generates every valid combination: for each entity × each subset of fault layers (one per group, respecting min/max), produce a task spec.

### Action Ordering: `(gate_tier, phase, requestor_priority)` — Stable Sort

The engine collects all atom actions with ordering metadata, then stable-sorts:

```python
entries = []
for layer in sorted(active_layers, key=lambda l: l.gate_tier):
    for atom in layer.atoms:
        entries.append((layer.gate_tier, atom.phase,
                        0 if atom.fix.requestor == "user" else 1,
                        atom.fix))

# Base actions at synthetic final tiers
max_tier = max((l.gate_tier for l in active_layers), default=0)
for aspec in flc.base_actions:
    entries.append((max_tier + 1, 0, 1, aspec))
for aspec in flc.base_user_actions:
    entries.append((max_tier + 2, 0, 0, aspec))

entries.sort(key=lambda x: (x[0], x[1], x[2]))
```

**Requestor is only a tiebreaker**, not a primary sort dimension. Phase takes precedence. Authors can freely interleave agent and user actions by assigning different phases.

### Completion Fragment System

Each `FaultLayer` has a `completion_fragment` — a half-sentence describing the user-observable "fixed" state. The framework composes these into `user_task_instructions` automatically:

```
"You will consider your issues resolved when <fragment_1> and <fragment_2>."
```

However, when `RecipeBook.resolution_instruction` is set, it **replaces** the AND-chained fragments with a single stopping criterion:

```
"You will consider your issues resolved when <resolution_instruction>."
```

This prevents the user sim from being overwhelmed by long multi-fault fragment lists. Two patterns for `resolution_instruction`:
- **Tool-referencing** (when a composite verification tool exists): `"your check_my_connection tool shows 'All systems working normally'"` — gives the user sim a concrete, tool-grounded stop signal.
- **Broad outcome** (otherwise): `"your vehicle service issues have been resolved"` — less precise but still better than AND-chaining 5+ fragments.

Rules:
- **`completion_fragment` is required on ALL layers** — fixable AND unfixable — even when `resolution_instruction` is set (fragments are still used for single-fault tasks and validation)
- **Unfixable layers use impossible-goal pattern**: describe what "fixed" would look like, NOT the transfer outcome. The user sim doesn't know the issue is unfixable — the agent must figure that out.
- Without `completion_fragment` on unfixable layers, user sim gets generic fallback → infinite conversation loops
- **`resolution_category`** on `FaultLayerGroup` is required when `resolution_instruction` is set — it's a semantic tag used by `verify_resolution_instruction()` to ensure all fault categories are covered by the instruction

### How Dependencies Work

Dependencies between fault layers are managed through several mechanisms:

1. **Gate tiers** — Layers at different `gate_tier` values execute sequentially. Tier-0 actions complete before tier-1 actions begin. This creates Archetype A progressive-disclosure patterns.

2. **Resource scope validation** — Layers in *different* groups that modify the same resource at the *same* gate_tier are flagged as an error at generation time. Layers at different tiers are allowed to share scopes (they execute sequentially).

3. **Predicate filtering** — A layer's `predicate_field` controls which entities it applies to. If an entity doesn't have a checkout, checkout fault layers are skipped for that entity.

4. **Phase ordering** — Within a layer, atoms at lower phases run before atoms at higher phases. This enables diagnostic-before-fix and fix-before-confirm sequences.

5. **Deduplication** — When multiple layers produce identical actions (same tool, same requestor, same resolved args), only one copy is kept. Same for assertions. **Caveat**: dedup collapses repeated identical actions — Archetype B check-fix-check patterns need different args or tool names to avoid silent destruction.

### Sampling Strategies

When the cartesian product is too large, two sampling strategies are available:
- `max_tasks_per_bin` — Uniform: group by (entity, fault_count), cap N per bin
- `max_total_tasks` — Proportional: preserve the natural C(N,K) bell-curve distribution, allocate budget proportionally to each fault-count tier

### Unfixable (Transfer) Tasks

When any layer in a combo has `unfixable=True`, the entire task becomes a transfer task:
- The only expected action is `transfer_to_human(summary="", compare_args=[])`
- **Preservation assertions** verify the agent didn't modify the injected state (e.g. `assert_checkout_status(checkout_id, "overdue")`)
- Init still runs (to inject the unfixable condition)
- Gate tiers are irrelevant — unfixable collapses everything to transfer

### The Generation Flow

```
RecipeBook(fault_layer_configs=[...], resolution_instruction="...")
  .resolution_instruction → optional single stopping criterion (replaces AND-chained fragments)
  → for each FaultLayerConfig:
      1. Query entities from DB
      2. Validate layer structure (atoms, step_types, unfixable rules)
      3. Validate resource scopes (no cross-group conflicts at same tier)
      4. Cartesian product: entity × group₁ × group₂ × ... × groupₙ
      5. Filter by (min_faults ≤ active_count ≤ max_faults)
      6. Optional sampling
      7. For each (entity, active_layers):
         - Sort layers by gate_tier
         - Collect all atom actions with (gate_tier, phase, requestor) metadata
         - Stable sort by (gate_tier, phase, requestor_priority)
         - Resolve {field} templates against entity
         - Dedup actions and assertions
         - Compose user_task_instructions from completion_fragments
         - Assign tier from fault count
         → GeneratedTaskSpec
  → _spec_to_task: attach persona, user_template, format as Task JSON
```

### Personas

Every task spec produces one task per persona. Domain authors define 2-4 personas with different interaction styles (e.g., friendly, frustrated, verbose, terse). The total task count is `specs × N_personas`.

## Layer 5: Verification Pipeline

After tasks are generated, they pass through a three-phase verification:

### Phase A.0: Pre-Generation Authoring Checks (25 checks, `src/tau2/generators/verify_authoring.py`)

Structural checks on authored definitions BEFORE task generation:

| # | Check | Type | What it catches |
|---|-------|------|-----------------|
| 1 | init_func_exists | Static | Init function not found on toolkit |
| 2 | fix_tool_exists | Static | Fix tool not found on toolkit |
| 3 | assertion_func_exists | Static | Assertion function not found on toolkit |
| 4 | template_vars_valid | Static | Unresolvable {field} references in args |
| 5 | predicate_fields_exist | Static | Predicate field not in entity |
| 6 | resource_scope_resolves | Static | Resource scope template won't resolve |
| 7 | set_assert_coverage | Static | set_X exists without matching assert_X |
| 8 | requestor_toolkit_match | Static | User action on agent toolkit or vice versa |
| 9 | fix_tool_is_write | Static | Agent fix action uses READ tool (skips diagnostic atoms) |
| 10 | known_info_fragment_templates | Static | Unresolvable template vars in text fields |
| 11 | assertion_density (DI-4) | Static | <40% of fixable layers have 2+ assertions |
| 12 | user_tool_diversity (DI-5) | Static | <3 distinct user WRITE tools |
| 13 | action_density (DI-6) | Static | Median actions per task < 6 |
| 14a | gate_tier_consistency | Static | gate_tier > 0 with no lower-tier layer in another group |
| 14b | phase_monotonicity | Static | Non-increasing phases within a layer's atoms |
| 14c | step_type_valid | Static | Invalid step_type value |
| 14d | diagnostic_is_read | Static | Diagnostic atom uses non-READ tool |
| 15 | dedup_collision | Static | Identical actions at different phases (destroyed by dedup) |
| 16 | diagnostic_has_no_init | Static | Diagnostic atom has init calls |
| 17 | confirm_has_no_init | Static | Confirm atom has init calls |
| 18 | legacy_atoms_collision | Static | Layer has both atoms and legacy flat lists |
| 19 | all_diagnostic_layer | Static | Fixable layer with no fix atoms |
| 20 | confirm_without_fix | Static | Confirm atoms but no fix atoms |
| 21 | unfixable_gate_tier | Static | Unfixable layer with gate_tier > 0 |
| 22 | phase_gaps | Static | Non-consecutive phases within a layer |
| 23 | duplicate_phase_requestor | Static | Multiple fix atoms at same (phase, requestor) |
| 24 | gate_tier_gaps | Static | Non-consecutive gate_tiers across config |
| 25 | diagnostic_only_at_nonzero_tier | Static | Read-only layer at tier > 0 with no downstream fix |

Plus: cross-layer confirmation consistency check and completion_fragment validation.

### Phase A.5: Per-Atom Verification (`verify_fault_atoms`)

Before full task verification, each atom is tested in isolation:
1. Run base init + atom init → verify atom check **FAILS** (fault was injected)
2. Run base init + atom init + atom fix + sync → verify atom check **PASSES** (fix works)

This catches broken init→fix→check chains at O(atoms × sample_size) cost instead of O(tasks).

### Phase A: Post-Generation Code Checks (11 checks, `src/tau2/generators/verify.py`)

| # | Check | Type | What it catches |
|---|-------|------|-----------------|
| 1 | Reward basis | Static | Invalid reward types, mismatched compare_args |
| 2 | Tool schemas | Static | Missing tools, invalid arg names, missing required params, Any-typed params |
| 3 | Argument reachability | Runtime | Action args not discoverable from ticket + READ tools |
| 4 | Golden path | Runtime | Fix actions don't actually fix the fault (run init → fix → check assertions) |
| 5 | User action feasibility | Static | Missing task_instructions, conditional user actions, undiscoverable user args |
| 6 | Policy alignment | Static | Policy doesn't instruct agent to tell user to perform user actions |
| 7 | User action redundancy | Runtime | Assertions pass without user actions (skips READ diagnostic tools) |
| 8 | Action state change | Runtime | No-op actions that don't modify DB state |
| 9 | Action necessity | Runtime | Redundant actions — all assertions pass without the action |
| 10 | Assertion robustness | Runtime | Assertions fail on LLM format variants (e.g. `["fiction"]` vs `"fiction"`) |
| 11 | Assertion value discoverability | Static | Assertion expected values not in user context or action args |

### Phase B: LLM-Based Semantic Checks (19 checks)

A subset of tasks is sent to an LLM reviewer that checks:

| # | Check | What it catches |
|---|-------|-----------------|
| 1 | Set/Assert semantic correspondence | set_X breaks field A but assert_X checks field B |
| 2 | Policy-scenario alignment | Expected actions don't match policy prescriptions |
| 3 | Known-info fragment clarity | Ambiguous user description, can't tell which resource is affected |
| 4 | Init state coherence | Stale fields after partial DB mutation |
| 5 | Multi-atom logical sequence | Atom ordering doesn't form natural progression |
| 6 | sync_tools completeness | Fault changes field that sync_tools doesn't project |
| 7 | DB data quality | Invalid FK relationships, insufficient entities |
| 8 | Unfixable layer design | Missing preservation assertions, wrong transfer conditions |
| 9 | User tool realism | User tools don't match what real user would do |
| 10 | Tool precondition safety | sync_tools or user tools invalidate agent tool preconditions |
| 11 | DI-1 diagnostic disambiguation | >70% of layers have unique fix tools (too easy) |
| 12 | DI-2 value computation | Zero fix actions require agent to compute/derive a value |
| 13 | DI-3 ordering dependency | All faults completely independent (no ordering constraints) |
| 14 | User action arg / assertion mismatch | compare_args=[] but assertion checks specific arg value |
| 15 | User tool input validation | User tool blindly stores arbitrary ID without validation |
| 16 | Policy → confirmation routing ambiguity | Agent tool maps to multiple user confirmations |
| 17 | Gate tier semantic justification | Gating is artificial, not justified by domain logic |
| 18 | Diagnostic atom purpose validation | Diagnostic reads info already in known_info or never used |
| 19 | Phase coherence with domain workflow | Phase assignments don't reflect real workflow dependencies |

## Layer 6: Domain Generation (Claude Code Skills Workflow)

New domains are authored via a Claude Code skill: `/generate-domain <concept>`. Claude Code itself is the LLM — it reads instruction files, writes domain files directly, runs validation CLIs, and self-corrects naturally.

### The Skill

The orchestrator skill at `.claude/skills/generate-domain/SKILL.md` walks Claude through all 12 steps:

```
/generate-domain hotel_resort
       │
       ▼
  Step 0: scaffold_domain CLI         ← Creates dirs, utils.py, __init__.py
  Steps 1-10: Per-step instruction    ← Claude reads docs/skills/<NN>.md,
               files                     reads auto_repair reference files,
                                         writes the domain file
       │
       └── After each: validate_domain CLI  ← Claude runs to check its work,
                                               fixes errors, re-validates
  Step 10.5: Exhaustive audit          ← Claude reads all files + 9-audit
                                         checklist, traces every chain
  Step 11: generate_tasks CLI          ← Runs create_tasks(verify=True)
  Step 12: finalize_domain CLI         ← Saves tasks.json, updates registry
```

### Instruction Files

Each of the 10 domain files has a corresponding instruction file in `docs/skills/`:

| File | Instructions |
|------|-------------|
| `docs/skills/00-archetype.md` | Classify domain archetype (A/B/C/D) and plan primitive usage |
| `docs/skills/01-domain-spec.md` | Design the domain's entity/tool/fault structure as JSON |
| `docs/skills/02-data-model.md` | Pydantic models for entities and the DB class |
| `docs/skills/03-user-data-model.md` | User-side state model with default values |
| `docs/skills/04-db-json.md` | Sample data with realistic entity relationships |
| `docs/skills/05-user-db-json.md` | User DB template with null identity fields |
| `docs/skills/06-policy.md` | Natural language agent rules mentioning tool names |
| `docs/skills/07-tools.md` | Agent toolkit with READ/WRITE/GENERIC tools + helpers |
| `docs/skills/08-user-tools.md` | User toolkit with confirmation/payment/acknowledgment tools |
| `docs/skills/09-environment.md` | Environment subclass with sync_tools() |
| `docs/skills/10-scenarios.md` | RecipeBook with FaultLayerConfigs (largest step) |
| `docs/skills/11-llm-review.md` | 9-audit exhaustive checklist |

Each instruction file contains the specific requirements, gotchas, and constraints for that step. The auto_repair domain (`src/tau2/domains/auto_repair/`) serves as the reference exemplar that Claude reads alongside each instruction file. It demonstrates information-hiding READ tools, the agent→user tool chain (policy naming user tools explicitly), and 9 fault groups with progressive discovery.

### CLI Tools

Four CLI scripts support the skill workflow:

| CLI | Purpose |
|-----|---------|
| `python -m tau2.generators.scaffold_domain <name>` | Creates directories, `__init__.py`, `utils.py` |
| `python -m tau2.generators.validate_domain <name> [--step <step>]` | Runs structural validation (syntax, imports, class hierarchy, DB loading, tool counts, etc.) |
| `python -m tau2.generators.generate_tasks <name> [--save]` | Calls `create_tasks(verify=True)`, optionally saves `tasks.json` |
| `python -m tau2.generators.finalize_domain <name>` | Updates `src/tau2/registry.py` with new domain imports and registration |

### The Reference Domain

The `docs/domain-authoring-guide.md` (1700+ lines) is the authoritative design guide that Claude reads first. It covers entity design, tool patterns, fault layer architecture, archetype selection, sync_tools gotchas, user action feasibility rules, and difficulty calibration. The auto_repair domain is the canonical reference implementation — it demonstrates information-hiding READ tools, the agent→user tool chain, and 9 fault groups with progressive discovery.

### Full Generation Flow

```python
# What Claude Code does via the skill:
# 1. Read authoring guide + classify archetype
# 2. Scaffold directories
# 3. For each of 10 files:
#    a. Read instruction file + reference file
#    b. Write the domain file
#    c. Run validate_domain --step <step>
#    d. If validation fails, read error, fix, re-validate
# 4. Exhaustive 9-audit review
# 5. generate_tasks --save (runs verify_authoring + verify_fault_atoms + verify_tasks)
# 6. finalize_domain (updates registry)

# What the deterministic code does:
create_tasks(verify=True, save=True)
  1. verify_authoring()       # 25 structural checks on authored definitions
  2. verify_fault_atoms()     # per-atom golden path
  3. generate_recipe_tasks()  # cartesian product → Task objects
  4. verify_tasks()           # 11 code checks on every generated task
  5. task.dump()              # save tasks.json
```

## Design Principle

The key design principle throughout: **structural correspondence prevents disagreement**. Atoms bundle init/fix/check so they can't diverge. Templates resolve from a single entity dict so IDs can't mismatch. Resource scopes prevent cross-group conflicts. Phase and gate_tier encode ordering dependencies structurally rather than relying on implicit conventions. And 25+11+19 verification checks catch anything the structural guarantees miss.
