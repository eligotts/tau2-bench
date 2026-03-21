#!/usr/bin/env python3
"""
Programmatically author reason_for_call, known_info, and ticket fields
for 159 daily planner tasks in task_specs.runtime.yaml.

Uses task_narrative_briefs.yaml for entity_context, notable_start_state,
start_bindings, undisclosed_binding_values, terminal_profile, resolved_when.
"""

import hashlib
import re
import yaml
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BRIEFS_PATH = BASE / "data" / "tau2" / "domains" / "daily_planner" / "task_narrative_briefs.yaml"
RUNTIME_PATH = BASE / "data" / "tau2" / "domains" / "daily_planner" / "task_specs.runtime.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_seed(name: str, task_id: str) -> int:
    """Deterministic hash for variation."""
    return int(hashlib.md5(f"{name}:{task_id}".encode()).hexdigest(), 16)


def _pick(seed: int, options: list[str]) -> str:
    return options[seed % len(options)]


def _parse_notable_state(lines: list[str]) -> dict[str, str]:
    """Parse notable_start_state lines into a dict."""
    state = {}
    for line in lines:
        m = re.match(r"^(.+?)\s*=\s*(.+)$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip().strip("'\"")
            state[key] = val
    return state


def _binding_map(start_bindings: list[dict]) -> dict[str, dict]:
    """Index start_bindings by binding_id."""
    return {b["binding_id"]: b for b in start_bindings}


def _binding_ids(start_bindings: list[dict]) -> set[str]:
    return {b["binding_id"] for b in start_bindings}


# ---------------------------------------------------------------------------
# Narrative generators — one per terminal_profile
# ---------------------------------------------------------------------------

def _gen_errands_done(name, state, bindings, seed, resolved_when, undisclosed):
    """Two errands need completing. Transport may be broken."""
    car_issue = state.get("agent.transport.car_issue", "none")
    has_car_issue = car_issue in ("flat_tire", "in_shop", "low_fuel")
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    # --- Human-readable car issue text, include raw value for checker ---
    car_text = {"flat_tire": "flat tire (flat_tire)", "in_shop": "in the shop (in_shop)", "low_fuel": "low on fuel (low_fuel)"}
    car_human = car_text.get(car_issue, "car trouble")

    # Whether transport_situation is disclosed (in start_bindings)
    transport_disclosed = "transport_situation" in bids
    # Whether errand_a_options is disclosed
    errand_a_disclosed = "errand_a_options" in bids

    # --- reason_for_call (first person, natural) ---
    if transport_disclosed:
        # User already knows about their transport issue
        openers = [
            f"My car has a {car_human} and I have a couple of errands to get done today. Can you help me figure out logistics?",
            f"I can't drive today because my car has a {car_human}. I still have two errands that need to get done.",
            f"Since my car has a {car_human}, I need help planning how to get my errands handled today.",
            f"My car has a {car_human} so driving is out. I need help getting two errands taken care of.",
        ]
    elif has_car_issue:
        # Transport is broken but user doesn't mention it yet (cold start)
        openers = [
            "I have a couple of errands I need to get done today and I'm not sure how to fit them in. Can you help me figure out the best way to handle them?",
            "I need help organizing my errands for the day. There are a few things I need to pick up or get delivered and I want to make sure everything gets taken care of.",
            "Hey, I've got some errands that need doing today and I could use a hand planning them out. Some might need delivery, others I might need to go get myself.",
            "I'm trying to get a few things done today but my schedule is a bit complicated. Can you help me work through my errands and figure out the logistics?",
            "I've got errands piling up and I need help sorting them out. Can you check what needs doing and help me get everything completed?",
        ]
    else:
        openers = [
            "I have a couple of errands to handle today. Can you help me get them organized and completed?",
            "I need help getting my errands done today. There are a couple of things I need to pick up or have delivered.",
            "Hey, I've got errands to take care of and I want to make sure they all get handled. Can you help?",
            "I'm trying to get some errands completed today and could use help coordinating everything.",
        ]

    reason = _pick(seed, openers)

    # --- known_info (second person) ---
    known_parts = [f"You are {name}."]

    if transport_disclosed:
        known_parts.append(f"Your car has a {car_human} and is not drivable.")

    if errand_a_disclosed:
        bval = str(bmap["errand_a_options"]["value"])
        known_parts.append(f"You have already looked into one of your errands and delivery is available for it ({bval}).")

    known_parts.append("You have errands that need completing today.")
    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")

    known = " ".join(known_parts)

    # --- ticket (third person) ---
    ticket_parts = [f"User {name} needs help completing errands for the day."]

    if transport_disclosed:
        ticket_parts.append(f"Note: User's car has a {car_human}.")

    if errand_a_disclosed:
        bval = str(bmap["errand_a_options"]["value"])
        ticket_parts.append(f"Note: User has confirmed delivery is available for one errand ({bval}).")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)

    return reason, known, ticket


