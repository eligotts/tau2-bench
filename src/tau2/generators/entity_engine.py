"""Entity-template engine for generating tasks from database entities."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Optional

from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall, Task
from tau2.environment.environment import Environment
from tau2.generators.diversity import DiversityTracker
from tau2.generators.types import Persona, UserTemplate


class TaskTier(IntEnum):
    """Difficulty tier for entity-template tasks (1=easiest, 5=hardest)."""

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4
    TIER_5 = 5


@dataclass
class GeneratedTaskSpec:
    """Lightweight spec that template functions return before conversion to Task."""

    task_id: str
    description: str
    purpose: str
    known_info: str
    reason_for_call: str
    actions: list[dict] = field(default_factory=list)
    env_assertions: list[EnvAssertion] = field(default_factory=list)
    nl_assertions: list[str] = field(default_factory=list)
    communicate_info: list[str] = field(default_factory=list)
    init_actions: list[EnvFunctionCall] = field(default_factory=list)
    user_task_instructions: Optional[str] = None
    tier: TaskTier = TaskTier.TIER_3


# Type alias for template functions
TemplateFunc = Callable[[Any, DiversityTracker], list[GeneratedTaskSpec]]
BuildIndexesFunc = Callable[[Any], Any]


def _spec_to_task(
    spec: GeneratedTaskSpec,
    user_template: UserTemplate,
    persona: Persona,
) -> Task:
    """Convert a GeneratedTaskSpec to a Task object."""
    known_info = spec.known_info

    reward_basis = ["ENV_ASSERTION"]
    if spec.actions:
        reward_basis.append("ACTION")
    if spec.communicate_info:
        reward_basis.append("COMMUNICATE")
    # NOTE: nl_assertions are stored on the task but NOT added to reward_basis
    # by default, because the default evaluator (EvaluationType.ALL) doesn't
    # evaluate them. Use EvaluationType.ALL_WITH_NL_ASSERTIONS to include them.

    eval_criteria: dict = {
        "actions": spec.actions,
        "env_assertions": spec.env_assertions,
        "reward_basis": reward_basis,
    }
    if spec.communicate_info:
        eval_criteria["communicate_info"] = spec.communicate_info
    if spec.nl_assertions:
        eval_criteria["nl_assertions"] = spec.nl_assertions

    # Recipe engine sets spec.user_task_instructions for specs with user actions.
    # For specs without user actions (unfixable, agent-only), it's None and
    # we fall back to the domain's default instructions from UserTemplate.
    if spec.user_task_instructions is not None:
        task_instructions = spec.user_task_instructions
    else:
        task_instructions = user_template.task_instructions

    task_dict = {
        "id": f"[{user_template.domain}]{spec.task_id}[PERSONA:{persona.name}]",
        "description": {
            "purpose": spec.purpose,
            "info": spec.description,
        },
        "user_scenario": {
            "instructions": {
                "task_instructions": task_instructions,
                "domain": user_template.domain,
                "reason_for_call": spec.reason_for_call,
                "known_info": known_info,
            },
            "persona": persona.description,
        },
        "ticket": spec.description,
        "initial_state": {
            "initialization_actions": spec.init_actions,
        },
        "evaluation_criteria": eval_criteria,
    }

    return Task(**task_dict)


def generate_entity_tasks(
    templates: list[TemplateFunc],
    build_indexes: BuildIndexesFunc,
    get_env: Callable[[], Environment],
    get_db: Callable[[], Any],
    user_template: UserTemplate,
    personas: list[Persona],
    seed: int = 42,
) -> list[Task]:
    """
    Main entry point for entity-template task generation.

    Args:
        templates: List of generator callables that take (indexes, tracker) and return specs.
        build_indexes: Domain-provided function that builds lookup indexes from DB.
        get_env: Factory for fresh environment instances.
        get_db: Factory for database instances.
        user_template: Template for user scenario fields.
        personas: Available personas for assignment (one task per persona per spec).
        seed: Random seed for diversity tracker.

    Returns:
        List of Task objects.
    """
    db = get_db()
    indexes = build_indexes(db)
    tracker = DiversityTracker(seed=seed)

    # Collect all specs from all templates
    all_specs: list[GeneratedTaskSpec] = []
    for template_func in templates:
        specs = template_func(indexes, tracker)
        all_specs.extend(specs)

    print(f"Entity engine: {len(all_specs)} specs from {len(templates)} templates")

    # Phase 3: iterate all personas per spec
    tasks: list[Task] = []
    for spec in all_specs:
        for persona in personas:
            task = _spec_to_task(spec, user_template, persona)
            tasks.append(task)

    print(f"Entity engine: {len(tasks)} tasks generated")
    return tasks
