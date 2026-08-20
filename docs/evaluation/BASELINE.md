# ORION Baseline Metrics

**Date:** 2026-08-20
**Repository:** orion/implementation
**Version:** 0.6.0
**Environment:** Sandbox (Python 3.11, no live PostgreSQL)

---

## 1. Code Metrics

| Metric | Value | Measurement Method |
|--------|-------|--------------------|
| Python files | 103 | `find . -name "*.py" -not -path "*__pycache__*" \| wc -l` |
| Python lines (src) | ~25,000 | `wc -l` per module |
| Python lines (tests) | 9,794 | `wc -l` on tests/ |
| Python lines (total) | ~35,000 | Sum of all .py files |
| Test files | 38 | Count of test_*.py files |
| Test functions | 625 | `grep -r "def test_" tests/ \| wc -l` |
| Documentation files | ~55 | Count of .md files |
| ADRs | 12 | Count in docs/adr/ |
| Domain modules | 4 | drone, home, industrial, vehicle |
| Safety modules | 8 | src/safety/*.py |

## 2. Test Suite Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Total collected | 625 | `pytest --collect-only` |
| Passed | 616 | `pytest -q -m "not live"` |
| Failed | 0 | — |
| Skipped | 9 | Live PostgreSQL tests (`test_live_postgres.py`) |
| Errors | 0 | — |
| Execution time | 164.11s | (~2 min 44 sec) |
| Collection time | 0.25s | — |

### Test Categories

| Category | Files | Approx Tests |
|----------|-------|--------------|
| Unit (per-module) | 33 | 550 |
| Integration | 3 | 25 |
| Load/Scalability | 2 | 7 |

## 3. Quality Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Ruff lint errors | 0 | After fixes (was 213) |
| Mypy type errors | 0 | After fixes (was 56) |
| CI `|| true` patterns | 0 | Removed (was 2) |
| Security CRITICAL findings | 1 | ORIONAPI auth bypass |
| Security HIGH findings | 5 | Various (see SECURITY_AUDIT.md) |
| Safety HIGH findings | 2 | Missing financial/legal enforcement, permission persistence |

## 4. Dependency Metrics

| Metric | Value |
|--------|-------|
| Runtime dependencies | 2 (asyncpg, openai) |
| Dev dependencies | 4 (pytest, pytest-asyncio, ruff, mypy) |
| External services | 1 (OpenAI GPT-4o API) |
| Docker images | 3 (python, postgres, pgvector) |
| Copyleft licenses | 0 |

## 5. Coverage by Module

| Module | Test File | Tests | Status |
|--------|-----------|-------|--------|
| src/api | test_api.py, test_auth.py, test_validation.py | ~50 | PASS |
| src/arbitration | test_safety_arbitration.py | ~15 | PASS |
| src/audit | test_audit_system.py, test_audit_replication.py | ~21 | PASS |
| src/cognitive | test_phase1.py | ~1 | PASS |
| src/config | (via other tests) | — | PASS |
| src/contracts | (via other tests) | — | PASS |
| src/domains/drone | test_drone_domain.py | 15 | PASS |
| src/domains/home | test_home_domain.py | ~16 | PASS |
| src/domains/industrial | test_industrial_domain.py | ~20 | PASS |
| src/domains/vehicle | test_vehicle_domain.py | ~20 | PASS |
| src/eval | test_eval.py, test_opib_scenarios.py | ~26 | PASS |
| src/hal | test_hal.py | ~15 | PASS |
| src/memory | test_memory_system.py | ~20 | PASS |
| src/models | test_models.py, test_live_gpt4o.py | ~26 | PASS |
| src/monitoring | test_monitoring_dashboard.py, test_gpt_monitor.py | ~25 | PASS |
| src/persistence | test_persistence.py, test_postgres_storage.py, test_pgvector_store.py | ~30 | PASS |
| src/runtime | test_runtime_supervisor.py | ~27 | PASS |
| src/safety | test_safety_v3_verification.py, test_sensor_validation.py, test_physical_watchdog.py, test_cross_domain*.py | ~50 | PASS |
| src/world_model | test_world_model.py | ~20 | PASS |
| src/planning | (via integration tests) | — | PASS |

## 6. Known Issues (Post-Audit)

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | ORIONAPI methods bypass auth | CRITICAL | **FIXED** — auth enforcement added + 8 tests |
| 2 | Default policy signing key fallback | HIGH | OPEN |
| 3 | Docker runs as root | HIGH | OPEN |
| 4 | Vision adapter path traversal | HIGH | OPEN |
| 5 | Permission registry not persistent | HIGH | OPEN |
| 6 | Missing financial/legal action enforcement | HIGH | OPEN |
| 7 | Missing Master Specification doc | MEDIUM | OPEN |
| 8 | Missing Constitution doc | MEDIUM | OPEN |

