# ORION Phase 3 Specification

## Document Info
- **Version:** 0.1 (Draft)
- **Date:** 2026-08-20
- **Author:** ORION Supervisor Agent
- **Reviewer:** GPT-5.6 Luna (Architect/Reviewer)
- **Approval Status:** DRAFT — Pending Luna Review & Founder Approval

---

## 1. Context

### 1.1 Phase 2 Baseline (Approved)
- 39 Python files, 11,358 lines of code
- 64 tests, all passing (including 5 live GPT-4o integration tests)
- SQLite persistence layer operational
- Industrial domain simulation module operational
- GPT-4o monitoring & alerting system operational (circuit breaker, 8 alert types)
- All Luna conditions from Phase 1 & Phase 2 satisfied except:
  - C1: Concurrency planning for PostgreSQL (Phase 3 target)
  - C3: Scalability assessment (Phase 3 target)

### 1.2 Luna's Phase 3 Conditions (from Phase 2 review)
1. **Concurrency Planning:** Develop a detailed concurrency management plan for PostgreSQL integration
2. **Monitoring and Alerts:** ✅ IMPLEMENTED in Phase 2 (monitoring bridge)
3. **Scalability Assessment:** Conduct a scalability assessment for increased load

---

## 2. Phase 3 Scope: PostgreSQL Migration + Multi-Domain + Scalability

### 2.1 Work Items

| ID | Work Item | Priority | Dependencies |
|----|-----------|----------|--------------|
| W3-1 | PostgreSQL persistence layer (replace SQLite) | Critical | None |
| W3-2 | Concurrency management (connection pooling, transaction isolation) | Critical | W3-1 |
| W3-3 | Domain module: Vehicle (autonomous driving simulation) | High | None |
| W3-4 | Domain module: Smart Home (lowest safety criticality) | Medium | None |
| W3-5 | Scalability assessment & load testing | High | W3-1, W3-2 |
| W3-6 | Cross-domain safety arbitration (industrial + vehicle coexistence) | Medium | W3-3 |
| W3-7 | Audit log replication & backup strategy | Medium | W3-1 |

### 2.2 PostgreSQL Migration (W3-1, W3-2)

**CONFIRMED:** SQLite was Phase 2. PostgreSQL is Phase 3. This addresses Luna's Condition C1.

- Implement `PostgresStorageManager` with same interface as `StorageManager`
- Connection pooling (psycopg2 or asyncpg)
- Transaction isolation levels:
  - Audit log: SERIALIZABLE (tamper-evident, no concurrent writes)
  - Memory store: READ COMMITTED (concurrent reads, single writer)
  - Belief states: READ COMMITTED
  - Action history: READ COMMITTED
- Migration script: SQLite → PostgreSQL data transfer
- Fallback: If PostgreSQL unavailable, degrade to SQLite (automatic)

**ASSUMPTION:** PostgreSQL runs in a local Docker container for development.
No cloud database costs. Founder must confirm or override.

### 2.3 Vehicle Domain Module (W3-3)

Simulates autonomous vehicle operation in a grid environment:
- Vehicle entity (speed, heading, lane position)
- Traffic sensors (lane detection, obstacle detection, traffic light)
- Speed control (acceleration, braking, cruise control)
- Lane keeping (steering, lane change)
- Emergency braking (AEB — automatic emergency braking)
- Collision avoidance (front, side, rear)
- Safety: velocity CBF already exists, add lane-keeping CBF

**Safety Criticality:** SC-2 (human occupants, but controlled environment)

### 2.4 Smart Home Domain Module (W3-4)

Simulates a smart home environment:
- Room entities (temperature, humidity, occupancy)
- HVAC controller (thermostat, zones)
- Lighting controller (dimmers, scenes)
- Security sensors (door/window contacts, motion detectors)
- Smart locks (fail-safe = unlocked on emergency)
- Smoke/CO detectors (triggers E-stop → evacuation mode)

**Safety Criticality:** SC-3 (lowest, but human occupancy)

### 2.5 Scalability Assessment (W3-5)

- Load testing: 1000+ concurrent belief state updates
- Memory store stress: 10,000+ memory entries with semantic search
- Audit log integrity under concurrent writes
- GPT-4o throughput: measure calls/sec, token usage patterns
- Circuit breaker behavior under sustained load
- Identify bottlenecks and document in scalability report

### 2.6 Cross-Domain Safety (W3-6)

- Industrial + Vehicle coexistence in simulation
- Shared safety enforcement (multiple CBFs from different domains)
- Authority state machine transitions across domains
- Safety arbitration priority: Industrial SC-1 > Vehicle SC-2 > Smart Home SC-3

### 2.7 Audit Log Replication (W3-7)

- WAL-based replication strategy
- Backup schedule and point-in-time recovery
- Hash chain verification across replicas
- Failure scenario: replica goes down → continue on primary, catch up on rejoin

---

## 3. Open Questions for Founder

| ID | Question | Options | Default |
|----|----------|---------|---------|
| F3-1 | PostgreSQL hosting | Docker (local) / Cloud (managed) / Embedded | Docker (local, zero cost) |
| F3-2 | Vehicle domain scope | Full autonomous / Highway only / Parking only | Highway only (fastest to validate) |
| F3-3 | Smart Home priority | Phase 3 / Defer to Phase 4 | Defer to Phase 4 (focus on PostgreSQL + Vehicle) |

---

## 4. Dependencies & License Registry

| Component | License | Phase | Status |
|-----------|--------|-------|--------|
| Python stdlib (sqlite3, json, etc.) | PSF | 1-3 | Active |
| openai (Python SDK) | MIT | 1-3 | Active |
| psycopg2 (PostgreSQL adapter) | LGPL | 3 | **NEW — needs verification** |
| Docker (for PostgreSQL) | Apache 2.0 | 3 | **NEW — infrastructure** |

---

## 5. Safety Constraints

- All work remains in simulation — no physical hardware
- Vehicle domain simulation only — no real vehicle connection
- PostgreSQL in local container — no production database
- Safety enforcement independence (IND-1 through IND-10) maintained
- GPT-4o circuit breaker protects against API failures
- Cross-domain safety arbitration preserves SC-1 > SC-2 > SC-3 priority

---

## 6. Success Criteria

1. PostgreSQL persistence layer operational with concurrent read/write support
2. Connection pooling with configurable pool size
3. Vehicle domain simulation with AEB, lane keeping, collision avoidance
4. Scalability report documenting throughput limits and bottlenecks
5. All 64+ existing tests still passing
6. New tests for PostgreSQL layer (≥8 tests)
7. New tests for Vehicle domain (≥10 tests)
8. Scalability load test results documented
9. Luna architectural review: APPROVED
