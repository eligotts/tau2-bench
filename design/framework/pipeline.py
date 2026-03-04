"""
Pipeline: Shared types for pipeline state and verification results.

The pipeline is NOT automated. Claude Code reads guides, authors artifacts,
and calls verify methods. This module just provides the shared types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from design.framework.verify import VerificationResult


@dataclass
class StepResult:
    """Result of one pipeline step (for logging/history)."""

    step_name: str
    output: Any
    verification: VerificationResult


@dataclass
class PipelineConfig:
    """Configuration for task generation (the only automated part)."""

    seed: int = 42
