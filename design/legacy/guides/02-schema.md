# Step 2: Entity Schema

## Purpose

Define the fields for every entity type named in Step 1. This is where the world
gets its substance: field types, which fields are mutable, which are breakable
(can be perturbed for tasks), and what "normal" vs "broken" values look like.

Breakable fields are the raw material for tasks. If a field isn't breakable,
it can't be used in any perturbation. More breakable fields = more diverse tasks.


## Input (locked from Step 1)

- `entity_names` — the exact entity type names. You CANNOT invent new entities.
- `topology.min_width` — target number of breakable fields.


## Output

A `WorldSchema` containing a list of `EntitySpec`, one per entity name from Step 1.

### EntitySpec
```
name: str              # Must match one of entity_names from Step 1
description: str       # 1 sentence
identity_field: str    # Primary key field name (must appear in fields list)
fields: list[FieldSpec]
```

### FieldSpec
```
name: str              # snake_case
type: FieldType        # One of: "str", "int", "float", "bool", "enum", "date", "list[str]"
description: str       # 1 sentence
mutable: bool = True   # Can the agent change this? (identity fields are immutable)
breakable: bool = False  # Can this be perturbed for tasks?
computed: bool = False   # Derived from other fields?
user_visible: bool = False  # Visible to user through their projection?
normal_value: Any = None    # The "correct" value. REQUIRED if breakable.
broken_values: list[Any] = []  # Possible "wrong" values. REQUIRED if breakable, >=1.
enum_values: list[str] = []    # Valid values. REQUIRED if type="enum", >=2.
```

### FieldType values
`"str"`, `"int"`, `"float"`, `"bool"`, `"enum"`, `"date"`, `"list[str]"`


## Constraints

- Every entity name in Step 1 must get an EntitySpec (no skipping)
- Do NOT add entities not in Step 1's entity_names
- Every entity must have an identity_field that appears in its fields list
- Identity fields should be `mutable: False`
- No duplicate field names within an entity
- If `breakable: True`, then `normal_value` MUST be set (ERROR if missing)
- If `breakable: True`, then `broken_values` MUST have >=1 entry (ERROR if missing)
- If `type: "enum"`, then `enum_values` MUST have >=2 entries (ERROR if missing)
- Target: at least `min_width` breakable fields total across all entities (WARNING if fewer)
- At least 3 breakable fields total (WARNING if fewer)


## Examples

### Customer Entity (Coffee Shop)
```python
EntitySpec(
    name="Customer",
    description="A registered coffee shop customer with a loyalty account",
    identity_field="customer_id",
    fields=[
        FieldSpec(name="customer_id", type="str", description="Unique customer identifier",
                  mutable=False),
        FieldSpec(name="name", type="str", description="Customer full name",
                  mutable=False),
        FieldSpec(name="email", type="str", description="Contact email",
                  mutable=True),
        FieldSpec(name="account_status", type="enum", description="Account standing",
                  mutable=True, breakable=True,
                  normal_value="active",
                  broken_values=["suspended", "frozen"],
                  enum_values=["active", "suspended", "frozen"]),
        FieldSpec(name="phone", type="str", description="Contact phone",
                  mutable=True),
    ]
)
```

### Deployment Entity (SRE)
```python
EntitySpec(
    name="Deployment",
    description="A Kubernetes deployment managing a set of pods",
    identity_field="deployment_id",
    fields=[
        FieldSpec(name="deployment_id", type="str", description="Deployment name",
                  mutable=False),
        FieldSpec(name="namespace", type="str", description="Kubernetes namespace",
                  mutable=False),
        FieldSpec(name="replicas", type="int", description="Desired replica count",
                  mutable=True, breakable=True,
                  normal_value=3,
                  broken_values=[0, 1]),
        FieldSpec(name="image", type="str", description="Container image tag",
                  mutable=True, breakable=True,
                  normal_value="app:v2.1.0",
                  broken_values=["app:v1.0.0-broken", "app:latest-unstable"]),
        FieldSpec(name="strategy", type="enum", description="Rollout strategy",
                  mutable=True,
                  enum_values=["RollingUpdate", "Recreate"]),
        FieldSpec(name="config_ref", type="str", description="Reference to ConfigMap",
                  mutable=False),
    ]
)
```

