import unittest

from tau2.generators.depgraph.stop_gate import (
    StopGateMapDoc,
    StopGateRule,
    inject_stop_gates,
    validate_stop_gates,
)
from tau2.generators.depgraph.types import (
    RuntimeTaskSpec,
    TaskIntent,
    TaskSpecsDoc,
    WorldPredicateSpec,
)


_STRICT_STOP_INSTRUCTIONS = (
    "Before deciding the issue is resolved, call check_resolution_status. "
    "Only emit ###STOP### when check_resolution_status returns resolved=true. "
    "If resolved=false, report unmet items and ask the assistant for the next step."
)


def _make_task(*, goal_world: list[WorldPredicateSpec]) -> TaskIntent:
    return TaskIntent(
        task_id="t1",
        start_world=[],
        goal_world=goal_world,
        required_actions=["a1"],
        min_plan_length=1,
        runtime=RuntimeTaskSpec(
            domain="test_domain",
            reason_for_call="Need help fixing the issue.",
            known_info="You are Taylor.",
            ticket="Taylor needs help fixing the issue.",
            task_instructions=_STRICT_STOP_INSTRUCTIONS,
        ),
    )


class TestStopGateSubsetMapping(unittest.TestCase):
    def test_injects_only_user_observable_goal_subset(self):
        task_doc = TaskSpecsDoc(
            tasks=[
                _make_task(
                    goal_world=[
                        WorldPredicateSpec(op="eq", path="agent.session.state", value="ready"),
                        WorldPredicateSpec(op="eq", path="user.physical.test_state", value="done"),
                    ]
                )
            ]
        )
        stop_gate_map = StopGateMapDoc(
            rules=[
                StopGateRule(
                    goal_path="agent.session.state",
                    goal_value="ready",
                    check_field="session_state",
                    expected="ready",
                    unmet_reason="Session is not ready yet.",
                )
            ]
        )

        issues = inject_stop_gates(task_doc, stop_gate_map)
        self.assertEqual(issues, [])

        gate_calls = [
            call
            for call in task_doc.tasks[0].runtime.initialization_actions
            if call.env_type == "user" and call.func_name == "set_stop_gate"
        ]
        self.assertEqual(len(gate_calls), 1)
        self.assertEqual(
            gate_calls[0].arguments["criteria"],
            [
                {
                    "check_field": "session_state",
                    "op": "eq",
                    "expected": "ready",
                    "unmet_reason": "Session is not ready yet.",
                }
            ],
        )
        self.assertEqual(validate_stop_gates(task_doc, stop_gate_map), [])

    def test_requires_at_least_one_observable_stop_gate_criterion(self):
        task_doc = TaskSpecsDoc(
            tasks=[
                _make_task(
                    goal_world=[
                        WorldPredicateSpec(op="eq", path="user.physical.test_state", value="done")
                    ]
                )
            ]
        )
        stop_gate_map = StopGateMapDoc(rules=[])

        issues = inject_stop_gates(task_doc, stop_gate_map)
        self.assertTrue(
            any("has no user-observable stop-gate criteria mapped from goal_world" in issue for issue in issues)
        )


if __name__ == "__main__":
    unittest.main()
