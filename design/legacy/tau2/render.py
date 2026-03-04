"""
Render: Convert framework types into tau2-specific task format.

Functions:
- derive_fault_layer_config(): FaultSpace → dict matching recipe engine format
- render_tau2_task(): TaskBlueprint → tau2 Task dict
- derive_entity_builder(): schema + seed_data → entity join function

Produces dicts matching src/tau2/generators/recipe.py interfaces
(FaultAtom, FaultLayer, FaultLayerGroup, FaultLayerConfig).
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

from design.framework.tasks import PerturbationSpec, TaskBlueprint
from design.framework.world import FieldType, WorldSchema
from design.legacy.tau2.faults import (
    FaultDeclaration,
    FaultGroup,
    FaultSpace,
    UnfixableFault,
)


def _snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# ══════════════════════════════════════════════════════════════════════
# FAULT LAYER CONFIG DERIVATION
# ══════════════════════════════════════════════════════════════════════


def derive_fault_layer_config(
    faults: FaultSpace,
    schema: WorldSchema,
    entity_query_fn: Any,
) -> dict:
    """FaultSpace → FaultLayerConfig dict (tau2 recipe engine format).

    Mechanical transformation:
    - FaultDeclaration → FaultAtom (init + fix + check)
    - FaultGroup → FaultLayerGroup
    - UserConfirmation → confirm FaultAtom
    - DiagnosticStep → diagnostic FaultAtom
    - UnfixableFault → FaultLayer(unfixable=True) with preservation assertion
    """
    entity_map = {e.name: e for e in schema.entities}
    groups_out = []

    for group in faults.groups:
        layers = []

        for p in group.perturbations:
            if not isinstance(p, FaultDeclaration):
                continue

            entity_spec = entity_map[p.entity]
            id_field = entity_spec.identity_field
            e_lower = _snake_case(p.entity)

            # Find normal_value
            field_spec = next(
                f for f in entity_spec.fields if f.name == p.field
            )
            normal_value = (
                p.check_value
                if p.check_value is not None
                else field_spec.normal_value
            )
            check_field = p.check_field or p.field

            atoms = []

            # Diagnostics
            if isinstance(group, FaultGroup):
                for diag in group.diagnostics:
                    atoms.append({
                        "init": None,
                        "fix": {
                            "tool_name": diag.tool_name,
                            "args": diag.args,
                            "requestor": "assistant",
                            "compare_args": [],
                        },
                        "check": None,
                        "phase": 0,
                        "step_type": "diagnostic",
                    })

            # Primary: init → fix → check
            atoms.append({
                "init": {
                    "env_type": "assistant",
                    "func_name": f"set_{e_lower}_{p.field}",
                    "args": {
                        id_field: f"{{{id_field}}}",
                        p.field: p.broken_value,
                    },
                },
                "fix": {
                    "tool_name": p.fix_tool,
                    "args": p.fix_args,
                    "requestor": p.fixer,
                    "compare_args": (
                        [id_field] if id_field in p.fix_args else []
                    ),
                },
                "check": {
                    "func_name": f"assert_{e_lower}_{check_field}",
                    "args": {
                        id_field: f"{{{id_field}}}",
                        "expected": normal_value,
                    },
                    "env_type": "assistant",
                    "assert_value": True,
                },
                "phase": 1,
                "step_type": "fix",
            })

            # User confirmation
            if isinstance(group, FaultGroup) and group.user_confirmation:
                conf = group.user_confirmation
                check = None
                if conf.check_func:
                    check = {
                        "func_name": conf.check_func,
                        "args": conf.check_args,
                        "env_type": "user",
                        "assert_value": True,
                    }
                atoms.append({
                    "init": None,
                    "fix": {
                        "tool_name": conf.tool_name,
                        "args": conf.args,
                        "requestor": "user",
                        "compare_args": [],
                    },
                    "check": check,
                    "phase": 2,
                    "step_type": "confirm",
                })

            layers.append({
                "name": p.name,
                "known_info_fragment": p.description,
                "completion_fragment": p.fixed_description,
                "atoms": atoms,
                "predicate_field": p.requires_field,
                "predicate_ne": p.requires_ne,
                "resource_scope": group.resource_scope,
            })

        # Unfixable fault
        if isinstance(group, FaultGroup) and group.unfixable_fault:
            uf = group.unfixable_fault
            entity_spec = entity_map[uf.entity]
            id_field = entity_spec.identity_field
            e_lower = _snake_case(uf.entity)

            uf_atoms = []
            if uf.preservation_check:
                uf_atoms.append({
                    "init": {
                        "env_type": "assistant",
                        "func_name": f"set_{e_lower}_{uf.field}",
                        "args": {
                            id_field: f"{{{id_field}}}",
                            uf.field: uf.broken_value,
                        },
                    },
                    "fix": {
                        "tool_name": "transfer_to_human",
                        "args": {},
                        "requestor": "assistant",
                        "compare_args": [],
                    },
                    "check": {
                        "func_name": f"assert_{e_lower}_{uf.field}",
                        "args": {
                            id_field: f"{{{id_field}}}",
                            "expected": uf.broken_value,
                        },
                        "env_type": "assistant",
                        "assert_value": True,
                    },
                    "phase": 0,
                    "step_type": "fix",
                })

            layers.append({
                "name": uf.name,
                "known_info_fragment": uf.description,
                "completion_fragment": "",
                "atoms": uf_atoms,
                "unfixable": True,
            })

        groups_out.append({
            "name": group.name,
            "layers": layers,
            "resolution_category": group.category,
        })

    return {
        "name": schema.concept.name,
        "groups": groups_out,
        "entity_query": entity_query_fn,
        "min_faults": faults.min_perturbations,
        "max_faults": faults.max_perturbations,
        "max_total_tasks": faults.max_total_tasks,
        "required_groups": faults.required_groups,
        "resolution_instruction": faults.resolution_instruction,
        "tool_grounding_block": faults.tool_grounding_block,
    }


# ══════════════════════════════════════════════════════════════════════
# BLUEPRINT → TAU2 TASK
# ══════════════════════════════════════════════════════════════════════


def render_tau2_task(
    blueprint: TaskBlueprint,
    fault_space: FaultSpace,
    schema: WorldSchema,
) -> dict:
    """Convert a core TaskBlueprint into a tau2 Task dict.

    This is the final rendering step: general blueprint → tau2-specific
    task with init_actions, evaluation_criteria, user_scenario.
    """
    entity = blueprint.entity
    entity_map = {e.name: e for e in schema.entities}

    init_actions = []
    actions = []
    assertions = []

    for p in blueprint.perturbations:
        if not isinstance(p, FaultDeclaration):
            continue

        entity_spec = entity_map[p.entity]
        id_field = entity_spec.identity_field
        e_lower = _snake_case(p.entity)
        field_spec = next(f for f in entity_spec.fields if f.name == p.field)

        # Init: break the field
        init_actions.append({
            "env_type": "assistant",
            "func_name": f"set_{e_lower}_{p.field}",
            "arguments": {
                id_field: entity.get(id_field),
                p.field: p.broken_value,
            },
        })

        # Action: fix the field
        resolved_args = {}
        for k, v in p.fix_args.items():
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                resolved_args[k] = entity.get(v[1:-1], v)
            else:
                resolved_args[k] = v

        actions.append({
            "requestor": p.fixer,
            "name": p.fix_tool,
            "arguments": resolved_args,
            "compare_args": (
                [id_field] if id_field in p.fix_args else []
            ),
        })

        # Assertion: verify the fix
        check_field = p.check_field or p.field
        normal_value = (
            p.check_value
            if p.check_value is not None
            else field_spec.normal_value
        )
        # Resolve template in expected value (e.g., "{correct_points}" → 1200)
        if (
            isinstance(normal_value, str)
            and normal_value.startswith("{")
            and normal_value.endswith("}")
        ):
            normal_value = entity.get(normal_value[1:-1], normal_value)

        assertions.append({
            "func_name": f"assert_{e_lower}_{check_field}",
            "arguments": {
                id_field: entity.get(id_field),
                "expected": normal_value,
            },
            "env_type": "assistant",
            "assert_value": True,
        })

    return {
        "id": blueprint.task_id,
        "initial_state": {"initialization_actions": init_actions},
        "evaluation_criteria": {
            "actions": actions,
            "env_assertions": assertions,
        },
        "description": {"purpose": blueprint.goal_description},
    }


# ══════════════════════════════════════════════════════════════════════
# ENTITY BUILDER
# ══════════════════════════════════════════════════════════════════════


def derive_entity_builder(
    schema: WorldSchema,
) -> Callable[[dict[str, list[dict]]], list[dict[str, Any]]]:
    """Derive an entity join function from the schema.

    Returns a function that takes seed data records and produces
    flattened entity dicts suitable for compose_blueprints().

    The join strategy:
    - Start with the first entity in the schema (root)
    - For each relationship, join the related records
    - For breakable fields, add {correct_X} template values
    """
    root_entity = schema.entities[0]
    root_id = root_entity.identity_field

    # Build relationship map: from_entity → [(to_entity, fk_field)]
    joins: dict[str, list[tuple[str, str]]] = {}
    for rel in schema.relationships:
        joins.setdefault(rel.from_entity, []).append(
            (rel.to_entity, rel.foreign_key)
        )

    # Build breakable field map: entity → [field_specs]
    breakable_fields: dict[str, list] = {}
    for entity in schema.entities:
        bf = [f for f in entity.fields if f.breakable]
        if bf:
            breakable_fields[entity.name] = bf

    def build_entities(records: dict[str, list[dict]]) -> list[dict[str, Any]]:
        root_records = records.get(root_entity.name, [])
        entities = []

        for root_rec in root_records:
            entity = dict(root_rec)
            root_id_val = root_rec.get(root_id)

            # Join related entities
            for to_entity, fk_field in joins.get(root_entity.name, []):
                related = next(
                    (
                        r
                        for r in records.get(to_entity, [])
                        if r.get(fk_field) == root_id_val
                    ),
                    None,
                )
                if related:
                    entity.update(
                        {
                            k: v
                            for k, v in related.items()
                            if k != fk_field
                        }
                    )

                    # Add correct_X values for breakable fields
                    for bf in breakable_fields.get(to_entity, []):
                        if bf.name in related:
                            entity[f"correct_{bf.name}"] = related[bf.name]

            # Add correct_X for root entity breakable fields
            for bf in breakable_fields.get(root_entity.name, []):
                if bf.name in root_rec:
                    entity[f"correct_{bf.name}"] = root_rec[bf.name]

            entities.append(entity)

        return entities

    return build_entities
