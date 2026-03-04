# Prompt 05: Gap Review

## Instruction

After a pilot run, generate a concise gap analysis.

Sections:

1. `What worked`
2. `What failed`
3. `Modeling gaps` (world/binding contracts and binding sources)
4. `Solver gaps` (state explosion, weak checks, false SAT/UNSAT)
5. `Tau2 mapping gaps` (init actions, env assertions, sync behavior)
6. `Known-risk closure status` (from `domain_scope.md`)
7. `Top 3 next code changes`
8. `Failure attribution` (agent vs user-sim vs task/setup)
9. `Stop-gate adherence` (did user call checker, did stop condition match checker result)

Quality bar:

- no vague statements
- each gap must reference one concrete file/function
- each recommendation must have a testable acceptance criterion
- each failed task must include one explicit primary root-cause label:
  - `agent_policy/planning`
  - `user_sim_prompt_adherence`
  - `contract_runtime_mismatch`
  - `tool_semantics_bug`
  - `unsat_or_bad_task_design`

Minimum evidence per failed task:

1. expected required actions from task spec
2. observed tool-call sequence from trace
3. first divergence turn
4. whether env assertions failed because required actions were missing or because actions executed but had no causal effect
