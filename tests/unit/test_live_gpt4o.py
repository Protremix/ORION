"""
ORION Live GPT-4o Integration Tests — Phase 3 Live Perception

These tests make REAL API calls to OpenAI. They verify the concrete
adapters work end-to-end with the live GPT-4o model.

Requires: OPENAI_PROJECT_KEY or OPENAI_API_KEY environment variable.
Token costs are accepted per Founder directive.

License: Apache 2.0
"""

import base64
import json
import os
import time

import pytest

# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_PROJECT_KEY") and not os.environ.get("OPENAI_API_KEY"),
    reason="No OpenAI API key available (OPENAI_PROJECT_KEY or OPENAI_API_KEY)"
)

from src.models import EmbeddingRequest, TextRequest, VisionRequest
from src.models.gpt4o_adapters import (
    GPT4oTextAdapter,
    GPT4oVisionAdapter,
    OpenAIEmbeddingAdapter,
    create_default_registry,
)
from src.planning import AutonomousPlanner, PlanStatus
from src.world_model import StateSnapshot, WorldModel

# ============================================================================
# Live Text Adapter Tests
# ============================================================================

class TestLiveTextAdapter:
    def test_live_text_generation(self):
        adapter = GPT4oTextAdapter()
        resp = adapter.generate(TextRequest(
            prompt="What is 2+2? Answer with just the number.",
            max_tokens=10,
            temperature=0.0,
        ))
        assert resp.text.strip() == "4"
        assert resp.tokens_used > 0
        assert resp.finish_reason == "stop"
        assert resp.latency_ms > 0

    def test_live_text_with_system_prompt(self):
        adapter = GPT4oTextAdapter()
        resp = adapter.generate(TextRequest(
            prompt="What is your name?",
            system_prompt="You are ORION, an AI agent. Always respond with 'ORION' when asked your name.",
            max_tokens=10,
            temperature=0.0,
        ))
        assert "ORION" in resp.text

    def test_live_text_reasoning(self):
        adapter = GPT4oTextAdapter()
        resp = adapter.generate(TextRequest(
            prompt="A factory has 3 machines running at 80°C, 75°C, and 90°C. Which machine is most likely to overheat first? Answer in one sentence.",
            system_prompt="You are an industrial safety analyst.",
            max_tokens=100,
            temperature=0.0,
        ))
        assert resp.text is not None
        assert len(resp.text) > 10
        # Should mention the 90°C machine
        assert "90" in resp.text

    def test_live_text_health_check(self):
        adapter = GPT4oTextAdapter()
        assert adapter.health_check() is True


# ============================================================================
# Live Vision Adapter Tests
# ============================================================================

class TestLiveVisionAdapter:
    @pytest.fixture
    def cat_image_b64(self):
        import base64
        import urllib.request
        url = "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=200"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return base64.b64encode(data).decode()

    def test_live_vision_describe(self, cat_image_b64):
        adapter = GPT4oVisionAdapter()
        resp = adapter.process(VisionRequest(
            image_data=base64.b64decode(cat_image_b64),
            task="describe",
            prompt="What animal is in this image? Answer in one word.",
        ))
        assert resp.description is not None
        assert len(resp.description) > 0
        # Should identify a cat
        assert "cat" in resp.description.lower()

    def test_live_vision_health_check(self):
        adapter = GPT4oVisionAdapter()
        assert adapter.health_check() is True


# ============================================================================
# Live Embedding Adapter Tests
# ============================================================================

class TestLiveEmbeddingAdapter:
    def test_live_embedding(self):
        adapter = OpenAIEmbeddingAdapter()
        resp = adapter.embed(EmbeddingRequest(text="factory machine overheating"))
        assert len(resp.vector) > 0
        assert resp.dimensions > 0
        assert resp.dimensions == len(resp.vector)
        assert resp.latency_ms > 0

    def test_live_embedding_dimensions(self):
        adapter = OpenAIEmbeddingAdapter()
        resp = adapter.embed(EmbeddingRequest(text="test"))
        # text-embedding-3-small has 1536 dimensions
        assert resp.dimensions == 1536

    def test_live_embedding_health_check(self):
        adapter = OpenAIEmbeddingAdapter()
        assert adapter.health_check() is True


# ============================================================================
# Live Registry Tests
# ============================================================================