def _gen_rescheduled_paid(name, state, bindings, seed, resolved_when, undisclosed):
    """Meeting conflict to reschedule + bill to pay."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    # Determine what's disclosed
    calendar_disclosed = "calendar_state" in bids
    accounts_disclosed = "account_balances" in bids

    openers = [
        "I have a scheduling conflict with one of my meetings and I also need to take care of a bill. Can you help me sort both out?",
        "Hey, I need help with a calendar issue and a payment that's due. There's a meeting that needs rescheduling and a bill I want to get paid.",
        "I've got a meeting conflict I need resolved and a bill that needs paying. Can you help me handle both of these today?",
        "I need to reschedule a meeting and also make sure a bill gets paid. Can you walk me through getting both handled?",
    ]
    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        known_parts.append(f"You have a meeting conflict involving meeting {meeting_id} that needs rescheduling.")
    else:
        known_parts.append("You have a meeting conflict that needs rescheduling.")

    if accounts_disclosed:
        sufficient = str(bmap["account_balances"]["value"])
        if sufficient == "True":
            known_parts.append("You have checked your accounts and have sufficient funds (True) available.")
        else:
            known_parts.append("You have checked your accounts and funds are insufficient (False).")
    else:
        known_parts.append("You also have a bill to pay.")

    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help rescheduling a meeting and paying a bill."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        ticket_parts.append(f"Note: Meeting conflict involves meeting {meeting_id}.")
    if accounts_disclosed:
        sufficient = str(bmap["account_balances"]["value"])
        if sufficient == "True":
            ticket_parts.append(f"Note: User reports having sufficient funds (True).")
        else:
            ticket_parts.append(f"Note: User reports insufficient funds (False).")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


def _gen_cancelled_paid(name, state, bindings, seed, resolved_when, undisclosed):
    """Meeting to cancel + bill to pay."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    calendar_disclosed = "calendar_state" in bids
    accounts_disclosed = "account_balances" in bids
    budget_disclosed = "budget_status" in bids

    openers = [
        "I need to cancel a meeting and take care of a bill payment. Can you help me handle both?",
        "Hey, there's a meeting I need to cancel and a bill that's due. Can you help me get both of these sorted out?",
        "I've got a meeting that needs cancelling and a payment to make. Can you help me work through both?",
        "I need help cancelling a meeting and paying a bill today. The meeting isn't going to work out and the bill needs attention.",
        "Can you help me cancel a meeting and handle a bill? I need to send apologies for the meeting and get the payment sorted.",
    ]
    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        known_parts.append(f"You need to cancel a meeting (meeting {meeting_id}) and send an apology.")
    else:
        known_parts.append("You need to cancel a meeting and send an apology.")

    if accounts_disclosed:
        sufficient = str(bmap["account_balances"]["value"])
        if sufficient == "True":
            known_parts.append(f"You have checked your accounts and have sufficient funds (True) available.")
        else:
            known_parts.append(f"You have checked your accounts and funds are insufficient (False).")
    elif budget_disclosed:
        budget_val = str(bmap["budget_status"]["value"])
        known_parts.append(f"You have checked your budget and your funds are {budget_val}.")
    else:
        known_parts.append("You also have a bill to pay.")

    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help cancelling a meeting and paying a bill."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        ticket_parts.append(f"Note: Meeting to cancel is {meeting_id}.")
    if accounts_disclosed:
        sufficient = str(bmap["account_balances"]["value"])
        if sufficient == "True":
            ticket_parts.append(f"Note: User reports having sufficient funds (True).")
        else:
            ticket_parts.append(f"Note: User reports insufficient funds (False).")
    if budget_disclosed:
        budget_val = str(bmap["budget_status"]["value"])
        ticket_parts.append(f"Note: User reports budget is {budget_val}.")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


