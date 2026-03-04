# Prompt 00: Session Contract

Use this at the start of any depgraph authoring run.

## Instruction

You are building a tau2 dependency-graph domain pipeline.

Hard constraints:

1. Treat `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md` as architecture source of truth.
2. Do not use legacy pipeline docs (`design/legacy/*`, `docs/archive/*`) as implementation directives.
3. Edit only one minimal file per step.
4. After each step, run verification and report pass/fail with exact command.
5. Prefer explicit v2 transition contracts (`requires_world/requires_bindings/effects_world/effects_bindings`) over implicit logic.
6. Fail closed: never emit compiled tasks when preflight or runtime alignment checks fail.
7. Do not manually author task journeys; structural intents must come from sampler fan-out.
8. Preserve creativity by constraining semantics/contracts, not narrative style/domain theme.
9. Do not mutate generated structural fields (`required_actions`, `required_precedence`) by hand.
10. Re-run `/Users/eligottlieb/Documents/tau2-bench/docs/prompts/depgraph/CHECKLIST.md` after each major phase.

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
