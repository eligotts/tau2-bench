"""Fitness gym scenario definitions using the Recipe Engine (FaultLayerConfig).

Generates tasks via cartesian product of fault groups across entities.
Each entity is a dict built from joined DB records (member + booking + session + invoice + locker).

7 fixable fault groups + 1 transfer config with 2 unfixable layers.
Each fixable group uses a distinct user confirmation tool to avoid action deduplication.
"""

from pathlib import Path
from typing import Any, Callable, Optional

from tau2.domains.fitness_gym.data_model import FitnessGymDB
from tau2.domains.fitness_gym.environment import get_environment
from tau2.domains.fitness_gym.utils import (
    FITNESS_GYM_DB_PATH,
    FITNESS_GYM_POLICY_PATH,
    FITNESS_GYM_TASK_SET_PATH,
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
from tau2.generators.types import Persona, UserTemplate, VariantConfig
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
    Persona(name="regular_member", description=(
        "You are a friendly and organized gym member. You clearly describe your "
        "issue and follow the agent's instructions without hesitation. You provide "
        "all requested information promptly."
    )),
    Persona(name="frustrated_member", description=(
        "You are a frustrated member who has been dealing with gym issues all week. "
        "You sometimes give vague descriptions and may express annoyance, but you "
        "ultimately cooperate when asked to take action."
    )),
]


# ===================================================================
# User Template
# ===================================================================

USER_TEMPLATE = UserTemplate(
    domain="fitness_gym",
    reason_for_call=(
        "You are contacting Iron Peak Fitness because you have multiple issues "
        "with your account — membership, class bookings, personal training sessions, "
        "billing, locker rentals, emergency contacts, or notification preferences."
    ),
    known_info=(
        "You are {member_name} (member ID: {member_id}). {fault_descriptions}"
    ),
    task_instructions=(
        "If the agent resolves an issue and asks you to acknowledge, use your acknowledge_resolution tool. "
        "If the agent changes a class booking and asks you to confirm, use your confirm_class_attendance tool. "
        "If the agent changes a training session and asks you to confirm, use your confirm_training_session tool. "
        "If the agent asks you to make an invoice payment, use your make_invoice_payment tool. "
        "If the agent changes a locker assignment and asks you to confirm, use your confirm_locker_assignment tool. "
        "You will consider the issue resolved only when the agent confirms the problem has been fixed."
    ),
    ticket=(
        "Member {member_name} (ID: {member_id}) contacting about gym account. "
        "{fault_descriptions}"
    ),
    purpose=(
        "Test resolution of fitness gym support issues including membership, "
        "class bookings, personal training, billing, locker rentals, "
        "emergency contacts, and notifications."
    ),
)


# ===================================================================
# Entity construction
# ===================================================================