def _gen_rescheduled_deferred(name, state, bindings, seed, resolved_when, undisclosed):
    """Meeting conflict to reschedule + bill to defer (broke)."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    calendar_disclosed = "calendar_state" in bids
    budget_disclosed = "budget_status" in bids

    openers = [
        "I have a meeting conflict and a bill situation to deal with. I'm not sure I can pay the bill right now. Can you help?",
        "Hey, I need to reschedule a meeting and figure out what to do about a bill. Money is tight.",
        "I've got a calendar conflict and a financial matter to handle. Can you help me work through the options?",
    ]
    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        known_parts.append(f"You have a meeting conflict involving meeting {meeting_id} that needs rescheduling.")
    else:
        known_parts.append("You have a meeting conflict that needs rescheduling.")

    if budget_disclosed:
        budget_val = str(bmap["budget_status"]["value"])
        known_parts.append(f"You have checked your budget and your funds are {budget_val}.")
    else:
        known_parts.append("You also have a bill to deal with but you are not sure you can pay it.")

    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help rescheduling a meeting and handling a bill."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        ticket_parts.append(f"Note: Meeting conflict involves meeting {meeting_id}.")
    if budget_disclosed:
        budget_val = str(bmap["budget_status"]["value"])
        ticket_parts.append(f"Note: User reports budget is {budget_val}.")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


def _gen_cancelled_deferred(name, state, bindings, seed, resolved_when, undisclosed):
    """Meeting to cancel + bill to defer."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    calendar_disclosed = "calendar_state" in bids
    budget_disclosed = "budget_status" in bids

    openers = [
        "I need to cancel a meeting and deal with a bill I might not be able to pay right now. Can you help me figure out the options?",
        "Hey, there's a meeting I need to cancel and a bill that's causing me stress. I may need to defer the payment.",
        "I've got a meeting to cancel and a financial situation to sort out. Can you help me handle both?",
        "I need help cancelling a meeting and figuring out what to do about a bill. I'm not sure I can pay it.",
        "Can you help me cancel a meeting and look into deferring a bill? I may not have the funds to cover it.",
    ]
    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        known_parts.append(f"You need to cancel a meeting (meeting {meeting_id}) and send an apology.")
    else:
        known_parts.append("You need to cancel a meeting and send an apology.")

    if budget_disclosed:
        budget_val = str(bmap["budget_status"]["value"])
        known_parts.append(f"You have checked your budget and your funds are {budget_val}.")
    else:
        known_parts.append("You also have a bill to deal with but you may not be able to pay it.")

    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help cancelling a meeting and handling a bill."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        ticket_parts.append(f"Note: Meeting to cancel is {meeting_id}.")
    if budget_disclosed:
        budget_val = str(bmap["budget_status"]["value"])
        ticket_parts.append(f"Note: User reports budget is {budget_val}.")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


def _gen_care_done(name, state, bindings, seed, resolved_when, undisclosed):
    """Dependent care pickup needed."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    transport_disclosed = "transport_situation" in bids

    car_issue = state.get("agent.transport.car_issue", "none")
    has_car_issue = car_issue in ("flat_tire", "in_shop", "low_fuel")
    car_text_raw = {"flat_tire": "flat tire (flat_tire)", "in_shop": "in the shop (in_shop)", "low_fuel": "low on fuel (low_fuel)"}
    car_human = car_text_raw.get(car_issue, "car trouble")

    if transport_disclosed:
        openers = [
            f"My car has a {car_human} and I need to arrange pickup for my dependent today. Can you help?",
            f"I can't drive because my car has a {car_human}. I need help making sure my dependent gets picked up.",
            f"My car has a {car_human} so I can't do the pickup myself. Can you help me arrange it?",
        ]
    elif has_car_issue:
        openers = [
            "I need to arrange a pickup for my dependent today. Can you help me get that sorted?",
            "Hey, I need help making sure the dependent care pickup happens today. Can you check on the options?",
            "I have a dependent care pickup that needs to happen and I want to make sure it's all arranged properly.",
            "Can you help me handle a dependent care pickup? I need to make sure someone gets picked up on time.",
            "I need to get a pickup arranged for dependent care today. Can you help me figure out the logistics?",
        ]
    else:
        openers = [
            "I need help coordinating a pickup for my dependent today.",
            "My dependent needs to be picked up and I need to figure out the best way to handle it.",
            "I'm trying to arrange for someone to handle a dependent pickup today. Can you help?",
            "I need to get my dependent picked up today. Can you help me plan this out?",
        ]

    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if transport_disclosed:
        known_parts.append(f"Your car has a {car_human} and is not drivable.")
    known_parts.append("Your dependent needs to be picked up today.")
    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help arranging dependent care pickup."]
    if transport_disclosed:
        ticket_parts.append(f"Note: User's car has a {car_human}.")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


def _gen_household_done(name, state, bindings, seed, resolved_when, undisclosed):
    """Household maintenance needed."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    maintenance_disclosed = "maintenance_info" in bids

    openers = [
        "I've got a maintenance issue at home that needs to be taken care of. Can you help me get it resolved?",
        "Something needs fixing around the house and I need to get a professional out here.",
        "I have a household repair that needs attention. Can you help me sort it out?",
        "There's a maintenance problem at my place and I need help getting it resolved.",
    ]
    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if maintenance_disclosed:
        maint_val = str(bmap["maintenance_info"]["value"])
        known_parts.append(f"You have a household maintenance issue that has been {maint_val}.")
    else:
        known_parts.append("You have a household maintenance issue that needs professional attention.")
    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help resolving a household maintenance issue."]
    if maintenance_disclosed:
        maint_val = str(bmap["maintenance_info"]["value"])
        ticket_parts.append(f"Note: Maintenance issue has been {maint_val}.")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


