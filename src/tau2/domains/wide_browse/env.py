"""Wide Browse environment factory with bridge-based setup and rubric.

Wires Bridge 1 (verify_start_state) into setup and
Bridge 3 (check_goal_world + data_quality_bonus) into the rubric.

Usage::

    from tau2.domains.wide_browse.env import make_wide_browse_env

    env = make_wide_browse_env(configs)
"""

from __future__ import annotations

from typing import Any, Callable

from tau2.domains.wide_browse.bridges import (
    check_goal_world,
    data_quality_bonus,
    verify_start_state,
)
from tau2.domains.wide_browse.tools import TOOL_FUNCTIONS
from tau2.generators.depgraph.verifiers_env import (
    DepgraphTaskConfig,
    DepgraphToolEnv,
)

try:
    import verifiers as vf
except ImportError:
    raise ImportError(
        "The verifiers package is required. Install it with: pip install verifiers"
    )


class WideBrowseRubric(vf.Rubric):
    """Two-function rubric: goal_world_score (0.7) + data_quality_bonus (0.3).

    Replaces the generic DepgraphRubric with bridge-aware scoring.
    """

    def __init__(
        self,
        goal_weight: float = 0.7,
        quality_weight: float = 0.3,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._goal_weight = goal_weight
        self._quality_weight = quality_weight
        self.add_reward_func(self._combined_reward)

    async def _combined_reward(self, state: vf.State, **kwargs: Any) -> float:
        config: DepgraphTaskConfig | None = state.get("task_config")
        if config is None:
            return 0.0

        db = state.get("db", {})

        # Bridge 3: goal world check
        goal_score, goal_details = check_goal_world(db, config.goal_world)
        state["goal_details"] = goal_details

        # Data quality bonus
        quality_score = data_quality_bonus(db)
        state["quality_details"] = {"score": quality_score}

        return (
            self._goal_weight * goal_score
            + self._quality_weight * quality_score
        )


class WideBrowseEnv(DepgraphToolEnv):
    """DepgraphToolEnv with Bridge 1 verification during setup."""

    async def setup_state(self, state: vf.State, **kwargs: Any) -> vf.State:
        state = await super().setup_state(state, **kwargs)

        # Bridge 1: verify start state
        config: DepgraphTaskConfig = state["task_config"]
        db: dict[str, Any] = state["db"]
        violations = verify_start_state(config.start_world, db)
        if violations:
            raise RuntimeError(
                f"Start state verification failed for {config.task_id}:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

        return state


def make_wide_browse_env(
    configs: list[DepgraphTaskConfig],
    *,
    max_turns: int = 30,
    goal_weight: float = 0.7,
    quality_weight: float = 0.3,
    **kwargs: Any,
) -> WideBrowseEnv:
    """Create a WideBrowseEnv from a list of compiled task configs.

    Parameters
    ----------
    configs:
        List of DepgraphTaskConfig objects (from compile_for_verifiers).
    max_turns:
        Maximum agent turns per episode.
    goal_weight:
        Weight for goal_world satisfaction in the rubric (default 0.7).
    quality_weight:
        Weight for data quality bonus in the rubric (default 0.3).
    """
    config_iter = iter(configs)

    def config_factory(state: vf.State) -> DepgraphTaskConfig:
        return next(config_iter)

    rubric = WideBrowseRubric(
        goal_weight=goal_weight,
        quality_weight=quality_weight,
    )

    return WideBrowseEnv(
        tool_functions=TOOL_FUNCTIONS,
        task_config_factory=config_factory,
        max_turns=max_turns,
        rubric=rubric,
        **kwargs,
    )
