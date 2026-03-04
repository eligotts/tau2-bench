# Step 10.5: Exhaustive Domain Audit

Read ALL generated files for the domain and perform these 12 audits. For each audit, enumerate EVERY item and verify individually. Do NOT skip items or summarize — trace each one.

> **Important:** This audit focuses on **semantic** properties that require reading source code and reasoning about meaning. Structural/mechanical checks are handled by the code verification system — see "What Code Already Verifies" below.

## What Code Already Verifies

The following properties are checked deterministically by `verify_tasks()`, `verify_authoring()`, and the recipe engine. Do NOT re-check these — they will be caught automatically:

- **Template variable resolution** — `_check_template_vars_valid()` + `_check_known_info_fragment_templates()` verify all `{field}` references resolve
- **Tool/method existence & signatures** — `verify_tool_schemas()` checks that every `InitCall.func_name`, `ActionSpec.tool_name`, and `AssertionSpec.func_name` exists with correct parameter names and required args
- **Assertion argument validation** — `verify_tool_schemas()` validates assertion arg keys match method parameters and required params are present
- **Predicate fields** — `_check_predicate_fields()` verifies predicate template variables
- **Resource scopes** — `_check_resource_scope_overlap()` detects intra-group resource collisions
- **Requestor-toolkit match** — `_check_requestor_toolkit_match()` verifies requestor aligns with toolkit type
- **Fix tools are WRITE** — `_check_fix_tools_are_write()` enforces fix actions use WRITE tools
- **DI-4/5/6 density thresholds** — `_check_assertion_density()`, `_check_user_tool_diversity()`, `_check_action_density()` enforce archetype minimums
- **Init→check fails + fix→check passes** (per atom) — `verify_fault_atoms()` executes each atom's chain
- **Pre-fix assertion failure** — `verify_golden_path()` warns if all assertions pass before any fix runs
- **completion_fragment presence + no frame phrases** — `verify_completion_fragments()` validates fixable layers have fragments and no framework phrases
- **Golden path execution** — `verify_golden_path()` runs init→fix→assert on composed tasks
- **Argument reachability** — `verify_argument_reachability()` traces arg values through tool call chains
- **User assertion arg discoverability** — `verify_user_assertion_arg_discoverability()` checks user assertion args appear in conversation
- **Action state change** — `verify_action_state_change()` verifies fix actions actually modify DB state
- **Action necessity** — `verify_action_necessity()` verifies each action is needed for assertions to pass
- **Policy text alignment** — `verify_user_action_policy_alignment()` checks user actions are mentioned in policy (when policy_text is wired)

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

---

## Group A: Semantic Chain Verification

### Audit 1: Per-FaultLayer Semantic Field Tracing (ERROR)

Code catches *execution* failures (method missing, assertion fails). This audit catches *semantic* misalignment — when init/fix/assertion all execute successfully but target different conceptual fields.

For EVERY FaultLayer defined in scenarios.py, **read the method bodies** in tools.py/user_tools.py and trace the complete chain:

a) **init_calls**: Read each `InitCall.func_name` method body. What DB field does it ACTUALLY modify? (Not what the name suggests — read the code.)

b) **actions (fix)**: Read each `ActionSpec.tool_name` method body. What DB field does it ACTUALLY modify? Is it the SAME field that init broke?

c) **assertions**: Read each `AssertionSpec.func_name` method body. What DB field does it ACTUALLY check? Is it the SAME field that the fix action modifies?

d) **The complete chain**: init breaks field X → fix modifies field X → assertion checks field X. If ANY of these refer to DIFFERENT fields, it's an ERROR. Code only checks that each step *runs* — you must verify they target the *same* conceptual state.

e) **Unfixable layers**: If `unfixable=True`, verify `atoms=[]` and `assertions=[]` (or only preservation assertions). Verify the init_calls actually create an unfixable state.

