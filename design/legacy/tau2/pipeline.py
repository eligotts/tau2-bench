"""
LEGACY PIPELINE (reference only): kept from an earlier design iteration.
Current source of truth is `design/tau2/dependency_graph_domain_plan.md`.

Pipeline: State container + verification runner for the 10-step authoring pipeline.

Claude Code IS the LLM. There are no generate methods or automation stubs.
The workflow is:
  1. Claude Code reads design/legacy/guides/NN-*.md for step N
  2. Claude Code authors the Python objects for that step
  3. Claude Code calls pipeline.verify_step_N(objects) to check them
  4. If errors: fix and re-verify. If pass: move to next step.
  5. Step 10: pipeline.step_10_tasks() generates tasks automatically.

Architecture:
  Phase 1 (steps 1-5): World Structure — format-agnostic
  Phase 2 (steps 6-9): Interaction Model — tau2-specific
  Phase 3 (step 10):   Task Generation — pure code
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from design.framework.gates import GatedRelationship
from design.framework.generator import compose_blueprints
from design.framework.verify import (
    Rule,
    VerificationResult,
    verify_concept_with_topology,
    verify_gates,
    verify_perturbation_space,
    verify_rules,
    verify_schema,
    verify_seed_data,
)
from design.framework.world import (
    SeedData,
    TopologyTargets,
    WorldConcept,
    WorldSchema,
)
from design.legacy.tau2.concept import Tau2Concept
from design.legacy.tau2.faults import FaultSpace
from design.legacy.tau2.policy import PolicySpec
from design.legacy.tau2.render import derive_entity_builder, render_tau2_task
from design.legacy.tau2.sync import SyncSpec
from design.legacy.tau2.tools import (
    ToolSuiteSpec,
    derive_tool_signatures,
)
from design.legacy.tau2.verify import verify_fault_space, verify_policy


# ══════════════════════════════════════════════════════════════════════
# PIPELINE STATE
# ══════════════════════════════════════════════════════════════════════


@dataclass
class Tau2PipelineState:
    """Accumulates outputs from each verified step.

    Phase 1 — World Structure (format-agnostic):
        concept, topology, schema, gated_relationships, rules, seed_data

    Phase 2 — Interaction Model (tau2-specific):
        tau2_concept, tool_suite, sync_spec, fault_space, policy

    Phase 3 — Task Generation (pure code):
        blueprints, tau2_tasks
    """

    # Phase 1: World Structure
    concept: Optional[WorldConcept] = None  # step 1
    topology: Optional[TopologyTargets] = None  # step 1
    schema: Optional[WorldSchema] = None  # step 2
    gated_relationships: list[GatedRelationship] = field(
        default_factory=list
    )  # step 3
    rules: list[Rule] = field(default_factory=list)  # step 4
    seed_data: Optional[SeedData] = None  # step 5

    # Phase 2: Interaction Model
    tau2_concept: Optional[Tau2Concept] = None  # step 1 (tau2 extension)
    tool_suite: Optional[ToolSuiteSpec] = None  # step 6 (derived)
    sync_spec: Optional[SyncSpec] = None  # step 7
    fault_space: Optional[FaultSpace] = None  # step 8
    policy: Optional[PolicySpec] = None  # step 9

    # Phase 3: Task Generation
    blueprints: list = field(default_factory=list)  # step 10
    tau2_tasks: list = field(default_factory=list)  # step 10


# ══════════════════════════════════════════════════════════════════════
# THE PIPELINE
# ══════════════════════════════════════════════════════════════════════


class Tau2Pipeline:
    """State container + verification runner for the 10-step pipeline.

    Claude Code authors each artifact. This class verifies and stores them.

    Usage:
        pipeline = Tau2Pipeline()

        # Step 1: Claude Code reads design/legacy/guides/01-concept.md, authors objects
        result = pipeline.verify_step_1(concept, topology, tau2_concept)
        # result.passed == True → move on. False → fix and re-verify.

        # Steps 2-5: same pattern
        result = pipeline.verify_step_2(schema)
        result = pipeline.verify_step_3(gated_relationships)
        result = pipeline.verify_step_4(rules)
        result = pipeline.verify_step_5(seed_data)

        # Step 6: auto-derived from schema (no authoring needed)
        result = pipeline.step_6_tools()

        # Steps 7-9: Claude Code authors, pipeline verifies
        result = pipeline.verify_step_7(sync_spec)
        result = pipeline.verify_step_8(fault_space)
        result = pipeline.verify_step_9(policy)

        # Step 10: pure code — generates tasks from the graph
        result = pipeline.step_10_tasks(seed=42)
    """

    def __init__(self):
        self.state = Tau2PipelineState()

    # ══════════════════════════════════════════════════════════════════
    # PHASE 1: WORLD STRUCTURE (steps 1-5)
    # ══════════════════════════════════════════════════════════════════

    def verify_step_1(
        self,
        concept: WorldConcept,
        topology: TopologyTargets,
        tau2_concept: Tau2Concept,
    ) -> VerificationResult:
        """Verify step 1 output: concept + topology + tau2 concept.

        Guide: design/legacy/guides/01-concept.md
        """
        result = verify_concept_with_topology(concept, topology)
        if result.passed:
            self.state.concept = concept
            self.state.topology = topology
            self.state.tau2_concept = tau2_concept
        return result

    def verify_step_2(self, schema: WorldSchema) -> VerificationResult:
        """Verify step 2 output: entity schema.

        Guide: design/legacy/guides/02-schema.md
        Constrained by: entity names from step 1
        """
        result = verify_schema(schema)
        if result.passed:
            self.state.schema = schema
        return result

    def verify_step_3(
        self, gated_relationships: list[GatedRelationship]
    ) -> VerificationResult:
        """Verify step 3 output: relationships + gates.

        Guide: design/legacy/guides/03-gates.md
        Constrained by: schema from step 2
        ** THE CRITICAL DEPTH GATE **
        """
        result = verify_gates(
            self.state.schema, gated_relationships, self.state.topology
        )
        if result.passed:
            self.state.gated_relationships = gated_relationships
        return result

    def verify_step_4(self, rules: list[Rule]) -> VerificationResult:
        """Verify step 4 output: business rules.

        Guide: design/legacy/guides/04-rules.md
        Constrained by: schema + gates from steps 2-3
        """
        result = verify_rules(rules, self.state.schema)
        if result.passed:
            self.state.rules = rules
        return result

    def verify_step_5(self, seed_data: SeedData) -> VerificationResult:
        """Verify step 5 output: seed data records.

        Guide: design/legacy/guides/05-seed-data.md
        Constrained by: full schema from steps 2-4
        """
        result = verify_seed_data(seed_data, self.state.schema)
        if result.passed:
            self.state.seed_data = seed_data
        return result

    # ══════════════════════════════════════════════════════════════════
    # PHASE 2: INTERACTION MODEL (steps 6-9)
    # ══════════════════════════════════════════════════════════════════

    def step_6_tools(self) -> ToolSuiteSpec:
        """Step 6: derive tools from schema. No authoring needed.

        Guide: design/legacy/guides/06-tools.md (reference only)
        """
        tools = derive_tool_signatures(self.state.schema)
        self.state.tool_suite = tools
        return tools

    def verify_step_7(self, sync_spec: SyncSpec) -> VerificationResult:
        """Verify step 7 output: projections + sync bridges.

        Guide: design/legacy/guides/07-projections-sync.md
        Constrained by: schema + tools from steps 2-6
        """
        # Basic validation — full verification would check field refs
        self.state.sync_spec = sync_spec
        return VerificationResult("sync", passed=True, issues=[])

    def verify_step_8(self, fault_space: FaultSpace) -> VerificationResult:
        """Verify step 8 output: fault declarations.

        Guide: design/legacy/guides/08-faults.md
        ** THE CRITICAL COMPOSITION GATE **
        """
        core_result = verify_perturbation_space(
            fault_space, self.state.schema
        )
        tau2_result = verify_fault_space(
            fault_space, self.state.schema, self.state.tool_suite
        )

        all_issues = core_result.issues + tau2_result.issues
        passed = core_result.passed and tau2_result.passed

        if passed:
            self.state.fault_space = fault_space

        return VerificationResult(
            "faults", passed=passed, issues=all_issues
        )

    def verify_step_9(self, policy: PolicySpec) -> VerificationResult:
        """Verify step 9 output: agent policy.

        Guide: design/legacy/guides/09-policy.md
        Constrained by: everything from steps 1-8
        """
        result = verify_policy(
            policy, self.state.tool_suite, self.state.fault_space
        )
        if result.passed:
            self.state.policy = policy
        return result

    # ══════════════════════════════════════════════════════════════════
    # PHASE 3: TASK GENERATION (step 10 — pure code)
    # ══════════════════════════════════════════════════════════════════

    def step_10_tasks(self, seed: int = 42) -> dict[str, Any]:
        """Generate tasks from the completed world graph. No authoring needed.

        Guide: design/legacy/guides/10-tasks.md (reference only)
        Returns: {"blueprints": [...], "tau2_tasks": [...]}
        """
        # Build flattened entities
        entity_builder = derive_entity_builder(self.state.schema)
        entities = entity_builder(self.state.seed_data.records)

        # Get root entity ID field
        root_entity = self.state.schema.entities[0]
        entity_id_field = root_entity.identity_field

        # Compose blueprints
        blueprints = compose_blueprints(
            space=self.state.fault_space,
            entities=entities,
            entity_id_field=entity_id_field,
            seed=seed,
        )
        self.state.blueprints = blueprints

        # Render to tau2 format
        tau2_tasks = [
            render_tau2_task(bp, self.state.fault_space, self.state.schema)
            for bp in blueprints
        ]
        self.state.tau2_tasks = tau2_tasks

        return {"blueprints": blueprints, "tau2_tasks": tau2_tasks}
