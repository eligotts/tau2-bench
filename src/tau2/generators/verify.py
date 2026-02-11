import textwrap
from typing import Callable

from tau2.data_model.tasks import EnvAssertion, Task
from tau2.environment.environment import Environment


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
    action_names = {a.name for a in task.evaluation_criteria.actions or []}
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
