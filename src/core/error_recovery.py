"""
ORION Core Error Recovery — Phase 004. License: Apache 2.0
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.core.task_engine import StepStatus, Task, TaskEngine, TaskStatus

logger = logging.getLogger(__name__)

class RecoveryAction(str, Enum):
    RETRY = "retry"
    ALTERNATE_PLAN = "alternate_plan"
    SKIP_STEP = "skip_step"
    ESCALATE = "escalate"
    ABORT = "abort"
    NO_ACTION = "no_action"

@dataclass
class RecoveryResult:
    action: RecoveryAction
    success: bool
    message: str
    retry_count: int = 0
    timestamp: float = field(default_factory=time.time)

class ErrorRecovery:
    def __init__(self, task_engine: TaskEngine) -> None:
        self._task_engine = task_engine
        self._recovery_history: List[RecoveryResult] = []
        self._max_retries = 3
        self._backoff_base = 1.0

    def handle_step_failure(self, task_id: str, step_id: str, error: str,
                            is_critical: bool = False) -> RecoveryResult:
        task = self._task_engine.get_task(task_id)
        if not task:
            return RecoveryResult(action=RecoveryAction.ABORT, success=False, message=f"Task not found: {task_id}")
        step = next((s for s in task.steps if s.id == step_id), None)
        if not step:
            return RecoveryResult(action=RecoveryAction.ABORT, success=False, message=f"Step not found: {step_id}")
        if step.retry_count < step.max_retries:
            retry_count = step.retry_count + 1
            backoff = self._backoff_base * (2 ** (retry_count - 1))
            logger.info(f"Retrying step {step_id} in {backoff:.1f}s (attempt {retry_count})")
            success = self._task_engine.retry_step(task_id, step_id)
            result = RecoveryResult(action=RecoveryAction.RETRY, success=success,
                message=f"Retry scheduled (attempt {retry_count}, backoff={backoff:.1f}s)", retry_count=retry_count)
            self._recovery_history.append(result)
            return result
        if not is_critical:
            success = self._task_engine.update_step(task_id, step_id, StepStatus.SKIPPED,
                error=f"Skipped after {step.retry_count} retries: {error}")
            result = RecoveryResult(action=RecoveryAction.SKIP_STEP, success=success,
                message=f"Non-critical step skipped after {step.retry_count} retries")
            self._recovery_history.append(result)
            return result
        self._task_engine.update_status(task_id, TaskStatus.FAILED)
        self._task_engine.update_step(task_id, step_id, StepStatus.FAILED, error=error)
        result = RecoveryResult(action=RecoveryAction.ESCALATE, success=False,
            message=f"Critical step failed after {step.retry_count} retries: {error}")
        self._recovery_history.append(result)
        return result

    def handle_model_failure(self, task_id: str, model_name: str, error: str) -> RecoveryResult:
        logger.warning(f"Model {model_name} failed for task {task_id}: {error}")
        result = RecoveryResult(action=RecoveryAction.ALTERNATE_PLAN, success=True,
            message=f"Model gateway fallback triggered for {model_name}")
        self._recovery_history.append(result)
        return result

    def get_history(self) -> List[RecoveryResult]:
        return list(self._recovery_history)

    def to_dict(self) -> dict:
        return {"max_retries": self._max_retries, "backoff_base": self._backoff_base,
                "history_count": len(self._recovery_history),
                "recent": [{"action": r.action.value, "success": r.success, "message": r.message}
                           for r in self._recovery_history[-10:]]}
