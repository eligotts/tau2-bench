import json
from copy import deepcopy
from typing import Callable, Optional

from tau2.data_model.message import ToolCall
from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall, Task
from tau2.environment.environment import Environment
from tau2.generators.compose import compose_scenarios
from tau2.generators.types import (
    ComposedScenario,
    Persona,
    Scenario,
    ScenarioGroup,
    UserTemplate,
    VariantConfig,
)
from tau2.utils import DATA_DIR


def generate_tasks(
    groups: list[ScenarioGroup],
    get_env: Callable[[], Environment],
    user_template: UserTemplate,
    personas: list[Persona],
    get_env_assertions: Callable[[bool], list[EnvAssertion]],
    env_setup: Callable[[Environment], list[EnvFunctionCall]],
    get_template_vars: Callable[[Environment], dict[str, str]],
    validator: Optional[Callable[[list[Optional[Scenario]]], bool]] = None,
    transfer_action_name: str = "transfer_to_human",
) -> list[Task]:
    """
    Main entry point for generating tasks.
    Composes scenarios, iterates combos x personas (round-robin), builds Task objects.
    Mirrors telecom's TaskManager.create_task/create_tasks but generalized.
    """
    composed = compose_scenarios(groups, validator)
    composed = sorted(composed, key=lambda x: len(x.composed_from))
    print(f"Number of composed scenarios: {len(composed)}")

    persona_options = personas
    tasks = []

    for i, cs in enumerate(composed):
        print(f"Task {i + 1}")
        print(cs.name)
        persona = persona_options[i % len(persona_options)]
        task = _create_task(
            composed_scenario=cs,
            get_env=get_env,
            user_template=user_template,
            persona=persona,
            get_env_assertions=get_env_assertions,
            env_setup=env_setup,
            get_template_vars=get_template_vars,
            transfer_action_name=transfer_action_name,
        )
        print(task)
        print("-" * 100)
        tasks.append(task)

    return tasks


def generate_tasks_with_variants(
    groups: list[ScenarioGroup],
    get_env: Callable[[], Environment],
    user_template: UserTemplate,
    personas: list[Persona],
    get_env_assertions: Callable[[bool], list[EnvAssertion]],
    env_setup: Callable[[Environment], list[EnvFunctionCall]],
    get_template_vars: Callable[[Environment], dict[str, str]],
    variant_config: VariantConfig,
    validator: Optional[Callable[[list[Optional[Scenario]]], bool]] = None,
    transfer_action_name: str = "transfer_to_human",
) -> list[Task]:
    """
    Generate A/B task variants for each composed scenario.
    Variant A: easy persona, exact known_info from user_template.
    Variant B: hard persona, vague known_info from variant_config.
    """
    composed = compose_scenarios(groups, validator)
    composed = sorted(composed, key=lambda x: len(x.composed_from))
    print(f"Number of composed scenarios: {len(composed)}")

    easy_personas = variant_config.easy_personas or personas
    hard_personas = variant_config.hard_personas or personas
    tasks = []

    for i, cs in enumerate(composed):
        print(f"Task {i + 1} (variants)")
        print(cs.name)

        # Variant A: easy persona, exact known_info
        easy_persona = easy_personas[i % len(easy_personas)]
        task_a = _create_task(
            composed_scenario=cs,
            get_env=get_env,
            user_template=user_template,
            persona=easy_persona,
            get_env_assertions=get_env_assertions,
            env_setup=env_setup,
            get_template_vars=get_template_vars,
            transfer_action_name=transfer_action_name,
            id_suffix="[VARIANT:a]",
        )
        tasks.append(task_a)

        # Variant B: hard persona, SAME known_info (difficulty from persona only)
        hard_persona = hard_personas[i % len(hard_personas)]
        task_b = _create_task(
            composed_scenario=cs,
            get_env=get_env,
            user_template=user_template,
            persona=hard_persona,
            get_env_assertions=get_env_assertions,
            env_setup=env_setup,
            get_template_vars=get_template_vars,
            transfer_action_name=transfer_action_name,
            id_suffix="[VARIANT:b]",
        )
        tasks.append(task_b)

        print("-" * 100)

    return tasks


