"""Runtime alignment checks between depgraph contracts and tau2 environments."""

from __future__ import annotations

import inspect
import re
from enum import Enum
from typing import Any, Callable, Literal, get_args, get_origin

from pydantic import BaseModel

from tau2.environment.environment import Environment
from tau2.generators.depgraph.semantics import materialize_world
from tau2.generators.depgraph.types import GraphContractSpec, TaskIntent, TaskSpecsDoc

_EXTRACTION_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_extraction_path(path: str) -> tuple[list[str] | None, str | None]:
    """Parse a dotted extraction path and return normalized tokens."""
    raw = path.strip()
    if not raw:
        return None, "extraction_path is empty"
    if ".." in raw or raw.startswith(".") or raw.endswith("."):
        return None, "extraction_path has malformed dot segments"
    tokens = raw.split(".")
    if not tokens:
        return None, "extraction_path has no usable path tokens"
    if tokens[0] == "result":
        tokens = tokens[1:]
    if not tokens:
        return None, "extraction_path only references root 'result' without a field"
    invalid = [token for token in tokens if not _EXTRACTION_TOKEN.fullmatch(token)]
    if invalid:
        return None, f"extraction_path has invalid token(s): {invalid}"
    return tokens, None


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    args = [arg for arg in get_args(annotation) if arg is not type(None)]  # noqa: E721
    if len(args) == 1:
        return args[0]
    return annotation


def _path_exists_on_annotation(annotation: Any, tokens: list[str]) -> tuple[bool, bool]:
    """Return (known_shape, path_exists) for a dotted path on a return annotation."""
    current = _unwrap_optional(annotation)
    for token in tokens:
        if current in (inspect.Signature.empty, Any):
            return (False, False)

        origin = get_origin(current)
        if origin is not None:
            # Light validation only: if generic collections/mappings are involved,
            # treat shape as unknown and avoid false failures.
            return (False, False)

        if isinstance(current, type) and issubclass(current, BaseModel):
            field = current.model_fields.get(token)
            if field is None:
                return (True, False)
            current = _unwrap_optional(field.annotation)
            continue

        annotations = getattr(current, "__annotations__", None)
        if isinstance(annotations, dict):
            if token not in annotations:
                return (True, False)
            current = _unwrap_optional(annotations[token])
            continue

        return (False, False)

    return (True, True)


def _is_bool_like_return(annotation: Any) -> bool:
    annotation = _unwrap_optional(annotation)
    if annotation is bool:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    args = [arg for arg in get_args(annotation) if arg is not type(None)]  # noqa: E721
    return len(args) == 1 and args[0] is bool


def _finite_annotation_values(annotation: Any) -> set[Any] | None:
    """Return finite allowed values for Literal/Enum annotations, else None."""
    annotation = _unwrap_optional(annotation)
    origin = get_origin(annotation)
    if origin is not None:
        if origin is Literal:
            return set(get_args(annotation))
        return None
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return {member.value for member in annotation}
    return None