**Archetype-specific checks:**
- **Archetype A**: Most atoms should have `env_type="assistant"` init calls (faults live on the backend). Verify that information-hiding READ tools actually gate on the fields that init breaks.
- **Archetype B**: Many atoms should have `env_type="user"` init calls (faults live on the user's device/side). Verify that fix actions have `requestor="user"`.
- **Archetype C**: Verify that WRITE tool fixes have overwrite guards (check the tool code for `if field != default: return "already done"`).
- **Archetype D**: Assertions should be lenient (check "not wrong" rather than "exactly right"). Flag any assertion that checks an exact expected value that could have multiple valid answers.

### Audit 2: Pre-Fix Broken State at Composed Level (ERROR)

Code checks per-atom chains individually. This audit checks the **composed** multi-fault task: after ALL init actions but before ANY fixes, would at least one assertion fail?

Mentally simulate the composed state:
- Apply all init_calls from all active FaultLayers (in the order they'd execute)
- Account for `sync_tools()` running between each init step
- Now check: would at least one assertion fail in this composed state?

If ALL assertions trivially pass before any fix runs, the task tests nothing — it's an ERROR.

**Note:** Some preservation assertions (checking that unfaulted state remains correct) are expected to pass pre-fix. The concern is when ALL assertions pass, meaning no fault is actually detectable.

### Audit 3: Policy Alignment Per Fault Layer (ERROR)

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

### Audit 4: Completion Fragment Faithfulness (ERROR)

Code verifies that completion_fragments exist and have no frame phrases. This audit verifies the **semantic alignment** between fragments, assertions, and user tools.

For EVERY fixable FaultLayer, trace the four-way chain:

a) **completion_fragment → user tool**: What user tool would let the user observe the state described by the completion_fragment? Does that tool exist?

b) **user tool → DB field**: Read the user tool's method body. What DB field does it read to produce its output?

c) **DB field → assertion**: Read the assertion method body. Does it check the SAME DB field that the user tool reads?

d) **assertion → completion_fragment**: Does the assertion's pass condition correspond to the state described by the completion_fragment?

If any link in this chain is broken (different DB fields, different conceptual state), it's an ERROR.

Also verify **complement consistency**: `completion_fragment` must describe the observable inverse of `known_info_fragment`. They must reference the SAME fault:
- known_info says "My internet is slow" → completion says "your speed test shows excellent results" — correct
- known_info says "My internet is slow" → completion says "your bill shows correct amount" — ERROR: different fault

**Archetype-specific expectations:**
- **Archetype A**: Completion references user READ tool output (e.g., `view_my_account()`)
- **Archetype B**: Completion references user diagnostic tool output (e.g., `run_speed_test()`, `get_status_bar()`)
- **Archetype C**: Completion references transaction state, often with template variables (e.g., `"your order total shows {original_amount}"`)
- **Archetype D**: Completion uses lenient language matching lenient assertions (e.g., `"your ticket has been reassigned"` not `"your ticket is assigned to team X"`)

---

## Group B: State & Data Integrity

### Audit 5: sync_tools Coverage (WARNING)

List every field in user_data_model.py. For each field that user tools read or that assertions check on user side:

- Verify environment.py's `sync_tools()` sets this field from agent DB
- If a user action modifies a user_db field that an agent tool needs as a precondition, verify `sync_tools` bridges it back to agent_db

Report WARNING for any missing projection that would cause stale data.

**Archetype B special attention:** Branching troubleshooter domains have many user-side state fields (device mode, signal strength, etc.). Verify that `sync_tools` bridges ALL user-side state that the agent needs to see indirectly (through user-reported diagnostics) AND that sync doesn't overwrite user-side state that was set by init_calls between steps.

### Audit 6: Cross-File FK Integrity (ERROR)

Check foreign key references in the data files:

- db.json: Do all FK values point to existing entities? (e.g., if a record references `patron_id: "PAT005"`, does PAT005 exist?)
- user_db.json: Do all FK values point to existing entities in db.json or user_db.json?
- scenarios.py entity builders: Do template FK values (e.g., `"{patron_id}"`) resolve to valid entity IDs from `_build_entities()`?

Report ERROR for any dangling FK reference that would cause a runtime lookup failure.

---

## Group C: Agent/User Interaction Quality

### Audit 7: known_info Solvability (ERROR)

For each FaultLayer's `known_info_fragment`:

- Does it express clear user INTENT (not just state)?
- Does it disambiguate which resource is affected when the entity has multiple (e.g., multiple appointments, orders)?
- Would a competent agent reading this + the ticket be able to identify which DB records to act on and what action to take?
- Could the framing mislead the agent into a different (wrong) resolution?

Report ERROR if the known_info would make the task unsolvable or misleading.

### Audit 8: User Action Feasibility — Semantic Focus (ERROR)

Code verifies tool existence, signatures, and argument discoverability. This audit focuses on the **semantic** side:

a) **Policy directs agent to instruct user**: Does the policy explicitly tell the agent to ask the user to perform this action? Look for phrases like "instruct the user to...", "ask the customer to...". If no policy guidance exists, the agent won't know to involve the user — ERROR.

b) **User tool args are realistic**: Would a real user know these values from the conversation? (Code checks arg discoverability, but can't judge whether the values make sense in context.)

c) **Precondition patterns**: If the user tool has a precondition gate (user tool sets user_db field → sync_tools bridges to agent_db → agent WRITE tool checks), verify the gate is semantically coherent. Is the bridged field the right one?

