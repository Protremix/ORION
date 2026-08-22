"""
ORION Phase 006 — World Model Test Suite. License: Apache 2.0.

Tests: FrameObserver, WorldStateBuilder, ChangeDetector, WorldEntity, EntityRelation, WorldState
Integration: multi-frame observation → change detection, memory persistence, WorldModel bridge
"""
from __future__ import annotations

import time

import pytest

from src.world_model.change_detector import ChangeDetector, ChangeReport
from src.world_model.frame_observer import FrameObservation, FrameObserver
from src.world_model.world_state import EntityRelation, WorldEntity, WorldState
from src.world_model.world_state_builder import WorldStateBuilder

# ============================================================================
# WorldEntity Tests
# ============================================================================

class TestWorldEntity:
    def test_construction(self):
        e = WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))
        assert e.entity_id == "e1"
        assert e.entity_type == "object"
        assert e.position == (1, 2, 3)
        assert e.confidence == 1.0

    def test_to_dict(self):
        e = WorldEntity(entity_id="e1", entity_type="vehicle", position=(1, 2, 3),
                        velocity=(0.5, 0, 0), orientation=1.5, properties={"color": "red"})
        d = e.to_dict()
        assert d["entity_id"] == "e1"
        assert d["position"] == [1, 2, 3]
        assert d["velocity"] == [0.5, 0, 0]
        assert d["orientation"] == 1.5
        assert d["properties"]["color"] == "red"

    def test_from_dict(self):
        d = {"entity_id": "e2", "entity_type": "person", "position": [4, 5, 6],
             "confidence": 0.8}
        e = WorldEntity.from_dict(d)
        assert e.entity_id == "e2"
        assert e.entity_type == "person"
        assert e.position == (4, 5, 6)
        assert e.confidence == 0.8

    def test_from_dict_with_velocity(self):
        d = {"entity_id": "e3", "entity_type": "vehicle", "position": [0, 0, 0],
             "velocity": [1.0, 2.0, 3.0]}
        e = WorldEntity.from_dict(d)
        assert e.velocity == (1.0, 2.0, 3.0)

    def test_equality(self):
        e1 = WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))
        e2 = WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))
        assert e1.entity_id == e2.entity_id
        assert e1.entity_type == e2.entity_type
        assert e1.position == e2.position


# ============================================================================
# EntityRelation Tests
# ============================================================================

class TestEntityRelation:
    def test_construction(self):
        r = EntityRelation(relation_id="r1", source_id="e1", target_id="e2",
                           relation_type="near", strength=0.7)
        assert r.relation_id == "r1"
        assert r.source_id == "e1"
        assert r.target_id == "e2"
        assert r.relation_type == "near"
        assert r.strength == 0.7

    def test_to_dict(self):
        r = EntityRelation(relation_id="r1", source_id="e1", target_id="e2",
                           relation_type="facing")
        d = r.to_dict()
        assert d["relation_id"] == "r1"
        assert d["source_id"] == "e1"
        assert d["relation_type"] == "facing"

    def test_from_dict(self):
        d = {"relation_id": "r2", "source_id": "a", "target_id": "b",
             "relation_type": "contains", "strength": 0.5}
        r = EntityRelation.from_dict(d)
        assert r.relation_id == "r2"
        assert r.strength == 0.5

    def test_equality(self):
        r1 = EntityRelation(relation_id="r1", source_id="a", target_id="b", relation_type="near")
        r2 = EntityRelation(relation_id="r2", source_id="a", target_id="b", relation_type="near")
        assert r1 == r2  # equality by source, target, type

    def test_hash(self):
        r1 = EntityRelation(relation_id="r1", source_id="a", target_id="b", relation_type="near")
        assert hash(r1) is not None


# ============================================================================
# WorldState Tests
# ============================================================================

class TestWorldState:
    def test_construction(self):
        ws = WorldState()
        assert ws.entities == []
        assert ws.relationships == []
        assert ws.uncertainty == 0.0
        assert ws.domain == "industrial"

    def test_to_dict(self):
        e = WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))
        ws = WorldState(entities=[e], environment={"temp": 22.0})
        d = ws.to_dict()
        assert len(d["entities"]) == 1
        assert d["environment"]["temp"] == 22.0

    def test_from_dict(self):
        d = {
            "entities": [{"entity_id": "e1", "entity_type": "object", "position": [1, 2, 3]}],
            "environment": {"temp": 25.0},
            "uncertainty": 0.3,
            "domain": "vehicle",
        }
        ws = WorldState.from_dict(d)
        assert len(ws.entities) == 1
        assert ws.environment["temp"] == 25.0
        assert ws.uncertainty == 0.3
        assert ws.domain == "vehicle"

    def test_get_entity(self):
        e = WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))
        ws = WorldState(entities=[e])
        assert ws.get_entity("e1") == e
        assert ws.get_entity("nonexistent") is None

    def test_to_state_snapshot(self):
        e = WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))
        ws = WorldState(entities=[e], domain="vehicle")
        snap = ws.to_state_snapshot()
        assert snap.domain == "vehicle"
        assert "e1" in snap.entities


