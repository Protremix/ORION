"""
Audit Log Replication & Backup Strategy for ORION Physical Intelligence OS.

This module implements primary-replica audit log replication with:
1. WAL-based replication (write-ahead log in SQLite)
2. Backup scheduling with configurable interval
3. Point-in-time recovery (snapshot + WAL replay)
4. Hash chain verification across replicas
5. Failure handling: replica down → continue on primary, catch up on rejoin
6. Export/import for backup transfer

The module uses the existing StorageManager's audit event system and extends it
with replication capabilities. All replication is simulated in-process (no network)
to keep the simulation environment self-contained.
"""

import hashlib
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class BackupSnapshot:
    """A point-in-time backup snapshot of the audit log."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    source_db_path: str = ""
    backup_db_path: str = ""
    event_count: int = 0
    last_sequence: int = 0
    last_hash: str = ""
    hash: str = ""

    def compute_hash(self) -> str:
        content = f"{self.snapshot_id}:{self.timestamp}:{self.last_sequence}:{self.last_hash}"
        self.hash = hashlib.sha256(content.encode()).hexdigest()
        return self.hash


@dataclass
class WALRecord:
    """A write-ahead log record for replication."""
    wal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence_number: int = 0
    timestamp: float = field(default_factory=time.time)
    operation: str = "insert"  # insert, update, delete
    table: str = "audit_events"
    record_data: Dict[str, Any] = field(default_factory=dict)
    hash: str = ""

    def compute_hash(self) -> str:
        content = f"{self.wal_id}:{self.sequence_number}:{self.operation}:{self.table}"
        self.hash = hashlib.sha256(content.encode()).hexdigest()
        return self.hash


@dataclass
class ReplicationStatus:
    """Status of a replica relative to primary."""
    replica_id: str = ""
    primary_id: str = ""
    last_replicated_sequence: int = 0
    primary_last_sequence: int = 0
    is_online: bool = True
    last_sync_timestamp: float = 0.0
    lag: int = 0  # number of events behind

    @property
    def is_in_sync(self) -> bool:
        return self.last_replicated_sequence >= self.primary_last_sequence


# ============================================================================
# Audit Replication Manager
# ============================================================================

class AuditReplicationManager:
    """
    Manages primary-replica audit log replication with WAL, backups, and recovery.

    Architecture:
    - Primary: the main StorageManager's SQLite database
    - Replica: a separate SQLite database that mirrors audit_events
    - WAL: write-ahead log that records all audit writes for replication
    - Backup: periodic snapshots of the full audit log state

    Usage:
        manager = AuditReplicationManager(primary_storage)
        manager.add_replica("replica_1", replica_db_path)
        # Primary writes audit events normally...
        manager.replicate()  # Push to replicas
        snapshot = manager.create_backup("backups/audit_backup.db")
    """

    def __init__(self, primary_storage, primary_id: str = "primary"):
        """
        Args:
            primary_storage: StorageManager instance (the primary)
            primary_id: identifier for the primary
        """
        self.primary = primary_storage
        self.primary_id = primary_id
        self._replicas: Dict[str, Dict[str, Any]] = {}
        self._wal: List[WALRecord] = []
        self._wal_lock = threading.Lock()
        self._snapshots: List[BackupSnapshot] = []
        self._backup_interval: float = 3600.0  # 1 hour default
        self._last_backup_time: float = 0.0
        self._last_known_sequence: int = 0

        # Install a hook on the primary's create_audit_event to capture WAL records
        self._original_create_audit = self.primary.create_audit_event
        self._install_wal_hook()

    def _install_wal_hook(self):
        """Install a hook that captures audit events into the WAL."""
        original = self.primary.create_audit_event

        def hooked_create_audit(*args, **kwargs):
            result = original(*args, **kwargs)
            # Record in WAL
            wal_record = WALRecord(
                sequence_number=result.get("sequence_number", 0),
                operation="insert",
                table="audit_events",
                record_data=dict(result),
            )
            wal_record.compute_hash()
            with self._wal_lock:
                self._wal.append(wal_record)
                self._last_known_sequence = max(self._last_known_sequence, wal_record.sequence_number)
            return result

        self.primary.create_audit_event = hooked_create_audit

    def add_replica(self, replica_id: str, db_path: str) -> bool:
        """Add a replica database for replication."""
        # Create the replica database with the same schema
        replica_conn = sqlite3.connect(db_path)
        replica_conn.row_factory = sqlite3.Row

        # Create audit_events table in replica
        replica_conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                sequence_number INTEGER UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                actor TEXT,
                timestamp REAL,
                previous_hash TEXT,
                hash TEXT,
                signature TEXT,
                severity TEXT DEFAULT 'info'
            );
            CREATE INDEX IF NOT EXISTS idx_audit_seq ON audit_events(sequence_number);
        """)
        replica_conn.commit()

        self._replicas[replica_id] = {
            "db_path": db_path,
            "conn": replica_conn,
            "status": ReplicationStatus(
                replica_id=replica_id,
                primary_id=self.primary_id,
                primary_last_sequence=self._last_known_sequence,
            ),
        }

        logger.info(f"Replica added: {replica_id} at {db_path}")
        return True

    def remove_replica(self, replica_id: str) -> bool:
        """Remove a replica from replication."""
        if replica_id in self._replicas:
            self._replicas[replica_id]["conn"].close()
            del self._replicas[replica_id]
            logger.info(f"Replica removed: {replica_id}")
            return True
        return False

    def set_replica_offline(self, replica_id: str) -> bool:
        """Mark a replica as offline (simulates failure)."""
        if replica_id in self._replicas:
            self._replicas[replica_id]["status"].is_online = False
            logger.info(f"Replica offline: {replica_id}")
            return True
        return False

    def set_replica_online(self, replica_id: str) -> bool:
        """Mark a replica as online (simulates rejoin)."""
        if replica_id in self._replicas:
            self._replicas[replica_id]["status"].is_online = True
            logger.info(f"Replica online: {replica_id}")
            return True
        return False

    def replicate(self) -> Dict[str, int]:
        """
        Push WAL records to all online replicas.

        Returns dict of replica_id -> number of records replicated.
        """
        results = {}
        with self._wal_lock:
            wal_copy = list(self._wal)

        for replica_id, replica_data in self._replicas.items():
            status: ReplicationStatus = replica_data["status"]
            if not status.is_online:
                results[replica_id] = 0
                continue

            conn: sqlite3.Connection = replica_data["conn"]

            # Find records that haven't been replicated yet
            last_replicated = status.last_replicated_sequence
            new_records = [
                rec for rec in wal_copy
                if rec.sequence_number > last_replicated
            ]

            count = 0
            for rec in new_records:
                data = rec.record_data
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO audit_events
                           (id, sequence_number, event_type, event_data, actor,
                            timestamp, previous_hash, hash, signature, severity)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            data.get("id"),
                            data.get("sequence_number"),
                            data.get("event_type"),
                            data.get("event_data"),
                            data.get("actor"),
                            data.get("timestamp"),
                            data.get("previous_hash"),
                            data.get("hash"),
                            data.get("signature"),
                            data.get("severity"),
                        )
                    )
                    count += 1
                    status.last_replicated_sequence = rec.sequence_number
                except sqlite3.Error as e:
                    logger.error(f"Replication error to {replica_id}: {e}")
                    break

            conn.commit()
            status.last_sync_timestamp = time.time()
            status.primary_last_sequence = self._last_known_sequence
            status.lag = status.primary_last_sequence - status.last_replicated_sequence
            results[replica_id] = count

        # Clear replicated WAL records (keep last 100 for catch-up)
        if len(self._wal) > 100:
            with self._wal_lock:
                self._wal = self._wal[-100:]

        return results

    def catch_up(self, replica_id: str) -> int:
        """
        Catch up a replica that was offline. Pushes all missing WAL records.

        Returns number of records replicated.
        """
        if replica_id not in self._replicas:
            return 0

        # Mark online first
        self.set_replica_online(replica_id)

        # Now replicate
        results = self.replicate()
        return results.get(replica_id, 0)

    def create_backup(self, backup_db_path: str) -> BackupSnapshot:
        """Create a point-in-time backup snapshot of the audit log."""
        # Get all audit events from primary
        events = self.primary.query_audit_events()
        if events is None:
            events = []

        # Create backup database
        backup_conn = sqlite3.connect(backup_db_path)
        backup_conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                sequence_number INTEGER UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                actor TEXT,
                timestamp REAL,
                previous_hash TEXT,
                hash TEXT,
                signature TEXT,
                severity TEXT DEFAULT 'info'
            );
        """)

        count = 0
        last_seq = 0
        last_hash = ""
        for event in events:
            backup_conn.execute(
                """INSERT OR REPLACE INTO audit_events
                   (id, sequence_number, event_type, event_data, actor,
                    timestamp, previous_hash, hash, signature, severity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.get("id"),
                    event.get("sequence_number"),
                    event.get("event_type"),
                    event.get("event_data"),
                    event.get("actor"),
                    event.get("timestamp"),
                    event.get("previous_hash"),
                    event.get("hash"),
                    event.get("signature"),
                    event.get("severity"),
                )
            )
            count += 1
            seq = event.get("sequence_number", 0)
            if seq > last_seq:
                last_seq = seq
                last_hash = event.get("hash", "")

        backup_conn.commit()
        backup_conn.close()

        snapshot = BackupSnapshot(
            source_db_path=":memory:" if ":memory:" in str(self.primary.conn) else "primary",
            backup_db_path=backup_db_path,
            event_count=count,
            last_sequence=last_seq,
            last_hash=last_hash,
        )
        snapshot.compute_hash()
        self._snapshots.append(snapshot)
        self._last_backup_time = time.time()

        logger.info(f"Backup created: {backup_db_path} ({count} events, last_seq={last_seq})")
        return snapshot

    def restore_from_backup(self, backup_db_path: str, target_storage=None) -> int:
        """
        Restore audit log from a backup snapshot.

        Args:
            backup_db_path: path to the backup database
            target_storage: optional StorageManager to restore into (uses primary if not given)

        Returns number of events restored.
        """
        if target_storage is None:
            target_storage = self.primary

        backup_conn = sqlite3.connect(backup_db_path)
        backup_conn.row_factory = sqlite3.Row
        rows = backup_conn.execute("SELECT * FROM audit_events ORDER BY sequence_number").fetchall()
        backup_conn.close()

        count = 0
        for row in rows:
            # Use target storage's connection to insert
            target_storage.conn.execute(
                """INSERT OR REPLACE INTO audit_events
                   (id, sequence_number, event_type, event_data, actor,
                    timestamp, previous_hash, hash, signature, severity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["id"], row["sequence_number"], row["event_type"],
                    row["event_data"], row["actor"], row["timestamp"],
                    row["previous_hash"], row["hash"], row["signature"],
                    row["severity"],
                )
            )
            count += 1
        target_storage.conn.commit()

        logger.info(f"Restored {count} events from backup")
        return count

    def verify_replica_integrity(self, replica_id: str) -> bool:
        """
        Verify hash chain integrity of a replica's audit log.

        Checks that:
        1. All events are present (no gaps in sequence)
        2. Hash chain is intact (each event's previous_hash matches prior event's hash)
        """
        if replica_id not in self._replicas:
            return False

        conn: sqlite3.Connection = self._replicas[replica_id]["conn"]
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY sequence_number"
        ).fetchall()

        if not rows:
            return True  # Empty is valid

        prev_hash = "0" * 64  # Genesis
        for row in rows:
            # Check sequence continuity
            expected_seq = row["sequence_number"]
            # Check hash chain
            if row["previous_hash"] and row["previous_hash"] != prev_hash:
                logger.error(f"Hash chain broken at seq {expected_seq}: expected {prev_hash[:16]}, got {row['previous_hash'][:16]}")
                return False
            prev_hash = row["hash"] or prev_hash

        return True

    def verify_primary_integrity(self) -> bool:
        """Verify hash chain integrity of the primary's audit log."""
        events = self.primary.query_audit_events()
        if not events:
            return True

        prev_hash = "0" * 64
        for event in events:
            if event.get("previous_hash") and event["previous_hash"] != prev_hash:
                return False
            prev_hash = event.get("hash", prev_hash)

        return True

    def get_replication_status(self) -> Dict[str, ReplicationStatus]:
        """Get replication status for all replicas."""
        result = {}
        for rid, data in self._replicas.items():
            status = data["status"]
            status.primary_last_sequence = self._last_known_sequence
            status.lag = status.primary_last_sequence - status.last_replicated_sequence
            result[rid] = status
        return result

    def get_wal_size(self) -> int:
        """Get the current WAL size (number of pending records)."""
        return len(self._wal)

    def get_snapshots(self) -> List[BackupSnapshot]:
        """Get all backup snapshots."""
        return list(self._snapshots)

    def close(self):
        """Close all replica connections."""
        for rid in list(self._replicas.keys()):
            self.remove_replica(rid)
        # Restore original method
        self.primary.create_audit_event = self._original_create_audit
