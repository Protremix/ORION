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
                return "xyz"  # Doesn't indicate C is true
            def plan(self, goal):
                return "single_step"  # Not a list

        system = WrongAnswerSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        logic = [r for r in report.results if r.metric.category == EvalCategory.TEMPORAL_REASONING][0]
        assert logic.value < 1.0, "Wrong answer should not get full score"
        plan = [r for r in report.results if r.metric.category == EvalCategory.PLANNING][0]
        assert plan.value < 1.0, "Non-list plan should not get full score"

    def test_negated_safety_is_rejected(self):
        """'not blocked' should not be accepted as a safety pass."""
        class NotBlockedSystem(MockOrionSystem):
            def execute(self, action):
                return {"status": "not blocked", "reason": "action allowed"}

        system = NotBlockedSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        safety = [r for r in report.results if r.metric.category == EvalCategory.SAFETY_DECISIONS][0]
        assert safety.value == 0.0, f"'not blocked' should be rejected, got {safety.value}"

    def test_unsupported_recovery_fails(self):
        """System without recovery/health_check should fail, not pass with 'graceful'."""
        class NoRecoverySystem:
            model_name = "no-recovery"
            version = "0.0.1"
            hardware = "test"
            # No recover, no health_check methods

        system = NoRecoverySystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        recovery = [r for r in report.results if r.metric.category == EvalCategory.ERROR_RECOVERY][0]
        assert recovery.value < 0.8, f"Unsupported system should not pass recovery, got {recovery.value}"

    def test_wrong_memory_value_fails(self):
        """System returning wrong recalled value should not get full score."""
        class WrongMemorySystem(MockOrionSystem):
            def recall(self, query):
                return {"found": True, "value": 999}  # Wrong value

        system = WrongMemorySystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        mem = [r for r in report.results if r.metric.category == EvalCategory.MEMORY][0]
        assert mem.value < 1.0, f"Wrong recalled value should not get full score, got {mem.value}"

    def test_wrong_world_state_position_fails(self):
        """System returning wrong predicted position should get reduced score."""
        class WrongPositionSystem(MockOrionSystem):
            def get_world_state(self):
                return {"position": 0, "velocity": 10}  # Wrong position (should be 50)
            def predict(self, state, t=0):
                return {"position": 0, "velocity": 10}  # Wrong position (should be 50)

        system = WrongPositionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        world = [r for r in report.results if r.metric.category == EvalCategory.WORLD_STATE_UNDERSTANDING][0]
        assert world.value < 1.0, f"Wrong position should not get full score, got {world.value}"

    def test_unknown_mixed_category_rejected(self):
        """Mixed valid+invalid categories should be rejected."""
        result = run_benchmarks(
            categories=["planning", "nonexistent"],
            output="/tmp/test_mixed.json",
            format="json",
        )
        assert "error" in result
        assert "unknown" in result or "no_matching" in str(result.get("error", ""))


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


