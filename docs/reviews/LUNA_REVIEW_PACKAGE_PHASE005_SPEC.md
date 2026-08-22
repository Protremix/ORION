# ORION Phase 005 — Memory System Specification
# Luna Review Package — Specification Review (Pre-Implementation)

**Project:** ORION — Physical Intelligence OS
**Phase:** 005 — Memory
**Review Type:** Specification Review (pre-implementation)
**Commit SHA:** 8e8404a
**Branch:** main
**Date:** 2026-08-22
**Author:** ORION Supervisor (Selene)
**Reviewer:** Luna (GPT-5.6)

---

## 1. Purpose

This review package requests Luna to independently review the Phase 005
Memory System specification and determine whether it satisfies the Phase 005
acceptance criteria from the ORION Master Roadmap. This is a SPECIFICATION
review, not an implementation review. Implementation is paused pending review
feedback.

## 2. Phase Context

Per the ORION Master Roadmap v1.0:
- Phase 001: Repository Audit — VERIFIED
- Phase 002: Evaluation System — VERIFIED (Luna Round 7, commit dab4a6d)
- Phase 003: Model Selection — VERIFIED (Luna Round 7, commit e7f855b)
- Phase 004: ORION Core — VERIFIED (Luna Round 2, commit 189c12a)
- Phase 005: Memory — CURRENT (spec complete, implementation paused)

## 3. Specification Document

**File:** `docs/specs/PHASE005_MEMORY_SPEC.md`
**Commit:** ffdf402 (included in 8e8404a)
**Lines:** ~480

## 4. Acceptance Criteria (12 criteria)

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| AC1 | ORION can retrieve relevant previous information by semantic query | Integration test: store memory, new session, retrieve by related query |
| AC2 | Memory persists across sessions (disconnect/reconnect) | Integration test: store in session 1, retrieve in session 2 |
| AC3 | Memory writes are validated (poisoning resistance) | Unit test: attempt poisoned write, verify rejection |
| AC4 | Memory permissions enforced per type and operation | Unit test: attempt unauthorized read/write/delete, verify denial |
| AC5 | Contradictions detected and resolved | Unit test: store conflicting memories, verify detection |
| AC6 | Short-term memories consolidate to long-term | Unit test: create short-term, run decay, verify promotion |
| AC7 | World state maintained from memory entries | Unit test: store observations, verify world state snapshot |
| AC8 | CoreSupervisor consults memory before planning | Integration test: verify recall() called, context injected |
| AC9 | CoreSupervisor stores observations after execution | Integration test: verify remember() called after task completion |
| AC10 | Memory verification detects stale/wrong memories | Unit test: store memory, observe contradiction, verify update |
| AC11 | All tests pass (existing + new) | `python -m pytest -q` |
| AC12 | Ruff/mypy clean | `ruff check src/memory/ && mypy src/memory/` |

## 5. Architecture Summary

### 7 New Components

1. **MemoryPermissions** — Integrates with Phase 004 PermissionEngine.
   Per-type, per-operation access control. Read/write/delete permission matrix.

2. **MemoryRetriever** — Unified retrieval with semantic search, ranking, filtering.
   Combined score = semantic_similarity × 0.5 + recency × 0.3 + confidence × 0.2.
   Falls back to keyword matching if embeddings unavailable.

3. **MemoryWriter** — Validated, permission-checked writes.
   Pipeline: validate → check permissions → check contradictions → store.
   Wraps existing ValidationPipeline and PoisoningResistance from Phase 1.

4. **MemoryVerifier** — Truth reconciliation.
   Compare stored memories against new observations. Resolve conflicts:
   OVERWRITE (new wins), REJECT (keep stored), FLAG (human review).

5. **MemoryDecay** — Lifecycle management.
   TTL expiration, importance scoring, short-term → long-term promotion,
   low-importance demotion.

6. **WorldStateManager** — Structured world state from memories.
   Current state snapshot, state diff on update, state history,
   historical reconstruction at timestamp.

7. **MemoryManager** — Orchestrator (single entry point for CoreSupervisor).
   recall() before PLANNING, remember() after EVALUATE,
   get_context_for_planning() for prompt injection.

### CoreSupervisor Integration

```
GOAL → recall() → PLAN (with memory context) → EXECUTE → OBSERVE →
EVALUATE → remember() → [next iteration or complete]
```

### Existing Baseline (Phase 1)

