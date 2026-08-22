"""
ORION Phase 010 — Task Manager. License: Apache 2.0.

Creates, tracks, updates, and completes tasks.
Integrates with JARVISInterface for natural language task management.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ManagedTask:
    """A managed task in the JARVIS system."""
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    subtasks: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "subtasks": self.subtasks,
            "result": self.result,
            "metadata": self.metadata,
        }


class TaskManager:
    """Manages tasks for the JARVIS interface."""

    def __init__(self) -> None:
        self._tasks: Dict[str, ManagedTask] = {}
        self._counter = 0

    def create_task(self, description: str, priority: int = 0,
                    subtasks: Optional[List[str]] = None) -> ManagedTask:
        """Create a new task."""
        self._counter += 1
        task_id = f"task_{self._counter}"
        task = ManagedTask(
            id=task_id,
            description=description,
            priority=priority,
            subtasks=subtasks or [],
        )
        self._tasks[task_id] = task
        logger.info("Created task: %s — %s", task_id, description)
        return task

    def update_task(self, task_id: str, status: Optional[TaskStatus] = None,
                    result: Optional[Dict[str, Any]] = None) -> bool:
        """Update a task's status and/or result."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if status is not None:
            task.status = status
            task.updated_at = time.time()
        if result is not None:
            task.result = result
            task.updated_at = time.time()
        return True

    def get_task(self, task_id: str) -> Optional[ManagedTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[ManagedTask]:
        """List all tasks, optionally filtered by status."""
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        return True

    def get_pending(self) -> List[ManagedTask]:
        """Get all pending tasks."""
        return self.list_tasks(TaskStatus.PENDING)

    def get_in_progress(self) -> List[ManagedTask]:
        """Get all in-progress tasks."""
        return self.list_tasks(TaskStatus.IN_PROGRESS)

    def get_completed(self) -> List[ManagedTask]:
        """Get all completed tasks."""
        return self.list_tasks(TaskStatus.COMPLETED)

    def task_count(self) -> int:
        return len(self._tasks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tasks": len(self._tasks),
            "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
        }
