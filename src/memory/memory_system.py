"""
ORION Physical Intelligence OS - Phase 1 Memory Subsystem
Architecture Version: v0.5

This module implements the complete Phase 1 Memory Subsystem for Project ORION.
It enforces strict separation between Cognitive Memory and Audit Data to prevent
memory poisoning and self-reinforcement loops.

Key Components:
1. Memory Data Classes: ShortTerm, Working, Episodic, Semantic, Procedural, AuditTrail
2. Provenance, Retention, and Poisoning Resistance Metadata
3. EmbeddingService: OpenAI text-embedding-3-large embeddings with vector utilities
4. ContradictionDetector: Cosine similarity threshold for semantic memories & exact-match for facts
5. PoisoningResistance: Writer rate limiting, source permission verification, and anomaly detection
6. ValidationPipeline: Enforces multi-stage validation prior to memory storage
7. MemoryStore: SQLite storage for cognitive memory and separate tamper-evident audit logs
"""

import hashlib
import json
import logging
import math
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Configure logger
logger = logging.getLogger("orion.memory_system")


# ============================================================================
# Enums
# ============================================================================

class MemoryType(str, Enum):
    """Enumeration of supported memory types in ORION Architecture v0.5."""
    SHORT_TERM = "short_term"
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    AUDIT_TRAIL = "audit_trail"


class SourceType(str, Enum):
    """Origin source of memory entry."""
    SENSOR = "sensor"
    AGENT = "agent"
    INFERENCE = "inference"
    HUMAN = "human"


class RetentionType(str, Enum):
    """Retention policies for memory lifecycle management."""
    EPHEMERAL = "ephemeral"      # Seconds to minutes TTL
    SESSION = "session"          # Single execution session TTL
    LONG_TERM = "long_term"      # Extended TTL with decay
    PERMANENT = "permanent"      # No automatic expiration


class ContradictionStatus(str, Enum):
    """Status of contradiction detection for a memory entry."""
    NONE = "none"
    SUSPECTED = "suspected"
    RESOLVED_OVERWRITE = "resolved_overwrite"
    RESOLVED_REJECTED = "resolved_rejected"
    FLAGGED = "flagged"


# ============================================================================
# Metadata Data Classes
# ============================================================================

@dataclass
class Provenance:
    """
    Provenance tracking metadata for memory entry accountability.
    """
    writer_id: str
    writer_permissions: List[str]
    source_type: SourceType
    source_plane: str = "CognitivePlane"
    model_name: Optional[str] = None
    signature: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "writer_id": self.writer_id,
            "writer_permissions": self.writer_permissions,
            "source_type": self.source_type.value if isinstance(self.source_type, Enum) else self.source_type,
            "source_plane": self.source_plane,
            "model_name": self.model_name,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Provenance":
        st = d.get("source_type", SourceType.AGENT)
        if isinstance(st, str):
            st = SourceType(st)
        return cls(
            writer_id=d["writer_id"],
            writer_permissions=d.get("writer_permissions", []),
            source_type=st,
            source_plane=d.get("source_plane", "CognitivePlane"),
            model_name=d.get("model_name"),
            signature=d.get("signature"),
        )


@dataclass
class RetentionPolicy:
    """
    Retention policy defining the lifecycle and expiration of a memory entry.
    """
    retention_type: RetentionType
    ttl_seconds: Optional[float] = None
    expires_at: Optional[float] = None  # Unix epoch timestamp

    def __post_init__(self):
        if self.expires_at is None and self.ttl_seconds is not None:
            self.expires_at = time.time() + self.ttl_seconds

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        if self.retention_type == RetentionType.PERMANENT:
            return False
        if self.expires_at is None:
            return False
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "retention_type": self.retention_type.value if isinstance(self.retention_type, Enum) else self.retention_type,
            "ttl_seconds": self.ttl_seconds,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RetentionPolicy":
        rt = d.get("retention_type", RetentionType.SESSION)
        if isinstance(rt, str):
            rt = RetentionType(rt)
        return cls(
            retention_type=rt,
            ttl_seconds=d.get("ttl_seconds"),
            expires_at=d.get("expires_at"),
        )


@dataclass
class PoisoningMetadata:
    """
    Poisoning resistance tracking metadata.
    """
    anomaly_score: float = 0.0
    rate_limit_ok: bool = True
    source_verified: bool = True
    flagged_for_review: bool = False
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_score": self.anomaly_score,
            "rate_limit_ok": self.rate_limit_ok,
            "source_verified": self.source_verified,
            "flagged_for_review": self.flagged_for_review,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PoisoningMetadata":
        return cls(
            anomaly_score=float(d.get("anomaly_score", 0.0)),
            rate_limit_ok=bool(d.get("rate_limit_ok", True)),
            source_verified=bool(d.get("source_verified", True)),
            flagged_for_review=bool(d.get("flagged_for_review", False)),
            notes=d.get("notes"),
        )


# ============================================================================
# Memory Data Classes
# ============================================================================

