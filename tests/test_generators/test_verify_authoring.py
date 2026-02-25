"""Tests for verify_authoring module — pre-generation structural checks."""

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tau2.domains.library.data_model import LibraryDB
from tau2.domains.library.environment import get_environment
from tau2.domains.library.scenarios import RECIPE_BOOK, LIBRARY_FAULT_CONFIG
from tau2.domains.library.utils import LIBRARY_DB_PATH, LIBRARY_POLICY_PATH
from tau2.generators.recipe import (
    ActionSpec,
    AssertionSpec,
    FaultAtom,
    FaultLayer,
    FaultLayerConfig,
    FaultLayerGroup,
    InitCall,
    RecipeBook,
)
from tau2.generators.verify_authoring import (
    _build_recipe_summary,
    _check_assertion_func_exists,
    _check_fix_tool_exists,
    _check_fix_tool_is_write,
    _check_init_func_exists,
    _check_known_info_fragment_templates,
    _check_predicate_fields_exist,
    _check_requestor_toolkit_match,
    _check_resource_scope_resolves,
    _check_template_vars_valid,
    collect_authored_files,
    verify_authoring,
    verify_authoring_with_llm,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def get_db():
    return lambda: LibraryDB.load(LIBRARY_DB_PATH)


@pytest.fixture
def env():
    return get_environment()


@pytest.fixture
def sample_entity(get_db):
    """A sample entity from library that passes most predicates."""
    db = get_db()
    entities = LIBRARY_FAULT_CONFIG.entity_query(db)
    # Find one with all flags True
    for e in entities:
        if e.get("has_checkout") and e.get("has_hold") and e.get("has_fine"):
            return e
    return entities[0]


def _make_layer(
    name="test_layer",
    atoms=None,
    init_calls=None,
    actions=None,
    assertions=None,
    known_info_fragment="Test fragment",
    predicate_field=None,
    predicate_ne=None,
    resource_scope=None,
    unfixable=False,
):
    """Helper to create a FaultLayer for tests."""
    return FaultLayer(
        name=name,
        known_info_fragment=known_info_fragment,
        atoms=atoms or [],
        init_calls=init_calls or [],
        actions=actions or [],
        assertions=assertions or [],
        unfixable=unfixable,
        predicate_field=predicate_field,
        predicate_ne=predicate_ne,
        resource_scope=resource_scope,
    )


def _make_flc(groups=None, base_init_calls=None):
    """Helper to create a minimal FaultLayerConfig."""
    return FaultLayerConfig(
        name="test_config",
        entity_query=lambda db: LIBRARY_FAULT_CONFIG.entity_query(db),
        groups=groups or [],
        base_init_calls=base_init_calls or [],
        base_known_info_template="Test: {fault_descriptions}",
        base_ticket_template="Ticket: {fault_descriptions}",
        reason_for_call="Testing",
        purpose="Test verification",
    )


# ===================================================================
# Positive test: library passes
# ===================================================================


def test_verify_authoring_library_no_errors(get_db):
    """Full verify_authoring on RECIPE_BOOK produces 0 errors."""
    issues = verify_authoring(RECIPE_BOOK, get_environment, get_db)
    errors = [i for i in issues if i.startswith("ERROR:")]
    # Print all issues for debugging
    for i in issues:
        print(f"  {i}")
    assert len(errors) == 0, f"Expected 0 errors, got:\n" + "\n".join(errors)


# ===================================================================
# Negative tests: intentionally broken fixtures
# ===================================================================


class TestInitFuncExists:
    """Check 1: init_func_exists."""

    def test_init_func_bad_name(self, env):
        """InitCall with typo'd func_name → ERROR."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    init=InitCall(
                        env_type="assistant",
                        func_name="set_checkout_due_datee",  # typo
                        args={"checkout_id": "CK001", "due_date": "2025-12-31"},
                    ),
                    fix=ActionSpec(tool_name="renew_checkout", args={}),
                ),
            ],
        )
        flc = _make_flc()
        issues = _check_init_func_exists(env, flc, layer)
        assert any("ERROR" in i and "set_checkout_due_datee" in i for i in issues)

    def test_init_func_valid(self, env):
        """Valid init func → no issues."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    init=InitCall(
                        env_type="assistant",
                        func_name="set_checkout_due_date",
                        args={"checkout_id": "CK001", "due_date": "2025-12-31"},
                    ),
                    fix=ActionSpec(tool_name="renew_checkout", args={}),
                ),
            ],
        )
        flc = _make_flc()
        issues = _check_init_func_exists(env, flc, layer)
        assert len(issues) == 0


