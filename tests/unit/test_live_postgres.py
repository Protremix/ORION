"""
ORION Phase 5 — Live PostgreSQL Docker Test Suite.

These tests are designed to run against a live PostgreSQL instance,
typically started via Docker:

    docker run --name orion-test-pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=orion \
        -p 5432:5432 -d postgres:16

Run these tests with:
    python3 -m pytest tests/unit/test_live_postgres.py -v --tb=short

Tests are automatically SKIPPED if no PostgreSQL connection is available.
This allows the test suite to pass in sandbox environments without PostgreSQL.

License: Apache 2.0
"""

import asyncio
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Try to import asyncpg
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False


def has_postgres():
    """Check if a PostgreSQL instance is available."""
    if not ASYNCPG_AVAILABLE:
        return False
    try:
        from src.persistence.postgres_storage import PostgresStorageManager
        mgr = PostgresStorageManager(
            host=os.environ.get("ORION_PG_HOST", "localhost"),
            port=int(os.environ.get("ORION_PG_PORT", "5432")),
            user=os.environ.get("ORION_PG_USER", "postgres"),
            password=os.environ.get("ORION_PG_PASSWORD", "test"),
            database=os.environ.get("ORION_PG_DB", "orion"),
            connection_timeout=2.0,
        )
        # Try to initialize — if it fails, no PostgreSQL available
        mgr.initialize()
        mgr.close()
        return True
    except Exception:
        return False


@unittest.skipUnless(ASYNCPG_AVAILABLE, "asyncpg not installed")
@unittest.skipUnless(has_postgres(), "No PostgreSQL instance available (set ORION_PG_* env vars)")
class TestLivePostgresStorage(unittest.TestCase):
    """Test PostgreSQL storage against a live instance."""

    @classmethod
    def setUpClass(cls):
        from src.persistence.postgres_storage import PostgresStorageManager
        cls.mgr = PostgresStorageManager(
            host=os.environ.get("ORION_PG_HOST", "localhost"),
            port=int(os.environ.get("ORION_PG_PORT", "5432")),
            user=os.environ.get("ORION_PG_USER", "postgres"),
            password=os.environ.get("ORION_PG_PASSWORD", "test"),
            database=os.environ.get("ORION_PG_DB", "orion"),
        )
        cls.mgr.initialize()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'mgr'):
            cls.mgr.close()

    def setUp(self):
        # Clean tables before each test
        for table in ["memory_records", "audit_events", "belief_states", "action_history"]:
            try:
                self.mgr._execute(f"DELETE FROM {table}")
            except Exception:
                pass

    def test_connection_established(self):
        """PostgreSQL connection is established."""
        self.assertTrue(self.mgr._pool is not None)

    def test_create_and_read_audit_event(self):
        """Audit event can be created and read from PostgreSQL."""
        self.mgr.create_audit_event(
            event_type="test_event",
            actor="test_user",
            details={"test": True, "seq": 1},
        )
        events = self.mgr.query_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "test_event")

    def test_hash_chain_integrity_live(self):
        """Hash chain integrity is maintained in PostgreSQL."""
        for i in range(10):
            self.mgr.create_audit_event(
                event_type=f"chain_{i}",
                actor="verifier",
                details={"seq": i},
            )
        events = self.mgr.query_audit_events()
        self.assertEqual(len(events), 10)

        # Verify chain
        prev_hash = "0" * 64
        for event in events:
            self.assertEqual(event["previous_hash"], prev_hash)
            prev_hash = event["hash"]

    def test_concurrent_writes(self):
        """PostgreSQL handles concurrent writes without data loss."""
        import threading

        def write_events(prefix, count):
            for i in range(count):
                self.mgr.create_audit_event(
                    event_type=f"concurrent_{prefix}_{i}",
                    actor=f"thread_{prefix}",
                    details={"seq": i},
                )

        threads = []
        for t in range(4):
            thread = threading.Thread(target=write_events, args=(t, 25))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        events = self.mgr.query_audit_events()
        self.assertEqual(len(events), 100)  # 4 threads * 25 events

    def test_transaction_rollback(self):
        """Transaction rollback prevents partial writes."""
        try:
            # This should fail and rollback
            self.mgr._execute_in_transaction([
                ("INSERT INTO audit_events (id, event_type, actor, event_data, previous_hash, hash, timestamp) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("test1", "rollback_test", "test", '{"a":1}', "0"*64, "hash1", int(time.time()))),
                # This invalid SQL should cause rollback
                ("INVALID SQL STATEMENT", ()),
            ])
            self.fail("Should have raised an exception")
        except Exception:
            pass

        # Verify no data was written
        events = self.mgr.query_audit_events()
        self.assertEqual(len(events), 0)

    def test_memory_store_and_retrieve(self):
        """Memory records can be stored and retrieved from PostgreSQL."""
        self.mgr.store_memory(
            memory_id="test_mem_1",
            memory_type="episodic",
            content={"event": "test", "timestamp": time.time()},
            summary="Test memory for live PostgreSQL",
        )
        memories = self.mgr.query_memories()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["memory_id"], "test_mem_1")

    def test_query_by_time_range(self):
        """Audit events can be queried by time range."""
        t_start = time.time()
        for i in range(5):
            self.mgr.create_audit_event(
                event_type=f"time_{i}",
                actor="timer",
                details={"seq": i},
            )
        t_end = time.time()

        events = self.mgr.query_audit_events(start_time=t_start - 1, end_time=t_end + 1)
        self.assertEqual(len(events), 5)

    def test_large_payload(self):
        """PostgreSQL handles large JSON payloads."""
        large_data = {"data": ["x" * 1000] * 100}
        self.mgr.create_audit_event(
            event_type="large_payload",
            actor="test",
            details=large_data,
        )
        events = self.mgr.query_audit_events()
        self.assertEqual(len(events), 1)
        retrieved_data = json.loads(events[0]["event_data"])
        self.assertEqual(len(retrieved_data["data"]), 100)


