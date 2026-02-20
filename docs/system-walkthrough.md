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

### Building Blocks (bottom-up)

**FaultAtom** — The smallest unit. One `(init, fix, check)` triple:
```python
FaultAtom(
    init = InitCall(set_checkout_due_date, checkout_id="{checkout_id}", due_date="2024-01-01")  # break it
    fix  = ActionSpec(renew_checkout, checkout_id="{checkout_id}", new_due_date="{date}")        # fix tool
    check = AssertionSpec(assert_checkout_due_date, checkout_id="{checkout_id}", expected_date="{date}")  # verify
)
```
The structural bundling means init/fix/check can never disagree — they're authored as one unit.

Three atom patterns exist:
- `init + fix + check` — primary fault (break → fix → verify)
- `None + fix + check` — consequence action (no separate init, but needed to complete the fix, e.g. user acknowledges after agent fixes)
- `None + fix + None` — terminal follow-up (e.g. reboot, no independent assertion)

**FaultLayer** — A single injectable fault, composed of one or more atoms. Example: "overdue checkout" has two atoms:
1. Agent renews (init sets overdue status/date → agent calls renew_checkout → assert due date correct)
2. User acknowledges (no init → user calls acknowledge_resolution → assert resolution acknowledged)

A layer also has:
- `known_info_fragment` — what the user says about this fault ("my checkout is showing as overdue")
- `predicate_field` — entity filter (only apply if `entity.has_checkout == True`)
- `resource_scope` — conflict detection key (e.g. `"checkout:{checkout_id}"`)
- `unfixable=True` — the fault can't be resolved, agent must transfer to human

**FaultLayerGroup** — Mutually exclusive layers. You pick 0 or 1 from each group. Example: "checkout_issues" group contains `overdue_checkout` and `lost_book_record` — you can't have both simultaneously.

**FaultLayerConfig** — The cartesian product engine. It takes:
- `entity_query` — function returning entities from the DB
- `groups` — list of FaultLayerGroups
- `base_init_calls` — normalization that runs for every task (set user identity, etc.)
- `base_known_info_template` — template with `{fault_descriptions}` placeholder
- `min_faults` / `max_faults` — bounds on simultaneous faults

The engine then generates every valid combination: for each entity × each subset of fault layers (one per group, respecting min/max), produce a task spec.

### How Dependencies Work

Dependencies between fault layers are managed through several mechanisms:

1. **Resource scope validation** — Layers in *different* groups that modify the same resource are flagged as an error at generation time. If two layers both touch `checkout:{CK001}`, they must be in the same group (mutually exclusive).

2. **Predicate filtering** — A layer's `predicate_field` controls which entities it applies to. If an entity doesn't have a checkout, checkout fault layers are skipped for that entity.

3. **Action ordering** — Within a combo, actions are ordered: layer user actions first → layer agent actions → base agent actions → base user actions. This ensures user-side preconditions (e.g. `make_fine_payment`) run before agent-side actions that depend on them.

4. **Deduplication** — When multiple layers produce identical actions (same tool, same requestor, same resolved args), only one copy is kept. Same for assertions. This prevents the evaluator from expecting 3 identical `acknowledge_resolution` calls when 3 fault layers compose together.

### Sampling Strategies

When the cartesian product is too large, two sampling strategies are available:
- `max_tasks_per_bin` — Uniform: group by (entity, fault_count), cap N per bin
- `max_total_tasks` — Proportional: preserve the natural C(N,K) bell-curve distribution, allocate budget proportionally to each fault-count tier

### Unfixable (Transfer) Tasks

When any layer in a combo has `unfixable=True`, the entire task becomes a transfer task:
- The only expected action is `transfer_to_human(summary="", compare_args=[])`
- **Preservation assertions** verify the agent didn't modify the injected state (e.g. `assert_checkout_status(checkout_id, "overdue")`)
- Init still runs (to inject the unfixable condition)

### The Generation Flow

```
RecipeBook.fault_layer_configs
  → for each FaultLayerConfig:
      1. Query entities from DB
      2. Validate layer structure (atoms vs legacy, unfixable rules)
      3. Validate resource scopes (no cross-group conflicts)
      4. Cartesian product: entity × group₁ × group₂ × ... × groupₙ
      5. Filter by (min_faults ≤ active_count ≤ max_faults)
      6. Optional sampling
      7. For each (entity, active_layers):
         - Resolve {field} templates against entity
         - Unfold atoms → flat init/actions/assertions
         - Dedup actions and assertions
         - Build known_info from fragment composition
         - Assign tier from fault count
         → GeneratedTaskSpec
  → _spec_to_task: attach persona, user_template, format as Task JSON
```

### Personas and Variants

Each task gets a persona based on its tier:
- Tier 1-2 (1 fault) → easy persona (cooperative, clear communicator)
- Tier 3-4 (2-3 faults) → medium persona
- Tier 5 (4+ faults) → hard persona (anxious, vague)

Optional `VariantConfig` produces A/B variants: same task with easy and hard personas, so you can measure persona impact on agent performance.

## Layer 5: Verification Pipeline

After tasks are generated, they pass through a two-phase verification:

