from typing import Any, Dict, List, Optional

from tau2.domains.online_shopping.data_model import (
    Customer,
    OnlineShoppingDB,
    Order,
    PaymentMethod,
    ReturnRequest,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


# Shipping rates used by review_order_charges and policy
SHIPPING_RATES = {
    "standard": 5.99,
    "express": 12.99,
    "overnight": 24.99,
}

FREE_STANDARD_TIERS = {"gold", "platinum"}
HALF_EXPRESS_TIERS = {"gold", "platinum"}


def _compute_expected_shipping(method: str, tier: str) -> float:
    if method == "standard" and tier in FREE_STANDARD_TIERS:
        return 0.00
    if method == "express" and tier in HALF_EXPRESS_TIERS:
        return 6.50
    return SHIPPING_RATES.get(method, 5.99)


def _compute_total(unit_price: float, quantity: int, promo_discount_pct: float,
                   shipping_cost: float, tax_amount: float) -> float:
    discounted_subtotal = unit_price * quantity * (1 - promo_discount_pct / 100)
    return round(discounted_subtotal + shipping_cost + tax_amount, 2)


def _compute_tax(unit_price: float, quantity: int, promo_discount_pct: float) -> float:
    discounted_subtotal = unit_price * quantity * (1 - promo_discount_pct / 100)
    return round(discounted_subtotal * 0.085, 2)


class OnlineShoppingTools(ToolKitBase):
    db: OnlineShoppingDB

    def __init__(self, db: OnlineShoppingDB):
        super().__init__(db)

    # =============================================
    # PRIVATE HELPERS
    # =============================================

    def _find_customer(self, customer_id: str) -> Customer:
        for c in self.db.customers:
            if c.customer_id == customer_id:
                return c
        raise ValueError(f"Customer '{customer_id}' not found.")

    def _find_customer_by_name(self, name: str) -> Optional[Customer]:
        name_lower = name.strip().lower()
        for c in self.db.customers:
            if c.name.lower() == name_lower:
                return c
        return None

    def _find_order(self, order_id: str) -> Order:
        for o in self.db.orders:
            if o.order_id == order_id:
                return o
        raise ValueError(f"Order '{order_id}' not found.")

    def _find_return(self, return_id: str) -> ReturnRequest:
        for r in self.db.return_requests:
            if r.return_id == return_id:
                return r
        raise ValueError(f"Return request '{return_id}' not found.")

    def _find_payment(self, payment_id: str) -> PaymentMethod:
        for p in self.db.payment_methods:
            if p.payment_id == payment_id:
                return p
        raise ValueError(f"Payment method '{payment_id}' not found.")

    def _get_customer_tier(self, customer_id: str) -> str:
        customer = self._find_customer(customer_id)
        return customer.membership_tier

    # =============================================
    # READ TOOLS — transparent (Archetype C)
    # =============================================

    @is_tool(ToolType.READ)
    def get_customer_by_name(self, name: str) -> Dict[str, Any]:
        """
        Look up a customer by name.

        Args:
            name: Customer's full name.

        Returns:
            Customer details including ID, contact info, account status, and membership.
        """
        customer = self._find_customer_by_name(name)
        if customer is None:
            raise ValueError(f"No customer found with name '{name}'.")
        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "account_status": customer.account_status,
            "membership_tier": customer.membership_tier,
            "membership_expiry": customer.membership_expiry,
        }

    @is_tool(ToolType.READ)
    def get_customer_by_id(self, customer_id: str) -> Dict[str, Any]:
        """
        Look up a customer by their customer ID.

        Args:
            customer_id: The unique customer identifier.

        Returns:
            Customer details including name, contact info, account status, and membership.
        """
        customer = self._find_customer(customer_id)
        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "account_status": customer.account_status,
            "membership_tier": customer.membership_tier,
            "membership_expiry": customer.membership_expiry,
        }

    @is_tool(ToolType.READ)
    def get_orders(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all orders for a customer.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            List of orders with product, pricing, shipping, and status details.
        """
        self._find_customer(customer_id)
        orders = [o for o in self.db.orders if o.customer_id == customer_id]
        return [
            {
                "order_id": o.order_id,
                "product_name": o.product_name,
                "quantity": o.quantity,
                "unit_price": o.unit_price,
                "total": o.total,
                "status": o.status,
                "order_date": o.order_date,
                "shipping_method": o.shipping_method,
                "shipping_address": o.shipping_address,
                "tracking_number": o.tracking_number,
            }
            for o in orders
        ]

    @is_tool(ToolType.READ)
    def get_order_details(self, order_id: str) -> Dict[str, Any]:
        """
        Get full details of a specific order.

        Args:
            order_id: The order identifier.

        Returns:
            Complete order details including all pricing fields.
        """
        order = self._find_order(order_id)
        return {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "product_name": order.product_name,
            "quantity": order.quantity,
            "unit_price": order.unit_price,
            "shipping_cost": order.shipping_cost,
            "tax_amount": order.tax_amount,
            "promo_code": order.promo_code,
            "promo_discount_pct": order.promo_discount_pct,
            "total": order.total,
            "status": order.status,
            "order_date": order.order_date,
            "shipping_method": order.shipping_method,
            "shipping_address": order.shipping_address,
            "tracking_number": order.tracking_number,
            "payment_method_id": order.payment_method_id,
        }

    @is_tool(ToolType.READ)
    def get_returns(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all return requests for a customer.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            List of return requests with status and refund details.
        """
        self._find_customer(customer_id)
        returns = [r for r in self.db.return_requests if r.customer_id == customer_id]
        return [
            {
                "return_id": r.return_id,
                "order_id": r.order_id,
                "product_name": r.product_name,
                "quantity": r.quantity,
                "unit_price": r.unit_price,
                "reason": r.reason,
                "status": r.status,
                "refund_amount": r.refund_amount,
                "refund_method": r.refund_method,
            }
            for r in returns
        ]

    @is_tool(ToolType.READ)
    def get_payment_methods(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all payment methods for a customer.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            List of payment methods with card type, status, and default flag.
        """
        self._find_customer(customer_id)
        methods = [p for p in self.db.payment_methods if p.customer_id == customer_id]
        return [
            {
                "payment_id": p.payment_id,
                "card_type": p.card_type,
                "last_four": p.last_four,
                "is_default": p.is_default,
                "status": p.status,
            }
            for p in methods
        ]

    @is_tool(ToolType.READ)
    def review_order_charges(self, order_id: str) -> Dict[str, Any]:
        """
        Run a diagnostic review of an order's charges. Computes expected
        tax, shipping cost, and total based on policy rules, then flags
        any discrepancies with the actual values.

        Args:
            order_id: The order to review.

        Returns:
            Diagnostic results with expected vs actual values and any issues found.
        """
        order = self._find_order(order_id)
        customer = self._find_customer(order.customer_id)

        expected_tax = _compute_tax(
            order.unit_price, order.quantity, order.promo_discount_pct
        )
        expected_shipping = _compute_expected_shipping(
            order.shipping_method, customer.membership_tier
        )
        expected_total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )

        issues = []
        if abs(order.tax_amount - expected_tax) > 0.01:
            issues.append(
                f"Tax discrepancy: actual ${order.tax_amount:.2f} vs "
                f"expected ${expected_tax:.2f}"
            )
        if abs(order.shipping_cost - expected_shipping) > 0.01:
            issues.append(
                f"Shipping cost discrepancy: actual ${order.shipping_cost:.2f} vs "
                f"expected ${expected_shipping:.2f} for {order.shipping_method} "
                f"({customer.membership_tier} tier)"
            )
        if abs(order.total - expected_total) > 0.01:
            issues.append(
                f"Total discrepancy: actual ${order.total:.2f} vs "
                f"expected ${expected_total:.2f}"
            )

        return {
            "order_id": order_id,
            "unit_price": order.unit_price,
            "quantity": order.quantity,
            "promo_discount_pct": order.promo_discount_pct,
            "actual_tax": order.tax_amount,
            "expected_tax": expected_tax,
            "actual_shipping": order.shipping_cost,
            "expected_shipping": expected_shipping,
            "actual_total": order.total,
            "expected_total": expected_total,
            "issues": issues,
            "status": "issues_found" if issues else "all_clear",
        }

    # =============================================
    # WRITE TOOLS — with overwrite guards (Archetype C)
    # =============================================

    @is_tool(ToolType.WRITE)
    def unlock_account(self, customer_id: str) -> str:
        """
        Unlock a locked customer account.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            Confirmation message.
        """
        customer = self._find_customer(customer_id)
        if customer.account_status != "locked":
            return (
                f"Account {customer_id} is not locked "
                f"(status: {customer.account_status}). No changes made."
            )
        customer.account_status = "active"
        return f"Account {customer_id} has been unlocked."

    @is_tool(ToolType.WRITE)
    def lift_account_restriction(self, customer_id: str) -> str:
        """
        Lift a restriction on a customer account.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            Confirmation message.
        """
        customer = self._find_customer(customer_id)
        if customer.account_status != "restricted":
            return (
                f"Account {customer_id} is not restricted "
                f"(status: {customer.account_status}). No changes made."
            )
        customer.account_status = "active"
        return f"Account {customer_id} restriction has been lifted."

    @is_tool(ToolType.WRITE)
    def adjust_item_price(self, order_id: str, unit_price: float) -> str:
        """
        Correct the unit price on an order and recalculate the total.

        Args:
            order_id: The order identifier.
            unit_price: The correct unit price.

        Returns:
            Confirmation with updated total.
        """
        order = self._find_order(order_id)
        old_price = order.unit_price
        order.unit_price = unit_price
        order.total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )
        return (
            f"Order {order_id} unit price adjusted from ${old_price:.2f} to "
            f"${unit_price:.2f}. New total: ${order.total:.2f}."
        )

    @is_tool(ToolType.WRITE)
    def apply_promo_code(self, order_id: str, promo_code: str,
                         discount_pct: float) -> str:
        """
        Apply a promotional code and discount to an order.

        Args:
            order_id: The order identifier.
            promo_code: The promotional code to apply.
            discount_pct: The discount percentage (0-100).

        Returns:
            Confirmation with updated total.
        """
        order = self._find_order(order_id)
        if order.promo_discount_pct > 0:
            return (
                f"Order {order_id} already has promo code '{order.promo_code}' "
                f"with {order.promo_discount_pct}% discount. No changes made."
            )
        order.promo_code = promo_code
        order.promo_discount_pct = discount_pct
        order.total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )
        return (
            f"Promo code '{promo_code}' applied to order {order_id} "
            f"({discount_pct}% discount). New total: ${order.total:.2f}."
        )

    @is_tool(ToolType.WRITE)
    def update_shipping_address(self, order_id: str, address: str) -> str:
        """
        Update the shipping address on an order.

        Args:
            order_id: The order identifier.
            address: The correct shipping address.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        old_address = order.shipping_address
        order.shipping_address = address
        return (
            f"Order {order_id} shipping address updated from "
            f"'{old_address}' to '{address}'."
        )

    @is_tool(ToolType.WRITE)
    def update_shipping_method(self, order_id: str, method: str) -> str:
        """
        Update the shipping method on an order.

        Args:
            order_id: The order identifier.
            method: The shipping method (standard, express, overnight).

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        if method not in SHIPPING_RATES:
            return (
                f"Invalid shipping method '{method}'. "
                "Valid options: standard, express, overnight."
            )
        old_method = order.shipping_method
        order.shipping_method = method
        return (
            f"Order {order_id} shipping method updated from "
            f"'{old_method}' to '{method}'."
        )

    @is_tool(ToolType.WRITE)
    def assign_tracking_number(self, order_id: str, tracking_number: str) -> str:
        """
        Assign a tracking number to an order.

        Args:
            order_id: The order identifier.
            tracking_number: The tracking number to assign.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        if order.tracking_number:
            return (
                f"Order {order_id} already has tracking number "
                f"'{order.tracking_number}'. No changes made."
            )
        order.tracking_number = tracking_number
        return f"Tracking number '{tracking_number}' assigned to order {order_id}."

    @is_tool(ToolType.WRITE)
    def approve_return(self, return_id: str) -> str:
        """
        Approve a pending return request.

        Args:
            return_id: The return request identifier.

        Returns:
            Confirmation message.
        """
        ret = self._find_return(return_id)
        if ret.status != "pending":
            return (
                f"Return {return_id} is not pending "
                f"(status: {ret.status}). No changes made."
            )
        ret.status = "approved"
        return f"Return request {return_id} has been approved."

    @is_tool(ToolType.WRITE)
    def adjust_refund_amount(self, return_id: str, amount: float) -> str:
        """
        Adjust the refund amount on a return request.

        Args:
            return_id: The return request identifier.
            amount: The correct refund amount.

        Returns:
            Confirmation message.
        """
        ret = self._find_return(return_id)
        old_amount = ret.refund_amount
        ret.refund_amount = amount
        return (
            f"Return {return_id} refund adjusted from ${old_amount:.2f} "
            f"to ${amount:.2f}."
        )

    @is_tool(ToolType.WRITE)
    def reprocess_payment(self, order_id: str) -> str:
        """
        Reprocess payment on an order after the customer has updated
        their payment method. Requires the payment method to be active.

        Args:
            order_id: The order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        payment = self._find_payment(order.payment_method_id)
        if payment.status != "active":
            return (
                f"Cannot reprocess: payment method {payment.payment_id} "
                f"is still {payment.status}. The customer must update their "
                "payment information first."
            )
        order.payment_reprocessed = True
        return f"Payment reprocessed successfully for order {order_id}."

    @is_tool(ToolType.WRITE)
    def update_order_payment(self, order_id: str, payment_id: str) -> str:
        """
        Change the payment method on an order.

        Args:
            order_id: The order identifier.
            payment_id: The new payment method ID.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        payment = self._find_payment(payment_id)
        if payment.status != "active":
            return (
                f"Payment method {payment_id} is {payment.status}. "
                "Cannot assign an inactive payment method."
            )
        old_payment = order.payment_method_id
        order.payment_method_id = payment_id
        return (
            f"Order {order_id} payment updated from {old_payment} "
            f"to {payment_id}."
        )

    @is_tool(ToolType.WRITE)
    def renew_membership(self, customer_id: str, tier: str) -> str:
        """
        Renew an expired membership to the specified tier.

        Args:
            customer_id: The customer's unique identifier.
            tier: The membership tier (standard, silver, gold, platinum).

        Returns:
            Confirmation message.
        """
        customer = self._find_customer(customer_id)
        valid_tiers = {"standard", "silver", "gold", "platinum"}
        if tier not in valid_tiers:
            return (
                f"Invalid tier '{tier}'. "
                f"Valid options: {', '.join(sorted(valid_tiers))}."
            )
        if customer.membership_tier != "expired":
            return (
                f"Customer {customer_id} membership is not expired "
                f"(tier: {customer.membership_tier}). No changes made."
            )
        customer.membership_tier = tier
        return (
            f"Customer {customer_id} membership renewed to {tier} tier."
        )

    @is_tool(ToolType.WRITE)
    def adjust_tax(self, order_id: str, amount: float) -> str:
        """
        Correct the tax amount on an order and recalculate the total.

        Args:
            order_id: The order identifier.
            amount: The correct tax amount.

        Returns:
            Confirmation with updated total.
        """
        order = self._find_order(order_id)
        old_tax = order.tax_amount
        order.tax_amount = amount
        order.total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )
        return (
            f"Order {order_id} tax adjusted from ${old_tax:.2f} to "
            f"${amount:.2f}. New total: ${order.total:.2f}."
        )

    @is_tool(ToolType.WRITE)
    def adjust_shipping_cost(self, order_id: str, amount: float) -> str:
        """
        Correct the shipping cost on an order and recalculate the total.

        Args:
            order_id: The order identifier.
            amount: The correct shipping cost.

        Returns:
            Confirmation with updated total.
        """
        order = self._find_order(order_id)
        old_cost = order.shipping_cost
        order.shipping_cost = amount
        order.total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )
        return (
            f"Order {order_id} shipping cost adjusted from ${old_cost:.2f} to "
            f"${amount:.2f}. New total: ${order.total:.2f}."
        )

    # =============================================
    # GENERIC TOOLS
    # =============================================

    @is_tool(ToolType.GENERIC)
    def transfer_to_human(self, summary: str) -> str:
        """
        Transfer the call to a human specialist.

        Args:
            summary: Brief description of the issue for the specialist.

        Returns:
            Confirmation of transfer.
        """
        return f"Call transferred to human specialist. Summary: {summary}"

    # =============================================
    # SETUP HELPERS — called by scenarios init
    # =============================================

    def set_account_status(self, customer_id: str, status: str) -> None:
        self._find_customer(customer_id).account_status = status

    def set_unit_price(self, order_id: str, price: float) -> None:
        order = self._find_order(order_id)
        order.unit_price = price
        order.total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )

    def set_promo_discount(self, order_id: str, pct: float) -> None:
        order = self._find_order(order_id)
        order.promo_discount_pct = pct
        if pct == 0.0:
            order.promo_code = None
        order.total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )

    def set_shipping_address(self, order_id: str, address: str) -> None:
        self._find_order(order_id).shipping_address = address

    def set_shipping_method(self, order_id: str, method: str) -> None:
        self._find_order(order_id).shipping_method = method

    def set_tracking_number(self, order_id: str, tracking_number: str) -> None:
        self._find_order(order_id).tracking_number = tracking_number

    def set_return_status(self, return_id: str, status: str) -> None:
        self._find_return(return_id).status = status

    def set_refund_amount(self, return_id: str, amount: float) -> None:
        self._find_return(return_id).refund_amount = amount

    def set_payment_method_status(self, payment_id: str, status: str) -> None:
        self._find_payment(payment_id).status = status

    def set_order_payment_method(self, order_id: str, payment_id: str) -> None:
        self._find_order(order_id).payment_method_id = payment_id

    def set_membership_tier(self, customer_id: str, tier: str) -> None:
        self._find_customer(customer_id).membership_tier = tier

    def set_tax_amount(self, order_id: str, amount: float) -> None:
        order = self._find_order(order_id)
        order.tax_amount = amount
        order.total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )

    def set_shipping_cost(self, order_id: str, amount: float) -> None:
        order = self._find_order(order_id)
        order.shipping_cost = amount
        order.total = _compute_total(
            order.unit_price, order.quantity, order.promo_discount_pct,
            order.shipping_cost, order.tax_amount
        )

    def set_payment_reprocessed(self, order_id: str, value: bool) -> None:
        self._find_order(order_id).payment_reprocessed = value

    # =============================================
    # ASSERTION HELPERS — called by verification
    # =============================================

    def assert_account_status(self, customer_id: str, expected: str) -> bool:
        return self._find_customer(customer_id).account_status == expected

    def assert_unit_price(self, order_id: str, expected: float) -> bool:
        return abs(self._find_order(order_id).unit_price - expected) < 0.01

    def assert_promo_discount(self, order_id: str, expected_pct: float) -> bool:
        return abs(self._find_order(order_id).promo_discount_pct - expected_pct) < 0.01

    def assert_shipping_address(self, order_id: str, expected: str) -> bool:
        return self._find_order(order_id).shipping_address == expected

    def assert_shipping_method(self, order_id: str, expected: str) -> bool:
        return self._find_order(order_id).shipping_method == expected

    def assert_tracking_number(self, order_id: str) -> bool:
        return self._find_order(order_id).tracking_number != ""

    def assert_tracking_number_assigned(self, order_id: str) -> bool:
        return self._find_order(order_id).tracking_number != ""

    def assert_return_status(self, return_id: str, expected: str) -> bool:
        return self._find_return(return_id).status == expected

    def assert_refund_amount(self, return_id: str, expected: float) -> bool:
        return abs(self._find_return(return_id).refund_amount - expected) < 0.01

    def assert_payment_method_status(self, payment_id: str, expected: str) -> bool:
        return self._find_payment(payment_id).status == expected

    def assert_payment_reprocessed(self, order_id: str) -> bool:
        return self._find_order(order_id).payment_reprocessed is True

    def assert_order_payment_method(self, order_id: str, expected: str) -> bool:
        return self._find_order(order_id).payment_method_id == expected

    def assert_membership_tier(self, customer_id: str, expected: str) -> bool:
        return self._find_customer(customer_id).membership_tier == expected

    def assert_tax_amount(self, order_id: str, expected: float) -> bool:
        return abs(self._find_order(order_id).tax_amount - expected) < 0.01

    def assert_shipping_cost(self, order_id: str, expected: float) -> bool:
        return abs(self._find_order(order_id).shipping_cost - expected) < 0.01

    def assert_order_total(self, order_id: str, expected: float) -> bool:
        return abs(self._find_order(order_id).total - expected) < 0.01
