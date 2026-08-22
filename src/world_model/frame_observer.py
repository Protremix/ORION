"""
ORION Phase 006 — Frame Observer. License: Apache 2.0.

Extracts structured observations from raw frame data.
In simulation mode, frame data is a structured dict.
Future hardware phases will replace with actual perception models.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.world_model.world_state import EntityRelation, WorldEntity

logger = logging.getLogger(__name__)


@dataclass
class FrameObservation:
    """Observation extracted from a single frame."""
    entities: List[WorldEntity] = field(default_factory=list)
    relationships: List[EntityRelation] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    frame_id: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
            "environment": self.environment,
            "timestamp": self.timestamp,
            "frame_id": self.frame_id,
            "confidence": self.confidence,
        }


class FrameObserver:
    """
    Observes frames and extracts structured world observations.

    In simulation mode, frame_data is a dict with keys:
    - "entities": list of entity dicts (id, type, position, velocity, properties, confidence)
    - "relationships": optional list of relation dicts
    - "environment": optional dict of environment properties
    - "timestamp": optional float
    - "frame_id": optional string
    """

    def __init__(self, confidence_threshold: float = 0.3) -> None:
        self._confidence_threshold = confidence_threshold
        self._observation_count = 0

    def observe(self, frame_data: Dict[str, Any]) -> FrameObservation:
        """Extract observation from a single frame."""
        start = time.time()

        entities: List[WorldEntity] = []
        for entity_data in frame_data.get("entities", []):
            try:
                entity = WorldEntity.from_dict(entity_data)
                if entity.confidence >= self._confidence_threshold:
                    entities.append(entity)
            except (KeyError, TypeError) as e:
                logger.warning("Failed to parse entity: %s", e)

        relationships: List[EntityRelation] = []
        for rel_data in frame_data.get("relationships", []):
            try:
                relationships.append(EntityRelation.from_dict(rel_data))
            except (KeyError, TypeError) as e:
                logger.warning("Failed to parse relation: %s", e)

        environment = frame_data.get("environment", {})
        timestamp = frame_data.get("timestamp", time.time())
        frame_id = frame_data.get("frame_id", f"frame_{self._observation_count}")
        confidence = frame_data.get("confidence", 1.0)

        self._observation_count += 1
        elapsed = (time.time() - start) * 1000

        obs = FrameObservation(
            entities=entities,
            relationships=relationships,
            environment=environment,
            timestamp=timestamp,
            frame_id=frame_id,
            confidence=confidence,
        )

        logger.debug("FrameObserver: %d entities, %d relations, %.1fms",
                     len(entities), len(relationships), elapsed)
        return obs

    def observe_batch(self, frames: List[Dict[str, Any]]) -> List[FrameObservation]:
        """Observe multiple frames."""
        return [self.observe(frame) for frame in frames]

    def get_statistics(self) -> Dict[str, Any]:
        return {"total_observations": self._observation_count}
