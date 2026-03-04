"""
Tools: Format-agnostic tool interface.

These types describe what operations exist in a world without
specifying the interaction format (tool calls, code edits, API
requests, etc.). The rendering layer converts these into
format-specific tool definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ToolType(str, Enum):
    """What kind of operation this tool performs."""

    READ = "read"  # pure observation, no state change
    WRITE = "write"  # mutates world state
    INIT = "init"  # sets initial state (not exposed to agent)
    ASSERTION = "assertion"  # checks a condition (for verification)


@dataclass
class ToolParam:
    """One parameter of a tool."""

    name: str
    type: str  # Python type as string ("str", "int", "float", "bool")
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolSpec:
    """A single tool in the world. Format-agnostic.

    Describes WHAT the tool does, not HOW it's invoked (that's
    format-specific). A rendering layer converts this into its
    own tool format (tau2 ToolSignatureSpec, function signature, etc.).
    """

    name: str
    tool_type: ToolType
    description: str
    params: list[ToolParam]
    returns: str
    entity: Optional[str] = None  # which entity this operates on
    field_name: Optional[str] = None  # which field (for WRITE/INIT/ASSERTION)
    preconditions: list[str] = field(default_factory=list)  # rule-derived


@dataclass
class ToolSuite:
    """All tools available in a world. Format-agnostic.

    Organized by type for easy filtering. The rendering layer
    decides which tools are exposed to which actors.
    """

    read_tools: list[ToolSpec] = field(default_factory=list)
    write_tools: list[ToolSpec] = field(default_factory=list)
    init_tools: list[ToolSpec] = field(default_factory=list)
    assertion_tools: list[ToolSpec] = field(default_factory=list)
    custom_tools: list[ToolSpec] = field(default_factory=list)

    @property
    def all_tools(self) -> list[ToolSpec]:
        return (
            self.read_tools
            + self.write_tools
            + self.init_tools
            + self.assertion_tools
            + self.custom_tools
        )

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        for tool in self.all_tools:
            if tool.name == name:
                return tool
        return None
