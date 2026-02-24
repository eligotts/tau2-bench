# Step 10.5: Exhaustive Domain Audit

Read ALL generated files for the domain and perform these 12 audits. For each audit, enumerate EVERY item and verify individually. Do NOT skip items or summarize — trace each one.

## Files to Read

Read all of these before starting the audits:

- `data/tau2/domains/<domain_name>/domain_spec.json` — including the `archetype` field
- `src/tau2/domains/<domain_name>/data_model.py`
- `src/tau2/domains/<domain_name>/user_data_model.py`
- `src/tau2/domains/<domain_name>/tools.py`
- `src/tau2/domains/<domain_name>/user_tools.py`
- `src/tau2/domains/<domain_name>/environment.py`
- `src/tau2/domains/<domain_name>/utils.py`
- `src/tau2/domains/<domain_name>/scenarios.py`
- `data/tau2/domains/<domain_name>/db.json`
- `data/tau2/domains/<domain_name>/user_db.json`
- `data/tau2/domains/<domain_name>/policy.md`
- `docs/skills/00-archetype.md` — for archetype-specific expectations

## Audit 1: Per-FaultLayer Chain Verification (ERROR)

For EVERY FaultLayer defined in scenarios.py, trace the complete chain. List each layer by its variable name and verify:

a) **init_calls**: Each `InitCall.func_name` must be an actual method on the toolkit class specified by `env_type` (`"assistant"` → tools.py, `"user"` → user_tools.py). Look up the method — does it exist? Does it accept the args specified? What DB field does it modify?

b) **actions (fix)**: Each `ActionSpec.tool_name` must be an `@is_tool`-decorated method in tools.py (or user_tools.py for user actions). Look up the tool — does it exist? Does it accept the args specified? What DB field does it ACTUALLY modify when called? Is it the SAME field that init broke?

c) **assertions**: Each `AssertionSpec.func_name` must be an `assert_*` method (no decorator) in the correct toolkit. Look up the method — does it exist? What DB field does it check? Is it the SAME field that the fix action modifies?

d) **The complete chain**: init breaks field X → fix modifies field X → assertion checks field X. If ANY of these refer to DIFFERENT fields, it's an ERROR.

e) **Unfixable layers**: If `unfixable=True`, verify `atoms=[]` and `assertions=[]` (or only preservation assertions). Verify the init_calls actually create an unfixable state.

