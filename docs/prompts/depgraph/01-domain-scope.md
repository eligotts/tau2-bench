# Prompt 01: Domain World Scope + Pilot Selection (DB-Explicit)

## Instruction

Given a candidate domain concept, produce a tight, schema-explicit world sketch for first trial run.
Do not prescribe task-level goals yet.

Requirements:

1. Choose one domain and one narrow operational slice.
2. Explicitly list out-of-scope capabilities for the pilot slice (to avoid hidden complexity).
3. Define **agent DB** entities and fields:
   - include ids, relationships, and finite value domains for gate-relevant fields
4. Define **user DB** entities and fields (entity-structured, not a flat list):
   - include ids/relationships where applicable
   - include finite value domains for gate-relevant fields
5. For every field in both DBs, tag:
   - `owner_db`: `agent` or `user`
   - `projected_for_solver`: `yes` or `no`
   - `update_source`: one of `assistant_tool`, `user_tool`, `sync`, `init_only`, `view_only`
6. Mark projection/view-only fields explicitly (kept in runtime DB, excluded from solver state).
7. Define context slots that select the active entity slice per task instance (for example `active_customer`, `active_line`).
8. Define projected world paths used by solver state (scoped through context slots).
9. List assistant tools with rough behavior and whether they are read/write in practice.
10. List user tools with rough behavior, including which are causal vs likely stutter/read-only.
11. Describe sync/world logic at a high level (`user -> agent` bridges and `agent -> user projection` updates).
12. If a user-visible value is derived through sync, identify its single canonical source field or the exact explicit prereqs that drive it.
13. For each candidate binding, decide whether it is stable context or a volatile stage token:
   - stable context can safely flow through multiple downstream tools
   - volatile stage tokens should gate only immediate observation-driven transitions, with explicit reread points in policy
   - express those reread points as decision rules, not as a full numbered recovery script
14. Design dependency patterns that produce **structurally diverse** tasks (see Structural Diversity below).
15. Capture likely shortcut risks and ambiguity risks.
16. Identify candidate user-observable fields that can support strict stop-gating (`check_resolution_status`).
17. Identify canonical terminal end states for each branch:
   - distinguish true resolution states from useful intermediate milestones
   - note which fields prove the issue is actually done from both agent-state and user-observable perspectives
18. Define persona strategy for later runtime sampling:
   - 3-5 persona archetypes representing **genuinely different people** — vary life situation,
     role, knowledge level, and communication style, not just mood or urgency of the same person
   - behavioral axes (for example: technical comfort, urgency, verbosity, compliance)
   - note which archetypes are better for easy vs hard tasks
   - personas should feel like different users of the same system, not variations of one user
19. Keep this file instance-agnostic:
   - no concrete task IDs
   - no concrete required action sequences
   - no fixed goal baskets yet

## Structural Diversity

The dependency patterns you design here determine whether the sampler produces genuinely
different tasks or just shorter/longer versions of the same chain. A well-designed domain
graph creates tasks that differ in **topology** (which actions are needed and how they
relate), not just **depth** (how many steps).

Design for these properties:

1. **Multiple knowledge gates (bindings).** A domain with one binding produces tasks where
   the agent always gathers the same piece of information. Design at least 2 bindings from
   different source tools so different tasks require discovering different things.
   - Example: binding `fault_code` from a screen-read tool, binding `account_tier` from
     an account-lookup tool. Some tasks need both; some need only one.

2. **Value-dependent branching.** Different values of a world field should enable different
   actions. This means the same starting topology can produce structurally different
   resolution paths depending on what the agent discovers.
   - Example: if `fault_class == "billing"`, the account recovery chain is needed;
     if `fault_class == "network"`, the network recovery chain is needed. The agent
     must diagnose first, then choose the right path.

3. **Cross-dependencies between user actions.** User-side actions should form a mini-DAG,
   not a flat basket. If 5 user actions can happen in any order with no dependencies
   between them, they contribute no reasoning — the agent just tells the user to do all 5.
   - Example: "inspect cable" must precede "reseat connector" (need to know cable is OK
     before reseating). "Power cycle" must follow "reseat connector" (so the reset picks
     up the new connection).

