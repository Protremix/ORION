"""
ORION Phase 006 — World State Builder. License: Apache 2.0.

Aggregates frame observations into a complete WorldState.
Handles merging, confidence aggregation, and relationship inference.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional

from src.world_model.frame_observer import FrameObservation
from src.world_model.world_state import EntityRelation, WorldEntity, WorldState

logger = logging.getLogger(__name__)


class WorldStateBuilder:
    """
    Builds WorldState from FrameObservations.

    Capabilities:
    - Build from single observation
    - Merge with existing state (update entities, add new, keep stable)
    - Infer relationships between entities based on proximity
    - Aggregate confidence across observations
    """

    def __init__(self, proximity_threshold: float = 5.0, domain: str = "industrial") -> None:
        self._proximity_threshold = proximity_threshold
        self._domain = domain
        self._build_count = 0

    def build(self, observations: List[FrameObservation]) -> WorldState:
        """Build a complete WorldState from multiple observations."""
        start = time.time()

        if not observations:
            return WorldState(domain=self._domain, uncertainty=1.0)

        # Merge all entities (latest wins by timestamp)
        entity_map: Dict[str, WorldEntity] = {}
        environment: Dict[str, Any] = {}
        max_timestamp = 0.0
        total_confidence = 0.0

        for obs in observations:
            for entity in obs.entities:
                existing = entity_map.get(entity.entity_id)
                if existing is None or entity.last_seen > existing.last_seen:
                    entity_map[entity.entity_id] = entity
            if obs.environment:
                environment.update(obs.environment)
            max_timestamp = max(max_timestamp, obs.timestamp)
            total_confidence += obs.confidence

        entities = list(entity_map.values())

        # Infer relationships based on proximity
        relationships = self._infer_relationships(entities, max_timestamp)

        # Also include explicitly observed relationships
        seen_relation_ids = {r.relation_id for r in relationships}
        for obs in observations:
            for rel in obs.relationships:
                if rel.relation_id not in seen_relation_ids:
                    relationships.append(rel)
                    seen_relation_ids.add(rel.relation_id)

        # Aggregate confidence
        avg_confidence = total_confidence / len(observations) if observations else 0.0
        # Uncertainty = 1 - avg confidence
        uncertainty = max(0.0, 1.0 - avg_confidence)

        # Build geometry summary
        geometry = self._build_geometry(entities)

        self._build_count += 1
        elapsed = (time.time() - start) * 1000

        state = WorldState(
            entities=entities,
            relationships=relationships,
            geometry=geometry,
            environment=environment,
            timestamp=max_timestamp,
            uncertainty=uncertainty,
            source="world_state_builder",
            domain=self._domain,
        )

        logger.debug("WorldStateBuilder: %d entities, %d relations, %.1fms",
                     len(entities), len(relationships), elapsed)
        return state

    def merge(self, existing: WorldState, new_obs: FrameObservation) -> WorldState:
        """Merge a new observation into an existing WorldState."""
        start = time.time()

        entity_map: Dict[str, WorldEntity] = {e.entity_id: e for e in existing.entities}

        for entity in new_obs.entities:
            existing_entity = entity_map.get(entity.entity_id)
            if existing_entity is None or entity.last_seen > existing_entity.last_seen:
                entity_map[entity.entity_id] = entity

        entities = list(entity_map.values())
        relationships = self._infer_relationships(entities, new_obs.timestamp)

        # Merge environments
        env = dict(existing.environment)
        env.update(new_obs.environment)

        # Recalculate uncertainty (weight new observation)
        new_weight = 0.3
        merged_uncertainty = (
            existing.uncertainty * (1 - new_weight) + (1 - new_obs.confidence) * new_weight
        )

        geometry = self._build_geometry(entities)

        elapsed = (time.time() - start) * 1000

        state = WorldState(
            entities=entities,
            relationships=relationships,
            geometry=geometry,
            environment=env,
            timestamp=max(existing.timestamp, new_obs.timestamp),
            uncertainty=merged_uncertainty,
            source="world_state_builder_merge",
            domain=existing.domain,
        )

        logger.debug("WorldStateBuilder.merge: %d entities, %.1fms", len(entities), elapsed)
        return state

    def _infer_relationships(self, entities: List[WorldEntity], timestamp: float) -> List[EntityRelation]:
        """Infer spatial relationships based on proximity."""
        relationships: List[EntityRelation] = []

        for i, a in enumerate(entities):
            for j, b in enumerate(entities):
                if i >= j:
                    continue
                dist = self._distance(a.position, b.position)
                if dist < self._proximity_threshold:
                    rel_id = f"rel_{a.entity_id}_{b.entity_id}_near"
                    relationships.append(EntityRelation(
                        relation_id=rel_id,
                        source_id=a.entity_id,
                        target_id=b.entity_id,
                        relation_type="near",
                        strength=max(0.0, 1.0 - dist / self._proximity_threshold),
                        timestamp=timestamp,
                    ))
                # Check if moving toward or away
                if a.velocity and b.velocity:
                    rel_vel = self._relative_velocity(a.velocity, b.velocity)
                    rel_speed = math.sqrt(sum(v * v for v in rel_vel))
                    if rel_speed > 0.5:
                        is_approaching = self._is_approaching(a, b)
                        rel_type = "moving_toward" if is_approaching else "moving_away"
                        rel_id = f"rel_{a.entity_id}_{b.entity_id}_{rel_type}"
                        relationships.append(EntityRelation(
                            relation_id=rel_id,
                            source_id=a.entity_id,
                            target_id=b.entity_id,
                            relation_type=rel_type,
                            strength=min(1.0, rel_speed / 10.0),
                            timestamp=timestamp,
                        ))

        return relationships

    def _distance(self, a: tuple, b: tuple) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def _relative_velocity(self, a: tuple, b: tuple) -> tuple:
        return tuple(x - y for x, y in zip(a, b))

    def _is_approaching(self, a: WorldEntity, b: WorldEntity) -> bool:
        if not a.velocity or not b.velocity:
            return False
        dx = b.position[0] - a.position[0]
        dy = b.position[1] - a.position[1]
        dz = b.position[2] - a.position[2]
        rvx = b.velocity[0] - a.velocity[0]
        rvy = b.velocity[1] - a.velocity[1]
        rvz = b.velocity[2] - a.velocity[2]
        dot = dx * rvx + dy * rvy + dz * rvz
        return dot < 0

    def _build_geometry(self, entities: List[WorldEntity]) -> Dict[str, Any]:
        """Build geometry summary from entities."""
        if not entities:
            return {}
        positions = [e.position for e in entities]
        min_x = min(p[0] for p in positions)
        max_x = max(p[0] for p in positions)
        min_y = min(p[1] for p in positions)
        max_y = max(p[1] for p in positions)
        min_z = min(p[2] for p in positions)
        max_z = max(p[2] for p in positions)
        return {
            "bounds": {
                "min": [min_x, min_y, min_z],
                "max": [max_x, max_y, max_z],
            },
            "entity_count": len(entities),
            "centroid": [
                sum(p[0] for p in positions) / len(positions),
                sum(p[1] for p in positions) / len(positions),
                sum(p[2] for p in positions) / len(positions),
            ],
        }

    def get_statistics(self) -> Dict[str, Any]:
        return {"total_builds": self._build_count}
