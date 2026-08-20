# ORION Architecture v0.6 — Phase 3 + Phase 4 Update

**Date:** August 20, 2026
**Status:** Phase 3 Complete (96/96 tests), Phase 4 In Progress
**Luna Verdict:** Phase 3 APPROVED WITH CONDITIONS

---

## Architecture Overview

ORION is a Physical Intelligence OS designed to integrate reasoning, long-term memory, multimodal perception, and world models for robotics, automotive, drones, and smart home applications.

### Hierarchy
```
FOUNDER (strategic, money, legal, physical risk)
    │
ARCHITECT / REVIEWER — GPT-5.6 Luna (architecture, QC)
    │
ORION SUPERVISOR — Selene (planning, execution)
    │
    ├── Research Agent
    ├── Engineering Agent
    ├── ML Agent
    ├── Vision Agent
    ├── World Agent
    ├── Memory Agent
    ├── Simulation Agent
    ├── Data Agent
    ├── Security Agent
    └── Evaluation Agent
```

### Autonomous Execution Constitution v1.0
ORION operates autonomously per the Constitution:
- No stops for ordinary work
- Stop only for: real money, legal decisions, physical risk, strategic changes
- Error recovery: Diagnose → Research → Fix → Test → Continue
- Technical decisions made autonomously within approved architecture

---

## Planes Architecture (Luna's Design)

### Plane 1: State Plane
- Belief state management (position, velocity, uncertainty)
- Sensor fusion (vision, audio, tactile, proprioception)
- State revision tracking
- Throughput: ~6.2M ops/s (in-memory)

### Plane 2: Memory Plane
- Semantic memory (facts, relationships)
- Episodic memory (events, experiences)
- Embedding-based semantic search (hash-based → pgvector in Phase 4)
- Memory poisoning resistance (permissions, rate limiting)
- Contradiction detection
- Retention policy enforcement

### Plane 3: Cognitive Plane
- Goal management (active goals, priorities, dependencies)
- Action proposal generation
- Cognitive confidence scoring
- Risk assessment
- GPT-4o integration for reasoning

### Plane 4: Action Plane
- Action arbitration (safety enforcement, CBF)
- Authority state machine (NORMAL → DEGRADED → EMERGENCY)
- Lease-based execution (atomic, time-limited)
- Action execution and verification
- Fallback controller execution

### Plane 5: Safety Plane
- SafetyEnforcement with CBF (Control Barrier Functions)
- Independence requirements (IND-1 through IND-10)
- Common cause failure handling
- Fallback controller execution
- Cross-domain safety arbitration (Phase 3: W3-6)
- Safety priority: SC-1 (Industrial) > SC-2 (Vehicle) > SC-3 (Smart Home)

### Plane 6: Persistence Plane
- SQLite StorageManager (Phase 1-2, fallback)
- PostgresStorageManager with asyncpg (Phase 3)
- StorageFactory with automatic fallback
- Transaction isolation: SERIALIZABLE (audit), READ COMMITTED (others)
- Connection pooling (configurable)
- Audit log replication (Phase 3: W3-7)
- Hash chain integrity (tamper-evident)

### Plane 7: Monitoring Plane
- GPTIntegrationMonitor (circuit breaker, 8 alert types)
- Health summary (operational, degraded, critical)
- Circuit breaker: closed → open → half-open recovery
- Scalability assessment (Phase 3: 7 load tests)
- Monitoring dashboard (Phase 4: W4-2)

### Plane 8: Simulation Plane
- GridWorld environment
- Entity management (spawn, update, remove)
- Sensor simulation (vision, distance, contact)
- Domain-specific simulators:
  - Industrial: factory floor (conveyor, robot arm, tank, valve, sensors)
  - Vehicle: full autonomous (highway, urban, parking)
  - Smart Home: in progress (Phase 4)
  - Drone: planned (Phase 4)

---

## Domain Modules