def _create_task(
    composed_scenario: ComposedScenario,
    get_env: Callable[[], Environment],
    user_template: UserTemplate,
    persona: Persona,
    get_env_assertions: Callable[[bool], list[EnvAssertion]],
    env_setup: Callable[[Environment], list[EnvFunctionCall]],
    get_template_vars: Callable[[Environment], dict[str, str]],
    transfer_action_name: str = "transfer_to_human",
    id_suffix: str = "",
) -> Task:
    """Create a single Task from a ComposedScenario."""
    env = get_env()

    # Run environment setup (set user surroundings, etc.)
    init_actions = env_setup(env)
    env.run_env_function_calls(init_actions)

    # Run scenario init funcs to create issues
    for func in composed_scenario.init_funcs:
        func_calls = func(env)
        env.run_env_function_calls(func_calls)
        init_actions.extend(
            [fc for fc in func_calls if not isinstance(fc, EnvAssertion)]
        )

    # Collect fix tool calls
    fix_tool_calls: list[ToolCall] = []
    expected_failure = False
    for func in composed_scenario.fix_funcs:
        if func is None:
            expected_failure = True
            break
        tool_calls = func(env)
        fix_tool_calls.extend(tool_calls)

    compare_args_map = composed_scenario.compare_args_map

    reward_eval_mode = ["ENV_ASSERTION"]
    if expected_failure:
        fix_actions = [
            {
                "action_id": transfer_action_name,
                "name": transfer_action_name,
                "requestor": "assistant",
                "arguments": {"summary": "I cannot fix the issue."},
                "compare_args": [],
            }
        ]
        reward_eval_mode.append("ACTION")
    else:
        fix_actions = []
        for i, tc in enumerate(fix_tool_calls):
            action_dict: dict = {
                "action_id": f"{tc.name}_{i}",
                "name": tc.name,
                "requestor": tc.requestor,
                "arguments": tc.arguments,
            }
            # Apply compare_args from the map if the tool name has an entry
            if compare_args_map is not None and tc.name in compare_args_map:
                action_dict["compare_args"] = compare_args_map[tc.name]
            fix_actions.append(action_dict)

    env_assertions = get_env_assertions(expected_success=not expected_failure)
    if not expected_failure:
        for func in composed_scenario.extra_env_assertions:
            env_assertions.extend(func(env))

    # Collect nl_assertions from composed scenario
    nl_assertions = composed_scenario.nl_assertions or []

    # NOTE: nl_assertions are stored on the task but NOT added to reward_basis
    # by default, because the default evaluator (EvaluationType.ALL) doesn't
    # evaluate them. Use EvaluationType.ALL_WITH_NL_ASSERTIONS to include them.

    # Fill in template variables
    template_vars = get_template_vars(env)
    known_info = user_template.known_info.format(**template_vars)
    ticket = user_template.ticket.format(**template_vars)

    # Build evaluation criteria
    eval_criteria: dict = {
        "actions": fix_actions,
        "env_assertions": env_assertions,
        "reward_basis": reward_eval_mode,
    }
    if nl_assertions:
        eval_criteria["nl_assertions"] = nl_assertions

    task_dict = {
        "id": f"[{user_template.domain}]{composed_scenario.name}[PERSONA:{persona.name}]{id_suffix}",
        "description": {
            "purpose": user_template.purpose,
            "info": composed_scenario.description,
        },
        "user_scenario": {
            "instructions": {
                "task_instructions": user_template.task_instructions,
                "domain": user_template.domain,
                "reason_for_call": user_template.reason_for_call,
                "known_info": known_info,
            },
            "persona": persona.description,
        },
        "ticket": ticket,
        "initial_state": {
            "initialization_actions": init_actions,
        },
        "evaluation_criteria": eval_criteria,
    }

    return Task(**task_dict)
