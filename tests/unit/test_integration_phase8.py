"""
ORION Integration Tests — Luna's Phase 3/5 Conditions

1. Integration testing of GPT-4o adapters with domain simulators
2. Autonomous Planner validation with complex goals
3. Stress-testing TaskStateManager under load
4. Cross-module integration: planner + safety + task state + simulators

License: Apache 2.0
"""

import json
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domains.drone.drone_simulator import DroneSimulation
from src.domains.home.home_simulator import HomeSimulation
from src.domains.industrial.industrial_simulator import IndustrialSimulation
from src.domains.vehicle.vehicle_simulator import VehicleSimulation
from src.models import EmbeddingRequest, TextRequest, VisionRequest
from src.models.gpt4o_adapters import (
    GPT4oTextAdapter,
    GPT4oVisionAdapter,
    OpenAIEmbeddingAdapter,
    create_default_registry,
)
from src.persistence.task_state import (
    CheckpointType,
    TaskStateManager,
    TaskStatus,
)
from src.planning import (
    Action,
    AutonomousPlanner,
    ExecutionPlan,
    PlanStatus,
    SubGoal,
)
from src.safety.safety_enforcement import SafetyEnforcement, SafetyScope

# ============================================================================
# Condition 1: Integration Testing of GPT-4o Adapters with Domain Simulators
# ============================================================================

class TestGPT4oWithSimulators:
    """Test GPT-4o adapters integrated with domain simulators."""

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_text_adapter_with_industrial_context(self, mock_api):
        """GPT-4o should generate reasoning about industrial state."""
        sim = IndustrialSimulation()
        state = sim.get_state() if hasattr(sim, 'get_state') else {"machines": 3, "status": "running"}

        mock_api.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "analysis": "Factory operating normally",
                "recommended_action": "monitor",
                "risk_level": "low"
            })}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 100},
        }

        adapter = GPT4oTextAdapter(api_key="test-key")
        resp = adapter.generate(TextRequest(
            prompt=f"Analyze industrial state: {json.dumps(state)}",
            system_prompt="You are ORION's industrial reasoning module.",
        ))
        assert resp.text is not None
        assert resp.tokens_used == 100
        mock_api.assert_called_once()

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_vision_adapter_with_vehicle_scenario(self, mock_api):
        """GPT-4o Vision should process vehicle simulation frames."""
        mock_api.return_value = {
            "choices": [{"message": {"content": "Highway scene: 3 vehicles ahead, clear road, speed limit 120"}, "finish_reason": "stop"}],
        }

        adapter = GPT4oVisionAdapter(api_key="test-key")
        resp = adapter.process(VisionRequest(
            image_url="http://sim/orion/vehicle/frame_001.png",
            task="describe",
            prompt="Describe the traffic situation for autonomous driving",
        ))
        assert "Highway" in resp.description or "road" in resp.description.lower()
        assert resp.latency_ms > 0

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_text_adapter_drone_navigation_reasoning(self, mock_api):
        """GPT-4o should generate drone navigation reasoning."""
        mock_api.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "heading": "north",
                "altitude_change": "+5m",
                "obstacle_detected": False,
                "safe_to_proceed": True
            })}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 80},
        }

        adapter = GPT4oTextAdapter(api_key="test-key")
        resp = adapter.generate(TextRequest(
            prompt="Drone at altitude 50m, wind 10km/h NE. Plan next navigation step.",
            system_prompt="You are ORION's drone navigation module.",
        ))
        assert resp.text is not None
        parsed = json.loads(resp.text)
        assert "heading" in parsed
        assert "safe_to_proceed" in parsed

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_embedding_adapter_with_memory_search(self, mock_api):
        """Embedding adapter should support memory semantic search."""
        mock_api.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}],
        }

        adapter = OpenAIEmbeddingAdapter(api_key="test-key")
        resp = adapter.embed(EmbeddingRequest(text="factory machine overheating alert"))
        assert resp.dimensions == 5
        assert len(resp.vector) == 5

    def test_default_registry_all_adapters_present(self):
        """Default registry should have all 3 adapter types."""
        registry = create_default_registry(api_key="test-key")
        models = registry.list_models()
        assert len(models["text"]) >= 1
        assert len(models["vision"]) >= 1
        assert len(models["embedding"]) >= 1
        # Verify each is the right type
        assert registry.get_text().get_descriptor().model_type.value == "llm"
        assert registry.get_vision().get_descriptor().model_type.value == "vision"
        assert registry.get_embedding().get_descriptor().model_type.value == "embedding"


