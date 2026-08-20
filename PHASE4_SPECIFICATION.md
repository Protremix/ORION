# ORION Phase 4 Specification

## Document Info
- **Version:** 0.1 (Draft)
- **Date:** 2026-08-20
- **Author:** ORION Supervisor Agent (Selene)
- **Reviewer:** GPT-5.6 Luna (Architect/Reviewer)
- **Approval Status:** DRAFT — Pending Luna Review

---

## 1. Context

### 1.1 Phase 3 Baseline (Approved with Conditions)
- 48 Python files, ~14,816 lines of code
- 96 tests, all passing
- PostgreSQL persistence layer (asyncpg) — interface ready, live testing pending
- Vehicle domain (full autonomous) — operational
- Scalability assessment — complete (7 load tests)
- Cross-domain safety arbitration — implementation in progress
- Audit log replication — implementation in progress

### 1.2 Luna's Phase 3 Conditions (for Phase 4)
1. **Live PostgreSQL Testing:** Conduct live testing with PostgreSQL in Docker
2. **Monitoring Dashboards:** Implement performance monitoring and alerting dashboards

### 1.3 Remaining Phase 3 Items (Completing Now)
- W3-6: Cross-domain safety arbitration (Industrial + Vehicle)
- W3-7: Audit log replication and backup strategy

---

## 2. Phase 4 Scope: Production Readiness + New Domains

### 2.1 Work Items

| ID | Work Item | Priority | Dependencies | Luna Condition |
|----|-----------|----------|--------------|----------------|
| W4-1 | Live PostgreSQL testing (Docker) | Critical | Docker environment | C1 |
| W4-2 | Monitoring dashboard (metrics + alerts) | High | W4-1 | C2 |
| W4-3 | Smart Home domain module (SC-3) | High | None | — |
| W4-4 | Drone domain module (SC-2) | Medium | None | — |
| W4-5 | pgvector integration for semantic search | Medium | W4-1 | — |
| W4-6 | Cross-domain integration test (all domains) | High | W4-3, W4-4 | — |
| W4-7 | Safety layer v2 (formal verification) | Critical | None | — |
| W4-8 | Architecture document v0.6 | Medium | All | — |

### 2.2 Live PostgreSQL Testing (W4-1)

**Luna's Condition C1:** Validate PostgreSQL integration in a live environment.

- Deploy PostgreSQL via Docker container
- Run full test suite against live PostgreSQL
- Benchmark: connection pool sizes (5, 10, 20, 50)
- Benchmark: concurrent write throughput vs SQLite
- Benchmark: SERIALIZABLE vs READ COMMITTED audit log performance
- Verify: hash chain integrity under concurrent writes
- Verify: fallback mechanism when PostgreSQL goes down mid-operation

**INFRASTRUCTURE NOTE:** Requires Docker in the execution environment. No cloud costs — local Docker only.

### 2.3 Monitoring Dashboard (W4-2)

**Luna's Condition C2:** Performance monitoring and alerting.

- Collect metrics from: StatePlane, MemoryStore, StorageManager, GPTMonitor, SafetyEnforcement
- Time-series storage (SQLite-based for local, PostgreSQL for production)
- Dashboard components:
  - GPT-4o health (latency, error rate, circuit state, token usage)
  - Belief state throughput (ops/s, latency percentiles)
  - Memory store stats (entries, search latency, hit rate)
  - Audit log health (chain integrity, write rate, replication lag)
  - Safety events (AEB triggers, CBF violations, authority transitions)
  - Cross-domain arbitration decisions
- Alert routing: integrate with existing GPTIntegrationMonitor alerts

### 2.4 Smart Home Domain (W4-3)

**Safety Criticality:** SC-3 (lowest, but human occupancy)

- Room entities (temperature, humidity, occupancy)
- HVAC controller (thermostat, zones, schedules)
- Lighting controller (dimmers, scenes, occupancy-based)
- Security sensors (door/window contacts, motion detectors)
- Smart locks (fail-safe = unlocked on emergency)
- Smoke/CO detectors (triggers E-stop → evacuation mode)
- Energy management (power monitoring, optimization)

