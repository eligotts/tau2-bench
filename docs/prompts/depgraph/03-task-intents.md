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
2. `terminal_profiles[]`:
   - `profile_id`
   - `requires_world`
3. `seed_schemas[]`:
   - `schema_id`
   - `seed_id_template`
   - `allowed_terminal_profiles`
   - `min_depth`
   - `max_depth`
   - `dimensions[]`
     - `dimension_id`
     - `variants[]`
       - `variant_id`
       - optional `start_world`
       - optional `start_bindings`
       - optional `min_depth_delta`
       - optional `max_depth_delta`

Optional: `terminal_schemas[]` for combinatorial terminal profile expansion:
   - `schema_id`
   - `profile_id_template`
   - optional `description_template`
   - optional `requires_world` (shared predicates for all expanded profiles)
   - `dimensions[]`
     - `dimension_id`
     - `variants[]`
       - `variant_id`
       - `requires_world`

Requirements:

1. At least one seed should require a `knowledge-only` action (binding dependency).
2. At least one seed should require a user causal action (dependency on projected `user.*` world paths).
3. Use `min_depth >= 4` for long-horizon chains.
4. Keep sampled tasks fail-closed: only keep tasks that pass preflight in sampler output.
5. Keep structure abstract:
   - no concrete customer/account IDs in sampled intents
   - bind concrete entities later in runtime enrichment.
6. Every sampled task must end in an explicit terminal profile. Do not use intermediate repair states as ordinary task ends.
7. `goal_world` is populated directly from the matched terminal profile's `requires_world` predicates. There is no diff capture.
8. Author start-state variation only through `seed_schemas`. Direct `seeds[]` authoring is removed.
9. Set `min_depth` against the true shortest reachable plan for each expanded seed variant, not against an intuitive "expected journey". If a `knowledge` variant removes a discovery step, its floor must drop too.

## Goal Model

The goal model is terminal-profile-driven:

- `terminal_profiles` declare which committed world states are valid task ends.
- When BFS reaches a state satisfying a terminal profile's `requires_world`, the profile's predicates become the task's `goal_world`.
- There is no separate goal capture mechanism. The terminal profile IS the goal definition.
- Bindings must be consumed by downstream actions before terminality. Terminal profiles are world-only (no binding requirements).

## Deduplication

Tasks are deduped by `(seed_id, terminal_profile_id)`:

- Different BFS paths from the same seed to the same terminal profile collapse to one task.
- The first (shortest) BFS path wins.
- This means each seed can produce at most one task per allowed terminal profile.

## Terminal Schemas

When the domain has combinatorial terminal profiles (e.g., multi-lane domains where each
lane can end in one of several states), use `terminal_schemas` instead of hand-listing
every combination:

```yaml
terminal_schemas:
  - schema_id: multi_lane
    profile_id_template: "{lane_a}_{lane_b}"
    requires_world:
      - path: agent.common_status
        value: done
    dimensions:
      - dimension_id: lane_a
        variants:
          - variant_id: completed
            requires_world:
              - path: agent.lane_a.status
                value: completed
          - variant_id: cancelled
            requires_world:
              - path: agent.lane_a.status
                value: cancelled
      - dimension_id: lane_b
        variants:
          - variant_id: completed
            requires_world:
              - path: agent.lane_b.status
                value: completed
          - variant_id: skipped
            requires_world:
              - path: agent.lane_b.status
                value: skipped
```

Expanded profiles are merged with any directly-authored `terminal_profiles`. Use
`terminal_schemas` when profile count grows past 4-5 and follows a clear dimensional pattern.

## Seed Design for Structural Diversity

Seeds control which subgraphs of the contract are activated. The goal is to produce tasks
that differ in **topology** (which actions are needed and how they connect), not just
**depth** (how many steps of the same chain).

## Seed Schemas

When a domain has a small number of recurring start-state patterns, author `seed_schemas`
instead of manually copying many concrete seeds.

- A `seed_schema` defines:
  - a family-level depth budget and terminal-profile set
  - one or more variation dimensions
  - a `seed_id_template` that combines chosen variant ids into concrete seed ids
- Each concrete expanded seed is still a normal BFS root.
- The sampler expands schemas before search, so preflight/runtime behavior stays identical.

Use `seed_schemas` when the domain varies along finite axes such as:

- branch family (`billing`, `connectivity`, `full_system`)
- blocker subset (`hold`, `fraud`, `payment`)
- partial-knowledge variant (`base`, `screen_known`, `app_known`)
- shared downstream blockers (`allowlist`, `tariff`, `reservation`)

