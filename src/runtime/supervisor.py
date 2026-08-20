"""
ORION RuntimeSupervisor — 24/7 Autonomous Operation Manager

The RuntimeSupervisor is the main loop of ORION's 24/7 operation:
1. Load state from last checkpoint
2. Find unfinished tasks
3. Schedule workers for pending tasks
4. Monitor worker health
5. Handle worker failures (restart/reassign)
6. Save checkpoints periodically
7. On shutdown: save state, log reason, prepare recommendation

Per 24/7 Policy:
- Worker isolation: single worker failure must NOT stop the whole system
- On stop: save state, record reason, prepare recommendation, set DECISION_REQUIRED
- On restart: load state → find unfinished → check checkpoint → verify → continue

License: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from runtime.worker import Worker, WorkerStatus, WorkerResult

logger = logging.getLogger(__name__)


class SupervisorStatus(str, Enum):
    """Status of the supervisor."""
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"
    EMERGENCY = "emergency"


class SupervisorState(str, Enum):
    """Internal state of the supervisor."""
    INITIALIZING = "initializing"
    LOADING_STATE = "loading_state"
    EXECUTING = "executing"
    CHECKPOINTING = "checkpointing"
    RECOVERING = "recovering"
    SHUTDOWN = "shutdown"
    DECISION_REQUIRED = "decision_required"


@dataclass
class SupervisorMetrics:
    """Metrics tracked by the supervisor."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    retried_tasks: int = 0
    worker_crashes: int = 0
    worker_timeouts: int = 0
    checkpoints_saved: int = 0
    uptime_seconds: float = 0.0
    last_checkpoint_time: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / self.total_tasks


