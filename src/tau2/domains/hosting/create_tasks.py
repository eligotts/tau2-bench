"""
Generate web hosting support tasks using the generators framework.

Run as: python -m tau2.domains.hosting.create_tasks [--difficulty LEVEL]

Difficulty levels:
  easy    - 1-2 scenarios per task
  medium  - 2-3 scenarios per task
  hard    - 3-5 scenarios per task
  expert  - 4-6 scenarios per task
  all     - 2+ scenarios per task (default)
"""

import argparse
import json

from tau2.data_model.tasks import Task
from tau2.domains.hosting.environment import get_environment
from tau2.domains.hosting.scenarios import (
    PERSONAS,
    SCENARIO_GROUPS,
    USER_TEMPLATE,
    get_env_assertions,
    get_template_vars,
    is_fixed,
    make_task_validator,
    set_surrounding,
)
from tau2.domains.hosting.utils import HOSTING_TASK_SET_PATH
from tau2.generators import generate_tasks

DIFFICULTY_PRESETS = {
    "easy":   {"min_scenarios": 1, "max_scenarios": 2},
    "medium": {"min_scenarios": 2, "max_scenarios": 3},
    "hard":   {"min_scenarios": 3, "max_scenarios": 5},
    "expert": {"min_scenarios": 4, "max_scenarios": 6},
    "all":    {"min_scenarios": 2, "max_scenarios": None},
}


def verify_task_relaxed(
    task: Task,
    get_env,
    is_fixed_fn,
) -> None:
    """
    Relaxed verification: only checks that init breaks the env and all
    fix actions together repair it. Does NOT check per-action is_fixed.
    """
    env = get_env()
    assert is_fixed_fn(env), f"Environment starts in broken state for {task.id}"

    env.set_state(
        initialization_data=task.initial_state.initialization_data,
        initialization_actions=task.initial_state.initialization_actions,
        message_history=[],
    )

    fix_actions = task.evaluation_criteria.actions or []
    fixable = not any(a.name == "transfer_to_human" for a in fix_actions)

    assert not is_fixed_fn(env), f"Environment is fixed after init for {task.id}"

    for action in fix_actions:
        env.make_tool_call(
            tool_name=action.name, requestor=action.requestor, **action.arguments
        )
        env.sync_tools()

    if fixable:
        assert is_fixed_fn(env), f"Task {task.id} is not fixed after all actions."
    else:
        assert not is_fixed_fn(env), f"Task {task.id} is fixed but should not be."


def main():
    parser = argparse.ArgumentParser(description="Generate web hosting tasks")
    parser.add_argument(
        "--difficulty",
        choices=list(DIFFICULTY_PRESETS.keys()),
        default="all",
        help="Difficulty preset (default: all)",
    )
    args = parser.parse_args()

    preset = DIFFICULTY_PRESETS[args.difficulty]
    validator = make_task_validator(**preset)

    print("=" * 80)
    print(f"Generating Hosting Tasks (difficulty={args.difficulty})")
    print(f"  min_scenarios={preset['min_scenarios']}, max_scenarios={preset['max_scenarios']}")
    print("=" * 80)

    tasks = generate_tasks(
        groups=SCENARIO_GROUPS,
        get_env=get_environment,
        user_template=USER_TEMPLATE,
        personas=PERSONAS,
        get_env_assertions=get_env_assertions,
        env_setup=set_surrounding,
        get_template_vars=get_template_vars,
        validator=validator,
        transfer_action_name="transfer_to_human",
    )

    print(f"\nGenerated {len(tasks)} tasks.")

    # Verify each task
    print("\n" + "=" * 80)
    print("Verifying Tasks")
    print("=" * 80)

    verified = 0
    failed = 0
    for task in tasks:
        try:
            verify_task_relaxed(task, get_environment, is_fixed)
            verified += 1
        except AssertionError as e:
            print(f"FAILED: {task.id}: {e}")
            failed += 1

    print(f"\nVerification: {verified} passed, {failed} failed out of {len(tasks)} tasks.")

    # Print stats
    print("\n" + "=" * 80)
    print("Task Statistics")
    print("=" * 80)

    fix_action_counts = []
    user_action_counts = []
    persona_counts = {}
    scenario_counts = {}
    for task in tasks:
        actions = task.evaluation_criteria.actions or []
        fix_action_counts.append(len(actions))
        user_action_counts.append(sum(1 for a in actions if a.requestor == "user"))

        persona_name = task.id.split("[PERSONA:")[1].rstrip("]") if "[PERSONA:" in task.id else "unknown"
        persona_counts[persona_name] = persona_counts.get(persona_name, 0) + 1

        scenario_part = task.id.split("]")[1].split("[PERSONA:")[0]
        num_scenarios = len(scenario_part.split("|")) if scenario_part else 0
        scenario_counts[num_scenarios] = scenario_counts.get(num_scenarios, 0) + 1

    print(f"Total tasks: {len(tasks)}")
    print(f"Persona distribution: {persona_counts}")
    print(f"Scenario count distribution: {scenario_counts}")

    avg_fix = sum(fix_action_counts) / len(fix_action_counts) if fix_action_counts else 0
    avg_user = sum(user_action_counts) / len(user_action_counts) if user_action_counts else 0
    total_actions = sum(fix_action_counts)
    total_user = sum(user_action_counts)
    print(f"Avg fix actions per task: {avg_fix:.1f}")
    print(f"Max fix actions: {max(fix_action_counts) if fix_action_counts else 0}")
    print(f"Avg user-side actions per task: {avg_user:.1f}")
    print(f"User-side action %: {100*total_user/total_actions:.0f}%" if total_actions else "N/A")

    fixable = sum(
        1 for t in tasks
        if not any(a.name == "transfer_to_human" for a in (t.evaluation_criteria.actions or []))
    )
    unfixable = len(tasks) - fixable
    print(f"Fixable: {fixable}, Unfixable (escalate): {unfixable}")

    # Save to JSON
    print(f"\nSaving tasks to {HOSTING_TASK_SET_PATH}")
    HOSTING_TASK_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HOSTING_TASK_SET_PATH, "w") as f:
        json.dump([t.model_dump() for t in tasks], f, indent=2, default=str)

    print("Done!")


if __name__ == "__main__":
    main()
