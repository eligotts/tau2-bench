import unittest

from tau2.generators.depgraph.compiler import preflight_and_compile
from tau2.generators.depgraph.preflight import run_task_preflight
from tau2.generators.depgraph.runtime_checks import (
    check_contract_against_environment,
    check_runtime_against_environment,
)
from tau2.generators.depgraph.sampler import sample_task_intents
from tau2.generators.depgraph.types import (
    ActionContract,
    EnvAssertionSpec,
    EnvFunctionCallSpec,
    FactSourceSpec,
    GraphContractSpec,
    RuntimeTaskSpec,
    SamplingRequestDoc,
    SamplingSeedSpec,
    TaskIntent,
    TaskSpecsDoc,
)


class TestDepgraphPreflight(unittest.TestCase):
    def test_knowledge_gate_and_chain_pass(self):
        contract = GraphContractSpec(
            facts=[
                "agent.line_exists",
                "user.causal.phone_powered_on",
                "user.causal.phone_restarted",
                "K.iccid_known",
                "agent.profile_ready",
                "agent.data_active",
            ],
            actions=[
                ActionContract(
                    action_id="power_on_phone",
                    requestor="user",
                    tool_name="power_on_phone",
                    classification="causal",
                    produces=["user.causal.phone_powered_on"],
                ),
                ActionContract(
                    action_id="acquire_iccid",
                    requestor="assistant",
                    tool_name="acquire_fact_from_user(iccid)",
                    classification="knowledge-only",
                    requires=["agent.line_exists"],
                    requires_absent=["K.iccid_known"],
                    produces=["K.iccid_known"],
                ),
                ActionContract(
                    action_id="restart_phone",
                    requestor="user",
                    tool_name="restart_phone",
                    classification="causal",
                    produces=["user.causal.phone_restarted"],
                ),
                ActionContract(
                    action_id="reprovision",
                    requestor="assistant",
                    tool_name="reprovision_esim",
                    classification="causal",
                    requires=["K.iccid_known", "user.causal.phone_restarted"],
                    produces=["agent.profile_ready"],
                ),
                ActionContract(
                    action_id="run_data_test",
                    requestor="user",
                    tool_name="run_data_test",
                    classification="causal",
                    requires=["agent.profile_ready"],
                    produces=["agent.data_active"],
                ),
            ],
            fact_sources=[
                FactSourceSpec(
                    fact_id="K.iccid_known",
                    source_tool="get_sim_info",
                    extraction_path="result.iccid",
                    observability_all_of=["agent.line_exists", "user.causal.phone_powered_on"],
                )
            ],
        )
        task = TaskIntent(
            task_id="telecom_chain",
            start_true_facts=["agent.line_exists"],
            goal_facts=["agent.data_active"],
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
        contract = GraphContractSpec(
            facts=[
                "agent.line_exists",
                "user.causal.phone_powered_on",
                "K.iccid_known",
                "agent.profile_ready",
            ],
            actions=[
                ActionContract(
                    action_id="acquire_iccid",
                    requestor="assistant",
                    tool_name="acquire_fact_from_user(iccid)",
                    classification="knowledge-only",
                    requires=["agent.line_exists"],
                    requires_absent=["K.iccid_known"],
                    produces=["K.iccid_known"],
                ),
                ActionContract(
                    action_id="reprovision",
                    requestor="assistant",
                    tool_name="reprovision_esim",
                    classification="causal",
                    requires=["K.iccid_known"],
                    produces=["agent.profile_ready"],
                ),
            ],
            fact_sources=[
                FactSourceSpec(
                    fact_id="K.iccid_known",
                    source_tool="get_sim_info",
                    extraction_path="result.iccid",
                    observability_all_of=["user.causal.phone_powered_on"],
                )
            ],
        )
        task = TaskIntent(
            task_id="missing_observability",
            start_true_facts=["agent.line_exists"],
            goal_facts=["agent.profile_ready"],
            required_actions=["acquire_iccid", "reprovision"],
        )
        report = run_task_preflight(contract, task, max_depth=4)
        self.assertFalse(report.passed)
        self.assertFalse(report.sat_full.sat)

    def test_goal_mutex_contradiction_fails(self):
        contract = GraphContractSpec(
            facts=["agent.good", "agent.bad"],
            actions=[],
            mutex_pairs=[("agent.good", "agent.bad")],
        )
        task = TaskIntent(
            task_id="bad_goal",
            start_true_facts=[],
            goal_facts=["agent.good", "agent.bad"],
        )
        report = run_task_preflight(contract, task, max_depth=2)
        self.assertFalse(report.passed)
        self.assertTrue(any("Goal contradiction" in issue for issue in report.issues))


class TestDepgraphSampler(unittest.TestCase):
    def test_sampler_emits_chain_tasks(self):
        contract = GraphContractSpec(
            facts=["agent.f0", "agent.f1", "agent.f2", "agent.f3"],
            actions=[
                ActionContract(
                    action_id="a1",
                    requestor="assistant",
                    tool_name="tool_a1",
                    classification="causal",
                    requires=["agent.f0"],
                    produces=["agent.f1"],
                ),
                ActionContract(
                    action_id="a2",
                    requestor="assistant",
                    tool_name="tool_a2",
                    classification="causal",
                    requires=["agent.f1"],
                    produces=["agent.f2"],
                ),
                ActionContract(
                    action_id="a3",
                    requestor="assistant",
                    tool_name="tool_a3",
                    classification="causal",
                    requires=["agent.f2"],
                    produces=["agent.f3"],
                ),
            ],
        )
        request = SamplingRequestDoc(
            max_tasks=5,
            goal_fact_prefixes=["agent."],
            seeds=[
                SamplingSeedSpec(
                    seed_id="seed",
                    start_true_facts=["agent.f0"],
                    min_depth=3,
                    max_depth=3,
                )
            ],
        )
        sampled = sample_task_intents(contract, request)
        self.assertGreaterEqual(len(sampled), 1)
        self.assertEqual(sampled[0].task.min_plan_length, 3)
        self.assertEqual(sampled[0].task.required_precedence, [("a1", "a2"), ("a2", "a3")])


class TestDepgraphCompiler(unittest.TestCase):
    def test_compile_fails_without_runtime(self):
        contract = GraphContractSpec(
            facts=["agent.done"],
            actions=[
                ActionContract(
                    action_id="do",
                    requestor="assistant",
                    tool_name="do_tool",
                    classification="causal",
                    produces=["agent.done"],
                )
            ],
        )
        task_doc = TaskSpecsDoc(
            tasks=[
                TaskIntent(
                    task_id="t1",
                    start_true_facts=[],
                    goal_facts=["agent.done"],
                    required_actions=["do"],
                    min_plan_length=1,
                )
            ]
        )
        result = preflight_and_compile(contract, task_doc)
        self.assertFalse(result.success)
        self.assertIn("runtime validation failed", " ".join(result.errors))

    def test_compile_success_with_runtime(self):
        contract = GraphContractSpec(
            facts=["agent.done"],
            actions=[
                ActionContract(
                    action_id="do",
                    requestor="assistant",
                    tool_name="do_tool",
                    classification="causal",
                    produces=["agent.done"],
                )
            ],
        )
        runtime = RuntimeTaskSpec(
            domain="tech_support",
            reason_for_call="Need help fixing service.",
            task_instructions="Work with the agent to resolve the issue.",
            known_info="Account ID is CUST001.",
            initialization_actions=[
                EnvFunctionCallSpec(
                    env_type="user",
                    func_name="set_user_info",
                    arguments={"name": "Alex", "customer_id": "CUST001"},
                )
            ],
            env_assertions=[
                EnvAssertionSpec(
                    env_type="assistant",
                    func_name="assert_customer_account_status",
                    arguments={"customer_id": "CUST001", "expected": "active"},
                )
            ],
        )
        task_doc = TaskSpecsDoc(
            tasks=[
                TaskIntent(
                    task_id="t1",
                    start_true_facts=[],
                    goal_facts=["agent.done"],
                    required_actions=["do"],
                    min_plan_length=1,
                    runtime=runtime,
                )
            ]
        )
        result = preflight_and_compile(contract, task_doc)
        self.assertTrue(result.success)
        self.assertEqual(len(result.tasks), 1)
        self.assertEqual(result.tasks[0].id, "t1")


class TestRuntimeAlignment(unittest.TestCase):
    def test_contract_tool_alignment_detects_missing_tools(self):
        from tau2.domains.tech_support.environment import get_environment

        contract = GraphContractSpec(
            facts=["agent.done"],
            actions=[
                ActionContract(
                    action_id="bad",
                    requestor="assistant",
                    tool_name="non_existent_tool",
                    classification="causal",
                    produces=["agent.done"],
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
                    start_true_facts=[],
                    goal_facts=[],
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
                    start_true_facts=[],
                    goal_facts=[],
                    runtime=runtime,
                )
            ]
        )
        issues = check_runtime_against_environment(task_doc, get_environment)
        self.assertTrue(any("should return bool" in issue for issue in issues))

    def test_contract_alignment_detects_invalid_fact_source_extraction_path(self):
        from tau2.domains.tech_support.environment import get_environment

        contract = GraphContractSpec(
            facts=["K.connection_status_known"],
            actions=[],
            fact_sources=[
                FactSourceSpec(
                    fact_id="K.connection_status_known",
                    source_tool="check_my_connection",
                    extraction_path="result..connection_status",
                    observability_all_of=[],
                )
            ],
        )
        issues = check_contract_against_environment(contract, get_environment)
        self.assertTrue(any("invalid extraction_path" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
