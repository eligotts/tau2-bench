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
12. Design dependency patterns that produce **structurally diverse** tasks (see Structural Diversity below).
13. Capture likely shortcut risks and ambiguity risks.
14. Identify candidate user-observable fields that can support strict stop-gating (`check_resolution_status`).
15. Define persona strategy for later runtime sampling:
   - 2-5 persona archetypes
   - behavioral axes (for example: technical comfort, urgency, verbosity, compliance)
   - note which archetypes are better for easy vs hard tasks
16. Keep this file instance-agnostic:
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

5. **Non-uniform binding usage.** Not every tool should require the same binding. If every
   assistant action takes `fault_code`, the agent learns one pattern and repeats it.
   Design tools where some need binding A, some need binding B, and one critical tool
   needs both.

When sketching dependency patterns in this step, explicitly note:
- How many distinct bindings the domain will have and their source tools
- Which actions branch based on discovered values (value-gated actions)
- What ordering constraints exist between user-side actions
- Where early convergence points force cross-lane coordination

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
