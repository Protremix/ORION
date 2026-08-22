"""
ORION Phase 005 — Memory Permissions. License: Apache 2.0.

Integrates with Phase 004 PermissionEngine to enforce per-type, per-operation
permission checks for memory access.

Luna R1 fixes:
- Added MemoryRequestContext (trusted authorization context)
- Read permissions enforced on retrieval APIs
- Audit trail isolation — generic APIs cannot modify AUDIT_TRAIL
- WRITE and IRREVERSIBLE levels added to read matrix
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Set

from src.core.permission_engine import PermissionLevel
from src.memory.memory_system import MemoryType, SourceType

logger = logging.getLogger(__name__)


class MemoryOperation(str, Enum):
    """Memory operation types for permission checks."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    VERIFY = "verify"
    CONSOLIDATE = "consolidate"


@dataclass(frozen=True)
class MemoryRequestContext:
    """
    Trusted authorization context for every memory operation.

    Luna R1 Finding #1: Caller-supplied permission levels must NOT be trusted.
    The permission_level is resolved by the PermissionEngine, not the caller.
    """
    principal_id: str
    task_id: Optional[str] = None
    source_type: SourceType = SourceType.AGENT
    permission_level: PermissionLevel = PermissionLevel.READ
    correlation_id: Optional[str] = None

    def with_level(self, level: PermissionLevel) -> "MemoryRequestContext":
        """Return a new context with updated permission level."""
        return MemoryRequestContext(
            principal_id=self.principal_id,
            task_id=self.task_id,
            source_type=self.source_type,
            permission_level=level,
            correlation_id=self.correlation_id,
        )


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

    Luna R1: Permission levels are resolved from the engine, not from
    caller-supplied values. MemoryRequestContext is the authoritative
    authorization context for all operations.
    """

    # Luna R1 #2: READ matrix includes WRITE and IRREVERSIBLE levels
    _READ_MATRIX: Dict[PermissionLevel, Set] = {
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

    _WRITE_MATRIX: Dict[SourceType, Set] = {
        SourceType.AGENT: {MemoryType.SHORT_TERM, MemoryType.WORKING, MemoryType.EPISODIC},
        SourceType.HUMAN: {MemoryType.SHORT_TERM, MemoryType.WORKING, MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL},
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

    def resolve_context(
        self,
        principal_id: str,
        task_id: Optional[str] = None,
        source_type: SourceType = SourceType.AGENT,
        requester_level: Optional[PermissionLevel] = None,
    ) -> MemoryRequestContext:
        """
        Resolve a trusted MemoryRequestContext.
        Luna R1 #1: Engine resolves effective level, not the caller.
        """
        level = requester_level
        if level is None and self._engine is not None:
            engine_level = getattr(self._engine, "_current_level", None)
            if engine_level is not None:
                level = engine_level
        if level is None:
            level = PermissionLevel.READ
        return MemoryRequestContext(
            principal_id=principal_id,
            task_id=task_id,
            source_type=source_type,
            permission_level=level,
        )

    def can_read(
        self,
        memory_type: MemoryType,
        requester_level: Optional[PermissionLevel] = None,
        context: Optional[MemoryRequestContext] = None,
    ) -> MemoryPermissionResult:
        """Check read permission."""
        if context is not None:
            level = context.permission_level
        else:
            level = self._get_requester_level(requester_level)

        # Luna R1 #3: AUDIT_TRAIL reads require ADMIN
        if memory_type == MemoryType.AUDIT_TRAIL and level < PermissionLevel.ADMIN:
            return MemoryPermissionResult(
                allowed=False, operation=MemoryOperation.READ,
                memory_type=memory_type, requester_level=level,
                reason="AUDIT_TRAIL read requires ADMIN level",
            )

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
        context: Optional[MemoryRequestContext] = None,
    ) -> MemoryPermissionResult:
        """Check write permission."""
        if context is not None:
            level = context.permission_level
            source_type = context.source_type
        else:
            level = self._get_requester_level(requester_level)

        # Luna R1 #3: AUDIT_TRAIL cannot be written through generic APIs
        if memory_type == MemoryType.AUDIT_TRAIL:
            return MemoryPermissionResult(
                allowed=False, operation=MemoryOperation.WRITE,
                memory_type=memory_type, requester_level=level,
                reason="AUDIT_TRAIL must use append-only audit path, not generic write",
            )

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
        context: Optional[MemoryRequestContext] = None,
    ) -> MemoryPermissionResult:
        """Check delete permission."""
        if context is not None:
            level = context.permission_level
        else:
            level = self._get_requester_level(requester_level)

        # Luna R1 #3: AUDIT_TRAIL cannot be deleted through generic APIs
        if memory_type == MemoryType.AUDIT_TRAIL:
            return MemoryPermissionResult(
                allowed=False, operation=MemoryOperation.DELETE,
                memory_type=memory_type, requester_level=level,
                reason="AUDIT_TRAIL is immutable — cannot be deleted via generic API",
            )

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

    def filter_readable_types(
        self,
        all_types: Set,
        requester_level: Optional[PermissionLevel] = None,
        context: Optional[MemoryRequestContext] = None,
    ) -> Set:
        """Return only the memory types the requester is allowed to read."""
        if context is not None:
            level = context.permission_level
        else:
            level = self._get_requester_level(requester_level)
        allowed = self._READ_MATRIX.get(level, set())
        if level < PermissionLevel.ADMIN:
            allowed = allowed - {MemoryType.AUDIT_TRAIL}
        return all_types & allowed

    def _get_requester_level(self, requester_level: Optional[PermissionLevel]) -> PermissionLevel:
        if requester_level is not None:
            return requester_level
        if self._engine is not None:
            level = getattr(self._engine, "_current_level", None)
            if level is not None:
                return level
        return PermissionLevel.READ
