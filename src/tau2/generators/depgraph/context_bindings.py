"""Deterministic concrete context binding generation for sampled tasks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from tau2.generators.depgraph.types import EnvFunctionCallSpec, GraphContractSpec, TaskSpecsDoc


class TaskContextBindingSpec(BaseModel):
    """Concrete entity-slot binding plus per-task context init actions."""

    task_id: str
    slots: dict[str, str] = Field(default_factory=dict)
    initialization_actions: list[EnvFunctionCallSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_binding(self) -> "TaskContextBindingSpec":
        if not self.task_id.strip():
            raise ValueError("task_id cannot be empty")
        for key, value in self.slots.items():
            if not key.strip():
                raise ValueError(f"task '{self.task_id}' has blank slot key")
            if not value.strip():
                raise ValueError(f"task '{self.task_id}' has blank slot value for '{key}'")
        return self


class TaskContextBindingsDoc(BaseModel):
    """Top-level context-binding document."""

    version: int = 1
    domain: str
    strategy: str = "task_id_hash_mod_candidates"
    tasks: list[TaskContextBindingSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_doc(self) -> "TaskContextBindingsDoc":
        if self.version != 1:
            raise ValueError(f"Unsupported task context bindings version: {self.version}")
        if not self.domain.strip():
            raise ValueError("task context bindings domain cannot be empty")
        task_ids = [entry.task_id for entry in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Duplicate task_id values in task context bindings")
        return self


def load_task_context_bindings(path: str | Path) -> TaskContextBindingsDoc:
    """Load and validate task context bindings YAML."""
    payload = yaml.safe_load(Path(path).read_text())
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML object at root for {path}")
    return TaskContextBindingsDoc.model_validate(payload)


def dump_task_context_bindings(doc: TaskContextBindingsDoc, out_path: str | Path) -> None:
    """Write context bindings to YAML."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc.model_dump(mode="python"), sort_keys=False))


def _stable_index(task_id: str, modulo: int) -> int:
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _derive_user_id(account_id: str) -> str:
    digits = "".join(ch for ch in account_id if ch.isdigit())
    if digits:
        return f"U{digits}"
    return f"U_{account_id}"


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at root for {path}")
    return payload


def generate_cloud_ir_context_bindings(
    *,
    sampled: TaskSpecsDoc,
    contract: GraphContractSpec,
    db_json_path: str | Path,
    domain: str = "cloud_incident_response",
) -> TaskContextBindingsDoc:
    """Generate deterministic context bindings for cloud incident response.

    This domain has exactly one entity per type, so every task binds to the same
    set of entity IDs. The user context sets the on-call engineer identity.
    """
    expected_slots = {
        "active_incident", "active_app", "active_db", "active_cache",
        "active_auth", "active_lb", "active_queue", "active_dns",
    }
    contract_slots = {slot.slot_id for slot in contract.context_slots}
    if contract_slots != expected_slots:
        raise ValueError(
            "Cloud IR context binding generator expects context slots "
            f"{sorted(expected_slots)}, got {sorted(contract_slots)}"
        )

    db = _load_json_object(db_json_path)

    # Extract single entity IDs
    incident_id = db["incidents"][0]["incident_id"]
    app_id = db["app_services"][0]["service_id"]
    db_id = db["databases"][0]["db_id"]
    cache_id = db["caches"][0]["cache_id"]
    auth_id = db["auth_services"][0]["auth_id"]
    lb_id = db["load_balancers"][0]["lb_id"]
    queue_id = db["queues"][0]["queue_id"]
    dns_id = db["dns_records"][0]["dns_id"]

    slots = {
        "active_incident": incident_id,
        "active_app": app_id,
        "active_db": db_id,
        "active_cache": cache_id,
        "active_auth": auth_id,
        "active_lb": lb_id,
        "active_queue": queue_id,
        "active_dns": dns_id,
    }

    # Names for personas (deterministic assignment via hash)
    oncall_names = [
        "Alex Chen", "Sam Rivera", "Jordan Patel", "Morgan Kim",
        "Casey O'Brien", "Riley Zhang", "Drew Nakamura", "Jamie Santos",
    ]

    task_entries: list[TaskContextBindingSpec] = []
    for task in sampled.tasks:
        idx = _stable_index(task.task_id, len(oncall_names))
        name = oncall_names[idx]
        user_id = f"U{idx + 1001}"

        task_entries.append(
            TaskContextBindingSpec(
                task_id=task.task_id,
                slots=dict(slots),
                initialization_actions=[
                    EnvFunctionCallSpec(
                        env_type="user",
                        func_name="set_user_context",
                        arguments={
                            "user_id": user_id,
                            "name": name,
                            "incident_id": incident_id,
                            "oncall_role": "on-call engineer",
                        },
                    )
                ],
            )
        )

    return TaskContextBindingsDoc(
        version=1,
        domain=domain,
        strategy="single_entity_set_with_persona_rotation",
        tasks=task_entries,
    )


