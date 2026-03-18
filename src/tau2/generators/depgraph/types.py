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

    op: Literal["eq", "neq", "gt", "lt", "gte", "lte"] = "eq"
    path: str
    value: Any

    @model_validator(mode="after")
    def validate_predicate(self) -> "WorldPredicateSpec":
        if not self.path.strip():
            raise ValueError("world predicate path cannot be empty")
        if self.op in {"gt", "lt", "gte", "lte"} and not isinstance(
            self.value, (int, float)
        ):
            raise ValueError(
                f"Comparison operator '{self.op}' requires numeric value, "
                f"got {type(self.value).__name__}"
            )
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


class SyncEffectSpec(BaseModel):
    """Sync output: either copy from another path or set a literal."""

    path: str
    set: Optional[Any] = None
    from_path: Optional[str] = None

    @model_validator(mode="after")
    def validate_sync_effect(self) -> "SyncEffectSpec":
        if not self.path.strip():
            raise ValueError("sync effect path cannot be empty")
        has_set = "set" in self.model_fields_set
        has_from_path = self.from_path is not None
        if not has_set and not has_from_path:
            raise ValueError("sync effect must have either 'set' or 'from_path'")
        if has_set and has_from_path:
            raise ValueError("sync effect cannot have both 'set' and 'from_path'")
        if self.from_path is not None and not self.from_path.strip():
            raise ValueError("sync effect from_path cannot be blank when provided")
        return self


class BindingSourceSpec(BaseModel):
    """How a binding value is extracted from a tool's return type.

    source_tool can reference either a user tool or an assistant tool,
    whichever naturally provides the information in the domain.
    """

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


class BindingPredicateSpec(BaseModel):
    """Predicate over binding acquisition state."""

    binding_id: str
    acquired: bool = True

    @model_validator(mode="after")
    def validate_binding_predicate(self) -> "BindingPredicateSpec":
        if not self.binding_id.strip():
            raise ValueError("binding predicate binding_id cannot be empty")
        return self


class SyncRuleSpec(BaseModel):
    """Reactive rule that fires after init and after every action."""

    rule_id: str
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)
    effects_world: list[SyncEffectSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sync_rule(self) -> "SyncRuleSpec":
        if not self.rule_id.strip():
            raise ValueError("sync rule rule_id cannot be empty")
        if not self.effects_world:
            raise ValueError(f"Sync rule '{self.rule_id}' must have at least one effect")
        return self


class ActionContract(BaseModel):
    """One transition/action contract in depgraph v2."""

    action_id: str
    requestor: Literal["assistant", "user"]
    tool_name: str
    classification: ToolClassification
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)
    requires_bindings: list[BindingPredicateSpec] = Field(default_factory=list)
    effects_world: list[WorldEffectSpec] = Field(default_factory=list)
    effects_bindings: list[str] = Field(default_factory=list)
    tool_arg_bindings: dict[str, str] = Field(default_factory=dict)
    tool_arg_literals: dict[str, Any] = Field(default_factory=dict)
    stutter_on_fail: bool = True

    @model_validator(mode="after")
    def validate_semantics(self) -> "ActionContract":
        if not self.action_id.strip():
            raise ValueError("action_id cannot be empty")
        if not self.tool_name.strip():
            raise ValueError(f"Action '{self.action_id}' has empty tool_name")

        _check_unique(
            [predicate.binding_id for predicate in self.requires_bindings],
            label=f"action '{self.action_id}' requires_bindings",
        )
        _check_unique(
            self.effects_bindings,
            label=f"action '{self.action_id}' effects_bindings",
        )

        if self.classification == "stutter-only":
            if self.effects_world or self.effects_bindings:
                raise ValueError(
                    f"stutter-only action '{self.action_id}' cannot define world/binding effects"
                )

        required_present_bindings = {
            predicate.binding_id for predicate in self.requires_bindings if predicate.acquired
        }
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
                binding_id not in required_present_bindings
                and self.classification != "knowledge-only"
            ):
                raise ValueError(
                    f"Action '{self.action_id}' maps tool param '{param_name}' to binding "
                    f"'{binding_id}' that is not listed in requires_bindings"
                )
        overlapping_arg_keys = set(self.tool_arg_bindings) & set(self.tool_arg_literals)
        if overlapping_arg_keys:
            raise ValueError(
                f"Action '{self.action_id}' uses the same tool arg key in tool_arg_bindings "
                f"and tool_arg_literals: {sorted(overlapping_arg_keys)}"
            )
        for param_name in self.tool_arg_literals:
            if not param_name.strip():
                raise ValueError(
                    f"Action '{self.action_id}' has empty tool_arg_literals key"
                )
        return self