# ============================================================================
# FrameObserver Tests
# ============================================================================

class TestFrameObserver:
    def test_observe_single_frame(self):
        obs = FrameObserver()
        frame = {"entities": [{"entity_id": "e1", "entity_type": "object",
                                "position": [1, 2, 3], "confidence": 0.9}]}
        result = obs.observe(frame)
        assert len(result.entities) == 1
        assert result.entities[0].entity_id == "e1"

    def test_observe_multiple_entities(self):
        obs = FrameObserver()
        frame = {"entities": [
            {"entity_id": "e1", "entity_type": "object", "position": [1, 2, 3]},
            {"entity_id": "e2", "entity_type": "person", "position": [4, 5, 6]},
            {"entity_id": "e3", "entity_type": "vehicle", "position": [7, 8, 9]},
        ]}
        result = obs.observe(frame)
        assert len(result.entities) == 3

    def test_observe_empty_frame(self):
        obs = FrameObserver()
        result = obs.observe({})
        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    def test_observe_malformed_frame(self):
        obs = FrameObserver()
        frame = {"entities": [{"entity_id": "e1"}]}  # missing type
        result = obs.observe(frame)
        # Malformed entity should be skipped, not crash
        assert len(result.entities) == 0

    def test_observe_batch(self):
        obs = FrameObserver()
        frames = [
            {"entities": [{"entity_id": "e1", "entity_type": "object", "position": [0, 0, 0]}]},
            {"entities": [{"entity_id": "e2", "entity_type": "person", "position": [1, 1, 1]}]},
        ]
        results = obs.observe_batch(frames)
        assert len(results) == 2
        assert results[0].entities[0].entity_id == "e1"
        assert results[1].entities[0].entity_id == "e2"

    def test_observe_with_environment(self):
        obs = FrameObserver()
        frame = {"entities": [], "environment": {"temperature": 22.5, "lighting": "bright"}}
        result = obs.observe(frame)
        assert result.environment["temperature"] == 22.5
        assert result.environment["lighting"] == "bright"

    def test_observe_with_relationships(self):
        obs = FrameObserver()
        frame = {"entities": [
            {"entity_id": "e1", "entity_type": "object", "position": [0, 0, 0]},
            {"entity_id": "e2", "entity_type": "object", "position": [1, 0, 0]},
        ], "relationships": [
            {"relation_id": "r1", "source_id": "e1", "target_id": "e2", "relation_type": "near"}
        ]}
        result = obs.observe(frame)
        assert len(result.relationships) == 1
        assert result.relationships[0].relation_type == "near"

    def test_confidence_threshold_filters_low(self):
        obs = FrameObserver(confidence_threshold=0.5)
        frame = {"entities": [
            {"entity_id": "e1", "entity_type": "object", "position": [0, 0, 0], "confidence": 0.3},
            {"entity_id": "e2", "entity_type": "object", "position": [1, 0, 0], "confidence": 0.9},
        ]}
        result = obs.observe(frame)
        assert len(result.entities) == 1
        assert result.entities[0].entity_id == "e2"


# ============================================================================
# WorldStateBuilder Tests
# ============================================================================