- MemoryType enum (6 types: SHORT_TERM, WORKING, EPISODIC, SEMANTIC, PROCEDURAL, AUDIT_TRAIL)
- MemoryEntry + 5 subclasses (ShortTerm, Working, Episodic, Semantic, Procedural)
- Provenance tracking (writer_id, permissions, source_type)
- RetentionPolicy (EPHEMERAL, SESSION, LONG_TERM, PERMANENT)
- PoisoningMetadata (anomaly_score, rate_limit, source_verified)
- EmbeddingService (OpenAI text-embedding-3-large, cosine similarity)
- ContradictionDetector (cosine threshold + exact match)
- PoisoningResistance (rate limiting, source verification, anomaly detection)
- ValidationPipeline (multi-stage validation before storage)
- MemoryStore (SQLite-backed, cognitive/audit separation)
- PgVectorStore (pgvector for semantic search, fallback to cosine)
- 7 existing tests (tests/unit/test_memory_system.py)

## 6. Dependencies

| Dependency | Version | License | Status |
|------------|---------|---------|--------|
| Python | ≥3.11 | PSF | ✅ Existing |
| SQLite3 | stdlib | PSF | ✅ Existing |
| asyncpg | optional | BSD | ✅ Existing |
| pgvector | optional | PostgreSQL | ✅ Existing |
| OpenAI API | — | Commercial | ✅ Existing |
| src/core (Phase 004) | — | Apache 2.0 | ✅ VERIFIED |

**No new dependencies.** Phase 005 builds entirely on existing modules.

## 7. Test Plan (target: ~45 tests)

| Suite | Tests | Coverage |
|-------|-------|----------|
| TestMemoryManager | 6 | Orchestrator: remember, recall, context, verify, integration |
| TestMemoryRetriever | 8 | Semantic search, type filter, recent, related, ranking, fallback |
| TestMemoryWriter | 6 | Write, batch, update, delete, permission denial, validation rejection |
| TestMemoryVerifier | 5 | Verify, resolve conflict (3 modes), confidence trend |
| TestMemoryPermissions | 7 | Read/write/delete per level and type, all denial paths |
| TestMemoryDecay | 5 | Expire, importance score, promote, demote, consolidate |
| TestWorldStateManager | 5 | Current state, update, history, state-at-timestamp, diff |
| TestCoreMemoryIntegration | 5 | Full lifecycle with memory: recall → plan → execute → remember |

## 8. Current Repository State

- **Commit:** 8e8404a on main
- **Tests:** 880 passed, 9 skipped, 0 failed (excluding Phase 005 tests — WIP)
- **Ruff:** Clean on src/memory/
- **Mypy:** Clean on src/memory/ (9 source files)
- **Phase 005 test files exist** but need API alignment (implementation paused)

## 9. Known Limitations

1. No distributed memory — single-node SQLite/PostgreSQL
2. Embedding dependency — semantic retrieval requires OpenAI API, fallback to keyword
3. No memory sharing between agents — each ORION instance has own memory
4. No memory compression — long-term memories stored verbatim

## 10. Known Risks

1. Memory poisoning via inference — mitigated by ValidationPipeline + contradiction detection
2. Retrieval latency on large stores — mitigated by pgvector index, result limiting
3. State drift if observations infrequent — mitigated by confidence decay + verification

## 11. Reproduction Commands

```bash
# Verify existing tests pass
python -m pytest tests/unit/test_memory_system.py -v

# Verify lint/type check on Phase 005 code
ruff check src/memory/
mypy src/memory/ --ignore-missing-imports

# Verify imports
python -c "from src.memory import MemoryManager, MemoryPermissions, MemoryRetriever, MemoryWriter, MemoryVerifier, MemoryDecay, WorldStateManager; print('OK')"

# View the specification
cat docs/specs/PHASE005_MEMORY_SPEC.md
```

## 12. Request to Luna

Independently review the Phase 005 Memory System specification
(docs/specs/PHASE005_MEMORY_SPEC.md, commit 8e8404a) and determine whether:

1. The architecture satisfies all 12 acceptance criteria
2. The 7 new components are sufficiently specified
3. The integration with Phase 004 CoreSupervisor is sound
4. The test plan covers all acceptance criteria
5. Any gaps, missing components, or architectural concerns exist
6. The existing Phase 1 baseline is properly leveraged
7. Security considerations (memory poisoning, permissions) are adequate

Provide a verdict: APPROVED, APPROVED_WITH_CONDITIONS, or REQUIRES_CHANGES.
List any required changes before implementation can proceed.
