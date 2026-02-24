"""Online shopping scenario definitions using the Recipe Engine.

8 fault groups for Archetype C (Transaction Processor):
  - Account issues (locked / restricted)
  - Pricing issues (wrong unit price / missing promo)
  - Shipping config issues (wrong address / wrong method+cost)
  - Tracking issues (missing tracking number)
  - Return issues (stuck return / wrong refund)
  - Payment issues (expired payment / wrong payment method)
  - Membership issues (expired membership)
  - Billing computation issues (wrong tax / wrong shipping cost)

Cartesian product sampled to max_total_tasks=1200, x2 personas = 2400 tasks.
2 unfixable layers in a separate transfer config.
"""

from pathlib import Path
from typing import Any, Callable, Optional

from tau2.domains.online_shopping.data_model import OnlineShoppingDB
from tau2.domains.online_shopping.environment import get_environment
from tau2.domains.online_shopping.tools import _compute_expected_shipping
from tau2.domains.online_shopping.utils import (
    ONLINE_SHOPPING_DB_PATH,
    ONLINE_SHOPPING_POLICY_PATH,
    ONLINE_SHOPPING_TASK_SET_PATH,
)
from tau2.generators.recipe import (
    ActionSpec,
    AssertionSpec,
    FaultAtom,
    FaultLayer,
    FaultLayerConfig,
    FaultLayerGroup,
    InitCall,
    RecipeBook,
    generate_recipe_tasks,
    verify_fault_atoms,
)
from tau2.generators.types import Persona, UserTemplate
from tau2.generators.verify import verify_tasks
from tau2.generators.verify_authoring import (
    collect_authored_files,
    verify_authoring,
    verify_authoring_with_llm,
)
from tau2.utils import dump_file


# ===================================================================
# Personas
# ===================================================================

PERSONAS = [
    Persona(
        name="practical_shopper",
        description=(
            "You are a practical, detail-oriented online shopper. You describe "
            "your issues clearly, provide order numbers and specifics promptly, "
            "and follow the agent's instructions without hesitation."
        ),
    ),
    Persona(
        name="frustrated_shopper",
        description=(
            "You are frustrated with your shopping experience and somewhat "
            "impatient. You describe your problems emotionally but still "
            "cooperate when the agent provides solutions. You may express "
            "annoyance but always follow through on requested actions."
        ),
    ),
]


# ===================================================================
# User Template
# ===================================================================

USER_TEMPLATE = UserTemplate(
    domain="online_shopping",
    reason_for_call=(
        "You are contacting QuickCart Online Shopping customer support "
        "because you have issues with your order, account, or a recent purchase."
    ),
    known_info=(
        "You are {customer_name} (customer ID: {customer_id}). "
        "{fault_descriptions}"
    ),
    task_instructions=(
        "Follow the agent's instructions throughout the conversation. "
        "When the agent asks you to perform an action or use one of your tools, do so. "
        "You must actually call the tool — describing the action in words is not sufficient. "
        "You will consider your issues resolved when the agent confirms all problems "
        "have been addressed."
    ),
    ticket=(
        "Customer {customer_name} (ID: {customer_id}). "
        "{fault_descriptions}"
    ),
    purpose=(
        "Test resolution of online shopping support issues including account access, "
        "order pricing, shipping configuration, tracking, returns, payments, "
        "membership management, and billing accuracy."
    ),
)


# ===================================================================
# Entity construction
# ===================================================================

