# Prompt 05: Rubric Review + Gap Review

Use this prompt in one of two modes:

- `Mode A: authoring audit` before simulation, sign-off, or PR
- `Mode B: post-run gap review` after simulation traces exist

The coding agent should use a code-review mindset in both modes: findings first, ordered by
severity, with exact file/function evidence and testable fixes.

## Mode A: Authoring Audit

### Goal

Ask the coding agent to review the authored domain against a fixed rubric before you spend
time on LLM simulations.

### Required inputs

- `data/tau2/domains/<domain>/review_bundle.md`
- the source files cited in that bundle, especially:
  - `domain_scope.md`
  - `graph_contract.yaml`
  - `policy.md`
  - `runtime_defaults.yaml`
  - `sampling_request.yaml`
  - `stop_gate_map.yaml`
  - `tools.py`
  - `user_tools.py`
  - `environment.py`
  - `task_specs.runtime.yaml`

Generate the bundle first:

```bash
uv run python -m tau2.generators.depgraph.run_review_bundle \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --policy data/tau2/domains/<domain>/policy.md \
  --domain-scope data/tau2/domains/<domain>/domain_scope.md \
  --runtime-defaults data/tau2/domains/<domain>/runtime_defaults.yaml \
  --sampling-request data/tau2/domains/<domain>/sampling_request.yaml \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --out data/tau2/domains/<domain>/review_bundle.md
```

### Rubric

Judge the domain against these exact categories:

1. `policy_contract_parity`
   - Does `policy.md` teach domain knowledge (principles, ordering constraints, side-effects, resolution criteria) without listing tool names? Agent tools are injected via the API with docstrings; user tools are the user's to discover.
   - Does it teach the actual reread points and stop semantics the runtime requires?
   - Does it expose constraints and domain reasoning guidance without hardcoding a single exact repair trajectory or duplicating the tool catalog?
2. `volatile_binding_discipline`
   - Are volatile bindings only used for immediate observation-driven transitions?
   - Is any moving observation value threaded through a long repair chain?
   - Does every binding have a `world_path` that correctly tracks its canonical value?
3. `sync_rule_fidelity`
   - Is every derived/runtime-visible behavior declared in `sync_rules` in the graph contract?
   - Does `environment.sync_tools()` call `run_contract_sync()` from the `runtime_sync` module?
   - Is the contract the single source of truth for sync logic (no dual implementation)?
   - Do view projections (`display_*` fields) stay as adapter Python code, separate from contract sync rules?
4. `branch_specific_consistency`
   - Do policy, contract, sync logic, and stop-gates agree for each branch/family?
   - Are billing-only tasks free of hardware-only prerequisites unless intentionally modeled?
5. `terminal_profile_goal_alignment`
   - Does each task's `goal_world` match its terminal profile's `requires_world` predicates exactly?
   - Do sampled tasks end in explicit terminal profiles rather than intermediate repair states?
   - Do shorter tasks come from easier starts rather than partial endings?
   - Do sampled tasks reflect the minimal terminal-reaching plan, rather than duplicate variants
     created by optional extra reads or unused binding acquisitions?
   - If the domain uses `seed_schemas`, do the expanded starts represent genuine incoming-case
     variation rather than checkpoint states copied from the middle of the repair funnel?
6. `stop_gate_clarity`
   - Are user-observable completion fields projected and checked?
   - Does the policy tell the agent what to do for both `resolved=true` and `resolved=false`?
7. `reward_eval_fit`
   - Does `reward_basis` fit the task mechanics?
   - If reacquisition is expected, is correctness driven by `ENV_ASSERTION`/stop-gate rather than `ACTION` alone?
8. `task_realism_and_teachability`
   - Do representative SAT plans require behaviors the policy actually teaches?
   - Would an agent following the policy for domain reasoning plus its injected tool definitions for tool affordances know how to complete the representative tasks?
   - Do `reason_for_call`, `known_info`, and `ticket` stay at the user-observable case surface, or do they leak latent blocker inventories / internal path labels that pre-solve the task?
9. `difficulty_engineering` (for domains targeting strong agents)
   - Does the policy avoid being an answer key? (No direct fault->fix mappings that an LLM
     can pattern-match without reasoning.)
   - Do cascading sync rules or repair side-effects create non-obvious work the agent must
     discover? What percentage of tasks require reasoning beyond "read fault, apply fix"?
   - Are there sync-rule traps where naive repairs bounce back until the root cause is
     addressed?
   - Do resolution gates require side-effect cleanup, or is collateral damage "free"?
   - Are terminal profile requirements achievable for ALL seeds targeting that profile?
     (Check for unreachable preconditions like DNS verification for non-DNS seeds.)
10. `dedup_integrity`
    - Are tasks properly deduped by `(seed_id, terminal_profile_id)`?
    - Are there near-duplicate tasks that should have collapsed?

### Required output

Output sections, in this order:

1. `Findings`
   - ordered by severity
   - one finding per bullet
   - each finding must name the rubric category
   - each finding must cite exact file/function references
   - each finding must include the smallest concrete fix
2. `Open questions / assumptions`
3. `Residual risks`

### Minimum evidence per finding

Every failing finding must include:

1. the rubric category id
2. one exact file reference
3. one concrete symptom from `review_bundle.md`:
   - representative SAT plan requirement
   - repeated reacquisition pattern
   - branch mismatch
   - stop-gate mismatch
4. one testable acceptance criterion for the fix

### Hard rule

Do not proceed to simulation or sign-off until all high-severity findings are fixed or
explicitly waived.

## Mode B: Post-Run Gap Review

### Goal

After a pilot run, generate a concise root-cause analysis that attributes failures to the
right layer.

### Sections

1. `What worked`
2. `What failed`
3. `Modeling gaps` (world/binding contracts and binding sources)
4. `Solver gaps` (state explosion, weak checks, false SAT/UNSAT)
5. `Tau2 mapping gaps` (init actions, env assertions, sync behavior)
6. `Known-risk closure status` (from `domain_scope.md`)
7. `Top 3 next code changes`
8. `Failure attribution` (agent vs user-sim vs task/setup)
9. `Stop-gate adherence` (did user call checker, did stop condition match checker result)

### Quality bar

- no vague statements
- each gap must reference one concrete file/function
- each recommendation must have a testable acceptance criterion
- each failed task must include one explicit primary root-cause label:
  - `agent_policy/planning`
  - `user_sim_prompt_adherence`
  - `contract_runtime_mismatch`
  - `tool_semantics_bug`
  - `unsat_or_bad_task_design`

### Minimum evidence per failed task

1. expected required actions from task spec
2. observed tool-call sequence from trace
3. first divergence turn
4. whether env assertions failed because required actions were missing or because actions executed but had no causal effect