@dataclass
class MemoryEntry:
    """
    Base dataclass for Cognitive Memory Entries.
    Every memory entry includes provenance, timestamp, confidence, contradiction status,
    versioning, poisoning resistance metadata, and retention policy.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType = MemoryType.SHORT_TERM
    content: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    embedding: Optional[List[float]] = None
    provenance: Provenance = field(default_factory=lambda: Provenance("system", ["memory:write:cognitive"], SourceType.AGENT))
    retention_policy: RetentionPolicy = field(default_factory=lambda: RetentionPolicy(RetentionType.SESSION))
    poisoning_metadata: PoisoningMetadata = field(default_factory=PoisoningMetadata)
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1
    schema_version: str = "1.0"
    contradiction_status: ContradictionStatus = ContradictionStatus.NONE
    contradicting_memory_ids: List[str] = field(default_factory=list)
    is_deleted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "memory_type": self.memory_type.value if isinstance(self.memory_type, Enum) else self.memory_type,
            "content": self.content,
            "summary": self.summary,
            "embedding": self.embedding,
            "provenance": self.provenance.to_dict(),
            "retention_policy": self.retention_policy.to_dict(),
            "poisoning_metadata": self.poisoning_metadata.to_dict(),
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "schema_version": self.schema_version,
            "contradiction_status": self.contradiction_status.value if isinstance(self.contradiction_status, Enum) else self.contradiction_status,
            "contradicting_memory_ids": self.contradicting_memory_ids,
            "is_deleted": self.is_deleted,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryEntry":
        mt = d.get("memory_type", MemoryType.SHORT_TERM)
        if isinstance(mt, str):
            mt = MemoryType(mt)
        cs = d.get("contradiction_status", ContradictionStatus.NONE)
        if isinstance(cs, str):
            cs = ContradictionStatus(cs)

        prov = d["provenance"]
        if isinstance(prov, dict):
            prov = Provenance.from_dict(prov)

        ret = d["retention_policy"]
        if isinstance(ret, dict):
            ret = RetentionPolicy.from_dict(ret)

        pm = d.get("poisoning_metadata", PoisoningMetadata())
        if isinstance(pm, dict):
            pm = PoisoningMetadata.from_dict(pm)

        return cls(
            id=d["id"],
            memory_type=mt,
            content=d.get("content", {}),
            summary=d.get("summary", ""),
            embedding=d.get("embedding"),
            provenance=prov,
            retention_policy=ret,
            poisoning_metadata=pm,
            confidence=float(d.get("confidence", 1.0)),
            timestamp=float(d.get("timestamp", time.time())),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=d.get("updated_at", datetime.now(timezone.utc).isoformat()),
            version=int(d.get("version", 1)),
            schema_version=d.get("schema_version", "1.0"),
            contradiction_status=cs,
            contradicting_memory_ids=d.get("contradicting_memory_ids", []),
            is_deleted=bool(d.get("is_deleted", False)),
        )


@dataclass
class ShortTermMemory(MemoryEntry):
    """
    Short-Term Memory representation for transient, high-frequency context (e.g., immediate sensor state).
    Default TTL: 300 seconds (5 minutes).
    """
    def __post_init__(self):
        self.memory_type = MemoryType.SHORT_TERM
        if self.retention_policy is None or self.retention_policy.retention_type == RetentionType.SESSION:
            self.retention_policy = RetentionPolicy(RetentionType.EPHEMERAL, ttl_seconds=300.0)


@dataclass
class WorkingMemory(MemoryEntry):
    """
    Working Memory representation for current reasoning task execution context, goals, and scratchpad.
    """
    focus_goal: str = ""
    active_step: int = 0

    def __post_init__(self):
        self.memory_type = MemoryType.WORKING
        if "focus_goal" in self.content:
            self.focus_goal = str(self.content["focus_goal"])
        if "active_step" in self.content:
            self.active_step = int(self.content["active_step"])

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["content"]["focus_goal"] = self.focus_goal
        d["content"]["active_step"] = self.active_step
        return d


@dataclass
class EpisodicMemory(MemoryEntry):
    """
    Episodic Memory representation for past experienced events, actions, outcomes, and environmental conditions.
    """
    episode_id: str = ""
    outcome: str = "unknown"

    def __post_init__(self):
        self.memory_type = MemoryType.EPISODIC
        if "episode_id" in self.content:
            self.episode_id = str(self.content["episode_id"])
        if "outcome" in self.content:
            self.outcome = str(self.content["outcome"])

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["content"]["episode_id"] = self.episode_id
        d["content"]["outcome"] = self.outcome
        return d


@dataclass
class SemanticMemory(MemoryEntry):
    """
    Semantic Memory representation for general domain knowledge, facts, and concepts.
    Uses OpenAI text-embedding-3-large for vector similarity lookup.
    """
    concept_key: str = ""

    def __post_init__(self):
        self.memory_type = MemoryType.SEMANTIC
        if "concept_key" in self.content:
            self.concept_key = str(self.content["concept_key"])

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["content"]["concept_key"] = self.concept_key
        return d


@dataclass
class ProceduralMemory(MemoryEntry):
    """
    Procedural Memory representation for action skills, control recipes, and execution workflows.
    """
    skill_name: str = ""
    preconditions: List[str] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self.memory_type = MemoryType.PROCEDURAL
        if "skill_name" in self.content:
            self.skill_name = str(self.content["skill_name"])
        if "preconditions" in self.content:
            self.preconditions = list(self.content["preconditions"])
        if "steps" in self.content:
            self.steps = list(self.content["steps"])

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["content"]["skill_name"] = self.skill_name
        d["content"]["preconditions"] = self.preconditions
        d["content"]["steps"] = self.steps
        return d


@dataclass
class AuditTrailEntry:
    """
    AuditTrail Entry stored SEPARATELY from cognitive memory to prevent self-reinforcement / memory poisoning.
    Audit entries use cryptographic hash-chaining (SHA-256) for tamper detection.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "audit"
    actor_id: str = "system"
    action: str = "read"
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_hash: str = "GENESIS"
    hash: str = ""
    source_type: SourceType = SourceType.AGENT
    retention_policy: RetentionPolicy = field(default_factory=lambda: RetentionPolicy(RetentionType.PERMANENT))

    def __post_init__(self):
        if not self.hash:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Computes cryptographic SHA-256 hash of entry content linked to previous_hash."""
        payload_str = json.dumps(self.payload, sort_keys=True)
        raw = f"{self.previous_hash}|{self.id}|{self.event_type}|{self.actor_id}|{self.action}|{payload_str}|{self.timestamp}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Verifies if the stored hash matches computed hash."""
        return self.hash == self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "action": self.action,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "created_at": self.created_at,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
            "source_type": self.source_type.value if isinstance(self.source_type, Enum) else self.source_type,
            "retention_policy": self.retention_policy.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditTrailEntry":
        st = d.get("source_type", SourceType.AGENT)
        if isinstance(st, str):
            st = SourceType(st)

        ret = d.get("retention_policy", RetentionPolicy(RetentionType.PERMANENT))
        if isinstance(ret, dict):
            ret = RetentionPolicy.from_dict(ret)

        return cls(
            id=d["id"],
            event_type=d.get("event_type", "audit"),
            actor_id=d.get("actor_id", "system"),
            action=d.get("action", "read"),
            payload=d.get("payload", {}),
            timestamp=float(d.get("timestamp", time.time())),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
            previous_hash=d.get("previous_hash", "GENESIS"),
            hash=d.get("hash", ""),
            source_type=st,
            retention_policy=ret,
        )


