"""
tau2: tau2-specific adapter layer for synthetic task generation.

Layer 2 of the two-layer architecture. Extends framework types with:
- Tau2Concept (archetype, agent/user roles)
- Tool signatures (derived from schema)
- Fault declarations (perturbations + fix semantics)
- Sync bridges (user ↔ agent state)
- Policy (structured rules + prose)
- Rendering (blueprint → tau2 Task format)
- Verification (tool exclusivity, policy coverage)
- Pipeline (10-step authoring process)
"""

from design.legacy.tau2.concept import Archetype, Tau2Concept
from design.legacy.tau2.faults import (
    DiagnosticStep,
    FaultDeclaration,
    FaultGroup,
    FaultSpace,
    UnfixableFault,
    UserConfirmation,
)
from design.legacy.tau2.pipeline import Tau2Pipeline, Tau2PipelineState
from design.legacy.tau2.policy import PolicyRule, PolicySpec
from design.legacy.tau2.render import (
    derive_entity_builder,
    derive_fault_layer_config,
    render_tau2_task,
)
from design.legacy.tau2.sync import SyncBridge, SyncSpec
from design.legacy.tau2.tools import (
    ToolAccess,
    ToolImplSpec,
    ToolParam,
    ToolRole,
    ToolSignatureSpec,
    ToolSuiteSpec,
    derive_tool_signatures,
)
from design.legacy.tau2.verify import verify_fault_space, verify_policy

__all__ = [
    # concept
    "Archetype",
    "Tau2Concept",
    # tools
    "ToolRole",
    "ToolAccess",
    "ToolParam",
    "ToolSignatureSpec",
    "ToolSuiteSpec",
    "ToolImplSpec",
    "derive_tool_signatures",
    # faults
    "FaultDeclaration",
    "UserConfirmation",
    "DiagnosticStep",
    "UnfixableFault",
    "FaultGroup",
    "FaultSpace",
    # sync
    "SyncBridge",
    "SyncSpec",
    # policy
    "PolicyRule",
    "PolicySpec",
    # render
    "derive_fault_layer_config",
    "render_tau2_task",
    "derive_entity_builder",
    # verify
    "verify_fault_space",
    "verify_policy",
    # pipeline
    "Tau2Pipeline",
    "Tau2PipelineState",
]
