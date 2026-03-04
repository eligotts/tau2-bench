import unittest

from tau2.generators.depgraph.compiler import preflight_and_compile
from tau2.generators.depgraph.preflight import run_task_preflight
from tau2.generators.depgraph.runtime_checks import (
    check_contract_against_environment,
    check_runtime_against_environment,
    check_start_bindings_visibility,
)
from tau2.generators.depgraph.sampler import sample_task_intents
from tau2.generators.depgraph.types import (
    ActionContract,
    BindingSourceSpec,
    EnvAssertionSpec,
    EnvFunctionCallSpec,
    GraphContractSpec,
    RuntimeTaskSpec,
    SamplingRequestDoc,
    SamplingSeedSpec,
    TaskIntent,
    TaskSpecsDoc,
    WorldEffectSpec,
    WorldPredicateSpec,
)


def _make_chain_contract():
    """Telecom-like chain: power_on -> acquire_iccid -> restart -> reprovision -> run_data_test."""
    return GraphContractSpec(
        projection_fields=[
            "agent.line_exists",
            "user.phone_powered_on",
            "user.phone_restarted",
            "agent.profile_ready",
            "agent.data_active",
        ],
        bindings=[
            BindingSourceSpec(
                binding_id="iccid",
                source_tool="get_sim_info",
                extraction_path="result.iccid",
                world_path="agent.iccid_value",
                observability_all_of=[
                    WorldPredicateSpec(op="eq", path="agent.line_exists", value=True),
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
                requires_world=[],
                requires_absent_world=[
                    WorldPredicateSpec(op="eq", path="user.phone_powered_on", value=True),
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
                    WorldPredicateSpec(op="eq", path="agent.line_exists", value=True),
                    WorldPredicateSpec(op="eq", path="user.phone_powered_on", value=True),
                ],
                requires_absent_bindings=["iccid"],
                effects_bindings=["iccid"],
            ),
            ActionContract(
                action_id="restart_phone",
                requestor="user",
                tool_name="restart_phone",
                classification="causal",
                requires_absent_world=[
                    WorldPredicateSpec(op="eq", path="user.phone_restarted", value=True),
                ],
                effects_world=[
                    WorldEffectSpec(path="user.phone_restarted", set=True),
                ],
            ),
            ActionContract(
                action_id="reprovision",
                requestor="assistant",
                tool_name="reprovision_esim",
                classification="causal",
                requires_world=[
                    WorldPredicateSpec(op="eq", path="user.phone_restarted", value=True),
                ],
                requires_bindings=["iccid"],
                effects_world=[
                    WorldEffectSpec(path="agent.profile_ready", set=True),
                ],
                tool_arg_bindings={"iccid": "iccid"},
            ),
            ActionContract(
                action_id="run_data_test",
                requestor="user",
                tool_name="run_data_test",
                classification="causal",
                requires_world=[
                    WorldPredicateSpec(op="eq", path="agent.profile_ready", value=True),
                ],
                requires_absent_world=[
                    WorldPredicateSpec(op="eq", path="agent.data_active", value=True),
                ],
                effects_world=[
                    WorldEffectSpec(path="agent.data_active", set=True),
                ],
            ),
        ],
    )


def _make_simple_contract():
    """Minimal two-step chain: a -> b."""
    return GraphContractSpec(
        projection_fields=["agent.a", "agent.b"],
        actions=[
            ActionContract(
                action_id="do_a",
                requestor="assistant",
                tool_name="tool_a",
                classification="causal",
                requires_absent_world=[
                    WorldPredicateSpec(op="eq", path="agent.a", value=True),
                ],
                effects_world=[WorldEffectSpec(path="agent.a", set=True)],
            ),
            ActionContract(
                action_id="do_b",
                requestor="assistant",
                tool_name="tool_b",
                classification="causal",
                requires_world=[
                    WorldPredicateSpec(op="eq", path="agent.a", value=True),
                ],
                requires_absent_world=[
                    WorldPredicateSpec(op="eq", path="agent.b", value=True),
                ],
                effects_world=[WorldEffectSpec(path="agent.b", set=True)],
            ),
        ],
    )


_VALID_TASK_INSTRUCTIONS = (
    "You will consider the issue resolved when the data connection is active. "
    "When that condition is met, reply with ###STOP###. "
    "Before deciding the issue is resolved, call check_resolution_status. "
    "Only emit ###STOP### when check_resolution_status returns resolved=true. "
    "If resolved=false, report unmet items and ask for the next step."
)


class TestDepgraphPreflight(unittest.TestCase):
    def test_simple_chain_is_sat(self):
        contract = _make_simple_contract()
        task = TaskIntent(
            task_id="chain",
            start_world=[],
            goal_world=[WorldPredicateSpec(op="eq", path="agent.b", value=True)],
            required_actions=["do_a", "do_b"],
            min_plan_length=2,
        )
        report = run_task_preflight(contract, task, max_depth=5)
        self.assertTrue(report.passed)
        self.assertTrue(report.sat_full.sat)
        self.assertEqual(len(report.sat_full.plan), 2)

    def test_missing_action_is_unsat(self):
        contract = GraphContractSpec(
            projection_fields=["agent.a", "agent.b"],
            actions=[
                ActionContract(
                    action_id="do_a",
                    requestor="assistant",
                    tool_name="tool_a",
                    classification="causal",
                    effects_world=[WorldEffectSpec(path="agent.a", set=True)],
                ),
            ],
        )
        task = TaskIntent(
            task_id="missing",
            start_world=[],
            goal_world=[WorldPredicateSpec(op="eq", path="agent.b", value=True)],
            required_actions=["do_a"],
        )
        report = run_task_preflight(contract, task, max_depth=3)
        self.assertFalse(report.passed)
        self.assertFalse(report.sat_full.sat)

    def test_trivial_goal_already_met(self):
        contract = _make_simple_contract()
        task = TaskIntent(
            task_id="trivial",
            start_world=[WorldEffectSpec(path="agent.b", set=True)],
            goal_world=[WorldPredicateSpec(op="eq", path="agent.b", value=True)],
            min_plan_length=0,
        )
        report = run_task_preflight(contract, task, max_depth=3)
        self.assertTrue(report.passed)
        self.assertTrue(report.sat_full.sat)
        self.assertEqual(report.sat_full.plan, [])

    def test_knowledge_gate_and_chain_pass(self):
        contract = _make_chain_contract()
        task = TaskIntent(
            task_id="telecom_chain",
            start_world=[
                WorldEffectSpec(path="agent.line_exists", set=True),
            ],
            goal_world=[
                WorldPredicateSpec(op="eq", path="agent.data_active", value=True),
            ],
            goal_bindings=["iccid"],
            required_actions=[
                "power_on_phone",
                "acquire_iccid",
                "restart_phone",
                "reprovision",
                "run_data_test",
            ],
            required_precedence=[
                ("power_on_phone", "acquire_iccid"),
                ("acquire_iccid", "reprovision"),
                ("restart_phone", "reprovision"),
                ("reprovision", "run_data_test"),
            ],
            min_plan_length=5,
        )
        report = run_task_preflight(contract, task, max_depth=10)
        self.assertTrue(report.passed)
        self.assertTrue(report.sat_full.sat)
        self.assertEqual(len(report.sat_full.plan), 5)

    def test_knowledge_source_unsatisfied_is_unsat(self):
        """Binding requires phone_powered_on for observability, but no action produces it."""
        contract = GraphContractSpec(
            projection_fields=[
                "agent.line_exists",
                "agent.profile_ready",
            ],
            bindings=[
                BindingSourceSpec(
                    binding_id="iccid",
                    source_tool="get_sim_info",
                    extraction_path="result.iccid",
                    observability_all_of=[
                        WorldPredicateSpec(op="eq", path="user.phone_powered_on", value=True),
                    ],
                )
            ],
            actions=[
                ActionContract(
                    action_id="acquire_iccid",
                    requestor="user",
                    tool_name="get_sim_info",
                    classification="knowledge-only",
                    requires_world=[
                        WorldPredicateSpec(op="eq", path="agent.line_exists", value=True),
                        WorldPredicateSpec(op="eq", path="user.phone_powered_on", value=True),
                    ],
                    requires_absent_bindings=["iccid"],
                    effects_bindings=["iccid"],
                ),
                ActionContract(
                    action_id="reprovision",
                    requestor="assistant",
                    tool_name="reprovision_esim",
                    classification="causal",
                    requires_bindings=["iccid"],
                    effects_world=[
                        WorldEffectSpec(path="agent.profile_ready", set=True),
                    ],
                    tool_arg_bindings={"iccid": "iccid"},
                ),
            ],
        )
        task = TaskIntent(
            task_id="missing_observability",
            start_world=[
                WorldEffectSpec(path="agent.line_exists", set=True),
            ],
            goal_world=[
                WorldPredicateSpec(op="eq", path="agent.profile_ready", value=True),
            ],
            required_actions=["acquire_iccid", "reprovision"],
        )
        report = run_task_preflight(contract, task, max_depth=4)
        self.assertFalse(report.passed)
        self.assertFalse(report.sat_full.sat)

    def test_goal_contradiction_fails(self):
        """Same goal path with two different target values is a contradiction."""
        contract = _make_simple_contract()
        task = TaskIntent(
            task_id="bad_goal",
            start_world=[],
            goal_world=[
                WorldPredicateSpec(op="eq", path="agent.a", value=True),
                WorldPredicateSpec(op="eq", path="agent.a", value=False),
            ],
        )
        report = run_task_preflight(contract, task, max_depth=2)
        self.assertFalse(report.passed)
        self.assertTrue(any("Goal contradiction" in issue for issue in report.issues))


class TestDepgraphSampler(unittest.TestCase):
    def test_sampler_emits_chain_tasks(self):
        contract = GraphContractSpec(
            projection_fields=["agent.f0", "agent.f1", "agent.f2", "agent.f3"],
            actions=[
                ActionContract(
                    action_id="a1",
                    requestor="assistant",
                    tool_name="tool_a1",
                    classification="causal",
                    requires_world=[
                        WorldPredicateSpec(op="eq", path="agent.f0", value=True),
                    ],
                    requires_absent_world=[
                        WorldPredicateSpec(op="eq", path="agent.f1", value=True),
                    ],
                    effects_world=[WorldEffectSpec(path="agent.f1", set=True)],
                ),
                ActionContract(
                    action_id="a2",
                    requestor="assistant",
                    tool_name="tool_a2",
                    classification="causal",
                    requires_world=[
                        WorldPredicateSpec(op="eq", path="agent.f1", value=True),
                    ],
                    requires_absent_world=[
                        WorldPredicateSpec(op="eq", path="agent.f2", value=True),
                    ],
                    effects_world=[WorldEffectSpec(path="agent.f2", set=True)],
                ),
                ActionContract(
                    action_id="a3",
                    requestor="assistant",
                    tool_name="tool_a3",
                    classification="causal",
                    requires_world=[
                        WorldPredicateSpec(op="eq", path="agent.f2", value=True),
                    ],
                    requires_absent_world=[
                        WorldPredicateSpec(op="eq", path="agent.f3", value=True),
                    ],
                    effects_world=[WorldEffectSpec(path="agent.f3", set=True)],
                ),
            ],
        )
        request = SamplingRequestDoc(
            max_tasks=5,
            goal_world_path_prefixes=["agent."],
            seeds=[
                SamplingSeedSpec(
                    seed_id="seed",
                    start_world=[WorldEffectSpec(path="agent.f0", set=True)],
                    min_depth=3,
                    max_depth=3,
                )
            ],
        )
        sampled = sample_task_intents(contract, request)
        self.assertGreaterEqual(len(sampled), 1)
        self.assertEqual(sampled[0].task.min_plan_length, 3)
        self.assertEqual(
            sampled[0].task.required_precedence, [("a1", "a2"), ("a2", "a3")]
        )

    def test_sampler_propagates_start_bindings(self):
        contract = _make_chain_contract()
        request = SamplingRequestDoc(
            max_tasks=5,
            goal_world_path_prefixes=["agent."],
            seeds=[
                SamplingSeedSpec(
                    seed_id="with_binding",
                    start_world=[
                        WorldEffectSpec(path="agent.line_exists", set=True),
                        WorldEffectSpec(path="user.phone_powered_on", set=True),
                    ],
                    start_bindings=["iccid"],
                    min_depth=2,
                    max_depth=5,
                )
            ],
        )
        sampled = sample_task_intents(contract, request)
        self.assertGreaterEqual(len(sampled), 1)
        for entry in sampled:
            self.assertEqual(entry.task.start_bindings, ["iccid"])
            self.assertNotIn("acquire_iccid", entry.task.required_actions)


class TestDepgraphCompiler(unittest.TestCase):
    def test_compile_fails_without_runtime(self):
        contract = _make_simple_contract()
        task_doc = TaskSpecsDoc(
            tasks=[
                TaskIntent(
                    task_id="t1",
                    start_world=[],
                    goal_world=[
                        WorldPredicateSpec(op="eq", path="agent.b", value=True),
                    ],
                    required_actions=["do_a", "do_b"],
                    min_plan_length=2,
                )
            ]
        )
        result = preflight_and_compile(contract, task_doc)
        self.assertFalse(result.success)
        self.assertIn("runtime validation failed", " ".join(result.errors))

    def test_compile_success_with_runtime(self):
        contract = _make_simple_contract()
        runtime = RuntimeTaskSpec(
            domain="test_domain",
            reason_for_call="Need help fixing service.",
            task_instructions=_VALID_TASK_INSTRUCTIONS,
            ticket="Something is broken, please fix it.",
            initialization_actions=[
                EnvFunctionCallSpec(
                    env_type="user",
                    func_name="set_stop_gate",
                    arguments={"criteria": [{"check_field": "done", "op": "eq", "expected": True}]},
                )
            ],
            env_assertions=[
                EnvAssertionSpec(
                    env_type="assistant",
                    func_name="check_b_is_true",
                    arguments={},
                )
            ],
        )
        task_doc = TaskSpecsDoc(
            tasks=[
                TaskIntent(
                    task_id="t1",
                    start_world=[],
                    goal_world=[
                        WorldPredicateSpec(op="eq", path="agent.b", value=True),
                    ],
                    required_actions=["do_a", "do_b"],
                    min_plan_length=2,
                    runtime=runtime,
                )
            ]
        )
        result = preflight_and_compile(contract, task_doc)
        self.assertTrue(result.success, f"Errors: {result.errors}")
        self.assertEqual(len(result.tasks), 1)
        self.assertEqual(result.tasks[0].id, "t1")


class TestRuntimeAlignment(unittest.TestCase):
    def test_contract_tool_alignment_detects_missing_tools(self):
        from tau2.domains.tech_support.environment import get_environment

        contract = GraphContractSpec(
            projection_fields=["agent.done"],
            actions=[
                ActionContract(
                    action_id="bad",
                    requestor="assistant",
                    tool_name="non_existent_tool",
                    classification="causal",
                    effects_world=[WorldEffectSpec(path="agent.done", set=True)],
                )
            ],
        )
        issues = check_contract_against_environment(contract, get_environment)
        self.assertTrue(any("unknown assistant tool" in issue for issue in issues))

    def test_runtime_alignment_detects_missing_init_callable(self):
        from tau2.domains.tech_support.environment import get_environment

        runtime = RuntimeTaskSpec(
            domain="tech_support",
            reason_for_call="Need a connectivity fix.",
            task_instructions="Follow troubleshooting steps.",
            initialization_actions=[
                EnvFunctionCallSpec(
                    env_type="assistant",
                    func_name="non_existent_init_func",
                    arguments={},
                )
            ],
        )
        task_doc = TaskSpecsDoc(
            tasks=[
                TaskIntent(
                    task_id="runtime_bad_init",
                    start_world=[],
                    goal_world=[],
                    runtime=runtime,
                )
            ]
        )
        issues = check_runtime_against_environment(task_doc, get_environment)
        self.assertTrue(any("non_existent_init_func" in issue for issue in issues))

    def test_runtime_alignment_detects_non_bool_assertion_callable(self):
        from tau2.domains.tech_support.environment import get_environment

        runtime = RuntimeTaskSpec(
            domain="tech_support",
            reason_for_call="Need account help.",
            task_instructions="Follow steps.",
            env_assertions=[
                EnvAssertionSpec(
                    env_type="user",
                    func_name="set_user_info",
                    arguments={"name": "Alex", "customer_id": "CUST001"},
                )
            ],
        )
        task_doc = TaskSpecsDoc(
            tasks=[
                TaskIntent(
                    task_id="runtime_bad_assert",
                    start_world=[],
                    goal_world=[],
                    runtime=runtime,
                )
            ]
        )
        issues = check_runtime_against_environment(task_doc, get_environment)
        self.assertTrue(any("should return bool" in issue for issue in issues))

    def test_contract_alignment_detects_invalid_extraction_path(self):
        from tau2.domains.tech_support.environment import get_environment

        contract = GraphContractSpec(
            projection_fields=[],
            bindings=[
                BindingSourceSpec(
                    binding_id="connection_status",
                    source_tool="check_my_connection",
                    extraction_path="result..connection_status",
                )
            ],
        )
        issues = check_contract_against_environment(contract, get_environment)
        self.assertTrue(any("invalid extraction_path" in issue for issue in issues))


class TestStartBindingsVisibility(unittest.TestCase):
    def test_missing_value_in_ticket_and_known_info_flagged(self):
        contract = _make_chain_contract()
        task = TaskIntent(
            task_id="t1",
            start_world=[
                WorldEffectSpec(path="agent.iccid_value", set="89012345"),
            ],
            start_bindings=["iccid"],
            goal_world=[
                WorldPredicateSpec(op="eq", path="agent.data_active", value=True),
            ],
            runtime=RuntimeTaskSpec(
                domain="test",
                reason_for_call="Needs data fix.",
                task_instructions=_VALID_TASK_INSTRUCTIONS,
                ticket="My data connection is not working.",
                known_info="You are at home.",
            ),
        )
        task_doc = TaskSpecsDoc(tasks=[task])
        issues = check_start_bindings_visibility(task_doc, contract)
        self.assertEqual(len(issues), 2)
        ticket_issue = [i for i in issues if "ticket" in i]
        known_info_issue = [i for i in issues if "known_info" in i]
        self.assertEqual(len(ticket_issue), 1)
        self.assertEqual(len(known_info_issue), 1)

    def test_value_in_ticket_only_flags_known_info(self):
        contract = _make_chain_contract()
        task = TaskIntent(
            task_id="t1",
            start_world=[
                WorldEffectSpec(path="agent.iccid_value", set="89012345"),
            ],
            start_bindings=["iccid"],
            goal_world=[
                WorldPredicateSpec(op="eq", path="agent.data_active", value=True),
            ],
            runtime=RuntimeTaskSpec(
                domain="test",
                reason_for_call="Needs data fix.",
                task_instructions=_VALID_TASK_INSTRUCTIONS,
                ticket="SIM ICCID is 89012345 but data is not working.",
                known_info="You are at home.",
            ),
        )
        task_doc = TaskSpecsDoc(tasks=[task])
        issues = check_start_bindings_visibility(task_doc, contract)
        self.assertEqual(len(issues), 1)
        self.assertIn("known_info", issues[0])

    def test_value_present_in_both_passes(self):
        contract = _make_chain_contract()
        task = TaskIntent(
            task_id="t1",
            start_world=[
                WorldEffectSpec(path="agent.iccid_value", set="89012345"),
            ],
            start_bindings=["iccid"],
            goal_world=[
                WorldPredicateSpec(op="eq", path="agent.data_active", value=True),
            ],
            runtime=RuntimeTaskSpec(
                domain="test",
                reason_for_call="Needs data fix.",
                task_instructions=_VALID_TASK_INSTRUCTIONS,
                ticket="SIM ICCID is 89012345 but data is not working.",
                known_info="Your SIM ICCID is 89012345.",
            ),
        )
        task_doc = TaskSpecsDoc(tasks=[task])
        issues = check_start_bindings_visibility(task_doc, contract)
        self.assertEqual(issues, [])

    def test_empty_start_bindings_passes(self):
        contract = _make_chain_contract()
        task = TaskIntent(
            task_id="t1",
            start_world=[],
            start_bindings=[],
            goal_world=[
                WorldPredicateSpec(op="eq", path="agent.data_active", value=True),
            ],
            runtime=RuntimeTaskSpec(
                domain="test",
                reason_for_call="Needs fix.",
                task_instructions=_VALID_TASK_INSTRUCTIONS,
                ticket="Something broke.",
            ),
        )
        task_doc = TaskSpecsDoc(tasks=[task])
        issues = check_start_bindings_visibility(task_doc, contract)
        self.assertEqual(issues, [])

    def test_missing_world_path_flagged(self):
        """Binding without world_path can't resolve concrete value."""
        contract = GraphContractSpec(
            projection_fields=["agent.done"],
            bindings=[
                BindingSourceSpec(
                    binding_id="some_fact",
                    source_tool="get_info",
                    extraction_path="result.value",
                    # no world_path
                )
            ],
            actions=[],
        )
        task = TaskIntent(
            task_id="t1",
            start_world=[],
            start_bindings=["some_fact"],
            goal_world=[],
            runtime=RuntimeTaskSpec(
                domain="test",
                reason_for_call="Fix it.",
                task_instructions=_VALID_TASK_INSTRUCTIONS,
                ticket="Ticket text.",
            ),
        )
        task_doc = TaskSpecsDoc(tasks=[task])
        issues = check_start_bindings_visibility(task_doc, contract)
        self.assertEqual(len(issues), 1)
        self.assertIn("no world_path", issues[0])


if __name__ == "__main__":
    unittest.main()
