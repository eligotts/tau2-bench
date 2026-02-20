"""Library scenario definitions using the Recipe Engine (FaultLayerConfig).

Generates tasks via cartesian product of fault groups across entities.
Each entity is a dict built from joined DB records (patron + checkout/book + hold + fine + event + loan).

8 fault groups, no unfixable/transfer layers. max_faults = 8 (no cap).
Each group uses a distinct user confirmation tool to avoid action deduplication.
"""

from pathlib import Path
from typing import Any, Callable, Optional

from tau2.domains.library.data_model import LibraryDB
from tau2.domains.library.environment import get_environment
from tau2.domains.library.utils import (
    LIBRARY_DB_PATH,
    LIBRARY_POLICY_PATH,
    LIBRARY_TASK_SET_PATH,
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
    Persona(name="regular_patron", description=(
        "You are a friendly and organized library patron. You clearly describe your "
        "issue and follow the agent's instructions without hesitation. You provide "
        "all requested information promptly."
    )),
    Persona(name="frustrated_patron", description=(
        "You are a frustrated patron who has been dealing with library issues all week. "
        "You sometimes give vague descriptions and may express annoyance, but you "
        "ultimately cooperate when asked to take action."
    )),
]


# ===================================================================
# User Template
# ===================================================================

USER_TEMPLATE = UserTemplate(
    domain="library",
    reason_for_call=(
        "You are contacting Greenfield Public Library because you have multiple issues "
        "with your account — checkouts, holds, fines, membership, book records, events, "
        "inter-library loans, or notification preferences."
    ),
    known_info=(
        "You are {patron_name} (patron ID: {patron_id}). {fault_descriptions}"
    ),
    task_instructions=(
        "If the agent resolves an issue and asks you to acknowledge, use your acknowledge_resolution tool. "
        "If the agent changes a hold and asks you to confirm pickup, use your confirm_hold_pickup tool. "
        "If the agent asks you to make a fine payment, use your make_fine_payment tool. "
        "If the agent fixes an event registration and asks you to confirm, use your confirm_event tool. "
        "If the agent updates a loan and asks you to acknowledge, use your acknowledge_loan tool. "
        "You will consider the issue resolved only when the agent confirms the problem has been fixed."
    ),
    ticket=(
        "Patron {patron_name} (ID: {patron_id}) contacting about library account. "
        "{fault_descriptions}"
    ),
    purpose=(
        "Test resolution of library support issues including checkouts, holds, "
        "fines, book records, memberships, events, inter-library loans, and notifications."
    ),
)


# ===================================================================
# Entity construction
# ===================================================================

