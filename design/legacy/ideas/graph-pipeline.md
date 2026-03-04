# Graph-Based Authoring Pipeline

## Design Principles (carried forward)

1. **Small authoring surface per step** — LLM generates a small, well-typed artifact
2. **Narrowing funnel** — each step's output constrains the next step's input space
3. **Verify-then-proceed** — code + LLM verification gate between every step
4. **Derive, don't author** — anything derivable from earlier steps is derived mechanically
5. **Retry is narrow** — on failure, re-generate just the failing step

## The Problem

The previous pipeline had 9 steps that were somewhat ad-hoc. With the graph
model, we can make the steps follow a natural ontological order:

  What exists? → How is it connected? → What are the rules? →
  What data fills it? → How do actors interact? → What can break? →
  How does the agent know what to do? → Generate tasks

Each step answers one question and constrains the next.

## Pipeline Steps

### Phase 1: World Structure (format-agnostic)

#### Step 1: Concept + Topology Targets
**Authoring surface:** ~30 lines
**Author:** LLM (or human)

Input:  A domain idea (freeform) + optional topology parameters
Output: WorldConcept + TopologyTargets

The LLM names the domain, lists entity types, writes a short description.
Topology targets (width, depth, gating density) can be specified or defaulted.

```
concept:
  name: "coffee_shop"
  description: "A specialty coffee shop with orders, loyalty, subscriptions"
  entity_names: [Customer, Order, MenuItem, LoyaltyAccount, Subscription]

topology_targets:
  min_depth: 3
  min_width: 4
  gating_density: "medium"    # low / medium / high
  branching: "moderate"       # narrow / moderate / wide
```

**Verification:**
- Valid name, >=2 entities, unique names
- Topology targets are consistent (can't have depth 5 with only 2 entities)


#### Step 2: Entity Schema
**Authoring surface:** ~5-10 lines per entity
**Author:** LLM

Input:  Concept (entity names locked in)
Output: Entity definitions with typed fields

The LLM defines fields for each entity.  It CANNOT invent new entity types —
only the ones from step 1.  Each field gets type, mutable flag, breakable flag.

```
Customer:
  identity: customer_id
  fields:
    - customer_id: str (immutable)
    - name: str (immutable)
    - account_status: enum[active, suspended, frozen] (mutable, breakable)
      normal: "active"
      broken: ["suspended", "frozen"]
```

**Verification:**
- Every entity has an identity field
- Breakable fields have normal_value + broken_values
- Enough breakable fields for target width
- No duplicate field names


#### Step 3: Relationship Graph + Gates
**Authoring surface:** ~3-5 lines per relationship
**Author:** LLM

Input:  Entity schema (field names/types locked in)
Output: Relationships between entities + edge gate conditions

This is where the graph gets its SHAPE.  The LLM declares edges between
entity types, with optional gate conditions.  This is separated from step 2
because the LLM needs to see all entities' fields before it can define
cross-entity relationships and gates.

```
relationships:
  - Customer -[1:N]-> Order
    via: customer_id
    gate: account_status == "active"    # can't see orders if account suspended

  - Customer -[1:1]-> LoyaltyAccount
    via: customer_id

  - Order -[1:N]-> OrderItem
    via: order_id
    gate: order.status != "cancelled"   # can't see items of cancelled orders

  - OrderItem -[N:1]-> MenuItem
    via: item_id
```

**Verification:**
- All entities referenced exist
- Gate fields exist on the source entity and are breakable
- Graph is connected (no orphan entities)
- Depth meets topology target (longest path from any entry-point entity)
- Gating density matches target


#### Step 4: Rules + Constraints
**Authoring surface:** ~2-5 lines per rule
**Author:** LLM

Input:  Schema + relationships (structure locked in)
Output: Business rules, mutation guards, protocols

Rules that can't be expressed as simple edge gates.  These constrain what
actions are valid in what states.

```
rules:
  - "Cannot modify order.total if order.status == 'completed'"
  - "Loyalty points cannot go below 0"
  - "Subscription monthly_charge must be one of [14.99, 29.99, 49.99]"
  - "Must verify customer identity before accessing account details"
```

**Verification:**
- Every rule references existing entities/fields
- Rules are non-contradictory (no rule makes a breakable field unfixable)
- Rules use valid comparison operators
- Enough rules for target rule complexity


#### Step 5: Seed Data
**Authoring surface:** ~100-200 lines JSON
**Author:** LLM

Input:  Schema + relationships + rules (structure locked in)
Output: Realistic records conforming to schema

The LLM generates records.  The schema fully constrains field types and
valid values.  Relationships constrain foreign keys.  Rules constrain
value combinations.

**Verification:**
- Min records per entity (8-10)
- Identity uniqueness
- Referential integrity (all FKs valid)
- Enum coverage (>=80%)
- Breakable fields start at normal_value
- All rules satisfied by seed data
- Enough variety in non-breakable fields (realistic, not "Test User 1")


### Phase 2: Interaction Model (rendering-layer-specific)

From here, steps depend on the evaluation format.  For tau2:

#### Step 6: Tool Derivation + Custom Tools
**Authoring surface:** ~5-15 lines per CUSTOM tool only
**Author:** CODE (derivation) + LLM (custom tools)

Input:  Schema + relationships + rules
Output: Complete tool suite

Mechanical derivation produces CRUD tools from schema:
- get_{entity}(id) → READ for each entity type
- update_{entity}_{field}(id, value) → WRITE for each mutable field
- set_{entity}_{field}(id, value) → INIT for each breakable field
- assert_{entity}_{field}(id, expected) → ASSERTION for each breakable field
- list_{entity}(**filters) → READ

Gate-aware tools from relationships:
- get_{entity} respects edge gates (returns error if gate condition not met)

Rule-aware tools from step 4:
- WRITE tools include precondition checks from rules

The LLM only needs to author CUSTOM tools — domain-specific operations
that can't be derived (e.g., run_diagnostic, calculate_shipping,
transfer_to_specialist).  These are few (~2-5 per domain).