def generate_ev_context_bindings(
    *,
    sampled: TaskSpecsDoc,
    contract: GraphContractSpec,
    db_json_path: str | Path,
    domain: str = "ev_charging_support",
) -> TaskContextBindingsDoc:
    """Generate deterministic context bindings for EV charging support."""
    expected_slots = {"active_account", "active_station", "active_session"}
    contract_slots = {slot.slot_id for slot in contract.context_slots}
    if contract_slots != expected_slots:
        raise ValueError(
            "EV context binding generator expects context slots "
            f"{sorted(expected_slots)}, got {sorted(contract_slots)}"
        )

    db = _load_json_object(db_json_path)
    accounts = db.get("accounts")
    stations = db.get("stations")
    sessions = db.get("sessions")
    network_paths = db.get("network_paths")
    if not isinstance(accounts, list) or not isinstance(stations, list) or not isinstance(
        sessions, list
    ):
        raise ValueError(
            "EV db.json must include list fields: accounts, stations, sessions"
        )

    account_by_id: dict[str, dict[str, Any]] = {}
    for account in accounts:
        if not isinstance(account, dict):
            continue
        account_id = account.get("account_id")
        if isinstance(account_id, str) and account_id.strip():
            account_by_id[account_id] = account

    station_ids = {
        station.get("station_id")
        for station in stations
        if isinstance(station, dict) and isinstance(station.get("station_id"), str)
    }
    network_station_ids = {
        path.get("station_id")
        for path in (network_paths or [])
        if isinstance(path, dict) and isinstance(path.get("station_id"), str)
    }

    candidates: list[TaskContextBindingSpec] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        session_id = session.get("session_id")
        account_id = session.get("account_id")
        station_id = session.get("station_id")
        if not (
            isinstance(session_id, str)
            and isinstance(account_id, str)
            and isinstance(station_id, str)
        ):
            continue
        account = account_by_id.get(account_id)
        if account is None:
            continue
        if station_id not in station_ids:
            continue
        if network_station_ids and station_id not in network_station_ids:
            continue

        customer_name = account.get("customer_name")
        if not isinstance(customer_name, str) or not customer_name.strip():
            customer_name = f"Customer {account_id}"
        user_id = _derive_user_id(account_id)

        candidates.append(
            TaskContextBindingSpec(
                task_id=f"candidate:{session_id}",
                slots={
                    "active_account": account_id,
                    "active_station": station_id,
                    "active_session": session_id,
                },
                initialization_actions=[
                    EnvFunctionCallSpec(
                        env_type="user",
                        func_name="set_user_context",
                        arguments={
                            "user_id": user_id,
                            "name": customer_name,
                            "account_id": account_id,
                            "station_id": station_id,
                            "session_id": session_id,
                        },
                    )
                ],
            )
        )

    if not candidates:
        raise ValueError("No valid EV context candidates found from db.json")

    task_entries: list[TaskContextBindingSpec] = []
    for task in sampled.tasks:
        idx = _stable_index(task.task_id, len(candidates))
        candidate = candidates[idx]
        task_entries.append(
            TaskContextBindingSpec(
                task_id=task.task_id,
                slots=dict(candidate.slots),
                initialization_actions=[
                    call.model_copy(deep=True) for call in candidate.initialization_actions
                ],
            )
        )

    return TaskContextBindingsDoc(
        version=1,
        domain=domain,
        strategy="task_id_hash_mod_candidates",
        tasks=task_entries,
    )