4. **Early convergence points.** Don't save all multi-prerequisite gates for the very end.
   Place actions that require 2-3 upstream results earlier in the graph so the agent must
   coordinate mid-task, not just check a final gate.
   - Example: "run diagnostics" requires BOTH the fault code binding AND user having
     power-cycled the station. This is an early cross-lane convergence.

4A. **Shared downstream gates.** Harder domains should not just add more independent
   fixes. Multiple branches should fan into shared late-stage gates so branch repair,
   customer readiness, and final verification all interact.
   - Example: billing cleanup, secure-transport recovery, and firmware update all feed
     a shared reprovision/auth/retry/test-charge funnel.

5. **Non-uniform binding usage.** Not every tool should require the same binding. If every
   assistant action takes `fault_code`, the agent learns one pattern and repeats it.
   Design tools where some need binding A, some need binding B, and one critical tool
   needs both.

6. **Volatile-stage discipline.** If a user-visible value changes as recovery progresses
   (for example a screen fault code that advances after each repair), decide up front
   which steps truly need the current observed value. The long middle of the repair chain
   should usually run on stable world state established by diagnostics, not on repeated
   reuse of a moving observation token.

### Complexity Ladder

Use this ladder to calibrate domain ambition. Each tier builds on the previous one.

**Tier 1 — Baseline** (produces 10-30 tasks, tests tool-following):
- 2+ bindings from different sources
- Value-gated branching (different fault values → different repair paths)
- One resolution gate
- Expect 5-8 step plans

**Tier 2 — Intermediate** (produces 30-80 tasks, tests multi-step reasoning):
- 4+ bindings with tiered prerequisites (binding B requires binding A first)
- Cross-dependencies between user actions (mini-DAG, not flat basket)
- Early convergence points (mid-graph gates requiring 2+ upstream results)
- Shared downstream gates (multiple branches fan into shared verification)
- Expect 7-12 step plans

**Tier 3 — Advanced** (produces 80-200+ tasks, tests causal reasoning):
- 6+ bindings with discovery trees
- Cascading sync rules (one fault automatically damages downstream systems)
- Repair side-effects (fixing system A creates new problems in system B)
- Resolution gates that require side-effect cleanup
- Multi-fault seeds (2-3 simultaneous failures with cross-dependencies)
- Expect 10-18 step plans

**Tier 4 — Expert** (produces 150-400+ tasks, tests deep causal reasoning):
- All of Tier 3, plus:
- Sync-rule traps / bouncing state (naive repairs get undone until root cause is addressed)
- Multi-step repair chains (fault A → intermediate state → fault B → healthy)
- Cross-system repair prerequisites (fixing cache requires DB healthy first)
- Seed schemas expanding combinatorial fault/knowledge dimensions
- Expect 12-20+ step plans

Most domains should target Tier 2-3. Only target Tier 4 when the goal is to challenge
frontier models. Each tier roughly doubles the number of unique tasks because the
combinatorial space grows with each new diversity axis.

### Depth Through Intermediate Steps (Critical)

The single most common mistake in domain design is making actions too coarse-grained.
If "do errand" is one action, you get depth-3 tasks. If it's reserve → confirm
reservation → arrange delivery/pickup → confirm completion, you get depth-8+ tasks
with meaningful intermediate decision points.

**Expand every conceptual operation into its real-world sub-steps:**

- **Errands/purchases**: check availability → reserve item → confirm reservation →
  arrange delivery OR pickup → confirm receipt. Each sub-step is a separate action
  with its own preconditions.
- **Delegation**: contact delegate → check response → check ETA → notify facility →
  assign delegate. Don't collapse "delegate the task" into one action.
- **Service requests**: request quotes → review quotes → select provider → schedule
  visit → arrange access → verify completion.
- **Payments/finances**: check balance → transfer if needed → make payment → verify
  payment. Each payment degrades available funds.

The depth comes from realistic granularity, not from artificial padding. Each sub-step
should represent a real decision point where the agent could fail or choose wrong.

### Fate Flags and Conditional Failure (Critical)

Real-world actions can fail. Model this with **fate flags** — `init_only` boolean fields
that determine whether an action succeeds or fails. The agent doesn't know the fate flag
value; it must attempt the action and handle the outcome.

**How fate flags work:**
- A field like `rideshare_will_succeed` is set in the seed's `start_world` and tagged
  `init_only` (never changed by any action).
