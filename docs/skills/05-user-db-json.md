# Step 5: User Database JSON (user_db.json)

Generate the initial (empty) state of the user-side database.

## Reference

- Read `data/tau2/domains/auto_repair/user_db.json` for the reference format

## Context

- Read `src/tau2/domains/<domain_name>/user_data_model.py`

## Output

Write to `data/tau2/domains/<domain_name>/user_db.json`.

## Requirements

1. **Match the user_data_model.py schema exactly.**

2. **Identity fields** (fields ending with `_name` or `_id`) must be `null`.

3. **Lists** should be empty `[]`.

4. **Dicts** should be empty `{}`.

5. **Numeric fields** should be `0` or `0.0`.

6. **Boolean fields** should be `false`.

## Example

```json
{
  "patron_id": null,
  "patron_name": null,
  "my_checkouts": [],
  "my_holds": [],
  "fine_summaries": {},
  "resolution_acknowledged": {},
  "hold_pickup_confirmed": {}
}
```

## Validation

The validator will:
- Parse the JSON
- Load with `<DomainClass>UserDB.load(path)`
- Check that identity fields (`_name`, `_id`) are null
