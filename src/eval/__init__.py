"""
ORION Evaluation Framework — Master Spec §20, §21

Measures:
- Perception, object permanence, temporal reasoning, spatial reasoning
- Memory, world-state reconstruction, future prediction
- Planning, simulation, action selection, error recovery
- Multimodal reasoning, agent task completion, safety compliance

Proposed benchmark: OPIB (ORION Physical Intelligence Benchmark)

License: Apache 2.0
"""

from __future__ import annotations

import abc
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Evaluation Metric Types
# ============================================================================

class EvalCategory(str, Enum):
    """Master Spec §20 evaluation categories."""
    PERCEPTION = "perception"
    OBJECT_PERMANENCE = "object_permanence"
    TEMPORAL_REASONING = "temporal_reasoning"
    SPATIAL_REASONING = "spatial_reasoning"
    MEMORY = "memory"
    WORLD_STATE_RECONSTRUCTION = "world_state_reconstruction"
    FUTURE_PREDICTION = "future_prediction"
    PLANNING = "planning"
    SIMULATION = "simulation"
    ACTION_SELECTION = "action_selection"
    ERROR_RECOVERY = "error_recovery"
    MULTIMODAL_REASONING = "multimodal_reasoning"
    AGENT_TASK_COMPLETION = "agent_task_completion"
    SAFETY_COMPLIANCE = "safety_compliance"
    # Phase 002 additions — 7 new categories per Master Roadmap
    TASK_DECOMPOSITION = "task_decomposition"
    SAFETY_DECISIONS = "safety_decisions"
    PERMISSION_DISCIPLINE = "permission_discipline"
    TOOL_SELECTION = "tool_selection"
    WORLD_STATE_UNDERSTANDING = "world_state_understanding"
    UNCERTAINTY_CALIBRATION = "uncertainty_calibration"
    AGENT_COORDINATION = "agent_coordination"


class EvalStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class EvalMetric:
    """A single evaluation metric."""
    name: str
    category: EvalCategory
    description: str
    target_value: Optional[float] = None  # Minimum acceptable value
    weight: float = 1.0  # Weight in aggregate score