### Sheet Entity (Spreadsheet — higher abstraction)
```python
EntitySpec(
    name="Sheet",
    description="A spreadsheet sheet with tabular data, formulas, and charts",
    identity_field="sheet_name",
    fields=[
        FieldSpec(name="sheet_name", type="str", description="Sheet name",
                  mutable=False),
        FieldSpec(name="purpose", type="str", description="What this sheet is for",
                  mutable=False),
        FieldSpec(name="headers", type="list[str]", description="Column headers",
                  mutable=True),
        FieldSpec(name="row_count", type="int", description="Number of data rows",
                  mutable=True, breakable=True,
                  normal_value=200,
                  broken_values=[0, 15]),
        FieldSpec(name="is_locked", type="bool", description="Whether sheet is locked",
                  mutable=True, breakable=True,
                  normal_value=False,
                  broken_values=[True]),
    ]
)
```


## Anti-Patterns

**Breakable field without normal_value or broken_values**
```python
# BAD: breakable=True but no normal/broken values — verification will ERROR
FieldSpec(name="status", type="enum", breakable=True,
          enum_values=["active", "suspended"])
```
Fix: add `normal_value="active"` and `broken_values=["suspended"]`.

**Too few breakable fields**
```python
# BAD: Only 1 breakable field across 5 entities — tasks will all be identical
# You need >= min_width (usually 4-6) for diversity
```
Fix: identify more fields that could realistically go wrong. Think about what
a customer might complain about: wrong status, wrong amount, missing data, etc.

**Identity field not in fields list**
```python
# BAD: identity_field references a field that doesn't exist
EntitySpec(name="Order", identity_field="order_id", fields=[
    FieldSpec(name="status", ...),  # order_id is missing!
])
```
Fix: always include the identity field in the fields list with `mutable=False`.

**Enum field without enum_values**
```python
# BAD: type is enum but no values listed
FieldSpec(name="tier", type="enum", breakable=True,
          normal_value="gold", broken_values=["bronze"])
# Missing: enum_values=["bronze", "silver", "gold", "platinum"]
```

**Mutable identity field**
```python
# BAD: identity field should never change
FieldSpec(name="customer_id", type="str", mutable=True)
```


## Verification

`verify_schema()` checks:

| Check                 | Severity | What It Catches                                    |
|-----------------------|----------|----------------------------------------------------|
| `identity_field_exists` | ERROR  | identity_field not in entity's fields list          |
| `unique_fields`       | ERROR    | Duplicate field names within an entity              |
| `breakable_normal_value` | ERROR | Breakable field missing normal_value                |
| `breakable_broken_values` | ERROR | Breakable field missing broken_values (empty list) |
| `enum_values`         | ERROR    | Enum field with fewer than 2 enum_values            |
| `rel_entity_exists`   | ERROR    | Relationship references non-existent entity         |
| `breakable_diversity` | WARNING  | Fewer than 3 total breakable fields                 |
| `connected_graph`     | WARNING  | Orphan entities (not connected via relationships)   |


## Common Failures & Fixes

**"breakable_normal_value" error**: Every breakable field needs a `normal_value`.
This is what the field should be in the "correct" state. For enums, it's the
default/good value. For ints, it's the correct amount. For bools, it's the
expected state.

**"breakable_diversity" warning**: Think harder about what can go wrong in the
domain. In a coffee shop: account status, order status, order total, loyalty
points, loyalty tier, subscription status, subscription charge, menu item
availability — that's 8 breakable fields across 5 entities.

**"connected_graph" warning**: Make sure every entity is reachable from at least
one other entity. If you have a MenuItem entity, it should be referenced from
OrderItem or similar. Orphan entities can't participate in gated traversals.
