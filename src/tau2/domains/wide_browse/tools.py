"""Tool functions for the Wide Browse domain.

Each function accepts ``db: dict`` as its first parameter. The ``db`` arg is
hidden from the agent's tool schema and injected at call time by
``DepgraphToolEnv.update_tool_args``.

Tool functions read and mutate ``db`` directly — this is the concrete
implementation of what the graph contract models abstractly in effects_world.
"""

from __future__ import annotations

from typing import Literal


# ---------------------------------------------------------------------------
# Page content templates (keyed by page_type × site_category)
# ---------------------------------------------------------------------------

_PAGE_CONTENT: dict[tuple[str, str], str] = {
    ("home", "travel"): (
        "Welcome to FlightSearch.com\n"
        "Find the best deals on flights worldwide.\n"
        "Use the search form to get started."
    ),
    ("home", "jobs"): (
        "Welcome to JobBoard.com\n"
        "Search thousands of job listings.\n"
        "Enter your keywords and location to begin."
    ),
    ("home", "shopping"): (
        "Welcome to ShopCompare.com\n"
        "Compare prices across retailers.\n"
        "Browse categories or search for products."
    ),
    ("home", "research"): (
        "Welcome to InfoHub.com\n"
        "Your source for articles, profiles, and data.\n"
        "Navigate to the content you need."
    ),
    ("home", "real_estate"): (
        "Welcome to PropertySearch.com\n"
        "Find homes, apartments, and commercial listings.\n"
        "Search by location, price, or property type."
    ),
    ("search_form", "travel"): (
        "Flight Search Form\n"
        "Fields: Origin, Destination, Date, Passengers, Cabin Class\n"
        "Filters: Stops, Airlines, Price Range, Times"
    ),
    ("search_form", "jobs"): (
        "Job Search Form\n"
        "Fields: Keywords, Location\n"
        "Filters: Experience Level, Salary Range, Remote, Date Posted"
    ),
    ("search_form", "real_estate"): (
        "Property Search Form\n"
        "Fields: Location, Property Type, Date Available\n"
        "Filters: Price Range, Bedrooms, Bathrooms, Square Footage"
    ),
    ("results_list", "travel"): (
        "Flight Results (12 found)\n"
        "1. EasyJet - 6:10 AM → 8:55 AM - 2h 45m - Nonstop - $203\n"
        "2. RyanAir - 9:30 AM → 12:15 PM - 2h 45m - Nonstop - $178\n"
        "3. TAP Air - 7:00 AM → 11:30 AM - 4h 30m - 1 stop - $245\n"
        "4. British Airways - 2:15 PM → 4:55 PM - 2h 40m - Nonstop - $312\n"
        "5. Vueling - 11:45 AM → 2:30 PM - 2h 45m - Nonstop - $189"
    ),
    ("results_list", "jobs"): (
        "Job Results (24 found)\n"
        "1. Personal Trainer - Bay Club Corte Madera - San Francisco, CA - $28-35/hr\n"
        "2. Fitness Coach - EXOS - San Francisco, CA - $30-40/hr\n"
        "3. Group Fitness Instructor - 24 Hour Fitness - Daly City, CA - $25-32/hr\n"
        "4. Strength Coach - Equinox - San Francisco, CA - $35-50/hr\n"
        "5. Yoga Instructor - CorePower - San Francisco, CA - $22-30/hr"
    ),
    ("results_list", "shopping"): (
        "Product Results (8 found)\n"
        "1. Apple Mac Mini M4 - $599 - Apple Store\n"
        "2. Apple Mac Mini M4 Pro - $1,399 - Amazon\n"
        "3. Apple Mac Mini M4 - $579 - Best Buy\n"
        "4. Apple Mac Mini M4 16GB - $649 - B&H Photo"
    ),
    ("results_list", "real_estate"): (
        "Property Results (6 found)\n"
        "1. 1010 Baywood Dr - 3 bed / 2 bath - $1,250,000 - 1,850 sqft\n"
        "2. 2045 Oak Lane - 4 bed / 3 bath - $1,475,000 - 2,200 sqft\n"
        "3. 890 Maple Ave - 2 bed / 1 bath - $875,000 - 1,100 sqft"
    ),
    ("detail", "jobs"): (
        "Job Detail: Personal Trainer at Bay Club Corte Madera\n"
        "Location: 5000 Paradise Dr, Corte Madera, CA 94925\n"
        "Pay: $28-35/hr depending on experience\n"
        "Certifications: NASM, ACE, or ACSM required\n"
        "Apply: https://bayclub.com/careers/trainer-123\n"
        "Hiring Manager: Sarah Chen - sarah.chen@bayclub.com"
    ),
    ("detail", "real_estate"): (
        "Property Detail: 1010 Baywood Dr\n"
        "Type: Single Family Home\n"
        "Bedrooms: 3 | Bathrooms: 2\n"
        "Square Footage: 1,850 | Lot Size: 5,200 sqft\n"
        "Year Built: 1978\n"
        "Zestimate: $1,280,000\n"
        "Last Sold: 2019 for $985,000\n"
        "HOA: None"
    ),
    ("detail", "shopping"): (
        "Product Detail: Apple Mac Mini M4\n"
        "Price: $599.00\n"
        "Processor: Apple M4 chip\n"
        "Memory: 16GB unified\n"
        "Storage: 256GB SSD\n"
        "Rating: 4.7/5 (234 reviews)\n"
        "Availability: In Stock"
    ),
    ("detail", "research"): (
        "Article: Bitcoin ETF Approval Impact\n"
        "Author: John Smith\n"
        "Published: January 15, 2024\n"
        "Content: The approval of spot Bitcoin ETFs has significantly...\n"
        "Tags: cryptocurrency, ETF, regulation"
    ),
}

