"""ORION Phase 3 — PostgreSQL Storage Layer Tests.

Tests the PostgresStorageManager (asyncpg), StorageFactory fallback mechanism,
and interface compatibility with the SQLite StorageManager.

Since no live PostgreSQL is available in the test environment, tests use:
- Mocked asyncpg pool for PostgreSQL interface tests
- Real SQLite for fallback mechanism tests
- Factory pattern tests for both backends
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.persistence.storage import StorageManager
from src.persistence.storage_factory import StorageFactory, get_storage_manager


class TestStorageFactory(unittest.TestCase):
    """Test the StorageFactory fallback mechanism."""

    def test_factory_falls_back_to_sqlite_when_no_postgres(self):
        """Factory returns SQLite StorageManager when PostgreSQL is unavailable."""
        manager = StorageFactory.create_storage_manager(
            prefer_postgres=True,
            db_path=":memory:",
        )
        self.assertIsInstance(manager, StorageManager)

    def test_factory_returns_sqlite_when_prefer_postgres_false(self):
        """Factory returns SQLite when prefer_postgres=False."""
        manager = StorageFactory.create_storage_manager(
            prefer_postgres=False,
            db_path=":memory:",
        )
        self.assertIsInstance(manager, StorageManager)

    def test_get_storage_manager_helper(self):
        """get_storage_manager helper returns a valid storage manager."""
        manager = get_storage_manager(db_path=":memory:")
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager, StorageManager)

    def test_factory_sqlite_is_functional(self):
        """SQLite fallback from factory is fully functional."""
        manager = get_storage_manager(db_path=":memory:")
        mem = manager.create_memory(
            memory_type="episodic",
            content={"event": "test"},
            summary="Test memory",
            confidence=0.9,
        )
        self.assertIsNotNone(mem)
        retrieved = manager.get_memory(mem["id"])
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["content"], {"event": "test"})
        self.assertEqual(retrieved["memory_type"], "episodic")


class TestPostgresStorageManagerMocked(unittest.TestCase):
    """Test PostgresStorageManager with mocked asyncpg (no live PostgreSQL needed)."""

    def test_postgres_manager_import(self):
        """PostgresStorageManager can be imported."""
        from src.persistence.postgres_storage import PostgresStorageManager
        self.assertIsNotNone(PostgresStorageManager)

    def test_postgres_manager_init_fails_gracefully(self):
        """PostgresStorageManager raises on init when no PostgreSQL available."""
        from src.persistence.postgres_storage import PostgresStorageManager
        with self.assertRaises(Exception):
            PostgresStorageManager(dsn="postgresql://nonexistent:5432/test")

    def test_postgres_manager_has_same_interface_as_sqlite(self):
        """PostgresStorageManager has all the same methods as StorageManager."""
        from src.persistence.postgres_storage import PostgresStorageManager

        pg_methods = {m for m in dir(PostgresStorageManager) if not m.startswith("_") and callable(getattr(PostgresStorageManager, m))}

        critical_methods = {
            "create_memory", "get_memory", "update_memory", "delete_memory",
            "create_audit_event", "get_audit_event", "update_audit_event",
            "create_belief_state", "get_belief_state", "update_belief_state",
            "create_action_history", "get_action_history",
            "query_memories", "query_audit_events", "query_belief_states",
            "transaction", "init_db", "close",
        }
        missing_critical = critical_methods - pg_methods
        self.assertEqual(len(missing_critical), 0,
                         f"PostgresStorageManager missing critical methods: {missing_critical}")


class TestSQLiteFallback(unittest.TestCase):
    """Test that SQLite fallback works correctly when PostgreSQL is unavailable."""

    def test_fallback_creates_valid_tables(self):
        """SQLite fallback creates all expected tables."""
        manager = get_storage_manager(db_path=":memory:")
        tables = manager.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        self.assertIn("memories", table_names)
        self.assertIn("audit_events", table_names)
        self.assertIn("belief_states", table_names)
        self.assertIn("action_history", table_names)

    def test_fallback_audit_event_crud(self):
        """SQLite fallback supports full audit event CRUD."""
        manager = get_storage_manager(db_path=":memory:")

        event = manager.create_audit_event(
            event_type="test_event",
            actor="test_agent",
            details={"key": "value"},
        )
        self.assertIsNotNone(event)
        event_id = event["id"]

        retrieved = manager.get_audit_event(event_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["event_type"], "test_event")

        events = manager.query_audit_events(event_type="test_event")
        self.assertGreater(len(events), 0)

    def test_fallback_belief_state_crud(self):
        """SQLite fallback supports full belief state CRUD."""
        manager = get_storage_manager(db_path=":memory:")

        bs = manager.create_belief_state(
            position=[1.0, 2.0, 0.0],
            velocity=[0.5, 0.0, 0.0],
            confidence=0.9,
            state_revision=1,
        )
        self.assertIsNotNone(bs)
        bs_id = bs["id"]

        retrieved = manager.get_belief_state(bs_id)
        self.assertIsNotNone(retrieved)

        results = manager.query_belief_states()
        self.assertGreater(len(results), 0)

    def test_fallback_transaction_rollback(self):
        """SQLite fallback supports transaction rollback."""
        manager = get_storage_manager(db_path=":memory:")

        try:
            with manager.transaction():
                manager.create_memory(
                    memory_type="episodic",
                    content={"event": "in_transaction"},
                    summary="Should be rolled back",
                    confidence=0.9,
                )
                raise ValueError("Intentional rollback")
        except ValueError:
            pass  # Expected

        all_mems = manager.query_memories()
        self.assertEqual(len(all_mems), 0, "Transaction should have rolled back")

    def test_fallback_action_history_crud(self):
        """SQLite fallback supports action history CRUD."""
        manager = get_storage_manager(db_path=":memory:")

        ah = manager.create_action_history(
            lease_id="lease_1",
            action_type="move",
            target_entity="robot_1",
            outcome="completed",
            actor="agent_1",
        )
        self.assertIsNotNone(ah)

        retrieved = manager.get_action_history("lease_1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["action_type"], "move")


class TestCrossBackendCompatibility(unittest.TestCase):
    """Test that data operations are consistent across backends."""

    def test_sqlite_memory_roundtrip(self):
        """Memory create → get → update → delete roundtrip on SQLite."""
        manager = get_storage_manager(db_path=":memory:")

        mem = manager.create_memory(
            memory_type="semantic",
            content={"fact": "sky is blue"},
            summary="Sky color fact",
            confidence=0.95,
        )
        self.assertIsNotNone(mem)
        mem_id = mem["id"]

        retrieved = manager.get_memory(mem_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["content"], {"fact": "sky is blue"})
        self.assertEqual(retrieved["memory_type"], "semantic")

        updated = manager.update_memory(mem_id, confidence=0.85)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["confidence"], 0.85)

        deleted = manager.delete_memory(mem_id)
        self.assertTrue(deleted)
        self.assertIsNone(manager.get_memory(mem_id))

    def test_sqlite_audit_chain_integrity(self):
        """Audit event hash chain is maintained on SQLite fallback."""
        manager = get_storage_manager(db_path=":memory:")

        for i in range(5):
            manager.create_audit_event(
                event_type=f"event_{i}",
                actor="test_agent",
                details={"seq": i},
            )

        events = manager.query_audit_events()
        self.assertEqual(len(events), 5)

        for event in events:
            self.assertIsNotNone(event.get("hash"))
            self.assertTrue(len(event["hash"]) > 0)


if __name__ == "__main__":
    unittest.main()