# ============================================================================
# Condition 2: Autonomous Planner Validation with Complex Goals
# ============================================================================

class TestPlannerComplexGoals:
    """Validate planner with complex, multi-domain goals."""

    def test_complex_goal_decomposition(self):
        """Planner should decompose a complex goal into multiple sub-goals."""
        planner = AutonomousPlanner()
        sub_goals = planner.decompose(
            "Coordinate factory robots to optimize production line while maintaining safety zones",
            "industrial"
        )
        assert len(sub_goals) >= 3
        # Verify dependency chain
        for i in range(1, len(sub_goals)):
            assert any(dep in [sg.id for sg in sub_goals] for dep in sub_goals[i].dependencies) or len(sub_goals[i].dependencies) == 0

    def test_multi_domain_goal(self):
        """Planner should handle cross-domain goals."""
        planner = AutonomousPlanner()
        plan = planner.plan("Secure factory and deploy monitoring drone", "industrial")
        assert plan.status in (PlanStatus.READY, PlanStatus.SAFETY_BLOCKED, PlanStatus.FAILED)
        assert len(plan.sub_goals) >= 3

    def test_planner_with_safety_gateway_rejecting_dangerous_action(self):
        """Planner should block when safety gateway rejects dangerous actions."""
        gateway = MagicMock()
        gateway.check_action.side_effect = lambda cmd: cmd.get("action_type") != "execute"
        planner = AutonomousPlanner(safety_gateway=gateway)
        plan = planner.plan("Activate industrial furnace", "industrial")
        assert plan.status == PlanStatus.SAFETY_BLOCKED
        assert not plan.safety_verified

    def test_planner_with_safety_gateway_allowing_safe_action(self):
        """Planner should approve safe actions."""
        gateway = MagicMock()
        gateway.check_action.return_value = True
        planner = AutonomousPlanner(safety_gateway=gateway)
        plan = planner.plan("Read sensor data from machine 1", "industrial")
        assert plan.status == PlanStatus.READY
        assert plan.safety_verified

    def test_planner_priority_escalation(self):
        """High-priority goals should generate more actions."""
        planner = AutonomousPlanner()
        # Low priority sub-goal
        sg_low = SubGoal(id="sg1", description="Observe", priority=0)
        actions_low = planner.generate_actions(sg_low, "industrial")
        # High priority sub-goal
        sg_high = SubGoal(id="sg2", description="Execute critical action", priority=2)
        actions_high = planner.generate_actions(sg_high, "industrial")
        assert len(actions_high) >= len(actions_low)

    def test_planner_simulation_integration(self):
        """Planner should use simulator for validation."""
        simulator = MagicMock()
        simulator.simulate_plan.return_value = {"success": True, "steps": 4}
        planner = AutonomousPlanner(simulator=simulator)
        plan = planner.plan("Move robot from A to B", "industrial")
        assert plan.simulation_verified
        simulator.simulate_plan.assert_called_once()

    def test_planner_simulation_failure_blocks_execution(self):
        """Failed simulation should block the plan."""
        simulator = MagicMock()
        simulator.simulate_plan.return_value = {"success": False, "errors": ["Collision detected"]}
        planner = AutonomousPlanner(simulator=simulator)
        plan = planner.plan("Drive vehicle through obstacle", "vehicle")
        assert plan.status == PlanStatus.FAILED
        assert not plan.simulation_verified

    def test_planner_estimated_duration(self):
        """Plan should estimate total duration."""
        gateway = MagicMock()
        gateway.check_action.return_value = True
        planner = AutonomousPlanner(safety_gateway=gateway)
        plan = planner.plan("Monitor factory floor", "industrial")
        assert plan.estimated_duration > 0
        assert plan.status == PlanStatus.READY

    def test_planner_multiple_goals_sequential(self):
        """Planner should handle multiple goals without state leakage."""
        planner = AutonomousPlanner()
        plan1 = planner.plan("Goal A", "industrial")
        plan2 = planner.plan("Goal B", "vehicle")
        assert plan1.id != plan2.id
        assert plan1.goal != plan2.goal

    def test_planner_subgoal_safety_levels(self):
        """Sub-goals should have appropriate safety levels."""
        planner = AutonomousPlanner()
        sub_goals = planner.decompose("Move vehicle at high speed", "vehicle")
        # At least one sub-goal should be SC_1 (critical) for vehicle movement
        sc1_goals = [sg for sg in sub_goals if sg.safety_level == "SC_1"]
        assert len(sc1_goals) >= 1

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_planner_llm_decomposition_fallback(self, mock_api):
        """When LLM fails, planner should fall back to rule-based decomposition."""
        mock_api.side_effect = Exception("API error")
        text_adapter = GPT4oTextAdapter(api_key="test-key")
        planner = AutonomousPlanner(text_adapter=text_adapter)
        sub_goals = planner.decompose("Complex goal", "industrial")
        # Should fall back to rule-based (4 sub-goals)
        assert len(sub_goals) >= 3
        assert sub_goals[0].description.startswith("Observe")

    @patch('src.models.gpt4o_adapters._openai_request')
    def test_planner_llm_decomposition_success(self, mock_api):
        """LLM should produce structured sub-goals when available."""
        mock_api.return_value = {
            "choices": [{"message": {"content": json.dumps([
                {"description": "Scan environment", "priority": 0, "dependencies": [], "safety_level": "SC_3"},
                {"description": "Plan route", "priority": 1, "dependencies": [0], "safety_level": "SC_2"},
                {"description": "Execute movement", "priority": 2, "dependencies": [1], "safety_level": "SC_1"},
            ])}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 100},
        }
        text_adapter = GPT4oTextAdapter(api_key="test-key")
        planner = AutonomousPlanner(text_adapter=text_adapter)
        sub_goals = planner.decompose("Move robot to target", "industrial")
        assert len(sub_goals) == 3
        assert sub_goals[0].description == "Scan environment"
        assert sub_goals[2].safety_level == "SC_1"


# ============================================================================
# Condition 3: Stress-Test TaskStateManager Under Load
# ============================================================================

class TestTaskStateStressTest:
    """Stress test the TaskStateManager with high volume and complex scenarios."""

    def test_high_volume_task_creation(self, tmp_path):
        """Create 500 tasks and verify persistence."""
        mgr = TaskStateManager(str(tmp_path / "stress.json"))
        for i in range(500):
            mgr.create_task(f"Task_{i}", f"Stress test task {i}")
        assert len(mgr.list_tasks()) == 500
        # Verify persistence by reloading
        mgr2 = TaskStateManager(str(tmp_path / "stress.json"))
        assert len(mgr2.list_tasks()) == 500

    def test_rapid_start_complete_cycle(self, tmp_path):
        """Rapidly create, start, and complete 100 tasks."""
        mgr = TaskStateManager(str(tmp_path / "rapid.json"))
        task_ids = []
        for i in range(100):
            t = mgr.create_task(f"Rapid_{i}", "rapid test")
            task_ids.append(t.id)
            mgr.start_task(t.id)
            mgr.complete_task(t.id)

        completed = mgr.list_tasks(status=TaskStatus.COMPLETED)
        assert len(completed) == 100

    def test_concurrent_task_management(self, tmp_path):
        """Manage 50 in-progress tasks simultaneously."""
        mgr = TaskStateManager(str(tmp_path / "concurrent.json"))
        task_ids = []
        for i in range(50):
            t = mgr.create_task(f"Concurrent_{i}", "concurrent test")
            mgr.start_task(t.id)
            task_ids.append(t.id)

        in_progress = mgr.list_tasks(status=TaskStatus.IN_PROGRESS)
        assert len(in_progress) == 50

        # Complete half, fail the rest
        for i, tid in enumerate(task_ids):
            if i < 25:
                mgr.complete_task(tid)
            else:
                mgr.fail_task(tid, "Simulated failure")

        completed = mgr.list_tasks(status=TaskStatus.COMPLETED)
        failed = mgr.list_tasks(status=TaskStatus.FAILED)
        assert len(completed) == 25
        assert len(failed) == 25

    def test_checkpoint_storm(self, tmp_path):
        """Create 200 checkpoints rapidly."""
        mgr = TaskStateManager(str(tmp_path / "ckpt_storm.json"))
        task = mgr.create_task("Checkpoint storm", "stress test")
        mgr.start_task(task.id)

        for i in range(200):
            mgr.create_checkpoint(
                task.id,
                CheckpointType.AFTER_ACTION,
                state={"step": i, "data": f"checkpoint_{i}"},
                description=f"Checkpoint {i}"
            )

        assert len(mgr._checkpoints) == 200
        # Last checkpoint should be accessible
        last = mgr.get_last_checkpoint(task.id)
        assert last is not None
        assert last.state["step"] == 199

    def test_shutdown_resume_with_many_tasks(self, tmp_path):
        """Shutdown with 100 pending tasks and verify all survive restart."""
        path = str(tmp_path / "shutdown_stress.json")
        mgr = TaskStateManager(path)

        for i in range(100):
            mgr.create_task(f"Pending_{i}", "pending on shutdown")

        # Start 10 of them
        tasks = mgr.list_tasks(status=TaskStatus.PENDING)
        for t in tasks[:10]:
            mgr.start_task(t.id)

        mgr.shutdown("TEST: simulated shutdown", recommendation="Restart and continue")

        # Reload and verify
        mgr2 = TaskStateManager(path)
        result = mgr2.resume()
        unfinished = result["unfinished_tasks"]
        assert len(unfinished) == 100
        assert result["stop_reason"] == "TEST: simulated shutdown"
        assert result["resume_from"] is not None

    def test_nested_sub_tasks(self, tmp_path):
        """Create deeply nested task hierarchy (5 levels)."""
        mgr = TaskStateManager(str(tmp_path / "nested.json"))
        parent = mgr.create_task("Root", "root task")
        current = parent
        for i in range(5):
            child = mgr.create_task(f"Level_{i+1}", f"nested level {i+1}", parent_task=current.id)
            current = child

        # Verify hierarchy
        root = mgr.get_task(parent.id)
        assert len(root.sub_tasks) == 1
        level1 = mgr.get_task(root.sub_tasks[0])
        assert len(level1.sub_tasks) == 1

    def test_task_progress_updates_rapid(self, tmp_path):
        """Rapidly update progress on a task 1000 times."""
        mgr = TaskStateManager(str(tmp_path / "progress.json"))
        task = mgr.create_task("Progress test", "rapid updates")
        mgr.start_task(task.id)

        for i in range(1000):
            mgr.update_progress(task.id, i / 1000.0)

        assert mgr.get_task(task.id).progress == 0.999  # Last update (999/1000)
        mgr.complete_task(task.id)
        assert mgr.get_task(task.id).progress == 1.0

    def test_health_status_under_load(self, tmp_path):
        """Health status should report correctly under load."""
        mgr = TaskStateManager(str(tmp_path / "health.json"))
        for i in range(200):
            t = mgr.create_task(f"Health_{i}", "test")
            if i < 50:
                mgr.complete_task(t.id)
            elif i < 100:
                mgr.start_task(t.id)
            elif i < 120:
                mgr.fail_task(t.id, "test failure")

        health = mgr.health_status()
        assert health["total_tasks"] == 200
        assert health["completed"] == 50
        assert health["in_progress"] == 50
        assert health["failed"] == 20
        assert health["pending"] == 80  # 200 - 50 - 50 - 20


# ============================================================================
# Condition 4: Cross-Module Integration
# ============================================================================

class TestCrossModuleIntegration:
    """Test planner + safety + task state + simulators working together."""

    def test_planner_creates_task_state(self, tmp_path):
        """Planner execution should be trackable through TaskStateManager."""
        task_mgr = TaskStateManager(str(tmp_path / "integration.json"))
        gateway = MagicMock()
        gateway.check_action.return_value = True

        # Create a task for the planning operation
        task = task_mgr.create_task("Plan execution", "Plan and execute goal")
        task_mgr.start_task(task.id)

        # Create checkpoint before planning
        task_mgr.create_checkpoint(task.id, CheckpointType.BEFORE_ACTION, state={"phase": "planning"})

        # Run planner
        planner = AutonomousPlanner(safety_gateway=gateway)
        plan = planner.plan("Optimize production", "industrial")

        # Create checkpoint after planning
        task_mgr.create_checkpoint(task.id, CheckpointType.AFTER_ACTION,
                                    state={"plan_id": plan.id, "status": plan.status.value})

        # Complete task
        task_mgr.complete_task(task.id, result={"plan_id": plan.id})

        # Verify
        assert task_mgr.get_task(task.id).status == TaskStatus.COMPLETED
        assert len(task_mgr._checkpoints) == 2
        assert task_mgr.get_last_checkpoint(task.id).state["plan_id"] == plan.id

    def test_planner_safety_task_state_pipeline(self, tmp_path):
        """Full pipeline: task state → planner → safety → checkpoint."""
        task_mgr = TaskStateManager(str(tmp_path / "pipeline.json"))
        gateway = MagicMock()
        gateway.check_action.return_value = True
        simulator = MagicMock()
        simulator.simulate_plan.return_value = {"success": True}

        # Track the entire pipeline as a task
        task = task_mgr.create_task("Full pipeline", "plan → simulate → verify → execute")
        task_mgr.start_task(task.id)

        # Phase 1: Plan
        task_mgr.create_checkpoint(task.id, CheckpointType.BEFORE_ACTION, state={"phase": "decompose"})
        planner = AutonomousPlanner(safety_gateway=gateway, simulator=simulator)
        plan = planner.plan("Coordinate 3 robots", "industrial")

        # Phase 2: Verify results
        task_mgr.create_checkpoint(task.id, CheckpointType.AFTER_ACTION,
                                   state={"plan_status": plan.status.value, "actions": len(plan.actions)})
        task_mgr.update_progress(task.id, 0.5)

        # Phase 3: Complete
        if plan.status == PlanStatus.READY:
            task_mgr.complete_task(task.id, {"plan_id": plan.id, "actions": len(plan.actions)})
        else:
            task_mgr.fail_task(task.id, f"Plan failed: {plan.status.value}")

        # Verify full trail
        checkpoints = list(task_mgr._checkpoints.values())
        assert len(checkpoints) == 2
        assert task_mgr.get_task(task.id).status in (TaskStatus.COMPLETED, TaskStatus.FAILED)

    def test_shutdown_during_planning_preserves_state(self, tmp_path):
        """If system shuts down during planning, state should be recoverable."""
        path = str(tmp_path / "shutdown_plan.json")
        task_mgr = TaskStateManager(path)
        gateway = MagicMock()
        gateway.check_action.return_value = True

        task = task_mgr.create_task("Interrupted plan", "planning was interrupted")
        task_mgr.start_task(task.id)
        task_mgr.create_checkpoint(task.id, CheckpointType.BEFORE_ACTION,
                                   state={"phase": "decompose", "goal": "move robot"})

        # Simulate shutdown (e.g., hit financial boundary)
        task_mgr.shutdown("FINANCIAL: API budget exceeded", recommendation="Increase API budget")

        # Verify task is in DECISION_REQUIRED
        assert task_mgr.get_task(task.id).status == TaskStatus.DECISION_REQUIRED

        # Resume
        mgr2 = TaskStateManager(path)
        result = mgr2.resume()
        assert len(result["unfinished_tasks"]) >= 1
        assert result["stop_reason"] == "FINANCIAL: API budget exceeded"

    def test_multi_domain_planner_with_task_tracking(self, tmp_path):
        """Plan across multiple domains with task state tracking."""
        task_mgr = TaskStateManager(str(tmp_path / "multi_domain.json"))
        gateway = MagicMock()
        gateway.check_action.return_value = True
        planner = AutonomousPlanner(safety_gateway=gateway)

        domains = ["industrial", "vehicle", "drone", "home"]
        parent_task = task_mgr.create_task("Multi-domain operation", "coordinate across domains")
        task_mgr.start_task(parent_task.id)

        for domain in domains:
            child = task_mgr.create_task(
                f"Plan_{domain}", f"Plan for {domain}",
                parent_task=parent_task.id
            )
            task_mgr.start_task(child.id)

            plan = planner.plan(f"Secure {domain} domain", domain)
            task_mgr.create_checkpoint(child.id, CheckpointType.AFTER_ACTION,
                                       state={"plan_status": plan.status.value})

            if plan.status == PlanStatus.READY:
                task_mgr.complete_task(child.id, {"plan_id": plan.id})
            else:
                task_mgr.fail_task(child.id, plan.status.value)

        task_mgr.complete_task(parent_task.id)
        assert task_mgr.get_task(parent_task.id).status == TaskStatus.COMPLETED
        assert len(task_mgr.get_task(parent_task.id).sub_tasks) == 4
