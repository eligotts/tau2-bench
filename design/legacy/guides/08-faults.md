# Step 8: Fault Declarations

**This is the second most critical step (after gates).** Faults define what can
go wrong in the world, grouped for composition safety. If faults are well-designed,
the task generator produces diverse, correct tasks. If they violate composition
rules, tasks fail at runtime.


## Purpose

Declare what can break (perturbations), which tool fixes each break, and how
breaks group together. The task generator selects combinations of fault groups
to compose into tasks. Composition safety (no shared tools, no shared fields
across groups) is verified here.

The key insight: you don't declare dependencies between faults. Dependencies
emerge from the gate structure (Step 3). A fault on a deep node is automatically
hidden behind gates. The task generator handles this.


## Input (locked from Steps 1-7)

- Full schema with breakable fields and their normal/broken values (Step 2)
- Gates that create depth (Step 3)
- Tool suite with fix tools (Step 6)
- Everything from prior steps


## Output

A `FaultSpace` object.

### FaultSpace (extends PerturbationSpace)
```
groups: list[FaultGroup]         # 8-10 groups for diversity
field_ownership: dict[str, str]  # {"Customer.account_status": "account_issues"}
tool_ownership: dict[str, str]   # {"update_customer_account_status": "account_issues"}
min_perturbations: int = 1       # Min faults per task
max_perturbations: int = 5       # Max faults per task
max_total_tasks: int = 400       # Budget cap
required_groups: list[str] = []  # Groups that must appear in every task
resolution_instruction: str      # Single outcome sentence (stopping criterion)
tool_grounding_block: str = ""   # Domain-level constant appended to all tasks
```

### FaultGroup (extends PerturbationGroup)
```
name: str                                  # e.g. "account_issues"
category: str                              # Semantic tag: "account", "billing", "connectivity"
perturbations: list[FaultDeclaration]      # What can break (mutually exclusive within group)
resource_scope: str = None                 # Scope prefix for conflict detection
unfixable_fault: UnfixableFault = None     # Fault agent can't fix (must transfer)
user_confirmation: UserConfirmation = None # User action after agent fix
diagnostics: list[DiagnosticStep] = []     # READ actions before fixing
```

### FaultDeclaration (extends PerturbationSpec)
```
name: str                    # e.g. "suspended_account"
description: str             # What the problem looks like (user-visible)
fixed_description: str       # What "fixed" looks like (completion fragment)
entity: str                  # Entity type name
field: str                   # Field name
broken_value: Any            # What value to set (from field's broken_values)
fix_tool: str                # Tool that fixes this fault
fix_args: dict[str, str]     # Tool arguments (can use {field} templates)
fixer: str = "agent"         # "agent" or "user"
check_field: str = None      # Check a different field than the broken one (rare)
check_value: Any = None      # Expected value for check_field
requires_field: str = None   # Only applies if entity has this field truthy
requires_ne: tuple = None    # Only applies if entity[field] != value
```

### UnfixableFault
```
name: str
description: str
entity: str
field: str
broken_value: Any
preservation_check: bool = True  # Verify field stays broken (wasn't incorrectly fixed)
```

### UserConfirmation
```
tool_name: str               # User tool to call after agent fix
args: dict[str, str] = {}
check_func: str = None       # Verification function
check_args: dict[str, str] = {}
```

### DiagnosticStep
```
tool_name: str               # READ tool to call before fixing
args: dict[str, str] = {}
gate_tier: int = 0           # Which depth tier this diagnostic belongs to
```


## Constraints

### CRITICAL Composition Rules

- **No two groups may share a fix_tool** — if two groups use the same tool to fix
  different faults, composing them causes no-op actions and wrong confirmations
- **No two groups may modify the same entity.field** — if group A breaks Customer.status
  and group B also breaks Customer.status, composing them is undefined
- **tool_ownership dict must be populated** — maps each fix_tool to its group name
- **field_ownership dict must be populated** — maps each "Entity.field" to its group name

### Other Constraints
- Every perturbation's entity and field must exist in the schema
- Every field must be marked breakable in the schema
- broken_value must be one of the field's broken_values from Step 2
- fix_tool must exist in the tool suite (Step 6)
- Target 8-10 groups for diversity (WARNING if <4)
- Every group should have a distinct `category`
- `resolution_instruction` should cover all categories
- `fixed_description` must be non-empty on ALL faults (fixable and unfixable)