class TestWorldStateBuilder:
    def test_build_from_single_observation(self):
        builder = WorldStateBuilder()
        obs = FrameObservation(
            entities=[WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))],
            environment={"temp": 22.0},
        )
        ws = builder.build([obs])
        assert len(ws.entities) == 1
        assert ws.environment["temp"] == 22.0

    def test_build_from_multiple_observations(self):
        builder = WorldStateBuilder()
        obs1 = FrameObservation(
            entities=[WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))],
        )
        obs2 = FrameObservation(
            entities=[WorldEntity(entity_id="e2", entity_type="person", position=(4, 5, 6))],
        )
        ws = builder.build([obs1, obs2])
        assert len(ws.entities) == 2

    def test_build_empty_observations(self):
        builder = WorldStateBuilder()
        ws = builder.build([])
        assert len(ws.entities) == 0
        assert ws.uncertainty == 1.0

    def test_build_infers_proximity_relationships(self):
        builder = WorldStateBuilder(proximity_threshold=5.0)
        obs = FrameObservation(
            entities=[
                WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0)),
                WorldEntity(entity_id="e2", entity_type="object", position=(1, 0, 0)),
            ],
        )
        ws = builder.build([obs])
        assert len(ws.relationships) >= 1
        assert ws.relationships[0].relation_type == "near"

    def test_build_confidence_aggregation(self):
        builder = WorldStateBuilder()
        obs = FrameObservation(
            entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))],
            confidence=0.8,
        )
        ws = builder.build([obs])
        assert 0.0 <= ws.uncertainty <= 1.0
        assert ws.uncertainty == pytest.approx(0.2, abs=0.01)

    def test_merge_existing_with_new(self):
        builder = WorldStateBuilder()
        existing = WorldState(
            entities=[WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))],
            environment={"temp": 20.0},
        )
        new_obs = FrameObservation(
            entities=[
                WorldEntity(entity_id="e1", entity_type="object", position=(5, 2, 3)),
                WorldEntity(entity_id="e2", entity_type="person", position=(0, 0, 0)),
            ],
            environment={"temp": 25.0},
            confidence=0.9,
        )
        merged = builder.merge(existing, new_obs)
        assert len(merged.entities) == 2
        assert merged.environment["temp"] == 25.0  # new overwrites

    def test_build_geometry_summary(self):
        builder = WorldStateBuilder()
        obs = FrameObservation(
            entities=[
                WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0)),
                WorldEntity(entity_id="e2", entity_type="object", position=(10, 10, 10)),
            ],
        )
        ws = builder.build([obs])
        assert "bounds" in ws.geometry
        assert ws.geometry["entity_count"] == 2
        assert "centroid" in ws.geometry

    def test_build_includes_explicit_relationships(self):
        builder = WorldStateBuilder()
        rel = EntityRelation(relation_id="r1", source_id="e1", target_id="e2",
                            relation_type="contains")
        obs = FrameObservation(
            entities=[
                WorldEntity(entity_id="e1", entity_type="zone", position=(0, 0, 0)),
                WorldEntity(entity_id="e2", entity_type="object", position=(100, 0, 0)),
            ],
            relationships=[rel],
        )
        ws = builder.build([obs])
        # Explicit relationship should be included even if far apart
        rel_types = [r.relation_type for r in ws.relationships]
        assert "contains" in rel_types


# ============================================================================
# ChangeDetector Tests
# ============================================================================

