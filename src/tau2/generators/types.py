from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel, Field

from tau2.data_model.message import ToolCall
from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall
from tau2.environment.environment import Environment

InitFuncType = Callable[[Environment], list[EnvFunctionCall | EnvAssertion]]
FixFuncType = Callable[[Environment], list[ToolCall]] | None
EnvAssertionType = Callable[[Environment], list[EnvAssertion]]


class Difficulty(str, Enum):
    """Difficulty level for personas and task variants."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Scenario(BaseModel):
    """Atomic fault definition. Maps to telecom's BaseTask."""

    name: str
    description: str
    init_funcs: list[InitFuncType]
    fix_funcs: list[FixFuncType]
    extra_env_assertions: list[EnvAssertionType] = Field(default_factory=list)
    nl_assertions: list[str] = Field(default_factory=list)
    compare_args_map: Optional[dict[str, Optional[list[str]]]] = None


class ScenarioGroup(BaseModel):
    """Mutually exclusive scenarios (pick 0 or 1). Maps to telecom's SelectionSet."""

    scenarios: list[Scenario]


class ComposedScenario(BaseModel):
    """Result of merging selected scenarios. Maps to telecom's ComposedTask."""

    name: str
    description: str
    composed_from: list[Scenario]
    init_funcs: list[InitFuncType]
    fix_funcs: list[FixFuncType]
    extra_env_assertions: list[EnvAssertionType] = Field(default_factory=list)
    nl_assertions: list[str] = Field(default_factory=list)
    compare_args_map: Optional[dict[str, Optional[list[str]]]] = None

    def __str__(self):
        lines = []
        lines.append("-" * len(self.name))
        lines.append(self.name)
        lines.append("-" * len(self.name))
        lines.append(f"Description: {self.description}")
        lines.append("Scenarios:")
        for s in self.composed_from:
            lines.append(f"  - {s.name}: {s.description}")
        lines.append("Init Funcs:")
        for func in self.init_funcs:
            lines.append(f"  - {func.__name__}")
        lines.append("Fix Funcs:")
        for func in self.fix_funcs:
            lines.append(f"  - {func.__name__}" if func is not None else "  - None")
        lines.append("Extra Env Assertions:")
        for func in self.extra_env_assertions:
            lines.append(f"  - {func.__name__}")
        if self.nl_assertions:
            lines.append("NL Assertions:")
            for a in self.nl_assertions:
                lines.append(f"  - {a}")
        return "\n".join(lines)

    def __repr__(self):
        return self.__str__()


class Persona(BaseModel):
    """User persona."""

    name: str
    description: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    instructions: Optional[str] = None


class UserTemplate(BaseModel):
    """Template with {placeholder} strings for generating user scenarios."""

    domain: str
    reason_for_call: str
    known_info: str
    task_instructions: str
    ticket: str
    purpose: str


class VariantConfig(BaseModel):
    """Configuration for generating A/B task variants.

    Difficulty comes from persona behavior (cooperative vs anxious/confused),
    NOT from withholding information. Both variants get the same known_info.
    This matches the telecom domain's PERSONA pattern.
    """

    easy_personas: list[Persona] = Field(default_factory=list)
    hard_personas: list[Persona] = Field(default_factory=list)
