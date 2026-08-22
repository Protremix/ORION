"""
ORION Phase 005 — World State Manager. License: Apache 2.0

Maintains a structured snapshot of the current world state derived from
memory entries. Updated after each REMEMBER step.

World state structure:
{
    "entities": {id: {properties, confidence, last_updated}},
    "relations": [(from, to, type, confidence)],
    "timestamps": {key: float},
    "confidence_scores": {key: float}
}
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.memory.memory_system import MemoryEntry, MemoryStore, MemoryType

logger = logging.getLogger(__name__)


@dataclass
class StateDiff:
    """Difference between two world state snapshots."""
    added: Dict[str, Any] = field(default_factory=dict)
    modified: Dict[str, Any] = field(default_factory=dict)
    removed: List[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "added": self.added,
            "modified": self.modified,
            "removed": self.removed,
            "timestamp": self.timestamp,
        }

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.removed)


class WorldStateManager:
    """
    Maintains a structured snapshot of the current world state.

    The world state is derived from episodic and semantic memory entries.
    Updated after each REMEMBER step in the CoreSupervisor lifecycle.
    """

    def __init__(self, store: MemoryStore) -> None:
        self._store = store
        self._current_state: Dict[str, Any] = {
            "entities": {},
            "relations": [],
            "timestamps": {},
            "confidence_scores": {},
        }
        self._state_history: List[Tuple[float, Dict[str, Any]]] = []

    def get_current_state(self) -> Dict[str, Any]:
        """Return current world state snapshot."""
        return dict(self._current_state)

    def update_state(self, observation: Dict[str, Any]) -> StateDiff:
        """
        Apply observation to world state. Returns diff of what changed.

        Observation should contain:
        - 'entities': dict of entity_id -> properties
        - 'relations': list of (from, to, type) tuples
        - 'confidence': optional float
        """
        diff = StateDiff(timestamp=time.time())
        now = time.time()

        # Update entities
        entities = observation.get("entities", {})
        for entity_id, props in entities.items():
            if entity_id not in self._current_state["entities"]:
                # New entity
                self._current_state["entities"][entity_id] = {
                    "properties": props,
                    "confidence": observation.get("confidence", 1.0),
                    "last_updated": now,
                }
                diff.added[entity_id] = props
            else:
                # Existing entity — check if modified
                existing = self._current_state["entities"][entity_id]
                if existing["properties"] != props:
                    self._current_state["entities"][entity_id] = {
                        "properties": props,
                        "confidence": observation.get("confidence",
                                                       existing.get("confidence", 1.0)),
                        "last_updated": now,
                    }
                    diff.modified[entity_id] = props

        # Update relations
        relations = observation.get("relations", [])
        for rel in relations:
            if isinstance(rel, (list, tuple)) and len(rel) >= 3:
                rel_tuple = (rel[0], rel[1], rel[2])
                if rel_tuple not in self._current_state["relations"]:
                    self._current_state["relations"].append(rel_tuple)

        # Update timestamps
        for key in entities:
            self._current_state["timestamps"][key] = now

        # Update confidence scores
        for entity_id, props in entities.items():
            self._current_state["confidence_scores"][entity_id] = \
                observation.get("confidence", 1.0)

        # Record state in history if there are changes
        if diff.has_changes:
            self._state_history.append((now, dict(self._current_state)))
            # Keep history bounded (last 1000 states)
            if len(self._state_history) > 1000:
                self._state_history = self._state_history[-1000:]

        logger.info("World state updated: %d added, %d modified, %d removed",
                    len(diff.added), len(diff.modified), len(diff.removed))
        return diff

    def get_state_history(self, key: str, n: int = 10) -> List[Dict[str, Any]]:
        """Return history of state changes for a given entity key."""
        history: List[Dict[str, Any]] = []
        for timestamp, state in (reversed(self._state_history[-n * 10:]) if self._state_history else []):
            entities = state.get("entities", {})
            if key in entities:
                history.append({
                    "timestamp": timestamp,
                    "properties": entities[key].get("properties", {}),
                    "confidence": entities[key].get("confidence", 0),
                })
            if len(history) >= n:
                break
        return history

    def get_state_at(self, timestamp: float) -> Dict[str, Any]:
        """Reconstruct world state at a given timestamp."""
        result: Optional[Dict[str, Any]] = None
        for ts, state in self._state_history:
            if ts <= timestamp:
                result = state
            else:
                break
        return result if result else dict(self._current_state)

    def rebuild_from_memory(self) -> Dict[str, Any]:
        """
        Rebuild world state from all episodic and semantic memories.
        Useful for recovery after restart.
        """
        self._current_state = {
            "entities": {},
            "relations": [],
            "timestamps": {},
            "confidence_scores": {},
        }

        # Rebuild from episodic memories
        episodic = self._store.query_memories(
            memory_type=MemoryType.EPISODIC, limit=500
        )
        for entry in episodic:
            content = entry.content if isinstance(entry.content, dict) else {}
            self.update_state(content)

        # Rebuild from semantic memories
        semantic = self._store.query_memories(
            memory_type=MemoryType.SEMANTIC, limit=500
        )
        for entry in semantic:
            content = entry.content if isinstance(entry.content, dict) else {}
            self.update_state(content)

        logger.info("World state rebuilt: %d entities, %d relations",
                    len(self._current_state["entities"]),
                    len(self._current_state["relations"]))
        return dict(self._current_state)
