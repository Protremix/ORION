"""ORION Physical Intelligence OS - PostgreSQL Persistent Storage Subsystem.
Architecture Version: v0.5 (Luna Phase 3 Condition C1 Compliance)

Provides a PostgreSQL persistent storage layer using asyncpg with connection pooling,
transaction isolation control (SERIALIZABLE for audit events, READ COMMITTED for others),
and full compatibility with the SQLite StorageManager interface.

License: Apache 2.0
"""

import asyncio
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

import asyncpg

from src.persistence.storage import (
    GENESIS_HASH,
    ActionHistoryRecord,
    AuditEventRecord,
    BeliefStateRecord,
    MemoryRecord,
    _parse_field,
    _serialize_field,
    compute_audit_hash,
)

logger = logging.getLogger("orion.persistence.postgres")


class LoopRunner:
    """Helper to run asyncpg coroutines on a dedicated background event loop."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro, timeout: float = 30.0):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)

    def close(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=3.0)


class PostgresStorageManager:
    """PostgreSQL Storage Manager using asyncpg for ORION Physical Intelligence OS."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        database: str = "orion",
        min_size: int = 1,
        max_size: int = 10,
        connection_timeout: float = 5.0,
        db_path: Optional[Union[str, Path]] = None,
        pool: Optional[Any] = None,
        **kwargs,
    ):
        self.dsn = dsn
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.database = database
        self.min_size = int(min_size)
        self.max_size = int(max_size)
        self.connection_timeout = float(connection_timeout)

        self._runner = LoopRunner()
        self._local = threading.local()

        if pool is not None:
            self.pool = pool
        else:
            self.pool = self._runner.run(self._create_pool(), timeout=self.connection_timeout)

        self.init_db()

    async def _create_pool(self):
        if self.dsn:
            return await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=self.min_size,
                max_size=self.max_size,
                timeout=self.connection_timeout,
            )
        else:
            return await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                min_size=self.min_size,
                max_size=self.max_size,
                timeout=self.connection_timeout,
            )

    @property
    def _in_transaction(self) -> bool:
        return getattr(self._local, "in_transaction", False)

    @_in_transaction.setter
    def _in_transaction(self, val: bool):
        self._local.in_transaction = val

    @property
    def _current_conn(self) -> Optional[Any]:
        return getattr(self._local, "current_conn", None)

    @_current_conn.setter
    def _current_conn(self, conn: Optional[Any]):
        self._local.current_conn = conn

    @property
    def _current_tr(self) -> Optional[Any]:
        return getattr(self._local, "current_tr", None)

    @_current_tr.setter
    def _current_tr(self, tr: Optional[Any]):
        self._local.current_tr = tr

    def _run_async(self, coro, timeout: float = 30.0):
        if self._runner is None:
            raise RuntimeError("LoopRunner has been closed.")
        return self._runner.run(coro, timeout=timeout)

    def init_db(self) -> None:
        """Creates PostgreSQL tables and indexes if they do not exist."""
        sql = """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                memory_type TEXT,
                content TEXT,
                source TEXT,
                confidence DOUBLE PRECISION,
                timestamp BIGINT,
                retention_ttl INTEGER,
                schema_version TEXT,
                contradiction_flag INTEGER
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                sequence_number BIGINT,
                event_type TEXT,
                event_data TEXT,
                actor TEXT,
                timestamp BIGINT,
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
                timestamp BIGINT,
                sensor_health TEXT
            );

            CREATE TABLE IF NOT EXISTS action_history (
                lease_id TEXT PRIMARY KEY,
                action_type TEXT,
                target_entity TEXT,
                outcome TEXT,
                execution_stage TEXT,
                duration_ms INTEGER,
                timestamp BIGINT
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
        """
        async def _init():
            async with self.pool.acquire() as conn:
                await conn.execute(sql)

        self._run_async(_init())

    @contextmanager
    def transaction(self, isolation_level: Optional[str] = None):
        """Context manager for atomic database transactions with configurable isolation level."""
        if self._in_transaction:
            yield
            return

        iso = isolation_level or "read_committed"

        async def _start():
            conn = await self.pool.acquire()
            tr = conn.transaction(isolation=iso)
            await tr.start()
            return conn, tr

        conn, tr = self._run_async(_start())
        self._current_conn = conn
        self._current_tr = tr
        self._in_transaction = True

        try:
            yield
            async def _commit():
                await tr.commit()
                await self.pool.release(conn)

            self._run_async(_commit())
        except Exception as e:
            async def _rollback():
                try:
                    await tr.rollback()
                finally:
                    await self.pool.release(conn)

            self._run_async(_rollback())
            raise e
        finally:
            self._in_transaction = False
            self._current_conn = None
            self._current_tr = None

    def close(self) -> None:
        """Closes the connection pool and runner thread."""
        if hasattr(self, "pool") and self.pool is not None:
            async def _close_pool():
                await self.pool.close()

            try:
                self._run_async(_close_pool(), timeout=5.0)
            except Exception as e:
                logger.warning(f"Error closing asyncpg pool: {e}")
            self.pool = None

        if hasattr(self, "_runner") and self._runner is not None:
            self._runner.close()
            self._runner = None

    def _execute_sql(self, sql: str, *args, isolation: str = "read_committed"):
        """Executes SQL statement with optional automatic transaction if not already in transaction."""
        async def _op():
            if self._in_transaction and self._current_conn is not None:
                return await self._current_conn.execute(sql, *args)
            else:
                async with self.pool.acquire() as conn:
                    tr = conn.transaction(isolation=isolation)
                    await tr.start()
                    try:
                        res = await conn.execute(sql, *args)
                        await tr.commit()
                        return res
                    except Exception:
                        await tr.rollback()
                        raise

        return self._run_async(_op())

    def _fetch_sql(self, sql: str, *args, isolation: str = "read_committed"):
        """Fetches multiple records."""
        async def _op():
            if self._in_transaction and self._current_conn is not None:
                rows = await self._current_conn.fetch(sql, *args)
            else:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]

        return self._run_async(_op())

    def _fetchrow_sql(self, sql: str, *args, isolation: str = "read_committed"):
        """Fetches a single record row."""
        async def _op():
            if self._in_transaction and self._current_conn is not None:
                row = await self._current_conn.fetchrow(sql, *args)
            else:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(sql, *args)
            return dict(row) if row else None

        return self._run_async(_op())

    def _fetchval_sql(self, sql: str, *args, isolation: str = "read_committed"):
        """Fetches a single value."""
        async def _op():
            if self._in_transaction and self._current_conn is not None:
                val = await self._current_conn.fetchval(sql, *args)
            else:
                async with self.pool.acquire() as conn:
                    val = await conn.fetchval(sql, *args)
            return val

        return self._run_async(_op())

    def _format_row(self, row: Optional[Dict[str, Any]], parse_json: bool = True) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        if parse_json:
            for k, v in d.items():
                if isinstance(v, str):
                    d[k] = _parse_field(v)
        return d

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
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """
        self._execute_sql(
            sql,
            mem_id,
            memory_type,
            content,
            source,
            confidence,
            ts,
            retention_ttl,
            schema_version,
            contradiction_flag,
            isolation="read_committed",
        )
        return self.get_memory(mem_id) or {}

    add_memory = create_memory
    save_memory = create_memory

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Reads a memory record by ID."""
        sql = "SELECT * FROM memories WHERE id = $1"
        row = self._fetchrow_sql(sql, memory_id, isolation="read_committed")
        return self._format_row(row)

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
        idx = 1
        for k, v in updates.items():
            if k in allowed_cols:
                set_clauses.append(f"{k} = ${idx}")
                idx += 1
                if k == "content":
                    vals.append(_serialize_field(v))
                else:
                    vals.append(v)

        if not set_clauses:
            return existing

        vals.append(memory_id)
        sql = f"UPDATE memories SET {', '.join(set_clauses)} WHERE id = ${idx}"
        self._execute_sql(sql, *vals, isolation="read_committed")
        return self.get_memory(memory_id)

    def delete_memory(self, memory_id: str) -> bool:
        """Deletes a memory record by ID."""
        sql = "DELETE FROM memories WHERE id = $1"
        res = self._execute_sql(sql, memory_id, isolation="read_committed")
        if isinstance(res, str) and res.startswith("DELETE "):
            try:
                count = int(res.split(" ")[-1])
                return count > 0
            except (IndexError, ValueError):
                pass
        return False

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
            max_seq = self._fetchval_sql(
                "SELECT MAX(sequence_number) FROM audit_events",
                isolation="serializable"
            )
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
            last_row = self._fetchrow_sql(
                "SELECT hash FROM audit_events ORDER BY sequence_number DESC LIMIT 1",
                isolation="serializable"
            )
            prev_hash = last_row["hash"] if last_row and last_row.get("hash") else GENESIS_HASH
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
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        self._execute_sql(
            sql,
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
            isolation="serializable",
        )
        return self.get_audit_event(event_id) or {}

    add_audit_event = create_audit_event
    save_audit_event = create_audit_event

    def get_audit_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Reads an audit event record by ID."""
        sql = "SELECT * FROM audit_events WHERE id = $1"
        row = self._fetchrow_sql(sql, event_id, isolation="serializable")
        return self._format_row(row)

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
        idx = 1
        for k, v in updates.items():
            if k in allowed_cols:
                set_clauses.append(f"{k} = ${idx}")
                idx += 1
                if k == "event_data":
                    vals.append(_serialize_field(v))
                else:
                    vals.append(v)

        if not set_clauses:
            return existing

        vals.append(event_id)
        sql = f"UPDATE audit_events SET {', '.join(set_clauses)} WHERE id = ${idx}"
        self._execute_sql(sql, *vals, isolation="serializable")
        return self.get_audit_event(event_id)

    def delete_audit_event(self, event_id: str) -> bool:
        """Deletes an audit event by ID."""
        sql = "DELETE FROM audit_events WHERE id = $1"
        res = self._execute_sql(sql, event_id, isolation="serializable")
        if isinstance(res, str) and res.startswith("DELETE "):
            try:
                count = int(res.split(" ")[-1])
                return count > 0
            except (IndexError, ValueError):
                pass
        return False

    def verify_audit_hash_chain(self) -> bool:
        """Verifies hash chain integrity across all stored audit events."""
        rows = self._fetch_sql(
            "SELECT * FROM audit_events ORDER BY sequence_number ASC",
            isolation="serializable"
        )
        if not rows:
            return True

        events = [self._format_row(r, parse_json=False) for r in rows]

        for i, event in enumerate(events):
            if i > 0:
                prev_event_hash = events[i - 1].get("hash", "")
                if event.get("previous_hash") != prev_event_hash:
                    logger.error(
                        f"Audit chain link broken at sequence {event.get('sequence_number')}: "
                        f"expected previous_hash={prev_event_hash}, got {event.get('previous_hash')}"
                    )
                    return False

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
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        self._execute_sql(sql, belief_id, revision, pos, ori, vel, unc, ts, health, isolation="read_committed")
        return self.get_belief_state(belief_id) or {}

    add_belief_state = create_belief_state
    save_belief_state = create_belief_state

    def get_belief_state(self, belief_id: str) -> Optional[Dict[str, Any]]:
        """Reads a belief state record by ID."""
        sql = "SELECT * FROM belief_states WHERE id = $1"
        row = self._fetchrow_sql(sql, belief_id, isolation="read_committed")
        return self._format_row(row)

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
        idx = 1
        for k, v in updates.items():
            if k in allowed_cols:
                set_clauses.append(f"{k} = ${idx}")
                idx += 1
                if k in json_cols:
                    vals.append(_serialize_field(v))
                else:
                    vals.append(v)

        if not set_clauses:
            return existing

        vals.append(belief_id)
        sql = f"UPDATE belief_states SET {', '.join(set_clauses)} WHERE id = ${idx}"
        self._execute_sql(sql, *vals, isolation="read_committed")
        return self.get_belief_state(belief_id)

    def delete_belief_state(self, belief_id: str) -> bool:
        """Deletes a belief state record by ID."""
        sql = "DELETE FROM belief_states WHERE id = $1"
        res = self._execute_sql(sql, belief_id, isolation="read_committed")
        if isinstance(res, str) and res.startswith("DELETE "):
            try:
                count = int(res.split(" ")[-1])
                return count > 0
            except (IndexError, ValueError):
                pass
        return False

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
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        self._execute_sql(
            sql, lease_id, action_type, target_entity, outcome, execution_stage, duration_ms, ts,
            isolation="read_committed"
        )
        return self.get_action_history(lease_id) or {}

    add_action_history = create_action_history
    save_action_history = create_action_history

    def get_action_history(self, lease_id: str) -> Optional[Dict[str, Any]]:
        """Reads an action history record by lease_id."""
        sql = "SELECT * FROM action_history WHERE lease_id = $1"
        row = self._fetchrow_sql(sql, lease_id, isolation="read_committed")
        return self._format_row(row)

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
        idx = 1
        for k, v in updates.items():
            if k in allowed_cols:
                set_clauses.append(f"{k} = ${idx}")
                idx += 1
                vals.append(v)

        if not set_clauses:
            return existing

        vals.append(lease_id)
        sql = f"UPDATE action_history SET {', '.join(set_clauses)} WHERE lease_id = ${idx}"
        self._execute_sql(sql, *vals, isolation="read_committed")
        return self.get_action_history(lease_id)

    def delete_action_history(self, lease_id: str) -> bool:
        """Deletes an action history record by lease_id."""
        sql = "DELETE FROM action_history WHERE lease_id = $1"
        res = self._execute_sql(sql, lease_id, isolation="read_committed")
        if isinstance(res, str) and res.startswith("DELETE "):
            try:
                count = int(res.split(" ")[-1])
                return count > 0
            except (IndexError, ValueError):
                pass
        return False

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
        param_idx = 1

        if start_time is not None:
            where_clauses.append(f"timestamp >= ${param_idx}")
            params.append(int(start_time))
            param_idx += 1

        if end_time is not None:
            where_clauses.append(f"timestamp <= ${param_idx}")
            params.append(int(end_time))
            param_idx += 1

        if filters:
            for k, v in filters.items():
                if v is not None:
                    where_clauses.append(f"{k} = ${param_idx}")
                    params.append(v)
                    param_idx += 1

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT * FROM {table_name}{where_sql} ORDER BY {order_by}"

        iso = "serializable" if table_name == "audit_events" else "read_committed"
        rows = self._fetch_sql(sql, *params, isolation=iso)
        return [self._format_row(row) for row in rows]

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
        param_idx = 1

        if start_time is not None:
            where_clauses.append(f"timestamp >= ${param_idx}")
            params.append(int(start_time))
            param_idx += 1
        if end_time is not None:
            where_clauses.append(f"timestamp <= ${param_idx}")
            params.append(int(end_time))
            param_idx += 1
        if min_revision is not None:
            where_clauses.append(f"revision >= ${param_idx}")
            params.append(int(min_revision))
            param_idx += 1

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT * FROM belief_states{where_sql} ORDER BY revision ASC, timestamp ASC"
        rows = self._fetch_sql(sql, *params, isolation="read_committed")
        return [self._format_row(row) for row in rows]

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
                    iso = "serializable" if table == "audit_events" else "read_committed"
                    self._execute_sql(f"DELETE FROM {table}", isolation=iso)

            for mem in data.get("memories", []):
                self.create_memory(mem)

            for evt in data.get("audit_events", []):
                self.create_audit_event(evt)

            for bst in data.get("belief_states", []):
                self.create_belief_state(bst)

            for act in data.get("action_history", []):
                self.create_action_history(act)
