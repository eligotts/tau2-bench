from typing import Any, Dict, List, Optional

from tau2.domains.vet_clinic.data_model import (
    Appointment,
    Invoice,
    Owner,
    Pet,
    Treatment,
    VetClinicDB,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class VetClinicTools(ToolKitBase):
    """Tools available to the assistant for veterinary clinic support.

    Gate structure enforced by tools:
      Depth 0: Owner (always accessible)
      Depth 1: Pet, Appointment (require Owner.identity_verified == True)
      Depth 2: Treatment (require Appointment.checked_in == True)
      Depth 3: Invoice (require Treatment.status == "completed")

    Both READ and WRITE tools enforce gates. The agent cannot see or
    modify records at depth N until all gates at depths 0..N-1 are open.
    This creates real progressive disclosure: the agent must fix gates
    in order to proceed deeper.
    """

    db: VetClinicDB

    def __init__(self, db: VetClinicDB):
        super().__init__(db)

    # ---------------------------------------------------------------
    # Internal helpers (not tools)
    # ---------------------------------------------------------------

    def _find_owner(self, owner_id: str) -> Optional[Owner]:
        for o in self.db.owners:
            if o.owner_id == owner_id:
                return o
        return None

    def _find_owner_by_name(self, name: str) -> Optional[Owner]:
        for o in self.db.owners:
            if o.owner_name.lower() == name.lower():
                return o
        return None

    def _find_pet(self, pet_id: str) -> Optional[Pet]:
        for p in self.db.pets:
            if p.pet_id == pet_id:
                return p
        return None

    def _find_appointment(self, appointment_id: str) -> Optional[Appointment]:
        for a in self.db.appointments:
            if a.appointment_id == appointment_id:
                return a
        return None

    def _find_treatment(self, treatment_id: str) -> Optional[Treatment]:
        for t in self.db.treatments:
            if t.treatment_id == treatment_id:
                return t
        return None

    def _find_invoice(self, invoice_id: str) -> Optional[Invoice]:
        for i in self.db.invoices:
            if i.invoice_id == invoice_id:
                return i
        return None

    # ---------------------------------------------------------------
    # Gate enforcement helpers
    # ---------------------------------------------------------------

    def _owner_for_pet(self, pet_id: str) -> Optional[Owner]:
        """Find the owner of a pet."""
        pet = self._find_pet(pet_id)
        if pet is None:
            return None
        return self._find_owner(pet.owner_id)

    def _owner_for_appointment(self, appointment_id: str) -> Optional[Owner]:
        """Find the owner via appointment → pet → owner."""
        appt = self._find_appointment(appointment_id)
        if appt is None:
            return None
        return self._owner_for_pet(appt.pet_id)

    def _appointment_for_treatment(self, treatment_id: str) -> Optional[Appointment]:
        """Find the appointment for a treatment."""
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            return None
        return self._find_appointment(treatment.appointment_id)

    def _treatment_for_invoice(self, invoice_id: str) -> Optional[Treatment]:
        """Find the treatment for an invoice."""
        invoice = self._find_invoice(invoice_id)
        if invoice is None:
            return None
        return self._find_treatment(invoice.treatment_id)

    def _require_identity_verified(self, owner: Owner) -> None:
        """Gate 1: Owner identity must be verified to access pet/appointment records."""
        if not owner.identity_verified:
            raise ValueError(
                f"Access denied: owner {owner.owner_id} ({owner.owner_name}) "
                f"identity is not verified. Verify identity first using "
                f"update_owner_identity_verified before accessing pet records."
            )

    def _require_checked_in(self, appointment: Appointment) -> None:
        """Gate 2: Appointment must be checked in to access treatment records."""
        if not appointment.checked_in:
            raise ValueError(
                f"Access denied: appointment {appointment.appointment_id} is not "
                f"checked in. Confirm check-in using update_appointment_checked_in "
                f"before accessing treatment records."
            )

    def _require_treatment_completed(self, treatment: Treatment) -> None:
        """Gate 3: Treatment must be completed to access invoice records."""
        if treatment.status != "completed":
            raise ValueError(
                f"Access denied: treatment {treatment.treatment_id} status is "
                f"'{treatment.status}', not 'completed'. Update treatment status "
                f"using update_treatment_status before accessing invoice records."
            )

    # ---------------------------------------------------------------
    # READ tools
    # ---------------------------------------------------------------

    # --- Depth 0: Owner (no gate) ---

    @is_tool(ToolType.READ)
    def get_owner_by_name(self, name: str) -> Dict[str, Any]:
        """
        Look up a pet owner by their full name.

        Args:
            name: The full name of the owner (e.g., 'Sarah Chen').

        Returns:
            Owner details including owner_id, phone, and identity verification status.
        """
        owner = self._find_owner_by_name(name)
        if owner is None:
            raise ValueError(f"Owner with name '{name}' not found.")
        return owner.model_dump()

    @is_tool(ToolType.READ)
    def get_owner(self, owner_id: str) -> Dict[str, Any]:
        """
        Look up a pet owner by their ID.

        Args:
            owner_id: The unique identifier of the owner.

        Returns:
            Owner details including name, phone, and identity verification status.
        """
        owner = self._find_owner(owner_id)
        if owner is None:
            raise ValueError(f"Owner '{owner_id}' not found.")
        return owner.model_dump()

    # --- Depth 1: Pet, Appointment (require identity_verified) ---

    @is_tool(ToolType.READ)
    def get_pet(self, pet_id: str) -> Dict[str, Any]:
        """
        Look up a pet by its ID. Requires owner identity to be verified.

        Args:
            pet_id: The unique identifier of the pet.

        Returns:
            Pet details including name, species, vaccination status, and microchip status.
        """
        pet = self._find_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        owner = self._find_owner(pet.owner_id)
        if owner is not None:
            self._require_identity_verified(owner)
        return pet.model_dump()

    @is_tool(ToolType.READ)
    def get_pets_by_owner(self, owner_id: str) -> List[Dict[str, Any]]:
        """
        Get all pets belonging to an owner. Requires owner identity to be verified.

        Args:
            owner_id: The unique identifier of the owner.

        Returns:
            List of pet details for this owner.
        """
        owner = self._find_owner(owner_id)
        if owner is None:
            raise ValueError(f"Owner '{owner_id}' not found.")
        self._require_identity_verified(owner)
        pets = [p for p in self.db.pets if p.owner_id == owner_id]
        return [p.model_dump() for p in pets]

    @is_tool(ToolType.READ)
    def get_appointment(self, appointment_id: str) -> Dict[str, Any]:
        """
        Look up an appointment by its ID. Requires owner identity to be verified.

        Args:
            appointment_id: The unique identifier of the appointment.

        Returns:
            Appointment details including date, type, and check-in status.
        """
        appt = self._find_appointment(appointment_id)
        if appt is None:
            raise ValueError(f"Appointment '{appointment_id}' not found.")
        owner = self._owner_for_appointment(appointment_id)
        if owner is not None:
            self._require_identity_verified(owner)
        return appt.model_dump()

    @is_tool(ToolType.READ)
    def get_appointments_by_pet(self, pet_id: str) -> List[Dict[str, Any]]:
        """
        Get all appointments for a pet. Requires owner identity to be verified.

        Args:
            pet_id: The unique identifier of the pet.

        Returns:
            List of appointment details for this pet.
        """
        pet = self._find_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        owner = self._find_owner(pet.owner_id)
        if owner is not None:
            self._require_identity_verified(owner)
        appts = [a for a in self.db.appointments if a.pet_id == pet_id]
        return [a.model_dump() for a in appts]

    # --- Depth 2: Treatment (require identity_verified AND checked_in) ---

    @is_tool(ToolType.READ)
    def get_treatment(self, treatment_id: str) -> Dict[str, Any]:
        """
        Look up a treatment by its ID. Requires owner identity to be verified
        and the appointment to be checked in.

        Args:
            treatment_id: The unique identifier of the treatment.

        Returns:
            Treatment details including medication, dosage, and status.
        """
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            raise ValueError(f"Treatment '{treatment_id}' not found.")
        appt = self._appointment_for_treatment(treatment_id)
        if appt is not None:
            owner = self._owner_for_appointment(appt.appointment_id)
            if owner is not None:
                self._require_identity_verified(owner)
            self._require_checked_in(appt)
        return treatment.model_dump()

    # --- Depth 3: Invoice (require identity_verified AND checked_in AND completed) ---

    @is_tool(ToolType.READ)
    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Look up an invoice by its ID. Requires owner identity to be verified,
        appointment to be checked in, and treatment to be completed.

        Args:
            invoice_id: The unique identifier of the invoice.

        Returns:
            Invoice details including amount and payment status.
        """
        invoice = self._find_invoice(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice '{invoice_id}' not found.")
        treatment = self._treatment_for_invoice(invoice_id)
        if treatment is not None:
            appt = self._appointment_for_treatment(treatment.treatment_id)
            if appt is not None:
                owner = self._owner_for_appointment(appt.appointment_id)
                if owner is not None:
                    self._require_identity_verified(owner)
                self._require_checked_in(appt)
            self._require_treatment_completed(treatment)
        return invoice.model_dump()

    # ---------------------------------------------------------------
    # WRITE tools
    # ---------------------------------------------------------------

    # --- Depth 0: Owner fields (no gate) ---

    @is_tool(ToolType.WRITE)
    def update_owner_phone(self, owner_id: str, phone: str) -> str:
        """
        Update the contact phone number for an owner.

        Args:
            owner_id: The unique identifier of the owner.
            phone: The correct phone number.

        Returns:
            Confirmation message.
        """
        owner = self._find_owner(owner_id)
        if owner is None:
            raise ValueError(f"Owner '{owner_id}' not found.")
        owner.phone = phone
        return f"Phone number for {owner.owner_name} updated to {phone}."

    @is_tool(ToolType.WRITE)
    def update_owner_identity_verified(self, owner_id: str, identity_verified: bool) -> str:
        """
        Update the identity verification status for an owner.

        Args:
            owner_id: The unique identifier of the owner.
            identity_verified: Whether the owner's identity is verified.

        Returns:
            Confirmation message.
        """
        owner = self._find_owner(owner_id)
        if owner is None:
            raise ValueError(f"Owner '{owner_id}' not found.")
        owner.identity_verified = identity_verified
        status = "verified" if identity_verified else "unverified"
        return f"Identity for {owner.owner_name} marked as {status}."

    # --- Depth 1: Pet, Appointment fields (require identity_verified) ---

    @is_tool(ToolType.WRITE)
    def update_pet_vaccination_status(self, pet_id: str, vaccination_status: str) -> str:
        """
        Update the vaccination status for a pet. Requires owner identity to be verified.

        Args:
            pet_id: The unique identifier of the pet.
            vaccination_status: The vaccination status ('current', 'expired', or 'unknown').

        Returns:
            Confirmation message.
        """
        pet = self._find_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        owner = self._find_owner(pet.owner_id)
        if owner is not None:
            self._require_identity_verified(owner)
        valid = {"current", "expired", "unknown"}
        if vaccination_status not in valid:
            raise ValueError(f"Invalid status '{vaccination_status}'. Must be one of {valid}.")
        pet.vaccination_status = vaccination_status
        return f"Vaccination status for {pet.pet_name} updated to {vaccination_status}."

    @is_tool(ToolType.WRITE)
    def update_pet_microchip_registered(self, pet_id: str, microchip_registered: bool) -> str:
        """
        Update the microchip registration status for a pet. Requires owner identity to be verified.

        Args:
            pet_id: The unique identifier of the pet.
            microchip_registered: Whether the microchip is registered.

        Returns:
            Confirmation message.
        """
        pet = self._find_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        owner = self._find_owner(pet.owner_id)
        if owner is not None:
            self._require_identity_verified(owner)
        pet.microchip_registered = microchip_registered
        status = "registered" if microchip_registered else "unregistered"
        return f"Microchip for {pet.pet_name} marked as {status}."

    @is_tool(ToolType.WRITE)
    def update_appointment_appointment_type(self, appointment_id: str, appointment_type: str) -> str:
        """
        Update the appointment type. Requires owner identity to be verified.

        Args:
            appointment_id: The unique identifier of the appointment.
            appointment_type: The correct appointment type ('checkup', 'vaccination', 'surgery', 'dental', or 'grooming').

        Returns:
            Confirmation message.
        """
        appt = self._find_appointment(appointment_id)
        if appt is None:
            raise ValueError(f"Appointment '{appointment_id}' not found.")
        owner = self._owner_for_appointment(appointment_id)
        if owner is not None:
            self._require_identity_verified(owner)
        valid = {"checkup", "vaccination", "surgery", "dental", "grooming"}
        if appointment_type not in valid:
            raise ValueError(f"Invalid type '{appointment_type}'. Must be one of {valid}.")
        appt.appointment_type = appointment_type
        return f"Appointment {appointment_id} type updated to {appointment_type}."

    @is_tool(ToolType.WRITE)
    def update_appointment_checked_in(self, appointment_id: str, checked_in: bool) -> str:
        """
        Update the check-in status for an appointment. Requires owner identity to be verified.

        Args:
            appointment_id: The unique identifier of the appointment.
            checked_in: Whether the pet has been checked in.

        Returns:
            Confirmation message.
        """
        appt = self._find_appointment(appointment_id)
        if appt is None:
            raise ValueError(f"Appointment '{appointment_id}' not found.")
        owner = self._owner_for_appointment(appointment_id)
        if owner is not None:
            self._require_identity_verified(owner)
        appt.checked_in = checked_in
        status = "checked in" if checked_in else "not checked in"
        return f"Appointment {appointment_id} marked as {status}."

    # --- Depth 2: Treatment fields (require identity_verified AND checked_in) ---

    @is_tool(ToolType.WRITE)
    def update_treatment_medication(self, treatment_id: str, medication: str) -> str:
        """
        Update the medication for a treatment. Requires owner identity to be verified
        and the appointment to be checked in.

        Args:
            treatment_id: The unique identifier of the treatment.
            medication: The correct medication name.

        Returns:
            Confirmation message.
        """
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            raise ValueError(f"Treatment '{treatment_id}' not found.")
        appt = self._appointment_for_treatment(treatment_id)
        if appt is not None:
            owner = self._owner_for_appointment(appt.appointment_id)
            if owner is not None:
                self._require_identity_verified(owner)
            self._require_checked_in(appt)
        treatment.medication = medication
        return f"Treatment {treatment_id} medication updated to {medication}."

    @is_tool(ToolType.WRITE)
    def update_treatment_dosage(self, treatment_id: str, dosage: str) -> str:
        """
        Update the dosage for a treatment. Requires owner identity to be verified
        and the appointment to be checked in.

        Args:
            treatment_id: The unique identifier of the treatment.
            dosage: The correct dosage instructions.

        Returns:
            Confirmation message.
        """
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            raise ValueError(f"Treatment '{treatment_id}' not found.")
        appt = self._appointment_for_treatment(treatment_id)
        if appt is not None:
            owner = self._owner_for_appointment(appt.appointment_id)
            if owner is not None:
                self._require_identity_verified(owner)
            self._require_checked_in(appt)
        treatment.dosage = dosage
        return f"Treatment {treatment_id} dosage updated to {dosage}."

    @is_tool(ToolType.WRITE)
    def update_treatment_status(self, treatment_id: str, status: str) -> str:
        """
        Update the status for a treatment. Requires owner identity to be verified
        and the appointment to be checked in.

        Args:
            treatment_id: The unique identifier of the treatment.
            status: The correct status ('in_progress', 'completed', 'cancelled', or 'on_hold').

        Returns:
            Confirmation message.
        """
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            raise ValueError(f"Treatment '{treatment_id}' not found.")
        appt = self._appointment_for_treatment(treatment_id)
        if appt is not None:
            owner = self._owner_for_appointment(appt.appointment_id)
            if owner is not None:
                self._require_identity_verified(owner)
            self._require_checked_in(appt)
        valid = {"in_progress", "completed", "cancelled", "on_hold"}
        if status not in valid:
            raise ValueError(f"Invalid status '{status}'. Must be one of {valid}.")
        treatment.status = status
        return f"Treatment {treatment_id} status updated to {status}."

    # --- Depth 3: Invoice fields (require all three gates) ---

    @is_tool(ToolType.WRITE)
    def update_invoice_payment_status(self, invoice_id: str, payment_status: str) -> str:
        """
        Update the payment status for an invoice. Requires owner identity to be verified,
        appointment to be checked in, and treatment to be completed.

        Args:
            invoice_id: The unique identifier of the invoice.
            payment_status: The correct payment status ('pending', 'paid', 'overdue', or 'disputed').

        Returns:
            Confirmation message.
        """
        invoice = self._find_invoice(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice '{invoice_id}' not found.")
        treatment = self._treatment_for_invoice(invoice_id)
        if treatment is not None:
            appt = self._appointment_for_treatment(treatment.treatment_id)
            if appt is not None:
                owner = self._owner_for_appointment(appt.appointment_id)
                if owner is not None:
                    self._require_identity_verified(owner)
                self._require_checked_in(appt)
            self._require_treatment_completed(treatment)
        valid = {"pending", "paid", "overdue", "disputed"}
        if payment_status not in valid:
            raise ValueError(f"Invalid status '{payment_status}'. Must be one of {valid}.")
        invoice.payment_status = payment_status
        return f"Invoice {invoice_id} payment status updated to {payment_status}."

    # ---------------------------------------------------------------
    # GENERIC tools
    # ---------------------------------------------------------------

    @is_tool(ToolType.GENERIC)
    def transfer_to_human(self, summary: str) -> str:
        """
        Transfer the conversation to a human specialist or supervisor.

        Args:
            summary: A brief summary of the situation and reason for transfer.

        Returns:
            Confirmation that the transfer has been initiated.
        """
        return f"Transfer initiated. Summary: {summary}"

    # ---------------------------------------------------------------
    # Setup helpers (not tools -- used by scenario init)
    # These BYPASS gate checks because init must break fields
    # before gates are open.
    # ---------------------------------------------------------------

    def set_owner_phone(self, owner_id: str, phone: str) -> None:
        owner = self._find_owner(owner_id)
        if owner is None:
            raise ValueError(f"Owner '{owner_id}' not found.")
        owner.phone = phone

    def set_owner_identity_verified(self, owner_id: str, identity_verified: bool) -> None:
        owner = self._find_owner(owner_id)
        if owner is None:
            raise ValueError(f"Owner '{owner_id}' not found.")
        owner.identity_verified = identity_verified

    def set_pet_vaccination_status(self, pet_id: str, vaccination_status: str) -> None:
        pet = self._find_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        pet.vaccination_status = vaccination_status

    def set_pet_microchip_registered(self, pet_id: str, microchip_registered: bool) -> None:
        pet = self._find_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        pet.microchip_registered = microchip_registered

    def set_appointment_appointment_type(self, appointment_id: str, appointment_type: str) -> None:
        appt = self._find_appointment(appointment_id)
        if appt is None:
            raise ValueError(f"Appointment '{appointment_id}' not found.")
        appt.appointment_type = appointment_type

    def set_appointment_checked_in(self, appointment_id: str, checked_in: bool) -> None:
        appt = self._find_appointment(appointment_id)
        if appt is None:
            raise ValueError(f"Appointment '{appointment_id}' not found.")
        appt.checked_in = checked_in

    def set_treatment_medication(self, treatment_id: str, medication: str) -> None:
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            raise ValueError(f"Treatment '{treatment_id}' not found.")
        treatment.medication = medication

    def set_treatment_dosage(self, treatment_id: str, dosage: str) -> None:
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            raise ValueError(f"Treatment '{treatment_id}' not found.")
        treatment.dosage = dosage

    def set_treatment_status(self, treatment_id: str, status: str) -> None:
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            raise ValueError(f"Treatment '{treatment_id}' not found.")
        treatment.status = status

    def set_invoice_payment_status(self, invoice_id: str, payment_status: str) -> None:
        invoice = self._find_invoice(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice '{invoice_id}' not found.")
        invoice.payment_status = payment_status

    # ---------------------------------------------------------------
    # Assertion helpers (not tools -- used by verification)
    # These also BYPASS gate checks.
    # ---------------------------------------------------------------

    def assert_owner_phone(self, owner_id: str, expected: str) -> bool:
        owner = self._find_owner(owner_id)
        if owner is None:
            return False
        return owner.phone == expected

    def assert_owner_identity_verified(self, owner_id: str, expected: bool) -> bool:
        owner = self._find_owner(owner_id)
        if owner is None:
            return False
        return owner.identity_verified == expected

    def assert_pet_vaccination_status(self, pet_id: str, expected: str) -> bool:
        pet = self._find_pet(pet_id)
        if pet is None:
            return False
        return pet.vaccination_status == expected

    def assert_pet_microchip_registered(self, pet_id: str, expected: bool) -> bool:
        pet = self._find_pet(pet_id)
        if pet is None:
            return False
        return pet.microchip_registered == expected

    def assert_appointment_appointment_type(self, appointment_id: str, expected: str) -> bool:
        appt = self._find_appointment(appointment_id)
        if appt is None:
            return False
        return appt.appointment_type == expected

    def assert_appointment_checked_in(self, appointment_id: str, expected: bool) -> bool:
        appt = self._find_appointment(appointment_id)
        if appt is None:
            return False
        return appt.checked_in == expected

    def assert_treatment_medication(self, treatment_id: str, expected: str) -> bool:
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            return False
        return treatment.medication == expected

    def assert_treatment_dosage(self, treatment_id: str, expected: str) -> bool:
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            return False
        return treatment.dosage == expected

    def assert_treatment_status(self, treatment_id: str, expected: str) -> bool:
        treatment = self._find_treatment(treatment_id)
        if treatment is None:
            return False
        return treatment.status == expected

    def assert_invoice_payment_status(self, invoice_id: str, expected: str) -> bool:
        invoice = self._find_invoice(invoice_id)
        if invoice is None:
            return False
        return invoice.payment_status == expected
