"""Runtime sync adapter: run contract sync rules against a live domain DB.

This bridges the kernel's flat-world sync rules (semantics.apply_sync_rules)
with the typed Pydantic DB models used at runtime. Domain environments provide
a field-level read/write interface; this module handles the rest.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from tau2.generators.depgraph.semantics import apply_sync_rules
from tau2.generators.depgraph.types import SyncRuleSpec


class FieldAccessor(Protocol):
    """Read/write interface for one side of the world (agent or user)."""

    def get_field(self, field_name: str) -> Any: ...
    def set_field(self, field_name: str, value: Any) -> None: ...


from tau2.generators.depgraph.semantics import leaf_field_name as _leaf_field_name


def _env_side(path: str) -> str:
    """Return 'agent' or 'user' based on path prefix."""
    if path.startswith("agent."):
        return "agent"
    if path.startswith("user."):
        return "user"
    raise ValueError(f"Unsupported path prefix: '{path}'")


def run_contract_sync(
    sync_rules: list[SyncRuleSpec],
    projection_fields: list[str],
    agent_accessor: FieldAccessor,
    user_accessor: FieldAccessor,
) -> None:
    """Run contract sync rules against live domain state.

    1. Reads current values from the typed DB into a flat world dict.
    2. Runs apply_sync_rules() (kernel fixed-point iteration).
    3. Writes back any changed values to the typed DB.
    """
    if not sync_rules:
        return

    accessors = {"agent": agent_accessor, "user": user_accessor}

    # Step 1: Read current state into flat world
    world: dict[str, Any] = {}
    for path in projection_fields:
        side = _env_side(path)
        field = _leaf_field_name(path)
        try:
            world[path] = accessors[side].get_field(field)
        except (AttributeError, KeyError):
            pass  # Field not readable — skip (e.g. view-only projections)

    # Step 2: Run kernel sync rules to fixed point
    world = apply_sync_rules(sync_rules, world)

    # Step 3: Write back changed values
    for path in projection_fields:
        if path not in world:
            continue
        side = _env_side(path)
        field = _leaf_field_name(path)
        try:
            accessors[side].set_field(field, world[path])
        except (AttributeError, KeyError):
            pass  # Field not writable — skip


class ToolKitFieldAccessor:
    """FieldAccessor backed by a domain ToolKitBase with set_*/get_* methods.

    Falls back to assert_* pattern for reads if no explicit get_* exists.
    This works with the existing domain tool convention where:
      - set_{field}(value) writes the field
      - The field value is readable via a get_{field}() method

    Domains should add simple get_{field}() methods alongside their existing
    set_{field}() methods to support this adapter.
    """

    def __init__(self, toolkit: Any) -> None:
        self.toolkit = toolkit

    def get_field(self, field_name: str) -> Any:
        getter = getattr(self.toolkit, f"get_{field_name}", None)
        if getter is not None:
            return getter()
        raise AttributeError(f"No get_{field_name}() on {type(self.toolkit).__name__}")

    def set_field(self, field_name: str, value: Any) -> None:
        setter = getattr(self.toolkit, f"set_{field_name}", None)
        if setter is not None:
            setter(value)
            return
        raise AttributeError(f"No set_{field_name}() on {type(self.toolkit).__name__}")
