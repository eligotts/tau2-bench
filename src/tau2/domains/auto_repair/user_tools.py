from typing import Any, Dict, List

from tau2.domains.auto_repair.user_data_model import AutoRepairUserDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class AutoRepairUserTools(ToolKitBase):
    db: AutoRepairUserDB

    def __init__(self, db: AutoRepairUserDB):
        super().__init__(db)

    # =============================================
    # READ TOOLS — user's view of their account
    # =============================================

    @is_tool(ToolType.READ)
    def view_my_vehicles(self) -> List[Dict[str, Any]]:
        """View my registered vehicles."""
        return [v.model_dump() for v in self.db.my_vehicles]

    @is_tool(ToolType.READ)
    def view_my_orders(self) -> List[Dict[str, Any]]:
        """View my service orders."""
        return [o.model_dump() for o in self.db.my_orders]

    @is_tool(ToolType.READ)
    def view_my_invoices(self) -> List[Dict[str, Any]]:
        """View my invoices."""
        return [i.model_dump() for i in self.db.my_invoices]

    # =============================================
    # WRITE TOOLS — user actions
    # =============================================

    @is_tool(ToolType.WRITE)
    def approve_repairs(self, order_id: str) -> str:
        """
        Approve repair work on a service order.

        Args:
            order_id: The service order to approve.

        Returns:
            Confirmation of approval.
        """
        self.db.repair_approved[order_id] = True
        return f"Repairs approved for service order {order_id}."

    @is_tool(ToolType.WRITE)
    def make_payment(self, invoice_id: str) -> str:
        """
        Make a payment on an invoice.

        Args:
            invoice_id: The invoice to pay.

        Returns:
            Confirmation of payment.
        """
        self.db.payment_made[invoice_id] = True
        return f"Payment submitted for invoice {invoice_id}."

    @is_tool(ToolType.WRITE)
    def acknowledge_resolution(self, customer_id: str) -> str:
        """
        Acknowledge that an account or administrative issue has been resolved.

        Args:
            customer_id: Your customer ID.

        Returns:
            Confirmation of acknowledgment.
        """
        self.db.resolution_acknowledged[customer_id] = True
        return "Resolution acknowledged. Thank you."

    @is_tool(ToolType.WRITE)
    def confirm_warranty_renewal(self, warranty_id: str) -> str:
        """
        Confirm renewal of a warranty plan.

        Args:
            warranty_id: The warranty plan ID.

        Returns:
            Confirmation of warranty renewal.
        """
        self.db.warranty_renewal_confirmed[warranty_id] = True
        return f"Warranty renewal confirmed for {warranty_id}."

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

    def assert_repair_approved(self, order_id: str) -> bool:
        return self.db.repair_approved.get(order_id, False)

    def assert_payment_made(self, invoice_id: str) -> bool:
        return self.db.payment_made.get(invoice_id, False)

    def assert_resolution_acknowledged(self, customer_id: str) -> bool:
        return self.db.resolution_acknowledged.get(customer_id, False)

    def assert_warranty_renewal_confirmed(self, warranty_id: str) -> bool:
        return self.db.warranty_renewal_confirmed.get(warranty_id, False)
