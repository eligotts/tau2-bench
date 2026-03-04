import unittest

from tau2.data_model.message import ToolCall
from tau2.data_model.tasks import (
    Action,
    EnvAssertion,
    EnvFunctionCall,
    EvaluationCriteria,
    RewardType,
    Task,
)
from tau2.domains.library.environment import get_environment
from tau2.generators.verify import (
    _collect_leaf_values,
    _extract_values,
    _generate_format_variants,
    build_llm_verification_prompt,
    parse_llm_verification_response,
    verify_action_necessity,
    verify_action_ordering,
    verify_action_state_change,
    verify_argument_reachability,
    verify_assertion_robustness,
    verify_assertion_value_discoverability,
    verify_golden_path,
    verify_reward_basis,
    verify_tasks,
    verify_tasks_with_llm,
    verify_tool_schemas,
    verify_user_action_feasibility,
    verify_user_action_policy_alignment,
    verify_user_action_redundancy,
    verify_user_assertion_arg_discoverability,
)


def _make_task(
    actions=None,
    env_assertions=None,
    reward_basis=None,
    nl_assertions=None,
    ticket="Patron Maria Garcia (ID: PAT001) has checkout issues.",
    known_info="You are Maria Garcia (patron ID: PAT001).",
    init_actions=None,
) -> Task:
    """Helper to build a minimal Task for testing."""
    if reward_basis is None:
        reward_basis = ["ENV_ASSERTION"]
    if init_actions is None:
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
        ]

    eval_criteria = {
        "actions": actions or [],
        "reward_basis": reward_basis,
    }
    if env_assertions is not None:
        eval_criteria["env_assertions"] = env_assertions
    if nl_assertions is not None:
        eval_criteria["nl_assertions"] = nl_assertions

    return Task(
        id="test_task_1",
        description={"purpose": "Test", "info": "Test task"},
        user_scenario={
            "instructions": {
                "task_instructions": "Follow instructions.",
                "domain": "library",
                "reason_for_call": "Issues",
                "known_info": known_info,
            },
            "persona": None,
        },
        ticket=ticket,
        initial_state={
            "initialization_actions": init_actions,
        },
        evaluation_criteria=eval_criteria,
    )


# ---------------------------------------------------------------------------
# verify_reward_basis tests
# ---------------------------------------------------------------------------


