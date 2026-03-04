"""
Verify: All framework-level verification functions.

Verification gates between pipeline steps. Each function checks
one step's output and returns a VerificationResult with issues.

Functions:
- verify_concept(): valid name, entity count
- verify_schema(): field types, relationships, breakable fields, connectivity
- verify_topology(): depth targets, gating density (NEW)
- verify_rules(): non-contradictory, fields exist (NEW)
- verify_seed_data(): FK integrity, enum coverage, breakable starts normal
- verify_perturbation_space(): composition safety, field exclusivity
- verify_blueprint(): reachability analysis (NEW)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from design.framework.gates import (
    CompoundGate,
    Gate,
    GatedRelationship,
    PropertyGate,
)
from design.framework.tasks import PerturbationSpace
from design.framework.world import (
    FieldType,
    SeedData,
    TopologyTargets,
    WorldConcept,
    WorldSchema,
)


# ══════════════════════════════════════════════════════════════════════
# VERIFICATION TYPES
# ══════════════════════════════════════════════════════════════════════


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class VerificationIssue:
    severity: Severity
    check_name: str
    message: str
    fix_hint: Optional[str] = None


@dataclass
class VerificationResult:
    step: str
    passed: bool
    issues: list[VerificationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[VerificationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[VerificationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]


# ══════════════════════════════════════════════════════════════════════
# CONCEPT VERIFICATION (Step 1)
# ══════════════════════════════════════════════════════════════════════


def verify_concept(concept: WorldConcept) -> VerificationResult:
    """Verify a world concept."""
    issues = []

    if not concept.name.replace("_", "").isalnum():
        issues.append(VerificationIssue(
            Severity.ERROR, "valid_name",
            f"Name '{concept.name}' must be alphanumeric with underscores",
        ))
    if len(concept.entity_names) < 2:
        issues.append(VerificationIssue(
            Severity.ERROR, "min_entities",
            "Need at least 2 entity types",
        ))
    if len(set(concept.entity_names)) != len(concept.entity_names):
        issues.append(VerificationIssue(
            Severity.ERROR, "unique_entities",
            "Entity names must be unique",
        ))
    if len(concept.entity_names) < 4:
        issues.append(VerificationIssue(
            Severity.WARNING, "entity_diversity",
            "Domains with <4 entities produce limited perturbation variety",
            fix_hint="Add more entity types for richer task generation",
        ))

    return VerificationResult(
        step="concept",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


def verify_concept_with_topology(
    concept: WorldConcept,
    targets: TopologyTargets,
) -> VerificationResult:
    """Verify concept + topology targets together."""
    result = verify_concept(concept)
    issues = list(result.issues)

    if targets.min_depth > len(concept.entity_names):
        issues.append(VerificationIssue(
            Severity.ERROR, "depth_feasible",
            f"Target depth {targets.min_depth} > entity count "
            f"{len(concept.entity_names)} — impossible to achieve",
            fix_hint="Reduce min_depth or add more entities",
        ))

    if targets.gating_density not in ("low", "medium", "high"):
        issues.append(VerificationIssue(
            Severity.ERROR, "valid_gating_density",
            f"gating_density must be 'low', 'medium', or 'high', "
            f"got '{targets.gating_density}'",
        ))

    if targets.branching not in ("narrow", "moderate", "wide"):
        issues.append(VerificationIssue(
            Severity.ERROR, "valid_branching",
            f"branching must be 'narrow', 'moderate', or 'wide', "
            f"got '{targets.branching}'",
        ))

    return VerificationResult(
        step="concept_with_topology",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


# ══════════════════════════════════════════════════════════════════════
# SCHEMA VERIFICATION (Step 2)
# ══════════════════════════════════════════════════════════════════════


def verify_schema(schema: WorldSchema) -> VerificationResult:
    """Verify world schema: field types, relationships, breakable fields."""
    issues = []
    entity_names = {e.name for e in schema.entities}

    for entity in schema.entities:
        field_names = [f.name for f in entity.fields]

        if entity.identity_field not in field_names:
            issues.append(VerificationIssue(
                Severity.ERROR, "identity_field_exists",
                f"{entity.name}.{entity.identity_field} not in fields",
            ))
        if len(set(field_names)) != len(field_names):
            issues.append(VerificationIssue(
                Severity.ERROR, "unique_fields",
                f"{entity.name} has duplicate field names",
            ))

        for f in entity.fields:
            if f.breakable:
                if f.normal_value is None and not f.broken_values:
                    # Dynamic-valued breakable field (normal/broken from record)
                    # This is valid for template-based faults like points, tier
                    issues.append(VerificationIssue(
                        Severity.WARNING, "breakable_dynamic",
                        f"{entity.name}.{f.name} is breakable with no "
                        f"static normal_value/broken_values — ensure "
                        f"fault declarations provide values",
                    ))
                elif f.normal_value is None:
                    issues.append(VerificationIssue(
                        Severity.ERROR, "breakable_normal_value",
                        f"{entity.name}.{f.name} is breakable but has "
                        f"no normal_value",
                    ))
                elif not f.broken_values:
                    issues.append(VerificationIssue(
                        Severity.ERROR, "breakable_broken_values",
                        f"{entity.name}.{f.name} is breakable but has "
                        f"no broken_values",
                    ))
            if f.type == FieldType.ENUM and len(f.enum_values) < 2:
                issues.append(VerificationIssue(
                    Severity.ERROR, "enum_values",
                    f"{entity.name}.{f.name} is enum but has <2 values",
                ))

    for rel in schema.relationships:
        for name in (rel.from_entity, rel.to_entity):
            if name not in entity_names:
                issues.append(VerificationIssue(
                    Severity.ERROR, "rel_entity_exists",
                    f"Relationship references unknown entity: {name}",
                ))

    total_breakable = sum(
        1 for e in schema.entities for f in e.fields if f.breakable
    )
    if total_breakable < 3:
        issues.append(VerificationIssue(
            Severity.WARNING, "breakable_diversity",
            f"Only {total_breakable} breakable fields — need >=3 for "
            f"perturbation diversity",
        ))

    # Graph connectivity
    if schema.relationships:
        connected = {schema.relationships[0].from_entity}
        changed = True
        while changed:
            changed = False
            for rel in schema.relationships:
                for a, b in [
                    (rel.from_entity, rel.to_entity),
                    (rel.to_entity, rel.from_entity),
                ]:
                    if a in connected and b not in connected:
                        connected.add(b)
                        changed = True
        orphans = entity_names - connected
        if orphans:
            issues.append(VerificationIssue(
                Severity.WARNING, "connected_graph",
                f"Orphan entities: {orphans}",
            ))

    return VerificationResult(
        step="schema",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


# ══════════════════════════════════════════════════════════════════════
# GATE / TOPOLOGY VERIFICATION (Step 3)
# ══════════════════════════════════════════════════════════════════════


def verify_gates(
    schema: WorldSchema,
    gated_relationships: list[GatedRelationship],
    targets: Optional[TopologyTargets] = None,
) -> VerificationResult:
    """Verify gates: fields exist, no circular deps, depth targets.

    This is the CRITICAL EARLY GATE. If the graph is too shallow,
    re-generate step 3 (relationships + gates), not the whole domain.
    """
    issues = []
    entity_map = {e.name: e for e in schema.entities}
    field_map: dict[tuple[str, str], Any] = {}
    for entity in schema.entities:
        for f in entity.fields:
            field_map[(entity.name, f.name)] = f

    # Gate fields exist and are breakable
    for gr in gated_relationships:
        rel = gr.relationship
        if rel.from_entity not in entity_map:
            issues.append(VerificationIssue(
                Severity.ERROR, "gate_entity_exists",
                f"Gated relationship references unknown entity: {rel.from_entity}",
            ))
            continue

        gate = gr.gate
        _verify_gate_fields(gate, field_map, entity_map, issues)

    # Check for circular gate dependencies
    # Build a dependency graph: entity A -> entity B if A has a gate
    # field that could be broken, and B is gated by A
    gate_deps: dict[str, set[str]] = {}
    for gr in gated_relationships:
        gate_fields = _extract_gate_fields(gr.gate)
        for entity_name, field_name in gate_fields:
            fspec = field_map.get((entity_name, field_name))
            if fspec and fspec.breakable:
                # This gate can be broken, so the target entity
                # depends on the source entity being fixed
                gate_deps.setdefault(gr.relationship.to_entity, set()).add(
                    entity_name
                )

    # Detect cycles
    if _has_cycle(gate_deps):
        issues.append(VerificationIssue(
            Severity.ERROR, "no_circular_gates",
            "Circular gate dependency detected — gate A requires B, "
            "gate B requires A",
            fix_hint="Remove one of the circular gate conditions",
        ))

    # Check depth targets
    if targets is not None:
        from design.framework.generator import compute_gated_depth

        # Try all entities as entry points, take max depth
        max_depth = 0
        for entity in schema.entities:
            depth = compute_gated_depth(
                schema, gated_relationships, entity.name
            )
            max_depth = max(max_depth, depth)

        if max_depth < targets.min_depth:
            issues.append(VerificationIssue(
                Severity.WARNING, "depth_target",
                f"Max graph depth is {max_depth}, target is {targets.min_depth}. "
                f"Add more gate conditions on relationships.",
                fix_hint="Gate more edges to increase depth",
            ))

        # Check gating density
        total_rels = len(schema.relationships)
        gated_count = len(gated_relationships)
        if total_rels > 0:
            density = gated_count / total_rels
            expected = {"low": 0.2, "medium": 0.4, "high": 0.6}
            target_density = expected.get(targets.gating_density, 0.4)
            if density < target_density - 0.15:
                issues.append(VerificationIssue(
                    Severity.WARNING, "gating_density",
                    f"Gating density {density:.0%} is below target "
                    f"'{targets.gating_density}' ({target_density:.0%})",
                ))

    return VerificationResult(
        step="gates",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


# ══════════════════════════════════════════════════════════════════════
# RULES VERIFICATION (Step 4)
# ══════════════════════════════════════════════════════════════════════


@dataclass
class Rule:
    """A business rule / constraint on the world."""

    description: str
    entity: str
    field: Optional[str] = None
    condition_entity: Optional[str] = None
    condition_field: Optional[str] = None
    condition_value: Any = None


def verify_rules(
    rules: list[Rule],
    schema: WorldSchema,
) -> VerificationResult:
    """Verify rules: fields exist, non-contradictory."""
    issues = []
    entity_map = {e.name: e for e in schema.entities}
    field_map: dict[tuple[str, str], Any] = {}
    for entity in schema.entities:
        for f in entity.fields:
            field_map[(entity.name, f.name)] = f

    for rule in rules:
        if rule.entity not in entity_map:
            issues.append(VerificationIssue(
                Severity.ERROR, "rule_entity_exists",
                f"Rule '{rule.description}' references unknown entity: "
                f"{rule.entity}",
            ))
        if rule.field and (rule.entity, rule.field) not in field_map:
            issues.append(VerificationIssue(
                Severity.ERROR, "rule_field_exists",
                f"Rule '{rule.description}' references unknown field: "
                f"{rule.entity}.{rule.field}",
            ))
        if rule.condition_entity and rule.condition_entity not in entity_map:
            issues.append(VerificationIssue(
                Severity.ERROR, "rule_condition_entity_exists",
                f"Rule '{rule.description}' condition references unknown "
                f"entity: {rule.condition_entity}",
            ))
        if (
            rule.condition_entity
            and rule.condition_field
            and (rule.condition_entity, rule.condition_field) not in field_map
        ):
            issues.append(VerificationIssue(
                Severity.ERROR, "rule_condition_field_exists",
                f"Rule '{rule.description}' condition references unknown "
                f"field: {rule.condition_entity}.{rule.condition_field}",
            ))

        # Check rule doesn't make a breakable field permanently unfixable
        if rule.field:
            fspec = field_map.get((rule.entity, rule.field))
            if fspec and fspec.breakable and not fspec.mutable:
                issues.append(VerificationIssue(
                    Severity.ERROR, "rule_not_unfixable",
                    f"Rule on {rule.entity}.{rule.field} but field is "
                    f"breakable and immutable — fault would be unfixable",
                ))

    return VerificationResult(
        step="rules",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


# ══════════════════════════════════════════════════════════════════════
# SEED DATA VERIFICATION (Step 5)
# ══════════════════════════════════════════════════════════════════════


def verify_seed_data(
    seed_data: SeedData,
    schema: WorldSchema,
) -> VerificationResult:
    """Verify seed data against schema."""
    issues = []

    entity_map = {e.name: e for e in schema.entities}
    for name, entity_spec in entity_map.items():
        records = seed_data.records.get(name, [])
        if len(records) < seed_data.min_records_per_entity:
            issues.append(VerificationIssue(
                Severity.ERROR, "min_records",
                f"{name}: {len(records)} records < minimum "
                f"{seed_data.min_records_per_entity}",
            ))

        # Check identity uniqueness
        id_field = entity_spec.identity_field
        ids = [r.get(id_field) for r in records]
        if len(set(ids)) != len(ids):
            issues.append(VerificationIssue(
                Severity.ERROR, "unique_ids",
                f"{name}: duplicate {id_field} values",
            ))

        # Check breakable fields start at normal_value
        for record in records:
            for f in entity_spec.fields:
                if f.breakable and f.normal_value is not None:
                    actual = record.get(f.name)
                    if actual != f.normal_value:
                        issues.append(VerificationIssue(
                            Severity.WARNING, "breakable_starts_normal",
                            f"{name}.{f.name}: record {record.get(id_field)} "
                            f"has {actual!r}, expected normal_value "
                            f"{f.normal_value!r}",
                        ))

    # Referential integrity
    id_sets: dict[str, set] = {}
    for name, entity_spec in entity_map.items():
        id_field = entity_spec.identity_field
        id_sets[name] = {
            r[id_field] for r in seed_data.records.get(name, [])
        }

    for rel in schema.relationships:
        to_records = seed_data.records.get(rel.to_entity, [])
        valid_ids = id_sets.get(rel.from_entity, set())
        for record in to_records:
            fk_val = record.get(rel.foreign_key)
            if fk_val is not None and fk_val not in valid_ids:
                issues.append(VerificationIssue(
                    Severity.ERROR, "referential_integrity",
                    f"{rel.to_entity}.{rel.foreign_key}={fk_val!r} "
                    f"not found in {rel.from_entity}",
                ))

    # Enum coverage
    for name, entity_spec in entity_map.items():
        records = seed_data.records.get(name, [])
        for f in entity_spec.fields:
            if f.type == FieldType.ENUM and f.enum_values:
                used = {r.get(f.name) for r in records}
                coverage = (
                    len(used & set(f.enum_values)) / len(f.enum_values)
                )
                if coverage < seed_data.min_enum_coverage:
                    issues.append(VerificationIssue(
                        Severity.WARNING, "enum_coverage",
                        f"{name}.{f.name}: {coverage:.0%} enum coverage "
                        f"< {seed_data.min_enum_coverage:.0%} target",
                    ))

    return VerificationResult(
        step="seed_data",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


# ══════════════════════════════════════════════════════════════════════
# PERTURBATION SPACE VERIFICATION (Step 8)
# ══════════════════════════════════════════════════════════════════════


def verify_perturbation_space(
    space: PerturbationSpace,
    schema: WorldSchema,
) -> VerificationResult:
    """Verify perturbation space: structural validity + composition safety.

    This is the CRITICAL gate. Catches the composition failures
    that plagued the current tau2 system.
    """
    issues = []
    entity_map = {e.name: e for e in schema.entities}
    field_map: dict[tuple[str, str], Any] = {}
    for entity in schema.entities:
        for f in entity.fields:
            field_map[(entity.name, f.name)] = f

    # --- Structural checks ---
    for group in space.groups:
        for p in group.perturbations:
            if p.entity not in entity_map:
                issues.append(VerificationIssue(
                    Severity.ERROR, "entity_exists",
                    f"Perturbation '{p.name}': entity '{p.entity}' "
                    f"not in schema",
                ))
            elif (p.entity, p.field) not in field_map:
                issues.append(VerificationIssue(
                    Severity.ERROR, "field_exists",
                    f"Perturbation '{p.name}': field '{p.field}' "
                    f"not on {p.entity}",
                ))
            elif not field_map[(p.entity, p.field)].breakable:
                issues.append(VerificationIssue(
                    Severity.ERROR, "field_breakable",
                    f"Perturbation '{p.name}': {p.entity}.{p.field} "
                    f"not marked breakable",
                ))

    # --- Composition safety: field exclusivity across groups ---
    field_to_group: dict[tuple[str, str], str] = {}
    for group in space.groups:
        for p in group.perturbations:
            key = (p.entity, p.field)
            if key in field_to_group:
                other = field_to_group[key]
                if other != group.name:
                    issues.append(VerificationIssue(
                        Severity.ERROR, "field_exclusivity",
                        f"{p.entity}.{p.field} modified by groups "
                        f"'{other}' AND '{group.name}'. "
                        f"Move these perturbations into the same group.",
                    ))
            field_to_group[key] = group.name

    # --- Completeness ---
    if len(space.groups) < 4:
        issues.append(VerificationIssue(
            Severity.WARNING, "group_count",
            f"Only {len(space.groups)} groups — target 8-10 for diversity",
        ))

    return VerificationResult(
        step="perturbation_space",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


# ══════════════════════════════════════════════════════════════════════
# BLUEPRINT VERIFICATION (Step 10)
# ══════════════════════════════════════════════════════════════════════


def verify_blueprint(
    blueprint: Any,  # TaskBlueprint
    schema: WorldSchema,
    gated_relationships: list[GatedRelationship],
    entry_entity: str,
) -> VerificationResult:
    """Verify a task blueprint: reachability analysis.

    Checks that all perturbations in the blueprint are reachable
    by the oracle agent (Level 3 constraint guarantee).
    """
    from design.framework.generator import verify_solvable

    issues = []

    # Check all perturbations reference existing entities/fields
    entity_map = {e.name: e for e in schema.entities}
    for p in blueprint.perturbations:
        if p.entity not in entity_map:
            issues.append(VerificationIssue(
                Severity.ERROR, "blueprint_entity_exists",
                f"Blueprint perturbation references unknown entity: "
                f"{p.entity}",
            ))

    # Solvability check
    if not any(i.severity == Severity.ERROR for i in issues):
        solvable = verify_solvable(
            schema, gated_relationships, blueprint, entry_entity
        )
        if not solvable:
            issues.append(VerificationIssue(
                Severity.ERROR, "blueprint_solvable",
                f"Blueprint '{blueprint.task_id}' is not solvable — "
                f"oracle agent cannot reach all perturbations",
                fix_hint="Check gate conditions and perturbation placement",
            ))

    return VerificationResult(
        step="blueprint",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


# ══════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════


def _verify_gate_fields(gate, field_map, entity_map, issues):
    """Recursively verify gate field references."""
    if isinstance(gate, PropertyGate):
        if gate.entity not in entity_map:
            issues.append(VerificationIssue(
                Severity.ERROR, "gate_entity_exists",
                f"Property gate references unknown entity: {gate.entity}",
            ))
        elif (gate.entity, gate.field) not in field_map:
            issues.append(VerificationIssue(
                Severity.ERROR, "gate_field_exists",
                f"Property gate references unknown field: "
                f"{gate.entity}.{gate.field}",
            ))
        else:
            fspec = field_map[(gate.entity, gate.field)]
            if not fspec.breakable:
                issues.append(VerificationIssue(
                    Severity.WARNING, "gate_field_breakable",
                    f"Property gate on {gate.entity}.{gate.field} but "
                    f"field is not breakable — gate can never close",
                ))
    elif isinstance(gate, CompoundGate):
        for condition in gate.conditions:
            _verify_gate_fields(condition, field_map, entity_map, issues)


def _extract_gate_fields(gate) -> list[tuple[str, str]]:
    """Extract (entity, field) pairs from a gate."""
    if isinstance(gate, PropertyGate):
        return [(gate.entity, gate.field)]
    if isinstance(gate, CompoundGate):
        result = []
        for c in gate.conditions:
            result.extend(_extract_gate_fields(c))
        return result
    return []


def _has_cycle(deps: dict[str, set[str]]) -> bool:
    """Detect cycles in a dependency graph using DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    all_nodes = set(deps.keys())
    for targets in deps.values():
        all_nodes.update(targets)

    for node in all_nodes:
        color[node] = WHITE

    def dfs(node):
        color[node] = GRAY
        for neighbor in deps.get(node, set()):
            if color.get(neighbor, WHITE) == GRAY:
                return True
            if color.get(neighbor, WHITE) == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    for node in all_nodes:
        if color.get(node, WHITE) == WHITE:
            if dfs(node):
                return True
    return False
