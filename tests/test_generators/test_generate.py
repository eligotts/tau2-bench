import unittest
from unittest.mock import patch

from tau2.data_model.message import ToolCall
from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall
from tau2.generators import Persona, Scenario, ScenarioGroup, UserTemplate, generate_tasks
from tau2.domains.smart_home.environment import get_environment


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
                func_name="assert_room_temp_in_range",
                arguments={"room_name": "living_room", "min_temp": 68.0, "max_temp": 76.0},
            ),
        ]
    return []


class TestGenerateTasks(unittest.TestCase):
    def test_basic_generation(self):
        """Generate tasks from two small scenario groups and verify count and structure."""

        def init_a(env):
            return [
                EnvFunctionCall(
                    env_type="assistant",
                    func_name="set_device_setting",
                    arguments={"device_id": "D001", "setting_name": "target_temp", "setting_value": 55},
                ),
                EnvFunctionCall(
                    env_type="user",
                    func_name="set_room_temperature",
                    arguments={"room_name": "living_room", "temperature": 55.0},
                ),
            ]

        def fix_a(env):
            return [
                ToolCall(
                    requestor="assistant",
                    name="update_device_setting",
                    arguments={"device_id": "D001", "setting_name": "target_temp", "setting_value": 72},
                ),
            ]

        def init_b(env):
            return [
                EnvFunctionCall(
                    env_type="assistant",
                    func_name="set_device_setting",
                    arguments={"device_id": "D002", "setting_name": "on", "setting_value": False},
                ),
                EnvFunctionCall(
                    env_type="user",
                    func_name="set_light_state",
                    arguments={"room_name": "living_room", "lights_on": False, "brightness": 0},
                ),
            ]

        def fix_b(env):
            return [
                ToolCall(
                    requestor="assistant",
                    name="update_device_setting",
                    arguments={"device_id": "D002", "setting_name": "on", "setting_value": True},
                ),
            ]

        g1 = ScenarioGroup(
            scenarios=[
                Scenario(name="temp_low", description="Temp too low", init_funcs=[init_a], fix_funcs=[fix_a]),
            ]
        )
        g2 = ScenarioGroup(
            scenarios=[
                Scenario(name="light_off", description="Light off", init_funcs=[init_b], fix_funcs=[fix_b]),
            ]
        )

        personas = [
            Persona(name="None", description=None),
            Persona(name="elderly", description="Elderly user"),
        ]

        template = UserTemplate(
            domain="smart_home",
            reason_for_call="Issues with smart home",
            known_info="You are {name} (user ID: {user_id}).",
            task_instructions="Follow agent instructions.",
            ticket="User {name} (ID: {user_id}) has issues.",
            purpose="Test smart home issues.",
        )

        tasks = generate_tasks(
            groups=[g1, g2],
            get_env=get_environment,
            user_template=template,
            personas=personas,
            get_env_assertions=_get_assertions,
            env_setup=_noop_setup,
            get_template_vars=_get_template_vars,
        )

        # (1+1) * (1+1) - 1 = 3 composed scenarios
        self.assertEqual(len(tasks), 3)

        # Check task structure
        for task in tasks:
            self.assertIsNotNone(task.id)
            self.assertIn("[smart_home]", task.id)
            self.assertIn("[PERSONA:", task.id)
            self.assertIsNotNone(task.initial_state)
            self.assertIsNotNone(task.evaluation_criteria)
            self.assertIsNotNone(task.evaluation_criteria.actions)

    def test_round_robin_personas(self):
        """Personas are assigned round-robin."""

        def init_s(env):
            return [
                EnvFunctionCall(
                    env_type="assistant",
                    func_name="set_device_setting",
                    arguments={"device_id": "D001", "setting_name": "target_temp", "setting_value": 55},
                ),
                EnvFunctionCall(
                    env_type="user",
                    func_name="set_room_temperature",
                    arguments={"room_name": "living_room", "temperature": 55.0},
                ),
            ]

        def fix_s(env):
            return [
                ToolCall(
                    requestor="assistant",
                    name="update_device_setting",
                    arguments={"device_id": "D001", "setting_name": "target_temp", "setting_value": 72},
                ),
            ]

        s1 = Scenario(name="s1", description="S1", init_funcs=[init_s], fix_funcs=[fix_s])
        s2 = Scenario(name="s2", description="S2", init_funcs=[init_s], fix_funcs=[fix_s])
        g = ScenarioGroup(scenarios=[s1, s2])

        personas = [
            Persona(name="A", description=None),
            Persona(name="B", description="Persona B"),
        ]

        template = UserTemplate(
            domain="smart_home",
            reason_for_call="Test",
            known_info="{name} {user_id}",
            task_instructions="Test",
            ticket="{name} {user_id}",
            purpose="Test",
        )

        tasks = generate_tasks(
            groups=[g],
            get_env=get_environment,
            user_template=template,
            personas=personas,
            get_env_assertions=_get_assertions,
            env_setup=_noop_setup,
            get_template_vars=_get_template_vars,
        )

        self.assertEqual(len(tasks), 2)
        self.assertIn("[PERSONA:A]", tasks[0].id)
        self.assertIn("[PERSONA:B]", tasks[1].id)


if __name__ == "__main__":
    unittest.main()
