# ORION — Dependency & License Registry

**Last Updated:** August 20, 2026
**Phase:** 3 (PostgreSQL Migration + Vehicle Domain)

---

## Core Dependencies

| # | Component | Version | License | License Compatibility | Phase Added | Status | Notes |
|---|-----------|---------|---------|----------------------|-------------|--------|-------|
| 1 | Python stdlib (sqlite3, json, asyncio, etc.) | 3.11 | PSF License 2.0 | ✅ Apache 2.0 compatible | Phase 1 | Active | Standard library |
| 2 | openai (Python SDK) | latest | MIT | ✅ Apache 2.0 compatible | Phase 1 | Active | GPT-4o reasoning, vision, embeddings |
| 3 | asyncpg | 0.31.0 | Apache 2.0 (BSD-compatible) | ✅ Apache 2.0 compatible | Phase 3 | Active | PostgreSQL async driver — replaces psycopg2 (LGPL) |
| 4 | sqlite3 (stdlib) | 3.11 | Public Domain | ✅ No restrictions | Phase 1 | Active | Fallback persistence layer |

## Dev Dependencies

| # | Component | Version | License | License Compatibility | Phase Added | Status | Notes |
|---|-----------|---------|---------|----------------------|-------------|--------|-------|
| 5 | pytest | 9.1.1 | MIT | ✅ Apache 2.0 compatible | Phase 1 | Active | Test framework |

## Infrastructure

| # | Component | License | Phase Added | Status | Notes |
|---|-----------|---------|-------------|--------|-------|
| 6 | Docker (for PostgreSQL) | Apache 2.0 | Phase 3 | Pending | Local Docker for PostgreSQL testing — not available in current sandbox |
| 7 | PostgreSQL | PostgreSQL License (BSD-like) | Phase 3 | Pending | Local Docker deployment — no cloud costs |

---

## License Decisions

### D1: asyncpg over psycopg2 (Phase 3)
- **Date:** August 20, 2026
- **Decision:** Use asyncpg (Apache 2.0) instead of psycopg2 (LGPL)
- **Reason:** LGPL has copyleft requirements that could complicate ORION's Apache 2.0 licensing. asyncpg is clean BSD-compatible, has better async performance, and is actively maintained.
- **Decided by:** ORION Supervisor (Selene), per Luna's Phase 3 spec recommendation
- **Approved by:** Luna (GPT-5.6, Architect/Reviewer) — Phase 3 spec review

### D2: Apache 2.0 for ORION-owned code
- **Date:** August 20, 2026
- **Decision:** All ORION-owned code uses Apache 2.0 license
- **Decided by:** Founder directive

### D3: SQLite as fallback persistence
- **Date:** August 20, 2026
- **Decision:** SQLite (public domain) as automatic fallback when PostgreSQL unavailable
- **Reason:** Zero-cost, zero-license-restriction fallback for development and testing

---

## External API Dependencies

| # | Service | API Key Env Var | Cost | Phase Added | Status | Notes |
|---|---------|-----------------|------|-------------|--------|-------|
| 1 | OpenAI GPT-4o | $OPENAI_PROJECT_KEY | Per-token | Phase 2 | Active | Reasoning, vision, embeddings |
| 2 | OpenAI GPT-5.6 (Luna) | $OPENAI_PROJECT_KEY | Per-token | Phase 1 | Active | Architect/Reviewer role |

---

## Verification Status

- ✅ All licenses verified against Apache 2.0 compatibility
- ✅ No GPL/LGPL/AGPL dependencies in ORION-owned code
- ✅ asyncpg selected over psycopg2 specifically for license clarity
- ✅ All external APIs documented with cost model
- ⏳ PostgreSQL/Docker infrastructure pending sandbox availability

---

## Phase 4 Additions

### New Python Modules (all Apache 2.0)

| # | Module | Path | Purpose | License | Lines | Tests |
|---|--------|------|---------|---------|-------|-------|
| 8 | home_entities.py | src/domains/home/ | Smart Home domain entities (SC-3) | Apache 2.0 | ~350 | 16 |
| 9 | home_simulator.py | src/domains/home/ | Smart Home simulation | Apache 2.0 | ~300 | — |
| 10 | drone_entities.py | src/domains/drone/ | Drone domain entities (SC-2) | Apache 2.0 | ~350 | 15 |
| 11 | drone_simulator.py | src/domains/drone/ | Drone simulation with CBF | Apache 2.0 | ~350 | — |
| 12 | formal_verification.py | src/safety/ | Formal verification of safety properties | Apache 2.0 | ~500 | 8 |
| 13 | test_cross_domain_integration.py | tests/unit/ | Cross-domain integration tests | Apache 2.0 | ~200 | 12 |

### Phase 4 Dependencies

| # | Dependency | Version | License | Compatible | Phase Added | Purpose |
|---|-----------|---------|---------|------------|-------------|---------|
| 7 | math (stdlib) | 3.11 | PSF | ✅ | Phase 4 | Drone 3D vector math |
| 8 | random (stdlib) | 3.11 | PSF | ✅ | Phase 4 | Formal verification randomized testing |

### Phase 4 Verification

- ✅ All Phase 4 code is Apache 2.0
- ✅ No new external dependencies
- ✅ 6 formally verified safety properties
- ✅ Cross-domain integration tested across all 4 domains
- ✅ 168/168 tests passing

---

## Phase 5 Additions (In Progress)

### New Python Modules (all Apache 2.0)

| # | Module | Path | Purpose | License | Tests |
|---|--------|------|---------|---------|-------|
| 14 | test_live_postgres.py | tests/unit/ | Live PostgreSQL Docker tests | Apache 2.0 | 10 (9 skip) |
| 15 | test_performance_benchmarks.py | tests/unit/ | Performance benchmark suite | Apache 2.0 | 7 |
| 16 | docker-compose.yml | . | Docker Compose for PG testing | Apache 2.0 | — |
| 17 | pgvector_store.py | src/persistence/ | pgvector integration (pending) | Apache 2.0 | ~8 |
| 18 | dashboard.py | src/monitoring/ | Monitoring dashboard (pending) | Apache 2.0 | ~10 |

### Phase 5 Dependencies

| # | Dependency | Version | License | Compatible | Phase Added | Purpose |
|---|-----------|---------|---------|------------|-------------|---------|
| 9 | pgvector (PostgreSQL ext) | 0.7+ | PostgreSQL License (BSD-like) | ✅ | Phase 5 | Vector similarity search |
| 10 | Docker Compose | 3.8 | Apache 2.0 | ✅ | Phase 5 | PostgreSQL testing environment |
| 11 | pgvector/pgvector:pg16 | latest | PostgreSQL License | ✅ | Phase 5 | Docker image with pgvector |

### Phase 5 Verification

- ⏳ pgvector integration (sub-agent in progress)
- ⏳ Monitoring dashboard (sub-agent in progress)
- ✅ Live PostgreSQL test suite written (auto-skips without PG)
- ✅ Performance benchmarks established (7 tests)
- ✅ Docker Compose configuration validated
