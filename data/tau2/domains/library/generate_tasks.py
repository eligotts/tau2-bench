#!/usr/bin/env python3
"""Procedurally generate ~200 library domain tasks from db.json.

Standalone script (stdlib only: json, random, pathlib).
Deterministic via random.seed(42).

Usage:
    python generate_tasks.py            # writes tasks.json next to db.json
    python generate_tasks.py --stats    # print stats only, don't write
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

SEED = 42
TODAY = "2026-02-10"
FINE_CHECKOUT_BLOCK_THRESHOLD = 10.0
MAX_RENEWALS_STANDARD = 2
MAX_RENEWALS_STUDENT = 3

DB_PATH = Path(__file__).parent / "db.json"
TASKS_PATH = Path(__file__).parent / "tasks.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_db() -> dict:
    with open(DB_PATH) as f:
        return json.load(f)


def patron_name(db: dict, pid: str) -> str:
    return db["patrons"][pid]["name"]


def book_title(db: dict, bid: str) -> str:
    return db["books"][bid]["title"]


def branch_name(db: dict, brid: str) -> str:
    return db["branches"][brid]["name"]


def copy_book_id(db: dict, cid: str) -> str:
    return db["copies"][cid]["book_id"]


def copy_branch_id(db: dict, cid: str) -> str:
    return db["copies"][cid]["branch_id"]


def max_renewals(db: dict, patron_id: str) -> int:
    mtype = db["patrons"][patron_id]["membership_type"]
    return MAX_RENEWALS_STUDENT if mtype == "student" else MAX_RENEWALS_STANDARD


def book_has_pending_hold(db: dict, book_id: str) -> bool:
    return any(
        h["book_id"] == book_id and h["status"] == "pending"
        for h in db["holds"].values()
    )


def patron_is_active(db: dict, pid: str) -> bool:
    return db["patrons"][pid]["membership_expiry"] >= TODAY


def patron_can_checkout(db: dict, pid: str) -> bool:
    p = db["patrons"][pid]
    return (
        p["membership_expiry"] >= TODAY
        and p["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD
        and len(p["active_loans"]) < p["borrowing_limit"]
    )


# ---------------------------------------------------------------------------
# Entity Indexes
# ---------------------------------------------------------------------------


@dataclass
class EntityIndexes:
    active_patrons: list = field(default_factory=list)
    expired_patrons: list = field(default_factory=list)
    patrons_with_fines_blocking: list = field(default_factory=list)
    patrons_with_outstanding_fines: list = field(default_factory=list)
    patrons_at_limit: list = field(default_factory=list)
    patrons_below_limit: list = field(default_factory=list)
    patrons_no_fines_active: list = field(default_factory=list)

    available_copies: list = field(default_factory=list)
    checked_out_copies: list = field(default_factory=list)
    unavailable_copies: list = field(default_factory=list)

    active_loans: list = field(default_factory=list)
    overdue_active_loans: list = field(default_factory=list)
    not_overdue_active_loans: list = field(default_factory=list)
    renewable_loans: list = field(default_factory=list)
    max_renewal_loans: list = field(default_factory=list)
    hold_blocked_loans: list = field(default_factory=list)

    pending_holds: list = field(default_factory=list)
    ready_holds: list = field(default_factory=list)
    cancellable_holds: list = field(default_factory=list)

    outstanding_fines: list = field(default_factory=list)
    waiver_eligible_fines: list = field(default_factory=list)
    waiver_ineligible_fines: list = field(default_factory=list)

    upcoming_events_with_capacity: list = field(default_factory=list)
    full_events: list = field(default_factory=list)
    cancelled_events: list = field(default_factory=list)
    completed_events: list = field(default_factory=list)

    books_all_out_at_branch: dict = field(default_factory=dict)
    available_copies_by_book_branch: dict = field(default_factory=dict)


def build_indexes(db: dict) -> EntityIndexes:
    ix = EntityIndexes()

    for pid, p in db["patrons"].items():
        if p["membership_expiry"] >= TODAY:
            ix.active_patrons.append(pid)
            if len(p["active_loans"]) >= p["borrowing_limit"]:
                ix.patrons_at_limit.append(pid)
            else:
                ix.patrons_below_limit.append(pid)
            if p["fines_owed"] == 0.0:
                ix.patrons_no_fines_active.append(pid)
        else:
            ix.expired_patrons.append(pid)

        if p["fines_owed"] > FINE_CHECKOUT_BLOCK_THRESHOLD:
            ix.patrons_with_fines_blocking.append(pid)
        if 0 < p["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD:
            ix.patrons_with_outstanding_fines.append(pid)

    for cid, c in db["copies"].items():
        if c["status"] == "available":
            ix.available_copies.append(cid)
        elif c["status"] == "checked_out":
            ix.checked_out_copies.append(cid)
        else:
            ix.unavailable_copies.append(cid)

    for lid, loan in db["loans"].items():
        if loan["return_date"] is not None:
            continue
        ix.active_loans.append(lid)
        if loan["due_date"] < TODAY:
            ix.overdue_active_loans.append(lid)
        else:
            ix.not_overdue_active_loans.append(lid)

        patron_id = loan["patron_id"]
        copy = db["copies"][loan["copy_id"]]
        book_id = copy["book_id"]
        mr = max_renewals(db, patron_id)
        has_hold = book_has_pending_hold(db, book_id)

        if loan["renewals_count"] >= mr:
            ix.max_renewal_loans.append(lid)
        elif has_hold:
            ix.hold_blocked_loans.append(lid)
        else:
            ix.renewable_loans.append(lid)

    for hid, h in db["holds"].items():
        if h["status"] == "pending":
            ix.pending_holds.append(hid)
            ix.cancellable_holds.append(hid)
        elif h["status"] == "ready":
            ix.ready_holds.append(hid)
            ix.cancellable_holds.append(hid)

    for fid, f in db["fines"].items():
        if f["status"] != "outstanding":
            continue
        ix.outstanding_fines.append(fid)
        other = [
            f2
            for f2 in db["fines"].values()
            if f2["patron_id"] == f["patron_id"] and f2["fine_id"] != fid
        ]
        if not other:
            ix.waiver_eligible_fines.append(fid)
        else:
            ix.waiver_ineligible_fines.append(fid)

    for eid, e in db["events"].items():
        if e["status"] == "upcoming" and len(e["registered_patrons"]) < e["capacity"]:
            ix.upcoming_events_with_capacity.append(eid)
        elif e["status"] == "full":
            ix.full_events.append(eid)
        elif e["status"] == "cancelled":
            ix.cancelled_events.append(eid)
        elif e["status"] == "completed":
            ix.completed_events.append(eid)

    # Book-branch availability
    for book_id, book in db["books"].items():
        by_br: dict[str, list] = {}
        for cid in book["copies"]:
            c = db["copies"][cid]
            by_br.setdefault(c["branch_id"], []).append(c)
        for br, copies in by_br.items():
            avail = [c for c in copies if c["status"] == "available"]
            if avail:
                ix.available_copies_by_book_branch[(book_id, br)] = [
                    c["copy_id"] for c in avail
                ]
            else:
                ix.books_all_out_at_branch[(book_id, br)] = True

    return ix


# ---------------------------------------------------------------------------
# Persona / template generation
# ---------------------------------------------------------------------------

PERSONALITIES = [
    "Friendly and patient",
    "Polite but in a hurry",
    "Chatty and sociable, tends to go off-topic",
    "Quiet and straightforward, prefers brief answers",
    "Nervous first-time library user",
    "Elderly patron, not very familiar with the system",
    "Young student, very casual tone",
    "Parent with kids, slightly distracted",
    "Regular patron who knows the system well",
    "Formal and precise in communication",
    "Enthusiastic book lover, talks a lot about books",
    "Shy and soft-spoken, needs encouragement",
    "Busy professional, wants quick service",
    "Cheerful retiree with plenty of time to chat",
    "Tech-savvy patron, comfortable with the system",
]

PAYMENT_METHODS = ["cash", "credit_card", "debit_card"]


def pick_persona() -> str:
    return random.choice(PERSONALITIES)


def pick_payment() -> str:
    return random.choice(PAYMENT_METHODS)


# Entity usage tracking to diversify
_entity_usage: dict[str, int] = {}


def track_use(entity_id: str) -> None:
    _entity_usage[entity_id] = _entity_usage.get(entity_id, 0) + 1


def sort_by_usage(ids: list[str]) -> list[str]:
    return sorted(ids, key=lambda x: _entity_usage.get(x, 0))


def sample_diverse(ids: list[str], n: int) -> list[str]:
    """Sample up to n items, preferring under-used entities."""
    ordered = sort_by_usage(list(ids))
    chosen = ordered[:n]
    for c in chosen:
        track_use(c)
    return chosen


# ---------------------------------------------------------------------------
# Task builder helper
# ---------------------------------------------------------------------------


def make_task(
    task_id: str,
    purpose: str,
    relevant_policies: str,
    notes: str,
    persona: str,
    task_instructions: str,
    reason_for_call: str,
    known_info: str,
    unknown_info: str,
    ticket: str,
    actions: list[dict],
    env_assertions: list[dict] | None = None,
    nl_assertions: list[str] | None = None,
    reward_basis: list[str] | None = None,
) -> dict:
    if reward_basis is None:
        reward_basis = ["ACTION"]
    task = {
        "id": task_id,
        "description": {
            "purpose": purpose,
            "relevant_policies": relevant_policies,
            "notes": notes,
        },
        "user_scenario": {
            "persona": persona,
            "instructions": {
                "task_instructions": task_instructions,
                "domain": "library",
                "reason_for_call": reason_for_call,
                "known_info": known_info,
                "unknown_info": unknown_info,
            },
        },
        "ticket": ticket,
        "evaluation_criteria": {
            "actions": actions,
            "env_assertions": env_assertions,
            "nl_assertions": nl_assertions,
            "reward_basis": reward_basis,
        },
    }
    return task


def action(action_id: str, name: str, arguments: dict, info: str, compare_args=None):
    d = {
        "action_id": action_id,
        "name": name,
        "arguments": arguments,
        "info": info,
    }
    if compare_args is not None:
        d["compare_args"] = compare_args
    return d


def env_assert(func_name: str, arguments: dict):
    return {
        "env_type": "assistant",
        "func_name": func_name,
        "arguments": arguments,
    }


# ---------------------------------------------------------------------------
# Scenario generators
# ---------------------------------------------------------------------------


def gen_simple_checkout(db, ix, n=15):
    """Tier 1: Simple checkout — patron eligible, copy available."""
    tasks = []
    eligible = [
        pid
        for pid in ix.patrons_below_limit
        if pid in ix.patrons_no_fines_active or pid in ix.active_patrons
        if patron_can_checkout(db, pid)
    ]
    eligible = list(set(eligible))
    random.shuffle(eligible)

    # Pair each patron with an available copy
    avail = list(ix.available_copies)
    random.shuffle(avail)

    count = 0
    for pid in eligible:
        if count >= n or not avail:
            break
        cid = avail.pop()
        track_use(pid)
        track_use(cid)

        p = db["patrons"][pid]
        bid = copy_book_id(db, cid)
        brid = copy_branch_id(db, cid)
        title = book_title(db, bid)
        br = branch_name(db, brid)
        name = p["name"]
        loan_count = len(p["active_loans"])

        reasons = [
            f"You want to borrow '{title}' from the {br}.",
            f"You'd like to check out a copy of '{title}' at the {br}.",
            f"You're looking to get '{title}' from the {br}.",
        ]

        tasks.append(
            make_task(
                task_id=f"simple_checkout_{count + 1}",
                purpose="Test simple book checkout with eligible patron",
                relevant_policies="Patron must have active membership, fines <= $10, and be below borrowing limit.",
                notes=f"Patron {name} checks out '{title}' at {br}. Straightforward checkout.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to check out a book from the library.",
                reason_for_call=random.choice(reasons),
                known_info=f"Your name is {name}. You want '{title}' at the {br}.",
                unknown_info="You don't know the copy ID or your patron ID. The agent should look you up by name.",
                ticket=f"Patron {name} wants to check out '{title}' at {br}. Patron is eligible. Agent should find the patron, find an available copy, and process the checkout.",
                actions=[
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": cid},
                        f"Check out {cid} ('{title}') to {name}",
                        compare_args=["patron_id", "copy_id"],
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": loan_count + 1},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


def gen_simple_return(db, ix, n=10):
    """Tier 1: Simple return — not overdue active loans."""
    tasks = []
    not_overdue = list(ix.not_overdue_active_loans)
    random.shuffle(not_overdue)
    chosen = not_overdue[:n]

    for i, lid in enumerate(chosen):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        track_use(pid)
        track_use(cid)

        tasks.append(
            make_task(
                task_id=f"simple_return_{i + 1}",
                purpose="Test simple book return (not overdue)",
                relevant_policies="Copy must be checked out. Return processes the loan and makes the copy available.",
                notes=f"Patron {name} returns '{title}'. Not overdue, so no fine generated.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to return a book you borrowed.",
                reason_for_call=f"You want to return '{title}'.",
                known_info=f"Your name is {name}. You have '{title}' checked out.",
                unknown_info="You don't know the copy ID. The agent should look up your loans.",
                ticket=f"Patron {name} wants to return '{title}' (copy {cid}). Not overdue. Agent should process the return.",
                actions=[
                    action(
                        "return_1",
                        "return_book",
                        {"copy_id": cid},
                        f"Return {cid} ('{title}')",
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "available"},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_overdue_return(db, ix, n=8):
    """Tier 1: Return overdue book — fine will be generated."""
    tasks = []
    overdue = list(ix.overdue_active_loans)
    random.shuffle(overdue)
    chosen = overdue[:n]

    for i, lid in enumerate(chosen):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        track_use(pid)
        track_use(cid)

        tasks.append(
            make_task(
                task_id=f"overdue_return_{i + 1}",
                purpose="Test return of overdue book (fine generated)",
                relevant_policies="Overdue returns generate fines at $0.25/day, capped at $25. The fine is created automatically on return.",
                notes=f"Patron {name} returns overdue '{title}' (due {loan['due_date']}). A fine will be generated.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You need to return a book that's overdue.",
                reason_for_call=f"You want to return '{title}'. You think it might be overdue.",
                known_info=f"Your name is {name}. You have '{title}' checked out.",
                unknown_info="You're not sure exactly how overdue it is or what the fine will be.",
                ticket=f"Patron {name} returns overdue '{title}' (copy {cid}, due {loan['due_date']}). Agent should process return; system auto-generates a fine.",
                actions=[
                    action(
                        "return_1",
                        "return_book",
                        {"copy_id": cid},
                        f"Return overdue {cid} ('{title}')",
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "available"},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_renew_loan(db, ix, n=8):
    """Tier 1: Renew a loan — eligible for renewal."""
    tasks = []
    renewable = list(ix.renewable_loans)
    random.shuffle(renewable)
    chosen = renewable[:n]

    for i, lid in enumerate(chosen):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"renew_loan_{i + 1}",
                purpose="Test loan renewal for eligible loan",
                relevant_policies="Loans can be renewed if under max renewals and no pending holds on the book.",
                notes=f"Patron {name} renews '{title}' (loan {lid}, current renewals: {loan['renewals_count']}).",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to renew a book you have checked out.",
                reason_for_call=f"You'd like to renew '{title}' — you need more time with it.",
                known_info=f"Your name is {name}. You have '{title}' checked out.",
                unknown_info="You don't know your loan ID. The agent should look up your loans.",
                ticket=f"Patron {name} wants to renew '{title}' (loan {lid}). Eligible for renewal. Agent should process the renewal.",
                actions=[
                    action(
                        "renew_1",
                        "renew_loan",
                        {"loan_id": lid},
                        f"Renew loan {lid} for '{title}'",
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_pay_fine_full(db, ix, n=7):
    """Tier 1: Pay a fine in full."""
    tasks = []
    # Pick outstanding fines with moderate amounts (not the $50 lost book fines)
    fines = [fid for fid in ix.outstanding_fines if db["fines"][fid]["amount"] <= 10.0]
    random.shuffle(fines)
    chosen = fines[:n]

    for i, fid in enumerate(chosen):
        fine = db["fines"][fid]
        pid = fine["patron_id"]
        name = patron_name(db, pid)
        amount = fine["amount"]
        payment = pick_payment()
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"pay_fine_full_{i + 1}",
                purpose="Test full fine payment",
                relevant_policies="Fines can be paid in full or partially. Payment reduces patron's fines_owed.",
                notes=f"Patron {name} pays fine {fid} (${amount:.2f}) in full via {payment}.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to pay off a fine.",
                reason_for_call=f"You want to pay your library fine. You'd like to pay the full amount.",
                known_info=f"Your name is {name}. You know you have a fine to pay.",
                unknown_info=f"You don't know the exact fine amount. When the agent tells you, agree to pay the full ${amount:.2f} using {payment}.",
                ticket=f"Patron {name} wants to pay fine {fid} (${amount:.2f}) in full via {payment}. Agent should look up fines and process payment.",
                actions=[
                    action(
                        "pay_fine_1",
                        "pay_fine",
                        {"fine_id": fid, "amount": amount, "payment_method": payment},
                        f"Pay ${amount:.2f} on {fid}",
                        compare_args=["fine_id"],
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_fine_status",
                        {"fine_id": fid, "expected_status": "paid"},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_cancel_hold(db, ix, n=4):
    """Tier 1: Cancel a hold."""
    tasks = []
    holds = list(ix.cancellable_holds)
    random.shuffle(holds)
    chosen = holds[:n]

    for i, hid in enumerate(chosen):
        hold = db["holds"][hid]
        pid = hold["patron_id"]
        bid = hold["book_id"]
        title = book_title(db, bid)
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"cancel_hold_{i + 1}",
                purpose="Test hold cancellation",
                relevant_policies="Pending or ready holds can be cancelled.",
                notes=f"Patron {name} cancels hold on '{title}' (hold {hid}).",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to cancel a hold you placed.",
                reason_for_call=f"You want to cancel your hold on '{title}'. You no longer need it.",
                known_info=f"Your name is {name}. You placed a hold on '{title}'.",
                unknown_info="You don't know the hold ID. The agent should look up your account.",
                ticket=f"Patron {name} wants to cancel hold {hid} on '{title}'. Agent should find the hold and cancel it.",
                actions=[
                    action(
                        "cancel_hold_1",
                        "cancel_hold",
                        {"hold_id": hid},
                        f"Cancel hold {hid} on '{title}'",
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_renew_membership(db, ix, n=3):
    """Tier 1: Renew expired membership."""
    tasks = []
    expired = list(ix.expired_patrons)
    random.shuffle(expired)
    chosen = expired[:n]

    for i, pid in enumerate(chosen):
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"renew_membership_{i + 1}",
                purpose="Test membership renewal",
                relevant_policies="Expired memberships can be renewed for one year.",
                notes=f"Patron {name} has expired membership ({db['patrons'][pid]['membership_expiry']}). Renewing.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. Your library membership has expired and you want to renew it.",
                reason_for_call="You want to renew your library membership.",
                known_info=f"Your name is {name}.",
                unknown_info="You're not sure when your membership expired.",
                ticket=f"Patron {name} wants to renew expired membership. Agent should look up the patron and renew.",
                actions=[
                    action(
                        "renew_1",
                        "renew_membership",
                        {"patron_id": pid},
                        f"Renew membership for {name}",
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


# ── Tier 2: Information & Search ──────────────────────────────────────────


def gen_search_by_title(db, ix, n=5):
    """Tier 2: Search catalog by title."""
    tasks = []
    books = list(db["books"].keys())
    random.shuffle(books)
    chosen = books[:n]

    for i, bid in enumerate(chosen):
        title = book_title(db, bid)
        tasks.append(
            make_task(
                task_id=f"search_title_{i + 1}",
                purpose="Test catalog search by title",
                relevant_policies="search_catalog supports partial, case-insensitive title search.",
                notes=f"Patron searches for '{title}'.",
                persona=pick_persona(),
                task_instructions="You are a library patron looking for a specific book.",
                reason_for_call=f"You're looking for a book called '{title}'. Can you check if the library has it?",
                known_info=f"You know the book title: '{title}'.",
                unknown_info="You don't know the book ID or availability.",
                ticket=f"Patron asks about '{title}'. Agent should search the catalog.",
                actions=[
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search catalog for '{title}'",
                        compare_args=["title"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_search_by_author(db, ix, n=5):
    """Tier 2: Search catalog by author or category."""
    tasks = []
    books = list(db["books"].values())
    random.shuffle(books)
    chosen = books[:n]

    for i, book in enumerate(chosen):
        # Alternate between author and category search
        if i % 2 == 0:
            search_arg = {"author": book["author"]}
            query_desc = f"author '{book['author']}'"
            reason = f"You're looking for books by {book['author']}."
            known = f"You want books by {book['author']}."
        else:
            search_arg = {"category": book["category"]}
            query_desc = f"category '{book['category']}'"
            reason = f"You're looking for {book['category']} books."
            known = f"You want {book['category']} books."

        tasks.append(
            make_task(
                task_id=f"search_author_category_{i + 1}",
                purpose=f"Test catalog search by {query_desc}",
                relevant_policies="search_catalog supports author and category search.",
                notes=f"Patron searches by {query_desc}.",
                persona=pick_persona(),
                task_instructions="You are a library patron looking for books.",
                reason_for_call=reason,
                known_info=known,
                unknown_info="You don't know specific book IDs.",
                ticket=f"Patron asks about books by {query_desc}. Agent should search the catalog.",
                actions=[
                    action(
                        "search_1",
                        "search_catalog",
                        search_arg,
                        f"Search catalog by {query_desc}",
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_check_availability(db, ix, n=5):
    """Tier 2: Search catalog + check availability."""
    tasks = []
    books = list(db["books"].keys())
    random.shuffle(books)
    branches = list(db["branches"].keys())

    for i in range(min(n, len(books))):
        bid = books[i]
        brid = random.choice(branches)
        title = book_title(db, bid)
        br = branch_name(db, brid)

        tasks.append(
            make_task(
                task_id=f"check_availability_{i + 1}",
                purpose="Test checking book availability at a branch",
                relevant_policies="Use search_catalog to find the book, then get_book_availability to check copies.",
                notes=f"Patron asks about availability of '{title}' at {br}.",
                persona=pick_persona(),
                task_instructions="You are a library patron checking if a book is available.",
                reason_for_call=f"You want to know if '{title}' is available at the {br}.",
                known_info=f"You want '{title}' at the {br}.",
                unknown_info="You don't know if there are copies available.",
                ticket=f"Patron asks about availability of '{title}' at {br}. Agent should search catalog and check availability.",
                actions=[
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search for '{title}'",
                        compare_args=["title"],
                    ),
                    action(
                        "availability_1",
                        "get_book_availability",
                        {"book_id": bid, "branch_id": brid},
                        f"Check availability of '{title}' at {br}",
                        compare_args=["book_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_list_loans(db, ix, n=5):
    """Tier 2: List my loans."""
    tasks = []
    # Pick patrons with active loans
    with_loans = [
        pid for pid in ix.active_patrons if db["patrons"][pid]["active_loans"]
    ]
    random.shuffle(with_loans)
    chosen = with_loans[:n]

    for i, pid in enumerate(chosen):
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"list_loans_{i + 1}",
                purpose="Test listing patron's active loans",
                relevant_policies="Use find_patron_by_name then list_patron_loans.",
                notes=f"Patron {name} asks to see their current loans.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to see what books you currently have checked out.",
                reason_for_call="You want to know what books you currently have out from the library.",
                known_info=f"Your name is {name}.",
                unknown_info="You don't remember exactly which books you have.",
                ticket=f"Patron {name} wants to see their active loans. Agent should look up the patron and list loans.",
                actions=[
                    action(
                        "find_1",
                        "find_patron_by_name",
                        {"name": name},
                        f"Find patron {name}",
                    ),
                    action(
                        "list_loans_1",
                        "list_patron_loans",
                        {"patron_id": pid},
                        f"List loans for {name}",
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_list_fines(db, ix, n=5):
    """Tier 2: List my fines."""
    tasks = []
    with_fines = [
        pid for pid in ix.active_patrons if db["patrons"][pid]["fines_owed"] > 0
    ]
    random.shuffle(with_fines)
    chosen = with_fines[:n]

    for i, pid in enumerate(chosen):
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"list_fines_{i + 1}",
                purpose="Test listing patron's outstanding fines",
                relevant_policies="Use find_patron_by_name then list_patron_fines.",
                notes=f"Patron {name} (fines: ${db['patrons'][pid]['fines_owed']:.2f}) asks about fines.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to check what fines you have.",
                reason_for_call="You want to know if you have any outstanding library fines.",
                known_info=f"Your name is {name}.",
                unknown_info="You don't know your exact fine balance.",
                ticket=f"Patron {name} wants to check outstanding fines. Agent should look up patron and list fines.",
                actions=[
                    action(
                        "find_1",
                        "find_patron_by_name",
                        {"name": name},
                        f"Find patron {name}",
                    ),
                    action(
                        "list_fines_1",
                        "list_patron_fines",
                        {"patron_id": pid},
                        f"List fines for {name}",
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


# ── Tier 3: Moderate Multi-Step ───────────────────────────────────────────


def gen_checkout_blocked_by_fines(db, ix, n=8):
    """Tier 3: Fines block checkout → pay → checkout."""
    tasks = []
    # Patrons with fines > $10 who are otherwise active
    blocking = [
        pid
        for pid in ix.patrons_with_fines_blocking
        if patron_is_active(db, pid)
        and len(db["patrons"][pid]["active_loans"])
        < db["patrons"][pid]["borrowing_limit"]
    ]

    # Also create scenarios where patrons have fines that are close to blocking
    # and we can construct pay→checkout flows
    avail = list(ix.available_copies)
    random.shuffle(avail)

    for i, pid in enumerate(blocking):
        if i >= n or not avail:
            break
        p = db["patrons"][pid]
        name = p["name"]
        track_use(pid)

        # Find an outstanding fine to pay
        patron_fines = [
            f
            for f in db["fines"].values()
            if f["patron_id"] == pid and f["status"] == "outstanding"
        ]
        if not patron_fines:
            continue

        fine = patron_fines[0]
        fid = fine["fine_id"]

        # Calculate minimum payment needed to bring fines to $10 or below
        excess = p["fines_owed"] - FINE_CHECKOUT_BLOCK_THRESHOLD
        pay_amount = min(round(excess + 0.50, 2), fine["amount"])
        payment = pick_payment()

        cid = avail.pop()
        bid = copy_book_id(db, cid)
        brid = copy_branch_id(db, cid)
        title = book_title(db, bid)
        br = branch_name(db, brid)
        loan_count = len(p["active_loans"])

        tasks.append(
            make_task(
                task_id=f"checkout_with_fines_{i + 1}",
                purpose="Test checkout blocked by fines, requiring payment before checkout",
                relevant_policies=f"Fines exceeding ${FINE_CHECKOUT_BLOCK_THRESHOLD:.2f} block all new checkouts until the balance is reduced to ${FINE_CHECKOUT_BLOCK_THRESHOLD:.2f} or below through payment.",
                notes=f"Patron {name} has ${p['fines_owed']:.2f} in fines (above ${FINE_CHECKOUT_BLOCK_THRESHOLD:.2f} threshold). Needs to pay at least ${excess:.2f} before checkout.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to check out a book but you might have fines.",
                reason_for_call=f"You want to check out '{title}' at the {br}. You know you have some overdue fines but you're not sure of the exact amount.",
                known_info=f"Your name is {name}. You want to check out '{title}' at the {br}.",
                unknown_info=f"You do not know your exact fine amount or that fines above $10 block checkout. When the agent tells you about the fines blocking checkout, agree to pay ${pay_amount:.2f} toward {fid} using {payment}. Then ask the agent to proceed with the checkout.",
                ticket=f"Patron {name} wants to check out '{title}' at {br}. Has ${p['fines_owed']:.2f} in fines blocking checkout. Agent must collect payment on {fid} to bring total to $10 or below, then complete checkout.",
                actions=[
                    action(
                        "pay_fine_1",
                        "pay_fine",
                        {
                            "fine_id": fid,
                            "amount": pay_amount,
                            "payment_method": payment,
                        },
                        f"Pay ${pay_amount:.2f} toward {fid} to bring total fines from ${p['fines_owed']:.2f} to ${p['fines_owed'] - pay_amount:.2f}",
                        compare_args=["fine_id"],
                    ),
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": cid},
                        f"Check out {cid} ('{title}') to {name}",
                        compare_args=["patron_id", "copy_id"],
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": loan_count + 1},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_checkout_blocked_by_membership(db, ix, n=8):
    """Tier 3: Expired membership → renew → checkout."""
    tasks = []
    expired_eligible = [
        pid
        for pid in ix.expired_patrons
        if db["patrons"][pid]["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD
        and len(db["patrons"][pid]["active_loans"])
        < db["patrons"][pid]["borrowing_limit"]
    ]
    avail = list(ix.available_copies)
    random.shuffle(avail)
    random.shuffle(expired_eligible)

    for i, pid in enumerate(expired_eligible):
        if i >= n or not avail:
            break
        p = db["patrons"][pid]
        name = p["name"]
        track_use(pid)

        cid = avail.pop()
        bid = copy_book_id(db, cid)
        brid = copy_branch_id(db, cid)
        title = book_title(db, bid)
        br = branch_name(db, brid)
        loan_count = len(p["active_loans"])

        tasks.append(
            make_task(
                task_id=f"checkout_expired_membership_{i + 1}",
                purpose="Test checkout blocked by expired membership, requiring renewal first",
                relevant_policies="Membership must be active for checkout. Expired memberships can be renewed for one year.",
                notes=f"Patron {name} has expired membership ({p['membership_expiry']}). Must renew before checkout.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to check out a book. Your membership may have expired.",
                reason_for_call=f"You want to check out '{title}' at the {br}.",
                known_info=f"Your name is {name}. You want '{title}' at the {br}.",
                unknown_info="You're not sure if your membership is still valid. If the agent says it's expired, agree to renew it.",
                ticket=f"Patron {name} wants to check out '{title}' at {br}. Membership expired on {p['membership_expiry']}. Agent must renew membership, then process checkout.",
                actions=[
                    action(
                        "renew_membership_1",
                        "renew_membership",
                        {"patron_id": pid},
                        f"Renew membership for {name}",
                    ),
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": cid},
                        f"Check out {cid} ('{title}') to {name}",
                        compare_args=["patron_id", "copy_id"],
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": loan_count + 1},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_place_hold(db, ix, n=8):
    """Tier 3: Place hold (book unavailable at branch)."""
    tasks = []
    # Pick (book, branch) combos where all copies are out
    combos = list(ix.books_all_out_at_branch.keys())
    random.shuffle(combos)

    # Need eligible patrons
    eligible = [pid for pid in ix.active_patrons if pid not in ix.patrons_at_limit]
    random.shuffle(eligible)

    count = 0
    patron_idx = 0
    for book_id, branch_id in combos:
        if count >= n or patron_idx >= len(eligible):
            break
        pid = eligible[patron_idx]
        patron_idx += 1
        name = patron_name(db, pid)
        title = book_title(db, book_id)
        br = branch_name(db, branch_id)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"place_hold_{count + 1}",
                purpose="Test placing a hold on an unavailable book",
                relevant_policies="Holds can be placed when no copies are available at the requested branch.",
                notes=f"Patron {name} wants '{title}' at {br} but no copies are available. Agent should place a hold.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want a book that might not be available.",
                reason_for_call=f"You'd like to get '{title}' from the {br}.",
                known_info=f"Your name is {name}. You want '{title}' at the {br}.",
                unknown_info="You don't know if the book is available. If the agent says it's not available, ask them to place a hold for you.",
                ticket=f"Patron {name} wants '{title}' at {br}. No copies available. Agent should search, check availability, and place a hold.",
                actions=[
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search for '{title}'",
                        compare_args=["title"],
                    ),
                    action(
                        "availability_1",
                        "get_book_availability",
                        {"book_id": book_id, "branch_id": branch_id},
                        f"Check availability at {br}",
                        compare_args=["book_id"],
                    ),
                    action(
                        "place_hold_1",
                        "place_hold",
                        {"patron_id": pid, "book_id": book_id, "branch_id": branch_id},
                        f"Place hold on '{title}' at {br} for {name}",
                        compare_args=["patron_id", "book_id", "branch_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
        count += 1
    return tasks


def gen_register_event(db, ix, n=8):
    """Tier 3: Register for event."""
    tasks = []
    events = list(ix.upcoming_events_with_capacity)
    eligible = [pid for pid in ix.active_patrons]
    random.shuffle(eligible)
    random.shuffle(events)

    count = 0
    patron_idx = 0
    for eid in events:
        if count >= n or patron_idx >= len(eligible):
            break
        event = db["events"][eid]
        brid = event["branch_id"]
        br = branch_name(db, brid)

        # Find a patron not already registered
        while patron_idx < len(eligible):
            pid = eligible[patron_idx]
            patron_idx += 1
            if pid not in event["registered_patrons"]:
                break
        else:
            continue

        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"register_event_{count + 1}",
                purpose="Test event registration",
                relevant_policies="Patron must have active membership. Event must have capacity.",
                notes=f"Patron {name} registers for '{event['title']}' at {br}.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You're interested in attending a library event.",
                reason_for_call=f"You heard about '{event['title']}' at the {br} and want to sign up.",
                known_info=f"Your name is {name}. You want to attend '{event['title']}' at the {br}.",
                unknown_info="You don't know the event ID or if there's still space.",
                ticket=f"Patron {name} wants to register for '{event['title']}' ({eid}) at {br}. Event has capacity. Agent should find the event and register the patron.",
                actions=[
                    action(
                        "find_branch_1",
                        "find_branch_by_name",
                        {"name": br},
                        f"Find branch {br}",
                    ),
                    action(
                        "list_events_1",
                        "list_events",
                        {"branch_id": brid},
                        f"List events at {br}",
                    ),
                    action(
                        "register_1",
                        "register_for_event",
                        {"patron_id": pid, "event_id": eid},
                        f"Register {name} for '{event['title']}'",
                        compare_args=["patron_id", "event_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
        count += 1
    return tasks


def gen_pay_fine_partial(db, ix, n=5):
    """Tier 3: Partial fine payment."""
    tasks = []
    fines = [fid for fid in ix.outstanding_fines if db["fines"][fid]["amount"] > 2.0]
    random.shuffle(fines)
    chosen = fines[:n]

    for i, fid in enumerate(chosen):
        fine = db["fines"][fid]
        pid = fine["patron_id"]
        name = patron_name(db, pid)
        # Pay roughly half
        pay_amount = round(fine["amount"] / 2, 2)
        if pay_amount <= 0:
            pay_amount = 1.0
        payment = pick_payment()
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"pay_fine_partial_{i + 1}",
                purpose="Test partial fine payment",
                relevant_policies="Fines can be paid partially. Remaining balance stays outstanding.",
                notes=f"Patron {name} pays ${pay_amount:.2f} of ${fine['amount']:.2f} fine ({fid}).",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to make a partial payment on a fine.",
                reason_for_call="You want to pay some of your library fine but not all of it right now.",
                known_info=f"Your name is {name}.",
                unknown_info=f"You don't know the exact amount. When the agent tells you, say you'd like to pay ${pay_amount:.2f} using {payment}.",
                ticket=f"Patron {name} wants to pay ${pay_amount:.2f} toward fine {fid} (${fine['amount']:.2f}) via {payment}.",
                actions=[
                    action(
                        "find_1",
                        "find_patron_by_name",
                        {"name": name},
                        f"Find patron {name}",
                    ),
                    action(
                        "list_fines_1",
                        "list_patron_fines",
                        {"patron_id": pid},
                        f"List fines for {name}",
                    ),
                    action(
                        "pay_fine_1",
                        "pay_fine",
                        {
                            "fine_id": fid,
                            "amount": pay_amount,
                            "payment_method": payment,
                        },
                        f"Pay ${pay_amount:.2f} on {fid}",
                        compare_args=["fine_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_interlibrary_loan(db, ix, n=5):
    """Tier 3: Request interlibrary loan."""
    tasks = []
    eligible = [pid for pid in ix.active_patrons]
    random.shuffle(eligible)
    books = list(db["books"].keys())
    random.shuffle(books)

    for i in range(min(n, len(eligible), len(books))):
        pid = eligible[i]
        bid = books[i]
        name = patron_name(db, pid)
        title = book_title(db, bid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"interlibrary_loan_{i + 1}",
                purpose="Test interlibrary loan request",
                relevant_policies="Active membership required. Interlibrary loans requested when local copies unavailable.",
                notes=f"Patron {name} requests ILL for '{title}'.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to request an interlibrary loan.",
                reason_for_call=f"You've been looking for '{title}' but can't find it at your local branch. You'd like to request it from another library system.",
                known_info=f"Your name is {name}. You want '{title}'.",
                unknown_info="You're not sure how the interlibrary loan process works.",
                ticket=f"Patron {name} wants an interlibrary loan for '{title}'. Agent should search catalog and submit ILL request.",
                actions=[
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search for '{title}'",
                        compare_args=["title"],
                    ),
                    action(
                        "ill_1",
                        "request_interlibrary_loan",
                        {"patron_id": pid, "book_id": bid},
                        f"Request ILL for '{title}'",
                        compare_args=["patron_id", "book_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_waive_fine_eligible(db, ix, n=5):
    """Tier 3: Waive fine (eligible — first offense)."""
    tasks = []
    # Only fines that are actually waiver-eligible (no other fines on record)
    eligible = list(ix.waiver_eligible_fines)
    # Filter to reasonable amounts (not $50 lost book fines for more realistic scenarios)
    eligible_small = [fid for fid in eligible if db["fines"][fid]["amount"] <= 10.0]
    random.shuffle(eligible_small)
    chosen = eligible_small[:n]

    for i, fid in enumerate(chosen):
        fine = db["fines"][fid]
        pid = fine["patron_id"]
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"waive_fine_{i + 1}",
                purpose="Test fine waiver for eligible patron (first offense)",
                relevant_policies="Fine waivers are only allowed for first offense (no other fines on record).",
                notes=f"Patron {name} has only one fine ({fid}, ${fine['amount']:.2f}) — eligible for waiver.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to ask about getting a fine waived.",
                reason_for_call="You have a library fine and you'd like to ask if it can be waived. This is your first time having a fine.",
                known_info=f"Your name is {name}. You have a fine you'd like waived.",
                unknown_info="You don't know if you're eligible for a waiver. Mention that this is your first offense when the agent asks.",
                ticket=f"Patron {name} requests waiver of fine {fid} (${fine['amount']:.2f}). First offense — eligible. Agent should verify eligibility and waive the fine.",
                actions=[
                    action(
                        "list_fines_1",
                        "list_patron_fines",
                        {"patron_id": pid},
                        f"List fines for {name}",
                    ),
                    action(
                        "waive_1",
                        "waive_fine",
                        {"fine_id": fid, "reason": "first_offense"},
                        f"Waive fine {fid}",
                        compare_args=["fine_id"],
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_fine_status",
                        {"fine_id": fid, "expected_status": "waived"},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_search_availability_checkout(db, ix, n=8):
    """Tier 3: Search → availability → checkout (full flow)."""
    tasks = []
    eligible = [pid for pid in ix.patrons_below_limit if patron_can_checkout(db, pid)]
    random.shuffle(eligible)

    # Find (book, branch) combos with available copies
    avail_combos = list(ix.available_copies_by_book_branch.items())
    random.shuffle(avail_combos)

    count = 0
    patron_idx = 0
    for (book_id, branch_id), copy_ids in avail_combos:
        if count >= n or patron_idx >= len(eligible):
            break
        pid = eligible[patron_idx]
        patron_idx += 1
        cid = copy_ids[0]
        name = patron_name(db, pid)
        title = book_title(db, book_id)
        br = branch_name(db, branch_id)
        loan_count = len(db["patrons"][pid]["active_loans"])
        track_use(pid)
        track_use(cid)

        tasks.append(
            make_task(
                task_id=f"search_checkout_{count + 1}",
                purpose="Test full flow: search catalog → check availability → checkout",
                relevant_policies="Agent should search catalog, verify availability, then process checkout.",
                notes=f"Patron {name} wants '{title}' at {br}. Copy {cid} is available.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to find and check out a specific book.",
                reason_for_call=f"You're looking for '{title}' at the {br} and want to borrow it.",
                known_info=f"Your name is {name}. You want '{title}' at the {br}.",
                unknown_info="You don't know if the book is available.",
                ticket=f"Patron {name} wants '{title}' at {br}. Agent should search, check availability, and check out copy {cid}.",
                actions=[
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search for '{title}'",
                        compare_args=["title"],
                    ),
                    action(
                        "availability_1",
                        "get_book_availability",
                        {"book_id": book_id, "branch_id": branch_id},
                        f"Check availability at {br}",
                        compare_args=["book_id"],
                    ),
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": cid},
                        f"Check out {cid} to {name}",
                        compare_args=["patron_id", "copy_id"],
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": loan_count + 1},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


# ── Tier 4: Complex Multi-Step ────────────────────────────────────────────


def gen_return_then_checkout(db, ix, n=8):
    """Tier 4: Return a book then checkout a new one."""
    tasks = []
    # Patrons with active loans who can checkout after return
    candidates = []
    for lid in ix.active_loans:
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        p = db["patrons"][pid]
        if (
            p["membership_expiry"] >= TODAY
            and p["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD
        ):
            candidates.append(lid)
    random.shuffle(candidates)

    avail = list(ix.available_copies)
    random.shuffle(avail)

    count = 0
    for lid in candidates:
        if count >= n or not avail:
            break
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        return_cid = loan["copy_id"]
        return_bid = copy_book_id(db, return_cid)
        return_title = book_title(db, return_bid)

        new_cid = avail.pop()
        new_bid = copy_book_id(db, new_cid)
        new_title = book_title(db, new_bid)
        new_br = branch_name(db, copy_branch_id(db, new_cid))

        # Skip if same book
        if new_bid == return_bid:
            avail.append(new_cid)
            continue

        name = patron_name(db, pid)
        p = db["patrons"][pid]
        # After return, loan count will be current - 1, then +1 for new checkout = same as current
        final_loan_count = len(p["active_loans"])
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"return_checkout_{count + 1}",
                purpose="Test return of one book followed by checkout of another",
                relevant_policies="Return processes the loan. Checkout requires eligibility.",
                notes=f"Patron {name} returns '{return_title}' and checks out '{new_title}' at {new_br}.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to return a book and borrow a different one.",
                reason_for_call=f"You want to return '{return_title}' and check out '{new_title}' at the {new_br}.",
                known_info=f"Your name is {name}. You have '{return_title}' to return and want '{new_title}' at the {new_br}.",
                unknown_info="You don't know the copy IDs.",
                ticket=f"Patron {name} returns '{return_title}' (copy {return_cid}) and checks out '{new_title}' (copy {new_cid}) at {new_br}.",
                actions=[
                    action(
                        "return_1",
                        "return_book",
                        {"copy_id": return_cid},
                        f"Return {return_cid} ('{return_title}')",
                    ),
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": new_cid},
                        f"Check out {new_cid} ('{new_title}') to {name}",
                        compare_args=["patron_id", "copy_id"],
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": return_cid, "expected_status": "available"},
                    ),
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": new_cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": final_loan_count},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


def gen_renew_membership_register_event(db, ix, n=5):
    """Tier 4: Renew expired membership + register for event."""
    tasks = []
    expired = list(ix.expired_patrons)
    events = list(ix.upcoming_events_with_capacity)
    random.shuffle(expired)
    random.shuffle(events)

    for i in range(min(n, len(expired), len(events))):
        pid = expired[i]
        eid = events[i % len(events)]
        event = db["events"][eid]
        name = patron_name(db, pid)
        brid = event["branch_id"]
        br = branch_name(db, brid)
        track_use(pid)

        if pid in event["registered_patrons"]:
            continue

        tasks.append(
            make_task(
                task_id=f"renew_register_event_{i + 1}",
                purpose="Test membership renewal followed by event registration",
                relevant_policies="Membership must be active for event registration. Expired memberships can be renewed.",
                notes=f"Patron {name} has expired membership. Renew, then register for '{event['title']}' at {br}.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to sign up for a library event but your membership might be expired.",
                reason_for_call=f"You want to attend '{event['title']}' at the {br}.",
                known_info=f"Your name is {name}. You want to attend '{event['title']}' at the {br}.",
                unknown_info="You're not sure if your membership is current. If the agent says it's expired, agree to renew.",
                ticket=f"Patron {name} wants to register for '{event['title']}' at {br}. Membership expired. Agent must renew membership first, then register for event.",
                actions=[
                    action(
                        "renew_1",
                        "renew_membership",
                        {"patron_id": pid},
                        f"Renew membership for {name}",
                    ),
                    action(
                        "register_1",
                        "register_for_event",
                        {"patron_id": pid, "event_id": eid},
                        f"Register {name} for '{event['title']}'",
                        compare_args=["patron_id", "event_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_pay_multiple_fines(db, ix, n=5):
    """Tier 4: Pay multiple fines for same patron."""
    tasks = []
    # Find patrons with multiple outstanding fines
    patron_fines: dict[str, list] = {}
    for fid in ix.outstanding_fines:
        fine = db["fines"][fid]
        patron_fines.setdefault(fine["patron_id"], []).append(fid)

    multi = [(pid, fids) for pid, fids in patron_fines.items() if len(fids) >= 2]
    random.shuffle(multi)

    for i, (pid, fids) in enumerate(multi[:n]):
        name = patron_name(db, pid)
        payment = pick_payment()
        track_use(pid)

        fine_actions = []
        fine_assertions = []
        total = 0.0
        for j, fid in enumerate(fids):
            fine = db["fines"][fid]
            total += fine["amount"]
            fine_actions.append(
                action(
                    f"pay_fine_{j + 1}",
                    "pay_fine",
                    {
                        "fine_id": fid,
                        "amount": fine["amount"],
                        "payment_method": payment,
                    },
                    f"Pay ${fine['amount']:.2f} on {fid}",
                    compare_args=["fine_id"],
                )
            )
            fine_assertions.append(
                env_assert(
                    "assert_fine_status", {"fine_id": fid, "expected_status": "paid"}
                )
            )

        tasks.append(
            make_task(
                task_id=f"pay_multiple_fines_{i + 1}",
                purpose="Test paying multiple outstanding fines",
                relevant_policies="Each fine can be paid individually. Payment reduces patron's total fines_owed.",
                notes=f"Patron {name} pays {len(fids)} fines totaling ${total:.2f}.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to pay off all your library fines.",
                reason_for_call="You want to pay all your outstanding library fines.",
                known_info=f"Your name is {name}. You want to pay all your fines.",
                unknown_info=f"You don't know exactly how many fines you have. Pay them all using {payment}.",
                ticket=f"Patron {name} wants to pay all outstanding fines ({len(fids)} fines, ${total:.2f}). Agent should list fines and process each payment.",
                actions=fine_actions,
                env_assertions=fine_assertions,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_return_overdue_pay_fine(db, ix, n=5):
    """Tier 4: Return overdue book + pay the resulting fine."""
    tasks = []
    overdue = list(ix.overdue_active_loans)
    random.shuffle(overdue)
    chosen = overdue[:n]

    for i, lid in enumerate(chosen):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        payment = pick_payment()
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"return_overdue_pay_{i + 1}",
                purpose="Test returning overdue book and paying the resulting fine",
                relevant_policies="Overdue returns generate fines ($0.25/day). Patron wants to return and pay immediately.",
                notes=f"Patron {name} returns overdue '{title}' (due {loan['due_date']}) and pays the resulting fine.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to return an overdue book and pay any fines right away.",
                reason_for_call=f"You want to return '{title}' — you know it's overdue. You'd like to pay any fine immediately.",
                known_info=f"Your name is {name}. You have '{title}' checked out and it's overdue.",
                unknown_info=f"You don't know the exact fine amount. After returning, agree to pay the full fine using {payment}.",
                ticket=f"Patron {name} returns overdue '{title}' (copy {cid}) and pays the resulting fine immediately via {payment}.",
                actions=[
                    action(
                        "return_1",
                        "return_book",
                        {"copy_id": cid},
                        f"Return overdue {cid} ('{title}')",
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "available"},
                    ),
                ],
                nl_assertions=[
                    "The agent informed the patron about the overdue fine amount",
                    "The agent processed or offered to process the fine payment",
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_hold_plus_checkout_different(db, ix, n=4):
    """Tier 4: Search → unavailable → hold + checkout a different book."""
    tasks = []
    combos = list(ix.books_all_out_at_branch.keys())
    random.shuffle(combos)

    eligible = [pid for pid in ix.patrons_below_limit if patron_can_checkout(db, pid)]
    random.shuffle(eligible)

    avail = list(ix.available_copies)
    random.shuffle(avail)

    count = 0
    patron_idx = 0
    for book_id, branch_id in combos:
        if count >= n or patron_idx >= len(eligible) or not avail:
            break
        pid = eligible[patron_idx]
        patron_idx += 1

        # Find available copy of a different book
        new_cid = None
        for j, c in enumerate(avail):
            if copy_book_id(db, c) != book_id:
                new_cid = avail.pop(j)
                break
        if new_cid is None:
            continue

        name = patron_name(db, pid)
        hold_title = book_title(db, book_id)
        br = branch_name(db, branch_id)
        new_bid = copy_book_id(db, new_cid)
        new_title = book_title(db, new_bid)
        new_br = branch_name(db, copy_branch_id(db, new_cid))
        loan_count = len(db["patrons"][pid]["active_loans"])
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"hold_and_checkout_{count + 1}",
                purpose="Test placing hold on unavailable book and checking out a different available book",
                relevant_policies="Holds placed when unavailable. Checkouts require eligibility.",
                notes=f"Patron {name} places hold on '{hold_title}' at {br} (unavailable) and checks out '{new_title}' at {new_br}.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want two books — one might not be available.",
                reason_for_call=f"You want '{hold_title}' from the {br} and also '{new_title}' from the {new_br}.",
                known_info=f"Your name is {name}. You want '{hold_title}' at the {br} and '{new_title}' at the {new_br}.",
                unknown_info=f"You don't know which books are available. If '{hold_title}' isn't available, ask for a hold.",
                ticket=f"Patron {name} wants '{hold_title}' (unavailable at {br} — place hold) and '{new_title}' (available at {new_br} — checkout).",
                actions=[
                    action(
                        "place_hold_1",
                        "place_hold",
                        {"patron_id": pid, "book_id": book_id, "branch_id": branch_id},
                        f"Place hold on '{hold_title}' at {br}",
                        compare_args=["patron_id", "book_id", "branch_id"],
                    ),
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": new_cid},
                        f"Check out {new_cid} ('{new_title}') to {name}",
                        compare_args=["patron_id", "copy_id"],
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": new_cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": loan_count + 1},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


def gen_renew_membership_pay_fines_checkout(db, ix, n=3):
    """Tier 4: Renew membership + pay fines + checkout (triple combo)."""
    tasks = []
    # Expired patrons with fines > $10
    candidates = [
        pid
        for pid in ix.expired_patrons
        if db["patrons"][pid]["fines_owed"] > FINE_CHECKOUT_BLOCK_THRESHOLD
        and len(db["patrons"][pid]["active_loans"])
        < db["patrons"][pid]["borrowing_limit"]
    ]
    # Also expired patrons with moderate fines
    candidates += [
        pid
        for pid in ix.expired_patrons
        if 0 < db["patrons"][pid]["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD
        and len(db["patrons"][pid]["active_loans"])
        < db["patrons"][pid]["borrowing_limit"]
    ]
    random.shuffle(candidates)

    avail = list(ix.available_copies)
    random.shuffle(avail)

    count = 0
    for pid in candidates:
        if count >= n or not avail:
            break
        p = db["patrons"][pid]
        name = p["name"]
        track_use(pid)

        # Find a fine to pay
        patron_fines = [
            f
            for f in db["fines"].values()
            if f["patron_id"] == pid and f["status"] == "outstanding"
        ]
        if not patron_fines:
            continue

        fine = patron_fines[0]
        fid = fine["fine_id"]
        pay_amount = fine["amount"]
        payment = pick_payment()

        cid = avail.pop()
        bid = copy_book_id(db, cid)
        brid = copy_branch_id(db, cid)
        title = book_title(db, bid)
        br = branch_name(db, brid)
        loan_count = len(p["active_loans"])

        tasks.append(
            make_task(
                task_id=f"full_combo_{count + 1}",
                purpose="Test renewal + fine payment + checkout (triple blocker)",
                relevant_policies="Membership must be active, fines <= $10, and below borrowing limit for checkout.",
                notes=f"Patron {name}: expired membership, ${p['fines_owed']:.2f} in fines. Must renew, pay, then checkout.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to check out a book but your membership might be expired and you have fines.",
                reason_for_call=f"You want to check out '{title}' at the {br}.",
                known_info=f"Your name is {name}. You want '{title}' at the {br}.",
                unknown_info=f"You don't know if your membership is valid or your fine balance. If the agent says your membership is expired, agree to renew. If fines block checkout, agree to pay ${pay_amount:.2f} via {payment}.",
                ticket=f"Patron {name}: expired membership + ${p['fines_owed']:.2f} fines. Agent must: 1) renew membership, 2) collect fine payment, 3) checkout '{title}' at {br}.",
                actions=[
                    action(
                        "renew_1",
                        "renew_membership",
                        {"patron_id": pid},
                        f"Renew membership for {name}",
                    ),
                    action(
                        "pay_fine_1",
                        "pay_fine",
                        {
                            "fine_id": fid,
                            "amount": pay_amount,
                            "payment_method": payment,
                        },
                        f"Pay ${pay_amount:.2f} on {fid}",
                        compare_args=["fine_id"],
                    ),
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": cid},
                        f"Check out {cid} ('{title}') to {name}",
                        compare_args=["patron_id", "copy_id"],
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": loan_count + 1},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


# ── Tier 5: Edge Cases / Policy Failures ──────────────────────────────────


def gen_checkout_at_limit(db, ix, n=3):
    """Tier 5: Patron at borrowing limit tries to checkout."""
    tasks = []
    at_limit = list(ix.patrons_at_limit)
    random.shuffle(at_limit)
    chosen = at_limit[:n]

    avail = list(ix.available_copies)
    random.shuffle(avail)

    for i, pid in enumerate(chosen):
        if not avail:
            break
        cid = avail[i % len(avail)]
        name = patron_name(db, pid)
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        br = branch_name(db, copy_branch_id(db, cid))
        limit = db["patrons"][pid]["borrowing_limit"]
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"checkout_at_limit_{i + 1}",
                purpose="Test checkout when patron is at borrowing limit",
                relevant_policies=f"Patrons cannot exceed their borrowing limit of {limit} books.",
                notes=f"Patron {name} has {limit} active loans (at limit). Checkout should fail gracefully.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to check out another book.",
                reason_for_call=f"You want to check out '{title}' at the {br}.",
                known_info=f"Your name is {name}. You want '{title}' at the {br}.",
                unknown_info="You don't realize you've hit your borrowing limit.",
                ticket=f"Patron {name} wants to checkout but is at borrowing limit ({limit}). Agent should inform patron and suggest returning a book.",
                actions=[],
                nl_assertions=[
                    f"The agent informed the patron they have reached the borrowing limit of {limit} books",
                    "The agent suggested the patron return a book to free up a slot",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_renewal_at_max(db, ix, n=5):
    """Tier 5: Renewal at max renewals."""
    tasks = []
    max_loans = list(ix.max_renewal_loans)
    random.shuffle(max_loans)
    chosen = max_loans[:n]

    for i, lid in enumerate(chosen):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        mr = max_renewals(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"renewal_max_{i + 1}",
                purpose="Test renewal when maximum renewals reached",
                relevant_policies=f"Maximum {mr} renewals allowed. Patron has used all renewals.",
                notes=f"Patron {name} tries to renew '{title}' (loan {lid}) but has {loan['renewals_count']}/{mr} renewals used.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to renew a book you have checked out.",
                reason_for_call=f"You'd like to renew '{title}' — you need more time with it.",
                known_info=f"Your name is {name}. You have '{title}' checked out.",
                unknown_info="You don't know you've already renewed the maximum number of times.",
                ticket=f"Patron {name} wants to renew '{title}' (loan {lid}) but has reached max renewals ({mr}). Agent should inform the patron.",
                actions=[],
                nl_assertions=[
                    f"The agent informed the patron that maximum renewals ({mr}) have been reached",
                    "The agent explained the patron cannot renew the book further",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_renewal_blocked_by_hold(db, ix, n=5):
    """Tier 5: Renewal blocked by pending hold on book."""
    tasks = []
    blocked = list(ix.hold_blocked_loans)
    random.shuffle(blocked)
    chosen = blocked[:n]

    for i, lid in enumerate(chosen):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"renewal_hold_blocked_{i + 1}",
                purpose="Test renewal blocked by pending hold from another patron",
                relevant_policies="Loans cannot be renewed if another patron has a pending hold on the book.",
                notes=f"Patron {name} tries to renew '{title}' but another patron has a hold on it.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to renew a book.",
                reason_for_call=f"You'd like to renew '{title}'.",
                known_info=f"Your name is {name}. You have '{title}' checked out.",
                unknown_info="You don't know that another patron has placed a hold on this book.",
                ticket=f"Patron {name} wants to renew '{title}' (loan {lid}) but a hold exists on the book. Agent should inform the patron.",
                actions=[],
                nl_assertions=[
                    "The agent informed the patron that the book cannot be renewed because another patron has placed a hold",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_event_full(db, ix, n=3):
    """Tier 5: Try to register for a full event."""
    tasks = []
    full = list(ix.full_events)
    random.shuffle(full)
    eligible = [pid for pid in ix.active_patrons]
    random.shuffle(eligible)

    for i in range(min(n, len(full), len(eligible))):
        eid = full[i % len(full)]
        pid = eligible[i]
        event = db["events"][eid]
        name = patron_name(db, pid)
        br = branch_name(db, event["branch_id"])
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"event_full_{i + 1}",
                purpose="Test registration for a full event",
                relevant_policies="Events at capacity cannot accept new registrations.",
                notes=f"Patron {name} tries to register for '{event['title']}' ({eid}) which is full.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to attend a library event.",
                reason_for_call=f"You want to sign up for '{event['title']}' at the {br}.",
                known_info=f"Your name is {name}. You want to attend '{event['title']}' at the {br}.",
                unknown_info="You don't know the event is full.",
                ticket=f"Patron {name} wants to register for '{event['title']}' but it's full. Agent should inform the patron.",
                actions=[],
                nl_assertions=[
                    f"The agent informed the patron that '{event['title']}' is full",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_event_cancelled(db, ix, n=2):
    """Tier 5: Try to register for cancelled/completed event."""
    tasks = []
    events = ix.cancelled_events + ix.completed_events
    random.shuffle(events)
    eligible = [pid for pid in ix.active_patrons]
    random.shuffle(eligible)

    for i in range(min(n, len(events), len(eligible))):
        eid = events[i]
        pid = eligible[i]
        event = db["events"][eid]
        name = patron_name(db, pid)
        br = branch_name(db, event["branch_id"])
        status = event["status"]
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"event_{status}_{i + 1}",
                purpose=f"Test registration for a {status} event",
                relevant_policies=f"Events that are {status} cannot accept registrations.",
                notes=f"Patron {name} tries to register for '{event['title']}' which is {status}.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to attend a library event.",
                reason_for_call=f"You want to sign up for '{event['title']}' at the {br}.",
                known_info=f"Your name is {name}. You want to attend '{event['title']}' at the {br}.",
                unknown_info=f"You don't know the event is {status}.",
                ticket=f"Patron {name} wants to register for '{event['title']}' but it's {status}. Agent should inform the patron.",
                actions=[],
                nl_assertions=[
                    f"The agent informed the patron that '{event['title']}' is {status}",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_hold_unnecessary(db, ix, n=3):
    """Tier 5: Patron asks for hold when copy is available → suggest checkout."""
    tasks = []
    # Find (book, branch) where copies ARE available
    avail_combos = list(ix.available_copies_by_book_branch.keys())
    random.shuffle(avail_combos)
    eligible = [pid for pid in ix.active_patrons]
    random.shuffle(eligible)

    for i in range(min(n, len(avail_combos), len(eligible))):
        book_id, branch_id = avail_combos[i]
        pid = eligible[i]
        name = patron_name(db, pid)
        title = book_title(db, book_id)
        br = branch_name(db, branch_id)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"hold_unnecessary_{i + 1}",
                purpose="Test patron requesting hold when book is actually available",
                relevant_policies="Holds cannot be placed when copies are available at the branch. Agent should suggest checkout instead.",
                notes=f"Patron {name} asks for hold on '{title}' at {br}, but copies are available.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to place a hold on a book.",
                reason_for_call=f"You'd like to place a hold on '{title}' at the {br}. You assume it's not available.",
                known_info=f"Your name is {name}. You want to place a hold on '{title}' at the {br}.",
                unknown_info="You don't realize the book is actually available right now.",
                ticket=f"Patron {name} asks for hold on '{title}' at {br}, but a copy is available. Agent should inform patron the book is available and suggest checking it out instead.",
                actions=[],
                nl_assertions=[
                    f"The agent informed the patron that a copy of '{title}' is available at the {br}",
                    "The agent suggested checking out the book instead of placing a hold",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_waive_fine_ineligible(db, ix, n=4):
    """Tier 5: Patron asks for waiver but has prior fines (ineligible)."""
    tasks = []
    ineligible = list(ix.waiver_ineligible_fines)
    # Filter to non-lost fines for more realistic scenarios
    ineligible = [fid for fid in ineligible if db["fines"][fid]["amount"] <= 10.0]
    random.shuffle(ineligible)
    chosen = ineligible[:n]

    for i, fid in enumerate(chosen):
        fine = db["fines"][fid]
        pid = fine["patron_id"]
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"waive_ineligible_{i + 1}",
                purpose="Test fine waiver denial for patron with prior fines",
                relevant_policies="Fine waivers are only for first offense. Patron with prior fines is ineligible.",
                notes=f"Patron {name} asks for waiver of {fid} but has other fines on record — ineligible.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to ask about getting a fine waived.",
                reason_for_call="You have a library fine and want to see if it can be waived.",
                known_info=f"Your name is {name}.",
                unknown_info="You don't know you're ineligible because you have prior fines on record.",
                ticket=f"Patron {name} requests waiver of {fid} but has prior fines — ineligible. Agent should deny and explain policy.",
                actions=[],
                nl_assertions=[
                    "The agent informed the patron that the fine waiver is not eligible because they have prior fines on record",
                    "The agent explained the waiver policy (first offense only)",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_checkout_unavailable_copy(db, ix, n=3):
    """Tier 5: Patron asks about a copy that's damaged/lost/in-transit."""
    tasks = []
    unavail = [
        cid
        for cid in ix.unavailable_copies
        if db["copies"][cid]["status"] in ("damaged", "lost", "in_transit")
    ]
    random.shuffle(unavail)
    eligible = [pid for pid in ix.active_patrons]
    random.shuffle(eligible)

    for i in range(min(n, len(unavail), len(eligible))):
        cid = unavail[i]
        pid = eligible[i]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        brid = copy_branch_id(db, cid)
        br = branch_name(db, brid)
        status = db["copies"][cid]["status"]
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"checkout_unavailable_{i + 1}",
                purpose=f"Test checkout attempt for {status} copy",
                relevant_policies=f"Copies with status '{status}' cannot be checked out.",
                notes=f"Patron {name} wants '{title}' at {br} but the copy is {status}.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You want to borrow a specific book.",
                reason_for_call=f"You want '{title}' from the {br}.",
                known_info=f"Your name is {name}. You want '{title}' at the {br}.",
                unknown_info=f"You don't know the copy is {status}.",
                ticket=f"Patron {name} wants '{title}' at {br} but copy is {status}. Agent should check availability and inform patron.",
                actions=[],
                nl_assertions=[
                    f"The agent informed the patron that the requested copy is not available (status: {status})",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_transfer_scenarios(db, ix, n=4):
    """Tier 5: Scenarios requiring transfer to human agent."""
    tasks = []
    eligible = [pid for pid in ix.active_patrons]
    random.shuffle(eligible)

    transfer_types = [
        {
            "suffix": "dispute_fine",
            "reason": "You want to dispute a fine on your account. You believe it's an error and insist on speaking with someone who can investigate.",
            "known": "Your name is {name}. You have a fine you believe is incorrect.",
            "unknown": "Even if the agent can't resolve it, keep insisting until they transfer you.",
            "ticket": "Patron {name} wants to dispute a fine and insists on human review. Agent should attempt to help, then transfer when unable to resolve.",
            "nl": [
                "The agent transferred the patron to a human agent after being unable to resolve the dispute"
            ],
        },
        {
            "suffix": "change_info",
            "reason": "You want to update your address and phone number on your library account.",
            "known": "Your name is {name}. You recently moved and need to update your contact information.",
            "unknown": "If the agent can't update your info directly, ask to be transferred to someone who can.",
            "ticket": "Patron {name} wants to update personal information. No tool exists for this. Agent should transfer to human.",
            "nl": [
                "The agent transferred the patron to a human agent for updating personal information"
            ],
        },
        {
            "suffix": "lost_book",
            "reason": "You lost a library book and want to report it.",
            "known": "Your name is {name}. You lost a book you had checked out.",
            "unknown": "You're not sure what happens when a book is lost. Ask the agent for help.",
            "ticket": "Patron {name} reports a lost book. No tool to process this directly. Agent should transfer to human staff.",
            "nl": [
                "The agent transferred the patron to a human agent to handle the lost book report"
            ],
        },
        {
            "suffix": "meeting_room",
            "reason": "You want to reserve a meeting room at the library for a study group.",
            "known": "Your name is {name}. You want to book a meeting room.",
            "unknown": "You expect the library to have meeting rooms available for reservation.",
            "ticket": "Patron {name} wants to reserve a meeting room. Not supported by tools. Agent should transfer to human.",
            "nl": [
                "The agent transferred the patron to a human agent for meeting room reservation"
            ],
        },
    ]

    for i, scenario in enumerate(transfer_types[:n]):
        if i >= len(eligible):
            break
        pid = eligible[i]
        name = patron_name(db, pid)
        track_use(pid)

        tasks.append(
            make_task(
                task_id=f"transfer_{scenario['suffix']}",
                purpose=f"Test transfer to human agent ({scenario['suffix']})",
                relevant_policies="Agent should transfer to human when unable to resolve with available tools.",
                notes=f"Patron {name}: {scenario['suffix']} scenario. Requires human agent.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. {scenario['reason']}",
                reason_for_call=scenario["reason"],
                known_info=scenario["known"].format(name=name),
                unknown_info=scenario["unknown"],
                ticket=scenario["ticket"].format(name=name),
                actions=[
                    action(
                        "transfer_1",
                        "transfer_to_human_agents",
                        {"summary": f"Patron {name}: {scenario['suffix']}"},
                        f"Transfer to human agent",
                        compare_args=[],
                    )
                ],
                nl_assertions=scenario["nl"],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_find_by_card(db, ix, n=3):
    """Tier 5: Patron identifies by card number instead of name."""
    tasks = []
    eligible = [pid for pid in ix.active_patrons]
    random.shuffle(eligible)
    chosen = eligible[:n]

    avail = list(ix.available_copies)
    random.shuffle(avail)

    for i, pid in enumerate(chosen):
        if not avail:
            break
        cid = avail.pop()
        name = patron_name(db, pid)
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        brid = copy_branch_id(db, cid)
        br = branch_name(db, brid)
        loan_count = len(db["patrons"][pid]["active_loans"])
        track_use(pid)

        # Only include if patron can checkout
        if not patron_can_checkout(db, pid):
            avail.append(cid)
            continue

        tasks.append(
            make_task(
                task_id=f"find_by_card_{i + 1}",
                purpose="Test patron lookup by card number instead of name",
                relevant_policies="find_patron_by_card accepts the patron_id as a library card number.",
                notes=f"Patron {name} gives card number '{pid}' instead of name. Agent should use find_patron_by_card.",
                persona=pick_persona(),
                task_instructions=f"You are {name}. You prefer to identify yourself by your library card number rather than your name.",
                reason_for_call=f"You want to check out '{title}' at the {br}.",
                known_info=f"Your library card number is {pid}. You want '{title}' at the {br}.",
                unknown_info="You don't want to give your name — only your card number. If the agent asks for your name, provide your card number instead.",
                ticket=f"Patron gives card number '{pid}' (not name). Agent should use find_patron_by_card, then check out '{title}' at {br}.",
                actions=[
                    action(
                        "find_1",
                        "find_patron_by_card",
                        {"card_number": pid},
                        f"Look up patron by card {pid}",
                    ),
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": cid},
                        f"Check out {cid} to {name}",
                        compare_args=["patron_id", "copy_id"],
                    ),
                ],
                env_assertions=[
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": loan_count + 1},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    random.seed(SEED)
    db = load_db()
    ix = build_indexes(db)

    all_tasks = []
    stats = {}

    # Tier 1: Simple Single-Action (~60)
    generators_t1 = [
        ("simple_checkout", gen_simple_checkout, 18),
        ("simple_return", gen_simple_return, 12),
        ("overdue_return", gen_overdue_return, 10),
        ("renew_loan", gen_renew_loan, 10),
        ("pay_fine_full", gen_pay_fine_full, 7),
        ("cancel_hold", gen_cancel_hold, 4),
        ("renew_membership", gen_renew_membership, 3),
    ]

    # Tier 2: Information & Search (~30)
    generators_t2 = [
        ("search_title", gen_search_by_title, 7),
        ("search_author_category", gen_search_by_author, 7),
        ("check_availability", gen_check_availability, 6),
        ("list_loans", gen_list_loans, 5),
        ("list_fines", gen_list_fines, 5),
    ]

    # Tier 3: Moderate Multi-Step (~55)
    generators_t3 = [
        ("checkout_with_fines", gen_checkout_blocked_by_fines, 8),
        ("checkout_expired_membership", gen_checkout_blocked_by_membership, 8),
        ("place_hold", gen_place_hold, 8),
        ("register_event", gen_register_event, 8),
        ("pay_fine_partial", gen_pay_fine_partial, 5),
        ("interlibrary_loan", gen_interlibrary_loan, 5),
        ("waive_fine", gen_waive_fine_eligible, 5),
        ("search_checkout", gen_search_availability_checkout, 8),
    ]

    # Tier 4: Complex Multi-Step (~30)
    generators_t4 = [
        ("return_checkout", gen_return_then_checkout, 8),
        ("renew_register_event", gen_renew_membership_register_event, 5),
        ("pay_multiple_fines", gen_pay_multiple_fines, 5),
        ("return_overdue_pay", gen_return_overdue_pay_fine, 5),
        ("hold_and_checkout", gen_hold_plus_checkout_different, 4),
        ("full_combo", gen_renew_membership_pay_fines_checkout, 3),
    ]

    # Tier 5: Edge Cases (~35)
    generators_t5 = [
        ("checkout_at_limit", gen_checkout_at_limit, 3),
        ("renewal_max", gen_renewal_at_max, 5),
        ("renewal_hold_blocked", gen_renewal_blocked_by_hold, 5),
        ("event_full", gen_event_full, 3),
        ("event_cancelled", gen_event_cancelled, 2),
        ("hold_unnecessary", gen_hold_unnecessary, 3),
        ("waive_ineligible", gen_waive_fine_ineligible, 4),
        ("checkout_unavailable", gen_checkout_unavailable_copy, 3),
        ("transfer", gen_transfer_scenarios, 4),
        ("find_by_card", gen_find_by_card, 3),
    ]

    tier_names = [
        ("Tier 1: Simple Single-Action", generators_t1),
        ("Tier 2: Information & Search", generators_t2),
        ("Tier 3: Moderate Multi-Step", generators_t3),
        ("Tier 4: Complex Multi-Step", generators_t4),
        ("Tier 5: Edge Cases", generators_t5),
    ]

    for tier_name, generators in tier_names:
        tier_tasks = []
        for name, gen_fn, target_n in generators:
            tasks = gen_fn(db, ix, n=target_n)
            stats[name] = {"target": target_n, "actual": len(tasks)}
            tier_tasks.extend(tasks)
        all_tasks.extend(tier_tasks)
        tier_total = sum(
            s["actual"] for n, _, _ in generators for n2, s in stats.items() if n2 == n
        )

    # Validate unique IDs
    ids = [t["id"] for t in all_tasks]
    dupes = [tid for tid in ids if ids.count(tid) > 1]
    if dupes:
        print(f"WARNING: Duplicate task IDs: {set(dupes)}")

    # Print stats
    print(f"\n{'=' * 60}")
    print(f"Generated {len(all_tasks)} tasks")
    print(f"{'=' * 60}")
    for tier_name, generators in tier_names:
        tier_total = sum(stats[n]["actual"] for n, _, _ in generators)
        print(f"\n{tier_name}: {tier_total} tasks")
        for name, _, _ in generators:
            s = stats[name]
            marker = " *" if s["actual"] < s["target"] else ""
            print(f"  {name:35s} {s['actual']:3d}/{s['target']:3d}{marker}")

    # Reward basis distribution
    rb_counts: dict[str, int] = {}
    for t in all_tasks:
        for rb in t["evaluation_criteria"]["reward_basis"]:
            rb_counts[rb] = rb_counts.get(rb, 0) + 1
    print(f"\nReward basis distribution:")
    for rb, count in sorted(rb_counts.items()):
        print(f"  {rb}: {count}")

    # Write
    with open(TASKS_PATH, "w") as f:
        json.dump(all_tasks, f, indent=2)
    print(f"\nWritten to {TASKS_PATH}")


if __name__ == "__main__":
    main()
