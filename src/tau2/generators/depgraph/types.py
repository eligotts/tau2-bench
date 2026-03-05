"""Schema types for dependency-graph contracts and task intents (v2)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

ToolClassification = Literal["causal", "knowledge-only", "stutter-only"]
RewardBasis = Literal["DB", "ENV_ASSERTION", "ACTION", "COMMUNICATE", "NL_ASSERTION"]


def _check_unique(items: list[str], *, label: str) -> None:
    if len(items) != len(set(items)):
        raise ValueError(f"Duplicate values in {label}")


class ContextSlotSpec(BaseModel):
    """Named role slot to bind task instances to concrete entities."""

    slot_id: str
    entity_type: str
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_slot(self) -> "ContextSlotSpec":
        if not self.slot_id.strip():
            raise ValueError("context slot_id cannot be empty")
        if not self.entity_type.strip():
            raise ValueError("context entity_type cannot be empty")
        return self


class WorldPredicateSpec(BaseModel):
    """Predicate over projected world state."""

    op: Literal["eq"] = "eq"
    path: str
    value: Any

    @model_validator(mode="after")
    def validate_predicate(self) -> "WorldPredicateSpec":
        if not self.path.strip():
            raise ValueError("world predicate path cannot be empty")
        return self


class WorldEffectSpec(BaseModel):
    """Forward world assignment effect."""

    path: str
    set: Any

    @model_validator(mode="after")
    def validate_effect(self) -> "WorldEffectSpec":
        if not self.path.strip():
            raise ValueError("world effect path cannot be empty")
        return self


class BindingSourceSpec(BaseModel):
    """How an assistant binding is acquired from user-observable state."""

    binding_id: str
    source_tool: str
    extraction_path: str
    world_path: Optional[str] = None
    observability_all_of: list[WorldPredicateSpec] = Field(default_factory=list)
    observability_any_of: list[WorldPredicateSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_binding_source(self) -> "BindingSourceSpec":
        if not self.binding_id.strip():
            raise ValueError("binding source binding_id cannot be empty")
        if not self.source_tool.strip():
            raise ValueError("binding source source_tool cannot be empty")
        if not self.extraction_path.strip():
            raise ValueError("binding source extraction_path cannot be empty")
        if self.world_path is not None and not self.world_path.strip():
            raise ValueError("binding source world_path cannot be blank when provided")
        return self


class ActionContract(BaseModel):
    """One transition/action contract in depgraph v2."""

    action_id: str
    requestor: Literal["assistant", "user"]
    tool_name: str
    classification: ToolClassification
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)
    requires_absent_world: list[WorldPredicateSpec] = Field(default_factory=list)
    requires_bindings: list[str] = Field(default_factory=list)
    requires_absent_bindings: list[str] = Field(default_factory=list)
    effects_world: list[WorldEffectSpec] = Field(default_factory=list)
    effects_bindings: list[str] = Field(default_factory=list)
    tool_arg_bindings: dict[str, str] = Field(default_factory=dict)
    stutter_on_fail: bool = True

    @model_validator(mode="after")
    def validate_semantics(self) -> "ActionContract":
        if not self.action_id.strip():
            raise ValueError("action_id cannot be empty")
        if not self.tool_name.strip():
            raise ValueError(f"Action '{self.action_id}' has empty tool_name")

        _check_unique(
            self.requires_bindings,
            label=f"action '{self.action_id}' requires_bindings",
        )
        _check_unique(
            self.requires_absent_bindings,
            label=f"action '{self.action_id}' requires_absent_bindings",
        )
        _check_unique(
            self.effects_bindings,
            label=f"action '{self.action_id}' effects_bindings",
        )

        if set(self.requires_bindings) & set(self.requires_absent_bindings):
            raise ValueError(
                f"Action '{self.action_id}' has bindings present in both "
                "requires_bindings and requires_absent_bindings"
            )

        if self.classification == "stutter-only":
            if self.effects_world or self.effects_bindings:
                raise ValueError(
                    f"stutter-only action '{self.action_id}' cannot define world/binding effects"
                )

        for param_name, binding_id in self.tool_arg_bindings.items():
            if not param_name.strip():
                raise ValueError(
                    f"Action '{self.action_id}' has empty tool_arg_bindings key"
                )
            if not binding_id.strip():
                raise ValueError(
                    f"Action '{self.action_id}' has empty binding id in tool_arg_bindings"
                )
            if (
                binding_id not in self.requires_bindings
                and self.classification != "knowledge-only"
            ):
                raise ValueError(
                    f"Action '{self.action_id}' maps tool param '{param_name}' to binding "
                    f"'{binding_id}' that is not listed in requires_bindings"
                )
        return self


class FactSourceSpec(BaseModel):
    """
    Deprecated v1 alias retained only to avoid import errors during migration.
    New contracts must use BindingSourceSpec under GraphContractSpec.bindings.
    """

    fact_id: str
    source_tool: str
    extraction_path: str
    observability_all_of: list[str] = Field(default_factory=list)
    observability_any_of: list[str] = Field(default_factory=list)


class InvariantSpec(BaseModel):
    """
    Deprecated v1 alias retained only to avoid import errors during migration.
    """

    invariant_id: Optional[str] = None
    if_all: list[str] = Field(default_factory=list)
    then_all: list[str] = Field(default_factory=list)
    then_none: list[str] = Field(default_factory=list)


class EnvFunctionCallSpec(BaseModel):
    """Serializable env function call specification."""

    env_type: Literal["assistant", "user"]
    func_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class EnvAssertionSpec(EnvFunctionCallSpec):
    """Serializable env assertion specification."""

    assert_value: bool = True
    message: Optional[str] = None


class ActionExpectationSpec(BaseModel):
    """Serializable action expectation for Task.evaluation_criteria.actions."""

    action_id: str
    requestor: Literal["assistant", "user"] = "assistant"
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    compare_args: Optional[list[str]] = None


class RuntimeTaskSpec(BaseModel):
    """tau2 runtime-facing metadata needed to compile a Task."""

    domain: str
    reason_for_call: str
    task_instructions: str
    persona: Optional[str] = None
    known_info: Optional[str] = None
    unknown_info: Optional[str] = None
    ticket: Optional[str] = None
    purpose: Optional[str] = None
    relevant_policies: Optional[str] = None
    notes: Optional[str] = None
    initialization_actions: list[EnvFunctionCallSpec] = Field(default_factory=list)
    env_assertions: list[EnvAssertionSpec] = Field(default_factory=list)
    actions: list[ActionExpectationSpec] = Field(default_factory=list)
    reward_basis: list[RewardBasis] = Field(default_factory=lambda: ["ENV_ASSERTION"])


class GraphContractSpec(BaseModel):
    """Top-level depgraph v2 contract document."""

    version: int = 2
    context_slots: list[ContextSlotSpec] = Field(default_factory=list)
    projection_fields: list[str] = Field(default_factory=list)
    bindings: list[BindingSourceSpec] = Field(default_factory=list)
    actions: list[ActionContract] = Field(default_factory=list)

    # Deprecated v1 fields kept only to avoid runtime import/attribute errors while
    # other modules are migrated. New authoring should not populate these.
    fact_sources: list[FactSourceSpec] = Field(default_factory=list)
    mutex_pairs: list[tuple[str, str]] = Field(default_factory=list)
    invariants: list[InvariantSpec] = Field(default_factory=list)
    assistant_stutter_allowlist: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contract(self) -> "GraphContractSpec":
        if self.version != 2:
            raise ValueError(
                f"Graph contract version must be 2 for depgraph v2 (got {self.version})"
            )

        slot_ids = [s.slot_id for s in self.context_slots]
        _check_unique(slot_ids, label="context_slots.slot_id")

        projection_paths = [p for p in self.projection_fields if p.strip()]
        _check_unique(projection_paths, label="projection_fields")

        binding_ids = [b.binding_id for b in self.bindings]
        _check_unique(binding_ids, label="bindings.binding_id")
        binding_id_set = set(binding_ids)

        action_ids = [a.action_id for a in self.actions]
        _check_unique(action_ids, label="actions.action_id")

        for action in self.actions:
            if (
                action.requestor == "assistant"
                and action.classification == "stutter-only"
                and action.action_id not in self.assistant_stutter_allowlist
            ):
                raise ValueError(
                    "assistant stutter-only actions must be explicitly allowlisted: "
                    f"{action.action_id}"
                )
            unknown_refs = (
                set(action.requires_bindings)
                | set(action.requires_absent_bindings)
                | set(action.effects_bindings)
                | set(action.tool_arg_bindings.values())
            ) - binding_id_set
            if unknown_refs:
                raise ValueError(
                    f"Action '{action.action_id}' references unknown binding ids: "
                    f"{sorted(unknown_refs)}"
                )

        return self


class TaskIntent(BaseModel):
    """Task intent used for preflight checking and optional runtime compile."""

    task_id: str
    start_world: list[WorldEffectSpec] = Field(default_factory=list)
    start_bindings: list[str] = Field(default_factory=list)
    goal_world: list[WorldPredicateSpec] = Field(default_factory=list)
    goal_bindings: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    # Optional trace metadata; not enforced as a history-order constraint in SAT checks.
    required_precedence: list[tuple[str, str]] = Field(default_factory=list)
    min_plan_length: int = 1
    runtime: Optional[RuntimeTaskSpec] = None

    @model_validator(mode="after")
    def validate_task_intent(self) -> "TaskIntent":
        if not self.task_id.strip():
            raise ValueError("task_id cannot be empty")
        _check_unique(
            self.start_bindings,
            label=f"task '{self.task_id}' start_bindings",
        )
        _check_unique(
            self.goal_bindings,
            label=f"task '{self.task_id}' goal_bindings",
        )
        _check_unique(
            self.required_actions,
            label=f"task '{self.task_id}' required_actions",
        )
        if self.min_plan_length < 0:
            raise ValueError("min_plan_length must be >= 0")
        return self


class TaskSpecsDoc(BaseModel):
    """Top-level task specs document."""

    version: int = 1
    tasks: list[TaskIntent] = Field(default_factory=list)


class SamplingSeedSpec(BaseModel):
    """Seed state for task-intent sampling."""

    seed_id: str
    start_world: list[WorldEffectSpec] = Field(default_factory=list)
    start_bindings: list[str] = Field(default_factory=list)
    min_depth: int = 3
    max_depth: int = 8

    @model_validator(mode="after")
    def validate_seed(self) -> "SamplingSeedSpec":
        if not self.seed_id.strip():
            raise ValueError("seed_id cannot be empty")
        if self.min_depth < 0:
            raise ValueError("min_depth must be >= 0")
        if self.max_depth < self.min_depth:
            raise ValueError("max_depth must be >= min_depth")
        _check_unique(
            self.start_bindings,
            label=f"seed '{self.seed_id}' start_bindings",
        )
        return self


class SamplingRequestDoc(BaseModel):
    """Input document for fan-out task-intent sampling."""

    version: int = 1
    max_tasks: int = 20
    goal_world_path_prefixes: list[str] = Field(
        default_factory=lambda: ["agent.", "user."]
    )
    seeds: list[SamplingSeedSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sampling_request(self) -> "SamplingRequestDoc":
        if self.max_tasks <= 0:
            raise ValueError("max_tasks must be > 0")
        _check_unique(
            [seed.seed_id for seed in self.seeds],
            label="sampling_request.seeds.seed_id",
        )
        return self
