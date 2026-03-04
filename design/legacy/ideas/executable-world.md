# Executable World: The Unified Model

## Key Realization

The world graph isn't just a data structure — it's an EXECUTABLE environment.
Tools are operations on the graph. Rules are constraints on those operations.
Gates control information flow. The task generator and the agent both interact
with the SAME executable environment.

This means: if the task generator can solve it, the agent can solve it.
Not because they use the same strategy, but because they use the same
interface (tools) to the same state (graph).


## The Executable World

```python
class World:
    """The single source of truth.  Both task generator and agent
    interact with this through the same tool interface."""

    graph: Graph              # nodes (entity instances) + edges (relationships)
    rules: list[Rule]         # constraints on operations
    gates: list[Gate]         # conditions on edge traversal
    tools: list[Tool]         # operations available to actors
    projections: dict[str, Projection]  # what each actor can see
```

A Tool is a function that:
- Takes the graph + arguments
- Checks preconditions (rules, gates)
- Mutates the graph (or reads from it)
- Returns a result

The same tool definition is used by:
1. The task generator (to create tasks by doing operations)
2. The agent (to solve tasks)
3. The verifier (to simulate solutions)


## Node Types in the Graph

Not all nodes are the same.  Different node types create different
kinds of task challenges:

### Data Nodes (entities with properties)
The basic building block.  Customer, Order, MenuItem.
Properties can be read, some can be written, some are breakable.

### Gate Nodes (control information flow)
A property on a data node that controls edge traversal.
Customer.account_status == "active" gates Customer → Order.
Breaking this property HIDES downstream nodes.

### Information Nodes (only readable, not writable by agent)
Nodes that hold facts the agent needs but can't change.
The agent must discover this info and use it in other operations.
e.g., a PricingTable that tells the agent the correct price,
or a PolicyDocument that tells the agent the correct procedure.

