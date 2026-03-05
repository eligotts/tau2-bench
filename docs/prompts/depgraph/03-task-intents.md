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
3. `seeds[]`:
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
5. Keep structure abstract:
   - no concrete customer/account IDs in sampled intents
   - bind concrete entities later in runtime enrichment.

## Seed Design for Structural Diversity

Seeds control which subgraphs of the contract are activated. The goal is to produce tasks
that differ in **topology** (which actions are needed and how they connect), not just
**depth** (how many steps of the same chain).

### Design seeds around value-gated branches

If the contract has value-gated actions (e.g., `fault_class == "billing"` enables one path,
`fault_class == "network"` enables a different path), create separate seeds for each branch:

- Seed A: `start_world` includes `fault_class = billing` → activates billing recovery path
- Seed B: `start_world` includes `fault_class = network` → activates network recovery path
- Seed C: `start_world` includes both faults broken → activates both paths

These seeds produce structurally different tasks, not just shorter/longer versions of one chain.

### Vary which bindings are pre-acquired

If the contract has multiple bindings, create seeds where:
- No bindings are pre-acquired (agent must discover everything)
- One binding is pre-acquired via `start_bindings` (partial knowledge)
- Different bindings are pre-acquired in different seeds

This produces tasks that differ in what the agent needs to discover.

### Vary which lanes are pre-solved

Instead of just "everything broken" vs "less broken," think in terms of which parallel
lanes need work:

- Seed where only the user-side lane is active (agent-side pre-solved)
- Seed where only one agent-side branch is active
- Seed where cross-lane coordination is the core challenge (both lanes partially broken,
  requiring interleaved work)

### Avoid depth-only variation

**Anti-pattern:** 5 seeds that are identical except for how many actions are pre-completed
in the same chain. This produces tasks that look different (depth 5 vs depth 12) but test
identical reasoning.

**Good pattern:** 5 seeds that activate different subgraphs, different binding requirements,
or different value-gated branches. Even if depths overlap, the tasks test different
decision-making.

Acceptance checks:

1. `task_specs.sampled.yaml` is generated.
2. Every sampled task has non-empty `required_actions`.
3. Every sampled task has non-empty `goal_world` (bindings alone are not sufficient — goals must be verifiable DB state).
4. No sampled task has contradictory world goals.
5. Sample includes at least one assistant-heavy and one user-heavy chain where possible for the domain.
6. **Structural diversity check**: count distinct `required_actions` sets (ignoring order)
   across all sampled tasks. At least 60% of tasks should have a unique action set, not
   just a prefix/suffix of another task's set.
