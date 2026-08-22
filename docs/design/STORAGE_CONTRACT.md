# ORION Memory Storage Contract

**Phase:** 005
**Status:** Active
**License:** Apache 2.0

## Overview

This document formally specifies the storage contract for the ORION Memory subsystem.
It defines the interface, capabilities, and behavior expected from the MemoryStore
backend used by all Phase 005 components.

## Storage Backend

- **Primary:** SQLite (embedded, file-based or in-memory)
- **Future:** PostgreSQL + pgvector (not yet wired, interface-compatible)
- **Connection:** `sqlite3.connect(db_path, check_same_thread=False)`
- **Thread Safety:** Connection shared across threads (check_same_thread=False)

## Schema

### cognitive_memories table

| Column | Type | Description |
|---|---|---|
| id | TEXT PK | Unique memory ID |
| memory_type | TEXT NOT NULL | Enum: short_term, working, episodic, semantic, procedural, audit_trail |
| content_json | TEXT NOT NULL | JSON-serialized content dict |
| summary | TEXT | Optional human-readable summary |
| embedding_json | TEXT | JSON-serialized embedding vector (nullable) |
| writer_id | TEXT NOT NULL | Identity of writer |
| writer_permissions_json | TEXT NOT NULL | JSON array of permission strings |
| source_type | TEXT NOT NULL | Enum: agent, human, inference, sensor |
| source_plane | TEXT NOT NULL | Source plane identifier |
| confidence | REAL NOT NULL | Confidence score [0.0, 1.0] |
| timestamp | REAL NOT NULL | Unix timestamp |
| created_at | TEXT NOT NULL | ISO datetime |
| updated_at | TEXT NOT NULL | ISO datetime |
| version | INTEGER NOT NULL | Version counter for optimistic concurrency |
| schema_version | TEXT NOT NULL | Schema version string |
| retention_type | TEXT NOT NULL | Enum: session, short_term, long_term, permanent |
| ttl_seconds | REAL | Time-to-live in seconds (nullable) |
| expires_at | REAL | Expiration timestamp (nullable) |
| contradiction_status | TEXT NOT NULL | Enum: none, flag, resolved, reject |
| contradicting_ids_json | TEXT NOT NULL | JSON array of conflicting memory IDs |
| poisoning_metadata_json | TEXT NOT NULL | JSON poisoning check metadata |
| is_deleted | INTEGER NOT NULL DEFAULT 0 | Soft-delete flag |

### audit_trail table (SEPARATE — tamper-evident)

| Column | Type | Description |
|---|---|---|
| id | TEXT PK | Unique audit entry ID |
| event_type | TEXT NOT NULL | Event type enum |
| actor_id | TEXT NOT NULL | Actor identity |
| action | TEXT NOT NULL | Action performed |
| payload_json | TEXT NOT NULL | JSON event payload |
| timestamp | REAL NOT NULL | Unix timestamp |
| created_at | TEXT NOT NULL | ISO datetime |
| previous_hash | TEXT NOT NULL | Hash of previous entry (chain) |
| hash | TEXT NOT NULL | SHA-256 hash of this entry |
| source_type | TEXT NOT NULL | Source type enum |
| retention_type | TEXT NOT NULL | Retention policy |

## Interface Contract

### Required Operations

```python
class MemoryStore:
    # Lifecycle
    def __init__(self, db_path: str = ":memory:", ...) -> None
    def close(self) -> None

    # Write
    def write_memory(self, entry: MemoryEntry, actor_permissions: List[str]) -> Tuple[Optional[MemoryEntry], ValidationResult]
    def update_memory(self, memory_id: str, updates: Dict, actor_permissions: List[str]) -> bool
    def delete_memory(self, memory_id: str, actor_permissions: List[str]) -> bool

    # Read
    def get_memory(self, memory_id: str) -> Optional[MemoryEntry]
    def query_memories(self, memory_type: Optional[MemoryType] = None, limit: int = 100, include_deleted: bool = False) -> List[MemoryEntry]
    def search_semantic(self, query_text: str, top_k: int = 10) -> List[Tuple[MemoryEntry, float]]

    # Audit (separate path)
    def append_audit(self, event: AuditEvent) -> bool
    def query_audit(self, limit: int = 100) -> List[Dict]
```

### Transaction Behavior

- **Atomic writes:** Each write/update/delete is wrapped in `with self.conn:` (auto-commit/rollback)
- **Batch writes:** `write_batch()` iterates individually (no batch transaction)
- **Rollback:** On exception, SQLite auto-rolls the current `with` block
- **Concurrency:** Single connection, shared across threads (no write concurrency guarantee)

### Soft-Delete Filtering

- `query_memories(include_deleted=False)` filters `is_deleted = 0` by default
- `get_memory()` returns entries regardless of deletion status
- `delete_memory()` sets `is_deleted = 1` (soft delete, not physical removal)

### Expiration Filtering

- `query_memories()` filters expired entries (`expires_at < now`) when `include_deleted=False`
- Expired entries are not physically removed until decay process runs

### Embedding Storage

- Embeddings stored as JSON-serialized vectors in `embedding_json` column
- Generated automatically for SEMANTIC type or when summary is provided
- Model: Configurable via `EmbeddingService` (default: deterministic local embedding)
- Dimensionality: Determined by embedding service (not fixed in schema)

### Schema Versioning

- `schema_version` field on each entry tracks individual entry schema
- No migration framework yet (future: pgvector backend will require migrations)
- Current schema version: "1.0"

### Retention Types

| Type | Behavior |
|---|---|
| SESSION | Survives within session, eligible for decay after session end |
| SHORT_TERM | TTL-based expiration, default 1 hour |
| LONG_TERM | No automatic expiration, eligible for consolidation |
| PERMANENT | Never expires, never consolidated |

### Access Count & Confidence History

- Access count: Not currently tracked (future enhancement)
- Confidence history: Stored via version counter, no explicit history table

### Contradiction Links

- `contradicting_ids_json` stores JSON array of conflicting memory IDs
- `contradiction_status` tracks resolution state (none, flag, resolved, reject)

## Cognitive/Audit Separation

**Critical security invariant:**
- `cognitive_memories` table: mutable, soft-deletable, queryable by all authorized users
- `audit_trail` table: append-only, tamper-evident (hash chain), NOT modifiable via generic APIs
- No foreign key relationship (intentional separation)
- Phase 005 `MemoryPermissions` enforces: AUDIT_TRAIL writes/deletes denied via generic APIs

## pgvector Backend (Future)

When pgvector is wired:
- `search_semantic()` will use pgvector's `<=>` (cosine) operator
- Embeddings stored in `vector` column instead of JSON
- Interface remains identical (swap backend, not API)
- Migration required from SQLite to PostgreSQL schema

## Behavior Under Concurrent Access

- SQLite with `check_same_thread=False` allows multi-threaded access
- No explicit locking — SQLite handles row-level locking internally
- Concurrent writes may raise `sqlite3.OperationalError` (database locked)
- Recommended: single-writer pattern for production use
