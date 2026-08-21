"""
ORION Physical Intelligence OS - Phase 1 Simulation
Audit Subsystem (v0.5 Architecture Compliance)

This module provides an immutable, append-only, tamper-evident audit logging system
for safety-relevant physical simulation events, decisions, and system state transitions.

Key Architecture Requirements Implemented:
- Immutable audit log (append-only, tamper-evident via SHA-256 hash chaining).
- AuditEvent contract matching v0.5 spec: event_id, timestamp, event_type, actor,
  action, target, outcome, risk_tier, safety_decision, state_revision, schema_version,
  contract_version, producer, consumer, correlation_id, signature, previous_hash, hash.
- Rollback on storage failure: if an audit write fails, actions are treated as unexecuted
  and rolled back via user-provided rollback callbacks.
- Cognitive memory isolation: explicit guard preventing raw audit events from polluting
  cognitive memory (poisoning risk).
- Replay functionality: sequential replay from timestamp, event ID, or index.
- Verification: full chain tamper detection and signature validation.
- Query interface: filter by event_type, actor, risk_tier, safety_decision, time range, etc.
- Export/Import: JSON serialization for external regulatory auditing and verification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

logger = logging.getLogger("orion.audit")

T = TypeVar("T")

# Genesis hash for the initial event in the audit chain (64 hex zeros for SHA-256)
GENESIS_HASH: str = "0" * 64


class EventType(str, Enum):
    """Standard audit event types as specified in ORION v0.5 architecture."""
    DECISION = "decision"
    ACTION = "action"
    STATE_TRANSITION = "state_transition"
    CONFIG_CHANGE = "config_change"
    SECURITY = "security"
    SAFETY = "safety"
    ERROR = "error"


class RiskTier(str, Enum):
    """Safety risk classification tiers."""
    TIER_0 = "TIER_0"  # Informational / zero risk
    TIER_1 = "TIER_1"  # Low risk
    TIER_2 = "TIER_2"  # Medium risk
    TIER_3 = "TIER_3"  # High risk
    TIER_4 = "TIER_4"  # Critical risk / E-stop


class SafetyDecision(str, Enum):
    """Safety assurance decision outcomes."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"
    PENDING = "PENDING"


