# Step 4: Rules + Constraints

## Purpose

Define business rules that constrain what actions are valid. Rules are richer
than gates: gates control **information flow** (what the agent can see), while
rules control **action validity** (what the agent can do in a given state).

Rules make the world feel real and create non-obvious constraints that test
the agent's reasoning about preconditions and protocols.


## Input (locked from Steps 1-3)

- Full schema with all entities, fields, and types (Step 2)
- Relationships and gates (Step 3)
- Entity names and topology targets (Step 1)


## Output

A list of `Rule` objects.

### Rule
```
description: str          # Natural language description of the rule
entity: str               # Which entity this rule applies to
field: str = None         # Which field (optional)
condition_entity: str = None  # Entity whose state triggers the rule (optional)
condition_field: str = None   # Field on condition entity (optional)
condition_value: Any = None   # Triggering value (optional)
```


## Constraints

- Every rule must reference existing entities and fields from the schema
- Rules must not contradict each other
- **Rules must not make breakable fields permanently unfixable** — if a field
  is breakable, there must be SOME state where it can be changed back to normal
- Use rules for things that CAN'T be expressed as simple edge gates


## When to Use Rules vs. Gates

| Mechanism | Controls                | Example                                           |
|-----------|------------------------|---------------------------------------------------|
| **Gate**  | Information flow       | "Can't see orders if account suspended"            |
| **Rule**  | Action validity        | "Can't modify order total if order is completed"   |
| **Rule**  | Business logic         | "Loyalty points cannot go below 0"                 |
| **Rule**  | Protocols              | "Must verify identity before accessing details"    |
| **Rule**  | Computed constraints   | "Subscription charge must be one of [14.99, 29.99, 49.99]" |


## Examples

### Coffee Shop Rules
```python
rules = [
    Rule(
        description="Cannot modify order total if order status is completed",
        entity="Order",
        field="total",
        condition_entity="Order",
        condition_field="status",
        condition_value="completed"
    ),
    Rule(
        description="Loyalty points cannot go below 0",
        entity="LoyaltyAccount",
        field="points"
    ),
    Rule(
        description="Subscription monthly charge must be one of [14.99, 29.99, 49.99]",
        entity="Subscription",
        field="monthly_charge"
    ),
    Rule(
        description="Must verify customer identity before accessing account details",
        entity="Customer"
    ),
]
```

### SRE Infrastructure Rules
```python
rules = [
    Rule(
        description="Cannot delete pods while deployment rollout is in progress",
        entity="Pod",
        condition_entity="Deployment",
        condition_field="rollout_status",
        condition_value="in_progress"
    ),
    Rule(
        description="ConfigMap data must be valid JSON or key-value pairs",
        entity="ConfigMap",
        field="data"
    ),
    Rule(
        description="Cannot scale deployment above namespace resource quota",
        entity="Deployment",
        field="replicas",
        condition_entity="Namespace",
        condition_field="resource_quota"
    ),
]
```

### Data Pipeline Rules
```python
rules = [
    Rule(
        description="Cannot retry a stage while its source database is disconnected",
        entity="Stage",
        condition_entity="SourceDB",
        condition_field="status",
        condition_value="disconnected"
    ),
    Rule(
        description="Cannot refresh dashboard if underlying warehouse tables are stale",
        entity="Dashboard",
        condition_entity="Table",
        condition_field="freshness",
        condition_value="stale"
    ),
]
```


## Anti-Patterns

**Rule makes a breakable field permanently unfixable**
```python
# BAD: If account_status is breakable but this rule makes it impossible
# to change it back when some condition is met, tasks become unsolvable.
Rule(
    description="Account status cannot be changed if account is frozen",
    entity="Customer",
    field="account_status",
    condition_field="account_status",
    condition_value="frozen"
)
# "frozen" is a broken_value for account_status — but this rule says
# you can't change it when it's frozen. Circular!
```

**Rule references non-existent field**
```python
# BAD: "priority" doesn't exist on Order entity
Rule(description="High priority orders processed first",
     entity="Order", field="priority")
```

**Contradictory rules**
```python
# BAD: Rule 1 says X must happen, Rule 2 says X can't happen
Rule(description="Must update order status after fixing items", entity="Order")
Rule(description="Cannot update order status while items are pending", entity="Order")
```


## Verification

`verify_rules()` checks:

| Check                       | Severity | What It Catches                           |
|-----------------------------|----------|-------------------------------------------|
| `rule_entity_exists`        | ERROR    | Rule references entity not in schema       |
| `rule_field_exists`         | ERROR    | Rule references field not on entity        |
| `rule_condition_entity_exists`| ERROR  | Condition entity not in schema             |
| `rule_condition_field_exists` | ERROR  | Condition field not on condition entity    |
| `rule_not_unfixable`        | ERROR    | Breakable field made immutable by rule     |


## Common Failures & Fixes

**"rule_not_unfixable" error**: The rule makes a breakable field impossible to
fix. Rewrite the rule so there's always a valid path to restore the field.
For example, instead of "can't change status when frozen", use "must unfreeze
account through admin tool before changing status" — this preserves the
constraint while allowing a fix path.

**Keep it light**: Most domains need 3-8 rules. Don't over-specify. Rules
exist to add realism and catch edge cases, not to describe the entire domain.
The graph structure + gates already provide most of the constraints.
