---
name: generate-domain
description: Generate a complete tau2-bench domain from a concept name. Walks through all 12 steps — scaffolding, writing 10 domain files, validation, LLM review, task generation, and finalization.
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

1. Read the full domain authoring guide at `docs/domain-authoring-guide.md` (all 1500+ lines). This is the authoritative reference for all design decisions.
2. Run the scaffold CLI to create directories and boilerplate:
   ```
   uv run python -m tau2.generators.scaffold_domain <domain_name>
   ```

### Step 1: Domain Spec

1. Read `docs/skills/01-domain-spec.md` for detailed instructions.
2. Design a structured domain specification as a JSON object.
3. Save it to `data/tau2/domains/<domain_name>/domain_spec.json`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step domain_spec`

### Step 2: Data Model

1. Read `docs/skills/02-data-model.md` for detailed instructions.
2. Read `src/tau2/domains/library/data_model.py` as the reference pattern.
3. Write `src/tau2/domains/<domain_name>/data_model.py`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step data_model`

### Step 3: User Data Model

1. Read `docs/skills/03-user-data-model.md` for detailed instructions.
2. Read `src/tau2/domains/library/user_data_model.py` as the reference.
3. Write `src/tau2/domains/<domain_name>/user_data_model.py`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step user_data_model`

### Step 4: Database JSON

1. Read `docs/skills/04-db-json.md` for detailed instructions.
2. Read `data/tau2/domains/library/db.json` as the reference.
3. Write `data/tau2/domains/<domain_name>/db.json`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step db_json`

### Step 5: User Database JSON

1. Read `docs/skills/05-user-db-json.md` for detailed instructions.
2. Read `data/tau2/domains/library/user_db.json` as the reference.
3. Write `data/tau2/domains/<domain_name>/user_db.json`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step user_db_json`

### Step 6: Policy Document

1. Read `docs/skills/06-policy.md` for detailed instructions.
2. Read `data/tau2/domains/library/policy.md` as the reference.
3. Write `data/tau2/domains/<domain_name>/policy.md`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step policy`

### Step 7: Agent Tools

1. Read `docs/skills/07-tools.md` for detailed instructions.
2. Read `src/tau2/domains/library/tools.py` as the reference.
3. Write `src/tau2/domains/<domain_name>/tools.py`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step tools`

### Step 8: User Tools

1. Read `docs/skills/08-user-tools.md` for detailed instructions.
2. Read `src/tau2/domains/library/user_tools.py` as the reference.
3. Write `src/tau2/domains/<domain_name>/user_tools.py`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step user_tools`

### Step 9: Environment

1. Read `docs/skills/09-environment.md` for detailed instructions.
2. Read `src/tau2/domains/library/environment.py` as the reference.
3. Write `src/tau2/domains/<domain_name>/environment.py`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step environment`

### Step 10: Scenarios

1. Read `docs/skills/10-scenarios.md` for detailed instructions (longest step).
2. Read `src/tau2/domains/library/scenarios.py` as the reference.
3. Write `src/tau2/domains/<domain_name>/scenarios.py`.
4. Validate: `uv run python -m tau2.generators.validate_domain <domain_name> --step scenarios`

### Step 10.5: Exhaustive Audit

1. Read `docs/skills/11-llm-review.md` for the 9-audit checklist.
2. Read ALL generated files for the domain together.
3. Perform each of the 9 audits, tracing every fault layer chain, template variable, etc.
4. Fix any issues found, then re-validate the affected files.

### Step 11: Task Generation

1. Run task generation with verification:
   ```
   uv run python -m tau2.generators.generate_tasks <domain_name> --save
   ```
2. If errors occur, read the error output, fix the relevant file (usually `scenarios.py` or `tools.py`), and retry.
3. The output should show 20+ tasks with a bell-curve difficulty distribution.

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
5. If stuck after 3 attempts on the same error, re-read the authoring guide section and the reference file for that step

## Quality Targets

- 20+ tasks generated
- Both VARIANT:a and VARIANT:b present
- Bell-curve difficulty distribution (most tasks have 4-8 actions)
- All validation steps pass
- No resource conflicts between fault groups
