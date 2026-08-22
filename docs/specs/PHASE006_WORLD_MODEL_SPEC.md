# ORION Phase 006 — World Model Specification

**Phase:** 006
**Status:** DRAFT — Pending Luna Review
**License:** Apache 2.0
**Roadmap Reference:** ORION_MASTER_ROADMAP_v1.0 Phase 006

## 1. Goal

Create the first digital World Model that can observe multiple frames of input and correctly identify what changed.

**Input:** image, video, sensor-like data
**Output:** WORLD STATE — including objects, people, vehicles, geometry, relationships, motion, environment, time, uncertainty

**Acceptance Criterion:** ORION can observe multiple frames and correctly identify what changed.

## 2. Current State (VERIFIED FACT)

The existing `src/world_model/__init__.py` (467 lines) implements:
- `StateSnapshot`: timestamped environment snapshot
- `PredictionResult`: predicted future states with confidence/uncertainty
- 4 domain physics models: Industrial, Vehicle, Drone, Home
- `WorldModel.predict()`: physics-based future state prediction
- `WorldModel.batch_predict()`: multi-action comparison
- `WorldModel.select_best_action()`: safety-ranked action selection
- 37 tests passing

**Gap:** The existing model handles *prediction* (action → future state) but NOT *observation* (frames → current world state). Phase 006 adds the observation and change detection layer.

## 3. Architecture

```
FRAMES (image/video/sensor data)
    ↓
[FrameObserver] — extracts entities, positions, motion from raw input
    ↓
[WorldStateBuilder] — aggregates frame observations into structured WorldState
    ↓
[ChangeDetector] — compares sequential WorldStates to identify changes
    ↓
[WorldStateManager (Phase 005)] — persists world state in memory
    ↓
[WorldModel (existing)] — predicts future states for planning
```

### 3.1 New Components

#### A. FrameObserver
- **Purpose:** Extract structured observations from raw frame data
- **Input:** Frame data (simulated: dict of entities, positions; future: image tensors)
- **Output:** `FrameObservation` — list of detected entities with positions, types, confidence
- **Key methods:**
  - `observe(frame_data: Dict[str, Any]) -> FrameObservation`
  - `observe_batch(frames: List[Dict]) -> List[FrameObservation]`
- **Design note:** In simulation mode, frame data is a structured dict. Future hardware phase will replace with actual perception models (vision, LiDAR, etc.).

#### B. WorldStateBuilder
- **Purpose:** Aggregate frame observations into a complete world state
- **Input:** One or more FrameObservations
- **Output:** `WorldState` — structured representation of all entities, relationships, geometry, environment
- **Key methods:**
  - `build(observations: List[FrameObservation]) -> WorldState`
  - `merge(existing: WorldState, new_obs: FrameObservation) -> WorldState`
- **WorldState fields:**
  - `entities: List[WorldEntity]` — objects, people, vehicles
  - `relationships: List[EntityRelation]` — spatial, temporal, causal
  - `geometry: Dict[str, Any]` — positions, dimensions, orientations
  - `environment: Dict[str, Any]` — temperature, lighting, weather, time
  - `timestamp: float` — observation time
  - `uncertainty: float` — overall state confidence [0, 1]
  - `source: str` — observation source identifier

#### C. ChangeDetector
- **Purpose:** Compare two WorldStates and identify what changed
- **Input:** `WorldState` (previous), `WorldState` (current)
- **Output:** `ChangeReport` — structured diff
- **Key methods:**
  - `detect(previous: WorldState, current: WorldState) -> ChangeReport`
  - `detect_batch(states: List[WorldState]) -> List[ChangeReport]`
- **ChangeReport fields:**
  - `added: List[WorldEntity]` — new entities
  - `removed: List[WorldEntity]` — disappeared entities
  - `modified: List[EntityChange]` — changed entities (position, state, properties)
  - `relationships_changed: List[EntityRelation]` — new/removed/modified relations
  - `environment_changed: Dict[str, Tuple[Any, Any]]` — env changes (old, new)
  - `summary: str` — human-readable change description
  - `significant: bool` — whether changes are meaningful (above threshold)

#### D. WorldEntity (data class)
- **Fields:**
  - `entity_id: str` — unique identifier
  - `entity_type: str` — object, person, vehicle, sensor, zone
  - `position: Tuple[float, float, float]` — x, y, z coordinates
  - `velocity: Tuple[float, float, float]` — velocity vector (optional)
  - `orientation: float` — rotation in radians (optional)
  - `properties: Dict[str, Any]` — type-specific attributes
  - `confidence: float` — detection confidence [0, 1]
  - `last_seen: float` — timestamp of last observation

#### E. EntityRelation (data class)
- **Fields:**
  - `relation_id: str`
  - `source_id: str` — entity ID
  - `target_id: str` — entity ID
  - `relation_type: str` — near, far, facing, moving_toward, moving_away, contains, part_of
  - `strength: float` — relation intensity [0, 1]
  - `timestamp: float`

