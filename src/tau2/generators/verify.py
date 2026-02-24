import re
import textwrap
from typing import Any, Callable, Optional

from tau2.data_model.tasks import EnvAssertion, RewardType, Task
from tau2.environment.environment import Environment
from tau2.environment.toolkit import ToolType


def verify_task(
    task: Task,
    get_env: Callable[[], Environment],
    is_fixed: Callable[[Environment], bool],
) -> None:
    """
    Validate a task is internally consistent:
    - Fresh env starts fixed
    - Init actions break it
    - Fix actions repair it (or confirm unfixable)
    - Assertions pass
    Mirrors telecom's TaskManager.verify_task.
    """
    print(f"Verifying task: {task.id}")

    env = get_env()
    assert is_fixed(env), "Environment starts in broken state"

    env.set_state(
        initialization_data=task.initial_state.initialization_data,
        initialization_actions=task.initial_state.initialization_actions,
        message_history=[],
    )

    fix_actions = task.evaluation_criteria.actions or []
    fixable = _is_fixable(task)

    for i, action in enumerate(fix_actions):
        assert not is_fixed(env), (
            f"Task {task.id} is already fixed after {i} actions. {task}"
        )
        env.make_tool_call(
            tool_name=action.name, requestor=action.requestor, **action.arguments
        )
        env.sync_tools()

    if fixable:
        assert is_fixed(env), (
            f"Task {task.id} is not fixed after all actions. {task}"
        )
    else:
        assert not is_fixed(env), (
            f"Task {task.id} is fixed but should not be. {task}"
        )

    assert _run_assertions(env, task, verbose=True)


def _is_fixable(task: Task) -> bool:
    transfer_action_name = "transfer_to_human"
    actions = task.evaluation_criteria.actions or []
    if len(actions) == 0:
        return False
    action_names = {a.name for a in actions}
    if transfer_action_name in action_names:
        return False
    return True


def _run_assertions(
    env: Environment, task: Task, verbose: bool = False
) -> bool:
    assertions = task.evaluation_criteria.env_assertions or []
    if len(assertions) == 0:
        return True
    success = True
    for i, assertion in enumerate(assertions):
        if verbose:
            print(f"Verifying env assertion {i + 1} of {len(assertions)}")
            print(textwrap.indent(str(assertion), "  "))
        assertion_success = env.run_env_assertion(
            assertion,
            raise_assertion_error=False,
        )
        if verbose:
            print("Success: ", assertion_success)
        success = success and assertion_success
    return success


# ---------------------------------------------------------------------------
# Generation-time verification checks
# ---------------------------------------------------------------------------


def verify_reward_basis(task: Task) -> list[str]:
    """
    Static check — no environment needed.

    - Warn if NL_ASSERTION is in reward_basis (needs ALL_WITH_NL_ASSERTIONS evaluator)
    - Error if a reward_basis value is not a valid RewardType
    - Warn if compare_args references arg names not present in the action's arguments
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria

    # Check each reward_basis value
    for rb in ec.reward_basis:
        if rb == RewardType.NL_ASSERTION:
            issues.append(
                "WARNING: reward_basis contains NL_ASSERTION — requires "
                "EvaluationType.ALL_WITH_NL_ASSERTIONS, not the default evaluator"
            )
        # Pydantic already validates enum membership on construction, but guard
        # against raw strings that slipped past validation.
        if isinstance(rb, str) and not isinstance(rb, RewardType):
            try:
                RewardType(rb)
            except ValueError:
                issues.append(f"ERROR: reward_basis contains invalid value: {rb}")

    # Check compare_args reference valid argument names
    for action in ec.actions or []:
        if action.compare_args is not None:
            for ca in action.compare_args:
                if ca not in action.arguments:
                    issues.append(
                        f"WARNING: action '{action.name}' compare_args contains "
                        f"'{ca}' which is not in action arguments "
                        f"{sorted(action.arguments.keys())}"
                    )

    return issues


def verify_tool_schemas(task: Task, env: Environment) -> list[str]:
    """
    Static check — needs environment for tool definitions, but doesn't execute tools.

    - Check action tool names exist in the appropriate toolkit
    - Check action argument keys are valid parameter names
    - Check required parameters are present
    - Check compare_args entries are valid parameter names
    - Check env_assertion func_names exist on the appropriate toolkit
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria

    # Build tool registries
    assistant_tools = env.tools.get_tools() if env.tools else {}
    user_tools = env.user_tools.get_tools() if env.user_tools else {}

    # Check actions
    for action in ec.actions or []:
        if action.requestor == "assistant":
            tools = assistant_tools
        else:
            tools = user_tools

        # Check tool name exists
        if action.name not in tools:
            issues.append(
                f"ERROR: action '{action.name}' "
                f"(requestor={action.requestor}) not found in toolkit"
            )
            continue

        tool = tools[action.name]
        schema = tool.params.model_json_schema()
        valid_params = set(schema.get("properties", {}).keys())
        required_params = set(schema.get("required", []))

        # Check argument keys
        for arg_name in action.arguments:
            if arg_name not in valid_params:
                issues.append(
                    f"ERROR: action '{action.name}' has invalid argument "
                    f"'{arg_name}' (valid: {sorted(valid_params)})"
                )

        # Check required params present
        for rp in required_params:
            if rp not in action.arguments:
                issues.append(
                    f"ERROR: action '{action.name}' missing required argument "
                    f"'{rp}'"
                )

        # Check compare_args entries are valid param names
        if action.compare_args is not None:
            for ca in action.compare_args:
                if ca not in valid_params:
                    issues.append(
                        f"ERROR: action '{action.name}' compare_args entry "
                        f"'{ca}' is not a valid parameter "
                        f"(valid: {sorted(valid_params)})"
                    )

    # Check env_assertions
    for assertion in ec.env_assertions or []:
        if assertion.env_type == "assistant":
            toolkit = env.tools
        else:
            toolkit = env.user_tools

        if toolkit is None:
            issues.append(
                f"ERROR: env_assertion '{assertion.func_name}' — "
                f"toolkit is None for env_type={assertion.env_type}"
            )
            continue

        if not hasattr(toolkit, assertion.func_name):
            issues.append(
                f"ERROR: env_assertion func_name '{assertion.func_name}' "
                f"not found on {assertion.env_type} toolkit"
            )

    # Check for Any-typed tool parameters (anti-pattern for LLM-facing tools).
    # Tools with ``value: Any`` invite type mismatches from LLM callers.
    # Flag once per tool, not per task; use a set to avoid noise.
    for action in ec.actions or []:
        tools = assistant_tools if action.requestor == "assistant" else user_tools
        if action.name not in tools:
            continue
        tool = tools[action.name]
        for pname, pfield in tool.params.model_fields.items():
            if pfield.annotation is Any:
                issues.append(
                    f"WARNING: tool '{action.name}' parameter '{pname}' is "
                    f"typed as Any — use ToolKitBase._coerce_and_set_field() "
                    f"in the tool body to prevent LLM type mismatches"
                )

    return issues


