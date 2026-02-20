"""Unified entry point for domain task generation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall, Task
from tau2.environment.environment import Environment
from tau2.generators.entity_engine import (
    TemplateFunc,
    BuildIndexesFunc,
    generate_entity_tasks,
)
from tau2.generators.recipe import RecipeBook, generate_recipe_tasks
from tau2.generators.generate import generate_tasks, generate_tasks_with_variants
from tau2.generators.types import (
    Persona,
    Scenario,
    ScenarioGroup,
    UserTemplate,
    VariantConfig,
)
from tau2.generators.verify import verify_tasks


class GenerationStrategy(str, Enum):
    """Strategy for generating tasks."""

    FAULT_COMPOSITION = "fault_composition"
    ENTITY_TEMPLATE = "entity_template"
    RECIPE = "recipe"


@dataclass
class DomainConfig:
    """Unified configuration for task generation, supporting either strategy."""

    strategy: GenerationStrategy
    user_template: UserTemplate
    personas: list[Persona]

    # Fault-composition params
    groups: list[ScenarioGroup] = field(default_factory=list)
    get_env: Optional[Callable[[], Environment]] = None
    get_env_assertions: Optional[Callable[[bool], list[EnvAssertion]]] = None
    env_setup: Optional[Callable[[Environment], list[EnvFunctionCall]]] = None
    get_template_vars: Optional[Callable[[Environment], dict[str, str]]] = None
    validator: Optional[Callable[[list[Optional[Scenario]]], bool]] = None
    transfer_action_name: str = "transfer_to_human"

    # Entity-template params
    templates: list[TemplateFunc] = field(default_factory=list)
    build_indexes: Optional[BuildIndexesFunc] = None
    get_db: Optional[Callable[[], Any]] = None
    task_instructions: Optional[str] = None
    seed: int = 42

    # Recipe params
    recipe_book: Optional[RecipeBook] = None

    # Shared variant params
    variant_config: Optional[VariantConfig] = None

    # Verification
    verify: bool = True


def create_domain_tasks(config: DomainConfig) -> list[Task]:
    """Dispatch to the appropriate generation engine based on strategy."""
    if config.strategy == GenerationStrategy.FAULT_COMPOSITION:
        assert config.get_env is not None, "get_env required for fault_composition"
        assert config.get_env_assertions is not None, "get_env_assertions required"
        assert config.env_setup is not None, "env_setup required"
        assert config.get_template_vars is not None, "get_template_vars required"

        if config.variant_config is not None:
            tasks = generate_tasks_with_variants(
                groups=config.groups,
                get_env=config.get_env,
                user_template=config.user_template,
                personas=config.personas,
                get_env_assertions=config.get_env_assertions,
                env_setup=config.env_setup,
                get_template_vars=config.get_template_vars,
                variant_config=config.variant_config,
                validator=config.validator,
                transfer_action_name=config.transfer_action_name,
            )
        else:
            tasks = generate_tasks(
                groups=config.groups,
                get_env=config.get_env,
                user_template=config.user_template,
                personas=config.personas,
                get_env_assertions=config.get_env_assertions,
                env_setup=config.env_setup,
                get_template_vars=config.get_template_vars,
                validator=config.validator,
                transfer_action_name=config.transfer_action_name,
            )

    elif config.strategy == GenerationStrategy.ENTITY_TEMPLATE:
        assert config.get_env is not None, "get_env required for entity_template"
        assert config.get_db is not None, "get_db required for entity_template"
        assert config.build_indexes is not None, "build_indexes required"
        assert config.templates, "templates required for entity_template"

        tasks = generate_entity_tasks(
            templates=config.templates,
            build_indexes=config.build_indexes,
            get_env=config.get_env,
            get_db=config.get_db,
            user_template=config.user_template,
            personas=config.personas,
            task_instructions=config.task_instructions,
            variant_config=config.variant_config,
            seed=config.seed,
        )

    elif config.strategy == GenerationStrategy.RECIPE:
        assert config.get_db is not None, "get_db required for recipe"
        assert config.build_indexes is not None, "build_indexes required for recipe"
        assert config.recipe_book is not None, "recipe_book required for recipe"

        tasks = generate_recipe_tasks(
            recipe_book=config.recipe_book,
            build_indexes=config.build_indexes,
            get_db=config.get_db,
            user_template=config.user_template,
            personas=config.personas,
            task_instructions=config.task_instructions,
            variant_config=config.variant_config,
            seed=config.seed,
        )

    else:
        raise ValueError(f"Unknown strategy: {config.strategy}")

    if config.verify and config.get_env is not None:
        report = verify_tasks(tasks, config.get_env)
        errors = {
            tid: [i for i in issues if i.startswith("ERROR:")]
            for tid, issues in report.items()
        }
        errors = {tid: errs for tid, errs in errors.items() if errs}
        if errors:
            raise ValueError(
                f"Verification found errors in {len(errors)} task(s). "
                f"See report above."
            )

    return tasks
