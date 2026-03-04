# Step 6: Tools

## Purpose

Define the tool interface the agent (and user) will use to interact with the
world graph. Most tools are **auto-derived** from the schema — no LLM needed.
You only author **custom tools**: domain-specific operations that can't be
mechanically derived.

This is the step where the graph becomes executable.


## Input (locked from Steps 1-5)

- Full schema with entities, fields, types (Steps 1-2)
- Relationships and gates (Step 3)
- Rules (Step 4)
- Seed data (Step 5)


## Output

Standard tools are produced by `derive_tool_signatures(schema)` — pure code.
You optionally produce a list of custom `ToolSignatureSpec` objects.

### What Gets Auto-Derived

For each entity in the schema, the code generates:

| Pattern                        | Tool Type  | Role  | When Generated              |
|-------------------------------|------------|-------|-----------------------------|
| `get_{entity}({id_field})`     | READ       | agent | Every entity                |
| `update_{entity}_{field}({id}, {field})` | WRITE | agent | Every mutable field  |
| `set_{entity}_{field}({id}, {field})`   | INIT  | system | Every breakable field |
| `assert_{entity}_{field}({id}, expected)` | ASSERTION | system | Every breakable field |
| `acknowledge_resolution()`     | WRITE      | user  | Always (one per domain)     |

Example for a Customer entity with fields `account_status` (mutable, breakable)
and `email` (mutable, not breakable):
```
get_customer(customer_id)                        → READ agent
update_customer_account_status(customer_id, account_status) → WRITE agent
update_customer_email(customer_id, email)        → WRITE agent
set_customer_account_status(customer_id, account_status)   → INIT system
assert_customer_account_status(customer_id, expected)      → ASSERTION system
```

### Gate-Aware Tools

Auto-derived READ tools (`get_{entity}`) should respect gate conditions from
Step 3. If `Customer → Order` is gated by `account_status == "active"`, then
`get_order(order_id)` should fail/return limited info when the customer's
account is suspended.

### ToolSignatureSpec (for custom tools)
```
name: str           # snake_case tool name
role: str           # "agent" | "user"
access: str         # "read" | "write"
description: str    # What this tool does
params: list[ToolParam]  # Parameters
returns: str        # Return type description
entity: str = None  # Which entity it operates on (optional)
field_name: str = None  # Which field (optional)
```

### ToolParam
```
name: str
type: str           # Python type: "str", "int", "float", "bool"
description: str
required: bool = True
```


## When Custom Tools Are Needed

Most domains need 0-5 custom tools. You need a custom tool when:

1. **Computed operations** — the tool COMPUTES a result from the graph, not just reads a field
2. **Domain-specific logic** — the operation is semantically meaningful in the domain
3. **Escalation / routing** — transfer to specialist, escalate issue
4. **Multi-entity operations** — operations that span multiple entities at once

### Examples of Custom Tools

**Calendar: check_availability (computed READ)**
```python
ToolSignatureSpec(
    name="check_availability",
    role="agent", access="read",
    description="Compute free time slots for a person in a date range",
    params=[
        ToolParam(name="person_id", type="str", description="Person to check"),
        ToolParam(name="date_range", type="str", description="Date range to check"),
    ],
    returns="List of available time slots",
    entity="Calendar"
)
```
This can't be derived from schema — it requires scanning events and computing gaps.

**SRE: kubectl_logs (domain-specific READ)**
```python
ToolSignatureSpec(
    name="kubectl_logs",
    role="agent", access="read",
    description="Get container logs from a pod",
    params=[
        ToolParam(name="pod_id", type="str", description="Pod name"),
        ToolParam(name="container", type="str", description="Container name",
                  required=False),
    ],
    returns="Log output text",
    entity="Pod"
)
```

**General: transfer_to_specialist (escalation WRITE)**
```python
ToolSignatureSpec(
    name="transfer_to_specialist",
    role="agent", access="write",
    description="Transfer the case to a human specialist",
    params=[
        ToolParam(name="reason", type="str", description="Why transferring"),
        ToolParam(name="department", type="str", description="Target department"),
    ],
    returns="Transfer confirmation"
)
```


## Anti-Patterns

**Custom tool duplicates a derived tool**
```python
# BAD: This is exactly what get_customer() already does
ToolSignatureSpec(name="lookup_customer", role="agent", access="read",
                  description="Look up customer by ID", ...)
```
Fix: don't add custom tools for operations the derivation already covers.

**Tool bypasses a gate condition**
```python
# BAD: This tool lets the agent see orders even when account is suspended
# — it circumvents the account_status gate on Customer → Order
ToolSignatureSpec(name="get_all_orders_admin", role="agent", access="read",
                  description="Get all orders for any customer regardless of status")
```
Fix: respect gate conditions. Gate-bypassing tools destroy progressive disclosure.


## Verification

No formal verification step for derived tools (they're mechanically correct).
For custom tools, verify:
- Tool names don't conflict with derived tool names
- Parameters reference valid types
- Entity and field_name (if specified) exist in schema


## Common Failures & Fixes

**Too many custom tools**: If you're writing >5 custom tools, you're probably
reimplementing what derived tools already do. Check the derived list first.

**Missing user tools**: For domains with user interaction (actor gates), you
need user-callable tools that satisfy the gates. The `acknowledge_resolution()`
tool is auto-derived, but you may need tools like `verify_identity()`,
`restart_device()`, `sign_documents()` depending on your actor gates from Step 3.
