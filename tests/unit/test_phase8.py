"""
Tests for GPT-4o concrete adapters, autonomous planner, and task state system.
"""

import pytest
import os
import json
import tempfile
import time
from unittest.mock import MagicMock, patch, AsyncMock

from src.models.gpt4o_adapters import (
    GPT4oTextAdapter, GPT4oVisionAdapter, OpenAIEmbeddingAdapter,
    create_default_registry, _openai_request,
)
from src.models import (
    TextRequest, TextResponse, VisionRequest, VisionResponse,
    EmbeddingRequest, EmbeddingResponse, ModelRegistry,
)
from src.planning import (
    AutonomousPlanner, ExecutionPlan, SubGoal, Action,
    PlanStatus, 
)
from src.persistence.task_state import (
    TaskStateManager, Task, Checkpoint, SystemState,
    TaskStatus, CheckpointType,
)


# ============================================================================
# GPT-4o Adapter Tests (Mocked — no live API calls)
# ============================================================================

class TestGPT4oTextAdapter:
    def test_descriptor(self):
        adapter = GPT4oTextAdapter(api_key="test-key")
        desc = adapter.get_descriptor()
        assert desc.model_type.value == "llm"
        assert desc.provider == "openai"

    def test_health_check_no_key(self):
        # Create adapter with no key, then clear env vars
        with patch.dict(os.environ, {}, clear=True):
            adapter = GPT4oTextAdapter(api_key=None)
            assert adapter._api_key is None
            assert adapter.health_check() is False

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_generate_success(self, mock_api):
        mock_api.return_value = {
            "choices": [{"message": {"content": "Hello from GPT-4o"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 50},
            "id": "test-id",
        }
        adapter = GPT4oTextAdapter(api_key="test-key")
        resp = adapter.generate(TextRequest(prompt="Say hello"))
        assert resp.text == "Hello from GPT-4o"
        assert resp.tokens_used == 50
        assert resp.finish_reason == "stop"
        assert resp.latency_ms > 0

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_generate_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        adapter = GPT4oTextAdapter(api_key="test-key")
        resp = adapter.generate(TextRequest(prompt="test"))
        assert resp.text == ""
        assert resp.finish_reason == "error"
        assert "error" in resp.metadata

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_generate_async(self, mock_api):
        mock_api.return_value = {
            "choices": [{"message": {"content": "async response"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10},
        }
        adapter = GPT4oTextAdapter(api_key="test-key")
        import asyncio
        resp = asyncio.get_event_loop().run_until_complete(adapter.generate_async(TextRequest(prompt="test")))
        assert resp.text == "async response"

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_health_check_success(self, mock_api):
        mock_api.return_value = {"choices": [{"message": {"content": "pong"}}]}
        adapter = GPT4oTextAdapter(api_key="test-key")
        assert adapter.health_check() is True


class TestGPT4oVisionAdapter:
    def test_descriptor(self):
        adapter = GPT4oVisionAdapter(api_key="test-key")
        desc = adapter.get_descriptor()
        assert desc.model_type.value == "vision"

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_process_describe(self, mock_api):
        mock_api.return_value = {
            "choices": [{"message": {"content": "A red car on a highway"}, "finish_reason": "stop"}],
        }
        adapter = GPT4oVisionAdapter(api_key="test-key")
        resp = adapter.process(VisionRequest(image_url="http://example.com/img.png", task="describe"))
        assert "red car" in resp.description
        assert resp.latency_ms > 0

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_process_answer(self, mock_api):
        mock_api.return_value = {
            "choices": [{"message": {"content": "There are 3 people"}, "finish_reason": "stop"}],
        }
        adapter = GPT4oVisionAdapter(api_key="test-key")
        resp = adapter.process(VisionRequest(image_url="http://example.com/img.png", task="answer", prompt="How many people?"))
        assert resp.answer == "There are 3 people"

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_process_error(self, mock_api):
        mock_api.side_effect = Exception("Vision API error")
        adapter = GPT4oVisionAdapter(api_key="test-key")
        resp = adapter.process(VisionRequest(image_url="http://example.com/img.png"))
        assert resp.description == ""
        assert "error" in resp.metadata

    def test_process_no_image(self):
        adapter = GPT4oVisionAdapter(api_key="test-key")
        resp = adapter.process(VisionRequest())
        assert resp.description == ""
        assert "error" in resp.metadata

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_health_check(self, mock_api):
        mock_api.return_value = {"choices": [{"message": {"content": "pong"}}]}
        adapter = GPT4oVisionAdapter(api_key="test-key")
        assert adapter.health_check() is True


class TestOpenAIEmbeddingAdapter:
    def test_descriptor(self):
        adapter = OpenAIEmbeddingAdapter(api_key="test-key")
        desc = adapter.get_descriptor()
        assert desc.model_type.value == "embedding"

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_embed_success(self, mock_api):
        mock_api.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}],
        }
        adapter = OpenAIEmbeddingAdapter(api_key="test-key")
        resp = adapter.embed(EmbeddingRequest(text="test text"))
        assert resp.vector == [0.1, 0.2, 0.3, 0.4]
        assert resp.dimensions == 4
        assert resp.latency_ms > 0

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_embed_error(self, mock_api):
        mock_api.side_effect = Exception("Embedding API error")
        adapter = OpenAIEmbeddingAdapter(api_key="test-key")
        resp = adapter.embed(EmbeddingRequest(text="test"))
        assert resp.vector == []
        assert resp.dimensions == 0

    def test_embed_no_text(self):
        adapter = OpenAIEmbeddingAdapter(api_key="test-key")
        with pytest.raises(ValueError):
            adapter.embed(EmbeddingRequest())


class TestDefaultRegistry:
    def test_create_default_registry(self):
        registry = create_default_registry(api_key="test-key")
        models = registry.list_models()
        assert "gpt-4o" in models["text"]
        assert "gpt-4o" in models["vision"]
        assert "text-embedding-3" in models["embedding"]
        assert registry.get_text() is not None
        assert registry.get_vision() is not None
        assert registry.get_embedding() is not None


# ============================================================================
# Autonomous Planner Tests
# ============================================================================

class TestAutonomousPlanner:
    def test_rule_based_decompose(self):
        planner = AutonomousPlanner()
        sub_goals = planner.decompose("Move robot to position A", "industrial")
        assert len(sub_goals) >= 3
        assert sub_goals[0].description.startswith("Observe")
        assert sub_goals[-1].description.startswith("Verify")
        # Dependencies should form a chain
        assert len(sub_goals[1].dependencies) == 1
        assert sub_goals[1].dependencies[0] == sub_goals[0].id

    def test_rule_based_decompose_safety_level(self):
        planner = AutonomousPlanner()
        sub_goals = planner.decompose("Move vehicle forward", "vehicle")
        # "move" in goal should trigger SC_1 for the execution sub-goal
        exec_sg = [sg for sg in sub_goals if "Execute" in sg.description][0]
        assert exec_sg.safety_level == "SC_1"

    def test_generate_actions_rule_based(self):
        planner = AutonomousPlanner()
        sg = SubGoal(id="sg_1", description="Test sub-goal", priority=1)
        actions = planner.generate_actions(sg, "industrial")
        assert len(actions) >= 1
        assert actions[0].action_type == "observe"

    def test_generate_actions_high_priority(self):
        planner = AutonomousPlanner()
        sg = SubGoal(id="sg_1", description="Critical action", priority=2)
        actions = planner.generate_actions(sg, "industrial")
        # High priority should generate observe + execute + verify
        assert len(actions) >= 2
        assert any(a.action_type == "execute" for a in actions)

    def test_full_plan_no_dependencies(self):
        planner = AutonomousPlanner()
        plan = planner.plan("Optimize factory output", "industrial")
        assert plan.status == PlanStatus.READY or plan.status == PlanStatus.SAFETY_BLOCKED
        assert len(plan.sub_goals) >= 3
        assert len(plan.actions) >= 1
        assert plan.id.startswith("plan_")

    def test_full_plan_with_safety_gateway(self):
        """Plan should be safety_blocked when gateway rejects actions."""
        gateway = MagicMock()
        gateway.check_action.return_value = False  # All actions unsafe
        planner = AutonomousPlanner(safety_gateway=gateway)
        plan = planner.plan("Move robot", "industrial")
        assert plan.status == PlanStatus.SAFETY_BLOCKED
        assert not plan.safety_verified
        assert len(plan.metadata.get("safety_violations", [])) > 0

    def test_full_plan_safety_gateway_passes(self):
        """Plan should be READY when gateway approves all actions."""
        gateway = MagicMock()
        gateway.check_action.return_value = True
        planner = AutonomousPlanner(safety_gateway=gateway)
        plan = planner.plan("Check sensor readings", "industrial")
        assert plan.status == PlanStatus.READY
        assert plan.safety_verified

    def test_plan_with_simulator(self):
        simulator = MagicMock()
        simulator.simulate_plan.return_value = {"success": True}
        planner = AutonomousPlanner(simulator=simulator)
        plan = planner.plan("Test goal", "industrial")
        assert plan.simulation_verified

    def test_plan_simulator_failure(self):
        simulator = MagicMock()
        simulator.simulate_plan.return_value = {"success": False, "errors": ["Collision"]}
        planner = AutonomousPlanner(simulator=simulator)
        plan = planner.plan("Move robot through wall", "industrial")
        assert plan.status == PlanStatus.FAILED
        assert not plan.simulation_verified

    def test_no_safety_gateway(self):
        """Without safety gateway, plan cannot be verified."""
        planner = AutonomousPlanner()
        plan = planner.plan("Test goal", "industrial")
        # No safety gateway → safety_verified = False
        assert not plan.safety_verified
        assert "warning" in plan.metadata

    def test_execution_plan_to_dict(self):
        plan = ExecutionPlan(id="test_plan", goal="test")
        plan.sub_goals = [SubGoal(id="sg1", description="test")]
        plan.actions = [Action(id="a1", action_type="observe", target="sensor")]
        d = plan.to_dict()
        assert d["id"] == "test_plan"
        assert d["sub_goals"] == 1
        assert d["actions"] == 1

    def test_plan_ids_increment(self):
        planner = AutonomousPlanner()
        plan1 = planner.plan("Goal 1", "industrial")
        plan2 = planner.plan("Goal 2", "industrial")
        assert plan1.id != plan2.id

    def test_sub_goal_dependencies_chain(self):
        planner = AutonomousPlanner()
        sub_goals = planner.decompose("Complex goal", "industrial")
        # Each sub-goal should depend on the previous one (chain)
        for i in range(1, len(sub_goals)):
            assert sub_goals[i-1].id in sub_goals[i].dependencies or len(sub_goals[i].dependencies) == 0


# ============================================================================
# Task State Manager Tests
# ============================================================================

class TestTaskStateManager:
    def test_create_and_get_task(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        task = mgr.create_task("Test", "A test task")
        assert task.name == "Test"
        assert task.status == TaskStatus.PENDING
        assert mgr.get_task(task.id) is not None

    def test_start_task(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        task = mgr.create_task("Test", "test")
        assert mgr.start_task(task.id)
        updated = mgr.get_task(task.id)
        assert updated.status == TaskStatus.IN_PROGRESS
        assert updated.started_at is not None

    def test_complete_task(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        task = mgr.create_task("Test", "test")
        mgr.start_task(task.id)
        mgr.complete_task(task.id, result={"output": "done"})
        updated = mgr.get_task(task.id)
        assert updated.status == TaskStatus.COMPLETED
        assert updated.progress == 1.0
        assert updated.metadata["result"]["output"] == "done"

    def test_fail_task(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        task = mgr.create_task("Test", "test")
        mgr.fail_task(task.id, "Something went wrong")
        updated = mgr.get_task(task.id)
        assert updated.status == TaskStatus.FAILED
        assert updated.error == "Something went wrong"

    def test_update_progress(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        task = mgr.create_task("Test", "test")
        mgr.update_progress(task.id, 0.5)
        assert mgr.get_task(task.id).progress == 0.5
        # Out of range should be clamped
        mgr.update_progress(task.id, 1.5)
        assert mgr.get_task(task.id).progress == 1.0
        mgr.update_progress(task.id, -0.5)
        assert mgr.get_task(task.id).progress == 0.0

    def test_list_tasks_by_status(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        t1 = mgr.create_task("T1", "test")
        t2 = mgr.create_task("T2", "test")
        mgr.start_task(t2.id)
        pending = mgr.list_tasks(status=TaskStatus.PENDING)
        in_progress = mgr.list_tasks(status=TaskStatus.IN_PROGRESS)
        assert len(pending) == 1
        assert len(in_progress) == 1

    def test_unfinished_tasks(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        t1 = mgr.create_task("T1", "test")
        t2 = mgr.create_task("T2", "test")
        mgr.complete_task(t1.id)
        unfinished = mgr.get_unfinished_tasks()
        assert len(unfinished) == 1
        assert unfinished[0].id == t2.id

    def test_checkpoint_create_and_get(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        task = mgr.create_task("Test", "test")
        cp = mgr.create_checkpoint(task.id, CheckpointType.BEFORE_ACTION, state={"step": 1})
        assert cp.task_id == task.id
        assert cp.type == CheckpointType.BEFORE_ACTION
        assert mgr.get_checkpoint(cp.id) is not None
        assert mgr.get_last_checkpoint(task.id).id == cp.id

    def test_checkpoint_verify(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        task = mgr.create_task("Test", "test")
        cp = mgr.create_checkpoint(task.id, CheckpointType.AFTER_ACTION)
        assert mgr.verify_checkpoint(cp.id)
        assert mgr.get_checkpoint(cp.id).verified

    def test_persistence_save_load(self, tmp_path):
        path = str(tmp_path / "state.json")
        mgr1 = TaskStateManager(path)
        t = mgr1.create_task("Persistent", "survives restart")
        mgr1.start_task(t.id)
        cp = mgr1.create_checkpoint(t.id, CheckpointType.PHASE_COMPLETE, description="Phase 1 done")

        # New manager loads from same file
        mgr2 = TaskStateManager(path)
        assert len(mgr2.list_tasks()) == 1
        loaded = mgr2.get_task(t.id)
        assert loaded.name == "Persistent"
        assert loaded.status == TaskStatus.IN_PROGRESS
        assert len(mgr2._checkpoints) == 1

    def test_shutdown_and_resume(self, tmp_path):
        path = str(tmp_path / "state.json")
        mgr = TaskStateManager(path)
        task = mgr.create_task("Long task", "takes a while")
        mgr.start_task(task.id)
        mgr.create_checkpoint(task.id, CheckpointType.BEFORE_ACTION, state={"step": 5})
        mgr.shutdown("FINANCIAL: Hardware purchase required", recommendation="Approve $5000 for GPU")

        # Verify shutdown state
        assert mgr._stop_reason == "FINANCIAL: Hardware purchase required"
        assert len(mgr._pending_decisions) == 1
        assert mgr.get_task(task.id).status == TaskStatus.DECISION_REQUIRED

        # Resume
        mgr2 = TaskStateManager(path)
        result = mgr2.resume()
        assert len(result["unfinished_tasks"]) >= 1
        assert result["stop_reason"] == "FINANCIAL: Hardware purchase required"
        assert result["resume_from"] is not None

    def test_health_status(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        t1 = mgr.create_task("T1", "test")
        t2 = mgr.create_task("T2", "test")
        mgr.start_task(t1.id)
        mgr.complete_task(t2.id)
        mgr.create_checkpoint(t1.id, CheckpointType.MANUAL)

        health = mgr.health_status()
        assert health["total_tasks"] == 2
        assert health["completed"] == 1
        assert health["in_progress"] == 1
        assert health["total_checkpoints"] == 1

    def test_sub_tasks(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        parent = mgr.create_task("Parent", "parent task")
        child = mgr.create_task("Child", "child task", parent_task=parent.id)
        assert child.id in mgr.get_task(parent.id).sub_tasks

    def test_retry_tracking(self, tmp_path):
        mgr = TaskStateManager(str(tmp_path / "state.json"))
        task = mgr.create_task("Retry test", "test")
        assert task.retries == 0
        assert task.max_retries == 3

    def test_empty_state_load(self, tmp_path):
        """Loading from non-existent file should start fresh."""
        mgr = TaskStateManager(str(tmp_path / "nonexistent.json"))
        assert len(mgr.list_tasks()) == 0
        assert mgr.health_status()["total_tasks"] == 0
