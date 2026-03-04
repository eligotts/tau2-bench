"""
World: Format-agnostic world schema types.

These types describe what EXISTS in a world — entities, fields,
relationships — without any knowledge of how agents interact with them.

Key addition over the old core.py: TopologyTargets (guides graph
structure generation) and computed/user_visible field flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ══════════════════════════════════════════════════════════════════════
# CONCEPT
# ══════════════════════════════════════════════════════════════════════


@dataclass
class WorldConcept:
    """The seed of a world. Format-agnostic.

    Just: what is this world, and what entity types exist in it?
    How an agent interacts with this world is defined by the rendering layer.
    """

    name: str  # "coffee_shop", "kubernetes_cluster", "git_repo"
    description: str  # 2-3 sentences
    entity_names: list[str]  # ["Customer", "Order", "MenuItem"]


@dataclass
class TopologyTargets:
    """Desired graph topology parameters. Guides steps 2-3.

    These are TARGETS, not hard constraints — the verification gate
    checks whether the authored graph meets them, and if not, the
    step is re-generated.
    """

    min_depth: int = 3  # longest gated path from entry to deepest node
    min_width: int = 4  # minimum breakable fields for perturbation diversity
    gating_density: str = "medium"  # "low" / "medium" / "high"
    branching: str = "moderate"  # "narrow" / "moderate" / "wide"


# ══════════════════════════════════════════════════════════════════════
# FIELD + ENTITY SCHEMA
# ══════════════════════════════════════════════════════════════════════


class FieldType(str, Enum):
    """Supported field types. Intentionally simple — complex types
    are modeled as relationships, not nested fields."""

    STRING = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    ENUM = "enum"
    DATE = "date"
    LIST_STR = "list[str]"


@dataclass
class FieldSpec:
    """One field on an entity.

    The `mutable` and `breakable` flags are the key innovation:
    they tell downstream pipeline steps what's possible WITHOUT
    those steps having been authored yet.

    - mutable=True → the agent can change this field
    - breakable=True → this field can be perturbed for task generation
    - computed=True → derived from other fields (read-only, not in seed data)
    - user_visible=True → included in user projection
    - normal_value / broken_values → defines the perturbation space
    """

    name: str
    type: FieldType
    description: str

    mutable: bool = True
    breakable: bool = False
    computed: bool = False
    user_visible: bool = False
    normal_value: Any = None  # the "correct" state
    broken_values: list[Any] = field(default_factory=list)

    enum_values: list[str] = field(default_factory=list)


@dataclass
class EntitySpec:
    """One entity type in the world."""

    name: str
    description: str
    identity_field: str
    fields: list[FieldSpec]


class Cardinality(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_MANY = "N:M"


@dataclass
class RelationshipSpec:
    """A relationship between two entities (ungated edge)."""

    from_entity: str
    to_entity: str
    cardinality: Cardinality
    foreign_key: str
    description: str


@dataclass
class WorldSchema:
    """Complete world schema. The structural backbone.

    From this, any rendering layer can derive:
    - Its data model (Python classes, SQL tables, file structures, ...)
    - What can break (breakable fields)
    - What the agent can change (mutable fields)
    """

    concept: WorldConcept
    entities: list[EntitySpec]
    relationships: list[RelationshipSpec]


# ══════════════════════════════════════════════════════════════════════
# SEED DATA
# ══════════════════════════════════════════════════════════════════════


@dataclass
class SeedData:
    """Seed data: realistic records conforming to the schema.

    Format-agnostic — just dicts keyed by entity name.
    How this gets loaded (JSON file, DB, in-memory) is up to
    the rendering layer.
    """

    records: dict[str, list[dict[str, Any]]]
    # {"Customer": [{"customer_id": "C001", ...}, ...], ...}

    min_records_per_entity: int = 8
    min_enum_coverage: float = 0.8