class TestChangeDetector:
    def test_detect_added_entity(self):
        detector = ChangeDetector()
        prev = WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))])
        curr = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0)),
            WorldEntity(entity_id="e2", entity_type="person", position=(1, 0, 0)),
        ])
        report = detector.detect(prev, curr)
        assert len(report.added) == 1
        assert report.added[0].entity_id == "e2"

    def test_detect_removed_entity(self):
        detector = ChangeDetector()
        prev = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0)),
            WorldEntity(entity_id="e2", entity_type="person", position=(1, 0, 0)),
        ])
        curr = WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))])
        report = detector.detect(prev, curr)
        assert len(report.removed) == 1
        assert report.removed[0].entity_id == "e2"

    def test_detect_modified_position(self):
        detector = ChangeDetector(position_threshold=0.1)
        prev = WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))])
        curr = WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(5, 0, 0))])
        report = detector.detect(prev, curr)
        assert len(report.modified) >= 1
        mod = [m for m in report.modified if m.field_name == "position"]
        assert len(mod) == 1
        assert mod[0].delta > 0.1

    def test_detect_no_changes(self):
        detector = ChangeDetector()
        prev = WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))])
        curr = WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))])
        report = detector.detect(prev, curr)
        assert not report.has_changes
        assert "No changes" in report.summary
        assert not report.significant

    def test_detect_relationship_changes(self):
        detector = ChangeDetector()
        prev = WorldState(
            entities=[
                WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0)),
                WorldEntity(entity_id="e2", entity_type="object", position=(100, 0, 0)),
            ],
            relationships=[],
        )
        curr = WorldState(
            entities=[
                WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0)),
                WorldEntity(entity_id="e2", entity_type="object", position=(1, 0, 0)),
            ],
            relationships=[EntityRelation(relation_id="r1", source_id="e1",
                                         target_id="e2", relation_type="near")],
        )
        report = detector.detect(prev, curr)
        assert len(report.relationships_changed) >= 1

    def test_detect_environment_changes(self):
        detector = ChangeDetector()
        prev = WorldState(environment={"temperature": 20.0, "lighting": "bright"})
        curr = WorldState(environment={"temperature": 25.0, "lighting": "bright"})
        report = detector.detect(prev, curr)
        assert "temperature" in report.environment_changed
        assert report.environment_changed["temperature"] == (20.0, 25.0)

    def test_detect_significance_threshold(self):
        # threshold=3 means need 3+ changes to be significant
        detector = ChangeDetector(significance_threshold=3)
        prev = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0)),
        ])
        curr = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(5, 0, 0)),  # modified
            WorldEntity(entity_id="e2", entity_type="person", position=(1, 0, 0)),  # added
        ])
        report = detector.detect(prev, curr)
        # 2 changes (1 added + 1 modified) < threshold 3 = NOT significant
        assert not report.significant

    def test_detect_significance_threshold_met(self):
        # With threshold=1, even 1 change is significant
        detector = ChangeDetector(significance_threshold=1)
        prev = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0)),
        ])
        curr = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(5, 0, 0)),
            WorldEntity(entity_id="e2", entity_type="person", position=(1, 0, 0)),
            WorldEntity(entity_id="e3", entity_type="vehicle", position=(2, 0, 0)),
        ])
        report = detector.detect(prev, curr)
        assert report.significant

    def test_detect_batch(self):
        detector = ChangeDetector()
        states = [
            WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))]),
            WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(1, 0, 0))]),
            WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(2, 0, 0))]),
        ]
        reports = detector.detect_batch(states)
        assert len(reports) == 2
        assert reports[0].has_changes
        assert reports[1].has_changes

    def test_change_report_to_dict(self):
        detector = ChangeDetector()
        prev = WorldState(entities=[])
        curr = WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))])
        report = detector.detect(prev, curr)
        d = report.to_dict()
        assert len(d["added"]) == 1
        assert d["significant"] is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhase006Integration:
    def test_multi_frame_pipeline(self):
        """AC9: Observe multiple frames and identify what changed."""
        observer = FrameObserver()
        builder = WorldStateBuilder()
        detector = ChangeDetector()

        # Frame 1: baseline
        frame1 = {"entities": [
            {"entity_id": "e1", "entity_type": "object", "position": [0, 0, 0]},
            {"entity_id": "e2", "entity_type": "person", "position": [5, 0, 0]},
        ], "environment": {"temperature": 20.0}}

        # Frame 2: e1 moves, e3 added, temp changes
        frame2 = {"entities": [
            {"entity_id": "e1", "entity_type": "object", "position": [3, 0, 0]},
            {"entity_id": "e2", "entity_type": "person", "position": [5, 0, 0]},
            {"entity_id": "e3", "entity_type": "vehicle", "position": [10, 0, 0]},
        ], "environment": {"temperature": 22.0}}

        # Frame 3: e2 removed, e1 moves again
        frame3 = {"entities": [
            {"entity_id": "e1", "entity_type": "object", "position": [6, 0, 0]},
            {"entity_id": "e3", "entity_type": "vehicle", "position": [10, 0, 0]},
        ], "environment": {"temperature": 22.0}}

        obs1 = observer.observe(frame1)
        obs2 = observer.observe(frame2)
        obs3 = observer.observe(frame3)

        state1 = builder.build([obs1])
        state2 = builder.build([obs2])
        state3 = builder.build([obs3])

        report1 = detector.detect(state1, state2)
        report2 = detector.detect(state2, state3)

        # Frame 1→2: e1 moved, e3 added, temp changed
        assert len(report1.added) >= 1
        assert any(m.entity_id == "e1" and m.field_name == "position" for m in report1.modified)
        assert "temperature" in report1.environment_changed

        # Frame 2→3: e2 removed, e1 moved
        assert len(report2.removed) >= 1
        assert report2.removed[0].entity_id == "e2"

    def test_world_state_to_state_snapshot_bridge(self):
        """WorldState converts to StateSnapshot for existing WorldModel."""
        ws = WorldState(
            entities=[WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3))],
            domain="vehicle",
        )
        snap = ws.to_state_snapshot()
        assert snap.domain == "vehicle"
        assert "e1" in snap.entities
        assert snap.entities["e1"]["position"] == [1, 2, 3]

    def test_observe_build_detect_no_changes(self):
        """Identical frames produce no changes."""
        observer = FrameObserver()
        builder = WorldStateBuilder()
        detector = ChangeDetector()

        frame = {"entities": [{"entity_id": "e1", "entity_type": "object", "position": [0, 0, 0]}]}

        obs1 = observer.observe(frame)
        obs2 = observer.observe(frame)

        state1 = builder.build([obs1])
        state2 = builder.build([obs2])

        report = detector.detect(state1, state2)
        assert not report.has_changes

    def test_world_state_persistence_roundtrip(self):
        """WorldState can be serialized and deserialized."""
        ws = WorldState(
            entities=[
                WorldEntity(entity_id="e1", entity_type="object", position=(1, 2, 3)),
                WorldEntity(entity_id="e2", entity_type="person", position=(4, 5, 6)),
            ],
            environment={"temp": 22.0},
            domain="industrial",
            uncertainty=0.15,
        )
        d = ws.to_dict()
        restored = WorldState.from_dict(d)
        assert len(restored.entities) == 2
        assert restored.entities[0].entity_id == "e1"
        assert restored.environment["temp"] == 22.0
        assert restored.domain == "industrial"

    def test_large_scale_observations(self):
        """Builder handles 10 observations efficiently."""
        observer = FrameObserver()
        builder = WorldStateBuilder()

        observations = []
        for i in range(10):
            frame = {"entities": [
                {"entity_id": f"e{i}", "entity_type": "object", "position": [i, 0, 0]}
            ]}
            observations.append(observer.observe(frame))

        ws = builder.build(observations)
        assert len(ws.entities) == 10

    def test_change_summary_is_human_readable(self):
        """ChangeReport summary is a readable string."""
        detector = ChangeDetector()
        prev = WorldState(entities=[])
        curr = WorldState(entities=[WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0))])
        report = detector.detect(prev, curr)
        assert isinstance(report.summary, str)
        assert "added" in report.summary

    def test_velocity_change_detection(self):
        """ChangeDetector detects velocity changes."""
        detector = ChangeDetector()
        prev = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="vehicle", position=(0, 0, 0),
                        velocity=(1, 0, 0))
        ])
        curr = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="vehicle", position=(0, 0, 0),
                        velocity=(5, 0, 0))
        ])
        report = detector.detect(prev, curr)
        vel_changes = [m for m in report.modified if m.field_name == "velocity"]
        assert len(vel_changes) == 1

    def test_properties_change_detection(self):
        """ChangeDetector detects property changes."""
        detector = ChangeDetector()
        prev = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0),
                        properties={"color": "red"})
        ])
        curr = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0),
                        properties={"color": "blue"})
        ])
        report = detector.detect(prev, curr)
        prop_changes = [m for m in report.modified if m.field_name == "properties"]
        assert len(prop_changes) == 1

    def test_confidence_change_detection(self):
        """ChangeDetector detects confidence changes."""
        detector = ChangeDetector(confidence_threshold=0.05)
        prev = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0),
                        confidence=0.9)
        ])
        curr = WorldState(entities=[
            WorldEntity(entity_id="e1", entity_type="object", position=(0, 0, 0),
                        confidence=0.5)
        ])
        report = detector.detect(prev, curr)
        conf_changes = [m for m in report.modified if m.field_name == "confidence"]
        assert len(conf_changes) == 1


