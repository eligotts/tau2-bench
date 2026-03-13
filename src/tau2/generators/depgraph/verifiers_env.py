"""Verifiers StatefulToolEnv adapter for depgraph contracts.

Compiles a GraphContractSpec + TaskIntent into a verifiers StatefulToolEnv
that an agent interacts with via tool calls. The DB (world state) lives in
state["db"] and is injected into tool functions via update_tool_args.

This adapter is for **agent-only** domains — no user simulator. The agent
calls tools, tools mutate the DB, and a rubric checks goal predicates at
the end. The built-in ``no_tools_called`` stop condition from ToolEnv
terminates the episode when the agent stops calling tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from tau2.generators.depgraph.semantics import (
    materialize_world,
    predicate_holds,
)
from tau2.generators.depgraph.types import (
    GraphContractSpec,
    TaskIntent,
    WorldPredicateSpec,
)

try:
    import verifiers as vf
    from verifiers.envs.stateful_tool_env import StatefulToolEnv
except ImportError:
    raise ImportError(
        "The verifiers package is required for the verifiers adapter. "
        "Install it with: pip install verifiers"
    )


@dataclass
class DepgraphTaskConfig:
    """Everything needed to initialize one episode of a depgraph task.

    Produced by :func:`compile_task_config` from a contract + task intent.
    """

    task_id: str
    start_world: dict[str, Any]
    start_bindings: set[str]
    goal_world: list[WorldPredicateSpec]
    goal_bindings: list[str]
    system_prompt: str = ""
    task_prompt: str = ""


class DepgraphToolEnv(StatefulToolEnv):
    """Verifiers environment driven by a depgraph graph contract.

    Parameters
    ----------
    tool_functions:
        Mapping from tool name to a callable. Each callable must accept
        a ``db`` keyword argument (dict) which is the mutable world state.
        The ``db`` arg is hidden from the agent's tool schema and injected
        at call time via ``update_tool_args``.
    task_config_factory:
        A callable that takes a :class:`vf.State` and returns a
        :class:`DepgraphTaskConfig`. This is called during ``setup_state``
        to initialize the DB for the current episode. For static configs,
        wrap in a lambda: ``lambda state: my_config``.
    max_turns:
        Maximum number of agent turns before the episode is truncated.
    **kwargs:
        Passed through to ``StatefulToolEnv`` / verifiers ``Environment``.
    """

    def __init__(
        self,
        tool_functions: dict[str, Callable],
        task_config_factory: Callable[[vf.State], DepgraphTaskConfig],
        max_turns: int = 30,
        **kwargs: Any,
    ):
        # Provide sensible defaults for verifiers base class requirements.
        if "rubric" not in kwargs:
            from tau2.generators.depgraph.verifiers_rubric import DepgraphRubric

            kwargs["rubric"] = DepgraphRubric()
        if "parser" not in kwargs:
            kwargs["parser"] = vf.Parser()

        super().__init__(tools=[], max_turns=max_turns, **kwargs)

        self._task_config_factory = task_config_factory

        # Register each tool, hiding the 'db' argument from the agent.
        for _name, func in tool_functions.items():
            self.add_tool(func, args_to_skip=["db"])

    async def setup_state(self, state: vf.State, **kwargs: Any) -> vf.State:
        """Initialize the DB from the task config."""
        state = await super().setup_state(state, **kwargs)
        config = self._task_config_factory(state)
        state["task_config"] = config
        state["db"] = dict(config.start_world)
        state["bindings"] = set(config.start_bindings)
        return state

    def update_tool_args(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        messages: vf.Messages,
        state: vf.State,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Inject the DB into every tool call."""
        tool_args["db"] = state["db"]
        return tool_args


def compile_task_config(
    contract: GraphContractSpec,
    task: TaskIntent,
    *,
    system_prompt: str = "",
    task_prompt: str = "",
) -> DepgraphTaskConfig:
    """Compile a graph contract + task intent into a DepgraphTaskConfig.

    This is the verifiers equivalent of the tau2 compiler — it takes the
    same inputs (contract + task intent) and produces the config needed
    to run one episode in a DepgraphToolEnv.

    Parameters
    ----------
    contract:
        The graph contract (used only to run sync rules during world
        materialization).
    task:
        The task intent with start_world, goal_world, etc.
    system_prompt:
        Optional system prompt prepended to the agent's context.
    task_prompt:
        The natural-language task description shown to the agent.
    """
    start_world, issues = materialize_world(
        task.start_world,
        sync_rules=contract.sync_rules,
    )
    if issues:
        raise ValueError(
            f"Task '{task.task_id}' has conflicting start_world: {'; '.join(issues)}"
        )

    return DepgraphTaskConfig(
        task_id=task.task_id,
        start_world=start_world,
        start_bindings=set(task.start_bindings),
        goal_world=list(task.goal_world),
        goal_bindings=list(task.goal_bindings),
        system_prompt=system_prompt,
        task_prompt=task_prompt,
    )


def check_goal(
    db: dict[str, Any],
    bindings: set[str],
    goal_world: list[WorldPredicateSpec],
    goal_bindings: list[str],
) -> tuple[float, dict[str, Any]]:
    """Check goal predicates against current DB state.

    Returns (reward, details) where reward is the fraction of satisfied
    predicates and details maps each predicate to pass/fail.
    """
    total = len(goal_world) + len(goal_bindings)
    if total == 0:
        return 1.0, {}

    passed = 0
    details: dict[str, Any] = {}

    for pred in goal_world:
        key = f"{pred.path} {pred.op} {pred.value!r}"
        ok = predicate_holds(pred, db)
        details[key] = ok
        if ok:
            passed += 1

    for binding_id in goal_bindings:
        key = f"binding:{binding_id}"
        ok = binding_id in bindings
        details[key] = ok
        if ok:
            passed += 1

    return passed / total, details
