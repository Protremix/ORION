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

from eval.cloud_adapter import CloudModelAdapter, CloudProvider
from eval.benchmark_tests import create_orion_eval


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

    def test_select_tool_maps_memory_tasks(self):
        """select_tool returns 'recall' for memory-related tasks."""
        adapter = CloudModelAdapter(model="test-model")
        assert adapter.select_tool("query_memory") == "recall"
        assert adapter.select_tool("recall past events") == "recall"
        assert adapter.select_tool("query database") == "recall"

    def test_select_tool_maps_planning_tasks(self):
        """select_tool returns 'plan' for planning tasks."""
        adapter = CloudModelAdapter(model="test-model")
        assert adapter.select_tool("plan a route") == "plan"

    def test_select_tool_maps_safety_tasks(self):
        """select_tool returns 'check' for safety tasks."""
        adapter = CloudModelAdapter(model="test-model")
        assert adapter.select_tool("check_safety") == "check"

    def test_remember_recall_roundtrip(self):
        """remember() + recall() stores and retrieves values correctly."""
        adapter = CloudModelAdapter(model="test-model")
        test_data = {"event": "test_event_001", "value": 42}
        adapter.remember(test_data)
        result = adapter.recall("test_event")
        assert result["found"] is True
        assert result["value"] == 42
        assert result["event"] == "test_event_001"

    def test_remember_recall_simple_value(self):
        """recall() works with non-dict values."""
        adapter = CloudModelAdapter(model="test-model")
        adapter.remember(123)
        result = adapter.recall("anything")
        assert result["found"] is True
        assert result["value"] == 123

    def test_health_check(self):
        """health_check returns status."""
        adapter = CloudModelAdapter(model="test-model")
        result = adapter.health_check()
        assert result["status"] == "healthy"
        assert result["model"] == "test-model"

    def test_get_world_state(self):
        """get_world_state returns valid state dict."""
        adapter = CloudModelAdapter(model="test-model")
        state = adapter.get_world_state()
        assert "position" in state
        assert "velocity" in state
        assert "agents" in state

    def test_predict_basic(self):
        """predict() computes future state from current state."""
        adapter = CloudModelAdapter(model="test-model")
        result = adapter.predict({"position": 0, "velocity": 10}, t=5)
        assert result["position"] == 50
        assert result["velocity"] == 10

    def test_get_stats(self):
        """get_stats returns call statistics."""
        adapter = CloudModelAdapter(model="test-model")
        stats = adapter.get_stats()
        assert "model" in stats
        assert "api_calls" in stats
        assert "errors" in stats
        assert stats["api_calls"] == 0

    def test_coordinate_returns_dict(self):
        """coordinate() returns coordination result."""
        adapter = CloudModelAdapter(model="test-model")
        result = adapter.coordinate(["agent_a", "agent_b"], goal="test_goal")
        assert "agents" in result
        assert "goal" in result

    def test_recover_returns_recovered_status(self):
        """recover() returns 'recovered' status."""
        adapter = CloudModelAdapter(model="test-model")
        result = adapter.recover({"error": "connection_failure"})
        # Without a live API call, fallback returns "recovered"
        assert result["status"] in ("recovered", "healthy", "ok")


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
        # (get_world_state, predict, health_check, get_confidence are local)
        report = eval_system.run_all(adapter)
        report_dict = report.to_dict()

        assert report_dict["summary"]["total"] == 12
        assert "category_scores" in report_dict
        assert "results" in report_dict

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

    def test_provider_from_string_invalid(self):
        """_provider_from_string raises on unknown provider."""
        from eval.phase003_runner import _provider_from_string
        with pytest.raises(ValueError):
            _provider_from_string("unknown")
