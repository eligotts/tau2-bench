"""Deterministically author EV runtime narratives from structural task state."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs
from tau2.generators.depgraph.semantics import materialize_world


def _user_name(task) -> str:
    if task.runtime is None:
        return "the customer"
    for call in task.runtime.initialization_actions:
        if call.env_type == "user" and call.func_name == "set_user_context":
            name = call.arguments.get("name")
            if isinstance(name, str) and name.strip():
                return name
    return "the customer"


def _current_state(task, contract):
    world, issues = materialize_world(task.start_world, sync_rules=contract.sync_rules)
    if issues:
        raise ValueError(f"task '{task.task_id}' has invalid start_world: {issues}")
    return world


def _branch(world: dict[str, object]) -> str:
    return str(world.get("agent.sessions[active_session].error_class", "unknown"))


def _fault(world: dict[str, object]) -> str:
    return str(world.get("agent.sessions[active_session].last_fault_code", "UNKNOWN"))


def _reason_for_call() -> str:
    return (
        "I'm at a public charger and my charging session will not start. The charger is "
        "showing an error and I need help getting the charge going."
    )


def _known_info(name: str, task, world: dict[str, object]) -> str:
    parts = [
        f"You are {name}.",
        "You are at a public charging station with the vehicle plugged in.",
        "You can read the station screen and use the charging app when the assistant asks.",
    ]
    if "screen_fault_code" in task.start_bindings:
        parts.append(f"The station screen currently shows fault code {_fault(world)}.")
    if "app_error_class" in task.start_bindings:
        parts.append(
            f"The charging app is already classifying this as a {_branch(world)} issue."
        )
    return " ".join(parts)


def _ticket(name: str, task, world: dict[str, object]) -> str:
    known_bits: list[str] = []
    if "screen_fault_code" in task.start_bindings:
        known_bits.append(f"The customer already reports station fault code {_fault(world)}.")
    if "app_error_class" in task.start_bindings:
        known_bits.append(
            f"The customer already knows the app-side issue class is {_branch(world)}."
        )
    known_text = f"{' '.join(known_bits)} " if known_bits else ""
    return (
        f"{name} reports that their public EV charging session will not start. "
        f"{known_text}"
        "They will consider the issue resolved when charging starts successfully, the charger "
        "no longer shows an unresolved error, and check_resolution_status confirms the session is recovered."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill EV runtime narratives deterministically")
    parser.add_argument("--graph-contract", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--out-runtime", required=False)
    args = parser.parse_args()

    contract = load_graph_contract(args.graph_contract)
    task_doc = load_task_specs(args.runtime)

    for task in task_doc.tasks:
        if task.runtime is None:
            continue
        world = _current_state(task, contract)
        name = _user_name(task)
        task.runtime.reason_for_call = _reason_for_call()
        task.runtime.known_info = _known_info(name, task, world)
        task.runtime.ticket = _ticket(name, task, world)

    out_path = Path(args.out_runtime or args.runtime)
    out_path.write_text(yaml.safe_dump(task_doc.model_dump(mode="python"), sort_keys=False))
    print(f"[PASS] Authored EV runtime narratives: {out_path}")
    print(f"[INFO] Tasks updated: {len(task_doc.tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