### Industrial Domain (SC-1) — Phase 2 ✅
- Factory floor simulation
- Conveyor belt, robot arm, pressure tank, safety valve
- Temperature, pressure, vibration sensors
- Safety light curtain (E-stop)
- Collision prevention (CBF)
- Tank overflow protection
- Valve failsafe (closes on E-stop)

### Vehicle Domain (SC-2) — Phase 3 ✅
- Full autonomous driving simulation
- Highway, urban, parking scenarios
- Lane sensor (detection, departure warning)
- Obstacle sensor (front/side/rear)
- Traffic light compliance
- Speed controller (accelerate, brake, cruise)
- Steering controller (lane keeping, lane change)
- AEB (Automatic Emergency Braking)
- Collision avoidance (CBF: front, side, rear)
- Adaptive cruise control (safe following distance)

### Smart Home Domain (SC-3) — Phase 4 (In Progress)
- Room entities (temperature, humidity, occupancy)
- HVAC controller (thermostat, zones)
- Lighting controller (dimmers, scenes, occupancy-based)
- Security sensors (door/window, motion)
- Smart locks (fail-safe = unlocked on emergency)
- Smoke/CO detectors (evacuation mode)
- Energy monitor

### Drone Domain (SC-2) — Phase 4 (Planned)
- 2D grid simulation (Phase 5: 3D physics)
- Geofencing (CBF boundary enforcement)
- Collision avoidance (3D CBF)
- Battery management (return-to-base)
- Flight modes: hover, waypoint, return-to-base, emergency

---

## Persistence Architecture

### Phase 1-2: SQLite
- Single-writer, in-process
- ~850 ops/s (belief states)
- Hash chain audit log
- Zero external dependencies

### Phase 3: PostgreSQL (asyncpg)
- Connection pooling (async, configurable size)
- MVCC concurrent writers
- SERIALIZABLE for audit events (tamper-evident)
- READ COMMITTED for other tables
- Automatic fallback to SQLite
- License: asyncpg = Apache 2.0 (BSD-compatible)

### Phase 4: pgvector
- GPT-4o embeddings stored in PostgreSQL
- Cosine similarity search
- Migration from hash-based embeddings

---

## Test Suite

| Suite | Tests | Status |
|-------|-------|--------|
| test_audit_system | 9 | ✅ |
| test_gpt_integration | 5 | ✅ (live GPT-4o) |
| test_phase1 | 1 | ✅ |
| unit/test_gpt_monitor | 16 | ✅ |
| unit/test_industrial_domain | 9 | ✅ |
| unit/test_memory_system | 7 | ✅ |
| unit/test_persistence | 8 | ✅ |
| unit/test_postgres_storage | 14 | ✅ |
| unit/test_safety_arbitration | 9 | ✅ |
| unit/test_vehicle_domain | 11 | ✅ |
| load/test_scalability | 7 | ✅ |
| **Total** | **96** | **✅ All pass** |

Phase 3 additions: +32 tests (14 PostgreSQL + 11 Vehicle + 7 Scalability)

---

## Dependency & License Registry

| Component | License | Status |
|-----------|---------|--------|
| Python stdlib | PSF 2.0 | ✅ Active |
| openai SDK | MIT | ✅ Active |
| asyncpg | Apache 2.0 | ✅ Active |
| pytest | MIT | ✅ Active |
| All ORION code | Apache 2.0 | ✅ Per Founder directive |

No GPL/LGPL/AGPL dependencies.

---

## Phase 4 Roadmap

1. Live PostgreSQL testing (Docker) — Luna condition C1
2. Monitoring dashboard — Luna condition C2
3. Smart Home domain (SC-3) — in progress
4. Drone domain (SC-2)
5. pgvector integration
6. Cross-domain integration test
7. Safety layer v2 (formal verification with Z3 SMT)
8. Architecture document v0.7

---

## Safety Constraints

- All work in simulation — no physical hardware
- Safety enforcement independence (IND-1 through IND-10)
- Cross-domain priority: SC-1 > SC-2 > SC-3
- GPT-4o circuit breaker protects against API failures
- Formal safety verification required before any physical deployment
