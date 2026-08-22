"""
ORION Core Execution Engine — Phase 004. License: Apache 2.0
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.core.policy_engine import PolicyDecision, PolicyEngine
from src.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

@dataclass
class ExecutionResult:
    success: bool
    tool_name: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    timed_out: bool = False
    rolled_back: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"success": self.success, "tool_name": self.tool_name, "result": self.result,
                "error": self.error, "latency_ms": round(self.latency_ms, 2),
                "timed_out": self.timed_out, "rolled_back": self.rolled_back, "timestamp": self.timestamp}

class ExecutionEngine:
    def __init__(self, tool_registry: ToolRegistry, policy_engine: PolicyEngine) -> None:
        self._tool_registry = tool_registry
        self._policy_engine = policy_engine
        self._cancel_flags: Dict[str, threading.Event] = {}

    def execute(self, tool_name: str, args: Dict[str, Any],
                task_id: Optional[str] = None, timeout_override: Optional[float] = None) -> ExecutionResult:
        start = time.time()
        decision = self._policy_engine.evaluate_tool(tool_name, args, task_id)
        if decision == PolicyDecision.DENY:
            return ExecutionResult(success=False, tool_name=tool_name,
                error=f"Denied by policy: {tool_name}", latency_ms=(time.time()-start)*1000)
        if decision == PolicyDecision.REQUIRE_APPROVAL:
            return ExecutionResult(success=False, tool_name=tool_name,
                error=f"Requires approval: {tool_name}", latency_ms=(time.time()-start)*1000)
        if decision == PolicyDecision.RATE_LIMITED:
            return ExecutionResult(success=False, tool_name=tool_name,
                error=f"Rate limited: {tool_name}", latency_ms=(time.time()-start)*1000)
        valid, error = self._tool_registry.validate_args(tool_name, args)
        if not valid:
            return ExecutionResult(success=False, tool_name=tool_name,
                error=f"Invalid arguments: {error}", latency_ms=(time.time()-start)*1000)
        tool = self._tool_registry.get(tool_name)
        if not tool or not tool.handler:
            return ExecutionResult(success=False, tool_name=tool_name,
                error=f"Tool has no handler: {tool_name}", latency_ms=(time.time()-start)*1000)
        timeout = timeout_override or tool.timeout
        result_box: Dict[str, Any] = {}
        exec_id = f"{task_id or 'adhoc'}_{tool_name}_{start}"
        def _run():
            try:
                result_box["output"] = tool.handler(**args)
                result_box["success"] = True
            except Exception as e:
                result_box["error"] = str(e)
                result_box["traceback"] = traceback.format_exc()
                result_box["success"] = False
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        latency_ms = (time.time()-start)*1000
        timed_out = thread.is_alive()
        self._cancel_flags.pop(exec_id, None)
        if timed_out:
            rolled_back = False
            if tool.rollback:
                try:

                    rolled_back = tool.rollback()
                except Exception as e:

                    logger.error(f"Rollback failed for {tool_name}: {e}")
            return ExecutionResult(success=False, tool_name=tool_name,
                error=f"Timed out after {timeout}s", latency_ms=latency_ms,
                timed_out=True, rolled_back=rolled_back)
        if result_box.get("success"):
            output = result_box.get("output")
            return ExecutionResult(success=True, tool_name=tool_name,
                result={"output": output} if not isinstance(output, dict) else output, latency_ms=latency_ms)
        else:
            rolled_back = False
            if tool.rollback:
                try:

                    rolled_back = tool.rollback()
                except Exception as e:

                    logger.error(f"Rollback failed for {tool_name}: {e}")
            return ExecutionResult(success=False, tool_name=tool_name,
                error=result_box.get("error", "Unknown error"), latency_ms=latency_ms, rolled_back=rolled_back)

    def cancel(self, exec_id: str) -> bool:
        event = self._cancel_flags.get(exec_id)
        if event:
            event.set()
        return True
        return False