**Verification:**
- Every derived tool matches schema exactly
- Custom tools reference valid entities/fields
- WRITE tools have correct preconditions from rules
- Gate-respecting tools enforce gate conditions
- No duplicate tool names


#### Step 7: Projections (User Data Model + Sync)
**Authoring surface:** ~3-5 lines per bridge
**Author:** LLM

Input:  Schema + tools
Output: What the user can see + how user/agent state syncs

Declares which parts of the graph the user sees (their projection),
and how actions by one party affect the other's view.

```
user_projection:
  - Customer: [name, account_status]           # user sees these fields
  - Order: [order_id, total, status]
  - LoyaltyAccount: [points, tier]
  - Subscription: [status, monthly_charge]

sync_bridges:
  - agent updates Order.status → user sees updated order status
  - user calls restart_device → agent sees Device.restarted = true
```

**Verification:**
- Every projected field exists
- Every sync bridge references existing fields
- Every user-visible field has a sync path
- No circular bridges


#### Step 8: Perturbation Space
**Authoring surface:** ~5-7 lines per perturbation
**Author:** LLM

Input:  Schema + graph (with gates) + tools + rules
Output: What can go wrong, grouped by resource scope

The LLM declares perturbations — which fields break, to what values,
and which tool fixes them.  The graph structure (from step 3) determines
the depth: a perturbation on a node that's behind a gated edge is
automatically deep.

```
groups:
  account_issues:
    category: "account"
    perturbations:
      - suspended_account:
          entity: Customer
          field: account_status
          broken_value: "suspended"
          fix_tool: update_customer_account_status
          fix_args: {customer_id: "{customer_id}", account_status: "active"}

  order_issues:
    category: "orders"
    perturbations:
      - cancelled_order:
          entity: Order
          field: status
          broken_value: "cancelled"
          fix_tool: update_order_status
          fix_args: {order_id: "{order_id}", status: "preparing"}
```

The KEY: the LLM doesn't need to declare dependencies between perturbations.
If account_status gates the Customer → Order edge (from step 3), then
cancelled_order is automatically gated behind suspended_account.
Depth is EMERGENT from graph structure + perturbation placement.

**Verification (critical gate):**
- Every perturbation references existing entity/field/tool
- Breakable fields only
- No two groups share a fix_tool (composition safety)
- No two groups modify the same field (field exclusivity)
- 8-10 groups (diversity target)
- Perturbation placement achieves target depth (check against graph gates)
- Every gate-creating perturbation (one that breaks a field used as a gate
  condition) is flagged — these are the depth-creating perturbations


#### Step 9: Policy
**Authoring surface:** ~50-100 lines markdown
**Author:** LLM

Input:  Tools + perturbation space + rules + graph
Output: Agent instructions

Generated LAST, grounded on actual tools and faults.  The graph structure
informs the policy — e.g., "before accessing order details, verify the
customer's account is active" follows naturally from the gate conditions.

**Verification:**
- Every tool referenced exists
- Every perturbation group has a resolution path
- No prescriptive language for selective faults
- Policy doesn't reveal information the agent should discover
- Rules from step 4 are reflected in policy


