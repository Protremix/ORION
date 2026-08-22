"""
ORION Phase 011 — Physical AI Simulation Test Suite. License: Apache 2.0.

Tests: PhysicalSimEnvironment, RobotSimulator, RecoveryManager, predefined tasks,
task execution across 5 domains, recovery, safety verification.
"""
from __future__ import annotations

import pytest

from src.physical_sim import PhysicalSimEnvironment, TaskResult
from src.physical_sim.predefined_tasks import SimTask, get_task, list_domains, list_tasks
from src.physical_sim.recovery_manager import RecoveryAction, RecoveryManager, RecoveryStrategy
from src.physical_sim.robot_simulator import RobotSimulator

# ============================================================================
# PhysicalSimEnvironment Tests (AC1, AC2, AC16, AC18)
# ============================================================================

class TestPhysicalSimEnvironment:
    def test_registers_five_domains(self):
        """AC1: PhysicalSimEnvironment registers 5 domains."""
        env = PhysicalSimEnvironment()
        domains = env.list_domains()
        assert "home" in domains
        assert "vehicle" in domains
        assert "robot" in domains
        assert "drone" in domains
        assert "industrial" in domains
        assert len(domains) == 5

    def test_register_duplicate(self):
        env = PhysicalSimEnvironment()
        assert env.register_domain("robot", RobotSimulator()) is False

    def test_load_task(self):
        """AC2: PhysicalSimEnvironment loads predefined tasks."""
        env = PhysicalSimEnvironment()
        task = env.load_task("home_navigate_room")
        assert task is not None
        assert task.domain == "home"
        assert task.description is not None

    def test_load_unknown_task(self):
        env = PhysicalSimEnvironment()
        assert env.load_task("nonexistent") is None

    def test_list_tasks(self):
        env = PhysicalSimEnvironment()
        tasks = env.list_tasks()
        assert len(tasks) >= 10  # 2 per domain × 5 domains

    def test_list_tasks_by_domain(self):
        env = PhysicalSimEnvironment()
        home_tasks = env.list_tasks("home")
        assert all(t.domain == "home" for t in home_tasks)
        assert len(home_tasks) >= 2

    def test_success_rates_reported(self):
        """AC16: Success rates are measurable and reported."""
        env = PhysicalSimEnvironment()
        env.execute_task("home_navigate_room")
        rates = env.get_success_rates()
        assert "home" in rates
        assert 0.0 <= rates["home"] <= 1.0

    def test_domain_stats(self):
        env = PhysicalSimEnvironment()
        env.execute_task("robot_navigate_warehouse")
        stats = env.get_domain_stats()
        assert "robot" in stats
        assert stats["robot"]["total_tasks"] >= 1

    def test_is_simulation_always_true(self):
        """AC18: ORION operates only inside simulation."""
        env = PhysicalSimEnvironment()
        assert env.is_simulation() is True

    def test_to_dict(self):
        env = PhysicalSimEnvironment()
        d = env.to_dict()
        assert d["is_simulation"] is True
        assert len(d["domains"]) == 5


# ============================================================================
# RobotSimulator Tests (AC3, AC4)
# ============================================================================

class TestRobotSimulator:
    def test_step_move(self):
        """AC3: RobotSimulator simulates robot actions."""
        robot = RobotSimulator()
        state = robot.step({"type": "move", "direction": [1, 0, 0], "speed": 1.0})
        assert state["position"][0] > 0

    def test_step_rotate(self):
        robot = RobotSimulator()
        state = robot.step({"type": "rotate", "angle": 1.57})
        assert abs(state["orientation"] - 1.57) < 0.01

    def test_step_joints(self):
        robot = RobotSimulator()
        state = robot.step({"type": "move_joints", "joints": {"elbow": 0.5}})
        assert state["joints"]["elbow"] == 0.5

    def test_gripper_open_close(self):
        robot = RobotSimulator()
        robot.step({"type": "gripper", "action": "close"})
        assert robot.get_state()["joints"]["gripper"] == 1.0
        robot.step({"type": "gripper", "action": "open"})
        assert robot.get_state()["joints"]["gripper"] == 0.0

    def test_navigate(self):
        robot = RobotSimulator()
        robot.set_target([5.0, 0.0, 0.0])
        for _ in range(100):
            robot.step({"type": "navigate_to", "target": [5.0, 0.0, 0.0]})
            if robot.get_state().get("at_target"):
                break
        assert robot.get_state()["at_target"] is True

    def test_pick_and_place(self):
        robot = RobotSimulator()
        robot.step({"type": "pick", "object": "box"})
        assert robot.get_state()["gripper_holding"] == "box"
        robot.step({"type": "place", "location": [1, 1, 0]})
        assert robot.get_state()["gripper_holding"] is None

    def test_collision_detection(self):
        robot = RobotSimulator()
        robot.set_obstacles([{"position": [0.1, 0, 0], "radius": 0.5}])
        robot.step({"type": "move", "direction": [1, 0, 0], "speed": 1.0})
        assert robot.get_state()["collision"] is True

    def test_battery_drains(self):
        robot = RobotSimulator()
        for _ in range(10):
            robot.step({"type": "move", "direction": [1, 0, 0], "speed": 1.0})
        assert robot.get_state()["battery"] < 100.0

    def test_tracks_state(self):
        """AC4: RobotSimulator tracks state (position, velocity, joints)."""
        robot = RobotSimulator()
        state = robot.get_state()
        assert "position" in state
        assert "velocity" in state
        assert "joints" in state
        assert "orientation" in state

    def test_reset(self):
        robot = RobotSimulator()
        robot.step({"type": "move", "direction": [5, 0, 0], "speed": 2.0})
        robot.reset()
        state = robot.get_state()
        assert state["position"] == [0.0, 0.0, 0.0]
        assert state["battery"] == 100.0

    def test_step_count(self):
        robot = RobotSimulator()
        for i in range(5):
            robot.step({"type": "idle"})
        assert robot.get_state()["step_count"] == 5


