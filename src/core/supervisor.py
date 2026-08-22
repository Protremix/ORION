"""
ORION Core Supervisor — Phase 004. License: Apache 2.0
Lifecycle: GOAL -> PLAN -> EXECUTE -> OBSERVE -> EVALUATE -> CORRECT -> REMEMBER
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.core.audit_logger import AuditEventType, AuditLogger
from src.core.error_recovery import ErrorRecovery, RecoveryAction
from src.core.execution_engine import ExecutionEngine
from src.core.model_gateway import ModelGateway
from src.core.policy_engine import PolicyDecision, PolicyEngine
from src.core.task_engine import StepStatus, Task, TaskEngine, TaskPriority, TaskStatus, TaskStep
from src.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

class CoreSupervisor:
    def __init__(self, task_engine: TaskEngine, tool_registry: ToolRegistry,
                 policy_engine: PolicyEngine, execution_engine: ExecutionEngine,
                 model_gateway: ModelGateway, audit_logger: AuditLogger,
                 error_recovery: ErrorRecovery) -> None:
        self._task_engine = task_engine
        self._tool_registry = tool_registry
        self._policy_engine = policy_engine
        self._execution_engine = execution_engine
        self._model_gateway = model_gateway
        self._audit = audit_logger
        self._recovery = error_recovery
        self._step_timeout: float = 120.0

    def run(self, goal: str, context: Optional[Dict[str, Any]] = None,
            model: Optional[str] = None) -> Task:
        ctx = context or {}
        task = self._task_engine.create_task(goal=goal, normalized_goal=goal.strip().lower(),
            priority=TaskPriority.NORMAL, model=model, context=ctx)
        self._audit.log(AuditEventType.TASK_CREATED, task.correlation_id,
            {"task_id": task.id, "goal": goal, "model": model})
        # PLAN
        self._task_engine.update_status(task.id, TaskStatus.PLANNING)
        self._audit.log(AuditEventType.STATE_TRANSITION, task.correlation_id,
            {"task_id": task.id, "from": "pending", "to": "planning"})
        available_tools = [t.name for t in self._tool_registry.list_tools()
                          if self._policy_engine.evaluate_tool(t.name, {}) == PolicyDecision.ALLOW]
        plan_response = self._model_gateway.generate_plan(goal=goal, available_tools=available_tools, model=model)
        self._audit.log(AuditEventType.MODEL_CALLED, task.correlation_id,
            {"task_id": task.id, "model": plan_response.model,
             "success": plan_response.success, "latency_ms": plan_response.latency_ms})
        if not plan_response.success or not plan_response.parsed:
            self._audit.log(AuditEventType.PLAN_REJECTED, task.correlation_id,
                {"task_id": task.id, "error": plan_response.error or "No plan generated"})
            self._task_engine.update_status(task.id, TaskStatus.FAILED)
            task.failure_reason = plan_response.error or "No plan generated"
            return task
        plan = plan_response.parsed
        self._task_engine.set_plan(task.id, plan)
        self._audit.log(AuditEventType.PLAN_GENERATED, task.correlation_id,
            {"task_id": task.id, "steps": len(plan.get("steps", []))})
        # Create steps
        for i, step_data in enumerate(plan.get("steps", [])):
            deps = []
            for d in step_data.get("dependencies", []):
                try:

                    deps.append(f"{task.id}_step_{int(d)+1}")
                except (ValueError, TypeError):

                    pass
            step = TaskStep(id=f"{task.id}_step_{i+1}",
                description=step_data.get("description", ""),
                action_type=step_data.get("action_type", ""),
                parameters=step_data.get("parameters", {}), dependencies=deps)
            self._task_engine.add_step(task.id, step)
        self._audit.log(AuditEventType.PLAN_VALIDATED, task.correlation_id,
            {"task_id": task.id, "step_count": len(plan.get("steps", []))})
        # EXECUTE
        self._task_engine.update_status(task.id, TaskStatus.EXECUTING)
        self._audit.log(AuditEventType.STATE_TRANSITION, task.correlation_id,
            {"task_id": task.id, "from": "planning", "to": "executing"})
        max_iterations = max(len(plan.get("steps", [])) * 3, 10)
        for iteration in range(max_iterations):
            ready_steps = self._task_engine.get_ready_steps(task.id)
            if not ready_steps:
                task = self._task_engine.get_task(task.id)
                if task and all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in task.steps):
                    break
                if task and any(s.status == StepStatus.FAILED for s in task.steps):
                    failed = [s for s in task.steps if s.status == StepStatus.FAILED]
                    if failed:
                        result = self._recovery.handle_step_failure(task.id, failed[-1].id, failed[-1].error or "Unknown")
                        self._audit.log(AuditEventType.RECOVERY, task.correlation_id,
                            {"task_id": task.id, "step_id": failed[-1].id,
                             "action": result.action.value, "success": result.success})
                        if result.action in (RecoveryAction.ESCALATE, RecoveryAction.ABORT):
                            break
                    continue
                break
            for step in ready_steps:
                self._execute_step(task, step)
        # EVALUATE
        task = self._task_engine.get_task(task.id)
        if task:
            if all(s.status == StepStatus.COMPLETED for s in task.steps):
                self._task_engine.update_status(task.id, TaskStatus.COMPLETED)
                self._audit.log(AuditEventType.TASK_COMPLETED, task.correlation_id,
                    {"task_id": task.id, "duration": task.duration})
            elif any(s.status == StepStatus.FAILED for s in task.steps):
                self._task_engine.update_status(task.id, TaskStatus.FAILED)
                self._audit.log(AuditEventType.TASK_FAILED, task.correlation_id,
                    {"task_id": task.id, "failed_steps": task.failed_steps})
            else:
                self._task_engine.update_status(task.id, TaskStatus.COMPLETED)
        return self._task_engine.get_task(task.id) or task

    def _execute_step(self, task: Task, step: Any) -> None:
        self._task_engine.update_step(task.id, step.id, StepStatus.RUNNING)
        self._audit.log(AuditEventType.TOOL_INVOKED, task.correlation_id,
            {"task_id": task.id, "step_id": step.id, "tool": step.action_type})
        result = self._execution_engine.execute(tool_name=step.action_type,
            args=step.parameters, task_id=task.id, timeout_override=self._step_timeout)
        if result.success:
            self._task_engine.update_step(task.id, step.id, StepStatus.COMPLETED, result=result.result)
            self._audit.log(AuditEventType.TOOL_RESULT, task.correlation_id,
                {"task_id": task.id, "step_id": step.id, "success": True, "latency_ms": result.latency_ms})
        else:
            self._task_engine.update_step(task.id, step.id, StepStatus.FAILED, error=result.error)
            self._audit.log(AuditEventType.TOOL_ERROR, task.correlation_id,
                {"task_id": task.id, "step_id": step.id, "error": result.error, "timed_out": result.timed_out})
