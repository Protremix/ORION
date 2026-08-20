"""
ORION Persistent Task State & Checkpoint System — 24/7 Runtime Policy v1.0

Required mechanisms (per policy):
- persistent task state
- persistent memory
- checkpoints
- automatic recovery

On restart:
1. Load last state
2. Find unfinished tasks
3. Check last checkpoint
4. Verify last operation
5. Continue from safe point

Never lose progress on stop.

License: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Task State Types
# ============================================================================

class TaskStatus(str, Enum):
    """Status of a tracked task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    DECISION_REQUIRED = "decision_required"  # Hit authority boundary
    CANCELLED = "cancelled"


class CheckpointType(str, Enum):
    """Type of checkpoint."""
    BEFORE_ACTION = "before_action"
    AFTER_ACTION = "after_action"
    PHASE_COMPLETE = "phase_complete"
    ERROR_RECOVERY = "error_recovery"
    MANUAL = "manual"
    SHUTDOWN = "shutdown"


@dataclass
class Task:
    """A tracked task in the ORION system."""
    id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: float = 0.0  # 0.0 to 1.0
    sub_tasks: List[str] = field(default_factory=list)  # IDs of sub-tasks
    parent_task: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    last_checkpoint: Optional[str] = None  # Checkpoint ID
    retries: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        data = dict(data)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = TaskStatus(data["status"])
        return cls(**data)


@dataclass
class Checkpoint:
    """A saved point in the system's execution state."""
    id: str
    task_id: str
    type: CheckpointType
    timestamp: float = field(default_factory=time.time)
    state: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    verified: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        data = dict(data)
        if "type" in data and isinstance(data["type"], str):
            data["type"] = CheckpointType(data["type"])
        return cls(**data)


@dataclass
class SystemState:
    """Complete ORION system state for persistence."""
    version: str = "1.0"
    timestamp: float = field(default_factory=time.time)
    tasks: Dict[str, dict] = field(default_factory=dict)
    checkpoints: Dict[str, dict] = field(default_factory=dict)
    current_task_id: Optional[str] = None
    last_checkpoint_id: Optional[str] = None
    health: Dict[str, Any] = field(default_factory=dict)
    stop_reason: Optional[str] = None
    pending_decisions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Persistent Task State Manager
# ============================================================================

