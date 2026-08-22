"""
ORION Phase 005 — Memory Decay. License: Apache 2.0

Automatic lifecycle management — TTL expiration, importance scoring,
and consolidation of short-term to long-term memories.

Importance score = access_count_norm * 0.3 + recency_norm * 0.3 +
                   confidence * 0.2 + contradiction_penalty * 0.2
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.memory.memory_system import (
    MemoryEntry,
    MemoryStore,
    MemoryType,
    Provenance,
    RetentionType,
    SemanticMemory,
    SourceType,
)

logger = logging.getLogger(__name__)


@dataclass
class DecayReport:
    """Result of a decay pass."""
    expired: int = 0
    promoted: int = 0
    demoted: int = 0
    expired_ids: List[str] = field(default_factory=list)
    promoted_ids: List[str] = field(default_factory=list)
    demoted_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expired": self.expired,
            "promoted": self.promoted,
            "demoted": self.demoted,
            "expired_ids": self.expired_ids,
            "promoted_ids": self.promoted_ids,
            "demoted_ids": self.demoted_ids,
        }


class MemoryDecay:
    """
    Automatic lifecycle management for memory entries.

    1. Expire memories past their TTL
    2. Score importance (access frequency x recency x confidence)
    3. Promote high-importance SHORT_TERM -> LONG_TERM (semantic)
    4. Demote low-importance LONG_TERM -> archive
    """

    PROMOTION_THRESHOLD = 0.6
    DEMOTION_THRESHOLD = 0.2
    MAX_ACCESS_COUNT = 100

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run_decay(self) -> DecayReport:
        """Run a full decay pass: expire, score, promote, demote."""
        report = DecayReport()

        # Step 1: Expire memories past TTL
        report.expired = self._expire_memories(time.time())

        # Step 2: Score and promote short-term memories
        short_term = self._store.query_memories(
            memory_type=MemoryType.SHORT_TERM, limit=500
        )
        for entry in short_term:
            score = self.score_importance(entry.id)
            if score >= self.PROMOTION_THRESHOLD:
                if self._promote_to_long_term(entry):
                    report.promoted += 1
                    report.promoted_ids.append(entry.id)

        # Step 3: Demote low-importance semantic memories
        semantic = self._store.query_memories(
            memory_type=MemoryType.SEMANTIC, limit=500
        )
        for entry in semantic:
            score = self.score_importance(entry.id)
            if score < self.DEMOTION_THRESHOLD:
                if self._demote_to_archive(entry):
                    report.demoted += 1
                    report.demoted_ids.append(entry.id)

        logger.info(
            "Decay pass: %d expired, %d promoted, %d demoted",
            report.expired, report.promoted, report.demoted,
        )
        return report

    def score_importance(self, memory_id: str) -> float:
        """
        Calculate importance score: 0.0-1.0.

        score = access_count_norm * 0.3 + recency_norm * 0.3 +
                confidence * 0.2 + contradiction_penalty * 0.2
        """
        entry = self._store.get_memory(memory_id)
        if entry is None:
            return 0.0

        now = time.time()

        # Access count normalized (0-1) — MemoryStore doesn't track natively
        access_norm = 0.5  # Default neutral

        # Recency: exponential decay, 7-day half-life
        age_seconds = now - entry.timestamp
        recency_norm = math.exp(-age_seconds / (7 * 86400.0))

        # Confidence (already 0-1)
        confidence = entry.confidence

        # Contradiction penalty
        contradiction_penalty = 1.0
        if entry.contradiction_status and hasattr(entry.contradiction_status, 'value'):
            if entry.contradiction_status.value in ("suspected", "flagged"):
                contradiction_penalty = 0.3

        score = (
            access_norm * 0.3
            + recency_norm * 0.3
            + confidence * 0.2
            + contradiction_penalty * 0.2
        )
        return min(max(score, 0.0), 1.0)

    def consolidate(self, memory_ids: List[str]) -> Optional[str]:
        """Consolidate multiple related memories into a single semantic memory."""
        if len(memory_ids) < 2:
            return None

        entries: List[MemoryEntry] = []
        for mid in memory_ids:
            entry = self._store.get_memory(mid)
            if entry is not None:
                entries.append(entry)

        if len(entries) < 2:
            return None

        # Merge content dicts
        merged_content: Dict[str, Any] = {}
        total_confidence = 0.0
        for entry in entries:
            merged_content.update(entry.content)
            total_confidence += entry.confidence
        avg_confidence = total_confidence / len(entries)

        new_entry = SemanticMemory(
            content=merged_content,
            confidence=avg_confidence,
            provenance=Provenance(
                writer_id="decay_consolidator",
                writer_permissions=["consolidate"],
                source_type=SourceType.INFERENCE,
            ),
        )

        try:
            stored, _ = self._store.write_memory(new_entry)
            if stored:
                logger.info("Consolidated %d memories into %s", len(entries), stored.id)
                return stored.id
            return None
        except Exception as e:
            logger.error("Consolidation failed: %s", e)
            return None

    def _expire_memories(self, current_time: float) -> int:
        """Expire memories past their retention TTL."""
        try:
            return self._store.enforce_retention_policies(current_time)
        except Exception as e:
            logger.warning("Retention enforcement failed: %s", e)
            return 0

    def _promote_to_long_term(self, entry: MemoryEntry) -> bool:
        """Promote a short-term memory to long-term (semantic)."""
        try:
            semantic_entry = SemanticMemory(
                content=entry.content,
                memory_type=MemoryType.SEMANTIC,
                confidence=entry.confidence,
                provenance=entry.provenance,
            )
            stored, _ = self._store.write_memory(semantic_entry)
            if stored:
                self._store.delete_memory(entry.id, soft=True)
                logger.info("Promoted %s -> %s", entry.id, stored.id)
                return True
            return False
        except Exception as e:
            logger.error("Promotion failed for %s: %s", entry.id, e)
            return False

    def _demote_to_archive(self, entry: MemoryEntry) -> bool:
        """Demote a low-importance long-term memory to archive (soft-delete)."""
        try:
            self._store.delete_memory(entry.id, soft=True)
            logger.info("Demoted (archived): %s", entry.id)
            return True
        except Exception as e:
            logger.error("Demotion failed for %s: %s", entry.id, e)
            return False
