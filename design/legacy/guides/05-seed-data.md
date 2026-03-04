# Step 5: Seed Data

## Purpose

Generate realistic records for every entity type. Seed data populates the world
graph with concrete instances that become the basis for tasks. Each task picks
an entry-point entity (e.g., a specific Customer) and perturbs fields on related
entities.

Good seed data = realistic, varied, and correctly structured.
Bad seed data = "Test User 1", broken foreign keys, breakable fields starting wrong.


## Input (locked from Steps 1-4)

- Full schema: entity names, field names, types, identity fields (Steps 1-2)
- Relationships: foreign keys between entities (Step 3)
- Rules: constraints on valid value combinations (Step 4)
- Breakable fields: normal_value for each (Step 2)


## Output

A `SeedData` object.

### SeedData
```
records: dict[str, list[dict[str, Any]]]  # {"Customer": [{...}, ...], "Order": [{...}, ...]}
min_records_per_entity: int = 8
min_enum_coverage: float = 0.8
```


## Constraints

- **Minimum 8 records per entity type** (ERROR if fewer)
- **Identity field values must be unique** within each entity (ERROR if duplicates)
- **Foreign keys must reference existing records** — if Order has customer_id,
  that customer_id must exist in Customer records (ERROR if broken)
- **Enum fields: use >=80% of enum values** across records (WARNING if less)
- **Breakable fields: ALL records must start at normal_value** (WARNING if wrong) —
  the task generator will break them; they should start correct
- **Data should be realistic and varied** — real names, realistic values,
  not "Test User 1, Test User 2"
- All rules from Step 4 should be satisfied by seed data


## Examples

### Coffee Shop Seed Data (partial)
```json
{
  "Customer": [
    {"customer_id": "C001", "name": "Maya Chen", "email": "maya.chen@email.com",
     "account_status": "active", "phone": "555-0101"},
    {"customer_id": "C002", "name": "James Rodriguez", "email": "j.rodriguez@email.com",
     "account_status": "active", "phone": "555-0102"},
    {"customer_id": "C003", "name": "Priya Patel", "email": "priya.p@email.com",
     "account_status": "active", "phone": "555-0103"},
    {"customer_id": "C004", "name": "Alex Kim", "email": "akim@email.com",
     "account_status": "active", "phone": "555-0104"},
    {"customer_id": "C005", "name": "Sarah Johnson", "email": "sjohnson@email.com",
     "account_status": "active", "phone": "555-0105"},
    {"customer_id": "C006", "name": "David Okafor", "email": "d.okafor@email.com",
     "account_status": "active", "phone": "555-0106"},
    {"customer_id": "C007", "name": "Emma Watson", "email": "ewatson@email.com",
     "account_status": "active", "phone": "555-0107"},
    {"customer_id": "C008", "name": "Carlos Mendez", "email": "cmendez@email.com",
     "account_status": "active", "phone": "555-0108"}
  ],

  "Order": [
    {"order_id": "ORD001", "customer_id": "C001", "status": "completed", "total": 24.50},
    {"order_id": "ORD002", "customer_id": "C001", "status": "completed", "total": 18.75},
    {"order_id": "ORD003", "customer_id": "C002", "status": "completed", "total": 32.00},
    {"order_id": "ORD004", "customer_id": "C003", "status": "completed", "total": 15.99},
    {"order_id": "ORD005", "customer_id": "C004", "status": "completed", "total": 42.25},
    {"order_id": "ORD006", "customer_id": "C005", "status": "completed", "total": 28.50},
    {"order_id": "ORD007", "customer_id": "C006", "status": "completed", "total": 19.99},
    {"order_id": "ORD008", "customer_id": "C007", "status": "completed", "total": 35.75}
  ],

  "LoyaltyAccount": [
    {"loyalty_id": "L001", "customer_id": "C001", "points": 1200, "tier": "gold"},
    {"loyalty_id": "L002", "customer_id": "C002", "points": 450, "tier": "silver"},
    {"loyalty_id": "L003", "customer_id": "C003", "points": 2100, "tier": "platinum"},
    {"loyalty_id": "L004", "customer_id": "C004", "points": 150, "tier": "bronze"},
    {"loyalty_id": "L005", "customer_id": "C005", "points": 800, "tier": "gold"},
    {"loyalty_id": "L006", "customer_id": "C006", "points": 50, "tier": "bronze"},
    {"loyalty_id": "L007", "customer_id": "C007", "points": 1600, "tier": "platinum"},
    {"loyalty_id": "L008", "customer_id": "C008", "points": 300, "tier": "silver"}
  ]
}
```

Key things to notice:
- All `account_status` values are `"active"` (the normal_value) — not broken
- All `order.status` values are `"completed"` (the normal_value)
- Foreign keys are valid: every `customer_id` in Order exists in Customer
- Enum coverage: LoyaltyAccount.tier uses all 4 values (bronze, silver, gold, platinum)
- Names are realistic and diverse, not "User1, User2"
- Values are varied (different point amounts, totals, tiers)


## Anti-Patterns

**"Test User" names**
```json
{"customer_id": "C001", "name": "Test User 1", "email": "test1@test.com"}
```
Fix: use realistic, diverse names from different cultural backgrounds.

**Broken foreign keys**
```json
{"order_id": "ORD001", "customer_id": "C999"}
```
Fix: C999 doesn't exist in Customer records. Use only IDs that appear in the
referenced entity's records.

**Breakable fields starting broken**
```json
{"customer_id": "C001", "account_status": "suspended"}
```
Fix: all breakable fields must start at `normal_value`. The task generator will
break them. Starting them broken means the task generator can't control
which combinations are broken.

**Missing enum coverage**
```json
// All 8 customers have tier="gold" — missing bronze, silver, platinum
```
Fix: spread enum values across records. With 8 records and 4 enum values,
use each value at least twice.


## Verification

`verify_seed_data()` checks:

| Check                   | Severity | What It Catches                                 |
|-------------------------|----------|-------------------------------------------------|
| `min_records`           | ERROR    | Fewer than min_records_per_entity (default 8)    |
| `unique_ids`            | ERROR    | Duplicate identity field values within entity    |
| `breakable_starts_normal`| WARNING | Breakable field value != normal_value            |
| `referential_integrity` | ERROR    | FK references non-existent record                |
| `enum_coverage`         | WARNING  | Enum field uses < 80% of enum_values             |


## Common Failures & Fixes

**"referential_integrity" error**: Trace the foreign key. If Order.customer_id = "C005",
make sure Customer records include one with customer_id = "C005". Usually this
means you need to ensure your record counts align: if you have 8 Customers (C001-C008),
only use customer_ids in that range for Orders.

**"breakable_starts_normal" warning**: Go through every breakable field and set
ALL records to the `normal_value` from Step 2. It's tempting to add variety
by varying these values, but don't — the task generator handles variety by
breaking fields in different combinations.

**"min_records" error**: Add more records. 8 is the minimum; 10 is better.
Each record is a potential entry point for a task, so more records = more
task diversity.
