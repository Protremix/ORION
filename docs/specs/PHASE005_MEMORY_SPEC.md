# ORION Phase 005 — Memory System Specification

**Project:** ORION — Physical Intelligence OS
**Phase:** 005 — Memory
**Architecture Version:** v0.5
**License:** Apache 2.0
**Date:** 2026-08-22
**Author:** ORION Supervisor (Selene)
**Reviewer:** Luna (GPT-5.6)

---

## 1. Overview

Phase 005 upgrades ORION's memory subsystem from a standalone Phase 1 baseline
into a fully integrated component of ORION Core. The existing `src/memory/`
module (1,267 lines) provides the foundation: 6 memory types, provenance
tracking, contradiction detection, poisoning resistance, validation pipeline,
and SQLite-backed MemoryStore. Phase 005 extends this with retrieval,
cross-session persistence, memory verification, and memory permissions —
integrating directly with the CoreSupervisor lifecycle.

**Key Principle:** Memory is NOT a passive log. It is an active, queryable,
verified knowledge base that the Supervisor consults during planning and
updates after execution. Memory poisoning is the #1 attack vector for
autonomous agents — every write is validated, every read is permission-checked.

---

## 2. Existing Baseline (Phase 1)

### What Already Exists

| Component | Module | Lines | Status |
|-----------|--------|-------|--------|
| MemoryType enum | `src/memory/memory_system.py` | — | ✅ 6 types |
| MemoryEntry + 5 subclasses | `src/memory/memory_system.py` | ~200 | ✅ ShortTerm, Working, Episodic, Semantic, Procedural |
| Provenance tracking | `src/memory/memory_system.py` | ~30 | ✅ writer_id, permissions, source_type |
| RetentionPolicy | `src/memory/memory_system.py` | ~30 | ✅ EPHEMERAL, SESSION, LONG_TERM, PERMANENT |
| PoisoningMetadata | `src/memory/memory_system.py` | ~25 | ✅ anomaly_score, rate_limit, source_verified |
| EmbeddingService | `src/memory/memory_system.py` | ~80 | ✅ OpenAI text-embedding-3-large, cosine similarity |
| ContradictionDetector | `src/memory/memory_system.py` | ~60 | ✅ Cosine threshold + exact match |
| PoisoningResistance | `src/memory/memory_system.py` | ~80 | ✅ Rate limiting, source verification, anomaly detection |
| ValidationPipeline | `src/memory/memory_system.py` | ~60 | ✅ Multi-stage validation before storage |
| MemoryStore | `src/memory/memory_system.py` | ~400 | ✅ SQLite-backed, cognitive/audit separation |
| PgVectorStore | `src/persistence/pgvector_store.py` | — | ✅ pgvector for semantic search, fallback to cosine |
| StorageManager | `src/persistence/storage.py` | — | ✅ SQLite CRUD, hash chain, export/import |
| Tests | `tests/unit/test_memory_system.py` | 207 | ✅ 7 tests passing |

### What's Missing (Phase 005 Scope)

1. **Retrieval API** — No unified query interface for the Supervisor to fetch
   relevant memories by goal, context, or semantic similarity
2. **Cross-session persistence** — Current MemoryStore uses SQLite but no
   session disconnect/reconnect lifecycle
3. **Memory verification** — No mechanism to verify stored memories against
   new observations (truth reconciliation)
4. **Memory permissions** — No integration with PermissionEngine from Phase 004
5. **Core integration** — No hooks in CoreSupervisor lifecycle for REMEMBER step
6. **Structured world state** — No maintained world state model from memories
7. **Decay and consolidation** — No automatic promotion of short-term → long-term
8. **Context injection** — No mechanism to inject relevant memories into
   planning prompts

---

## 3. Architecture

### 3.1 Component Diagram