- Two action variants exist: `book_rideshare_success` (requires `rideshare_will_succeed=true`,
  sets `rideshare_result=booked`) and `book_rideshare_fail` (requires
  `rideshare_will_succeed=false`, sets `rideshare_result=no_drivers`).
- The BFS explores both variants depending on the seed's fate flag value, producing
  structurally different tasks from the same topology.

**Fate flags create fallback cascades:**
- Rideshare fails → must route public transit → user confirms transit
- Delivery fails → must recover to pickup mode → user picks up in person
- Primary delegate unavailable → try secondary delegate → secondary fails → try
  extended care → extended care unavailable → user must handle it directly
- Each fallback is a multi-step chain with its own preconditions and confirmations

**Design at least 2-3 fate-flagged actions per domain.** Each fate flag doubles the
structural branching for seeds that include it. A domain with 3 fate flags and 2 values
each creates 8 structurally different paths through the same topology.

### Cross-Lane Resource Coupling (Critical)

Independent parallel lanes (errands, calendar, care, household) produce tasks where
the agent just does each lane sequentially with no interaction between them. This tests
parallelism but not resource reasoning.

**Add a shared degradable resource that couples lanes:**
- A `available_funds` field with values like `plenty → tight → broke`
- Each paid service (delivery, transport, extended care, bill payment) consumes funds,
  degrading the level
- When funds run out, paid options become unavailable and the agent must switch to free
  alternatives (user pickup instead of delivery, user transport instead of rideshare)
- This creates genuine cross-lane tradeoffs: paying for errand delivery may leave
  insufficient funds for extended dependent care

**Implementation pattern for degradable resources:**
- Each cost action needs variants per resource level:
  `pay_bill_plenty` (plenty→tight) and `pay_bill_tight` (tight→broke)
- This is necessary because graph contract effects must be concrete values, not
  arithmetic expressions
- Actions requiring resources gate on the current level:
  `arrange_delivery` requires `available_funds != broke`

### Obligation-Creating Actions

Some actions should create NEW obligations that the agent must then handle. This
prevents the agent from taking actions without considering consequences.

- Cancelling a meeting → creates `apology_needed=true` → agent must send apology
- Arranging delivery → creates payment obligation → agent must pay
- Delegating a task → creates notification obligation → agent must notify facility

Design these as explicit world state transitions: the action sets a flag, and a
downstream action (or terminal profile) requires that flag to be resolved.

### Sketching Checklist

When sketching dependency patterns in this step, explicitly note:
- How many distinct bindings the domain will have and their source tools
- Which actions branch based on discovered values (value-gated actions)
- What ordering constraints exist between user-side actions
- Where early convergence points force cross-lane coordination
- Which bindings are volatile and where the policy must instruct the agent to reacquire them
- How the policy will expose domain constraints without hardcoding a single end-to-end solution path (remember: the policy teaches domain reasoning, not tool catalogs — agent tools are injected via the API with docstrings)
- The policy must clearly reflect the `requestor` split: if some tools are user-operated and others are assistant-operated, the policy language must not imply all actions go through the user (e.g., "guide the engineer through diagnostics" vs "you perform repairs directly")
- Which branch-specific terminal profiles the sampler should use, and why shorter tasks should come from easier starts rather than partial endings
- Which late-stage shared gates every branch must still clear before terminal completion
- **Target complexity tier** and which diversity axes the domain will use to reach it
- **Persona diversity**: personas should represent genuinely different people who use this system (different life situations, roles, knowledge levels), not just different moods of the same archetype

Output sections:

1. `Pilot domain`
2. `Agent DB schema sketch`
3. `User DB schema sketch`
4. `Field projection table`
5. `Context slots`
6. `Projected world paths`
7. `Assistant toolset (rough)`
8. `User toolset (rough)`
9. `World/sync logic`
10. `Dependency patterns to support` (must address all 5 structural diversity properties above)
11. `Known risks`
12. `Stop-gate observables (candidate)`
13. `Persona strategy (candidate)`
14. `Out of scope (pilot)`

Format guidance for field projection table:

- one row per field path
- columns:
  - `field_path`
  - `owner_db`
  - `type_or_domain`
  - `projected_for_solver`
  - `update_source`
  - `notes`
