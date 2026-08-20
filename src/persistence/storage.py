"""ORION Physical Intelligence OS - Persistent Storage Subsystem.
Architecture Version: v0.5 (Luna Phase 1 Condition-3 Compliance)

Provides an SQLite persistent storage layer using Python's standard library.
Supports memories, audit_events, belief_states, and action_history tables with
CRUD operations, timestamp/type/actor query filters, atomic transactions with rollback,
hash chain verification for audit logs, and JSON export/import.

License: Apache 2.0
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("orion.persistence")

GENESIS_HASH: str = "0" * 64


# ============================================================================
# Dataclasses for standard table records
# ============================================================================

@dataclass
class MemoryRecord:
    """Represents a row in the memories table."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: str = "episodic"
    content: Union[str, Dict[str, Any]] = ""
    source: str = ""
    confidence: float = 1.0
    timestamp: int = field(default_factory=lambda: int(time.time()))
    retention_ttl: int = 0
    schema_version: str = "1.0.0"
    contradiction_flag: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEventRecord:
    """Represents a row in the audit_events table."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence_number: int = 0
    event_type: str = "decision"
    event_data: Union[str, Dict[str, Any]] = ""
    actor: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time()))
    previous_hash: str = GENESIS_HASH
    hash: str = ""
    signature: str = ""
    severity: str = "info"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BeliefStateRecord:
    """Represents a row in the belief_states table."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    revision: int = 0
    position: Union[str, Dict[str, Any], List[Any]] = ""
    orientation: Union[str, Dict[str, Any], List[Any]] = ""
    velocity: Union[str, Dict[str, Any], List[Any]] = ""
    uncertainty: Union[str, Dict[str, Any], List[Any]] = ""
    timestamp: int = field(default_factory=lambda: int(time.time()))
    sensor_health: Union[str, Dict[str, Any]] = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionHistoryRecord:
    """Represents a row in the action_history table."""
    lease_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = "execute"
    target_entity: str = ""
    outcome: str = "completed"
    execution_stage: str = "completed"
    duration_ms: int = 0
    timestamp: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Helpers for field serialization and parsing
# ============================================================================

def _serialize_field(val: Any) -> str:
    """Serializes dictionaries, lists, or non-primitive structures to JSON strings."""
    if val is None:
        return ""
    if isinstance(val, (dict, list)):
        return json.dumps(val, sort_keys=True)
    return str(val)


def _parse_field(val: Any) -> Any:
    """Attempts to parse string value back to dict/list if formatted as JSON."""
    if not isinstance(val, str):
        return val
    s = val.strip()
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            return json.loads(s)
        except Exception:
            return val
    return val


def _row_to_dict(row: sqlite3.Row, parse_json: bool = True) -> Dict[str, Any]:
    """Converts sqlite3.Row to dict and optionally deserializes JSON strings."""
    d = dict(row)
    if parse_json:
        for k, v in d.items():
            if isinstance(v, str):
                d[k] = _parse_field(v)
    return d


def compute_audit_hash(
    event_id: str,
    sequence_number: int,
    event_type: str,
    event_data: Any,
    actor: str,
    timestamp: int,
    previous_hash: str,
    severity: str,
) -> str:
    """Computes SHA-256 hash for audit event record fields."""
    data_str = _serialize_field(event_data)
    canonical = f"{event_id}:{sequence_number}:{event_type}:{data_str}:{actor}:{timestamp}:{previous_hash}:{severity}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ============================================================================
# StorageManager Class
# ============================================================================