```
CoreSupervisor
    ↓ (REMEMBER step)
MemoryManager (NEW — orchestrator)
    ├── MemoryRetriever (NEW — query + rank)
    │   ├── semantic search (EmbeddingService / PgVectorStore)
    │   ├── temporal filter
    │   └── type filter
    ├── MemoryWriter (NEW — validated writes)
    │   ├── ValidationPipeline (existing)
    │   ├── PoisoningResistance (existing)
    │   └── ContradictionDetector (existing)
    ├── MemoryVerifier (NEW — truth reconciliation)
    │   ├── observation comparison
    │   ├── confidence update
    │   └── contradiction resolution
    ├── MemoryPermissions (NEW — PermissionEngine integration)
    │   ├── read permissions (per type)
    │   ├── write permissions (per source)
    │   └── delete permissions (ADMIN only)
    ├── MemoryDecay (NEW — lifecycle management)
    │   ├── TTL expiration
    │   ├── consolidation (short → long term)
    │   └── importance scoring
    └── WorldStateManager (NEW — structured state from memories)
        ├── current state snapshot
        ├── state diff on update
        └── state history
```

### 3.2 Module Structure

```
src/memory/
├── __init__.py              (existing — update exports)
├── memory_system.py         (existing — no changes to core classes)
├── memory_manager.py        (NEW — orchestrator, CoreSupervisor integration)
├── memory_retriever.py      (NEW — retrieval + ranking)
├── memory_writer.py          (NEW — validated writes)
├── memory_verifier.py       (NEW — truth reconciliation)
├── memory_permissions.py    (NEW — PermissionEngine integration)
├── memory_decay.py           (NEW — TTL, consolidation, importance)
└── world_state_manager.py    (NEW — structured world state)
```

---

## 4. Component Specifications

### 4.1 MemoryManager (Orchestrator)

**Purpose:** Single entry point for CoreSupervisor. Manages the REMEMBER
lifecycle step and coordinates all memory subsystems.

**Interface:**
```python
class MemoryManager:
    def __init__(self, store: MemoryStore, retriever: MemoryRetriever,
                 writer: MemoryWriter, verifier: MemoryVerifier,
                 permissions: MemoryPermissions, decay: MemoryDecay,
                 world_state: WorldStateManager) -> None: ...

    def remember(self, task: Task, observation: Dict[str, Any]) -> MemoryResult:
        """Called by CoreSupervisor after EVALUATE step. Stores observation,
        updates world state, runs decay, returns summary of what was stored."""

    def recall(self, goal: str, context: Optional[Dict] = None,
               max_results: int = 10) -> List[MemoryEntry]:
        """Called by CoreSupervisor before PLANNING. Retrieves relevant
        memories for the given goal."""

    def get_context_for_planning(self, goal: str) -> Dict[str, Any]:
        """Returns structured context dict with relevant memories, world state,
        and recent observations for injection into planning prompt."""

    def verify_memories(self, observations: List[Dict]) -> VerificationReport:
        """Run verification pass — compare stored memories against new
        observations. Returns conflicts, updates, and confidence changes."""
```

**Integration point in CoreSupervisor.run():**
```
GOAL → recall() → PLAN (with memory context) → EXECUTE → OBSERVE →
EVALUATE → remember() → [next iteration or complete]
```

### 4.2 MemoryRetriever

**Purpose:** Unified retrieval interface with ranking and filtering.

**Interface:**
```python
class MemoryRetriever:
    def __init__(self, store: MemoryStore, embedding_service: EmbeddingService) -> None: ...

    def retrieve(self, query: str, memory_types: Optional[List[MemoryType]] = None,
                 min_confidence: float = 0.0, max_results: int = 10,
                 time_range: Optional[Tuple[float, float]] = None) -> List[MemoryEntry]:
        """Retrieve memories by semantic similarity to query.
        Uses EmbeddingService for embedding, MemoryStore for storage.
        Falls back to keyword matching if embeddings unavailable."""

    def retrieve_by_type(self, memory_type: MemoryType,
                         max_results: int = 50) -> List[MemoryEntry]:
        """Retrieve all memories of a specific type."""

    def retrieve_recent(self, n: int = 10,
                        memory_types: Optional[List[MemoryType]] = None) -> List[MemoryEntry]:
        """Retrieve N most recent memories."""

    def retrieve_related(self, memory_id: str,
                        max_results: int = 10) -> List[MemoryEntry]:
        """Retrieve memories related to a given memory (by shared entities,
        temporal proximity, or semantic similarity)."""
```

**Ranking:** Combined score = semantic_similarity × 0.5 + recency × 0.3 + confidence × 0.2

### 4.3 MemoryWriter

**Purpose:** Validated, permission-checked memory writes.

