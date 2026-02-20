# Step 10.5: Exhaustive Domain Audit

Read ALL generated files for the domain and perform these 9 audits. For each audit, enumerate EVERY item and verify individually. Do NOT skip items or summarize — trace each one.

## Files to Read

Read all of these before starting the audits:

- `data/tau2/domains/<domain_name>/domain_spec.json`
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

## Audit 1: Per-FaultLayer Chain Verification (ERROR)

For EVERY FaultLayer defined in scenarios.py, trace the complete chain. List each layer by its variable name and verify:

a) **init_calls**: Each `InitCall.func_name` must be an actual method on the toolkit class specified by `env_type` (`"assistant"` → tools.py, `"user"` → user_tools.py). Look up the method — does it exist? Does it accept the args specified? What DB field does it modify?

b) **actions (fix)**: Each `ActionSpec.tool_name` must be an `@is_tool`-decorated method in tools.py (or user_tools.py for user actions). Look up the tool — does it exist? Does it accept the args specified? What DB field does it ACTUALLY modify when called? Is it the SAME field that init broke?

c) **assertions**: Each `AssertionSpec.func_name` must be an `assert_*` method (no decorator) in the correct toolkit. Look up the method — does it exist? What DB field does it check? Is it the SAME field that the fix action modifies?

d) **The complete chain**: init breaks field X → fix modifies field X → assertion checks field X. If ANY of these refer to DIFFERENT fields, it's an ERROR.

e) **Unfixable layers**: If `unfixable=True`, verify `atoms=[]` and `assertions=[]` (or only preservation assertions). Verify the init_calls actually create an unfixable state.

## Audit 2: Template Variable Resolution (ERROR)

Find the `_build_entities()` function in scenarios.py. List every key it returns in its entity dicts.

Then scan EVERY `{field}` template reference in scenarios.py — in `known_info_fragment`, `InitCall` args, `ActionSpec` args, `AssertionSpec` args, and `resource_scope`. For EACH template variable, verify it matches a key from `_build_entities()`. Report ERROR for any unresolvable variable.

## Audit 3: Policy Alignment Per Fault Layer (ERROR)

For EACH fixable FaultLayer, read its `known_info_fragment` (the user's complaint) and its fix actions (what the agent must do). Then check policy.md:

- Does the policy describe a workflow that leads to these fix actions?
- Could the policy be interpreted to prescribe a DIFFERENT resolution? (e.g., policy says "reschedule" but fix action is "reassign")
- Does the policy forbid any of the fix actions under any conditions?

If the policy would lead a competent agent to do something different than the expected fix actions, it's an ERROR.

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

## Audit 9: Cross-Group Composition Safety (WARNING)

Layers in DIFFERENT FaultLayerGroups get composed via cartesian product. Check each pair of groups:

- Do any layers across different groups target the same DB record with conflicting operations? (e.g., cancel appointment + reschedule same appointment)
- Check `resource_scope` values for overlaps across groups

Report WARNING for any composition that would create contradictory tasks.

## What to Do with Findings

- For each ERROR: Fix the issue in the relevant file, then re-run validation for that step
- For each WARNING: Consider whether it needs fixing; warnings are informational but may indicate real problems
- After fixing, re-read the affected files to verify the fix didn't introduce new issues