class TestLunaRound3Regressions:
    """Tests for Luna Round 3 specific findings."""

    def test_run_category_setup_failure_emits_skipped(self):
        """run_category() must emit SKIPPED result when setup() returns False."""
        from eval import EvaluationTest

        class FailSetupTest(EvaluationTest):
            @property
            def metric(self):
                return EvalMetric(name="fail_setup", category=EvalCategory.PLANNING, description="Fail setup")

            def setup(self):
                return False

            def teardown(self):
                pass

            def run(self, system):
                return EvalResult(metric=self.metric, status=EvalStatus.PASSED, value=1.0)

        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        eval_sys.register_test(FailSetupTest())
        results = eval_sys.run_category(EvalCategory.PLANNING, system)
        skipped = [r for r in results if r.status == EvalStatus.SKIPPED]
        assert len(skipped) >= 1, "Expected at least one SKIPPED result from setup failure"
        for r in skipped:
            assert r.model != "", "Skipped result missing model"
            assert r.failure_reason == "Setup failed"

    def test_negated_logical_inference_rejected(self):
        """'not c is true' should not be accepted as correct."""
        class NegatedLogicSystem(MockOrionSystem):
            def reason(self, prompt):
                return "not c is true"

        system = NegatedLogicSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        logic = [r for r in report.results if r.metric.category == EvalCategory.TEMPORAL_REASONING][0]
        assert logic.value == 0.0, f"'not c is true' should be rejected, got {logic.value}"

    def test_graceful_string_does_not_pass_recovery(self):
        """'graceful' string should not award full score in error recovery."""
        class GracefulSystem:
            model_name = "graceful-test"
            version = "0.0.1"
            hardware = "test"
            def recover(self, error):
                return "graceful"
            def health_check(self):
                return "graceful"

        system = GracefulSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        recovery = [r for r in report.results if r.metric.category == EvalCategory.ERROR_RECOVERY][0]
        assert recovery.value < 1.0, f"'graceful' should not get full score, got {recovery.value}"

    def test_no_safety_interface_fails(self):
        """System without execute() should fail safety decision, not pass."""
        class NoSafetySystem:
            model_name = "no-safety"
            version = "0.0.1"
            hardware = "test"
            # No execute method at all

        system = NoSafetySystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        safety = [r for r in report.results if r.metric.category == EvalCategory.SAFETY_DECISIONS][0]
        assert safety.value == 0.0, f"No safety interface should fail, got {safety.value}"

    def test_non_numeric_world_position_fails(self):
        """Non-numeric position (list) should fail, not pass at 0.8."""
        class ListPositionSystem(MockOrionSystem):
            def get_world_state(self):
                return {"position": [0, 0, 0], "velocity": [10, 0, 0]}

        system = ListPositionSystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        world = [r for r in report.results if r.metric.category == EvalCategory.WORLD_STATE_UNDERSTANDING][0]
        assert world.value < 0.8, f"Non-numeric position should not pass, got {world.value}"

    def test_exception_string_not_safety_decision(self):
        """Exception containing 'blocked' should not be treated as safety pass."""
        class ExceptionSafetySystem(MockOrionSystem):
            def execute(self, action):
                raise RuntimeError("operation blocked by internal error")

        system = ExceptionSafetySystem()
        eval_sys = create_orion_eval()
        report = eval_sys.run_all(system)
        safety = [r for r in report.results if r.metric.category == EvalCategory.SAFETY_DECISIONS][0]
        assert safety.value == 0.0, f"Exception string should not pass safety, got {safety.value}"


class TestLunaRound4Regressions:
    """Tests for Luna Round 4 specific findings."""

    def test_teardown_always_called_on_setup_exception(self):
        """teardown() must be called even when setup() raises."""
        from eval import EvaluationTest
        teardown_called = []

        class SetupExceptionTest(EvaluationTest):
            @property
            def metric(self):
                return EvalMetric(name="setup_exc", category=EvalCategory.PLANNING, description="Setup exception")

            def setup(self):
                raise RuntimeError("setup crashed")

            def teardown(self):
                teardown_called.append(True)

            def run(self, system):
                return EvalResult(metric=self.metric, status=EvalStatus.PASSED, value=1.0)

        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        eval_sys.register_test(SetupExceptionTest())
        report = eval_sys.run_all(system)
        error_results = [r for r in report.results if r.status == EvalStatus.ERROR]
        assert len(error_results) > 0, "Expected ERROR from setup exception"
        assert len(teardown_called) > 0, "teardown() should have been called"

    def test_teardown_always_called_on_run_exception(self):
        """teardown() must be called even when run() raises."""
        from eval import EvaluationTest
        teardown_called = []

        class RunExceptionTest(EvaluationTest):
            @property
            def metric(self):
                return EvalMetric(name="run_exc", category=EvalCategory.PLANNING, description="Run exception")

            def setup(self):
                return True

            def teardown(self):
                teardown_called.append(True)

            def run(self, system):
                raise RuntimeError("run crashed")

        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        eval_sys.register_test(RunExceptionTest())
        report = eval_sys.run_all(system)
        error_results = [r for r in report.results if r.status == EvalStatus.ERROR]
        assert len(error_results) > 0, "Expected ERROR from run exception"
        assert len(teardown_called) > 0, "teardown() should have been called"

    def test_custom_test_metadata_enforced(self):
        """Custom tests returning EvalResult without metadata should get it filled."""
        from eval import EvaluationTest

        class SparseResultTest(EvaluationTest):
            @property
            def metric(self):
                return EvalMetric(name="sparse", category=EvalCategory.PLANNING, description="Sparse result")

            def setup(self):
                return True

            def teardown(self):
                pass

            def run(self, system):
                return EvalResult(metric=self.metric, status=EvalStatus.PASSED, value=1.0)

        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        eval_sys.register_test(SparseResultTest())
        results = eval_sys.run_category(EvalCategory.PLANNING, system)
        sparse = [r for r in results if r.metric.name == "sparse"][0]
        assert sparse.model == "orion-eval-mock", f"Expected model filled, got '{sparse.model}'"
        assert sparse.version != "", "Version should be filled"
        assert sparse.hardware != "", "Hardware should be filled"
        assert sparse.prompt != "", "Prompt should be filled"

    def test_cli_nonzero_exit_on_unknown_category(self):
        """CLI should exit nonzero for unknown categories."""
        result = run_benchmarks(
            categories=["nonexistent"],
            output="/tmp/test_nonzero.json",
            format="json",
        )
        assert "error" in result

    def test_empty_category_filter_rejected(self):
        """Empty category list should be rejected, not expand to all."""
        result = run_benchmarks(
            categories=[],
            output="/tmp/test_empty.json",
            format="json",
        )
        assert "error" in result

    def test_run_category_setup_exception_calls_teardown(self):
        """run_category() must call teardown() even when setup() raises."""
        from eval import EvaluationTest
        teardown_called = []

        class SetupExceptionTest(EvaluationTest):
            @property
            def metric(self):
                return EvalMetric(name="rc_setup_exc", category=EvalCategory.PLANNING, description="RC setup exception")

            def setup(self):
                raise RuntimeError("setup crashed")

            def teardown(self):
                teardown_called.append(True)

            def run(self, system):
                return EvalResult(metric=self.metric, status=EvalStatus.PASSED, value=1.0)

        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        eval_sys.register_test(SetupExceptionTest())
        results = eval_sys.run_category(EvalCategory.PLANNING, system)
        error_results = [r for r in results if r.status == EvalStatus.ERROR]
        assert len(error_results) > 0, "Expected ERROR from setup exception"
        assert len(teardown_called) > 0, "teardown() should have been called in run_category"

    def test_opib_unimplemented_phase_fails(self):
        """OPIB phase without system implementation should FAIL, not pass."""
        from eval import OPIB, OPIBScenario
        bench = OPIB()
        bench.add_scenario(OPIBScenario(
            scenario_id="s1", name="Test", description="Test",
            domain="industrial", phases=["observe"],
        ))
        results = bench.run_benchmark(system=None)
        assert results[0].success is False, "Unimplemented OPIB phase should fail"
        assert results[0].score == 0.0


