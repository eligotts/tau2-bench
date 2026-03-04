# depgraph

Dependency-graph authoring pipeline for tau2-compatible tasks.

Purpose:

- load prompt-authored graph contracts and sampling/task specs
- run causal solvability checks with dependency necessity and contradiction guards
- sample structural tasks via graph fan-out
- compile only passing tasks into tau2 `Task` json with runtime payload checks

Source-of-truth architecture:

- `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md`

Key modules:

- `types.py`: contract/spec/runtime schemas
- depgraph v2 contracts include context slots, projected world paths, binding sources, and action binding gates
- `semantics.py`: action eligibility over `(world, bindings)` and binding-source observability
- `loaders.py`: YAML loading and schema parsing
- `solver.py`: world-state BFS search (state key is projected world assignments + bindings)
- `preflight.py`: SAT checks (`SAT_full`, required-action ablations, contradiction checks)
- `runtime_checks.py`: env/tool alignment checks, binding-source extraction-path checks, and runtime callable/argument validation
- `stop_gate.py`: goal->observable stop-gate mapping, runtime injection, and stop-gate validation
- `sampler.py`: fan-out sampling for structural task intents
- `compiler.py`: fail-closed preflight+compile to tau2 `Task`
- `run_preflight.py`: CLI preflight report
- `run_sampler.py`: CLI sampler
- `run_stop_gate_inject.py`: CLI to inject strict `set_stop_gate` criteria into runtime specs
- `run_compile.py`: CLI compile path
