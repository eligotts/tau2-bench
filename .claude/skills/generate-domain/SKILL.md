---
name: generate-domain
description: Generate a complete tau2-bench domain from a concept name. Walks through all 13 steps — archetype classification, scaffolding, writing 10 domain files, validation, LLM review, task generation, and finalization.
user_invocable: true
---

# Generate Domain

Generate a complete tau2-bench customer service domain from a concept name.

## Arguments

The user provides a **domain concept** as the argument, e.g.:
- `/generate-domain hotel_resort`
- `/generate-domain car_rental`
- `/generate-domain pet_grooming`

The concept should be a snake_case name for a customer service domain.

## Workflow

Follow these steps in order. After each file-writing step, run validation and fix any errors before proceeding.

### Step 0: Preparation

1. Read the full domain authoring guide at `docs/domain-authoring-guide.md` (all 1700+ lines). This is the authoritative reference for all design decisions.
2. Run the scaffold CLI to create directories and boilerplate:
   ```
   uv run python -m tau2.generators.scaffold_domain <domain_name>
   ```

### Step 0.5: Archetype Classification

1. Read `docs/skills/00-archetype.md` for the four domain archetypes.
2. Classify the domain concept into its primary archetype:
   - **A: Sequential Diagnostic** — dependency hierarchies, gated tool access, progressive discovery
   - **B: Branching Troubleshooter** — user-as-instrument, device/physical actions, decision trees
   - **C: Transaction Processor** — structured protocols, numeric computation, policy-based denial
   - **D: Triage / Classification** — information gathering, judgment calls, routing
3. Note the archetype in the domain spec (Step 1). **This archetype determines which patterns you use for every subsequent step.**
4. Read the reference snippets in `00-archetype.md` for your chosen archetype.

### Step 1: Domain Spec

1. Read `docs/skills/01-domain-spec.md` for detailed instructions.
2. Design a structured domain specification as a JSON object, including the archetype field.
3. Save it to `data/tau2/domains/<domain_name>/domain_spec.json`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step domain_spec`

### Step 2: Data Model

1. Read `docs/skills/02-data-model.md` for detailed instructions.
2. Read `src/tau2/domains/auto_repair/data_model.py` as the structural reference (class hierarchy and DB pattern are the same for all archetypes).
3. Write `src/tau2/domains/<domain_name>/data_model.py`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step data_model`

### Step 3: User Data Model

1. Read `docs/skills/03-user-data-model.md` for detailed instructions.
2. Read `src/tau2/domains/auto_repair/user_data_model.py` as the structural reference.
3. For **Archetype B** (branching troubleshooter): the user data model will be larger — it holds device/physical state the user interacts with (signal strength, connection status, toggles). For other archetypes, it's mainly projections and tracking fields.
4. Write `src/tau2/domains/<domain_name>/user_data_model.py`.
5. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step user_data_model`

### Step 4: Database JSON

1. Read `docs/skills/04-db-json.md` for detailed instructions.
2. Read `data/tau2/domains/auto_repair/db.json` as the reference.
3. Write `data/tau2/domains/<domain_name>/db.json`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step db_json`

### Step 5: User Database JSON

1. Read `docs/skills/05-user-db-json.md` for detailed instructions.
2. Read `data/tau2/domains/auto_repair/user_db.json` as the reference.
3. Write `data/tau2/domains/<domain_name>/user_db.json`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step user_db_json`

### Step 6: Policy Document

1. Read `docs/skills/06-policy.md` for detailed instructions.
2. Read `data/tau2/domains/auto_repair/policy.md` as a reference for structure and user-tool naming.
3. **Match the policy style to your archetype:**
   - **A:** Iterative diagnostic workflow ("fix X before you can see Y")
   - **B:** Branching decision tree with device-side troubleshooting steps
   - **C:** Prescriptive protocol with precondition checks and denial conditions
   - **D:** Classification criteria with routing rules
4. Write `data/tau2/domains/<domain_name>/policy.md`.
5. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step policy`

### Step 7: Agent Tools

1. Read `docs/skills/07-tools.md` for detailed instructions.
2. Read `src/tau2/domains/auto_repair/tools.py` as the structural reference (class hierarchy, decorator pattern, helper methods).
3. **Match READ tool patterns to your archetype:**
   - **A:** State-dependent READ tools (information hiding — gated by upstream state)
   - **B:** Transparent backend READ tools (agent sees full backend state)
   - **C:** Transparent READ tools with guarded WRITE tools (precondition checks)
   - **D:** Mix of transparent and classification-oriented READ tools