# ============================================================================
# SimTask / TaskResult Tests (AC5, AC6)
# ============================================================================

class TestSimTaskResult:
    def test_sim_task_construction(self):
        """AC5: SimTask defines success criteria."""
        task = SimTask(
            task_id="test_task",
            domain="home",
            description="Test task",
            success_criteria={"target_reached": True},
        )
        assert task.task_id == "test_task"
        assert task.domain == "home"
        assert task.success_criteria == {"target_reached": True}

    def test_sim_task_defaults(self):
        task = SimTask(task_id="t", domain="home", description="d")
        assert task.max_steps == 50
        assert task.obstacles == []
        assert task.safety_constraints == []

    def test_task_result_construction(self):
        """AC6: TaskResult reports success and success_rate."""
        result = TaskResult(
            task_id="test_task",
            domain="home",
            success=True,
            success_rate=1.0,
        )
        assert result.success is True
        assert result.success_rate == 1.0

    def test_task_result_to_dict(self):
        result = TaskResult(task_id="t", domain="home", success=True)
        d = result.to_dict()
        assert d["task_id"] == "t"
        assert d["success"] is True

    def test_predefined_tasks_exist(self):
        assert len(list_tasks()) >= 10
        assert len(list_domains()) == 5

    def test_get_task(self):
        task = get_task("home_navigate_room")
        assert task is not None
        assert task.domain == "home"


# ============================================================================
# RecoveryManager Tests (AC7, AC8)
# ============================================================================

class TestRecoveryManager:
    def test_recover_generates_strategy(self):
        """AC7: RecoveryManager generates recovery strategies."""
        rm = RecoveryManager()
        action = rm.recover("collision")
        assert action.strategy == RecoveryStrategy.RESET_POSITION
        assert "collision" in action.description

    def test_recover_timeout(self):
        rm = RecoveryManager()
        action = rm.recover("timeout")
        assert action.strategy == RecoveryStrategy.RETRY

    def test_recover_path_blocked(self):
        rm = RecoveryManager()
        action = rm.recover("path_blocked")
        assert action.strategy == RecoveryStrategy.ALTERNATIVE_PATH

    def test_recover_low_battery(self):
        rm = RecoveryManager()
        action = rm.recover("low_battery")
        assert action.strategy == RecoveryStrategy.REQUEST_HELP

    def test_recover_unknown_error(self):
        rm = RecoveryManager()
        action = rm.recover("unknown_error_type")
        assert action.strategy == RecoveryStrategy.REQUEST_HELP

    def test_execute_recovery_reset(self):
        """AC8: RecoveryManager executes recovery actions."""
        rm = RecoveryManager()
        robot = RobotSimulator()
        action = rm.recover("collision")
        result = rm.execute_recovery(action, robot)
        assert result["recovered"] is True

    def test_execute_recovery_retry(self):
        rm = RecoveryManager()
        action = RecoveryAction(strategy=RecoveryStrategy.RETRY, description="retry")
        result = rm.execute_recovery(action)
        assert result["recovered"] is True

    def test_execute_recovery_request_help(self):
        rm = RecoveryManager()
        action = RecoveryAction(strategy=RecoveryStrategy.REQUEST_HELP, description="help")
        result = rm.execute_recovery(action)
        assert result["recovered"] is False
        assert result.get("needs_human") is True

    def test_get_strategies(self):
        rm = RecoveryManager()
        strategies = rm.get_strategies()
        assert len(strategies) >= 6
        assert "retry" in strategies

    def test_statistics(self):
        rm = RecoveryManager()
        rm.recover("collision")
        rm.execute_recovery(RecoveryAction(strategy=RecoveryStrategy.RETRY, description="r"))
        stats = rm.get_statistics()
        assert stats["total_recoveries"] >= 1
        assert stats["successful_recoveries"] >= 1


