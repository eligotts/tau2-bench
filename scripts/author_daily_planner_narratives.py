#!/usr/bin/env python3
"""
Programmatically author reason_for_call, known_info, and ticket fields
for 593 daily planner tasks in task_specs.runtime.yaml.

Uses task_narrative_briefs.yaml for entity_context, start_state_summary,
goal_state_summary, and goal_binding_do_not_disclose.
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


def _parse_state(world_lines: list[str]) -> dict[str, str]:
    """Parse start_state_summary.world lines into a dict."""
    state = {}
    for line in world_lines:
        m = re.match(r"^(.+?)\s*=\s*(.+)$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip().strip("'\"")
            state[key] = val
    return state


def _get_prefix(task_id: str) -> str:
    for p in ["cch2", "cch", "cfp", "cfd", "dfc", "dc", "df", "ec", "cc", "hh", "te"]:
        if task_id.startswith(p + "_"):
            return p
    return "unknown"


# ---------------------------------------------------------------------------
# Narrative generators — one per schema prefix
# ---------------------------------------------------------------------------

def _gen_te(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """transport_errands: Car has issue, two errands pending, may need rideshare."""
    car_issue = state.get("agent.transport.car_issue", "flat_tire")
    car_issue_human = "flat tire" if car_issue == "flat_tire" else "car trouble"
    rs_ok = state.get("agent.transport.rideshare_will_succeed", "True") == "True"
    del_a_avail = state.get("agent.errand_a.delivery_available", "True") == "True"
    del_b_avail = state.get("agent.errand_b.delivery_available", "True") == "True"
    funds = state.get("agent.finance.available_funds", "plenty")

    # reason_for_call — first person
    openers = [
        f"I just found out I have a {car_issue_human} and I can't drive anywhere today.",
        f"My car has a {car_issue_human} so I'm stuck at home right now.",
        f"I'm dealing with a {car_issue_human} situation — my car is completely out of commission.",
        f"So my car won't start — turns out it's a {car_issue_human}.",
    ]
    errand_bits = [
        "I've got a couple of errands I really need to get done today.",
        "There are two things I need picked up or taken care of today.",
        "I have two errands that can't wait — I need help figuring out how to handle them.",
        "I still need to get two errands sorted out even though I can't drive.",
    ]
    budget_bits = {
        "plenty": [
            "Money isn't an issue, I just need to figure out logistics.",
            "Budget should be fine, it's more about how to get things done.",
        ],
        "tight": [
            "I'm also a bit tight on cash so I need to be careful about spending.",
            "Budget-wise things are a little tight so I'd like to keep costs down.",
        ],
        "broke": [
            "And on top of that I'm basically broke right now.",
            "I really don't have extra money to throw at this.",
        ],
    }
    reason = (
        _pick(seed, openers) + " " +
        _pick(seed >> 4, errand_bits) + " " +
        _pick(seed >> 8, budget_bits.get(funds, budget_bits["plenty"]))
    )

    # known_info — second person
    delivery_note = ""
    if del_a_avail and del_b_avail:
        delivery_note = "Both errands may have delivery options available."
    elif del_a_avail:
        delivery_note = "One of your errands might be available for delivery, but the other would need a pickup trip."
    elif del_b_avail:
        delivery_note = "One errand might be deliverable, but you'd need to go pick up the other one in person."
    else:
        delivery_note = "Neither errand has delivery available — you'd need transportation for both."

    known = (
        f"You are {name}. Your car currently has a {car_issue_human} and is not drivable. "
        f"You have two pending errands that need to be completed today. {delivery_note}"
    )

    # ticket — third person
    resolution_bits = [
        "They will consider the issue resolved when both errands are completed and their budget situation has been reviewed.",
        "They will consider the issue resolved when both errands are taken care of and finances have been checked.",
    ]
    ticket = (
        f"{name} has a {car_issue_human} and cannot drive. They have two pending errands and "
        f"{'ample' if funds == 'plenty' else 'limited'} funds. "
        + _pick(seed >> 12, resolution_bits)
    )

    return reason, known, ticket


def _gen_cfp(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """calendar_finance_pay: Calendar conflict + bill to pay. Has funds."""
    funds = state.get("agent.finance.available_funds", "plenty")

    openers = [
        "I just realized I have a scheduling conflict and there's a bill I need to pay today too.",
        "I've got a meeting that overlaps with something else on my calendar, and I also need to deal with a bill that's due.",
        "My calendar is a mess — I have two things at the same time, and on top of that there's a bill I haven't paid yet.",
        "I noticed a conflict on my schedule and I also have an outstanding bill that needs attention.",
    ]
    reason = _pick(seed, openers)

    known = (
        f"You are {name}. You have a scheduling conflict on your calendar that needs to be resolved. "
        f"You also have an unpaid bill that is due. You have {'sufficient' if funds == 'plenty' else 'enough'} funds to cover payment."
    )

    ticket = (
        f"{name} has a calendar conflict and an unpaid bill. They have sufficient funds to pay. "
        "They will consider the issue resolved when the scheduling conflict is sorted out and the bill has been paid."
    )

    return reason, known, ticket


def _gen_cfd(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """calendar_finance_defer: Calendar conflict + bill, but broke."""
    openers = [
        "I have a calendar conflict and a bill that's due, but I really can't afford to pay it right now.",
        "My schedule has a conflict I need to fix, and there's a bill due that I just don't have the money for.",
        "I'm in a bind — I've got two things scheduled at the same time and a bill I can't pay because I'm short on cash.",
        "There's a conflict in my calendar and I need to figure out what to do about a bill I can't cover right now.",
    ]
    reason = _pick(seed, openers)

    known = (
        f"You are {name}. You have a scheduling conflict on your calendar that needs to be resolved. "
        f"You also have a bill that is due, but you do not currently have enough funds to pay it."
    )

    ticket = (
        f"{name} has a calendar conflict and an outstanding bill but insufficient funds to pay. "
        "They will consider the issue resolved when the calendar conflict is sorted out and the bill situation has been addressed appropriately."
    )

    return reason, known, ticket


def _gen_dc(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """dependent_care: Child needs pickup. Delegate paths."""
    car_issue = state.get("agent.transport.car_issue", "none")
    has_car_issue = car_issue != "none"
    car_issue_human = "flat tire" if car_issue == "flat_tire" else "car trouble"

    openers_no_car = [
        "I need someone to pick up my child but my car has a {ci} so I can't do it myself.",
        "My kid needs to be picked up and I'm stuck — my car has a {ci}.",
        "I can't pick up my child because of a {ci} situation with my car.",
    ]
    openers_car_ok = [
        "I need help coordinating my child's pickup today — I can't do it myself.",
        "My child needs to be picked up and I need to figure out who can handle it.",
        "I'm trying to arrange for someone to pick up my kid today.",
        "I need to get my child picked up but I'm not going to be able to do it personally.",
    ]

    if has_car_issue:
        reason = _pick(seed, openers_no_car).format(ci=car_issue_human)
    else:
        reason = _pick(seed, openers_car_ok)

    transport_note = ""
    if has_car_issue:
        transport_note = f" Your car currently has a {car_issue_human} and is not drivable."

    known = (
        f"You are {name}. Your child needs to be picked up from their facility today.{transport_note} "
        f"You need to arrange for someone to handle the pickup."
    )

    transport_ticket = f" Their car has a {car_issue_human}." if has_car_issue else ""
    ticket = (
        f"{name} needs their child picked up from a facility.{transport_ticket} "
        "They will consider the issue resolved when the child has been successfully picked up."
    )

    return reason, known, ticket


def _gen_hh(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """household: Maintenance needed. Technician scheduling."""
    funds = state.get("agent.finance.available_funds", "plenty")

    openers = [
        "I've got a maintenance issue at home that needs to be taken care of.",
        "Something needs fixing around the house and I need to get a technician out here.",
        "I have a household repair that's been reported and I need to get it sorted out.",
        "There's a maintenance problem at my place and I need help getting it resolved.",
    ]
    reason = _pick(seed, openers)

    known = (
        f"You are {name}. You have a household maintenance issue that has been reported and needs professional attention. "
        f"You have {'sufficient' if funds == 'plenty' else 'limited'} funds available for repairs."
    )

    ticket = (
        f"{name} has a household maintenance issue that needs professional repair. "
        f"They have {'ample' if funds == 'plenty' else 'limited'} budget for the work. "
        "They will consider the issue resolved when a technician has arrived, completed the repair, and the fix has been verified."
    )

    return reason, known, ticket


def _gen_ec(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """errands_and_care: Both errands and dependent care active."""
    car_issue = state.get("agent.transport.car_issue", "none")
    car_issue_human = "flat tire" if car_issue == "flat_tire" else "car trouble"
    has_car = car_issue != "none"
    funds = state.get("agent.finance.available_funds", "plenty")

    openers = [
        f"I've got a lot going on today — my car has a {car_issue_human}, I have an errand to take care of, and my child needs to be picked up.",
        f"My car is out with a {car_issue_human} and I still need to handle an errand and get my kid picked up.",
        f"I'm stuck without a car due to a {car_issue_human}, and I've got both an errand and my child's pickup to deal with.",
        f"Today is a nightmare — {car_issue_human} on my car, an errand that can't wait, and I need someone to grab my kid.",
    ]
    reason = _pick(seed, openers)

    budget_note = ""
    if funds == "tight":
        budget_note = " Your budget is tight, so cost matters."
    elif funds == "broke":
        budget_note = " You're very low on funds right now."

    known = (
        f"You are {name}. Your car has a {car_issue_human} and is not drivable. "
        f"You have a pending errand and your child also needs to be picked up from their facility.{budget_note}"
    )

    ticket = (
        f"{name} has a {car_issue_human} leaving them without transportation. They need an errand completed "
        f"and their child picked up. "
        "They will consider the issue resolved when the errand is confirmed complete and the child has been picked up."
    )

    return reason, known, ticket


def _gen_cch(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """calendar_care_household: Calendar + care + household. Reschedule path."""
    funds = state.get("agent.finance.available_funds", "plenty")

    openers = [
        "I have a calendar conflict, my child needs picking up, and there's a maintenance issue at home — all at the same time.",
        "Everything is piling up today: a meeting conflict, my kid's pickup, and a household repair that needs attention.",
        "I've got three things that all need handling — a scheduling conflict, childcare pickup, and something broken at home.",
        "My day just got complicated: calendar conflict, child pickup, and a home maintenance issue all need to be resolved.",
    ]
    reason = _pick(seed, openers)

    known = (
        f"You are {name}. You have a scheduling conflict on your calendar, your child needs to be picked up from their facility, "
        f"and you have a household maintenance issue that's been reported. "
        f"You have {'sufficient' if funds == 'plenty' else 'limited'} funds available."
    )

    ticket = (
        f"{name} is dealing with three concurrent issues: a calendar conflict that needs rescheduling, "
        f"a child who needs to be picked up, and a household maintenance problem. "
        "They will consider the issue resolved when the meeting is rescheduled, the child has been picked up, "
        "and the home repair has been completed and verified."
    )

    return reason, known, ticket


def _gen_cc(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """cancel_calendar: Calendar must be cancelled (not rescheduled) + bill."""
    funds = state.get("agent.finance.available_funds", "plenty")
    sufficient = state.get("agent.finance.sufficient_funds", "True") == "True"

    openers = [
        "I need to cancel a meeting on my calendar and I also have a bill situation to deal with.",
        "I've got a meeting I need to cancel outright, and there's also a bill that needs handling.",
        "I need to get a meeting taken off my schedule entirely, and I've got a bill due too.",
        "My calendar has a meeting that needs to be cancelled — not rescheduled, cancelled. I also have a bill to sort out.",
    ]
    reason = _pick(seed, openers)

    bill_note = "You have an unpaid bill that is due."
    if sufficient:
        bill_note += f" You have {'sufficient' if funds == 'plenty' else 'enough'} funds available."
    else:
        bill_note += " You do not have enough funds to cover it."

    known = (
        f"You are {name}. You need to cancel a meeting on your calendar — it cannot simply be rescheduled. "
        f"{bill_note}"
    )

    # cc tasks always end with meeting_cancelled + apology_sent + bill deferred
    goal_bill = "deferred"
    for g in goal_state.get("world", []):
        if "bill_status" in g and "paid" in g:
            goal_bill = "paid"

    if goal_bill == "deferred":
        resolved = "the meeting has been cancelled with an apology sent, and the bill has been deferred"
    else:
        resolved = "the meeting has been cancelled with an apology sent, and the bill has been paid"

    ticket = (
        f"{name} needs to cancel a scheduled meeting and handle an outstanding bill. "
        f"They will consider the issue resolved when {resolved}."
    )

    return reason, known, ticket


def _gen_df(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """delivery_failure: Errands where delivery will fail, forcing pickup recovery."""
    car_issue = state.get("agent.transport.car_issue", "none")
    has_car = car_issue != "none"
    car_issue_human = "flat tire" if car_issue == "flat_tire" else "car trouble"
    del_a_avail = state.get("agent.errand_a.delivery_available", "True") == "True"
    del_b_avail = state.get("agent.errand_b.delivery_available", "True") == "True"

    if has_car:
        openers = [
            f"I have a {car_issue_human} and two errands to get done. I'm hoping delivery works but I'm not sure.",
            f"My car is out of commission — {car_issue_human} — and I've got two errands I need to handle today.",
            f"I'm stuck with a {car_issue_human} and have a couple of errands that need to get done one way or another.",
        ]
    else:
        openers = [
            "I've got two errands to handle today. I'm hoping to get them delivered but we'll see.",
            "I need to get a couple of things taken care of today — trying to figure out the best way to handle them.",
            "I have two errands and I'd like to get them sorted. Let's see what the options are.",
        ]
    reason = _pick(seed, openers)

    transport_note = f" Your car has a {car_issue_human} and is not drivable." if has_car else ""
    known = (
        f"You are {name}.{transport_note} "
        f"You have two pending errands that need to be completed today."
    )

    ticket = (
        f"{name} needs two errands completed.{' Their car is unavailable due to a ' + car_issue_human + '.' if has_car else ''} "
        "Delivery may not work for all items, so pickup arrangements may be needed. "
        "They will consider the issue resolved when both errands are confirmed complete."
    )

    return reason, known, ticket


def _gen_dfc(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """delegate_forced_care: Transport broken + rideshare fails, delegate path."""
    car_issue = state.get("agent.transport.car_issue", "flat_tire")
    car_issue_human = "flat tire" if car_issue == "flat_tire" else "car trouble"

    openers = [
        f"My car has a {car_issue_human} and I need my child picked up. I can't drive and I'm worried about getting this sorted out.",
        f"I'm in a tough spot — {car_issue_human} on my car and my kid needs to be picked up. I can't get there myself.",
        f"I can't drive anywhere because of a {car_issue_human}, and my child needs to be picked up from their facility today.",
        f"My car is broken down with a {car_issue_human} and I still need to get my child picked up somehow.",
    ]
    reason = _pick(seed, openers)

    known = (
        f"You are {name}. Your car has a {car_issue_human} and is not drivable. "
        f"Your child needs to be picked up from their facility. "
        f"You need to find a way to get the pickup handled and deal with the car situation."
    )

    ticket = (
        f"{name} has a {car_issue_human} and cannot drive. Their child needs to be picked up. "
        "Rideshare is not a viable option. A delegate will need to handle the pickup, and the car situation needs to be addressed. "
        "They will consider the issue resolved when the child has been picked up and the car repair status has been confirmed."
    )

    return reason, known, ticket


def _gen_cch2(name: str, state: dict, seed: int, goal_state: dict) -> tuple[str, str, str]:
    """cancel_care_household: Cancel meeting + care + household."""
    funds = state.get("agent.finance.available_funds", "plenty")
    bill_active = state.get("agent.finance.bill_active", "False") == "True"

    openers = [
        "I need to cancel a meeting, get my child picked up, and there's a maintenance issue at home too.",
        "Everything is happening at once — I need a meeting cancelled, my kid picked up, and a house repair handled.",
        "I've got a meeting that needs to be cancelled outright, my child's pickup to coordinate, and a home maintenance problem.",
        "My day is packed with problems: a meeting I need to cancel, childcare pickup, and something broken at home.",
    ]
    reason = _pick(seed, openers)

    bill_note = ""
    if bill_active:
        bill_note = f" You also have a bill that needs attention, and your funds are {'sufficient' if funds == 'plenty' else 'limited'}."

    known = (
        f"You are {name}. You need to cancel a meeting on your calendar — it cannot be rescheduled. "
        f"Your child also needs to be picked up from their facility, and you have a household maintenance issue that's been reported.{bill_note}"
    )

    ticket = (
        f"{name} has three issues to resolve: a meeting that must be cancelled (with apology), "
        f"a child who needs to be picked up, and a household maintenance problem requiring professional repair. "
        "They will consider the issue resolved when the meeting is cancelled with an apology sent, "
        "the child has been picked up, and the home repair has been completed and verified."
    )

    return reason, known, ticket


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

GENERATORS = {
    "te": _gen_te,
    "cfp": _gen_cfp,
    "cfd": _gen_cfd,
    "dc": _gen_dc,
    "hh": _gen_hh,
    "ec": _gen_ec,
    "cch": _gen_cch,
    "cc": _gen_cc,
    "df": _gen_df,
    "dfc": _gen_dfc,
    "cch2": _gen_cch2,
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

        prefix = _get_prefix(tid)
        gen = GENERATORS.get(prefix)
        if gen is None:
            print(f"WARNING: no generator for prefix '{prefix}' (task {tid})")
            skipped += 1
            continue

        name = brief["entity_context"]["name"]
        state = _parse_state(brief["start_state_summary"]["world"])
        goal_state = brief.get("goal_state_summary", {})
        seed = _hash_seed(name, tid)

        reason, known, ticket = gen(name, state, seed, goal_state)

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
