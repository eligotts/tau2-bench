# Step 3: User Data Model (user_data_model.py)

Generate the user-side database model — what the user (customer) can observe.

## Reference

- Read `docs/domain-authoring-guide.md` lines 177-208 (User DB section)
- Read `src/tau2/domains/auto_repair/user_data_model.py` for the exact pattern

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json`
- Read `src/tau2/domains/<domain_name>/data_model.py` (the agent-side model you just wrote)

## Output

Write to `src/tau2/domains/<domain_name>/user_data_model.py`.

## Requirements

1. **Imports:**
   ```python
   from typing import Dict, List, Optional
   from tau2.environment.db import DB
   from tau2.utils.pydantic_utils import BaseModelNoExtra
   ```

2. **Summary classes:** Define lightweight summary classes for entity projections (e.g. `CheckoutSummary`, `HoldSummary`).

3. **UserDB class:** `<DomainClass>UserDB(DB)`
   - ALL fields MUST have default values (`None`, `[]`, `0.0`, `{}`, etc.)
   - Identity fields MUST end with `_name` or `_id` (e.g. `patron_name`, `patron_id`) and default to `None`
   - Do NOT put other data in fields whose name ends with `_name` or `_id`
   - For lists of names (e.g. pet names), use a descriptive field name that does NOT end with `_name` (e.g. `pet_name_list`, `visible_pets`)

4. **Projection fields:** Include fields that `sync_tools()` will populate from the agent DB:
   - Summary lists (e.g. `my_checkouts: List[CheckoutSummary] = []`)
   - Status strings (e.g. `fine_summaries: Dict[str, str] = {}`)

5. **User action tracking fields:** Include `Dict[str, bool]` fields for user confirmations:
   - e.g. `resolution_acknowledged: Dict[str, bool] = {}`
   - e.g. `hold_pickup_confirmed: Dict[str, bool] = {}`
   - These are set by user tools and checked by user assertions

## Pattern

Follow the auto_repair example — the UserDB is a PROJECTION of the agent DB (what the user can observe), plus tracking fields for user actions (e.g. `repair_approved`, `payment_made`).