**Interface:**
```python
class MemoryWriter:
    def __init__(self, store: MemoryStore, validation: ValidationPipeline,
                 poisoning: PoisoningResistance, permissions: MemoryPermissions) -> None: ...

    def write(self, entry: MemoryEntry) -> WriteResult:
        """Validate → check permissions → check contradictions → store.
        Returns WriteResult with success status, conflicts found, and
        storage metadata."""

    def write_batch(self, entries: List[MemoryEntry]) -> List[WriteResult]:
        """Batch write with atomic transaction."""

    def update(self, memory_id: str, content: Dict[str, Any]) -> WriteResult:
        """Update existing memory. Increments version, logs provenance."""

    def delete(self, memory_id: str, requester: str) -> bool:
        """Soft-delete memory. Requires ADMIN permission."""
```

### 4.4 MemoryVerifier

**Purpose:** Truth reconciliation — compare stored memories against new
observations and resolve conflicts.

**Interface:**
```python
class MemoryVerifier:
    def __init__(self, store: MemoryStore, detector: ContradictionDetector) -> None: ...

    def verify(self, observations: List[Dict[str, Any]]) -> VerificationReport:
        """Compare observations against stored semantic memories.
        Returns conflicts, confirmations, and confidence updates."""

    def resolve_conflict(self, memory_id: str, observation: Dict,
                        resolution: ConflictResolution) -> bool:
        """Resolve a detected contradiction. Options:
        OVERWRITE (new observation wins), REJECT (keep stored),
        FLAG (requires human review)."""

    def get_confidence_trend(self, memory_id: str) -> List[float]:
        """Return confidence history for a memory entry."""
```

### 4.5 MemoryPermissions

**Purpose:** Integrate with Phase 004 PermissionEngine. Per-type, per-operation
permission enforcement for memory access.

**Interface:**
```python
class MemoryPermissions:
    def __init__(self, permission_engine: PermissionEngine) -> None: ...

    def can_read(self, memory_type: MemoryType, requester_level: PermissionLevel) -> bool:
        """Check read permission for memory type.
        - READ level: can read SHORT_TERM, WORKING
        - EXECUTE level: can read all except AUDIT_TRAIL
        - ADMIN level: can read all including AUDIT_TRAIL"""

    def can_write(self, memory_type: MemoryType, source_type: SourceType,
                 requester_level: PermissionLevel) -> bool:
        """Check write permission.
        - Agent (EXECUTE): can write SHORT_TERM, WORKING, EPISODIC
        - Human (ADMIN): can write all types
        - Inference: can only write SEMANTIC (with validation)
        - Sensor: can write SHORT_TERM, EPISODIC"""

    def can_delete(self, memory_type: MemoryType,
                  requester_level: PermissionLevel) -> bool:
        """Delete requires ADMIN for all types. Soft-delete only."""
```

### 4.6 MemoryDecay

**Purpose:** Automatic lifecycle management — TTL expiration, importance
scoring, and consolidation of short-term → long-term memories.

**Interface:**
```python
class MemoryDecay:
    def __init__(self, store: MemoryStore) -> None: ...

    def run_decay(self) -> DecayReport:
        """Run decay pass:
        1. Expire memories past TTL
        2. Score importance (access frequency × recency × confidence)
        3. Promote high-importance SHORT_TERM → LONG_TERM
        4. Demote low-importance LONG_TERM → archive
        Returns counts of expired, promoted, demoted."""

    def score_importance(self, memory_id: str) -> float:
        """Calculate importance score: 0.0-1.0.
        score = access_count_norm * 0.3 + recency_norm * 0.3 +
                confidence * 0.2 + contradiction_penalty * 0.2"""

    def consolidate(self, memory_ids: List[str]) -> Optional[str]:
        """Consolidate multiple related memories into a single semantic
        memory. Returns new memory ID or None if consolidation failed."""
```

### 4.7 WorldStateManager

**Purpose:** Maintain a structured snapshot of the current world state derived
from memory entries. Updated after each REMEMBER step.

**Interface:**
```python
class WorldStateManager:
    def __init__(self, store: MemoryStore) -> None: ...

    def get_current_state(self) -> Dict[str, Any]:
        """Return current world state snapshot:
        {entities, relations, timestamps, confidence_scores}"""

    def update_state(self, observation: Dict[str, Any]) -> StateDiff:
        """Apply observation to world state. Returns diff of what changed."""

    def get_state_history(self, key: str, n: int = 10) -> List[Dict]:
        """Return history of state changes for a given key."""

    def get_state_at(self, timestamp: float) -> Dict[str, Any]:
        """Reconstruct world state at a given timestamp."""
```

