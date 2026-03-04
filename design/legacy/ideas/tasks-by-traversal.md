# Tasks by Traversal: Correct by Construction

## The Core Idea

Don't author tasks and then verify them. Don't even author task atoms.
**Generate tasks by actually traversing the graph and performing operations.**
If the task was created through the same mechanism it will be solved through,
solvability is guaranteed by construction.

The task generator IS a graph-traversing agent.  It walks the graph, does
stuff, records what it did.  The real agent's job is to figure out what
happened (or what needs to happen) and do it (or undo it).


## Why This Works

The graph + tools + rules form a STATE MACHINE.

- States: valid graph configurations (all rules satisfied)
- Transitions: tool calls (agent tools, user tools)
- A task is: start at state S1, reach state S2 where predicate P holds

If we create S1 by starting from a known-good state S0 and applying
a sequence of transitions T1, T2, ..., Tn, then we KNOW:
- S1 is a valid state (we got there by valid transitions)
- The goal (S0, or some property of S0) is reachable (reverse the transitions)
- The tool sequence exists (we just used those tools)

There is no way to produce an unsolvable task because task creation IS
a demonstration that the solution exists.


## Generation Algorithm

### For Perturbation Tasks (undo what was done)

```
generate_perturbation_task(graph, entry_point, target_depth):
    # Start from valid world state (seed data, all normal values)
    original = graph.snapshot()

    # Phase 1: Walk DEEP first, break things
    # (deepest first because breaking a gate field closes the path)
    operations = []

    for depth in [target_depth, target_depth-1, ..., 1]:
        node = pick_reachable_node_at_depth(graph, entry_point, depth)
        field = pick_breakable_field(node)
        broken_value = pick_broken_value(field)

        # Record what it was BEFORE we break it
        original_value = node[field]

        # Break it using the SAME init tool the real system would use
        graph.apply(set_{entity}_{field}(node.id, broken_value))

        operations.append({
            entity: node.entity_type,
            node_id: node.id,
            field: field,
            original_value: original_value,
            broken_value: broken_value,
        })

    # Phase 2: The operations we did, reversed, IS the solution
    # The goal predicate is: every field restored to original_value
    goal = AND(
        node[field] == original_value
        for op in operations
    )

    # Phase 3: Verify depth
    # Breaking gate fields in phase 1 may have closed edges.
    # Compute: from entry_point, what's the longest gated path to a
    # broken node?  That's the actual task depth.
    actual_depth = compute_gated_depth(graph, entry_point, operations)

    return Task(
        start_state=graph.snapshot(),  # the broken state
        entry_point=entry_point,
        goal=goal,
        depth=actual_depth,
        # The solution exists because we created the problem by
        # doing valid operations from a valid state
    )
```

The critical trick: **break deep nodes first, then break shallower gate
fields.**  This ensures the deep breaks are "hidden" behind gates.
The agent has to fix gates (shallow) before it can discover and fix
the deep breaks.  Progressive disclosure falls out of the generation
order — no hand-authored dependencies needed.


### For Construction Tasks (do something new)

```
generate_construction_task(graph, entry_point, target_complexity):
    original = graph.snapshot()

    # Phase 1: Perform a construction sequence
    # (create an order, add items, set preferences, etc.)
    operations = []

    # Walk the graph, performing VALID construction operations
    new_order = graph.apply(create_order(customer_id=entry_point.id))
    operations.append(new_order)

    for i in range(target_complexity):
        item = pick_menu_item(graph)
        graph.apply(add_order_item(order_id=new_order.id, item_id=item.id))
        operations.append(...)

    # Phase 2: Record the end state as the goal
    goal = (
        exists(Order where customer_id == entry_point.id and status == "pending")
        AND order.items == [...]
    )

    # Phase 3: REVERT to original state — that's the starting state
    graph.restore(original)

    return Task(
        start_state=original,  # before the construction
        entry_point=entry_point,
        goal=goal,
        # Solvable: we literally just demonstrated the construction
    )
```


### For Query/Discovery Tasks (find information)

```
generate_query_task(graph, entry_point, target_depth):
    # Phase 1: Walk to a node at target_depth
    target_node = walk_to_depth(graph, entry_point, target_depth)
    target_field = pick_field(target_node)
    target_value = target_node[target_field]

    # Phase 2: Optionally break gate fields to require traversal work
    # (same as perturbation — break gates on the path)

    # Phase 3: Goal is that agent communicated the correct value
    goal = agent_stated_value(target_value)

    return Task(
        start_state=graph.snapshot(),
        entry_point=entry_point,
        goal=goal,
        # Solvable: the value exists at the node, the path exists
    )
```


### For Compound Tasks (compose multiple atom types)

```
generate_compound_task(graph, entry_point, atoms_config):
    # atoms_config says: 1 perturbation + 1 construction + 1 query

    # Generate each atom using its type-specific algorithm
    # Composition safety: check scope overlap BEFORE generating
    atoms = []
    claimed_scopes = set()

    for atom_type in atoms_config:
        atom = generate_atom(graph, entry_point, atom_type)

        # Scope check: does this atom touch fields already claimed?
        if atom.scope & claimed_scopes:
            # Conflict — skip or pick different target
            continue

        claimed_scopes |= atom.scope
        atoms.append(atom)

    # Compound goal = AND of all atom goals
    goal = AND(atom.goal for atom in atoms)

    return Task(start_state=graph.snapshot(), goal=goal)
```


