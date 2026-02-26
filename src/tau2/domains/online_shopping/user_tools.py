from typing import Any, Dict, List

from tau2.domains.online_shopping.user_data_model import OnlineShoppingUserDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class OnlineShoppingUserTools(ToolKitBase):
    db: OnlineShoppingUserDB

    def __init__(self, db: OnlineShoppingUserDB):
        super().__init__(db)

    # =============================================
    # READ TOOLS — user's view of their account
    # =============================================

    @is_tool(ToolType.READ)
    def view_my_orders(self) -> List[Dict[str, Any]]:
        """View my orders."""
        return [o.model_dump() for o in self.db.my_orders]

    @is_tool(ToolType.READ)
    def view_my_returns(self) -> List[Dict[str, Any]]:
        """View my return requests."""
        return [r.model_dump() for r in self.db.my_returns]

    # =============================================
    # WRITE TOOLS — user actions
    # =============================================

    @is_tool(ToolType.WRITE)
    def acknowledge_resolution(self, customer_id: str) -> str:
        """
        Acknowledge that an account issue has been resolved.

        Args:
            customer_id: Your customer ID.

        Returns:
            Confirmation of acknowledgment.
        """
        self.db.resolution_acknowledged[customer_id] = True
        return "Resolution acknowledged. Thank you."

    @is_tool(ToolType.WRITE)
    def confirm_pricing_update(self, order_id: str) -> str:
        """
        Confirm that a pricing correction has been applied to your order.

        Args:
            order_id: The order that was updated.

        Returns:
            Confirmation message.
        """
        self.db.pricing_update_confirmed[order_id] = True
        return f"Pricing update confirmed for {order_id}."

    @is_tool(ToolType.WRITE)
    def confirm_shipping_update(self, order_id: str) -> str:
        """
        Confirm that a shipping update has been applied to your order.

        Args:
            order_id: The order that was updated.

        Returns:
            Confirmation message.
        """
        self.db.shipping_update_confirmed[order_id] = True
        return f"Shipping update confirmed for {order_id}."

    @is_tool(ToolType.WRITE)
    def confirm_tracking_update(self, order_id: str) -> str:
        """
        Confirm that tracking information has been assigned to your order.

        Args:
            order_id: The order that was updated.

        Returns:
            Confirmation message.
        """
        self.db.tracking_update_confirmed[order_id] = True
        return f"Tracking update confirmed for {order_id}."

    @is_tool(ToolType.WRITE)
    def confirm_payment_update(self, order_id: str) -> str:
        """
        Confirm that a payment issue has been resolved on your order.

        Args:
            order_id: The order that was updated.

        Returns:
            Confirmation message.
        """
        self.db.payment_update_confirmed[order_id] = True
        return f"Payment update confirmed for {order_id}."

    @is_tool(ToolType.WRITE)
    def confirm_billing_correction(self, order_id: str) -> str:
        """
        Confirm that a billing correction has been applied to your order.

        Args:
            order_id: The order that was updated.

        Returns:
            Confirmation message.
        """
        self.db.billing_correction_confirmed[order_id] = True
        return f"Billing correction confirmed for {order_id}."

    @is_tool(ToolType.WRITE)
    def confirm_return_resolution(self, return_id: str) -> str:
        """
        Confirm that a return issue has been resolved.

        Args:
            return_id: The return request that was resolved.

        Returns:
            Confirmation message.
        """
        self.db.return_resolution_confirmed[return_id] = True
        return f"Return resolution confirmed for {return_id}."

    @is_tool(ToolType.WRITE)
    def update_payment_info(self, payment_id: str) -> str:
        """
        Update your payment method with new card details.

        Args:
            payment_id: The payment method to update.

        Returns:
            Confirmation message.
        """
        self.db.payment_info_updated[payment_id] = True
        return f"Payment information updated for {payment_id}."

    @is_tool(ToolType.WRITE)
    def confirm_membership_renewal(self, customer_id: str) -> str:
        """
        Confirm that your membership has been renewed.

        Args:
            customer_id: Your customer ID.

        Returns:
            Confirmation message.
        """
        self.db.membership_renewal_confirmed[customer_id] = True
        return f"Membership renewal confirmed for {customer_id}."

    # =============================================
    # SETUP HELPERS — called by scenarios init
    # =============================================

    def set_customer_info(self, name: str, customer_id: str) -> None:
        """Set the user's identity for this scenario."""
        self.db.customer_name = name
        self.db.customer_id = customer_id

    # =============================================
    # ASSERTION HELPERS — called by verification
    # =============================================

    def assert_resolution_acknowledged(self, customer_id: str) -> bool:
        return self.db.resolution_acknowledged.get(customer_id, False)

    def assert_pricing_update_confirmed(self, order_id: str) -> bool:
        return self.db.pricing_update_confirmed.get(order_id, False)

    def assert_shipping_update_confirmed(self, order_id: str) -> bool:
        return self.db.shipping_update_confirmed.get(order_id, False)

    def assert_tracking_update_confirmed(self, order_id: str) -> bool:
        return self.db.tracking_update_confirmed.get(order_id, False)

    def assert_return_resolution_confirmed(self, return_id: str) -> bool:
        return self.db.return_resolution_confirmed.get(return_id, False)

    def assert_payment_info_updated(self, payment_id: str) -> bool:
        return self.db.payment_info_updated.get(payment_id, False)

    def assert_payment_update_confirmed(self, order_id: str) -> bool:
        return self.db.payment_update_confirmed.get(order_id, False)

    def assert_membership_renewal_confirmed(self, customer_id: str) -> bool:
        return self.db.membership_renewal_confirmed.get(customer_id, False)

    def assert_billing_correction_confirmed(self, order_id: str) -> bool:
        return self.db.billing_correction_confirmed.get(order_id, False)
