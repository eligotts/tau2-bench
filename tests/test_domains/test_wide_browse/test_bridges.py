"""Tests for the three formal bridges (BFS tasks → synthetic browser).

1. Exhaustive start bridge: all 408 tasks verify against their start_world
2. Description bridge: goal_world conditions produce matching keywords
3. Goal check bridge: simulated perfect agent scores ~1.0
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tau2.domains.wide_browse.bridges import (
    check_goal_world,
    data_quality_bonus,
    generate_description_from_goal,
    verify_start_state,
)
from tau2.generators.depgraph.types import WorldPredicateSpec


DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "tau2" / "domains" / "wide_browse"
TASK_SPECS_PATH = DATA_DIR / "task_specs.sampled.yaml"


def _load_tasks() -> list[dict]:
    """Load all sampled tasks from YAML."""
    with open(TASK_SPECS_PATH) as f:
        doc = yaml.safe_load(f)
    return doc["tasks"]


def _start_world_to_db(start_world_list: list[dict]) -> dict:
    """Convert start_world list-of-dicts to a flat DB dict."""
    return {item["path"]: item["set"] for item in start_world_list}


def _goal_world_to_preds(goal_world_list: list[dict]) -> list[WorldPredicateSpec]:
    """Convert goal_world list-of-dicts to WorldPredicateSpec objects."""
    return [
        WorldPredicateSpec(op=g.get("op", "eq"), path=g["path"], value=g["value"])
        for g in goal_world_list
    ]


# ---------------------------------------------------------------------------
# Bridge 1: verify_start_state
# ---------------------------------------------------------------------------


class TestVerifyStartState:
    """Every sampled task's start_world must pass verification."""

    @pytest.fixture(scope="class")
    def all_tasks(self):
        return _load_tasks()

    def test_all_tasks_pass(self, all_tasks):
        failures = []
        for task in all_tasks:
            db = _start_world_to_db(task["start_world"])
            violations = verify_start_state(db, db)
            if violations:
                failures.append((task["task_id"], violations))

        assert not failures, (
            f"{len(failures)} tasks failed start verification:\n"
            + "\n".join(
                f"  {tid}: {'; '.join(vs)}" for tid, vs in failures[:10]
            )
        )

    def test_detects_mismatch(self):
        """verify_start_state catches when DB doesn't match start_world."""
        start = {"nav.on_target_site": False, "nav.page_type": "blank"}
        db = {"nav.on_target_site": True, "nav.page_type": "blank"}
        violations = verify_start_state(start, db)
        assert len(violations) == 1
        assert "nav.on_target_site" in violations[0]

    def test_detects_unmapped_field(self):
        """New fields in start_world must be explicitly mapped."""
        start = {"nav.on_target_site": False, "totally.new.field": True}
        db = {"nav.on_target_site": False, "totally.new.field": True}
        violations = verify_start_state(start, db)
        assert any("UNMAPPED" in v for v in violations)


# ---------------------------------------------------------------------------
# Bridge 2: generate_description_from_goal
# ---------------------------------------------------------------------------


class TestGenerateDescription:
    """Goal conditions produce matching description keywords."""

    @pytest.fixture(scope="class")
    def all_tasks(self):
        return _load_tasks()

    def test_descriptions_contain_goal_keywords(self, all_tasks):
        """For each task, the description mentions keywords for each goal condition."""
        failures = []
        for task in all_tasks:
            start = _start_world_to_db(task["start_world"])
            goals = _goal_world_to_preds(task["goal_world"])
            desc = generate_description_from_goal(goals, start, task["task_id"])

            goal_set = {g.path: g.value for g in goals if g.op == "eq"}
            issues = []

            # Check key structural requirements appear in description
            if goal_set.get("form.submitted") is True:
                if "search" not in desc.lower() and "form" not in desc.lower():
                    issues.append("form.submitted=True but no search/form mention")

            if goal_set.get("content.detail_extracted") is True:
                if "detail" not in desc.lower():
                    issues.append("detail_extracted=True but no detail mention")

            if goal_set.get("results.submitted") is True:
                if "submit" not in desc.lower():
                    issues.append("results.submitted=True but no submit mention")

            if goal_set.get("error.encountered") is True:
                if "error" not in desc.lower() and "fail" not in desc.lower():
                    issues.append("error.encountered=True but no error mention")

            if issues:
                failures.append((task["task_id"], issues))

        assert not failures, (
            f"{len(failures)} tasks have description gaps:\n"
            + "\n".join(
                f"  {tid}: {'; '.join(iss)}" for tid, iss in failures[:10]
            )
        )

    def test_search_task_mentions_form(self):
        """A search task with form goals should mention form fields."""
        goals = [
            WorldPredicateSpec(path="form.primary_filled", value=True),
            WorldPredicateSpec(path="form.secondary_filled", value=True),
            WorldPredicateSpec(path="form.submitted", value=True),
            WorldPredicateSpec(path="results.submitted", value=True),
            WorldPredicateSpec(path="nav.on_target_site", value=True),
            WorldPredicateSpec(path="content.items_extracted", value="complete"),
        ]
        start = {"task.site_category": "travel", "task.type": "search"}
        desc = generate_description_from_goal(goals, start)
        assert "search" in desc.lower() or "form" in desc.lower()
        assert "submit" in desc.lower()

    def test_error_task_mentions_recovery(self):
        """A task with error goals should mention recovery."""
        goals = [
            WorldPredicateSpec(path="error.encountered", value=True),
            WorldPredicateSpec(path="error.recovered", value=True),
            WorldPredicateSpec(path="results.submitted", value=True),
            WorldPredicateSpec(path="nav.on_target_site", value=True),
        ]
        start = {
            "task.site_category": "travel",
            "site.load_behavior": "page_not_found",
        }
        desc = generate_description_from_goal(goals, start)
        assert "error" in desc.lower() or "fail" in desc.lower()


