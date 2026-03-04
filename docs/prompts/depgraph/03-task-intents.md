# Prompt 03: Fan-Out Sampling (No Manual Journeys)

## Instruction

Do not manually author golden journeys. Instead:

1. Author `data/tau2/domains/<domain>/sampling_request.yaml`.
2. Run the sampler to generate candidate task intents via graph fan-out:

```bash
uv run python -m tau2.generators.depgraph.run_sampler \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --sampling-request data/tau2/domains/<domain>/sampling_request.yaml \
  --out-task-specs data/tau2/domains/<domain>/task_specs.sampled.yaml
```

`sampling_request.yaml` must define:

1. `max_tasks`
2. `goal_world_path_prefixes`
3. optional `goal_binding_prefixes`
4. `seeds[]`:
   - `seed_id`
   - `start_world` (list of `{path, set}`)
   - optional `start_bindings`
   - `min_depth`
   - `max_depth`

Requirements:

1. At least one seed should require a `knowledge-only` action (binding dependency).
2. At least one seed should require a user causal action (dependency on projected `user.*` world paths).
3. Use `min_depth >= 4` for long-horizon chains.
4. Keep sampled tasks fail-closed: only keep tasks that pass preflight in sampler output.
5. Prefer multiple seeds with varied starting worlds (not just one start state clone) to increase downstream task diversity.
6. Keep structure abstract:
   - no concrete customer/account IDs in sampled intents
   - bind concrete entities later in runtime enrichment.

Acceptance checks:

1. `task_specs.sampled.yaml` is generated.
2. Every sampled task has non-empty `required_actions`.
3. Every sampled task has non-empty `goal_world` or `goal_bindings`.
4. No sampled task has contradictory world goals.
5. Sample includes at least one assistant-heavy and one user-heavy chain where possible for the domain.