class Outcome(str, Enum):
    """Event execution outcome status."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"
    PENDING = "PENDING"


class AuditError(Exception):
    """Base exception for all ORION Audit System errors."""
    pass


class AuditStorageError(AuditError):
    """Raised when writing to or reading from audit storage fails."""
    pass


class AuditTamperedError(AuditError):
    """Raised when tamper detection identifies a broken hash chain or signature mismatch."""
    pass


class AuditRollbackError(AuditError):
    """Raised when an action is rolled back due to an audit storage write failure."""
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class AuditMemoryPoisoningError(AuditError):
    """Raised when raw audit data is illegitimately transferred directly to cognitive memory."""
    pass


@dataclass
class AuditEvent:
    """
    AuditEvent contract specification matching ORION v0.5 Architecture B.8.

    Represents an immutable record of a safety-relevant decision, action,
    or state change within ORION.
    """
    event_id: str
    timestamp: float
    event_type: str
    actor: str
    action: str
    target: str
    outcome: str
    risk_tier: str
    safety_decision: str
    state_revision: Union[int, str]
    schema_version: str = "1.0.0"
    contract_version: str = "1.0.0"
    producer: str = "ORION-AuditPlane"
    consumer: str = "ORION-AuditStore"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signature: str = ""
    previous_hash: str = GENESIS_HASH
    hash: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if self.timestamp <= 0:
            self.timestamp = time.time()

    def get_canonical_dict(self) -> Dict[str, Any]:
        """
        Returns a deterministic dictionary representation of content fields
        for cryptographic hash computation (excluding hash itself).
        """
        return {
            "action": self.action,
            "actor": self.actor,
            "consumer": self.consumer,
            "contract_version": self.contract_version,
            "correlation_id": self.correlation_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "outcome": self.outcome,
            "payload": self.payload,
            "previous_hash": self.previous_hash,
            "producer": self.producer,
            "risk_tier": self.risk_tier,
            "safety_decision": self.safety_decision,
            "schema_version": self.schema_version,
            "state_revision": str(self.state_revision),
            "target": self.target,
            "timestamp": f"{self.timestamp:.6f}",
        }

    def calculate_hash(self) -> str:
        """Computes SHA-256 hash over canonical event content fields."""
        canonical = self.get_canonical_dict()
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def sign_event(self, secret_key: str) -> str:
        """
        Computes the event hash and signs it using HMAC-SHA256.
        Sets self.hash and self.signature.
        """
        self.hash = self.calculate_hash()
        sig = hmac.new(
            secret_key.encode("utf-8"),
            self.hash.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        self.signature = sig
        return sig

    def verify_signature(self, secret_key: str) -> bool:
        """Verifies HMAC-SHA256 signature against current event hash."""
        if not self.signature or not self.hash:
            return False
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            self.hash.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(self.signature, expected_sig)

    def to_dict(self) -> Dict[str, Any]:
        """Converts AuditEvent to dictionary format."""
        d = asdict(self)
        d["timestamp"] = float(self.timestamp)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AuditEvent:
        """Constructs AuditEvent from a dictionary."""
        return cls(
            event_id=str(data.get("event_id", "")),
            timestamp=float(data.get("timestamp", time.time())),
            event_type=str(data.get("event_type", EventType.DECISION.value)),
            actor=str(data.get("actor", "system")),
            action=str(data.get("action", "unknown")),
            target=str(data.get("target", "system")),
            outcome=str(data.get("outcome", Outcome.SUCCESS.value)),
            risk_tier=str(data.get("risk_tier", RiskTier.TIER_0.value)),
            safety_decision=str(data.get("safety_decision", SafetyDecision.APPROVED.value)),
            state_revision=data.get("state_revision", 0),
            schema_version=str(data.get("schema_version", "1.0.0")),
            contract_version=str(data.get("contract_version", "1.0.0")),
            producer=str(data.get("producer", "ORION-AuditPlane")),
            consumer=str(data.get("consumer", "ORION-AuditStore")),
            correlation_id=str(data.get("correlation_id", "")),
            signature=str(data.get("signature", "")),
            previous_hash=str(data.get("previous_hash", GENESIS_HASH)),
            hash=str(data.get("hash", "")),
            payload=dict(data.get("payload", {})),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> AuditEvent:
        return cls.from_dict(json.loads(json_str))


@dataclass
class VerificationResult:
    """Result of audit chain tamper detection verification."""
    is_valid: bool
    total_events: int
    verified_events: int
    first_broken_index: Optional[int] = None
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.is_valid:
            return f"VERIFICATION PASSED: All {self.total_events} events intact and valid."
        return (
            f"VERIFICATION FAILED: {len(self.errors)} error(s) detected. "
            f"First failure at index {self.first_broken_index}. Details: {self.errors[:3]}"
        )


class BaseStorageBackend:
    """Abstract interface for audit log storage backends."""

    def append(self, event: AuditEvent) -> None:
        raise NotImplementedError

    def read_all(self) -> List[AuditEvent]:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


class InMemoryStorageBackend(BaseStorageBackend):
    """In-memory audit storage backend with failure simulation capabilities."""

    def __init__(self) -> None:
        self._events: List[AuditEvent] = []
        self.simulate_failure: bool = False

    def append(self, event: AuditEvent) -> None:
        if self.simulate_failure:
            raise AuditStorageError("Simulated storage write failure in InMemoryStorageBackend")
        self._events.append(event)

    def read_all(self) -> List[AuditEvent]:
        import copy
        return [copy.deepcopy(e) for e in self._events]

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        """Audit events are immutable — clearing is rejected."""
        raise PermissionError("Audit events are immutable — clear not permitted")


class FileStorageBackend(BaseStorageBackend):
    """
    Persistent file storage backend using JSON Lines (.jsonl).
    Forces immediate flushing and fsync to guarantee append-only durability.
    """

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.simulate_failure: bool = False

    def append(self, event: AuditEvent) -> None:
        if self.simulate_failure:
            raise AuditStorageError("Simulated storage write failure in FileStorageBackend")
        try:
            line = json.dumps(event.to_dict(), separators=(",", ":")) + "\n"
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            raise AuditStorageError(f"Failed to append AuditEvent to file {self.file_path}: {e}") from e

    def read_all(self) -> List[AuditEvent]:
        if not self.file_path.exists():
            return []
        events: List[AuditEvent] = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        events.append(AuditEvent.from_dict(data))
        except Exception as e:
            raise AuditStorageError(f"Failed to read AuditEvents from file {self.file_path}: {e}") from e
        return events

    def count(self) -> int:
        return len(self.read_all())

    def clear(self) -> None:
        if self.file_path.exists():
            self.file_path.unlink()


class AuditLog:
    """
    Append-only, tamper-evident audit log for Project ORION Phase 1.

    Manages event hash chaining, signature verification, storage persistence,
    rollback handling on write failure, replay capabilities, query interface,
    and JSON exports.
    """

    def __init__(
        self,
        storage: Optional[BaseStorageBackend] = None,
        storage_path: Optional[Union[str, Path]] = None,
        hmac_secret: Optional[str] = None,
    ) -> None:
        if storage is not None:
            self._storage = storage
        elif storage_path is not None:
            self._storage = FileStorageBackend(storage_path)
        else:
            self._storage = InMemoryStorageBackend()

        self._hmac_secret = hmac_secret
        self._cache: List[AuditEvent] = []
        self._load_existing_events()

    def _load_existing_events(self) -> None:
        try:
            self._cache = self._storage.read_all()
        except Exception as e:
            logger.error("Failed to load existing audit log events: %s", e)
            self._cache = []

    @property
    def head_hash(self) -> str:
        """Returns the hash of the latest logged event, or GENESIS_HASH if empty."""
        if self._cache:
            return self._cache[-1].hash
        return GENESIS_HASH

    @property
    def count(self) -> int:
        """Returns total number of logged events."""
        return len(self._cache)

    def get_events(self) -> List[AuditEvent]:
        """Returns deep copies of all logged events in cache (immutable records)."""
        import copy
        return [copy.deepcopy(e) for e in self._cache]

    def create_event(
        self,
        event_type: Union[EventType, str],
        actor: str,
        action: str,
        target: str,
        outcome: Union[Outcome, str] = Outcome.SUCCESS,
        risk_tier: Union[RiskTier, str] = RiskTier.TIER_0,
        safety_decision: Union[SafetyDecision, str] = SafetyDecision.APPROVED,
        state_revision: Union[int, str] = 0,
        correlation_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> AuditEvent:
        """Factory method to construct an AuditEvent instance."""
        ev_type_val = event_type.value if isinstance(event_type, EventType) else str(event_type)
        outcome_val = outcome.value if isinstance(outcome, Outcome) else str(outcome)
        risk_val = risk_tier.value if isinstance(risk_tier, RiskTier) else str(risk_tier)
        safety_val = safety_decision.value if isinstance(safety_decision, SafetyDecision) else str(safety_decision)

        return AuditEvent(
            event_id=event_id or str(uuid.uuid4()),
            timestamp=timestamp or time.time(),
            event_type=ev_type_val,
            actor=actor,
            action=action,
            target=target,
            outcome=outcome_val,
            risk_tier=risk_val,
            safety_decision=safety_val,
            state_revision=state_revision,
            correlation_id=correlation_id or str(uuid.uuid4()),
            payload=payload or {},
        )

    def append_event(self, event: AuditEvent) -> AuditEvent:
        """
        Appends an event to the audit log with hash chaining and HMAC signing.

        If storage write fails, raises AuditStorageError and ensures the log cache
        state remains unpolluted.

        Args:
            event: AuditEvent to write.

        Returns:
            The written AuditEvent with completed hash and signature fields.

        Raises:
            AuditStorageError: If storage write fails.
        """
        # Set hash chain link from latest head
        event.previous_hash = self.head_hash

        # Compute hash and signature
        if self._hmac_secret:
            event.sign_event(self._hmac_secret)
        else:
            event.hash = event.calculate_hash()

        # Write to storage backend
        try:
            self._storage.append(event)
        except Exception as e:
            logger.critical("Audit log storage write failed! Event ID: %s. Error: %s", event.event_id, e)
            raise AuditStorageError(f"Storage write failed for AuditEvent {event.event_id}: {e}") from e

        # Append to in-memory cache only after storage succeeds
        self._cache.append(event)
        logger.debug("Successfully logged AuditEvent %s [hash: %s...]", event.event_id, event.hash[:8])
        return event

    def execute_audited_action(
        self,
        action_fn: Callable[[], T],
        rollback_fn: Callable[[], None],
        event_type: Union[EventType, str],
        actor: str,
        action: str,
        target: str,
        risk_tier: Union[RiskTier, str] = RiskTier.TIER_0,
        safety_decision: Union[SafetyDecision, str] = SafetyDecision.APPROVED,
        state_revision: Union[int, str] = 0,
        correlation_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Executes an action within a transactional audit boundary.

        Requirements:
        If storage write fails, the action MUST be treated as unexecuted and rolled back
        via rollback_fn.

        Returns:
            The return value of action_fn if both action and audit logging succeed.

        Raises:
            AuditRollbackError: If storage write fails, triggering rollback.
            Exception: If action_fn raises an exception, also invoking rollback.
        """
        # 1. Execute action
        # Change #12: When an exception occurs during action execution, we MUST
        # record a FAILED audit event BEFORE re-raising. Previously, the exception
        # escaped without any audit trail — the failure was invisible in the log.
        try:
            result = action_fn()
        except Exception as act_err:
            logger.error("Action execution failed prior to audit log: %s", act_err)
            try:
                rollback_fn()
            except Exception as rb_err:
                logger.critical("Rollback failed after action error: %s", rb_err)
            # Record the failure in the audit log before re-raising
            try:
                fail_event = self.create_event(
                    event_type=event_type,
                    actor=actor,
                    action=action,
                    target=target,
                    outcome=Outcome.FAILED,
                    risk_tier=risk_tier,
                    safety_decision=SafetyDecision.REJECTED,
                    state_revision=state_revision,
                    correlation_id=correlation_id,
                    payload={**(payload or {}), "error": str(act_err), "rolled_back": True},
                )
                self.append_event(fail_event)
            except Exception as audit_err:
                logger.critical(
                    "Failed to log FAILED audit event for action '%s': %s", action, audit_err
                )
            raise act_err

        # 2. Build audit event
        event = self.create_event(
            event_type=event_type,
            actor=actor,
            action=action,
            target=target,
            outcome=Outcome.SUCCESS,
            risk_tier=risk_tier,
            safety_decision=safety_decision,
            state_revision=state_revision,
            correlation_id=correlation_id,
            payload=payload,
        )

        # 3. Attempt to write to audit log
        try:
            self.append_event(event)
        except AuditStorageError as storage_err:
            logger.error("Audit write failed after action execution! Executing rollback...")
            try:
                rollback_fn()
            except Exception as rb_err:
                logger.critical("Rollback error after audit storage failure: %s", rb_err)
            raise AuditRollbackError(
                f"Action '{action}' rolled back due to audit storage failure: {storage_err}",
                original_error=storage_err
            ) from storage_err

        return result

    def verify_chain_integrity(self, secret_key: Optional[str] = None) -> VerificationResult:
        """
        Verifies the tamper-evident integrity of the entire audit chain.

        Checks:
        1. Genesis event previous_hash == GENESIS_HASH.
        2. Sequential chain links (event[i].previous_hash == event[i-1].hash).
        3. Event internal SHA-256 hash recalculation match.
        4. Optional HMAC signature verification.

        Returns:
            VerificationResult detailing validation status and any integrity failures.
        """
        key_to_use = secret_key or self._hmac_secret
        events = self._storage.read_all()
        total = len(events)
        if total == 0:
            return VerificationResult(is_valid=True, total_events=0, verified_events=0)

        errors: List[str] = []
        first_broken: Optional[int] = None

        for idx, event in enumerate(events):
            # Check 1 & 2: Chain continuity
            if idx == 0:
                if event.previous_hash != GENESIS_HASH:
                    err = f"Index 0: Expected genesis previous_hash '{GENESIS_HASH}', got '{event.previous_hash}'"
                    errors.append(err)
                    if first_broken is None:
                        first_broken = 0
            else:
                prev_hash = events[idx - 1].hash
                if event.previous_hash != prev_hash:
                    err = (
                        f"Index {idx} ({event.event_id}): Broken chain link. "
                        f"Previous event hash '{prev_hash}', event points to '{event.previous_hash}'"
                    )
                    errors.append(err)
                    if first_broken is None:
                        first_broken = idx

            # Check 3: Hash recalculation
            calc_hash = event.calculate_hash()
            if event.hash != calc_hash:
                err = (
                    f"Index {idx} ({event.event_id}): Tampered data detected! "
                    f"Stored hash '{event.hash}', calculated '{calc_hash}'"
                )
                errors.append(err)
                if first_broken is None:
                    first_broken = idx

            # Check 4: Signature verification
            if key_to_use and event.signature:
                if not event.verify_signature(key_to_use):
                    err = f"Index {idx} ({event.event_id}): Signature mismatch! HMAC verification failed."
                    errors.append(err)
                    if first_broken is None:
                        first_broken = idx

        is_valid = len(errors) == 0
        return VerificationResult(
            is_valid=is_valid,
            total_events=total,
            verified_events=total if is_valid else (first_broken or 0),
            first_broken_index=first_broken,
            errors=errors,
        )

    def replay_events(
        self,
        start_timestamp: Optional[float] = None,
        start_event_id: Optional[str] = None,
        start_index: Optional[int] = None,
        end_timestamp: Optional[float] = None,
        handler: Optional[Callable[[AuditEvent], None]] = None,
        verify_integrity: bool = True,
    ) -> Generator[AuditEvent, None, None]:
        """
        Replays log events sequentially from a specified starting point.

        Args:
            start_timestamp: Replay events with timestamp >= start_timestamp.
            start_event_id: Replay events starting from event matching this ID.
            start_index: Replay events starting from index offset.
            end_timestamp: Replay events up to timestamp <= end_timestamp.
            handler: Optional callback function invoked for each replayed event.
            verify_integrity: If True, verifies chain integrity before replay.

        Yields:
            AuditEvents in sequential order.

        Raises:
            AuditTamperedError: If chain integrity verification fails prior to replay.
        """
        if verify_integrity:
            verification = self.verify_chain_integrity()
            if not verification.is_valid:
                raise AuditTamperedError(f"Cannot replay tampered audit log: {verification.summary()}")

        events = self._storage.read_all()
        start_pos = 0

        if start_index is not None:
            start_pos = max(0, min(start_index, len(events)))
        elif start_event_id is not None:
            found = False
            for idx, ev in enumerate(events):
                if ev.event_id == start_event_id:
                    start_pos = idx
                    found = True
                    break
            if not found:
                logger.warning("start_event_id '%s' not found in log, starting replay from beginning", start_event_id)
        elif start_timestamp is not None:
            for idx, ev in enumerate(events):
                if ev.timestamp >= start_timestamp:
                    start_pos = idx
                    break

        for ev in events[start_pos:]:
            if end_timestamp is not None and ev.timestamp > end_timestamp:
                break
            if handler:
                handler(ev)
            yield ev

    def query(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        actor: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        risk_tier: Optional[Union[RiskTier, str]] = None,
        safety_decision: Optional[Union[SafetyDecision, str]] = None,
        outcome: Optional[Union[Outcome, str]] = None,
        target: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """
        Queries audit events by filtering on event criteria with offset and limit pagination.
        """
        events = self._storage.read_all()

        ev_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        risk_str = risk_tier.value if isinstance(risk_tier, RiskTier) else risk_tier
        safety_str = safety_decision.value if isinstance(safety_decision, SafetyDecision) else safety_decision
        outcome_str = outcome.value if isinstance(outcome, Outcome) else outcome

        filtered: List[AuditEvent] = []
        for ev in events:
            if ev_type_str and ev.event_type != ev_type_str:
                continue
            if actor and ev.actor != actor:
                continue
            if start_time is not None and ev.timestamp < start_time:
                continue
            if end_time is not None and ev.timestamp > end_time:
                continue
            if risk_str and ev.risk_tier != risk_str:
                continue
            if safety_str and ev.safety_decision != safety_str:
                continue
            if outcome_str and ev.outcome != outcome_str:
                continue
            if target and ev.target != target:
                continue
            if correlation_id and ev.correlation_id != correlation_id:
                continue
            filtered.append(ev)

        sliced = filtered[offset:]
        if limit is not None and limit >= 0:
            sliced = sliced[:limit]
        return sliced

    def export_to_json(
        self,
        file_path: Optional[Union[str, Path]] = None,
        verify_before_export: bool = True,
        indent: int = 2,
    ) -> str:
        """
        Exports the entire audit log to a JSON string or file for external verification.

        Includes chain verification metadata.
        """
        if verify_before_export:
            res = self.verify_chain_integrity()
            if not res.is_valid:
                raise AuditTamperedError(f"Refusing to export tampered audit log: {res.summary()}")

        events = self._storage.read_all()
        export_data = {
            "metadata": {
                "export_timestamp": time.time(),
                "total_events": len(events),
                "head_hash": self.head_hash,
                "genesis_hash": GENESIS_HASH,
                "verified": verify_before_export,
            },
            "events": [ev.to_dict() for ev in events],
        }

        json_str = json.dumps(export_data, indent=indent)

        if file_path:
            out_path = Path(file_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json_str, encoding="utf-8")

        return json_str

    @classmethod
    def import_from_json(
        cls,
        json_content_or_path: Union[str, Path],
        verify_imported: bool = True,
        secret_key: Optional[str] = None,
    ) -> Tuple[AuditLog, VerificationResult]:
        """
        Imports an audit log from exported JSON content or file, constructing a new AuditLog.

        Returns:
            Tuple of (AuditLog instance, VerificationResult).
        """
        path_obj = (
            Path(json_content_or_path)
            if isinstance(json_content_or_path, (str, Path)) and os.path.exists(str(json_content_or_path))
            else None
        )

        if path_obj:
            content = path_obj.read_text(encoding="utf-8")
        else:
            content = str(json_content_or_path)

        data = json.loads(content)
        raw_events = data.get("events", []) if isinstance(data, dict) and "events" in data else data

        backend = InMemoryStorageBackend()
        audit_log = cls(storage=backend, hmac_secret=secret_key)

        for item in raw_events:
            event = AuditEvent.from_dict(item)
            backend.append(event)
            audit_log._cache.append(event)

        verification = audit_log.verify_chain_integrity(secret_key=secret_key)
        if verify_imported and not verification.is_valid:
            raise AuditTamperedError(f"Imported audit log failed verification: {verification.summary()}")

        return audit_log, verification


class AuditMemoryIsolationGuard:
    """
    Architectural guard enforcing strict separation between Audit Data and Cognitive Memory.

    ORION Architecture Rule (v0.5 Sec 20.5):
    - Audit events are immutable records of physical & safety decisions.
    - Audit events MUST NOT automatically become cognitive memories (poisoning risk).
    - Cognitive memory may reference audit event IDs but must not ingest full audit payloads.
    """

    @staticmethod
    def sanitize_for_cognitive_reference(event: AuditEvent) -> Dict[str, Any]:
        """
        Creates a sanitized reference dictionary suitable for cognitive memory indexing.

        Strips raw executable payloads to eliminate cognitive prompt poisoning risks.
        """
        return {
            "audit_reference_id": event.event_id,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "actor": event.actor,
            "outcome": event.outcome,
            "risk_tier": event.risk_tier,
            "event_hash": event.hash,
            "is_cognitive_fact": False,
        }

    @staticmethod
    def assert_not_audit_payload(data: Any) -> None:
        """
        Validates that data being ingested into Cognitive Memory is not a raw audit event.

        Raises:
            AuditMemoryPoisoningError: If data matches raw AuditEvent structures.
        """
        if isinstance(data, AuditEvent):
            raise AuditMemoryPoisoningError(
                "Direct ingestion of AuditEvent instance into Cognitive Memory is forbidden by ORION Safety Architecture."
            )
        if isinstance(data, dict) and "previous_hash" in data and "safety_decision" in data and "contract_version" in data:
            raise AuditMemoryPoisoningError(
                "Direct ingestion of raw AuditEvent dictionary into Cognitive Memory is forbidden by ORION Safety Architecture."
            )
