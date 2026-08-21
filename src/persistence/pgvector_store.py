# Copyright 2026 ORION Physical Intelligence OS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
ORION Physical Intelligence OS - PgVector Memory Embeddings Store.
Architecture Version: v0.6

Provides pgvector integration for storing and semantic searching of 3072-dimensional memory
embeddings with asyncpg. Includes automatic fallback to Python cosine similarity when pgvector
or PostgreSQL is unavailable.

License: Apache 2.0
"""

import json
import logging
import math
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from src.persistence.postgres_storage import PostgresStorageManager
except ImportError:
    PostgresStorageManager = None

logger = logging.getLogger("orion.persistence.pgvector")

# SQL Schema and Query Constants for PostgreSQL + pgvector
CREATE_VECTOR_EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS vector;"

CREATE_MEMORY_EMBEDDINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    embedding vector(3072) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
""".strip()

CREATE_MEMORY_EMBEDDINGS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_vector
ON memory_embeddings USING hnsw (embedding vector_cosine_ops);
""".strip()

STORE_EMBEDDING_SQL = """
INSERT INTO memory_embeddings (memory_id, text, embedding)
VALUES ($1, $2, $3::vector)
ON CONFLICT (memory_id)
DO UPDATE SET text = EXCLUDED.text, embedding = EXCLUDED.embedding, created_at = CURRENT_TIMESTAMP;
""".strip()

SEMANTIC_SEARCH_SQL = """
SELECT
    memory_id,
    text,
    embedding,
    1 - (embedding <=> $1::vector) AS similarity