Do not use `seed_schemas` to create checkpoint starts halfway through the repair funnel.
The generated concrete seeds should still look like plausible incoming cases.

### Design seeds around value-gated branches

If the contract has value-gated actions (e.g., `fault_class == "billing"` enables one path,
`fault_class == "network"` enables a different path), create separate seeds for each branch:

- Seed A: `start_world` includes `fault_class = billing` -> activates billing recovery path
- Seed B: `start_world` includes `fault_class = network` -> activates network recovery path
- Seed C: `start_world` includes both faults broken -> activates both paths

These seeds produce structurally different tasks, not just shorter/longer versions of one chain.

### Use fate flags as a seed dimension

If the contract has fate-flagged action pairs (success/fail variants gated by `init_only`
booleans), model the fate flag combinations as a seed schema dimension:

```yaml
- dimension_id: service_fate
  variants:
    - variant_id: all_succeed
      start_world:
        - path: agent.rideshare_will_succeed
          set: true
        - path: agent.delivery_will_succeed
          set: true
    - variant_id: rideshare_fails
      start_world:
        - path: agent.rideshare_will_succeed
          set: false
        - path: agent.delivery_will_succeed
          set: true
    - variant_id: delivery_fails
      start_world:
        - path: agent.rideshare_will_succeed
          set: true
        - path: agent.delivery_will_succeed
          set: false
    - variant_id: both_fail
      start_world:
        - path: agent.rideshare_will_succeed
          set: false
        - path: agent.delivery_will_succeed
          set: false
```

Each variant activates structurally different action paths. Combined with other dimensions
(knowledge, resource level, active lanes), fate flags are the highest-leverage diversity axis.

### Vary which bindings are pre-acquired

If the contract has multiple bindings, create seeds where:
- No bindings are pre-acquired (agent must discover everything)
- One binding is pre-acquired via `start_bindings` (partial knowledge)
- Different bindings are pre-acquired in different seeds

This produces tasks that differ in what the agent needs to discover.

When using `seed_schemas`, model these as one dimension instead of cloning whole seeds.

Important: `start_bindings` often shorten the true shortest plan by one or more steps. If a
schema includes `cold`, `one_known`, and `both_known` variants, either:
- give the knowledge variants explicit `min_depth_delta` reductions, or
- keep the schema-level `min_depth` low enough that the shortest known variants still satisfy it.

Otherwise the sampler may emit a witness path at the schema floor while preflight later finds a
shorter satisfiable plan and rejects the task for `min_plan_length` / `required_actions` mismatch.

### Prefer real entry states over post-repair milestones

When you want more cheap seeds, first add:
- New branch combinations in the initial broken state
- New `start_bindings` combinations (partial knowledge)
- Externally plausible pre-contact state differences

Do **not** add seeds that are just the domain's own repair path with several earlier
steps already completed. In practice, avoid starts like:
- `diagnostics_state = ran` when the normal same-session path begins at `idle`
- `profile_state = ready` or `retry_state = ready` while the main repair chain is still in flight
- user physical/app remediation fields already advanced unless the scenario explicitly models that
  as customer-done work before the session begins

A good cheap seed should still look like a legitimate incoming ticket, not like a saved
checkpoint halfway through the benchmark's own solution path.

### Vary which lanes are active

Instead of just "everything broken" vs "less broken," think in terms of which parallel
lanes need work:

- Seed where only the user-side lane is active (agent-side pre-solved)
- Seed where only one agent-side branch is active
- Seed where cross-lane coordination is the core challenge (both lanes partially broken,
  requiring interleaved work)
- If you add a new shared downstream lane, prefer seeds that vary which subset of that lane's
  blockers is active. This increases both task count and path depth without turning tasks into
  post-repair checkpoint starts.

### Multi-lane seeds for cross-lane coverage

When the domain has parallel lanes (errands, calendar, care, household), create seed
schemas that combine 2-3 lanes in a single seed. This is how you populate multi-lane
terminal profiles (e.g., `errands_care_done`, `cancelled_care_household`).

Each multi-lane schema should set ALL lanes' fields explicitly in `start_world` -- both
the active lanes (with their broken/pending states) and the inactive lanes (with their
resolved/not-applicable states). If a lane isn't relevant to the seed, set its status to
the terminal value so the terminal profile's requirements are already met for that lane.

**Common mistake:** Creating a terminal profile that requires 3 lanes to be resolved, but
no seed schema activates all 3 lanes. If `cancelled_care_household` requires cancelled
meeting + care completed + household completed, you need a schema that starts with all
three lanes active.

### Avoid depth-only variation

