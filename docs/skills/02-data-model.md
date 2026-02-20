# Step 2: Data Model (data_model.py)

Generate the agent-side database model — the Pydantic classes representing all domain entities.

## Reference

- Read `docs/domain-authoring-guide.md` lines 116-176 (Agent DB section)
- Read `src/tau2/domains/library/data_model.py` for the exact pattern to follow

## Context

Read `data/tau2/domains/<domain_name>/domain_spec.json` for the entity definitions.

## Output

Write to `src/tau2/domains/<domain_name>/data_model.py`.

## Requirements

1. **Imports:**
   ```python
   from typing import List, Optional
   from tau2.environment.db import DB
   from tau2.utils.pydantic_utils import BaseModelNoExtra
   ```

2. **Entity classes:** Each entity type from the domain spec is a class inheriting `BaseModelNoExtra`.
   - Use descriptive field names matching the spec
   - Use `str` for IDs, status fields, dates (YYYY-MM-DD format)
   - Use `float` for monetary amounts
   - Use `Optional[str] = None` for nullable fields

3. **DB class:** The top-level class inherits from `DB`.
   - Name: `<DomainClass>DB` (e.g. `HotelResortDB` for `hotel_resort`)
   - Replace `<DomainClass>` with the PascalCase form of the domain name
   - Each entity collection is a `List[<EntityClass>]` field

4. **All fields must be JSON-serializable** — no custom types.

5. **Use `typing.List` and `typing.Optional`** for type hints (not `list[...]` or `... | None`).

## Pattern

Follow the library example exactly:

```python
class Patron(BaseModelNoExtra):
    patron_id: str
    name: str
    # ... fields

class LibraryDB(DB):
    patrons: List[Patron]
    books: List[Book]
    # ... collections
```
