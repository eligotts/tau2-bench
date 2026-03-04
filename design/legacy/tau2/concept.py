"""
Concept: tau2-specific domain concept types.

Extends the format-agnostic WorldConcept with tau2's two-party
interaction model (agent + user simulator).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Archetype(str, Enum):
    """Domain interaction pattern. Determines tool generation strategy."""

    DIAGNOSTIC = "diagnostic"  # Sequential info-hiding (auto_repair, library)
    TROUBLESHOOT = "troubleshoot"  # Branching with user actions (tech_support)
    TRANSACTION = "transaction"  # Transparent state + guarded writes (shopping)
    TRIAGE = "triage"  # Classify + route (wellness helpline)


@dataclass
class Tau2Concept:
    """tau2-specific concept: adds the two-party interaction model.

    This supplements the format-agnostic WorldConcept with information
    about how agents and users interact in this domain.
    """

    archetype: Archetype
    agent_role: str  # "customer support agent"
    user_role: str  # "customer"
    agent_purpose: str  # "resolve order issues, manage accounts, ..."
