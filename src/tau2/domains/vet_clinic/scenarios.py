"""Vet clinic scenario definitions using the Recipe Engine (FaultLayerConfig).

Generates tasks via cartesian product of fault groups across entities.
Each entity is a dict built from joined DB records (owner + pet + appointment + treatment + invoice).

10 fault groups with gate structure creating depth:
  Owner (depth 0) → Pet (depth 1) → Appointment (depth 1) → Treatment (depth 2) → Invoice (depth 3)
  Gates: identity_verified, checked_in, treatment.status

Gate fields:
  - identity_verified: must be True to access pet/appointment records
  - checked_in: must be True to access treatment records
  - treatment.status: must be "completed" to access invoice records
"""

from pathlib import Path
from typing import Any, Callable, Optional

from tau2.domains.vet_clinic.data_model import VetClinicDB
from tau2.domains.vet_clinic.environment import get_environment
from tau2.domains.vet_clinic.utils import (
    VET_CLINIC_DB_PATH,
    VET_CLINIC_POLICY_PATH,
    VET_CLINIC_TASK_SET_PATH,
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
    Persona(name="regular_owner", description=(
        "You are a friendly and organized pet owner. You clearly describe your "
        "issue and follow the agent's instructions without hesitation. You provide "
        "all requested information promptly."
    )),
    Persona(name="worried_owner", description=(
        "You are a worried pet owner who is anxious about your pet's care. "
        "You sometimes ask follow-up questions and may express concern, but you "
        "ultimately cooperate when asked to take action."
    )),
]


# ===================================================================
# User Template
# ===================================================================

USER_TEMPLATE = UserTemplate(
    domain="vet_clinic",
    reason_for_call=(
        "You are contacting Pawsitive Care Veterinary Clinic because you have issues "
        "with your pet's records — identity verification, vaccination records, microchip "
        "registration, appointments, treatments, or billing."
    ),
    known_info=(
        "You are {owner_name} (owner ID: {owner_id}). Your pet is {pet_name}. "
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
        "Owner {owner_name} (ID: {owner_id}) contacting about pet {pet_name}. "
        "{fault_descriptions}"
    ),
    purpose=(
        "Test resolution of veterinary clinic support issues including identity "
        "verification, pet records, appointments, treatments, and billing."
    ),
)


# ===================================================================
# Entity construction
# ===================================================================

def _build_entities(db: VetClinicDB) -> list[dict[str, Any]]:
    """Build entity dicts by joining owner + pet + appointment + treatment + invoice.

    Each entity represents one owner, enriched with their first pet,
    first appointment, first treatment, and first invoice. This gives
    the fault layers enough fields to template against.
    """
    pet_by_owner: dict[str, Any] = {}
    for p in db.pets:
        if p.owner_id not in pet_by_owner:
            pet_by_owner[p.owner_id] = p

    appt_by_pet: dict[str, Any] = {}
    for a in db.appointments:
        if a.pet_id not in appt_by_pet:
            appt_by_pet[a.pet_id] = a

    treatment_by_appt: dict[str, Any] = {}
    for t in db.treatments:
        if t.appointment_id not in treatment_by_appt:
            treatment_by_appt[t.appointment_id] = t

    invoice_by_treatment: dict[str, Any] = {}
    for inv in db.invoices:
        if inv.treatment_id not in invoice_by_treatment:
            invoice_by_treatment[inv.treatment_id] = inv

    entities = []
    for owner in db.owners:
        pet = pet_by_owner.get(owner.owner_id)
        appt = appt_by_pet.get(pet.pet_id) if pet else None
        treatment = treatment_by_appt.get(appt.appointment_id) if appt else None
        invoice = invoice_by_treatment.get(treatment.treatment_id) if treatment else None

        entity: dict[str, Any] = {
            # Owner fields
            "owner_id": owner.owner_id,
            "owner_name": owner.owner_name,
            "phone": owner.phone,
            "correct_phone": owner.phone,
            "identity_verified": owner.identity_verified,
            # Pet fields
            "pet_id": pet.pet_id if pet else None,
            "pet_name": pet.pet_name if pet else None,
            "species": pet.species if pet else None,
            "vaccination_status": pet.vaccination_status if pet else None,
            "correct_vaccination_status": pet.vaccination_status if pet else None,
            "microchip_registered": pet.microchip_registered if pet else None,
            # Appointment fields
            "appointment_id": appt.appointment_id if appt else None,
            "appt_date": appt.appt_date if appt else None,
            "appointment_type": appt.appointment_type if appt else None,
            "correct_appointment_type": appt.appointment_type if appt else None,
            "checked_in": appt.checked_in if appt else None,
            # Treatment fields
            "treatment_id": treatment.treatment_id if treatment else None,
            "medication": treatment.medication if treatment else None,
            "correct_medication": treatment.medication if treatment else None,
            "dosage": treatment.dosage if treatment else None,
            "correct_dosage": treatment.dosage if treatment else None,
            "treatment_status": treatment.status if treatment else None,
            # Invoice fields
            "invoice_id": invoice.invoice_id if invoice else None,
            "amount": invoice.amount if invoice else None,
            "payment_status": invoice.payment_status if invoice else None,
            # Flags
            "has_pet": pet is not None,
            "has_appointment": appt is not None,
            "has_treatment": treatment is not None,
            "has_invoice": invoice is not None,
        }
        entities.append(entity)

    return entities