class TestVerifyRewardBasis(unittest.TestCase):
    def test_valid_reward_basis(self):
        """Task with only ENV_ASSERTION and ACTION passes."""
        task = _make_task(
            actions=[{"action_id": "a", "name": "renew_checkout", "requestor": "assistant", "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}}],
            reward_basis=["ENV_ASSERTION", "ACTION"],
        )
        issues = verify_reward_basis(task)
        self.assertEqual(issues, [])

    def test_no_evaluation_criteria(self):
        """Task with no evaluation_criteria returns no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_reward_basis(task)
        self.assertEqual(issues, [])

    def test_nl_assertions_not_in_reward_basis(self):
        """Task with nl_assertions but NL_ASSERTION not in reward_basis still passes."""
        task = _make_task(
            nl_assertions=["Agent should be polite"],
            reward_basis=["ENV_ASSERTION"],
        )
        issues = verify_reward_basis(task)
        # nl_assertions are stored but not evaluated by default — no error expected
        error_issues = [i for i in issues if "ERROR" in i]
        self.assertEqual(error_issues, [])

    def test_compare_args_valid(self):
        """compare_args as list produces no issues."""
        task = _make_task(
            actions=[{
                "action_id": "a",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"},
                "compare_args": ["checkout_id"],
            }],
            reward_basis=["ENV_ASSERTION", "ACTION"],
        )
        issues = verify_reward_basis(task)
        self.assertEqual(issues, [])

    def test_compare_args_bad_entry_rejected_by_pydantic(self):
        """compare_args with non-string entries is rejected at Task construction."""
        with self.assertRaises(Exception):
            _make_task(
                actions=[{
                    "action_id": "a",
                    "name": "renew_checkout",
                    "requestor": "assistant",
                    "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"},
                    "compare_args": [123],  # Pydantic rejects non-string
                }],
                reward_basis=["ENV_ASSERTION", "ACTION"],
            )


# ---------------------------------------------------------------------------
# verify_tool_schemas tests
# ---------------------------------------------------------------------------


class TestVerifyToolSchemas(unittest.TestCase):
    def test_valid_tool_and_args(self):
        """Task with correct tool names and arguments passes."""
        actions = [
            {
                "action_id": "act_1",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {
                    "checkout_id": "CK001",
                    "new_due_date": "2025-07-01",
                },
            }
        ]
        task = _make_task(actions=actions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        self.assertEqual(issues, [])

    def test_bad_tool_name(self):
        """Task with nonexistent tool name returns error."""
        actions = [
            {
                "action_id": "act_1",
                "name": "nonexistent_tool",
                "requestor": "assistant",
                "arguments": {},
            }
        ]
        task = _make_task(actions=actions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        self.assertEqual(len(issues), 1)
        self.assertIn("ERROR", issues[0])
        self.assertIn("nonexistent_tool", issues[0])

    def test_bad_argument_key(self):
        """Task with invalid argument key returns error."""
        actions = [
            {
                "action_id": "act_1",
                "name": "get_patron_by_name",
                "requestor": "assistant",
                "arguments": {"name": "Maria Garcia", "bad_arg": "oops"},
            }
        ]
        task = _make_task(actions=actions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        # Should have error for bad_arg
        bad_arg_issues = [i for i in issues if "bad_arg" in i]
        self.assertTrue(len(bad_arg_issues) >= 1)
        self.assertIn("ERROR", bad_arg_issues[0])

    def test_missing_required_arg(self):
        """Task missing required parameter returns error."""
        actions = [
            {
                "action_id": "act_1",
                "name": "get_patron_by_name",
                "requestor": "assistant",
                "arguments": {},  # name is required
            }
        ]
        task = _make_task(actions=actions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        # Should flag missing name
        missing_issues = [i for i in issues if "missing required" in i.lower()]
        self.assertTrue(len(missing_issues) >= 1)
        self.assertIn("name", missing_issues[0])

    def test_compare_args_valid_params(self):
        """compare_args entries that are valid tool params produce no errors."""
        actions = [
            {
                "action_id": "act_1",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {
                    "checkout_id": "CK001",
                    "new_due_date": "2025-07-01",
                },
                "compare_args": ["checkout_id", "new_due_date"],
            }
        ]
        task = _make_task(actions=actions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        self.assertEqual(issues, [])

    def test_compare_args_invalid_param(self):
        """compare_args entry not in tool schema returns error."""
        actions = [
            {
                "action_id": "act_1",
                "name": "get_patron_by_name",
                "requestor": "assistant",
                "arguments": {"name": "Maria Garcia"},
                "compare_args": ["name", "totally_fake"],
            }
        ]
        task = _make_task(actions=actions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        fake_issues = [i for i in issues if "totally_fake" in i]
        self.assertTrue(len(fake_issues) >= 1)
        self.assertIn("ERROR", fake_issues[0])

    def test_env_assertion_valid(self):
        """Valid env_assertion func_name produces no errors."""
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_membership_type",
                arguments={
                    "patron_id": "PAT001",
                    "expected_type": "premium",
                },
            )
        ]
        task = _make_task(env_assertions=env_assertions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        self.assertEqual(issues, [])

    def test_env_assertion_bad_func(self):
        """Invalid env_assertion func_name returns error."""
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="nonexistent_assertion",
                arguments={},
            )
        ]
        task = _make_task(env_assertions=env_assertions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        self.assertEqual(len(issues), 1)
        self.assertIn("ERROR", issues[0])
        self.assertIn("nonexistent_assertion", issues[0])

    def test_no_evaluation_criteria(self):
        """Task with no evaluation_criteria returns no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# verify_argument_reachability tests
# ---------------------------------------------------------------------------


class TestVerifyArgumentReachability(unittest.TestCase):
    def test_value_in_ticket(self):
        """Argument value present in ticket text passes (no reachability errors)."""
        actions = [
            {
                "action_id": "act_1",
                "name": "get_patron_by_name",
                "requestor": "assistant",
                "arguments": {"name": "Maria Garcia"},
            }
        ]
        task = _make_task(
            actions=actions,
            ticket="Patron Maria Garcia has a checkout issue.",
        )
        issues = verify_argument_reachability(
            task, get_environment, ["Patron Maria Garcia has a checkout issue."]
        )
        error_issues = [i for i in issues if "ERROR" in i]
        self.assertEqual(error_issues, [])

    def test_value_in_known_info(self):
        """Argument value present in known_info passes (no reachability errors)."""
        actions = [
            {
                "action_id": "act_1",
                "name": "get_patron_by_name",
                "requestor": "assistant",
                "arguments": {"name": "Maria Garcia"},
            }
        ]
        task = _make_task(
            actions=actions,
            known_info="You are Maria Garcia.",
        )
        issues = verify_argument_reachability(
            task, get_environment, ["You are Maria Garcia."]
        )
        error_issues = [i for i in issues if "ERROR" in i]
        self.assertEqual(error_issues, [])

    def test_value_via_read_tool(self):
        """Argument value discoverable via READ tool chain passes."""
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
        ]
        actions = [
            {
                "action_id": "act_1",
                "name": "get_patron_by_name",
                "requestor": "assistant",
                "arguments": {"name": "Maria Garcia"},
            },
            {
                "action_id": "act_2",
                "name": "get_checkouts",
                "requestor": "assistant",
                "arguments": {"patron_id": "PAT001"},
            },
        ]
        task = _make_task(
            actions=actions,
            ticket="Patron Maria Garcia (ID: PAT001) reports issues.",
            known_info="You are Maria Garcia (patron ID: PAT001).",
            init_actions=init_actions,
        )
        context_texts = [
            "Patron Maria Garcia (ID: PAT001) reports issues.",
            "You are Maria Garcia (patron ID: PAT001).",
        ]
        issues = verify_argument_reachability(task, get_environment, context_texts)
        patron_errors = [i for i in issues if "PAT001" in i]
        self.assertEqual(patron_errors, [], f"PAT001 should be reachable, got: {issues}")

    def test_unreachable_value(self):
        """Argument value not discoverable returns error."""
        actions = [
            {
                "action_id": "act_1",
                "name": "get_checkouts",
                "requestor": "assistant",
                "arguments": {"patron_id": "TOTALLY_FAKE_PATRON_XYZ"},
            }
        ]
        task = _make_task(
            actions=actions,
            ticket="Patron has generic issues.",
            known_info="You are Maria Garcia.",
        )
        context_texts = ["Patron has generic issues.", "You are Maria Garcia."]
        issues = verify_argument_reachability(task, get_environment, context_texts)
        self.assertTrue(len(issues) >= 1)
        self.assertIn("ERROR", issues[0])
        self.assertIn("TOTALLY_FAKE_PATRON_XYZ", issues[0])

    def test_compare_args_filters_check(self):
        """Only args listed in compare_args are checked for reachability."""
        actions = [
            {
                "action_id": "act_1",
                "name": "restore_membership",
                "requestor": "assistant",
                "arguments": {
                    "patron_id": "PAT001",
                    "membership_type": "premium",
                },
                "compare_args": ["patron_id"],  # membership_type excluded
            }
        ]
        task = _make_task(
            actions=actions,
            ticket="Patron PAT001 needs membership restored.",
        )
        context_texts = ["Patron PAT001 needs membership restored."]
        issues = verify_argument_reachability(task, get_environment, context_texts)
        # membership_type is NOT in compare_args, so it should NOT be checked
        self.assertEqual(issues, [])

    def test_compare_args_empty_skips_all(self):
        """compare_args=[] means name-only match, skip all arg reachability."""
        actions = [
            {
                "action_id": "act_1",
                "name": "transfer_to_human",
                "requestor": "assistant",
                "arguments": {"summary": "TOTALLY_UNREACHABLE_VALUE"},
                "compare_args": [],
            }
        ]
        task = _make_task(
            actions=actions,
            ticket="Patron needs help.",
        )
        context_texts = ["Patron needs help."]
        issues = verify_argument_reachability(task, get_environment, context_texts)
        self.assertEqual(issues, [])

    def test_compare_args_none_checks_all(self):
        """compare_args=None means check all args (default behavior)."""
        actions = [
            {
                "action_id": "act_1",
                "name": "restore_membership",
                "requestor": "assistant",
                "arguments": {
                    "patron_id": "PAT001",
                    "membership_type": "UNREACHABLE_TYPE",
                },
                # compare_args not set -> None -> check all
            }
        ]
        task = _make_task(
            actions=actions,
            ticket="Restore membership for patron PAT001.",
        )
        context_texts = ["Restore membership for patron PAT001."]
        issues = verify_argument_reachability(task, get_environment, context_texts)
        self.assertTrue(len(issues) >= 1)
        self.assertIn("UNREACHABLE_TYPE", issues[0])

    def test_user_actions_skipped(self):
        """User-side actions are skipped (no errors for their args)."""
        actions = [
            {
                "action_id": "act_1",
                "name": "view_my_checkouts",
                "requestor": "user",
                "arguments": {},
            }
        ]
        task = _make_task(actions=actions, ticket="Test", known_info="Test")
        issues = verify_argument_reachability(
            task, get_environment, ["Test"]
        )
        self.assertEqual(issues, [])

    def test_boolean_args_skipped(self):
        """Boolean and None argument values are skipped (no reachability errors)."""
        actions = [
            {
                "action_id": "act_1",
                "name": "get_patron_by_name",
                "requestor": "assistant",
                "arguments": {
                    "name": "Maria Garcia",
                },
            }
        ]
        task = _make_task(
            actions=actions,
            ticket="Patron Maria Garcia.",
        )
        issues = verify_argument_reachability(
            task, get_environment, ["Patron Maria Garcia."]
        )
        error_issues = [i for i in issues if "ERROR" in i]
        self.assertEqual(error_issues, [])

    def test_no_evaluation_criteria(self):
        """Task with no evaluation_criteria returns no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_argument_reachability(task, get_environment, ["test"])
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelperFunctions(unittest.TestCase):
    def test_extract_values(self):
        """_extract_values pulls out meaningful tokens."""
        text = "Patron Maria (ID: PAT001) has book BK001."
        values = _extract_values(text)
        self.assertIn("Maria", values)
        self.assertIn("PAT001", values)
        self.assertIn("BK001", values)
        self.assertIn("Patron", values)

    def test_extract_values_short_tokens_excluded(self):
        """Tokens shorter than 2 chars are excluded."""
        text = "A B CD EFG"
        values = _extract_values(text)
        self.assertNotIn("A", values)
        self.assertNotIn("B", values)
        self.assertIn("CD", values)
        self.assertIn("EFG", values)

    def test_collect_leaf_values_dict(self):
        """_collect_leaf_values traverses dicts and lists."""
        obj = {
            "name": "Maria",
            "ids": ["PAT001", "PAT002"],
            "nested": {"key": "val123"},
            "count": 42,
        }
        values: set[str] = set()
        _collect_leaf_values(obj, values)
        self.assertIn("Maria", values)
        self.assertIn("PAT001", values)
        self.assertIn("PAT002", values)
        self.assertIn("val123", values)
        self.assertIn("42", values)

    def test_collect_leaf_values_bool_skipped(self):
        """Booleans are not collected (they're a subclass of int)."""
        values: set[str] = set()
        _collect_leaf_values(True, values)
        _collect_leaf_values(False, values)
        self.assertEqual(values, set())


# ---------------------------------------------------------------------------
# verify_tasks integration test
# ---------------------------------------------------------------------------


class TestVerifyTasks(unittest.TestCase):
    def test_clean_task_passes(self):
        """A well-formed task produces no issues."""
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
        ]
        actions = [
            {
                "action_id": "act_1",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {
                    "checkout_id": "CK001",
                    "new_due_date": "2025-07-10",
                },
                "compare_args": ["checkout_id"],
            },
        ]
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_checkout_due_date",
                arguments={
                    "checkout_id": "CK001",
                    "expected_date": "2025-07-10",
                },
            ),
        ]
        task = _make_task(
            actions=actions,
            env_assertions=env_assertions,
            ticket="Patron Maria Garcia (ID: PAT001) needs checkout CK001 renewed to 2025-07-10.",
            known_info="You are Maria Garcia (patron ID: PAT001). Your checkout CK001 needs renewal.",
            init_actions=init_actions,
        )
        report = verify_tasks([task], get_environment)
        self.assertEqual(report, {})

    def test_task_with_errors_reported(self):
        """Tasks with bad tool names are reported."""
        actions = [
            {
                "action_id": "act_1",
                "name": "nonexistent_tool",
                "requestor": "assistant",
                "arguments": {},
            }
        ]
        task = _make_task(actions=actions)
        report = verify_tasks([task], get_environment)
        self.assertIn("test_task_1", report)
        error_issues = [i for i in report["test_task_1"] if "ERROR" in i]
        self.assertTrue(len(error_issues) >= 1)


