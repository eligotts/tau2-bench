# Domain Provenance

This file records where existing domains came from so new work does not mix pipelines accidentally.

## Existing Domains

| Domain | Artifact Paths | Authoring Lineage | Status |
|---|---|---|---|
| `airline` | `src/tau2/domains/airline`, `data/tau2/domains/airline` | Legacy pre-dependency-graph pipeline | Runtime artifact |
| `retail` | `src/tau2/domains/retail`, `data/tau2/domains/retail` | Legacy pre-dependency-graph pipeline | Runtime artifact |
| `telecom` | `src/tau2/domains/telecom`, `data/tau2/domains/telecom` | Legacy pre-dependency-graph pipeline | Runtime artifact |
| `library` | `src/tau2/domains/library`, `data/tau2/domains/library` | Legacy synthetic/recipe-style pipeline | Runtime artifact |
| `fitness_gym` | `src/tau2/domains/fitness_gym`, `data/tau2/domains/fitness_gym` | Legacy synthetic/recipe-style pipeline | Runtime artifact |
| `auto_repair` | `src/tau2/domains/auto_repair`, `data/tau2/domains/auto_repair` | Legacy synthetic/recipe-style pipeline | Runtime artifact |
| `online_shopping` | `src/tau2/domains/online_shopping`, `data/tau2/domains/online_shopping` | Legacy synthetic/recipe-style pipeline | Runtime artifact |
| `tech_support` | `src/tau2/domains/tech_support`, `data/tau2/domains/tech_support` | Legacy synthetic/recipe-style pipeline | Runtime artifact |
| `travel_agency` | `src/tau2/domains/travel_agency`, `data/tau2/domains/travel_agency` | Legacy synthetic/recipe-style pipeline | Runtime artifact |
| `vet_clinic` | `src/tau2/domains/vet_clinic`, `data/tau2/domains/vet_clinic` | Legacy synthetic/recipe-style pipeline | Runtime artifact |
| `mock` | `src/tau2/domains/mock` | Utility/mock domain | Runtime utility |

## Current Plan for New Domains

New domain authoring should follow:

- [/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md](/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md)

Do not mix old authoring assumptions with new dependency-graph contracts in the same domain implementation.