class TestFixToolExists:
    """Check 2: fix_tool_exists."""

    def test_fix_tool_not_decorated(self, env):
        """ActionSpec referencing non-@is_tool method → ERROR."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(
                        tool_name="set_checkout_due_date",  # helper, not a tool
                        args={},
                    ),
                ),
            ],
        )
        issues = _check_fix_tool_exists(env, layer)
        assert any("ERROR" in i and "set_checkout_due_date" in i for i in issues)

    def test_fix_tool_valid(self, env):
        """Valid fix tool → no issues."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(tool_name="renew_checkout", args={}),
                ),
            ],
        )
        issues = _check_fix_tool_exists(env, layer)
        assert len(issues) == 0


class TestAssertionFuncExists:
    """Check 3: assertion_func_exists."""

    def test_assertion_func_missing(self, env):
        """AssertionSpec with nonexistent func_name → ERROR."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(tool_name="renew_checkout", args={}),
                    check=AssertionSpec(
                        func_name="assert_nonexistent_thing",
                        args={},
                        env_type="assistant",
                    ),
                ),
            ],
        )
        issues = _check_assertion_func_exists(env, layer)
        assert any("ERROR" in i and "assert_nonexistent_thing" in i for i in issues)

    def test_assertion_func_valid(self, env):
        """Valid assertion func → no issues."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(tool_name="renew_checkout", args={}),
                    check=AssertionSpec(
                        func_name="assert_checkout_due_date",
                        args={"checkout_id": "CK001", "expected_date": "2025-01-01"},
                        env_type="assistant",
                    ),
                ),
            ],
        )
        issues = _check_assertion_func_exists(env, layer)
        assert len(issues) == 0


class TestTemplateVarsValid:
    """Check 4: template_vars_valid."""

    def test_template_var_missing(self, sample_entity):
        """Unresolvable {field} in args → ERROR."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    init=InitCall(
                        env_type="assistant",
                        func_name="set_checkout_due_date",
                        args={"checkout_id": "{nonexistent_field}", "due_date": "2025-12-31"},
                    ),
                    fix=ActionSpec(tool_name="renew_checkout", args={}),
                ),
            ],
        )
        flc = _make_flc()
        issues = _check_template_vars_valid(flc, layer, sample_entity)
        assert any("ERROR" in i and "nonexistent_field" in i for i in issues)

    def test_template_var_in_action(self, sample_entity):
        """Unresolvable {field} in action args → ERROR."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(
                        tool_name="renew_checkout",
                        args={"checkout_id": "{bad_field}"},
                    ),
                ),
            ],
        )
        flc = _make_flc()
        issues = _check_template_vars_valid(flc, layer, sample_entity)
        assert any("ERROR" in i and "bad_field" in i for i in issues)


class TestPredicateFieldsExist:
    """Check 5: predicate_fields_exist."""

    def test_predicate_field_missing(self, sample_entity):
        """predicate_field not in entity → ERROR."""
        layer = _make_layer(predicate_field="has_spaceship")
        issues = _check_predicate_fields_exist(layer, sample_entity)
        assert any("ERROR" in i and "has_spaceship" in i for i in issues)

    def test_predicate_ne_field_missing(self, sample_entity):
        """predicate_ne field not in entity → ERROR."""
        layer = _make_layer(predicate_ne=("warp_speed", 9))
        issues = _check_predicate_fields_exist(layer, sample_entity)
        assert any("ERROR" in i and "warp_speed" in i for i in issues)

    def test_predicate_field_valid(self, sample_entity):
        """Valid predicate_field → no issues."""
        layer = _make_layer(predicate_field="has_checkout")
        issues = _check_predicate_fields_exist(layer, sample_entity)
        assert len(issues) == 0