# ---------------------------------------------------------------------------
# verify_golden_path tests
# ---------------------------------------------------------------------------


class TestVerifyGoldenPath(unittest.TestCase):
    def test_correct_fix_passes(self):
        """Task where fix actions actually fix the assertion passes golden path."""
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
            EnvFunctionCall(
                env_type="assistant",
                func_name="set_checkout_due_date",
                arguments={"checkout_id": "CK001", "due_date": "2025-01-01"},
            ),
        ]
        actions = [
            {
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {
                    "checkout_id": "CK001",
                    "new_due_date": "2025-07-15",
                },
            },
        ]
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_checkout_due_date",
                arguments={"checkout_id": "CK001", "expected_date": "2025-07-15"},
            ),
        ]
        task = _make_task(
            actions=actions,
            env_assertions=env_assertions,
            init_actions=init_actions,
        )
        issues = verify_golden_path(task, get_environment)
        self.assertEqual(issues, [])

    def test_wrong_fix_tool_fails(self):
        """Task where fix action doesn't actually fix the assertion fails golden path."""
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
            EnvFunctionCall(
                env_type="assistant",
                func_name="set_fine_status",
                arguments={"fine_id": "FN001", "status": "overdue"},
            ),
        ]
        # Fix action: renew_checkout (doesn't fix fine status)
        actions = [
            {
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {
                    "checkout_id": "CK001",
                    "new_due_date": "2025-07-15",
                },
            },
        ]
        # Assertion: check fine status (which renew_checkout doesn't change!)
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_fine_status",
                arguments={"fine_id": "FN001", "expected_status": "paid"},
            ),
        ]
        task = _make_task(
            actions=actions,
            env_assertions=env_assertions,
            init_actions=init_actions,
        )
        issues = verify_golden_path(task, get_environment)
        self.assertTrue(len(issues) >= 1)
        self.assertIn("golden path assertion FAILED", issues[0])

    def test_transfer_to_human_skipped(self):
        """Transfer-to-human tasks are skipped (no assertions to check)."""
        actions = [
            {
                "action_id": "0",
                "name": "transfer_to_human",
                "requestor": "assistant",
                "arguments": {"summary": "specialist referral"},
                "compare_args": [],
            },
        ]
        task = _make_task(actions=actions)
        issues = verify_golden_path(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_assertions_skipped(self):
        """Tasks with no assertions are skipped."""
        actions = [
            {
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"},
            },
        ]
        task = _make_task(actions=actions, env_assertions=[])
        issues = verify_golden_path(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_evaluation_criteria_skipped(self):
        """Tasks with no evaluation_criteria return no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_golden_path(task, get_environment)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# verify_user_action_feasibility tests
# ---------------------------------------------------------------------------


class TestVerifyUserActionFeasibility(unittest.TestCase):
    def test_no_user_actions_passes(self):
        """Task with only assistant actions produces no issues."""
        actions = [
            {
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-01"},
            }
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_feasibility(task, ["test context"])
        self.assertEqual(issues, [])

    def test_user_action_name_only_match_passes(self):
        """User action with compare_args=[] (name-only) passes cleanly."""
        actions = [
            {
                "action_id": "0",
                "name": "confirm_hold_pickup",
                "requestor": "user",
                "arguments": {"hold_id": "HLD001"},
                "compare_args": [],
            }
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_feasibility(
            task, ["You are Maria Garcia. Your hold needs confirmation."]
        )
        # Only the task_instructions warning, no arg discovery issues
        arg_issues = [i for i in issues if "arg" in i.lower() and "compare_args" not in i]
        self.assertEqual(arg_issues, [])

    def test_user_action_undiscoverable_arg_warns(self):
        """User action with arg value not in context produces warning."""
        actions = [
            {
                "action_id": "0",
                "name": "make_fine_payment",
                "requestor": "user",
                "arguments": {"fine_id": "FN001", "amount": 999.99},
                "compare_args": ["amount"],
            }
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_feasibility(
            task, ["You are Maria Garcia."]
        )
        arg_issues = [i for i in issues if "999.99" in i]
        self.assertTrue(len(arg_issues) >= 1)

    def test_missing_task_instructions_warns(self):
        """Task with user actions but no task_instructions warns."""
        actions = [
            {
                "action_id": "0",
                "name": "confirm_hold_pickup",
                "requestor": "user",
                "arguments": {"hold_id": "HLD001"},
                "compare_args": [],
            }
        ]
        # Create task with empty task_instructions
        task = _make_task(actions=actions)
        task.user_scenario.instructions.task_instructions = ""
        issues = verify_user_action_feasibility(task, ["test"])
        instruction_warnings = [i for i in issues if "user_task_instructions" in i]
        self.assertTrue(len(instruction_warnings) >= 1)

    def test_with_task_instructions_no_instruction_warning(self):
        """Task with user actions AND task_instructions doesn't warn about missing instructions."""
        actions = [
            {
                "action_id": "0",
                "name": "confirm_hold_pickup",
                "requestor": "user",
                "arguments": {"hold_id": "HLD001"},
                "compare_args": [],
            }
        ]
        task = _make_task(actions=actions)
        task.user_scenario.instructions.task_instructions = (
            "When the agent instructs you to confirm hold pickup, use the confirm_hold_pickup tool."
        )
        issues = verify_user_action_feasibility(task, ["test"])
        instruction_warnings = [i for i in issues if "user_task_instructions" in i]
        self.assertEqual(instruction_warnings, [])

    def test_no_evaluation_criteria_passes(self):
        """Task with no evaluation_criteria returns no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_user_action_feasibility(task, ["test"])
        self.assertEqual(issues, [])

    def test_boolean_args_skipped(self):
        """Boolean args are not flagged as undiscoverable."""
        actions = [
            {
                "action_id": "0",
                "name": "confirm_hold_pickup",
                "requestor": "user",
                "arguments": {"hold_id": "HLD001"},
                "compare_args": [],
            }
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_feasibility(task, ["test"])
        # No arg discovery warnings for compare_args=[]
        arg_issues = [i for i in issues if "HLD001" in i and "compare_args" not in i]
        self.assertEqual(arg_issues, [])


# ---------------------------------------------------------------------------
# verify_user_action_policy_alignment tests
# ---------------------------------------------------------------------------


class TestVerifyUserActionPolicyAlignment(unittest.TestCase):
    GOOD_POLICY = (
        "After renewing or reinstating, ask the patron to confirm the hold pickup "
        "using their confirm_hold_pickup tool.\n"
        "For unpaid or overdue fines, ask the patron to make a payment using their "
        "make_fine_payment tool.\n"
        "Ask the patron to acknowledge resolutions using their acknowledge_resolution tool."
    )

    BAD_POLICY = (
        "Always verify the patron's identity.\n"
        "Check the book records on the backend."
    )

    def test_policy_mentions_instruction_passes(self):
        """User action whose tool name appears in a policy instruction sentence passes."""
        actions = [
            {
                "action_id": "0",
                "name": "confirm_hold_pickup",
                "requestor": "user",
                "arguments": {"hold_id": "HLD001"},
                "compare_args": [],
            }
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_policy_alignment(task, self.GOOD_POLICY)
        hold_issues = [i for i in issues if "confirm_hold_pickup" in i]
        self.assertEqual(hold_issues, [])

    def test_policy_missing_instruction_warns(self):
        """User action not mentioned in any instruction sentence warns."""
        actions = [
            {
                "action_id": "0",
                "name": "confirm_hold_pickup",
                "requestor": "user",
                "arguments": {"hold_id": "HLD001"},
                "compare_args": [],
            }
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_policy_alignment(task, self.BAD_POLICY)
        hold_issues = [i for i in issues if "confirm_hold_pickup" in i]
        self.assertTrue(len(hold_issues) >= 1)

    def test_make_fine_payment_found_in_good_policy(self):
        """make_fine_payment matches 'ask the patron to make a payment using their make_fine_payment tool'."""
        actions = [
            {
                "action_id": "0",
                "name": "make_fine_payment",
                "requestor": "user",
                "arguments": {"fine_id": "FN001", "amount": 100.0},
                "compare_args": [],
            }
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_policy_alignment(task, self.GOOD_POLICY)
        payment_issues = [i for i in issues if "make_fine_payment" in i]
        self.assertEqual(payment_issues, [])

    def test_no_user_actions_passes(self):
        """Task with only assistant actions produces no issues."""
        actions = [
            {
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-01"},
            }
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_policy_alignment(task, self.BAD_POLICY)
        self.assertEqual(issues, [])

    def test_no_evaluation_criteria_passes(self):
        """Task with no evaluation_criteria returns no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_user_action_policy_alignment(task, self.GOOD_POLICY)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# verify_user_action_redundancy tests
# ---------------------------------------------------------------------------


class TestVerifyUserActionRedundancy(unittest.TestCase):
    def test_non_redundant_no_warning(self):
        """Agent-only actions (no user actions) produce no redundancy warnings."""
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
            EnvFunctionCall(
                env_type="assistant",
                func_name="set_checkout_due_date",
                arguments={"checkout_id": "CK001", "due_date": "2025-01-01"},
            ),
        ]
        actions = [
            {
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"},
            },
        ]
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_checkout_due_date",
                arguments={"checkout_id": "CK001", "expected_date": "2025-07-15"},
            ),
        ]
        task = _make_task(
            actions=actions,
            env_assertions=env_assertions,
            init_actions=init_actions,
        )
        issues = verify_user_action_redundancy(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_assertions_skipped(self):
        """Tasks with no assertions skip redundancy check."""
        actions = [
            {
                "action_id": "0",
                "name": "confirm_hold_pickup",
                "requestor": "user",
                "arguments": {"hold_id": "HLD001"},
                "compare_args": [],
            },
        ]
        task = _make_task(actions=actions, env_assertions=[])
        issues = verify_user_action_redundancy(task, get_environment)
        self.assertEqual(issues, [])

    def test_transfer_to_human_skipped(self):
        """Transfer tasks are skipped."""
        actions = [
            {
                "action_id": "0",
                "name": "transfer_to_human",
                "requestor": "assistant",
                "arguments": {"summary": "specialist referral"},
                "compare_args": [],
            },
        ]
        task = _make_task(actions=actions)
        issues = verify_user_action_redundancy(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_evaluation_criteria_passes(self):
        """Task with no evaluation_criteria returns no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_user_action_redundancy(task, get_environment)
        self.assertEqual(issues, [])

    def test_read_only_user_actions_skipped(self):
        """User actions that are READ tools are excluded from redundancy check.

        A diagnostic user action (e.g. view_my_checkouts) doesn't change state,
        so assertions will always pass without it. This is expected behavior,
        not a redundancy problem — the ACTION evaluator enforces the call.
        """
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
        ]
        actions = [
            {
                "action_id": "0",
                "name": "view_my_checkouts",  # READ user tool
                "requestor": "user",
                "arguments": {},
                "compare_args": [],
            },
        ]
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_checkout_due_date",
                arguments={"checkout_id": "CK001", "expected_date": "2025-03-10"},
            ),
        ]
        task = _make_task(
            actions=actions,
            env_assertions=env_assertions,
            init_actions=init_actions,
        )
        # Should return no issues because the only user action is READ
        # (filtered out before redundancy check)
        issues = verify_user_action_redundancy(task, get_environment)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# LLM verification tests
# ---------------------------------------------------------------------------


class TestLLMVerification(unittest.TestCase):
    def test_build_prompt_includes_task_details(self):
        """Prompt includes task ID, ticket, actions, assertions."""
        task = _make_task(
            actions=[{
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-01"},
            }],
            env_assertions=[
                EnvAssertion(
                    env_type="assistant",
                    func_name="assert_checkout_due_date",
                    arguments={"checkout_id": "CK001", "expected_date": "2025-07-01"},
                ),
            ],
        )
        prompt = build_llm_verification_prompt(task, "Test policy", "test tools")
        self.assertIn("test_task_1", prompt)
        self.assertIn("renew_checkout", prompt)
        self.assertIn("assert_checkout_due_date", prompt)
        self.assertIn("Test policy", prompt)

    def test_parse_response_no_issues(self):
        """Parsing 'ISSUES_FOUND: no' returns empty list."""
        response = "ISSUES_FOUND: no\nAll looks good."
        issues = parse_llm_verification_response(response)
        self.assertEqual(issues, [])

    def test_parse_response_with_issues(self):
        """Parsing response with ERROR/WARNING lines extracts them."""
        response = (
            "ISSUES_FOUND: yes\n"
            "- ERROR: Fix action doesn't modify the right field\n"
            "- WARNING: Known info is ambiguous\n"
        )
        issues = parse_llm_verification_response(response)
        self.assertEqual(len(issues), 2)
        self.assertIn("ERROR:", issues[0])
        self.assertIn("WARNING:", issues[1])

    def test_verify_tasks_with_llm_calls_fn(self):
        """verify_tasks_with_llm calls the llm_call_fn and returns results."""
        task = _make_task()
        call_count = [0]

        def mock_llm(prompt):
            call_count[0] += 1
            return "ISSUES_FOUND: yes\n- ERROR: test issue found\n"

        results = verify_tasks_with_llm(
            [task], "policy", "tools", mock_llm
        )
        self.assertEqual(call_count[0], 1)
        self.assertIn("test_task_1", results)
        self.assertEqual(len(results["test_task_1"]), 1)

    def test_verify_tasks_with_llm_sample_size(self):
        """sample_size limits how many tasks are checked."""
        tasks = [_make_task() for _ in range(10)]
        # Give each a unique ID
        for i, t in enumerate(tasks):
            t.id = f"task_{i}"

        call_count = [0]

        def mock_llm(prompt):
            call_count[0] += 1
            return "ISSUES_FOUND: no"

        verify_tasks_with_llm(tasks, "policy", "tools", mock_llm, sample_size=3)
        self.assertEqual(call_count[0], 3)


# ---------------------------------------------------------------------------
# verify_action_state_change tests
# ---------------------------------------------------------------------------


class TestVerifyActionStateChange(unittest.TestCase):
    """Tests for the verify_action_state_change no-op detection pass."""

    def test_read_tool_skipped(self):
        """READ tools are skipped — they're diagnostic, not expected to change state."""
        # get_checkouts is a READ tool — calling it won't change state,
        # but it should be silently skipped (not flagged as no-op)
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "get_checkouts",
                 "requestor": "assistant", "arguments": {"patron_id": "PAT001"}},
            ],
        )
        issues = verify_action_state_change(task, get_environment)
        # READ tool should NOT be flagged as no-op
        self.assertEqual(
            [i for i in issues if "no-op" in i], [],
            f"READ tool should not be flagged as no-op, got: {issues}",
        )

    def test_passes_real_state_change(self):
        """Action that changes DB state produces no issues."""
        # renew_checkout actually changes checkout due date
        # Must first set due date so the action is not a no-op
        task = _make_task(
            init_actions=[
                EnvFunctionCall(
                    env_type="user",
                    func_name="set_patron_info",
                    arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
                ),
                EnvFunctionCall(
                    env_type="assistant",
                    func_name="set_checkout_due_date",
                    arguments={"checkout_id": "CK001", "due_date": "2025-01-01"},
                ),
            ],
            actions=[
                {"action_id": "0", "name": "renew_checkout",
                 "requestor": "assistant", "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}},
            ],
        )
        issues = verify_action_state_change(task, get_environment)
        noop_issues = [i for i in issues if "no-op" in i]
        self.assertEqual(noop_issues, [])

    def test_skips_transfer_to_human(self):
        """transfer_to_human is always skipped (never a no-op error)."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "transfer_to_human",
                 "requestor": "assistant", "arguments": {"summary": "test"}},
            ],
        )
        issues = verify_action_state_change(task, get_environment)
        self.assertEqual(issues, [])

    def test_empty_actions(self):
        """Task with no actions produces no issues."""
        task = _make_task(actions=[])
        issues = verify_action_state_change(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_eval_criteria(self):
        """Task with no evaluation_criteria produces no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_action_state_change(task, get_environment)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# verify_action_necessity tests
# ---------------------------------------------------------------------------


class TestVerifyActionNecessity(unittest.TestCase):
    """Tests for the verify_action_necessity redundancy detection pass."""

    def test_single_action_skipped(self):
        """Single-action tasks are skipped (can't test necessity with 1 action)."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "renew_checkout",
                 "requestor": "assistant", "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}},
            ],
            env_assertions=[
                {"func_name": "assert_checkout_due_date",
                 "arguments": {"checkout_id": "CK001", "expected_date": "2025-07-15"}, "env_type": "assistant",
                 "assert_value": True, "message": ""},
            ],
        )
        issues = verify_action_necessity(task, get_environment)
        self.assertEqual(issues, [])

    def test_skips_transfer_tasks(self):
        """Tasks containing transfer_to_human are skipped entirely."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "renew_checkout",
                 "requestor": "assistant", "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}},
                {"action_id": "1", "name": "transfer_to_human",
                 "requestor": "assistant", "arguments": {"summary": "test"}},
            ],
            env_assertions=[
                {"func_name": "assert_checkout_due_date",
                 "arguments": {"checkout_id": "CK001", "expected_date": "2025-07-15"}, "env_type": "assistant",
                 "assert_value": True, "message": ""},
            ],
        )
        issues = verify_action_necessity(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_assertions_skipped(self):
        """Tasks with no assertions are skipped."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "renew_checkout",
                 "requestor": "assistant", "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}},
                {"action_id": "1", "name": "reinstate_hold",
                 "requestor": "assistant",
                 "arguments": {"hold_id": "HLD001"}},
            ],
        )
        issues = verify_action_necessity(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_eval_criteria(self):
        """Task with no evaluation_criteria produces no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_action_necessity(task, get_environment)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# _generate_format_variants tests
# ---------------------------------------------------------------------------


class TestGenerateFormatVariants(unittest.TestCase):
    """Tests for the _generate_format_variants helper."""

    def test_list_string_variants(self):
        """List[str] produces scalar-unwrap and dict-wrapped variants."""
        variants = _generate_format_variants(["penicillin"])
        descs = {v[0] for v in variants}
        self.assertIn("scalar-unwrap", descs)
        self.assertIn("dict-wrapped", descs)
        self.assertIn("single-dict", descs)

    def test_multi_element_list_no_scalar_unwrap(self):
        """Multi-element list does NOT produce scalar-unwrap."""
        variants = _generate_format_variants(["a", "b"])
        descs = {v[0] for v in variants}
        self.assertNotIn("scalar-unwrap", descs)
        self.assertIn("dict-wrapped", descs)

    def test_string_produces_list_wrapped(self):
        """A plain string produces list-wrapped variant."""
        variants = _generate_format_variants("penicillin")
        descs = {v[0] for v in variants}
        self.assertIn("list-wrapped", descs)

    def test_number_produces_string_number(self):
        """A number produces string-number variant."""
        variants = _generate_format_variants(42)
        descs = {v[0] for v in variants}
        self.assertIn("string-number", descs)

    def test_empty_list_no_variants(self):
        """Empty list produces no variants."""
        variants = _generate_format_variants([])
        self.assertEqual(variants, [])


# ---------------------------------------------------------------------------
# verify_assertion_robustness tests
# ---------------------------------------------------------------------------


class TestVerifyAssertionRobustness(unittest.TestCase):
    """Tests for the verify_assertion_robustness pass."""

    def test_no_eval_criteria(self):
        """Task with no evaluation_criteria passes."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_assertion_robustness(task, get_environment)
        self.assertEqual(issues, [])

    def test_transfer_tasks_skipped(self):
        """Transfer tasks are skipped."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "transfer_to_human",
                 "requestor": "assistant", "arguments": {"summary": "test"}},
            ],
            env_assertions=[
                {"func_name": "assert_checkout_due_date",
                 "arguments": {"checkout_id": "CK001", "expected_date": "2025-07-15"}, "env_type": "assistant",
                 "assert_value": True, "message": ""},
            ],
        )
        issues = verify_assertion_robustness(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_any_typed_params_skipped(self):
        """Actions without Any-typed params are skipped."""
        task = _make_task(
            init_actions=[
                EnvFunctionCall(
                    env_type="user",
                    func_name="set_patron_info",
                    arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
                ),
                EnvFunctionCall(
                    env_type="assistant",
                    func_name="set_checkout_due_date",
                    arguments={"checkout_id": "CK001", "due_date": "2025-01-01"},
                ),
            ],
            actions=[
                {"action_id": "0", "name": "renew_checkout",
                 "requestor": "assistant",
                 "arguments": {"checkout_id": "CK001",
                               "new_due_date": "2025-07-15"}},
            ],
            env_assertions=[
                {"func_name": "assert_checkout_due_date",
                 "arguments": {"checkout_id": "CK001", "expected_date": "2025-07-15"}, "env_type": "assistant",
                 "assert_value": True, "message": ""},
            ],
        )
        issues = verify_assertion_robustness(task, get_environment)
        self.assertEqual(issues, [])

    def test_catches_brittle_assertion_with_dict_wrapped_value(self):
        """Detects when dict-wrapping a list value causes assertion failure.

        NOTE: After fixing assertions to use substring matching, this should
        no longer produce an error. We test that the pass at least runs
        without error for this case.
        """
        task = _make_task(
            init_actions=[
                EnvFunctionCall(
                    env_type="user",
                    func_name="set_patron_info",
                    arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
                ),
                EnvFunctionCall(
                    env_type="assistant",
                    func_name="set_book_location",
                    arguments={"book_id": "BK001", "location": "storage"},
                ),
            ],
            actions=[
                {"action_id": "0", "name": "update_book_record",
                 "requestor": "assistant",
                 "arguments": {"book_id": "BK001", "field": "location",
                               "value": "main_floor"}},
            ],
            env_assertions=[
                {"func_name": "assert_book_location",
                 "arguments": {"book_id": "BK001", "expected_location": "main_floor"},
                 "env_type": "assistant",
                 "assert_value": True, "message": ""},
            ],
        )
        issues = verify_assertion_robustness(task, get_environment)
        error_issues = [i for i in issues if i.startswith("ERROR")]
        self.assertEqual(
            error_issues, [],
            "After substring fix, dict-wrapped variants should not fail",
        )


# ---------------------------------------------------------------------------
# verify_assertion_value_discoverability tests
# ---------------------------------------------------------------------------


class TestVerifyAssertionValueDiscoverability(unittest.TestCase):
    """Tests for the verify_assertion_value_discoverability pass."""

    def test_no_eval_criteria(self):
        """Task with no evaluation_criteria passes."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_assertion_value_discoverability(task, [])
        self.assertEqual(issues, [])

    def test_trivial_values_skipped(self):
        """Common end-state values (active, paid, current, 0.0) are not flagged."""
        task = _make_task(
            env_assertions=[
                {"func_name": "assert_hold_status",
                 "arguments": {"hold_id": "HLD001", "expected_status": "active"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        # HLD001 must be discoverable from context for this assertion arg
        issues = verify_assertion_value_discoverability(
            task, ["Hold HLD001 needs reinstating."]
        )
        self.assertEqual(issues, [])

    def test_discoverable_value_from_context(self):
        """Assertion value present in context text passes."""
        task = _make_task(
            env_assertions=[
                {"func_name": "assert_checkout_due_date",
                 "arguments": {"checkout_id": "CK001",
                               "expected_date": "2025-06-15"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        context = ["Checkout CK001 should be due on 2025-06-15."]
        issues = verify_assertion_value_discoverability(task, context)
        self.assertEqual(issues, [])

    def test_undiscoverable_value_warns(self):
        """Assertion value NOT in context or action args is flagged."""
        task = _make_task(
            env_assertions=[
                {"func_name": "assert_membership_type",
                 "arguments": {"patron_id": "PAT001",
                               "expected_type": "platinum"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        # "platinum" not mentioned anywhere
        context = ["Patron PAT001 has a membership issue."]
        issues = verify_assertion_value_discoverability(task, context)
        self.assertTrue(
            any("platinum" in i for i in issues),
            f"Expected warning about undiscoverable 'platinum', got: {issues}",
        )

    def test_value_in_action_args_passes(self):
        """Assertion values that appear in action arguments pass."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "restore_membership",
                 "requestor": "assistant",
                 "arguments": {"patron_id": "PAT001", "membership_type": "premium"}},
            ],
            env_assertions=[
                {"func_name": "assert_membership_type",
                 "arguments": {"patron_id": "PAT001",
                               "expected_type": "premium"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        context = ["Patron PAT001 should be premium tier."]
        issues = verify_assertion_value_discoverability(task, context)
        tier_issues = [i for i in issues if "premium" in i]
        self.assertEqual(tier_issues, [])

    def test_transfer_tasks_skipped(self):
        """Transfer tasks are skipped."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "transfer_to_human",
                 "requestor": "assistant", "arguments": {"summary": "test"}},
            ],
            env_assertions=[
                {"func_name": "assert_membership_type",
                 "arguments": {"patron_id": "PAT001",
                               "expected_type": "unobtainium"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        issues = verify_assertion_value_discoverability(task, [])
        self.assertEqual(issues, [])

    def test_entity_id_args_skipped(self):
        """Entity ID args (*_id) are skipped — they are tool-discoverable."""
        task = _make_task(
            env_assertions=[
                {"func_name": "assert_tire_pressure",
                 "arguments": {"vehicle_id": "VH010", "min_psi": 30},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        # vehicle_id not in context, but should not warn (it's an _id arg)
        issues = verify_assertion_value_discoverability(task, ["Some context"])
        id_issues = [i for i in issues if "vehicle_id" in i]
        self.assertEqual(id_issues, [])

    def test_threshold_args_skipped(self):
        """Threshold args (min_*, max_*) are skipped — assertion-internal criteria."""
        task = _make_task(
            env_assertions=[
                {"func_name": "assert_battery_voltage",
                 "arguments": {"vehicle_id": "VH010", "min_voltage": 12.4},
                 "env_type": "assistant", "assert_value": True, "message": ""},
                {"func_name": "assert_tire_pressure",
                 "arguments": {"vehicle_id": "VH010", "max_deviation": 5.0},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        issues = verify_assertion_value_discoverability(task, ["Some context"])
        threshold_issues = [i for i in issues
                           if "min_voltage" in i or "max_deviation" in i]
        self.assertEqual(threshold_issues, [])

    def test_end_state_values_skipped(self):
        """End-state values (normal, clean, aligned, etc.) are trivial."""
        task = _make_task(
            env_assertions=[
                {"func_name": "assert_brake_fluid",
                 "arguments": {"expected": "normal"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
                {"func_name": "assert_air_filter",
                 "arguments": {"expected": "clean"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
                {"func_name": "assert_wheels",
                 "arguments": {"expected": "aligned"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        issues = verify_assertion_value_discoverability(task, [])
        self.assertEqual(issues, [])

    def test_nontrivial_values_still_warn(self):
        """Non-trivial, non-_id, non-threshold values that are absent still warn."""
        task = _make_task(
            env_assertions=[
                {"func_name": "assert_membership_type",
                 "arguments": {"expected_type": "diamond"},
                 "env_type": "assistant", "assert_value": True, "message": ""},
            ],
        )
        issues = verify_assertion_value_discoverability(
            task, ["Patron needs membership help."]
        )
        self.assertTrue(
            any("diamond" in i for i in issues),
            f"Expected warning about undiscoverable 'diamond', got: {issues}",
        )


# ---------------------------------------------------------------------------
# verify_user_action_feasibility — conditional action warning tests
# ---------------------------------------------------------------------------


class TestVerifyConditionalUserActions(unittest.TestCase):
    """Tests for the conditional user action warning in verify_user_action_feasibility."""

    def test_conditional_user_action_warns(self):
        """User action gated by 'if the agent asks' produces a warning."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "confirm_hold_pickup",
                 "requestor": "user",
                 "arguments": {"hold_id": "HLD001"},
                 "compare_args": []},
            ],
        )
        task.user_scenario.instructions.task_instructions = (
            "If the agent asks you to confirm a hold pickup, "
            "use your confirm_hold_pickup tool."
        )
        context = [
            "You are Maria Garcia (patron ID: PAT001).",
            task.user_scenario.instructions.task_instructions,
        ]
        issues = verify_user_action_feasibility(task, context)
        conditional_issues = [i for i in issues if "conditional" in i.lower()]
        self.assertTrue(
            len(conditional_issues) > 0,
            f"Expected conditional user action warning, got: {issues}",
        )

    def test_proactive_user_action_no_warning(self):
        """User action with proactive instructions does NOT warn about conditionality."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "make_fine_payment",
                 "requestor": "user",
                 "arguments": {"fine_id": "FN001", "amount": 150.0},
                 "compare_args": []},
            ],
        )
        task.user_scenario.instructions.task_instructions = (
            "Go ahead and use your make_fine_payment tool to pay your outstanding fine."
        )
        context = [
            "You are Maria Garcia (patron ID: PAT001). Fine FN001 is $150.00.",
            task.user_scenario.instructions.task_instructions,
        ]
        issues = verify_user_action_feasibility(task, context)
        conditional_issues = [i for i in issues if "conditional" in i.lower()]
        self.assertEqual(
            conditional_issues, [],
            f"Proactive instructions should not trigger conditional warning: {issues}",
        )


# ---------------------------------------------------------------------------
# Tests for Fix 1: Pre-fix assertion failure check in verify_golden_path
# ---------------------------------------------------------------------------


class TestVerifyGoldenPathPreFix(unittest.TestCase):
    """Tests for the pre-fix assertion failure check added to verify_golden_path."""

    def test_assertions_fail_before_fix_no_warning(self):
        """Normal task where assertions fail before fix → no warning about pre-fix."""
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
            EnvFunctionCall(
                env_type="assistant",
                func_name="set_checkout_due_date",
                arguments={"checkout_id": "CK001", "due_date": "2025-01-01"},
            ),
        ]
        actions = [
            {
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {
                    "checkout_id": "CK001",
                    "new_due_date": "2025-07-15",
                },
            },
        ]
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_checkout_due_date",
                arguments={"checkout_id": "CK001", "expected_date": "2025-07-15"},
            ),
        ]
        task = _make_task(
            actions=actions,
            env_assertions=env_assertions,
            init_actions=init_actions,
        )
        issues = verify_golden_path(task, get_environment)
        pre_fix_issues = [i for i in issues if "before fix" in i.lower()]
        self.assertEqual(pre_fix_issues, [])

    def test_transfer_tasks_skip_pre_fix_check(self):
        """Transfer-to-human tasks skip the pre-fix assertion check."""
        actions = [
            {
                "action_id": "0",
                "name": "transfer_to_human",
                "requestor": "assistant",
                "arguments": {"summary": "test"},
                "compare_args": [],
            },
        ]
        task = _make_task(actions=actions)
        issues = verify_golden_path(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_assertions_skips_pre_fix(self):
        """Tasks with no assertions skip the pre-fix check entirely."""
        actions = [
            {
                "action_id": "0",
                "name": "renew_checkout",
                "requestor": "assistant",
                "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"},
            },
        ]
        task = _make_task(actions=actions, env_assertions=[])
        issues = verify_golden_path(task, get_environment)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# Tests for Fix 3: Silent exceptions emit warnings
# ---------------------------------------------------------------------------


class TestSilentExceptionsEmitWarnings(unittest.TestCase):
    """Tests that previously-silent exceptions now emit warnings."""

    def test_action_state_change_exception_emits_warning(self):
        """verify_action_state_change emits warning when action raises."""
        # Create a task with an action that will raise (bad args)
        task = _make_task(
            actions=[
                {
                    "action_id": "0",
                    "name": "renew_checkout",
                    "requestor": "assistant",
                    "arguments": {
                        "checkout_id": "NONEXISTENT_CHECKOUT_XYZ",
                        "new_due_date": "2025-07-15",
                    },
                },
            ],
        )
        issues = verify_action_state_change(task, get_environment)
        # Should emit a warning about the exception, not silently skip
        warning_issues = [i for i in issues if "WARNING" in i]
        self.assertTrue(
            len(warning_issues) >= 1,
            f"Expected warning about exception during action, got: {issues}",
        )

    def test_action_necessity_exception_emits_warning(self):
        """verify_action_necessity emits warning when action raises."""
        # Task with two actions, one of which will raise due to bad args
        task = _make_task(
            actions=[
                {
                    "action_id": "0",
                    "name": "renew_checkout",
                    "requestor": "assistant",
                    "arguments": {
                        "checkout_id": "CK001",
                        "new_due_date": "2025-07-15",
                    },
                },
                {
                    "action_id": "1",
                    "name": "renew_checkout",
                    "requestor": "assistant",
                    "arguments": {
                        "checkout_id": "NONEXISTENT_CHECKOUT_XYZ",
                        "new_due_date": "2025-07-15",
                    },
                },
            ],
            env_assertions=[
                EnvAssertion(
                    env_type="assistant",
                    func_name="assert_checkout_due_date",
                    arguments={"checkout_id": "CK001", "expected_date": "2025-07-15"},
                ),
            ],
        )
        issues = verify_action_necessity(task, get_environment)
        warning_issues = [i for i in issues if "WARNING" in i]
        self.assertTrue(
            len(warning_issues) >= 1,
            f"Expected warning about exception during action, got: {issues}",
        )


# ---------------------------------------------------------------------------
# Tests for Fix 4: Assertion argument schema validation
# ---------------------------------------------------------------------------


class TestAssertionArgSchemaValidation(unittest.TestCase):
    """Tests for assertion argument key/required validation in verify_tool_schemas."""

    def test_valid_assertion_args_pass(self):
        """Assertion with correct arg names produces no errors."""
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_membership_type",
                arguments={
                    "patron_id": "PAT001",
                    "expected_type": "premium",
                },
            )
        ]
        task = _make_task(env_assertions=env_assertions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        assertion_issues = [i for i in issues if "assertion" in i.lower() and "arg" in i.lower()]
        self.assertEqual(assertion_issues, [])

    def test_invalid_assertion_arg_key_errors(self):
        """Assertion with wrong arg key produces ERROR."""
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_membership_type",
                arguments={
                    "patron_id": "PAT001",
                    "totally_wrong_param": "premium",
                },
            )
        ]
        task = _make_task(env_assertions=env_assertions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        wrong_arg_issues = [i for i in issues if "totally_wrong_param" in i]
        self.assertTrue(
            len(wrong_arg_issues) >= 1,
            f"Expected error about invalid assertion arg, got: {issues}",
        )

    def test_missing_required_assertion_arg_errors(self):
        """Assertion missing a required arg produces ERROR."""
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_membership_type",
                arguments={
                    # Missing patron_id (required)
                    "expected_type": "premium",
                },
            )
        ]
        task = _make_task(env_assertions=env_assertions)
        env = get_environment()
        issues = verify_tool_schemas(task, env)
        missing_issues = [i for i in issues if "patron_id" in i]
        self.assertTrue(
            len(missing_issues) >= 1,
            f"Expected error about missing assertion arg, got: {issues}",
        )


# ---------------------------------------------------------------------------
# verify_action_ordering tests
# ---------------------------------------------------------------------------


class TestVerifyActionOrdering(unittest.TestCase):
    """Tests for the verify_action_ordering dependency detection pass."""

    def test_single_action_skipped(self):
        """Single-action tasks are skipped."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "renew_checkout",
                 "requestor": "assistant",
                 "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}},
            ],
            env_assertions=[
                EnvAssertion(
                    env_type="assistant",
                    func_name="assert_checkout_due_date",
                    arguments={"checkout_id": "CK001", "expected_date": "2025-07-15"},
                ),
            ],
        )
        issues = verify_action_ordering(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_assertions_skipped(self):
        """Tasks with no assertions are skipped."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "renew_checkout",
                 "requestor": "assistant",
                 "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}},
                {"action_id": "1", "name": "reinstate_hold",
                 "requestor": "assistant",
                 "arguments": {"hold_id": "HLD001"}},
            ],
        )
        issues = verify_action_ordering(task, get_environment)
        self.assertEqual(issues, [])

    def test_transfer_tasks_skipped(self):
        """Transfer tasks are skipped."""
        task = _make_task(
            actions=[
                {"action_id": "0", "name": "renew_checkout",
                 "requestor": "assistant",
                 "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}},
                {"action_id": "1", "name": "transfer_to_human",
                 "requestor": "assistant",
                 "arguments": {"summary": "test"}},
            ],
            env_assertions=[
                EnvAssertion(
                    env_type="assistant",
                    func_name="assert_checkout_due_date",
                    arguments={"checkout_id": "CK001", "expected_date": "2025-07-15"},
                ),
            ],
        )
        issues = verify_action_ordering(task, get_environment)
        self.assertEqual(issues, [])

    def test_no_eval_criteria(self):
        """Task with no evaluation_criteria produces no issues."""
        task = _make_task()
        task.evaluation_criteria = None
        issues = verify_action_ordering(task, get_environment)
        self.assertEqual(issues, [])

    def test_independent_actions_no_issues(self):
        """Two independent actions produce no issues (ordering doesn't matter)."""
        init_actions = [
            EnvFunctionCall(
                env_type="user",
                func_name="set_patron_info",
                arguments={"name": "Maria Garcia", "patron_id": "PAT001"},
            ),
            EnvFunctionCall(
                env_type="assistant",
                func_name="set_checkout_due_date",
                arguments={"checkout_id": "CK001", "due_date": "2025-01-01"},
            ),
            EnvFunctionCall(
                env_type="assistant",
                func_name="set_fine_status",
                arguments={"fine_id": "FN001", "status": "overdue"},
            ),
        ]
        actions = [
            {"action_id": "0", "name": "renew_checkout",
             "requestor": "assistant",
             "arguments": {"checkout_id": "CK001", "new_due_date": "2025-07-15"}},
            {"action_id": "1", "name": "waive_fine",
             "requestor": "assistant",
             "arguments": {"fine_id": "FN001"}},
        ]
        env_assertions = [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_checkout_due_date",
                arguments={"checkout_id": "CK001", "expected_date": "2025-07-15"},
            ),
            EnvAssertion(
                env_type="assistant",
                func_name="assert_fine_status",
                arguments={"fine_id": "FN001", "expected_status": "waived"},
            ),
        ]
        task = _make_task(
            actions=actions,
            env_assertions=env_assertions,
            init_actions=init_actions,
        )
        issues = verify_action_ordering(task, get_environment)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# verify_fault_atoms integration tests (using library environment)
# ---------------------------------------------------------------------------


class TestVerifyFaultAtomsIntegration(unittest.TestCase):
    """Integration tests for verify_fault_atoms using the library domain."""

    def test_valid_atom_passes(self):
        """A valid init→fix→check atom produces no issues."""
        from tau2.generators.recipe import (
            ActionSpec,
            AssertionSpec,
            FaultAtom,
            FaultLayer,
            FaultLayerConfig,
            FaultLayerGroup,
            InitCall,
            verify_fault_atoms,
        )
        from tau2.domains.library.environment import get_environment as get_lib_env

        atom = FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_checkout_due_date",
                args={"checkout_id": "{checkout_id}", "due_date": "2025-01-01"},
            ),
            fix=ActionSpec(
                tool_name="renew_checkout",
                args={"checkout_id": "{checkout_id}", "new_due_date": "2025-07-15"},
            ),
            check=AssertionSpec(
                func_name="assert_checkout_due_date",
                args={"checkout_id": "{checkout_id}", "expected_date": "2025-07-15"},
                env_type="assistant",
            ),
        )

        layer = FaultLayer(
            name="overdue_checkout",
            atoms=[atom],
            known_info_fragment="my checkout is overdue",
            completion_fragment="your checkout has been renewed",
        )

        flc = FaultLayerConfig(
            name="library_test",
            entity_query=lambda db: [{"checkout_id": "CK001", "id": "CK001"}],
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            base_init_calls=[
                InitCall(
                    env_type="user",
                    func_name="set_patron_info",
                    args={"name": "Maria Garcia", "patron_id": "PAT001"},
                ),
            ],
            base_known_info_template="{fault_descriptions}",
            base_ticket_template="{fault_descriptions}",
            reason_for_call="test",
            purpose="test",
            entity_id_field="id",
            min_faults=1,
        )

        issues = verify_fault_atoms(
            flc,
            get_lib_env,
            lambda: {"checkout_id": "CK001", "id": "CK001"},
        )
        self.assertEqual(issues, [], f"Expected no issues, got: {issues}")

    def test_broken_fix_detected(self):
        """Atom where fix doesn't repair what check verifies is flagged."""
        from tau2.generators.recipe import (
            ActionSpec,
            AssertionSpec,
            FaultAtom,
            FaultLayer,
            FaultLayerConfig,
            FaultLayerGroup,
            InitCall,
            verify_fault_atoms,
        )
        from tau2.domains.library.environment import get_environment as get_lib_env

        # Init breaks fine status, but fix renews checkout (wrong fix!)
        atom = FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_fine_status",
                args={"fine_id": "{fine_id}", "status": "overdue"},
            ),
            fix=ActionSpec(
                tool_name="renew_checkout",
                args={"checkout_id": "CK001", "new_due_date": "2025-07-15"},
            ),
            check=AssertionSpec(
                func_name="assert_fine_status",
                args={"fine_id": "{fine_id}", "expected_status": "paid"},
                env_type="assistant",
            ),
        )

        layer = FaultLayer(
            name="broken_fix",
            atoms=[atom],
            known_info_fragment="fine is overdue",
            completion_fragment="your fine is paid",
        )

        flc = FaultLayerConfig(
            name="library_test",
            entity_query=lambda db: [{"fine_id": "FN001", "id": "FN001"}],
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            base_init_calls=[
                InitCall(
                    env_type="user",
                    func_name="set_patron_info",
                    args={"name": "Maria Garcia", "patron_id": "PAT001"},
                ),
            ],
            base_known_info_template="{fault_descriptions}",
            base_ticket_template="{fault_descriptions}",
            reason_for_call="test",
            purpose="test",
            entity_id_field="id",
            min_faults=1,
        )

        issues = verify_fault_atoms(
            flc,
            get_lib_env,
            lambda: {"fine_id": "FN001", "id": "FN001"},
        )
        error_issues = [i for i in issues if "FAILS after fix" in i]
        self.assertTrue(
            len(error_issues) >= 1,
            f"Expected 'FAILS after fix' error, got: {issues}",
        )


