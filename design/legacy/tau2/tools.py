"""
Tools: tau2-specific tool types and derivation.

Extends the format-agnostic ToolSpec with tau2's role-based tool
model (agent tools, user tools, init tools, assertion tools).

The key function is derive_tool_signatures(): schema → ToolSuiteSpec.
This is pure code (no LLM) — it mechanically generates tool signatures
from the world schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from design.framework.world import EntitySpec, FieldType, WorldSchema


class ToolRole(str, Enum):
    AGENT = "agent"
    USER = "user"


class ToolAccess(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass
class ToolParam:
    name: str
    type: str
    description: str
    required: bool = True


@dataclass
class ToolSignatureSpec:
    """A tool signature. Derived mechanically from schema."""

    name: str
    role: ToolRole
    access: ToolAccess
    description: str
    params: list[ToolParam]
    returns: str
    entity: Optional[str] = None
    field_name: Optional[str] = None


@dataclass
class ToolSuiteSpec:
    """All tool signatures for the domain."""

    agent_tools: list[ToolSignatureSpec] = field(default_factory=list)
    user_tools: list[ToolSignatureSpec] = field(default_factory=list)
    init_tools: list[ToolSignatureSpec] = field(default_factory=list)
    assertion_tools: list[ToolSignatureSpec] = field(default_factory=list)

    @property
    def all_tools(self) -> list[ToolSignatureSpec]:
        return (
            self.agent_tools
            + self.user_tools
            + self.init_tools
            + self.assertion_tools
        )

    def get_tool(self, name: str) -> Optional[ToolSignatureSpec]:
        for tool in self.all_tools:
            if tool.name == name:
                return tool
        return None


@dataclass
class ToolImplSpec:
    """Tool implementation: just the body, signature is derived."""

    tool: ToolSignatureSpec
    body: str
    preconditions: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════
# DERIVATION
# ══════════════════════════════════════════════════════════════════════


def _snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _field_type_to_python(ft: FieldType) -> str:
    return {
        FieldType.STRING: "str",
        FieldType.INT: "int",
        FieldType.FLOAT: "float",
        FieldType.BOOL: "bool",
        FieldType.ENUM: "str",
        FieldType.DATE: "str",
        FieldType.LIST_STR: "list[str]",
    }[ft]


def derive_tool_signatures(schema: WorldSchema) -> ToolSuiteSpec:
    """Schema → tool signatures. Pure code, no LLM.

    Generates:
    - get_{entity}(id) → READ for each entity
    - update_{entity}_{field}(id, value) → WRITE for each mutable field
    - set_{entity}_{field}(id, value) → init tool for each breakable field
    - assert_{entity}_{field}(id, expected) → assertion for each breakable field
    - acknowledge_resolution() → common user WRITE
    """
    agent_tools, user_tools, init_tools, assertion_tools = [], [], [], []

    for entity in schema.entities:
        id_field = entity.identity_field
        id_type = "str"  # simplification
        for f in entity.fields:
            if f.name == id_field:
                id_type = _field_type_to_python(f.type)
                break
        e_lower = _snake_case(entity.name)

        # Agent READ
        agent_tools.append(ToolSignatureSpec(
            name=f"get_{e_lower}",
            role=ToolRole.AGENT,
            access=ToolAccess.READ,
            description=f"Look up a {entity.name} by {id_field}.",
            params=[ToolParam(id_field, id_type, f"The {id_field}")],
            returns=f"{entity.name} details",
            entity=entity.name,
        ))

        for f in entity.fields:
            if f.mutable and f.name != id_field:
                # Agent WRITE
                agent_tools.append(ToolSignatureSpec(
                    name=f"update_{e_lower}_{f.name}",
                    role=ToolRole.AGENT,
                    access=ToolAccess.WRITE,
                    description=f"Update {entity.name}.{f.name}.",
                    params=[
                        ToolParam(
                            id_field, id_type, f"The {id_field}"
                        ),
                        ToolParam(
                            f.name,
                            _field_type_to_python(f.type),
                            f"New value for {f.name}",
                        ),
                    ],
                    returns="Confirmation",
                    entity=entity.name,
                    field_name=f.name,
                ))

            if f.breakable:
                # Init tool (not exposed to agent)
                init_tools.append(ToolSignatureSpec(
                    name=f"set_{e_lower}_{f.name}",
                    role=ToolRole.AGENT,
                    access=ToolAccess.WRITE,
                    description=f"[INIT] Set {entity.name}.{f.name}.",
                    params=[
                        ToolParam(
                            id_field, id_type, f"The {id_field}"
                        ),
                        ToolParam(
                            f.name,
                            _field_type_to_python(f.type),
                            "Value",
                        ),
                    ],
                    returns="None",
                    entity=entity.name,
                    field_name=f.name,
                ))

                # Assertion tool
                assertion_tools.append(ToolSignatureSpec(
                    name=f"assert_{e_lower}_{f.name}",
                    role=ToolRole.AGENT,
                    access=ToolAccess.READ,
                    description=(
                        f"Assert {entity.name}.{f.name} equals expected."
                    ),
                    params=[
                        ToolParam(
                            id_field, id_type, f"The {id_field}"
                        ),
                        ToolParam(
                            "expected",
                            _field_type_to_python(f.type),
                            "Expected value",
                        ),
                    ],
                    returns="bool",
                    entity=entity.name,
                    field_name=f.name,
                ))

    user_tools.append(ToolSignatureSpec(
        name="acknowledge_resolution",
        role=ToolRole.USER,
        access=ToolAccess.WRITE,
        description="Acknowledge that the agent resolved your issue.",
        params=[],
        returns="Confirmation",
    ))

    return ToolSuiteSpec(agent_tools, user_tools, init_tools, assertion_tools)
