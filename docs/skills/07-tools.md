# Step 7: Agent Tools (tools.py)

Generate the agent-side toolkit — the tools available to the AI agent for looking up data and resolving issues.

## Reference

- Read `docs/domain-authoring-guide.md` lines 257-403 (Agent Tools) and 1172-1257 (Gotchas)
- Read `src/tau2/domains/library/tools.py` for the EXACT pattern to follow

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json`
- Read `src/tau2/domains/<domain_name>/data_model.py`
- Read `data/tau2/domains/<domain_name>/policy.md` (for tool requirements)

## Output

Write to `src/tau2/domains/<domain_name>/tools.py`.

## Requirements

### Imports

```python
from typing import Any, Dict, List, Optional
from tau2.domains.<domain_name>.data_model import <DomainClass>DB, <Entity1>, <Entity2>, ...
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool
```

Replace `<domain_name>` and `<DomainClass>` with actual values.

### Class Structure

```python
class <DomainClass>Tools(ToolKitBase):
    db: <DomainClass>DB

    def __init__(self, db: <DomainClass>DB):
        super().__init__(db)
```

### Tool Categories

1. **Internal helpers** (prefixed with `_`, no decorator):
   - `_find_<entity>(self, id: str)` — lookup by ID
   - `_find_<entity>_by_name(self, name: str)` — lookup by name
   - `_normalize_str(s: str)` — normalize strings for comparison

2. **READ tools** (`@is_tool(ToolType.READ)`):
   - At least 3 READ tools
   - `get_<entity>_by_name(name)` — lookup by name
   - `get_<entity>_by_id(id)` — lookup by ID
   - ENTITY NAVIGATION: For every child entity type with a foreign key to the primary entity, include `get_<children>(parent_id)` — e.g. `get_checkouts(patron_id)`, `get_holds(patron_id)`
   - Without navigation tools, the agent cannot discover entity IDs and will fail tasks

3. **WRITE tools** (`@is_tool(ToolType.WRITE)`):
   - At least 3 WRITE tools
   - Each corresponds to a fix action from the fault groups
   - Every tool must have proper docstring with Args and Returns

4. **GENERIC tools** (`@is_tool(ToolType.GENERIC)`):
   - `transfer_to_human(summary: str)` — transfers to human specialist

5. **Setup helpers** (no decorator, used by scenario init):
   - `set_<field>(self, entity_id, value)` — sets a DB field directly
   - One per mutable field that fault layers need to initialize

6. **Assertion helpers** (no decorator, used by verification):
   - `assert_<field>(self, entity_id, expected_value) -> bool`
   - CRITICAL: For each WRITE tool, ensure a matching assertion helper that checks the EXACT field that tool modifies
   - If `reassign_dentist` changes `appointment.dentist`, there must be `assert_appointment_dentist`
   - The verification system runs fix actions then checks assertions

### Precondition Pattern

When a WRITE tool depends on a user action (e.g. `process_payment` requires user to call `make_payment` first):
- The tool MUST check a bridged field that `sync_tools` sets when the user acts
- Without this precondition, the agent bypasses the user action entirely (ACTION:0.0)
- Pattern: user tool sets `user_db` field → `sync_tools` bridges to `agent_db` → agent WRITE tool checks the bridged field and raises `ValueError` if not set

### Docstrings

Every tool must have a proper docstring with:
```python
"""
Brief description.

Args:
    param1: Description.
    param2: Description.

Returns:
    Description of return value.
"""
```

## Validation

The validator will:
- Check Python syntax
- Import the module
- Check class exists and inherits `ToolKitBase`
- Instantiate with the DB
- Count tools by type (>= 1 READ, >= 1 WRITE, >= 1 GENERIC)
- Check for `assert_*` methods (no decorator)
- Check for `set_*` methods (no decorator)
- Check entity navigation tools exist
