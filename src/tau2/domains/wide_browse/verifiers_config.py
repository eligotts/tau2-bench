"""Verifiers configuration for the Wide Browse domain.

Provides the system prompt and task prompt factory used by
``compile_for_verifiers`` to produce DepgraphTaskConfig objects.

The task prompt factory delegates to Bridge 2 (generate_description_from_goal)
so that descriptions are structurally driven by goal_world conditions rather
than ad-hoc category templates.
"""

from __future__ import annotations

from tau2.domains.wide_browse.bridges import generate_description_from_goal
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


def task_prompt_factory(task: TaskIntent, contract: GraphContractSpec) -> str:
    """Generate a natural-language task prompt from a TaskIntent.

    Delegates to Bridge 2 (generate_description_from_goal) which composes
    the description from goal_world conditions rather than category templates.
    """
    start_map = {effect.path: effect.set for effect in task.start_world}

    return generate_description_from_goal(
        goal_world=list(task.goal_world),
        start_world=start_map,
        task_id=task.task_id,
    )