def _check_call_args(func: Callable[..., Any], args: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return issues

    params = [
        param for name, param in signature.parameters.items() if name != "self"
    ]
    has_var_kw = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params)
    named_params = {
        param.name
        for param in params
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    required = {
        param.name
        for param in params
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and param.default is inspect.Parameter.empty
    }

    provided = set(args.keys())
    if not has_var_kw:
        unknown = sorted(provided - named_params)
        if unknown:
            issues.append(f"unknown arguments {unknown}")
    missing = sorted(required - provided)
    if missing:
        issues.append(f"missing required arguments {missing}")
    return issues


def _binding_is_volatile(contract: GraphContractSpec, world_path: str | None) -> bool:
    """A binding is volatile when normal action or sync effects can rewrite its world_path."""
    if world_path is None:
        return False
    for action in contract.actions:
        for effect in action.effects_world:
            if effect.path == world_path:
                return True
    for rule in contract.sync_rules:
        for effect in rule.effects_world:
            if effect.path == world_path:
                return True
    return False


def _volatile_binding_stage_key(action: Any, world_path: str) -> tuple[str, ...]:
    """Return any explicit value-gating this action declares on a volatile binding path."""
    values = {
        repr(predicate.value)
        for predicate in action.requires_world
        if predicate.path == world_path and predicate.op == "eq"
    }
    return tuple(sorted(values))


def _actions_are_mutually_exclusive(action_a: Any, action_b: Any) -> bool:
    """Two actions are mutually exclusive when they require different eq values on the same path."""
    eq_a: dict[str, set[str]] = {}
    eq_b: dict[str, set[str]] = {}

    for predicate in action_a.requires_world:
        if predicate.op == "eq":
            eq_a.setdefault(predicate.path, set()).add(repr(predicate.value))
    for predicate in action_b.requires_world:
        if predicate.op == "eq":
            eq_b.setdefault(predicate.path, set()).add(repr(predicate.value))

    shared_paths = set(eq_a) & set(eq_b)
    for path in shared_paths:
        if eq_a[path].isdisjoint(eq_b[path]):
            return True
    return False


def _resolve_runtime_callable(
    environment: Environment,
    env_type: str,
    func_name: str,
) -> tuple[Callable[..., Any] | None, str | None]:
    if env_type == "assistant":
        toolkit = environment.tools
    elif env_type == "user":
        toolkit = environment.user_tools
    else:
        return None, f"invalid env_type '{env_type}'"
    if toolkit is None:
        return None, f"{env_type} toolkit is unavailable"
    func = getattr(toolkit, func_name, None)
    if func is None or not callable(func):
        return None, f"callable '{func_name}' not found on {env_type} toolkit"
    return func, None


def check_contract_against_environment(
    contract: GraphContractSpec,
    environment_constructor: Callable[[], Environment],
    *,
    strict_full_coverage: bool = False,
) -> list[str]:
    """Validate contract tool/binding references against a concrete tau2 environment."""
    issues: list[str] = []
    environment = environment_constructor()
    projection_set = set(contract.projection_fields)
    assistant_tools = set(environment.tools.get_tools().keys()) if environment.tools else set()
    user_tools = (
        set(environment.user_tools.get_tools().keys()) if environment.user_tools else set()
    )

    contracted_assistant_tools: set[str] = set()
    contracted_user_tools: set[str] = set()
    tool_funcs: dict[tuple[str, str], Callable[..., Any]] = {}
    for action in contract.actions:
        if action.requestor == "assistant":
            toolkit = environment.tools
        else:
            toolkit = environment.user_tools

        if action.requestor == "assistant":
            contracted_assistant_tools.add(action.tool_name)
            if action.tool_name not in assistant_tools:
                issues.append(
                    f"Action '{action.action_id}' references unknown assistant tool '{action.tool_name}'"
                )
                continue
        else:
            contracted_user_tools.add(action.tool_name)
            if action.tool_name not in user_tools:
                issues.append(
                    f"Action '{action.action_id}' references unknown user tool '{action.tool_name}'"
                )
                continue

        if toolkit is None:
            issues.append(
                f"Action '{action.action_id}' cannot be validated because "
                f"{action.requestor} toolkit is unavailable"
            )
            continue

        tool_func = getattr(toolkit, action.tool_name, None)
        if tool_func is None or not callable(tool_func):
            issues.append(
                f"Action '{action.action_id}' tool '{action.tool_name}' is not callable on "
                f"{action.requestor} toolkit"
            )
            continue
        tool_funcs[(action.requestor, action.tool_name)] = tool_func

        try:
            sig = inspect.signature(tool_func)
        except (TypeError, ValueError):
            continue
        params = [p for n, p in sig.parameters.items() if n != "self"]
        has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
        named_params = {
            p.name
            for p in params
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
        contracted_param_names = set(action.tool_arg_bindings) | set(action.tool_arg_literals)
        unknown_param_bindings = sorted(contracted_param_names - named_params)
        if unknown_param_bindings and not has_var_kw:
            issues.append(
                f"Action '{action.action_id}' maps unknown tool params: "
                f"{unknown_param_bindings}"
            )

    literal_args_by_tool: dict[tuple[str, str, str], set[Any]] = {}
    for action in contract.actions:
        for param_name, literal_value in action.tool_arg_literals.items():
            literal_args_by_tool.setdefault(
                (action.requestor, action.tool_name, param_name), set()
            ).add(literal_value)

    for (requestor, tool_name, param_name), literal_values in sorted(literal_args_by_tool.items()):
        tool_func = tool_funcs.get((requestor, tool_name))
        if tool_func is None:
            continue
        try:
            sig = inspect.signature(tool_func)
        except (TypeError, ValueError):
            continue
        param = sig.parameters.get(param_name)
        if param is None:
            continue
        allowed_values = _finite_annotation_values(param.annotation)
        if allowed_values is None:
            issues.append(
                f"Tool '{tool_name}' parameter '{param_name}' accepts finite contract literals "
                f"{sorted(literal_values, key=repr)} but is not annotated as Literal[...] or Enum."
            )
            continue
        missing_values = sorted(set(literal_values) - set(allowed_values), key=repr)
        if missing_values:
            issues.append(
                f"Tool '{tool_name}' parameter '{param_name}' annotation does not cover contract "
                f"literal values {missing_values}; allowed values are {sorted(allowed_values, key=repr)}."
            )

    for source in contract.bindings:
        all_tools = user_tools | assistant_tools
        if source.source_tool not in all_tools:
            issues.append(
                f"Binding source for '{source.binding_id}' references missing tool "
                f"'{source.source_tool}' (not found in user or assistant toolkit)"
            )
            continue
        # Look up the source function from whichever toolkit owns it
        if source.source_tool in user_tools:
            source_func = getattr(environment.user_tools, source.source_tool, None)
        else:
            source_func = getattr(environment.tools, source.source_tool, None)
        tokens, parse_error = _parse_extraction_path(source.extraction_path)
        if parse_error is not None:
            issues.append(
                f"Binding source for '{source.binding_id}' has invalid extraction_path "
                f"'{source.extraction_path}': {parse_error}"
            )
            continue
        if source_func is None:
            continue
        try:
            source_sig = inspect.signature(source_func)
        except (TypeError, ValueError):
            continue
        known_shape, path_exists = _path_exists_on_annotation(
            source_sig.return_annotation,
            tokens,
        )
        if known_shape and not path_exists:
            issues.append(
                f"Binding source for '{source.binding_id}' extraction_path "
                f"'{source.extraction_path}' does not match return schema of "
                f"tool '{source.source_tool}'"
            )

    # Check that every binding has at least one tool_arg_bindings consumer.
    # Bindings without consumers are unenforceable at runtime — requires_bindings
    # is a solver-only constraint with no runtime mechanism unless the binding
    # value flows through tool_arg_bindings into a required tool parameter.
    for source in contract.bindings:
        all_consumers = [
            action
            for action in contract.actions
            if action.classification != "knowledge-only"
            and source.binding_id in action.tool_arg_bindings.values()
        ]
        if not all_consumers:
            issues.append(
                f"Binding '{source.binding_id}' has no tool_arg_bindings consumer. "
                f"It is only used in requires_bindings, which has no runtime enforcement. "
                f"Add tool_arg_bindings on at least one downstream action so the agent "
                f"must discover the value before calling the tool."
            )

    for source in contract.bindings:
        if not _binding_is_volatile(contract, source.world_path):
            continue
        consumers = [
            action
            for action in contract.actions
            if action.classification != "knowledge-only"
            and source.binding_id in action.tool_arg_bindings.values()
        ]
        if len(consumers) <= 1:
            continue

        generic_consumers: list[str] = []
        stage_consumers: dict[tuple[str, ...], list[str]] = {}
        for action in consumers:
            stage_key = _volatile_binding_stage_key(action, source.world_path or "")
            if not stage_key:
                generic_consumers.append(action.action_id)
                continue
            stage_consumers.setdefault(stage_key, []).append(action.action_id)

        if len(generic_consumers) > 1:
            # Check if the generic consumers are all mutually exclusive
            # (e.g. triage variants that each require a different broken system).
            generic_actions = [
                action
                for action in consumers
                if action.action_id in generic_consumers
            ]
            all_mutex = all(
                _actions_are_mutually_exclusive(generic_actions[i], generic_actions[j])
                for i in range(len(generic_actions))
                for j in range(i + 1, len(generic_actions))
            )
            if not all_mutex:
                issues.append(
                    f"Volatile binding '{source.binding_id}' (world_path '{source.world_path}') "
                    f"is mapped into tool args by multiple generic actions "
                    f"{sorted(generic_consumers)}. Capture stable operational context in world "
                    f"state or make later consumers stage-specific via requires_world on "
                    f"'{source.world_path}'."
                )
        for stage_key, action_ids in sorted(stage_consumers.items()):
            stage_actions = [
                action
                for action in consumers
                if _volatile_binding_stage_key(action, source.world_path or "") == stage_key
            ]
            if len(action_ids) > 1 and not all(
                _actions_are_mutually_exclusive(stage_actions[i], stage_actions[j])
                for i in range(len(stage_actions))
                for j in range(i + 1, len(stage_actions))
            ):
                issues.append(
                    f"Volatile binding '{source.binding_id}' (world_path '{source.world_path}') "
                    f"is reused by multiple actions {sorted(action_ids)} at the same staged "
                    f"value(s) {list(stage_key)}. This is brittle: keep only one immediate "
                    f"consumer per observed stage or replace the binding with stable world state."
                )

    for rule in contract.sync_rules:
        for predicate in rule.requires_world:
            if predicate.path not in projection_set:
                issues.append(
                    f"Sync rule '{rule.rule_id}' references unknown path '{predicate.path}'"
                )
        for effect in rule.effects_world:
            if effect.path not in projection_set:
                issues.append(
                    f"Sync rule '{rule.rule_id}' writes to unknown path '{effect.path}'"
                )
            if effect.from_path is not None and effect.from_path not in projection_set:
                issues.append(
                    f"Sync rule '{rule.rule_id}' copies from unknown path '{effect.from_path}'"
                )

    if strict_full_coverage:
        # Stutter-allowlisted tools are permitted but not contracted via actions
        contracted_assistant_tools |= set(contract.assistant_stutter_allowlist or [])
        missing_assistant = sorted(assistant_tools - contracted_assistant_tools)
        if missing_assistant:
            issues.append(
                "Unclassified assistant tools (missing in action contracts): "
                + ", ".join(missing_assistant)
            )
        # Binding source_tools can be in either toolkit; only count user-side ones here
        binding_user_sources = {s.source_tool for s in contract.bindings if s.source_tool in user_tools}
        covered_user_tools = contracted_user_tools | binding_user_sources
        missing_user = sorted(user_tools - covered_user_tools)
        if missing_user:
            issues.append(
                "Unclassified user tools (missing in action contracts/binding sources): "
                + ", ".join(missing_user)
            )

    return issues


def check_policy_against_contract(
    contract: GraphContractSpec,
    policy_text: str,
) -> list[str]:
    """Validate that policy.md teaches domain reasoning without being a tool catalog.

    The policy should NOT list tool names — agent tools are injected via the API with
    docstrings, and user tools are the user's to discover. The policy should teach
    domain knowledge: principles, ordering constraints, side-effects, and resolution
    criteria.
    """
    issues: list[str] = []
    lowered = policy_text.lower()

    # Check that the policy teaches resolution semantics (stop gate discipline).
    # The policy doesn't need to name the exact tool, but it must teach the agent
    # to verify resolution and handle both met/unmet outcomes.
    has_resolution_checker = any(
        action.tool_name == "check_resolution_status" for action in contract.actions
    )
    if has_resolution_checker:
        resolution_terms = ["resolution", "resolved", "criteria", "unmet"]
        if not any(term in lowered for term in resolution_terms):
            issues.append(
                "policy.md must teach the agent about resolution checking: "
                "how to verify all criteria are met, and what to do when they are not."
            )

    return issues


def check_task_runtime_fields(task: TaskIntent) -> list[str]:
    """Validate runtime payload needed for compile step."""
    issues: list[str] = []
    if task.runtime is None:
        issues.append("Task is missing runtime block required for Task compilation")
        return issues
    instructions = task.runtime.task_instructions.strip()
    if not instructions:
        issues.append("runtime.task_instructions cannot be empty")
    if not task.runtime.reason_for_call.strip():
        issues.append("runtime.reason_for_call cannot be empty")
    lowered = instructions.lower()
    if "consider" not in lowered or "resolved when" not in lowered:
        issues.append(
            "runtime.task_instructions must include an explicit completion criterion "
            "(for example: 'You will consider the issue resolved when ...')."
        )
    if "###stop###" not in lowered:
        issues.append(
            "runtime.task_instructions must explicitly instruct the user to emit "
            "'###STOP###' when the completion criterion is met."
        )

    has_stop_gate_init = any(
        call.env_type == "user" and call.func_name == "set_stop_gate"
        for call in task.runtime.initialization_actions
    )
    if has_stop_gate_init:
        if "check_resolution_status" not in lowered:
            issues.append(
                "runtime.task_instructions must require calling "
                "'check_resolution_status' before STOP when set_stop_gate is used."
            )
        if "resolved=true" not in lowered and "resolved = true" not in lowered:
            issues.append(
                "runtime.task_instructions must explicitly gate STOP on "
                "'check_resolution_status returning resolved=true' when set_stop_gate is used."
            )
    return issues


def check_runtime_against_environment(
    task_doc: TaskSpecsDoc,
    environment_constructor: Callable[[], Environment],
) -> list[str]:
    """Validate runtime init/assert callables and argument shapes against environment."""
    issues: list[str] = []
    environment = environment_constructor()
    for task in task_doc.tasks:
        if task.runtime is None:
            continue

        for call in task.runtime.initialization_actions:
            func, error = _resolve_runtime_callable(environment, call.env_type, call.func_name)
            if error is not None:
                issues.append(
                    f"Task '{task.task_id}' initialization action '{call.func_name}' invalid: {error}"
                )
                continue
            arg_issues = _check_call_args(func, call.arguments)
            for issue in arg_issues:
                issues.append(
                    f"Task '{task.task_id}' initialization action '{call.func_name}' invalid: {issue}"
                )

        for assertion in task.runtime.env_assertions:
            func, error = _resolve_runtime_callable(
                environment,
                assertion.env_type,
                assertion.func_name,
            )
            if error is not None:
                issues.append(
                    f"Task '{task.task_id}' env assertion '{assertion.func_name}' invalid: {error}"
                )
                continue
            arg_issues = _check_call_args(func, assertion.arguments)
            for issue in arg_issues:
                issues.append(
                    f"Task '{task.task_id}' env assertion '{assertion.func_name}' invalid: {issue}"
                )
            try:
                ret_ann = inspect.signature(func).return_annotation
            except (TypeError, ValueError):
                ret_ann = inspect.Signature.empty
            if ret_ann is not inspect.Signature.empty and not _is_bool_like_return(ret_ann):
                issues.append(
                    f"Task '{task.task_id}' env assertion '{assertion.func_name}' should return bool; "
                    f"got annotated return {ret_ann}"
                )

    return issues


def check_start_bindings_visibility(
    task_doc: TaskSpecsDoc,
    contract: GraphContractSpec,
) -> list[str]:
    """Validate that start_bindings values are visible in ticket and known_info.

    When a task starts with a binding already present (start_bindings is non-empty),
    the concrete value must appear in:
    - ticket (so the agent has the information)
    - known_info (so the user sim knows it too and can discuss it naturally)
    """
    issues: list[str] = []
    binding_map = {b.binding_id: b for b in contract.bindings}

    for task in task_doc.tasks:
        if not task.start_bindings:
            continue
        if task.runtime is None:
            continue

        sw, sw_issues = materialize_world(task.start_world, sync_rules=contract.sync_rules)
        if sw_issues:
            issues.extend(
                f"Task '{task.task_id}' has invalid start_world: {issue}" for issue in sw_issues
            )
            continue

        for binding_id in task.start_bindings:
            source = binding_map.get(binding_id)
            if source is None:
                issues.append(
                    f"Task '{task.task_id}' lists start_binding '{binding_id}' "
                    f"not found in contract bindings"
                )
                continue

            if source.world_path is None:
                issues.append(
                    f"Task '{task.task_id}' has start_binding '{binding_id}' but "
                    f"binding source has no world_path — cannot resolve concrete value"
                )
                continue

            value = sw.get(source.world_path)
            if value is None:
                issues.append(
                    f"Task '{task.task_id}' has start_binding '{binding_id}' with "
                    f"world_path '{source.world_path}' but no matching entry in start_world"
                )
                continue

            value_str = str(value)
            ticket_text = task.runtime.ticket or ""
            known_info_text = task.runtime.known_info or ""

            if value_str not in ticket_text:
                issues.append(
                    f"Task '{task.task_id}' has start_binding '{binding_id}' "
                    f"with value '{value_str}' (from world_path '{source.world_path}') "
                    f"but this value does not appear in the ticket — "
                    f"the agent will not know the binding value"
                )
            if value_str not in known_info_text:
                issues.append(
                    f"Task '{task.task_id}' has start_binding '{binding_id}' "
                    f"with value '{value_str}' (from world_path '{source.world_path}') "
                    f"but this value does not appear in known_info — "
                    f"the user sim will not know the binding value"
                )

    return issues


def check_stop_gate_runtime(
    task_doc: TaskSpecsDoc,
    stop_gate_map_path: str,
) -> list[str]:
    """Validate stop-gate mapping + runtime wiring for all tasks."""
    from tau2.generators.depgraph.stop_gate import load_stop_gate_map, validate_stop_gates

    stop_gate_map = load_stop_gate_map(stop_gate_map_path)
    return validate_stop_gates(task_doc, stop_gate_map)


# ---------------------------------------------------------------------------
# Guard completeness: verify contract preconditions are sufficient for tools
# ---------------------------------------------------------------------------


def _leaf_field_name(path: str) -> str:
    """Derive a set_/assert_ method suffix from a world path.

    Mirrors the logic in runtime_scaffold._leaf_field_name so that the same
    path-to-setter mapping is used here and in task compilation.
    """
    parts = path.split(".")
    if not parts or not parts[-1]:
        raise ValueError(f"Cannot derive field name from path '{path}'")
    if len(parts) >= 3 and "[" not in path:
        return f"{parts[-2]}_{parts[-1]}"
    return parts[-1]


def _env_type_for_path(path: str) -> str:
    if path.startswith("agent."):
        return "assistant"
    if path.startswith("user."):
        return "user"
    raise ValueError(f"Unsupported world path prefix: '{path}'")


def _resolve_setter(toolkit: Any, path: str) -> tuple[Any | None, str | None]:
    """Find the set_* method for a world path, trying multiple naming conventions."""
    tried: list[str] = []
    leaf_field = _leaf_field_name(path)
    leaf_only = path.rsplit(".", 1)[-1]
    parts = path.split(".")

    # Build candidate names in priority order:
    candidates = [leaf_field]
    if leaf_only != leaf_field:
        candidates.append(leaf_only)
    # Try parent_leaf pattern: agent.auth[active_auth].cert_state → auth_cert_state
    if len(parts) >= 3:
        parent = parts[-2].split("[")[0]  # strip slot ref
        qualified = f"{parent}_{leaf_only}"
        if qualified not in candidates:
            candidates.append(qualified)

    for name in candidates:
        setter_name = f"set_{name}"
        tried.append(setter_name)
        setter = getattr(toolkit, setter_name, None)
        if setter is not None and callable(setter):
            return setter, None

    return None, f"setter not found (tried: {', '.join(tried)})"


def _apply_predicate_to_env(
    environment: Environment,
    predicate_path: str,
    predicate_value: Any,
) -> str | None:
    """Set a single world predicate on the environment via set_* helpers.

    Returns an error string if the setter is not found, else None.
    """
    env_type = _env_type_for_path(predicate_path)
    toolkit = environment.tools if env_type == "assistant" else environment.user_tools
    if toolkit is None:
        return f"{env_type} toolkit unavailable"
    setter, err = _resolve_setter(toolkit, predicate_path)
    if err is not None:
        return f"{err} on {env_type} toolkit"
    try:
        setter(str(predicate_value) if not isinstance(predicate_value, bool) else predicate_value)
    except Exception as exc:
        return f"setter raised {type(exc).__name__}: {exc}"
    return None


def _enum_values_for_path(environment: Environment, path: str) -> set[str]:
    """Extract all valid enum values for a world path by inspecting Pydantic model annotations."""
    env_type = _env_type_for_path(path)
    toolkit = environment.tools if env_type == "assistant" else environment.user_tools
    if toolkit is None or not hasattr(toolkit, "db"):
        return set()

    parts = path.split(".")
    leaf = parts[-1] if parts else ""
    if not leaf:
        return set()

    # Scan all DB sub-models for the leaf field and return its enum values.
    db_cls = type(toolkit.db)
    for field_name, fi in db_cls.model_fields.items():
        ann = fi.annotation
        ann = _unwrap_optional(ann)
        origin = get_origin(ann)
        if origin is list:
            inner_args = get_args(ann)
            if inner_args:
                ann = inner_args[0]
        if isinstance(ann, type) and hasattr(ann, "model_fields") and leaf in ann.model_fields:
            leaf_ann = ann.model_fields[leaf].annotation
            leaf_ann = _unwrap_optional(leaf_ann)
            if isinstance(leaf_ann, type) and issubclass(leaf_ann, Enum):
                return {str(m.value) for m in leaf_ann}
    return set()


def _satisfy_neq_predicate(
    environment: Environment,
    contract: GraphContractSpec,
    path: str,
    excluded_value: Any,
) -> str | None:
    """Ensure a world field does NOT equal excluded_value.

    If the default already satisfies neq, do nothing. Otherwise, find an
    alternative value from the contract's action effects and set it.
    """
    env_type = _env_type_for_path(path)
    toolkit = environment.tools if env_type == "assistant" else environment.user_tools
    if toolkit is None:
        return f"{env_type} toolkit unavailable"

    # Check current value via assert_*.
    assert_name = f"assert_{_leaf_field_name(path)}"
    asserter = getattr(toolkit, assert_name, None)
    # Fallback to leaf-only.
    if asserter is None:
        leaf_only = path.rsplit(".", 1)[-1]
        assert_name = f"assert_{leaf_only}"
        asserter = getattr(toolkit, assert_name, None)

    if asserter is not None and callable(asserter):
        try:
            is_excluded = asserter(
                str(excluded_value) if not isinstance(excluded_value, bool) else excluded_value
            )
        except Exception:
            is_excluded = False
        if not is_excluded:
            return None  # Default already satisfies neq, nothing to do.

    # Default IS the excluded value. Find an alternative from the contract.
    alternatives: set[str] = set()
    for action in contract.actions:
        for pred in action.requires_world:
            if pred.path == path and pred.op == "eq":
                alternatives.add(str(pred.value))
        for effect in action.effects_world:
            if effect.path == path:
                alternatives.add(str(effect.set))
    for rule in contract.sync_rules:
        for effect in rule.effects_world:
            if effect.path == path and effect.set is not None:
                alternatives.add(str(effect.set))

    alternatives.discard(str(excluded_value))

    # If the contract has no alternatives, try enum values from the Pydantic model field.
    if not alternatives:
        enum_values = _enum_values_for_path(environment, path)
        alternatives.update(enum_values)
        alternatives.discard(str(excluded_value))

    if not alternatives:
        return (
            f"neq predicate on '{path}' excludes default '{excluded_value}' "
            f"but no alternative value found in contract"
        )

    # Pick the first alternative alphabetically for determinism.
    alt = sorted(alternatives)[0]
    return _apply_predicate_to_env(environment, path, alt)


def check_tool_guard_completeness(
    contract: GraphContractSpec,
    environment_constructor: Callable[[], Environment],
) -> list[str]:
    """Verify that contract requires_world preconditions are sufficient for tools.

    For every causal action in the contract, this check:
    1. Creates a fresh environment (all defaults from db.json / user_db.json).
    2. Sets exactly the requires_world predicates declared in the contract.
    3. Calls the tool directly (bypassing sync_tools to avoid cascading effects).
    4. Checks whether the tool returns success.

    If the tool returns noop or error despite all declared preconditions being
    met, the tool has a guard on a field not declared in requires_world — a
    contract/tool mismatch that can produce unsolvable tasks.
    """
    issues: list[str] = []

    for action in contract.actions:
        if action.classification != "causal":
            continue

        # Build a fresh environment per action to avoid cross-contamination.
        environment = environment_constructor()

        # Apply every requires_world predicate via set_* helpers.
        setup_errors: list[str] = []
        for predicate in action.requires_world:
            if predicate.op == "eq":
                err = _apply_predicate_to_env(
                    environment, predicate.path, predicate.value,
                )
            elif predicate.op == "neq":
                # neq predicates say the field must NOT equal this value.
                # If the default already satisfies neq, leave it alone.
                # Otherwise, pick a different value from the projection
                # field's known values to satisfy the constraint.
                err = _satisfy_neq_predicate(
                    environment, contract, predicate.path, predicate.value,
                )
            else:
                continue  # gt/lt/gte/lte — skip, uncommon
            if err is not None:
                setup_errors.append(
                    f"Action '{action.action_id}': cannot set "
                    f"'{predicate.path}={predicate.value}': {err}"
                )

        if setup_errors:
            issues.extend(setup_errors)
            continue

        # Resolve the tool callable.
        if action.requestor == "assistant":
            toolkit = environment.tools
        else:
            toolkit = environment.user_tools
        if toolkit is None:
            continue
        tool_func = getattr(toolkit, action.tool_name, None)
        if tool_func is None or not callable(tool_func):
            continue  # Already caught by check_contract_against_environment

        # Build call arguments from tool_arg_literals (the only args we can
        # supply without runtime bindings). For binding-gated args, we pass
        # a placeholder string — the tool guard we care about fires BEFORE
        # parameter validation in well-structured tools.
        call_kwargs: dict[str, Any] = dict(action.tool_arg_literals)
        try:
            sig = inspect.signature(tool_func)
        except (TypeError, ValueError):
            sig = None
        if sig is not None:
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                if param_name in call_kwargs:
                    continue
                if param.default is not inspect.Parameter.empty:
                    continue  # Has a default, no need to supply
                # Required param not in literals — supply a placeholder.
                call_kwargs[param_name] = "__guard_check_placeholder__"

        # Call the tool.
        try:
            result = tool_func(**call_kwargs)
        except Exception as exc:
            issues.append(
                f"Action '{action.action_id}' tool '{action.tool_name}' raised "
                f"{type(exc).__name__} when all contract preconditions were met: {exc}"
            )
            continue

        # Interpret the result.
        if not isinstance(result, dict):
            continue  # Non-dict returns are opaque; skip.

        status = result.get("status", "")
        if status in ("noop", "error"):
            message = result.get("message", "(no message)")
            issues.append(
                f"Action '{action.action_id}' tool '{action.tool_name}' returned "
                f"{{status: {status!r}, message: {message!r}}} when all contract "
                f"preconditions ({_format_predicates(action.requires_world)}) were "
                f"satisfied. The tool has a guard on a field not declared in "
                f"requires_world — add the missing field to the contract's "
                f"requires_world and projection_fields."
            )

    return issues


def _format_predicates(predicates: list[Any]) -> str:
    """Format requires_world predicates for human-readable error messages."""
    parts = []
    for p in predicates:
        parts.append(f"{p.path}={p.value!r}")
    return ", ".join(parts) if parts else "(none)"
