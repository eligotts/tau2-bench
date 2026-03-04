# design/

This folder contains architecture and authoring-system material.

## Active Now

Use this as the current source of truth:

- [/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md](/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md)
- [/Users/eligottlieb/Documents/tau2-bench/design/tau2/depgraph_to_tau2_primitive_mapping.md](/Users/eligottlieb/Documents/tau2-bench/design/tau2/depgraph_to_tau2_primitive_mapping.md)

It defines the dependency-graph tau2 system we are actively pursuing.

## Layout

1. `tau2/`
- Active: `dependency_graph_domain_plan.md`
- Current-only architecture docs for the dependency-graph direction.

2. `framework/`
- Legacy format-agnostic graph framework from earlier iteration.
- Keep for reference; do not treat as current build target.

3. `legacy/`
- Archived design-era material moved out of the main path:
  - `legacy/tau2/` (old tau2 design adapters and render/pipeline code)
  - `legacy/guides/`
  - `legacy/ideas/`
  - `legacy/examples/`

## Current Engineering Direction

- Runtime remains in `src/tau2/`.
- Existing domains remain in `src/tau2/domains/` + `data/tau2/domains/`.
- New dependency-graph implementation work should be added as new code paths, not by broad refactors of existing runtime/domain artifacts.

## Related Indexes

- Repo map: [/Users/eligottlieb/Documents/tau2-bench/docs/repo_map.md](/Users/eligottlieb/Documents/tau2-bench/docs/repo_map.md)
- Domain provenance: [/Users/eligottlieb/Documents/tau2-bench/docs/domain_provenance.md](/Users/eligottlieb/Documents/tau2-bench/docs/domain_provenance.md)