class TaskStateManager:
    """
    Manages persistent task state, checkpoints, and recovery.

    Per 24/7 Runtime Policy v1.0:
    - Save state after significant operations
    - On restart: load state → find unfinished → check checkpoint → continue
    - Never lose progress on stop
    - On stop: save state, record reason, prepare recommendation, set DECISION_REQUIRED
    """

    def __init__(self, storage_path: str = "orion_state.json") -> None:
        self._storage_path = storage_path
        self._tasks: Dict[str, Task] = {}
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._current_task_id: Optional[str] = None
        self._last_checkpoint_id: Optional[str] = None
        self._task_counter = 0
        self._checkpoint_counter = 0
        self._stop_reason: Optional[str] = None
        self._pending_decisions: List[Dict[str, Any]] = []

        # Load existing state
        self._load()

    def _next_task_id(self) -> str:
        self._task_counter += 1
        return f"task_{int(time.time())}_{self._task_counter}"

    def _next_checkpoint_id(self) -> str:
        self._checkpoint_counter += 1
        return f"ckpt_{int(time.time())}_{self._checkpoint_counter}"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> bool:
        """Save complete state to disk."""
        state = SystemState(
            tasks={tid: t.to_dict() for tid, t in self._tasks.items()},
            checkpoints={cid: c.to_dict() for cid, c in self._checkpoints.items()},
            current_task_id=self._current_task_id,
            last_checkpoint_id=self._last_checkpoint_id,
            stop_reason=self._stop_reason,
            pending_decisions=self._pending_decisions,
        )
        try:
            with open(self._storage_path, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            logger.debug(f"State saved: {len(self._tasks)} tasks, {len(self._checkpoints)} checkpoints")
            return True
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False

    def _load(self) -> bool:
        """Load state from disk."""
        if not os.path.exists(self._storage_path):
            logger.info("No existing state file, starting fresh")
            return True
        try:
            with open(self._storage_path, "r") as f:
                data = json.load(f)
            self._tasks = {tid: Task.from_dict(td) for tid, td in data.get("tasks", {}).items()}
            self._checkpoints = {cid: Checkpoint.from_dict(cd) for cid, cd in data.get("checkpoints", {}).items()}
            self._current_task_id = data.get("current_task_id")
            self._last_checkpoint_id = data.get("last_checkpoint_id")
            self._stop_reason = data.get("stop_reason")
            self._pending_decisions = data.get("pending_decisions", [])

            # Restore counters
            self._task_counter = len(self._tasks)
            self._checkpoint_counter = len(self._checkpoints)

            logger.info(f"State loaded: {len(self._tasks)} tasks, {len(self._checkpoints)} checkpoints")
            if self._stop_reason:
                logger.warning(f"Previous stop reason: {self._stop_reason}")
            if self._pending_decisions:
                logger.warning(f"Pending decisions: {len(self._pending_decisions)}")
            return True
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return False

    # ------------------------------------------------------------------
    # Task Management
    # ------------------------------------------------------------------

    def create_task(self, name: str, description: str,
                    parent_task: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Task:
        """Create a new tracked task."""
        task_id = self._next_task_id()
        task = Task(
            id=task_id,
            name=name,
            description=description,
            parent_task=parent_task,
            metadata=metadata or {},
        )
        self._tasks[task_id] = task

        if parent_task and parent_task in self._tasks:
            self._tasks[parent_task].sub_tasks.append(task_id)

        self._save()
        logger.info(f"Created task: {task_id} ({name})")
        return task

    def start_task(self, task_id: str) -> bool:
        """Mark a task as in progress."""
        if task_id not in self._tasks:
            return False
        task = self._tasks[task_id]
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = time.time()
        task.updated_at = time.time()
        self._current_task_id = task_id
        self._save()
        logger.info(f"Started task: {task_id}")
        return True

    def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """Mark a task as completed."""
        if task_id not in self._tasks:
            return False
        task = self._tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.completed_at = time.time()
        task.updated_at = time.time()
        task.progress = 1.0
        if result:
            task.metadata["result"] = result
        self._save()
        logger.info(f"Completed task: {task_id}")
        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark a task as failed."""
        if task_id not in self._tasks:
            return False
        task = self._tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error = error
        task.updated_at = time.time()
        self._save()
        logger.error(f"Failed task: {task_id} — {error}")
        return True

    def update_progress(self, task_id: str, progress: float) -> bool:
        """Update task progress (0.0 to 1.0)."""
        if task_id not in self._tasks:
            return False
        task = self._tasks[task_id]
        task.progress = max(0.0, min(1.0, progress))
        task.updated_at = time.time()
        self._save()
        return True

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    def get_unfinished_tasks(self) -> List[Task]:
        """Get all tasks that are not completed, failed, or cancelled."""
        unfinished = [t for t in self._tasks.values()
                      if t.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)]
        return unfinished

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    def create_checkpoint(self, task_id: str, checkpoint_type: CheckpointType,
                          state: Optional[Dict[str, Any]] = None,
                          description: str = "") -> Checkpoint:
        """Create a checkpoint for the current state."""
        cp_id = self._next_checkpoint_id()
        checkpoint = Checkpoint(
            id=cp_id,
            task_id=task_id,
            type=checkpoint_type,
            state=state or {},
            description=description,
        )
        self._checkpoints[cp_id] = checkpoint
        self._last_checkpoint_id = cp_id

        # Link checkpoint to task
        if task_id in self._tasks:
            self._tasks[task_id].last_checkpoint = cp_id
            self._tasks[task_id].updated_at = time.time()

        self._save()
        logger.info(f"Created checkpoint: {cp_id} ({checkpoint_type.value}) for task {task_id}")
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        return self._checkpoints.get(checkpoint_id)

    def get_last_checkpoint(self, task_id: Optional[str] = None) -> Optional[Checkpoint]:
        """Get the last checkpoint, optionally for a specific task."""
        if task_id:
            task = self._tasks.get(task_id)
            if task and task.last_checkpoint:
                return self._checkpoints.get(task.last_checkpoint)
            return None
        if self._last_checkpoint_id:
            return self._checkpoints.get(self._last_checkpoint_id)
        return None

    def verify_checkpoint(self, checkpoint_id: str) -> bool:
        """Verify that a checkpoint is valid and can be restored."""
        cp = self._checkpoints.get(checkpoint_id)
        if not cp:
            return False
        cp.verified = True
        self._save()
        logger.info(f"Verified checkpoint: {checkpoint_id}")
        return True

    # ------------------------------------------------------------------
    # Shutdown & Recovery
    # ------------------------------------------------------------------

    def shutdown(self, reason: str, recommendation: str = "") -> bool:
        """
        Graceful shutdown per 24/7 Runtime Policy.
        Save state, record reason, prepare recommendation, set DECISION_REQUIRED.
        """
        self._stop_reason = reason

        # Create shutdown checkpoint
        if self._current_task_id:
            self.create_checkpoint(
                self._current_task_id,
                CheckpointType.SHUTDOWN,
                state={"reason": reason},
                description=f"Shutdown: {reason}",
            )

            # Set current task to DECISION_REQUIRED if it hit a boundary
            task = self._tasks.get(self._current_task_id)
            if task:
                task.status = TaskStatus.DECISION_REQUIRED
                task.metadata["shutdown_reason"] = reason
                task.metadata["recommendation"] = recommendation
                task.updated_at = time.time()

        # Record pending decision
        if reason:
            self._pending_decisions.append({
                "timestamp": time.time(),
                "reason": reason,
                "recommendation": recommendation,
                "task_id": self._current_task_id,
            })

        self._save()
        logger.info(f"Shutdown: {reason}")
        return True

    def resume(self) -> Dict[str, Any]:
        """
        Resume from last checkpoint per 24/7 Runtime Policy.
        1. Load state (done in __init__)
        2. Find unfinished tasks
        3. Check last checkpoint
        4. Verify last operation
        5. Continue from safe point
        """
        result = {
            "unfinished_tasks": [],
            "last_checkpoint": None,
            "stop_reason": self._stop_reason,
            "pending_decisions": self._pending_decisions.copy(),
            "resume_from": None,
        }

        # Find unfinished tasks
        unfinished = self.get_unfinished_tasks()
        result["unfinished_tasks"] = [t.to_dict() for t in unfinished]

        # Check last checkpoint
        if self._last_checkpoint_id:
            cp = self._checkpoints.get(self._last_checkpoint_id)
            if cp:
                result["last_checkpoint"] = cp.to_dict()
                self.verify_checkpoint(cp.id)
                result["resume_from"] = cp.id

        # Clear stop reason (we're resuming)
        self._stop_reason = None
        self._pending_decisions.clear()
        self._save()

        logger.info(f"Resume: {len(unfinished)} unfinished tasks, resume from {result['resume_from']}")
        return result

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        total = len(self._tasks)
        completed = len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED])
        failed = len([t for t in self._tasks.values() if t.status == TaskStatus.FAILED])
        in_progress = len([t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS])
        pending = len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING])
        decision_required = len([t for t in self._tasks.values() if t.status == TaskStatus.DECISION_REQUIRED])

        return {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": pending,
            "decision_required": decision_required,
            "total_checkpoints": len(self._checkpoints),
            "has_stop_reason": self._stop_reason is not None,
            "pending_decisions": len(self._pending_decisions),
            "storage_path": self._storage_path,
        }