def _build_entities(db: OnlineShoppingDB) -> list[dict[str, Any]]:
    """Build entity dicts: one per customer with order, return, and payment info."""
    return_by_customer: dict[str, Any] = {}
    for r in db.return_requests:
        if r.customer_id not in return_by_customer:
            return_by_customer[r.customer_id] = r

    default_pay: dict[str, Any] = {}
    alt_pay: dict[str, Any] = {}
    for p in db.payment_methods:
        if p.is_default:
            default_pay[p.customer_id] = p
        elif p.customer_id not in alt_pay:
            alt_pay[p.customer_id] = p

    entities = []
    for customer in db.customers:
        order = next(
            (o for o in db.orders if o.customer_id == customer.customer_id), None
        )
        if order is None:
            continue

        ret = return_by_customer.get(customer.customer_id)
        alt = alt_pay.get(customer.customer_id)
        dpay = default_pay.get(customer.customer_id)

        entity: dict[str, Any] = {
            # Customer
            "customer_id": customer.customer_id,
            "customer_name": customer.name,
            # Order
            "order_id": order.order_id,
            "product_name": order.product_name,
            "original_unit_price": order.unit_price,
            "original_quantity": order.quantity,
            "original_shipping_cost": order.shipping_cost,
            "original_tax_amount": order.tax_amount,
            "original_total": order.total,
            "original_promo_code": order.promo_code or "",
            "original_promo_discount_pct": order.promo_discount_pct,
            "original_shipping_method": order.shipping_method,
            "original_shipping_address": order.shipping_address,
            "payment_method_id": order.payment_method_id,
            # Membership
            "original_membership_tier": customer.membership_tier,
            "has_membership": customer.membership_tier not in ("standard",),
            # Predicates
            "is_shipped": order.status == "shipped",
            "has_promo": order.promo_discount_pct > 0,
            # Return info
            "has_return": ret is not None,
            "return_id": ret.return_id if ret else None,
            "return_product_name": ret.product_name if ret else None,
            "return_quantity": ret.quantity if ret else None,
            "return_unit_price": ret.unit_price if ret else None,
            "correct_refund_amount": round(ret.unit_price * ret.quantity, 2) if ret else None,
            # Alt payment
            "has_alt_payment": alt is not None,
            "alt_payment_id": alt.payment_id if alt else None,
            "original_card_type": dpay.card_type if dpay else "",
            "original_last_four": dpay.last_four if dpay else "",
            # Wrong shipping values (guaranteed different from original)
            "wrong_shipping_method": (
                "standard" if order.shipping_method == "overnight"
                else "overnight"
            ),
            "wrong_shipping_cost_value": _compute_expected_shipping(
                "standard" if order.shipping_method == "overnight" else "overnight",
                customer.membership_tier,
            ),
        }
        entities.append(entity)

    return entities


# ===================================================================
# Fault Layers
# ===================================================================

# --- Group 1: Account Issues (2 mutually exclusive) ---

