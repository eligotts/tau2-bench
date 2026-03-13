"""Rubric for scoring depgraph tasks in verifiers environments.

Checks goal_world predicates and goal_bindings against the DB state
at episode end. This is the verifiers equivalent of tau2's env_assertions.
"""

from __future__ import annotations

from typing import Any

try:
    import verifiers as vf
except ImportError:
    raise ImportError(
        "The verifiers package is required for the verifiers adapter. "
        "Install it with: pip install verifiers"
    )

from tau2.generators.depgraph.verifiers_env import check_goal


class DepgraphRubric(vf.Rubric):
    """Rubric that checks depgraph goal predicates against state["db"].

    Registers a single reward function that returns the fraction of
    goal predicates satisfied (0.0 to 1.0).

    Usage::

        rubric = DepgraphRubric()
        env = DepgraphToolEnv(
            tool_functions={...},
            task_config_factory=...,
            rubric=rubric,
        )
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.add_reward_func(self._goal_reward)

    async def _goal_reward(self, state: vf.State, **kwargs: Any) -> float:
        """Score the episode by checking goal predicates against the DB."""
        config = state.get("task_config")
        if config is None:
            return 0.0

        db = state.get("db", {})
        bindings = state.get("bindings", set())

        reward, details = check_goal(
            db=db,
            bindings=bindings,
            goal_world=config.goal_world,
            goal_bindings=config.goal_bindings,
        )

        # Store details in state for debugging / logging
        state["goal_details"] = details
        return reward
