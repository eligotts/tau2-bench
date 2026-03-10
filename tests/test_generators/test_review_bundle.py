import unittest
from pathlib import Path

from tau2.generators.depgraph.review_bundle import (
    ReviewSourcePaths,
    build_review_bundle_markdown,
    infer_task_family,
    select_representative_tasks,
)
from tau2.generators.depgraph.types import (
    ActionContract,
    BindingPredicateSpec,
    BindingSourceSpec,
    GraphContractSpec,
    TaskIntent,
    TaskSpecsDoc,
    WorldEffectSpec,
    WorldPredicateSpec,
)


def _make_review_contract() -> GraphContractSpec:
    return GraphContractSpec(
        projection_fields=[
            "agent.iccid_value",
            "agent.profile_ready",
            "user.phone_powered_on",
        ],
        bindings=[
            BindingSourceSpec(
                binding_id="iccid",
                source_tool="get_sim_info",
                extraction_path="result.iccid",
                world_path="agent.iccid_value",
                observability_all_of=[
                    WorldPredicateSpec(op="eq", path="user.phone_powered_on", value=True),
                ],
            )
        ],
        actions=[
            ActionContract(
                action_id="power_on_phone",
                requestor="user",
                tool_name="power_on_phone",
                classification="causal",
                requires_world=[
                    WorldPredicateSpec(op="neq", path="user.phone_powered_on", value=True),
                ],
                effects_world=[
                    WorldEffectSpec(path="user.phone_powered_on", set=True),
                ],
            ),
            ActionContract(
                action_id="acquire_iccid",
                requestor="user",
                tool_name="get_sim_info",
                classification="knowledge-only",
                requires_world=[
                    WorldPredicateSpec(op="eq", path="user.phone_powered_on", value=True),
                ],
                requires_bindings=[
                    BindingPredicateSpec(binding_id="iccid", acquired=False),
                ],
                effects_bindings=["iccid"],
            ),
            ActionContract(
                action_id="refresh_iccid",
                requestor="assistant",
                tool_name="refresh_iccid",
                classification="causal",
                requires_world=[
                    WorldPredicateSpec(op="eq", path="user.phone_powered_on", value=True),
                ],
                requires_bindings=[
                    BindingPredicateSpec(binding_id="iccid", acquired=True),
                ],
                effects_world=[
                    WorldEffectSpec(path="agent.iccid_value", set="890999"),
                    WorldEffectSpec(path="agent.profile_ready", set=True),
                ],
                tool_arg_bindings={"iccid": "iccid"},
            ),
        ],
    )


class TestReviewBundle(unittest.TestCase):
    def test_infer_task_family(self):
        self.assertEqual(infer_task_family("billing_full_d12_101"), "billing_full")
        self.assertEqual(infer_task_family("custom_task"), "custom_task")

    def test_select_representative_tasks_picks_hardest_per_family(self):
        task_doc = TaskSpecsDoc(
            tasks=[
                TaskIntent(task_id="family_a_d2_001", min_plan_length=2),
                TaskIntent(task_id="family_a_d5_002", min_plan_length=5),
                TaskIntent(task_id="family_b_d1_003", min_plan_length=1),
            ]
        )

        representatives = select_representative_tasks(task_doc, samples_per_family=1)

        self.assertEqual(representatives["family_a"][0].task_id, "family_a_d5_002")
        self.assertEqual(representatives["family_b"][0].task_id, "family_b_d1_003")

    def test_build_review_bundle_includes_volatile_binding_and_plan(self):
        contract = _make_review_contract()
        task_doc = TaskSpecsDoc(
            tasks=[
                TaskIntent(
                    task_id="sim_setup_d3_001",
                    goal_world=[
                        WorldPredicateSpec(op="eq", path="agent.profile_ready", value=True),
                    ],
                    required_actions=[
                        "power_on_phone",
                        "acquire_iccid",
                        "refresh_iccid",
                    ],
                    min_plan_length=3,
                )
            ]
        )

        bundle = build_review_bundle_markdown(
            domain="sample_domain",
            contract=contract,
            task_doc=task_doc,
            source_paths=ReviewSourcePaths(graph_contract=Path(__file__).resolve()),
            samples_per_family=1,
            max_depth=8,
        )

        self.assertIn("# Depgraph Review Bundle: `sample_domain`", bundle)
        self.assertIn("`sim_setup`", bundle)
        self.assertIn("volatile=True", bundle)
        self.assertIn("refresh_iccid", bundle)
        self.assertIn("`SAT_full plan` (3): power_on_phone -> acquire_iccid -> refresh_iccid", bundle)


if __name__ == "__main__":
    unittest.main()