def _build_entities(db: LibraryDB) -> list[dict[str, Any]]:
    """Build entity dicts by joining patron + checkout/book + hold + fine + event + loan.

    Each entity represents one patron, enriched with their first active
    checkout (and its book), first hold, first fine, first event, and
    first loan. This gives the fault layers enough fields to template against.
    """
    book_map = {b.book_id: b for b in db.books}

    # checkout by patron (first active)
    ck_by_patron: dict[str, Any] = {}
    for ck in db.checkouts:
        if ck.patron_id not in ck_by_patron and ck.status != "returned":
            ck_by_patron[ck.patron_id] = ck

    # hold by patron (first non-cancelled)
    hold_by_patron: dict[str, Any] = {}
    for h in db.holds:
        if h.patron_id not in hold_by_patron and h.status != "cancelled":
            hold_by_patron[h.patron_id] = h

    # fine by patron (first unpaid preferred)
    fine_by_patron: dict[str, Any] = {}
    for f in db.fines:
        if f.patron_id not in fine_by_patron:
            fine_by_patron[f.patron_id] = f
        elif f.status == "unpaid" and fine_by_patron[f.patron_id].status != "unpaid":
            fine_by_patron[f.patron_id] = f

    # event by patron (first registered)
    event_by_patron: dict[str, Any] = {}
    for e in db.events:
        if e.patron_id not in event_by_patron and e.status != "cancelled":
            event_by_patron[e.patron_id] = e

    # loan by patron (first non-cancelled)
    loan_by_patron: dict[str, Any] = {}
    for loan in db.interlibrary_loans:
        if loan.patron_id not in loan_by_patron and loan.status != "cancelled":
            loan_by_patron[loan.patron_id] = loan

    entities = []
    for patron in db.patrons:
        ck = ck_by_patron.get(patron.patron_id)
        book = book_map.get(ck.book_id) if ck else None
        hold = hold_by_patron.get(patron.patron_id)
        hold_book = book_map.get(hold.book_id) if hold else None
        fine = fine_by_patron.get(patron.patron_id)
        event = event_by_patron.get(patron.patron_id)
        loan = loan_by_patron.get(patron.patron_id)

        entity: dict[str, Any] = {
            # Patron fields
            "patron_id": patron.patron_id,
            "patron_name": patron.name,
            "patron_phone": patron.phone,
            "patron_email": patron.email,
            "membership_type": patron.membership_type,
            "membership_status": patron.membership_status,
            "original_membership_type": patron.membership_type,
            "notification_preference": patron.notification_preference,
            "original_notification_preference": patron.notification_preference,
            # Book fields (from checkout)
            "book_id": book.book_id if book else None,
            "book_title": book.title if book else None,
            "book_author": book.author if book else None,
            "book_location": book.location if book else None,
            # Checkout fields
            "checkout_id": ck.checkout_id if ck else None,
            "checkout_due_date": ck.due_date if ck else None,
            "checkout_status": ck.status if ck else None,
            # Hold fields
            "hold_id": hold.hold_id if hold else None,
            "hold_book_title": hold_book.title if hold_book else None,
            "hold_status": hold.status if hold else None,
            "hold_pickup_branch": hold.pickup_branch if hold else None,
            # Fine fields
            "fine_id": fine.fine_id if fine else None,
            "fine_amount": fine.amount if fine else None,
            "fine_reason": fine.reason if fine else None,
            "fine_status": fine.status if fine else None,
            # Event fields
            "event_id": event.event_id if event else None,
            "event_name": event.event_name if event else None,
            "event_date": event.event_date if event else None,
            "event_location": event.location if event else None,
            "event_status": event.status if event else None,
            # Loan fields
            "loan_id": loan.loan_id if loan else None,
            "loan_book_title": loan.book_title if loan else None,
            "loan_source_library": loan.source_library if loan else None,
            "loan_status": loan.status if loan else None,
            # Flags for predicate filtering
            "has_checkout": ck is not None,
            "has_hold": hold is not None,
            "has_fine": fine is not None,
            "has_event": event is not None,
            "has_loan": loan is not None,
        }
        entities.append(entity)

    return entities


# ===================================================================
# Fault Layers
# ===================================================================

# --- Group 1: Checkout Issues (2 mutually exclusive) ---

overdue_checkout = FaultLayer(
    name="overdue_checkout",
    known_info_fragment=(
        "My checkout {checkout_id} for '{book_title}' is showing as overdue. "
        "The due date should be {checkout_due_date} — please renew it."
    ),
    atoms=[
        FaultAtom(
            init=[
                InitCall(
                    env_type="assistant",
                    func_name="set_checkout_status",
                    args={"checkout_id": "{checkout_id}", "status": "overdue"},
                ),
                InitCall(
                    env_type="assistant",
                    func_name="set_checkout_due_date",
                    args={"checkout_id": "{checkout_id}", "due_date": "2025-01-01"},
                ),
            ],
            fix=ActionSpec(
                tool_name="renew_checkout",
                args={
                    "checkout_id": "{checkout_id}",
                    "new_due_date": "{checkout_due_date}",
                },
                compare_args=["checkout_id"],
            ),
            check=AssertionSpec(
                func_name="assert_checkout_due_date",
                args={
                    "checkout_id": "{checkout_id}",
                    "expected_date": "{checkout_due_date}",
                },
                env_type="assistant",
                message_template="Checkout {checkout_id} should have due date {checkout_due_date}.",
            ),
        ),
        # Policy: "After renewing, ask the patron to acknowledge the resolution."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"patron_id": "{patron_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"patron_id": "{patron_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_checkout",
    resource_scope="checkout:{checkout_id}",
)

lost_book_record = FaultLayer(
    name="lost_book_record",
    known_info_fragment=(
        "My book '{book_title}' (checkout {checkout_id}) is incorrectly marked as "
        "lost in the system. I have the book right here."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_book_status",
                args={"book_id": "{book_id}", "status": "lost"},
            ),
            fix=ActionSpec(
                tool_name="update_book_record",
                args={
                    "book_id": "{book_id}",
                    "field": "status",
                    "value": "checked_out",
                },
                compare_args=["book_id", "field"],
            ),
            check=AssertionSpec(
                func_name="assert_book_status",
                args={"book_id": "{book_id}", "expected_status": "checked_out"},
                env_type="assistant",
                message_template="Book {book_id} should be marked as checked_out.",
            ),
        ),
        # Policy: "After correcting a book record, ask the patron to acknowledge."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"patron_id": "{patron_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"patron_id": "{patron_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_checkout",
    resource_scope="checkout:{checkout_id}",
)

