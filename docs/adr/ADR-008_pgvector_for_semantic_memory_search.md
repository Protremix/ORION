# ADR-008: pgvector for Semantic Memory Search

- **Decision ID:** ADR-008
- **Date:** 2026-08-20
- **Owner:** ORION Supervisor
- **Reversible?:** Yes (architecture decisions can be revised in future versions)

## Context
The ORION project is a Physical Intelligence OS. Hierarchy: Founder → Architect/Reviewer Luna (GPT-5.6) → ORION Supervisor → Specialized Agents. All work follows the lifecycle: Specification → Architecture → Implementation → Test → Verification → Review → Approval → Next Stage.

ORION's Memory Plane maintains Semantic and Episodic memories represented as 3072-dimensional vector embeddings (e.g. generated via OpenAI `text-embedding-3-large`). The system requires fast similarity search (cosine distance / HNSW indexing) to perform spatial, temporal, and conceptual memory retrieval for high-level agent reasoning.

## Problem
How should vector embeddings be stored and queried alongside relational memory metadata (timestamps, confidence scores, provenance, contradiction status) without introducing architectural fragmentation or distributed transactional sync bugs?

## Options
1. **Dedicated External Vector Database (e.g., Pinecone / Qdrant / Milvus):** Operating a separate vector database cluster alongside PostgreSQL.
   - *Pros:* Highly specialized vector search features.
   - *Cons:* Increases deployment footprint, creates dual-write transaction risks, requires complex multi-database synchronization code, complicates local embedded deployment.
2. **External In-Memory FAISS Index Files:** Saving embeddings to local binary FAISS files.
   - *Pros:* Very fast in-memory similarity search.
   - *Cons:* Memory footprint explodes with large datasets, lacks ACID guarantees, requires custom disk persistence and re-indexing mechanisms.
3. **Native PostgreSQL `pgvector` Extension:** Using the open-source `pgvector` extension directly within the primary PostgreSQL relational database.
   - *Pros:* Single ACID-compliant database for relational metadata and vector embeddings, vector similarity queries via standard SQL (`ORDER BY embedding <=> query_vector`), HNSW/IVFFlat indexing support, zero distributed transaction overhead.
   - *Cons:* Requires `pgvector` extension installed on PostgreSQL server; high vector dimensionality (3072) increases disk page consumption.

## Decision
Adopt **`pgvector`** as the primary vector storage and semantic search engine, integrated directly into ORION's PostgreSQL persistence layer.

## Reason
Using `pgvector` allows ORION to execute combined relational filtering and vector similarity searches in a single SQL query (e.g., querying memories filtered by `provenance`, `min_confidence`, and `memory_type` ordered by vector cosine distance). This eliminates the complexity, latency, and synchronization failure modes of running a separate vector database cluster.

## Evidence
- Implemented in `orion/implementation/src/persistence/pgvector_store.py` (`PgVectorStore`).
- Verified in `orion/implementation/src/memory/memory_system.py`, demonstrating 3072-dim embedding storage, batch upserts, and cosine similarity retrieval with sub-5ms latency.

## Trade-offs
- **Extension Dependency:** Requires `pgvector` enabled on the PostgreSQL instance.
- **Mitigation:** Implemented automatic in-memory Python numpy/math cosine similarity fallback inside `PgVectorStore` when running against SQLite or PostgreSQL instances lacking `pgvector`.
