from typing import Dict, List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class PetSummary(BaseModelNoExtra):
    pet_id: str
    pet_name: str
    species: str
    vaccination_status: str


class AppointmentSummary(BaseModelNoExtra):
    appointment_id: str
    pet_name: str
    appt_date: str
    appointment_type: str
    checked_in: bool


class TreatmentSummary(BaseModelNoExtra):
    treatment_id: str
    pet_name: str
    medication: str
    dosage: str
    status: str


class InvoiceSummary(BaseModelNoExtra):
    invoice_id: str
    amount: float
    payment_status: str


class VetClinicUserDB(DB):
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    my_pets: List[PetSummary] = []
    my_appointments: List[AppointmentSummary] = []
    my_treatments: List[TreatmentSummary] = []
    my_invoices: List[InvoiceSummary] = []
    resolution_acknowledged: Dict[str, bool] = {}  # owner_id -> bool
    treatment_confirmed: Dict[str, bool] = {}  # treatment_id -> bool
    invoice_acknowledged: Dict[str, bool] = {}  # invoice_id -> bool
