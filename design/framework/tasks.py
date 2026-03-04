"""
Tasks: Format-agnostic task types.

Tasks are composed from perturbation groups and rendered into
format-specific evaluation tasks. This module defines:
- GoalPredicate: mechanically checkable assertion over world state
- TaskAtomType: the four kinds of task challenges
- TaskAtom: one unit of work in a task
- TaskBlueprint: a composed task ready for rendering
- PerturbationSpec/Group/Space: the composition engine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ══════════════════════════════════════════════════════════════════════
# GOAL PREDICATES
# ══════════════════════════════════════════════════════════════════════


@dataclass
class GoalPredicate:
    """A mechanically checkable assertion over world state.

    No LLM judge needed — this is a function over the graph.
    Examples:
      - entity.field == expected_value (property check)
      - entity exists with certain properties (existence check)
      - count(entity where condition) == N (aggregate check)
    """

    entity: str
    field: str
    operator: str = "=="  # "==", "!=", ">", "<", ">=", "<="
    expected_value: Any = None
    description: str = ""


# ══════════════════════════════════════════════════════════════════════
# TASK ATOMS
# ══════════════════════════════════════════════════════════════════════


class TaskAtomType(str, Enum):
    """The four kinds of task challenges."""

    PERTURBATION = "perturbation"  # something is broken, fix it
    CONSTRUCTION = "construction"  # build something that doesn't exist
    QUERY = "query"  # find information in the graph
    TRANSFORMATION = "transformation"  # change state according to rules


@dataclass
class TaskAtom:
    """One unit of work in a task.

    For PERTURBATION: break a field, agent fixes it
    For CONSTRUCTION: agent creates new entity/relationship
    For QUERY: agent discovers information
    For TRANSFORMATION: agent changes state following rules
    """

    atom_type: TaskAtomType
    entity: str
    description: str

    # For PERTURBATION:
    field: Optional[str] = None
    broken_value: Any = None
    fixed_value: Any = None

    # For all types:
    goal: Optional[GoalPredicate] = None
    depth: int = 0  # how many gated hops from entry point


# ══════════════════════════════════════════════════════════════════════
# PERTURBATIONS (the composition engine input)
# ══════════════════════════════════════════════════════════════════════


@dataclass
class PerturbationSpec:
    """One thing that can go wrong in the world.

    This is the GENERAL version — it describes WHAT is broken,
    not HOW to fix it. The rendering layer extends this with
    fix semantics (tool calls, code patches, API requests, etc.).
    """

    name: str
    description: str  # what the problem looks like: "account is suspended"
    fixed_description: str  # what fixed looks like: "account is active"

    # What state is wrong:
    entity: str  # entity type name
    field: str  # field name on that entity
    broken_value: Any  # what it gets set to

    # Check a different field than the one that broke (rare):
    check_field: Optional[str] = None
    check_value: Any = None

    # Conditional: only applies to entities matching this predicate:
    requires_field: Optional[str] = None  # entity must have this truthy
    requires_ne: Optional[tuple[str, Any]] = None  # entity[field] != value


@dataclass
class PerturbationGroup:
    """Mutually exclusive perturbations. Pick 0 or 1 per task.

    Perturbations in the same group touch the same resource.
    The composition engine (cartesian product across groups) ensures
    no two active perturbations conflict.
    """

    name: str
    category: str  # semantic tag for coverage checking
    perturbations: list[PerturbationSpec]
    resource_scope: Optional[str] = None  # "account:{customer_id}"


@dataclass
class PerturbationSpace:
    """Complete perturbation space for a world.

    This is the core composition engine's input. From this, the
    pipeline can generate all valid task combinations.
    """

    groups: list[PerturbationGroup]

    # Composition constraints:
    field_ownership: dict[str, str] = field(default_factory=dict)
    # {"Customer.account_status": "account_group", ...}

    # Task generation parameters:
    min_perturbations: int = 1
    max_perturbations: int = 99
    max_total_tasks: Optional[int] = None
    required_groups: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════
# TASK BLUEPRINT
# ══════════════════════════════════════════════════════════════════════


@dataclass
class TaskBlueprint:
    """A composed task: which entity, which perturbations, what's the goal.

    This is format-agnostic. The rendering layer converts it into
    a format-specific task (tau2 Task, SWE-bench instance, etc.).
    """

    task_id: str
    entity: dict[str, Any]  # flattened entity record from seed data
    perturbations: list[PerturbationSpec]  # what's wrong
    goal_description: str  # composed from fixed_descriptions
    difficulty: int  # derived from perturbation count
    atoms: list[TaskAtom] = field(default_factory=list)
    goals: list[GoalPredicate] = field(default_factory=list)
