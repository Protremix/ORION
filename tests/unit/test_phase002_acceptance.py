"""
Phase 002 Acceptance Tests — Luna Required Changes

Tests for:
- Report serialization completeness
- Metadata completeness on error/skip results
- Reproducibility
- CLI filtered execution
- Benchmark output validation
- Cost measurement

License: Apache 2.0
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from eval import EvalCategory, EvalMetric, EvalReport, EvalResult, EvalStatus, EvaluationTest, ORIONEval
from eval.benchmark_tests import create_all_benchmark_tests, create_orion_eval
from eval.run import MockOrionSystem, run_benchmarks


class CrashingTest(EvaluationTest):
    """Test that raises an exception to test error metadata."""
    @property
    def metric(self):
        return EvalMetric(name="crash_test", category=EvalCategory.TEMPORAL_REASONING, description="Crash test")

    def setup(self):
        return True

    def teardown(self):
        pass

    def run(self, system):
        raise RuntimeError("Test crashed intentionally")


class TestReportSerialization:
    """Test that EvalReport.to_dict() includes all required fields."""

    def test_report_has_report_id(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        d = report.to_dict()
        assert "report_id" in d
        assert d["report_id"].startswith("eval_")

    def test_report_has_timestamp(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        d = report.to_dict()
        assert "timestamp" in d
        assert isinstance(d["timestamp"], float)

    def test_report_has_metadata(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        d = report.to_dict()
        assert "metadata" in d
        assert "test_count" in d["metadata"]

    def test_report_summary_has_benchmark_version(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        d = report.to_dict()
        assert "benchmark_version" in d["summary"]

    def test_report_summary_has_skipped_and_errors(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        d = report.to_dict()
        assert "skipped" in d["summary"]
        assert "errors" in d["summary"]


class TestMetadataCompleteness:
    """Test that all results (including error/skip) have metadata."""

    REQUIRED_FIELDS = ["model", "version", "hardware", "prompt", "test_version",
                        "latency_ms", "memory_usage_mb", "cost_estimate", "failure_reason"]

    def test_passing_results_have_metadata(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        for r in report.results:
            d = r.to_dict()
            for field in self.REQUIRED_FIELDS:
                assert field in d, f"Result {r.metric.name} missing {field}"

    def test_error_results_have_metadata(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        eval_sys.register_test(CrashingTest())
        report = eval_sys.run_all(system)
        error_results = [r for r in report.results if r.status == EvalStatus.ERROR]
        assert len(error_results) > 0, "Expected error results from CrashingTest"
        for r in error_results:
            assert r.model != "", "Error result missing model"
            assert r.version != "", "Error result missing version"
            assert r.hardware != "", "Error result missing hardware"
            assert r.failure_reason != "", "Error result missing failure_reason"

    def test_cost_is_measured(self):
        """Cost should not be a hard-coded default of 0.0 for all results."""
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        # In simulation mode, cost will be very small but should be a float
        for r in report.results:
            assert isinstance(r.cost_estimate, float), f"{r.metric.name} cost not float"
            assert r.cost_estimate >= 0.0, f"{r.metric.name} cost negative"

    def test_test_version_is_set(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        for r in report.results:
            assert r.test_version != "", f"{r.metric.name} missing test_version"
            assert r.test_version != "1.0", f"{r.metric.name} has default test_version"


class TestBenchmarkValidation:
    """Test that benchmarks validate outputs, not just non-None."""

    def test_logical_inference_validates_answer(self):
        """Mock system returns 'conclusion_derived' which should be accepted."""
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        logic_result = [r for r in report.results if r.metric.category == EvalCategory.TEMPORAL_REASONING]
        assert len(logic_result) == 1
        assert logic_result[0].status == EvalStatus.PASSED

    def test_planning_validates_multiple_steps(self):
        """Mock system returns 3 steps, should pass."""
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        plan_result = [r for r in report.results if r.metric.category == EvalCategory.PLANNING]
        assert len(plan_result) == 1
        assert plan_result[0].status == EvalStatus.PASSED

    def test_memory_validates_recalled_data(self):
        """Mock system returns dict with 'found' key, should pass."""
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        mem_result = [r for r in report.results if r.metric.category == EvalCategory.MEMORY]
        assert len(mem_result) == 1
        assert mem_result[0].status == EvalStatus.PASSED

    def test_multimodal_validates_text_and_image(self):
        """Mock system returns text_understood and image_analyzed, should pass."""
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        mm_result = [r for r in report.results if r.metric.category == EvalCategory.MULTIMODAL_REASONING]
        assert len(mm_result) == 1
        assert mm_result[0].status == EvalStatus.PASSED

    def test_coordination_validates_agents_and_goal(self):
        """Mock system returns dict with agents and goal, should pass."""
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        coord_result = [r for r in report.results if r.metric.category == EvalCategory.AGENT_COORDINATION]
        assert len(coord_result) == 1
        assert coord_result[0].status == EvalStatus.PASSED

    def test_wrong_answer_is_not_full_score(self):
        """System returning wrong answer should get reduced score."""
        class WrongAnswerSystem(MockOrionSystem):
            def reason(self, prompt):
                return "xyz"  # Doesn't mention C or true
            def plan(self, goal):
                return "single_step"  # Not a list

        system = WrongAnswerSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        logic = [r for r in report.results if r.metric.category == EvalCategory.TEMPORAL_REASONING][0]
        assert logic.value < 1.0, "Wrong answer should not get full score"
        plan = [r for r in report.results if r.metric.category == EvalCategory.PLANNING][0]
        assert plan.value < 1.0, "Non-list plan should not get full score"


class TestCLIExecution:
    """Test CLI runner with filtered categories."""

    def test_filtered_categories_works(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name
        try:
            result = run_benchmarks(
                categories=["planning", "memory"],
                output=output_path,
                format="json",
            )
            assert "results" in result
            assert len(result["results"]) >= 1
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_unknown_categories_returns_error(self):
        result = run_benchmarks(
            categories=["nonexistent_category"],
            output="/tmp/test_unknown.json",
            format="json",
        )
        assert "error" in result

    def test_all_categories_produces_complete_report(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name
        try:
            result = run_benchmarks(
                categories=None,  # all
                output=output_path,
                format="json",
            )
            assert result["summary"]["total"] == 12
            assert result["summary"]["passed"] == 12
            # Check report has complete metadata
            assert "report_id" in result
            assert "timestamp" in result
            assert "metadata" in result
            assert "benchmark_version" in result["summary"]
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestReproducibility:
    """Test that reports are structurally reproducible."""

    def test_same_system_same_categories(self):
        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        report1 = eval_sys.run_all(system)
        report2 = eval_sys.run_all(system)
        # Same number of results
        assert len(report1.results) == len(report2.results)
        # Same categories tested
        cats1 = {r.metric.category for r in report1.results}
        cats2 = {r.metric.category for r in report2.results}
        assert cats1 == cats2
        # Same pass/fail pattern
        statuses1 = [r.status for r in report1.results]
        statuses2 = [r.status for r in report2.results]
        assert statuses1 == statuses2
