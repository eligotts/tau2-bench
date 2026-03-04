# Depgraph Trial Run Plan

This is the concrete order of operations to test the new dependency-graph pipeline quickly and expose gaps early.

Architecture source of truth:

- `/Users/eligottlieb/Documents/tau2-bench/design/tau2/dependency_graph_domain_plan.md`

Prompt pack:

- `/Users/eligottlieb/Documents/tau2-bench/docs/prompts/depgraph/`

Fact namespace convention:

- `agent.*` = backend/world causal facts
- `user.causal.*` = user-side causal facts
- `K.*` = assistant knowledge facts

## Phase 0: Minimal bootstrap (1 domain, 1 chain)

Goal: prove end-to-end viability with a tiny slice.

1. Pick one pilot domain (recommended: `tech_support` or `telecom` style flow).
2. Author world scope (`domain_scope.md`) describing agent DB, user DB, tools, and world logic.
3. Author minimal graph contract (4-8 facts, 4-8 transitions).
4. Author sampling request.
5. Sample structural intents via fan-out.
6. Add runtime payloads to sampled intents.
7. Run SAT preflight checks + runtime alignment checks.
8. Compile passing intents to tau2 tasks.

Exit criteria:

- at least 1 task passes all dependency checks and compiles.

## Phase 1: Hardening checks

Goal: prevent false-positive solvability.

1. Add contradiction checks (mutex/invariants).
2. Add `SAT_without_d` required-action ablations.
3. Add runtime callable alignment checks (`initialization_actions` / `env_assertions`).
4. Add fact-source extraction path sanity/schema checks.
5. Add no-shortcut validation for goal facts.

Exit criteria:

- failed dependency design is rejected deterministically.

## Phase 2: Tau2 integration quality

Goal: ensure preflight semantics align with runtime.

1. Map start facts to `initialization_actions`.
2. Map goals to `env_assertions`.
3. Mirror `sync_tools()` causal effects in contracts.
4. Verify no leakage between ticket/known_info and hidden discovery facts.

Exit criteria:

- preflight-passing task also behaves correctly under tau2 runtime verification.

## Phase 3: Scale and authoring ergonomics

Goal: make this usable for larger domain generation.

1. Expand prompt pack with richer templates and anti-pattern checks.
2. Add domain-level `graph_contract` + `task_specs` conventions.
3. Add regression tests for solver and compiler.
4. Add CLI entrypoint for depgraph preflight/compile.

Exit criteria:

- repeatable generation of small task sets with clear failure diagnostics.

## Phase 4: Runtime Domain Porting

Goal: convert depgraph-authored artifacts into executable tau2 domain runtime code.

1. Author runtime models and seed files (`data_model.py`, `user_data_model.py`, `db.json`, `user_db.json`, `utils.py`).
2. Author runtime toolkits (`tools.py`, `user_tools.py`) including `set_*` and `assert_*` helpers referenced in runtime specs.
3. Author environment wiring (`environment.py`) including `sync_tools()` bridges aligned with contract effects.
4. Register the domain in `src/tau2/registry.py`.
5. Re-run depgraph preflight/compile with `--domain <domain>` and ensure clean pass.

Exit criteria:

- domain loads through registry
- contract/runtime alignment checks are clean
- compiled task set is runnable through tau2 task loader path

## Immediate Next Step (do this first)

Run the full pilot pipeline on one domain:

```bash
uv run python -m tau2.generators.depgraph.run_sampler \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --sampling-request data/tau2/domains/<domain>/sampling_request.yaml \
  --out-task-specs data/tau2/domains/<domain>/task_specs.sampled.yaml
```

Then enrich runtime blocks and compile:

```bash
uv run python -m tau2.generators.depgraph.run_compile \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --out data/tau2/domains/<domain>/tasks.depgraph.json
```
