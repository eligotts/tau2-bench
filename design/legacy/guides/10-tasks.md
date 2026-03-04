# Step 10: Task Generation

## Purpose

Generate tasks from the world graph. **This step is pure code — no LLM authoring.**
If Steps 1-9 are correct, task generation is mechanical and produces tasks that
are solvable by construction.

This guide is a reference for understanding what the code does, not instructions
for what to write.


## What Happens

Three operations run in sequence:

### 1. Build Flattened Entities
`derive_entity_builder(schema)` creates a join function that transforms seed
data records into flattened entity dicts. Each flattened entity contains fields
from the root entity plus related entities joined via foreign keys.

```
Input:  {"Customer": [{...}], "Order": [{...}], "LoyaltyAccount": [{...}]}
Output: [{"customer_id": "C001", "name": "Maya Chen", "order_id": "ORD001",
          "order_status": "completed", "loyalty_id": "L001", "points": 1200,
          "correct_points": 1200, "correct_account_status": "active", ...}]
```

Notice `correct_*` fields: for every breakable field, the builder adds the
normal_value as a template value. These are used in fix_args templates like
`{"points": "{correct_points}"}`.

### 2. Compose Blueprints
`compose_blueprints(space, entities, entity_id_field, seed)` generates task
blueprints by combining fault groups:

- Select 1-N groups (controlled by `min_perturbations` / `max_perturbations`)
- From each selected group, pick one fault declaration (mutually exclusive within group)
- Apply to each entity in the seed data
- Filter by `max_total_tasks` budget

Each `TaskBlueprint` contains:
- `task_id`: identifier
- `entity`: the flattened entity record (entry point)
- `perturbations`: list of PerturbationSpec (what's broken)
- `goals`: list of GoalPredicate (what "fixed" looks like)
- `difficulty`: derived from perturbation count

### 3. Render to tau2 Format
`render_tau2_task(blueprint, fault_space, schema)` converts each blueprint to
a tau2-compatible task dict:

```python
{
    "id": "coffee_shop_C001_2faults_seed42",
    "initial_state": {
        "initialization_actions": [
            # Break account_status to "suspended"
            {"env_type": "assistant",
             "func_name": "set_customer_account_status",
             "arguments": {"customer_id": "C001", "account_status": "suspended"}},
            # Break points to 0
            {"env_type": "assistant",
             "func_name": "set_loyalty_account_points",
             "arguments": {"loyalty_id": "L001", "points": 0}},
        ]
    },
    "evaluation_criteria": {
        "actions": [
            # Agent should fix account_status
            {"requestor": "agent",
             "name": "update_customer_account_status",
             "arguments": {"customer_id": "C001", "account_status": "active"},
             "compare_args": ["customer_id"]},
            # Agent should fix points
            {"requestor": "agent",
             "name": "update_loyalty_account_points",
             "arguments": {"loyalty_id": "L001", "points": 1200},
             "compare_args": ["loyalty_id"]},
        ],
        "env_assertions": [
            {"func_name": "assert_customer_account_status",
             "arguments": {"customer_id": "C001", "expected": "active"},
             "assert_value": True},
            {"func_name": "assert_loyalty_account_points",
             "arguments": {"loyalty_id": "L001", "expected": 1200},
             "assert_value": True},
        ]
    }
}
```


## The Depth Trick (How It Works)

When the task generator composes perturbations from multiple groups, depth
emerges from the gate structure defined in Step 3:

```
Task has 3 perturbations:
  1. Customer.account_status = "suspended"  (from account_issues group)
  2. Order.status = "cancelled"             (from order_status group)
  3. LoyaltyAccount.points = 0             (from loyalty_points group)

Gate structure (Step 3):
  Customer → Order: gated by account_status == "active"
  Customer → LoyaltyAccount: gated by User.identity_verified == true

Agent's path:
  1. See Customer has suspended account → fix it (now Order edge opens)
  2. See Order is cancelled → fix it
  3. Ask user to verify identity (actor gate) → LoyaltyAccount edge opens
  4. See points are wrong → fix them
```

Depth = 2 (two sequential gates). The task generator didn't plan this —
it emerged from composing independent fault groups against the gate graph.


## Solvability by Construction

Every generated task is solvable because:

1. Each perturbation breaks a field from `normal_value` to `broken_value`
2. The fix tool exists and can restore `normal_value` (verified in Step 8)
3. The graph is traversable once gates are fixed (verified in Step 3)
4. No circular gate dependencies (verified in Step 3)

The solution to any task is: fix perturbations in gate-order (shallowest first),
satisfying actor gates by requesting user actions when needed.


## Graph-Aware Generation

For deeper tasks, `generate_graph_tasks()` in `design/framework/generator.py`
does gate-aware traversal:

1. Compute reachable nodes from entry point (respecting gate conditions)
2. Classify perturbations as "gate perturbations" (break a gate field) vs "content perturbations"
3. Order: gate perturbations first (they unlock access), content perturbations second
4. Verify every perturbation is reachable after fixing gates in order
5. Compute actual depth from the gate chain

This produces tasks where depth is explicitly controlled, not just an accident
of which groups were selected.


## What Good Output Looks Like

After Step 10, you should see:
- 20-100+ tasks generated (depending on seed data size and fault groups)
- Difficulty distribution: mix of 1-fault (easy), 2-fault (medium), 3-4 fault (hard)
- Every fault group represented across the task set
- Every entity in seed data used as entry point at least once
- All tasks solvable (by construction)


## Key Functions

- `derive_entity_builder(schema)` → `design/legacy/tau2/render.py`
- `compose_blueprints(space, entities, id_field, seed)` → `design/framework/generator.py`
- `generate_graph_tasks(schema, gated_rels, space, ...)` → `design/framework/generator.py`
- `render_tau2_task(blueprint, fault_space, schema)` → `design/legacy/tau2/render.py`
- `verify_solvable(schema, gated_rels, blueprint, entry)` → `design/framework/generator.py`
