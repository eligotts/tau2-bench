"""
Policy: tau2's agent instruction model.

Structured policy rules that can be verified against the tool suite
and fault space. Also carries prose for the full policy document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PolicyRule:
    """One verifiable policy rule.

    Each rule has a condition, an action, and references to
    the tools involved. This allows verification that:
    - All referenced tools exist
    - Every fault group has a resolution path
    - No prescriptive language for selective faults
    """

    condition: str
    action: str
    tools_referenced: list[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class PolicySpec:
    """Agent policy: structured rules + prose.

    The structured rules are for verification.
    The prose is the actual policy document given to the agent.
    """

    structured_rules: list[PolicyRule] = field(default_factory=list)
    prose: str = ""
