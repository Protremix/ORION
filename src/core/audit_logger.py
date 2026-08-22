"""
ORION Core Audit Logger — Phase 004. License: Apache 2.0
Tamper-evident audit trail with SHA-256 hash chaining.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class AuditEventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    PLAN_GENERATED = "plan_generated"
    PLAN_VALIDATED = "plan_validated"
    PLAN_REJECTED = "plan_rejected"
    POLICY_DECISION = "policy_decision"
    PERMISSION_CHECK = "permission_check"
    TOOL_INVOKED = "tool_invoked"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    TOOL_TIMEOUT = "tool_timeout"
    RETRY = "retry"
    ROLLBACK = "rollback"
    STATE_TRANSITION = "state_transition"
    MODEL_CALLED = "model_called"
    MODEL_RESPONSE = "model_response"
    ERROR = "error"
    RECOVERY = "recovery"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"

@dataclass
class AuditEvent:
    id: str
    type: AuditEventType
    correlation_id: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""

    def __post_init__(self):
        self._compute_hash()

    def _compute_hash(self) -> None:
        content = json.dumps({"id": self.id, "type": self.type.value,
            "correlation_id": self.correlation_id, "timestamp": self.timestamp,
            "details": self.details, "prev_hash": self.prev_hash}, sort_keys=True)
        self.hash = hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {"id": self.id, "type": self.type.value, "correlation_id": self.correlation_id,
                "timestamp": self.timestamp, "details": self.details,
                "prev_hash": self.prev_hash, "hash": self.hash}

class AuditLogger:
    def __init__(self) -> None:
        self._events: List[AuditEvent] = []
        self._lock = threading.RLock()
        self._correlation_index: Dict[str, List[int]] = {}

    def log(self, event_type: AuditEventType, correlation_id: str,
            details: Optional[Dict[str, Any]] = None) -> AuditEvent:
        with self._lock:
            prev_hash = self._events[-1].hash if self._events else ""
            event = AuditEvent(id=str(uuid.uuid4()), type=event_type,
                correlation_id=correlation_id, details=details or {}, prev_hash=prev_hash)
            idx = len(self._events)
            self._events.append(event)
            self._correlation_index.setdefault(correlation_id, []).append(idx)
            logger.debug(f"Audit: {event_type.value} [{correlation_id}]")
            return event

    def get_events(self, correlation_id: Optional[str] = None,
                   event_type: Optional[AuditEventType] = None, limit: int = 100) -> List[AuditEvent]:
        with self._lock:
            if correlation_id:
                indices = self._correlation_index.get(correlation_id, [])
                events = [self._events[i] for i in indices]
            else:
                events = list(self._events)
            if event_type:
                events = [e for e in events if e.type == event_type]
            return events[-limit:]

    def verify_chain(self) -> bool:
        with self._lock:
            prev = ""
            for event in self._events:
                if event.prev_hash != prev:
                    logger.error(f"Audit chain broken at event {event.id}")
                    return False
                content = json.dumps({"id": event.id, "type": event.type.value,
                    "correlation_id": event.correlation_id, "timestamp": event.timestamp,
                    "details": event.details, "prev_hash": event.prev_hash}, sort_keys=True)
                if hashlib.sha256(content.encode()).hexdigest() != event.hash:
                    logger.error(f"Audit hash mismatch at event {event.id}")
                    return False
                prev = event.hash
            return True

    def get_task_history(self, correlation_id: str) -> List[Dict[str, Any]]:
        events = self.get_events(correlation_id=correlation_id, limit=10000)
        return [e.to_dict() for e in events]

    def event_count(self) -> int:
        with self._lock:
            return len(self._events)

    def to_dict(self) -> dict:
        with self._lock:
            return {"event_count": len(self._events),
                    "correlation_count": len(self._correlation_index),
                    "chain_valid": self.verify_chain()}