# ---------------------------------------------------------------------------
# verify_completion_fragments — impossible-goal validation tests
# ---------------------------------------------------------------------------


class TestVerifyCompletionFragmentsImpossibleGoal(unittest.TestCase):
    """Tests for the impossible-goal validation in verify_completion_fragments."""

    def _make_flc(self, layers):
        from tau2.generators.recipe import (
            FaultLayerConfig,
            FaultLayerGroup,
            InitCall,
        )
        return FaultLayerConfig(
            name="test_flc",
            entity_query=lambda db: [{"id": "E001"}],
            groups=[FaultLayerGroup(name="g1", layers=layers)],
            base_init_calls=[],
            base_known_info_template="{fault_descriptions}",
            base_ticket_template="{fault_descriptions}",
            reason_for_call="test",
            purpose="test",
            entity_id_field="id",
            min_faults=1,
        )

    def test_transfer_leaking_fragment_rejected(self):
        """Unfixable layer with 'transferred' in fragment produces ERROR."""
        from tau2.generators.recipe import FaultLayer, verify_completion_fragments

        layer = FaultLayer(
            name="unfixable_fault",
            unfixable=True,
            atoms=[],
            known_info_fragment="something is broken",
            completion_fragment="the agent has transferred you to a specialist team",
        )
        flc = self._make_flc([layer])
        issues = verify_completion_fragments(flc)
        errors = [i for i in issues if "ERROR" in i and "leak" in i.lower()]
        self.assertTrue(
            len(errors) >= 1,
            f"Expected transfer-leaking error, got: {issues}",
        )

    def test_escalated_fragment_rejected(self):
        """Unfixable layer with 'escalated' in fragment produces ERROR."""
        from tau2.generators.recipe import FaultLayer, verify_completion_fragments

        layer = FaultLayer(
            name="unfixable_fault",
            unfixable=True,
            atoms=[],
            known_info_fragment="something is broken",
            completion_fragment="your issue has been escalated to a higher level",
        )
        flc = self._make_flc([layer])
        issues = verify_completion_fragments(flc)
        errors = [i for i in issues if "ERROR" in i and "leak" in i.lower()]
        self.assertTrue(
            len(errors) >= 1,
            f"Expected transfer-leaking error, got: {issues}",
        )

    def test_specialist_fragment_rejected(self):
        """Unfixable layer with 'specialist' in fragment produces ERROR."""
        from tau2.generators.recipe import FaultLayer, verify_completion_fragments

        layer = FaultLayer(
            name="unfixable_fault",
            unfixable=True,
            atoms=[],
            known_info_fragment="something is broken",
            completion_fragment="a specialist has been assigned to your case",
        )
        flc = self._make_flc([layer])
        issues = verify_completion_fragments(flc)
        errors = [i for i in issues if "ERROR" in i and "leak" in i.lower()]
        self.assertTrue(
            len(errors) >= 1,
            f"Expected transfer-leaking error, got: {issues}",
        )

    def test_impossible_goal_fragment_passes(self):
        """Unfixable layer with proper impossible-goal fragment passes."""
        from tau2.generators.recipe import FaultLayer, verify_completion_fragments

        layer = FaultLayer(
            name="hardware_failure",
            unfixable=True,
            atoms=[],
            known_info_fragment="my router has a hardware failure",
            completion_fragment="your router is back online with all lights showing normal status",
        )
        flc = self._make_flc([layer])
        issues = verify_completion_fragments(flc)
        errors = [i for i in issues if "ERROR" in i]
        self.assertEqual(errors, [])

    def test_fixable_layer_not_checked_for_transfer_leak(self):
        """Fixable layers are NOT checked for transfer-leak phrases."""
        from tau2.generators.recipe import (
            ActionSpec,
            AssertionSpec,
            FaultAtom,
            FaultLayer,
            InitCall,
            verify_completion_fragments,
        )

        layer = FaultLayer(
            name="fixable_fault",
            atoms=[
                FaultAtom(
                    fix=ActionSpec(tool_name="fix_it", args={"id": "{id}"}),
                    check=AssertionSpec(func_name="assert_fixed", args={"id": "{id}"}),
                ),
            ],
            known_info_fragment="something is broken",
            # "transferred" is weird for a fixable layer but should not error
            completion_fragment="your case has been transferred to the resolution queue",
        )
        flc = self._make_flc([layer])
        issues = verify_completion_fragments(flc)
        leak_errors = [i for i in issues if "leak" in i.lower()]
        self.assertEqual(leak_errors, [])


if __name__ == "__main__":
    unittest.main()