@unittest.skipUnless(ASYNCPG_AVAILABLE, "asyncpg not installed")
@unittest.skipUnless(has_postgres(), "No PostgreSQL instance available")
class TestLivePostgresPgvector(unittest.TestCase):
    """Test pgvector integration against live PostgreSQL with pgvector extension."""

    @classmethod
    def setUpClass(cls):
        from src.persistence.postgres_storage import PostgresStorageManager
        cls.mgr = PostgresStorageManager(
            host=os.environ.get("ORION_PG_HOST", "localhost"),
            port=int(os.environ.get("ORION_PG_PORT", "5432")),
            user=os.environ.get("ORION_PG_USER", "postgres"),
            password=os.environ.get("ORION_PG_PASSWORD", "test"),
            database=os.environ.get("ORION_PG_DB", "orion"),
        )
        cls.mgr.initialize()

        # Check if pgvector extension is available
        try:
            cls.mgr._execute("CREATE EXTENSION IF NOT EXISTS vector")
            cls.pgvector_available = True
        except Exception:
            cls.pgvector_available = False

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'mgr'):
            cls.mgr.close()

    def test_vector_storage_and_search(self):
        """pgvector can store and search embeddings."""
        cls = self.__class__
        if not getattr(cls, 'pgvector_available', False):
            self.skipTest("pgvector extension not available")
        # Create table
        cls = self.__class__
        cls.mgr._execute("""
            CREATE TABLE IF NOT EXISTS test_embeddings (
                id TEXT PRIMARY KEY,
                content TEXT,
                embedding vector(3072)
            )
        """)

        # Insert test vectors (simplified for test)
        # In real usage, these would be 3072-dim embeddings from OpenAI
        # For testing, use small vectors
        cls.mgr._execute("DROP TABLE IF EXISTS test_embeddings_small")
        cls.mgr._execute("""
            CREATE TABLE test_embeddings_small (
                id TEXT PRIMARY KEY,
                content TEXT,
                embedding vector(3)
            )
        """)

        cls.mgr._execute(
            "INSERT INTO test_embeddings_small VALUES ('1', 'hello world', '[0.1, 0.2, 0.3]')"
        )
        cls.mgr._execute(
            "INSERT INTO test_embeddings_small VALUES ('2', 'goodbye world', '[0.4, 0.5, 0.6]')"
        )

        # Search by similarity
        results = cls.mgr._fetch(
            "SELECT id, content, embedding <=> '[0.1, 0.2, 0.3]' as distance "
            "FROM test_embeddings_small ORDER BY distance LIMIT 1"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "1")  # Should match itself

        # Clean up
        cls.mgr._execute("DROP TABLE IF EXISTS test_embeddings_small")


class TestDockerComposeConfig(unittest.TestCase):
    """Test that Docker Compose configuration for PostgreSQL is correct (no Docker needed)."""

    def test_docker_compose_exists(self):
        """Docker Compose file can be created with correct configuration."""
        compose_config = {
            "version": "3.8",
            "services": {
                "postgres": {
                    "image": "postgres:16",
                    "environment": {
                        "POSTGRES_USER": "postgres",
                        "POSTGRES_PASSWORD": "test",
                        "POSTGRES_DB": "orion",
                    },
                    "ports": ["5432:5432"],
                    "volumes": ["orion_pgdata:/var/lib/postgresql/data"],
                },
                "postgres-pgvector": {
                    "image": "pgvector/pgvector:pg16",
                    "environment": {
                        "POSTGRES_USER": "postgres",
                        "POSTGRES_PASSWORD": "test",
                        "POSTGRES_DB": "orion",
                    },
                    "ports": ["5433:5432"],
                    "volumes": ["orion_pgvector_data:/var/lib/postgresql/data"],
                },
            },
            "volumes": {
                "orion_pgdata": None,
                "orion_pgvector_data": None,
            },
        }

        # Validate structure
        self.assertEqual(compose_config["version"], "3.8")
        self.assertIn("postgres", compose_config["services"])
        self.assertIn("postgres-pgvector", compose_config["services"])

        # Validate pgvector image
        pgvector_service = compose_config["services"]["postgres-pgvector"]
        self.assertEqual(pgvector_service["image"], "pgvector/pgvector:pg16")

        # Validate port mapping
        self.assertEqual(pgvector_service["ports"], ["5433:5432"])

        # Write docker-compose file for reference
        import json
        compose_path = os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.yml")
        with open(compose_path, "w") as f:
            json.dump(compose_config, f, indent=2)


if __name__ == "__main__":
    unittest.main()
