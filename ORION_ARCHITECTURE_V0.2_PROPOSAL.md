# ORION ARCHITECTURE V0.2 PROPOSAL

**Date:** 2026-08-20
**Basis:** Evidence from ORION_AUDIT_REPORT_v0.1.md
**Status:** PROPOSAL — requires Luna review and Founder approval

---

## Evidence Base

This proposal is driven by findings from the independent audit (ORION_AUDIT_REPORT_v0.1.md). Every recommendation traces to a verified finding.

---

## Priorities (per ORION_TASK_002 §23)

1. **Reliability** — system must not lose progress
2. **Observability** — system must be inspectable
3. **Testability** — every component must be testable
4. **Modularity** — components must be replaceable
5. **Model independence** — no hard-coded provider
6. **Hardware independence** — no hard-coded device
7. **Security** — authenticated, authorized, isolated
8. **Safety** — physical actions gated
9. **Reproducibility** — deterministic results when needed
10. **Research extensibility** — new domains/capabilities without rewrites

---

## Current Architecture (v0.5/v0.6)

8 cognitive planes (Cognitive, State, Memory, Safety, Arbitration, Audit, Config, Contracts) + 4 domain simulators + HAL + API + World Model + Planner + Models.

**Strengths:** Clean plane separation, CBF safety, minimal dependencies (1 external), adapter patterns.

**Weaknesses (evidence-based):**
- No running process (library, not service) — AUDIT §9
- No CI — AUDIT §14
- No auth — AUDIT §12
- No Discovery — AUDIT §16
- No causal reasoning — AUDIT §7
- No process watchdog — AUDIT §9
- World Model not persistent — AUDIT §6
- OpenAI API via urllib (no retry/timeout) — AUDIT §10
- simulation/ outside src/ — AUDIT §2
- No project config — AUDIT §2

---

## Proposed Changes

### 1. Project Structure (Reliability, Reproducibility)

```
orion/
  pyproject.toml          # NEW — project config, deps, tool config
  Dockerfile              # NEW — container definition
  docker-compose.yml      # EXISTS — add app service
  .github/workflows/
    ci.yml                # NEW — pytest + lint on push/PR
  src/
    simulation/           # MOVED from simulation/
    cognitive/
    state/
    memory/
    safety/
    arbitration/
    audit/
    config/
    contracts/
    persistence/
    domains/
    monitoring/
    hal/
    api/
    models/
    world_model/
    planning/
    eval/
    runtime/              # NEW — process supervisor, watchdog
  tests/
  docs/
```

### 2. Runtime Layer (Reliability)

New `src/runtime/` module:

```
src/runtime/
  supervisor.py     # Main process — loads state, starts workers, health monitor
  worker.py         # Worker process — executes tasks
  watchdog.py       # Process watchdog — monitors workers, restarts on crash
  health.py         # Health check service — periodic health_check() calls
  signals.py        # Graceful shutdown handler — SIGTERM/SIGINT → save state
```

**Why:** AUDIT §9 found TaskStateManager has checkpoints but no running process. The 24/7 Runtime Policy requires persistent process, watchdog, automatic recovery.

**Model:** Supervisor process (systemd-managed) → spawns workers → workers execute tasks → watchdog monitors → restarts failed workers → supervisor saves state on shutdown.

### 3. Security Layer (Security)

New authentication on ORIONAPI:

```
src/api/
  __init__.py        # EXISTS — add auth decorator
  auth.py            # NEW — bearer token auth, rate limiting
```

**Why:** AUDIT §12 found API has no authentication. Anyone with network access can call ORION.

**Model:** Bearer token auth (env var ORION_API_KEY). Rate limiting (configurable). Optional: per-agent auth tokens.

### 4. Model Layer Hardening (Model Independence)

```
src/models/
  __init__.py           # EXISTS — adapter interfaces
  gpt4o_adapters.py     # EXISTS — GPT-4o concrete adapters
  local_adapters.py     # NEW — local model adapters (future)
  retry.py              # NEW — retry with exponential backoff
  http_client.py        # NEW — httpx-based client (replace urllib)
```

**Why:** AUDIT §10 found urllib with no retry/timeout. GPT-4o hardcoded as default. Adapter pattern is good but needs robust HTTP client.

**Model:** Replace urllib with httpx (or requests). Add retry with exponential backoff. Configurable model selection via registry. Default model from env var, not hardcoded.

### 5. World Model Persistence (Reliability)

```
src/world_model/
  __init__.py          # EXISTS
  persistence.py       # NEW — save/load state snapshots to DB
```

**Why:** AUDIT §6 found World Model is in-memory only. State is lost on restart.

### 6. CI/CD Pipeline (Testability, Reproducibility)

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - run: pip install -e ".[dev]"
      - run: pytest --tb=short
      - run: ruff check src/
      - run: mypy src/ --ignore-missing-imports
```

**Why:** AUDIT §14 found zero CI. 463 tests exist but nothing runs them automatically.

### 7. Discovery Decision (Research Extensibility)

**Option A: Implement Discovery** — requires knowledge ingestion, evidence tracking, hypothesis generation, contradiction detection. Significant effort (~2000+ lines).

**Option B: De-scope Discovery** — remove from Master Spec, focus on physical intelligence (safety, planning, simulation).

**Recommendation:** De-scope for now. Focus on core physical intelligence. Discovery can be added as extension module when needed.

### 8. Causal Reasoning Decision (Research Extensibility)

**Option A: Implement** — causal models, counterfactual simulation, model-mismatch detection. Significant effort.

**Option B: De-scope** — physics-based prediction is sufficient for current domains.

**Recommendation:** De-scope for now. Add causal reasoning when ORION handles complex multi-agent environments where physics-only prediction is insufficient.

---

## What Does NOT Change

- 8-plane architecture — VERIFIED, working well
- CBF-based safety — VERIFIED, most mature component
- 4 domain simulators — VERIFIED
- Adapter pattern for models — VERIFIED
- SQLite + PostgreSQL dual storage — VERIFIED
- Memory system with 6 types — VERIFIED
- HAL with Protocol adapters — VERIFIED
- Audit system with hash chains — VERIFIED

---

## Migration Path

1. Create pyproject.toml + pin dependencies
2. Move simulation/ → src/simulation/ (fix imports)
3. Add CI workflow
4. Add auth to API
5. Replace urllib with httpx + retry
6. Implement runtime/ (supervisor, watchdog)
7. Add World Model persistence
8. Run OPIB benchmarks
9. Send to Luna for review

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Move simulation/ | LOW — import path fix | Update imports in test_phase1.py |
| Add auth | LOW — additive | Backward compatible (env var optional) |
| Replace urllib | MEDIUM — HTTP behavior change | Keep urllib as fallback |
| Runtime layer | MEDIUM — new code | Start with simple supervisor, add watchdog later |
| World Model persistence | LOW — additive | Add save/load methods |
| De-scope Discovery | LOW — documentation only | Update Master Spec |

---

## Summary

V0.2 is NOT a rewrite. It adds infrastructure (runtime, auth, CI, project config) and hardens existing components (HTTP client, World Model persistence). The 8-plane architecture stays. The safety system stays. The domain simulators stay. The changes make ORION deployable and reliable, not just testable.

**Requires:** Luna review, Founder approval for scope decisions (Discovery, Causal).
