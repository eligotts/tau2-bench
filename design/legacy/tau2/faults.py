"""
Faults: tau2-specific fault types extending framework perturbations.

Adds fix semantics (which tool fixes it, with what args, who calls it)
to the format-agnostic PerturbationSpec. Also adds user confirmations,
diagnostic steps, and unfixable faults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from design.framework.tasks import (
    PerturbationGroup,
    PerturbationSpace,
    PerturbationSpec,
)


# ══════════════════════════════════════════════════════════════════════
# FAULT DECLARATION (extends PerturbationSpec with fix semantics)
# ══════════════════════════════════════════════════════════════════════


@dataclass
class FaultDeclaration(PerturbationSpec):
    """tau2-specific: a perturbation with tool-based fix semantics.

    Adds: which tool fixes it, with what args, and who calls it.
    The derivation layer converts this into tau2's FaultAtom
    (InitCall + ActionSpec + AssertionSpec).

    Authoring surface per fault: ~7 lines (vs. ~50 in current system).
    """

    fix_tool: str = ""
    fix_args: dict[str, str] = field(default_factory=dict)
    fixer: str = "agent"  # "agent" or "user"


@dataclass
class UserConfirmation:
    """User action that follows an agent fix (e.g., acknowledge_resolution)."""

    tool_name: str
    args: dict[str, str] = field(default_factory=dict)
    check_func: Optional[str] = None
    check_args: dict[str, str] = field(default_factory=dict)


@dataclass
class DiagnosticStep:
    """READ action the agent must perform before fixing."""

    tool_name: str
    args: dict[str, str] = field(default_factory=dict)
    gate_tier: int = 0


@dataclass
class UnfixableFault:
    """A fault the agent cannot fix — must transfer to human."""

    name: str
    description: str
    entity: str
    field: str
    broken_value: Any
    preservation_check: bool = True


# ══════════════════════════════════════════════════════════════════════
# FAULT GROUP + SPACE (extend framework perturbation types)
# ══════════════════════════════════════════════════════════════════════


@dataclass
class FaultGroup(PerturbationGroup):
    """tau2-specific group: adds user confirmation, diagnostics, unfixable."""

    unfixable_fault: Optional[UnfixableFault] = None
    user_confirmation: Optional[UserConfirmation] = None
    diagnostics: list[DiagnosticStep] = field(default_factory=list)


@dataclass
class FaultSpace(PerturbationSpace):
    """tau2-specific perturbation space: adds tool constraints + user-facing text."""

    # Tool exclusivity across groups:
    tool_ownership: dict[str, str] = field(default_factory=dict)

    # User-facing:
    resolution_instruction: str = ""
    tool_grounding_block: str = ""
