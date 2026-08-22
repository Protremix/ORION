"""
ORION Phase 005 — Memory Writer. License: Apache 2.0

Validated, permission-checked memory writes. Wraps existing ValidationPipeline
and PoisoningResistance from Phase 1, adds permission checks from MemoryPermissions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.permission_engine import PermissionLevel
from src.memory.memory_permissions import MemoryPermissions
from src.memory.memory_system import (
    ContradictionDetector,
    MemoryEntry,
    MemoryStore,
    MemoryType,
    PoisoningResistance,
    SourceType,
    ValidationPipeline,
    ValidationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    """Result of a memory write operation."""
    success: bool
    memory_id: Optional[str] = None
    conflicts: List[str] = field(default_factory=list)
    validation_result: Optional[ValidationResult] = None
    permission_denied: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "memory_id": self.memory_id,
            "conflicts": self.conflicts,
            "permission_denied": self.permission_denied,
            "error": self.error,
            "validation_valid": self.validation_result.is_valid if self.validation_result else None,
        }


class MemoryWriter:
    """
    Validated, permission-checked memory writes.

    Pipeline: validate -> check permissions -> check contradictions -> store.
    Every write goes through the full Phase 1 validation pipeline.
    """

    def __init__(
        self,
        store: MemoryStore,
        validation: ValidationPipeline,
        poisoning: PoisoningResistance,
        permissions: MemoryPermissions,
        contradiction_detector: Optional[ContradictionDetector] = None,
    ) -> None:
        self._store = store
        self._validation = validation
        self._poisoning = poisoning
        self._permissions = permissions
        self._contradiction_detector = contradiction_detector

    def write(
        self,
        entry: MemoryEntry,
        requester_level: Optional[PermissionLevel] = None,
    ) -> WriteResult:
        """
        Validate -> check permissions -> check contradictions -> store.
        Returns WriteResult with success status, conflicts, and storage metadata.
        """
        # Step 1: Check write permissions
        source_type = entry.provenance.source_type if entry.provenance else SourceType.AGENT
        perm_result = self._permissions.can_write(
            memory_type=entry.memory_type,
            source_type=source_type,
            requester_level=requester_level,
        )
        if not perm_result.allowed:
            logger.warning("Memory write denied: %s", perm_result.reason)
            return WriteResult(
                success=False,
                permission_denied=True,
                error=perm_result.reason,
            )

        # Step 2: Get recent entries for poisoning/anomaly detection
        recent = self._store.query_memories(
            memory_type=entry.memory_type, limit=50
        )

        # Step 3: Check for contradictions (optional)
        conflicts: List[str] = []
        if self._contradiction_detector is not None:
            _, contradicting_ids, details = self._contradiction_detector.check_contradictions(
                new_entry=entry, existing_entries=recent
            )
            if bool(contradicting_ids):
                conflicts.extend(details)
                logger.info("Contradiction detected during write: %s", details)

        # Step 4: Store — write_memory returns (MemoryEntry, ValidationResult) tuple
        try:
            stored_entry, validation_result = self._store.write_memory(entry, actor_permissions=["memory:write:cognitive"])
            if stored_entry is None:
                return WriteResult(
                    success=False,
                    validation_result=validation_result,
                    error="; ".join(validation_result.errors) if validation_result.errors else "Write failed",
                )
            memory_id = stored_entry.id
            logger.info("Memory written: id=%s type=%s", memory_id, entry.memory_type.value)
            return WriteResult(
                success=True,
                memory_id=memory_id,
                conflicts=conflicts,
                validation_result=validation_result,
            )
        except Exception as e:
            logger.error("Failed to store memory: %s", e)
            return WriteResult(
                success=False,
                error=f"Storage error: {e}",
            )

    def write_batch(
        self,
        entries: List[MemoryEntry],
        requester_level: Optional[PermissionLevel] = None,
    ) -> List[WriteResult]:
        """Batch write with per-entry validation. Non-atomic."""
        results: List[WriteResult] = []
        for entry in entries:
            result = self.write(entry, requester_level=requester_level)
            results.append(result)
        return results

    def update(
        self,
        memory_id: str,
        content: Dict[str, Any],
        writer_id: str = "supervisor",
        writer_permissions: Optional[List[str]] = None,
        requester_level: Optional[PermissionLevel] = None,
    ) -> WriteResult:
        """Update existing memory. Increments version, logs provenance."""
        existing = self._store.get_memory(memory_id)
        if existing is None:
            return WriteResult(success=False, error="Memory not found")

        # Check write permission for the memory type
        source_type = existing.provenance.source_type if existing.provenance else SourceType.AGENT
        perm_result = self._permissions.can_write(
            memory_type=existing.memory_type,
            source_type=source_type,
            requester_level=requester_level,
        )
        if not perm_result.allowed:
            return WriteResult(
                success=False,
                permission_denied=True,
                error=perm_result.reason,
            )

        try:
            perms = writer_permissions or ["memory:write:cognitive"]
            updated_entry, val_result = self._store.update_memory(
                memory_id, content, writer_id, perms
            )
            if updated_entry is None:
                return WriteResult(
                    success=False,
                    error="; ".join(val_result.errors) if val_result.errors else "Update failed",
                )
            logger.info("Memory updated: id=%s", memory_id)
            return WriteResult(success=True, memory_id=memory_id)
        except Exception as e:
            logger.error("Failed to update memory %s: %s", memory_id, e)
            return WriteResult(success=False, error=f"Update error: {e}")

    def delete(
        self,
        memory_id: str,
        requester_level: Optional[PermissionLevel] = None,
    ) -> bool:
        """Soft-delete memory. Requires ADMIN permission."""
        existing = self._store.get_memory(memory_id)
        if existing is None:
            return False

        perm_result = self._permissions.can_delete(
            memory_type=existing.memory_type,
            requester_level=requester_level,
        )
        if not perm_result.allowed:
            logger.warning("Memory delete denied: %s", perm_result.reason)
            return False

        try:
            self._store.delete_memory(memory_id, soft=True, actor_permissions=["admin"])
            logger.info("Memory soft-deleted: id=%s", memory_id)
            return True
        except Exception as e:
            logger.error("Failed to delete memory %s: %s", memory_id, e)
            return False