# ============================================================================
# Performance Tests (AC13-15)
# ============================================================================

class TestPhase006Performance:
    def test_frame_observer_latency(self):
        """AC13: FrameObserver processes a frame in < 100ms."""
        observer = FrameObserver()
        frame = {"entities": [
            {"entity_id": f"e{i}", "entity_type": "object", "position": [i, 0, 0]}
            for i in range(50)
        ]}
        start = time.time()
        observer.observe(frame)
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 100.0, f"FrameObserver took {elapsed_ms:.1f}ms"

    def test_change_detector_latency(self):
        """AC14: ChangeDetector compares two WorldStates in < 50ms."""
        detector = ChangeDetector()
        prev = WorldState(entities=[
            WorldEntity(entity_id=f"e{i}", entity_type="object", position=(i, 0, 0))
            for i in range(100)
        ])
        curr = WorldState(entities=[
            WorldEntity(entity_id=f"e{i}", entity_type="object", position=(i + 1, 0, 0))
            for i in range(100)
        ])
        start = time.time()
        detector.detect(prev, curr)
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 50.0, f"ChangeDetector took {elapsed_ms:.1f}ms"

    def test_world_state_builder_latency(self):
        """AC15: WorldStateBuilder builds from 10 observations in < 200ms."""
        builder = WorldStateBuilder()
        observations = []
        for i in range(10):
            obs = FrameObservation(
                entities=[
                    WorldEntity(entity_id=f"e{j}", entity_type="object",
                                position=(j + i, 0, 0))
                    for j in range(50)
                ],
            )
            observations.append(obs)
        start = time.time()
        builder.build(observations)
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 200.0, f"WorldStateBuilder took {elapsed_ms:.1f}ms"