# ---------------------------------------------------------------------------
# Bridge 3: check_goal_world
# ---------------------------------------------------------------------------


class TestCheckGoalWorld:
    """Goal checking against DB state."""

    def test_perfect_search_task(self):
        """Simulated perfect agent for a search task scores 1.0."""
        goals = [
            WorldPredicateSpec(path="nav.on_target_site", value=True),
            WorldPredicateSpec(path="form.primary_filled", value=True),
            WorldPredicateSpec(path="form.secondary_filled", value=True),
            WorldPredicateSpec(path="form.submitted", value=True),
            WorldPredicateSpec(path="content.items_extracted", value="complete"),
            WorldPredicateSpec(path="results.compiled", value=True),
            WorldPredicateSpec(path="results.submitted", value=True),
        ]
        db = {
            "nav.on_target_site": True,
            "nav.page_type": "results_list",
            "nav.page_loaded": True,
            "form.primary_filled": True,
            "form.secondary_filled": True,
            "form.submitted": True,
            "content.items_extracted": "complete",
            "results.compiled": True,
            "results.submitted": True,
        }
        score, details = check_goal_world(db, goals)
        assert score == 1.0
        assert all(details.values())

    def test_partial_score(self):
        """Missing some goals gives partial score."""
        goals = [
            WorldPredicateSpec(path="nav.on_target_site", value=True),
            WorldPredicateSpec(path="results.submitted", value=True),
        ]
        db = {
            "nav.on_target_site": True,
            "results.submitted": False,
        }
        score, details = check_goal_world(db, goals)
        assert score == 0.5

    def test_items_extracted_complete_satisfies_partial(self):
        """'complete' satisfies a goal of 'partial'."""
        goals = [
            WorldPredicateSpec(path="content.items_extracted", value="partial"),
        ]
        db = {"content.items_extracted": "complete"}
        score, details = check_goal_world(db, goals)
        assert score == 1.0

    def test_error_recovery_task(self):
        """Error recovery goals check correctly."""
        goals = [
            WorldPredicateSpec(path="error.encountered", value=True),
            WorldPredicateSpec(path="error.alternative_found", value=True),
            WorldPredicateSpec(path="error.recovered", value=True),
            WorldPredicateSpec(path="site.load_behavior", value="normal"),
        ]
        db = {
            "error.encountered": True,
            "error.alternative_found": True,
            "error.recovered": True,
            "site.load_behavior": "normal",
        }
        score, details = check_goal_world(db, goals)
        assert score == 1.0

    def test_empty_goals(self):
        score, details = check_goal_world({}, [])
        assert score == 1.0
        assert details == {}


class TestDataQualityBonus:
    def test_full_quality(self):
        db = {
            "content.text_extracted": True,
            "content.structure_known": True,
            "content.detail_extracted": True,
            "content.items_extracted": "complete",
        }
        assert data_quality_bonus(db) == 1.0

    def test_no_quality(self):
        assert data_quality_bonus({}) == 0.0

    def test_partial_quality(self):
        db = {
            "content.text_extracted": True,
            "content.structure_known": True,
        }
        assert data_quality_bonus(db) == 0.5