def _gen_errands_care_done(name, state, bindings, seed, resolved_when, undisclosed):
    """One errand + dependent care pickup."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    transport_disclosed = "transport_situation" in bids

    car_issue = state.get("agent.transport.car_issue", "none")
    has_car_issue = car_issue in ("flat_tire", "in_shop", "low_fuel")
    car_text_raw = {"flat_tire": "flat tire (flat_tire)", "in_shop": "in the shop (in_shop)", "low_fuel": "low on fuel (low_fuel)"}
    car_human = car_text_raw.get(car_issue, "car trouble")

    if transport_disclosed:
        openers = [
            f"My car has a {car_human} and I have an errand to take care of plus a dependent care pickup to arrange. Can you help?",
            f"I can't drive today because my car has a {car_human}. I still need to handle an errand and get my dependent picked up.",
            f"Since my car has a {car_human}, I need help planning how to get my errand done and my dependent picked up.",
            f"My car has a {car_human} so I'm stuck. I have an errand and a dependent pickup that both need handling.",
        ]
    else:
        openers = [
            "I have an errand to take care of and a dependent care pickup to arrange. Can you help me handle both?",
            "Hey, I need to get an errand done and also make sure a dependent care pickup happens. Can you help me plan this out?",
            "I've got an errand and a pickup for dependent care that both need handling today. Can you help?",
            "I need help with an errand and arranging dependent care pickup. Both need to get done today.",
        ]

    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if transport_disclosed:
        known_parts.append(f"Your car has a {car_human} and is not drivable.")
    known_parts.append("You have an errand to complete and a dependent care pickup to arrange.")
    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help completing an errand and arranging dependent care pickup."]
    if transport_disclosed:
        ticket_parts.append(f"Note: User's car has a {car_human}.")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


def _gen_rescheduled_care_household(name, state, bindings, seed, resolved_when, undisclosed):
    """Meeting reschedule + dependent care + household maintenance."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    calendar_disclosed = "calendar_state" in bids
    maintenance_disclosed = "maintenance_info" in bids

    openers = [
        "I have a meeting conflict, a dependent care pickup, and a household maintenance issue all happening today. Can you help me manage everything?",
        "Hey, I need to reschedule a meeting, arrange a pickup for dependent care, and deal with a maintenance issue. Can you help me sort it all out?",
        "I've got a scheduling conflict plus dependent care and household maintenance to handle. Can you help me work through everything?",
        "I need help with a meeting reschedule, a dependent pickup, and home maintenance. It's a lot to juggle today.",
    ]
    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        known_parts.append(f"You have a meeting conflict involving meeting {meeting_id} that needs rescheduling.")
    else:
        known_parts.append("You have a meeting conflict that needs rescheduling.")

    known_parts.append("Your dependent needs to be picked up today.")

    if maintenance_disclosed:
        maint_val = str(bmap["maintenance_info"]["value"])
        known_parts.append(f"You have a household maintenance issue that has been {maint_val}.")
    else:
        known_parts.append("You have a household maintenance issue to resolve.")

    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help rescheduling a meeting, arranging dependent care, and handling household maintenance."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        ticket_parts.append(f"Note: Meeting conflict involves meeting {meeting_id}.")
    if maintenance_disclosed:
        maint_val = str(bmap["maintenance_info"]["value"])
        ticket_parts.append(f"Note: Maintenance issue has been {maint_val}.")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