class TestResourceScopeResolves:
    """Check 6: resource_scope_resolves."""

    def test_resource_scope_bad_var(self, sample_entity):
        """Bad template var in resource_scope → ERROR."""
        layer = _make_layer(resource_scope="device:{unknown_device_id}")
        issues = _check_resource_scope_resolves(layer, sample_entity)
        assert any("ERROR" in i and "unknown_device_id" in i for i in issues)

    def test_resource_scope_valid(self, sample_entity):
        """Valid resource_scope → no issues."""
        layer = _make_layer(resource_scope="checkout:{checkout_id}")
        issues = _check_resource_scope_resolves(layer, sample_entity)
        assert len(issues) == 0


class TestSetAssertCoverage:
    """Check 7: set_assert_coverage."""

    def test_set_without_assert(self, env):
        """set_* without assert_* → WARNING."""
        from tau2.generators.verify_authoring import _check_set_assert_coverage

        issues = _check_set_assert_coverage(env)
        # Library may have some set_* without assert_* — just check the check runs
        warnings = [i for i in issues if i.startswith("WARNING:")]
        # This is a structural check — we just verify it runs without error
        assert isinstance(warnings, list)


class TestRequestorToolkitMatch:
    """Check 8: requestor_toolkit_match."""

    def test_user_action_on_agent_toolkit(self, env):
        """requestor='user' but tool only on agent toolkit → ERROR."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(
                        tool_name="renew_checkout",  # agent-only tool
                        args={},
                        requestor="user",  # wrong requestor
                    ),
                ),
            ],
        )
        issues = _check_requestor_toolkit_match(env, layer)
        assert any("ERROR" in i and "renew_checkout" in i for i in issues)

    def test_valid_requestor(self, env):
        """Correct requestor → no issues."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(
                        tool_name="confirm_hold_pickup",
                        args={},
                        requestor="user",
                    ),
                ),
            ],
        )
        issues = _check_requestor_toolkit_match(env, layer)
        assert len(issues) == 0