**Archetype-specific checks:**
- **Archetype A**: Most atoms should have `env_type="assistant"` init calls (faults live on the backend). Verify that information-hiding READ tools actually gate on the fields that init breaks.
- **Archetype B**: Many atoms should have `env_type="user"` init calls (faults live on the user's device/side). Verify that fix actions have `requestor="user"`.
- **Archetype C**: Verify that WRITE tool fixes have overwrite guards (check the tool code for `if field != default: return "already done"`).
- **Archetype D**: Assertions should be lenient (check "not wrong" rather than "exactly right"). Flag any assertion that checks an exact expected value that could have multiple valid answers.

## Audit 2: Template Variable Resolution (ERROR)

Find the `_build_entities()` function in scenarios.py. List every key it returns in its entity dicts.

Then scan EVERY `{field}` template reference in scenarios.py — in `known_info_fragment`, `InitCall` args, `ActionSpec` args, `AssertionSpec` args, and `resource_scope`. For EACH template variable, verify it matches a key from `_build_entities()`. Report ERROR for any unresolvable variable.

Also verify:
- `original_<field>` copies exist for every field that init_calls will modify
- `has_<relation>` boolean flags exist for predicate filtering on optional relations

## Audit 3: Policy Alignment Per Fault Layer (ERROR)

For EACH fixable FaultLayer, read its `known_info_fragment` (the user's complaint) and its fix actions (what the agent must do). Then check policy.md:

- Does the policy describe a workflow that leads to these fix actions?
- Could the policy be interpreted to prescribe a DIFFERENT resolution? (e.g., policy says "reschedule" but fix action is "reassign")
- Does the policy forbid any of the fix actions under any conditions?

If the policy would lead a competent agent to do something different than the expected fix actions, it's an ERROR.

**Archetype-specific checks:**
- **Archetype A (reactive policy)**: The policy should describe symptoms and corresponding fixes. It should NOT prescribe calling a tool unconditionally when the corresponding fault is only sometimes active.
- **Archetype B (branching policy)**: The policy should describe a decision tree where diagnostic results determine the next step. Verify every branch in the policy's decision tree maps to exactly one fault layer's fix.
- **Archetype C (prescriptive policy)**: The policy prescribes mandatory steps. For EVERY prescriptive "always do X" instruction, verify the corresponding WRITE tool has an overwrite guard (see Audit 11).
- **Archetype D (classification policy)**: The policy describes classification criteria. Verify the criteria are unambiguous enough that the correct classification is deterministic given the task info.

## Audit 4: Tool Existence & Signature Verification (ERROR)

Collect EVERY tool/method name referenced anywhere in scenarios.py (in `InitCall.func_name`, `ActionSpec.tool_name`, `AssertionSpec.func_name`). For EACH one:

- Verify it exists as a method in tools.py or user_tools.py
- Verify it has the right decorator (or no decorator for helpers)
- Verify the args passed in scenarios.py match the method's parameters

Report ERROR for any missing method or signature mismatch.

## Audit 5: sync_tools Coverage (WARNING)

List every field in user_data_model.py. For each field that user tools read or that assertions check on user side:

- Verify environment.py's `sync_tools()` sets this field from agent DB
- If a user action modifies a user_db field that an agent tool needs as a precondition, verify `sync_tools` bridges it back to agent_db

Report WARNING for any missing projection that would cause stale data.

**Archetype B special attention:** Branching troubleshooter domains have many user-side state fields (device mode, signal strength, etc.). Verify that `sync_tools` bridges ALL user-side state that the agent needs to see indirectly (through user-reported diagnostics) AND that sync doesn't overwrite user-side state that was set by init_calls between steps.

## Audit 6: known_info Solvability (ERROR)

For each FaultLayer's `known_info_fragment`:

- Does it express clear user INTENT (not just state)?
- Does it disambiguate which resource is affected when the entity has multiple (e.g., multiple appointments, orders)?
- Would a competent agent reading this + the ticket be able to identify which DB records to act on and what action to take?
- Could the framing mislead the agent into a different (wrong) resolution?

Report ERROR if the known_info would make the task unsolvable or misleading.

## Audit 7: Cross-File Type & Data Consistency (ERROR)

- data_model.py field types vs db.json values (e.g., if model says `List[str]` but db.json has a plain string)
- user_data_model.py field types vs user_db.json values
- tools.py parameter types vs what scenarios.py passes in `ActionSpec` args
- Foreign key references in db.json: do all FK values point to existing entities?

Report ERROR for type mismatches that would cause runtime failures.

## Audit 8: User Action Feasibility (ERROR)

For each FaultLayer that has user actions (atoms with `requestor="user"`):

- Does the referenced user tool exist in user_tools.py with `@is_tool` decorator?
- Does the policy explicitly instruct the agent to tell the user to perform this action? (Look for phrases like "instruct the user to...", "ask the customer to...")
- If the user action has args, are they values the user would know from the conversation?
- Is there a precondition pattern? (user tool sets user_db field → sync_tools bridges to agent_db → agent WRITE tool checks the bridged field). Without this, the agent bypasses the user action entirely.

Report ERROR if user actions are unreachable or bypassable.

**Archetype-specific checks:**
- **Archetype B**: User tools ARE the primary fix mechanism. Verify the policy's decision tree names every user tool explicitly. Count user WRITE tools — there should be 5-15 for a branching troubleshooter.
- **Archetype A/C/D**: User tools are confirmations/acknowledgments. Verify they are zero-arg or single-arg for reliability. Flag any user tool with 2+ complex arguments — user sim pass rate drops significantly with complex args.

## Audit 9: Cross-Group Composition Safety (WARNING)

Layers in DIFFERENT FaultLayerGroups get composed via cartesian product. Check each pair of groups:

- Do any layers across different groups target the same DB record with conflicting operations? (e.g., cancel appointment + reschedule same appointment)
- Check `resource_scope` values for overlaps across groups

Report WARNING for any composition that would create contradictory tasks.

## Audit 10: Agent Success Determines Outcome (ERROR)

This is the throughline requirement: **task success must depend on the agent doing the right thing, not on the user sim's autonomous behavior.**

For EVERY FaultLayer, verify:

a) **Agent drives the interaction**: The agent must be the one who identifies the problem, determines the fix, and either performs it or instructs the user to perform it. If a task could be solved by a user sim acting on its own without agent guidance, it's an ERROR.

b) **No baked-in user instructions**: Check that `USER_TEMPLATE.task_instructions` does NOT name specific tools or prescribe specific actions. The task_instructions should say "Follow the agent's instructions" — not "Use your acknowledge_resolution tool after the agent fixes things." (The recipe engine auto-generates per-fault user instructions, which is fine — but the base template must be agent-driven.)

