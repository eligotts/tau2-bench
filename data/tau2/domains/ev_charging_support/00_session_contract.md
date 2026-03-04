# Depgraph Session Contract (v2): ev_charging_support

- Step goal:
  - Restart EV authoring under depgraph v2 with context slots, projection fields, monotonic bindings, and forward world effects.

- Files to author in this initial chunk:
  - `data/tau2/domains/ev_charging_support/domain_scope.md`
  - `data/tau2/domains/ev_charging_support/graph_contract.yaml`

- Acceptance checks:
  - Use `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md` as source of truth.
  - Use depgraph v2 contract shape (`version: 2`) from `src/tau2/generators/depgraph/types.py`.
  - Define context slots for active entity slice selection per task instance.
  - Define projection fields only for solver-relevant world paths.
  - Define bindings as monotonic (no stale binding invalidation in this version).
  - Define actions with `requires_world/requires_bindings/effects_world/effects_bindings`.
  - Keep fail-closed posture: no sampling/compile in this chunk.

- Out of scope for this chunk:
  - task sampling
  - runtime task specs
  - compile output
  - registry/simulation verification

- Rollback criteria:
  - If graph contract cannot parse as v2, revert and fix schema alignment before any next-step authoring.
  - If scope fields cannot be mapped to concrete tool/action contracts, reduce scope before proceeding.
