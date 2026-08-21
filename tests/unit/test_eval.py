"""
Tests for ORION Evaluation Framework (§20) and OPIB (§21).
"""

import pytest

from src.eval import (
    OPIB,
    EvalCategory,
    EvalMetric,
    EvalReport,
    EvalResult,
    EvalStatus,
    EvaluationTest,
    OPIBResult,
    OPIBScenario,
    ORIONEval,
)

# ============================================================================
# Eval Metric / Result Tests
# ============================================================================

class TestEvalMetric:
    def test_metric_creation(self):
        m = EvalMetric(name="perception_accuracy", category=EvalCategory.PERCEPTION, description="Accuracy")
        assert m.name == "perception_accuracy"
        assert m.category == EvalCategory.PERCEPTION
        assert m.weight == 1.0
        assert m.target_value is None

    def test_metric_with_target(self):
        m = EvalMetric(name="memory_recall", category=EvalCategory.MEMORY, description="Recall", target_value=0.8)
        assert m.target_value == 0.8


class TestEvalResult:
    def test_result_passed(self):
        m = EvalMetric(name="test", category=EvalCategory.PLANNING, description="Test", target_value=0.7)
        r = EvalResult(metric=m, status=EvalStatus.PASSED, value=0.85, max_value=1.0)
        assert r.passed is True
        assert r.normalized_score == 0.85

    def test_result_failed_below_target(self):
        m = EvalMetric(name="test", category=EvalCategory.PLANNING, description="Test", target_value=0.7)
        r = EvalResult(metric=m, status=EvalStatus.PASSED, value=0.5, max_value=1.0)
        assert r.passed is False

    def test_result_status_failed(self):
        m = EvalMetric(name="test", category=EvalCategory.PLANNING, description="Test")
        r = EvalResult(metric=m, status=EvalStatus.FAILED)
        assert r.passed is False

    def test_result_normalized_score_clamped(self):
        m = EvalMetric(name="test", category=EvalCategory.PERCEPTION, description="Test")
        r = EvalResult(metric=m, status=EvalStatus.PASSED, value=1.5, max_value=1.0)
        assert r.normalized_score == 1.0


# ============================================================================
# Eval Report Tests
# ============================================================================

class TestEvalReport:
    def test_empty_report(self):
        report = EvalReport(report_id="test")
        assert report.total_score == 0.0
        assert report.pass_rate == 0.0

    def test_report_with_results(self):
        m1 = EvalMetric(name="m1", category=EvalCategory.PERCEPTION, description="M1", weight=1.0)
        m2 = EvalMetric(name="m2", category=EvalCategory.MEMORY, description="M2", weight=2.0)
        report = EvalReport(report_id="test", results=[
            EvalResult(metric=m1, status=EvalStatus.PASSED, value=0.8, max_value=1.0),
            EvalResult(metric=m2, status=EvalStatus.PASSED, value=0.6, max_value=1.0),
        ])
        # weighted: (0.8*1 + 0.6*2) / (1+2) = 2.0/3.0
        assert abs(report.total_score - (2.0 / 3.0)) < 0.01
        assert report.pass_rate == 1.0

    def test_report_category_filter(self):
        m1 = EvalMetric(name="m1", category=EvalCategory.PERCEPTION, description="M1")
        m2 = EvalMetric(name="m2", category=EvalCategory.MEMORY, description="M2")
        report = EvalReport(report_id="test", results=[
            EvalResult(metric=m1, status=EvalStatus.PASSED, value=0.9, max_value=1.0),
            EvalResult(metric=m2, status=EvalStatus.PASSED, value=0.5, max_value=1.0),
        ])
        perception = report.by_category(EvalCategory.PERCEPTION)
        assert len(perception) == 1
        assert perception[0].metric.name == "m1"

    def test_report_category_scores(self):
        m1 = EvalMetric(name="m1", category=EvalCategory.PERCEPTION, description="M1")
        m2 = EvalMetric(name="m2", category=EvalCategory.PERCEPTION, description="M2")
        report = EvalReport(report_id="test", results=[
            EvalResult(metric=m1, status=EvalStatus.PASSED, value=0.8, max_value=1.0),
            EvalResult(metric=m2, status=EvalStatus.PASSED, value=0.6, max_value=1.0),
        ])
        scores = report.category_scores()
        assert "perception" in scores
        assert abs(scores["perception"] - 0.7) < 0.01


# ============================================================================
# ORION Eval Engine Tests
# ============================================================================

class MockEvalTest(EvaluationTest):
    """A mock evaluation test for testing."""
    def __init__(self, metric, result_value=0.9, result_status=EvalStatus.PASSED):
        self._metric = metric
        self._result_value = result_value
        self._result_status = result_status

    @property
    def metric(self):
        return self._metric

    def run(self, system):
        return EvalResult(
            metric=self._metric,
            status=self._result_status,
            value=self._result_value,
            max_value=1.0,
        )