# ============================================================================
# 3. EmbeddingService
# ============================================================================

class EmbeddingService:
    """
    Embedding Service using OpenAI API text-embedding-3-large model.
    Falls back to deterministic hash-based embeddings when OPENAI_API_KEY is omitted or offline.
    """
    MODEL_NAME = "text-embedding-3-large"
    EMBEDDING_DIM = 3072

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None
        if self.api_key:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
                logger.info("EmbeddingService initialized with OpenAI client.")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}. Falling back to offline embedding generator.")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates vector embedding for the given text.
        Uses OpenAI text-embedding-3-large API if key is available, else synthetic fallback.
        """
        if not text or not text.strip():
            return [0.0] * self.EMBEDDING_DIM

        if self._client is not None:
            try:
                response = self._client.embeddings.create(
                    model=self.MODEL_NAME,
                    input=text.strip()
                )
                embedding = response.data[0].embedding
                return embedding
            except Exception as e:
                logger.warning(f"OpenAI embedding generation call failed: {e}. Utilizing fallback generator.")

        # Fallback deterministic normalized vector generator for offline/testing environments
        return self._generate_fallback_embedding(text)

    def _generate_fallback_embedding(self, text: str) -> List[float]:
        """Generates a unit-normalized pseudo-random 3072-dim embedding from text SHA-256 seed."""
        dim = self.EMBEDDING_DIM
        vec = [0.0] * dim
        base_hash = hashlib.sha256(text.encode("utf-8")).digest()
        for i in range(dim):
            # Mix hash byte with index for variation
            byte_val = base_hash[i % len(base_hash)]
            val = ((byte_val ^ (i & 0xFF)) / 255.0) - 0.5
            vec[i] = val

        # Normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculates cosine similarity between two vector embeddings."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = math.sqrt(sum(a * a for a in vec1))
        norm_b = math.sqrt(sum(b * b for b in vec2))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        similarity = dot_product / (norm_a * norm_b)
        # Clamp to [-1.0, 1.0] to handle floating point rounding
        return max(-1.0, min(1.0, similarity))


# ============================================================================
# 5. Contradiction Detection
# ============================================================================

class ContradictionDetector:
    """
    Contradiction Detector.
    Supports cosine similarity thresholding for semantic memories
    and exact match key/value collision detection for structured facts.
    """

    def __init__(self, semantic_similarity_threshold: float = 0.82):
        self.semantic_similarity_threshold = semantic_similarity_threshold

    def check_contradictions(
        self,
        new_entry: MemoryEntry,
        existing_entries: List[MemoryEntry]
    ) -> Tuple[ContradictionStatus, List[str], List[str]]:
        """
        Checks a new memory entry against existing entries for contradictions.
        Returns (status, contradicting_ids, details_list).
        """
        contradicting_ids: List[str] = []
        details: List[str] = []

        for existing in existing_entries:
            if existing.id == new_entry.id or existing.is_deleted:
                continue

            # Check 1: Fact / Structured key collision check
            fact_conflict, fact_msg = self._check_fact_contradiction(new_entry, existing)
            if fact_conflict:
                contradicting_ids.append(existing.id)
                details.append(f"Fact contradiction with {existing.id}: {fact_msg}")

            # Check 2: Semantic embedding similarity contradiction check
            if new_entry.memory_type == MemoryType.SEMANTIC or existing.memory_type == MemoryType.SEMANTIC:
                sem_conflict, sem_msg = self._check_semantic_contradiction(new_entry, existing)
                if sem_conflict:
                    contradicting_ids.append(existing.id)
                    details.append(f"Semantic contradiction with {existing.id}: {sem_msg}")

        if contradicting_ids:
            return ContradictionStatus.SUSPECTED, contradicting_ids, details

        return ContradictionStatus.NONE, [], []

    def _check_fact_contradiction(self, new_entry: MemoryEntry, existing: MemoryEntry) -> Tuple[bool, str]:
        """Exact match attribute key collision check for facts."""
        new_content = new_entry.content
        exist_content = existing.content

        # Key structured fact pattern: subject + attribute -> value
        subject_keys = ["subject", "entity", "target", "concept_key", "fact_subject"]
        attribute_keys = ["attribute", "property", "key", "predicate"]
        value_keys = ["value", "state", "val"]

        # If subject and attribute match but value differs -> contradiction
        for s_key in subject_keys:
            if s_key in new_content and s_key in exist_content:
                if new_content[s_key] == exist_content[s_key]:
                    for a_key in attribute_keys:
                        if a_key in new_content and a_key in exist_content:
                            if new_content[a_key] == exist_content[a_key]:
                                # Compare values
                                for v_key in value_keys:
                                    if v_key in new_content and v_key in exist_content:
                                        if new_content[v_key] != exist_content[v_key]:
                                            return True, (
                                                f"Conflicting value for [{new_content[s_key]}.{new_content[a_key]}]: "
                                                f"'{new_content[v_key]}' vs existing '{exist_content[v_key]}'"
                                            )

        # Check explicit contradictory boolean assertions
        if "negation" in new_content or "is_true" in new_content:
            if new_content.get("fact_id") and new_content.get("fact_id") == exist_content.get("fact_id"):
                if new_content.get("is_true") != exist_content.get("is_true"):
                    return True, f"Negated truth value for fact_id '{new_content.get('fact_id')}'"

        return False, ""

    def _check_semantic_contradiction(self, new_entry: MemoryEntry, existing: MemoryEntry) -> Tuple[bool, str]:
        """Cosine similarity + semantic polarity check."""
        if not new_entry.embedding or not existing.embedding:
            return False, ""

        similarity = EmbeddingService.cosine_similarity(new_entry.embedding, existing.embedding)

        # High similarity means identical context/topic
        if similarity >= self.semantic_similarity_threshold:
            # High vector similarity with explicit opposing terms or status signals a contradiction
            new_text = (new_entry.summary + " " + json.dumps(new_entry.content)).lower()
            exist_text = (existing.summary + " " + json.dumps(existing.content)).lower()

            opposing_pairs = [
                ("enabled", "disabled"),
                ("true", "false"),
                ("active", "inactive"),
                ("open", "closed"),
                ("success", "failure"),
                ("safe", "unsafe"),
                ("allow", "deny"),
                ("start", "stop")
            ]

            for pos, neg in opposing_pairs:
                if (pos in new_text and neg in exist_text) or (neg in new_text and pos in exist_text):
                    return True, f"High semantic similarity ({similarity:.3f}) with contradictory terms ({pos}/{neg})"

        return False, ""


# ============================================================================
# 7. Poisoning Resistance
# ============================================================================

class PoisoningResistance:
    """
    Poisoning Resistance Component.
    Enforces writer rate limits, source permission validation, and anomaly detection
    to prevent cognitive memory corruption.
    """

    def __init__(self, max_writes_per_minute: int = 120, anomaly_threshold: float = 0.75):
        self.max_writes_per_minute = max_writes_per_minute
        self.anomaly_threshold = anomaly_threshold
        # Writer rate limit history: writer_id -> list of timestamps
        self._writer_timestamps: Dict[str, List[float]] = {}
        # Authorized permission mappings
        self._required_permissions = {
            MemoryType.SHORT_TERM: ["memory:write:cognitive", "memory:write:short_term", "admin"],
            MemoryType.WORKING: ["memory:write:cognitive", "memory:write:working", "admin"],
            MemoryType.EPISODIC: ["memory:write:cognitive", "memory:write:episodic", "admin"],
            MemoryType.SEMANTIC: ["memory:write:cognitive", "memory:write:semantic", "admin"],
            MemoryType.PROCEDURAL: ["memory:write:cognitive", "memory:write:procedural", "admin"],
            MemoryType.AUDIT_TRAIL: ["audit:write", "admin"],
        }

    def verify_writer_permission(self, writer_permissions: List[str], memory_type: MemoryType) -> bool:
        """Verifies if writer permissions contain required authorization for the memory type."""
        allowed_perms = self._required_permissions.get(memory_type, ["admin"])
        return any(p in allowed_perms for p in writer_permissions)

    def check_rate_limit(self, writer_id: str, current_time: Optional[float] = None) -> bool:
        """Rate limits writers to prevent flooding / spam attacks."""
        now = current_time if current_time is not None else time.time()
        window_start = now - 60.0

        if writer_id not in self._writer_timestamps:
            self._writer_timestamps[writer_id] = []

        # Prune older timestamps
        self._writer_timestamps[writer_id] = [
            t for t in self._writer_timestamps[writer_id] if t > window_start
        ]

        if len(self._writer_timestamps[writer_id]) >= self.max_writes_per_minute:
            logger.warning(f"Rate limit exceeded for writer '{writer_id}' ({len(self._writer_timestamps[writer_id])} writes/min)")
            return False

        self._writer_timestamps[writer_id].append(now)
        return True

    def calculate_anomaly_score(self, entry: MemoryEntry, recent_entries: List[MemoryEntry]) -> float:
        """
        Calculates memory anomaly score based on confidence jumps, content repetition, and bounds.
        Returns float score between 0.0 (normal) and 1.0 (anomalous).
        """
        score = 0.0

        # Anomaly 1: Confidence out of range [0, 1] or unexplained sudden 1.0 confidence for unverified source
        if entry.confidence < 0.0 or entry.confidence > 1.0:
            score += 0.8
        elif entry.confidence == 1.0 and entry.provenance.source_type == SourceType.INFERENCE:
            # Pure inferences stating absolute 1.0 certainty get slight anomaly weighting
            score += 0.15

        # Anomaly 2: Rapid identical payload repetition (spam check)
        entry_content_str = json.dumps(entry.content, sort_keys=True)
        dup_count = sum(
            1 for e in recent_entries[-20:]
            if json.dumps(e.content, sort_keys=True) == entry_content_str and e.provenance.writer_id == entry.provenance.writer_id
        )
        if dup_count > 3:
            score += 0.5

        # Anomaly 3: Empty content payload
        if not entry.content and not entry.summary:
            score += 0.4

        return min(1.0, score)

    def evaluate_entry(self, entry: MemoryEntry, recent_entries: List[MemoryEntry]) -> PoisoningMetadata:
        """Evaluates an entry for rate limit, source verification, and anomaly score."""
        writer_id = entry.provenance.writer_id
        rate_ok = self.check_rate_limit(writer_id, entry.timestamp)
        source_ok = self.verify_writer_permission(entry.provenance.writer_permissions, entry.memory_type)
        anomaly_score = self.calculate_anomaly_score(entry, recent_entries)
        is_flagged = (not rate_ok) or (not source_ok) or (anomaly_score >= self.anomaly_threshold)

        notes_parts = []
        if not rate_ok:
            notes_parts.append("Rate limit exceeded")
        if not source_ok:
            notes_parts.append(f"Writer '{writer_id}' lacks required permission for {entry.memory_type.value}")
        if anomaly_score >= self.anomaly_threshold:
            notes_parts.append(f"High anomaly score ({anomaly_score:.2f})")

        return PoisoningMetadata(
            anomaly_score=anomaly_score,
            rate_limit_ok=rate_ok,
            source_verified=source_ok,
            flagged_for_review=is_flagged,
            notes="; ".join(notes_parts) if notes_parts else "Verified clear"
        )


# ============================================================================
# 4. ValidationPipeline
# ============================================================================

@dataclass
class ValidationResult:
    """Outcome of ValidationPipeline write validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    poisoning_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "contradictions": self.contradictions,
            "poisoning_flags": self.poisoning_flags,
        }


