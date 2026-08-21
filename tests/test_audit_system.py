"""
Unit tests for ORION Physical Intelligence OS - Audit System.
"""

import os
import tempfile
import unittest
from pathlib import Path

from src.audit import (
    GENESIS_HASH,
    AuditError,
    AuditEvent,
    AuditLog,
    AuditMemoryIsolationGuard,
    AuditMemoryPoisoningError,
    AuditRollbackError,
    AuditStorageError,
    AuditTamperedError,
    EventType,
    FileStorageBackend,
    InMemoryStorageBackend,
    Outcome,
    RiskTier,
    SafetyDecision,
)


class TestAuditEvent(unittest.TestCase):
    def test_audit_event_creation(self):
        event = AuditEvent(
            event_id="test-id-1",
            timestamp=1700000000.0,
            event_type=EventType.ACTION.value,
            actor="Operator",
            action="MOVE_ARM",
            target="joint_1",
            outcome=Outcome.SUCCESS.value,
            risk_tier=RiskTier.TIER_2.value,
            safety_decision=SafetyDecision.APPROVED.value,
            state_revision=10,
        )
        self.assertEqual(event.event_id, "test-id-1")
        self.assertEqual(event.event_type, "action")
        self.assertEqual(event.actor, "Operator")
        self.assertEqual(event.action, "MOVE_ARM")
        self.assertEqual(event.target, "joint_1")
        self.assertEqual(event.outcome, "SUCCESS")
        self.assertEqual(event.risk_tier, "TIER_2")
        self.assertEqual(event.safety_decision, "APPROVED")
        self.assertEqual(event.state_revision, 10)
        self.assertEqual(event.schema_version, "1.0.0")
        self.assertEqual(event.contract_version, "1.0.0")

    def test_hash_calculation_and_signing(self):
        event = AuditEvent(
            event_id="test-id-2",
            timestamp=1700000001.0,
            event_type=EventType.SAFETY.value,
            actor="SafetyPlane",
            action="E_STOP",
            target="system",
            outcome=Outcome.SUCCESS.value,
            risk_tier=RiskTier.TIER_4.value,
            safety_decision=SafetyDecision.APPROVED.value,
            state_revision=1,
        )
        h1 = event.calculate_hash()
        self.assertTrue(len(h1) == 64)

        sig = event.sign_event("secret-key-123")
        self.assertTrue(len(sig) > 0)
        self.assertTrue(event.verify_signature("secret-key-123"))
        self.assertFalse(event.verify_signature("wrong-key"))


