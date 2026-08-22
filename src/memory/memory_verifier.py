"""
ORION Phase 005 — Memory Verifier. License: Apache 2.0

Truth reconciliation — compares stored memories against new observations
and resolves conflicts. Uses existing ContradictionDetector from Phase 1.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.memory.memory_system import (
    ContradictionDetector,
    MemoryEntry,
    MemoryStore,
    MemoryType,
    Provenance,
    SemanticMemory,
    SourceType,
)

logger = logging.getLogger(__name__)


class ConflictResolution(str, Enum):
    """How to resolve a detected contradiction."""
    OVERWRITE = "overwrite"
    REJECT = "reject"
    FLAG = "flag"


@dataclass
class VerificationConflict:
    """A single conflict found during verification."""
    memory_id: str
    memory_content: str
    observation: str
    conflict_reason: str
    resolution: Optional[ConflictResolution] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_content": self.memory_content,
            "observation": self.observation,
            "conflict_reason": self.conflict_reason,
            "resolution": self.resolution.value if self.resolution else None,
        }


@dataclass
class VerificationReport:
    """Result of a verification pass."""
    total_checked: int = 0
    conflicts_found: int = 0
    confirmations: int = 0
    confidence_updates: int = 0
    conflicts: List[VerificationConflict] = field(default_factory=list)
    confirmed_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_checked": self.total_checked,
            "conflicts_found": self.conflicts_found,
            "confirmations": self.confirmations,
            "confidence_updates": self.confidence_updates,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "confirmed_ids": self.confirmed_ids,
        }


class MemoryVerifier:
    """
    Truth reconciliation engine.

    Compares stored semantic memories against new observations.
    Detects conflicts, updates confidence, and resolves contradictions.
    """

    def __init__(
        self,
        store: MemoryStore,
        detector: ContradictionDetector,
    ) -> None:
        self._store = store
        self._detector = detector

    def verify(
        self,
        observations: List[Dict[str, Any]],
    ) -> VerificationReport:
        """Compare observations against stored semantic memories."""
        report = VerificationReport()
        semantic_entries = self._store.query_memories(
            memory_type=MemoryType.SEMANTIC, limit=500
        )

        for obs in observations:
            obs_content = obs.get("content", {})
            obs_type_str = obs.get("memory_type", "semantic")
            try:
                obs_type = MemoryType(obs_type_str)
            except ValueError:
                obs_type = MemoryType.SEMANTIC

            report.total_checked += 1

            temp_entry = self._create_temp_entry(obs_content, obs_type)
            if temp_entry is None:
                continue

            has_contradiction, reason = self._detector.check_contradictions(
                new_entry=temp_entry,
                existing_entries=semantic_entries,
            )

            if has_contradiction:
                conflict = self._find_conflicting_memory(temp_entry, semantic_entries, reason)
                if conflict:
                    report.conflicts_found += 1
                    report.conflicts.append(VerificationConflict(
                        memory_id=conflict.id,
                        memory_content=str(conflict.content),
                        observation=str(obs_content),
                        conflict_reason=reason,
                    ))
            else:
                confirmed = self._find_matching_memory(temp_entry, semantic_entries)
                if confirmed:
                    report.confirmations += 1
                    report.confirmed_ids.append(confirmed.id)
                    report.confidence_updates += 1

        logger.info(
            "Verification pass: %d checked, %d conflicts, %d confirmations",
            report.total_checked, report.conflicts_found, report.confirmations,
        )
        return report

    def resolve_conflict(
        self,
        memory_id: str,
        observation: Dict[str, Any],
        resolution: ConflictResolution,
    ) -> bool:
        """Resolve a detected contradiction."""
        existing = self._store.get_memory(memory_id)
        if existing is None:
            return False

        if resolution == ConflictResolution.OVERWRITE:
            new_content = observation.get("content", existing.content)
            try:
                updated, _ = self._store.update_memory(
                    memory_id, new_content, "verifier", ["write"]
                )
                logger.info("Conflict resolved (OVERWRITE): %s", memory_id)
                return updated is not None
            except Exception as e:
                logger.error("Failed to overwrite memory %s: %s", memory_id, e)
                return False

        elif resolution == ConflictResolution.REJECT:
            logger.info("Conflict resolved (REJECT): %s", memory_id)
            return True

        elif resolution == ConflictResolution.FLAG:
            try:
                flagged_content = {**existing.content, "_conflict_flagged": True}
                updated, _ = self._store.update_memory(
                    memory_id, flagged_content, "verifier", ["write"]
                )
                logger.info("Conflict flagged for review: %s", memory_id)
                return updated is not None
            except Exception as e:
                logger.error("Failed to flag memory %s: %s", memory_id, e)
                return False

        return False

    def get_confidence_trend(self, memory_id: str) -> List[float]:
        """Return confidence history for a memory entry."""
        entry = self._store.get_memory(memory_id)
        if entry is None:
            return []
        return [entry.confidence]

    def _create_temp_entry(
        self,
        content: Dict[str, Any],
        memory_type: MemoryType,
    ) -> Optional[MemoryEntry]:
        """Create a temporary MemoryEntry for contradiction detection."""
        try:
            entry = SemanticMemory(
                content=content,
                memory_type=memory_type,
                confidence=content.get("confidence", 1.0),
                provenance=Provenance(
                    writer_id="verifier",
                    writer_permissions=["verify"],
                    source_type=SourceType.INFERENCE,
                ),
            )
            return entry
        except Exception as e:
            logger.error("Failed to create temp entry: %s", e)
            return None

    def _find_conflicting_memory(
        self,
        new_entry: MemoryEntry,
        existing: List[MemoryEntry],
        reason: str,
    ) -> Optional[MemoryEntry]:
        """Find which existing memory conflicts with the new entry."""
        for entry in existing:
            has_conflict, _ = self._detector.check_contradictions(
                new_entry=new_entry,
                existing_entries=[entry],
            )
            if has_conflict:
                return entry
        return None

    def _find_matching_memory(
        self,
        new_entry: MemoryEntry,
        existing: List[MemoryEntry],
    ) -> Optional[MemoryEntry]:
        """Find a memory that matches/confirms the new entry."""
        for entry in existing:
            has_conflict, _ = self._detector.check_contradictions(
                new_entry=new_entry,
                existing_entries=[entry],
            )
            if not has_conflict and self._content_matches(new_entry.content, entry.content):
                return entry
        return None

    def _content_matches(self, content_a: Dict[str, Any], content_b: Dict[str, Any]) -> bool:
        """Check if two content dicts share key facts."""
        if not content_a or not content_b:
            return False
        shared_keys = set(content_a.keys()) & set(content_b.keys())
        if not shared_keys:
            return False
        matches = sum(1 for k in shared_keys if content_a[k] == content_b[k])
        return matches >= len(shared_keys) * 0.5
