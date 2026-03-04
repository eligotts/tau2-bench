"""
Sync: tau2's two-party state bridge types.

Declares how user actions affect agent state and vice versa.
Replaces hand-written sync_tools() with declarative data
that can be verified statically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SyncBridge:
    """One bridge between user and agent state.

    direction="user_to_agent": user calls a tool, agent state changes
    direction="agent_to_user": agent changes state, user sees the change
    """

    direction: str  # "user_to_agent" or "agent_to_user"

    # user_to_agent:
    user_trigger_field: Optional[str] = None
    agent_entity: Optional[str] = None
    agent_field: Optional[str] = None
    agent_value: Any = None
    condition: Optional[str] = None

    # agent_to_user:
    source_entity: Optional[str] = None
    source_field: Optional[str] = None
    target_field: Optional[str] = None


@dataclass
class SyncSpec:
    """Declarative sync_tools specification.

    A list of bridges that define all state synchronization between
    the user and agent environments.
    """

    bridges: list[SyncBridge] = field(default_factory=list)