### 3.2 Existing Components (Reuse)

- `WorldModel` (src/world_model/__init__.py) — physics prediction, unchanged
- `WorldStateManager` (src/memory/world_state_manager.py) — world state persistence, enhanced
- `StateSnapshot` — bridge between WorldState and existing prediction pipeline

### 3.3 Integration Points

1. **Phase 005 (Memory):** WorldState snapshots stored via WorldStateManager → MemoryManager
2. **Phase 004 (Core):** CoreSupervisor can query world state during planning
3. **Phase 007 (Simulation):** WorldModel predictions use observed WorldState as input

## 4. Acceptance Criteria

| AC | Description | Verification |
|---|---|---|
| AC1 | FrameObserver extracts entities from frame data | Unit test: observe structured frame → verify entities detected |
| AC2 | WorldStateBuilder aggregates observations into WorldState | Unit test: multiple observations → complete WorldState with entities, relationships, environment |
| AC3 | WorldState includes objects, people, vehicles, geometry, relationships, motion, environment, time, uncertainty | Unit test: verify all fields present and correctly typed |
| AC4 | ChangeDetector identifies added entities | Unit test: add entity between frames → detect as "added" |
| AC5 | ChangeDetector identifies removed entities | Unit test: remove entity between frames → detect as "removed" |
| AC6 | ChangeDetector identifies modified entities | Unit test: move entity between frames → detect as "modified" with position delta |
| AC7 | ChangeDetector identifies relationship changes | Unit test: entities change proximity → detect relationship change |
| AC8 | ChangeDetector identifies environment changes | Unit test: temperature change → detect in environment_changed |
| AC9 | ORION can observe multiple frames and identify what changed (integration) | Integration test: 3+ frames with multiple changes → correct ChangeReport |
| AC10 | WorldState persists via WorldStateManager (Phase 005 integration) | Integration test: build WorldState → store → retrieve → verify |
| AC11 | All tests pass | pytest -q (zero failures) |
| AC12 | Ruff/mypy clean | ruff check + mypy |

## 5. Test Plan

### Unit Tests (~30 tests)
- FrameObserver: observe single frame, batch, empty frame, malformed frame
- WorldStateBuilder: build from single obs, merge with existing, empty obs, confidence aggregation
- WorldEntity: construction, to_dict, from_dict, equality
- EntityRelation: construction, to_dict, relation types
- ChangeDetector: added, removed, modified, relationship changes, environment changes, no changes, threshold
- WorldState: construction, to_dict, to StateSnapshot conversion

### Integration Tests (~10 tests)
- Multi-frame observation → change detection pipeline
- WorldState → WorldStateManager → MemoryManager persistence
- WorldState → StateSnapshot → WorldModel.predict() pipeline
- 3-frame scenario: baseline → change1 → change2 → verify all changes detected
- Edge cases: empty frames, identical frames, massive changes, uncertainty propagation

## 6. Scope

### IN SCOPE
- Frame observation from structured (simulated) data
- World state construction and aggregation
- Change detection between world states
- Entity and relationship modeling
- Integration with Phase 005 memory and existing WorldModel
- Simulation-only (no real sensors/hardware)

### OUT OF SCOPE
- Real image/video processing (Phase 008 Multimodal)
- Real sensor integration (Phase 011+ Physical AI)
- 3D geometry reconstruction
- SLAM / mapping
- Real-time performance optimization
- Actual vision model integration

## 7. Dependencies

| Dependency | Version | License | Status |
|---|---|---|---|
| Python | >= 3.11 | PSF | Existing |
| Existing WorldModel | Phase 004 | Apache 2.0 | VERIFIED |
| WorldStateManager (Phase 005) | Phase 005 | Apache 2.0 | VERIFIED |
| MemoryManager (Phase 005) | Phase 005 | Apache 2.0 | VERIFIED |
| CoreSupervisor (Phase 004) | Phase 004 | Apache 2.0 | VERIFIED |

No new external dependencies required.

## 8. File Structure

```
src/world_model/
    __init__.py              — existing WorldModel (prediction) — UNCHANGED
    frame_observer.py        — NEW: FrameObserver + FrameObservation
    world_state.py           — NEW: WorldState, WorldEntity, EntityRelation
    world_state_builder.py   — NEW: WorldStateBuilder
    change_detector.py       — NEW: ChangeDetector + ChangeReport

tests/unit/
    test_phase006.py         — NEW: all Phase 006 tests
```

## 9. Lifecycle

This spec follows: Specification → Architecture → Implementation → Test → Verification → Review → Approval → Next Stage

**Current stage:** Specification — pending Luna review per Founder decision.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Simulation data too synthetic | Design frame data format that mirrors real sensor structure |
| WorldState too complex | Keep fields minimal, extend in Phase 008 |
| Change detection false positives | Significance threshold configurable |
| Integration with existing WorldModel breaks | StateSnapshot bridge, no modification to existing code |
