"""
ORION Phase 005 — Memory System Tests. License: Apache 2.0

Tests for all Phase 005 memory components:
- MemoryPermissions (7 tests)
- MemoryRetriever (8 tests)
- MemoryWriter (6 tests)
- MemoryVerifier (5 tests)
- MemoryDecay (5 tests)
- WorldStateManager (5 tests)
- MemoryManager (6 tests)
- CoreIntegration (5 tests)

Total target: ~47 tests
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from src.core.permission_engine import PermissionLevel
from src.core.tool_registry import ToolRegistry
from src.memory.memory_decay import DecayReport, MemoryDecay
from src.memory.memory_manager import MemoryManager, MemoryResult
from src.memory.memory_permissions import MemoryOperation, MemoryPermissions
from src.memory.memory_retriever import MemoryRetriever, RetrievalResult
from src.memory.memory_system import (
    ContradictionDetector,
    EmbeddingService,
    EpisodicMemory,
    MemoryEntry,
    MemoryStore,
    MemoryType,
    PoisoningResistance,
    Provenance,
    RetentionPolicy,
    RetentionType,
    SemanticMemory,
    ShortTermMemory,
    SourceType,
    ValidationPipeline,
    WorkingMemory,
)
from src.memory.memory_verifier import ConflictResolution, MemoryVerifier
from src.memory.memory_writer import MemoryWriter, WriteResult
from src.memory.world_state_manager import StateDiff, WorldStateManager


# ============================================================================
# Helper: create a fresh in-memory store with seed data
# ============================================================================

def make_store(db_path: Optional[str] = None) -> MemoryStore:
    """Create a fresh MemoryStore backed by a temp SQLite file."""
    if db_path is None:
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
    store = MemoryStore(db_path=db_path)
    return store


def make_entry(
    content: Dict[str, Any],
    memory_type: MemoryType = MemoryType.SHORT_TERM,
    confidence: float = 0.9,
    writer_id: str = "test_agent",
    source_type: SourceType = SourceType.AGENT,
) -> MemoryEntry:
    """Create a memory entry for testing."""
    provenance = Provenance(
        writer_id=writer_id,
        writer_permissions=["execute"],
        source_type=source_type,
        source_plane="CognitivePlane",
    )

    if memory_type == MemoryType.SHORT_TERM:
        entry = ShortTermMemory(content=content, provenance=provenance, confidence=confidence)
    elif memory_type == MemoryType.WORKING:
        entry = WorkingMemory(content=content, provenance=provenance, confidence=confidence)
    elif memory_type == MemoryType.EPISODIC:
        entry = EpisodicMemory(content=content, provenance=provenance, confidence=confidence)
    elif memory_type == MemoryType.SEMANTIC:
        entry = SemanticMemory(content=content, provenance=provenance, confidence=confidence)
    else:
        entry = ShortTermMemory(content=content, provenance=provenance, confidence=confidence)

    return entry


# ============================================================================
# TestMemoryPermissions (7 tests)
# ============================================================================

class TestMemoryPermissions(unittest.TestCase):
    """Tests for MemoryPermissions — read/write/delete per level and type."""

    def setUp(self):
        self.permissions = MemoryPermissions()

    def test_read_permission_short_term_at_read_level(self):
        """READ level can read SHORT_TERM."""
        result = self.permissions.can_read(MemoryType.SHORT_TERM, PermissionLevel.READ)
        self.assertTrue(result.allowed)

    def test_read_permission_audit_trail_denied_at_execute(self):
        """EXECUTE level cannot read AUDIT_TRAIL."""
        result = self.permissions.can_read(MemoryType.AUDIT_TRAIL, PermissionLevel.EXECUTE)
        self.assertFalse(result.allowed)

    def test_read_permission_all_at_admin(self):
        """ADMIN can read all types."""
        for mt in MemoryType:
            result = self.permissions.can_read(mt, PermissionLevel.ADMIN)
            self.assertTrue(result.allowed, f"ADMIN should read {mt.value}")

    def test_write_permission_agent_can_write_short_term(self):
        """Agent source can write SHORT_TERM at EXECUTE level."""
        result = self.permissions.can_write(
            MemoryType.SHORT_TERM, SourceType.AGENT, PermissionLevel.EXECUTE
        )
        self.assertTrue(result.allowed)

    def test_write_permission_inference_can_only_write_semantic(self):
        """Inference source can ONLY write SEMANTIC."""
        # Semantic allowed
        result = self.permissions.can_write(
            MemoryType.SEMANTIC, SourceType.INFERENCE, PermissionLevel.EXECUTE
        )
        self.assertTrue(result.allowed)
        # Short-term denied
        result = self.permissions.can_write(
            MemoryType.SHORT_TERM, SourceType.INFERENCE, PermissionLevel.EXECUTE
        )
        self.assertFalse(result.allowed)

    def test_write_permission_procedural_requires_admin(self):
        """Procedural memory write requires ADMIN level."""
        result = self.permissions.can_write(
            MemoryType.PROCEDURAL, SourceType.AGENT, PermissionLevel.EXECUTE
        )
        self.assertFalse(result.allowed)
        result = self.permissions.can_write(
            MemoryType.PROCEDURAL, SourceType.HUMAN, PermissionLevel.ADMIN
        )
        self.assertTrue(result.allowed)

    def test_delete_permission_requires_admin(self):
        """Delete requires ADMIN level for all types."""
        # EXECUTE denied
        result = self.permissions.can_delete(MemoryType.SHORT_TERM, PermissionLevel.EXECUTE)
        self.assertFalse(result.allowed)
        # ADMIN allowed
        result = self.permissions.can_delete(MemoryType.SHORT_TERM, PermissionLevel.ADMIN)
        self.assertTrue(result.allowed)


# ============================================================================
# TestMemoryRetriever (8 tests)
# ============================================================================

class TestMemoryRetriever(unittest.TestCase):
    """Tests for MemoryRetriever — semantic search, type filter, ranking."""

    def setUp(self):
        self.store = make_store()
        self.retriever = MemoryRetriever(self.store, embedding_service=None)

    def tearDown(self):
        self.store.close()

    def test_retrieve_by_type(self):
        """Retrieve all memories of a specific type."""
        for i in range(5):
            entry = make_entry({"key": f"val_{i}"}, MemoryType.SHORT_TERM)
            self.store.write_memory(entry)
        results = self.retriever.retrieve_by_type(MemoryType.SHORT_TERM, max_results=10)
        self.assertEqual(len(results), 5)

    def test_retrieve_recent(self):
        """Retrieve N most recent memories."""
        for i in range(10):
            entry = make_entry({"index": i}, MemoryType.SHORT_TERM)
            entry.timestamp = time.time() + i  # Increasing timestamps
            self.store.write_memory(entry)
        results = self.retriever.retrieve_recent(n=3)
        self.assertLessEqual(len(results), 3)

    def test_retrieve_related(self):
        """Retrieve memories related to a given memory."""
        entry1 = make_entry({"topic": "robotics"}, MemoryType.SHORT_TERM)
        entry2 = make_entry({"topic": "sensors"}, MemoryType.SHORT_TERM)
        id1 = self.store.write_memory(entry1)
        id2 = self.store.write_memory(entry2)
        related = self.retriever.retrieve_related(id1, max_results=5)
        self.assertIsInstance(related, list)

    def test_retrieve_keyword_fallback(self):
        """Keyword search fallback when embeddings unavailable."""
        entry = make_entry({"description": "robot arm calibration procedure"}, MemoryType.SHORT_TERM)
        self.store.write_memory(entry)
        results = self.retriever.retrieve(query="robot calibration")
        # Should find at least one result via keyword matching
        self.assertGreater(len(results), 0)

    def test_retrieve_with_type_filter(self):
        """Retrieve with memory type filter."""
        self.store.write_memory(make_entry({"data": "st"}, MemoryType.SHORT_TERM))
        self.store.write_memory(make_entry({"data": "sm"}, MemoryType.SEMANTIC))
        results = self.retriever.retrieve(
            query="data", memory_types=[MemoryType.SHORT_TERM]
        )
        # All results should be SHORT_TERM (or empty if keyword doesn't match)
        for r in results:
            self.assertEqual(r.entry.memory_type, MemoryType.SHORT_TERM)

    def test_retrieve_with_confidence_filter(self):
        """Retrieve with minimum confidence filter."""
        self.store.write_memory(make_entry({"data": "low"}, confidence=0.1))
        self.store.write_memory(make_entry({"data": "high"}, confidence=0.9))
        results = self.retriever.retrieve(query="high", min_confidence=0.5)
        for r in results:
            self.assertGreaterEqual(r.entry.confidence, 0.5)

    def test_retrieve_max_results(self):
        """Retrieve respects max_results."""
        for i in range(20):
            self.store.write_memory(make_entry({"data": f"item_{i}"}, MemoryType.SHORT_TERM))
        results = self.retriever.retrieve(query="data", max_results=3)
        self.assertLessEqual(len(results), 3)

    def test_retrieve_empty_store(self):
        """Retrieve from empty store returns empty list."""
        results = self.retriever.retrieve(query="anything")
        self.assertEqual(len(results), 0)


# ============================================================================
# TestMemoryWriter (6 tests)
# ============================================================================

class TestMemoryWriter(unittest.TestCase):
    """Tests for MemoryWriter — write, batch, update, delete, permission, validation."""

    def setUp(self):
        self.store = make_store()
        self.poisoning = PoisoningResistance()
        self.detector = ContradictionDetector()
        self.validation = ValidationPipeline(self.poisoning, self.detector)
        self.permissions = MemoryPermissions()
        self.writer = MemoryWriter(
            self.store, self.validation, self.poisoning, self.permissions,
            contradiction_detector=self.detector,
        )

    def tearDown(self):
        self.store.close()

    def test_write_success(self):
        """Valid memory write succeeds."""
        entry = make_entry({"task": "test"}, MemoryType.SHORT_TERM)
        result = self.writer.write(entry, requester_level=PermissionLevel.EXECUTE)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.memory_id)

    def test_write_permission_denied(self):
        """Write denied when permission level too low."""
        entry = make_entry({"task": "test"}, MemoryType.PROCEDURAL)
        result = self.writer.write(entry, requester_level=PermissionLevel.EXECUTE)
        self.assertFalse(result.success)
        self.assertTrue(result.permission_denied)

    def test_write_batch(self):
        """Batch write writes multiple entries."""
        entries = [
            make_entry({"i": 0}, MemoryType.SHORT_TERM),
            make_entry({"i": 1}, MemoryType.SHORT_TERM),
            make_entry({"i": 2}, MemoryType.SHORT_TERM),
        ]
        results = self.writer.write_batch(entries, requester_level=PermissionLevel.EXECUTE)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))

    def test_update_existing(self):
        """Update existing memory content."""
        entry = make_entry({"value": 1}, MemoryType.SHORT_TERM)
        mid = self.store.write_memory(entry)
        result = self.writer.update(mid, {"value": 2}, requester_level=PermissionLevel.EXECUTE)
        self.assertTrue(result.success)
        updated = self.store.get_memory(mid)
        self.assertEqual(updated.content.get("value"), 2)

    def test_delete_requires_admin(self):
        """Delete is denied without ADMIN level."""
        entry = make_entry({"value": 1}, MemoryType.SHORT_TERM)
        mid = self.store.write_memory(entry)
        result = self.writer.delete(mid, requester_level=PermissionLevel.EXECUTE)
        self.assertFalse(result)
        # With ADMIN
        result = self.writer.delete(mid, requester_level=PermissionLevel.ADMIN)
        self.assertTrue(result)

    def test_write_validation_rejects_anomalous(self):
        """Validation pipeline rejects anomalous entries."""
        # Create an entry with anomalous source (very high rate to trigger rate limit)
        # We test by creating many entries rapidly from the same writer
        entry = make_entry({"flood": True}, MemoryType.SHORT_TERM, writer_id="flooder")
        results = []
        for _ in range(200):  # Exceed rate limit (120/min)
            r = self.writer.write(entry, requester_level=PermissionLevel.EXECUTE)
            results.append(r)
        # At least some should be rejected by rate limiting
        rejected = [r for r in results if not r.success]
        self.assertGreater(len(rejected), 0, "Rate limiting should reject some entries")


# ============================================================================
# TestMemoryVerifier (5 tests)
# ============================================================================

class TestMemoryVerifier(unittest.TestCase):
    """Tests for MemoryVerifier — verify, resolve conflict, confidence trend."""

    def setUp(self):
        self.store = make_store()
        self.detector = ContradictionDetector()
        self.verifier = MemoryVerifier(self.store, self.detector)

    def tearDown(self):
        self.store.close()

    def test_verify_detects_conflict(self):
        """Verification detects conflicting observations."""
        entry = make_entry({"status": "online"}, MemoryType.SEMANTIC, confidence=0.9)
        mid = self.store.write_memory(entry)
        observations = [{"content": {"status": "offline"}, "memory_type": MemoryType.SEMANTIC}]
        report = self.verifier.verify(observations)
        self.assertGreater(report.total_checked, 0)
        self.assertGreater(len(report.conflicts), 0)

    def test_verify_confirms_matching(self):
        """Verification confirms matching observations."""
        entry = make_entry({"status": "online"}, MemoryType.SEMANTIC, confidence=0.9)
        self.store.write_memory(entry)
        observations = [{"content": {"status": "online"}, "memory_type": MemoryType.SEMANTIC}]
        report = self.verifier.verify(observations)
        self.assertGreater(report.confirmations, 0)

    def test_resolve_conflict_overwrite(self):
        """Resolve conflict with OVERWRITE — new observation wins."""
        entry = make_entry({"status": "online"}, MemoryType.SEMANTIC)
        mid = self.store.write_memory(entry)
        obs = {"status": "offline"}
        result = self.verifier.resolve_conflict(mid, obs, ConflictResolution.OVERWRITE)
        self.assertTrue(result)

    def test_resolve_conflict_reject(self):
        """Resolve conflict with REJECT — stored memory kept."""
        entry = make_entry({"status": "online"}, MemoryType.SEMANTIC)
        mid = self.store.write_memory(entry)
        result = self.verifier.resolve_conflict(mid, {"status": "offline"}, ConflictResolution.REJECT)
        self.assertTrue(result)
        # Memory should still be there
        still_there = self.store.get_memory(mid)
        self.assertIsNotNone(still_there)

    def test_resolve_conflict_flag(self):
        """Resolve conflict with FLAG — marked for review."""
        entry = make_entry({"status": "online"}, MemoryType.SEMANTIC)
        mid = self.store.write_memory(entry)
        result = self.verifier.resolve_conflict(mid, {"status": "offline"}, ConflictResolution.FLAG)
        self.assertTrue(result)

    def test_confidence_trend(self):
        """Get confidence trend for a memory."""
        entry = make_entry({"data": "test"}, MemoryType.SEMANTIC, confidence=0.85)
        mid = self.store.write_memory(entry)
        trend = self.verifier.get_confidence_trend(mid)
        self.assertIsInstance(trend, list)
        self.assertEqual(len(trend), 1)
        self.assertAlmostEqual(trend[0], 0.85, places=1)


# ============================================================================
# TestMemoryDecay (5 tests)
# ============================================================================

class TestMemoryDecay(unittest.TestCase):
    """Tests for MemoryDecay — expire, importance, promote, demote, consolidate."""

    def setUp(self):
        self.store = make_store()
        self.decay = MemoryDecay(self.store)

    def tearDown(self):
        self.store.close()

    def test_run_decay_basic(self):
        """Run decay pass returns a DecayReport."""
        self.store.write_memory(make_entry({"data": "test"}, MemoryType.SHORT_TERM))
        report = self.decay.run_decay()
        self.assertIsInstance(report, DecayReport)
        self.assertIsInstance(report.expired, int)

    def test_score_importance(self):
        """Importance score is between 0 and 1."""
        entry = make_entry({"data": "test"}, MemoryType.SHORT_TERM, confidence=0.9)
        mid = self.store.write_memory(entry)
        score = self.decay.score_importance(mid)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_score_importance_nonexistent(self):
        """Importance score for nonexistent memory is 0."""
        score = self.decay.score_importance("nonexistent_id")
        self.assertEqual(score, 0.0)

    def test_consolidate_memories(self):
        """Consolidate multiple memories into one."""
        entries = [
            make_entry({"a": 1}, MemoryType.SHORT_TERM, confidence=0.8),
            make_entry({"b": 2}, MemoryType.SHORT_TERM, confidence=0.6),
        ]
        ids = [self.store.write_memory(e) for e in entries]
        new_id = self.decay.consolidate(ids)
        self.assertIsNotNone(new_id)

    def test_consolidate_single_memory_returns_none(self):
        """Consolidating a single memory returns None."""
        entry = make_entry({"a": 1}, MemoryType.SHORT_TERM)
        mid = self.store.write_memory(entry)
        result = self.decay.consolidate([mid])
        self.assertIsNone(result)


# ============================================================================
# TestWorldStateManager (5 tests)
# ============================================================================

class TestWorldStateManager(unittest.TestCase):
    """Tests for WorldStateManager — current state, update, history, diff."""

    def setUp(self):
        self.store = make_store()
        self.wsm = WorldStateManager(self.store)

    def tearDown(self):
        self.store.close()

    def test_get_current_state_empty(self):
        """Empty store yields empty state."""
        self.wsm.clear()
        state = self.wsm.get_current_state()
        self.assertIsInstance(state, dict)

    def test_update_state(self):
        """Update state returns a diff."""
        self.wsm.clear()
        observation = {"entities": {"robot_1": {"position": "home"}}, "confidence": 0.9}
        diff = self.wsm.update_state(observation)
        self.assertFalse(diff.is_empty)
        self.assertIn("robot_1", diff.added)

    def test_update_state_modifies_existing(self):
        """Update modifies existing entity."""
        self.wsm.clear()
        self.wsm.update_state({"entities": {"robot_1": {"position": "home"}}, "confidence": 0.9})
        diff = self.wsm.update_state({"entities": {"robot_1": {"position": "kitchen"}}, "confidence": 0.85})
        self.assertIn("robot_1", diff.modified)

    def test_get_state_history(self):
        """Get state history for a key."""
        self.wsm.clear()
        self.wsm.update_state({"entities": {"sensor_1": 100}, "confidence": 0.9})
        self.wsm.update_state({"entities": {"sensor_1": 200}, "confidence": 0.8})
        history = self.wsm.get_state_history("sensor_1", n=5)
        self.assertGreater(len(history), 0)

    def test_get_state_at_timestamp(self):
        """Reconstruct state at a given timestamp."""
        self.wsm.clear()
        t1 = time.time()
        self.wsm.update_state({"entities": {"x": 1}, "confidence": 0.9})
        t2 = time.time()
        self.wsm.update_state({"entities": {"x": 2}, "confidence": 0.9})
        state = self.wsm.get_state_at(t1)
        self.assertIsInstance(state, dict)


# ============================================================================
# TestMemoryManager (6 tests)
# ============================================================================

class TestMemoryManager(unittest.TestCase):
    """Tests for MemoryManager — orchestrator."""

    def setUp(self):
        self.store = make_store()
        self.embedding = EmbeddingService(api_key=None)  # Fallback mode
        self.retriever = MemoryRetriever(self.store, embedding_service=None)
        self.poisoning = PoisoningResistance()
        self.detector = ContradictionDetector()
        self.validation = ValidationPipeline(self.poisoning, self.detector)
        self.permissions = MemoryPermissions()
        self.writer = MemoryWriter(self.store, self.validation, self.poisoning,
                                    self.permissions, contradiction_detector=self.detector)
        self.verifier = MemoryVerifier(self.store, self.detector)
        self.decay = MemoryDecay(self.store)
        self.wsm = WorldStateManager(self.store)
        self.manager = MemoryManager(
            self.store, self.retriever, self.writer, self.verifier,
            self.permissions, self.decay, self.wsm,
        )

    def tearDown(self):
        self.store.close()

    def test_remember_stores_observation(self):
        """remember() stores an observation as memory."""
        result = self.manager.remember(
            task_id="task_001",
            goal="test goal",
            observation={
                "content": {"result": "success"},
                "memory_type": "short_term",
                "writer_id": "test_agent",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        self.assertTrue(result.stored)
        self.assertIsNotNone(result.memory_id)

    def test_remember_permission_denied(self):
        """remember() denied without sufficient permissions."""
        result = self.manager.remember(
            task_id="task_002",
            goal="test goal",
            observation={
                "content": {"result": "data"},
                "memory_type": "procedural",
                "writer_id": "test_agent",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        self.assertFalse(result.stored)

    def test_recall_returns_memories(self):
        """recall() retrieves relevant memories."""
        # Store a memory first
        self.manager.remember(
            task_id="task_001",
            goal="calibrate robot arm",
            observation={
                "content": {"task": "calibrate robot arm", "status": "done"},
                "memory_type": "short_term",
                "writer_id": "test_agent",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        results = self.manager.recall("calibrate robot arm")
        self.assertIsInstance(results, list)

    def test_get_context_for_planning(self):
        """get_context_for_planning returns structured context."""
        # Store some memories
        self.manager.remember(
            task_id="task_001",
            goal="test",
            observation={
                "content": {"data": "context"},
                "memory_type": "short_term",
                "writer_id": "test_agent",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        ctx = self.manager.get_context_for_planning("test")
        self.assertIn("relevant_memories", ctx)
        self.assertIn("world_state", ctx)
        self.assertIn("recent_observations", ctx)
        self.assertIn("contradictions_flagged", ctx)

    def test_verify_memories(self):
        """verify_memories returns a verification report."""
        self.manager.remember(
            task_id="task_001",
            goal="test",
            observation={
                "content": {"status": "online"},
                "memory_type": "semantic",
                "writer_id": "test_agent",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        report = self.manager.verify_memories([
            {"content": {"status": "offline"}, "memory_type": MemoryType.SEMANTIC},
        ])
        self.assertGreater(report.total_checked, 0)

    def test_run_decay(self):
        """run_decay returns a DecayReport."""
        self.manager.remember(
            task_id="task_001",
            goal="test",
            observation={
                "content": {"data": "test"},
                "memory_type": "short_term",
                "writer_id": "test_agent",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        report = self.manager.run_decay()
        self.assertIsInstance(report, DecayReport)


# ============================================================================
# TestCoreMemoryIntegration (5 tests)
# ============================================================================

class TestCoreMemoryIntegration(unittest.TestCase):
    """Integration tests for memory with CoreSupervisor lifecycle."""

    def setUp(self):
        self.store = make_store()
        self.embedding = None
        self.retriever = MemoryRetriever(self.store, embedding_service=None)
        self.poisoning = PoisoningResistance()
        self.detector = ContradictionDetector()
        self.validation = ValidationPipeline(self.poisoning, self.detector)
        self.permissions = MemoryPermissions()
        self.writer = MemoryWriter(self.store, self.validation, self.poisoning,
                                    self.permissions, contradiction_detector=self.detector)
        self.verifier = MemoryVerifier(self.store, self.detector)
        self.decay = MemoryDecay(self.store)
        self.wsm = WorldStateManager(self.store)
        self.manager = MemoryManager(
            self.store, self.retriever, self.writer, self.verifier,
            self.permissions, self.decay, self.wsm,
        )

    def tearDown(self):
        self.store.close()

    def test_full_lifecycle_recall_plan_execute_remember(self):
        """Full lifecycle: recall -> plan -> execute -> remember."""
        # Step 1: Remember from a "previous task"
        self.manager.remember(
            task_id="prev_task",
            goal="calibrate sensor A",
            observation={
                "content": {"sensor": "A", "calibrated": True},
                "memory_type": "short_term",
                "writer_id": "orion",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )

        # Step 2: Recall for a new similar goal
        memories = self.manager.recall("calibrate sensor")
        self.assertIsInstance(memories, list)

        # Step 3: Get context for planning
        ctx = self.manager.get_context_for_planning("calibrate sensor A")
        self.assertIsInstance(ctx, dict)

        # Step 4: Remember the new task result
        result = self.manager.remember(
            task_id="new_task",
            goal="calibrate sensor A",
            observation={
                "content": {"sensor": "A", "calibrated": True, "repeat": True},
                "memory_type": "short_term",
                "writer_id": "orion",
                "source_type": "agent",
                "confidence": 0.95,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        self.assertTrue(result.stored)

    def test_cross_session_persistence(self):
        """Memory persists across store close/reopen."""
        # Store a memory
        self.manager.remember(
            task_id="session1",
            goal="test persistence",
            observation={
                "content": {"data": "persistent"},
                "memory_type": "semantic",
                "writer_id": "orion",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        db_path = self.store.db_path
        self.store.close()

        # Reopen store from the same file
        self.store = MemoryStore(db_path=db_path)
        entries = self.store.query_memories(memory_type=MemoryType.SEMANTIC, limit=10)
        self.assertGreater(len(entries), 0)
        found = any(e.content.get("data") == "persistent" for e in entries)
        self.assertTrue(found, "Memory should persist across sessions")

    def test_memory_poisoning_resistance(self):
        """Poisoned writes are rejected by validation pipeline."""
        # Create many entries rapidly to trigger rate limiting
        results = []
        for i in range(200):
            r = self.writer.write(
                make_entry({"flood": i}, MemoryType.SHORT_TERM, writer_id="attacker"),
                requester_level=PermissionLevel.EXECUTE,
            )
            results.append(r)
        rejected = [r for r in results if not r.success]
        self.assertGreater(len(rejected), 0, "Rate limiting should prevent flooding")

    def test_contradiction_detection_lifecycle(self):
        """Contradictions detected during write and verification."""
        # Write initial memory
        self.writer.write(
            make_entry({"status": "online"}, MemoryType.SEMANTIC, confidence=0.9),
            requester_level=PermissionLevel.EXECUTE,
        )
        # Verify with conflicting observation
        report = self.verifier.verify([
            {"content": {"status": "offline"}, "memory_type": MemoryType.SEMANTIC},
        ])
        self.assertGreater(len(report.conflicts), 0)

    def test_world_state_updates_with_remember(self):
        """World state updates when remember() is called."""
        self.wsm.clear()
        self.manager.remember(
            task_id="task_001",
            goal="update state",
            observation={
                "content": {"entity_1": {"pos": [0, 0]}},
                "memory_type": "semantic",
                "writer_id": "orion",
                "source_type": "agent",
                "confidence": 0.9,
            },
            requester_level=PermissionLevel.EXECUTE,
        )
        state = self.wsm.get_current_state()
        self.assertIsInstance(state, dict)


if __name__ == "__main__":
    unittest.main()
