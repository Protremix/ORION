"""
ORION Core Task Engine — Phase 004

Task lifecycle management: creation, steps, dependencies, retry, cancel, pause, resume.
Idempotency and duplicate-execution protection.

License: Apache 2.0
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    READY = "ready"
    EXECUTING = "executing"
    OBSERVING = "observing"
    EVALUATING = "evaluating"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    CRASHED = "crashed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskStep:
    id: str
    description: str
    action_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "description": self.description,
            "action_type": self.action_type, "status": self.status.value,
            "dependencies": self.dependencies, "result": self.result,
            "error": self.error, "retry_count": self.retry_count,
            "duration": self.duration,
        }


@dataclass
class Task:
    id: str
    goal: str
    normalized_goal: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    steps: List[TaskStep] = field(default_factory=list)
    model: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    failure_reason: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "goal": self.goal, "normalized_goal": self.normalized_goal,
            "status": self.status.value, "priority": self.priority.value,
            "steps": [s.to_dict() for s in self.steps], "model": self.model,
            "correlation_id": self.correlation_id, "created_at": self.created_at,
            "updated_at": self.updated_at, "started_at": self.started_at,
            "completed_at": self.completed_at, "failure_reason": self.failure_reason,
            "completed_steps": self.completed_steps, "failed_steps": self.failed_steps,
            "total_steps": len(self.steps), "duration": self.duration,
            "metadata": self.metadata,
        }


class TaskEngine:
    """Task lifecycle management with idempotency, dependencies, retry, cancel, pause, resume."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}
        self._idempotency_index: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"task_{self._counter}"

    def create_task(self, goal: str, normalized_goal: Optional[str] = None,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    steps: Optional[List[TaskStep]] = None,
                    model: Optional[str] = None, context: Optional[Dict[str, Any]] = None,
                    idempotency_key: Optional[str] = None,
                    parent_task_id: Optional[str] = None) -> Task:
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_index:
                existing_id = self._idempotency_index[idempotency_key]
                logger.info(f"Idempotent task creation: {idempotency_key} -> {existing_id}")
                return self._tasks[existing_id]
            task = Task(id=self._next_id(), goal=goal, normalized_goal=normalized_goal,
                       priority=priority, steps=steps or [], model=model,
                       context=context or {}, idempotency_key=idempotency_key,
                       parent_task_id=parent_task_id)
            self._tasks[task.id] = task
            if idempotency_key:
                self._idempotency_index[idempotency_key] = task.id
            logger.info(f"Created task {task.id}: {goal[:80]}")
            return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def update_status(self, task_id: str, status: TaskStatus) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.status = status
            task.updated_at = time.time()
            if status == TaskStatus.EXECUTING and not task.started_at:
                task.started_at = time.time()
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task.completed_at = time.time()
            return True

    def set_plan(self, task_id: str, plan: Dict[str, Any]) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.plan = plan
            task.updated_at = time.time()
            return True

    def add_step(self, task_id: str, step: TaskStep) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.steps.append(step)
            task.updated_at = time.time()
            return True

    def update_step(self, task_id: str, step_id: str, status: StepStatus,
                    result: Optional[Dict] = None, error: Optional[str] = None) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            for step in task.steps:
                if step.id == step_id:
                    step.status = status
                    if result is not None:
                        step.result = result
                    if error is not None:
                        step.error = error
                    if status == StepStatus.RUNNING and not step.started_at:
                        step.started_at = time.time()
                    if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                        step.completed_at = time.time()
                    task.updated_at = time.time()
                    return True
            return False

    def get_ready_steps(self, task_id: str) -> List[TaskStep]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return []
            completed_ids = {s.id for s in task.steps if s.status == StepStatus.COMPLETED}
            ready = []
            for step in task.steps:
                if step.status != StepStatus.PENDING:
                    continue
                if all(dep in completed_ids for dep in step.dependencies):
                    ready.append(step)
            return ready

    def cancel(self, task_id: str, reason: str = "") -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
                return False
            task.status = TaskStatus.CANCELLED
            task.failure_reason = reason
            task.completed_at = time.time()
            task.updated_at = time.time()
            for step in task.steps:
                if step.status == StepStatus.RUNNING:
                    step.status = StepStatus.SKIPPED
                    step.completed_at = time.time()
            logger.info(f"Cancelled task {task_id}: {reason}")
            return True

    def pause(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status not in (TaskStatus.EXECUTING, TaskStatus.PLANNING, TaskStatus.PENDING):
                return False
            task.status = TaskStatus.PAUSED
            task.updated_at = time.time()
            return True

    def resume(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status != TaskStatus.PAUSED:
                return False
            if task.steps and all(s.status == StepStatus.COMPLETED for s in task.steps):
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
            else:
                task.status = TaskStatus.EXECUTING
            task.updated_at = time.time()
            return True

    def retry_step(self, task_id: str, step_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            for step in task.steps:
                if step.id == step_id and step.status == StepStatus.FAILED:
                    if step.retry_count >= step.max_retries:
                        logger.warning(f"Step {step_id} exceeded max_retries ({step.max_retries})")
                        return False
                    step.retry_count += 1
                    step.status = StepStatus.PENDING
                    step.error = None
                    step.result = None
                    step.started_at = None
                    step.completed_at = None
                    task.updated_at = time.time()
                    logger.info(f"Retrying step {step_id} (attempt {step.retry_count + 1})")
                    return True
            return False

    def get_all_tasks(self) -> List[Task]:
        with self._lock:
            return list(self._tasks.values())

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        with self._lock:
            return [t for t in self._tasks.values() if t.status == status]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
                "counter": self._counter,
                "idempotency_index": dict(self._idempotency_index),
            }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        with self._lock:
            self._counter = snapshot.get("counter", 0)
            self._idempotency_index = snapshot.get("idempotency_index", {})
            for tid, task_data in snapshot.get("tasks", {}).items():
                if tid not in self._tasks:
                    task = Task(id=tid, goal=task_data.get("goal", "unknown"),
                               status=TaskStatus.CRASHED, failure_reason="Lost in crash recovery")
                    task.metadata = task_data.get("metadata", {})
                    self._tasks[tid] = task
