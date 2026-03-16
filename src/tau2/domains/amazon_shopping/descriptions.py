"""Task description generator for Amazon Shopping domain.

Turns a sampled task (start_world config + goal_world predicates)
and a TaskEntitySet into a natural-language instruction that tells
the agent what to do without revealing the exact action sequence.

The description must cover every goal_world predicate so the agent
knows what's expected. Non-monotonic predicates (page.*) are excluded.
"""

from __future__ import annotations

from typing import Any

from .entities import TaskEntitySet


# ---------------------------------------------------------------------------
# Goal-world predicate analysis
# ---------------------------------------------------------------------------

def _goal_has(goal_world: list[dict], path: str, value: Any = True) -> bool:
    """Check if a goal_world predicate exists with the given path and value."""
    for pred in goal_world:
        if pred["path"] == path and pred.get("value") == value:
            return True
    return False


def _goal_value(goal_world: list[dict], path: str) -> Any:
    """Get the value of a goal_world predicate, or None if not present."""
    for pred in goal_world:
        if pred["path"] == path:
            return pred.get("value")
    return None


# ---------------------------------------------------------------------------
# Description fragments — composed based on goal requirements
# ---------------------------------------------------------------------------

def _opening(entities: TaskEntitySet, entry_point: str) -> str:
    """First sentence: how to enter the site."""
    if entry_point == "category":
        cat = next((c for c in entities.categories if c.subcategories), None)
        cat_name = cat.name if cat else "Electronics"
        return (
            f"Go to Amazon.com and navigate to the {cat_name} category "
            f"from the main menu."
        )
    elif entry_point == "deals":
        return "Go to Amazon.com and navigate to Today's Deals."
    else:
        return f"Go to Amazon.com and search for \"{entities.search_query}\"."