### Actor Nodes (represent the user or external systems)
The user is a node in the graph.  The user has properties
(what they know, what they've done, what they want).
Some gates require USER PROPERTIES — the agent can't traverse
until the user has taken an action.

This is the "go to the user to get info" pattern:
- Agent needs to traverse Edge X
- Edge X is gated by User.provided_verification == true
- Agent must ask user to verify identity
- User calls verify_identity tool → User.provided_verification = true
- Now agent can traverse Edge X

The user-as-node means user interaction emerges from the SAME graph
mechanism as everything else.  No special-casing needed.


## Gate Types (the source of task complexity)

### Property Gates (field value controls traversal)
The basic gate.  A field on the source node must have a specific value.
  Customer.account_status == "active" → can traverse to Orders

### Actor Gates (require action from a specific actor)
An edge that requires a specific actor (user, agent, external system)
to have performed an action.
  User.identity_verified == true → can access account details
  User.device_restarted == true → can check connectivity

### Information Gates (require knowledge, not state change)
An edge that requires the traversing actor to HAVE certain information,
not to change state.  The agent must have looked up a value from
another node before they can meaningfully operate on this node.
  agent.knows(Customer.plan_type) → can correctly update Subscription

### Compound Gates (multiple conditions)
  Customer.account_status == "active"
  AND User.identity_verified == true
  AND agent.knows(Customer.plan_type)

Each gate type creates a different kind of challenge for the agent:
- Property gates → fix something to proceed (perturbation)
- Actor gates → coordinate with user to proceed (interaction)
- Information gates → discover information to proceed (investigation)
- Compound gates → do multiple things to proceed (multi-step reasoning)


## Task Generation by Recorded Traversal

### The Generator

The task generator is a program that:
1. Takes a World and topology parameters (target depth, width, task types)
2. Walks the graph performing operations
3. Records everything it does
4. Produces a Task = (modified world state, goal predicate, solution trace)

```python
class TaskGenerator:
    def __init__(self, world: World):
        self.world = world.deepcopy()
        self.trace = []  # recorded operations

    def generate(self, entry_point, config: TaskConfig) -> Task:
        # Phase 1: Plan a traversal path
        path = self.plan_path(entry_point, config)

        # Phase 2: Walk the path, performing operations
        for step in path:
            result = self.execute_step(step)
            self.trace.append(result)

        # Phase 3: Derive goal from trace
        goal = self.derive_goal()

        # Phase 4: Derive task description (LLM step)
        description = self.generate_description()

        return Task(
            world_state=self.world.snapshot(),
            entry_point=entry_point,
            goal=goal,
            solution_trace=self.trace,  # proof of solvability
            description=description,
        )

    def execute_step(self, step):
        """Execute an operation through the SAME tool interface
        the agent will use.  If this succeeds, the agent can do it too."""
        tool = self.world.get_tool(step.tool_name)
        result = tool.execute(step.args)
        return TraceEntry(tool=step.tool_name, args=step.args, result=result)
```


### Path Planning

The generator doesn't random-walk.  It PLANS a traversal that achieves
target topology parameters.  This is where the structure comes from:

```python
def plan_path(self, entry_point, config) -> list[Step]:
    steps = []

    if config.task_type == "perturbation":
        # Find nodes at target depth, break them, then break gates backward
        steps = self.plan_perturbation_path(entry_point, config.target_depth)

    elif config.task_type == "construction":
        # Plan a sequence of construction operations
        steps = self.plan_construction_path(entry_point, config.target_complexity)

    elif config.task_type == "investigation":
        # Plant information at a deep node, gate the path
        steps = self.plan_investigation_path(entry_point, config.target_depth)

    elif config.task_type == "compound":
        # Compose multiple sub-paths with scope checking
        steps = self.plan_compound_path(entry_point, config.atom_configs)

    # Inject actor gates where needed
    if config.requires_user_interaction:
        steps = self.inject_actor_gates(steps, config.interaction_points)

    return steps
```


### Injecting User Interaction

To create tasks that require the agent to go to the user:

```python
def inject_actor_gates(self, steps, interaction_points):
    """Add actor gates at specified points in the traversal.

    For each interaction point:
    1. Find an edge in the path
    2. Add an actor gate on that edge (User.did_X == true)
    3. The agent will need to ask the user to do X
    4. The user's tool (do_X) sets User.did_X = true
    5. Now the agent can traverse the edge
    """
    for point in interaction_points:
        edge = steps[point.step_index].edge
        gate = ActorGate(
            actor="user",
            field=point.user_field,
            required_value=True,
            user_tool=point.user_tool,  # the tool the user calls
        )
        self.world.add_gate(edge, gate)

    return steps
```

This means user interaction isn't a separate mechanism — it's another
gate type.  The generator injects actor gates into the traversal path,
creating points where the agent MUST coordinate with the user.


## Solvability: Three Levels of Guarantee

### Level 1: Construction Guarantee (strongest)
Task was created by performing valid operations on a valid graph.
The operations used the same tools the agent has access to.
Therefore the solution exists.  PROOF: the trace IS the solution.

### Level 2: Simulation Guarantee (strong)
Given a task (however created), simulate an oracle agent:
- Oracle can see full graph (ignores projections)
- Oracle knows optimal operation order
- Oracle executes operations through the tool interface
- If oracle reaches goal: task is solvable
- If oracle gets stuck: task is unsolvable → reject

```python
def verify_solvable(world, entry_point, goal) -> bool:
    """Simulate an oracle agent with full visibility."""
    state = world.deepcopy()
    max_steps = 100

    for _ in range(max_steps):
        if goal.evaluate(state):
            return True

        # Find operations that make progress toward goal
        reachable = state.reachable_nodes(entry_point)
        candidates = find_useful_operations(state, reachable, goal)

        if not candidates:
            return False  # stuck — no useful operation available

        # Apply the most promising operation
        best = rank_operations(candidates, goal)
        best.tool.execute(best.args)

    return False  # timeout
```

### Level 3: Constraint Guarantee (lightweight, fast)
Static analysis without simulation:
- Every goal predicate references reachable nodes
  (accounting for gate-opening operations)
- Every required tool exists and has valid preconditions
- No circular dependencies (gate A requires B, gate B requires A)
- Scope analysis: no two task atoms write the same field

Level 1 is what traversal-based generation gives you.
Level 2 is a fallback for LLM-generated or manually-authored tasks.
Level 3 is a fast pre-check that catches obvious issues.


## What the LLM Does vs. What Code Does

### LLM authors the WORLD (creative, semantic):
- Step 1: What entities exist, what the domain is about
- Step 2: What fields they have, which are breakable
- Step 3: How entities relate, what gates edges
- Step 4: Business rules and constraints
- Step 5: Realistic seed data
- Step 6: Custom tools (non-derivable ones)
- Step 7: What the user can see, how state syncs
- Step 8: Policy (how the agent should behave)

### LLM authors TASK DESCRIPTIONS (natural language):
- Given structured task data from the generator
- Write natural language user messages
- "Hi, I can't access my account and I think my recent order was cancelled"

### Code does EVERYTHING ELSE:
- Derive standard tools from schema (step 6 partial)
- Generate tasks by graph traversal (step 9)
- Compose compound tasks (step 10)
- Render to format-specific output (step 11)
- Verify solvability (construction guarantee + simulation)
- Verify composition safety (scope analysis)
- Verify diversity (coverage metrics)


## Reward / Verification at Runtime

When the agent runs against a task:

```python
def evaluate(task, agent_trace):
    world = World.from_snapshot(task.world_state)

    # Replay the agent's actions on the world
    for action in agent_trace:
        tool = world.get_tool(action.tool_name)
        tool.execute(action.args)

    # Check goal predicate against final world state
    return task.goal.evaluate(world)
```

The goal predicate is a function over the graph state.  It was derived
from the generator's operations.  It checks properties of nodes.
Fully deterministic, no LLM judge needed.

For more nuanced evaluation (did the agent take a reasonable path?
did it ask good questions? did it handle the user interaction well?),
you can compare the agent's trace against the generator's trace or
measure efficiency metrics.  But the CORE reward is binary: does the
final graph state satisfy the goal predicate?


## What "Interesting" Worlds Look Like

Since tasks emerge from worlds, the diversity question becomes:
how do we generate interesting worlds?

A world is interesting when its graph has:
- Multiple gate types (property + actor + information) along paths
- Cross-references between subgraphs (fixing something in subgraph A
  reveals information needed for subgraph B)
- Rules that create non-obvious constraints (can't do X before Y,
  but the connection isn't obvious from the graph structure alone)
- Rich information nodes that the agent must consult
- Actor gates at strategic points (forcing user coordination)

The topology parameters from the concept step guide this:
- depth → how many sequential gates
- width → how many parallel subgraphs
- gating_density → what fraction of edges are gated
- interaction_density → what fraction of gates are actor gates
- rule_complexity → how many non-obvious constraints

These parameters let you systematically explore the space of
"interesting" worlds, rather than hoping the LLM produces variety.
