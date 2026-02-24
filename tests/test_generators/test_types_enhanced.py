import unittest

from tau2.generators.types import (
    ComposedScenario,
    Persona,
    Scenario,
)


class TestPersonaBackwardCompat(unittest.TestCase):
    def test_persona_with_name_and_description(self):
        """Persona(name=..., description=...) works."""
        p = Persona(name="test", description="A test persona")
        self.assertEqual(p.name, "test")
        self.assertEqual(p.description, "A test persona")

    def test_persona_name_only(self):
        p = Persona(name="minimal")
        self.assertEqual(p.name, "minimal")
        self.assertIsNone(p.description)


class TestScenarioEnhanced(unittest.TestCase):
    def test_scenario_without_new_fields(self):
        """Existing Scenario creation still works without nl_assertions/compare_args_map."""
        s = Scenario(
            name="test",
            description="Test",
            init_funcs=[lambda env: []],
            fix_funcs=[lambda env: []],
        )
        self.assertEqual(s.nl_assertions, [])
        self.assertIsNone(s.compare_args_map)

    def test_scenario_with_nl_assertions(self):
        s = Scenario(
            name="test",
            description="Test",
            init_funcs=[lambda env: []],
            fix_funcs=[lambda env: []],
            nl_assertions=["Agent should escalate"],
        )
        self.assertEqual(s.nl_assertions, ["Agent should escalate"])

    def test_scenario_with_compare_args_map(self):
        cam = {"check_status": [], "update_setting": ["device_id", "value"]}
        s = Scenario(
            name="test",
            description="Test",
            init_funcs=[lambda env: []],
            fix_funcs=[lambda env: []],
            compare_args_map=cam,
        )
        self.assertEqual(s.compare_args_map, cam)


class TestComposedScenarioEnhanced(unittest.TestCase):
    def test_composed_scenario_defaults(self):
        cs = ComposedScenario(
            name="a|b",
            description="A, B",
            composed_from=[],
            init_funcs=[],
            fix_funcs=[],
        )
        self.assertEqual(cs.nl_assertions, [])
        self.assertIsNone(cs.compare_args_map)

    def test_composed_scenario_with_nl_assertions(self):
        cs = ComposedScenario(
            name="a|b",
            description="A, B",
            composed_from=[],
            init_funcs=[],
            fix_funcs=[],
            nl_assertions=["Check escalation"],
        )
        self.assertIn("Check escalation", cs.nl_assertions)

    def test_str_includes_nl_assertions(self):
        cs = ComposedScenario(
            name="test",
            description="Test",
            composed_from=[],
            init_funcs=[],
            fix_funcs=[],
            nl_assertions=["Should escalate"],
        )
        output = str(cs)
        self.assertIn("NL Assertions", output)
        self.assertIn("Should escalate", output)

    def test_str_no_nl_assertions(self):
        cs = ComposedScenario(
            name="test",
            description="Test",
            composed_from=[],
            init_funcs=[],
            fix_funcs=[],
        )
        output = str(cs)
        self.assertNotIn("NL Assertions", output)


if __name__ == "__main__":
    unittest.main()
