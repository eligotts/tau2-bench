# Repo Map

This map is for new contributors and coding agents.

## Active Workstream

Current architecture and planning source of truth:

- [/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md](/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md)

This is the dependency-graph tau2 plan (state model, contracts, SAT checks, authoring flow).

## Runtime (Stable)

- `src/tau2/`:
  - runtime loop, orchestrator, environment, evaluator, registry
  - task schema and execution engine

Treat this lane as stable runtime infrastructure.

## Existing Domain Artifacts

- `src/tau2/domains/`
- `data/tau2/domains/`

Existing benchmark domains live here. They remain valid runtime assets and should not be reorganized broadly.

## Active New Implementation Target

When implementing the dependency-graph system, prefer new isolated code paths:

- `src/tau2/generators/depgraph/` (new package)
- domain-level `graph_contract.py` and task intent specs
- prompt pack: `docs/prompts/depgraph/`
- skill wrapper: `.claude/skills/depgraph-bootstrap/SKILL.md`

## Legacy / Reference

- `design/legacy/` (old guides, ideas, examples)
- `design/legacy/tau2/` (old tau2 design adapters and render/pipeline code)
- `design/framework/` (legacy generic framework)
- `docs/archive/` (old authoring docs and skills)

These are reference only and should not be treated as active architecture directives.