@dataclass
class ScheduledTask:
    """A task scheduled for execution by the supervisor."""
    id: str
    name: str
    task_fn_name: str  # Name of the registered task function
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: int = 0  # Lower = higher priority
    timeout: float = 300.0
    max_retries: int = 3
    status: str = "pending"  # pending, running, completed, failed
    worker_id: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "task_fn_name": self.task_fn_name,
            "priority": self.priority,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "status": self.status,
            "worker_id": self.worker_id,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class RuntimeSupervisor:
    """
    24/7 Autonomous Operation Supervisor.

    Manages task scheduling, worker execution, health monitoring,
    checkpointing, and recovery.

    Usage:
        supervisor = RuntimeSupervisor(state_file="orion_state.json")
        supervisor.register_task_fn("simulate_vehicle", simulate_vehicle_fn)
        supervisor.schedule_task("task-1", "Vehicle simulation", "simulate_vehicle")
        supervisor.start()  # Runs main loop
    """

    def __init__(
        self,
        state_file: str = "orion_state.json",
        checkpoint_interval: float = 60.0,
        max_concurrent_workers: int = 4,
    ) -> None:
        self._state_file = state_file
        self._checkpoint_interval = checkpoint_interval
        self._max_concurrent_workers = max_concurrent_workers

        self._status: SupervisorStatus = SupervisorStatus.STOPPED
        self._state: SupervisorState = SupervisorState.INITIALIZING
        self._metrics = SupervisorMetrics()
        self._start_time: float = 0.0

        # Task management
        self._task_fns: Dict[str, Callable] = {}
        self._scheduled_tasks: Dict[str, ScheduledTask] = {}
        self._active_workers: Dict[str, Worker] = {}
        self._completed_results: List[WorkerResult] = []

        # Recovery info
        self._shutdown_reason: Optional[str] = None
        self._recovery_recommendation: Optional[str] = None

    @property
    def status(self) -> SupervisorStatus:
        return self._status

    @property
    def state(self) -> SupervisorState:
        return self._state

    @property
    def metrics(self) -> SupervisorMetrics:
        return self._metrics

    @property
    def uptime(self) -> float:
        if self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    @property
    def pending_tasks(self) -> List[ScheduledTask]:
        return sorted(
            [t for t in self._scheduled_tasks.values() if t.status == "pending"],
            key=lambda t: t.priority,
        )

    @property
    def running_tasks(self) -> List[ScheduledTask]:
        return [t for t in self._scheduled_tasks.values() if t.status == "running"]

    @property
    def completed_tasks(self) -> List[ScheduledTask]:
        return [t for t in self._scheduled_tasks.values() if t.status == "completed"]

    @property
    def failed_tasks(self) -> List[ScheduledTask]:
        return [t for t in self._scheduled_tasks.values() if t.status == "failed"]

    def register_task_fn(self, name: str, fn: Callable) -> None:
        """Register a callable that can be scheduled as a task."""
        self._task_fns[name] = fn
        logger.info(f"Registered task function: {name}")

    def schedule_task(
        self,
        task_id: str,
        name: str,
        task_fn_name: str,
        args: tuple = (),
        kwargs: Optional[dict] = None,
        priority: int = 0,
        timeout: float = 300.0,
        max_retries: int = 3,
    ) -> ScheduledTask:
        """Schedule a task for execution."""
        if task_fn_name not in self._task_fns:
            raise ValueError(f"Unknown task function: {task_fn_name}. Register it first.")

        task = ScheduledTask(
            id=task_id,
            name=name,
            task_fn_name=task_fn_name,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._scheduled_tasks[task_id] = task
        self._metrics.total_tasks += 1
        logger.info(f"Scheduled task: {task_id} ({name})")
        return task

    def start(self, max_steps: int = 0) -> None:
        """
        Start the supervisor main loop.

        Args:
            max_steps: Maximum number of task execution steps (0 = unlimited)
        """
        self._status = SupervisorStatus.STARTING
        self._start_time = time.time()
        self._metrics.uptime_seconds = 0.0

        # Try to load previous state
        if os.path.exists(self._state_file):
            self._state = SupervisorState.LOADING_STATE
            self._load_state()
            logger.info(f"Recovered state: {len(self._scheduled_tasks)} tasks, "
                        f"{len(self.pending_tasks)} pending, {len(self.completed_tasks)} completed")

        self._status = SupervisorStatus.RUNNING
        self._state = SupervisorState.EXECUTING
        logger.info("Supervisor started")

        # Main loop
        last_checkpoint = time.time()
        steps = 0

        while self._status == SupervisorStatus.RUNNING:
            # Check for pending tasks
            pending = self.pending_tasks
            if not pending:
                # No pending tasks — check if all done
                if not self.running_tasks:
                    logger.info("All tasks complete, supervisor idle")
                    break
                # Wait for running tasks
                self._collect_finished_workers()
                time.sleep(0.01)
                continue

            # Start workers for pending tasks (up to max concurrent)
            slots = self._max_concurrent_workers - len(self._active_workers)
            for task in pending[:slots]:
                self._start_worker(task)

            # Collect finished workers
            self._collect_finished_workers()

            # Periodic checkpoint
            if time.time() - last_checkpoint >= self._checkpoint_interval:
                self._state = SupervisorState.CHECKPOINTING
                self._save_state()
                self._metrics.checkpoints_saved += 1
                self._metrics.last_checkpoint_time = time.time()
                last_checkpoint = time.time()
                self._state = SupervisorState.EXECUTING

            # Update uptime
            self._metrics.uptime_seconds = self.uptime

            steps += 1
            if max_steps > 0 and steps >= max_steps:
                logger.info(f"Reached max_steps ({max_steps}), stopping")
                break

        # Final checkpoint
        self._save_state()
        self._status = SupervisorStatus.STOPPED
        self._state = SupervisorState.SHUTDOWN
        logger.info(f"Supervisor stopped. Metrics: {self._metrics.to_dict()}")

    def stop(self, reason: str = "manual") -> None:
        """Stop the supervisor gracefully."""
        self._shutdown_reason = reason
        self._status = SupervisorStatus.SHUTTING_DOWN

        # Stop active workers
        for worker in self._active_workers.values():
            worker.request_stop()

        # Collect any remaining results
        self._collect_finished_workers()

        # Save state
        self._save_state()

        # Prepare recovery recommendation
        pending = self.pending_tasks
        if pending:
            self._recovery_recommendation = (
                f"{len(pending)} tasks were pending when supervisor stopped. "
                f"Restart supervisor to resume execution."
            )

        self._status = SupervisorStatus.STOPPED
        logger.info(f"Supervisor stopped: {reason}")

    def emergency_stop(self, reason: str = "emergency") -> None:
        """Emergency stop — save state immediately and stop."""
        self._shutdown_reason = f"EMERGENCY: {reason}"
        self._status = SupervisorStatus.EMERGENCY
        self._save_state()
        logger.error(f"EMERGENCY STOP: {reason}")

    def _start_worker(self, task: ScheduledTask) -> None:
        """Start a worker for a task."""
        task_fn = self._task_fns.get(task.task_fn_name)
        if not task_fn:
            task.status = "failed"
            task.error = f"Unknown task function: {task.task_fn_name}"
            self._metrics.failed_tasks += 1
            return

        worker_id = f"worker-{task.id}-{uuid.uuid4().hex[:8]}"
        worker = Worker(
            worker_id=worker_id,
            task_fn=task_fn,
            args=task.args,
            kwargs=task.kwargs,
            timeout=task.timeout,
            max_retries=task.max_retries,
        )

        task.status = "running"
        task.started_at = time.time()
        task.worker_id = worker_id
        self._active_workers[worker_id] = worker

        # Run worker (synchronous — in a real system this would be async/threaded)
        result = worker.run()
        self._handle_worker_result(worker_id, task, result)

    def _collect_finished_workers(self) -> None:
        """Collect results from finished workers."""
        # In synchronous mode, workers finish immediately in _start_worker
        # This method is for future async mode
        finished = [wid for wid, w in self._active_workers.items() if w.is_finished]
        for wid in finished:
            worker = self._active_workers.pop(wid)
            # Find the task for this worker
            for task in self._scheduled_tasks.values():
                if task.worker_id == wid and task.status == "running":
                    self._handle_worker_result(wid, task, worker.result)
                    break

    def _handle_worker_result(self, worker_id: str, task: ScheduledTask, result: WorkerResult) -> None:
        """Handle the result of a worker execution."""
        task.completed_at = time.time()
        task.result = result.to_dict()
        self._active_workers.pop(worker_id, None)

        if result.success:
            task.status = "completed"
            self._metrics.completed_tasks += 1
            logger.info(f"Task {task.id} completed successfully")
        else:
            task.status = "failed"
            task.error = result.error
            self._metrics.failed_tasks += 1

            if result.status == WorkerStatus.TIMEOUT:
                self._metrics.worker_timeouts += 1
            elif result.status == WorkerStatus.CRASHED:
                self._metrics.worker_crashes += 1

            logger.warning(f"Task {task.id} failed: {result.error}")

        self._completed_results.append(result)

    def _save_state(self) -> None:
        """Save supervisor state to file for recovery."""
        state = {
            "status": self._status.value,
            "shutdown_reason": self._shutdown_reason,
            "recovery_recommendation": self._recovery_recommendation,
            "metrics": self._metrics.to_dict(),
            "uptime": self.uptime,
            "tasks": {tid: t.to_dict() for tid, t in self._scheduled_tasks.items()},
            "saved_at": time.time(),
        }
        tmp_file = self._state_file + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(state, f, indent=2)
        os.rename(tmp_file, self._state_file)  # Atomic write
        logger.debug(f"State saved to {self._state_file}")

    def _load_state(self) -> None:
        """Load supervisor state from file."""
        try:
            with open(self._state_file, "r") as f:
                state = json.load(f)

            self._shutdown_reason = state.get("shutdown_reason")
            self._recovery_recommendation = state.get("recovery_recommendation")

            # Restore metrics
            metrics = state.get("metrics", {})
            self._metrics.total_tasks = metrics.get("total_tasks", 0)
            self._metrics.completed_tasks = metrics.get("completed_tasks", 0)
            self._metrics.failed_tasks = metrics.get("failed_tasks", 0)
            self._metrics.checkpoints_saved = metrics.get("checkpoints_saved", 0)

            # Restore tasks
            for tid, tdata in state.get("tasks", {}).items():
                task = ScheduledTask(
                    id=tdata["id"],
                    name=tdata["name"],
                    task_fn_name=tdata["task_fn_name"],
                    priority=tdata.get("priority", 0),
                    timeout=tdata.get("timeout", 300.0),
                    max_retries=tdata.get("max_retries", 3),
                    status=tdata.get("status", "pending"),
                    worker_id=tdata.get("worker_id"),
                    result=tdata.get("result"),
                    error=tdata.get("error"),
                    created_at=tdata.get("created_at", time.time()),
                    started_at=tdata.get("started_at"),
                    completed_at=tdata.get("completed_at"),
                )
                # Reset running tasks to pending on recovery
                if task.status == "running":
                    task.status = "pending"
                    task.worker_id = None
                    logger.info(f"Recovered task {tid} (was running, reset to pending)")
                self._scheduled_tasks[tid] = task

            logger.info(f"Loaded state: {len(self._scheduled_tasks)} tasks")

        except Exception as e:
            logger.warning(f"Failed to load state from {self._state_file}: {e}")
            self._state = SupervisorState.INITIALIZING

    def get_health_status(self) -> dict:
        """Get current health status of the supervisor."""
        return {
            "status": self._status.value,
            "state": self._state.value,
            "uptime": self.uptime,
            "pending_tasks": len(self.pending_tasks),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "active_workers": len(self._active_workers),
            "success_rate": self._metrics.success_rate,
            "worker_crashes": self._metrics.worker_crashes,
            "worker_timeouts": self._metrics.worker_timeouts,
            "checkpoints_saved": self._metrics.checkpoints_saved,
        }

    def to_dict(self) -> dict:
        """Serialize full supervisor state."""
        return {
            "status": self._status.value,
            "state": self._state.value,
            "metrics": self._metrics.to_dict(),
            "uptime": self.uptime,
            "shutdown_reason": self._shutdown_reason,
            "recovery_recommendation": self._recovery_recommendation,
            "pending": len(self.pending_tasks),
            "running": len(self.running_tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "task_fns": list(self._task_fns.keys()),
        }
