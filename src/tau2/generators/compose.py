from itertools import product
from typing import Callable, Optional

from tau2.generators.types import ComposedScenario, Scenario, ScenarioGroup


def compose_scenarios(
    groups: list[ScenarioGroup],
    validator: Optional[Callable[[list[Optional[Scenario]]], bool]] = None,
) -> list[ComposedScenario]:
    """
    Return all combinations of selecting 0 or 1 scenario from each group.
    Identical logic to telecom's compose_tasks but using generator types.
    """
    product_scenarios = list(
        product(*[group.scenarios + [None] for group in groups])
    )
    composed = []
    for scenarios in product_scenarios:
        if validator is not None:
            if not validator(scenarios):
                continue
        scenarios = [s for s in scenarios if s is not None]
        if validator is None and len(scenarios) == 0:
            continue
        init_funcs = [f for s in scenarios for f in s.init_funcs]
        fix_funcs = [f for s in scenarios for f in s.fix_funcs]
        extra_env_assertions = [f for s in scenarios for f in s.extra_env_assertions]
        composed.append(
            ComposedScenario(
                name="|".join([s.name for s in scenarios]),
                description=", ".join([s.description for s in scenarios]),
                composed_from=scenarios,
                init_funcs=init_funcs,
                fix_funcs=fix_funcs,
                extra_env_assertions=extra_env_assertions,
            )
        )
    return composed
