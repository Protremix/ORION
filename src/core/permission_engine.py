"""
ORION Core Permission Engine — Phase 004. License: Apache 2.0

Separate from PolicyEngine — handles permission levels (read/write/irreversible)
and per-task authorization. PolicyEngine makes tool-level decisions;
PermissionEngine handles operation-level authorization.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from src.core.tool_registry import ToolCategory, ToolDefinition, ToolRegistry, ToolRiskLevel

logger = logging.getLogger(__name__)


class PermissionLevel(int, Enum):
    """Hierarchy of permissions — higher levels include all lower levels."""
    READ = 0       # Can read data, observe state
    WRITE = 1      # Can modify data, create/update entities
    EXECUTE = 2    # Can execute tools and invoke agents
    IRREVERSIBLE = 3  # Can perform irreversible actions (physical, financial)
    ADMIN = 4      # Full access — Founder only


class AuthorizationResult:
    """Result of a permission check."""
    def __init__(self, allowed: bool, required_level: PermissionLevel,
                 granted_level: PermissionLevel, reason: str = "") -> None:
        self.allowed = allowed
        self.required_level = required_level
        self.granted_level = granted_level
        self.reason = reason
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "required_level": self.required_level.name,
            "granted_level": self.granted_level.name,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class PermissionEngine:
    """
    Permission engine for ORION Core.

    Separates permission levels from policy decisions:
    - PolicyEngine: "Is this tool allowed to be invoked?"
    - PermissionEngine: "Does the caller have permission to perform this operation?"

    In Phase 004, the Supervisor operates at EXECUTE level.
    IRREVERSIBLE level is blocked (no physical/financial actions).
    ADMIN level is reserved for the Founder.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._current_level: PermissionLevel = PermissionLevel.EXECUTE
        self._task_levels: Dict[str, PermissionLevel] = {}  # per-task override
        self._blocked_operations: Set[str] = set()
        self._version = "1.0.0"
        self._setup_blocked_ops()

    def _setup_blocked_ops(self) -> None:
        """Block all irreversible operations in Phase 004."""
        self._blocked_operations = {
            "physical_actuation",
            "financial_transaction",
            "legal_action",
            "irreversible_delete",
            "system_shutdown",
            "network_deployment",
        }

    def set_level(self, level: PermissionLevel) -> None:
        """Set the current permission level (for testing or Founder override)."""
        self._current_level = level
        logger.info(f"Permission level set to: {level.name}")

    def set_task_level(self, task_id: str, level: PermissionLevel) -> None:
        """Set a per-task permission override."""
        self._task_levels[task_id] = level

    def get_required_level(self, tool_name: str) -> PermissionLevel:
        """Determine the required permission level for a tool."""
        tool = self._tool_registry.get(tool_name)
        if not tool:
            return PermissionLevel.ADMIN  # Unknown tools require admin
        if tool.category == ToolCategory.PHYSICAL:
            return PermissionLevel.IRREVERSIBLE
        if tool.risk_level in (ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL):
            return PermissionLevel.IRREVERSIBLE
        if tool.risk_level == ToolRiskLevel.MEDIUM:
            return PermissionLevel.EXECUTE
        if tool.category == ToolCategory.WRITE:
            return PermissionLevel.WRITE
        return PermissionLevel.READ

    def check(self, tool_name: str, operation: Optional[str] = None,
              task_id: Optional[str] = None) -> AuthorizationResult:
        """
        Check if the current permission level allows the given tool/operation.

        Returns AuthorizationResult with details.
        """
        # Check blocked operations first
        if operation and operation in self._blocked_operations:
            return AuthorizationResult(
                allowed=False,
                required_level=PermissionLevel.IRREVERSIBLE,
                granted_level=self._current_level,
                reason=f"Operation blocked in Phase 004: {operation}",
            )

        required = self.get_required_level(tool_name)
        granted = self._task_levels.get(task_id, self._current_level) if task_id else self._current_level

        # IRREVERSIBLE is always blocked in Phase 004
        if required >= PermissionLevel.IRREVERSIBLE:
            return AuthorizationResult(
                allowed=False,
                required_level=required,
                granted_level=granted,
                reason="Irreversible operations blocked in Phase 004",
            )

        if granted >= required:
            return AuthorizationResult(
                allowed=True,
                required_level=required,
                granted_level=granted,
            )
        else:
            return AuthorizationResult(
                allowed=False,
                required_level=required,
                granted_level=granted,
                reason=f"Insufficient permissions: need {required.name}, have {granted.name}",
            )

    def is_irreversible_blocked(self) -> bool:
        """Verify that irreversible operations are blocked."""
        return True  # Always blocked in Phase 004

    def list_blocked_operations(self) -> Set[str]:
        return set(self._blocked_operations)

    def to_dict(self) -> dict:
        return {
            "version": self._version,
            "current_level": self._current_level.name,
            "irreversible_blocked": self.is_irreversible_blocked(),
            "blocked_operations": list(self._blocked_operations),
            "task_overrides": {tid: lvl.name for tid, lvl in self._task_levels.items()},
        }
