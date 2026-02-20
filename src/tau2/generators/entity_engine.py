"""Entity-template engine for generating tasks from database entities."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Optional

from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall, Task
from tau2.environment.environment import Environment
from tau2.generators.diversity import DiversityTracker
from tau2.generators.types import Difficulty, Persona, UserTemplate, VariantConfig


class TaskTier(IntEnum):
    """Difficulty tier for entity-template tasks (1=easiest, 5=hardest)."""

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4
    TIER_5 = 5


# Map tiers to Difficulty levels
_TIER_TO_DIFFICULTY: dict[TaskTier, Difficulty] = {
    TaskTier.TIER_1: Difficulty.EASY,
    TaskTier.TIER_2: Difficulty.EASY,
    TaskTier.TIER_3: Difficulty.MEDIUM,
    TaskTier.TIER_4: Difficulty.MEDIUM,
    TaskTier.TIER_5: Difficulty.HARD,
}


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


def _select_persona(
    tier: TaskTier,
    personas: list[Persona],
    index: int,
) -> Persona:
    """Select persona based on tier→difficulty mapping when personas have difficulty set."""
    target_difficulty = _TIER_TO_DIFFICULTY[tier]

    # Filter personas by matching difficulty
    matching = [p for p in personas if p.difficulty == target_difficulty]
    if matching:
        return matching[index % len(matching)]

    # Fall back to round-robin over all personas
    return personas[index % len(personas)]


def _spec_to_task(
    spec: GeneratedTaskSpec,
    user_template: UserTemplate,
    persona: Persona,
    task_instructions: Optional[str] = None,
    id_suffix: str = "",
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

    task_dict = {
        "id": f"[{user_template.domain}]{spec.task_id}[PERSONA:{persona.name}]{id_suffix}",
        "description": {
            "purpose": spec.purpose,
            "info": spec.description,
        },
        "user_scenario": {
            "instructions": {
                "task_instructions": task_instructions or spec.user_task_instructions or user_template.task_instructions,
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
    task_instructions: Optional[str] = None,
    variant_config: Optional[VariantConfig] = None,
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
        personas: Available personas for assignment.
        task_instructions: Override for task instructions (optional).
        variant_config: If provided, generate A/B variants for each spec.
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

    tasks: list[Task] = []
    for i, spec in enumerate(all_specs):
        persona = _select_persona(spec.tier, personas, i)

        if variant_config is not None:
            # Variant A: easy persona, exact known_info
            easy_personas = variant_config.easy_personas or personas
            easy_persona = _select_persona(spec.tier, easy_personas, i)
            task_a = _spec_to_task(
                spec, user_template, easy_persona,
                task_instructions=task_instructions,
                id_suffix="[VARIANT:a]",
            )
            tasks.append(task_a)

            # Variant B: hard persona, SAME known_info (difficulty from persona only)
            hard_personas = variant_config.hard_personas or personas
            hard_persona = _select_persona(spec.tier, hard_personas, i)
            task_b = _spec_to_task(
                spec, user_template, hard_persona,
                task_instructions=task_instructions,
                id_suffix="[VARIANT:b]",
            )
            tasks.append(task_b)
        else:
            task = _spec_to_task(
                spec, user_template, persona,
                task_instructions=task_instructions,
            )
            tasks.append(task)

    print(f"Entity engine: {len(tasks)} tasks generated")
    return tasks