**Anti-pattern:** 5 seeds that are identical except for how many actions are pre-completed
in the same chain. This produces tasks that look different (depth 5 vs depth 12) but test
identical reasoning, and often turns one task's start state into another task's mid-trajectory
checkpoint.

**Good pattern:** 5 seeds that activate different subgraphs, different binding requirements,
or different value-gated branches. Even if depths overlap, the tasks test different
decision-making.

**Better pattern:** 3 `seed_schemas` with a few finite dimensions each, expanded into many
concrete seeds that still differ in branch structure, blocker mix, or known information.

### Leverage cascading sync rules in seed design

If the graph contract has cascading sync rules (e.g., `db_unhealthy -> cache_stale`),
single-fault seeds automatically become multi-system tasks. This means:

- **Remove redundant multi-fault seeds.** If `db_corrupted` automatically cascades to
  `cache_stale`, don't also create a `db_corrupted + cache_stale` seed -- it's redundant.
  Instead, create `db_corrupted + cache_eviction_storm` (a DIFFERENT cache fault that the
  sync rule wouldn't produce).
- **Single-fault seeds are now your highest-value seeds** because cascading turns them into
  multi-system tasks with non-obvious damage that the agent must discover.
- **Multi-fault seeds should combine systems that DON'T cascade into each other**, to
  create truly independent parallel repair lanes.

### Side-effect seeds

If the graph contract has repair side-effects (e.g., `failover_db -> dlq_has_messages`),
account for the extra work in depth estimates. A single `db_corrupted` seed may need
depth 12+ (investigation + triage + failover + DLQ replay + cache repair from cascade +
comms + smoke test) even though it looks like a "single fault."

### Depth estimation for complex domains

Cascading sync rules, repair side-effects, and multi-step chains all expand depth beyond
what the raw fault count suggests. Use this formula to estimate `min_depth` for a seed:

```
base_depth = (investigation actions) + (triage) + (comms)
per_fault_depth = sum of repair chain length for each fault
cascade_depth = number of systems damaged by cascading rules x avg repair steps
side_effect_depth = number of side-effects that require cleanup
verification_depth = smoke test + any DNS/network verification steps

estimated_depth = base_depth + per_fault_depth + cascade_depth + side_effect_depth + verification_depth
```

**Rule of thumb by seed type:**
- Single fault, no cascading: `min_depth` 5-8
- Single fault with cascading: `min_depth` 8-12
- Two faults with cross-dependencies: `min_depth` 10-14
- Three faults or fault + side-effect chain: `min_depth` 13-18
- Complex cascading + traps: `min_depth` 15-20

Set `max_depth` to `estimated_depth + 4` to give BFS headroom for alternative paths.
If BFS times out on a seed, the depth budget is likely too tight -- increase `max_depth`
before assuming the seed is unsolvable.

After authoring a schema, sanity-check the shortest variants explicitly:
- `cold` should usually define the upper end of the family
- `known` variants should often be 1-2 steps shorter
- if the sampler no longer canonicalizes with a separate re-solve, stale `min_depth` floors
  become visible immediately in preflight

### Diversity quantification targets

When evaluating sampled output, use these targets:
- **60%+ unique action sets** (distinct `required_actions` ignoring order)
- **3+ distinct plan topologies** (different DAG shapes, not just depth variation)
- **All terminal profiles represented** (at least 2 tasks per profile)
- **Depth spread** -- tasks should span at least a 2:1 ratio (e.g., 6-step to 14-step)
- **No single action appearing in >80% of tasks** (unless it's universal like triage/comms)

### Terminal profile reachability

**Critical bug pattern:** A terminal profile requires a condition that some seeds can never
achieve. Example: `cascading_resolved` requires `connectivity_verified`, which needs
`dns_flushed_locally=done`, which needs DNS to have been server-side flushed. But many
cascading seeds have no DNS fault, so DNS was never flushed, so `dns_flushed_locally`
can never be set, so the seed is unsolvable.

Always verify: for every (seed, terminal_profile) pair in `allowed_terminal_profiles`,
can the BFS actually reach that profile? If a profile has extra requirements beyond
"all systems healthy," ensure those requirements are achievable for all seeds that target
that profile.

### Initialize all fields referenced by terminal profiles and action preconditions

**Critical bug pattern:** A terminal profile requires `apology_sent=true`. The action
`send_apology` requires `apology_sent=false` as a precondition. But the seed never
initializes `apology_sent`, so its value is `None`. `None != false`, so the precondition
fails, and the terminal profile is unreachable.

**Rule:** Every field that appears in a terminal profile's `requires_world` or in any
action's `requires_world` with an explicit value check MUST be initialized in seed
`start_world` if that seed needs to traverse actions involving that field. The BFS treats
uninitialized fields as `None`, which doesn't match `false`, `0`, `"not_needed"`, or any
other default-looking value.

When in doubt, initialize boolean fields to `false`, enum fields to their "not started"
value, and status fields to their initial state.

**Companion field rule:** When a seed sets a status field to a fault value (e.g.,
`auth_health=cert_invalid`), check the repair action's guard conditions. If the repair
guards on a detail field (`cert_state != valid`), the seed MUST also set that detail field
to a broken value (`cert_state=expired`). Otherwise the repair action will noop or error
because the detail field defaults to its "healthy" value.

This applies across ALL seed schemas — if the same fault appears as a primary fault in
one schema and a secondary fault in another (e.g., `two_fault_cases`, `cascading_cases`),
the companion field must be set in every variant. Search the entire sampling_request for
the fault value and fix all occurrences, not just the first schema you find.

Also verify the companion value is a valid enum member. Check the data model's enum
definition before using a value (e.g., `TokenPool` has `valid/refreshed/invalid`, not
`expired`).

### Schema fertility and post-hoc balancing

Some seed schemas are naturally more fertile than others. A schema with 30 seeds and deep
BFS trees (care delegation with multiple fate flags) may produce 300+ tasks, while a
schema with 4 seeds and short linear paths (cancel meeting + pay bill) produces only 8.

If the sampler processes seeds sequentially, fertile schemas consume the `max_tasks` budget
before sparse schemas are reached. Two mitigations:

1. **Set `max_tasks` high enough** to exhaust all seeds (not just the first few schemas).
   Run once with a very high cap to see the natural ceiling, then decide.
2. **Post-hoc per-schema capping**: After sampling all tasks, cap each schema to N tasks
   to produce a balanced evaluation set. Use `cap_per_schema()` from the sampler module.
   This preserves the shortest/best tasks from each schema while preventing any single
   schema from dominating.

Target: no schema should contribute more than 25% of the final task set unless the domain
has very few schemas.

### BFS performance with cascading

Cascading sync rules increase BFS state space because more systems are broken (more
investigation actions can fire, more triage options exist). Monitor per-seed BFS time:

- < 100ms/seed: excellent
- 100ms-1s/seed: acceptable
- 1-5s/seed: borderline, check for optional binding explosion
- > 5s/seed: investigate -- likely optional investigation actions or too many triage variants

The main BFS explosion risk is **optional knowledge-only actions** that can fire for any
seed. Gate investigation actions on the relevant system being unhealthy AND on
`triage_state=not_run` to prevent post-triage binding explosion.

## Terminal Profiles

Terminal profiles define the states that count as legitimate task endings.
They are world-only: terminal profiles declare `requires_world` predicates
but not binding requirements. If the domain needs knowledge acquisition
before terminality, model it through a final consuming action whose
`effects_world` satisfies the terminal profile.

- Put terminality in `terminal_profiles`, not in ad hoc depth cutoffs.
- A seed may only emit tasks whose end state matches one of its `allowed_terminal_profiles`.
- The terminal profile's `requires_world` predicates become the task's `goal_world` directly.
- Shorter tasks should come from seeds that start closer to resolution, not from stopping in
  the middle of an otherwise-fixable repair chain.
- Sampled tasks should be canonicalized to the minimal terminal-reaching plan.
  Optional extra reads or unused binding acquisitions should not create separate task variants.
- Fail closed on frame drift: if a sampled terminal plan changes authored start-state paths
  outside the terminal profile's `requires_world`, that is acceptable incidental state change
  (not penalized, not rewarded).
- If the domain needs milestone tasks, model them explicitly as milestone profiles with a
  matching prompt/tool surface. Do not reuse a full-resolution policy and then stop halfway.

Acceptance checks:

1. `task_specs.sampled.yaml` is generated.
2. Every sampled task has non-empty `required_actions`.
3. Every sampled task has non-empty `goal_world` (populated from terminal profile).
4. No sampled task has contradictory world goals.
5. Sample includes at least one assistant-heavy and one user-heavy chain where possible for the domain.
6. **Structural diversity check**: count distinct `required_actions` sets (ignoring order)
   across all sampled tasks. At least 60% of tasks should have a unique action set, not
   just a prefix/suffix of another task's set.
7. Every sampled task has a non-empty `terminal_profile_id`.
8. Sampling does not emit duplicate tasks: dedup is by `(seed_id, terminal_profile_id)`.
9. Cheap seed expansion prefers new early entry states or binding-known variants over
   post-repair checkpoint starts.
10. If the domain has many near-copy starts, they are authored as `seed_schemas` rather than
    hand-maintained concrete seed lists.