---

## 5. CoreSupervisor Integration

### 5.1 Lifecycle Update

The CoreSupervisor.run() method (Phase 004) is extended with memory hooks:

```python
def run(self, goal: str, context: Optional[Dict] = None,
        model: Optional[str] = None) -> Task:
    # NEW: Recall relevant memories before planning
    memory_context = self._memory.recall(goal, context)

    # PLAN (with memory context injected)
    plan_response = self._model_gateway.generate_plan(
        goal=goal,
        available_tools=available_tools,
        model=model,
        context=memory_context  # NEW parameter
    )

    # ... existing EXECUTE loop ...

    # NEW: REMEMBER step after EVALUATE
    if task.status == TaskStatus.COMPLETED:
        observation = self._build_observation(task)
        self._memory.remember(task, observation)

    return task
```

### 5.2 Context Injection Format

Memories injected into planning prompt as structured context:

```json
{
  "relevant_memories": [
    {"type": "episodic", "summary": "...", "confidence": 0.9, "timestamp": "..."},
    {"type": "semantic", "summary": "...", "confidence": 0.85}
  ],
  "world_state": {"entities": [...], "relations": [...]},
  "recent_observations": [...],
  "contradictions_flagged": [...]
}
```

---

## 6. Acceptance Criteria

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

---

## 7. Test Plan

### New Tests (target: ~40-50)

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

---

## 8. Dependencies

| Dependency | Version | License | Status |
|------------|---------|---------|--------|
| Python | ≥3.11 | PSF | ✅ Existing |
| SQLite3 | stdlib | PSF | ✅ Existing |
| asyncpg | optional | BSD | ✅ Existing (PostgreSQL) |
| pgvector | optional | PostgreSQL | ✅ Existing (semantic search) |
| OpenAI API | — | Commercial | ✅ Existing (embeddings) |
| src/core (Phase 004) | — | Apache 2.0 | ✅ VERIFIED |

**No new dependencies.** Phase 005 builds entirely on existing modules.

---

## 9. Known Limitations

1. **No distributed memory** — Single-node SQLite/PostgreSQL. Distributed
   memory store is a future phase.
2. **Embedding dependency** — Semantic retrieval requires OpenAI API or
   local embedding model. Fallback to keyword matching if unavailable.
3. **No memory sharing between agents** — Each ORION instance has its own
   memory. Multi-agent memory sharing is a future phase.
4. **No memory compression** — Long-term memories are stored verbatim.
   Summarization/compression is a future enhancement.

---

## 10. Known Risks

1. **Memory poisoning via inference** — LLM-generated semantic memories could
   reinforce wrong conclusions. Mitigation: ValidationPipeline + contradiction
   detection + confidence decay.
2. **Retrieval latency** — Semantic search on large memory stores may be slow.
   Mitigation: pgvector index, result limiting, caching.
3. **State drift** — World state may diverge from reality if observations are
   infrequent. Mitigation: confidence decay + verification pass.

---

## 11. Reproduction Commands

```bash
# Run Phase 005 tests (when implemented)
python -m pytest tests/unit/test_phase005.py -v

# Run full test suite
python -m pytest -q

# Lint + type check
ruff check src/memory/ tests/unit/test_phase005.py
mypy src/memory/ --ignore-missing-imports
```

---

## 12. Implementation Order

1. MemoryPermissions (integrates with Phase 004 PermissionEngine)
2. MemoryRetriever (uses existing EmbeddingService + MemoryStore)
3. MemoryWriter (wraps existing ValidationPipeline + PoisoningResistance)
4. MemoryVerifier (uses existing ContradictionDetector)
5. MemoryDecay (new — TTL, importance, consolidation)
6. WorldStateManager (new — structured state from memories)
7. MemoryManager (orchestrator — ties all together)
8. CoreSupervisor integration (recall + remember hooks)
9. Tests (incremental — write tests alongside each component)
10. Luna review package

---

## Request to Luna

Review this specification and determine whether it satisfies the Phase 005
acceptance criteria from the ORION Master Roadmap. Identify any gaps, missing
components, or architectural concerns before implementation begins.