_SEARCH_RESULTS: dict[str, str] = {
    "find_site": (
        "Search Results:\n"
        "1. FlightSearch.com - Compare flight deals\n"
        "2. Kayak.com - Search flights, hotels, rental cars\n"
        "3. Google Flights - Find cheap flights"
    ),
    "find_alternative": (
        "Search Results:\n"
        "1. Alternative site found: mirror.example.com\n"
        "2. Cached version available via web archive\n"
        "3. Similar content at related-site.com"
    ),
    "error_recovery": (
        "Search Results:\n"
        "1. Alternative URL found: alt.example.com/content\n"
        "2. API endpoint available: api.example.com/v2/data\n"
        "3. Cached copy at cache.example.com"
    ),
    "verify_info": (
        "Search Results:\n"
        "1. Verified: information matches official source\n"
        "2. Cross-reference found at secondary source"
    ),
}

_ERROR_MESSAGES: dict[str, str] = {
    "page_not_found": "Error 404: Page Not Found. The requested URL could not be located.",
    "paywall": "Access Restricted: This content requires a subscription or login.",
    "blocked": "Error 403: Access Denied. Your request has been blocked.",
    "timeout": "Error: Connection timed out. The server did not respond.",
    "rate_limited": "Error 429: Too Many Requests. Please try again later.",
}


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def navigate(db: dict, target: Literal[
    "site_home", "search_page", "results_page",
    "detail_page", "next_page", "alternative_url",
]) -> str:
    """Navigate to a page in the browser.

    Args:
        target: Where to navigate — one of: site_home, search_page,
                results_page, detail_page, next_page, alternative_url.
    """
    site_category = db.get("task.site_category", "research")

    if target == "site_home":
        behavior = db.get("site.load_behavior", "normal")
        if behavior != "normal" and not db.get("error.encountered", False):
            db["error.encountered"] = True
            db["error.type"] = behavior
            db["nav.page_type"] = "error"
            db["nav.page_loaded"] = False
            return _ERROR_MESSAGES.get(behavior, f"Error: {behavior}")

        db["nav.on_target_site"] = True
        db["nav.page_type"] = "home"
        db["nav.page_loaded"] = True
        content = _PAGE_CONTENT.get(("home", site_category), "Home page loaded.")
        return f"Navigated to site home.\n\n{content}"

    if target == "search_page":
        db["nav.page_type"] = "search_form"
        db["nav.page_loaded"] = True
        db["content.structure_known"] = False
        db["content.text_extracted"] = False
        content = _PAGE_CONTENT.get(("search_form", site_category), "Search form loaded.")
        return f"Navigated to search page.\n\n{content}"

    if target == "results_page":
        db["nav.page_type"] = "results_list"
        db["nav.page_loaded"] = True
        db["content.structure_known"] = False
        db["content.text_extracted"] = False
        items_found = db.get("content.items_found", "few")
        content = _PAGE_CONTENT.get(("results_list", site_category), "Results page loaded.")
        return f"Navigated to results page. Items: {items_found}.\n\n{content}"

    if target == "detail_page":
        behavior = db.get("site.detail_behavior", "normal")
        if behavior != "normal" and not db.get("error.encountered", False):
            db["error.encountered"] = True
            db["error.type"] = behavior
            db["nav.page_type"] = "error"
            db["nav.page_loaded"] = False
            return _ERROR_MESSAGES.get(behavior, f"Error: {behavior}")

        db["nav.page_type"] = "detail"
        db["nav.page_loaded"] = True
        db["content.structure_known"] = False
        db["content.text_extracted"] = False
        content = _PAGE_CONTENT.get(("detail", site_category), "Detail page loaded.")
        return f"Navigated to detail page.\n\n{content}"

    if target == "next_page":
        # pages_visited tracks total results pages seen (first page + next = 2)
        db["nav.pages_visited"] = 2
        db["content.structure_known"] = False
        db["content.text_extracted"] = False
        content = _PAGE_CONTENT.get(("results_list", site_category), "Next page loaded.")
        return f"Navigated to page 2.\n\n{content}"

    if target == "alternative_url":
        # Recovery: figure out which error to clear based on current state
        if db.get("site.load_behavior", "normal") != "normal":
            db["site.load_behavior"] = "normal"
            db["error.recovered"] = True
            db["nav.on_target_site"] = True
            db["nav.page_type"] = "home"
            db["nav.page_loaded"] = True
            content = _PAGE_CONTENT.get(("home", site_category), "Home page loaded.")
            return f"Recovered via alternative URL. Site loaded.\n\n{content}"

        if db.get("site.detail_behavior", "normal") != "normal":
            db["site.detail_behavior"] = "normal"
            db["error.recovered"] = True
            db["nav.page_type"] = "detail"
            db["nav.page_loaded"] = True
            db["content.structure_known"] = False
            db["content.text_extracted"] = False
            content = _PAGE_CONTENT.get(("detail", site_category), "Detail page loaded.")
            return f"Recovered via alternative URL. Detail page loaded.\n\n{content}"

        return "Error: no recovery target identified."

    return f"Unknown navigation target: {target}"


