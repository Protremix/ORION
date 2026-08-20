# ADR-003: PostgreSQL with asyncpg for Persistence

- **Decision ID:** ADR-003
- **Date:** 2026-08-20
- **Owner:** ORION Supervisor
- **Reversible?:** Yes (architecture decisions can be revised in future versions)

## Context
The ORION project is a Physical Intelligence OS. Hierarchy: Founder → Architect/Reviewer Luna (GPT-5.6) → ORION Supervisor → Specialized Agents. All work follows the lifecycle: Specification → Architecture → Implementation → Test → Verification → Review → Approval → Next Stage.

ORION's cognitive memory systems, belief state estimation, telemetry audit logs, and multi-agent coordination frameworks generate continuous streams of structured transactional data. The persistence layer must sustain high-concurrency read/write operations without blocking Python's `asyncio` event loop during real-time 100Hz operational ticks.

## Problem
What primary database engine and database driver should ORION utilize for enterprise-grade persistent data storage, concurrent state retrieval, and audit trail logging?

## Options
1. **Synchronous PostgreSQL Driver (`psycopg2`) with Thread Pools:** Traditional relational database driver wrapped in `asyncio.to_thread`.
   - *Pros:* Mature ecosystem, widely used.
   - *Cons:* Thread-pool context switching overhead, potential thread starvation under high concurrent load, higher latency jitter.
2. **Asynchronous MySQL / MariaDB (`aiomysql`):** Relational database using MySQL async driver.
   - *Pros:* Popular in web applications.
   - *Cons:* Lacks native vector search extension support (`pgvector`), weaker JSONB document query capabilities, less robust transactional concurrency.
3. **PostgreSQL with `asyncpg`:** High-performance, pure-async PostgreSQL client library implementing PostgreSQL's binary protocol directly.
   - *Pros:* Native asynchronous non-blocking I/O, up to 3x faster execution than psycopg2, direct binary protocol encoding/decoding, BSD-licensed, native support for PostgreSQL `JSONB` and extension ecosystem (`pgvector`).
   - *Cons:* Requires running a PostgreSQL database process in server/edge-cluster deployments.

## Decision
Adopt **PostgreSQL** as the primary persistent database engine, accessed via **`asyncpg`** connection pools (`asyncpg.create_pool`).

## Reason
`asyncpg` is specifically optimized for Python `asyncio`, communicating directly over PostgreSQL's wire protocol without C-extension ORM bottlenecks or synchronous blocking. This enables sub-millisecond database queries for state updates, audit events, and memory records directly inside ORION's async services without degrading real-time responsiveness. The BSD license of `asyncpg` is fully compatible with ORION's Apache 2.0 licensing.

## Evidence
- Benchmarked and implemented in `orion/implementation/src/persistence/postgres_storage.py`.
- Tested in `SCALABILITY_REPORT.md`, demonstrating connection pool connection scaling up to 1,000+ concurrent requests/sec with average query latencies under 0.8ms.

## Trade-offs
- **Deployment Requirement:** Server or edge-cluster deployments must host a running PostgreSQL instance.
- **Mitigation:** Implemented automatic zero-config fallback to embedded SQLite (`StorageFactory`) for standalone or disconnected embedded field devices (see ADR-005).