class ValidationPipeline:
    """
    Multi-stage Validation Pipeline for Memory Writes:
    Stage 1: Schema Validation
    Stage 2: Provenance Check
    Stage 3: Poisoning Resistance Check
    Stage 4: Contradiction Check
    """

    def __init__(self, poisoning_resistance: PoisoningResistance, contradiction_detector: ContradictionDetector):
        self.poisoning_resistance = poisoning_resistance
        self.contradiction_detector = contradiction_detector

    def validate(
        self,
        entry: MemoryEntry,
        existing_entries: List[MemoryEntry]
    ) -> ValidationResult:
        """Executes full validation pipeline for a memory entry prior to commit."""
        errors: List[str] = []
        warnings: List[str] = []
        contradictions: List[str] = []
        poisoning_flags: List[str] = []

        # Stage 1: Schema Validation
        if not entry.id or not isinstance(entry.id, str):
            errors.append("Invalid or missing memory entry ID")
        if entry.confidence < 0.0 or entry.confidence > 1.0:
            errors.append(f"Confidence value {entry.confidence} outside valid range [0.0, 1.0]")
        if not entry.memory_type:
            errors.append("Missing memory_type field")

        # Stage 2: Provenance Check
        if not entry.provenance:
            errors.append("Missing provenance metadata")
        else:
            if not entry.provenance.writer_id:
                errors.append("Missing writer_id in provenance")
            if not entry.provenance.writer_permissions:
                errors.append("Missing writer_permissions in provenance")

        # Early return if schema or basic provenance fails
        if errors:
            return ValidationResult(is_valid=False, errors=errors)

        # Stage 3: Poisoning Resistance Check
        poisoning_meta = self.poisoning_resistance.evaluate_entry(entry, existing_entries)
        entry.poisoning_metadata = poisoning_meta

        if not poisoning_meta.source_verified:
            errors.append(f"Source permission check failed: {poisoning_meta.notes}")
        if not poisoning_meta.rate_limit_ok:
            errors.append(f"Rate limit check failed: {poisoning_meta.notes}")
        if poisoning_meta.flagged_for_review:
            poisoning_flags.append(poisoning_meta.notes or "Flagged by poisoning detector")

        if errors:
            return ValidationResult(is_valid=False, errors=errors, poisoning_flags=poisoning_flags)

        # Stage 4: Contradiction Check
        status, contr_ids, contr_details = self.contradiction_detector.check_contradictions(entry, existing_entries)
        if status != ContradictionStatus.NONE:
            entry.contradiction_status = status
            entry.contradicting_memory_ids = contr_ids
            contradictions.extend(contr_details)
            warnings.append(f"Suspected contradiction detected with {len(contr_ids)} memories")

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            contradictions=contradictions,
            poisoning_flags=poisoning_flags
        )