## Examples

### Coffee Shop Fault Groups
```python
FaultSpace(
    groups=[
        FaultGroup(
            name="account_issues",
            category="account",
            perturbations=[
                FaultDeclaration(
                    name="suspended_account",
                    description="Customer's account is suspended",
                    fixed_description="account has been reactivated",
                    entity="Customer",
                    field="account_status",
                    broken_value="suspended",
                    fix_tool="update_customer_account_status",
                    fix_args={"customer_id": "{customer_id}",
                              "account_status": "active"}
                ),
                FaultDeclaration(
                    name="frozen_account",
                    description="Customer's account is frozen",
                    fixed_description="account has been unfrozen",
                    entity="Customer",
                    field="account_status",
                    broken_value="frozen",
                    fix_tool="update_customer_account_status",
                    fix_args={"customer_id": "{customer_id}",
                              "account_status": "active"}
                ),
            ],
            user_confirmation=UserConfirmation(
                tool_name="acknowledge_resolution"
            ),
        ),
        FaultGroup(
            name="order_status_issues",
            category="orders",
            perturbations=[
                FaultDeclaration(
                    name="cancelled_order",
                    description="Customer's order shows as cancelled",
                    fixed_description="order status has been corrected",
                    entity="Order",
                    field="status",
                    broken_value="cancelled",
                    fix_tool="update_order_status",
                    fix_args={"order_id": "{order_id}",
                              "status": "completed"}
                ),
            ],
        ),
        FaultGroup(
            name="loyalty_points_issues",
            category="loyalty",
            perturbations=[
                FaultDeclaration(
                    name="missing_points",
                    description="Customer's loyalty points are missing",
                    fixed_description="loyalty points have been restored",
                    entity="LoyaltyAccount",
                    field="points",
                    broken_value=0,
                    fix_tool="update_loyalty_account_points",
                    fix_args={"loyalty_id": "{loyalty_id}",
                              "points": "{correct_points}"}
                ),
            ],
        ),
        # ... more groups for: loyalty_tier, subscription_status,
        #     subscription_billing, menu_availability (unfixable)
    ],
    field_ownership={
        "Customer.account_status": "account_issues",
        "Order.status": "order_status_issues",
        "LoyaltyAccount.points": "loyalty_points_issues",
    },
    tool_ownership={
        "update_customer_account_status": "account_issues",
        "update_order_status": "order_status_issues",
        "update_loyalty_account_points": "loyalty_points_issues",
    },
    resolution_instruction="all your account, order, loyalty, and subscription "
                          "issues have been resolved",
    min_perturbations=1,
    max_perturbations=4,
)
```

### SRE Fault Groups (agent-only, no user confirmation)
```python
FaultGroup(
    name="configmap_issues",
    category="configuration",
    perturbations=[
        FaultDeclaration(
            name="wrong_db_host",
            description="ConfigMap has wrong database connection string",
            fixed_description="database configuration has been corrected",
            entity="ConfigMap",
            field="db_host",
            broken_value="wrong-host.internal",
            fix_tool="update_configmap",
            fix_args={"configmap_id": "{configmap_id}",
                      "key": "DB_HOST",
                      "value": "prod-db.internal"}
        ),
    ],
    diagnostics=[
        DiagnosticStep(tool_name="kubectl_logs",
                       args={"pod_id": "{pod_id}"},
                       gate_tier=2),
    ],
),
FaultGroup(
    name="replica_issues",
    category="scaling",
    perturbations=[
        FaultDeclaration(
            name="zero_replicas",
            description="Deployment scaled to zero replicas",
            fixed_description="deployment has been scaled back up",
            entity="Deployment",
            field="replicas",
            broken_value=0,
            fix_tool="kubectl_scale",
            fix_args={"deployment_id": "{deployment_id}",
                      "replicas": "3"}
        ),
    ],
),
```

