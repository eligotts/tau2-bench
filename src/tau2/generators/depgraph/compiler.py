"""Compile preflight-passing depgraph task intents into tau2 Task objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import json

from tau2.data_model.tasks import (
    Action,
    Description,
    EnvAssertion,
    EnvFunctionCall,
    EvaluationCriteria,
    InitialState,
    StructuredUserInstructions,
    Task,
    UserScenario,
)
from tau2.generators.depgraph.preflight import run_task_preflight
from tau2.generators.depgraph.runtime_checks import check_task_runtime_fields
from tau2.generators.depgraph.types import (
    GraphContractSpec,
    TaskIntent,
    TaskSpecsDoc,
    TerminalProfileSpec,
)


@dataclass
class CompileResult:
    """Structured result for preflight+compile stage."""

    tasks: list[Task] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors


def _compile_one(task: TaskIntent) -> Task:
    assert task.runtime is not None
    runtime = task.runtime

    goal_world_text = ", ".join(
        f"{goal.path} == {goal.value!r}" for goal in task.goal_world
    )
    ticket = runtime.ticket or (
        f"{runtime.reason_for_call}\n"
        f"Goal world: {goal_world_text or '(none)'}"
    )
    user_instructions = StructuredUserInstructions(
        domain=runtime.domain,
        reason_for_call=runtime.reason_for_call,
        known_info=runtime.known_info,
        unknown_info=runtime.unknown_info,
        task_instructions=runtime.task_instructions,
    )
    user_scenario = UserScenario(
        persona=runtime.persona,
        instructions=user_instructions,
    )

    init_actions = [
        EnvFunctionCall(
            env_type=call.env_type,
            func_name=call.func_name,
            arguments=call.arguments,
        )
        for call in runtime.initialization_actions
    ]
    env_assertions = [
        EnvAssertion(
            env_type=assertion.env_type,
            func_name=assertion.func_name,
            arguments=assertion.arguments,
            assert_value=assertion.assert_value,
            message=assertion.message,
        )
        for assertion in runtime.env_assertions
    ]
    action_assertions = [
        Action(
            action_id=action.action_id,
            requestor=action.requestor,
            name=action.name,
            arguments=action.arguments,
            compare_args=action.compare_args,
        )
        for action in runtime.actions
    ]

    evaluation = EvaluationCriteria(
        actions=action_assertions or None,
        env_assertions=env_assertions or None,
        reward_basis=runtime.reward_basis,
    )
    initial_state = InitialState(
        initialization_actions=init_actions or None,
    )
    description = Description(
        purpose=runtime.purpose,
        relevant_policies=runtime.relevant_policies,
        notes=runtime.notes,
    )

    return Task(
        id=task.task_id,
        description=description,
        user_scenario=user_scenario,
        ticket=ticket,
        initial_state=initial_state,
        evaluation_criteria=evaluation,
    )


def preflight_and_compile(
    contract: GraphContractSpec,
    task_doc: TaskSpecsDoc,
    *,
    max_depth: int | None = None,
    require_runtime: bool = True,
    terminal_profiles: list[TerminalProfileSpec] | dict[str, TerminalProfileSpec] | None = None,
    require_terminal_profile: bool = False,
    check_required_action_necessity: bool = False,
    skip_bfs: bool = False,
) -> CompileResult:
    """Run preflight checks and compile passing tasks."""
    result = CompileResult()
    effective_max_depth = max_depth
    if effective_max_depth is None:
        effective_max_depth = max(
            20,
            max((task.min_plan_length for task in task_doc.tasks), default=0),
        )
    for task in task_doc.tasks:
        if not skip_bfs:
            report = run_task_preflight(
                contract,
                task,
                max_depth=effective_max_depth,
                terminal_profiles=terminal_profiles,
                require_terminal_profile=require_terminal_profile,
                check_required_action_necessity=check_required_action_necessity,
            )
            if not report.passed:
                result.skipped.append(task.task_id)
                preflight_reason = "; ".join(report.issues) if report.issues else (
                    f"SAT_full={report.sat_full.sat}, "
                    f"required_action_checks={report.required_action_unsat}"
                )
                result.errors.append(
                    f"{task.task_id}: preflight failed - {preflight_reason}"
                )
                continue
        runtime_issues = check_task_runtime_fields(task)
        if runtime_issues:
            if require_runtime:
                result.skipped.append(task.task_id)
                result.errors.append(
                    f"{task.task_id}: runtime validation failed - "
                    + "; ".join(runtime_issues)
                )
                continue
        if task.runtime is None:
            result.skipped.append(task.task_id)
            result.errors.append(f"{task.task_id}: missing runtime payload")
            continue
        if (
            "ENV_ASSERTION" in task.runtime.reward_basis
            and len(task.runtime.env_assertions) == 0
        ):
            result.skipped.append(task.task_id)
            result.errors.append(
                f"{task.task_id}: reward_basis includes ENV_ASSERTION but runtime.env_assertions is empty"
            )
            continue
        result.tasks.append(_compile_one(task))
    return result


def dump_tasks_json(tasks: list[Task], out_path: str | Path, *, shuffle: bool = True) -> None:
    """Write compiled tasks to json file.

    Tasks are deterministically shuffled by default so that running a subset
    (e.g., first N tasks) gives good diversity across profiles and seed schemas.
    """
    import hashlib

    output_tasks = list(tasks)
    if shuffle:
        output_tasks.sort(key=lambda t: hashlib.sha256(t.id.encode()).hexdigest())

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [task.model_dump(mode="json") for task in output_tasks]
    path.write_text(json.dumps(payload, indent=2))
