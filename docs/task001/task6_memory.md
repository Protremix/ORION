# ORION TASK 001 — TASK 6: ORION Memory Architecture

## Overview

ORION's memory system must support working, episodic, semantic, project, world, and decision memory — with provenance, timestamps, confidence, and corrections.

## Current Implementation (VERIFIED FACT)

ORION currently has:
- **SQLite persistence** — task state, checkpoints, audit logs
- **PostgreSQL persistence** — production storage with asyncpg
- **TaskStateManager** — full task lifecycle, checkpoints, shutdown/resume
- **pgvector integration** — vector embeddings for semantic search
- **Audit log replication** — cross-domain safety audit trail
- 463 tests covering all persistence layers

## Full Memory Architecture

### Memory Types

```
ORION MEMORY
├── Working Memory (short-term, in-memory)
│   ├── Current task context
│   ├── Active goals and sub-goals
│   ├── Recent observations (last N seconds)
│   └── Active hypotheses
│
├── Episodic Memory (event sequences)
│   ├── Past episodes (what happened, when, where)
│   ├── Action-outcome pairs (what we did, what resulted)
│   ├── Error episodes (what went wrong, how we recovered)
│   └── Success episodes (what worked, how)
│
├── Semantic Memory (facts and knowledge)
│   ├── Domain knowledge (how machines work, traffic rules)
│   ├── Entity definitions (what is a robot, what is a furnace)
│   ├── Relationship knowledge (A causes B, X is part of Y)
│   └── Knowledge from external sources (papers, databases)
│
├── Project Memory (task and project tracking)
│   ├── Project goals and milestones
│   ├── Architecture decisions and rationale (ADR)
│   ├── Dependency and license registry
│   ├── Test results and benchmarks
│   └── Code and documentation state
│
├── World Memory (persistent world knowledge)
│   ├── Entity histories (what has this machine done over its lifetime)
│   ├── Environment models (this factory's layout, this city's traffic)
│   ├── Behavioral patterns (how does this system usually behave)
│   ├── Anomaly records (when did things deviate from normal)
│   └── Causal models (what causes what in this environment)
│
└── Decision Memory (choices made)
    ├── Decision log (what was decided, when, by whom, why)
    ├── Alternatives considered (what else could have been done)
    ├── Outcomes (what happened after the decision)
    ├── Corrections (when was a decision found to be wrong)
    └── Policy memory (what rules guide similar future decisions)
```

### Storage Strategy

| Memory Type | Storage | Rationale |
|-------------|---------|-----------|
| Working | In-memory (RAM) | Speed: needs sub-millisecond access |
| Episodic | PostgreSQL (relational) + pgvector | Need temporal queries + semantic similarity |
| Semantic | Knowledge graph + pgvector | Need graph traversal + semantic search |
| Project | PostgreSQL (relational) + Git | Need structured queries + version history |
| World | PostgreSQL + pgvector + time-series | Need historical queries + similarity + trends |
| Decision | PostgreSQL (relational, append-only) | Need audit trail, never modify |

### Provenance and Confidence

Every memory entry has:
```python
@dataclass
class MemoryEntry:
    id: str
    type: MemoryType           # working, episodic, semantic, etc.
    content: Any               # The actual memory
    source: str                # Where it came from
    source_type: str           # observation, inference, external, user
    timestamp: float           # When it was created
    confidence: float          # 0.0-1.0
    provenance: List[str]      # Chain of sources
    tags: List[str]            # For retrieval
    domain: str                # Which domain
    correction_id: Optional[str]  # If this corrects a previous entry
    superseded_by: Optional[str]  # If this was corrected later
```

### Correction Mechanism

When new information contradicts old information:
1. Don't delete the old entry — mark it `superseded_by` the new entry
2. Create the new entry with `correction_id` pointing to the old one
3. Adjust confidence of both entries
4. Log the correction in the decision memory
5. Notify dependent systems (world model, planner)

This preserves the full history and allows rollback if the correction is itself wrong.

### Memory Retrieval

```python
class MemoryRetriever:
    def query_working(self, key: str) -> Any
    def query_episodic(self, time_range: Tuple[float, float], domain: str) -> List[Episode]
    def query_semantic(self, query: str, limit: int) -> List[MemoryEntry]
        # Uses pgvector for semantic similarity
    def query_project(self, project_id: str) -> ProjectState
    def query_world(self, entity_id: str, time_range: Tuple[float, float]) -> EntityHistory
    def query_decisions(self, domain: str, time_range: Tuple[float, float]) -> List[Decision]
```

### Memory Consolidation

Periodic process that:
1. **Promotes** working memory → episodic (important recent events)
2. **Summarizes** episodic → semantic (patterns extracted from episodes)
3. **Compresses** old episodic entries (keep summaries, delete details)
4. **Updates** confidence based on consistency (entries confirmed by multiple sources → higher confidence)
5. **Forgets** low-confidence, old, unused entries (with configurable retention policy)

## What Should Be Structured/Relational vs Vector vs Graph

| Data Type | Storage | Why |
|-----------|---------|-----|
| Task state, checkpoints | Relational (SQL) | Structured, queried by ID/status/time |
| Audit logs | Relational (append-only) | Never modified, time-ordered |
| Entity properties | Relational + JSON | Structured fields + flexible properties |
| Semantic knowledge | Graph (Neo4j/NetworkX) | Relationship traversal |
| Text/content embeddings | Vector (pgvector) | Semantic similarity search |
| Raw documents | Document store (SQL JSON) | Full-text + metadata |
| Time-series (sensor data) | Time-series (TimescaleDB) | Efficient temporal queries |
| Decision history | Relational (append-only) | Audit trail |

## Integration with Existing System

Current ORION memory → Full architecture mapping:
- SQLite/PostgreSQL tables → Project Memory + Decision Memory
- TaskStateManager → Working Memory (active tasks) + Episodic (completed tasks)
- pgvector → Semantic Memory (embedding search)
- Audit logs → Decision Memory (append-only)
- World Model state → World Memory (entity histories)

**Gap:** No dedicated Semantic Memory (knowledge graph), no consolidation process, no correction mechanism.

**Priority:** Build knowledge graph → consolidation → correction mechanism

## Benchmarks (from Master Spec §20)

- **Memory accuracy:** Can ORION recall specific past events?
- **Memory consistency:** Do memories contradict each other?
- **Forgetting curve:** How much information is retained over time?
- **Retrieval speed:** How fast can relevant memories be found?
- **Provenance tracking:** Can the source of any claim be traced?