### Unfixable Fault Example
```python
FaultGroup(
    name="menu_availability",
    category="menu",
    perturbations=[],  # No fixable faults in this group
    unfixable_fault=UnfixableFault(
        name="item_unavailable",
        description="Requested menu item is out of stock",
        entity="MenuItem",
        field="available",
        broken_value=False,
        preservation_check=True  # Verify agent didn't wrongly mark as available
    ),
)
```


## Anti-Patterns

**Two groups sharing a fix_tool**
```python
# BAD: Both groups use update_order_status
FaultGroup(name="order_cancel", perturbations=[
    FaultDeclaration(fix_tool="update_order_status", ...)])
FaultGroup(name="order_delay", perturbations=[
    FaultDeclaration(fix_tool="update_order_status", ...)])
```
When both are composed into one task, the agent calls `update_order_status`
once — which fault did it fix? The evaluator can't tell. Runtime failures.

Fix: put related faults in the SAME group (mutually exclusive), or use
different tools. If `order_cancel` and `order_delay` both modify `Order.status`,
they belong in ONE group with two alternative FaultDeclarations.

**Two groups modifying the same field**
```python
# BAD: Both groups break Customer.status
FaultGroup(name="suspension", perturbations=[
    FaultDeclaration(entity="Customer", field="status", broken_value="suspended")])
FaultGroup(name="freezing", perturbations=[
    FaultDeclaration(entity="Customer", field="status", broken_value="frozen")])
```
These must be in the SAME group — they're alternative states of the same field.

**Empty fixed_description**
```python
# BAD: No completion fragment — user sim doesn't know when to stop
FaultDeclaration(name="wrong_total", fixed_description="", ...)
```
Fix: always set `fixed_description` to describe the user-observable "fixed" state.

**Prescriptive resolution_instruction**
```python
# BAD: Tells the agent what to do instead of describing the outcome
resolution_instruction="Use update_account_status to fix the account, then..."
```
Fix: describe the OUTCOME, not the process: "all your account and order issues
have been resolved".


## Verification

Two verification passes run:

### `verify_perturbation_space()` (framework-level)

| Check              | Severity | What It Catches                              |
|--------------------|----------|----------------------------------------------|
| `entity_exists`    | ERROR    | Perturbation references non-existent entity   |
| `field_exists`     | ERROR    | Perturbation references non-existent field    |
| `field_breakable`  | ERROR    | Field is not marked breakable                 |
| `field_exclusivity`| ERROR    | Same field modified by 2+ groups              |
| `group_count`      | WARNING  | Fewer than 4 groups                           |

### `verify_fault_space()` (tau2-level)

| Check                  | Severity | What It Catches                          |
|------------------------|----------|------------------------------------------|
| `fix_tool_exists`      | ERROR    | fix_tool not in tool suite               |
| `tool_exclusivity`     | ERROR    | Same fix_tool used by 2+ groups          |
| `user_confirm_tool_exists` | ERROR | UserConfirmation tool not in user tools |
| `diagnostic_tool_exists`   | ERROR | DiagnosticStep tool not a READ tool     |
| `resolution_coverage`  | WARNING  | Group category not in resolution_instruction |
| `completion_fragment`  | WARNING  | Empty fixed_description on any fault      |
| `group_count`          | WARNING  | Fewer than 4 fault groups                 |


## Common Failures & Fixes

**"field_exclusivity" error**: Two groups modify the same Entity.field. Move the
faults into the same group as alternative FaultDeclarations (mutually exclusive
within a group).

**"tool_exclusivity" error**: Two groups use the same fix_tool. Either merge the
groups, or create distinct fix tools for each. For example, if both groups use
`update_order_status`, you might need `reactivate_order` and `update_order_shipping`
as separate tools.

**"fix_tool_exists" error**: The tool name in fix_tool doesn't match any tool in
the suite from Step 6. Check the auto-derived tool names — they follow the pattern
`update_{entity}_{field}` using snake_case versions of the entity and field names.

**"group_count" warning**: Add more fault groups. Think about what else can go wrong
in the domain. Each breakable field is a candidate for a fault group. Target 8-10
groups with distinct semantic categories.

**"resolution_coverage" warning**: Update `resolution_instruction` to mention every
group's category. If you have groups with categories "account", "orders", "loyalty",
"subscription", and "menu", the resolution instruction should reference all five.
