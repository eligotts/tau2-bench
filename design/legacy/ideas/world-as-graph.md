# World as Information Topology

## Core Insight

The world is a graph of entities. Tasks are traversals of that graph.
Difficulty emerges from where perturbations are placed relative to the
entry point, not from hand-authored dependency chains.

## The Graph

- **Nodes** = entity instances (a specific Customer, a specific Order)
- **Edges** = relationships (Customer → Order via customer_id FK)
- **Properties** = field values on nodes (order.status, customer.account_status)
- **Entry point** = the node the user identifies (e.g., "I'm customer C001")

## Four Layers on the Graph

### 1. Structure (the graph itself)
Nodes, edges, properties, types. This is the static backbone.
Modeled by WorldSchema (entities, fields, relationships).

### 2. Rules (constraints on traversal and mutation)
- Gate conditions: "can't traverse Customer → Order unless account_status == 'active'"
- Mutation guards: "can't update order.status if order.payment_status == 'disputed'"
- Protocols: "must verify identity before accessing account details"
- Business logic: "order total = sum of line item prices"

Not just gate fields on edges — richer constraints that make the world feel real.

### 3. Projections (how different actors see the graph)
- Agent sees the raw graph through tools (READ: traverse edges, read nodes; WRITE: mutate properties)
- User sees a projected subgraph (their own orders, their account, not other customers')
- The information asymmetry between projections drives the agent-user interaction
- Tools ARE the projections — each tool is a window into a specific part of the graph

### 4. Dynamics (how the graph responds to actions)
- Fixing node A may change node B (sync bridges)
- User physical actions update graph state (restart device → device.restarted = true)
- Computed properties update when inputs change (order total recalculated)

## Perturbations in the Graph

A perturbation is simply: a node has a wrong property value.
- Customer C001 has account_status = "suspended" (should be "active")
- Order ORD001 has status = "cancelled" (should be "completed")

Progressive disclosure is emergent:
- If account_status gates the Customer → Order edge, the agent MUST fix the account
  before it can even discover the order problem
- No hand-authored dependency chain needed — it falls out of graph structure

## Difficulty as Topology

Task difficulty is determined by WHERE perturbations sit in the graph:

- **Depth 1**: On the entry node. Agent sees it immediately.
- **Depth 2**: One hop away. Agent traverses one edge.
- **Depth 3+**: Behind multiple hops, possibly gated.

Two graphs with identical structure produce different difficulty tasks
depending on perturbation placement.

## Six Topology Parameters

These control what skills the agent needs:

| Parameter        | What it means                           | High value forces agent to...    |
|------------------|-----------------------------------------|----------------------------------|
| Width            | Number of entity types / relationships  | Handle multiple concerns         |
| Depth            | Hops from entry to deepest node         | Chain multi-step reasoning       |
| Branching        | Edges per node                          | Search and disambiguate          |
| Gating density   | Fraction of edges that are gated        | Solve prerequisites first        |
| Rule complexity  | Number of constraints on traversal      | Reason about policies            |
| Projection gap   | Difference between agent/user views     | Extract info from user           |

These could be explicit inputs to world generation: "generate a world with
depth 4, high gating, moderate branching" — LLM fills in content, structure
is parameterized.

## Tools as Graph Operations

In tau2, both agent and user interact with the same graph through tools:

- Agent READ tools: traverse edges, read node properties
- Agent WRITE tools: mutate node properties
- User READ tools: see own projected subgraph
- User WRITE tools: physical actions that update graph state

This generalizes beyond tau2:
- Coding agent: READ = grep/cat/ls (traverse file graph), WRITE = file edits
- API agent: READ = GET requests, WRITE = POST/PUT/DELETE
- Same pattern: traverse, read, mutate

## Why Graphs Are Maximally General

Alternatives (relational models, document models, state machines) are all
special cases of labeled property graphs. The graph is general enough for
any structured world.

What matters more than the data structure is the generation strategy — how
to produce graphs that are diverse, realistic, and create interesting tasks.
The topology parameters are the diversity knobs.

## Limitations

Things awkward to model as pure static graphs:
- Processes/protocols → modeled as Rules layer
- Computed/derived state → modeled as Dynamics layer
- Temporal dynamics → would need a time dimension
- Ambiguity → fuzzy entry points, partial information
