"""
ORION Phase 005 — Memory Manager (Orchestrator). License: Apache 2.0

Single entry point for CoreSupervisor. Manages the REMEMBER lifecycle step
and coordinates all memory subsystems.

Integration point in CoreSupervisor.run():
  GOAL -> recall() -> PLAN (with memory context) -> EXECUTE -> OBSERVE ->
  EVALUATE -> remember() -> [next iteration or complete]
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.permission_engine import PermissionLevel
from src.memory.memory_decay import DecayReport, MemoryDecay
from src.memory.memory_permissions import MemoryPermissions
from src.memory.memory_retriever import MemoryRetriever, RetrievalResult
from src.memory.memory_system import (
    EpisodicMemory,
    MemoryEntry,
    MemoryStore,
    MemoryType,
    Provenance,
    SemanticMemory,
    ShortTermMemory,
    SourceType,
)
from src.memory.memory_verifier import MemoryVerifier, VerificationReport
from src.memory.memory_writer import MemoryWriter, WriteResult
from src.memory.world_state_manager import StateDiff, WorldStateManager

logger = logging.getLogger(__name__)


@dataclass
class MemoryResult:
    """Result of a remember() call."""
    stored: bool = False
    memory_id: Optional[str] = None
    conflicts: List[str] = field(default_factory=list)
    world_state_updated: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stored": self.stored,
            "memory_id": self.memory_id,
            "conflicts": self.conflicts,
            "world_state_updated": self.world_state_updated,
            "error": self.error,
        }


class MemoryManager:
    """
    Orchestrator for the memory subsystem.

    Single entry point for CoreSupervisor. Coordinates retrieval, writing,
    verification, permissions, decay, and world state management.
    """

    def __init__(
        self,
        store: MemoryStore,
        retriever: MemoryRetriever,
        writer: MemoryWriter,
        verifier: MemoryVerifier,
        permissions: MemoryPermissions,
        decay: MemoryDecay,
        world_state: WorldStateManager,
    ) -> None:
        self._store = store
        self._retriever = retriever
        self._writer = writer
        self._verifier = verifier
        self._permissions = permissions
        self._decay = decay
        self._world_state = world_state

    def remember(
        self,
        goal: str,
        observation: Dict[str, Any],
        memory_type: MemoryType = MemoryType.EPISODIC,
        source_type: SourceType = SourceType.AGENT,
        requester_level: Optional[PermissionLevel] = None,
    ) -> MemoryResult:
        """
        Called by CoreSupervisor after EVALUATE step.
        Stores observation, updates world state, runs decay.
        """
        entry = self._create_memory_entry(
            goal=goal,
            observation=observation,
            memory_type=memory_type,
            source_type=source_type,
        )
        if entry is None:
            return MemoryResult(
                stored=False,
                error="Failed to create memory entry from observation",
            )

        write_result = self._writer.write(entry, requester_level=requester_level)
        if not write_result.success:
            return MemoryResult(
                stored=False,
                conflicts=write_result.conflicts,
                error=write_result.error,
            )

        world_diff = self._world_state.update_state(observation)

        return MemoryResult(
            stored=True,
            memory_id=write_result.memory_id,
            conflicts=write_result.conflicts,
            world_state_updated=world_diff.has_changes,
        )

    def recall(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        max_results: int = 10,
    ) -> List[MemoryEntry]:
        """Called by CoreSupervisor before PLANNING. Retrieves relevant memories."""
        query = goal
        if context:
            query_str = str(context.get("query", ""))
            if query_str:
                query = f"{goal} {query_str}"

        results = self._retriever.retrieve(query=query, max_results=max_results)
        return [r.entry for r in results]

    def get_context_for_planning(self, goal: str) -> Dict[str, Any]:
        """
        Returns structured context dict with relevant memories, world state,
        and recent observations for injection into planning prompt.
        """
        memories = self.recall(goal, max_results=10)
        world_state = self._world_state.get_current_state()
        recent = self._retriever.retrieve_recent(n=5)

        return {
            "relevant_memories": [
                {
                    "type": m.memory_type.value if hasattr(m.memory_type, 'value') else str(m.memory_type),
                    "content": m.content,
                    "confidence": m.confidence,
                    "timestamp": m.timestamp,
                }
                for m in memories
            ],
            "world_state": world_state,
            "recent_observations": [
                {
                    "type": m.memory_type.value if hasattr(m.memory_type, 'value') else str(m.memory_type),
                    "content": m.content,
                    "confidence": m.confidence,
                    "timestamp": m.timestamp,
                }
                for m in recent
            ],
        }

    def verify_memories(
        self, observations: List[Dict[str, Any]]
    ) -> VerificationReport:
        """Run verification pass — compare stored memories against new observations."""
        return self._verifier.verify(observations)

    def run_decay(self) -> DecayReport:
        """Run a full decay pass manually."""
        return self._decay.run_decay()

    def rebuild_world_state(self) -> Dict[str, Any]:
        """Rebuild world state from stored memories (recovery)."""
        return self._world_state.rebuild_from_memory()

    def _create_memory_entry(
        self,
        goal: str,
        observation: Dict[str, Any],
        memory_type: MemoryType,
        source_type: SourceType,
    ) -> Optional[MemoryEntry]:
        """Create a MemoryEntry from an observation."""
        try:
            now = time.time()
            provenance = Provenance(
                writer_id="supervisor",
                writer_permissions=["memory:write:cognitive"],
                source_type=source_type,
            )

            content = {
                "goal": goal,
                "observation": observation,
                "timestamp": now,
            }

            if memory_type == MemoryType.EPISODIC:
                return EpisodicMemory(
                    memory_type=memory_type,
                    content=content,
                    confidence=observation.get("confidence", 0.8),
                    provenance=provenance,
                )
            elif memory_type == MemoryType.SHORT_TERM:
                return ShortTermMemory(
                    memory_type=memory_type,
                    content=content,
                    confidence=observation.get("confidence", 0.7),
                    provenance=provenance,
                )
            elif memory_type == MemoryType.SEMANTIC:
                return SemanticMemory(
                    memory_type=memory_type,
                    content=content,
                    confidence=observation.get("confidence", 0.9),
                    provenance=provenance,
                )
            else:
                return MemoryEntry(
                    memory_type=memory_type,
                    content=content,
                    confidence=observation.get("confidence", 0.8),
                    provenance=provenance,
                )
        except Exception as e:
            logger.error("Failed to create memory entry: %s", e)
            return None