def computer(
    db: dict,
    action: Literal["click", "type", "scroll", "press_key", "select_all"],
    target: Literal[
        "search_button", "result_item", "next_page_btn",
        "filter_option", "form_field", "nav_link", "close_popup",
    ] = "form_field",
    text: str = "",
) -> str:
    """Interact with page elements in the browser.

    Args:
        action: The interaction type — click, type, scroll, press_key, or select_all.
        target: The page element to interact with.
        text: Text to type (only used when action is "type").
    """
    page_type = db.get("nav.page_type", "blank")

    if action == "type" and target == "form_field":
        if page_type != "search_form":
            return "Error: not on a form page."
        if text == "primary_value":
            db["form.primary_filled"] = True
            return "Typed primary search value into form field."
        if text == "secondary_value":
            db["form.secondary_filled"] = True
            return "Typed secondary search value into form field."
        if text == "date_value":
            db["form.date_filled"] = True
            return "Typed date value into form field."
        return f"Typed '{text}' into form field."

    if action == "click" and target == "search_button":
        if not db.get("form.primary_filled") or not db.get("form.secondary_filled"):
            return "Error: required form fields not filled."
        db["form.submitted"] = True
        return "Clicked search button. Form submitted."

    if action == "click" and target == "filter_option":
        db["form.filters_applied"] = True
        return "Applied filter option."

    if action == "click" and target == "result_item":
        return "Clicked on result item."

    if action == "click" and target == "next_page_btn":
        return "Clicked next page button."

    if action == "scroll":
        return "Scrolled page."

    if action == "press_key":
        return "Pressed key."

    if action == "select_all":
        return "Selected all text."

    return f"Performed {action} on {target}."


def read_page(
    db: dict,
    filter: Literal["all", "interactive"] = "all",
) -> str:
    """Read the page structure and identify elements.

    Args:
        filter: What to read — "all" for full structure, "interactive" for
                buttons, links, and form fields only.
    """
    page_type = db.get("nav.page_type", "blank")
    site_category = db.get("task.site_category", "research")

    if page_type == "error":
        error_type = db.get("error.type", "unknown")
        return (
            f"Error page detected.\n"
            f"Error type: {error_type}\n"
            f"Message: {_ERROR_MESSAGES.get(error_type, 'Unknown error')}\n"
            f"Elements: [back_button] [retry_button] [search_bar]"
        )

    if filter == "interactive" and page_type == "search_form":
        db["content.structure_known"] = True
        return (
            "Interactive elements on search form:\n"
            "- input[ref=field_1] 'Primary search field' (empty)\n"
            "- input[ref=field_2] 'Secondary search field' (empty)\n"
            "- input[ref=field_3] 'Date field' (empty)\n"
            "- button[ref=search_btn] 'Search'\n"
            "- dropdown[ref=filter_1] 'Filter options'\n"
            "- dropdown[ref=filter_2] 'Sort by'"
        )

    db["content.structure_known"] = True
    content = _PAGE_CONTENT.get((page_type, site_category), f"{page_type} page structure.")
    return (
        f"Page structure ({page_type}):\n"
        f"Content: {content}\n"
        f"Elements: [nav_bar] [main_content] [sidebar] [footer]"
    )