def _extract_values(text: str) -> set[str]:
    """Extract tokens that look like IDs or meaningful values from text."""
    tokens: set[str] = set()
    # Split on whitespace and common punctuation
    for token in re.split(r'[\s,;:()\[\]{}"\']+', text):
        token = token.strip().strip(".")
        if token and len(token) >= 2:
            tokens.add(token)
    return tokens


def _collect_leaf_values(obj: object, values: set[str]) -> None:
    """Recursively collect string and numeric leaf values from a Python object."""
    if isinstance(obj, str):
        values.add(obj)
        # Also extract sub-tokens from the string
        for token in re.split(r'[\s,;:()\[\]{}"\']+', obj):
            token = token.strip().strip(".")
            if token and len(token) >= 2:
                values.add(token)
    elif isinstance(obj, bool):
        # Must check bool before int since bool is a subclass of int
        pass
    elif isinstance(obj, (int, float)):
        values.add(str(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            # Collect keys too — agents see field names from READ tool responses
            if isinstance(k, str):
                values.add(k)
            _collect_leaf_values(v, values)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _collect_leaf_values(item, values)
    elif hasattr(obj, "model_dump"):
        # Pydantic BaseModel — convert to dict and recurse
        _collect_leaf_values(obj.model_dump(), values)
    elif hasattr(obj, "__dict__") and not isinstance(obj, type):
        # Generic object with attributes
        _collect_leaf_values(vars(obj), values)


def verify_argument_reachability(
    task: Task,
    get_env: Callable[[], Environment],
    context_texts: list[str],
) -> list[str]:
    """
    Runtime check — sets up environment, calls READ tools to check discoverability.

    For each assistant-side action, checks whether argument values are present in
    the context texts (ticket + known_info) or discoverable via READ tools.
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    actions = ec.actions or []

    # Set up environment with init actions
    env = get_env()
    env.set_state(
        initialization_data=(
            task.initial_state.initialization_data if task.initial_state else None
        ),
        initialization_actions=(
            task.initial_state.initialization_actions if task.initial_state else None
        ),
        message_history=[],
    )

    # Extract known values from context
    known_values: set[str] = set()
    for text in context_texts:
        if text:
            known_values.update(_extract_values(text))

    for action in actions:
        # Skip user-side actions
        if action.requestor == "user":
            continue

        # Determine which args matter for evaluation
        compared = action.compare_args  # None=all, []=name-only, ["a","b"]=specific
        if compared is not None and len(compared) == 0:
            # Name-only match — no arg values are checked during evaluation
            continue

        # Check which argument values are missing from known_values
        missing_args: dict[str, str] = {}
        for arg_name, arg_value in action.arguments.items():
            if isinstance(arg_value, bool) or arg_value is None:
                continue
            # Skip args that won't be checked during evaluation
            if compared is not None and arg_name not in compared:
                continue
            val_str = str(arg_value)
            # Build set of equivalent string representations for this value
            val_variants = {val_str}
            # Numeric normalization: "50.0" also matches "50", "50.00", etc.
            try:
                num = float(val_str)
                val_variants.add(str(int(num)) if num == int(num) else val_str)
                val_variants.add(f"{num:.0f}")
                val_variants.add(f"{num:.1f}")
                val_variants.add(f"{num:.2f}")
            except (ValueError, OverflowError):
                pass
            # Check both exact token match and substring match in original texts
            found = any(v in known_values for v in val_variants) or any(
                any(v in text for v in val_variants)
                for text in context_texts
                if text
            )
            if not found:
                missing_args[arg_name] = val_str

        # If some args missing, try READ tools to discover them
        if missing_args:
            if env.tools is not None:
                assistant_tools = env.tools.get_tools()
                for tool_name in assistant_tools:
                    try:
                        tool_type = env.tools.tool_type(tool_name)
                    except (KeyError, AttributeError):
                        continue
                    if tool_type != ToolType.READ:
                        continue

                    tool = assistant_tools[tool_name]
                    schema = tool.params.model_json_schema()
                    params = list(schema.get("properties", {}).keys())

                    for param_name in params:
                        for kv in list(known_values):
                            try:
                                result = env.make_tool_call(
                                    tool_name,
                                    requestor="assistant",
                                    **{param_name: kv},
                                )
                                _collect_leaf_values(result, known_values)
                            except Exception:
                                pass

            # Re-check missing args (token match or substring in context)
            def _is_discoverable(val: str) -> bool:
                variants = {val}
                try:
                    num = float(val)
                    variants.add(str(int(num)) if num == int(num) else val)
                    variants.add(f"{num:.0f}")
                    variants.add(f"{num:.1f}")
                    variants.add(f"{num:.2f}")
                except (ValueError, OverflowError):
                    pass
                if any(v in known_values for v in variants):
                    return True
                return any(
                    any(v in text for v in variants)
                    for text in context_texts
                    if text
                )

            still_missing = {
                k: v
                for k, v in missing_args.items()
                if not _is_discoverable(v)
            }

            if still_missing:
                issues.append(
                    f"ERROR: action '{action.name}' has argument values "
                    f"not discoverable from context or READ tools: {still_missing}"
                )

        # Execute this action and add return values to known_values
        try:
            result = env.make_tool_call(
                action.name, requestor=action.requestor, **action.arguments
            )
            _collect_leaf_values(result, known_values)
            env.sync_tools()
        except Exception:
            pass

    return issues


def verify_user_action_feasibility(
    task: Task,
    context_texts: list[str],
) -> list[str]:
    """
    Static check — no environment needed.

    For each user-side action, checks that:
    1. Task has user_task_instructions when user actions exist
    2. User actions with non-trivial args (compare_args != []) have values
       discoverable from known_info or task_instructions
    3. Warns about user actions where all args must match exactly
       (compare_args=None) since the user simulator must guess every value
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    actions = ec.actions or []
    user_actions = [a for a in actions if a.requestor == "user"]

    if not user_actions:
        return issues

    # Check 1: user_task_instructions should exist when user actions are present
    has_task_instructions = (
        task.user_scenario
        and task.user_scenario.instructions
        and task.user_scenario.instructions.task_instructions
        and task.user_scenario.instructions.task_instructions.strip()
    )
    if not has_task_instructions:
        issues.append(
            "WARNING: task has user-side actions but no user_task_instructions. "
            "The user simulator won't know to call these tools without instructions."
        )

    # Build known values from context (known_info, task_instructions, ticket)
    known_values: set[str] = set()
    for text in context_texts:
        if text:
            known_values.update(_extract_values(text))

    # Check 2: warn about conditional/reactive user actions
    # If task_instructions say "if the agent asks you to X" rather than
    # "go ahead and X", the user simulator may not reliably execute the action
    # because it depends on the agent prompting during conversation.
    if has_task_instructions:
        task_inst_lower = (
            task.user_scenario.instructions.task_instructions.lower()
        )
        conditional_phrases = [
            "if the agent asks",
            "when the agent asks",
            "if the agent tells",
            "when the agent tells",
            "if the agent instructs",
            "when the agent instructs",
            "if the agent directs",
            "when the agent directs",
            "if asked to",
            "when asked to",
            "if instructed to",
            "when instructed to",
        ]
        for action in user_actions:
            tool_words = set(action.name.split("_"))
            significant = {w for w in tool_words if len(w) > 3}
            if not significant:
                continue
            for sentence in re.split(r'[.!?\n]', task_inst_lower):
                has_keyword = any(w in sentence for w in significant)
                has_conditional = any(p in sentence for p in conditional_phrases)
                if has_keyword and has_conditional:
                    issues.append(
                        f"WARNING: user action '{action.name}' is conditional on "
                        f"agent behavior in task_instructions. LLM user simulators "
                        f"may not reliably execute conditional actions — the agent "
                        f"must explicitly prompt the user, and the simulator must "
                        f"comply. Consider making the user proactively take this "
                        f"action, or remove the user action requirement."
                    )
                    break

    for action in user_actions:
        compared = action.compare_args

        # Check 3: name-only match (compare_args=[]) is always safe — skip
        if compared is not None and len(compared) == 0:
            continue

        # Check 4: compare_args=None means ALL args must match exactly
        if compared is None and action.arguments:
            non_trivial_args = {
                k: v for k, v in action.arguments.items()
                if not isinstance(v, bool) and v is not None
            }
            if non_trivial_args:
                issues.append(
                    f"WARNING: user action '{action.name}' has compare_args=None "
                    f"(all {len(non_trivial_args)} args must match exactly). "
                    f"User simulator must guess every value correctly. "
                    f"Consider using compare_args=[] for name-only matching."
                )

        # Check 5: verify arg values are discoverable from context
        args_to_check = action.arguments
        if compared is not None:
            args_to_check = {k: v for k, v in args_to_check.items() if k in compared}

        for arg_name, arg_value in args_to_check.items():
            if isinstance(arg_value, bool) or arg_value is None:
                continue
            val_str = str(arg_value)
            found = val_str in known_values or any(
                val_str in text for text in context_texts if text
            )
            if not found:
                issues.append(
                    f"WARNING: user action '{action.name}' arg '{arg_name}={val_str}' "
                    f"not found in known_info or task_instructions. "
                    f"The user simulator may not be able to provide this value. "
                    f"Consider using compare_args=[] for name-only matching."
                )

    return issues


def verify_user_action_policy_alignment(
    task: Task,
    policy_text: str,
) -> list[str]:
    """
    Static check — verifies the policy explicitly instructs the agent to tell
    the user to perform each user-side action. Looks for instruction patterns
    (instruct/tell/ask/direct the patient) + tool keywords in the same sentence.

    Catches verbal-confirmation-misinterpreted-as-tool-call bugs.
    E.g., "confirm details with the patient" is an agent verbal action, not
    "instruct the patient to call confirm_appointment."
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    actions = ec.actions or []
    user_actions = [a for a in actions if a.requestor == "user"]

    if not user_actions:
        return issues

    policy_lower = policy_text.lower()

    # Instruction verbs indicating the agent should tell the user to act
    instruction_patterns = [
        "instruct the", "tell the", "ask the", "direct the",
        "have the", "advise the", "guide the",
        "instruct patient", "tell patient", "ask patient",
        "instruct the patient", "tell the patient", "ask the patient",
    ]

    # Split policy into sentences
    sentences = re.split(r'[.!?\n]', policy_lower)

    for action in user_actions:
        # Build keyword set from tool name
        tool_words = set(action.name.split("_"))
        tool_words.discard("")
        # Filter short/common words
        significant_words = {w for w in tool_words if len(w) > 3}

        if not significant_words:
            continue

        # Check if any sentence has an instruction pattern + tool keyword
        found_instruction = False
        for sentence in sentences:
            has_instruction = any(p in sentence for p in instruction_patterns)
            has_tool_keyword = any(w in sentence for w in significant_words)
            if has_instruction and has_tool_keyword:
                found_instruction = True
                break

        if not found_instruction:
            readable = action.name.replace("_", " ")
            issues.append(
                f"WARNING: user action '{action.name}' — policy does not contain "
                f"an instruction to tell the user to '{readable}'. "
                f"The agent may not direct the user to perform this action. "
                f"Verify the policy explicitly says to instruct the user."
            )

    return issues


def verify_user_action_redundancy(
    task: Task,
    get_env: Callable[[], Environment],
) -> list[str]:
    """
    Runtime check — executes only agent-side actions + sync, then checks
    whether ALL assertions pass WITHOUT user actions being executed.

    If they do, ENV_ASSERTION will always be 1.0 regardless of whether the
    user simulator calls the tools — task pass/fail depends entirely on the
    ACTION evaluator. This causes the ACTION:0.0 + ENV_ASSERTION:1.0 pattern
    seen when user simulators are unreliable.
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    actions = ec.actions or []
    assertions = ec.env_assertions or []

    user_actions = [a for a in actions if a.requestor == "user"]
    agent_actions = [a for a in actions if a.requestor != "user"]

    # Only check tasks that have BOTH user actions and assertions
    if not user_actions or not assertions:
        return issues

    # Skip unfixable tasks
    if any(a.name == "transfer_to_human" for a in actions):
        return issues

    # Set up environment with init actions
    env = get_env()
    if task.initial_state:
        env.set_state(
            initialization_data=task.initial_state.initialization_data,
            initialization_actions=task.initial_state.initialization_actions,
            message_history=[],
        )

    # Execute only agent-side actions + sync
    for action in agent_actions:
        try:
            env.make_tool_call(
                action.name, requestor=action.requestor, **action.arguments
            )
            env.sync_tools()
        except Exception:
            return issues  # Can't complete agent actions, skip check

    # Check if ALL assertions pass without user actions
    all_pass = True
    for assertion in assertions:
        try:
            result = env.run_env_assertion(
                assertion, raise_assertion_error=False
            )
            if not result:
                all_pass = False
                break
        except Exception:
            all_pass = False
            break

    if all_pass:
        user_action_names = [a.name for a in user_actions]
        issues.append(
            f"WARNING: all ENV_ASSERTIONs pass after agent actions + sync_tools "
            f"without executing user actions {user_action_names}. "
            f"ENV_ASSERTION will always be 1.0 regardless of user simulator "
            f"behavior — task pass/fail depends entirely on ACTION evaluator. "
            f"Consider adding user-side assertions (env_type='user') that fail "
            f"without the user action, or accept this as intentional behavioral testing."
        )

    return issues


def verify_golden_path(
    task: Task,
    get_env: Callable[[], Environment],
) -> list[str]:
    """
    Runtime semantic check — executes init actions, then fix actions, then checks
    assertions actually pass. Catches tool/assertion mismatches where the fix tool
    doesn't modify the DB field the assertion checks.

    Skips unfixable tasks (transfer_to_human) since they have no fix actions or assertions.
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    actions = ec.actions or []
    assertions = ec.env_assertions or []

    # Skip unfixable tasks — they only have transfer_to_human
    if any(a.name == "transfer_to_human" for a in actions):
        return issues

    # Skip tasks with no assertions to check
    if not assertions:
        return issues

    # Set up environment with init actions (inject faults)
    env = get_env()
    if task.initial_state:
        env.set_state(
            initialization_data=task.initial_state.initialization_data,
            initialization_actions=task.initial_state.initialization_actions,
            message_history=[],
        )

    # Execute all fix actions (both agent and user)
    for action in actions:
        try:
            env.make_tool_call(
                action.name, requestor=action.requestor, **action.arguments
            )
            env.sync_tools()
        except Exception as e:
            issues.append(
                f"ERROR: golden path action '{action.name}' "
                f"(requestor={action.requestor}) raised: {e}"
            )
            return issues

    # Check all assertions pass
    for assertion in assertions:
        try:
            result = env.run_env_assertion(
                assertion, raise_assertion_error=False
            )
            if not result:
                issues.append(
                    f"ERROR: golden path assertion FAILED after executing all "
                    f"fix actions: {assertion.func_name}({assertion.arguments}) "
                    f"— the fix actions don't actually fix this fault"
                )
        except Exception as e:
            issues.append(
                f"ERROR: golden path assertion '{assertion.func_name}' raised: {e}"
            )

    return issues


def _snapshot_db(env: Environment) -> tuple:
    """Snapshot all DB state from an environment for comparison."""
    agent_db = None
    user_db = None
    # DB is stored on the toolkit objects
    if hasattr(env, 'tools') and hasattr(env.tools, 'db') and env.tools.db:
        agent_db = env.tools.db.model_dump()
    if hasattr(env, 'user_tools') and hasattr(env.user_tools, 'db') and env.user_tools.db:
        user_db = env.user_tools.db.model_dump()
    return (agent_db, user_db)


def verify_action_state_change(
    task: Task,
    get_env: Callable[[], Environment],
) -> list[str]:
    """
    Runtime check — for each action, check that it actually changes environment state.
    Detects no-op actions that don't modify the DB. Would have caught the reconnect_wifi bug.
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    actions = ec.actions or []

    if not actions:
        return issues

    # Set up environment with init actions
    env = get_env()
    if task.initial_state:
        env.set_state(
            initialization_data=task.initial_state.initialization_data,
            initialization_actions=task.initial_state.initialization_actions,
            message_history=[],
        )

    for action in actions:
        if action.name == "transfer_to_human":
            continue

        # Snapshot before
        before = _snapshot_db(env)

        try:
            env.make_tool_call(
                action.name, requestor=action.requestor, **action.arguments
            )
            env.sync_tools()
        except Exception:
            continue  # Skip actions that error

        # Snapshot after
        after = _snapshot_db(env)

        if before == after:
            issues.append(
                f"ERROR: action '{action.name}' (requestor={action.requestor}) "
                f"is a no-op — no DB state changed after execution"
            )

    return issues


def _generate_format_variants(value: object) -> list[tuple[str, object]]:
    """Generate common LLM format variations for a value.

    LLMs often send values in slightly different formats than expected:
    - ``["penicillin"]`` → ``"penicillin"`` (unwrap single-element list)
    - ``["penicillin"]`` → ``[{"value": "penicillin"}]`` (dict-wrap elements)
    - ``["penicillin"]`` → ``{"allergen": "penicillin"}`` (single dict)
    - ``"hello"`` → ``["hello"]`` (list-wrap scalar)
    - ``42`` → ``"42"`` (stringify number)
    - ``"checked_out"`` → ``"checked out"`` (underscore-to-space)
    - ``"checked out"`` → ``"checked_out"`` (space-to-underscore)
    - ``"checked_out"`` → ``"Checked Out"`` (title case)
    """
    variants: list[tuple[str, object]] = []

    if isinstance(value, list) and len(value) > 0:
        # Variant: single element as scalar (unwrap)
        if len(value) == 1:
            variants.append(("scalar-unwrap", value[0]))
        # Variant: elements as dicts with descriptive keys
        if all(isinstance(v, str) for v in value):
            variants.append(("dict-wrapped", [{"value": v} for v in value]))
            if len(value) == 1:
                variants.append(("single-dict", {"value": value[0]}))
    elif isinstance(value, str):
        variants.append(("list-wrapped", [value]))
        # String normalization variants — LLMs paraphrase enum values
        if "_" in value:
            spaced = value.replace("_", " ")
            variants.append(("underscore-to-space", spaced))
            variants.append(("title-case", spaced.title()))
        elif " " in value:
            underscored = value.replace(" ", "_")
            variants.append(("space-to-underscore", underscored))
        if value != value.lower():
            variants.append(("lowered", value.lower()))
        if value != value.upper() and len(value) <= 20:
            variants.append(("uppered", value.upper()))
    elif isinstance(value, (int, float)):
        variants.append(("string-number", str(value)))

    return variants


def verify_assertion_robustness(
    task: Task,
    get_env: Callable[[], Environment],
) -> list[str]:
    """Runtime check — for actions with ``Any``-typed parameters, test common LLM
    format variations and check assertions still pass.

    Catches brittle assertions that fail when an LLM formats a value
    differently (e.g., sending ``{"value": "penicillin"}`` instead of
    ``"penicillin"`` for a ``List[str]`` field).
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    actions = ec.actions or []
    assertions = ec.env_assertions or []

    if not assertions:
        return issues
    if any(a.name == "transfer_to_human" for a in actions):
        return issues

    # Identify actions with Any-typed parameters
    env_probe = get_env()
    assistant_tools = env_probe.tools.get_tools() if env_probe.tools else {}
    user_tools = env_probe.user_tools.get_tools() if env_probe.user_tools else {}

    any_typed_actions: list[tuple[int, str]] = []  # (action_idx, param_name)
    for idx, action in enumerate(actions):
        tools = assistant_tools if action.requestor == "assistant" else user_tools
        if action.name not in tools:
            continue
        tool = tools[action.name]
        for pname, pfield in tool.params.model_fields.items():
            if pfield.annotation is Any and pname in action.arguments:
                any_typed_actions.append((idx, pname))

    if not any_typed_actions:
        return issues

    for target_idx, param_name in any_typed_actions:
        target_action = actions[target_idx]
        original_value = target_action.arguments[param_name]
        variants = _generate_format_variants(original_value)

        for variant_desc, variant_value in variants:
            test_env = get_env()
            if task.initial_state:
                test_env.set_state(
                    initialization_data=task.initial_state.initialization_data,
                    initialization_actions=task.initial_state.initialization_actions,
                    message_history=[],
                )

            # Run all actions, substituting the variant for the target
            action_failed = False
            for i, action in enumerate(actions):
                args = dict(action.arguments)
                if i == target_idx:
                    args[param_name] = variant_value
                try:
                    test_env.make_tool_call(
                        action.name, requestor=action.requestor, **args
                    )
                    test_env.sync_tools()
                except Exception:
                    action_failed = True
                    break

            if action_failed:
                continue

            # Check assertions
            for assertion in assertions:
                try:
                    result = test_env.run_env_assertion(
                        assertion, raise_assertion_error=False
                    )
                    if not result:
                        issues.append(
                            f"ERROR: assertion '{assertion.func_name}' fails when "
                            f"'{target_action.name}' param '{param_name}' uses "
                            f"{variant_desc} format ({variant_value!r} instead of "
                            f"{original_value!r}). Assertion may be too strict for "
                            f"LLM-formatted values."
                        )
                except Exception:
                    pass

    return issues


def verify_assertion_value_discoverability(
    task: Task,
    context_texts: list[str],
) -> list[str]:
    """Static check — for each env_assertion with expected values, verify
    the expected outcome is derivable from the user's context or action args.

    Catches scenarios where an assertion expects a specific result (e.g.,
    ``expected_amount=0.0``) but the known_info doesn't give the agent
    enough information to know what result to produce.
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    assertions = ec.env_assertions or []
    actions = ec.actions or []

    if any(a.name == "transfer_to_human" for a in actions):
        return issues

    # Collect discoverable values from context and action arguments
    known_values: set[str] = set()
    for text in context_texts:
        if text:
            known_values.update(_extract_values(text))
    for action in actions:
        _collect_leaf_values(action.arguments, known_values)

    # Common "end state" values that don't need to be in context.
    # These are target states produced by fix tools — the agent calls the
    # tool and the tool always sets the correct value.
    trivial_values = {
        "0", "0.0", "0.00", "1", "1.0",
        "true", "false", "True", "False",
        "active", "inactive", "scheduled", "cancelled",
        "paid", "pending", "overdue", "current", "expired",
        # Post-fix end states for progressive-discovery domains
        "normal", "clean", "aligned",
        "requested", "ready", "registered",
    }

    for assertion in assertions:
        for arg_name, arg_value in (assertion.arguments or {}).items():
            if isinstance(arg_value, bool) or arg_value is None:
                continue
            val_str = str(arg_value)

            if val_str.lower() in trivial_values:
                continue

            # Threshold / comparison args (min_*, max_*) are assertion-
            # internal criteria, not values the agent must target.  The
            # agent calls a fix tool which always sets a correct value;
            # the assertion merely checks the result exceeds a threshold.
            if arg_name.startswith("min_") or arg_name.startswith("max_"):
                continue

            # Entity ID args (*_id) are discovered through tool call
            # chains (e.g. customer_name → get_customer → customer_id →
            # get_vehicles → vehicle_id).  They are never user-provided
            # knowledge, so their absence from user context is expected.
            if arg_name.endswith("_id"):
                continue

            # Build numeric variants
            val_variants = {val_str}
            try:
                num = float(val_str)
                val_variants.add(str(int(num)) if num == int(num) else val_str)
                val_variants.add(f"{num:.0f}")
                val_variants.add(f"{num:.1f}")
                val_variants.add(f"{num:.2f}")
            except (ValueError, OverflowError):
                pass

            found = any(v in known_values for v in val_variants) or any(
                any(v in text for v in val_variants)
                for text in context_texts
                if text
            )
            if not found:
                issues.append(
                    f"WARNING: assertion '{assertion.func_name}' expected "
                    f"'{arg_name}={arg_value}' not found in user context or "
                    f"action arguments. The agent may not be able to achieve "
                    f"this specific result."
                )

    return issues


def verify_action_necessity(
    task: Task,
    get_env: Callable[[], Environment],
) -> list[str]:
    """
    Runtime check — for each action, check that removing it causes assertion failure.
    Detects redundant actions by running golden path without each action.
    """
    issues: list[str] = []

    if task.evaluation_criteria is None:
        return issues

    ec = task.evaluation_criteria
    actions = ec.actions or []
    assertions = ec.env_assertions or []

    if len(actions) <= 1 or not assertions:
        return issues
    if any(a.name == "transfer_to_human" for a in actions):
        return issues

    for skip_idx, skipped in enumerate(actions):
        env = get_env()
        if task.initial_state:
            env.set_state(
                initialization_data=task.initial_state.initialization_data,
                initialization_actions=task.initial_state.initialization_actions,
                message_history=[],
            )

        for i, action in enumerate(actions):
            if i == skip_idx:
                continue
            try:
                env.make_tool_call(
                    action.name, requestor=action.requestor, **action.arguments
                )
                env.sync_tools()
            except Exception:
                break  # Can't complete, skip this skip_idx

        all_pass = all(
            env.run_env_assertion(a, raise_assertion_error=False)
            for a in assertions
        )
        if all_pass:
            issues.append(
                f"WARNING: action '{skipped.name}' (requestor={skipped.requestor}) "
                f"is unnecessary — all assertions pass without it"
            )

    return issues


def verify_tasks(
    tasks: list[Task],
    get_env: Callable[[], Environment],
    is_fixed: Optional[Callable[[Environment], bool]] = None,
    policy_text: Optional[str] = None,
) -> dict[str, list[str]]:
    """Run all verification checks on generated tasks. Returns {task_id: [warnings]}.

    Args:
        tasks: Tasks to verify.
        get_env: Factory function that returns a fresh environment.
        is_fixed: Optional predicate for the legacy verify_task check.
        policy_text: Policy document text. Required for user action policy alignment
            check. If not provided and tasks have user actions, a warning is emitted.
    """
    results: dict[str, list[str]] = {}

    for task in tasks:
        task_issues: list[str] = []

        # Check 1: reward basis
        task_issues.extend(verify_reward_basis(task))

        # Check 2: tool schemas (needs env with init state applied)
        env = get_env()
        if task.initial_state:
            env.set_state(
                initialization_data=task.initial_state.initialization_data,
                initialization_actions=task.initial_state.initialization_actions,
                message_history=[],
            )
        task_issues.extend(verify_tool_schemas(task, env))

        # Check 3: argument reachability
        context_texts: list[str] = []
        if task.ticket:
            context_texts.append(task.ticket)
        if task.user_scenario and task.user_scenario.instructions:
            if task.user_scenario.instructions.known_info:
                context_texts.append(task.user_scenario.instructions.known_info)
            if task.user_scenario.instructions.task_instructions:
                context_texts.append(task.user_scenario.instructions.task_instructions)
        task_issues.extend(
            verify_argument_reachability(task, get_env, context_texts)
        )

        # Check 4: golden path (run fix actions, check assertions pass)
        task_issues.extend(verify_golden_path(task, get_env))

        # Check 5: user action feasibility
        task_issues.extend(
            verify_user_action_feasibility(task, context_texts)
        )

        # Check 6: user action policy alignment
        if policy_text is not None:
            task_issues.extend(
                verify_user_action_policy_alignment(task, policy_text)
            )

        # Check 7: user action redundancy
        task_issues.extend(
            verify_user_action_redundancy(task, get_env)
        )

        # Check 8: action state change (no-op detection)
        task_issues.extend(
            verify_action_state_change(task, get_env)
        )

        # Check 9: action necessity (redundancy detection)
        task_issues.extend(
            verify_action_necessity(task, get_env)
        )

        # Check 10: assertion robustness to LLM format variations
        task_issues.extend(
            verify_assertion_robustness(task, get_env)
        )

        # Check 11: assertion value discoverability
        task_issues.extend(
            verify_assertion_value_discoverability(task, context_texts)
        )

        # Existing verify_task check (if is_fixed provided)
        if is_fixed is not None:
            try:
                verify_task(task, get_env, is_fixed)
            except AssertionError as e:
                task_issues.append(f"ERROR: verify_task failed: {e}")

        if task_issues:
            results[task.id] = task_issues

    # Print summary
    num_passed = len(tasks) - len(results)
    num_warned = len(results)
    print(f"\nVerification: {num_passed} tasks passed, {num_warned} had issues")
    for task_id, issues in results.items():
        print(f"  {task_id}:")
        for issue in issues:
            print(f"    - {issue}")

    return results


# ---------------------------------------------------------------------------
# LLM-based semantic verification
# ---------------------------------------------------------------------------


def build_llm_verification_prompt(
    task: Task,
    policy_text: str,
    tools_summary: str,
) -> str:
    """Build an LLM prompt that checks a task for semantic issues.

    Returns a prompt string. The caller is responsible for sending it to an LLM
    and parsing the response.

    Checks the LLM is asked to perform:
    1. Fix-action / assertion chain: does the fix tool actually modify the DB field
       that the assertion checks?
    2. Policy alignment: do the expected actions match what the policy prescribes?
    3. Known_info clarity: does the user description express clear intent and
       disambiguate which resource is being discussed?
    4. User action feasibility: if user_actions exist, does the policy instruct
       the agent to tell the user to perform those actions?
    5. Task instructions for user simulator: if user_actions exist, are there
       task_instructions telling the simulator to call those tools?
    6. User action preconditions: for each fault with both agent and user actions,
       does the agent tool have a precondition requiring the user action first?
    7. Data-policy consistency: do task data values violate any policy rules?
    8. Init state record coherence: do init mutations leave stale/contradictory
       fields on the same DB record?
    9. Entity-resource ownership: do resource IDs belong to the correct entity?
    10. Tool precondition robustness: can user tools + sync_tools invalidate an
        agent tool's preconditions, making it unreachable?
    11. Known-info / resolution alignment: does the user framing make the expected
        fix actions the natural response, or does it suggest a different path?
    12. Unfixable state preservation: do transfer tasks have assertions verifying
        the agent didn't modify the injected state?
    13. Multi-action fault coherence: do multi-step fix sequences form a logical
        chain without redundancy or inconsistent intermediate states?
    """
    # Extract task fields
    ec = task.evaluation_criteria
    actions = ec.actions if ec else []
    assertions = ec.env_assertions if ec else []
    ticket = task.ticket or ""
    known_info = ""
    task_instructions = ""
    if task.user_scenario and task.user_scenario.instructions:
        known_info = task.user_scenario.instructions.known_info or ""
        task_instructions = task.user_scenario.instructions.task_instructions or ""

    # Format init actions for the prompt
    init_actions = []
    if task.initial_state and task.initial_state.initialization_actions:
        init_actions = task.initial_state.initialization_actions
    init_text = "\n".join(
        f"  - {a.func_name}(env_type={a.env_type}, args={a.arguments})"
        for a in init_actions
    ) if init_actions else "  (none)"

    # Format actions and assertions for the prompt
    actions_text = "\n".join(
        f"  - {a.name}(requestor={a.requestor}, args={a.arguments})"
        + (f" [compare_args={a.compare_args}]" if a.compare_args is not None else "")
        for a in (actions or [])
    )
    assertions_text = "\n".join(
        f"  - {a.func_name}(env_type={a.env_type}, args={a.arguments}, "
        f"assert_value={a.assert_value})"
        for a in (assertions or [])
    )

    user_actions = [a for a in (actions or []) if a.requestor == "user"]
    user_actions_text = "\n".join(
        f"  - {a.name}(args={a.arguments})"
        for a in user_actions
    ) if user_actions else "  (none)"

    return f"""You are a QA reviewer for an automated customer service benchmark.
Review this task for semantic correctness. Report any issues found.

## Task: {task.id}

### Ticket (agent sees this):
{ticket}

### Known Info (user tells agent this):
{known_info}

### Task Instructions (for user simulator):
{task_instructions or "(empty)"}

### Init Actions (run before conversation to inject faults):
{init_text}

### Fix Actions (agent/user must perform these):
{actions_text or "  (none)"}

### Post-Condition Assertions (must pass after fix actions):
{assertions_text or "  (none)"}

### User-Side Actions:
{user_actions_text}

## Policy:
{policy_text}

## Available Tools:
{tools_summary}

## Check these items and report issues:

1. **Fix-Action / Assertion Chain**: For each assertion, verify that one of the
   fix actions actually modifies the specific DB field the assertion checks.
   Example issue: assertion checks `appointment.dentist` but no fix action calls
   a tool that changes the dentist field.

2. **Policy Alignment**: Do the expected fix actions match what the policy says
   to do for this type of issue? Are there any policy violations?

3. **Known Info Clarity**: Does the known_info express clear USER INTENT
   (not just state)? Does it disambiguate which resource is affected when
   multiple exist (e.g., "my appointment on March 5" not "my appointment")?

4. **User Action Feasibility**: If user-side actions exist, does the policy
   instruct the agent to tell the user to perform those specific actions?
   Are the user actions realistic for this scenario?

5. **Task Instructions for User Simulator**: If there are user-side actions,
   are there task_instructions telling the user simulator to call those tools?
   Without instructions, the user simulator won't execute user actions.

6. **User Action Preconditions**: For each task that has BOTH agent actions and
   user actions, verify that the agent tool has a precondition requiring the
   user action to happen first. Look at the available tools — does the agent-side
   tool check a field that only gets set when the user acts? If the agent tool
   can succeed without the user action, the agent will bypass the user action
   entirely (ACTION:0.0). Flag this as a WARNING.

7. **Data-Policy Consistency**: Check whether any data values referenced in the
   task violate rules stated in the policy. For example: if the policy says
   "do not schedule on weekends or holidays" but the task expects rescheduling
   to a Saturday, that is a contradiction between the authored data and the
   policy. The agent may correctly follow the policy and refuse, causing the
   task to fail. Flag any such contradictions.

8. **Init State Record Coherence**: Look at the init mutations described in the
   task setup. After these mutations run, will ALL fields on each affected DB
   record be internally consistent? Init functions typically only set the fields
   they target — other fields on the same record retain their original values.
   Flag cases where this leaves stale or contradictory field values. For example:
   if an init sets amount_due=$999.99 on an invoice that originally had
   amount_paid=$150.00, the resulting record (amount_due=999.99, amount_paid=150,
   status=overdue) is contradictory and will confuse the agent.

9. **Entity-Resource Ownership**: Check that all resource IDs (appointment_id,
   prescription_id, invoice_id) referenced in the task actually belong to the
   correct entity. For example: if the task is about pet PET002 but the
   appointment APT001 belongs to pet PET001 according to the DB, the task has
   a cross-entity scoping error. The agent will see that APT001 belongs to a
   different pet and get confused.

10. **Tool Precondition Robustness**: For each agent WRITE tool the agent must
    call, check whether its preconditions (status checks, existence filters)
    can be permanently invalidated by user tools or sync_tools running
    concurrently. During a live conversation, sync_tools runs after EVERY
    tool call, and the user simulator can call ANY available user tool at any
    time — not just the expected user actions. If a user tool + sync_tools
    can change a field that the agent tool filters on (e.g., flipping status
    from "overdue" to "paid"), and this makes the agent tool unreachable even
    though the underlying data still needs fixing, that is a design flaw.
    Tools should gate on the data they actually modify (e.g., amount_due > 0)
    rather than on derived status fields that can be changed independently.
    Flag as a WARNING.

11. **Known-Info / Resolution Alignment**: Read the known_info from the user's
    perspective. Does it frame the problem in a way that makes the expected
    fix actions a natural response? If the expected resolution is a record
    update but the known_info reads like a request for future service (or
    vice versa), a competent agent will reasonably pursue the wrong path.
    The known_info must describe a problem whose obvious fix matches the
    expected actions. Flag as an ERROR if the framing suggests a different
    resolution than the one the task expects.

12. **Unfixable State Preservation**: For transfer/escalation tasks (where
    the only expected action is transfer_to_human), check that there are
    preservation assertions verifying the agent did NOT modify the injected
    state. For example, if a pet is marked deceased, the task should assert
    the status is still "deceased" after the conversation. Without these
    assertions, the agent could modify records it shouldn't touch and still
    pass. Flag as a WARNING if a transfer task injects state (has init
    actions) but has no preservation assertions.

13. **Multi-Action Fault Coherence**: Some faults require multiple fix actions
    (a multi-step resolution). Each step is authored as an "atom" — an
    (init, fix, check) triple — so the correspondence is structural. When
    you see multiple fix actions for what appears to be one fault, verify:
    (a) the actions form a logical sequence (e.g., user pays → agent confirms),
    (b) no action is redundant or contradicts another,
    (c) the assertions collectively verify the entire resolution, not just
    one step. Flag as a WARNING if the multi-step sequence seems fragile
    or if an intermediate step could leave the system in an inconsistent state.

Respond in this exact format:
ISSUES_FOUND: <yes|no>
<If yes, list each issue on its own line prefixed with "- ERROR:" or "- WARNING:">
"""


def parse_llm_verification_response(response: str) -> list[str]:
    """Parse the LLM's verification response into a list of issues.

    Returns a list of issue strings (empty if no issues found).
    """
    issues: list[str] = []
    lines = response.strip().splitlines()

    # Check if any issues were found
    found_line = ""
    for line in lines:
        if line.strip().upper().startswith("ISSUES_FOUND:"):
            found_line = line.strip()
            break

    if "no" in found_line.lower():
        return issues

    # Extract issue lines
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ERROR:") or stripped.startswith("- WARNING:"):
            issues.append(f"LLM_REVIEW: {stripped[2:]}")  # strip "- " prefix

    return issues


def verify_tasks_with_llm(
    tasks: list[Task],
    policy_text: str,
    tools_summary: str,
    llm_call_fn: Callable[[str], str],
    sample_size: Optional[int] = None,
    seed: int = 42,
) -> dict[str, list[str]]:
    """Run LLM-based semantic verification on tasks.

    Args:
        tasks: Tasks to verify.
        policy_text: The domain's policy.md content.
        tools_summary: Summary of available tools (e.g., from tools.py docstrings).
        llm_call_fn: Callable that takes a prompt string and returns LLM response string.
        sample_size: If set, verify only this many tasks (randomly sampled). None = all.
        seed: Random seed for sampling.

    Returns:
        Dict mapping task_id to list of LLM-reported issues.
    """
    import random

    tasks_to_check = tasks
    if sample_size is not None and sample_size < len(tasks):
        rng = random.Random(seed)
        tasks_to_check = rng.sample(tasks, sample_size)

    results: dict[str, list[str]] = {}
    for task in tasks_to_check:
        prompt = build_llm_verification_prompt(task, policy_text, tools_summary)
        try:
            response = llm_call_fn(prompt)
            issues = parse_llm_verification_response(response)
            if issues:
                results[task.id] = issues
        except Exception as e:
            results[task.id] = [f"LLM_REVIEW: ERROR calling LLM: {e}"]

    # Print summary
    num_checked = len(tasks_to_check)
    num_issues = len(results)
    print(f"\nLLM Verification: checked {num_checked} tasks, {num_issues} had issues")
    for task_id, issues in results.items():
        print(f"  {task_id}:")
        for issue in issues:
            print(f"    - {issue}")

    return results