locked_account = FaultLayer(
    name="locked_account",
    known_info_fragment=(
        "My account appears to be locked — I cannot access my orders in the portal."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_account_status",
                args={"customer_id": "{customer_id}", "status": "locked"},
            ),
            fix=ActionSpec(
                tool_name="unlock_account",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
            check=AssertionSpec(
                func_name="assert_account_status",
                args={"customer_id": "{customer_id}", "expected": "active"},
                env_type="assistant",
                message_template="Account {customer_id} should be active.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"customer_id": "{customer_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"customer_id": "{customer_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="account:{customer_id}",
)

restricted_account = FaultLayer(
    name="restricted_account",
    known_info_fragment=(
        "My account has a restriction on it — I cannot make any changes to my orders."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_account_status",
                args={"customer_id": "{customer_id}", "status": "restricted"},
            ),
            fix=ActionSpec(
                tool_name="lift_account_restriction",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
            check=AssertionSpec(
                func_name="assert_account_status",
                args={"customer_id": "{customer_id}", "expected": "active"},
                env_type="assistant",
                message_template="Account {customer_id} should be active.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"customer_id": "{customer_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"customer_id": "{customer_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="account:{customer_id}",
)

account_group = FaultLayerGroup(
    name="account_issues",
    layers=[locked_account, restricted_account],
)


# --- Group 2: Pricing Issues (2 mutually exclusive) ---

wrong_unit_price = FaultLayer(
    name="wrong_unit_price",
    known_info_fragment=(
        "The price on my order {order_id} for {product_name} is wrong. "
        "The correct price should be ${original_unit_price}."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_unit_price",
                args={"order_id": "{order_id}", "price": 999.99},
            ),
            fix=ActionSpec(
                tool_name="adjust_item_price",
                args={
                    "order_id": "{order_id}",
                    "unit_price": "{original_unit_price}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_unit_price",
                args={
                    "order_id": "{order_id}",
                    "expected": "{original_unit_price}",
                },
                env_type="assistant",
                message_template="Order {order_id} unit price should be ${original_unit_price}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_pricing_update",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_pricing_update_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="pricing:{order_id}",
)

missing_promo = FaultLayer(
    name="missing_promo",
    known_info_fragment=(
        "My promo code {original_promo_code} with {original_promo_discount_pct}% "
        "discount was not applied to order {order_id}."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_promo_discount",
                args={"order_id": "{order_id}", "pct": 0.0},
            ),
            fix=ActionSpec(
                tool_name="apply_promo_code",
                args={
                    "order_id": "{order_id}",
                    "promo_code": "{original_promo_code}",
                    "discount_pct": "{original_promo_discount_pct}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_promo_discount",
                args={
                    "order_id": "{order_id}",
                    "expected_pct": "{original_promo_discount_pct}",
                },
                env_type="assistant",
                message_template=(
                    "Order {order_id} should have {original_promo_discount_pct}% discount."
                ),
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_pricing_update",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_pricing_update_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_promo",
    resource_scope="pricing:{order_id}",
)

pricing_group = FaultLayerGroup(
    name="pricing_issues",
    layers=[wrong_unit_price, missing_promo],
)


# --- Group 3: Shipping Config Issues (2 mutually exclusive) ---

wrong_shipping_address = FaultLayer(
    name="wrong_shipping_address",
    known_info_fragment=(
        "The shipping address on order {order_id} is wrong. "
        "It should be {original_shipping_address}."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_shipping_address",
                args={"order_id": "{order_id}", "address": "999 Wrong Street, Nowhere XX 00000"},
            ),
            fix=ActionSpec(
                tool_name="update_shipping_address",
                args={
                    "order_id": "{order_id}",
                    "address": "{original_shipping_address}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_shipping_address",
                args={
                    "order_id": "{order_id}",
                    "expected": "{original_shipping_address}",
                },
                env_type="assistant",
                message_template="Order {order_id} address should be {original_shipping_address}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_shipping_update",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_shipping_update_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="shipping:{order_id}",
)

wrong_shipping_method = FaultLayer(
    name="wrong_shipping_method",
    known_info_fragment=(
        "Order {order_id} should be shipped via {original_shipping_method}, "
        "not the method currently listed. Please also update the shipping cost accordingly."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_shipping_method",
                args={"order_id": "{order_id}", "method": "{wrong_shipping_method}"},
            ),
            fix=ActionSpec(
                tool_name="update_shipping_method",
                args={
                    "order_id": "{order_id}",
                    "method": "{original_shipping_method}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_shipping_method",
                args={
                    "order_id": "{order_id}",
                    "expected": "{original_shipping_method}",
                },
                env_type="assistant",
                message_template="Order {order_id} method should be {original_shipping_method}.",
            ),
        ),
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_shipping_cost",
                args={"order_id": "{order_id}", "amount": "{wrong_shipping_cost_value}"},
            ),
            fix=ActionSpec(
                tool_name="adjust_shipping_cost",
                args={
                    "order_id": "{order_id}",
                    "amount": "{original_shipping_cost}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_shipping_cost",
                args={
                    "order_id": "{order_id}",
                    "expected": "{original_shipping_cost}",
                },
                env_type="assistant",
                message_template="Order {order_id} shipping should be ${original_shipping_cost}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_shipping_update",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_shipping_update_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="shipping:{order_id}",
)

shipping_group = FaultLayerGroup(
    name="shipping_config_issues",
    layers=[wrong_shipping_address, wrong_shipping_method],
)


# --- Group 4: Tracking Issues (1 layer, predicated) ---

missing_tracking = FaultLayer(
    name="missing_tracking",
    known_info_fragment=(
        "My order {order_id} has shipped but I do not have a tracking number."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_tracking_number",
                args={"order_id": "{order_id}", "tracking_number": ""},
            ),
            fix=ActionSpec(
                tool_name="assign_tracking_number",
                args={
                    "order_id": "{order_id}",
                    "tracking_number": "TRK0000000",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_tracking_number_assigned",
                args={"order_id": "{order_id}"},
                env_type="assistant",
                message_template="Order {order_id} should have a tracking number.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_tracking_update",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_tracking_update_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="is_shipped",
    resource_scope="tracking:{order_id}",
)

tracking_group = FaultLayerGroup(
    name="tracking_issues",
    layers=[missing_tracking],
)


# --- Group 5: Return Issues (2 mutually exclusive, predicated) ---

stuck_return = FaultLayer(
    name="stuck_return",
    known_info_fragment=(
        "My return {return_id} for {return_product_name} has been stuck "
        "in pending status. It should be approved."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_return_status",
                args={"return_id": "{return_id}", "status": "pending"},
            ),
            fix=ActionSpec(
                tool_name="approve_return",
                args={"return_id": "{return_id}"},
                compare_args=["return_id"],
            ),
            check=AssertionSpec(
                func_name="assert_return_status",
                args={"return_id": "{return_id}", "expected": "approved"},
                env_type="assistant",
                message_template="Return {return_id} should be approved.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_return_resolution",
                args={"return_id": "{return_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_return_resolution_confirmed",
                args={"return_id": "{return_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_return",
    resource_scope="return:{return_id}",
)

wrong_refund = FaultLayer(
    name="wrong_refund",
    known_info_fragment=(
        "The refund amount on my return {return_id} for {return_product_name} "
        "is incorrect. It should be ${correct_refund_amount} "
        "({return_quantity} x ${return_unit_price})."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_refund_amount",
                args={"return_id": "{return_id}", "amount": 1.00},
            ),
            fix=ActionSpec(
                tool_name="adjust_refund_amount",
                args={
                    "return_id": "{return_id}",
                    "amount": "{correct_refund_amount}",
                },
                compare_args=["return_id"],
            ),
            check=AssertionSpec(
                func_name="assert_refund_amount",
                args={
                    "return_id": "{return_id}",
                    "expected": "{correct_refund_amount}",
                },
                env_type="assistant",
                message_template="Return {return_id} refund should be ${correct_refund_amount}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_return_resolution",
                args={"return_id": "{return_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_return_resolution_confirmed",
                args={"return_id": "{return_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_return",
    resource_scope="return:{return_id}",
)

return_group = FaultLayerGroup(
    name="return_issues",
    layers=[stuck_return, wrong_refund],
)


# --- Group 6: Payment Issues (2 mutually exclusive) ---
# expired_payment has ordering gate (DI-3): user must update_payment_info first

expired_payment = FaultLayer(
    name="expired_payment",
    known_info_fragment=(
        "My payment for order {order_id} failed because my card expired. "
        "I need to update my payment details and have the payment retried."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_payment_method_status",
                args={"payment_id": "{payment_method_id}", "status": "expired"},
            ),
            fix=ActionSpec(
                tool_name="update_payment_info",
                args={"payment_id": "{payment_method_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_payment_info_updated",
                args={"payment_id": "{payment_method_id}"},
                env_type="user",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="reprocess_payment",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_payment_reprocessed",
                args={"order_id": "{order_id}"},
                env_type="assistant",
                message_template="Order {order_id} payment should be reprocessed.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_payment_update",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_payment_update_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="payment:{order_id}",
)

wrong_payment_method = FaultLayer(
    name="wrong_payment_method",
    known_info_fragment=(
        "My order {order_id} was charged to the wrong card. It should be on "
        "my {original_card_type} ending in {original_last_four}."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_order_payment_method",
                args={
                    "order_id": "{order_id}",
                    "payment_id": "{alt_payment_id}",
                },
            ),
            fix=ActionSpec(
                tool_name="update_order_payment",
                args={
                    "order_id": "{order_id}",
                    "payment_id": "{payment_method_id}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_order_payment_method",
                args={
                    "order_id": "{order_id}",
                    "expected": "{payment_method_id}",
                },
                env_type="assistant",
                message_template="Order {order_id} should use payment {payment_method_id}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_payment_update",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_payment_update_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_alt_payment",
    resource_scope="payment:{order_id}",
)

payment_group = FaultLayerGroup(
    name="payment_issues",
    layers=[expired_payment, wrong_payment_method],
)


# --- Group 7: Membership Issues (1 layer, predicated) ---

expired_membership = FaultLayer(
    name="expired_membership",
    known_info_fragment=(
        "My membership appears to have expired. I would like to renew my "
        "{original_membership_tier} membership."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_membership_tier",
                args={"customer_id": "{customer_id}", "tier": "expired"},
            ),
            fix=ActionSpec(
                tool_name="renew_membership",
                args={
                    "customer_id": "{customer_id}",
                    "tier": "{original_membership_tier}",
                },
                compare_args=["customer_id"],
            ),
            check=AssertionSpec(
                func_name="assert_membership_tier",
                args={
                    "customer_id": "{customer_id}",
                    "expected": "{original_membership_tier}",
                },
                env_type="assistant",
                message_template=(
                    "Customer {customer_id} should have {original_membership_tier} tier."
                ),
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_membership_renewal",
                args={"customer_id": "{customer_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_membership_renewal_confirmed",
                args={"customer_id": "{customer_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_membership",
    resource_scope="membership:{customer_id}",
)

membership_group = FaultLayerGroup(
    name="membership_issues",
    layers=[expired_membership],
)


# --- Group 8: Billing Computation Issues (2 mutually exclusive) ---
# Agent must use review_order_charges diagnostic to discover discrepancies (DI-1)

wrong_tax = FaultLayer(
    name="wrong_tax",
    known_info_fragment=(
        "I think the tax amount on my order {order_id} might be wrong. "
        "Can you check?"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_tax_amount",
                args={"order_id": "{order_id}", "amount": 99.99},
            ),
            fix=ActionSpec(
                tool_name="adjust_tax",
                args={
                    "order_id": "{order_id}",
                    "amount": "{original_tax_amount}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_tax_amount",
                args={
                    "order_id": "{order_id}",
                    "expected": "{original_tax_amount}",
                },
                env_type="assistant",
                message_template="Order {order_id} tax should be ${original_tax_amount}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_billing_correction",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_billing_correction_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="billing:{order_id}",
)

wrong_shipping_cost = FaultLayer(
    name="wrong_shipping_cost",
    known_info_fragment=(
        "I think the shipping cost on my order {order_id} might be incorrect. "
        "Can you review it?"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_shipping_cost",
                args={"order_id": "{order_id}", "amount": 50.00},
            ),
            fix=ActionSpec(
                tool_name="adjust_shipping_cost",
                args={
                    "order_id": "{order_id}",
                    "amount": "{original_shipping_cost}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_shipping_cost",
                args={
                    "order_id": "{order_id}",
                    "expected": "{original_shipping_cost}",
                },
                env_type="assistant",
                message_template=(
                    "Order {order_id} shipping cost should be ${original_shipping_cost}."
                ),
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_billing_correction",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_billing_correction_confirmed",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="billing:{order_id}",
)

billing_group = FaultLayerGroup(
    name="billing_computation_issues",
    layers=[wrong_tax, wrong_shipping_cost],
)


# ===================================================================
# Unfixable layers (separate transfer config)
# ===================================================================

counterfeit_product = FaultLayer(
    name="counterfeit_product",
    unfixable=True,
    known_info_fragment=(
        "I believe the {product_name} I received from order {order_id} "
        "is counterfeit. It does not match the brand packaging at all."
    ),
    atoms=[],
    resource_scope="counterfeit:{order_id}",
)

chargeback_dispute = FaultLayer(
    name="chargeback_dispute",
    unfixable=True,
    known_info_fragment=(
        "I have filed a chargeback with my bank for order {order_id}. "
        "I need to discuss the payment dispute."
    ),
    atoms=[],
    resource_scope="chargeback:{order_id}",
)

unfixable_group = FaultLayerGroup(
    name="unfixable_issues",
    layers=[counterfeit_product, chargeback_dispute],
)


# ===================================================================
# FaultLayerConfigs
# ===================================================================

FIXABLE_CONFIG = FaultLayerConfig(
    name="online_shopping",
    entity_query=lambda db: _build_entities(db),
    groups=[
        account_group,      # Group 1: account (2 layers)
        pricing_group,      # Group 2: pricing (2 layers, 1 predicated)
        shipping_group,     # Group 3: shipping config (2 layers)
        tracking_group,     # Group 4: tracking (1 layer, predicated)
        return_group,       # Group 5: returns (2 layers, both predicated)
        payment_group,      # Group 6: payment (2 layers, 1 predicated)
        membership_group,   # Group 7: membership (1 layer, predicated)
        billing_group,      # Group 8: billing computation (2 layers)
    ],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_customer_info",
            args={"name": "{customer_name}", "customer_id": "{customer_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {customer_name}. Your customer ID is {customer_id}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Customer {customer_name} (ID: {customer_id}). "
        "{fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting QuickCart Online Shopping customer support "
        "because you have issues with your order, account, or a recent purchase."
    ),
    purpose=(
        "Test resolution of online shopping support issues with prescriptive "
        "protocols, numeric computation, and active user participation."
    ),
    entity_id_field="customer_id",
    min_faults=1,
    max_faults=8,
    max_total_tasks=1200,
)

TRANSFER_CONFIG = FaultLayerConfig(
    name="online_shopping_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[unfixable_group],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_customer_info",
            args={"name": "{customer_name}", "customer_id": "{customer_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {customer_name}. Your customer ID is {customer_id}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Customer {customer_name} (ID: {customer_id}). "
        "{fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting QuickCart Online Shopping customer support "
        "about an issue with a recent purchase."
    ),
    purpose="Test transfer-to-human for issues outside standard support scope.",
    entity_id_field="customer_id",
    min_faults=1,
    max_faults=1,
    max_total_tasks=16,
)


# ===================================================================
# RecipeBook
# ===================================================================

RECIPE_BOOK = RecipeBook(
    fault_layer_configs=[FIXABLE_CONFIG, TRANSFER_CONFIG],
)


# ===================================================================
# Task generation entry point
# ===================================================================

def create_tasks(
    verify: bool = True,
    save: bool = False,
    seed: int = 42,
    llm_verify: bool = False,
    llm_call_fn: Optional[Callable[[str], str]] = None,
) -> list:
    """Generate tasks from the recipe book, optionally verify and save."""
    def get_db():
        return OnlineShoppingDB.load(ONLINE_SHOPPING_DB_PATH)

    if verify:
        authoring_issues = verify_authoring(RECIPE_BOOK, get_environment, get_db)
        auth_errors = [i for i in authoring_issues if i.startswith("ERROR:")]
        auth_warnings = [i for i in authoring_issues if i.startswith("WARNING:")]
        print(f"Authoring verification: {len(auth_errors)} error(s), {len(auth_warnings)} warning(s)")
        for i in authoring_issues:
            print(f"  {i}")
        if auth_errors:
            raise ValueError(f"Authoring verification failed: {len(auth_errors)} error(s)")

        if llm_verify and llm_call_fn:
            authored_files = collect_authored_files(
                file_paths={
                    "tools.py": str(Path(__file__).parent / "tools.py"),
                    "scenarios.py": str(Path(__file__).parent / "scenarios.py"),
                    "data_model.py": str(Path(__file__).parent / "data_model.py"),
                    "user_tools.py": str(Path(__file__).parent / "user_tools.py"),
                    "environment.py": str(Path(__file__).parent / "environment.py"),
                    "policy.md": str(ONLINE_SHOPPING_POLICY_PATH),
                },
                db_path=str(ONLINE_SHOPPING_DB_PATH),
            )
            verify_authoring_with_llm(
                RECIPE_BOOK, authored_files, authoring_issues, llm_call_fn
            )

    tasks = generate_recipe_tasks(
        recipe_book=RECIPE_BOOK,
        build_indexes=lambda db: db,
        get_db=get_db,
        user_template=USER_TEMPLATE,
        personas=PERSONAS,
        seed=seed,
    )

    print(f"Generated {len(tasks)} tasks.")

    if verify:
        atom_issues = verify_fault_atoms(
            FIXABLE_CONFIG, get_environment, get_db, sample_size=2
        )
        if atom_issues:
            raise ValueError(
                f"Atom verification failed: {len(atom_issues)} issue(s)."
            )

        report = verify_tasks(tasks, get_environment)
        errors = {}
        warnings_count = 0
        for task_id, issues in report.items():
            errs = [i for i in issues if i.startswith("ERROR:")]
            warns = [i for i in issues if i.startswith("WARNING:")]
            warnings_count += len(warns)
            if errs:
                errors[task_id] = errs
        print(f"Verification: {len(errors)} tasks with errors, {warnings_count} warnings.")
        if errors:
            for task_id, errs in list(errors.items())[:10]:
                print(f"\n  Task {task_id}:")
                for e in errs:
                    print(f"    {e}")
            raise ValueError(
                f"Verification failed: {len(errors)} task(s) have errors."
            )

    if save:
        task_dicts = [t.model_dump() for t in tasks]
        dump_file(ONLINE_SHOPPING_TASK_SET_PATH, task_dicts)
        print(f"Saved {len(tasks)} tasks to {ONLINE_SHOPPING_TASK_SET_PATH}")

    return tasks
