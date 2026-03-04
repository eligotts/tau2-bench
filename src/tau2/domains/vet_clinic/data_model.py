from typing import List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class Owner(BaseModelNoExtra):
    owner_id: str
    owner_name: str
    phone: str
    identity_verified: bool


class Pet(BaseModelNoExtra):
    pet_id: str
    owner_id: str
    pet_name: str
    species: str  # dog, cat, bird, rabbit
    vaccination_status: str  # current, expired, unknown
    microchip_registered: bool


class Appointment(BaseModelNoExtra):
    appointment_id: str
    pet_id: str
    appt_date: str
    appointment_type: str  # checkup, vaccination, surgery, dental, grooming
    checked_in: bool


class Treatment(BaseModelNoExtra):
    treatment_id: str
    appointment_id: str
    medication: str
    dosage: str
    status: str  # in_progress, completed, cancelled, on_hold


class Invoice(BaseModelNoExtra):
    invoice_id: str
    treatment_id: str
    amount: float
    payment_status: str  # pending, paid, overdue, disputed


class VetClinicDB(DB):
    owners: List[Owner]
    pets: List[Pet]
    appointments: List[Appointment]
    treatments: List[Treatment]
    invoices: List[Invoice]
