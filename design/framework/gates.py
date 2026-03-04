"""
Gates: First-class gate types for controlling graph traversal.

Gates are conditions on edges in the entity graph. They control
what information the agent can access based on the current state
of the world.

Four gate types:
- PropertyGate: field on source node must have specific value
- ActorGate: requires action from user/external system
- InformationGate: requires actor to HAVE knowledge
- CompoundGate: multiple conditions (AND)

Gates create task depth: a broken gate field hides everything
downstream of the gated edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

from design.framework.world import RelationshipSpec


class GateType(str, Enum):
    """Types of graph traversal gates."""

    PROPERTY = "property"  # field value controls traversal
    ACTOR = "actor"  # requires action from specific actor
    INFORMATION = "information"  # requires knowledge, not state change
    COMPOUND = "compound"  # multiple conditions (AND)


@dataclass
class PropertyGate:
    """A field on the source node must have a specific value.

    Example: Customer.account_status == "active" to traverse
    Customer → Order edge.

    If the field is breakable and gets set to a broken_value,
    this gate CLOSES, hiding everything downstream.
    """

    gate_type: str = "property"
    entity: str = ""  # source entity
    field: str = ""  # field name on source entity
    required_value: Any = None  # value needed to traverse


@dataclass
class ActorGate:
    """Requires action from a specific actor (user, external system).

    Example: User.identity_verified == true to access account details.
    The agent must ask the user to call verify_identity(), which sets
    the field to true, opening the gate.
    """

    gate_type: str = "actor"
    actor: str = ""  # "user" or external system name
    field: str = ""  # field on the actor's state
    required_value: Any = True  # value needed to traverse
    trigger_tool: Optional[str] = None  # tool the actor calls to satisfy gate


@dataclass
class InformationGate:
    """Requires the traversing actor to HAVE certain information.

    Example: agent must know Customer.plan_type before they can
    correctly update Subscription. The agent doesn't change state —
    they need to have looked up a value from another node first.
    """

    gate_type: str = "information"
    source_entity: str = ""  # where the info lives
    source_field: str = ""  # which field holds the info
    description: str = ""  # what the agent needs to know


@dataclass
class CompoundGate:
    """Multiple conditions that must ALL be satisfied (AND).

    Example: Customer.account_status == "active"
    AND User.identity_verified == true
    AND agent.knows(Customer.plan_type)
    """

    gate_type: str = "compound"
    conditions: list[Union[PropertyGate, ActorGate, InformationGate]] = field(
        default_factory=list
    )


# Union type for any gate
Gate = Union[PropertyGate, ActorGate, InformationGate, CompoundGate]


@dataclass
class GatedRelationship:
    """A relationship with a gate condition on traversal.

    Extends RelationshipSpec with gate information. The relationship
    defines the edge; the gate defines when the edge can be traversed.
    """

    relationship: RelationshipSpec
    gate: Gate
    description: str = ""  # human-readable gate description
