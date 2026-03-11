import unittest

from tau2.generators.depgraph.runtime_surface import check_runtime_author_surface
from tau2.generators.depgraph.types import EnvFunctionCallSpec, RuntimeTaskSpec, TaskIntent, TaskSpecsDoc


def _runtime(*, initialization_actions: list[EnvFunctionCallSpec]) -> RuntimeTaskSpec:
    return RuntimeTaskSpec(
        domain="test_domain",
        reason_for_call="Need help with an issue.",
        known_info="You are Taylor.",
        ticket="Taylor reports a problem and wants it fixed.",
        task_instructions="Follow the assistant's instructions and use tools only when asked.",
        initialization_actions=initialization_actions,
    )


def _task(runtime: RuntimeTaskSpec) -> TaskIntent:
    return TaskIntent(
        task_id="t1",
        start_world=[],
        goal_world=[],
        required_actions=["do_a"],
        min_plan_length=1,
        runtime=runtime,
    )


class TestRuntimeSurface(unittest.TestCase):
    def test_allows_injected_stop_gate_in_final_runtime(self):
        scaffold_doc = TaskSpecsDoc(
            tasks=[
                _task(
                    _runtime(
                        initialization_actions=[
                            EnvFunctionCallSpec(
                                env_type="user",
                                func_name="set_user_context",
                                arguments={"name": "Taylor"},
                            )
                        ]
                    )
                )
            ]
        )
        authored_doc = TaskSpecsDoc(
            tasks=[
                _task(
                    _runtime(
                        initialization_actions=[
                            EnvFunctionCallSpec(
                                env_type="user",
                                func_name="set_user_context",
                                arguments={"name": "Taylor"},
                            ),
                            EnvFunctionCallSpec(
                                env_type="user",
                                func_name="set_stop_gate",
                                arguments={
                                    "criteria": [
                                        {
                                            "check_field": "fault_code",
                                            "op": "eq",
                                            "expected": "NONE",
                                        }
                                    ]
                                },
                            ),
                        ]
                    )
                )
            ]
        )

        issues = check_runtime_author_surface(scaffold_doc, authored_doc)
        self.assertEqual(issues, [])

    def test_still_rejects_other_initialization_action_changes(self):
        scaffold_doc = TaskSpecsDoc(
            tasks=[
                _task(
                    _runtime(
                        initialization_actions=[
                            EnvFunctionCallSpec(
                                env_type="user",
                                func_name="set_user_context",
                                arguments={"name": "Taylor"},
                            )
                        ]
                    )
                )
            ]
        )
        authored_doc = TaskSpecsDoc(
            tasks=[
                _task(
                    _runtime(
                        initialization_actions=[
                            EnvFunctionCallSpec(
                                env_type="user",
                                func_name="set_user_context",
                                arguments={"name": "Taylor"},
                            ),
                            EnvFunctionCallSpec(
                                env_type="assistant",
                                func_name="set_debug_flag",
                                arguments={"value": True},
                            ),
                        ]
                    )
                )
            ]
        )

        issues = check_runtime_author_surface(scaffold_doc, authored_doc)
        self.assertTrue(any("changed disallowed runtime field 'initialization_actions'" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
