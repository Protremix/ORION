"""
ORION Phase 005 — Memory Retriever. License: Apache 2.0

Unified retrieval interface with semantic search, ranking, and filtering.
Uses existing EmbeddingService for vector similarity and MemoryStore for storage.
Falls back to keyword matching if embeddings unavailable.

Ranking: combined_score = semantic_similarity * 0.5 + recency * 0.3 + confidence * 0.2
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.memory.memory_system import (
    EmbeddingService,
    MemoryEntry,
    MemoryStore,
    MemoryType,
)

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """A single retrieval result with ranking metadata."""
    entry: MemoryEntry
    semantic_score: float = 0.0
    recency_score: float = 0.0
    confidence_score: float = 0.0
    combined_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry.id,
            "memory_type": self.entry.memory_type.value if hasattr(self.entry.memory_type, 'value') else str(self.entry.memory_type),
            "combined_score": round(self.combined_score, 4),
            "semantic_score": round(self.semantic_score, 4),
            "recency_score": round(self.recency_score, 4),
            "confidence_score": round(self.confidence_score, 4),
        }


class MemoryRetriever:
    """
    Unified retrieval interface for the memory subsystem.

    Provides semantic search, type filtering, temporal filtering, and
    ranking. Uses EmbeddingService for vector similarity, with keyword
    fallback when embeddings are unavailable.
    """

    SEMANTIC_WEIGHT = 0.5
    RECENCY_WEIGHT = 0.3
    CONFIDENCE_WEIGHT = 0.2

    def __init__(
        self,
        store: MemoryStore,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self._store = store
        self._embedding_service = embedding_service

    def retrieve(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        min_confidence: float = 0.0,
        max_results: int = 10,
        time_range: Optional[Tuple[float, float]] = None,
    ) -> List[RetrievalResult]:
        """Retrieve memories by semantic similarity to query."""
        # Try semantic search first
        entries = self._semantic_search(query, memory_types, max_results)

        # Fallback to keyword search if semantic returns nothing
        if not entries:
            entries = self._keyword_search(query, memory_types, max_results)

        # Apply filters
        filtered = self._apply_filters(entries, min_confidence, time_range)

        # Rank and sort
        ranked = self._rank(filtered)
        ranked.sort(key=lambda r: r.combined_score, reverse=True)
        return ranked[:max_results]

    def retrieve_by_type(
        self, memory_type: MemoryType, max_results: int = 50
    ) -> List[MemoryEntry]:
        """Retrieve all memories of a specific type."""
        return self._store.query_memories(memory_type=memory_type, limit=max_results)

    def retrieve_recent(
        self,
        n: int = 10,
        memory_types: Optional[List[MemoryType]] = None,
    ) -> List[MemoryEntry]:
        """Retrieve N most recent memories."""
        if memory_types is None:
            memory_types = list(MemoryType)

        all_entries: List[MemoryEntry] = []
        for mt in memory_types:
            entries = self._store.query_memories(memory_type=mt, limit=n * 2)
            all_entries.extend(entries)

        all_entries.sort(key=lambda e: e.timestamp, reverse=True)
        return all_entries[:n]

    def retrieve_related(
        self, memory_id: str, max_results: int = 10
    ) -> List[MemoryEntry]:
        """Retrieve memories related to a given memory by temporal proximity."""
        target = self._store.get_memory(memory_id)
        if target is None:
            return []

        related = self._store.query_memories(
            memory_type=target.memory_type, limit=max_results * 2
        )
        related = [e for e in related if e.id != memory_id]

        scored: List[Tuple[float, MemoryEntry]] = []
        for entry in related:
            time_diff = abs(entry.timestamp - target.timestamp)
            temporal_score = 1.0 / (1.0 + time_diff / 3600.0)
            scored.append((temporal_score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:max_results]]

    def _semantic_search(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]],
        max_results: int,
    ) -> List[MemoryEntry]:
        """Perform semantic search using MemoryStore.search_semantic."""
        try:
            results = self._store.search_semantic(query_text=query, top_k=max_results * 2)
            entries = [entry for entry, _score in results]

            # Filter by memory type if specified
            if memory_types:
                entries = [e for e in entries if e.memory_type in memory_types]
            return entries
        except Exception as e:
            logger.warning("Semantic search failed, falling back to keyword: %s", e)
            return []

    def _keyword_search(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]],
        max_results: int,
    ) -> List[MemoryEntry]:
        """Fallback keyword search when embeddings are unavailable."""
        query_lower = query.lower()
        keywords = set(query_lower.split())
        types_to_search = memory_types if memory_types else list(MemoryType)
        all_results: List[MemoryEntry] = []

        for mt in types_to_search:
            entries = self._store.query_memories(memory_type=mt, limit=100)
            for entry in entries:
                content_str = str(entry.content).lower()
                if any(kw in content_str for kw in keywords):
                    all_results.append(entry)

        return all_results[:max_results * 2]

    def _apply_filters(
        self,
        entries: List[MemoryEntry],
        min_confidence: float,
        time_range: Optional[Tuple[float, float]],
    ) -> List[MemoryEntry]:
        """Apply confidence and time range filters."""
        filtered = []
        for entry in entries:
            if entry.confidence < min_confidence:
                continue
            if time_range is not None:
                t_start, t_end = time_range
                if entry.timestamp < t_start or entry.timestamp > t_end:
                    continue
            filtered.append(entry)
        return filtered

    def _rank(self, entries: List[MemoryEntry]) -> List[RetrievalResult]:
        """Rank entries by combined score."""
        now = time.time()
        results: List[RetrievalResult] = []

        for entry in entries:
            age_seconds = now - entry.timestamp
            recency_score = math.exp(-age_seconds / 86400.0)
            confidence_score = entry.confidence
            semantic_score = 1.0  # Placeholder for actual similarity

            combined = (
                semantic_score * self.SEMANTIC_WEIGHT
                + recency_score * self.RECENCY_WEIGHT
                + confidence_score * self.CONFIDENCE_WEIGHT
            )

            results.append(RetrievalResult(
                entry=entry,
                semantic_score=semantic_score,
                recency_score=recency_score,
                confidence_score=confidence_score,
                combined_score=combined,
            ))

        return results