def get_page_text(db: dict, extract_items: bool = False) -> str:
    """Extract the full text content of the current page.

    Args:
        extract_items: When True, also extract structured item data from the
                       page (sets items_extracted / detail_extracted).
                       When False, only extract raw text.
    """
    page_type = db.get("nav.page_type", "blank")
    site_category = db.get("task.site_category", "research")

    if not db.get("nav.page_loaded", False):
        return "Error: page not loaded."

    db["content.text_extracted"] = True

    if extract_items:
        requires_detail = db.get("task.requires_detail", False)
        requires_form = db.get("task.requires_form", False)

        if page_type == "detail":
            db["content.detail_extracted"] = True
            db["content.items_extracted"] = "complete"
        elif page_type == "results_list":
            db["content.items_extracted"] = "partial" if requires_detail else "complete"
        elif not requires_form and not requires_detail:
            db["content.items_extracted"] = "complete"
        elif not requires_form and requires_detail:
            db["content.items_extracted"] = "partial"

    content = _PAGE_CONTENT.get((page_type, site_category), f"Text content of {page_type} page.")
    return content


def search_web(
    db: dict,
    query_type: Literal["find_site", "find_alternative", "error_recovery", "verify_info"],
) -> str:
    """Search the web for information.

    Args:
        query_type: The intent of the search — find_site, find_alternative,
                    error_recovery, or verify_info.
    """
    if query_type == "error_recovery":
        db["error.alternative_found"] = True

    return _SEARCH_RESULTS.get(query_type, "No results found.")


def form_input(
    db: dict,
    field: Literal["primary", "secondary", "date", "filter_1", "filter_2"],
    value: Literal["value_a", "value_b", "value_c"] = "value_a",
) -> str:
    """Set a value on a form field using accessibility tree reference.

    Args:
        field: Which form field to fill.
        value: The value to set.
    """
    if db.get("nav.page_type") != "search_form":
        return "Error: not on a form page."

    if field == "primary":
        db["form.primary_filled"] = True
        return f"Set primary field to {value}."
    if field == "secondary":
        db["form.secondary_filled"] = True
        return f"Set secondary field to {value}."
    if field == "date":
        db["form.date_filled"] = True
        return f"Set date field to {value}."
    if field in ("filter_1", "filter_2"):
        db["form.filters_applied"] = True
        return f"Set {field} to {value}."

    return f"Unknown field: {field}"


def find(
    db: dict,
    target: Literal["links", "buttons", "form_fields", "data_elements", "navigation"],
) -> str:
    """Search for specific elements on the current page.

    Args:
        target: What type of elements to find — links, buttons, form_fields,
                data_elements, or navigation.
    """
    if target == "data_elements":
        db["results.compiled"] = True
        items = db.get("content.items_extracted", "none")
        return f"Found data elements. Compilation status: ready. Items extracted: {items}."

    return f"Found {target} on the page."


def fetch_url(
    db: dict,
    target: Literal["current_page", "detail_url", "api_endpoint"],
) -> str:
    """Fetch content from a URL via HTTP.

    Args:
        target: What to fetch — current_page, detail_url, or api_endpoint.
    """
    behavior = db.get("site.fetch_behavior", "normal")

    if behavior != "normal" and not db.get("error.encountered", False):
        db["error.encountered"] = True
        db["error.type"] = behavior
        return _ERROR_MESSAGES.get(behavior, f"Error: {behavior}")

    if target == "api_endpoint" and db.get("site.fetch_behavior") != "normal":
        # Recovery path
        db["site.fetch_behavior"] = "normal"
        db["error.recovered"] = True
        db["content.text_extracted"] = True
        return "Fetched content via alternative API endpoint."

    db["content.text_extracted"] = True
    page_type = db.get("nav.page_type", "blank")
    site_category = db.get("task.site_category", "research")
    content = _PAGE_CONTENT.get((page_type, site_category), "Fetched page content.")
    return f"Fetched URL content.\n\n{content}"


def submit_result(db: dict) -> str:
    """Submit the collected structured results."""
    if not db.get("results.compiled", False):
        return "Error: results not compiled yet."

    db["results.submitted"] = True
    items = db.get("content.items_extracted", "none")
    return f"Results submitted successfully. Items: {items}."


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS: dict[str, callable] = {
    "navigate": navigate,
    "computer": computer,
    "read_page": read_page,
    "get_page_text": get_page_text,
    "search_web": search_web,
    "form_input": form_input,
    "find": find,
    "fetch_url": fetch_url,
    "submit_result": submit_result,
}