def _filter_instructions(goal_world: list[dict], entities: TaskEntitySet) -> str | None:
    """Instructions for filtering/sorting, driven by goal predicates."""
    parts = []

    condition = _goal_value(goal_world, "filter.condition")
    if condition and condition != "none":
        parts.append(f"filter results to show only {condition.upper()} condition items")

    if _goal_has(goal_world, "filter.price_range", True):
        # Pick a reasonable price range from the product catalog
        if entities.products:
            mid = entities.products[len(entities.products) // 2].price_cents
            low = max(0, mid - 5000)
            high = mid + 5000
            parts.append(f"set a price range of ${low/100:.0f}–${high/100:.0f}")
        else:
            parts.append("set a price range filter")

    if _goal_has(goal_world, "filter.prime_only", True):
        parts.append("enable the Prime-only filter")

    sort = _goal_value(goal_world, "sort.applied")
    if sort and sort != "none":
        sort_labels = {
            "price_asc": "price: low to high",
            "price_desc": "price: high to low",
            "avg_review": "average customer review",
        }
        label = sort_labels.get(sort, sort)
        parts.append(f"sort by {label}")

    if not parts:
        return None
    return "Apply the following filters: " + ", ".join(parts) + "."


def _search_refinement_instructions(goal_world: list[dict]) -> str | None:
    if _goal_has(goal_world, "search.refined", True):
        return (
            "If the initial results don't match what you're looking for, "
            "refine your search query and try again."
        )
    return None


def _category_instructions(goal_world: list[dict], entities: TaskEntitySet) -> str | None:
    """Instructions for category browsing tasks."""
    if not _goal_has(goal_world, "category.read", True):
        return None
    cat = next((c for c in entities.categories if c.subcategories), None)
    cat_name = cat.name if cat else "the category"
    return (
        f"Browse the {cat_name} category listings and review the available products."
    )


def _deals_instructions(goal_world: list[dict], entities: TaskEntitySet) -> str | None:
    """Instructions for deal browsing tasks."""
    if not _goal_has(goal_world, "deals.read", True):
        return None
    return "Review the current deals and note the discount percentages and original prices."


def _results_instructions(goal_world: list[dict]) -> str | None:
    """Instructions for reading search results."""
    if not _goal_has(goal_world, "extract.results_read", True):
        return None
    return (
        "Read through the search results and note the product names, "
        "prices, ratings, and Prime eligibility for each listing."
    )


def _product_detail_instructions(
    goal_world: list[dict],
    entities: TaskEntitySet,
    config: dict[str, Any],
) -> str | None:
    """Instructions for visiting product detail pages."""
    # Count how many products need detail visits
    detail_products = []
    for i in range(1, 4):
        if _goal_has(goal_world, f"p{i}.detail_read", True):
            detail_products.append(i)

    if not detail_products:
        return None

    n = len(detail_products)
    products = entities.products

    if n == 1:
        p = products[0] if products else None
        name = p.name if p else "the product"
        return f"Click on {name} to open its product detail page and read the full details."
    elif n == 2:
        names = [products[i].name if i < len(products) else f"product #{i+1}" for i in range(2)]
        return (
            f"Open the detail pages for the following products and read their full "
            f"details:\n1. {names[0]}\n2. {names[1]}"
        )
    else:
        names = [products[i].name if i < len(products) else f"product #{i+1}" for i in range(n)]
        items = "\n".join(f"{i+1}. {name}" for i, name in enumerate(names))
        return (
            f"Open the detail pages for each of the following {n} products "
            f"and read their full details:\n{items}"
        )


def _shipping_instructions(
    goal_world: list[dict],
    entities: TaskEntitySet,
) -> str | None:
    """Instructions for checking shipping."""
    shipping_products = []
    for i in range(1, 4):
        if _goal_has(goal_world, f"p{i}.shipping_checked", True):
            shipping_products.append(i)

    if not shipping_products:
        return None

    zip_code = entities.zip_code
    if len(shipping_products) == 1:
        return (
            f"On the product detail page, check the shipping and delivery information "
            f"for ZIP code {zip_code}. Note the estimated delivery date and shipping cost."
        )
    else:
        return (
            f"For each product, check the shipping and delivery information "
            f"for ZIP code {zip_code}. Note the estimated delivery date and shipping cost."
        )


def _review_instructions(goal_world: list[dict]) -> str | None:
    """Instructions for reading reviews."""
    review_products = []
    for i in range(1, 4):
        if _goal_has(goal_world, f"p{i}.reviews_read", True):
            review_products.append(i)

    if not review_products:
        return None

    if len(review_products) == 1:
        return (
            "Read the customer reviews section. Note the overall sentiment, "
            "common praise, and any recurring complaints."
        )
    else:
        return (
            "For each product, read the customer reviews. Note the overall sentiment, "
            "the top positive and negative reviews, and any patterns across products."
        )


def _seller_instructions(goal_world: list[dict]) -> str | None:
    """Instructions for checking seller info."""
    seller_products = []
    for i in range(1, 3):
        if _goal_has(goal_world, f"p{i}.seller_checked", True):
            seller_products.append(i)

    if not seller_products:
        return None

    return (
        "Check the seller information: seller name, rating, feedback percentage, "
        "and whether it's fulfilled by Amazon."
    )


def _variant_instructions(goal_world: list[dict]) -> str | None:
    """Instructions for checking product variants."""
    if not _goal_has(goal_world, "p1.variant_checked", True):
        return None
    return (
        "Check the available product variants (size, color, storage options) "
        "and note any price differences between configurations."
    )


def _qa_instructions(goal_world: list[dict]) -> str | None:
    """Instructions for reading Q&A section."""
    qa_products = []
    for i in range(1, 3):
        if _goal_has(goal_world, f"p{i}.qa_read", True):
            qa_products.append(i)

    if not qa_products:
        return None

    if len(qa_products) == 1:
        return (
            "Read the Questions & Answers section on the product page. "
            "Look for answers about compatibility, sizing, and common concerns."
        )
    else:
        return (
            "For each product, check the Questions & Answers section for information "
            "about compatibility, sizing, and common buyer questions."
        )


def _cart_instructions(goal_world: list[dict]) -> str | None:
    """Instructions for add-to-cart and cart verification."""
    cart_products = []
    for i in range(1, 3):
        if _goal_has(goal_world, f"p{i}.added_to_cart", True):
            cart_products.append(i)

    if not cart_products:
        return None

    parts = []
    if len(cart_products) == 1:
        parts.append("Add the product to your cart.")
    else:
        parts.append(f"Add all {len(cart_products)} products to your cart.")

    if _goal_has(goal_world, "cart.read", True):
        parts.append(
            "Open the cart and verify the items, quantities, individual prices, "
            "and cart total."
        )

    return " ".join(parts)


def _submission_instructions(
    goal_world: list[dict],
    config: dict[str, Any],
    entities: TaskEntitySet,
) -> str:
    """Final submission instructions — always present."""
    entry_point = config.get("task.entry_point", "search")
    num_products = config.get("task.num_products", 0)

    if _goal_has(goal_world, "cart.read", True):
        return (
            "Submit your findings including: each product's name, price, and "
            "the cart total. Note any discrepancies between listed prices and "
            "the cart total."
        )
    elif num_products >= 2:
        return (
            "Compile a comparison of the products and submit your findings. "
            "Include: product name, price, rating, seller, and any other "
            "relevant details you gathered for each product."
        )
    elif entry_point == "deals":
        return (
            "Submit your findings including: deal product name, original price, "
            "deal price, discount percentage, and deal type."
        )
    elif entry_point == "category":
        return (
            "Submit your findings with the product names, prices, and ratings "
            "from the category listings."
        )
    elif num_products == 1:
        return (
            "Submit your findings with the product name, price, rating, "
            "and all the details you gathered."
        )
    else:
        return (
            "Submit your findings with the product names, prices, and ratings "
            "from the search results."
        )


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_task_description(
    task_id: str,
    start_world: dict[str, Any],
    goal_world: list[dict],
    entities: TaskEntitySet,
) -> str:
    """Generate a natural-language task description from task config + entities.

    Composes instruction fragments based on goal_world predicates to ensure
    every required agent action is mentioned in the description. Non-monotonic
    predicates (page.*) are skipped.

    Args:
        task_id: Unique task identifier.
        start_world: Flat dict of start_world config.
        goal_world: List of goal_world predicates.
        entities: TaskEntitySet with product data.

    Returns:
        Multi-sentence task description string.
    """
    entry_point = start_world.get("task.entry_point", "search")

    # Build description from fragments, in natural task order
    fragments: list[str] = []

    # 1. Opening — how to get to the site
    fragments.append(_opening(entities, entry_point))

    # 2. Category/deals browsing (if applicable)
    cat_inst = _category_instructions(goal_world, entities)
    if cat_inst:
        fragments.append(cat_inst)

    deals_inst = _deals_instructions(goal_world, entities)
    if deals_inst:
        fragments.append(deals_inst)

    # 3. Search results reading
    results_inst = _results_instructions(goal_world)
    if results_inst:
        fragments.append(results_inst)

    # 4. Filters and sorting
    filter_inst = _filter_instructions(goal_world, entities)
    if filter_inst:
        fragments.append(filter_inst)

    # 5. Search refinement
    refine_inst = _search_refinement_instructions(goal_world)
    if refine_inst:
        fragments.append(refine_inst)

    # 6. Product detail visits
    detail_inst = _product_detail_instructions(goal_world, entities, start_world)
    if detail_inst:
        fragments.append(detail_inst)

    # 7. Per-product sub-actions
    shipping_inst = _shipping_instructions(goal_world, entities)
    if shipping_inst:
        fragments.append(shipping_inst)

    review_inst = _review_instructions(goal_world)
    if review_inst:
        fragments.append(review_inst)

    seller_inst = _seller_instructions(goal_world)
    if seller_inst:
        fragments.append(seller_inst)

    variant_inst = _variant_instructions(goal_world)
    if variant_inst:
        fragments.append(variant_inst)

    qa_inst = _qa_instructions(goal_world)
    if qa_inst:
        fragments.append(qa_inst)

    # 8. Cart actions
    cart_inst = _cart_instructions(goal_world)
    if cart_inst:
        fragments.append(cart_inst)

    # 9. Submission — always present
    fragments.append(_submission_instructions(goal_world, start_world, entities))

    return " ".join(fragments)