### Phase A: Code-Level Checks (11 checks, `src/tau2/generators/verify.py`)

| # | Check | Type | What it catches |
|---|-------|------|-----------------|
| 1 | Reward basis | Static | Invalid reward types, mismatched compare_args |
| 2 | Tool schemas | Static | Missing tools, invalid arg names, missing required params, Any-typed params |
| 3 | Argument reachability | Runtime | Action args not discoverable from ticket + READ tools |
| 4 | Golden path | Runtime | Fix actions don't actually fix the fault (run init → fix → check assertions) |
| 5 | User action feasibility | Static | Missing task_instructions, conditional user actions, undiscoverable user args |
| 6 | Policy alignment | Static | Policy doesn't instruct agent to tell user to perform user actions |
| 7 | User action redundancy | Runtime | Assertions pass without user actions (ENV_ASSERTION always 1.0) |
| 8 | Action state change | Runtime | No-op actions that don't modify DB state |
| 9 | Action necessity | Runtime | Redundant actions — all assertions pass without the action |
| 10 | Assertion robustness | Runtime | Assertions fail on LLM format variants (e.g. `["fiction"]` vs `"fiction"`) |
| 11 | Assertion value discoverability | Static | Assertion expected values not in user context or action args |

### Phase A.5: Per-Atom Verification (`verify_fault_atoms`)

Before full task verification, each atom is tested in isolation:
1. Run base init + atom init → verify atom check **FAILS** (fault was injected)
2. Run base init + atom init + atom fix + sync → verify atom check **PASSES** (fix works)

This catches broken init→fix→check chains at O(atoms × sample_size) cost instead of O(tasks).

### Phase B: LLM-Based Semantic Checks (13 checks)

A subset of tasks is sent to an LLM reviewer that checks:

| # | Check | What it catches |
|---|-------|-----------------|
| 1 | Fix-action / assertion chain | Fix tool doesn't modify the DB field the assertion checks |
| 2 | Policy alignment | Expected actions don't match policy prescriptions |
| 3 | Known-info clarity | Ambiguous user description, can't tell which resource is affected |
| 4 | User action feasibility | Policy doesn't instruct agent to tell user to act |
| 5 | Task instructions | User simulator won't know to call user tools |
| 6 | User action preconditions | Agent tool doesn't gate on user action, will bypass it |
| 7 | Data-policy consistency | Task data contradicts policy rules (e.g. scheduling on a holiday) |
| 8 | Init state record coherence | Stale fields after partial DB mutation |
| 9 | Entity-resource ownership | Cross-entity scoping errors (wrong patron's checkout) |
| 10 | Tool precondition robustness | sync_tools invalidates agent tool's preconditions |
| 11 | Known-info / resolution alignment | User framing suggests different fix than expected |
| 12 | Unfixable state preservation | Transfer tasks missing preservation assertions |
| 13 | Multi-action fault coherence | Multi-step sequences are illogical or redundant |

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
               files                     reads library reference files,
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

Each instruction file contains the specific requirements, gotchas, and constraints for that step. The library domain (`src/tau2/domains/library/`) serves as the reference pattern that Claude reads alongside each instruction file.

### CLI Tools

Four CLI scripts support the skill workflow:

| CLI | Purpose |
|-----|---------|
| `python -m tau2.generators.scaffold_domain <name>` | Creates directories, `__init__.py`, `utils.py` |
| `python -m tau2.generators.validate_domain <name> [--step <step>]` | Runs structural validation (syntax, imports, class hierarchy, DB loading, tool counts, etc.) |
| `python -m tau2.generators.generate_tasks <name> [--save]` | Calls `create_tasks(verify=True)`, optionally saves `tasks.json` |
| `python -m tau2.generators.finalize_domain <name>` | Updates `src/tau2/registry.py` with new domain imports and registration |

### The Reference Domain

The `docs/domain-authoring-guide.md` (1500+ lines) is the authoritative design guide that Claude reads first. It covers entity design, tool patterns, fault layer architecture, sync_tools gotchas, user action feasibility rules, and difficulty calibration. The library domain is the canonical reference implementation.

### Full Generation Flow

```python
# What Claude Code does via the skill:
# 1. Read authoring guide
# 2. Scaffold directories
# 3. For each of 10 files:
#    a. Read instruction file + reference file
#    b. Write the domain file
#    c. Run validate_domain --step <step>
#    d. If validation fails, read error, fix, re-validate
# 4. Exhaustive 9-audit review
# 5. generate_tasks --save (runs verify.py + verify_fault_atoms)
# 6. finalize_domain (updates registry)

# What the deterministic code does:
create_tasks(verify=True, save=True)
  1. verify_fault_atoms()     # per-atom golden path
  2. generate_recipe_tasks()  # cartesian product → Task objects
  3. verify_tasks()           # 11 code checks on every task
  4. task.dump()              # save tasks.json
```

## Design Principle

The key design principle throughout: **structural correspondence prevents disagreement**. Atoms bundle init/fix/check so they can't diverge. Templates resolve from a single entity dict so IDs can't mismatch. Resource scopes prevent cross-group conflicts. And 11+13 verification checks catch anything the structural guarantees miss.
