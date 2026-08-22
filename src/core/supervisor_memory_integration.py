"""
ORION Phase 005 — CoreSupervisor Memory Integration. License: Apache 2.0.

Luna R1 Finding #7: Integrate memory hooks into CoreSupervisor.

This module provides the memory integration layer that is mixed into
the existing CoreSupervisor. It adds:
- Pre-planning recall (get_context_for_planning)
- Post-execution remember (success and failure paths)
- _build_observation() for structured memory writes
- Memory failure policy: log and continue (memory unavailable ≠ task failure)
- Correlation ID propagation via MemoryRequestContext
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.core.permission_engine import PermissionLevel
from src.memory.memory_permissions import MemoryRequestContext, SourceType

logger = logging.getLogger(__name__)


class MemoryIntegrationMixin:
    """
    Mixin providing memory lifecycle hooks for CoreSupervisor.

    Luna R1 #7: Memory is OPTIONAL — CoreSupervisor works without it.
    All memory operations are wrapped in try/except with a failure policy
    of "log and continue" — memory unavailability never blocks task execution.
    """

    def _init_memory(self, memory_manager: Optional[Any] = None) -> None:
        """Initialize optional memory integration."""
        self._memory = memory_manager
        self._memory_enabled = memory_manager is not None

    def _get_memory_context(
        self,
        goal: str,
        caller_context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        principal_id: str = "supervisor",
    ) -> Dict[str, Any]:
        """
        Retrieve memory context for planning and merge with caller context.

        Luna R1 #7: Use get_context_for_planning() (returns dict, not list).
        Luna R1 #8: Memory context is merged safely with caller context.
        """
        if not self._memory_enabled:
            return caller_context or {}

        try:
            ctx = MemoryRequestContext(
                principal_id=principal_id,
                task_id=correlation_id,
                source_type=SourceType.AGENT,
                permission_level=PermissionLevel.EXECUTE,
                correlation_id=correlation_id,
            )
            memory_ctx = self._memory.get_context_for_planning(goal, context=ctx)

            # Merge: caller context takes priority, memory adds supplementary info
            merged: Dict[str, Any] = {}
            if memory_ctx:
                merged.update(memory_ctx)
            if caller_context:
                merged.update(caller_context)  # caller overrides memory

            logger.debug("Memory context merged: %d keys", len(merged))
            return merged
        except Exception as e:
            # Luna R1 #7: Memory failure policy — log and continue
            logger.warning("Memory context retrieval failed (non-blocking): %s", e)
            return caller_context or {}

    def _remember_outcome(
        self,
        goal: str,
        task_id: str,
        success: bool,
        observations: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Store task outcome in memory after execution.

        Luna R1 #7: Remember on BOTH success and failure paths.
        Luna R1 #9: Planning failures, execution failures, and partial
        observations are all remembered.
        """
        if not self._memory_enabled:
            return

        try:
            obs = self._build_observation(
                goal=goal,
                task_id=task_id,
                success=success,
                observations=observations,
                error=error,
            )
            ctx = MemoryRequestContext(
                principal_id="supervisor",
                task_id=task_id,
                source_type=SourceType.AGENT,
                permission_level=PermissionLevel.EXECUTE,
                correlation_id=correlation_id,
            )
            result = self._memory.remember(obs, context=ctx)
            logger.info("Memory stored: task=%s, success=%s, stored=%s",
                        task_id, success, result.success if result else False)
        except Exception as e:
            # Luna R1 #7: Memory failure never blocks task completion
            logger.warning("Memory remember failed (non-blocking): %s", e)

    def _build_observation(
        self,
        goal: str,
        task_id: str,
        success: bool,
        observations: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a structured observation dict for memory storage.

        Luna R1 #9: _build_observation() is defined here, not assumed.
        Includes: goal, outcome, error (if any), timestamp, observations.
        """
        obs: Dict[str, Any] = {
            "goal": goal,
            "task_id": task_id,
            "success": success,
            "timestamp": time.time(),
        }
        if error:
            obs["error"] = error
        if observations:
            obs["details"] = observations
        if not success and error:
            obs["failure_reason"] = error
        return obs
