import unittest

from tau2.generators.compose import compose_scenarios
from tau2.generators.types import Scenario, ScenarioGroup


def _make_scenario(name: str) -> Scenario:
    return Scenario(
        name=name,
        description=f"Scenario {name}",
        init_funcs=[lambda env: []],
        fix_funcs=[lambda env: []],
    )


class TestComposeScenarios(unittest.TestCase):
    def test_single_group(self):
        """Single group with 2 scenarios => 2 composed (each scenario alone)."""
        g = ScenarioGroup(scenarios=[_make_scenario("a"), _make_scenario("b")])
        result = compose_scenarios([g])
        self.assertEqual(len(result), 2)
        names = {r.name for r in result}
        self.assertEqual(names, {"a", "b"})

    def test_two_groups_cartesian(self):
        """Two groups with 2 scenarios each => 2*2 + 2 + 2 - 1 = 8 combos (excluding all-None)."""
        g1 = ScenarioGroup(scenarios=[_make_scenario("a"), _make_scenario("b")])
        g2 = ScenarioGroup(scenarios=[_make_scenario("x"), _make_scenario("y")])
        result = compose_scenarios([g1, g2])
        # (a+None) x (x+None) = 4, but remove all-None = 8
        # g1: a, b, None; g2: x, y, None
        # Products: (a,x), (a,y), (a,None), (b,x), (b,y), (b,None), (None,x), (None,y), (None,None)
        # Remove (None,None) => 8
        self.assertEqual(len(result), 8)

    def test_all_none_excluded_without_validator(self):
        """Without validator, all-None is excluded."""
        g = ScenarioGroup(scenarios=[_make_scenario("a")])
        result = compose_scenarios([g])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "a")

    def test_validator_filtering(self):
        """Validator can filter out unwanted combinations."""
        g1 = ScenarioGroup(scenarios=[_make_scenario("a")])
        g2 = ScenarioGroup(scenarios=[_make_scenario("x")])

        # Only allow combos where at least one is not None
        def validator(scenarios):
            non_none = [s for s in scenarios if s is not None]
            return len(non_none) >= 2  # Require both

        result = compose_scenarios([g1, g2], validator=validator)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "a|x")

    def test_composed_scenario_merges_funcs(self):
        """Composed scenario should merge init_funcs and fix_funcs from all scenarios."""
        def init_a(env):
            return []

        def init_b(env):
            return []

        def fix_a(env):
            return []

        def fix_b(env):
            return []

        s1 = Scenario(name="a", description="A", init_funcs=[init_a], fix_funcs=[fix_a])
        s2 = Scenario(name="b", description="B", init_funcs=[init_b], fix_funcs=[fix_b])
        g1 = ScenarioGroup(scenarios=[s1])
        g2 = ScenarioGroup(scenarios=[s2])
        result = compose_scenarios([g1, g2])
        combined = [r for r in result if r.name == "a|b"]
        self.assertEqual(len(combined), 1)
        cs = combined[0]
        self.assertEqual(len(cs.init_funcs), 2)
        self.assertEqual(len(cs.fix_funcs), 2)

    def test_preserves_group_order(self):
        """Scenarios within a composed scenario preserve group order."""
        g1 = ScenarioGroup(scenarios=[_make_scenario("z")])
        g2 = ScenarioGroup(scenarios=[_make_scenario("a")])
        result = compose_scenarios([g1, g2])
        combined = [r for r in result if "|" in r.name]
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0].name, "z|a")

    def test_three_groups_count(self):
        """Three groups: (3+1) x (2+1) x (2+1) - 1 = 35."""
        g1 = ScenarioGroup(scenarios=[_make_scenario("a"), _make_scenario("b"), _make_scenario("c")])
        g2 = ScenarioGroup(scenarios=[_make_scenario("x"), _make_scenario("y")])
        g3 = ScenarioGroup(scenarios=[_make_scenario("p"), _make_scenario("q")])
        result = compose_scenarios([g1, g2, g3])
        self.assertEqual(len(result), 35)


if __name__ == "__main__":
    unittest.main()
