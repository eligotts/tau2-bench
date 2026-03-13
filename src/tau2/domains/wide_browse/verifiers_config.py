"""Verifiers configuration for the Wide Browse domain.

Provides the system prompt and task prompt factory used by
``compile_for_verifiers`` to produce DepgraphTaskConfig objects.
"""

from __future__ import annotations

from tau2.generators.depgraph.types import GraphContractSpec, TaskIntent

SYSTEM_PROMPT = """\
You are a browser automation assistant. You complete web research and data \
extraction tasks by navigating websites, filling forms, reading page content, \
and submitting structured results.

You have access to the following tools:

- navigate(target): Navigate to a page. Targets: site_home, search_page, \
results_page, detail_page, next_page, alternative_url.
- computer(action, target, text): Interact with page elements. Actions: \
click, type, scroll, press_key, select_all. Targets: search_button, \
result_item, next_page_btn, filter_option, form_field, nav_link, close_popup.
- read_page(filter): Read page structure. Filter: "all" or "interactive".
- get_page_text(): Extract full text content of the current page.
- search_web(query_type): Search the web. Types: find_site, \
find_alternative, error_recovery, verify_info.
- form_input(field, value): Set a form field value. Fields: primary, \
secondary, date, filter_1, filter_2.
- find(target): Search for elements on the page. Targets: links, buttons, \
form_fields, data_elements, navigation.
- fetch_url(target): Fetch content from a URL. Targets: current_page, \
detail_url, api_endpoint.
- submit_result(): Submit the collected structured results.

Important guidelines:
- Always navigate to the target site before interacting with it.
- Read the page structure to understand available elements before filling forms.
- If you encounter an error (404, paywall, blocked), search for alternatives \
and try to recover.
- After extracting the data you need, compile results and submit them.
- Call submit_result() when you have gathered the requested information.
"""

_SITE_NAMES = {
    "travel": "a flight search website",
    "jobs": "a job listing website",
    "shopping": "a product comparison website",
    "research": "an information research website",
    "real_estate": "a real estate listing website",
}

_TASK_DESCRIPTIONS = {
    "search": "search for {detail} using the site's search form, review the results",
    "direct_extract": "navigate to the site and extract the relevant {detail} directly from the page",
    "multi_page": "browse the site, find the items of interest, and visit detail pages to gather complete information about {detail}",
}

_SITE_DETAILS = {
    "travel": "flights matching the given criteria",
    "jobs": "job listings matching the search criteria",
    "shopping": "products and their prices",
    "research": "articles and information",
    "real_estate": "property listings matching the criteria",
}


def task_prompt_factory(task: TaskIntent, contract: GraphContractSpec) -> str:
    """Generate a natural-language task prompt from a TaskIntent."""
    # Extract task metadata from start_world
    start_map = {effect.path: effect.set for effect in task.start_world}

    task_type = start_map.get("task.type", "search")
    site_category = start_map.get("task.site_category", "research")
    requires_detail = start_map.get("task.requires_detail", False)
    requires_form = start_map.get("task.requires_form", False)

    site_name = _SITE_NAMES.get(site_category, "a website")
    detail = _SITE_DETAILS.get(site_category, "the requested information")
    task_desc = _TASK_DESCRIPTIONS.get(task_type, "complete the task on the site")
    task_desc = task_desc.format(detail=detail)

    parts = [f"Go to {site_name} and {task_desc}."]

    if requires_form:
        parts.append(
            "Fill in the required search fields and submit the form to get results."
        )

    if requires_detail:
        parts.append(
            "Visit the detail page for the most relevant result to gather complete information."
        )

    parts.append(
        "Once you have the information, compile the data elements and submit your results."
    )

    # Mention error scenarios if the seed injects errors
    load_behavior = start_map.get("site.load_behavior", "normal")
    detail_behavior = start_map.get("site.detail_behavior", "normal")
    fetch_behavior = start_map.get("site.fetch_behavior", "normal")

    if load_behavior != "normal" or detail_behavior != "normal" or fetch_behavior != "normal":
        parts.append(
            "Note: you may encounter errors or access issues. "
            "If a page fails to load, search for alternatives and try to recover."
        )

    return " ".join(parts)