c) **Policy is the bridge**: For every user-side action, verify the chain: policy tells agent → agent tells user → user follows. If any user action would happen WITHOUT the agent explicitly requesting it, it's an ERROR.

d) **Assertions test agent work**: At least 50% of assertions should be on the assistant side (`env_type="assistant"`), verifying that the agent actually performed the correct fix. A domain where most assertions are user-side means the user sim (not the agent) is doing the real work.

**Archetype-specific thresholds:**
- **Archetype A**: ≥70% of assertions should be assistant-side.
- **Archetype B**: User-side assertions are expected (user performs fixes), but the agent must have guided the user to the right fix. Verify the policy decision tree is complex enough that a user couldn't solve it alone.
- **Archetype C**: ≥60% of assertions should be assistant-side.
- **Archetype D**: ≥80% of assertions should be assistant-side (classification is agent work).

## Audit 11: Prescriptive Policy Overwrite Risk (ERROR)

This audit catches the failure pattern: prescriptive policy + selective fault = agent overwrites correct data.

For EVERY `@is_tool(ToolType.WRITE)` method in tools.py:

a) **Find the policy instruction**: Does the policy say to ALWAYS call this tool (prescriptive), or only when a specific problem is detected (reactive)?

b) **Find the fault layer**: Which FaultLayer's init breaks the field this tool modifies?

c) **Check the guard**: If the policy is prescriptive ("for every call, do X") but the fault is selective (only active in some tasks), the WRITE tool MUST have a guard:
   ```python
   if field != broken_default_value:
       return "Already correct. No changes made."
   ```
   Without this guard, the agent will overwrite correct data on tasks where the fault is not active.

d) **Check the assertion**: If the tool has an overwrite guard, verify the assertion can still pass when the guard fires (i.e., the original correct value satisfies the assertion).

Report ERROR for any unguarded prescriptive-write combination.

**Archetype relevance:**
- **Archetype C** (transaction processor): Most vulnerable — prescriptive protocols are standard. EVERY WRITE tool should have a guard.
- **Archetype A** (sequential diagnostic): Reactive policies minimize risk, but check for any "always check X" instructions.
- **Archetype B** (branching troubleshooter): User-side fixes are naturally guarded (user only toggles when agent instructs). Agent-side WRITE tools still need guards.
- **Archetype D** (triage): Classification tools should guard against re-classifying already-classified items.

## Audit 12: User Tool Argument Complexity (WARNING)

User tools with complex arguments reduce the user sim's pass rate. The user sim must infer argument values from conversation context, and complex args lead to errors.

For EVERY user tool with `@is_tool` decorator in user_tools.py:

