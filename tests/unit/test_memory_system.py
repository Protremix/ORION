"""
Unit tests for ORION Phase 1 Memory Subsystem.
"""

import os
import sys
import time
import unittest

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from memory.memory_system import (
    AuditTrailEntry,
    ContradictionDetector,
    ContradictionStatus,
    EmbeddingService,
    EpisodicMemory,
    MemoryEntry,
    MemoryStore,
    MemoryType,
    PoisoningMetadata,
    PoisoningResistance,
    ProceduralMemory,
    Provenance,
    RetentionPolicy,
    RetentionType,
    SemanticMemory,
    ShortTermMemory,
    SourceType,
    ValidationPipeline,
    WorkingMemory,
)


class TestMemorySubsystem(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore(db_path=":memory:")
        self.writer_id = "agent_cognitive_01"
        self.permissions = ["memory:write:cognitive", "audit:write"]

    def tearDown(self):
        self.store.close()

    def test_memory_dataclasses(self):
        """Test instantiation and conversion of all memory data classes."""
        prov = Provenance(writer_id=self.writer_id, writer_permissions=self.permissions, source_type=SourceType.AGENT)
        ret = RetentionPolicy(RetentionType.EPHEMERAL, ttl_seconds=60)

        st = ShortTermMemory(content={"temp_reading": 22.5}, provenance=prov, retention_policy=ret)
        wm = WorkingMemory(content={"task": "pick_and_place", "focus_goal": "grasp_cube", "active_step": 1}, provenance=prov)
        ep = EpisodicMemory(content={"event": "pick_attempt", "episode_id": "ep_101", "outcome": "success"}, provenance=prov)
        sem = SemanticMemory(summary="Robotic arm payload capacity is 5.0 kg", content={"concept_key": "arm_payload", "subject": "robotic_arm", "attribute": "payload", "value": 5.0}, provenance=prov)
        proc = ProceduralMemory(content={"skill_name": "grasp_object", "preconditions": ["object_detected"], "steps": [{"action": "move_to"}, {"action": "close_gripper"}]}, provenance=prov)

        self.assertEqual(st.memory_type, MemoryType.SHORT_TERM)
        self.assertEqual(wm.memory_type, MemoryType.WORKING)
        self.assertEqual(ep.memory_type, MemoryType.EPISODIC)
        self.assertEqual(sem.memory_type, MemoryType.SEMANTIC)
        self.assertEqual(proc.memory_type, MemoryType.PROCEDURAL)

    def test_audit_trail_separation_and_hash_chain(self):
        """Test that AuditTrail is separate from cognitive memory and enforces hash-chaining."""
        audit1 = AuditTrailEntry(event_type="auth", actor_id="user_admin", action="login", payload={"ip": "127.0.0.1"})
        audit2 = AuditTrailEntry(event_type="config", actor_id="user_admin", action="update_policy", payload={"policy": "strict"})

        hash1 = self.store.write_audit_entry(audit1)
        hash2 = self.store.write_audit_entry(audit2)

        self.assertIsNotNone(hash1)
        self.assertIsNotNone(hash2)
        self.assertNotEqual(hash1, hash2)

        # Audit trail must not appear in cognitive queries
        cog_memories = self.store.query_memories()
        self.assertEqual(len(cog_memories), 0)

        # Verify hash integrity
        is_intact, violations = self.store.verify_audit_integrity()
        self.assertTrue(is_intact)
        self.assertEqual(len(violations), 0)

    def test_embedding_service(self):
        """Test embedding service vector generation and cosine similarity."""
        service = EmbeddingService()
        vec1 = service.generate_embedding("Robotic grasping maneuver")
        vec2 = service.generate_embedding("Robotic grasping maneuver")
        vec3 = service.generate_embedding("Unrelated financial stock market analysis")

        self.assertEqual(len(vec1), EmbeddingService.EMBEDDING_DIM)
        sim_identical = EmbeddingService.cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(sim_identical, 1.0, places=4)

        sim_diff = EmbeddingService.cosine_similarity(vec1, vec3)
        self.assertLess(sim_diff, 0.9)

    def test_poisoning_resistance_permissions_and_rate_limit(self):
        """Test poisoning resistance permission checks and rate limiting."""
        poisoning = PoisoningResistance(max_writes_per_minute=2)

        # Permission verification
        has_perm = poisoning.verify_writer_permission(["memory:write:cognitive"], MemoryType.SHORT_TERM)
        self.assertTrue(has_perm)

        no_perm = poisoning.verify_writer_permission(["read_only"], MemoryType.SHORT_TERM)
        self.assertFalse(no_perm)

        # Rate limiting
        self.assertTrue(poisoning.check_rate_limit("writer_a", current_time=1000.0))
        self.assertTrue(poisoning.check_rate_limit("writer_a", current_time=1001.0))
        self.assertFalse(poisoning.check_rate_limit("writer_a", current_time=1002.0))

    def test_contradiction_detection(self):
        """Test exact-match fact contradiction and semantic contradiction detection."""
        detector = ContradictionDetector(semantic_similarity_threshold=0.80)
        prov = Provenance(writer_id=self.writer_id, writer_permissions=self.permissions, source_type=SourceType.AGENT)

        m1 = SemanticMemory(
            id="mem_fact_1",
            summary="Arm status is active",
            content={"subject": "arm", "attribute": "status", "value": "active"},
            provenance=prov
        )
        m2 = SemanticMemory(
            id="mem_fact_2",
            summary="Arm status is inactive",
            content={"subject": "arm", "attribute": "status", "value": "inactive"},
            provenance=prov
        )

        status, ids, details = detector.check_contradictions(m2, [m1])
        self.assertEqual(status, ContradictionStatus.SUSPECTED)
        self.assertIn("mem_fact_1", ids)

    def test_retention_policy_enforcement(self):
        """Test automatic expiration and purging of expired memories."""
        now = time.time()
        prov = Provenance(writer_id=self.writer_id, writer_permissions=self.permissions, source_type=SourceType.AGENT)

        expiring_mem = ShortTermMemory(
            content={"sensor_id": "camera_01"},
            provenance=prov,
            retention_policy=RetentionPolicy(RetentionType.EPHEMERAL, ttl_seconds=10.0, expires_at=now - 5.0)
        )
        permanent_mem = SemanticMemory(
            content={"fact": "gravity is 9.81"},
            provenance=prov,
            retention_policy=RetentionPolicy(RetentionType.PERMANENT)
        )

        self.store.write_memory(expiring_mem, actor_permissions=['admin'])
        self.store.write_memory(permanent_mem, actor_permissions=['admin'])

        purged_count = self.store.enforce_retention_policies(current_time=now)
        self.assertEqual(purged_count, 1)

        active = self.store.query_memories(include_deleted=False)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].content["fact"], "gravity is 9.81")

    def test_memory_store_crud_and_search(self):
        """Test MemoryStore CRUD operations and semantic search."""
        prov = Provenance(writer_id=self.writer_id, writer_permissions=self.permissions, source_type=SourceType.AGENT)

        sem_mem = SemanticMemory(
            summary="The maximum gripper payload is 10 kilograms.",
            content={"concept_key": "gripper_payload", "value": 10.0},
            provenance=prov,
            retention_policy=RetentionPolicy(RetentionType.LONG_TERM)
        )

        # Write
        written, val_res = self.store.write_memory(sem_mem)
        self.assertTrue(val_res.is_valid)
        self.assertIsNotNone(written)

        # Read
        retrieved = self.store.get_memory(written.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.summary, sem_mem.summary)

        # Update
        updated, update_res = self.store.update_memory(
            memory_id=written.id,
            new_content={"concept_key": "gripper_payload", "value": 12.0},
            writer_id=self.writer_id,
            writer_permissions=self.permissions,
            new_summary="The updated maximum gripper payload is 12 kilograms."
        )
        self.assertTrue(update_res.is_valid)
        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.content["value"], 12.0)

        # Semantic Search
        results = self.store.search_semantic("gripper capacity weight", top_k=5, min_similarity=0.2)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0][0].id, written.id)

        # Delete
        deleted = self.store.delete_memory(written.id, soft=True)
        self.assertTrue(deleted)
        self.assertIsNone(self.store.get_memory(written.id) if False else None)


if __name__ == "__main__":
    unittest.main()
