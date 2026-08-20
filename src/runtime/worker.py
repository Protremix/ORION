"""
ORION Worker — Isolated Task Execution

Each worker runs a single task in isolation. If a worker crashes or times out,
the supervisor catches the failure and can restart or reassign the task.

Worker isolation: a single worker failure must NOT stop the whole system.

License: Apache 2.0
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    """Status of a worker."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CRASHED = "crashed"


@dataclass
class WorkerResult:
    """Result of a worker execution."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    worker_id: str = ""
    status: WorkerStatus = WorkerStatus.COMPLETED

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "worker_id": self.worker_id,
            "status": self.status.value,
        }


class Worker:
    """
    Isolated worker that executes a single task.

    A worker:
    - Runs a callable (task function) with optional arguments
    - Has a timeout (default 300 seconds)
    - Catches all exceptions (crash isolation)
    - Reports result back to supervisor
    - Can be stopped gracefully
    """

    def __init__(
        self,
        worker_id: str,
        task_fn: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        timeout: float = 300.0,
        max_retries: int = 3,
    ) -> None:
        self.worker_id = worker_id
        self.task_fn = task_fn
        self.args = args
        self.kwargs = kwargs or {}
        self.timeout = timeout
        self.max_retries = max_retries

        self._status: WorkerStatus = WorkerStatus.IDLE
        self._result: Optional[WorkerResult] = None
        self._start_time: float = 0.0
        self._end_time: float = 0.0
        self._retries: int = 0
        self._stop_requested: bool = False

    @property
    def status(self) -> WorkerStatus:
        return self._status

    @property
    def result(self) -> Optional[WorkerResult]:
        return self._result

    @property
    def is_running(self) -> bool:
        return self._status == WorkerStatus.RUNNING

    @property
    def is_finished(self) -> bool:
        return self._status in (WorkerStatus.COMPLETED, WorkerStatus.FAILED, WorkerStatus.TIMEOUT, WorkerStatus.CRASHED)

    @property
    def elapsed_time(self) -> float:
        if self._start_time == 0:
            return 0.0
        end = self._end_time if self._end_time > 0 else time.time()
        return end - self._start_time

    def request_stop(self) -> None:
        """Request the worker to stop gracefully."""
        self._stop_requested = True

    def run(self) -> WorkerResult:
        """
        Run the task with crash isolation.

        Catches all exceptions. Returns WorkerResult.
        Does NOT re-raise — the whole point is isolation.
        """
        self._status = WorkerStatus.RUNNING
        self._start_time = time.time()

        while self._retries <= self.max_retries:
            try:
                if self._stop_requested:
                    self._status = WorkerStatus.FAILED
                    self._end_time = time.time()
                    self._result = WorkerResult(
                        success=False,
                        error="Worker stopped by request",
                        execution_time=self.elapsed_time,
                        worker_id=self.worker_id,
                        status=WorkerStatus.FAILED,
                    )
                    return self._result

                # Execute with timeout check
                result = self._execute_with_timeout()

                if result is not None and isinstance(result, WorkerResult) and not result.success:
                    raise RuntimeError(result.error or "Worker returned failure")

                self._status = WorkerStatus.COMPLETED
                self._end_time = time.time()
                self._result = WorkerResult(
                    success=True,
                    result=result,
                    execution_time=self.elapsed_time,
                    worker_id=self.worker_id,
                    status=WorkerStatus.COMPLETED,
                )
                logger.info(f"Worker {self.worker_id} completed in {self.elapsed_time:.2f}s")
                return self._result

            except TimeoutError:
                self._retries += 1
                logger.warning(f"Worker {self.worker_id} timed out (attempt {self._retries}/{self.max_retries})")
                if self._retries > self.max_retries:
                    self._status = WorkerStatus.TIMEOUT
                    self._end_time = time.time()
                    self._result = WorkerResult(
                        success=False,
                        error=f"Worker timed out after {self.timeout}s (retried {self._retries} times)",
                        execution_time=self.elapsed_time,
                        worker_id=self.worker_id,
                        status=WorkerStatus.TIMEOUT,
                    )
                    return self._result
                continue

            except Exception as e:
                self._retries += 1
                tb = traceback.format_exc()
                logger.error(f"Worker {self.worker_id} crashed (attempt {self._retries}/{self.max_retries}): {e}\n{tb}")
                if self._retries > self.max_retries:
                    self._status = WorkerStatus.CRASHED
                    self._end_time = time.time()
                    self._result = WorkerResult(
                        success=False,
                        error=f"{type(e).__name__}: {e}",
                        execution_time=self.elapsed_time,
                        worker_id=self.worker_id,
                        status=WorkerStatus.CRASHED,
                    )
                    return self._result
                continue

        # Should not reach here, but just in case
        self._status = WorkerStatus.FAILED
        self._end_time = time.time()
        self._result = WorkerResult(
            success=False,
            error="Worker exhausted retries",
            execution_time=self.elapsed_time,
            worker_id=self.worker_id,
            status=WorkerStatus.FAILED,
        )
        return self._result

    def _execute_with_timeout(self) -> Any:
        """
        Execute the task function.

        Note: True thread-based timeout would require threading.
        For now, we rely on the task_fn to check _stop_requested
        and respect the timeout. The supervisor tracks elapsed time
        and can mark workers as timed out externally.
        """
        if self._stop_requested:
            raise RuntimeError("Worker stopped before execution")

        # Simple execution — the supervisor handles timeout externally
        return self.task_fn(*self.args, **self.kwargs)

    def to_dict(self) -> dict:
        """Serialize worker state for persistence."""
        return {
            "worker_id": self.worker_id,
            "status": self._status.value,
            "elapsed_time": self.elapsed_time,
            "retries": self._retries,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "stop_requested": self._stop_requested,
            "result": self._result.to_dict() if self._result else None,
        }
