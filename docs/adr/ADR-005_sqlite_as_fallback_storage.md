# ADR-005: SQLite as Fallback Storage

- **Decision ID:** ADR-005
- **Date:** 2026-08-20
- **Owner:** ORION Supervisor
- **Reversible?:** Yes (architecture decisions can be revised in future versions)

## Context
The ORION project is a Physical Intelligence OS. Hierarchy: Founder → Architect/Reviewer Luna (GPT-5.6) → ORION Supervisor → Specialized Agents. All work follows the lifecycle: Specification → Architecture → Implementation → Test → Verification → Review → Approval → Next Stage.

Mobile physical agents (such as field quadrupeds, inspection drones, and agricultural robots) frequently operate in remote, air-gapped, or network-degraded environments where external PostgreSQL server connectivity is unavailable or network partitions occur.

## Problem
How should ORION maintain transactional persistence for state estimations, memory entries, action logs, and audit trails when PostgreSQL is unreachable or when running on lightweight embedded compute units?

## Options
1. **Require PostgreSQL Unconditionally:** System halts or throws critical unhandled connection exceptions if PostgreSQL is unreachable.
   - *Pros:* Single database engine codebase to maintain.
   - *Cons:* Complete system failure on standalone embedded field hardware or during network isolation.
2. **Raw File-System Flat Files (JSON / CSV):** Write state and audit logs directly to local disk files.
   - *Pros:* Extremely simple file I/O.
   - *Cons:* No transactional ACID guarantees, prone to corruption on sudden power loss, lacks SQL query and indexing capabilities.
3. **Embedded SQLite with Automated `StorageFactory` Fallback:** Zero-configuration local database fallback using Python's standard `sqlite3` library.
   - *Pros:* Zero external process dependencies, serverless, transactional ACID compliant, WAL mode support for concurrent reads, public domain / open license, seamless API parity with primary storage.
   - *Cons:* Lower write concurrency than PostgreSQL server, requires local Python vector cosine similarity search fallback.

## Decision
Implement **SQLite** as the designated secondary fallback storage engine, managed automatically via **`StorageFactory`**.

## Reason
`StorageFactory` attempts connection to PostgreSQL (`PostgresStorageManager`) first; if PostgreSQL is unreachable, missing, or fails health checks, `StorageFactory` seamlessly instantiates the embedded SQLite storage manager (`StorageManager` in `src/persistence/storage.py`). This guarantees that ORION units boot reliably on any target system—from cloud clusters to embedded micro-controllers—without code changes or loss of transactional storage capabilities.

## Evidence
- Implemented in `orion/implementation/src/persistence/storage.py` and `storage_factory.py`.
- Verified in `test_phase1.py` unit tests, confirming automatic failover to SQLite and full schema parity for memory and audit trail tables.

## Trade-offs
- **Write Concurrency:** SQLite WAL mode handles single-writer / multi-reader concurrency well, but cannot match PostgreSQL's multi-client concurrent write throughput.
- **Vector Extension:** SQLite lacks native `pgvector` extensions.
- **Mitigation:** Implemented Python in-memory vector cosine similarity calculation in `PgVectorStore` when operating in SQLite fallback mode (`src/persistence/pgvector_store.py`).
