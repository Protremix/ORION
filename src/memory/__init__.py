"""
ORION Memory Subsystem package — Phase 005.

Includes Phase 1 baseline (memory_system) and Phase 005 extensions:
retriever, writer, verifier, permissions, decay, world state, and manager.
"""

from .memory_decay import DecayReport, MemoryDecay
from .memory_manager import MemoryManager, MemoryResult
from .memory_permissions import MemoryPermissionResult, MemoryPermissions
from .memory_retriever import MemoryRetriever, RetrievalResult
from .memory_system import (
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
    ValidationResult,
    WorkingMemory,
)
from .memory_verifier import ConflictResolution, MemoryVerifier, VerificationReport
from .memory_writer import MemoryWriter, WriteResult
from .world_state_manager import StateDiff, WorldStateManager

__all__ = [
    # Phase 1
    "MemoryType",
    "SourceType",
    "RetentionType",
    "ContradictionStatus",
    "Provenance",
    "RetentionPolicy",
    "PoisoningMetadata",
    "MemoryEntry",
    "ShortTermMemory",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "AuditTrailEntry",
    "EmbeddingService",
    "ContradictionDetector",
    "PoisoningResistance",
    "ValidationResult",
    "ValidationPipeline",
    "MemoryStore",
    # Phase 005
    "MemoryPermissions",
    "MemoryPermissionResult",
    "MemoryRetriever",
    "RetrievalResult",
    "MemoryWriter",
    "WriteResult",
    "MemoryVerifier",
    "VerificationReport",
    "ConflictResolution",
    "MemoryDecay",
    "DecayReport",
    "WorldStateManager",
    "StateDiff",
    "MemoryManager",
    "MemoryResult",
]
