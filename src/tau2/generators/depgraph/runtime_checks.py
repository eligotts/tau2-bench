"""Runtime alignment checks between depgraph contracts and tau2 environments."""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, get_args, get_origin

from pydantic import BaseModel

from tau2.environment.environment import Environment
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
    assistant_tools = set(environment.tools.get_tools().keys()) if environment.tools else set()
    user_tools = (
        set(environment.user_tools.get_tools().keys()) if environment.user_tools else set()
    )

    contracted_assistant_tools: set[str] = set()
    contracted_user_tools: set[str] = set()
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
        unknown_param_bindings = sorted(set(action.tool_arg_bindings.keys()) - named_params)
        if unknown_param_bindings and not has_var_kw:
            issues.append(
                f"Action '{action.action_id}' maps unknown tool params in tool_arg_bindings: "
                f"{unknown_param_bindings}"
            )

    for source in contract.bindings:
        if source.source_tool not in user_tools:
            issues.append(
                f"Binding source for '{source.binding_id}' references missing user tool "
                f"'{source.source_tool}'"
            )
            continue
        source_func = getattr(environment.user_tools, source.source_tool, None)
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
                f"user tool '{source.source_tool}'"
            )

    if strict_full_coverage:
        missing_assistant = sorted(assistant_tools - contracted_assistant_tools)
        if missing_assistant:
            issues.append(
                "Unclassified assistant tools (missing in action contracts): "
                + ", ".join(missing_assistant)
            )
        covered_user_tools = contracted_user_tools | {s.source_tool for s in contract.bindings}
        missing_user = sorted(user_tools - covered_user_tools)
        if missing_user:
            issues.append(
                "Unclassified user tools (missing in action contracts/binding sources): "
                + ", ".join(missing_user)
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

        sw: dict[str, Any] = {}
        for effect in task.start_world:
            sw[effect.path] = effect.set

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