checkout_group = FaultLayerGroup(
    name="checkout_issues",
    layers=[overdue_checkout, lost_book_record],
)


# --- Group 2: Hold Issues (2 mutually exclusive) ---

expired_hold = FaultLayer(
    name="expired_hold",
    known_info_fragment=(
        "My hold {hold_id} for '{hold_book_title}' was expired by mistake. "
        "I still want to pick it up at {hold_pickup_branch}."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_hold_status",
                args={"hold_id": "{hold_id}", "status": "expired"},
            ),
            fix=ActionSpec(
                tool_name="reinstate_hold",
                args={"hold_id": "{hold_id}"},
                compare_args=["hold_id"],
            ),
            check=AssertionSpec(
                func_name="assert_hold_status",
                args={"hold_id": "{hold_id}", "expected_status": "ready"},
                env_type="assistant",
                message_template="Hold {hold_id} should be ready for pickup.",
            ),
        ),
        # Policy: "After any hold change, ask the patron to confirm pickup."
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_hold_pickup",
                args={"hold_id": "{hold_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_hold_pickup_confirmed",
                args={"hold_id": "{hold_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_hold",
    resource_scope="hold:{hold_id}",
)

wrong_pickup_branch = FaultLayer(
    name="wrong_pickup_branch",
    known_info_fragment=(
        "My hold {hold_id} for '{hold_book_title}' is set to pick up at the wrong "
        "branch. It should be at {hold_pickup_branch}, not Remote Storage."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_hold_pickup_branch",
                args={"hold_id": "{hold_id}", "branch": "Remote Storage"},
            ),
            fix=ActionSpec(
                tool_name="transfer_hold",
                args={
                    "hold_id": "{hold_id}",
                    "new_branch": "{hold_pickup_branch}",
                },
                compare_args=["hold_id"],
            ),
            check=AssertionSpec(
                func_name="assert_hold_pickup_branch",
                args={
                    "hold_id": "{hold_id}",
                    "expected_branch": "{hold_pickup_branch}",
                },
                env_type="assistant",
                message_template="Hold {hold_id} should be at {hold_pickup_branch}.",
            ),
        ),
        # Policy: "After any hold change, ask the patron to confirm pickup."
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_hold_pickup",
                args={"hold_id": "{hold_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_hold_pickup_confirmed",
                args={"hold_id": "{hold_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_hold",
    resource_scope="hold:{hold_id}",
)

hold_group = FaultLayerGroup(
    name="hold_issues",
    layers=[expired_hold, wrong_pickup_branch],
)


# --- Group 3: Fine Issues (2 mutually exclusive) ---

overcharged_fine = FaultLayer(
    name="overcharged_fine",
    known_info_fragment=(
        "Fine {fine_id} shows $99.99 but this charge is completely incorrect — "
        "the full amount should be waived."
    ),
    atoms=[
        FaultAtom(
            init=[
                InitCall(
                    env_type="assistant",
                    func_name="set_fine_amount",
                    args={"fine_id": "{fine_id}", "amount": 99.99},
                ),
                InitCall(
                    env_type="assistant",
                    func_name="set_fine_status",
                    args={"fine_id": "{fine_id}", "status": "unpaid"},
                ),
            ],
            fix=ActionSpec(
                tool_name="waive_fine",
                args={
                    "fine_id": "{fine_id}",
                    "reason": "Billing correction - overcharge",
                },
                compare_args=["fine_id"],
            ),
            check=AssertionSpec(
                func_name="assert_fine_status",
                args={"fine_id": "{fine_id}", "expected_status": "waived"},
                env_type="assistant",
                message_template="Fine {fine_id} should be waived.",
            ),
        ),
    ],
    predicate_field="has_fine",
    resource_scope="fine:{fine_id}",
)

unpaid_fine = FaultLayer(
    name="unpaid_fine",
    known_info_fragment=(
        "I have an unpaid fine {fine_id} and I'm ready to pay it now. "
        "Please look up the balance so I can make my payment."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_fine_status",
                args={"fine_id": "{fine_id}", "status": "unpaid"},
            ),
            fix=ActionSpec(
                tool_name="make_fine_payment",
                args={
                    "fine_id": "{fine_id}",
                    "amount": "{fine_amount}",
                },
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_fine_status",
                args={"fine_id": "{fine_id}", "expected_status": "paid"},
                env_type="assistant",
                message_template="Fine {fine_id} should be paid.",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_fine_payment_made",
            args={"fine_id": "{fine_id}"},
            env_type="user",
            message_template="User should have made payment for fine {fine_id}.",
        ),
    ],
    predicate_field="has_fine",
    resource_scope="fine:{fine_id}",
)

fine_group = FaultLayerGroup(
    name="fine_issues",
    layers=[overcharged_fine, unpaid_fine],
)


# --- Group 4: Membership Issues (1 layer) ---

wrong_membership_type = FaultLayer(
    name="wrong_membership_type",
    known_info_fragment=(
        "My library membership was downgraded to standard by mistake. "
        "I should be on the {original_membership_type} tier."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_membership_type",
                args={"patron_id": "{patron_id}", "membership_type": "standard"},
            ),
            fix=ActionSpec(
                tool_name="restore_membership",
                args={
                    "patron_id": "{patron_id}",
                    "membership_type": "{original_membership_type}",
                },
                compare_args=["patron_id"],
            ),
            check=AssertionSpec(
                func_name="assert_membership_type",
                args={
                    "patron_id": "{patron_id}",
                    "expected_type": "{original_membership_type}",
                },
                env_type="assistant",
                message_template="Patron {patron_id} should have {original_membership_type} membership.",
            ),
        ),
    ],
    predicate_ne=("membership_type", "standard"),
    resource_scope="membership:{patron_id}",
)

