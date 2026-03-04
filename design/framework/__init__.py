"""
Framework: General, format-agnostic types for synthetic task generation.

Layer 1 of the two-layer architecture. Defines:
- World schema (entities, fields, relationships)
- Gates (property, actor, information, compound)
- Tools (format-agnostic operations)
- Tasks (perturbations, blueprints, goal predicates)
- Generator (graph traversal, composition engine)
- Verification (gates between pipeline steps)
- Pipeline (step runner with retry logic)
"""

from design.framework.gates import (
    ActorGate,
    CompoundGate,
    Gate,
    GatedRelationship,
    GateType,
    InformationGate,
    PropertyGate,
)
from design.framework.generator import (
    compose_blueprints,
    compute_gated_depth,
    compute_reachable_nodes,
    generate_graph_tasks,
    verify_solvable,
)
from design.framework.pipeline import PipelineConfig, StepResult
from design.framework.tasks import (
    GoalPredicate,
    PerturbationGroup,
    PerturbationSpace,
    PerturbationSpec,
    TaskAtom,
    TaskAtomType,
    TaskBlueprint,
)
from design.framework.tools import ToolParam, ToolSpec, ToolSuite, ToolType
from design.framework.verify import (
    Rule,
    Severity,
    VerificationIssue,
    VerificationResult,
    verify_blueprint,
    verify_concept,
    verify_concept_with_topology,
    verify_gates,
    verify_perturbation_space,
    verify_rules,
    verify_schema,
    verify_seed_data,
)
from design.framework.world import (
    Cardinality,
    EntitySpec,
    FieldSpec,
    FieldType,
    RelationshipSpec,
    SeedData,
    TopologyTargets,
    WorldConcept,
    WorldSchema,
)

__all__ = [
    # world
    "WorldConcept",
    "TopologyTargets",
    "FieldType",
    "FieldSpec",
    "EntitySpec",
    "Cardinality",
    "RelationshipSpec",
    "WorldSchema",
    "SeedData",
    # gates
    "GateType",
    "PropertyGate",
    "ActorGate",
    "InformationGate",
    "CompoundGate",
    "Gate",
    "GatedRelationship",
    # tools
    "ToolType",
    "ToolParam",
    "ToolSpec",
    "ToolSuite",
    # tasks
    "GoalPredicate",
    "TaskAtomType",
    "TaskAtom",
    "PerturbationSpec",
    "PerturbationGroup",
    "PerturbationSpace",
    "TaskBlueprint",
    # generator
    "compose_blueprints",
    "compute_gated_depth",
    "compute_reachable_nodes",
    "generate_graph_tasks",
    "verify_solvable",
    # verify
    "Severity",
    "VerificationIssue",
    "VerificationResult",
    "Rule",
    "verify_concept",
    "verify_concept_with_topology",
    "verify_schema",
    "verify_gates",
    "verify_rules",
    "verify_seed_data",
    "verify_perturbation_space",
    "verify_blueprint",
    # pipeline
    "StepResult",
    "PipelineConfig",
]
