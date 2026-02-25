import unittest

from tau2.generators.compose import compose_scenarios
from tau2.generators.types import Scenario, ScenarioGroup


def _make_scenario(name: str, **kwargs) -> Scenario:
    return Scenario(
        name=name,
        description=f"Scenario {name}",
        init_funcs=[lambda env: []],
        fix_funcs=[lambda env: []],
        **kwargs,
    )


class TestComposeNlAssertions(unittest.TestCase):
    def test_merges_nl_assertions(self):
        """nl_assertions from multiple scenarios are concatenated."""
        s1 = _make_scenario("a", nl_assertions=["Assert A1", "Assert A2"])
        s2 = _make_scenario("b", nl_assertions=["Assert B1"])
        g1 = ScenarioGroup(scenarios=[s1])
        g2 = ScenarioGroup(scenarios=[s2])
        result = compose_scenarios([g1, g2])

        combined = [r for r in result if r.name == "a|b"]
        self.assertEqual(len(combined), 1)
        cs = combined[0]
        self.assertEqual(cs.nl_assertions, ["Assert A1", "Assert A2", "Assert B1"])

    def test_empty_nl_assertions_stay_empty(self):
        """Scenarios without nl_assertions produce empty list."""
        s1 = _make_scenario("a")
        s2 = _make_scenario("b")
        g1 = ScenarioGroup(scenarios=[s1])
        g2 = ScenarioGroup(scenarios=[s2])
        result = compose_scenarios([g1, g2])

        combined = [r for r in result if r.name == "a|b"]
        self.assertEqual(combined[0].nl_assertions, [])

    def test_single_scenario_nl_assertions(self):
        """Single scenario's nl_assertions are preserved."""
        s1 = _make_scenario("a", nl_assertions=["Check A"])
        g1 = ScenarioGroup(scenarios=[s1])
        result = compose_scenarios([g1])
        self.assertEqual(result[0].nl_assertions, ["Check A"])


class TestComposeCompareArgsMap(unittest.TestCase):
    def test_merges_compare_args_map(self):
        """compare_args_map from multiple scenarios are merged (later wins)."""
        s1 = _make_scenario("a", compare_args_map={"tool_x": ["arg1"], "tool_y": []})
        s2 = _make_scenario("b", compare_args_map={"tool_y": ["arg2"], "tool_z": None})
        g1 = ScenarioGroup(scenarios=[s1])
        g2 = ScenarioGroup(scenarios=[s2])
        result = compose_scenarios([g1, g2])

        combined = [r for r in result if r.name == "a|b"]
        self.assertEqual(len(combined), 1)
        cam = combined[0].compare_args_map
        self.assertIsNotNone(cam)
        self.assertEqual(cam["tool_x"], ["arg1"])  # from s1
        self.assertEqual(cam["tool_y"], ["arg2"])  # s2 wins
        self.assertIsNone(cam["tool_z"])  # from s2

    def test_none_compare_args_map_stays_none(self):
        """When no scenario has compare_args_map, result is None."""
        s1 = _make_scenario("a")
        s2 = _make_scenario("b")
        g1 = ScenarioGroup(scenarios=[s1])
        g2 = ScenarioGroup(scenarios=[s2])
        result = compose_scenarios([g1, g2])
        combined = [r for r in result if r.name == "a|b"]
        self.assertIsNone(combined[0].compare_args_map)

    def test_partial_compare_args_map(self):
        """Only one scenario has compare_args_map."""
        s1 = _make_scenario("a", compare_args_map={"tool_x": ["arg1"]})
        s2 = _make_scenario("b")  # No compare_args_map
        g1 = ScenarioGroup(scenarios=[s1])
        g2 = ScenarioGroup(scenarios=[s2])
        result = compose_scenarios([g1, g2])
        combined = [r for r in result if r.name == "a|b"]
        self.assertEqual(combined[0].compare_args_map, {"tool_x": ["arg1"]})

    def test_single_scenario_compare_args_map(self):
        """Single scenario preserves compare_args_map in composed result."""
        s1 = _make_scenario("a", compare_args_map={"tool_x": []})
        g1 = ScenarioGroup(scenarios=[s1])
        result = compose_scenarios([g1])
        self.assertEqual(result[0].compare_args_map, {"tool_x": []})


if __name__ == "__main__":
    unittest.main()
