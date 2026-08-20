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
ORION Physical Intelligence OS - Unit Tests for PgVectorStore.
Architecture Version: v0.6

Tests pgvector schema SQL strings, fallback mode operation (Python cosine similarity),
vector storage, batch storage, semantic search, and similarity threshold filtering.
"""

import math
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.persistence.pgvector_store import (
    PgVectorStore,
    cosine_similarity,
    CREATE_VECTOR_EXTENSION_SQL,
    CREATE_MEMORY_EMBEDDINGS_TABLE_SQL,
    CREATE_MEMORY_EMBEDDINGS_INDEX_SQL,
    STORE_EMBEDDING_SQL,
    SEMANTIC_SEARCH_SQL,
    BATCH_STORE_EMBEDDINGS_SQL,
)


def create_unit_vector(dim: int = 3072, offset: int = 0) -> list:
    """Helper to create a normalized unit vector of length dim."""
    vec = [0.0] * dim
    idx1 = offset % dim
    idx2 = (offset + 1) % dim
    vec[idx1] = 1.0 / math.sqrt(2.0)
    vec[idx2] = 1.0 / math.sqrt(2.0)
    return vec


def create_vector_pair_with_similarity(sim: float, dim: int = 3072) -> tuple:
    """
    Creates two unit vectors in dim dimensions with exact cosine similarity sim.
    Uses orthonormal basis A and B:
    A = [1, 0, 0, ...]
    B = [0, 1, 0, ...]
    V1 = A
    V2 = sim * A + sqrt(1 - sim^2) * B
    """
    v1 = [0.0] * dim
    v2 = [0.0] * dim
    v1[0] = 1.0

    sim_clamped = max(-1.0, min(1.0, sim))
    perp_weight = math.sqrt(max(0.0, 1.0 - sim_clamped ** 2))

    v2[0] = sim_clamped
    v2[1] = perp_weight

    return v1, v2


class TestPgVectorSchemaAndSQL(unittest.TestCase):
    """Test 1 & 5: Validate SQL schema creation and query syntax."""

    def test_schema_creation_sql_syntax(self):
        """Test the schema creation SQL string constants (validate syntax and keywords)."""
        # Extension creation
        self.assertIn("CREATE EXTENSION", CREATE_VECTOR_EXTENSION_SQL.upper())
        self.assertIn("VECTOR", CREATE_VECTOR_EXTENSION_SQL.upper())
        self.assertTrue(CREATE_VECTOR_EXTENSION_SQL.endswith(";"))

        # Table creation
        self.assertIn("CREATE TABLE IF NOT EXISTS MEMORY_EMBEDDINGS", CREATE_MEMORY_EMBEDDINGS_TABLE_SQL.upper())
        self.assertIn("MEMORY_ID TEXT PRIMARY KEY", CREATE_MEMORY_EMBEDDINGS_TABLE_SQL.upper())
        self.assertIn("TEXT TEXT NOT NULL", CREATE_MEMORY_EMBEDDINGS_TABLE_SQL.upper())
        self.assertIn("EMBEDDING VECTOR(3072)", CREATE_MEMORY_EMBEDDINGS_TABLE_SQL.upper())
        self.assertTrue(CREATE_MEMORY_EMBEDDINGS_TABLE_SQL.strip().endswith(";"))

        # HNSW Index creation
        self.assertIn("CREATE INDEX IF NOT EXISTS IDX_MEMORY_EMBEDDINGS_VECTOR", CREATE_MEMORY_EMBEDDINGS_INDEX_SQL.upper())
        self.assertIn("ON MEMORY_EMBEDDINGS", CREATE_MEMORY_EMBEDDINGS_INDEX_SQL.upper())
        self.assertIn("USING HNSW", CREATE_MEMORY_EMBEDDINGS_INDEX_SQL.upper())
        self.assertIn("VECTOR_COSINE_OPS", CREATE_MEMORY_EMBEDDINGS_INDEX_SQL.upper())
        self.assertTrue(CREATE_MEMORY_EMBEDDINGS_INDEX_SQL.strip().endswith(";"))

    def test_pgvector_sql_queries_syntax(self):
        """Test that the pgvector SQL queries are syntactically correct with valid pgvector operators."""
        # Store embedding SQL
        self.assertIn("INSERT INTO MEMORY_EMBEDDINGS", STORE_EMBEDDING_SQL.upper())
        self.assertIn("VALUES ($1, $2, $3::VECTOR)", STORE_EMBEDDING_SQL.upper())
        self.assertIn("ON CONFLICT (MEMORY_ID)", STORE_EMBEDDING_SQL.upper())
        self.assertIn("DO UPDATE SET", STORE_EMBEDDING_SQL.upper())

        # Batch store embedding SQL
        self.assertIn("INSERT INTO MEMORY_EMBEDDINGS", BATCH_STORE_EMBEDDINGS_SQL.upper())
        self.assertIn("VALUES ($1, $2, $3::VECTOR)", BATCH_STORE_EMBEDDINGS_SQL.upper())

        # Semantic search SQL with cosine distance operator <=>
        self.assertIn("<=>", SEMANTIC_SEARCH_SQL)
        self.assertIn("1 - (EMBEDDING <=> $1::VECTOR) AS SIMILARITY", SEMANTIC_SEARCH_SQL.upper())
        self.assertIn("WHERE 1 - (EMBEDDING <=> $1::VECTOR) >= $2", SEMANTIC_SEARCH_SQL.upper())
        self.assertIn("ORDER BY EMBEDDING <=> $1::VECTOR ASC", SEMANTIC_SEARCH_SQL.upper())
        self.assertIn("LIMIT $3", SEMANTIC_SEARCH_SQL.upper())

        # Validate parameter placeholder numbering
        self.assertEqual(len(re.findall(r"\$1\b", SEMANTIC_SEARCH_SQL)), 3)
        self.assertEqual(len(re.findall(r"\$2\b", SEMANTIC_SEARCH_SQL)), 1)
        self.assertEqual(len(re.findall(r"\$3\b", SEMANTIC_SEARCH_SQL)), 1)


class TestPgVectorFallbackMode(unittest.TestCase):
    """Test 2: Test fallback mode initialization and Python cosine similarity function."""

    def test_fallback_mode_activation(self):
        """Test fallback mode activation when PostgreSQL/pgvector is unavailable."""
        store = PgVectorStore(use_fallback=True)
        self.assertTrue(store.fallback_mode)
        self.assertFalse(store.has_pgvector)
        self.assertIsNotNone(store._fallback_store)
        store.close()

    def test_fallback_mode_auto_detected_when_no_postgres(self):
        """Test that missing PostgreSQL auto-triggers fallback mode without raising errors."""
        store = PgVectorStore(host="127.0.0.1", port=59999, connection_timeout=0.5)
        self.assertTrue(store.fallback_mode)
        self.assertFalse(store.has_pgvector)
        store.close()

    def test_cosine_similarity_math(self):
        """Test Python cosine similarity math function against known vector products."""
        # Identical vectors -> 1.0
        v1 = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v1), 1.0, places=5)

        # Orthogonal vectors -> 0.0
        v2 = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v2), 0.0, places=5)

        # Opposite vectors -> -1.0
        v3 = [-1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v3), -1.0, places=5)

        # 45 degree angle -> cos(45 deg) = 1/sqrt(2) ~ 0.7071
        v4 = [1.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v4), 1.0 / math.sqrt(2.0), places=5)

        # Empty / dimension mismatch
        self.assertEqual(cosine_similarity([], v1), 0.0)
        self.assertEqual(cosine_similarity(v1, [1.0, 0.0]), 0.0)


class TestPgVectorStoreAndSearchFallback(unittest.TestCase):
    """Test 3: Test store and search in fallback mode (in-memory)."""

    def setUp(self):
        self.store = PgVectorStore(use_fallback=True)

    def tearDown(self):
        self.store.close()

    def test_store_and_get_embedding_fallback(self):
        """Test storing and retrieving an embedding in fallback mode."""
        vec = create_unit_vector(3072, offset=0)
        res = self.store.store_embedding(
            memory_id="mem_001",
            text="Physical navigation target reached",
            embedding_vector=vec,
        )
        self.assertEqual(res["status"], "stored")
        self.assertEqual(res["mode"], "fallback")

        retrieved = self.store.get_embedding("mem_001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["memory_id"], "mem_001")
        self.assertEqual(retrieved["text"], "Physical navigation target reached")
        self.assertEqual(len(retrieved["embedding"]), 3072)
        self.assertAlmostEqual(retrieved["embedding"][0], vec[0], places=5)

    def test_semantic_search_fallback(self):
        """Test semantic search with ranked cosine similarity in fallback mode."""
        v_query, v_similar = create_vector_pair_with_similarity(0.95, dim=3072)
        _, v_moderate = create_vector_pair_with_similarity(0.75, dim=3072)

        self.store.store_embedding("mem_query", "Exact query concept", v_query)
        self.store.store_embedding("mem_similar", "Very similar concept", v_similar)
        self.store.store_embedding("mem_moderate", "Moderately related concept", v_moderate)

        results = self.store.semantic_search(v_query, limit=10, threshold=0.7)

        self.assertGreaterEqual(len(results), 2)
        # First result should be the query vector itself (sim ~1.0)
        self.assertEqual(results[0]["memory_id"], "mem_query")
        self.assertAlmostEqual(results[0]["similarity"], 1.0, places=4)

        # Second result should be v_similar (sim ~0.95)
        self.assertEqual(results[1]["memory_id"], "mem_similar")
        self.assertAlmostEqual(results[1]["similarity"], 0.95, places=4)


class TestPgVectorBatchStoreFallback(unittest.TestCase):
    """Test 4: Test batch store in fallback mode."""

    def setUp(self):
        self.store = PgVectorStore(use_fallback=True)

    def tearDown(self):
        self.store.close()

    def test_batch_store_tuples_fallback(self):
        """Test bulk insert using tuple format (memory_id, text, vector)."""
        entries = []
        for i in range(5):
            vec = create_unit_vector(3072, offset=i)
            entries.append((f"batch_mem_{i}", f"Batch memory content {i}", vec))

        count = self.store.batch_store_embeddings(entries)
        self.assertEqual(count, 5)

        for i in range(5):
            rec = self.store.get_embedding(f"batch_mem_{i}")
            self.assertIsNotNone(rec)
            self.assertEqual(rec["text"], f"Batch memory content {i}")

    def test_batch_store_dicts_fallback(self):
        """Test bulk insert using dict format."""
        entries = []
        for i in range(3):
            vec = create_unit_vector(3072, offset=i * 2)
            entries.append({
                "memory_id": f"dict_mem_{i}",
                "text": f"Dict batch content {i}",
                "embedding": vec,
            })

        count = self.store.batch_store_embeddings(entries)
        self.assertEqual(count, 3)

        rec = self.store.get_embedding("dict_mem_1")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["text"], "Dict batch content 1")


class TestPgVectorSimilarityThreshold(unittest.TestCase):
    """Test 6: Test similarity threshold filtering in semantic search."""

    def setUp(self):
        self.store = PgVectorStore(use_fallback=True)

    def tearDown(self):
        self.store.close()

    def test_similarity_threshold_filtering(self):
        """Test filtering candidates based on minimum cosine similarity threshold."""
        v_base, v_90 = create_vector_pair_with_similarity(0.90, dim=3072)
        _, v_75 = create_vector_pair_with_similarity(0.75, dim=3072)
        _, v_50 = create_vector_pair_with_similarity(0.50, dim=3072)
        _, v_10 = create_vector_pair_with_similarity(0.10, dim=3072)

        self.store.store_embedding("base", "Base memory", v_base)
        self.store.store_embedding("high", "High similarity", v_90)
        self.store.store_embedding("med", "Medium similarity", v_75)
        self.store.store_embedding("low", "Low similarity", v_50)
        self.store.store_embedding("unrelated", "Unrelated memory", v_10)

        # Search with high threshold 0.85 -> expects base (1.0) and high (0.90)
        res_high = self.store.semantic_search(v_base, limit=10, threshold=0.85)
        ids_high = [r["memory_id"] for r in res_high]
        self.assertIn("base", ids_high)
        self.assertIn("high", ids_high)
        self.assertNotIn("med", ids_high)
        self.assertNotIn("low", ids_high)
        self.assertNotIn("unrelated", ids_high)

        # Search with threshold 0.70 -> expects base, high, med
        res_med = self.store.semantic_search(v_base, limit=10, threshold=0.70)
        ids_med = [r["memory_id"] for r in res_med]
        self.assertEqual(len(ids_med), 3)
        self.assertIn("base", ids_med)
        self.assertIn("high", ids_med)
        self.assertIn("med", ids_med)

        # Search with threshold 0.40 -> expects base, high, med, low
        res_low = self.store.semantic_search(v_base, limit=10, threshold=0.40)
        ids_low = [r["memory_id"] for r in res_low]
        self.assertEqual(len(ids_low), 4)
        self.assertNotIn("unrelated", ids_low)

        # Search with limit=2
        res_limit = self.store.semantic_search(v_base, limit=2, threshold=0.0)
        self.assertEqual(len(res_limit), 2)


if __name__ == "__main__":
    unittest.main()
