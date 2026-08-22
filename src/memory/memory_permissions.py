"""
ORION Phase 005 — Memory Permissions. License: Apache 2.0

Integrates with Phase 004 PermissionEngine to enforce per-type, per-operation
permission checks for memory access.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from src.core.permission_engine import PermissionLevel
from src.memory.memory_system import MemoryType, SourceType

logger = logging.getLogger(__name__)


class MemoryOperation(str, Enum):
    """Memory operation types for permission checks."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"


@dataclass
class MemoryPermissionResult:
    """Result of a memory permission check."""
    allowed: bool
    operation: MemoryOperation
    memory_type: MemoryType
    requester_level: PermissionLevel
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "operation": self.operation.value,
            "memory_type": self.memory_type.value,
            "requester_level": self.requester_level.name,
            "reason": self.reason,
        }


class MemoryPermissions:
    """
    Memory permission enforcement integrated with Phase 004 PermissionEngine.
    """

    _READ_MATRIX: Dict[PermissionLevel, set] = {
        PermissionLevel.READ: {MemoryType.SHORT_TERM, MemoryType.WORKING},
        PermissionLevel.WRITE: {MemoryType.SHORT_TERM, MemoryType.WORKING},
        PermissionLevel.EXECUTE: {
            MemoryType.SHORT_TERM, MemoryType.WORKING,
            MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL,
        },
        PermissionLevel.IRREVERSIBLE: {
            MemoryType.SHORT_TERM, MemoryType.WORKING,
            MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL,
        },
        PermissionLevel.ADMIN: set(MemoryType),
    }

    _WRITE_MATRIX: Dict[SourceType, set] = {
        SourceType.AGENT: {MemoryType.SHORT_TERM, MemoryType.WORKING, MemoryType.EPISODIC},
        SourceType.HUMAN: set(MemoryType),
        SourceType.INFERENCE: {MemoryType.SEMANTIC},
        SourceType.SENSOR: {MemoryType.SHORT_TERM, MemoryType.EPISODIC},
    }

    _WRITE_LEVEL_REQUIRED: Dict[MemoryType, PermissionLevel] = {
        MemoryType.SHORT_TERM: PermissionLevel.EXECUTE,
        MemoryType.WORKING: PermissionLevel.EXECUTE,
        MemoryType.EPISODIC: PermissionLevel.EXECUTE,
        MemoryType.SEMANTIC: PermissionLevel.EXECUTE,
        MemoryType.PROCEDURAL: PermissionLevel.ADMIN,
        MemoryType.AUDIT_TRAIL: PermissionLevel.ADMIN,
    }

    def __init__(self, permission_engine: Optional[Any] = None) -> None:
        self._engine = permission_engine

    def _get_requester_level(self, requester_level: Optional[PermissionLevel]) -> PermissionLevel:
        if requester_level is not None:
            return requester_level
        if self._engine is not None:
            level = getattr(self._engine, "_current_level", None)
            if level is not None:
                return level
        return PermissionLevel.READ

    def can_read(
        self,
        memory_type: MemoryType,
        requester_level: Optional[PermissionLevel] = None,
    ) -> MemoryPermissionResult:
        level = self._get_requester_level(requester_level)
        allowed_types = self._READ_MATRIX.get(level, set())
        if memory_type in allowed_types:
            return MemoryPermissionResult(
                allowed=True, operation=MemoryOperation.READ,
                memory_type=memory_type, requester_level=level,
                reason="Permission granted",
            )
        return MemoryPermissionResult(
            allowed=False, operation=MemoryOperation.READ,
            memory_type=memory_type, requester_level=level,
            reason=f"Permission level {level.name} cannot read {memory_type.value}",
        )

    def can_write(
        self,
        memory_type: MemoryType,
        source_type: SourceType,
        requester_level: Optional[PermissionLevel] = None,
    ) -> MemoryPermissionResult:
        level = self._get_requester_level(requester_level)
        allowed_types_for_source = self._WRITE_MATRIX.get(source_type, set())
        if memory_type not in allowed_types_for_source:
            return MemoryPermissionResult(
                allowed=False, operation=MemoryOperation.WRITE,
                memory_type=memory_type, requester_level=level,
                reason=f"Source {source_type.value} cannot write {memory_type.value}",
            )
        required_level = self._WRITE_LEVEL_REQUIRED.get(memory_type, PermissionLevel.ADMIN)
        if level < required_level:
            return MemoryPermissionResult(
                allowed=False, operation=MemoryOperation.WRITE,
                memory_type=memory_type, requester_level=level,
                reason=f"Requires {required_level.name} level, got {level.name}",
            )
        return MemoryPermissionResult(
            allowed=True, operation=MemoryOperation.WRITE,
            memory_type=memory_type, requester_level=level,
            reason="Permission granted",
        )

    def can_delete(
        self,
        memory_type: MemoryType,
        requester_level: Optional[PermissionLevel] = None,
    ) -> MemoryPermissionResult:
        level = self._get_requester_level(requester_level)
        if level >= PermissionLevel.ADMIN:
            return MemoryPermissionResult(
                allowed=True, operation=MemoryOperation.DELETE,
                memory_type=memory_type, requester_level=level,
                reason="ADMIN permission granted for delete",
            )
        return MemoryPermissionResult(
            allowed=False, operation=MemoryOperation.DELETE,
            memory_type=memory_type, requester_level=level,
            reason=f"Delete requires ADMIN level, got {level.name}",
        )
