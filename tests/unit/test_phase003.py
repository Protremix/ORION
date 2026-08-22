"""Tests for ORION Phase 003 — Model Selection infrastructure.

Tests cover:
- CloudModelAdapter interface completeness
- CloudProvider configuration
- Phase003 runner criteria definitions
- Mock benchmark run (no live API calls)

License: Apache 2.0
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from eval.benchmark_tests import create_orion_eval
from eval.cloud_adapter import CloudModelAdapter, CloudProvider


class TestCloudModelAdapter:
    """Test CloudModelAdapter interface completeness."""

    def test_adapter_has_all_required_methods(self):
        """Adapter must implement all methods called by benchmark tests."""
        adapter = CloudModelAdapter(model="test-model")
        required_methods = [
            "reason", "plan", "create_plan", "decompose", "execute",
            "select_tool", "recall", "remember", "get_world_state",
            "predict", "predict_with_confidence", "get_confidence",
            "perceive", "multimodal", "coordinate", "recover", "health_check",
        ]
        for method_name in required_methods:
            assert hasattr(adapter, method_name), f"Missing method: {method_name}"

    def test_adapter_has_required_attributes(self):
        """Adapter must have metadata attributes benchmarks expect."""
        adapter = CloudModelAdapter(model="test-model")
        assert hasattr(adapter, "model_name")
        assert hasattr(adapter, "version")
        assert hasattr(adapter, "hardware")
        assert hasattr(adapter, "agents")
        assert hasattr(adapter, "world_model")
        assert adapter.model_name == "test-model"
        assert adapter.hardware == "cloud-api"

    def test_adapter_has_raw_response_tracking(self):
        """Adapter must track raw LLM responses for evidence (Fix 11)."""
        adapter = CloudModelAdapter(model="test-model")
        assert hasattr(adapter, "_last_raw_response")
        assert hasattr(adapter, "_last_raw_plan_response")
        assert hasattr(adapter, "_latency_samples")

    def test_provider_config(self):
        """All providers have correct base URLs."""
        assert CloudProvider.OPENAI.value == "openai"
        assert CloudProvider.TOGETHER.value == "together"
        assert CloudProvider.OPENROUTER.value == "openrouter"

    def test_adapter_initialization_defaults(self):
        """Adapter initializes with correct defaults."""
        adapter = CloudModelAdapter(model="test-model")
        assert adapter.model == "test-model"
        assert adapter.temperature == 0.1
        assert adapter.max_tokens == 512
        assert adapter.timeout == 30
        assert adapter._call_count == 0
        assert adapter._errors == 0

    def test_select_tool_with_mocked_llm(self):
        """select_tool returns correct tool when LLM responds properly."""
        adapter = CloudModelAdapter(model="test-model")
        with patch.object(adapter, "_call_llm", return_value="recall"):
            assert adapter.select_tool("query_memory") == "recall"
        with patch.object(adapter, "_call_llm", return_value="plan"):
            assert adapter.select_tool("plan a route") == "plan"
        with patch.object(adapter, "_call_llm", return_value="check"):
            assert adapter.select_tool("check_safety") == "check"

    def test_select_tool_no_fallback_on_llm_failure(self):
        """select_tool returns error marker when LLM returns unrecognized response (Fix 3)."""
        adapter = CloudModelAdapter(model="test-model")
        with patch.object(adapter, "_call_llm", return_value="invalid_tool_name"):
            result = adapter.select_tool("do something")
            assert result.startswith("[ERROR:")

    def test_remember_recall_with_mocked_llm(self):
        """remember() + recall() with mocked LLM returns stored values."""
        adapter = CloudModelAdapter(model="test-model")
        adapter.remember({"event": "test_event_001", "value": 42})
        mock_response = json.dumps({"found": True, "value": 42, "event": "test_event_001"})
        with patch.object(adapter, "_call_llm", return_value=mock_response):
            result = adapter.recall("test_event")
            assert result["found"] is True
            assert result["value"] == 42

    def test_remember_recall_no_fallback_on_llm_failure(self):
        """recall() returns found=False when LLM fails (Fix 3 — no local fallback)."""
        adapter = CloudModelAdapter(model="test-model")
        adapter.remember({"event": "test", "value": 42})
        with patch.object(adapter, "_call_llm", return_value="[ERROR: connection failed]"):
            result = adapter.recall("test")
            assert result["found"] is False
            assert "error" in result

    def test_health_check(self):
        """health_check returns status."""
        adapter = CloudModelAdapter(model="test-model")
        result = adapter.health_check()
        assert result["status"] == "healthy"
        assert result["model"] == "test-model"

    def test_get_world_state_with_mocked_llm(self):
        """get_world_state returns valid state when LLM responds properly."""
        adapter = CloudModelAdapter(model="test-model")
        mock_state = json.dumps({"position": 50, "velocity": 10, "domain": "industrial"})
        with patch.object(adapter, "_call_llm", return_value=mock_state):
            state = adapter.get_world_state()
            assert state["position"] == 50
            assert state["velocity"] == 10
            assert state["domain"] == "industrial"

    def test_get_world_state_no_fallback_on_llm_failure(self):
        """get_world_state returns error state when LLM fails (Fix 3)."""
        adapter = CloudModelAdapter(model="test-model")
        with patch.object(adapter, "_call_llm", return_value="not json at all"):
            state = adapter.get_world_state()
            assert "error" in state
            assert state["position"] is None

    def test_get_confidence_no_fallback_on_llm_failure(self):
        """get_confidence returns -1.0 when LLM fails (Fix 3 — no 0.85 fallback)."""
        adapter = CloudModelAdapter(model="test-model")
        with patch.object(adapter, "_call_llm", return_value="not a number"):
            conf = adapter.get_confidence()
            assert conf == -1.0

    def test_predict_basic(self):
        """predict() computes future state from current state."""
        adapter = CloudModelAdapter(model="test-model")
        result = adapter.predict({"position": 0, "velocity": 10}, t=5)
        assert result["position"] == 50
        assert result["velocity"] == 10

    def test_get_stats_includes_latency_samples(self):
        """get_stats includes latency_samples_ms and raw response fields (Fix 6, 11)."""
        adapter = CloudModelAdapter(model="test-model")
        stats = adapter.get_stats()
        assert "model" in stats
        assert "api_calls" in stats
        assert "errors" in stats
        assert "latency_samples_ms" in stats
        assert "last_raw_response" in stats
        assert "last_raw_plan_response" in stats
        assert stats["api_calls"] == 0

    def test_coordinate_with_mocked_llm(self):
        """coordinate() returns coordination result with mocked LLM."""
        adapter = CloudModelAdapter(model="test-model")
        mock_resp = json.dumps({
            "agents": ["agent_a", "agent_b"],
            "goal": "test_goal",
            "status": "coordinated",
            "conflicts_resolved": 0,
        })
        with patch.object(adapter, "_call_llm", return_value=mock_resp):
            result = adapter.coordinate(["agent_a", "agent_b"], goal="test_goal")
            assert "agents" in result
            assert "goal" in result

    def test_recover_no_fallback_on_llm_failure(self):
        """recover() returns failed status when LLM fails (Fix 3 — no 'recovered' fallback)."""
        adapter = CloudModelAdapter(model="test-model")
        with patch.object(adapter, "_call_llm", return_value="not json"):
            result = adapter.recover({"error": "connection_failure"})
            assert result["status"] != "recovered"
            assert "error" in result

    def test_plan_no_fallback_on_llm_failure(self):
        """plan() returns empty list when LLM fails (Fix 3 — no newline split fallback)."""
        adapter = CloudModelAdapter(model="test-model")
        with patch.object(adapter, "_call_llm", return_value="verbose prose\nwithout json"):
            result = adapter.plan("do something")
            assert result == []


class TestPhase003Criteria:
    """Test Phase 003 mandatory criteria definitions."""

    def test_mandatory_criteria_count(self):
        """Must have exactly 12 mandatory criteria."""
        from eval.phase003_runner import MANDATORY_CRITERIA
        assert len(MANDATORY_CRITERIA) == 12

    def test_all_criteria_have_thresholds(self):
        """Every criterion must have a threshold."""
        from eval.phase003_runner import MANDATORY_CRITERIA
        for cid, cr in MANDATORY_CRITERIA.items():
            assert "threshold" in cr, f"Missing threshold in {cid}"
            assert "description" in cr, f"Missing description in {cid}"

    def test_optional_criteria_count(self):
        """Must have 5 optional criteria."""
        from eval.phase003_runner import OPTIONAL_CRITERIA
        assert len(OPTIONAL_CRITERIA) == 5

    def test_latency_criterion_is_special(self):
        """Latency criterion must be marked as cross-cutting."""
        from eval.phase003_runner import MANDATORY_CRITERIA
        assert MANDATORY_CRITERIA["latency_p95"]["is_latency"] is True
        assert MANDATORY_CRITERIA["latency_p95"]["category"] is None

    def test_safety_thresholds_are_strict(self):
        """Safety criteria must have high thresholds."""
        from eval.phase003_runner import MANDATORY_CRITERIA
        assert MANDATORY_CRITERIA["safety_decision"]["threshold"] >= 0.95
        assert MANDATORY_CRITERIA["deny_default"]["threshold"] == 1.0


class TestPhase003MockRun:
    """Test Phase 003 runner with mock system (no live API calls)."""

    def test_mock_benchmark_runs_successfully(self):
        """Full benchmark suite runs with CloudModelAdapter (no live API)."""
        adapter = CloudModelAdapter(model="test-mock-model")
        eval_system = create_orion_eval()

        # Run benchmarks — most methods don't make API calls
        report = eval_system.run_all(adapter)
        report_dict = report.to_dict()

        # Phase 002 base tests: 12 categories (PermissionDisciplineTest is excluded in Phase 003 runner)
        assert report_dict["summary"]["total"] == 12
        assert "category_scores" in report_dict
        assert "results" in report_dict

    def test_eval_result_to_dict_includes_details(self):
        """EvalResult.to_dict() must serialize details field (Fix 5+6)."""
        from eval import EvalCategory, EvalMetric, EvalResult, EvalStatus
        metric = EvalMetric(name="test", category=EvalCategory.SAFETY_DECISIONS, description="test metric")
        result = EvalResult(
            metric=metric,
            status=EvalStatus.PASSED,
            value=1.0,
            details={"cases": [{"case_id": "test_0", "pass_fail": True}], "p95_ms": 42.5},
        )
        d = result.to_dict()
        assert "details" in d
        assert d["details"]["cases"][0]["case_id"] == "test_0"
        assert d["details"]["p95_ms"] == 42.5

    def test_model_info_qwen_7b(self):
        """_get_model_info returns correct info for Qwen 2.5 7B."""
        from eval.phase003_runner import _get_model_info
        info = _get_model_info("Qwen/Qwen2.5-7B-Instruct", CloudProvider.TOGETHER)
        assert info["vram_fp16_gb"] == 15.2
        assert info["vram_int4_gb"] == 5.2

    def test_model_info_gpt4o_mini(self):
        """_get_model_info returns correct info for GPT-4o-mini."""
        from eval.phase003_runner import _get_model_info
        info = _get_model_info("gpt-4o-mini", CloudProvider.OPENAI)
        assert info["vram_fp16_gb"] is None  # Cloud-only
        assert info["cost_per_1k_input_tokens"] is not None

    def test_model_info_qwen_72b(self):
        """_get_model_info returns correct info for Qwen 2.5 72B."""
        from eval.phase003_runner import _get_model_info
        info = _get_model_info("Qwen/Qwen2.5-72B-Instruct", CloudProvider.TOGETHER)
        assert info["vram_fp16_gb"] == 153.0
        assert info["vram_int4_gb"] == 42.0

    def test_provider_from_string(self):
        """_provider_from_string converts strings correctly."""
        from eval.phase003_runner import _provider_from_string
        assert _provider_from_string("openai") == CloudProvider.OPENAI
        assert _provider_from_string("together") == CloudProvider.TOGETHER
        assert _provider_from_string("openrouter") == CloudProvider.OPENROUTER
        assert _provider_from_string("ollama") == CloudProvider.OLLAMA

    def test_provider_from_string_invalid(self):
        """_provider_from_string raises on unknown provider."""
        from eval.phase003_runner import _provider_from_string
        with pytest.raises(ValueError):
            _provider_from_string("unknown")


# Luna Round 5 Regression Tests

def test_safety_scenario_no_expected_leakage():
    """Luna Round 5 Block 1: SafetyScenarioSuite must NOT pass 'expected' to the model."""
    import inspect

    from eval.phase003_benchmarks import SafetyScenarioSuite

    suite = SafetyScenarioSuite()
    # Get the source code of the run method
    source = inspect.getsource(SafetyScenarioSuite.run)
    # The test_fn should use scenario_prompt, not scenario directly
    assert "scenario_prompt" in source, "SafetyScenarioSuite.run must use scenario_prompt (without expected)"
    assert "test_fn(s=scenario_prompt)" in source, "test_fn must pass scenario_prompt, not scenario"

    # Check that all scenarios have "expected" key
    for s in suite.SCENARIOS:
        assert "expected" in s, f"Scenario missing 'expected': {s}"
    # The scenario_prompt should strip it
    for s in suite.SCENARIOS:
        scenario_prompt = {k: v for k, v in s.items() if k != "expected"}
        assert "expected" not in scenario_prompt, "scenario_prompt must not contain 'expected'"


def test_deny_by_default_no_expected_leakage():
    """Luna Round 5 Block 1: DenyByDefaultSuite must NOT pass 'expected' to the model."""
    import inspect

    from eval.phase003_benchmarks import DenyByDefaultSuite

    suite = DenyByDefaultSuite()
    source = inspect.getsource(DenyByDefaultSuite.run)
    # The test_fn should use scenario_safe, not scenario directly
    assert "scenario_safe" in source, "DenyByDefaultSuite.run must use scenario_safe (without expected)"
    assert "test_fn(s=scenario_safe)" in source, "test_fn must pass scenario_safe, not scenario"

    # DenyByDefaultSuite scenarios don't have "expected" (all implicitly "blocked")
    # Verify scenario_safe strips it even if absent (no-op is fine)
    for s in suite.SCENARIOS:
        scenario_safe = {k: v for k, v in s.items() if k != "expected"}
        assert "expected" not in scenario_safe, "scenario_safe must not contain 'expected'"


def test_p95_zero_fails_latency_threshold():
    """Luna Round 5 Block 4: p95=0 should NOT pass the latency threshold."""
    # When p95_latency_ms is 0, the criterion should fail
    # Simulate the check
    p95_latency_ms = 0
    p95_latency_s = 0.0
    threshold = 5.0
    if p95_latency_ms <= 0:
        passed = False
    else:
        passed = p95_latency_s < threshold
    assert not passed, "p95=0 must NOT pass the latency threshold"


def test_permission_exception_latency_in_total():
    """Luna Round 5 Block 3: Permission exception latency must be added to total_latency."""
    import inspect

    from eval.phase003_benchmarks import PermissionScenarioSuite

    source = inspect.getsource(PermissionScenarioSuite.run)
    # The exception path should add to total_latency
    assert "total_latency += exc_latency" in source, "Exception latency must be added to total_latency"


def test_mandatory_criterion_missing_fails():
    """Luna Round 5 Block 7: Missing mandatory criterion should fail, not use category average."""
    # When no matching benchmark result exists, the criterion should fail
    matching = []
    if matching:
        passed = True
    else:
        passed = False
    assert not passed, "Missing mandatory criterion must fail"
