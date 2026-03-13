# tau2-bench

This file is the orientation guide for coding agents.

## What Is Active Right Now

The active architecture work is the tau2-first dependency graph plan:

- `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md`

Use that document as the source of truth for:

- state model (`S = (A, Uc, K)`)
- transition contracts (`requires/produces/invalidates`)
- SAT preflight solvability checks
- knowledge acquisition edges
- authoring pipeline for new dependency-graph domains

## Repo Lanes

1. Runtime lane (stable):
- `/Users/eligottlieb/Documents/tau2-bench/src/tau2/`
- This is the tau2 engine/runtime/evaluation layer. Do not refactor broadly unless explicitly requested.

2. Domain artifact lane (existing domains):
- `/Users/eligottlieb/Documents/tau2-bench/src/tau2/domains/`
- `/Users/eligottlieb/Documents/tau2-bench/data/tau2/domains/`
- These are existing benchmark domains produced by earlier pipelines. Keep them as runtime artifacts.

3. Architecture + authoring lane (active planning and new system work):
- `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md`
- Future implementation target should live under `src/tau2/generators/depgraph/` plus per-domain `graph_contract.py`/`task_specs`.

## Legacy Material (Reference Only)

- `/Users/eligottlieb/Documents/tau2-bench/docs/archive/simulation-trace-guide.md`

Do not treat any removed historical material as current architecture directives.

## Quick Navigation

- Active architecture plan:
  - `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md`
- Depgraph prompt pack:
  - `/Users/eligottlieb/Documents/tau2-bench/docs/prompts/depgraph/`
- Simulation trace guide:
  - `/Users/eligottlieb/Documents/tau2-bench/docs/archive/simulation-trace-guide.md`
