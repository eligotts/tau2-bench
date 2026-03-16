"""Deterministic runtime scaffold and narrative brief generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

from tau2.generators.depgraph.context_bindings import TaskContextBindingsDoc
from tau2.generators.depgraph.goal_capture import explicit_start_world_map
from tau2.generators.depgraph.semantics import materialize_world
from tau2.generators.depgraph.stop_gate import StopGateMapDoc
from tau2.generators.depgraph.types import (
    ActionExpectationSpec,
    EnvAssertionSpec,
    EnvFunctionCallSpec,
    GraphContractSpec,
    RewardBasis,
    RuntimeTaskSpec,
    TaskIntent,
    TaskSpecsDoc,
)

_AUTHOR_PLACEHOLDER = "__AUTHOR_ME__"
_DEFAULT_TASK_INSTRUCTIONS = (
    "Follow the assistant's guidance and use tools only when asked. "
    "Base status updates on concrete tool outputs, not guesses. "
    "You will consider the issue resolved when the station can charge and the remaining "
    "resolution criteria are met. "
    "Before deciding the issue is resolved, call check_resolution_status. "
    "Only emit ###STOP### when check_resolution_status returns resolved=true. "
    "If resolved=false, report unmet items and ask for the next step."
)


class PersonaSpec(BaseModel):
    """Runtime persona entry used for deterministic assignment."""

    persona_id: str
    display_name: Optional[str] = None
    profile_text: str
    style_tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_persona(self) -> "PersonaSpec":
        if not self.persona_id.strip():
            raise ValueError("persona_id cannot be empty")
        if not self.profile_text.strip():
            raise ValueError(f"persona '{self.persona_id}' profile_text cannot be empty")
        return self


class PersonaPoolDoc(BaseModel):
    """Persona pool document."""

    version: int = 1
    personas: list[PersonaSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_doc(self) -> "PersonaPoolDoc":
        if self.version != 1:
            raise ValueError(f"Unsupported personas version: {self.version}")
        ids = [persona.persona_id for persona in self.personas]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate persona_id values")
        if len(ids) < 2:
            raise ValueError("Need at least 2 personas in personas.yaml")
        return self


class RuntimeDefaultsDoc(BaseModel):
    """Optional domain-level defaults used by runtime scaffold generation."""

    version: int = 1
    domain: Optional[str] = None
    task_instructions: Optional[str] = None
    reward_basis: list[RewardBasis] = Field(
        default_factory=lambda: ["ACTION", "ENV_ASSERTION"]
    )
    initialization_actions_prefix: list[EnvFunctionCallSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_defaults(self) -> "RuntimeDefaultsDoc":
        if self.version != 1:
            raise ValueError(f"Unsupported runtime defaults version: {self.version}")
        if not self.reward_basis:
            raise ValueError("runtime defaults reward_basis cannot be empty")
        return self


class RuntimeScaffoldResult(BaseModel):
    """Generated runtime scaffold artifacts."""

    runtime_scaffold: TaskSpecsDoc
    narrative_briefs: dict[str, Any]


def _load_yaml_dict(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text())
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML object at root for {path}")
    return payload


def load_persona_pool(path: str | Path) -> PersonaPoolDoc:
    """Load and validate personas.yaml."""
    return PersonaPoolDoc.model_validate(_load_yaml_dict(path))


def load_runtime_defaults(path: str | Path) -> RuntimeDefaultsDoc:
    """Load and validate runtime_defaults.yaml."""
    return RuntimeDefaultsDoc.model_validate(_load_yaml_dict(path))


def _start_world_map(task: TaskIntent, contract: GraphContractSpec) -> dict[str, Any]:
    world, issues = materialize_world(task.start_world, sync_rules=contract.sync_rules)
    if issues:
        raise ValueError(
            f"Task '{task.task_id}' has conflicting start_world assignments: {'; '.join(issues)}"
        )
    return world


def _goal_map_from_predicates(task: TaskIntent) -> dict[str, Any]:
    goal: dict[str, Any] = {}
    for predicate in task.goal_world:
        goal[predicate.path] = predicate.value
    return goal


def _stable_goal_key(path: str, value: Any) -> tuple[str, str]:
    if isinstance(value, (str, int, float, bool, type(None))):
        encoded = repr(value)
    else:
        encoded = json.dumps(value, sort_keys=True)
    return (path, encoded)


def _env_type_for_path(path: str) -> str:
    if path.startswith("agent."):
        return "assistant"
    if path.startswith("user."):
        return "user"
    raise ValueError(
        f"Unsupported world path prefix for '{path}'. Expected 'agent.' or 'user.'"
    )


def _leaf_field_name(path: str) -> str:
    leaf = path.split(".")[-1]
    if not leaf:
        raise ValueError(f"Cannot derive field name from path '{path}'")
    return leaf


def _assign_persona(task_id: str, personas: list[PersonaSpec]) -> PersonaSpec:
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(personas)
    return personas[idx]


def _resolve_start_binding_values(
    task: TaskIntent,
    contract: GraphContractSpec,
) -> dict[str, Any]:
    binding_by_id = {binding.binding_id: binding for binding in contract.bindings}
    start_world = _start_world_map(task, contract)

    resolved: dict[str, Any] = {}
    for binding_id in task.start_bindings:
        binding = binding_by_id.get(binding_id)
        if binding is None or binding.world_path is None:
            continue
        if binding.world_path in start_world:
            resolved[binding_id] = start_world[binding.world_path]
    return resolved


def _build_start_init_actions(
    task: TaskIntent,
    *,
    initialization_prefix: list[EnvFunctionCallSpec],
    context_initialization_actions: list[EnvFunctionCallSpec],
) -> list[EnvFunctionCallSpec]:
    actions = [call.model_copy(deep=True) for call in initialization_prefix]

    # Context bindings should deterministically override template defaults
    # for the same init callable (for example set_user_context).
    for context_call in context_initialization_actions:
        for idx, existing in enumerate(actions):
            if (
                existing.env_type == context_call.env_type
                and existing.func_name == context_call.func_name
            ):
                actions[idx] = context_call.model_copy(deep=True)
                break
        else:
            actions.append(context_call.model_copy(deep=True))

    ordered_effects = sorted(task.start_world, key=lambda effect: effect.path)
    for effect in ordered_effects:
        actions.append(
            EnvFunctionCallSpec(
                env_type=_env_type_for_path(effect.path),
                func_name=f"set_{_leaf_field_name(effect.path)}",
                arguments={"value": effect.set},
            )
        )
    return actions


def _build_goal_env_assertions(task: TaskIntent) -> list[EnvAssertionSpec]:
    assertions: list[EnvAssertionSpec] = []
    goal_by_path = {goal.path: goal for goal in task.goal_world}
    for goal in goal_by_path.values():
        if goal.op != "eq":
            raise ValueError(
                f"Task '{task.task_id}' has unsupported goal op '{goal.op}' for runtime scaffold"
            )

    # Use goal_world as the sole source of truth for assertions.
    # goal_world is the diff of start_world vs end_world under goal_capture_paths —
    # it contains only fields the plan actually changed. This avoids penalizing
    # the agent for reasonable actions beyond the minimal plan.
    assertion_values: dict[str, Any] = {}
    for path, goal in goal_by_path.items():
        assertion_values[path] = goal.value

    for path in sorted(assertion_values):
        assertions.append(
            EnvAssertionSpec(
                env_type=_env_type_for_path(path),
                func_name=f"assert_{_leaf_field_name(path)}",
                arguments={"expected": assertion_values[path]},
                assert_value=True,
                message=None,
            )
        )
    return assertions


def _build_action_expectations(
    task: TaskIntent,
    *,
    contract: GraphContractSpec,
    start_binding_values: dict[str, Any],
) -> list[ActionExpectationSpec]:
    action_by_id = {action.action_id: action for action in contract.actions}
    expectations: list[ActionExpectationSpec] = []

    for action_id in task.required_actions:
        action = action_by_id.get(action_id)
        if action is None:
            raise ValueError(
                f"Task '{task.task_id}' required action '{action_id}' is missing from graph contract"
            )

        arguments: dict[str, Any] = {}
        for param_name, literal_value in sorted(action.tool_arg_literals.items()):
            arguments[param_name] = literal_value
        for param_name, binding_id in sorted(action.tool_arg_bindings.items()):
            if binding_id in start_binding_values:
                arguments[param_name] = start_binding_values[binding_id]

        # Action checks verify the tool was called, not argument values.
        # Binding values can shift during execution (e.g. fault-code cascades),
        # so comparing args leads to false negatives.  Env assertions are the
        # correct mechanism for verifying final state.
        expectations.append(
            ActionExpectationSpec(
                action_id=action.action_id,
                requestor=action.requestor,
                name=action.tool_name,
                arguments=arguments,
                compare_args=[],
            )
        )

    return expectations


def _extract_entity_identity(
    context_initialization_actions: list[EnvFunctionCallSpec],
) -> dict[str, str]:
    """Extract entity identity fields from a set_user_context init action."""
    for call in context_initialization_actions:
        if call.func_name == "set_user_context":
            return {
                k: str(v)
                for k, v in call.arguments.items()
                if isinstance(v, (str, int, float))
            }
    return {}


def _build_persona_text(persona: PersonaSpec, entity_identity: dict[str, str]) -> str:
    """Combine entity name with persona personality.

    Persona profile_text should not contain customer names — names come from
    the entity triple assigned via context bindings.
    """
    name = entity_identity.get("name")
    if name:
        return f"Your name is {name}. {persona.profile_text}"
    return persona.profile_text


def _build_runtime_task(
    task: TaskIntent,
    *,
    domain: str,
    task_instructions: str,
    persona: PersonaSpec,
    reward_basis: list[RewardBasis],
    initialization_prefix: list[EnvFunctionCallSpec],
    context_initialization_actions: list[EnvFunctionCallSpec],
    contract: GraphContractSpec,
) -> RuntimeTaskSpec:
    binding_values = _resolve_start_binding_values(task, contract)
    entity_identity = _extract_entity_identity(context_initialization_actions)

    return RuntimeTaskSpec(
        domain=domain,
        reason_for_call=_AUTHOR_PLACEHOLDER,
        task_instructions=task_instructions,
        persona=_build_persona_text(persona, entity_identity),
        known_info=_AUTHOR_PLACEHOLDER,
        unknown_info=None,
        ticket=_AUTHOR_PLACEHOLDER,
        initialization_actions=_build_start_init_actions(
            task,
            initialization_prefix=initialization_prefix,
            context_initialization_actions=context_initialization_actions,
        ),
        env_assertions=_build_goal_env_assertions(task),
        actions=_build_action_expectations(
            task,
            contract=contract,
            start_binding_values=binding_values,
        ),
        reward_basis=reward_basis,
    )


def _goal_cues_for_task(
    task: TaskIntent,
    stop_gate_map: StopGateMapDoc | None,
) -> list[dict[str, Any]]:
    if stop_gate_map is None:
        return []

    by_goal = {
        _stable_goal_key(rule.goal_path, rule.goal_value): rule for rule in stop_gate_map.rules
    }
    cues: list[dict[str, Any]] = []
    for goal in task.goal_world:
        rule = by_goal.get(_stable_goal_key(goal.path, goal.value))
        if rule is None:
            continue
        cues.append(
            {
                "goal": f"{goal.path} == {goal.value!r}",
                "check_field": rule.check_field,
                "expected": rule.expected,
                "unmet_reason": rule.unmet_reason,
            }
        )
    return cues


def _build_narrative_brief(
    task: TaskIntent,
    *,
    contract: GraphContractSpec,
    stop_gate_map: StopGateMapDoc | None,
    entity_identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    start_world = _start_world_map(task, contract)
    goal_world = _goal_map_from_predicates(task)

    binding_by_id = {binding.binding_id: binding for binding in contract.bindings}
    start_bindings: list[dict[str, Any]] = []
    for binding_id in sorted(task.start_bindings):
        binding = binding_by_id.get(binding_id)
        if binding is None:
            start_bindings.append({"binding_id": binding_id, "value": None})
            continue
        world_path = binding.world_path
        value = start_world.get(world_path) if world_path is not None else None
        start_bindings.append(
            {
                "binding_id": binding_id,
                "world_path": world_path,
                "value": value,
            }
        )

    # Goal-binding values must be discovered mid-conversation via tool calls.
    # Collect them so the brief can warn the author and the narrative check
    # can hard-fail if they leak into authored text.
    goal_binding_do_not_disclose: list[str] = []
    for binding_id in sorted(task.goal_bindings):
        binding = binding_by_id.get(binding_id)
        if binding is None or binding.world_path is None:
            continue
        value = start_world.get(binding.world_path)
        if value is not None:
            goal_binding_do_not_disclose.append(str(value))

    return {
        "task_id": task.task_id,
        "author_surface": {
            "editable_fields": [
                "runtime.reason_for_call",
                "runtime.known_info",
                "runtime.ticket",
            ],
            "required_non_empty": True,
            "placeholder": _AUTHOR_PLACEHOLDER,
        },
        "entity_context": entity_identity or {},
        "start_state_summary": {
            "world": [f"{path} = {value!r}" for path, value in sorted(start_world.items())],
            "bindings": start_bindings,
        },
        "goal_state_summary": {
            "world": [f"{path} == {value!r}" for path, value in sorted(goal_world.items())],
            "bindings": sorted(task.goal_bindings),
        },
        "goal_binding_do_not_disclose": goal_binding_do_not_disclose,
        "required_action_chain": list(task.required_actions),
        "required_precedence": [
            {"before": before, "after": after}
            for before, after in task.required_precedence
        ],
        "completion_cues": _goal_cues_for_task(task, stop_gate_map),
        "authoring_guidance": {
            "entity_ids_are_plumbing": (
                "Entity slot IDs in entity_context (account_id, station_id, session_id) "
                "are invisible plumbing — set by initialization_actions, resolved from "
                "context by tools. They must NEVER appear in authored text. Only the "
                "customer name is user-facing. Bindings (error codes, plan names) in "
                "start_state_summary.bindings ARE user-observable and should be included."
            ),
            "reason_for_call": (
                "First person, conversational. Describe what the user is experiencing "
                "and what they want fixed. Include frustration or urgency cues. "
                "Never mention internal paths, tool names, or solution steps."
            ),
            "known_info": (
                "Second person. Start with 'You are [name]' using ONLY the name from "
                "entity_context. Add situational context the user would naturally know "
                "(location, what they observe, what they were doing). Include concrete "
                "start-binding values (e.g. error codes) when present — these are "
                "user-observable facts, not plumbing."
            ),
            "ticket": (
                "Third person, agent-facing case summary. Start with the problem, then "
                "customer name. End with 'They will consider the issue resolved when...' "
                "describing a concrete observable outcome. Read completion_cues to "
                "understand what resolved means, but write it as natural language — the "
                "ticket gives the agent direction, not a mechanical checklist. Be specific "
                "enough that the agent knows what kind of task this is."
            ),
        },
    }


def generate_runtime_scaffold(
    *,
    sampled: TaskSpecsDoc,
    contract: GraphContractSpec,
    personas: PersonaPoolDoc,
    domain: str,
    runtime_defaults: RuntimeDefaultsDoc | None = None,
    context_bindings: TaskContextBindingsDoc | None = None,
    stop_gate_map: StopGateMapDoc | None = None,
) -> RuntimeScaffoldResult:
    """Generate runtime scaffold specs and task narrative briefs."""
    defaults = runtime_defaults or RuntimeDefaultsDoc()
    if defaults.domain and defaults.domain != domain:
        raise ValueError(
            "runtime defaults domain does not match scaffold domain: "
            f"{defaults.domain!r} vs {domain!r}"
        )

    task_instructions = (defaults.task_instructions or _DEFAULT_TASK_INSTRUCTIONS).strip()
    if not task_instructions:
        raise ValueError("task instructions template cannot be empty")

    reward_basis = list(defaults.reward_basis)
    init_prefix = list(defaults.initialization_actions_prefix)
    context_by_task_id = {}
    if context_bindings is not None:
        if context_bindings.domain != domain:
            raise ValueError(
                "context bindings domain does not match scaffold domain: "
                f"{context_bindings.domain!r} vs {domain!r}"
            )
        context_by_task_id = {entry.task_id: entry for entry in context_bindings.tasks}

    runtime_tasks: list[TaskIntent] = []
    narrative_tasks: list[dict[str, Any]] = []

    for task in sampled.tasks:
        persona = _assign_persona(task.task_id, personas.personas)
        context_entry = context_by_task_id.get(task.task_id)
        context_init_actions = (
            [call.model_copy(deep=True) for call in context_entry.initialization_actions]
            if context_entry is not None
            else []
        )
        entity_identity = _extract_entity_identity(context_init_actions)
        runtime = _build_runtime_task(
            task,
            domain=domain,
            task_instructions=task_instructions,
            persona=persona,
            reward_basis=reward_basis,
            initialization_prefix=init_prefix,
            context_initialization_actions=context_init_actions,
            contract=contract,
        )

        runtime_tasks.append(
            task.model_copy(update={"runtime": runtime}, deep=True)
        )
        narrative_tasks.append(
            _build_narrative_brief(
                task,
                contract=contract,
                stop_gate_map=stop_gate_map,
                entity_identity=entity_identity,
            )
        )

    runtime_doc = TaskSpecsDoc(version=sampled.version, tasks=runtime_tasks)
    brief_doc = {
        "version": 1,
        "domain": domain,
        "source": {
            "task_specs_sampled_version": sampled.version,
            "task_count": len(sampled.tasks),
        },
        "tasks": narrative_tasks,
    }
    return RuntimeScaffoldResult(
        runtime_scaffold=runtime_doc,
        narrative_briefs=brief_doc,
    )


def write_yaml(path: str | Path, payload: Any) -> None:
    """Write YAML payload to path with stable settings."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(payload, sort_keys=False))