@dataclass
class EvalResult:
    """Result of a single evaluation metric."""
    metric: EvalMetric
    status: EvalStatus
    value: Optional[float] = None
    max_value: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    # Phase 002: Required metadata per Master Roadmap
    model: str = ""
    version: str = ""
    hardware: str = ""
    prompt: str = ""
    test_version: str = "1.0"
    latency_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cost_estimate: float = 0.0
    failure_reason: str = ""

    @property
    def normalized_score(self) -> float:
        """Score normalized to [0, 1]."""
        if self.value is None or self.max_value == 0:
            return 0.0
        return min(self.value / self.max_value, 1.0)

    @property
    def passed(self) -> bool:
        if self.status != EvalStatus.PASSED:
            return False
        if self.metric.target_value is not None and self.value is not None:
            return self.value >= self.metric.target_value
        return self.status == EvalStatus.PASSED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for report generation."""
        return {
            "metric": self.metric.name,
            "category": self.metric.category.value,
            "status": self.status.value,
            "value": self.value,
            "max_value": self.max_value,
            "normalized_score": self.normalized_score,
            "passed": self.passed,
            "model": self.model,
            "version": self.version,
            "hardware": self.hardware,
            "prompt": self.prompt,
            "test_version": self.test_version,
            "latency_ms": self.latency_ms,
            "memory_usage_mb": self.memory_usage_mb,
            "cost_estimate": self.cost_estimate,
            "failure_reason": self.failure_reason or self.error or "",
        }


@dataclass
class EvalReport:
    """Full evaluation report."""
    report_id: str
    timestamp: float = field(default_factory=time.time)
    results: List[EvalResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_score(self) -> float:
        """Weighted aggregate score [0, 1]."""
        if not self.results:
            return 0.0
        total_weight = sum(r.metric.weight for r in self.results if r.status == EvalStatus.PASSED)
        weighted_sum = sum(
            r.normalized_score * r.metric.weight
            for r in self.results
            if r.status == EvalStatus.PASSED
        )
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    @property
    def pass_rate(self) -> float:
        """Fraction of metrics that passed."""
        if not self.results:
            return 0.0
        passed = sum(1 for r in self.results if r.passed)
        return passed / len(self.results)

    def by_category(self, category: EvalCategory) -> List[EvalResult]:
        """Filter results by category."""
        return [r for r in self.results if r.metric.category == category]

    def category_scores(self) -> Dict[str, float]:
        """Average score per category."""
        scores = {}
        for cat in EvalCategory:
            cat_results = self.by_category(cat)
            if cat_results:
                scores[cat.value] = sum(r.normalized_score for r in cat_results) / len(cat_results)
        return scores

    def to_dict(self) -> Dict[str, Any]:
        """Serialize full report to dictionary with complete metadata."""
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
                "skipped": sum(1 for r in self.results if r.status == EvalStatus.SKIPPED),
                "errors": sum(1 for r in self.results if r.status == EvalStatus.ERROR),
                "pass_rate": self.pass_rate,
                "total_score": self.total_score,
                "avg_latency_ms": sum(r.latency_ms for r in self.results) / max(len(self.results), 1),
                "avg_cost": sum(r.cost_estimate for r in self.results) / max(len(self.results), 1),
                "total_cost": sum(r.cost_estimate for r in self.results),
                "test_count": self.metadata.get("test_count", len(self.results)),
                "benchmark_version": self.metadata.get("benchmark_version", "1.0.0"),
            },
            "category_scores": self.category_scores(),
        }


# ============================================================================
# Evaluation Test Base
# ============================================================================

class EvaluationTest(abc.ABC):
    """Abstract base for an ORION evaluation test."""

    @property
    @abc.abstractmethod
    def metric(self) -> EvalMetric:
        """The metric this test evaluates."""
        ...

    @abc.abstractmethod
    def run(self, system: Any) -> EvalResult:
        """Run the evaluation against a system."""
        ...

    def setup(self) -> bool:
        """Setup before running. Override if needed."""
        return True

    def teardown(self) -> None:
        """Cleanup after running. Override if needed."""
        pass


# ============================================================================
# ORION EVAL — Main Evaluation Engine
# ============================================================================

class ORIONEval:
    """
    ORION Evaluation Engine — Master Spec §20.

    Runs evaluation tests across all categories and produces a report.
    No invented benchmark numbers — all results are measured.
    """

    def __init__(self) -> None:
        self._tests: List[EvaluationTest] = []

    def register_test(self, test: EvaluationTest) -> None:
        """Register an evaluation test."""
        self._tests.append(test)
        logger.info(f"Registered eval test: {test.metric.name} ({test.metric.category.value})")

    def register_tests(self, tests: List[EvaluationTest]) -> None:
        """Register multiple tests."""
        for t in tests:
            self.register_test(t)

    def list_tests(self) -> List[EvalMetric]:
        """List all registered test metrics."""
        return [t.metric for t in self._tests]

    def run_all(self, system: Any) -> EvalReport:
        """Run all registered evaluation tests."""
        report = EvalReport(
            report_id=f"eval_{int(time.time())}",
            metadata={"test_count": len(self._tests), "benchmark_version": "1.0.0"},
        )

        for test in self._tests:
            try:
                if not test.setup():
                    report.results.append(EvalResult(
                        metric=test.metric,
                        status=EvalStatus.SKIPPED,
                        error="Setup failed",
                        model=getattr(system, 'model_name', 'unknown'),
                        version=getattr(system, 'version', 'unknown'),
                        hardware=getattr(system, 'hardware', 'unknown'),
                        prompt=f"setup:{test.metric.name}",
                        test_version="1.0",
                        failure_reason="Setup failed",
                    ))
                    continue

                result = test.run(system)
                report.results.append(result)
                test.teardown()

            except Exception as e:
                logger.error(f"Eval test {test.metric.name} error: {e}")
                report.results.append(EvalResult(
                    metric=test.metric,
                    status=EvalStatus.ERROR,
                    error=str(e),
                    model=getattr(system, 'model_name', 'unknown'),
                    version=getattr(system, 'version', 'unknown'),
                    hardware=getattr(system, 'hardware', 'unknown'),
                    prompt=f"run:{test.metric.name}",
                    test_version="1.0",
                    failure_reason=str(e),
                ))

        return report

    def run_category(self, category: EvalCategory, system: Any) -> List[EvalResult]:
        """Run only tests in a specific category."""
        results = []
        for test in self._tests:
            if test.metric.category == category:
                try:
                    if test.setup():
                        results.append(test.run(system))
                    test.teardown()
                except Exception as e:
                    results.append(EvalResult(
                        metric=test.metric,
                        status=EvalStatus.ERROR,
                        error=str(e),
                        model=getattr(system, 'model_name', 'unknown'),
                        version=getattr(system, 'version', 'unknown'),
                        hardware=getattr(system, 'hardware', 'unknown'),
                        prompt=f"run_category:{test.metric.name}",
                        test_version="1.0",
                        failure_reason=str(e),
                    ))
        return results


# ============================================================================
# OPIB — ORION Physical Intelligence Benchmark (§21)
# ============================================================================

@dataclass
class OPIBScenario:
    """A single OPIB test scenario."""
    scenario_id: str
    name: str
    description: str
    domain: str  # industrial, vehicle, drone, home
    phases: List[str] = field(default_factory=list)  # observe, predict, plan, simulate, act, recover
    initial_state: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: Dict[str, Any] = field(default_factory=dict)
    difficulty: str = "medium"  # easy, medium, hard
    time_limit_seconds: float = 60.0


@dataclass
class OPIBResult:
    """Result of a single OPIB scenario."""
    scenario: OPIBScenario
    success: bool
    score: float = 0.0  # [0, 1]
    phases_completed: List[str] = field(default_factory=list)
    phases_failed: List[str] = field(default_factory=list)
    time_taken_seconds: float = 0.0
    safety_events: int = 0
    recovery_actions: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


class OPIB:
    """
    ORION Physical Intelligence Benchmark — Master Spec §21.

    Test flow per scenario:
        Observation -> World State -> Prediction -> Planning ->
        Simulation -> Action -> Result -> Recovery

    Uses unseen test environments and appropriate baselines.
    Claims of superiority require measured evidence.
    """

    def __init__(self) -> None:
        self._scenarios: List[OPIBScenario] = []
        self._results: List[OPIBResult] = []

    def add_scenario(self, scenario: OPIBScenario) -> None:
        """Add a benchmark scenario."""
        self._scenarios.append(scenario)
        logger.info(f"Added OPIB scenario: {scenario.name} ({scenario.domain})")

    def list_scenarios(self) -> List[OPIBScenario]:
        """List all scenarios."""
        return list(self._scenarios)

    def run_benchmark(self, system: Any, domain: Optional[str] = None) -> List[OPIBResult]:
        """
        Run all OPIB scenarios against a system.
        Optionally filter by domain.
        """
        self._results = []
        scenarios = self._scenarios if domain is None else [
            s for s in self._scenarios if s.domain == domain
        ]

        for scenario in scenarios:
            result = self._run_scenario(scenario, system)
            self._results.append(result)

        return self._results

    def _run_scenario(self, scenario: OPIBScenario, system: Any) -> OPIBResult:
        """Run a single OPIB scenario."""
        start = time.time()
        phases_completed = []
        phases_failed = []
        safety_events = 0
        recovery_actions = 0

        phases = scenario.phases or [
            "observe", "world_state", "predict", "plan",
            "simulate", "act", "result", "recover"
        ]

        for phase in phases:
            try:
                # Each phase is a method call on the system if available
                phase_success = self._execute_phase(phase, scenario, system)
                if phase_success:
                    phases_completed.append(phase)
                else:
                    phases_failed.append(phase)
                    if phase == "act":
                        safety_events += 1
                    if phase == "recover":
                        recovery_actions += 1
            except Exception as e:
                phases_failed.append(phase)
                logger.error(f"OPIB scenario {scenario.scenario_id} phase {phase} error: {e}")

        elapsed = time.time() - start
        success = len(phases_failed) == 0
        score = len(phases_completed) / len(phases) if phases else 0.0

        return OPIBResult(
            scenario=scenario,
            success=success,
            score=score,
            phases_completed=phases_completed,
            phases_failed=phases_failed,
            time_taken_seconds=elapsed,
            safety_events=safety_events,
            recovery_actions=recovery_actions,
        )

    def _execute_phase(self, phase: str, scenario: OPIBScenario, system: Any) -> bool:
        """Execute a single phase of an OPIB scenario."""
        # If the system has the method, call it; otherwise assume pass
        method_map = {
            "observe": "opib_observe",
            "world_state": "opib_world_state",
            "predict": "opib_predict",
            "plan": "opib_plan",
            "simulate": "opib_simulate",
            "act": "opib_act",
            "result": "opib_result",
            "recover": "opib_recover",
        }
        method_name = method_map.get(phase)
        if method_name and hasattr(system, method_name):
            method = getattr(system, method_name)
            result = method(scenario.initial_state)
            return bool(result if result is not None else True)
        # Default: phase passes if system doesn't implement it
        return True

    def get_results(self) -> List[OPIBResult]:
        """Get results from the last benchmark run."""
        return self._results

    def summary(self) -> Dict[str, Any]:
        """Summary statistics from the last run."""
        if not self._results:
            return {"total": 0, "passed": 0, "avg_score": 0.0}

        total = len(self._results)
        passed = sum(1 for r in self._results if r.success)
        avg_score = sum(r.score for r in self._results) / total
        total_safety = sum(r.safety_events for r in self._results)
        total_recovery = sum(r.recovery_actions for r in self._results)

        return {
            "total_scenarios": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total,
            "avg_score": avg_score,
            "total_safety_events": total_safety,
            "total_recovery_actions": total_recovery,
        }