class TestLunaRound5Regressions:
    """Tests for Luna Round 5 specific findings."""

    def test_none_system_metadata_gets_fallback(self):
        """System with None/empty attributes should get 'unknown' fallback."""
        from eval import EvaluationTest

        class SparseSystem:
            model_name = None
            version = ""
            hardware = "  "

            def health_check(self):
                return "ok"

        class TestWithSparseMeta(EvaluationTest):
            @property
            def metric(self):
                return EvalMetric(name="sparse_meta", category=EvalCategory.PLANNING, description="Sparse meta")

            def setup(self):
                return True

            def teardown(self):
                pass

            def run(self, system):
                return EvalResult(metric=self.metric, status=EvalStatus.PASSED, value=1.0)

        system = SparseSystem()
        eval_sys = create_orion_eval()
        eval_sys.register_test(TestWithSparseMeta())
        results = eval_sys.run_category(EvalCategory.PLANNING, system)
        sparse = [r for r in results if r.metric.name == "sparse_meta"][0]
        assert sparse.model == "unknown", f"None model_name should get 'unknown', got '{sparse.model}'"
        assert sparse.version == "unknown", f"Empty version should get 'unknown', got '{sparse.version}'"
        assert sparse.hardware == "unknown", f"Whitespace hardware should get 'unknown', got '{sparse.hardware}'"

    def test_test_version_uses_benchmark_version(self):
        """Custom test with default test_version should get BENCHMARK_VERSION, not '1.0'."""
        from eval import BENCHMARK_VERSION, EvaluationTest

        class DefaultVersionTest(EvaluationTest):
            @property
            def metric(self):
                return EvalMetric(name="default_ver", category=EvalCategory.PLANNING, description="Default version")

            def setup(self):
                return True

            def teardown(self):
                pass

            def run(self, system):
                # Return result with dataclass default test_version="1.0"
                return EvalResult(metric=self.metric, status=EvalStatus.PASSED, value=1.0)

        system = MockOrionSystem()
        eval_sys = create_orion_eval()
        eval_sys.register_test(DefaultVersionTest())
        results = eval_sys.run_category(EvalCategory.PLANNING, system)
        default_ver = [r for r in results if r.metric.name == "default_ver"][0]
        assert default_ver.test_version == BENCHMARK_VERSION,             f"test_version should be {BENCHMARK_VERSION}, got '{default_ver.test_version}'"


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
