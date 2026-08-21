"""Unit tests for ORION Physical Intelligence OS - Persistence Subsystem.
Architecture Version: v0.5 (Luna Phase 1 Condition-3 Compliance)
"""

import os
import tempfile
import unittest
from pathlib import Path

from src.persistence import (
    ActionHistoryRecord,
    AuditEventRecord,
    BeliefStateRecord,
    MemoryRecord,
    StorageManager,
)


class TestPersistenceSubsystem(unittest.TestCase):
    """Test suite for SQLite StorageManager implementation."""

    def setUp(self):
        """Initialize in-memory StorageManager for unit tests."""
        self.storage = StorageManager(":memory:")

    def tearDown(self):
        """Clean up storage connection."""
        self.storage.close()

    def test_database_initialization(self):
        """Test database table creation and schema initialization."""
        cursor = self.storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        expected_tables = {"memories", "audit_events", "belief_states", "action_history"}
        self.assertTrue(expected_tables.issubset(tables))

    def test_memory_crud(self):
        """Test Create, Read, Update, Delete operations for memories table."""
        # 1. Create
        rec = MemoryRecord(
            id="mem-001",
            memory_type="semantic",
            content={"concept": "obstacle_avoidance", "safe_distance": 0.5},
            source="cognitive_plane",
            confidence=0.95,
            timestamp=1000,
        )
        created = self.storage.create_memory(rec)
        self.assertEqual(created["id"], "mem-001")
        self.assertEqual(created["memory_type"], "semantic")
        self.assertEqual(created["confidence"], 0.95)
        self.assertEqual(created["content"]["concept"], "obstacle_avoidance")

        # 2. Read
        read_mem = self.storage.get_memory("mem-001")
        self.assertIsNotNone(read_mem)
        self.assertEqual(read_mem["source"], "cognitive_plane")

        # 3. Update
        updated = self.storage.update_memory("mem-001", confidence=0.99, contradiction_flag=1)
        self.assertEqual(updated["confidence"], 0.99)
        self.assertEqual(updated["contradiction_flag"], 1)

        # 4. Delete
        deleted = self.storage.delete_memory("mem-001")
        self.assertTrue(deleted)
        self.assertIsNone(self.storage.get_memory("mem-001"))

    def test_audit_event_persistence(self):
        """Test Audit event persistence and hash chain integrity verification."""
        e1 = self.storage.create_audit_event(
            id="audit-001",
            event_type="decision",
            event_data={"action": "STOP", "reason": "barrier"},
            actor="SafetyEnforcement",
            timestamp=100,
            severity="warning",
        )
        self.assertEqual(e1["sequence_number"], 1)
        self.assertEqual(e1["previous_hash"], "0" * 64)
        self.assertTrue(len(e1["hash"]) > 0)

        e2 = self.storage.create_audit_event(
            id="audit-002",
            event_type="action",
            event_data={"action": "APPLY_BRAKE"},
            actor="ControlPlane",
            timestamp=101,
            severity="critical",
        )
        self.assertEqual(e2["sequence_number"], 2)
        self.assertEqual(e2["previous_hash"], e1["hash"])

        # Hash chain must be intact
        self.assertTrue(self.storage.verify_audit_hash_chain())

        # Tamper detection: modify audit-001 directly in DB
        self.storage.conn.execute(
            "UPDATE audit_events SET actor = 'MaliciousActor' WHERE id = 'audit-001'"
        )
        self.storage.conn.commit()

        # Hash chain verification must now fail
        self.assertFalse(self.storage.verify_audit_hash_chain())

    def test_belief_state_storage(self):
        """Test Belief state storage, retrieval, and revision updates."""
        bst = BeliefStateRecord(
            id="belief-001",
            revision=1,
            position={"x": 1.2, "y": 3.4, "z": 0.0},
            orientation={"roll": 0.0, "pitch": 0.0, "yaw": 1.57},
            velocity={"vx": 0.5, "vy": 0.0, "vz": 0.0},
            uncertainty={"pos_cov": 0.01},
            timestamp=500,
            sensor_health={"camera_0": "ok", "lidar_0": "ok"},
        )
        created = self.storage.create_belief_state(bst)
        self.assertEqual(created["id"], "belief-001")
        self.assertEqual(created["revision"], 1)
        self.assertEqual(created["position"]["x"], 1.2)

        # Retrieve and verify
        retrieved = self.storage.get_belief_state("belief-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["velocity"]["vx"], 0.5)

        # Update revision
        updated = self.storage.update_belief_state("belief-001", revision=2)
        self.assertEqual(updated["revision"], 2)

    def test_action_history_storage(self):
        """Test Action history record storage and updates."""
        act = ActionHistoryRecord(
            lease_id="lease-100",
            action_type="MOVE_NAV",
            target_entity="waypoint_3",
            outcome="completed",
            execution_stage="verified",
            duration_ms=250,
            timestamp=600,
        )
        created = self.storage.create_action_history(act)
        self.assertEqual(created["lease_id"], "lease-100")
        self.assertEqual(created["action_type"], "MOVE_NAV")
        self.assertEqual(created["duration_ms"], 250)

        # Read back
        read_act = self.storage.get_action_history("lease-100")
        self.assertEqual(read_act["target_entity"], "waypoint_3")

        # Update outcome
        updated = self.storage.update_action_history("lease-100", outcome="failed")
        self.assertEqual(updated["outcome"], "failed")

    def test_query_filtering(self):
        """Test time range, type, and actor query filtering."""
        # Memories with timestamps 10, 20, 30
        self.storage.create_memory(id="m1", memory_type="episodic", timestamp=10, source="s1")
        self.storage.create_memory(id="m2", memory_type="semantic", timestamp=20, source="s2")
        self.storage.create_memory(id="m3", memory_type="episodic", timestamp=30, source="s1")

        # Filter memories by time range
        mems_range = self.storage.query_memories(start_time=15, end_time=35)
        self.assertEqual(len(mems_range), 2)
        self.assertEqual([m["id"] for m in mems_range], ["m2", "m3"])

        # Filter memories by type
        mems_type = self.storage.query_memories(memory_type="episodic")
        self.assertEqual(len(mems_type), 2)

        # Filter memories by source
        mems_source = self.storage.query_memories(source="s1")
        self.assertEqual(len(mems_source), 2)

        # Audit events by actor and severity
        self.storage.create_audit_event(id="a1", event_type="safety", actor="Operator", timestamp=10, severity="info")
        self.storage.create_audit_event(id="a2", event_type="action", actor="Robot", timestamp=20, severity="warning")
        self.storage.create_audit_event(id="a3", event_type="safety", actor="Operator", timestamp=30, severity="critical")

        audits_actor = self.storage.query_audit_events(actor="Operator")
        self.assertEqual(len(audits_actor), 2)

        audits_sev = self.storage.query_audit_events(severity="critical")
        self.assertEqual(len(audits_sev), 1)
        self.assertEqual(audits_sev[0]["id"], "a3")

    def test_transaction_rollback(self):
        """Test atomic transaction rollback when an exception occurs."""
        initial_memories = len(self.storage.query_memories())

        try:
            with self.storage.transaction():
                self.storage.create_memory(id="trans-m1", memory_type="working", timestamp=100)
                self.storage.create_audit_event(id="trans-a1", event_type="safety", timestamp=100)
                # Intentionally trigger exception
                raise RuntimeError("Simulated transaction failure")
        except RuntimeError:
            pass

        # Verify that changes inside transaction block were rolled back
        self.assertEqual(len(self.storage.query_memories()), initial_memories)
        self.assertIsNone(self.storage.get_memory("trans-m1"))
        self.assertIsNone(self.storage.get_audit_event("trans-a1"))

    def test_export_and_import(self):
        """Test JSON backup/export and restore/import roundtrip."""
        # Populate DB
        self.storage.create_memory(id="exp-m1", memory_type="episodic", content={"data": 123}, timestamp=10)
        self.storage.create_audit_event(id="exp-a1", event_type="decision", actor="Planner", timestamp=10)
        self.storage.create_belief_state(id="exp-b1", revision=5, timestamp=10)
        self.storage.create_action_history(lease_id="exp-l1", action_type="NAV", timestamp=10)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Export to file
            json_str = self.storage.export_to_json(tmp_path)
            self.assertTrue("exp-m1" in json_str)

            # Import into new storage instance
            new_storage = StorageManager(":memory:")
            new_storage.import_from_json(tmp_path)

            self.assertIsNotNone(new_storage.get_memory("exp-m1"))
            self.assertIsNotNone(new_storage.get_audit_event("exp-a1"))
            self.assertIsNotNone(new_storage.get_belief_state("exp-b1"))
            self.assertIsNotNone(new_storage.get_action_history("exp-l1"))
            self.assertTrue(new_storage.verify_audit_hash_chain())

            new_storage.close()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