def _build_entities(db: FitnessGymDB) -> list[dict[str, Any]]:
    """Build entity dicts by joining member + booking + session + invoice + locker.

    Each entity represents one member, enriched with their first class booking,
    first training session, first invoice, and first locker rental.
    """
    # booking by member (first non-cancelled)
    booking_by_member: dict[str, Any] = {}
    for bk in db.class_bookings:
        if bk.member_id not in booking_by_member and bk.status != "cancelled":
            booking_by_member[bk.member_id] = bk

    # session by member (first non-cancelled, non-completed)
    session_by_member: dict[str, Any] = {}
    for sess in db.training_sessions:
        if sess.member_id not in session_by_member and sess.status not in (
            "cancelled",
            "completed",
        ):
            session_by_member[sess.member_id] = sess

    # invoice by member (first unpaid preferred)
    invoice_by_member: dict[str, Any] = {}
    for inv in db.invoices:
        if inv.member_id not in invoice_by_member:
            invoice_by_member[inv.member_id] = inv
        elif (
            inv.status == "unpaid"
            and invoice_by_member[inv.member_id].status != "unpaid"
        ):
            invoice_by_member[inv.member_id] = inv

    # locker by member (first active)
    locker_by_member: dict[str, Any] = {}
    for ren in db.locker_rentals:
        if ren.member_id not in locker_by_member and ren.status == "active":
            locker_by_member[ren.member_id] = ren

    entities = []
    for member in db.members:
        bk = booking_by_member.get(member.member_id)
        sess = session_by_member.get(member.member_id)
        inv = invoice_by_member.get(member.member_id)
        ren = locker_by_member.get(member.member_id)

        entity: dict[str, Any] = {
            # Member fields
            "member_id": member.member_id,
            "member_name": member.name,
            "member_phone": member.phone,
            "member_email": member.email,
            "membership_tier": member.membership_tier,
            "membership_status": member.membership_status,
            "original_membership_tier": member.membership_tier,
            "notification_preference": member.notification_preference,
            "original_notification_preference": member.notification_preference,
            "emergency_contact_name": member.emergency_contact_name,
            "emergency_contact_phone": member.emergency_contact_phone,
            "original_emergency_contact_name": member.emergency_contact_name,
            "original_emergency_contact_phone": member.emergency_contact_phone,
            # Class booking fields
            "booking_id": bk.booking_id if bk else None,
            "booking_class_name": bk.class_name if bk else None,
            "booking_instructor": bk.instructor if bk else None,
            "booking_schedule_date": bk.schedule_date if bk else None,
            "booking_schedule_time": bk.schedule_time if bk else None,
            "booking_location": bk.location if bk else None,
            "booking_status": bk.status if bk else None,
            # Training session fields
            "session_id": sess.session_id if sess else None,
            "session_trainer_name": sess.trainer_name if sess else None,
            "session_date": sess.session_date if sess else None,
            "session_time": sess.session_time if sess else None,
            "session_type": sess.session_type if sess else None,
            "session_status": sess.status if sess else None,
            "original_session_trainer": sess.trainer_name if sess else None,
            # Invoice fields
            "invoice_id": inv.invoice_id if inv else None,
            "invoice_amount": inv.amount if inv else None,
            "invoice_description": inv.description if inv else None,
            "invoice_status": inv.status if inv else None,
            "invoice_due_date": inv.due_date if inv else None,
            # Locker rental fields
            "rental_id": ren.rental_id if ren else None,
            "locker_number": ren.locker_number if ren else None,
            "locker_location": ren.location if ren else None,
            "rental_status": ren.status if ren else None,
            "original_locker_location": ren.location if ren else None,
            # Flags for predicate filtering
            "has_booking": bk is not None,
            "has_session": sess is not None,
            "has_invoice": inv is not None,
            "has_locker": ren is not None,
        }
        entities.append(entity)

    return entities


# ===================================================================
# Fault Layers
# ===================================================================

# --- Group 1: Membership Issues (2 mutually exclusive) ---

suspended_membership = FaultLayer(
    name="suspended_membership",
    known_info_fragment=(
        "My gym membership was suspended by mistake. "
        "I need it reactivated so I can access the facilities."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_membership_status",
                args={"member_id": "{member_id}", "status": "suspended"},
            ),
            fix=ActionSpec(
                tool_name="reactivate_membership",
                args={"member_id": "{member_id}"},
                compare_args=["member_id"],
            ),
            check=AssertionSpec(
                func_name="assert_membership_status",
                args={
                    "member_id": "{member_id}",
                    "expected_status": "active",
                },
                env_type="assistant",
                message_template="Member {member_id} should have active status.",
            ),
        ),
        # Policy: "After any membership change, ask the member to acknowledge."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"member_id": "{member_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"member_id": "{member_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="membership_status:{member_id}",
)