class StorageManager:
    """SQLite Storage Manager for ORION Physical Intelligence OS."""

    def __init__(self, db_path: Union[str, Path] = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._in_transaction = False
        self.init_db()

    def init_db(self) -> None:
        """Creates DB schema tables and indexes if they do not exist."""
        with self.transaction():
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT,
                    content TEXT,
                    source TEXT,
                    confidence REAL,
                    timestamp INTEGER,
                    retention_ttl INTEGER,
                    schema_version TEXT,
                    contradiction_flag INTEGER
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    sequence_number INTEGER,
                    event_type TEXT,
                    event_data TEXT,
                    actor TEXT,
                    timestamp INTEGER,
                    previous_hash TEXT,
                    hash TEXT,
                    signature TEXT,
                    severity TEXT
                );

                CREATE TABLE IF NOT EXISTS belief_states (
                    id TEXT PRIMARY KEY,
                    revision INTEGER,
                    position TEXT,
                    orientation TEXT,
                    velocity TEXT,
                    uncertainty TEXT,
                    timestamp INTEGER,
                    sensor_health TEXT
                );

                CREATE TABLE IF NOT EXISTS action_history (
                    lease_id TEXT PRIMARY KEY,
                    action_type TEXT,
                    target_entity TEXT,
                    outcome TEXT,
                    execution_stage TEXT,
                    duration_ms INTEGER,
                    timestamp INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp);
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);

                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor);
                CREATE INDEX IF NOT EXISTS idx_audit_seq ON audit_events(sequence_number);

                CREATE INDEX IF NOT EXISTS idx_belief_timestamp ON belief_states(timestamp);
                CREATE INDEX IF NOT EXISTS idx_belief_revision ON belief_states(revision);

                CREATE INDEX IF NOT EXISTS idx_action_timestamp ON action_history(timestamp);
                CREATE INDEX IF NOT EXISTS idx_action_type ON action_history(action_type);
            """)

    @contextmanager
    def transaction(self):
        """Context manager for atomic database transactions with automatic rollback on failure."""
        in_trans = self._in_transaction
        if not in_trans:
            self.conn.execute("BEGIN TRANSACTION")
            self._in_transaction = True
        try:
            yield
            if not in_trans:
                self.conn.commit()
                self._in_transaction = False
        except Exception as e:
            if not in_trans:
                self.conn.rollback()
                self._in_transaction = False
            raise e

    def _commit_if_not_in_transaction(self):
        if not self._in_transaction:
            self.conn.commit()

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        if self.conn:
            self.conn.close()

    # ------------------------------------------------------------------------
    # Memories CRUD
    # ------------------------------------------------------------------------

    def create_memory(
        self,
        record: Optional[Union[MemoryRecord, Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Creates a memory record in the memories table."""
        if record is not None:
            if hasattr(record, "to_dict"):
                data = record.to_dict()
            elif isinstance(record, dict):
                data = dict(record)
            else:
                data = {}
        else:
            data = {}
        data.update(kwargs)

        mem_id = str(data.get("id") or str(uuid.uuid4()))
        memory_type = str(data.get("memory_type", "episodic"))
        content = _serialize_field(data.get("content", ""))
        source = str(data.get("source", ""))
        confidence = float(data.get("confidence", 1.0))
        ts = int(data.get("timestamp", int(time.time())))
        retention_ttl = int(data.get("retention_ttl", 0))
        schema_version = str(data.get("schema_version", "1.0.0"))
        contradiction_flag = int(data.get("contradiction_flag", 0))

        sql = """
            INSERT INTO memories (
                id, memory_type, content, source, confidence,
                timestamp, retention_ttl, schema_version, contradiction_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.conn.execute(
            sql,
            (
                mem_id,
                memory_type,
                content,
                source,
                confidence,
                ts,
                retention_ttl,
                schema_version,
                contradiction_flag,
            ),
        )
        self._commit_if_not_in_transaction()
        return self.get_memory(mem_id) or {}

    add_memory = create_memory
    save_memory = create_memory

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Reads a memory record by ID."""
        cursor = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_dict(row)

    read_memory = get_memory

    def update_memory(self, memory_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Updates fields of an existing memory record."""
        existing = self.get_memory(memory_id)
        if not existing:
            return None

        allowed_cols = {
            "memory_type", "content", "source", "confidence",
            "timestamp", "retention_ttl", "schema_version", "contradiction_flag"
        }
        set_clauses = []
        vals = []
        for k, v in updates.items():
            if k in allowed_cols:
                set_clauses.append(f"{k} = ?")
                if k == "content":
                    vals.append(_serialize_field(v))
                else:
                    vals.append(v)

        if not set_clauses:
            return existing

        vals.append(memory_id)
        sql = f"UPDATE memories SET {', '.join(set_clauses)} WHERE id = ?"
        self.conn.execute(sql, vals)
        self._commit_if_not_in_transaction()
        return self.get_memory(memory_id)

    def delete_memory(self, memory_id: str) -> bool:
        """Deletes a memory record by ID."""
        cursor = self.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._commit_if_not_in_transaction()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------------
    # Audit Events CRUD & Verification
    # ------------------------------------------------------------------------

    def create_audit_event(
        self,
        record: Optional[Union[AuditEventRecord, Any, Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Creates an audit event record preserving sequence numbers and hash chains."""
        if record is not None:
            if hasattr(record, "to_dict"):
                data = record.to_dict()
            elif isinstance(record, dict):
                data = dict(record)
            else:
                data = {
                    k: getattr(record, k) for k in dir(record)
                    if not k.startswith("_") and not callable(getattr(record, k))
                }
        else:
            data = {}
        data.update(kwargs)

        event_id = str(data.get("id") or data.get("event_id") or str(uuid.uuid4()))

        # Determine sequence number if not given
        seq_num = data.get("sequence_number")
        if seq_num is None or int(seq_num) <= 0:
            cursor = self.conn.execute("SELECT MAX(sequence_number) FROM audit_events")
            max_seq = cursor.fetchone()[0]
            seq_num = (max_seq + 1) if max_seq is not None else 1
        else:
            seq_num = int(seq_num)

        event_type = str(data.get("event_type", "decision"))
        event_data = data.get("event_data")
        if event_data is None:
            event_data = data.get("payload") or data.get("action") or ""
        event_data_str = _serialize_field(event_data)

        actor = str(data.get("actor", ""))
        ts = int(data.get("timestamp", int(time.time())))
        severity = str(data.get("severity") or data.get("risk_tier") or "info")
        signature = str(data.get("signature", ""))

        # Previous hash auto-chaining
        prev_hash = data.get("previous_hash")
        if not prev_hash:
            cursor = self.conn.execute(
                "SELECT hash FROM audit_events ORDER BY sequence_number DESC LIMIT 1"
            )
            last_row = cursor.fetchone()
            prev_hash = last_row["hash"] if last_row and last_row["hash"] else GENESIS_HASH
        else:
            prev_hash = str(prev_hash)

        # Hash auto-calculation
        event_hash = data.get("hash")
        if not event_hash:
            event_hash = compute_audit_hash(
                event_id=event_id,
                sequence_number=seq_num,
                event_type=event_type,
                event_data=event_data,
                actor=actor,
                timestamp=ts,
                previous_hash=prev_hash,
                severity=severity,
            )
        else:
            event_hash = str(event_hash)

        sql = """
            INSERT INTO audit_events (
                id, sequence_number, event_type, event_data, actor,
                timestamp, previous_hash, hash, signature, severity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.conn.execute(
            sql,
            (
                event_id,
                seq_num,
                event_type,
                event_data_str,
                actor,
                ts,
                prev_hash,
                event_hash,
                signature,
                severity,
            ),
        )
        self._commit_if_not_in_transaction()
        return self.get_audit_event(event_id) or {}

    add_audit_event = create_audit_event
    save_audit_event = create_audit_event

    def get_audit_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Reads an audit event record by ID."""
        cursor = self.conn.execute("SELECT * FROM audit_events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_dict(row)

    read_audit_event = get_audit_event

    def update_audit_event(self, event_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Updates specified fields of an audit event."""
        existing = self.get_audit_event(event_id)
        if not existing:
            return None

        allowed_cols = {
            "sequence_number", "event_type", "event_data", "actor",
            "timestamp", "previous_hash", "hash", "signature", "severity"
        }
        set_clauses = []
        vals = []
        for k, v in updates.items():
            if k in allowed_cols:
                set_clauses.append(f"{k} = ?")
                if k == "event_data":
                    vals.append(_serialize_field(v))
                else:
                    vals.append(v)

        if not set_clauses:
            return existing

        vals.append(event_id)
        sql = f"UPDATE audit_events SET {', '.join(set_clauses)} WHERE id = ?"
        self.conn.execute(sql, vals)
        self._commit_if_not_in_transaction()
        return self.get_audit_event(event_id)

    def delete_audit_event(self, event_id: str) -> bool:
        """Deletes an audit event by ID."""
        cursor = self.conn.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
        self._commit_if_not_in_transaction()
        return cursor.rowcount > 0

    def verify_audit_hash_chain(self) -> bool:
        """Verifies hash chain integrity across all stored audit events."""
        cursor = self.conn.execute(
            "SELECT * FROM audit_events ORDER BY sequence_number ASC"
        )
        rows = cursor.fetchall()
        if not rows:
            return True

        events = [_row_to_dict(r, parse_json=False) for r in rows]

        for i, event in enumerate(events):
            # 1. Verify previous hash chain connection
            if i == 0:
                pass
            else:
                prev_event_hash = events[i - 1].get("hash", "")
                if event.get("previous_hash") != prev_event_hash:
                    logger.error(
                        f"Audit chain link broken at sequence {event.get('sequence_number')}: "
                        f"expected previous_hash={prev_event_hash}, got {event.get('previous_hash')}"
                    )
                    return False

            # 2. Verify stored hash validity
            stored_hash = event.get("hash", "")
            if not stored_hash:
                logger.error(f"Audit event {event.get('id')} missing hash")
                return False

            computed = compute_audit_hash(
                event_id=event["id"],
                sequence_number=int(event["sequence_number"]),
                event_type=event["event_type"],
                event_data=event.get("event_data", ""),
                actor=event.get("actor", ""),
                timestamp=int(event.get("timestamp", 0)),
                previous_hash=event.get("previous_hash", ""),
                severity=event.get("severity", ""),
            )

            if computed != stored_hash:
                # Fallback check if calculated by AuditEvent class
                raw_data = event.get("event_data", "")
                hash_valid = False
                try:
                    if isinstance(raw_data, str) and raw_data.startswith("{"):
                        parsed = json.loads(raw_data)
                        if isinstance(parsed, dict) and ("contract_version" in parsed or "schema_version" in parsed):
                            from src.audit.audit_system import AuditEvent
                            ae = AuditEvent.from_dict(parsed)
                            if ae.calculate_hash() == stored_hash:
                                hash_valid = True
                except Exception:
                    pass

                if not hash_valid:
                    logger.error(
                        f"Audit event {event.get('id')} hash mismatch: stored={stored_hash}, computed={computed}"
                    )
                    return False

        return True

    verify_audit_chain = verify_audit_hash_chain

    # ------------------------------------------------------------------------
    # Belief States CRUD
    # ------------------------------------------------------------------------

    def create_belief_state(
        self,
        record: Optional[Union[BeliefStateRecord, Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Creates a belief state record in the belief_states table."""
        if record is not None:
            if hasattr(record, "to_dict"):
                data = record.to_dict()
            elif isinstance(record, dict):
                data = dict(record)
            else:
                data = {}
        else:
            data = {}
        data.update(kwargs)

        belief_id = str(data.get("id") or str(uuid.uuid4()))
        revision = int(data.get("revision", 0))
        pos = _serialize_field(data.get("position", ""))
        ori = _serialize_field(data.get("orientation", ""))
        vel = _serialize_field(data.get("velocity", ""))
        unc = _serialize_field(data.get("uncertainty", ""))
        ts = int(data.get("timestamp", int(time.time())))
        health = _serialize_field(data.get("sensor_health", ""))

        sql = """
            INSERT INTO belief_states (
                id, revision, position, orientation, velocity,
                uncertainty, timestamp, sensor_health
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.conn.execute(sql, (belief_id, revision, pos, ori, vel, unc, ts, health))
        self._commit_if_not_in_transaction()
        return self.get_belief_state(belief_id) or {}

    add_belief_state = create_belief_state
    save_belief_state = create_belief_state

    def get_belief_state(self, belief_id: str) -> Optional[Dict[str, Any]]:
        """Reads a belief state record by ID."""
        cursor = self.conn.execute("SELECT * FROM belief_states WHERE id = ?", (belief_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_dict(row)

    read_belief_state = get_belief_state

    def update_belief_state(self, belief_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Updates an existing belief state record."""
        existing = self.get_belief_state(belief_id)
        if not existing:
            return None

        allowed_cols = {
            "revision", "position", "orientation", "velocity",
            "uncertainty", "timestamp", "sensor_health"
        }
        json_cols = {"position", "orientation", "velocity", "uncertainty", "sensor_health"}
        set_clauses = []
        vals = []
        for k, v in updates.items():
            if k in allowed_cols:
                set_clauses.append(f"{k} = ?")
                if k in json_cols:
                    vals.append(_serialize_field(v))
                else:
                    vals.append(v)

        if not set_clauses:
            return existing

        vals.append(belief_id)
        sql = f"UPDATE belief_states SET {', '.join(set_clauses)} WHERE id = ?"
        self.conn.execute(sql, vals)
        self._commit_if_not_in_transaction()
        return self.get_belief_state(belief_id)

    def delete_belief_state(self, belief_id: str) -> bool:
        """Deletes a belief state record by ID."""
        cursor = self.conn.execute("DELETE FROM belief_states WHERE id = ?", (belief_id,))
        self._commit_if_not_in_transaction()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------------
    # Action History CRUD
    # ------------------------------------------------------------------------

    def create_action_history(
        self,
        record: Optional[Union[ActionHistoryRecord, Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Creates an action history record in the action_history table."""
        if record is not None:
            if hasattr(record, "to_dict"):
                data = record.to_dict()
            elif isinstance(record, dict):
                data = dict(record)
            else:
                data = {}
        else:
            data = {}
        data.update(kwargs)

        lease_id = str(data.get("lease_id") or str(uuid.uuid4()))
        action_type = str(data.get("action_type", "execute"))
        target_entity = str(data.get("target_entity", ""))
        outcome = str(data.get("outcome", "completed"))
        execution_stage = str(data.get("execution_stage", "completed"))
        duration_ms = int(data.get("duration_ms", 0))
        ts = int(data.get("timestamp", int(time.time())))

        sql = """
            INSERT INTO action_history (
                lease_id, action_type, target_entity, outcome,
                execution_stage, duration_ms, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.conn.execute(
            sql,
            (lease_id, action_type, target_entity, outcome, execution_stage, duration_ms, ts),
        )
        self._commit_if_not_in_transaction()
        return self.get_action_history(lease_id) or {}

    add_action_history = create_action_history
    save_action_history = create_action_history

    def get_action_history(self, lease_id: str) -> Optional[Dict[str, Any]]:
        """Reads an action history record by lease_id."""
        cursor = self.conn.execute(
            "SELECT * FROM action_history WHERE lease_id = ?", (lease_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_dict(row)

    read_action_history = get_action_history

    def update_action_history(self, lease_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Updates fields of an action history record."""
        existing = self.get_action_history(lease_id)
        if not existing:
            return None

        allowed_cols = {
            "action_type", "target_entity", "outcome",
            "execution_stage", "duration_ms", "timestamp"
        }
        set_clauses = []
        vals = []
        for k, v in updates.items():
            if k in allowed_cols:
                set_clauses.append(f"{k} = ?")
                vals.append(v)

        if not set_clauses:
            return existing

        vals.append(lease_id)
        sql = f"UPDATE action_history SET {', '.join(set_clauses)} WHERE lease_id = ?"
        self.conn.execute(sql, vals)
        self._commit_if_not_in_transaction()
        return self.get_action_history(lease_id)

    def delete_action_history(self, lease_id: str) -> bool:
        """Deletes an action history record by lease_id."""
        cursor = self.conn.execute("DELETE FROM action_history WHERE lease_id = ?", (lease_id,))
        self._commit_if_not_in_transaction()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------------
    # Query / Filter Methods
    # ------------------------------------------------------------------------

    def _query_table(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        order_by: str = "timestamp ASC",
    ) -> List[Dict[str, Any]]:
        """Generic query filter builder for storage tables."""
        where_clauses = []
        params = []

        if start_time is not None:
            where_clauses.append("timestamp >= ?")
            params.append(int(start_time))

        if end_time is not None:
            where_clauses.append("timestamp <= ?")
            params.append(int(end_time))

        if filters:
            for k, v in filters.items():
                if v is not None:
                    where_clauses.append(f"{k} = ?")
                    params.append(v)

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT * FROM {table_name}{where_sql} ORDER BY {order_by}"

        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        return [_row_to_dict(row) for row in rows]

    def query_memories(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        memory_type: Optional[str] = None,
        source: Optional[str] = None,
        contradiction_flag: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Queries memories filtered by time range, type, source, or contradiction flag."""
        filters = {}
        if memory_type is not None:
            filters["memory_type"] = str(memory_type)
        if source is not None:
            filters["source"] = str(source)
        if contradiction_flag is not None:
            filters["contradiction_flag"] = int(contradiction_flag)

        return self._query_table(
            "memories",
            filters=filters,
            start_time=start_time,
            end_time=end_time,
        )

    def query_audit_events(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries audit events filtered by time range, event_type, actor, or severity."""
        filters = {}
        if event_type is not None:
            filters["event_type"] = str(event_type)
        if actor is not None:
            filters["actor"] = str(actor)
        if severity is not None:
            filters["severity"] = str(severity)

        return self._query_table(
            "audit_events",
            filters=filters,
            start_time=start_time,
            end_time=end_time,
            order_by="sequence_number ASC",
        )

    def query_belief_states(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_revision: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Queries belief states filtered by time range or minimum revision."""
        where_clauses = []
        params = []

        if start_time is not None:
            where_clauses.append("timestamp >= ?")
            params.append(int(start_time))
        if end_time is not None:
            where_clauses.append("timestamp <= ?")
            params.append(int(end_time))
        if min_revision is not None:
            where_clauses.append("revision >= ?")
            params.append(int(min_revision))

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT * FROM belief_states{where_sql} ORDER BY revision ASC, timestamp ASC"
        cursor = self.conn.execute(sql, params)
        return [_row_to_dict(row) for row in cursor.fetchall()]

    def query_action_history(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        action_type: Optional[str] = None,
        target_entity: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries action history filtered by time range, action_type, target, or outcome."""
        filters = {}
        if action_type is not None:
            filters["action_type"] = str(action_type)
        if target_entity is not None:
            filters["target_entity"] = str(target_entity)
        if outcome is not None:
            filters["outcome"] = str(outcome)

        return self._query_table(
            "action_history",
            filters=filters,
            start_time=start_time,
            end_time=end_time,
        )

    def query(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Generic table query method."""
        valid_tables = {"memories", "audit_events", "belief_states", "action_history"}
        if table_name not in valid_tables:
            raise ValueError(f"Invalid table_name '{table_name}'. Expected one of {valid_tables}")
        order_col = "sequence_number ASC" if table_name == "audit_events" else "timestamp ASC"
        return self._query_table(
            table_name=table_name,
            filters=filters,
            start_time=start_time,
            end_time=end_time,
            order_by=order_col,
        )

    # ------------------------------------------------------------------------
    # Export (Backup) and Import (Restore) Methods
    # ------------------------------------------------------------------------

    def export_to_json(self, filepath: Optional[Union[str, Path]] = None) -> str:
        """Exports all database tables to a JSON string or file."""
        data = {
            "metadata": {
                "exported_at": int(time.time()),
                "version": "1.0.0",
                "schema_tables": ["memories", "audit_events", "belief_states", "action_history"],
            },
            "memories": self._query_table("memories", order_by="timestamp ASC"),
            "audit_events": self._query_table("audit_events", order_by="sequence_number ASC"),
            "belief_states": self._query_table("belief_states", order_by="revision ASC"),
            "action_history": self._query_table("action_history", order_by="timestamp ASC"),
        }

        json_str = json.dumps(data, indent=2, sort_keys=True)
        if filepath is not None:
            out_path = Path(filepath)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json_str, encoding="utf-8")

        return json_str

    def import_from_json(
        self,
        json_data: Union[str, Dict[str, Any], Path],
        clear_existing: bool = False,
    ) -> None:
        """Restores database tables from JSON content, dictionary, or JSON file path."""
        if isinstance(json_data, (str, Path)):
            p = Path(json_data)
            if p.is_file():
                raw_text = p.read_text(encoding="utf-8")
                data = json.loads(raw_text)
            else:
                s = str(json_data).strip()
                if s.startswith("{"):
                    data = json.loads(s)
                else:
                    raise ValueError(f"Invalid json_data argument or missing file: {json_data}")
        elif isinstance(json_data, dict):
            data = json_data
        else:
            raise TypeError(f"Unsupported json_data type: {type(json_data)}")

        with self.transaction():
            if clear_existing:
                for table in ["memories", "audit_events", "belief_states", "action_history"]:
                    self.conn.execute(f"DELETE FROM {table}")

            for mem in data.get("memories", []):
                self.create_memory(mem)

            for evt in data.get("audit_events", []):
                self.create_audit_event(evt)

            for bst in data.get("belief_states", []):
                self.create_belief_state(bst)

            for act in data.get("action_history", []):
                self.create_action_history(act)