membership_group = FaultLayerGroup(
    name="membership_issues",
    layers=[wrong_membership_type],
)


# --- Group 5: Book Record Issues (1 layer) ---

wrong_book_location = FaultLayer(
    name="wrong_book_location",
    known_info_fragment=(
        "The system shows '{book_title}' ({book_id}) at the wrong branch. "
        "It should be at {book_location} but it's showing Remote Storage."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_book_location",
                args={"book_id": "{book_id}", "location": "Remote Storage"},
            ),
            fix=ActionSpec(
                tool_name="update_book_record",
                args={
                    "book_id": "{book_id}",
                    "field": "location",
                    "value": "{book_location}",
                },
                compare_args=["book_id", "field"],
            ),
            check=AssertionSpec(
                func_name="assert_book_location",
                args={
                    "book_id": "{book_id}",
                    "expected_location": "{book_location}",
                },
                env_type="assistant",
                message_template="Book {book_id} should be at {book_location}.",
            ),
        ),
        # Policy: "After updating any book record, ask the patron to acknowledge."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"patron_id": "{patron_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"patron_id": "{patron_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_checkout",
    resource_scope="book_location:{book_id}",
)

book_record_group = FaultLayerGroup(
    name="book_record_issues",
    layers=[wrong_book_location],
)


