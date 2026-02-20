# Step 8: User Tools (user_tools.py)

Generate the user-side toolkit — tools available to the user (customer) for viewing their state and performing actions.

## Reference

- Read `docs/domain-authoring-guide.md` lines 404-461 (User Tools section)
- Read `src/tau2/domains/library/user_tools.py` for the exact pattern

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json`
- Read `src/tau2/domains/<domain_name>/user_data_model.py`

## Output

Write to `src/tau2/domains/<domain_name>/user_tools.py`.

## Requirements

### Imports

```python
from typing import Any, Dict, List
from tau2.domains.<domain_name>.user_data_model import <DomainClass>UserDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool
```

### Class Structure

```python
class <DomainClass>UserTools(ToolKitBase):
    db: <DomainClass>UserDB

    def __init__(self, db: <DomainClass>UserDB):
        super().__init__(db)
```

### Tool Categories

1. **READ tools** (`@is_tool(ToolType.READ)`):
   - At least 1 READ tool for the user to check their state
   - e.g. `view_my_checkouts()`, `view_my_appointments()`

2. **WRITE tools** (`@is_tool(ToolType.WRITE)`):
   - 3-5 WRITE tools for user-side actions
   - These are actions the agent instructs the user to perform:
     - Confirmations: `confirm_hold_pickup(hold_id)`, `confirm_event(event_id)`
     - Acknowledgments: `acknowledge_resolution(patron_id)`, `acknowledge_loan(loan_id)`
     - Payments: `make_fine_payment(fine_id, amount)`
   - Design DISTINCT tools for different fault groups to avoid action deduplication
   - Prefer zero-arg or single-arg tools for reliability

3. **Setup helper** (no decorator):
   - `set_patron_info(name, patron_id)` or `set_user_info(name, user_id)` — sets identity fields
   - Called during scenario initialization

4. **Assertion helpers** (no decorator, return `bool`):
   - `assert_resolution_acknowledged(patron_id) -> bool`
   - `assert_hold_pickup_confirmed(hold_id) -> bool`
   - One per user action tracking field in the UserDB

### Docstrings

Every tool must have proper docstrings with Args and Returns.

## Validation

The validator will:
- Check Python syntax
- Import the module
- Check class exists and inherits `ToolKitBase`
- Instantiate with the UserDB
- Check at least 1 tool exists
- Check for `assert_*` methods (no decorator)
- Check for `set_*` methods (no decorator)