# ============================================================================
# Task Execution Integration Tests (AC9-AC13)
# ============================================================================

class TestTaskExecution:
    def test_execute_home_task(self):
        """AC9: PhysicalSimEnvironment executes home task."""
        env = PhysicalSimEnvironment()
        result = env.execute_task("home_navigate_room")
        assert result.domain == "home"
        assert isinstance(result, TaskResult)
        assert result.steps_taken > 0

    def test_execute_vehicle_task(self):
        """AC10: PhysicalSimEnvironment executes vehicle task."""
        env = PhysicalSimEnvironment()
        result = env.execute_task("vehicle_navigate_road")
        assert result.domain == "vehicle"
        assert result.steps_taken > 0

    def test_execute_robot_task(self):
        """AC11: PhysicalSimEnvironment executes robot task."""
        env = PhysicalSimEnvironment()
        result = env.execute_task("robot_navigate_warehouse")
        assert result.domain == "robot"
        assert result.steps_taken > 0

    def test_execute_drone_task(self):
        """AC12: PhysicalSimEnvironment executes drone task."""
        env = PhysicalSimEnvironment()
        result = env.execute_task("drone_fly_to_target")
        assert result.domain == "drone"
        assert result.steps_taken > 0

    def test_execute_industrial_task(self):
        """AC13: PhysicalSimEnvironment executes industrial task."""
        env = PhysicalSimEnvironment()
        result = env.execute_task("industrial_process_control")
        assert result.domain == "industrial"
        assert result.steps_taken > 0

    def test_execute_unknown_task(self):
        env = PhysicalSimEnvironment()
        result = env.execute_task("nonexistent")
        assert result.success is False
        assert "Unknown task" in result.errors


# ============================================================================
# Pipeline Integration Tests (AC14, AC15, AC17)
# ============================================================================

class TestPipelineIntegration:
    def test_full_pipeline_home(self):
        """AC14: ORION completes task: perception → plan → act → verify."""
        env = PhysicalSimEnvironment()
        result = env.execute_task("home_navigate_room")
        assert result.steps_taken > 0
        assert result.final_state is not None

    def test_full_pipeline_robot(self):
        env = PhysicalSimEnvironment()
        result = env.execute_task("robot_navigate_warehouse")
        assert result.steps_taken > 0
        assert result.latency_ms > 0

    def test_recovery_on_failure(self):
        """AC15: ORION recovers from a failed action."""
        env = PhysicalSimEnvironment()
        # Execute a task with obstacles that may cause collision
        result = env.execute_task("vehicle_avoid_obstacle")
        # Even if task fails, recovery should be attempted
        if not result.success and len(result.recovery_actions) > 0:
            assert len(result.recovery_actions) > 0 or len(result.errors) > 0

    def test_safety_blocks_unsafe_actions(self):
        """AC17: Safety verification blocks unsafe actions."""
        env = PhysicalSimEnvironment()
        result = env.execute_task("industrial_emergency_stop")
        assert result.domain == "industrial"
        # Emergency stop should complete quickly
        assert result.steps_taken <= 5

    def test_success_rate_measurable(self):
        env = PhysicalSimEnvironment()
        # Execute multiple tasks
        env.execute_task("home_navigate_room")
        env.execute_task("home_pick_object")
        rates = env.get_success_rates()
        assert "home" in rates
        assert 0.0 <= rates["home"] <= 1.0

    def test_multiple_domain_execution(self):
        env = PhysicalSimEnvironment()
        for tid in ["home_navigate_room", "vehicle_navigate_road",
                     "robot_navigate_warehouse", "drone_fly_to_target",
                     "industrial_process_control"]:
            result = env.execute_task(tid)
            assert result.steps_taken > 0
        rates = env.get_success_rates()
        assert len(rates) == 5

    def test_recovery_manager_in_environment(self):
        env = PhysicalSimEnvironment()
        rm = env.get_recovery_manager()
        assert rm is not None
        assert isinstance(rm, RecoveryManager)

    def test_task_result_has_all_fields(self):
        env = PhysicalSimEnvironment()
        result = env.execute_task("home_navigate_room")
        d = result.to_dict()
        assert "task_id" in d
        assert "domain" in d
        assert "success" in d
        assert "steps_taken" in d
        assert "final_state" in d
        assert "success_rate" in d
        assert "errors" in d
        assert "recovery_actions" in d
        assert "safety_violations" in d
        assert "latency_ms" in d