# ===================================================================
# Fault Layers
# ===================================================================

# --- Group 1: Owner Contact (depth 0, always reachable) ---

wrong_phone = FaultLayer(
    name="wrong_phone",
    known_info_fragment=(
        "My phone number on file is incorrect — it should be {correct_phone}."
    ),
    completion_fragment="your contact phone number has been corrected",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_owner_phone",
                args={"owner_id": "{owner_id}", "phone": "000-000-0000"},
            ),
            fix=ActionSpec(
                tool_name="update_owner_phone",
                args={"owner_id": "{owner_id}", "phone": "{correct_phone}"},
                compare_args=["owner_id"],
            ),
            check=AssertionSpec(
                func_name="assert_owner_phone",
                args={"owner_id": "{owner_id}", "expected": "{correct_phone}"},
                env_type="assistant",
                message_template="Owner {owner_id} phone should be {correct_phone}.",
            ),
        ),
        # Ask user to acknowledge
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"owner_id": "{owner_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"owner_id": "{owner_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="contact:{owner_id}",
)

contact_group = FaultLayerGroup(
    name="owner_contact",
    layers=[wrong_phone],
    resolution_category="contact",
)


# --- Group 2: Identity Verification (depth 0, GATE FIELD) ---

identity_not_verified = FaultLayer(
    name="identity_not_verified",
    known_info_fragment=(
        "My identity verification has been reset and I need it restored."
    ),
    completion_fragment="your identity has been verified",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_owner_identity_verified",
                args={"owner_id": "{owner_id}", "identity_verified": False},
            ),
            fix=ActionSpec(
                tool_name="update_owner_identity_verified",
                args={"owner_id": "{owner_id}", "identity_verified": True},
                compare_args=["owner_id"],
            ),
            check=AssertionSpec(
                func_name="assert_owner_identity_verified",
                args={"owner_id": "{owner_id}", "expected": True},
                env_type="assistant",
                message_template="Owner {owner_id} identity should be verified.",
            ),
        ),
    ],
    resource_scope="identity:{owner_id}",
)

verification_group = FaultLayerGroup(
    name="owner_verification",
    layers=[identity_not_verified],
    resolution_category="verification",
)


# --- Group 3: Vaccination Records (depth 1, behind identity gate) ---

