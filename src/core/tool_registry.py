"""
ORION Core Tool Registry — Phase 004. License: Apache 2.0
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

class ToolRiskLevel(int, Enum):
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    FORBIDDEN = 5

class ToolCategory(str, Enum):
    READ = "read"
    WRITE = "write"
    COMPUTE = "compute"
    COMMUNICATE = "communicate"
    OBSERVE = "observe"
    PHYSICAL = "physical"

@dataclass
class ToolSchema:
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    returns: Dict[str, Any] = field(default_factory=dict)

    def validate(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        for req in self.required:
            if req not in args:
                return False, f"Missing required parameter: {req}"
        for key, value in args.items():
            if key in self.parameters:
                expected_type = self.parameters[key].get("type")
                if expected_type and not isinstance(value, eval(expected_type) if isinstance(expected_type, str) else expected_type):
                    return False, f"Parameter '{key}' has wrong type: expected {expected_type}, got {type(value).__name__}"
        return True, None

@dataclass
class ToolDefinition:
    name: str
    description: str
    category: ToolCategory
    risk_level: ToolRiskLevel
    schema: ToolSchema = field(default_factory=ToolSchema)
    permissions_required: Set[str] = field(default_factory=set)
    timeout: float = 30.0
    rollback: Optional[Callable[[], bool]] = None
    handler: Optional[Callable[..., Any]] = None
    side_effects: bool = False
    idempotent: bool = True
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "category": self.category.value, "risk_level": self.risk_level.name,
                "permissions_required": list(self.permissions_required), "timeout": self.timeout,
                "side_effects": self.side_effects, "idempotent": self.idempotent, "version": self.version}

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._version = "1.0.0"

    def register(self, tool: ToolDefinition) -> bool:
        if tool.name in self._tools:
            logger.warning(f"Tool already registered: {tool.name}")
            return False
        if tool.risk_level == ToolRiskLevel.FORBIDDEN:
            logger.warning(f"Cannot register forbidden tool: {tool.name}")
            return False
        if tool.category == ToolCategory.PHYSICAL:
            logger.warning(f"Physical tools blocked in Phase 004: {tool.name}")
            return False
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (risk={tool.risk_level.name})")
        return True

    def unregister(self, name: str) -> bool:
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def list_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        return [t for t in self._tools.values() if t.category == category]

    def list_by_risk(self, max_risk: ToolRiskLevel) -> List[ToolDefinition]:
        return [t for t in self._tools.values() if t.risk_level <= max_risk]

    def is_allowed(self, name: str) -> bool:
        tool = self._tools.get(name)
        if not tool:
            return False
        if tool.category == ToolCategory.PHYSICAL:
            return False
        if tool.risk_level >= ToolRiskLevel.FORBIDDEN:
            return False
        return True

    def validate_args(self, name: str, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        tool = self._tools.get(name)
        if not tool:
            return False, f"Unknown tool: {name}"
        if not self.is_allowed(name):
            return False, f"Tool not allowed in Phase 004: {name}"
        return tool.schema.validate(args)

    def to_dict(self) -> dict:
        return {"version": self._version, "tools": {n: t.to_dict() for n, t in self._tools.items()},
                "tool_count": len(self._tools)}
