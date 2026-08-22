"""
ORION Phase 006 — World State data structures. License: Apache 2.0.

WorldEntity, EntityRelation, WorldState — the structured representation
of the observed world used by FrameObserver, WorldStateBuilder, ChangeDetector.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class WorldEntity:
    """A detected entity in the world (object, person, vehicle, sensor, zone)."""
    entity_id: str
    entity_type: str  # object, person, vehicle, sensor, zone
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: Optional[Tuple[float, float, float]] = None
    orientation: float = 0.0  # radians
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0  # [0, 1]
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "position": list(self.position),
            "velocity": list(self.velocity) if self.velocity else None,
            "orientation": self.orientation,
            "properties": self.properties,
            "confidence": self.confidence,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> WorldEntity:
        pos = d.get("position", [0, 0, 0])
        vel = d.get("velocity")
        return cls(
            entity_id=d["entity_id"],
            entity_type=d["entity_type"],
            position=tuple(pos) if isinstance(pos, list) else pos,
            velocity=tuple(vel) if isinstance(vel, list) else vel,
            orientation=d.get("orientation", 0.0),
            properties=d.get("properties", {}),
            confidence=d.get("confidence", 1.0),
            last_seen=d.get("last_seen", time.time()),
        )


@dataclass
class EntityRelation:
    """A relationship between two entities."""
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str  # near, far, facing, moving_toward, moving_away, contains, part_of
    strength: float = 1.0  # [0, 1]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "strength": self.strength,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> EntityRelation:
        return cls(
            relation_id=d["relation_id"],
            source_id=d["source_id"],
            target_id=d["target_id"],
            relation_type=d["relation_type"],
            strength=d.get("strength", 1.0),
            timestamp=d.get("timestamp", time.time()),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EntityRelation):
            return NotImplemented
        return (
            self.source_id == other.source_id
            and self.target_id == other.target_id
            and self.relation_type == other.relation_type
        )

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.relation_type))


@dataclass
class WorldState:
    """
    Complete world state at a point in time.
    Includes entities, relationships, geometry, environment, uncertainty.
    """
    entities: List[WorldEntity] = field(default_factory=list)
    relationships: List[EntityRelation] = field(default_factory=list)
    geometry: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    uncertainty: float = 0.0  # [0, 1] — 0 = certain, 1 = no idea
    source: str = "observer"
    domain: str = "industrial"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
            "geometry": self.geometry,
            "environment": self.environment,
            "timestamp": self.timestamp,
            "uncertainty": self.uncertainty,
            "source": self.source,
            "domain": self.domain,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> WorldState:
        return cls(
            entities=[WorldEntity.from_dict(e) for e in d.get("entities", [])],
            relationships=[EntityRelation.from_dict(r) for r in d.get("relationships", [])],
            geometry=d.get("geometry", {}),
            environment=d.get("environment", {}),
            timestamp=d.get("timestamp", time.time()),
            uncertainty=d.get("uncertainty", 0.0),
            source=d.get("source", "observer"),
            domain=d.get("domain", "industrial"),
        )

    def get_entity(self, entity_id: str) -> Optional[WorldEntity]:
        for e in self.entities:
            if e.entity_id == entity_id:
                return e
        return None

    def to_state_snapshot(self) -> Any:
        """Bridge to existing WorldModel StateSnapshot."""
        from src.world_model import StateSnapshot

        entities_dict = {e.entity_id: e.to_dict() for e in self.entities}
        return StateSnapshot(
            timestamp=self.timestamp,
            domain=self.domain,
            entities=entities_dict,
            sensors={},
            safety_status="safe",
            metadata={
                "uncertainty": self.uncertainty,
                "source": self.source,
                "relationship_count": len(self.relationships),
            },
        )