a) **Count parameters**: Zero-arg tools are best. Single-arg tools are acceptable. 2+ args should be flagged.

b) **Check arg types**: String args with free-form values (not IDs) are risky — the user sim may paraphrase or truncate. Numeric args are moderately risky. Boolean args are safe. Enum-like args (from a small set) are safe.

c) **Check if args are conversation-derivable**: Would the user actually know these values? If an arg requires information the agent hasn't shared in conversation, it's unreachable.

d) **Check compare_args alignment**: In the corresponding `ActionSpec`, `compare_args` should be empty (`[]`) for user tools. If `compare_args` lists arg names, the verification system will check exact arg match — which fails when the user sim paraphrases.

Report WARNING for any user tool with 2+ free-form string arguments or with non-empty `compare_args` on user actions.

## Audit 13: Difficulty Invariant Compliance (ERROR)

This audit checks all six Difficulty Invariants (see `docs/skills/00-archetype.md`). A domain can pass all structural audits above and still be trivially easy.

### DI-1: Diagnostic Disambiguation

Count the fault layers where the fix tool is unique to that layer (1:1 mapping). If >70% of fixable layers have a unique fix tool (no other layer uses it), it's an **ERROR**.

Check:
- How many distinct fix tools are there vs. how many fixable layers?
- Are there at least 2 layers sharing a fix tool with different computed args?
- For Archetype A: is there at least 1 information-hiding READ tool?
- For Archetype B: does the policy have a decision tree with 3+ branches?

### DI-2: Value Computation

Check whether ANY fix action requires the agent to compute or derive an argument value. If every fix tool argument is either a direct template pass-through (e.g., `"{entity_id}"`) or a hard-coded literal, it's an **ERROR**.

Check:
- For each ActionSpec, are all args template variables or literals?
- Does the policy describe at least 1 computation the agent must perform?
- Zero computed values → ERROR.

### DI-3: Ordering Dependency

Check for any ordering patterns in the domain. If all faults are completely independent (no gate chains, no fix ordering, no precondition gates), it's an **ERROR**.

Check:
- Are there information-hiding READ tools that gate downstream faults?
- Does the policy specify any fix ordering ("do X before Y")?
- Is there any user action that must precede an agent action?
- No ordering patterns at all → ERROR.

### DI-4: Multi-Property Assertions

Count fixable layers that have 2+ assertions (including composite assertions). If the percentage is below the archetype minimum (A: 60%, B: 50%, C: 50%, D: 40%), it's an **ERROR**.

Check:
- For each fixable FaultLayer, count total assertions across all atoms.
- Layers with 2+ assertions / total fixable layers = percentage.
- Below archetype minimum → ERROR.

### DI-5: User Tool Diversity

Count distinct user WRITE tool names that appear as fix actions across all fault atoms. Compare against the archetype minimum (A: 4, B: 8, C: 3, D: 3). Also check if any single tool appears in >50% of layers.

Check:
- Collect all unique `tool_name` values from ActionSpecs with `requestor="user"`.
- Count < archetype minimum → ERROR.
- Most-used single tool in >50% of layers → ERROR.

### DI-6: Action Density

Estimate the median number of actions per task. A rough formula: `median_faults × avg_atoms_per_layer`. If this is below the archetype minimum (A: 8, B: 6, C: 6, D: 5), it's an **ERROR**.

Check:
- Count fault groups. Median faults ≈ max_faults / 2 (or count groups / 2 for proportional sampling).
- Count average atoms per fixable layer.
- Median faults × avg atoms < archetype minimum → ERROR.

## What to Do with Findings

- For each ERROR: Fix the issue in the relevant file, then re-run validation for that step
- For each WARNING: Consider whether it needs fixing; warnings are informational but may indicate real problems
- After fixing, re-read the affected files to verify the fix didn't introduce new issues
- **Target: 0 ERRORs and 0 WARNINGs before proceeding to task generation**
