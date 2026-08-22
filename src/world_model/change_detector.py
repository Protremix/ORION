"""
ORION Phase 006 — Change Detector. License: Apache 2.0.

Compares two WorldStates and identifies what changed.
Produces a structured ChangeReport with added, removed, modified entities,
relationship changes, and environment changes.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.world_model.world_state import EntityRelation, WorldEntity, WorldState

logger = logging.getLogger(__name__)


@dataclass
class EntityChange:
    """A change to an existing entity."""
    entity_id: str
    field_name: str  # position, velocity, orientation, properties, confidence
    old_value: Any
    new_value: Any
    delta: Any = None  # computed delta for numeric fields

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "delta": self.delta,
        }


@dataclass
class ChangeReport:
    """Structured diff between two WorldStates."""
    added: List[WorldEntity] = field(default_factory=list)
    removed: List[WorldEntity] = field(default_factory=list)
    modified: List[EntityChange] = field(default_factory=list)
    relationships_changed: List[EntityRelation] = field(default_factory=list)
    environment_changed: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    summary: str = ""
    significant: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "added": [e.to_dict() for e in self.added],
            "removed": [e.to_dict() for e in self.removed],
            "modified": [c.to_dict() for c in self.modified],
            "relationships_changed": [r.to_dict() for r in self.relationships_changed],
            "environment_changed": {k: [v[0], v[1]] for k, v in self.environment_changed.items()},
            "summary": self.summary,
            "significant": self.significant,
        }

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.modified or
                     self.relationships_changed or self.environment_changed)


class ChangeDetector:
    """
    Detects changes between sequential WorldStates.

    Identifies:
    - Added entities (in current, not in previous)
    - Removed entities (in previous, not in current)
    - Modified entities (position, velocity, orientation, properties changed)
    - Relationship changes (new, removed, or modified relations)
    - Environment changes (temperature, lighting, etc.)
    """

    def __init__(self, position_threshold: float = 0.5,
                 confidence_threshold: float = 0.1,
                 significance_threshold: int = 1) -> None:
        self._position_threshold = position_threshold
        self._confidence_threshold = confidence_threshold
        self._significance_threshold = significance_threshold
        self._detection_count = 0

    def detect(self, previous: WorldState, current: WorldState) -> ChangeReport:
        """Compare two WorldStates and return a ChangeReport."""
        start = time.time()

        prev_entities = {e.entity_id: e for e in previous.entities}
        curr_entities = {e.entity_id: e for e in current.entities}

        # Added entities
        added_ids = set(curr_entities.keys()) - set(prev_entities.keys())
        added = [curr_entities[eid] for eid in added_ids]

        # Removed entities
        removed_ids = set(prev_entities.keys()) - set(curr_entities.keys())
        removed = [prev_entities[eid] for eid in removed_ids]

        # Modified entities
        modified: List[EntityChange] = []
        common_ids = set(curr_entities.keys()) & set(prev_entities.keys())
        for eid in common_ids:
            old_e = prev_entities[eid]
            new_e = curr_entities[eid]

            # Position change
            pos_delta = self._position_delta(old_e.position, new_e.position)
            if pos_delta > self._position_threshold:
                modified.append(EntityChange(
                    entity_id=eid,
                    field_name="position",
                    old_value=list(old_e.position),
                    new_value=list(new_e.position),
                    delta=pos_delta,
                ))

            # Velocity change
            if old_e.velocity != new_e.velocity:
                modified.append(EntityChange(
                    entity_id=eid,
                    field_name="velocity",
                    old_value=list(old_e.velocity) if old_e.velocity else None,
                    new_value=list(new_e.velocity) if new_e.velocity else None,
                ))

            # Orientation change
            if abs(old_e.orientation - new_e.orientation) > 0.1:
                modified.append(EntityChange(
                    entity_id=eid,
                    field_name="orientation",
                    old_value=old_e.orientation,
                    new_value=new_e.orientation,
                    delta=abs(new_e.orientation - old_e.orientation),
                ))

            # Properties change
            if old_e.properties != new_e.properties:
                modified.append(EntityChange(
                    entity_id=eid,
                    field_name="properties",
                    old_value=old_e.properties,
                    new_value=new_e.properties,
                ))

            # Confidence change
            if abs(old_e.confidence - new_e.confidence) > self._confidence_threshold:
                modified.append(EntityChange(
                    entity_id=eid,
                    field_name="confidence",
                    old_value=old_e.confidence,
                    new_value=new_e.confidence,
                    delta=abs(new_e.confidence - old_e.confidence),
                ))

        # Relationship changes
        prev_rels = {r.relation_id: r for r in previous.relationships}
        curr_rels = {r.relation_id: r for r in current.relationships}
        changed_rel_ids = set(curr_rels.keys()) - set(prev_rels.keys())
        removed_rel_ids = set(prev_rels.keys()) - set(curr_rels.keys())
        relationships_changed = [curr_rels[rid] for rid in changed_rel_ids]
        relationships_changed.extend([prev_rels[rid] for rid in removed_rel_ids])

        # Environment changes
        env_changed: Dict[str, Tuple[Any, Any]] = {}
        all_env_keys = set(previous.environment.keys()) | set(current.environment.keys())
        for key in all_env_keys:
            old_val = previous.environment.get(key)
            new_val = current.environment.get(key)
            if old_val != new_val:
                env_changed[key] = (old_val, new_val)

        # Determine significance
        change_count = len(added) + len(removed) + len(modified) + len(relationships_changed) + len(env_changed)
        significant = change_count >= self._significance_threshold

        # Build summary
        parts: List[str] = []
        if added:
            parts.append(f"{len(added)} added")
        if removed:
            parts.append(f"{len(removed)} removed")
        if modified:
            parts.append(f"{len(modified)} modified")
        if relationships_changed:
            parts.append(f"{len(relationships_changed)} relationship changes")
        if env_changed:
            parts.append(f"{len(env_changed)} environment changes")
        summary = ", ".join(parts) if parts else "No changes detected"

        self._detection_count += 1
        elapsed = (time.time() - start) * 1000

        report = ChangeReport(
            added=added,
            removed=removed,
            modified=modified,
            relationships_changed=relationships_changed,
            environment_changed=env_changed,
            summary=summary,
            significant=significant,
        )

        logger.debug("ChangeDetector: %s, %.1fms", summary, elapsed)
        return report

    def detect_batch(self, states: List[WorldState]) -> List[ChangeReport]:
        """Detect changes across a sequence of WorldStates."""
        if len(states) < 2:
            return []
        return [self.detect(states[i], states[i + 1]) for i in range(len(states) - 1)]

    def _position_delta(self, a: tuple, b: tuple) -> float:
        import math
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def get_statistics(self) -> Dict[str, Any]:
        return {"total_detections": self._detection_count}
