"""
ORION Phase 009 — Verification Agent. License: Apache 2.0.

Specialist agent for result validation, test execution, and quality checks.
Verifies outputs from other agents before results are accepted.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.api import AgentDescriptor, AgentProtocol, AgentResult, AgentRole, AgentTask

logger = logging.getLogger(__name__)


class VerificationAgent(AgentProtocol):
    """Specialist agent for verifying other agents' results."""

    def __init__(self) -> None:
        self._task_count = 0
        self._total_latency = 0.0
        self._verification_count = 0
        self._passed_count = 0

    def get_descriptor(self) -> AgentDescriptor:
        return AgentDescriptor(
            agent_id="verification-agent",
            name="Verification Agent",
            role=AgentRole.EVALUATION,
            capabilities=["result_validation", "test_execution", "quality_checks", "consistency_verification"],
            permissions=["read"],
            tools=["test_runner", "validator", "comparator"],
            safety_level="SC_3",
            max_concurrent_tasks=2,
        )

    def execute_task(self, task: AgentTask) -> AgentResult:
        start = time.time()
        self._task_count += 1
        self._verification_count += 1

        operation = task.input_data.get("operation", "validate")
        target_result = task.input_data.get("result", {})
        expected = task.input_data.get("expected", None)
        agent_id = task.input_data.get("agent_id", "unknown")

        verification = self._verify(operation, target_result, expected, agent_id)

        if verification["verified"]:
            self._passed_count += 1

        elapsed = time.time() - start
        self._total_latency += elapsed

        return AgentResult(
            task_id=task.task_id,
            agent_id="verification-agent",
            success=True,
            output=verification,
            duration_seconds=elapsed,
            metadata={"agent": "verification", "operation": operation, "verified": verification["verified"]},
        )

    def get_capabilities(self) -> List[str]:
        return ["result_validation", "test_execution", "quality_checks", "consistency_verification"]

    def health_check(self) -> bool:
        return True

    def _verify(self, operation: str, result: Dict[str, Any],
                expected: Optional[Any], agent_id: str) -> Dict[str, Any]:
        """Verify a result from another agent."""
        checks: List[str] = []
        issues: List[str] = []

        # Check 1: result is non-empty
        if not result:
            issues.append("Result is empty")
            checks.append("non_empty: FAIL")
        else:
            checks.append("non_empty: PASS")

        # Check 2: result has expected fields
        if isinstance(result, dict) and "error" in result:
            issues.append(f"Result contains error: {result['error']}")
            checks.append("no_error: FAIL")
        else:
            checks.append("no_error: PASS")

        # Check 3: expected match
        if expected is not None:
            if result == expected:
                checks.append("matches_expected: PASS")
            else:
                checks.append("matches_expected: FAIL")
                issues.append("Result does not match expected value")

        # Check 4: agent-specific quality
        if isinstance(result, dict) and "output" in result:
            output = result["output"]
            if output is not None:
                checks.append("has_output: PASS")
            else:
                checks.append("has_output: FAIL")
                issues.append("Output is None")
        else:
            checks.append("has_output: N/A")

        verified = len(issues) == 0
        return {
            "operation": operation,
            "agent_id": agent_id,
            "verified": verified,
            "checks": checks,
            "issues": issues,
            "pass_rate": len([c for c in checks if "PASS" in c]) / max(1, len(checks)),
        }

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_verifications": self._verification_count,
            "passed": self._passed_count,
            "pass_rate": self._passed_count / max(1, self._verification_count),
        }
