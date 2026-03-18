# Prompt 00: Session Contract

Use this at the start of any depgraph authoring run.

## Adapter Choice

Before starting, determine which adapter path this domain targets:

- **tau2 path** — Full user-simulator environment with agent + user roles, personas, sync
  rules, stop-gate checker, and runtime narrative enrichment. Use when the domain needs a
  human-in-the-loop simulation (support agents, collaborative tasks).
- **verifiers path** — Agent-only `StatefulToolEnv` with no user simulator. Tools get a
  `db` dict injected via `state["db"]`. Goal checking via rubric at episode end. Use when
  the domain is pure tool-use (browser automation, API interaction, code editing).

Both paths share the same graph contract, sampler, and preflight. They diverge at Step 02
(tool authoring) and Step 04 (compilation).

| Step | tau2 path | verifiers path |
|---|---|---|
| 00 | `00-session-contract.md` | `00-session-contract.md` |
| 01 | `01-domain-scope.md` | `01-domain-scope.md` |
| 02 | `02-graph-contract.md` | `02v-graph-contract-verifiers.md` |
| 03 | `03-task-intents.md` | `03-task-intents.md` |
| 04+ | `04` → `05` → `06` → `07` → `08` → `09` | `04v-verifiers-compile-and-verify.md` |

## Instruction

You are building a dependency-graph domain pipeline.

Hard constraints:

1. Determine adapter path (tau2 or verifiers) before Step 02 and follow only the matching guides.
2. Treat `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md` as architecture source of truth.
3. Do not use archived material as implementation directives. The only archive file that remains normative for current work is `docs/archive/simulation-trace-guide.md` when reading simulation traces.
4. Edit only one minimal file per step.
5. After each step, run verification and report pass/fail with exact command.
6. Prefer explicit v2 transition contracts (`requires_world/requires_bindings/effects_world/effects_bindings`) over implicit logic.
7. (tau2 only) Treat derived/runtime-only state as contract-owned `sync_rules`; `environment.sync_tools()` must mirror those rules exactly at init time and after every tool call.
8. Assume bindings can invalidate whenever their `world_path` changes. Do not thread volatile bindings through long repair chains; use them only for immediate observation-driven steps or clearly mutually-exclusive stage transitions.
9. Fail closed: never emit compiled tasks when preflight, policy/contract alignment, or runtime alignment checks fail.
10. Do not manually author task journeys; structural intents must come from sampler fan-out.
11. Preserve creativity by constraining semantics/contracts, not narrative style/domain theme.
12. Do not mutate generated structural fields (`required_actions`, `required_precedence`) by hand.
13. Re-run `/Users/eligottlieb/Documents/tau2-bench/docs/prompts/depgraph/CHECKLIST.md` after each major phase.
14. (tau2 only) Treat `policy.md` as domain reasoning guidance, not a tool catalog or solve script. Agent tools are injected via the API with docstrings — the policy should teach *when* and *why* to act (principles, ordering, side-effects, resolution criteria), not *what tools exist*. Do not list agent or user tool names in the policy.
15. Declare valid task endings explicitly in `sampling_request.yaml` terminal profiles. Make tasks shorter by changing start states, not by stopping at intermediate fixable stages under a full-resolution policy.
16. (tau2 only) Persist both baseline seed files: `db.json` and `user_db.json`. The user DB is required package state, not optional glue. Keep it clean-base and encode task-specific user state only through runtime init actions.

Output format:

- `Step goal`
- `File to author`
- `Acceptance checks`
- `Rollback criteria`

Per-step completion report format:

- `Edited file`
- `Verification command`
- `Result: PASS|FAIL`
- `If FAIL: next minimal fix`