# --- Group 6: Event Issues (2 mutually exclusive) ---
# Uses confirm_event(event_id) as the user action — distinct from other groups.

cancelled_event = FaultLayer(
    name="cancelled_event",
    known_info_fragment=(
        "My registration for '{event_name}' ({event_id}) on {event_date} was "
        "cancelled by mistake. I still want to attend."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_event_status",
                args={"event_id": "{event_id}", "status": "cancelled"},
            ),
            fix=ActionSpec(
                tool_name="reinstate_event",
                args={"event_id": "{event_id}"},
                compare_args=["event_id"],
            ),
            check=AssertionSpec(
                func_name="assert_event_status",
                args={"event_id": "{event_id}", "expected_status": "registered"},
                env_type="assistant",
                message_template="Event {event_id} should be registered.",
            ),
        ),
        # Policy: "After any event registration change, ask the patron to confirm attendance."
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_event",
                args={"event_id": "{event_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_event_confirmed",
                args={"event_id": "{event_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_event",
    resource_scope="event:{event_id}",
)

wrong_event_location = FaultLayer(
    name="wrong_event_location",
    known_info_fragment=(
        "My event '{event_name}' ({event_id}) is listed at the wrong location. "
        "It should be at {event_location}, not Remote Storage."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_event_location",
                args={"event_id": "{event_id}", "location": "Remote Storage"},
            ),
            fix=ActionSpec(
                tool_name="transfer_event",
                args={
                    "event_id": "{event_id}",
                    "new_location": "{event_location}",
                },
                compare_args=["event_id"],
            ),
            check=AssertionSpec(
                func_name="assert_event_location",
                args={
                    "event_id": "{event_id}",
                    "expected_location": "{event_location}",
                },
                env_type="assistant",
                message_template="Event {event_id} should be at {event_location}.",
            ),
        ),
        # Policy: "After any event registration change, ask the patron to confirm attendance."
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_event",
                args={"event_id": "{event_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_event_confirmed",
                args={"event_id": "{event_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_event",
    resource_scope="event:{event_id}",
)

event_group = FaultLayerGroup(
    name="event_issues",
    layers=[cancelled_event, wrong_event_location],
)


# --- Group 7: Inter-Library Loan Issues (2 mutually exclusive) ---
# Uses acknowledge_loan(loan_id) as the user action — distinct from other groups.

cancelled_loan = FaultLayer(
    name="cancelled_loan",
    known_info_fragment=(
        "My inter-library loan request {loan_id} for '{loan_book_title}' from "
        "{loan_source_library} was cancelled by mistake. Please reinstate it."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_loan_status",
                args={"loan_id": "{loan_id}", "status": "cancelled"},
            ),
            fix=ActionSpec(
                tool_name="reinstate_loan",
                args={"loan_id": "{loan_id}"},
                compare_args=["loan_id"],
            ),
            check=AssertionSpec(
                func_name="assert_loan_status",
                args={"loan_id": "{loan_id}", "expected_status": "requested"},
                env_type="assistant",
                message_template="Loan {loan_id} should be requested.",
            ),
        ),
        # Policy: "After any ILL change, ask the patron to acknowledge the update."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_loan",
                args={"loan_id": "{loan_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_loan_acknowledged",
                args={"loan_id": "{loan_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_loan",
    resource_scope="loan:{loan_id}",
)

wrong_loan_source = FaultLayer(
    name="wrong_loan_source",
    known_info_fragment=(
        "My ILL request {loan_id} for '{loan_book_title}' is coming from the wrong "
        "library. It should be from {loan_source_library}, not 'Obsolete Branch Library'."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_loan_source",
                args={"loan_id": "{loan_id}", "source_library": "Obsolete Branch Library"},
            ),
            fix=ActionSpec(
                tool_name="update_loan_source",
                args={
                    "loan_id": "{loan_id}",
                    "source_library": "{loan_source_library}",
                },
                compare_args=["loan_id"],
            ),
            check=AssertionSpec(
                func_name="assert_loan_source",
                args={
                    "loan_id": "{loan_id}",
                    "expected_source": "{loan_source_library}",
                },
                env_type="assistant",
                message_template="Loan {loan_id} source should be {loan_source_library}.",
            ),
        ),
        # Policy: "After any ILL change, ask the patron to acknowledge the update."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_loan",
                args={"loan_id": "{loan_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_loan_acknowledged",
                args={"loan_id": "{loan_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_loan",
    resource_scope="loan:{loan_id}",
)

loan_group = FaultLayerGroup(
    name="loan_issues",
    layers=[cancelled_loan, wrong_loan_source],
)


# --- Group 8: Notification Preference Issues (1 layer) ---
# Uses acknowledge_resolution(patron_id) — but since this group is
# independent (different resource_scope), it still adds 1 agent action
# (update_notification_preference) that doesn't dedup with anything.

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
                args={"patron_id": "{patron_id}", "preference": "none"},
            ),
            fix=ActionSpec(
                tool_name="update_notification_preference",
                args={
                    "patron_id": "{patron_id}",
                    "preference": "{original_notification_preference}",
                },
                compare_args=["patron_id"],
            ),
            check=AssertionSpec(
                func_name="assert_notification_preference",
                args={
                    "patron_id": "{patron_id}",
                    "expected_preference": "{original_notification_preference}",
                },
                env_type="assistant",
                message_template="Patron {patron_id} should have {original_notification_preference} notification preference.",
            ),
        ),
        # Policy: "After updating notification preferences, ask the patron to acknowledge."
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"patron_id": "{patron_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"patron_id": "{patron_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="notification:{patron_id}",
)

notification_group = FaultLayerGroup(
    name="notification_issues",
    layers=[wrong_notification_preference],
)


# ===================================================================
# FaultLayerConfig
# ===================================================================

LIBRARY_FAULT_CONFIG = FaultLayerConfig(
    name="library",
    entity_query=lambda db: _build_entities(db),
    groups=[
        checkout_group,      # Group 1: checkout issues (2 layers, 2 atoms each)
        hold_group,          # Group 2: hold issues (2 layers, 2 atoms each)
        fine_group,          # Group 3: fine issues (2 layers, 1 atom each)
        membership_group,    # Group 4: membership issues (1 layer, 1 atom)
        book_record_group,   # Group 5: book record issues (1 layer, 2 atoms)
        event_group,         # Group 6: event issues (2 layers, 2 atoms each)
        loan_group,          # Group 7: ILL issues (2 layers, 2 atoms each)
        notification_group,  # Group 8: notification issues (1 layer, 2 atoms)
    ],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_patron_info",
            args={"name": "{patron_name}", "patron_id": "{patron_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {patron_name}. Your library patron ID is {patron_id}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Patron {patron_name} (ID: {patron_id}): {fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting Greenfield Public Library because you have issues "
        "with your library account that need to be resolved."
    ),
    purpose=(
        "Test resolution of library support issues including checkouts, holds, "
        "fines, book records, memberships, events, inter-library loans, and notifications."
    ),
    entity_id_field="patron_id",
    min_faults=1,
    max_faults=8,
    max_total_tasks=1200,
)


# ===================================================================
# RecipeBook
# ===================================================================

RECIPE_BOOK = RecipeBook(
    fault_layer_configs=[LIBRARY_FAULT_CONFIG],
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
        return LibraryDB.load(LIBRARY_DB_PATH)

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
                    "policy.md": str(LIBRARY_POLICY_PATH),
                },
                db_path=str(LIBRARY_DB_PATH),
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
            LIBRARY_FAULT_CONFIG, get_environment, get_db, sample_size=2
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
        dump_file(LIBRARY_TASK_SET_PATH, task_dicts)
        print(f"Saved {len(tasks)} tasks to {LIBRARY_TASK_SET_PATH}")

    return tasks