wrong_membership_tier = FaultLayer(
    name="wrong_membership_tier",
    known_info_fragment=(
        "My gym membership was downgraded to basic by mistake. "
        "I should be on the {original_membership_tier} tier."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_membership_tier",
                args={"member_id": "{member_id}", "tier": "basic"},
            ),
            fix=ActionSpec(
                tool_name="restore_membership_tier",
                args={
                    "member_id": "{member_id}",
                    "tier": "{original_membership_tier}",
                },
                compare_args=["member_id"],
            ),
            check=AssertionSpec(
                func_name="assert_membership_tier",
                args={
                    "member_id": "{member_id}",
                    "expected_tier": "{original_membership_tier}",
                },
                env_type="assistant",
                message_template="Member {member_id} should have {original_membership_tier} tier.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"member_id": "{member_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"member_id": "{member_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="membership_tier:{member_id}",
)

membership_group = FaultLayerGroup(
    name="membership_issues",
    layers=[suspended_membership, wrong_membership_tier],
)


# --- Group 2: Class Booking Issues (2 mutually exclusive) ---

cancelled_class_booking = FaultLayer(
    name="cancelled_class_booking",
    known_info_fragment=(
        "My {booking_class_name} class booking ({booking_id}) on "
        "{booking_schedule_date} at {booking_schedule_time} was cancelled by mistake. "
        "I still want to attend."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_booking_status",
                args={"booking_id": "{booking_id}", "status": "cancelled"},
            ),
            fix=ActionSpec(
                tool_name="reinstate_class_booking",
                args={"booking_id": "{booking_id}"},
                compare_args=["booking_id"],
            ),
            check=AssertionSpec(
                func_name="assert_booking_status",
                args={
                    "booking_id": "{booking_id}",
                    "expected_status": "registered",
                },
                env_type="assistant",
                message_template="Booking {booking_id} should be registered.",
            ),
        ),
        # Policy: "After any class booking change, ask the member to confirm attendance."
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_class_attendance",
                args={"booking_id": "{booking_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_class_attendance_confirmed",
                args={"booking_id": "{booking_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_booking",
    resource_scope="booking:{booking_id}",
)

wrong_class_schedule = FaultLayer(
    name="wrong_class_schedule",
    known_info_fragment=(
        "My {booking_class_name} class booking ({booking_id}) has the wrong schedule. "
        "It should be on {booking_schedule_date} at {booking_schedule_time}, "
        "not on 2025-01-01 at 05:00."
    ),
    atoms=[
        FaultAtom(
            init=[
                InitCall(
                    env_type="assistant",
                    func_name="set_booking_schedule",
                    args={
                        "booking_id": "{booking_id}",
                        "schedule_date": "2025-01-01",
                        "schedule_time": "05:00",
                    },
                ),
            ],
            fix=ActionSpec(
                tool_name="reschedule_class_booking",
                args={
                    "booking_id": "{booking_id}",
                    "new_date": "{booking_schedule_date}",
                    "new_time": "{booking_schedule_time}",
                },
                compare_args=["booking_id"],
            ),
            check=AssertionSpec(
                func_name="assert_booking_schedule",
                args={
                    "booking_id": "{booking_id}",
                    "expected_date": "{booking_schedule_date}",
                    "expected_time": "{booking_schedule_time}",
                },
                env_type="assistant",
                message_template="Booking {booking_id} should be on {booking_schedule_date} at {booking_schedule_time}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_class_attendance",
                args={"booking_id": "{booking_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_class_attendance_confirmed",
                args={"booking_id": "{booking_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_booking",
    resource_scope="booking:{booking_id}",
)

booking_group = FaultLayerGroup(
    name="class_booking_issues",
    layers=[cancelled_class_booking, wrong_class_schedule],
)


# --- Group 3: Training Session Issues (2 mutually exclusive) ---

cancelled_training_session = FaultLayer(
    name="cancelled_training_session",
    known_info_fragment=(
        "My {session_type} training session ({session_id}) with "
        "{session_trainer_name} on {session_date} was cancelled by mistake. "
        "Please reinstate it."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_session_status",
                args={"session_id": "{session_id}", "status": "cancelled"},
            ),
            fix=ActionSpec(
                tool_name="reinstate_training_session",
                args={"session_id": "{session_id}"},
                compare_args=["session_id"],
            ),
            check=AssertionSpec(
                func_name="assert_session_status",
                args={
                    "session_id": "{session_id}",
                    "expected_status": "scheduled",
                },
                env_type="assistant",
                message_template="Session {session_id} should be scheduled.",
            ),
        ),
        # Policy: "After any training session change, ask the member to confirm."
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_training_session",
                args={"session_id": "{session_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_training_session_confirmed",
                args={"session_id": "{session_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_session",
    resource_scope="session:{session_id}",
)

wrong_trainer = FaultLayer(
    name="wrong_trainer",
    known_info_fragment=(
        "My {session_type} training session ({session_id}) on {session_date} "
        "was assigned to the wrong trainer. It should be with "
        "{original_session_trainer}, not 'Unassigned Temp Staff'."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_session_trainer",
                args={
                    "session_id": "{session_id}",
                    "trainer_name": "Unassigned Temp Staff",
                },
            ),
            fix=ActionSpec(
                tool_name="reassign_trainer",
                args={
                    "session_id": "{session_id}",
                    "new_trainer": "{original_session_trainer}",
                },
                compare_args=["session_id"],
            ),
            check=AssertionSpec(
                func_name="assert_session_trainer",
                args={
                    "session_id": "{session_id}",
                    "expected_trainer": "{original_session_trainer}",
                },
                env_type="assistant",
                message_template="Session {session_id} should have trainer {original_session_trainer}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_training_session",
                args={"session_id": "{session_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_training_session_confirmed",
                args={"session_id": "{session_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_session",
    resource_scope="session:{session_id}",
)

session_group = FaultLayerGroup(
    name="training_session_issues",
    layers=[cancelled_training_session, wrong_trainer],
)


# --- Group 4: Billing Issues (2 mutually exclusive) ---

overcharged_invoice = FaultLayer(
    name="overcharged_invoice",
    known_info_fragment=(
        "Invoice {invoice_id} shows $999.99 but this charge is completely "
        "incorrect — the full amount should be credited."
    ),
    atoms=[
        FaultAtom(
            init=[
                InitCall(
                    env_type="assistant",
                    func_name="set_invoice_amount",
                    args={"invoice_id": "{invoice_id}", "amount": 999.99},
                ),
                InitCall(
                    env_type="assistant",
                    func_name="set_invoice_status",
                    args={"invoice_id": "{invoice_id}", "status": "unpaid"},
                ),
            ],
            fix=ActionSpec(
                tool_name="issue_credit",
                args={
                    "invoice_id": "{invoice_id}",
                    "reason": "Billing correction - overcharge",
                },
                compare_args=["invoice_id"],
            ),
            check=AssertionSpec(
                func_name="assert_invoice_status",
                args={
                    "invoice_id": "{invoice_id}",
                    "expected_status": "credited",
                },
                env_type="assistant",
                message_template="Invoice {invoice_id} should be credited.",
            ),
        ),
    ],
    predicate_field="has_invoice",
    resource_scope="invoice:{invoice_id}",
)

unpaid_invoice = FaultLayer(
    name="unpaid_invoice",
    known_info_fragment=(
        "I have an unpaid invoice {invoice_id} and I'm ready to pay it now. "
        "Please look up the balance so I can make my payment."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_invoice_status",
                args={"invoice_id": "{invoice_id}", "status": "unpaid"},
            ),
            fix=ActionSpec(
                tool_name="make_invoice_payment",
                args={
                    "invoice_id": "{invoice_id}",
                    "amount": "{invoice_amount}",
                },
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_invoice_status",
                args={
                    "invoice_id": "{invoice_id}",
                    "expected_status": "paid",
                },
                env_type="assistant",
                message_template="Invoice {invoice_id} should be paid.",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_invoice_payment_made",
            args={"invoice_id": "{invoice_id}"},
            env_type="user",
            message_template="User should have made payment for invoice {invoice_id}.",
        ),
    ],
    predicate_field="has_invoice",
    resource_scope="invoice:{invoice_id}",
)

billing_group = FaultLayerGroup(
    name="billing_issues",
    layers=[overcharged_invoice, unpaid_invoice],
)


# --- Group 5: Locker Issues (1 layer) ---
# Uses confirm_locker_assignment(rental_id) as the user action.

wrong_locker_location = FaultLayer(
    name="wrong_locker_location",
    known_info_fragment=(
        "My locker rental ({rental_id}, locker {locker_number}) is assigned to "
        "the wrong location. It should be at {original_locker_location}, "
        "not 'Storage Basement'."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_locker_location",
                args={"rental_id": "{rental_id}", "location": "Storage Basement"},
            ),
            fix=ActionSpec(
                tool_name="transfer_locker",
                args={
                    "rental_id": "{rental_id}",
                    "new_location": "{original_locker_location}",
                },
                compare_args=["rental_id"],
            ),
            check=AssertionSpec(
                func_name="assert_locker_location",
                args={
                    "rental_id": "{rental_id}",
                    "expected_location": "{original_locker_location}",
                },
                env_type="assistant",
                message_template="Rental {rental_id} should be at {original_locker_location}.",
            ),
        ),
        # Policy: "After any locker rental change, ask the member to confirm."
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_locker_assignment",
                args={"rental_id": "{rental_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_locker_assignment_confirmed",
                args={"rental_id": "{rental_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_locker",
    resource_scope="locker:{rental_id}",
)

locker_group = FaultLayerGroup(
    name="locker_issues",
    layers=[wrong_locker_location],
)


# --- Group 6: Emergency Contact Issues (1 layer) ---

wrong_emergency_contact = FaultLayer(
    name="wrong_emergency_contact",
    known_info_fragment=(
        "My emergency contact was changed to the wrong person. "
        "It should be {original_emergency_contact_name} at "
        "{original_emergency_contact_phone}, not 'Unknown Person' at '000-0000'."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_emergency_contact",
                args={
                    "member_id": "{member_id}",
                    "contact_name": "Unknown Person",
                    "contact_phone": "000-0000",
                },
            ),
            fix=ActionSpec(
                tool_name="update_emergency_contact",
                args={
                    "member_id": "{member_id}",
                    "contact_name": "{original_emergency_contact_name}",
                    "contact_phone": "{original_emergency_contact_phone}",
                },
                compare_args=["member_id"],
            ),
            check=AssertionSpec(
                func_name="assert_emergency_contact",
                args={
                    "member_id": "{member_id}",
                    "expected_name": "{original_emergency_contact_name}",
                    "expected_phone": "{original_emergency_contact_phone}",
                },
                env_type="assistant",
                message_template="Member {member_id} emergency contact should be {original_emergency_contact_name}.",
            ),
        ),
        # Policy: "After updating emergency contact, ask the member to acknowledge."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"member_id": "{member_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"member_id": "{member_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="emergency_contact:{member_id}",
)

emergency_contact_group = FaultLayerGroup(
    name="emergency_contact_issues",
    layers=[wrong_emergency_contact],
)


# --- Group 7: Notification Preference Issues (1 layer) ---

wrong_notification_preference = FaultLayer(
    name="wrong_notification_preference",
    known_info_fragment=(
        "My notification preference was changed to 'none' by mistake. "
        "I want to receive notifications via {original_notification_preference}."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_notification_preference",
                args={"member_id": "{member_id}", "preference": "none"},
            ),
            fix=ActionSpec(
                tool_name="update_notification_preference",
                args={
                    "member_id": "{member_id}",
                    "preference": "{original_notification_preference}",
                },
                compare_args=["member_id"],
            ),
            check=AssertionSpec(
                func_name="assert_notification_preference",
                args={
                    "member_id": "{member_id}",
                    "expected_preference": "{original_notification_preference}",
                },
                env_type="assistant",
                message_template="Member {member_id} should have {original_notification_preference} notifications.",
            ),
        ),
        # Policy: "After updating notification preferences, ask the member to acknowledge."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"member_id": "{member_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"member_id": "{member_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="notification:{member_id}",
)

notification_group = FaultLayerGroup(
    name="notification_issues",
    layers=[wrong_notification_preference],
)


# --- Unfixable Layers (separate transfer config) ---

medical_clearance_hold = FaultLayer(
    name="medical_clearance_hold",
    unfixable=True,
    known_info_fragment=(
        "My training session ({session_id}) is on medical hold but my doctor "
        "has cleared me. I need this hold removed so I can train."
    ),
    atoms=[],
    init_calls=[
        InitCall(
            env_type="assistant",
            func_name="set_session_status",
            args={"session_id": "{session_id}", "status": "medical_hold"},
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_session_status",
            args={"session_id": "{session_id}", "expected_status": "medical_hold"},
            env_type="assistant",
            message_template="Session {session_id} should still be on medical_hold (unfixable).",
        ),
    ],
    predicate_field="has_session",
    resource_scope="session:{session_id}",
)

contract_cancellation = FaultLayer(
    name="contract_cancellation",
    unfixable=True,
    known_info_fragment=(
        "I would like to cancel my gym membership contract entirely. "
        "Please help me with the cancellation process."
    ),
    atoms=[],
    init_calls=[
        InitCall(
            env_type="assistant",
            func_name="set_membership_status",
            args={
                "member_id": "{member_id}",
                "status": "pending_cancellation",
            },
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_membership_status",
            args={"member_id": "{member_id}", "expected_status": "pending_cancellation"},
            env_type="assistant",
            message_template="Member {member_id} should still be pending_cancellation (unfixable).",
        ),
    ],
    resource_scope="membership_cancel:{member_id}",
)


# ===================================================================
# FaultLayerConfigs
# ===================================================================

FITNESS_GYM_FAULT_CONFIG = FaultLayerConfig(
    name="fitness_gym",
    entity_query=lambda db: _build_entities(db),
    groups=[
        membership_group,         # Group 1: membership issues (2 layers, 2 atoms each)
        booking_group,            # Group 2: class booking issues (2 layers, 2 atoms each)
        session_group,            # Group 3: training session issues (2 layers, 2 atoms each)
        billing_group,            # Group 4: billing issues (2 layers, 1 atom each)
        locker_group,             # Group 5: locker issues (1 layer, 2 atoms)
        emergency_contact_group,  # Group 6: emergency contact issues (1 layer, 2 atoms)
        notification_group,       # Group 7: notification issues (1 layer, 2 atoms)
    ],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_member_info",
            args={"name": "{member_name}", "member_id": "{member_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {member_name}. Your gym member ID is {member_id}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Member {member_name} (ID: {member_id}): {fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting Iron Peak Fitness because you have issues "
        "with your gym account that need to be resolved."
    ),
    purpose=(
        "Test resolution of fitness gym support issues including membership, "
        "class bookings, personal training, billing, locker rentals, "
        "emergency contacts, and notifications."
    ),
    entity_id_field="member_id",
    min_faults=1,
    max_faults=7,
    max_total_tasks=600,
)

# Transfer config — unfixable layers only (small set)
FITNESS_GYM_TRANSFER_CONFIG = FaultLayerConfig(
    name="fitness_gym_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[
        FaultLayerGroup(
            name="unfixable_issues",
            layers=[medical_clearance_hold, contract_cancellation],
        ),
    ],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_member_info",
            args={"name": "{member_name}", "member_id": "{member_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {member_name}. Your gym member ID is {member_id}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Member {member_name} (ID: {member_id}): {fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting Iron Peak Fitness because you have an issue "
        "with your gym account."
    ),
    purpose="Test transfer-to-human for unsupported requests.",
    entity_id_field="member_id",
    min_faults=1,
    max_faults=1,
    max_total_tasks=16,
)


# ===================================================================
# RecipeBook
# ===================================================================

RECIPE_BOOK = RecipeBook(
    fault_layer_configs=[FITNESS_GYM_FAULT_CONFIG, FITNESS_GYM_TRANSFER_CONFIG],
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
        return FitnessGymDB.load(FITNESS_GYM_DB_PATH)

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
                    "policy.md": str(FITNESS_GYM_POLICY_PATH),
                },
                db_path=str(FITNESS_GYM_DB_PATH),
            )
            verify_authoring_with_llm(
                RECIPE_BOOK, authored_files, authoring_issues, llm_call_fn
            )

    variant_config = VariantConfig(
        easy_personas=[PERSONAS[0]],   # regular_member
        hard_personas=[PERSONAS[1]],   # frustrated_member
    )

    tasks = generate_recipe_tasks(
        recipe_book=RECIPE_BOOK,
        build_indexes=lambda db: db,
        get_db=get_db,
        user_template=USER_TEMPLATE,
        personas=PERSONAS,
        variant_config=variant_config,
        seed=seed,
    )

    print(f"Generated {len(tasks)} tasks.")

    if verify:
        # Per-atom verification: test each init->fix->check triple in isolation
        atom_issues = verify_fault_atoms(
            FITNESS_GYM_FAULT_CONFIG, get_environment, get_db, sample_size=2
        )
        if atom_issues:
            raise ValueError(
                f"Atom verification failed: {len(atom_issues)} issue(s)."
            )

        # Full task verification
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
        dump_file(FITNESS_GYM_TASK_SET_PATH, task_dicts)
        print(f"Saved {len(tasks)} tasks to {FITNESS_GYM_TASK_SET_PATH}")

    return tasks
