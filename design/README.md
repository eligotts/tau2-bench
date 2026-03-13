# design/

This folder contains architecture and authoring-system material.

## Active Now

Use this as the current source of truth:

- [/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md](/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md)

It defines the dependency-graph tau2 system we are actively pursuing.

## Layout

1. `tau2/`
- Active: `dependency_graph_domain_plan.md`
- Current-only architecture docs for the dependency-graph direction.

## Current Engineering Direction

- Runtime remains in `src/tau2/`.
- Existing domains remain in `src/tau2/domains/` + `data/tau2/domains/`.
- New dependency-graph implementation work should be added as new code paths, not by broad refactors of existing runtime/domain artifacts.
