---
name: depgraph-bootstrap
description: Bootstrap and trial-run the tau2 dependency-graph authoring pipeline using prompt-authored contracts/specs plus deterministic SAT preflight checks.
user_invocable: true
---

# Depgraph Bootstrap

Use this skill when building or iterating on the dependency-graph pipeline.

## Source of truth

- `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md`

## Prompt pack

- `/Users/eligottlieb/Documents/tau2-bench/docs/prompts/depgraph/`

## Fact namespaces

- `agent.*`: backend/world causal facts
- `user.causal.*`: user-side causal facts
- `K.*`: assistant knowledge facts

Run prompts in this order:

1. `00-session-contract.md`
2. `01-domain-scope.md`
3. `02-graph-contract.md`
4. `03-task-intents.md`
5. `04-preflight-and-compile.md`
6. `05-gap-review.md`
7. `06-runtime-models-and-seeds.md`
8. `07-runtime-tools-and-assertions.md`
9. `08-runtime-environment-and-sync.md`
10. `09-registry-and-e2e-verification.md`

## Implementation target

- `/Users/eligottlieb/Documents/tau2-bench/src/tau2/generators/depgraph/`

## Required outputs for a pilot

1. world scope (`domain_scope.md`)
2. graph contract (`graph_contract.yaml`)
3. sampling request (`sampling_request.yaml`)
4. sampled structural intents (`task_specs.sampled.yaml`)
5. runtime-enriched intents (`task_specs.runtime.yaml`)
6. preflight report (`SAT_full`, ablation UNSAT, contradiction checks)
7. compiled tau2 tasks (`tasks.depgraph.json`) for passing intents
8. runtime domain package under `src/tau2/domains/<domain>/`
9. registry wiring + registry-based load/compile verification

## Rules

- Do not use legacy design docs as implementation directives.
- Keep edits incremental and verifiable.
- Fail closed: do not emit task when required preflight checks fail.