class ActionSchemaVariantSpec(BaseModel):
    """One enum-like variant that expands to a concrete ActionContract."""

    variant_id: str
    action_id: Optional[str] = None
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)
    requires_bindings: list[BindingPredicateSpec] = Field(default_factory=list)
    effects_world: list[WorldEffectSpec] = Field(default_factory=list)
    effects_bindings: list[str] = Field(default_factory=list)
    tool_arg_bindings: dict[str, str] = Field(default_factory=dict)
    tool_arg_literals: dict[str, Any] = Field(default_factory=dict)
    stutter_on_fail: Optional[bool] = None

    @model_validator(mode="after")
    def validate_variant(self) -> "ActionSchemaVariantSpec":
        if not self.variant_id.strip():
            raise ValueError("action schema variant_id cannot be empty")
        _check_unique(
            self.effects_bindings,
            label=f"action schema variant '{self.variant_id}' effects_bindings",
        )
        overlapping_arg_keys = set(self.tool_arg_bindings) & set(self.tool_arg_literals)
        if overlapping_arg_keys:
            raise ValueError(
                f"Action schema variant '{self.variant_id}' uses the same tool arg key in "
                f"tool_arg_bindings and tool_arg_literals: {sorted(overlapping_arg_keys)}"
            )
        return self