d) **User action isn't bypassable**: Could the agent skip the user action and achieve the same result with a direct WRITE tool? If so, the user action is decorative — ERROR.

**Archetype-specific checks:**
- **Archetype B**: User tools ARE the primary fix mechanism. Verify the policy's decision tree names every user tool explicitly. Is the decision tree complex enough that a user couldn't solve it alone?
- **Archetype A/C/D**: User tools are confirmations/acknowledgments. Verify they are zero-arg or single-arg for reliability.

### Audit 9: Cross-Group Composition Safety (WARNING)

Layers in DIFFERENT FaultLayerGroups get composed via cartesian product. Check each pair of groups:

- Do any layers across different groups target the same DB record with conflicting operations? (e.g., cancel appointment + reschedule same appointment)
- Check `resource_scope` values for overlaps across groups — code catches resource_scope collisions within groups, but semantic conflicts across groups (same entity, different operations) require reading the tool code

Report WARNING for any composition that would create contradictory tasks.

### Audit 10: Agent Drives Outcome (ERROR)

**Task success must depend on the agent doing the right thing, not on the user sim's autonomous behavior.**

For EVERY FaultLayer, verify:

a) **Agent drives the interaction**: The agent must be the one who identifies the problem, determines the fix, and either performs it or instructs the user to perform it. If a task could be solved by a user sim acting on its own without agent guidance, it's an ERROR.

b) **No baked-in user instructions**: Check that `USER_TEMPLATE.task_instructions` does NOT name specific tools or prescribe specific actions. The task_instructions should say "Follow the agent's instructions" — the recipe engine auto-generates per-fault user instructions via completion_fragments, which is fine. But the base template must be agent-driven.

c) **Policy is the bridge**: For every user-side action, verify the chain: policy tells agent → agent tells user → user follows. If any user action would happen WITHOUT the agent explicitly requesting it, it's an ERROR.

d) **Assertions test agent work**: At least 50% of assertions should be on the assistant side (`env_type="assistant"`), verifying that the agent actually performed the correct fix. A domain where most assertions are user-side means the user sim (not the agent) is doing the real work.

**Archetype-specific thresholds:**
- **Archetype A**: ≥70% of assertions should be assistant-side.
- **Archetype B**: User-side assertions are expected (user performs fixes), but the agent must have guided the user to the right fix. Verify the policy decision tree is complex enough that a user couldn't solve it alone.
- **Archetype C**: ≥60% of assertions should be assistant-side.
- **Archetype D**: ≥80% of assertions should be assistant-side (classification is agent work).

### Audit 11: Prescriptive Overwrite Risk (ERROR)

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

---

## Group D: Difficulty Invariants (LLM-only subset)

### Audit 12: DI-1, DI-2, DI-3 Compliance (ERROR)

Code checks DI-4 (assertion density), DI-5 (user tool diversity), and DI-6 (action density). The remaining three invariants require reading tool source code to evaluate — they cannot be checked mechanically.

#### DI-1: Diagnostic Disambiguation

Count the fault layers where the fix tool is unique to that layer (1:1 mapping). If >70% of fixable layers have a unique fix tool (no other layer uses it), it's an ERROR — agents can shortcut by mapping symptom→tool without diagnosis.

Check:
- How many distinct fix tools are there vs. how many fixable layers?
- Are there at least 2 layers sharing a fix tool with different computed args?
- For Archetype A: is there at least 1 information-hiding READ tool?
- For Archetype B: does the policy have a decision tree with 3+ branches?

#### DI-2: Value Computation

Check whether ANY fix action requires the agent to compute or derive an argument value. If every fix tool argument is either a direct template pass-through (e.g., `"{entity_id}"`) or a hard-coded literal, it's an ERROR — agents need no reasoning to construct the call.

Check:
- For each ActionSpec, are all args template variables or literals?
- Does the policy describe at least 1 computation the agent must perform?
- Zero computed values → ERROR.

#### DI-3: Ordering Dependency

Check for any ordering patterns in the domain. If all faults are completely independent (no gate chains, no fix ordering, no precondition gates), it's an ERROR — agents can fix faults in any order without planning.

Check:
- Are there information-hiding READ tools that gate downstream faults?
- Does the policy specify any fix ordering ("do X before Y")?
- Is there any user action that must precede an agent action?
- No ordering patterns at all → ERROR.

---

## What to Do with Findings

- For each ERROR: Fix the issue in the relevant file, then re-run validation for that step
- For each WARNING: Consider whether it needs fixing; warnings are informational but may indicate real problems
- After fixing, re-read the affected files to verify the fix didn't introduce new issues
- **Target: 0 ERRORs and 0 WARNINGs before proceeding to task generation**
