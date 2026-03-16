"""Three formal bridges: BFS tasks → synthetic browser environment.

Bridge 1: verify_start_state  — start_world → browser initial DB state
Bridge 2: generate_description — goal_world → natural-language task prompt
Bridge 3: check_goal_world    — goal_world → rubric scoring

These bridges ensure the synthetic browser environment faithfully preserves
the BFS "correct by construction" guarantee.
"""

from __future__ import annotations

from typing import Any, Callable

from tau2.generators.depgraph.types import WorldPredicateSpec


# ---------------------------------------------------------------------------
# Bridge 1: verify_start_state
# ---------------------------------------------------------------------------

# Each checker takes (db_value, expected_value) and returns True if they match.
START_FIELD_CHECKS: dict[str, Callable[[Any, Any], bool]] = {
    # Task metadata (config fields, set by seed)
    "task.site_category":    lambda v, exp: v == exp,
    "task.type":             lambda v, exp: v == exp,
    "task.requires_form":    lambda v, exp: v == exp,
    "task.requires_detail":  lambda v, exp: v == exp,

    # Site behavior (config fields, set by seed)
    "site.load_behavior":    lambda v, exp: v == exp,
    "site.detail_behavior":  lambda v, exp: v == exp,
    "site.fetch_behavior":   lambda v, exp: v == exp,

    # Content config
    "content.items_found":   lambda v, exp: v == exp,

    # Navigation state (must match defaults at start)
    "nav.on_target_site":    lambda v, exp: v == exp,
    "nav.page_type":         lambda v, exp: v == exp,
    "nav.page_loaded":       lambda v, exp: v == exp,
    "nav.pages_visited":     lambda v, exp: v == exp,

    # Form state
    "form.primary_filled":   lambda v, exp: v == exp,
    "form.secondary_filled": lambda v, exp: v == exp,
    "form.date_filled":      lambda v, exp: v == exp,
    "form.filters_applied":  lambda v, exp: v == exp,
    "form.submitted":        lambda v, exp: v == exp,

    # Content / extraction state
    "content.structure_known":  lambda v, exp: v == exp,
    "content.text_extracted":   lambda v, exp: v == exp,
    "content.items_extracted":  lambda v, exp: v == exp,
    "content.detail_extracted": lambda v, exp: v == exp,

    # Results state
    "results.compiled":      lambda v, exp: v == exp,
    "results.submitted":     lambda v, exp: v == exp,

    # Error state
    "error.encountered":     lambda v, exp: v == exp,
    "error.type":            lambda v, exp: v == exp,
    "error.alternative_found": lambda v, exp: v == exp,
    "error.recovered":       lambda v, exp: v == exp,
}


def verify_start_state(
    start_world: dict[str, Any],
    db: dict[str, Any],
) -> list[str]:
    """Verify that the DB matches every start_world field.

    Returns a list of violation messages (empty = all good).
    Raises on unmapped fields to force explicit bridge updates.
    """
    violations: list[str] = []

    for path, expected in start_world.items():
        checker = START_FIELD_CHECKS.get(path)
        if checker is None:
            violations.append(
                f"UNMAPPED field '{path}' — add it to START_FIELD_CHECKS"
            )
            continue

        actual = db.get(path)
        if not checker(actual, expected):
            violations.append(
                f"{path}: expected {expected!r}, got {actual!r}"
            )

    return violations


# ---------------------------------------------------------------------------
# Bridge 2: generate_description_from_goal
# ---------------------------------------------------------------------------

_SITE_NAMES: dict[str, tuple[str, str]] = {
    "travel":      ("FlightSearch.com", "flightsearch.com"),
    "jobs":        ("JobBoard.com", "jobboard.com"),
    "shopping":    ("ShopCompare.com", "shopcompare.com"),
    "research":    ("InfoHub.com", "infohub.com"),
    "real_estate": ("PropertySearch.com", "propertysearch.com"),
}

_SEARCH_DETAIL: dict[str, str] = {
    "travel":      "flights matching your criteria",
    "jobs":        "job listings matching your search",
    "shopping":    "products and their prices",
    "research":    "articles and relevant information",
    "real_estate": "property listings matching your criteria",
}