expired_vaccination = FaultLayer(
    name="expired_vaccination",
    known_info_fragment=(
        "My pet {pet_name}'s vaccination shows as expired — it should be current."
    ),
    completion_fragment="your pet's vaccination status is current",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_pet_vaccination_status",
                args={"pet_id": "{pet_id}", "vaccination_status": "expired"},
            ),
            fix=ActionSpec(
                tool_name="update_pet_vaccination_status",
                args={"pet_id": "{pet_id}", "vaccination_status": "current"},
                compare_args=["pet_id"],
            ),
            check=AssertionSpec(
                func_name="assert_pet_vaccination_status",
                args={"pet_id": "{pet_id}", "expected": "current"},
                env_type="assistant",
                message_template="Pet {pet_id} vaccination should be current.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"owner_id": "{owner_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"owner_id": "{owner_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_pet",
    resource_scope="vaccination:{pet_id}",
)

unknown_vaccination = FaultLayer(
    name="unknown_vaccination",
    known_info_fragment=(
        "My pet {pet_name}'s vaccination status shows as unknown — it should be current."
    ),
    completion_fragment="your pet's vaccination status is current",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_pet_vaccination_status",
                args={"pet_id": "{pet_id}", "vaccination_status": "unknown"},
            ),
            fix=ActionSpec(
                tool_name="update_pet_vaccination_status",
                args={"pet_id": "{pet_id}", "vaccination_status": "current"},
                compare_args=["pet_id"],
            ),
            check=AssertionSpec(
                func_name="assert_pet_vaccination_status",
                args={"pet_id": "{pet_id}", "expected": "current"},
                env_type="assistant",
                message_template="Pet {pet_id} vaccination should be current.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"owner_id": "{owner_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"owner_id": "{owner_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_pet",
    resource_scope="vaccination:{pet_id}",
)

vaccination_group = FaultLayerGroup(
    name="vaccination_records",
    layers=[expired_vaccination, unknown_vaccination],
    resolution_category="vaccination",
)


# --- Group 4: Microchip Records (depth 1, behind identity gate) ---

unregistered_microchip = FaultLayer(
    name="unregistered_microchip",
    known_info_fragment=(
        "My pet {pet_name}'s microchip shows as unregistered — please register it."
    ),
    completion_fragment="your pet's microchip is registered",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_pet_microchip_registered",
                args={"pet_id": "{pet_id}", "microchip_registered": False},
            ),
            fix=ActionSpec(
                tool_name="update_pet_microchip_registered",
                args={"pet_id": "{pet_id}", "microchip_registered": True},
                compare_args=["pet_id"],
            ),
            check=AssertionSpec(
                func_name="assert_pet_microchip_registered",
                args={"pet_id": "{pet_id}", "expected": True},
                env_type="assistant",
                message_template="Pet {pet_id} microchip should be registered.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"owner_id": "{owner_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"owner_id": "{owner_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_pet",
    resource_scope="microchip:{pet_id}",
)

microchip_group = FaultLayerGroup(
    name="microchip_records",
    layers=[unregistered_microchip],
    resolution_category="microchip",
)


# --- Group 5: Appointment Type (depth 1, behind identity gate) ---

wrong_appointment_type = FaultLayer(
    name="wrong_appointment_type",
    known_info_fragment=(
        "My appointment ({appointment_id}) for {pet_name} is listed as the wrong type — "
        "it should be {correct_appointment_type}."
    ),
    completion_fragment="your appointment type has been corrected",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_appointment_appointment_type",
                args={"appointment_id": "{appointment_id}", "appointment_type": "other"},
            ),
            fix=ActionSpec(
                tool_name="update_appointment_appointment_type",
                args={
                    "appointment_id": "{appointment_id}",
                    "appointment_type": "{correct_appointment_type}",
                },
                compare_args=["appointment_id"],
            ),
            check=AssertionSpec(
                func_name="assert_appointment_appointment_type",
                args={
                    "appointment_id": "{appointment_id}",
                    "expected": "{correct_appointment_type}",
                },
                env_type="assistant",
                message_template="Appointment {appointment_id} should be {correct_appointment_type}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"owner_id": "{owner_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"owner_id": "{owner_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_appointment",
    resource_scope="appt_type:{appointment_id}",
)

appointment_type_group = FaultLayerGroup(
    name="appointment_type",
    layers=[wrong_appointment_type],
    resolution_category="appointment",
)


# --- Group 6: Appointment Check-in (depth 1, GATE FIELD) ---

not_checked_in = FaultLayer(
    name="not_checked_in",
    known_info_fragment=(
        "My appointment ({appointment_id}) for {pet_name} shows as not checked in — please confirm check-in."
    ),
    completion_fragment="your appointment check-in has been confirmed",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_appointment_checked_in",
                args={"appointment_id": "{appointment_id}", "checked_in": False},
            ),
            fix=ActionSpec(
                tool_name="update_appointment_checked_in",
                args={"appointment_id": "{appointment_id}", "checked_in": True},
                compare_args=["appointment_id"],
            ),
            check=AssertionSpec(
                func_name="assert_appointment_checked_in",
                args={"appointment_id": "{appointment_id}", "expected": True},
                env_type="assistant",
                message_template="Appointment {appointment_id} should be checked in.",
            ),
        ),
    ],
    predicate_field="has_appointment",
    resource_scope="checkin:{appointment_id}",
)

checkin_group = FaultLayerGroup(
    name="appointment_checkin",
    layers=[not_checked_in],
    resolution_category="checkin",
)


# --- Group 7: Treatment Medication (depth 2, behind identity + checkin gates) ---

wrong_medication = FaultLayer(
    name="wrong_medication",
    known_info_fragment=(
        "The medication listed for {pet_name} (treatment {treatment_id}) is wrong — "
        "it should be {correct_medication}, not Ibuprofen."
    ),
    completion_fragment="your pet's medication record has been corrected",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_treatment_medication",
                args={"treatment_id": "{treatment_id}", "medication": "Ibuprofen"},
            ),
            fix=ActionSpec(
                tool_name="update_treatment_medication",
                args={
                    "treatment_id": "{treatment_id}",
                    "medication": "{correct_medication}",
                },
                compare_args=["treatment_id"],
            ),
            check=AssertionSpec(
                func_name="assert_treatment_medication",
                args={
                    "treatment_id": "{treatment_id}",
                    "expected": "{correct_medication}",
                },
                env_type="assistant",
                message_template="Treatment {treatment_id} medication should be {correct_medication}.",
            ),
        ),
        # Ask user to confirm treatment
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_treatment",
                args={"treatment_id": "{treatment_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_treatment_confirmed",
                args={"treatment_id": "{treatment_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_treatment",
    resource_scope="medication:{treatment_id}",
)

medication_group = FaultLayerGroup(
    name="treatment_medication",
    layers=[wrong_medication],
    resolution_category="treatment",
)


# --- Group 8: Treatment Dosage (depth 2, behind identity + checkin gates) ---

wrong_dosage = FaultLayer(
    name="wrong_dosage",
    known_info_fragment=(
        "The dosage instructions for {pet_name} (treatment {treatment_id}) are incorrect — "
        "it should be {correct_dosage}, not '10 tablets daily'."
    ),
    completion_fragment="your pet's dosage has been corrected",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_treatment_dosage",
                args={"treatment_id": "{treatment_id}", "dosage": "10 tablets daily"},
            ),
            fix=ActionSpec(
                tool_name="update_treatment_dosage",
                args={
                    "treatment_id": "{treatment_id}",
                    "dosage": "{correct_dosage}",
                },
                compare_args=["treatment_id"],
            ),
            check=AssertionSpec(
                func_name="assert_treatment_dosage",
                args={
                    "treatment_id": "{treatment_id}",
                    "expected": "{correct_dosage}",
                },
                env_type="assistant",
                message_template="Treatment {treatment_id} dosage should be {correct_dosage}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_treatment",
                args={"treatment_id": "{treatment_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_treatment_confirmed",
                args={"treatment_id": "{treatment_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_treatment",
    resource_scope="dosage:{treatment_id}",
)

dosage_group = FaultLayerGroup(
    name="treatment_dosage",
    layers=[wrong_dosage],
    resolution_category="dosage",
)


# --- Group 9: Treatment Completion (depth 2, GATE FIELD) ---

treatment_cancelled = FaultLayer(
    name="treatment_cancelled",
    known_info_fragment=(
        "My pet {pet_name}'s treatment ({treatment_id}) shows as cancelled — please restore it."
    ),
    completion_fragment="your pet's treatment has been restored",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_treatment_status",
                args={"treatment_id": "{treatment_id}", "status": "cancelled"},
            ),
            fix=ActionSpec(
                tool_name="update_treatment_status",
                args={"treatment_id": "{treatment_id}", "status": "completed"},
                compare_args=["treatment_id"],
            ),
            check=AssertionSpec(
                func_name="assert_treatment_status",
                args={"treatment_id": "{treatment_id}", "expected": "completed"},
                env_type="assistant",
                message_template="Treatment {treatment_id} status should be completed.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_treatment",
                args={"treatment_id": "{treatment_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_treatment_confirmed",
                args={"treatment_id": "{treatment_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_treatment",
    resource_scope="treatment_status:{treatment_id}",
)

treatment_on_hold = FaultLayer(
    name="treatment_on_hold",
    known_info_fragment=(
        "My pet {pet_name}'s treatment ({treatment_id}) is on hold — please resume it."
    ),
    completion_fragment="your pet's treatment has been resumed",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_treatment_status",
                args={"treatment_id": "{treatment_id}", "status": "on_hold"},
            ),
            fix=ActionSpec(
                tool_name="update_treatment_status",
                args={"treatment_id": "{treatment_id}", "status": "completed"},
                compare_args=["treatment_id"],
            ),
            check=AssertionSpec(
                func_name="assert_treatment_status",
                args={"treatment_id": "{treatment_id}", "expected": "completed"},
                env_type="assistant",
                message_template="Treatment {treatment_id} status should be completed.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_treatment",
                args={"treatment_id": "{treatment_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_treatment_confirmed",
                args={"treatment_id": "{treatment_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_treatment",
    resource_scope="treatment_status:{treatment_id}",
)

completion_group = FaultLayerGroup(
    name="treatment_completion",
    layers=[treatment_cancelled, treatment_on_hold],
    resolution_category="treatment",
)


# --- Group 10: Invoice Status (depth 3, behind all gates) ---

overdue_payment = FaultLayer(
    name="overdue_payment",
    known_info_fragment=(
        "My invoice {invoice_id} shows as overdue — please correct it."
    ),
    completion_fragment="your payment status has been corrected",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_invoice_payment_status",
                args={"invoice_id": "{invoice_id}", "payment_status": "overdue"},
            ),
            fix=ActionSpec(
                tool_name="update_invoice_payment_status",
                args={"invoice_id": "{invoice_id}", "payment_status": "pending"},
                compare_args=["invoice_id"],
            ),
            check=AssertionSpec(
                func_name="assert_invoice_payment_status",
                args={"invoice_id": "{invoice_id}", "expected": "pending"},
                env_type="assistant",
                message_template="Invoice {invoice_id} should be pending.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_invoice",
                args={"invoice_id": "{invoice_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_invoice_acknowledged",
                args={"invoice_id": "{invoice_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_invoice",
    resource_scope="payment:{invoice_id}",
)

disputed_payment = FaultLayer(
    name="disputed_payment",
    known_info_fragment=(
        "My invoice {invoice_id} shows a payment dispute — please resolve it."
    ),
    completion_fragment="your payment dispute has been resolved",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_invoice_payment_status",
                args={"invoice_id": "{invoice_id}", "payment_status": "disputed"},
            ),
            fix=ActionSpec(
                tool_name="update_invoice_payment_status",
                args={"invoice_id": "{invoice_id}", "payment_status": "pending"},
                compare_args=["invoice_id"],
            ),
            check=AssertionSpec(
                func_name="assert_invoice_payment_status",
                args={"invoice_id": "{invoice_id}", "expected": "pending"},
                env_type="assistant",
                message_template="Invoice {invoice_id} should be pending.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_invoice",
                args={"invoice_id": "{invoice_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_invoice_acknowledged",
                args={"invoice_id": "{invoice_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_invoice",
    resource_scope="payment:{invoice_id}",
)

invoice_group = FaultLayerGroup(
    name="invoice_status",
    layers=[overdue_payment, disputed_payment],
    resolution_category="billing",
)


# ===================================================================
# FaultLayerConfig
# ===================================================================

VET_CLINIC_FAULT_CONFIG = FaultLayerConfig(
    name="vet_clinic",
    entity_query=lambda db: _build_entities(db),
    groups=[
        contact_group,           # Group 1: contact issues (1 layer, 2 atoms)
        verification_group,      # Group 2: identity verification (1 layer, 1 atom) — GATE
        vaccination_group,       # Group 3: vaccination records (2 layers, 2 atoms)
        microchip_group,         # Group 4: microchip records (1 layer, 2 atoms)
        appointment_type_group,  # Group 5: appointment type (1 layer, 2 atoms)
        checkin_group,           # Group 6: check-in (1 layer, 1 atom) — GATE
        medication_group,        # Group 7: medication (1 layer, 2 atoms)
        dosage_group,            # Group 8: dosage (1 layer, 2 atoms)
        completion_group,        # Group 9: treatment completion (2 layers, 2 atoms) — GATE
        invoice_group,           # Group 10: invoice status (2 layers, 2 atoms)
    ],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_owner_info",
            args={"name": "{owner_name}", "owner_id": "{owner_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {owner_name}. Your owner ID is {owner_id}. "
        "Your pet is {pet_name}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Owner {owner_name} (ID: {owner_id}), pet {pet_name}: {fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting Pawsitive Care Veterinary Clinic because you have issues "
        "with your pet's records that need to be resolved."
    ),
    purpose=(
        "Test resolution of veterinary clinic support issues including identity "
        "verification, pet records, appointments, treatments, and billing."
    ),
    entity_id_field="owner_id",
    min_faults=1,
    max_faults=10,
    max_total_tasks=600,
)


# ===================================================================
# RecipeBook
# ===================================================================

RECIPE_BOOK = RecipeBook(
    fault_layer_configs=[VET_CLINIC_FAULT_CONFIG],
    resolution_instruction=(
        "your identity has been verified, your pet's records are correct, "
        "your appointment and treatment details are accurate, and any "
        "billing issues have been resolved"
    ),
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
    """Generate tasks from the recipe book, optionally verify and save.

    Args:
        verify: Run verification passes on generated tasks.
        save: Write tasks.json to disk.
        seed: Random seed for reproducibility.
        llm_verify: Run LLM semantic review of authored source files.
        llm_call_fn: Callable for LLM calls (required if llm_verify=True).

    Returns:
        List of generated Task objects.
    """
    def get_db():
        return VetClinicDB.load(VET_CLINIC_DB_PATH)

    if verify:
        # Pre-generation: structural checks on authored definitions
        authoring_issues = verify_authoring(RECIPE_BOOK, get_environment, get_db)
        auth_errors = [i for i in authoring_issues if i.startswith("ERROR:")]
        auth_warnings = [i for i in authoring_issues if i.startswith("WARNING:")]
        print(f"Authoring verification: {len(auth_errors)} error(s), {len(auth_warnings)} warning(s)")
        for i in authoring_issues:
            print(f"  {i}")
        if auth_errors:
            raise ValueError(f"Authoring verification failed: {len(auth_errors)} error(s)")

        # Optional: LLM review of source files
        if llm_verify and llm_call_fn:
            authored_files = collect_authored_files(
                file_paths={
                    "tools.py": str(Path(__file__).parent / "tools.py"),
                    "scenarios.py": str(Path(__file__).parent / "scenarios.py"),
                    "data_model.py": str(Path(__file__).parent / "data_model.py"),
                    "user_tools.py": str(Path(__file__).parent / "user_tools.py"),
                    "environment.py": str(Path(__file__).parent / "environment.py"),
                    "policy.md": str(VET_CLINIC_POLICY_PATH),
                },
                db_path=str(VET_CLINIC_DB_PATH),
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
        # Per-atom verification: test each init->fix->check triple in isolation
        atom_issues = verify_fault_atoms(
            VET_CLINIC_FAULT_CONFIG, get_environment, get_db, sample_size=2
        )
        if atom_issues:
            raise ValueError(
                f"Atom verification failed: {len(atom_issues)} issue(s)."
            )

        # Full task verification
        policy_text = Path(VET_CLINIC_POLICY_PATH).read_text()
        report = verify_tasks(tasks, get_environment, policy_text=policy_text)
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
        dump_file(VET_CLINIC_TASK_SET_PATH, task_dicts)
        print(f"Saved {len(tasks)} tasks to {VET_CLINIC_TASK_SET_PATH}")

    return tasks