## Why Order of Operations Matters (The Depth Trick)

Consider this graph:
```
Customer (account_status gates edge) → Order (status) → OrderItem (quantity)
```

If we break in this order: [account_status, status, quantity]
Then after breaking account_status, the Customer → Order edge is gated.
We can no longer reach Order or OrderItem through normal traversal.
But we ALREADY broke them (we did it before breaking the gate).

The agent sees: Customer with suspended account.
Agent fixes account → can now see Order → sees cancelled order.
Agent fixes order status → can now see OrderItems → sees wrong quantity.
Agent fixes quantity → done.

Depth = 3, and it emerged purely from the order we broke things.

General rule: to create depth-N tasks, break nodes at depth N first,
then break gate fields working backward toward the entry point.


## What This Eliminates from the Pipeline

With traversal-based generation, the LLM does NOT need to:

1. ~~Author perturbation declarations~~ — generated by breaking fields during traversal
2. ~~Author dependency chains~~ — depth emerges from break order + gate structure
3. ~~Author goal predicates~~ — derived from the operations performed
4. ~~Ensure solvability~~ — guaranteed by construction

The LLM's job reduces to:
1. Author the WORLD (entities, fields, relationships, gates, rules, seed data)
2. Author the INTERACTION MODEL (tools, projections, sync, policy)

Tasks are generated ENTIRELY programmatically from the world.  The world
is the creative artifact; tasks are mechanical consequences of the world.


## The Revised Pipeline

```
Phase 1: World Structure (LLM)
  Step 1: Concept + topology targets
  Step 2: Entity schema
  Step 3: Relationships + gates
  Step 4: Rules
  Step 5: Seed data

Phase 2: Interaction Model (LLM + derivation)
  Step 6: Tools (mostly derived, some custom)
  Step 7: Projections + sync
  Step 8: Policy

Phase 3: Task Generation (PURE CODE — no LLM)
  Step 9:  Graph traversal → task atoms
  Step 10: Composition → compound tasks
  Step 11: Render to format (tau2 Task, etc.)
```

Step 8 (perturbation space) from the old pipeline is GONE.  It's been
replaced by step 9, which is pure code.  The LLM never touches tasks.


## Verification Is Also by Traversal

Even if we don't generate tasks by traversal, we can VERIFY them by
traversal.  Given any task (however generated):

```
verify_solvable(graph, entry_point, goal):
    # Simulate an oracle agent that can see the full graph
    state = graph.snapshot()

    # BFS/DFS from entry_point
    reachable = compute_reachable(state, entry_point)
    fixable = [op for op in required_operations(goal) if op.node in reachable]

    while fixable:
        # Apply the cheapest fix
        op = fixable.pop(0)
        state.apply(op)

        # Recompute reachability (fixing a gate may open new edges)
        reachable = compute_reachable(state, entry_point)
        fixable = [op for op in remaining_operations(goal, state)
                   if op.node in reachable]

    # Check: did we satisfy the goal?
    if goal.evaluate(state):
        return SOLVABLE
    else:
        # Some operations were never reachable — task is unsolvable
        return UNSOLVABLE(unreachable=remaining_operations(goal, state))
```

This works for ANY task, not just traversal-generated ones.  It's a
general solvability oracle that runs as pure code against the graph.


## Open Questions

### Q1: How do we generate the "user's perspective" for the task description?

The traversal generates what's broken and what the goal is.  But the
task description (what the user SAYS to the agent) needs to be natural
language that reflects the user's PROJECTION, not the full graph state.

Options:
- Template-based: "my {entity} has a problem with {field}"
- LLM-generated: given the task atoms, generate natural language
- Derived from projection: the user can only describe what they can see

### Q2: How do we control task diversity?

Traversal-based generation could produce many similar tasks (always
breaking the same fields).  Diversity controls:
- Vary the entry point (different customers)
- Vary the traversal path (different edges taken)
- Vary the break targets (different fields)
- Vary the atom types (perturbation vs construction vs query)
- Vary the depth target
- Coverage: every breakable field used at least once, every tool
  exercised at least once, every gate traversed at least once

### Q3: How do we handle tasks where the "right" action is to NOT act?

Some tasks should test that the agent correctly identifies that no
action is needed, or that a request should be refused.  These aren't
traversal operations — they're about the agent's JUDGMENT.

Possible: generate a "trap" task where the graph is in a valid state
but the user asks for something that violates a rule.  Goal predicate:
the graph state is UNCHANGED (nothing was modified that shouldn't be).

### Q4: How far can we push pure programmatic generation?

Simple tasks (break field, fix field) are fully programmatic.  But
the most INTERESTING tasks often involve subtle reasoning that's hard
to express as graph operations:
- "The customer was charged twice" (requires computing a sum)
- "The items in the order don't match the receipt" (requires cross-referencing)
- "The warranty expired yesterday" (requires date comparison)

These may need domain-specific operation types beyond simple field breaks.
The graph traversal generates the STRUCTURE, but the semantic richness
might still need LLM input (as custom operations defined in step 6).
