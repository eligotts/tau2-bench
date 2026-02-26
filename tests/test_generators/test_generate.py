import unittest
from unittest.mock import MagicMock, patch

from tau2.data_model.message import ToolCall
from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall
from tau2.generators import (
    Persona,
    Scenario,
    ScenarioGroup,
    UserTemplate,
    generate_tasks,
)


def _mock_get_env():
    """Return a mock Environment that accepts any function calls."""
    env = MagicMock()
    env.run_env_function_calls = MagicMock()
    return env


def _noop_setup(env):
    return [
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_info",
            arguments={"name": "Alice Johnson", "user_id": "U001"},
        )
    ]


def _get_template_vars(env):
    return {"name": "Alice Johnson", "user_id": "U001"}


def _get_assertions(expected_success):
    if expected_success:
        return [
            EnvAssertion(
                env_type="user",
                func_name="assert_something",
                arguments={"key": "value"},
            ),
        ]
    return []


def _make_init(device_id="D001", setting="target_temp", value=55):
    def init(env):
        return [
            EnvFunctionCall(
                env_type="assistant",
                func_name="set_setting",
                arguments={"device_id": device_id, "setting_name": setting, "setting_value": value},
            ),
        ]
    return init


def _make_fix(device_id="D001", setting="target_temp", value=72):
    def fix(env):
        return [
            ToolCall(
                requestor="assistant",
                name="update_setting",
                arguments={"device_id": device_id, "setting_name": setting, "setting_value": value},
            ),
        ]
    return fix


class TestGenerateTasks(unittest.TestCase):
    def test_basic_generation(self):
        """Generate tasks from two small scenario groups and verify count and structure."""
        g1 = ScenarioGroup(
            scenarios=[
                Scenario(name="issue_a", description="Issue A", init_funcs=[_make_init()], fix_funcs=[_make_fix()]),
            ]
        )
        g2 = ScenarioGroup(
            scenarios=[
                Scenario(name="issue_b", description="Issue B", init_funcs=[_make_init("D002")], fix_funcs=[_make_fix("D002")]),
            ]
        )

        personas = [
            Persona(name="None", description=None),
            Persona(name="elderly", description="Elderly user"),
        ]

        template = UserTemplate(
            domain="test",
            reason_for_call="Test issues",
            known_info="You are {name} (user ID: {user_id}).",
            task_instructions="Follow agent instructions.",
            ticket="User {name} (ID: {user_id}) has issues.",
            purpose="Test issues.",
        )

        tasks = generate_tasks(
            groups=[g1, g2],
            get_env=_mock_get_env,
            user_template=template,
            personas=personas,
            get_env_assertions=_get_assertions,
            env_setup=_noop_setup,
            get_template_vars=_get_template_vars,
        )

        # (1+1) * (1+1) - 1 = 3 composed scenarios × 2 personas = 6
        self.assertEqual(len(tasks), 6)

        # Check task structure
        for task in tasks:
            self.assertIsNotNone(task.id)
            self.assertIn("[test]", task.id)
            self.assertIn("[PERSONA:", task.id)
            self.assertIsNotNone(task.initial_state)
            self.assertIsNotNone(task.evaluation_criteria)
            self.assertIsNotNone(task.evaluation_criteria.actions)

    def test_persona_iteration(self):
        """Each composed scenario produces one task per persona."""
        s1 = Scenario(name="s1", description="S1", init_funcs=[_make_init()], fix_funcs=[_make_fix()])
        g = ScenarioGroup(scenarios=[s1])

        personas = [
            Persona(name="A", description=None),
            Persona(name="B", description="Persona B"),
        ]

        template = UserTemplate(
            domain="test",
            reason_for_call="Test",
            known_info="{name} {user_id}",
            task_instructions="Test",
            ticket="{name} {user_id}",
            purpose="Test",
        )

        tasks = generate_tasks(
            groups=[g],
            get_env=_mock_get_env,
            user_template=template,
            personas=personas,
            get_env_assertions=_get_assertions,
            env_setup=_noop_setup,
            get_template_vars=_get_template_vars,
        )

        # 1 composed scenario × 2 personas = 2 tasks
        self.assertEqual(len(tasks), 2)
        self.assertIn("[PERSONA:A]", tasks[0].id)
        self.assertIn("[PERSONA:B]", tasks[1].id)


    def test_compare_args_on_actions(self):
        """When scenarios have compare_args_map, generated actions include compare_args."""
        compare_args_map = {
            "update_setting": ["device_id", "setting_name", "setting_value"],
            "verify_result": [],
        }

        def fix_with_verify(env):
            return [
                ToolCall(
                    requestor="assistant",
                    name="update_setting",
                    arguments={"device_id": "D001", "setting_name": "target_temp", "setting_value": 72},
                ),
                ToolCall(
                    requestor="user",
                    name="verify_result",
                    arguments={"key": "value"},
                ),
            ]

        g1 = ScenarioGroup(
            scenarios=[
                Scenario(
                    name="issue_a",
                    description="Issue A",
                    init_funcs=[_make_init()],
                    fix_funcs=[fix_with_verify],
                    compare_args_map=compare_args_map,
                ),
            ]
        )

        personas = [Persona(name="None", description=None)]
        template = UserTemplate(
            domain="test",
            reason_for_call="Test issues",
            known_info="You are {name} (user ID: {user_id}).",
            task_instructions="Follow agent instructions.",
            ticket="User {name} (ID: {user_id}) has issues.",
            purpose="Test issues.",
        )

        tasks = generate_tasks(
            groups=[g1],
            get_env=_mock_get_env,
            user_template=template,
            personas=personas,
            get_env_assertions=_get_assertions,
            env_setup=_noop_setup,
            get_template_vars=_get_template_vars,
        )

        self.assertEqual(len(tasks), 1)
        actions = tasks[0].evaluation_criteria.actions
        # update_setting should have compare_args
        update_action = [a for a in actions if a.name == "update_setting"][0]
        self.assertEqual(update_action.compare_args, ["device_id", "setting_name", "setting_value"])
        # verify_result should have compare_args = []
        verify_action = [a for a in actions if a.name == "verify_result"][0]
        self.assertEqual(verify_action.compare_args, [])

    def test_nl_assertions_in_output(self):
        """When scenarios have nl_assertions, tasks include them but NOT in reward_basis."""
        g1 = ScenarioGroup(
            scenarios=[
                Scenario(
                    name="issue_a",
                    description="Issue A",
                    init_funcs=[_make_init()],
                    fix_funcs=[_make_fix()],
                    nl_assertions=["Agent should explain the problem"],
                ),
            ]
        )

        personas = [Persona(name="None", description=None)]
        template = UserTemplate(
            domain="test",
            reason_for_call="Test issues",
            known_info="You are {name} (user ID: {user_id}).",
            task_instructions="Follow agent instructions.",
            ticket="User {name} (ID: {user_id}) has issues.",
            purpose="Test issues.",
        )

        tasks = generate_tasks(
            groups=[g1],
            get_env=_mock_get_env,
            user_template=template,
            personas=personas,
            get_env_assertions=_get_assertions,
            env_setup=_noop_setup,
            get_template_vars=_get_template_vars,
        )

        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task.evaluation_criteria.nl_assertions, ["Agent should explain the problem"])
        # nl_assertions are stored on the task but NOT in reward_basis by default
        # (requires EvaluationType.ALL_WITH_NL_ASSERTIONS to evaluate)
        reward_values = [r.value for r in task.evaluation_criteria.reward_basis]
        self.assertNotIn("NL_ASSERTION", reward_values)


if __name__ == "__main__":
    unittest.main()