class ActionSchemaSpec(BaseModel):
    """Authoring sugar for one conceptual tool with multiple concrete variants."""

    schema_id: str
    action_id_template: str
    variant_param: str = "variant_id"
    requestor: Literal["assistant", "user"]
    tool_name: str
    classification: ToolClassification
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)
    requires_bindings: list[BindingPredicateSpec] = Field(default_factory=list)
    effects_world: list[WorldEffectSpec] = Field(default_factory=list)
    effects_bindings: list[str] = Field(default_factory=list)
    tool_arg_bindings: dict[str, str] = Field(default_factory=dict)
    tool_arg_literals: dict[str, Any] = Field(default_factory=dict)
    stutter_on_fail: bool = True
    variants: list[ActionSchemaVariantSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema(self) -> "ActionSchemaSpec":
        if not self.schema_id.strip():
            raise ValueError("action schema_id cannot be empty")
        if not self.action_id_template.strip():
            raise ValueError(f"Action schema '{self.schema_id}' has empty action_id_template")
        if not self.variant_param.strip():
            raise ValueError(f"Action schema '{self.schema_id}' has empty variant_param")
        if not self.tool_name.strip():
            raise ValueError(f"Action schema '{self.schema_id}' has empty tool_name")
        if not self.variants:
            raise ValueError(f"Action schema '{self.schema_id}' must declare at least one variant")
        _check_unique(
            [variant.variant_id for variant in self.variants],
            label=f"action schema '{self.schema_id}' variants.variant_id",
        )
        overlapping_arg_keys = set(self.tool_arg_bindings) & set(self.tool_arg_literals)
        if overlapping_arg_keys:
            raise ValueError(
                f"Action schema '{self.schema_id}' uses the same tool arg key in "
                f"tool_arg_bindings and tool_arg_literals: {sorted(overlapping_arg_keys)}"
            )
        return self

    def expand_actions(self) -> list[ActionContract]:
        """Expand schema variants into concrete ActionContract entries."""
        expanded: list[ActionContract] = []
        for variant in self.variants:
            substitutions = {
                "schema_id": self.schema_id,
                "variant_id": variant.variant_id,
                self.variant_param: variant.variant_id,
            }
            try:
                action_id = variant.action_id or self.action_id_template.format(**substitutions)
            except KeyError as exc:
                raise ValueError(
                    f"Action schema '{self.schema_id}' action_id_template references unknown "
                    f"placeholder '{exc.args[0]}'"
                ) from exc
            expanded.append(
                ActionContract(
                    action_id=action_id,
                    requestor=self.requestor,
                    tool_name=self.tool_name,
                    classification=self.classification,
                    requires_world=[*self.requires_world, *variant.requires_world],
                    requires_bindings=[*self.requires_bindings, *variant.requires_bindings],
                    effects_world=[*self.effects_world, *variant.effects_world],
                    effects_bindings=[*self.effects_bindings, *variant.effects_bindings],
                    tool_arg_bindings={**self.tool_arg_bindings, **variant.tool_arg_bindings},
                    tool_arg_literals={**self.tool_arg_literals, **variant.tool_arg_literals},
                    stutter_on_fail=(
                        self.stutter_on_fail
                        if variant.stutter_on_fail is None
                        else variant.stutter_on_fail
                    ),
                )
            )
        return expanded


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


class TerminalProfileSpec(BaseModel):
    """Named terminal world profile used to constrain valid task end states."""

    profile_id: str
    description: Optional[str] = None
    requires_world: list[WorldPredicateSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_profile(self) -> "TerminalProfileSpec":
        if not self.profile_id.strip():
            raise ValueError("terminal profile_id cannot be empty")
        if not self.requires_world:
            raise ValueError(
                f"terminal profile '{self.profile_id}' must declare at least one requires_world predicate"
            )
        return self


class GraphContractSpec(BaseModel):
    """Top-level depgraph v2 contract document."""

    version: int = 2
    context_slots: list[ContextSlotSpec] = Field(default_factory=list)
    projection_fields: list[str] = Field(default_factory=list)
    bindings: list[BindingSourceSpec] = Field(default_factory=list)
    actions: list[ActionContract] = Field(default_factory=list)
    action_schemas: list[ActionSchemaSpec] = Field(default_factory=list)
    sync_rules: list[SyncRuleSpec] = Field(default_factory=list)

    # Deprecated v1 fields kept only to avoid runtime import/attribute errors while
    # other modules are migrated. New authoring should not populate these.
    fact_sources: list[FactSourceSpec] = Field(default_factory=list)
    mutex_pairs: list[tuple[str, str]] = Field(default_factory=list)
    invariants: list[InvariantSpec] = Field(default_factory=list)
    assistant_stutter_allowlist: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def expand_action_schemas(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw_schemas = data.get("action_schemas") or []
        if not raw_schemas:
            return data

        expanded_actions: list[dict[str, Any]] = []
        for raw_schema in raw_schemas:
            schema = (
                raw_schema
                if isinstance(raw_schema, ActionSchemaSpec)
                else ActionSchemaSpec.model_validate(raw_schema)
            )
            expanded_actions.extend(
                action.model_dump(mode="python") for action in schema.expand_actions()
            )

        raw_actions = data.get("actions") or []
        normalized_actions: list[dict[str, Any] | ActionContract] = []
        for raw_action in raw_actions:
            if isinstance(raw_action, ActionContract):
                normalized_actions.append(raw_action.model_dump(mode="python"))
            else:
                normalized_actions.append(raw_action)

        payload = dict(data)
        payload["actions"] = [*normalized_actions, *expanded_actions]
        return payload

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
        projection_set = set(projection_paths)

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
                {predicate.binding_id for predicate in action.requires_bindings}
                | set(action.effects_bindings)
                | set(action.tool_arg_bindings.values())
            ) - binding_id_set
            if unknown_refs:
                raise ValueError(
                    f"Action '{action.action_id}' references unknown binding ids: "
                    f"{sorted(unknown_refs)}"
                )

        sync_rule_ids = [rule.rule_id for rule in self.sync_rules]
        _check_unique(sync_rule_ids, label="sync_rules.rule_id")
        for rule in self.sync_rules:
            for predicate in rule.requires_world:
                if predicate.path not in projection_set:
                    raise ValueError(
                        f"Sync rule '{rule.rule_id}' requires_world references "
                        f"unknown projection path '{predicate.path}'"
                    )
            for effect in rule.effects_world:
                if effect.path not in projection_set:
                    raise ValueError(
                        f"Sync rule '{rule.rule_id}' effect writes to "
                        f"unknown projection path '{effect.path}'"
                    )
                if effect.from_path is not None and effect.from_path not in projection_set:
                    raise ValueError(
                        f"Sync rule '{rule.rule_id}' effect copies from "
                        f"unknown projection path '{effect.from_path}'"
                    )

        return self


class TaskIntent(BaseModel):
    """Task intent used for preflight checking and optional runtime compile."""

    task_id: str
    start_world: list[WorldEffectSpec] = Field(default_factory=list)
    start_bindings: list[str] = Field(default_factory=list)
    goal_world: list[WorldPredicateSpec] = Field(default_factory=list)
    goal_capture_paths: list[str] = Field(default_factory=list)
    goal_bindings: list[str] = Field(default_factory=list)
    terminal_profile_id: Optional[str] = None
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
            self.goal_capture_paths,
            label=f"task '{self.task_id}' goal_capture_paths",
        )
        _check_unique(
            self.required_actions,
            label=f"task '{self.task_id}' required_actions",
        )
        if any(not path.strip() for path in self.goal_capture_paths):
            raise ValueError("goal_capture_paths cannot contain blank values")
        if self.min_plan_length < 0:
            raise ValueError("min_plan_length must be >= 0")
        if self.terminal_profile_id is not None and not self.terminal_profile_id.strip():
            raise ValueError("terminal_profile_id cannot be blank when provided")
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
    allowed_terminal_profiles: list[str] = Field(default_factory=list)
    goal_capture_paths: list[str] = Field(default_factory=list)
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
        _check_unique(
            self.allowed_terminal_profiles,
            label=f"seed '{self.seed_id}' allowed_terminal_profiles",
        )
        _check_unique(
            self.goal_capture_paths,
            label=f"seed '{self.seed_id}' goal_capture_paths",
        )
        if any(not path.strip() for path in self.goal_capture_paths):
            raise ValueError("goal_capture_paths cannot contain blank values")
        return self


class SeedSchemaVariantSpec(BaseModel):
    """One selectable variant inside a programmatically generated seed schema."""

    variant_id: str
    start_world: list[WorldEffectSpec] = Field(default_factory=list)
    start_bindings: list[str] = Field(default_factory=list)
    min_depth_delta: int = 0
    max_depth_delta: int = 0

    @model_validator(mode="after")
    def validate_variant(self) -> "SeedSchemaVariantSpec":
        if not self.variant_id.strip():
            raise ValueError("seed schema variant_id cannot be empty")
        _check_unique(
            self.start_bindings,
            label=f"seed schema variant '{self.variant_id}' start_bindings",
        )
        return self


class SeedSchemaDimensionSpec(BaseModel):
    """One exact-one variation axis in a generated seed schema."""

    dimension_id: str
    variants: list[SeedSchemaVariantSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimension(self) -> "SeedSchemaDimensionSpec":
        if not self.dimension_id.strip():
            raise ValueError("seed schema dimension_id cannot be empty")
        if not self.variants:
            raise ValueError(
                f"seed schema dimension '{self.dimension_id}' must declare at least one variant"
            )
        _check_unique(
            [variant.variant_id for variant in self.variants],
            label=f"seed schema dimension '{self.dimension_id}' variants.variant_id",
        )
        return self


class SeedSchemaSpec(BaseModel):
    """Authoring sugar for expanding one family of concrete start seeds."""

    schema_id: str
    seed_id_template: str
    start_world: list[WorldEffectSpec] = Field(default_factory=list)
    start_bindings: list[str] = Field(default_factory=list)
    allowed_terminal_profiles: list[str] = Field(default_factory=list)
    goal_capture_paths: list[str] = Field(default_factory=list)
    min_depth: int = 3
    max_depth: int = 8
    dimensions: list[SeedSchemaDimensionSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema(self) -> "SeedSchemaSpec":
        if not self.schema_id.strip():
            raise ValueError("seed schema_id cannot be empty")
        if not self.seed_id_template.strip():
            raise ValueError(
                f"Seed schema '{self.schema_id}' has empty seed_id_template"
            )
        if not self.allowed_terminal_profiles:
            raise ValueError(
                f"Seed schema '{self.schema_id}' must declare allowed_terminal_profiles"
            )
        if self.max_depth < self.min_depth:
            raise ValueError(
                f"Seed schema '{self.schema_id}' max_depth must be >= min_depth"
            )
        _check_unique(
            self.start_bindings,
            label=f"seed schema '{self.schema_id}' start_bindings",
        )
        _check_unique(
            self.allowed_terminal_profiles,
            label=f"seed schema '{self.schema_id}' allowed_terminal_profiles",
        )
        _check_unique(
            self.goal_capture_paths,
            label=f"seed schema '{self.schema_id}' goal_capture_paths",
        )
        if any(not path.strip() for path in self.goal_capture_paths):
            raise ValueError("goal_capture_paths cannot contain blank values")
        if not self.dimensions:
            raise ValueError(
                f"Seed schema '{self.schema_id}' must declare at least one dimension"
            )
        _check_unique(
            [dimension.dimension_id for dimension in self.dimensions],
            label=f"seed schema '{self.schema_id}' dimensions.dimension_id",
        )
        return self

    def expand_seeds(self, *, default_goal_capture_paths: list[str]) -> list[SamplingSeedSpec]:
        """Expand exact-one dimension cross-products into concrete sampling seeds."""
        from itertools import product

        capture_paths = list(self.goal_capture_paths or default_goal_capture_paths)

        def _ordered_unique(values: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for value in values:
                if value in seen:
                    continue
                seen.add(value)
                out.append(value)
            return out

        expanded: list[SamplingSeedSpec] = []
        for chosen_variants in product(*[dimension.variants for dimension in self.dimensions]):
            substitutions = {"schema_id": self.schema_id}
            substitutions.update(
                {
                    dimension.dimension_id: variant.variant_id
                    for dimension, variant in zip(self.dimensions, chosen_variants, strict=True)
                }
            )
            try:
                seed_id = self.seed_id_template.format(**substitutions)
            except KeyError as exc:
                raise ValueError(
                    f"Seed schema '{self.schema_id}' seed_id_template references unknown "
                    f"placeholder '{exc.args[0]}'"
                ) from exc

            start_world = [*self.start_world]
            start_bindings = list(self.start_bindings)
            min_depth = self.min_depth
            max_depth = self.max_depth
            for variant in chosen_variants:
                start_world.extend(variant.start_world)
                start_bindings.extend(variant.start_bindings)
                min_depth += variant.min_depth_delta
                max_depth += variant.max_depth_delta

            expanded.append(
                SamplingSeedSpec(
                    seed_id=seed_id,
                    start_world=start_world,
                    start_bindings=_ordered_unique(start_bindings),
                    allowed_terminal_profiles=list(self.allowed_terminal_profiles),
                    goal_capture_paths=capture_paths,
                    min_depth=min_depth,
                    max_depth=max_depth,
                )
            )

        return expanded


class SamplingRequestDoc(BaseModel):
    """Input document for fan-out task-intent sampling."""

    version: int = 1
    max_tasks: int = 20
    terminal_profiles: list[TerminalProfileSpec] = Field(default_factory=list)
    goal_capture_paths: list[str] = Field(default_factory=list)
    seeds: list[SamplingSeedSpec] = Field(default_factory=list)
    seed_schemas: list[SeedSchemaSpec] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def expand_seed_schemas(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("seeds"):
            raise ValueError(
                "sampling_request direct 'seeds' authoring has been removed; use "
                "'seed_schemas' to generate concrete seeds"
            )
        raw_schemas = data.get("seed_schemas") or []
        if not raw_schemas:
            return data

        default_goal_capture_paths = list(data.get("goal_capture_paths") or [])
        expanded_seeds: list[dict[str, Any]] = []
        for raw_schema in raw_schemas:
            schema = (
                raw_schema
                if isinstance(raw_schema, SeedSchemaSpec)
                else SeedSchemaSpec.model_validate(raw_schema)
            )
            expanded_seeds.extend(
                seed.model_dump(mode="python")
                for seed in schema.expand_seeds(
                    default_goal_capture_paths=default_goal_capture_paths
                )
            )

        payload = dict(data)
        payload["seeds"] = expanded_seeds
        return payload

    @model_validator(mode="after")
    def validate_sampling_request(self) -> "SamplingRequestDoc":
        if self.max_tasks <= 0:
            raise ValueError("max_tasks must be > 0")
        if not self.terminal_profiles:
            raise ValueError("sampling_request must declare at least one terminal profile")
        _check_unique(
            [profile.profile_id for profile in self.terminal_profiles],
            label="sampling_request.terminal_profiles.profile_id",
        )
        _check_unique(
            self.goal_capture_paths,
            label="sampling_request.goal_capture_paths",
        )
        if any(not path.strip() for path in self.goal_capture_paths):
            raise ValueError("goal_capture_paths cannot contain blank values")
        _check_unique(
            [seed.seed_id for seed in self.seeds],
            label="sampling_request.seeds.seed_id",
        )
        _check_unique(
            [schema.schema_id for schema in self.seed_schemas],
            label="sampling_request.seed_schemas.schema_id",
        )
        known_profiles = {profile.profile_id for profile in self.terminal_profiles}
        for seed in self.seeds:
            if not seed.allowed_terminal_profiles:
                raise ValueError(
                    f"seed '{seed.seed_id}' must declare allowed_terminal_profiles"
                )
            unknown_profiles = sorted(
                set(seed.allowed_terminal_profiles) - known_profiles
            )
            if unknown_profiles:
                raise ValueError(
                    f"seed '{seed.seed_id}' references unknown terminal profiles: {unknown_profiles}"
                )
            effective_capture_paths = seed.goal_capture_paths or self.goal_capture_paths
            if not effective_capture_paths:
                raise ValueError(
                    f"seed '{seed.seed_id}' must declare goal_capture_paths or inherit "
                    "sampling_request.goal_capture_paths"
                )
        return self

    def goal_capture_paths_for_seed(self, seed: SamplingSeedSpec) -> list[str]:
        """Return the effective goal-capture path list for one seed."""
        return list(seed.goal_capture_paths or self.goal_capture_paths)