class TestLiveRegistry:
    def test_live_default_registry(self):
        registry = create_default_registry()
        assert registry.get_text() is not None
        assert registry.get_vision() is not None
        assert registry.get_embedding() is not None

        # Verify all are healthy
        assert registry.get_text().health_check()
        assert registry.get_vision().health_check()
        assert registry.get_embedding().health_check()


# ============================================================================
# Live Planner + GPT-4o Tests
# ============================================================================

class TestLivePlanner:
    def test_live_planner_decomposition(self):
        """Planner should use live GPT-4o for goal decomposition."""
        text_adapter = GPT4oTextAdapter()
        planner = AutonomousPlanner(text_adapter=text_adapter)
        sub_goals = planner.decompose("Move robot from station A to station B while avoiding obstacles", "industrial")
        assert len(sub_goals) >= 2
        # Each sub-goal should have a description
        for sg in sub_goals:
            assert len(sg.description) > 5

    def test_live_planner_full_plan(self):
        """Full planning with live GPT-4o decomposition."""
        text_adapter = GPT4oTextAdapter()
        planner = AutonomousPlanner(text_adapter=text_adapter)
        plan = planner.plan("Check all sensors in the factory", "industrial")
        assert plan.status in (PlanStatus.READY, PlanStatus.SAFETY_BLOCKED, PlanStatus.FAILED)
        assert len(plan.sub_goals) >= 2
        assert len(plan.actions) >= 1

    def test_live_planner_action_generation(self):
        """GPT-4o should generate concrete actions for sub-goals."""
        text_adapter = GPT4oTextAdapter()
        planner = AutonomousPlanner(text_adapter=text_adapter)
        from src.planning import SubGoal
        sg = SubGoal(id="sg1", description="Move conveyor belt forward by 1 meter")
        actions = planner.generate_actions(sg, "industrial")
        assert len(actions) >= 1
        # Each action should have a type and target
        for action in actions:
            assert action.action_type is not None
            assert action.target is not None


# ============================================================================
# Live World Model + GPT-4o Tests
# ============================================================================

class TestLiveWorldModel:
    def test_live_world_model_with_planner(self):
        """World Model predictions should inform planner decisions."""
        wm = WorldModel()
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 0, "vy": 0})

        # Predict outcome of different actions
        actions = [
            {"acceleration_x": 1.0, "max_speed": 20},
            {"acceleration_x": 5.0, "max_speed": 30},
            {"acceleration_x": 0, "max_speed": 20},
        ]
        best_action, best_result = wm.select_best_action(state, actions, horizon=10)
        assert best_action is not None
        assert best_result is not None
        assert best_result.safety_assessment is not None


# ============================================================================
# Live End-to-End Pipeline Tests
# ============================================================================

class TestLiveEndToEnd:
    def test_live_full_pipeline(self):
        """Full pipeline: GPT-4o → Planner → World Model → Safety Check."""
        text_adapter = GPT4oTextAdapter()
        wm = WorldModel()
        planner = AutonomousPlanner(text_adapter=text_adapter)

        # 1. GPT-4o decomposes goal
        plan = planner.plan("Drive vehicle safely to destination", "vehicle")
        assert len(plan.sub_goals) >= 2

        # 2. World Model predicts outcome
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 0, "vy": 0})
        prediction = wm.predict(state, {"acceleration_x": 1.0, "max_speed": 20}, horizon=10)
        assert len(prediction.predicted_states) == 10
        assert prediction.safety_assessment is not None

        # 3. Verify pipeline produces safe results
        if plan.status == PlanStatus.READY:
            assert plan.safety_verified or plan.metadata.get("warning") is not None

    def test_live_text_vision_embedding_all_work(self):
        """Verify all three adapter types work live in one test."""
        registry = create_default_registry()

        # Text
        text_resp = registry.get_text().generate(TextRequest(
            prompt="Say 'OK' if you can hear me.",
            max_tokens=5,
            temperature=0.0,
        ))
        assert "OK" in text_resp.text.upper() or len(text_resp.text) > 0

        # Embedding
        emb_resp = registry.get_embedding().embed(EmbeddingRequest(text="test"))
        assert emb_resp.dimensions > 0

        # Vision (download image, send as base64)
        import base64
        import urllib.request
        img_url = "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=200"
        img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(img_req, timeout=10) as img_resp:
            img_data = img_resp.read()
        vision_resp = registry.get_vision().process(VisionRequest(
            image_data=img_data,
            task="describe",
            prompt="One word: what animal?",
        ))
        assert len(vision_resp.description) > 0
