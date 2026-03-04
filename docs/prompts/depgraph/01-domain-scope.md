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
12. Include at least one expected binding-dependency pattern and one expected user-action gate pattern.
13. Capture likely shortcut risks and ambiguity risks.
14. Identify candidate user-observable fields that can support strict stop-gating (`check_resolution_status`).
15. Keep this file instance-agnostic:
   - no concrete task IDs
   - no concrete required action sequences
   - no fixed goal baskets yet

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
10. `Dependency patterns to support`
11. `Known risks`
12. `Stop-gate observables (candidate)`
13. `Out of scope (pilot)`

Format guidance for field projection table:

- one row per field path
- columns:
  - `field_path`
  - `owner_db`
  - `type_or_domain`
  - `projected_for_solver`
  - `update_source`
  - `notes`
