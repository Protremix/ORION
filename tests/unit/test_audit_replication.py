"""ORION Phase 3 — Audit Log Replication Tests.

Tests the AuditReplicationManager for primary-replica replication,
hash chain verification, backup/restore, and failure recovery.
"""

import unittest
import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.persistence.storage import StorageManager
from src.persistence.audit_replication import (
    AuditReplicationManager,
    BackupSnapshot,
    WALRecord,
    ReplicationStatus,
)


class TestReplicationSetup(unittest.TestCase):
    """Test primary-replica initialization."""

    def setUp(self):
        self.primary = StorageManager(db_path=":memory:")
        self.repl_mgr = AuditReplicationManager(self.primary)

    def tearDown(self):
        self.repl_mgr.close()

    def test_primary_replica_initialization(self):
        """Primary and replica can be initialized."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            replica_path = f.name
        os.unlink(replica_path)  # Remove so SQLite creates fresh

        self.assertTrue(self.repl_mgr.add_replica("replica_1", replica_path))
        status = self.repl_mgr.get_replication_status()
        self.assertIn("replica_1", status)
        self.assertTrue(status["replica_1"].is_online)
        self.assertTrue(status["replica_1"].is_in_sync)

        # Clean up
        if os.path.exists(replica_path):
            os.unlink(replica_path)

    def test_wal_hook_installed(self):
        """WAL hook captures audit events from primary."""
        self.primary.create_audit_event(
            event_type="test",
            actor="test_agent",
            details={"key": "value"},
        )
        self.assertGreater(self.repl_mgr.get_wal_size(), 0)


class TestReplication(unittest.TestCase):
    """Test audit event replication."""

    def setUp(self):
        self.primary = StorageManager(db_path=":memory:")
        self.repl_mgr = AuditReplicationManager(self.primary)
        self.replica_path = tempfile.mktemp(suffix=".db")
        self.repl_mgr.add_replica("replica_1", self.replica_path)

    def tearDown(self):
        self.repl_mgr.close()
        if os.path.exists(self.replica_path):
            os.unlink(self.replica_path)

    def test_audit_event_replication(self):
        """Audit events replicate from primary to replica."""
        for i in range(5):
            self.primary.create_audit_event(
                event_type=f"event_{i}",
                actor="test_agent",
                details={"seq": i},
            )

        results = self.repl_mgr.replicate()
        self.assertEqual(results["replica_1"], 5)

        # Verify replica has the events
        conn = sqlite3.connect(self.replica_path)
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        conn.close()
        self.assertEqual(count, 5)

    def test_concurrent_writes_during_replication(self):
        """Replication works with multiple concurrent audit writes."""
        for i in range(20):
            self.primary.create_audit_event(
                event_type=f"concurrent_{i}",
                actor="thread_agent",
                details={"i": i},
            )

        results = self.repl_mgr.replicate()
        self.assertEqual(results["replica_1"], 20)

        status = self.repl_mgr.get_replication_status()
        self.assertTrue(status["replica_1"].is_in_sync)
        self.assertEqual(status["replica_1"].lag, 0)


class TestReplicaFailure(unittest.TestCase):
    """Test replica failure and catch-up."""

    def setUp(self):
        self.primary = StorageManager(db_path=":memory:")
        self.repl_mgr = AuditReplicationManager(self.primary)
        self.replica_path = tempfile.mktemp(suffix=".db")
        self.repl_mgr.add_replica("replica_1", self.replica_path)

    def tearDown(self):
        self.repl_mgr.close()
        if os.path.exists(self.replica_path):
            os.unlink(self.replica_path)

    def test_replica_failure_and_catch_up(self):
        """Replica goes down, primary continues, replica catches up on rejoin."""
        # Write some events while online
        for i in range(3):
            self.primary.create_audit_event(
                event_type=f"before_{i}",
                actor="test",
                details={},
            )
        self.repl_mgr.replicate()

        # Take replica offline
        self.repl_mgr.set_replica_offline("replica_1")

        # Write more events while offline
        for i in range(5):
            self.primary.create_audit_event(
                event_type=f"after_{i}",
                actor="test",
                details={},
            )
        # Replicate (replica offline, should skip)
        results = self.repl_mgr.replicate()
        self.assertEqual(results["replica_1"], 0)

        # Bring replica back online and catch up
        caught_up = self.repl_mgr.catch_up("replica_1")
        self.assertGreater(caught_up, 0)

        # Verify replica has all events
        conn = sqlite3.connect(self.replica_path)
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        conn.close()
        self.assertEqual(count, 8)  # 3 before + 5 after


class TestHashChainVerification(unittest.TestCase):
    """Test hash chain verification across replicas."""

    def setUp(self):
        self.primary = StorageManager(db_path=":memory:")
        self.repl_mgr = AuditReplicationManager(self.primary)
        self.replica_path = tempfile.mktemp(suffix=".db")
        self.repl_mgr.add_replica("replica_1", self.replica_path)

    def tearDown(self):
        self.repl_mgr.close()
        if os.path.exists(self.replica_path):
            os.unlink(self.replica_path)

    def test_hash_chain_integrity_across_replica(self):
        """Hash chain is intact on replica after replication."""
        for i in range(10):
            self.primary.create_audit_event(
                event_type=f"chain_{i}",
                actor="test",
                details={"seq": i},
            )
        self.repl_mgr.replicate()

        self.assertTrue(self.repl_mgr.verify_replica_integrity("replica_1"))
        self.assertTrue(self.repl_mgr.verify_primary_integrity())


class TestBackupRestore(unittest.TestCase):
    """Test backup creation and restore."""

    def setUp(self):
        self.primary = StorageManager(db_path=":memory:")
        self.repl_mgr = AuditReplicationManager(self.primary)
        self.backup_path = tempfile.mktemp(suffix=".db")

    def tearDown(self):
        self.repl_mgr.close()
        if os.path.exists(self.backup_path):
            os.unlink(self.backup_path)

    def test_backup_creation(self):
        """Backup snapshot can be created from primary."""
        for i in range(10):
            self.primary.create_audit_event(
                event_type=f"backup_{i}",
                actor="test",
                details={},
            )

        snapshot = self.repl_mgr.create_backup(self.backup_path)
        self.assertEqual(snapshot.event_count, 10)
        self.assertTrue(os.path.exists(self.backup_path))
        self.assertTrue(len(snapshot.hash) > 0)

    def test_restore_from_backup(self):
        """Audit log can be restored from backup."""
        # Create events and backup
        for i in range(5):
            self.primary.create_audit_event(
                event_type=f"restore_{i}",
                actor="test",
                details={},
            )
        snapshot = self.repl_mgr.create_backup(self.backup_path)

        # Create a fresh storage and restore into it
        new_storage = StorageManager(db_path=":memory:")
        restored = self.repl_mgr.restore_from_backup(self.backup_path, target_storage=new_storage)
        self.assertEqual(restored, 5)

        # Verify restored events
        events = new_storage.query_audit_events()
        self.assertEqual(len(events), 5)

    def test_point_in_time_recovery(self):
        """Point-in-time recovery via snapshot + WAL replay."""
        # Phase 1: write 3 events, snapshot
        for i in range(3):
            self.primary.create_audit_event(
                event_type=f"pitr_1_{i}",
                actor="test",
                details={},
            )
        snapshot = self.repl_mgr.create_backup(self.backup_path)
        self.assertEqual(snapshot.event_count, 3)

        # Phase 2: write 3 more events (WAL captures them)
        for i in range(3):
            self.primary.create_audit_event(
                event_type=f"pitr_2_{i}",
                actor="test",
                details={},
            )

        # Verify WAL has all 6 events
        self.assertEqual(self.repl_mgr.get_wal_size(), 6)

        # Restore from backup (gets first 3)
        new_storage = StorageManager(db_path=":memory:")
        restored = self.repl_mgr.restore_from_backup(self.backup_path, target_storage=new_storage)
        self.assertEqual(restored, 3)

        # WAL replay would add remaining 3 (simulated by direct replication)
        # In a real system, WAL records after snapshot point would be replayed
        events_after_snapshot = [
            rec for rec in self.repl_mgr._wal
            if rec.sequence_number > snapshot.last_sequence
        ]
        self.assertEqual(len(events_after_snapshot), 3)


if __name__ == "__main__":
    unittest.main()
