"""
Tests for ORION EVAL Phase 002 — Benchmark tests, metadata, and CLI runner.

License: Apache 2.0
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.eval import (
    ORIONEval, EvalCategory, EvalMetric, EvalResult, EvalStatus,
    EvalReport, EvaluationTest, OPIB, OPIBScenario,
)
from src.eval.benchmark_tests import (
    create_all_benchmark_tests, create_orion_eval, __version__,
    LogicalInferenceTest, GoalDirectedPlanningTest, TaskDecompositionTest,
    SafetyDecisionTest, PermissionDisciplineTest, ToolSelectionTest,
    MemoryRecallTest, WorldStateTrackingTest, ErrorRecoveryTest,
    UncertaintyCalibrationTest, MultimodalUnderstandingTest, AgentCoordinationTest,
)


# ============================================================================
# Category Tests
# ============================================================================

class TestEvalCategories:
    """Test all 12 required categories exist."""

    def test_all_12_categories_exist(self):
        """All 12 roadmap categories are defined."""
        required = [
            "TEMPORAL_REASONING", "PLANNING", "TASK_DECOMPOSITION",
            "SAFETY_DECISIONS", "PERMISSION_DISCIPLINE", "TOOL_SELECTION",
            "MEMORY", "WORLD_STATE_UNDERSTANDING", "ERROR_RECOVERY",
            "UNCERTAINTY_CALIBRATION", "MULTIMODAL_REASONING", "AGENT_COORDINATION",
        ]
        for cat in required:
            assert hasattr(EvalCategory, cat), f"Missing EvalCategory.{cat}"

    def test_category_values_are_strings(self):
        """All category values are lowercase strings."""
        for cat in EvalCategory:
            assert isinstance(cat.value, str)
            assert cat.value == cat.value.lower()


# ============================================================================
# Result Metadata Tests
# ============================================================================

class TestResultMetadata:
    """Test that EvalResult includes all required metadata fields."""

    def test_result_has_all_metadata_fields(self):
        """EvalResult has all fields required by the Master Roadmap."""
        m = EvalMetric(name="test", category=EvalCategory.PLANNING, description="test")
        r = EvalResult(metric=m, status=EvalStatus.PASSED, value=1.0)
        # Required fields
        assert hasattr(r, "model")
        assert hasattr(r, "version")
        assert hasattr(r, "hardware")
        assert hasattr(r, "prompt")
        assert hasattr(r, "test_version")
        assert hasattr(r, "latency_ms")
        assert hasattr(r, "memory_usage_mb")
        assert hasattr(r, "cost_estimate")
        assert hasattr(r, "failure_reason")

    def test_result_to_dict_includes_metadata(self):
        """to_dict() includes all metadata fields."""
        m = EvalMetric(name="test", category=EvalCategory.PLANNING, description="test")
        r = EvalResult(
            metric=m, status=EvalStatus.PASSED, value=0.9,
            model="gpt-4o", version="1.0", hardware="cloud",
            prompt="test prompt", latency_ms=12.5, memory_usage_mb=1.2,
            cost_estimate=0.001, failure_reason=""
        )
        d = r.to_dict()
        assert d["model"] == "gpt-4o"
        assert d["latency_ms"] == 12.5
        assert d["memory_usage_mb"] == 1.2
        assert d["cost_estimate"] == 0.001
        assert d["prompt"] == "test prompt"
        assert "failure_reason" in d

    def test_failed_result_has_failure_reason(self):
        """Failed results should include a failure reason."""
        m = EvalMetric(name="test", category=EvalCategory.PLANNING, description="test")
        r = EvalResult(
            metric=m, status=EvalStatus.FAILED, value=0.0,
            failure_reason="System could not plan"
        )
        assert r.failure_reason == "System could not plan"
        assert not r.passed


# ============================================================================
# Benchmark Test Tests (all 12)
# ============================================================================

class TestBenchmarkTests:
    """Test all 12 benchmark test classes."""

    def test_create_all_benchmark_tests(self):
        """create_all_benchmark_tests returns 12 tests."""
        tests = create_all_benchmark_tests()
        assert len(tests) == 12

    def test_all_benchmark_categories_covered(self):
        """All 12 roadmap categories are covered by benchmark tests."""
        tests = create_all_benchmark_tests()
        categories = {t.metric.category for t in tests}
        # Must include all 12
        required = {
            EvalCategory.TEMPORAL_REASONING,
            EvalCategory.PLANNING,
            EvalCategory.TASK_DECOMPOSITION,
            EvalCategory.SAFETY_DECISIONS,
            EvalCategory.PERMISSION_DISCIPLINE,
            EvalCategory.TOOL_SELECTION,
            EvalCategory.MEMORY,
            EvalCategory.WORLD_STATE_UNDERSTANDING,
            EvalCategory.ERROR_RECOVERY,
            EvalCategory.UNCERTAINTY_CALIBRATION,
            EvalCategory.MULTIMODAL_REASONING,
            EvalCategory.AGENT_COORDINATION,
        }
        assert required.issubset(categories)

    def test_each_benchmark_test_has_metric(self):
        """Each benchmark test has a properly defined metric."""
        tests = create_all_benchmark_tests()
        for t in tests:
            assert t.metric is not None or hasattr(t, '_metric')
            assert t.metric.name
            assert t.metric.description
            assert t.metric.category.value in [c.value for c in EvalCategory]

    def test_benchmark_tests_have_setup_teardown(self):
        """Each benchmark test implements setup and teardown."""
        tests = create_all_benchmark_tests()
        for t in tests:
            assert hasattr(t, "setup")
            assert hasattr(t, "teardown")
            assert t.setup() is True
            t.teardown()  # Should not raise


class TestBenchmarkTestExecution:
    """Test running benchmark tests against a mock system."""

    def setup_method(self):
        from src.eval.run import MockOrionSystem
        self.system = MockOrionSystem()

    def test_logical_inference_runs(self):
        test = LogicalInferenceTest()
        result = test.run(self.system)
        assert result is not None
        assert result.latency_ms > 0
        assert result.model == "orion-eval-mock"

    def test_planning_runs(self):
        test = GoalDirectedPlanningTest()
        result = test.run(self.system)
        assert result is not None
        assert result.latency_ms > 0

    def test_task_decomposition_runs(self):
        test = TaskDecompositionTest()
        result = test.run(self.system)
        assert result is not None
        assert result.latency_ms > 0

    def test_safety_decision_runs(self):
        test = SafetyDecisionTest()
        result = test.run(self.system)
        assert result is not None
        # Mock system blocks dangerous actions
        assert result.value == 1.0
        assert result.status == EvalStatus.PASSED

    def test_permission_discipline_runs(self):
        test = PermissionDisciplineTest()
        result = test.run(self.system)
        assert result is not None
        # Unregistered agent should be denied
        assert result.value == 1.0
        assert result.status == EvalStatus.PASSED

    def test_tool_selection_runs(self):
        test = ToolSelectionTest()
        result = test.run(self.system)
        assert result is not None

    def test_memory_recall_runs(self):
        test = MemoryRecallTest()
        result = test.run(self.system)
        assert result is not None

    def test_world_state_tracking_runs(self):
        test = WorldStateTrackingTest()
        result = test.run(self.system)
        assert result is not None

    def test_error_recovery_runs(self):
        test = ErrorRecoveryTest()
        result = test.run(self.system)
        assert result is not None
        assert result.value > 0

    def test_uncertainty_calibration_runs(self):
        test = UncertaintyCalibrationTest()
        result = test.run(self.system)
        assert result is not None

    def test_multimodal_understanding_runs(self):
        test = MultimodalUnderstandingTest()
        result = test.run(self.system)
        assert result is not None

    def test_agent_coordination_runs(self):
        test = AgentCoordinationTest()
        result = test.run(self.system)
        assert result is not None


# ============================================================================
# Report Generation Tests
# ============================================================================

class TestReportGeneration:
    """Test report generation and serialization."""

    def test_run_all_produces_report(self):
        """run_all produces a complete report with 12 results."""
        eval_system = create_orion_eval()
        from src.eval.run import MockOrionSystem
        system = MockOrionSystem()
        report = eval_system.run_all(system)
        assert len(report.results) == 12

    def test_report_to_dict(self):
        """Report to_dict includes summary and category scores."""
        eval_system = create_orion_eval()
        from src.eval.run import MockOrionSystem
        system = MockOrionSystem()
        report = eval_system.run_all(system)
        d = report.to_dict()
        assert "results" in d
        assert "summary" in d
        assert "category_scores" in d
        assert d["summary"]["total"] == 12

    def test_report_pass_rate(self):
        """Report pass_rate is calculated correctly."""
        eval_system = create_orion_eval()
        from src.eval.run import MockOrionSystem
        system = MockOrionSystem()
        report = eval_system.run_all(system)
        assert 0 <= report.pass_rate <= 1.0

    def test_report_has_latency_and_memory(self):
        """All results in report have latency and memory metadata."""
        eval_system = create_orion_eval()
        from src.eval.run import MockOrionSystem
        system = MockOrionSystem()
        report = eval_system.run_all(system)
        for r in report.results:
            assert r.latency_ms >= 0
            assert r.memory_usage_mb >= 0


# ============================================================================
# CLI Runner Tests
# ============================================================================

class TestCLIRunner:
    """Test the CLI runner."""

    def test_run_benchmarks_all(self):
        """Running all benchmarks produces a report."""
        from src.eval.run import run_benchmarks
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            output_path = f.name
        try:
            report = run_benchmarks(output=output_path, format="json")
            assert report is not None
            assert report["summary"]["total"] == 12
            assert os.path.exists(output_path)
            with open(output_path) as f:
                data = json.load(f)
            assert "results" in data
        finally:
            os.unlink(output_path)

    def test_run_benchmarks_markdown(self):
        """Running benchmarks with markdown format produces .md file."""
        from src.eval.run import run_benchmarks
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            output_path = f.name
        try:
            run_benchmarks(output=output_path, format="md")
            md_path = output_path.replace(".json", ".md")
            assert os.path.exists(md_path)
            with open(md_path) as f:
                content = f.read()
            assert "ORION EVAL" in content
            assert "Summary" in content
        finally:
            os.unlink(output_path)
            md_path = output_path.replace(".json", ".md")
            if os.path.exists(md_path):
                os.unlink(md_path)

    def test_no_invented_results(self):
        """Results should have real latency values (not zero)."""
        from src.eval.run import run_benchmarks
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            output_path = f.name
        try:
            report = run_benchmarks(output=output_path, format="json")
            for r in report["results"]:
                # Latency should be a real measured value (positive)
                assert r["latency_ms"] > 0, f"Result {r['metric']} has zero latency"
        finally:
            os.unlink(output_path)


# ============================================================================
# OPIB Integration Tests
# ============================================================================

class TestOPIBIntegration:
    """Test that OPIB scenarios still work with new categories."""

    def test_opib_scenarios_exist(self):
        """OPIB scenarios are still available."""
        from src.eval.opib_scenarios import create_all_scenarios
        scenarios = create_all_scenarios()
        assert len(scenarios) > 0

    def test_opib_run_with_mock(self):
        """OPIB can run with mock system."""
        from src.eval.opib_scenarios import create_all_scenarios, OPIBTestSystem
        opib = OPIB()
        for s in create_all_scenarios():
            opib.add_scenario(s)
        mock = OPIBTestSystem()
        results = opib.run_benchmark(mock)
        assert len(results) > 0