### Phase 3: Task Generation (mechanical)

#### Step 10: Compose Tasks
**Authoring surface:** ZERO (pure code)
**Author:** CODE

Input:  Graph + perturbations + seed data + topology targets
Output: Task blueprints

The composition engine:
1. For each entity in seed data (entry point candidates)
2. For each valid combination of perturbations
3. Compute the traversal graph (which perturbations gate which edges)
4. Calculate depth (longest gated path from entry point)
5. Filter by depth/difficulty targets
6. Render into format-specific tasks

**Verification:**
- Every task is solvable (traversal path exists from entry to all perturbations)
- Depth matches difficulty target
- No composition conflicts
- Sufficient diversity across topology parameter space


## What the LLM Authors at Each Step (Summary)

| Step | What                        | Lines | Constrained by           |
|------|-----------------------------|-------|--------------------------|
| 1    | Concept + topology targets  | ~30   | (freeform)               |
| 2    | Entity fields               | ~50   | Entity names from step 1 |
| 3    | Relationships + gates       | ~20   | Entities+fields from 2   |
| 4    | Business rules              | ~20   | Schema+rels from 2-3     |
| 5    | Seed data records           | ~150  | Full schema from 2-4     |
| 6    | Custom tools only (~3-5)    | ~30   | Schema+rules from 2-4    |
| 7    | Projections + sync bridges  | ~20   | Tools from step 6        |
| 8    | Perturbation declarations   | ~50   | Tools+schema from 2-6    |
| 9    | Policy prose                | ~80   | Everything from 1-8      |
| 10   | (nothing — pure code)       | 0     | Everything from 1-9      |

Total LLM authoring: ~450 lines across 9 steps, each step constrained by all
previous steps.  Compare to current approach: ~1000+ lines across 10 tightly
coupled files authored simultaneously.


## Why Separating Relationships (Step 3) from Schema (Step 2) Matters

In the previous pipeline, relationships were part of the schema step.  But
relationships are WHERE THE GRAPH STRUCTURE LIVES.  Gates especially need
their own step because:

1. The LLM needs to see ALL entities' fields before deciding which fields
   gate which edges.  You can't define "Customer → Order gated by
   account_status" until you know Customer has an account_status field.

2. Gates are the depth-creating mechanism.  Verifying that the graph meets
   depth targets requires checking the gate structure — that's a separate
   concern from "do the fields have valid types."

3. It makes the graph structure EXPLICIT and verifiable, rather than implicit
   in scenarios.py code.


## Why Rules (Step 4) Are Separate from Gates (Step 3)

Gates are simple: "field == value to traverse this edge."  Rules are richer:
"cannot modify X if Y is in state Z" or "must do A before B."

Gates control INFORMATION FLOW (what the agent can see).
Rules control ACTION VALIDITY (what the agent can do).

Both constrain the task, but they're verified differently:
- Gates: checked by graph traversal analysis
- Rules: checked by precondition analysis on tools

Keeping them separate means each verification gate is focused.


## The Key Verification Moments

1. **After step 3 (graph structure):** Can verify depth/width/gating targets
   are met.  If the graph is too shallow, re-generate relationships with
   more gates.  Don't wait until step 8 to discover the tasks are boring.

2. **After step 6 (tools):** Can verify tools respect gates and rules.
   A tool that bypasses a gate condition breaks progressive disclosure.

3. **After step 8 (perturbations):** Can verify composition safety AND depth.
   "These perturbation placements achieve depth 3 because perturbation X
   breaks the gate field on edge Y, hiding perturbation Z."

4. **After step 10 (tasks):** Can verify every task is solvable by simulating
   the traversal.  Start at entry point, follow edges (respecting gates),
   fix perturbations in reachable order, verify all perturbations resolved.


## Depth Verification: The New Critical Check

Previous system verified COMPOSITION safety (no field conflicts, no shared
tools).  New system also verifies DEPTH:

```
For each task blueprint:
  1. Start at entry point
  2. Which nodes are reachable? (traverse ungated edges)
  3. Which perturbations are on reachable nodes? (these are visible)
  4. If agent fixes perturbation P, does that ungate any edges?
     (P.field is a gate_field on some relationship)
  5. If yes: new nodes become reachable, new perturbations become visible
  6. Repeat until all perturbations are reachable
  7. If any perturbation is NEVER reachable: TASK IS UNSOLVABLE → ERROR

This is a graph reachability analysis that runs as code, not LLM.
It catches the case where the LLM placed a perturbation behind a
gate that no other perturbation can open.
```
