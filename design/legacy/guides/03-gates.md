# Step 3: Relationships + Gates

**This is the most important step.** Gates are the mechanism that creates task
depth, progressive disclosure, and dependency chains. If gates are wrong, tasks
are flat and boring. If gates are right, complex multi-step reasoning emerges
automatically from the graph structure.


## Purpose

Define edges between entity types (relationships) and gate conditions on those
edges. A gate on an edge means: a field on the source entity must have a specific
value before the agent can traverse to the target entity.

This step is separate from Step 2 because:
1. You need to see ALL entities' fields before defining cross-entity gates
2. Gates are the depth-creating mechanism — they deserve focused verification
3. It makes graph structure explicit and checkable, not implicit in code


## Input (locked from Steps 1-2)

- Entity names (Step 1) — cannot add new entities
- All fields on all entities (Step 2) — cannot add new fields
- Breakable fields with their normal/broken values (Step 2)
- Topology targets: `min_depth`, `gating_density` (Step 1)


## Output

A list of `GatedRelationship` objects.

### GatedRelationship
```
relationship: RelationshipSpec
gate: Gate (PropertyGate | ActorGate | InformationGate | CompoundGate)
description: str   # Human-readable gate description
```

### RelationshipSpec
```
from_entity: str       # Source entity name
to_entity: str         # Target entity name
cardinality: str       # "1:1" | "1:N" | "N:M"
foreign_key: str       # Field name used for the join
description: str
```

### Gate Types

**PropertyGate** — field value controls traversal
```
gate_type: "property"
entity: str            # Source entity (where the gate field lives)
field: str             # Field name (MUST be breakable)
required_value: Any    # Value needed to traverse
```

**ActorGate** — requires action from user or external system
```
gate_type: "actor"
actor: str             # "user" or system name
field: str             # Field on actor's state
required_value: Any    # Usually True
trigger_tool: str      # Tool the actor calls to satisfy gate (optional)
```

**InformationGate** — agent must know something before proceeding
```
gate_type: "information"
source_entity: str     # Where the info lives
source_field: str      # Which field holds the info
description: str       # What agent needs to know
```

**CompoundGate** — AND of multiple conditions
```
gate_type: "compound"
conditions: list[PropertyGate | ActorGate | InformationGate]
```


## The Core Mechanism: How Gates Create Depth

```
Entry Point: Customer
  │
  ├──[account_status == "active"]──> Order          ← Depth 1 gate
  │                                    │
  │                                    ├──[status != "cancelled"]──> OrderItem  ← Depth 2 gate
  │                                    │
  │                                    └── (order fields visible)
  │
  ├──[User.identity_verified == true]──> LoyaltyAccount  ← Actor gate
  │
  └──[User.identity_verified == true]──> Subscription    ← Actor gate
```

If you break `account_status` to "suspended":
- Agent can NOT traverse Customer → Order
- Agent can NOT see Order's fields or anything beyond Order
- Agent MUST fix account_status before discovering downstream problems

**Depth = number of sequential gates from entry to deepest perturbation.**

The task generator exploits this: break deep nodes first, then break the gate
fields that hide them. The agent discovers and fixes in the reverse order.


## Constraints

- All entities referenced must exist in the schema (Step 2)
- Gate fields must exist on the gate's entity
- **Gate fields should be breakable** — if a gate field isn't breakable, the gate
  can never close, so it adds no depth. This is a WARNING, not an error.
- Graph must be connected (no orphan entities)
- **No circular gate dependencies** — if A gates B and B gates A, no task is solvable
- Depth must meet `topology.min_depth` target
- Gating density should match target ("low" = few gated edges, "high" = most gated)


## Examples

### Customer Service (property + actor gates, depth 3)
```python
gated_relationships = [
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Customer", to_entity="Order",
            cardinality="1:N", foreign_key="customer_id",
            description="Customer's orders"),
        gate=PropertyGate(entity="Customer", field="account_status",
                          required_value="active"),
        description="Can't see orders if account is suspended"
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Order", to_entity="OrderItem",
            cardinality="1:N", foreign_key="order_id",
            description="Items in an order"),
        gate=PropertyGate(entity="Order", field="status",
                          required_value="completed"),
        description="Can't see items of cancelled orders"
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Customer", to_entity="LoyaltyAccount",
            cardinality="1:1", foreign_key="customer_id",
            description="Customer's loyalty account"),
        gate=ActorGate(actor="user", field="identity_verified",
                       required_value=True,
                       trigger_tool="verify_identity"),
        description="Must verify identity before accessing loyalty details"
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Customer", to_entity="Subscription",
            cardinality="1:1", foreign_key="customer_id",
            description="Customer's subscription"),
        gate=ActorGate(actor="user", field="identity_verified",
                       required_value=True,
                       trigger_tool="verify_identity"),
        description="Must verify identity before accessing subscription"
    ),
]
# Depth: Customer → Order (1 gate) → OrderItem (2 gates) = depth 2
# Plus actor gates for parallel branches
```