FROM memory_embeddings
WHERE 1 - (embedding <=> $1::vector) >= $2
ORDER BY embedding <=> $1::vector ASC
LIMIT $3;
""".strip()

BATCH_STORE_EMBEDDINGS_SQL = """
INSERT INTO memory_embeddings (memory_id, text, embedding)
VALUES ($1, $2, $3::vector)
ON CONFLICT (memory_id)
DO UPDATE SET text = EXCLUDED.text, embedding = EXCLUDED.embedding, created_at = CURRENT_TIMESTAMP;
""".strip()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculates cosine similarity between two vector embeddings.
    Identical to EmbeddingService.cosine_similarity math in memory_system.py.
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    similarity = dot_product / (norm_a * norm_b)
    # Clamp to [-1.0, 1.0] to handle floating point rounding
    return max(-1.0, min(1.0, similarity))


class PgVectorStore(PostgresStorageManager):
    """
    PostgreSQL Storage Manager extended with pgvector for 3072-dim memory embeddings.

    Supports both live pgvector storage via asyncpg and in-memory Python fallback mode.
    """

    VECTOR_DIM = 3072

    def __init__(
        self,
        dsn: Optional[str] = None,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        database: str = "orion",
        min_size: int = 1,
        max_size: int = 10,
        connection_timeout: float = 5.0,
        db_path: Optional[Union[str, Path]] = None,
        pool: Optional[Any] = None,
        use_fallback: bool = False,
        **kwargs,
    ):
        self.fallback_mode = use_fallback
        self.has_pgvector = False
        self._fallback_store: Dict[str, Dict[str, Any]] = {}

        if use_fallback:
            self.pool = pool
            self._runner = None
            self._local = threading.local()
            logger.info("PgVectorStore initialized in explicit fallback mode (Python cosine similarity).")
            return

        try:
            super().__init__(
                dsn=dsn,
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                min_size=min_size,
                max_size=max_size,
                connection_timeout=connection_timeout,
                db_path=db_path,
                pool=pool,
                **kwargs,
            )
            self.has_pgvector = self.init_pgvector_schema()
            if not self.has_pgvector:
                self.fallback_mode = True
                logger.warning("pgvector extension check failed; switched to fallback mode.")
            else:
                logger.info("PgVectorStore initialized with active pgvector extension.")
        except Exception as e:
            logger.warning(f"PostgreSQL initialization failed for PgVectorStore ({e}); operating in fallback mode.")
            self.fallback_mode = True
            self.has_pgvector = False
            self.pool = None
            self._runner = None
            self._local = threading.local()

    def init_pgvector_schema(self) -> bool:
        """
        Executes schema creation SQL statements for pgvector extension, table, and HNSW index.
        Returns True if successful, False if pgvector is unavailable.
        """
        if self.fallback_mode or not getattr(self, "pool", None):
            return False

        try:
            self._execute_sql(CREATE_VECTOR_EXTENSION_SQL)
            self._execute_sql(CREATE_MEMORY_EMBEDDINGS_TABLE_SQL)
            self._execute_sql(CREATE_MEMORY_EMBEDDINGS_INDEX_SQL)
            return True
        except Exception as e:
            logger.warning(f"Failed to execute pgvector schema SQL: {e}")
            return False

    def store_embedding(
        self,
        memory_id: str,
        text: str,
        embedding_vector: List[float],
    ) -> Dict[str, Any]:
        """
        Stores a 3072-dimensional vector embedding for a memory entry using pgvector's vector type.

        In fallback mode, stores the vector in-memory.

        Args:
            memory_id: Unique memory entry identifier
            text: Text content or summary
            embedding_vector: Vector of floats (3072 dims)

        Returns:
            Dict containing status and metadata.
        """
        if len(embedding_vector) != self.VECTOR_DIM:
            logger.warning(
                f"Embedding vector dimension mismatch: expected {self.VECTOR_DIM}, got {len(embedding_vector)}"
            )

        if self.fallback_mode:
            record = {
                "memory_id": memory_id,
                "text": text,
                "embedding": list(embedding_vector),
                "created_at": time.time(),
            }
            self._fallback_store[memory_id] = record
            return {
                "memory_id": memory_id,
                "text": text,
                "status": "stored",
                "mode": "fallback",
            }

        vec_str = json.dumps(embedding_vector)

        async def _op():
            if self._in_transaction and self._current_conn is not None:
                await self._current_conn.execute(STORE_EMBEDDING_SQL, memory_id, text, vec_str)
            else:
                async with self.pool.acquire() as conn:
                    await conn.execute(STORE_EMBEDDING_SQL, memory_id, text, vec_str)

        self._run_async(_op())
        return {
            "memory_id": memory_id,
            "text": text,
            "status": "stored",
            "mode": "pgvector",
        }

    async def async_store_embedding(
        self,
        memory_id: str,
        text: str,
        embedding_vector: List[float],
    ) -> Dict[str, Any]:
        """Async variant of store_embedding for direct coroutine usage with asyncpg."""
        if self.fallback_mode or not self.pool:
            record = {
                "memory_id": memory_id,
                "text": text,
                "embedding": list(embedding_vector),
                "created_at": time.time(),
            }
            self._fallback_store[memory_id] = record
            return {
                "memory_id": memory_id,
                "text": text,
                "status": "stored",
                "mode": "fallback",
            }

        vec_str = json.dumps(embedding_vector)
        async with self.pool.acquire() as conn:
            await conn.execute(STORE_EMBEDDING_SQL, memory_id, text, vec_str)
        return {
            "memory_id": memory_id,
            "text": text,
            "status": "stored",
            "mode": "pgvector",
        }

    def semantic_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic search using cosine similarity/distance.

        In pgvector mode: Uses the '<=>' operator for cosine distance search.
        In fallback mode: Uses Python cosine similarity over stored vectors.

        Args:
            query_embedding: Query vector (3072 floats)
            limit: Max results to return (default 10)
            threshold: Minimum cosine similarity threshold (default 0.7)

        Returns:
            List of dicts: [{'memory_id': str, 'text': str, 'similarity': float, 'embedding': List[float]}]
            Sorted by similarity descending.
        """
        if self.fallback_mode:
            results = []
            for mem_id, rec in self._fallback_store.items():
                emb = rec.get("embedding")
                if not emb:
                    continue
                sim = cosine_similarity(query_embedding, emb)
                if sim >= threshold:
                    results.append(
                        {
                            "memory_id": rec["memory_id"],
                            "text": rec["text"],
                            "embedding": rec["embedding"],
                            "similarity": sim,
                        }
                    )
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]

        vec_str = json.dumps(query_embedding)

        async def _op():
            if self._in_transaction and self._current_conn is not None:
                rows = await self._current_conn.fetch(SEMANTIC_SEARCH_SQL, vec_str, float(threshold), limit)
            else:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(SEMANTIC_SEARCH_SQL, vec_str, float(threshold), limit)
            return [dict(r) for r in rows]

        rows = self._run_async(_op())

        results = []
        for r in rows:
            emb = r.get("embedding")
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    pass
            results.append(
                {
                    "memory_id": r["memory_id"],
                    "text": r["text"],
                    "similarity": float(r["similarity"]),
                    "embedding": emb,
                }
            )
        return results

    async def async_semantic_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Async variant of semantic_search for direct coroutine usage with asyncpg."""
        if self.fallback_mode or not self.pool:
            return self.semantic_search(query_embedding, limit=limit, threshold=threshold)

        vec_str = json.dumps(query_embedding)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(SEMANTIC_SEARCH_SQL, vec_str, float(threshold), limit)

        results = []
        for r in rows:
            r_dict = dict(r)
            emb = r_dict.get("embedding")
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    pass
            results.append(
                {
                    "memory_id": r_dict["memory_id"],
                    "text": r_dict["text"],
                    "similarity": float(r_dict["similarity"]),
                    "embedding": emb,
                }
            )
        return results

    def batch_store_embeddings(
        self,
        entries: List[Union[Tuple[str, str, List[float]], Dict[str, Any]]],
    ) -> int:
        """
        Bulk inserts vector embeddings for efficiency.

        Args:
            entries: List of tuples (memory_id, text, embedding_vector) or dicts
                     containing 'memory_id', 'text', 'embedding' (or 'embedding_vector')

        Returns:
            int: Number of entries successfully stored.
        """
        normalized_entries = []
        for item in entries:
            if isinstance(item, (tuple, list)):
                if len(item) >= 3:
                    normalized_entries.append((item[0], item[1], item[2]))
            elif isinstance(item, dict):
                mem_id = item.get("memory_id")
                txt = item.get("text", "")
                emb = item.get("embedding") if "embedding" in item else item.get("embedding_vector")
                if mem_id and emb is not None:
                    normalized_entries.append((mem_id, txt, emb))

        if not normalized_entries:
            return 0

        if self.fallback_mode:
            now = time.time()
            for mem_id, txt, emb in normalized_entries:
                self._fallback_store[mem_id] = {
                    "memory_id": mem_id,
                    "text": txt,
                    "embedding": list(emb),
                    "created_at": now,
                }
            return len(normalized_entries)

        records = [(mem_id, txt, json.dumps(emb)) for mem_id, txt, emb in normalized_entries]

        async def _op():
            if self._in_transaction and self._current_conn is not None:
                await self._current_conn.executemany(BATCH_STORE_EMBEDDINGS_SQL, records)
            else:
                async with self.pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.executemany(BATCH_STORE_EMBEDDINGS_SQL, records)

        self._run_async(_op())
        return len(normalized_entries)

    async def async_batch_store_embeddings(
        self,
        entries: List[Union[Tuple[str, str, List[float]], Dict[str, Any]]],
    ) -> int:
        """Async variant of batch_store_embeddings for direct coroutine usage with asyncpg."""
        if self.fallback_mode or not self.pool:
            return self.batch_store_embeddings(entries)

        normalized_entries = []
        for item in entries:
            if isinstance(item, (tuple, list)) and len(item) >= 3:
                normalized_entries.append((item[0], item[1], item[2]))
            elif isinstance(item, dict):
                mem_id = item.get("memory_id")
                txt = item.get("text", "")
                emb = item.get("embedding") if "embedding" in item else item.get("embedding_vector")
                if mem_id and emb is not None:
                    normalized_entries.append((mem_id, txt, emb))

        if not normalized_entries:
            return 0

        records = [(mem_id, txt, json.dumps(emb)) for mem_id, txt, emb in normalized_entries]
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(BATCH_STORE_EMBEDDINGS_SQL, records)
        return len(normalized_entries)

    def get_embedding(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a stored vector record by memory_id.
        """
        if self.fallback_mode:
            rec = self._fallback_store.get(memory_id)
            if not rec:
                return None
            return dict(rec)

        sql = "SELECT memory_id, text, embedding, created_at FROM memory_embeddings WHERE memory_id = $1;"
        row = self._fetchrow_sql(sql, memory_id)
        if not row:
            return None
        emb = row.get("embedding")
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:
                pass
        return {
            "memory_id": row["memory_id"],
            "text": row["text"],
            "embedding": emb,
            "created_at": row.get("created_at"),
        }

    def close(self) -> None:
        """Closes pool and background loop runner if active."""
        if hasattr(self, "_fallback_store"):
            self._fallback_store.clear()

        try:
            super().close()
        except Exception as e:
            logger.debug(f"Error during super().close(): {e}")
