# ORION Phase 5 Specification
## Version: 1.0
## Date: August 20, 2026
## Author: ORION Supervisor
## Status: In Progress

---

## 1. Objective

Phase 5 focuses on production-readiness: vector search at database level, live PostgreSQL validation, comprehensive monitoring, and preparation for physical deployment (subject to Founder approval).

## 2. Work Items

### W5-1: pgvector Integration
- Integrate pgvector extension for PostgreSQL-native vector similarity search
- Replace Python cosine similarity with database-level vector operations
- Fallback to Python cosine similarity when pgvector is unavailable
- Batch embedding storage for efficiency
- Schema: `memory_embeddings` table with `vector(3072)` column

### W5-2: Live PostgreSQL Testing
- Docker Compose configuration for PostgreSQL 16 + pgvector
- Test suite for concurrent writes, transaction rollback, large payloads
- Hash chain integrity verification on live PostgreSQL
- Connection pooling and timeout handling
- Tests auto-skip when no PostgreSQL is available

### W5-3: Monitoring Dashboard
- MetricsCollector: collects metrics from all 4 domain simulators
- DashboardRenderer: text, JSON, and HTML rendering
- AlertManager: threshold-based alerts (INFO/WARNING/CRITICAL/EMERGENCY)
- MonitoringDashboard: unified monitoring cycle

### W5-4: Performance Benchmarking
- Benchmark all domain simulations under load
- Measure CBF filter latency
- Measure cross-domain arbitration latency
- Measure memory store/retrieve latency
- Generate performance baseline report

### W5-5: Documentation Update
- Update ORION_ARCHITECTURE document to v0.6
- Update Dependency & License Registry
- Generate comprehensive API documentation
- Update test coverage report

### W5-6: Physical Deployment Preparation (REQUIRES FOUNDER APPROVAL)
- Safety Layer certification checklist
- Hardware compatibility verification
- Regulatory compliance review
- Emergency shutdown procedure documentation
- Risk assessment for physical deployment

## 3. Safety Considerations

- All work items W5-1 through W5-5 are simulation/digital only — no physical risk
- W5-6 (Physical Deployment Preparation) is BLOCKED until Founder gives explicit approval
- No code changes that affect safety-critical paths without Luna review

## 4. Dependencies

- asyncpg (BSD) — already in use
- pgvector (PostgreSQL 2-Clause) — new, BSD-compatible
- Docker (Apache 2.0) — for testing environment only
- No new Python dependencies for monitoring dashboard

## 5. Success Criteria

- All existing 168 tests continue to pass
- New Phase 5 tests pass (target: 200+ total tests)
- pgvector integration works with fallback
- Monitoring dashboard renders all 4 domains
- Live PostgreSQL tests pass when PostgreSQL is available
- Performance benchmarks established
- Luna gives APPROVED verdict

## 6. Estimated Test Count

| Work Item | New Tests | Running Total |
|-----------|-----------|---------------|
| W5-1: pgvector | ~8 | 176 |
| W5-2: Live PG | ~10 (9 skip without PG) | 186 |
| W5-3: Dashboard | ~10 | 196 |
| W5-4: Benchmark | ~5 | 201 |
| W5-5: Docs | 0 (validation only) | 201 |
| **Total** | **~33** | **~201** |

---

## Architecture Decision Log

### AD-5.1: pgvector vs Python cosine similarity
**Decision:** Use pgvector when available, fall back to Python cosine similarity.
**Rationale:** pgvector provides O(n) search at database level with indexing support. Python fallback ensures the system works in all environments.
**Date:** August 20, 2026

### AD-5.2: Docker Compose for PostgreSQL testing
**Decision:** Use Docker Compose with postgres:16 and pgvector/pgvector:pg16 images.
**Rationale:** Isolated testing environment, reproducible, matches production PostgreSQL version.
**Date:** August 20, 2026

### AD-5.3: Monitoring dashboard without external dependencies
**Decision:** Implement dashboard with stdlib only, no external charting libraries.
**Rationale:** Maintains zero-dependency principle for core ORION components. HTML dashboard is self-contained.
**Date:** August 20, 2026