### SRE Infrastructure (all property gates, depth 4)
```python
gated_relationships = [
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Cluster", to_entity="Namespace",
            cardinality="1:N", foreign_key="cluster_id",
            description="Namespaces in cluster"),
        gate=PropertyGate(entity="Cluster", field="status",
                          required_value="reachable"),
        description="Can't see namespaces if cluster unreachable"
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Deployment", to_entity="Pod",
            cardinality="1:N", foreign_key="deployment_id",
            description="Pods managed by deployment"),
        gate=PropertyGate(entity="Deployment", field="replicas",
                          required_value=3),  # replicas > 0
        description="No pods visible if replicas scaled to 0"
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Service", to_entity="Ingress",
            cardinality="1:1", foreign_key="service_id",
            description="Ingress for service"),
        gate=PropertyGate(entity="Service", field="type",
                          required_value="LoadBalancer"),
        description="Ingress only exists for LoadBalancer services"
    ),
    # Depth chain: Cluster → Namespace → Deployment → Pod → (logs)
    # = 4 sequential gates if all gate fields are broken
]
```

### HR Onboarding (mixed actor + property, depth 3)
```python
gated_relationships = [
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Employee", to_entity="ITSetup",
            cardinality="1:1", foreign_key="employee_id",
            description="IT provisioning for employee"),
        gate=ActorGate(actor="manager", field="approval_given",
                       required_value=True,
                       trigger_tool="request_manager_approval"),
        description="IT setup blocked until manager approves hire"
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="ITSetup", to_entity="VPNConfig",
            cardinality="1:1", foreign_key="it_setup_id",
            description="VPN configuration"),
        gate=PropertyGate(entity="ITSetup", field="accounts_created",
                          required_value=True),
        description="VPN needs accounts created first"
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            from_entity="Employee", to_entity="PayrollRecord",
            cardinality="1:1", foreign_key="employee_id",
            description="Payroll setup"),
        gate=ActorGate(actor="user", field="documents_signed",
                       required_value=True,
                       trigger_tool="sign_documents"),
        description="Payroll blocked until new hire signs documents"
    ),
    # Depth: Manager approval → IT Setup → VPN = depth 2 (actor then property)
    # Parallel: Payroll branch blocked by user signing
]
```


## Anti-Patterns

**All edges ungated (flat tasks)**
```python
# BAD: No gates at all — every entity is immediately visible
# Tasks will be depth 1: see problem, fix problem. No progressive disclosure.
gated_relationships = [
    GatedRelationship(
        relationship=RelationshipSpec("Customer", "Order", "1:N", "customer_id", ""),
        gate=None,  # NO GATE
        description=""
    ),
]
```
Fix: add PropertyGates on breakable fields. Think about what must be true before
you can access downstream data.

**Circular gate dependencies**
```python
# BAD: A gates B and B gates A — unsolvable
GatedRelationship(
    ..., gate=PropertyGate(entity="A", field="x", required_value="ok")),
GatedRelationship(
    ..., gate=PropertyGate(entity="B", field="y", required_value="ok")),
# If x is broken AND y is broken, neither can be fixed
```
Fix: gate dependencies must form a DAG (directed acyclic graph). One entity's
field can gate another, but not the reverse.

**Gate field is not breakable**
```python
# BAD: account_type is not breakable, so this gate can never close
# The edge is always either open or always closed — adds no task depth
gate=PropertyGate(entity="Customer", field="account_type",
                  required_value="premium")
# But account_type has breakable=False in the schema
```
Fix: use breakable fields for gates. If you want a field to be a gate, go back
to Step 2 and mark it breakable with normal_value and broken_values.


## Verification

`verify_gates()` checks:

| Check               | Severity | What It Catches                                    |
|---------------------|----------|----------------------------------------------------|
| `gate_entity_exists`| ERROR    | Gate references entity not in schema               |
| `gate_field_exists` | ERROR    | Gate references field not on entity                 |
| `gate_field_breakable`| WARNING | Gate field isn't breakable (gate adds no depth)   |
| `no_circular_gates` | ERROR    | Circular dependency between gate fields             |
| `depth_target`      | WARNING  | Max depth < topology.min_depth                     |
| `gating_density`    | WARNING  | Gating density below target                         |

**This is the CRITICAL EARLY GATE.** If depth is too shallow, this step gets
re-generated with more gates. Don't wait until Step 8 to discover tasks are boring.


## Common Failures & Fixes

**"depth_target" warning (graph too shallow)**: Add more gates. Look for
relationships that should have conditions. Think about what must be true
at the source entity before accessing the target. Common patterns:
- Status fields gate downstream access (account active → can see orders)
- Approval gates block dependent workflows (manager approved → IT can start)
- Verification gates require user action (identity verified → see sensitive data)

**"no_circular_gates" error**: Rearrange which entity gates which. Gate
dependencies must be a DAG. If Customer.status gates Order access and Order.status
gates Customer access, break the cycle by removing one direction.

**"gate_field_breakable" warning**: Go back to Step 2 and mark the field as
breakable. A gate on a non-breakable field is useless — it either always blocks
or never blocks, adding no task variety.

**Shallow graph despite many entities**: Make sure gates form a CHAIN, not just
independent branches. Depth comes from sequential gates:
Customer → Order → OrderItem (depth 2) is deeper than
Customer → Order AND Customer → LoyaltyAccount (depth 1 each, parallel).
