"""Deterministically author Daily Planner runtime narratives from narrative briefs."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tau2.generators.depgraph.loaders import load_task_specs
from tau2.generators.depgraph.runtime_narrative_checks import load_narrative_briefs


def _problem_phrases(world_entries: list[str]) -> list[str]:
    text = " ".join(world_entries)
    problems: list[str] = []
    if "agent.calendar.conflict_status = 'has_conflict'" in text:
        problems.append("a calendar conflict")
    if "agent.finance.bill_active = True" in text and "agent.finance.bill_status = 'unpaid'" in text:
        problems.append("an unpaid bill due today")
    if "agent.transport.status = 'unavailable'" in text:
        problems.append("a transportation problem")
    if "agent.errand_a.active = True" in text or "agent.errand_b.active = True" in text:
        problems.append("time-sensitive errands")
    if "agent.dependent_care.active = True" in text:
        problems.append("a dependent pickup to coordinate")
    if "agent.household.active = True" in text:
        problems.append("a home repair issue")
    if not problems:
        problems.append("a day-of logistics problem")
    return problems


def _join_phrases(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _binding_facts(bindings: list[dict]) -> list[str]:
    facts: list[str] = []
    for binding in bindings:
        binding_id = str(binding.get("binding_id", ""))
        value = binding.get("value")
        if binding_id == "calendar_state":
            facts.append(f"The conflicting meeting ID is {value}.")
        elif binding_id == "transport_situation":
            facts.append(f"The transportation issue is {value}.")
        elif binding_id == "budget_status":
            facts.append(f"Your current budget status is {value}.")
        elif binding_id == "account_balances":
            funds_text = "True" if bool(value) else "False"
            facts.append(f"The current account balance check says sufficient funds is {funds_text}.")
        elif binding_id == "maintenance_info":
            facts.append(f"The current maintenance status is {value}.")
        elif binding_id == "errand_a_options":
            if isinstance(value, bool):
                facts.append(f"Errand A delivery availability is {value}.")
            else:
                facts.append(f"Errand A is tied to item {value}.")
        elif binding_id == "errand_b_options":
            if isinstance(value, bool):
                facts.append(f"Errand B delivery availability is {value}.")
            else:
                facts.append(f"Errand B is tied to item {value}.")
        elif binding_id == "delegate_a_response":
            facts.append(f"Delegate A response reference is {value}.")
        elif binding_id == "delegate_b_response":
            facts.append(f"Delegate B response reference is {value}.")
        elif binding_id == "delegate_eta":
            facts.append(f"The current delegate ETA is {value} minutes.")
        else:
            facts.append(f"{binding_id} is currently {value}.")
    return facts


def _completion_sentence(cues: list[dict]) -> str:
    clauses: list[str] = []
    for cue in cues:
        reason = str(cue.get("unmet_reason", "")).strip()
        if reason.endswith("."):
            reason = reason[:-1]
        if reason:
            clauses.append(reason.lower())
    if not clauses:
        return "the day plan is back under control"
    if len(clauses) == 1:
        return clauses[0]
    return _join_phrases(clauses)


def _reason_for_call(brief: dict) -> str:
    problems = _problem_phrases(brief["start_state_summary"]["world"])
    return (
        f"I need help sorting out my day. I'm dealing with {_join_phrases(problems)} "
        "and I want a concrete plan to get everything handled."
    )


def _known_info(brief: dict) -> str:
    name = brief["entity_context"]["name"]
    problems = _problem_phrases(brief["start_state_summary"]["world"])
    facts = [
        f"You are {name}.",
        f"Right now you are dealing with {_join_phrases(problems)}.",
    ]
    facts.extend(_binding_facts(brief["start_state_summary"]["bindings"]))
    return " ".join(facts)


def _ticket(brief: dict) -> str:
    name = brief["entity_context"]["name"]
    problems = _problem_phrases(brief["start_state_summary"]["world"])
    completion = _completion_sentence(brief["completion_cues"])
    binding_facts = " ".join(_binding_facts(brief["start_state_summary"]["bindings"]))
    if binding_facts:
        binding_facts = " " + binding_facts
    return (
        f"{name} needs help with {_join_phrases(problems)}.{binding_facts} "
        f"They will consider the issue resolved when {completion}."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fill Daily Planner runtime narratives deterministically"
    )
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--narrative-briefs", required=True)
    parser.add_argument("--out-runtime", required=False)
    args = parser.parse_args()

    task_doc = load_task_specs(args.runtime)
    briefs = load_narrative_briefs(args.narrative_briefs)
    briefs_by_id = {brief["task_id"]: brief for brief in briefs["tasks"]}

    for task in task_doc.tasks:
        if task.runtime is None:
            continue
        brief = briefs_by_id.get(task.task_id)
        if brief is None:
            continue
        task.runtime.reason_for_call = _reason_for_call(brief)
        task.runtime.known_info = _known_info(brief)
        task.runtime.ticket = _ticket(brief)

    out_path = Path(args.out_runtime or args.runtime)
    out_path.write_text(yaml.safe_dump(task_doc.model_dump(mode="python"), sort_keys=False))
    print(f"[PASS] Authored Daily Planner runtime narratives: {out_path}")
    print(f"[INFO] Tasks updated: {len(task_doc.tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
