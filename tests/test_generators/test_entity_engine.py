import unittest

from tau2.data_model.tasks import EnvAssertion
from tau2.generators.diversity import DiversityTracker
from tau2.generators.entity_engine import (
    GeneratedTaskSpec,
    TaskTier,
    _spec_to_task,
    generate_entity_tasks,
)
from tau2.generators.types import Persona, UserTemplate


def _make_template():
    return UserTemplate(
        domain="test_domain",
        reason_for_call="Testing",
        known_info="Test info",
        task_instructions="Follow instructions",
        ticket="Test ticket",
        purpose="Test purpose",
    )


def _make_spec(**kwargs):
    defaults = dict(
        task_id="test_task_1",
        description="Test task",
        purpose="Test purpose",
        known_info="You are user X",
        reason_for_call="Something broke",
        actions=[
            {
                "action_id": "fix_1",
                "name": "fix_thing",
                "requestor": "assistant",
                "arguments": {"id": "123"},
            }
        ],
        env_assertions=[
            EnvAssertion(
                env_type="user",
                func_name="assert_thing",
                arguments={},
                message="Thing should be fixed",
            )
        ],
        tier=TaskTier.TIER_3,
    )
    defaults.update(kwargs)
    return GeneratedTaskSpec(**defaults)


class TestTaskTier(unittest.TestCase):
    def test_tier_values(self):
        self.assertEqual(int(TaskTier.TIER_1), 1)
        self.assertEqual(int(TaskTier.TIER_5), 5)

    def test_tier_ordering(self):
        self.assertTrue(TaskTier.TIER_1 < TaskTier.TIER_5)


class TestSpecToTask(unittest.TestCase):
    def test_basic_conversion(self):
        spec = _make_spec()
        template = _make_template()
        persona = Persona(name="test_user")
        task = _spec_to_task(spec, template, persona)

        self.assertIn("[test_domain]", task.id)
        self.assertIn("test_task_1", task.id)
        self.assertIn("[PERSONA:test_user]", task.id)
        self.assertEqual(len(task.evaluation_criteria.actions), 1)
        self.assertIn("ENV_ASSERTION", [r.value for r in task.evaluation_criteria.reward_basis])
        self.assertIn("ACTION", [r.value for r in task.evaluation_criteria.reward_basis])

    def test_nl_assertions_included(self):
        spec = _make_spec(nl_assertions=["Agent should explain the issue"])
        template = _make_template()
        persona = Persona(name="test_user")
        task = _spec_to_task(spec, template, persona)

        # nl_assertions are stored on the task but NOT in reward_basis by default
        self.assertNotIn("NL_ASSERTION", [r.value for r in task.evaluation_criteria.reward_basis])
        self.assertEqual(task.evaluation_criteria.nl_assertions, ["Agent should explain the issue"])

    def test_no_actions_no_action_reward(self):
        spec = _make_spec(actions=[])
        template = _make_template()
        persona = Persona(name="test_user")
        task = _spec_to_task(spec, template, persona)

        reward_values = [r.value for r in task.evaluation_criteria.reward_basis]
        self.assertNotIn("ACTION", reward_values)

    def test_known_info_from_spec(self):
        spec = _make_spec(known_info="Exact info")
        template = _make_template()
        persona = Persona(name="test_user")
        task = _spec_to_task(spec, template, persona)
        self.assertEqual(
            task.user_scenario.instructions.known_info,
            "Exact info",
        )


class TestGenerateEntityTasks(unittest.TestCase):
    def _make_template_func(self, specs):
        """Create a template function that returns given specs."""
        def template_func(indexes, tracker):
            return specs
        return template_func

    def test_basic_generation(self):
        spec = _make_spec()
        template_func = self._make_template_func([spec])
        personas = [Persona(name="default")]
        user_template = _make_template()

        tasks = generate_entity_tasks(
            templates=[template_func],
            build_indexes=lambda db: {},
            get_env=lambda: None,
            get_db=lambda: None,
            user_template=user_template,
            personas=personas,
        )

        self.assertEqual(len(tasks), 1)
        self.assertIn("[test_domain]", tasks[0].id)

    def test_persona_iteration(self):
        """Each spec produces one task per persona."""
        spec = _make_spec()
        template_func = self._make_template_func([spec])
        personas = [
            Persona(name="friendly", description="A friendly user"),
            Persona(name="impatient", description="An impatient user"),
        ]
        user_template = _make_template()

        tasks = generate_entity_tasks(
            templates=[template_func],
            build_indexes=lambda db: {},
            get_env=lambda: None,
            get_db=lambda: None,
            user_template=user_template,
            personas=personas,
        )

        self.assertEqual(len(tasks), 2)
        self.assertIn("[PERSONA:friendly]", tasks[0].id)
        self.assertIn("[PERSONA:impatient]", tasks[1].id)

    def test_multiple_templates(self):
        spec1 = _make_spec(task_id="task_1")
        spec2 = _make_spec(task_id="task_2")
        t1 = self._make_template_func([spec1])
        t2 = self._make_template_func([spec2])
        personas = [Persona(name="default")]
        user_template = _make_template()

        tasks = generate_entity_tasks(
            templates=[t1, t2],
            build_indexes=lambda db: {},
            get_env=lambda: None,
            get_db=lambda: None,
            user_template=user_template,
            personas=personas,
        )

        self.assertEqual(len(tasks), 2)
        task_ids = [t.id for t in tasks]
        self.assertTrue(any("task_1" in tid for tid in task_ids))
        self.assertTrue(any("task_2" in tid for tid in task_ids))


if __name__ == "__main__":
    unittest.main()
