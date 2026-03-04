from typing import Any, Dict, List

from tau2.domains.vet_clinic.user_data_model import VetClinicUserDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class VetClinicUserTools(ToolKitBase):
    """Tools available to the user (pet owner)."""

    db: VetClinicUserDB

    def __init__(self, db: VetClinicUserDB):
        super().__init__(db)

    # ---------------------------------------------------------------
    # READ tools
    # ---------------------------------------------------------------

    @is_tool(ToolType.READ)
    def view_my_pets(self) -> List[Dict[str, Any]]:
        """
        View your pets' information.

        Returns:
            List of your pets with name, species, and vaccination status.
        """
        return [p.model_dump() for p in self.db.my_pets]

    @is_tool(ToolType.READ)
    def view_my_appointments(self) -> List[Dict[str, Any]]:
        """
        View your pet's appointments.

        Returns:
            List of appointments with date, type, and check-in status.
        """
        return [a.model_dump() for a in self.db.my_appointments]

    @is_tool(ToolType.READ)
    def view_my_treatments(self) -> List[Dict[str, Any]]:
        """
        View your pet's treatments.

        Returns:
            List of treatments with medication, dosage, and status.
        """
        return [t.model_dump() for t in self.db.my_treatments]

    @is_tool(ToolType.READ)
    def view_my_invoices(self) -> List[Dict[str, Any]]:
        """
        View your invoices.

        Returns:
            List of invoices with amount and payment status.
        """
        return [i.model_dump() for i in self.db.my_invoices]

    # ---------------------------------------------------------------
    # WRITE tools
    # ---------------------------------------------------------------

    @is_tool(ToolType.WRITE)
    def acknowledge_resolution(self, owner_id: str) -> str:
        """
        Acknowledge that an issue has been resolved.

        Args:
            owner_id: Your owner ID.

        Returns:
            Acknowledgment message.
        """
        self.db.resolution_acknowledged[owner_id] = True
        return f"Resolution acknowledged for owner {owner_id}."

    @is_tool(ToolType.WRITE)
    def confirm_treatment(self, treatment_id: str) -> str:
        """
        Confirm that a treatment update is correct.

        Args:
            treatment_id: The treatment to confirm.

        Returns:
            Confirmation message.
        """
        self.db.treatment_confirmed[treatment_id] = True
        return f"Treatment {treatment_id} confirmed."

    @is_tool(ToolType.WRITE)
    def acknowledge_invoice(self, invoice_id: str) -> str:
        """
        Acknowledge an invoice update.

        Args:
            invoice_id: The invoice to acknowledge.

        Returns:
            Acknowledgment message.
        """
        self.db.invoice_acknowledged[invoice_id] = True
        return f"Invoice {invoice_id} acknowledged."

    # ---------------------------------------------------------------
    # Setup helpers (not tools -- used by scenario init)
    # ---------------------------------------------------------------

    def set_owner_info(self, name: str, owner_id: str) -> None:
        self.db.owner_name = name
        self.db.owner_id = owner_id

    # ---------------------------------------------------------------
    # Assertion helpers (not tools -- used by verification)
    # ---------------------------------------------------------------

    def assert_resolution_acknowledged(self, owner_id: str) -> bool:
        return self.db.resolution_acknowledged.get(owner_id, False)

    def assert_treatment_confirmed(self, treatment_id: str) -> bool:
        return self.db.treatment_confirmed.get(treatment_id, False)

    def assert_invoice_acknowledged(self, invoice_id: str) -> bool:
        return self.db.invoice_acknowledged.get(invoice_id, False)