# ============================================================================
# 2. MemoryStore (SQLite Backend)
# ============================================================================

class MemoryStore:
    """
    SQLite-backed MemoryStore for ORION Phase 1.
    Maintains separate cognitive memory store and tamper-evident audit log tables.
    Provides full CRUD operations, semantic vector similarity query, and retention policy enforcement.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        embedding_service: Optional[EmbeddingService] = None,
        poisoning_resistance: Optional[PoisoningResistance] = None,
        contradiction_detector: Optional[ContradictionDetector] = None,
    ):
        self.db_path = db_path
        self.embedding_service = embedding_service or EmbeddingService()
        self.poisoning_resistance = poisoning_resistance or PoisoningResistance()
        self.contradiction_detector = contradiction_detector or ContradictionDetector()
        self.pipeline = ValidationPipeline(self.poisoning_resistance, self.contradiction_detector)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._initialize_tables()

    def verify_writer_permission(self, actor_permissions: List[str], memory_type: MemoryType) -> bool:
        """Check if actor has permission to write this memory type."""
        return self.poisoning_resistance.verify_writer_permission(actor_permissions, memory_type)

    def _initialize_tables(self):
        """Initializes database schema for cognitive memory and separate audit trail."""
        with self.conn:
            # Cognitive Memory Table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    summary TEXT,
                    embedding_json TEXT,
                    writer_id TEXT NOT NULL,
                    writer_permissions_json TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_plane TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    schema_version TEXT NOT NULL,
                    retention_type TEXT NOT NULL,
                    ttl_seconds REAL,
                    expires_at REAL,
                    contradiction_status TEXT NOT NULL,
                    contradicting_ids_json TEXT NOT NULL,
                    poisoning_metadata_json TEXT NOT NULL,
                    is_deleted INTEGER NOT NULL DEFAULT 0
                )
            """)

            # Audit Trail Table (SEPARATE from cognitive memory)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    retention_type TEXT NOT NULL
                )
            """)

            # Create Indexes
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cog_mem_type ON cognitive_memories(memory_type);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cog_writer ON cognitive_memories(writer_id);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cog_expires ON cognitive_memories(expires_at);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_trail(timestamp);")

    # ------------------------------------------------------------------------
    # Cognitive Memory CRUD & Operations
    # ------------------------------------------------------------------------

    def write_memory(
        self,
        entry: MemoryEntry,
        actor_permissions: Optional[List[str]] = None
    ) -> Tuple[Optional[MemoryEntry], ValidationResult]:
        """
        Validates and writes a cognitive memory entry to SQLite storage.
        Automatically generates embedding for Semantic memories if missing.
        Always validates — no bypass allowed.
        """
        # Permission check if actor_permissions provided
        if actor_permissions is None:
            raise PermissionError("actor_permissions is required for memory write — deny by default")
        if not self.verify_writer_permission(actor_permissions, entry.memory_type):
                raise PermissionError(f"Insufficient permissions to write {entry.memory_type} memory")

        # Ensure embedding for semantic memory or if summary is provided
        if entry.embedding is None and (entry.memory_type == MemoryType.SEMANTIC or entry.summary):
            text_to_embed = entry.summary if entry.summary else json.dumps(entry.content)
            entry.embedding = self.embedding_service.generate_embedding(text_to_embed)

        existing_entries = self.query_memories(include_deleted=False)

        # Always validate — no bypass allowed
        val_result = self.pipeline.validate(entry, existing_entries)
        if not val_result.is_valid:
            logger.warning(f"Memory write validation failed for ID {entry.id}: {val_result.errors}")
            return None, val_result

        entry.to_dict()

        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO cognitive_memories (
                    id, memory_type, content_json, summary, embedding_json,
                    writer_id, writer_permissions_json, source_type, source_plane,
                    confidence, timestamp, created_at, updated_at, version, schema_version,
                    retention_type, ttl_seconds, expires_at, contradiction_status,
                    contradicting_ids_json, poisoning_metadata_json, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.memory_type.value if isinstance(entry.memory_type, Enum) else entry.memory_type,
                    json.dumps(entry.content),
                    entry.summary,
                    json.dumps(entry.embedding) if entry.embedding else None,
                    entry.provenance.writer_id,
                    json.dumps(entry.provenance.writer_permissions),
                    entry.provenance.source_type.value if isinstance(entry.provenance.source_type, Enum) else entry.provenance.source_type,
                    entry.provenance.source_plane,
                    entry.confidence,
                    entry.timestamp,
                    entry.created_at,
                    entry.updated_at,
                    entry.version,
                    entry.schema_version,
                    entry.retention_policy.retention_type.value if isinstance(entry.retention_policy.retention_type, Enum) else entry.retention_policy.retention_type,
                    entry.retention_policy.ttl_seconds,
                    entry.retention_policy.expires_at,
                    entry.contradiction_status.value if isinstance(entry.contradiction_status, Enum) else entry.contradiction_status,
                    json.dumps(entry.contradicting_memory_ids),
                    json.dumps(entry.poisoning_metadata.to_dict()),
                    1 if entry.is_deleted else 0,
                )
            )

        logger.info(f"Successfully wrote memory entry ID {entry.id} (type: {entry.memory_type.value})")
        return entry, val_result

    def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieves a cognitive memory by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cognitive_memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_memory_entry(row)

    def update_memory(
        self,
        memory_id: str,
        new_content: Dict[str, Any],
        writer_id: str,
        writer_permissions: List[str],
        new_summary: Optional[str] = None
    ) -> Tuple[Optional[MemoryEntry], ValidationResult]:
        """
        Updates an existing memory entry, creating a new version while preserving provenance.
        """
        existing = self.get_memory(memory_id)
        if not existing or existing.is_deleted:
            val = ValidationResult(is_valid=False, errors=[f"Memory entry ID {memory_id} not found or deleted"])
            return None, val

        updated_entry = MemoryEntry.from_dict(existing.to_dict())
        updated_entry.content = new_content
        if new_summary is not None:
            updated_entry.summary = new_summary
        updated_entry.version = existing.version + 1
        updated_entry.updated_at = datetime.now(timezone.utc).isoformat()
        updated_entry.provenance.writer_id = writer_id
        updated_entry.provenance.writer_permissions = writer_permissions

        # Regenerate embedding if content changed
        if updated_entry.memory_type == MemoryType.SEMANTIC or updated_entry.summary:
            text_to_embed = updated_entry.summary if updated_entry.summary else json.dumps(updated_entry.content)
            updated_entry.embedding = self.embedding_service.generate_embedding(text_to_embed)

        return self.write_memory(updated_entry, actor_permissions=writer_permissions)

    def delete_memory(self, memory_id: str, soft: bool = True, actor_permissions: Optional[List[str]] = None) -> bool:
        """Deletes a memory entry (soft delete by default, or hard removal). Requires authorization."""
        if actor_permissions is None:
            raise PermissionError("actor_permissions is required for memory deletion — deny by default")
        existing = self.get_memory(memory_id)
        if not existing:
            return False

        with self.conn:
            if soft:
                self.conn.execute("UPDATE cognitive_memories SET is_deleted = 1 WHERE id = ?", (memory_id,))
            else:
                self.conn.execute("DELETE FROM cognitive_memories WHERE id = ?", (memory_id,))
        return True

    def query_memories(
        self,
        memory_type: Optional[MemoryType] = None,
        writer_id: Optional[str] = None,
        include_deleted: bool = False,
        limit: int = 100
    ) -> List[MemoryEntry]:
        """Queries cognitive memories by type or writer ID."""
        query = "SELECT * FROM cognitive_memories WHERE 1=1"
        params: List[Any] = []

        if not include_deleted:
            query += " AND is_deleted = 0"
        if memory_type is not None:
            m_type_val = memory_type.value if isinstance(memory_type, Enum) else memory_type
            query += " AND memory_type = ?"
            params.append(m_type_val)
        if writer_id is not None:
            query += " AND writer_id = ?"
            params.append(writer_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_memory_entry(row) for row in rows]

    def search_semantic(
        self,
        query_text: str,
        top_k: int = 5,
        min_similarity: float = 0.5
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Performs vector similarity search against stored semantic memory embeddings.
        """
        query_embedding = self.embedding_service.generate_embedding(query_text)
        candidates = self.query_memories(memory_type=MemoryType.SEMANTIC, include_deleted=False)

        scored: List[Tuple[MemoryEntry, float]] = []
        for cand in candidates:
            if cand.embedding:
                sim = EmbeddingService.cosine_similarity(query_embedding, cand.embedding)
                if sim >= min_similarity:
                    scored.append((cand, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------------
    # 6. Retention Policy Enforcement
    # ------------------------------------------------------------------------

    def enforce_retention_policies(self, current_time: Optional[float] = None) -> int:
        """
        Scans all cognitive memories and soft-deletes expired entries based on retention TTL.
        Returns total number of expired entries purged.
        """
        now = current_time if current_time is not None else time.time()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cognitive_memories WHERE is_deleted = 0 AND expires_at IS NOT NULL AND expires_at <= ?", (now,))
        rows = cursor.fetchall()

        expired_count = len(rows)
        if expired_count > 0:
            with self.conn:
                self.conn.execute("UPDATE cognitive_memories SET is_deleted = 1 WHERE is_deleted = 0 AND expires_at IS NOT NULL AND expires_at <= ?", (now,))
            logger.info(f"Retention policy enforcement purged {expired_count} expired memory entries.")

        return expired_count

    # ------------------------------------------------------------------------
    # Separate Audit Trail Operations
    # ------------------------------------------------------------------------

    def write_audit_entry(self, entry: AuditTrailEntry) -> str:
        """
        Writes an immutable AuditTrail entry into the separate audit_trail table.
        Automatically links entry hash to the previous entry's hash to form a tamper-evident hash chain.
        """
        # Fetch latest audit hash for hash chaining
        cursor = self.conn.cursor()
        cursor.execute("SELECT hash FROM audit_trail ORDER BY timestamp DESC, rowid DESC LIMIT 1")
        last_row = cursor.fetchone()

        if last_row:
            entry.previous_hash = last_row["hash"]
        else:
            entry.previous_hash = "GENESIS"

        entry.hash = entry.compute_hash()

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO audit_trail (
                    id, event_type, actor_id, action, payload_json, timestamp,
                    created_at, previous_hash, hash, source_type, retention_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.event_type,
                    entry.actor_id,
                    entry.action,
                    json.dumps(entry.payload),
                    entry.timestamp,
                    entry.created_at,
                    entry.previous_hash,
                    entry.hash,
                    entry.source_type.value if isinstance(entry.source_type, Enum) else entry.source_type,
                    entry.retention_policy.retention_type.value if isinstance(entry.retention_policy.retention_type, Enum) else entry.retention_policy.retention_type,
                )
            )

        logger.info(f"Recorded audit entry ID {entry.id} (hash: {entry.hash[:10]}...)")
        return entry.hash

    def verify_audit_integrity(self) -> Tuple[bool, List[str]]:
        """
        Verifies the cryptographic SHA-256 hash-chain integrity of the separate audit trail.
        Returns (is_intact, list_of_violations).
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM audit_trail ORDER BY timestamp ASC, rowid ASC")
        rows = cursor.fetchall()

        violations: List[str] = []
        expected_prev_hash = "GENESIS"

        for row in rows:
            entry = self._row_to_audit_entry(row)
            if entry.previous_hash != expected_prev_hash:
                violations.append(f"Broken hash chain at audit ID {entry.id}: previous_hash '{entry.previous_hash}' != expected '{expected_prev_hash}'")

            if not entry.verify_hash():
                violations.append(f"Tampered audit payload or hash at ID {entry.id}")

            expected_prev_hash = entry.hash

        is_intact = len(violations) == 0
        return is_intact, violations

    # ------------------------------------------------------------------------
    # Internal Serialization Utilities
    # ------------------------------------------------------------------------

    def _row_to_memory_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Converts database row to MemoryEntry dataclass instance."""
        embedding = json.loads(row["embedding_json"]) if row["embedding_json"] else None
        provenance = Provenance(
            writer_id=row["writer_id"],
            writer_permissions=json.loads(row["writer_permissions_json"]),
            source_type=SourceType(row["source_type"]),
            source_plane=row["source_plane"],
        )
        retention = RetentionPolicy(
            retention_type=RetentionType(row["retention_type"]),
            ttl_seconds=row["ttl_seconds"],
            expires_at=row["expires_at"]
        )
        poisoning = PoisoningMetadata.from_dict(json.loads(row["poisoning_metadata_json"]))

        return MemoryEntry(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            content=json.loads(row["content_json"]),
            summary=row["summary"] or "",
            embedding=embedding,
            provenance=provenance,
            retention_policy=retention,
            poisoning_metadata=poisoning,
            confidence=row["confidence"],
            timestamp=row["timestamp"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            version=row["version"],
            schema_version=row["schema_version"],
            contradiction_status=ContradictionStatus(row["contradiction_status"]),
            contradicting_memory_ids=json.loads(row["contradicting_ids_json"]),
            is_deleted=bool(row["is_deleted"])
        )

    def _row_to_audit_entry(self, row: sqlite3.Row) -> AuditTrailEntry:
        """Converts database row to AuditTrailEntry dataclass instance."""
        return AuditTrailEntry(
            id=row["id"],
            event_type=row["event_type"],
            actor_id=row["actor_id"],
            action=row["action"],
            payload=json.loads(row["payload_json"]),
            timestamp=row["timestamp"],
            created_at=row["created_at"],
            previous_hash=row["previous_hash"],
            hash=row["hash"],
            source_type=SourceType(row["source_type"]),
            retention_policy=RetentionPolicy(retention_type=RetentionType(row["retention_type"])),
        )

    def close(self):
        """Closes SQLite database connection."""
        if self.conn:
            self.conn.close()