class TestAuditLogAndChaining(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryStorageBackend()
        self.audit_log = AuditLog(storage=self.storage, hmac_secret="test-secret")

    def test_append_and_hash_chaining(self):
        e1 = self.audit_log.create_event(
            event_type=EventType.DECISION,
            actor="Planner",
            action="PLAN_PATH",
            target="trajectory",
            risk_tier=RiskTier.TIER_1,
        )
        e1_logged = self.audit_log.append_event(e1)
        self.assertEqual(e1_logged.previous_hash, GENESIS_HASH)

        e2 = self.audit_log.create_event(
            event_type=EventType.ACTION,
            actor="Controller",
            action="EXECUTE_STEP",
            target="arm",
            risk_tier=RiskTier.TIER_2,
        )
        e2_logged = self.audit_log.append_event(e2)
        self.assertEqual(e2_logged.previous_hash, e1_logged.hash)

        self.assertEqual(self.audit_log.count, 2)
        res = self.audit_log.verify_chain_integrity()
        self.assertTrue(res.is_valid)

    def test_tamper_detection(self):
        e1 = self.audit_log.create_event(
            event_type=EventType.CONFIG_CHANGE,
            actor="Admin",
            action="UPDATE_PARAM",
            target="speed_limit",
        )
        self.audit_log.append_event(e1)

        e2 = self.audit_log.create_event(
            event_type=EventType.ACTION,
            actor="Robot",
            action="DRIVE",
            target="wheels",
        )
        self.audit_log.append_event(e2)

        # Confirm chain is initially valid
        self.assertTrue(self.audit_log.verify_chain_integrity().is_valid)

        # Tamper with stored event data
        events = self.storage.read_all()
        events[0].action = "MALICIOUS_UPDATE"
        # Force modify in storage backend
        self.storage._events[0] = events[0]

        res = self.audit_log.verify_chain_integrity()
        self.assertFalse(res.is_valid)
        self.assertTrue(len(res.errors) > 0)


class TestRollbackOnStorageFailure(unittest.TestCase):
    def setUp(self):
        self.backend = InMemoryStorageBackend()
        self.audit_log = AuditLog(storage=self.backend)

    def test_action_rollback_on_audit_failure(self):
        state = {"arm_position": 0.0}

        def perform_action():
            state["arm_position"] = 90.0
            return "POSITION_UPDATED"

        def rollback_action():
            state["arm_position"] = 0.0

        # Case 1: Normal execution
        res = self.audit_log.execute_audited_action(
            action_fn=perform_action,
            rollback_fn=rollback_action,
            event_type=EventType.ACTION,
            actor="ServoDriver",
            action="ROTATE_JOINT",
            target="joint_1",
        )
        self.assertEqual(res, "POSITION_UPDATED")
        self.assertEqual(state["arm_position"], 90.0)
        self.assertEqual(self.audit_log.count, 1)

        # Case 2: Storage failure occurs during audit append
        self.backend.simulate_failure = True

        def perform_action_2():
            state["arm_position"] = 180.0
            return "POSITION_UPDATED_2"

        with self.assertRaises(AuditRollbackError):
            self.audit_log.execute_audited_action(
                action_fn=perform_action_2,
                rollback_fn=rollback_action,
                event_type=EventType.ACTION,
                actor="ServoDriver",
                action="ROTATE_JOINT",
                target="joint_1",
            )

        # Verify state was rolled back and action treated as unexecuted
        self.assertEqual(state["arm_position"], 0.0)


class TestReplayAndQuery(unittest.TestCase):
    def setUp(self):
        self.audit_log = AuditLog()
        self.timestamps = [100.0, 200.0, 300.0, 400.0]
        self.event_ids = []

        for i, ts in enumerate(self.timestamps):
            e = self.audit_log.create_event(
                event_type=EventType.DECISION if i % 2 == 0 else EventType.ACTION,
                actor=f"Actor_{i}",
                action=f"Action_{i}",
                target=f"Target_{i}",
                risk_tier=RiskTier.TIER_1 if i < 2 else RiskTier.TIER_3,
                timestamp=ts,
            )
            self.audit_log.append_event(e)
            self.event_ids.append(e.event_id)

    def test_query_filtering(self):
        # Query by event_type
        decisions = self.audit_log.query(event_type=EventType.DECISION)
        self.assertEqual(len(decisions), 2)

        # Query by actor
        actor1 = self.audit_log.query(actor="Actor_1")
        self.assertEqual(len(actor1), 1)
        self.assertEqual(actor1[0].action, "Action_1")

        # Query by risk_tier
        tier3_events = self.audit_log.query(risk_tier=RiskTier.TIER_3)
        self.assertEqual(len(tier3_events), 2)

        # Query by timestamp range
        range_events = self.audit_log.query(start_time=150.0, end_time=350.0)
        self.assertEqual(len(range_events), 2)

    def test_replay_functionality(self):
        replayed = list(self.audit_log.replay_events(start_timestamp=200.0))
        self.assertEqual(len(replayed), 3)
        self.assertEqual(replayed[0].timestamp, 200.0)

        # Replay by start_event_id
        replayed_id = list(self.audit_log.replay_events(start_event_id=self.event_ids[2]))
        self.assertEqual(len(replayed_id), 2)
        self.assertEqual(replayed_id[0].event_id, self.event_ids[2])


class TestExportImportAndMemoryGuard(unittest.TestCase):
    def test_json_export_and_import(self):
        audit_log = AuditLog(hmac_secret="secret-abc")
        e1 = audit_log.create_event(
            event_type=EventType.SAFETY,
            actor="Monitor",
            action="CHECK_LIMITS",
            target="sensors",
        )
        audit_log.append_event(e1)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            json_str = audit_log.export_to_json(file_path=tmp_path)
            self.assertTrue("metadata" in json_str)

            imported_log, result = AuditLog.import_from_json(
                json_content_or_path=tmp_path,
                secret_key="secret-abc"
            )
            self.assertTrue(result.is_valid)
            self.assertEqual(imported_log.count, 1)
            self.assertEqual(imported_log.get_events()[0].event_id, e1.event_id)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_cognitive_memory_isolation_guard(self):
        event = AuditEvent(
            event_id="audit-999",
            timestamp=100.0,
            event_type="safety",
            actor="Guard",
            action="HALT",
            target="system",
            outcome="SUCCESS",
            risk_tier="TIER_4",
            safety_decision="APPROVED",
            state_revision=5,
        )

        ref = AuditMemoryIsolationGuard.sanitize_for_cognitive_reference(event)
        self.assertEqual(ref["audit_reference_id"], "audit-999")
        self.assertFalse(ref["is_cognitive_fact"])
        self.assertNotIn("payload", ref)

        with self.assertRaises(AuditMemoryPoisoningError):
            AuditMemoryIsolationGuard.assert_not_audit_payload(event)

        with self.assertRaises(AuditMemoryPoisoningError):
            AuditMemoryIsolationGuard.assert_not_audit_payload({
                "previous_hash": "abc",
                "safety_decision": "APPROVED",
                "contract_version": "1.0.0",
            })


if __name__ == "__main__":
    unittest.main()