def _gen_cancelled_care_household(name, state, bindings, seed, resolved_when, undisclosed):
    """Meeting to cancel + dependent care + household maintenance."""
    bids = _binding_ids(bindings)
    bmap = _binding_map(bindings)

    calendar_disclosed = "calendar_state" in bids
    maintenance_disclosed = "maintenance_info" in bids

    openers = [
        "I need to cancel a meeting, arrange dependent care pickup, and deal with a household maintenance issue. Can you help?",
        "Hey, there's a meeting I need to cancel, plus I have dependent care and maintenance to handle. Can you help me get through all of it?",
        "I've got a meeting to cancel and I also need to take care of dependent pickup and a maintenance matter. Can you help?",
        "I need help cancelling a meeting and managing dependent care pickup and household maintenance today.",
    ]
    reason = _pick(seed, openers)

    known_parts = [f"You are {name}."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        known_parts.append(f"You need to cancel a meeting (meeting {meeting_id}) and send an apology.")
    else:
        known_parts.append("You need to cancel a meeting and send an apology.")

    known_parts.append("Your dependent needs to be picked up today.")

    if maintenance_disclosed:
        maint_val = str(bmap["maintenance_info"]["value"])
        known_parts.append(f"You have a household maintenance issue that has been {maint_val}.")
    else:
        known_parts.append("You have a household maintenance issue to resolve.")

    known_parts.append("You have not yet checked any planning tools or confirmed arrangements.")
    known = " ".join(known_parts)

    ticket_parts = [f"User {name} needs help cancelling a meeting, arranging dependent care, and handling household maintenance."]
    if calendar_disclosed:
        meeting_id = bmap["calendar_state"]["value"]
        ticket_parts.append(f"Note: Meeting to cancel is {meeting_id}.")
    if maintenance_disclosed:
        maint_val = str(bmap["maintenance_info"]["value"])
        ticket_parts.append(f"Note: Maintenance issue has been {maint_val}.")

    resolution_items = []
    for rw in resolved_when:
        resolution_items.append(rw["unmet_reason"].replace(" has not been ", " is ").replace(" yet.", "."))
    if resolution_items:
        ticket_parts.append("Issue will be considered resolved when: " + " and ".join(resolution_items))

    ticket = " ".join(ticket_parts)
    return reason, known, ticket


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

GENERATORS = {
    "errands_done": _gen_errands_done,
    "rescheduled_paid": _gen_rescheduled_paid,
    "cancelled_paid": _gen_cancelled_paid,
    "rescheduled_deferred": _gen_rescheduled_deferred,
    "cancelled_deferred": _gen_cancelled_deferred,
    "care_done": _gen_care_done,
    "household_done": _gen_household_done,
    "errands_care_done": _gen_errands_care_done,
    "rescheduled_care_household": _gen_rescheduled_care_household,
    "cancelled_care_household": _gen_cancelled_care_household,
}


def main():
    # Load briefs
    with open(BRIEFS_PATH) as f:
        briefs_data = yaml.safe_load(f)
    briefs_by_id = {t["task_id"]: t for t in briefs_data["tasks"]}

    # Load runtime
    with open(RUNTIME_PATH) as f:
        runtime_data = yaml.safe_load(f)

    authored = 0
    skipped = 0

    for task in runtime_data["tasks"]:
        tid = task["task_id"]
        brief = briefs_by_id.get(tid)
        if brief is None:
            print(f"WARNING: no brief for {tid}")
            skipped += 1
            continue

        tp = brief["terminal_profile"]
        gen = GENERATORS.get(tp)
        if gen is None:
            print(f"WARNING: no generator for terminal_profile '{tp}' (task {tid})")
            skipped += 1
            continue

        name = brief["entity_context"]["name"]
        state = _parse_notable_state(brief.get("notable_start_state", []))
        start_bindings = brief.get("start_bindings", [])
        resolved_when = brief.get("resolved_when", [])
        undisclosed = brief.get("undisclosed_binding_values", [])
        seed = _hash_seed(name, tid)

        reason, known, ticket = gen(name, state, start_bindings, seed, resolved_when, undisclosed)

        task["runtime"]["reason_for_call"] = reason
        task["runtime"]["known_info"] = known
        task["runtime"]["ticket"] = ticket
        authored += 1

    # Write back
    with open(RUNTIME_PATH, "w") as f:
        yaml.dump(runtime_data, f, default_flow_style=False, allow_unicode=True, width=120, sort_keys=False)

    print(f"Done. Authored: {authored}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