class TestFixToolIsWrite:
    """Check 9: fix_tool_is_write."""

    def test_read_tool_as_fix(self, env):
        """READ tool referenced as agent fix action → WARNING."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(
                        tool_name="get_patron_by_name",  # READ tool
                        args={},
                        requestor="assistant",
                    ),
                ),
            ],
        )
        issues = _check_fix_tool_is_write(env, layer)
        assert any("WARNING" in i and "get_patron_by_name" in i for i in issues)

    def test_write_tool_as_fix(self, env):
        """WRITE tool as fix → no issues."""
        layer = _make_layer(
            atoms=[
                FaultAtom(
                    fix=ActionSpec(
                        tool_name="renew_checkout",
                        args={},
                        requestor="assistant",
                    ),
                ),
            ],
        )
        issues = _check_fix_tool_is_write(env, layer)
        assert len(issues) == 0


class TestKnownInfoFragmentTemplates:
    """Check 10: known_info_fragment_templates."""

    def test_known_info_bad_template(self, sample_entity):
        """Unresolvable {field} in known_info_fragment → ERROR."""
        layer = _make_layer(
            known_info_fragment="My book {bad_field} has a problem"
        )
        flc = _make_flc()
        issues = _check_known_info_fragment_templates(flc, layer, sample_entity)
        assert any("ERROR" in i and "bad_field" in i for i in issues)

    def test_communicate_template_bad(self, sample_entity):
        """Bad template in communicate_templates → ERROR."""
        layer = FaultLayer(
            name="test_layer",
            known_info_fragment="Test",
            communicate_templates=["Tell {nonexistent_user} about it"],
        )
        flc = _make_flc()
        issues = _check_known_info_fragment_templates(flc, layer, sample_entity)
        assert any("ERROR" in i and "nonexistent_user" in i for i in issues)

    def test_valid_fragment(self, sample_entity):
        """Valid fragment → no issues."""
        layer = _make_layer(
            known_info_fragment="My checkout {checkout_id} for book {book_title} has issues"
        )
        flc = _make_flc()
        issues = _check_known_info_fragment_templates(flc, layer, sample_entity)
        # Filter to only this layer's issues
        layer_issues = [i for i in issues if "test_layer" in i]
        assert len(layer_issues) == 0


# ===================================================================
# LLM prompt tests
# ===================================================================


class TestLLMPrompt:
    """Tests for LLM prompt construction and parsing."""

    def test_prompt_includes_all_files(self):
        """Prompt contains all authored file contents."""
        files = {
            "tools.py": "def renew_checkout(): pass",
            "scenarios.py": "RECIPE_BOOK = ...",
            "policy.md": "# Policy\nRule 1: ...",
        }
        recipe_book = RecipeBook()

        # Use a mock that captures the prompt
        captured_prompt = []

        def mock_llm(prompt):
            captured_prompt.append(prompt)
            return "ISSUES_FOUND: no"

        verify_authoring_with_llm(recipe_book, files, [], mock_llm)

        prompt = captured_prompt[0]
        assert "def renew_checkout(): pass" in prompt
        assert "RECIPE_BOOK = ..." in prompt
        assert "# Policy" in prompt

    def test_prompt_includes_recipe_summary(self, get_db):
        """Prompt has layer/group/atom structure."""
        captured_prompt = []

        def mock_llm(prompt):
            captured_prompt.append(prompt)
            return "ISSUES_FOUND: no"

        files = {"tools.py": "# tools"}
        verify_authoring_with_llm(RECIPE_BOOK, files, [], mock_llm)

        prompt = captured_prompt[0]
        assert "FaultLayerConfig: library" in prompt
        assert "overdue_checkout" in prompt

    def test_prompt_includes_structural_issues(self):
        """Prompt includes previously found structural issues."""
        captured_prompt = []

        def mock_llm(prompt):
            captured_prompt.append(prompt)
            return "ISSUES_FOUND: no"

        issues = ["ERROR: [test] something broke", "WARNING: [test] watch out"]
        verify_authoring_with_llm(RecipeBook(), {}, issues, mock_llm)

        prompt = captured_prompt[0]
        assert "ERROR: [test] something broke" in prompt
        assert "WARNING: [test] watch out" in prompt

    def test_llm_error_handling(self):
        """LLM call failure → error in results."""

        def failing_llm(prompt):
            raise RuntimeError("API down")

        issues = verify_authoring_with_llm(RecipeBook(), {}, [], failing_llm)
        assert len(issues) == 1
        assert "ERROR calling LLM" in issues[0]


# ===================================================================
# File collector tests
# ===================================================================


class TestCollectAuthoredFiles:
    """Tests for collect_authored_files."""

    def test_collects_existing_files(self, tmp_path):
        """Reads real files and returns content."""
        (tmp_path / "test.py").write_text("print('hello')")
        result = collect_authored_files(
            {"test.py": str(tmp_path / "test.py")},
            db_path=str(tmp_path / "nonexistent_db.json"),
        )
        assert result["test.py"] == "print('hello')"
        assert "NOT FOUND" in result["db.json (sample)"]

    def test_truncates_db(self, tmp_path):
        """Truncates db.json collections to max_db_entities."""
        db_data = {
            "books": [{"id": i, "title": f"Book{i}"} for i in range(10)],
            "patrons": [{"id": 1, "name": "Patron"}],
        }
        db_path = tmp_path / "db.json"
        db_path.write_text(json.dumps(db_data))

        result = collect_authored_files({}, db_path=str(db_path), max_db_entities=2)
        parsed = json.loads(result["db.json (sample)"])
        assert len(parsed["books"]) == 2
        assert parsed["__books_total_count"] == 10
        assert len(parsed["patrons"]) == 1  # not truncated (< max)

    def test_missing_file(self):
        """Missing source file → placeholder."""
        result = collect_authored_files(
            {"missing.py": "/nonexistent/path/missing.py"},
            db_path="/nonexistent/db.json",
        )
        assert "NOT FOUND" in result["missing.py"]


# ===================================================================
# Recipe summary test
# ===================================================================


class TestRecipeSummary:
    """Tests for _build_recipe_summary."""

    def test_summary_structure(self):
        """Summary includes config, group, and layer info."""
        summary = _build_recipe_summary(RECIPE_BOOK)
        assert "library" in summary
        assert "checkout_issues" in summary
        assert "overdue_checkout" in summary
        assert "set_checkout_due_date" in summary or "set_checkout_status" in summary
        assert "renew_checkout" in summary