def _goal_set(goal_world: list[WorldPredicateSpec]) -> dict[str, Any]:
    """Convert goal_world predicates to a {path: value} dict for eq checks."""
    return {
        pred.path: pred.value
        for pred in goal_world
        if pred.op == "eq"
    }


def generate_description_from_goal(
    goal_world: list[WorldPredicateSpec],
    start_world: dict[str, Any],
    task_id: str = "",
) -> str:
    """Generate a task description driven by goal_world conditions.

    Each goal condition maps to a required instruction fragment.
    The description is composed from these fragments rather than
    from ad-hoc category templates.
    """
    goals = _goal_set(goal_world)
    site_category = start_world.get("task.site_category", "research")
    site_name, site_domain = _SITE_NAMES.get(
        site_category, ("the website", "example.com")
    )
    detail = _SEARCH_DETAIL.get(site_category, "the requested information")

    parts: list[str] = []

    # --- Opening: always navigate to the site ---
    parts.append(f"Go to {site_name} ({site_domain}).")

    # --- Error warning: if goal expects error encounter + recovery ---
    if goals.get("error.encountered") is True:
        error_type = start_world.get("site.load_behavior", "normal")
        if error_type == "normal":
            error_type = start_world.get("site.detail_behavior", "normal")
        if error_type == "normal":
            error_type = start_world.get("site.fetch_behavior", "normal")
        parts.append(
            f"You may encounter an error ({error_type}). "
            "If the page fails to load, search for alternatives and try to recover."
        )

    # --- Form instructions: only if goal requires form fields ---
    needs_form = (
        goals.get("form.primary_filled") is True
        or goals.get("form.secondary_filled") is True
        or goals.get("form.submitted") is True
    )
    if needs_form:
        form_parts = ["Navigate to the search form"]
        if goals.get("form.primary_filled") is True:
            form_parts.append("fill in the primary search field")
        if goals.get("form.secondary_filled") is True:
            form_parts.append("fill in the secondary search field")
        if goals.get("form.date_filled") is True:
            form_parts.append("set the date")
        if goals.get("form.filters_applied") is True:
            form_parts.append("apply relevant filters")
        parts.append(", ".join(form_parts) + ", and submit the search.")

    # --- Content extraction ---
    items_goal = goals.get("content.items_extracted")
    detail_goal = goals.get("content.detail_extracted")

    if items_goal == "complete" and detail_goal is True:
        parts.append(
            f"Review the search results, then visit the detail page for the most "
            f"relevant result to gather complete information about {detail}."
        )
    elif items_goal == "complete":
        parts.append(
            f"Review the results and extract complete information about {detail}."
        )
    elif items_goal == "partial" and detail_goal is True:
        parts.append(
            f"Browse the results and visit detail pages to gather information about {detail}."
        )
    elif items_goal == "partial":
        parts.append(
            f"Browse the results and extract what information you can about {detail}."
        )

    # --- Pagination: if goal expects multiple pages ---
    if goals.get("nav.pages_visited") is not None:
        pages = goals.get("nav.pages_visited")
        if isinstance(pages, int) and pages >= 2:
            parts.append("Check additional pages of results if available.")

    # --- Close: compile and submit ---
    if goals.get("results.submitted") is True:
        parts.append(
            "Once you have the information, compile the data elements and submit your results."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Bridge 3: check_goal_world
# ---------------------------------------------------------------------------

def _visited_page_type(db: dict[str, Any], expected: str) -> bool:
    """Check if the expected page type was visited (or is current)."""
    return db.get("nav.page_type") == expected


def _items_extracted_check(db: dict[str, Any], expected: str) -> bool:
    """Check items_extracted with ordered comparison.

    'complete' satisfies both 'complete' and 'partial' goals.
    """
    actual = db.get("content.items_extracted", "none")
    if expected == "none":
        return actual == "none"
    if expected == "partial":
        return actual in ("partial", "complete")
    if expected == "complete":
        return actual == "complete"
    return actual == expected


# Each checker takes (db, expected_value) and returns bool.
GOAL_CHECK_MAP: dict[str, Callable[[dict[str, Any], Any], bool]] = {
    # Navigation
    "nav.on_target_site":    lambda db, v: db.get("nav.on_target_site") == v,
    "nav.page_loaded":       lambda db, v: (
        db.get("nav.page_loaded") == v
        or (v is True and db.get("results.submitted") is True)
    ),
    "nav.page_type":         lambda db, v: _visited_page_type(db, v),
    "nav.pages_visited":     lambda db, v: db.get("nav.pages_visited", 0) >= v,

    # Form
    "form.primary_filled":   lambda db, v: db.get("form.primary_filled") == v,
    "form.secondary_filled": lambda db, v: db.get("form.secondary_filled") == v,
    "form.date_filled":      lambda db, v: db.get("form.date_filled") == v,
    "form.filters_applied":  lambda db, v: db.get("form.filters_applied") == v,
    "form.submitted":        lambda db, v: db.get("form.submitted") == v,

    # Content
    "content.structure_known":  lambda db, v: db.get("content.structure_known") == v,
    "content.text_extracted":   lambda db, v: db.get("content.text_extracted") == v,
    "content.items_extracted":  lambda db, v: _items_extracted_check(db, v),
    "content.detail_extracted": lambda db, v: db.get("content.detail_extracted") == v,

    # Results
    "results.compiled":      lambda db, v: db.get("results.compiled") == v,
    "results.submitted":     lambda db, v: db.get("results.submitted") == v,

    # Error
    "error.encountered":      lambda db, v: db.get("error.encountered") == v,
    "error.type":             lambda db, v: db.get("error.type") == v,
    "error.alternative_found": lambda db, v: db.get("error.alternative_found") == v,
    "error.recovered":        lambda db, v: db.get("error.recovered") == v,

    # Site config (these are set by seed but may appear in goal_world)
    "site.load_behavior":    lambda db, v: db.get("site.load_behavior") == v,
    "site.detail_behavior":  lambda db, v: db.get("site.detail_behavior") == v,
    "site.fetch_behavior":   lambda db, v: db.get("site.fetch_behavior") == v,
}


def check_goal_world(
    db: dict[str, Any],
    goal_world: list[WorldPredicateSpec],
) -> tuple[float, dict[str, bool]]:
    """Check every goal_world predicate against the DB.

    Returns (fraction_satisfied, per_condition_results).

    For conditions whose path is in GOAL_CHECK_MAP, uses the bridge checker.
    For unknown paths, falls back to direct equality on DB value.
    """
    if not goal_world:
        return 1.0, {}

    results: dict[str, bool] = {}
    passed = 0

    for pred in goal_world:
        key = f"{pred.path} {pred.op} {pred.value!r}"
        checker = GOAL_CHECK_MAP.get(pred.path)

        if checker is not None and pred.op == "eq":
            ok = checker(db, pred.value)
        elif pred.op == "eq":
            ok = db.get(pred.path) == pred.value
        elif pred.op == "neq":
            ok = db.get(pred.path) != pred.value
        elif pred.op == "gte":
            ok = (db.get(pred.path) or 0) >= pred.value
        elif pred.op == "gt":
            ok = (db.get(pred.path) or 0) > pred.value
        elif pred.op == "lte":
            ok = (db.get(pred.path) or 0) <= pred.value
        elif pred.op == "lt":
            ok = (db.get(pred.path) or 0) < pred.value
        else:
            ok = False

        results[key] = ok
        if ok:
            passed += 1

    return passed / len(goal_world), results


def data_quality_bonus(db: dict[str, Any]) -> float:
    """Bonus score for data quality indicators beyond goal predicates.

    Rewards:
    - Using get_page_text (text_extracted)
    - Reading page structure (structure_known)
    - Visiting detail pages (detail_extracted)
    - Complete item extraction
    """
    score = 0.0
    max_score = 4.0

    if db.get("content.text_extracted") is True:
        score += 1.0
    if db.get("content.structure_known") is True:
        score += 1.0
    if db.get("content.detail_extracted") is True:
        score += 1.0
    if db.get("content.items_extracted") == "complete":
        score += 1.0

    return score / max_score