class TestORIONEval:
    def test_register_test(self):
        engine = ORIONEval()
        m = EvalMetric(name="test", category=EvalCategory.PERCEPTION, description="Test")
        engine.register_test(MockEvalTest(m))
        assert len(engine.list_tests()) == 1

    def test_register_tests(self):
        engine = ORIONEval()
        tests = [
            MockEvalTest(EvalMetric(name="t1", category=EvalCategory.PERCEPTION, description="T1")),
            MockEvalTest(EvalMetric(name="t2", category=EvalCategory.MEMORY, description="T2")),
        ]
        engine.register_tests(tests)
        assert len(engine.list_tests()) == 2

    def test_run_all(self):
        engine = ORIONEval()
        engine.register_test(MockEvalTest(
            EvalMetric(name="perception", category=EvalCategory.PERCEPTION, description="Perception"),
            result_value=0.85,
        ))
        report = engine.run_all(system=None)
        assert len(report.results) == 1
        assert report.results[0].status == EvalStatus.PASSED
        assert report.results[0].value == 0.85

    def test_run_all_with_error(self):
        engine = ORIONEval()
        m = EvalMetric(name="error_test", category=EvalCategory.PLANNING, description="Error")

        class ErrorTest(EvaluationTest):
            @property
            def metric(self):
                return m

            def run(self, system):
                raise RuntimeError("Test error")

        engine.register_test(ErrorTest())
        report = engine.run_all(system=None)
        assert len(report.results) == 1
        assert report.results[0].status == EvalStatus.ERROR

    def test_run_category(self):
        engine = ORIONEval()
        engine.register_tests([
            MockEvalTest(EvalMetric(name="t1", category=EvalCategory.PERCEPTION, description="T1")),
            MockEvalTest(EvalMetric(name="t2", category=EvalCategory.MEMORY, description="T2")),
        ])
        results = engine.run_category(EvalCategory.PERCEPTION, system=None)
        assert len(results) == 1
        assert results[0].metric.category == EvalCategory.PERCEPTION


# ============================================================================
# OPIB Tests
# ============================================================================

class TestOPIB:
    def test_add_scenario(self):
        bench = OPIB()
        s = OPIBScenario(
            scenario_id="s1", name="Test", description="Test scenario",
            domain="industrial",
        )
        bench.add_scenario(s)
        assert len(bench.list_scenarios()) == 1

    def test_run_benchmark_no_scenarios(self):
        bench = OPIB()
        results = bench.run_benchmark(system=None)
        assert results == []
        assert bench.summary()["total"] == 0

    def test_run_benchmark_with_scenarios(self):
        bench = OPIB()
        s = OPIBScenario(
            scenario_id="s1", name="Test", description="Test",
            domain="industrial",
            phases=["observe", "plan", "act"],
        )
        bench.add_scenario(s)
        # system=None means no OPIB methods available — phases should FAIL
        results = bench.run_benchmark(system=None)
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].score == 0.0

        # With a system that implements all methods, should pass
        class FullOPIBSystem:
            def opib_observe(self, state): return True
            def opib_plan(self, state): return True
            def opib_act(self, state): return True
        results2 = bench.run_benchmark(system=FullOPIBSystem())
        assert results2[0].success is True
        assert results2[0].score == 1.0

    def test_run_benchmark_domain_filter(self):
        bench = OPIB()
        class FullOPIBSystem:
            def opib_observe(self, state): return True
            def opib_act(self, state): return True
            def opib_plan(self, state): return True
            def opib_perceive(self, state): return True
            def opib_reason(self, state): return True
            def opib_recover(self, state): return True
            def opib_decide(self, state): return True
        bench.add_scenarios = [
            OPIBScenario(scenario_id="s1", name="Industrial", description="", domain="industrial"),
            OPIBScenario(scenario_id="s2", name="Vehicle", description="", domain="vehicle"),
        ]
        bench.add_scenario(OPIBScenario(scenario_id="s1", name="Industrial", description="", domain="industrial"))
        bench.add_scenario(OPIBScenario(scenario_id="s2", name="Vehicle", description="", domain="vehicle"))
        results = bench.run_benchmark(system=FullOPIBSystem(), domain="vehicle")
        assert len(results) == 1
        assert results[0].scenario.domain == "vehicle"

    def test_summary(self):
        bench = OPIB()
        class MockOPIBSystem:
            def opib_observe(self, state): return True
            def opib_act(self, state): return True
            def opib_plan(self, state): return True
            def opib_perceive(self, state): return True
            def opib_reason(self, state): return True
            def opib_recover(self, state): return True
            def opib_decide(self, state): return True
        bench.add_scenario(OPIBScenario(
            scenario_id="s1", name="Test1", description="", domain="industrial",
            phases=["observe", "act"],
        ))
        bench.run_benchmark(system=MockOPIBSystem())
        summary = bench.summary()
        assert summary["total_scenarios"] == 1
        assert summary["passed"] == 1
        assert summary["pass_rate"] == 1.0

    def test_scenario_with_system_methods(self):
        """Test that system methods are called when available."""
        bench = OPIB()
        bench.add_scenario(OPIBScenario(
            scenario_id="s1", name="Test", description="", domain="industrial",
            phases=["observe"],
        ))

        class MockSystem:
            def opib_observe(self, state):
                return True

        results = bench.run_benchmark(system=MockSystem())
        assert results[0].phases_completed == ["observe"]

    def test_scenario_with_failing_system_method(self):
        bench = OPIB()
        bench.add_scenario(OPIBScenario(
            scenario_id="s1", name="Test", description="", domain="industrial",
            phases=["observe", "act"],
        ))

        class MockSystem:
            def opib_observe(self, state):
                return True

            def opib_act(self, state):
                return False  # Action failed

        results = bench.run_benchmark(system=MockSystem())
        assert "observe" in results[0].phases_completed
        assert "act" in results[0].phases_failed
        assert results[0].success is False
        assert results[0].safety_events == 1