### 2.5 Drone Domain (W4-4)

**Safety Criticality:** SC-2 (physical risk to people/property below)

- Drone entity (position, velocity, altitude, battery, state)
- IMU/altitude sensors
- Geofencing (virtual boundary enforcement via CBF)
- Collision avoidance (3D CBF — ground, obstacles, other drones)
- Battery management (low battery → return-to-base)
- Flight modes: hover, waypoint navigation, return-to-base, emergency landing
- Wind disturbance simulation

### 2.6 pgvector Integration (W4-5)

- Replace hash-based embeddings with pgvector
- Store GPT-4o embeddings directly in PostgreSQL
- Semantic search via pgvector cosine similarity
- Benchmark: pgvector vs hash-based search (accuracy + speed)
- Migration script: existing hash embeddings → pgvector

### 2.7 Cross-Domain Integration Test (W4-6)

- Industrial + Vehicle + Smart Home coexistence
- Shared safety enforcement (multiple CBFs)
- Cross-domain emergency cascade
- Full autonomous cycle across all domains
- Scalability: all domains running concurrently

### 2.8 Safety Layer v2 (W4-7)

- Formal verification of safety properties
- CBF correctness proofs (mathematical verification)
- Authority state machine model checking
- Independence requirement automated verification
- Safety case document generation
- FMEA (Failure Modes and Effects Analysis)

### 2.9 Architecture Document v0.6 (W4-8)

- Update with Phase 3 + Phase 4 results
- Complete domain module documentation
- Production deployment architecture
- Safety certification roadmap

---

## 3. Open Questions

| ID | Question | Options | Default | Constitution Section |
|----|----------|---------|---------|---------------------|
| F4-1 | Docker availability | Provide Docker env / Use cloud PostgreSQL | Provide Docker env | §4 (no cost, autonomous) |
| F4-2 | Drone simulation complexity | 2D grid / 3D full physics | 2D grid (Phase 5 for 3D) | §2 (autonomous decision) |
| F4-3 | Safety layer formalism | TLA+ / Z3 SMT / Custom | Z3 SMT (Python-native) | §2 (autonomous decision) |

---

## 4. Dependencies & License Registry Update

| Component | License | Phase | Status |
|-----------|--------|-------|--------|
| Docker | Apache 2.0 | 4 | Infrastructure |
| PostgreSQL | PostgreSQL License (BSD-like) | 4 | Infrastructure |
| pgvector | PostgreSQL License | 4 | NEW — needs verification |
| Z3 (if selected) | MIT | 4 | NEW — needs verification |

---

## 5. Safety Constraints

- All work remains in simulation — no physical hardware
- Drone domain simulation only — no real drone connection
- Smart home simulation only — no real device control
- Safety enforcement independence (IND-1 through IND-10) maintained
- Cross-domain safety priority: SC-1 > SC-2 > SC-3
- Formal safety verification before any physical deployment phase

---

## 6. Success Criteria

1. Live PostgreSQL testing with Docker (all tests pass against PostgreSQL)
2. Monitoring dashboard operational with real metrics
3. Smart Home domain simulation operational (≥8 tests)
4. Drone domain simulation operational (≥10 tests)
5. pgvector integration for semantic search
6. Cross-domain integration test (all domains concurrent)
7. Safety layer v2 with formal verification
8. Architecture document v0.6 published
9. All existing 96+ tests still passing
10. Luna architectural review: APPROVED

---

## 7. Autonomous Execution Constitution Compliance

Per the ORION Autonomous Execution Constitution v1.0:
- **Section 2:** ORION will autonomously plan, implement, test, and fix errors
- **Section 3:** Only stop for real money, legal decisions, physical risk, or strategic changes
- **Section 4:** No permission needed for code, tests, research, benchmarks, free dependencies
- **Section 5:** Error recovery: Diagnose → Research → Fix → Test → Continue
- **Section 7:** Technical decisions made autonomously within approved architecture
- **Section 12:** Standard reporting format: TASK/STATUS/ACTIONS/DECISIONS/TESTS/ERRORS/FIXES/RESULTS/RISKS/COST/NEXT ACTION
