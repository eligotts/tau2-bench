# Step 4: Database JSON (db.json)

Generate realistic test data that populates the agent-side database.

## Reference

- Read `docs/domain-authoring-guide.md` lines 116-176 (Agent DB section)
- Read `data/tau2/domains/auto_repair/db.json` for the reference data format

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json`
- Read `src/tau2/domains/<domain_name>/data_model.py`

## Output

Write to `data/tau2/domains/<domain_name>/db.json`.

## Requirements

1. **Match the data_model.py schema EXACTLY** — all required fields present, correct types.

2. **Entity counts:**
   - 15-20 primary entities (e.g. patrons, customers, patients)
   - 5-10 secondary entities per collection (e.g. books, appointments, invoices)
   - Enough variety for fault groups to have 2-3 applicable entities each

3. **Pre-seed variety:**
   - Some entities in normal/active state
   - Some with existing issues (overdue, suspended, etc.)
   - Mix of membership types, statuses, locations

4. **Relationships:** Include proper foreign key references between entities (e.g. checkout.patron_id references a valid patron).

5. **Realistic names and values:**
   - IMPORTANT: Avoid apostrophes or special characters in names
   - Use `Kevin Brooks` not `Kevin O'Brien`
   - Use `Napoli Pizzeria` not `Napoli's Pizzeria`
   - LLMs send curly quotes that fail exact-match lookups

6. **Date format:** Use `YYYY-MM-DD` for all dates.

7. **ID format:** Use descriptive IDs like `PAT001`, `BK001`, `CK001` (not UUIDs).

## Validation

The validator will:
- Parse the JSON
- Load it with `<DomainClass>DB.load(path)` — this validates against the Pydantic model
- Check that total entities >= 3