4. Also read the archetype-specific snippets in `docs/skills/00-archetype.md` for tool patterns.
5. Write `src/tau2/domains/<domain_name>/tools.py`.
6. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step tools`

### Step 8: User Tools

1. Read `docs/skills/08-user-tools.md` for detailed instructions.
2. Read `src/tau2/domains/auto_repair/user_tools.py` as the structural reference.
3. **Match user tool density to your archetype:**
   - **A:** 3-5 confirmation/acknowledgment tools (agent-driven)
   - **B:** 5-15 diagnostic + fix tools (user-as-instrument)
   - **C:** 1-3 confirmation tools (minimal user role)
   - **D:** 1-2 acknowledgment tools (minimal user role)
4. Write `src/tau2/domains/<domain_name>/user_tools.py`.
5. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step user_tools`

### Step 9: Environment

1. Read `docs/skills/09-environment.md` for detailed instructions.
2. Read `src/tau2/domains/auto_repair/environment.py` as the structural reference (class hierarchy, factory function, task loading are the same for all archetypes).
3. Write `src/tau2/domains/<domain_name>/environment.py`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step environment`

### Step 10: Scenarios

1. Read `docs/skills/10-scenarios.md` for detailed instructions (longest step).
2. Read `src/tau2/domains/auto_repair/scenarios.py` as the structural reference for RecipeBook, FaultLayerConfig, and create_tasks().
3. Also read the archetype-specific snippets in `docs/skills/00-archetype.md` for fault layer patterns.
4. **Match fault layer patterns to your archetype:**
   - **A:** 2 atoms/layer (agent fix + user confirm), 6-10 groups
   - **B:** 1-2 atoms/layer (often user-only fix), 5-9 groups, `requestor="user"` on fix actions
   - **C:** 1-2 atoms/layer (agent fix + optional confirm), 5-8 groups, numeric assertions
   - **D:** 1 atom/layer (agent classify/route), 4-7 groups, lenient assertions
5. Write `src/tau2/domains/<domain_name>/scenarios.py`.
6. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step scenarios`

### Step 10.5: Exhaustive Audit

1. Read `docs/skills/11-llm-review.md` for the audit checklist.
2. Read ALL generated files for the domain together.
3. Perform each audit, tracing every fault layer chain, template variable, etc.
4. **Pay special attention to the "Agent Success Determines Outcome" audit** — verify that task success depends on the AGENT doing the right thing, not the user sim behaving correctly.
5. Fix any issues found, then re-validate the affected files.

### Step 11: Task Generation

1. Run task generation with verification:
   ```
   uv run python -m tau2.generators.generate_tasks <domain_name> --save
   ```
2. If errors occur, read the error output, fix the relevant file (usually `scenarios.py` or `tools.py`), and retry.
3. **CRITICAL: The output must show 0 errors AND 0 warnings.** Do NOT dismiss warnings — they predict real runtime failures.
4. The output should show 20+ tasks with a difficulty distribution.

### Step 12: Finalize

1. Run finalization to update the registry:
   ```
   uv run python -m tau2.generators.finalize_domain <domain_name>
   ```
2. Verify the domain appears in `src/tau2/registry.py`.

## File Locations

- Python source files (`.py`) go in `src/tau2/domains/<domain_name>/`
- Data files (`.json`, `.md`) go in `data/tau2/domains/<domain_name>/`
- The `utils.py` and `__init__.py` are created by the scaffold step

## Error Handling

When validation fails:
1. Read the error output carefully
2. Read the file that failed validation
3. Fix the specific issue (don't rewrite from scratch)
4. Re-run validation for that step
5. If stuck after 3 attempts on the same error, re-read the authoring guide section, the archetype snippets in `docs/skills/00-archetype.md`, and the auto_repair reference file for that step

## Quality Targets

- 20+ tasks generated
- All defined personas appear in task IDs (`[PERSONA:name]` suffix)
- Difficulty distribution appropriate to archetype (not all tasks trivially easy)
- All validation steps pass
- No resource conflicts between fault groups
- 0 errors AND 0 warnings from task generation
- Agent success determines task outcome (not user sim reliability)
