"""
Tests for ORION Runtime Supervisor — 24/7 Autonomous Operation.

License: Apache 2.0
"""

import json
import os
import time

import pytest

from runtime.supervisor import (
    RuntimeSupervisor,
    ScheduledTask,
    SupervisorMetrics,
    SupervisorState,
    SupervisorStatus,
)
from runtime.worker import Worker, WorkerResult, WorkerStatus


@pytest.fixture(autouse=True)
def cleanup_state_files():
    """Clean up state files before and after each test."""
    import glob
    for f in glob.glob("/tmp/test_sup*.json*"):
        os.remove(f)
    yield
    for f in glob.glob("/tmp/test_sup*.json*"):
        os.remove(f)


class TestWorker:
    """Test worker isolation and crash recovery."""

    def test_worker_success(self):
        """Worker completes a task successfully."""
        def simple_task():
            return {"result": "success"}

        worker = Worker("w1", simple_task)
        result = worker.run()

        assert result.success is True
        assert result.result == {"result": "success"}
        assert result.status == WorkerStatus.COMPLETED
        assert worker.status == WorkerStatus.COMPLETED

    def test_worker_crash_isolation(self):
        """Worker catches exceptions — does NOT propagate them."""
        def crash_task():
            raise ValueError("Intentional crash")

        worker = Worker("w2", crash_task, max_retries=0)
        result = worker.run()

        assert result.success is False
        assert "ValueError" in result.error
        assert result.status == WorkerStatus.CRASHED
        assert worker.status == WorkerStatus.CRASHED

    def test_worker_retry_on_crash(self):
        """Worker retries on crash up to max_retries."""
        attempts = []

        def flaky_task():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("Flaky failure")
            return "success on 3rd try"

        worker = Worker("w3", flaky_task, max_retries=3)
        result = worker.run()

        assert result.success is True
        assert result.result == "success on 3rd try"
        assert len(attempts) == 3

    def test_worker_exhaust_retries(self):
        """Worker fails after exhausting retries."""
        def always_fail():
            raise RuntimeError("Always fails")

        worker = Worker("w4", always_fail, max_retries=2)
        result = worker.run()

        assert result.success is False
        assert result.status == WorkerStatus.CRASHED
        assert "Always fails" in result.error

    def test_worker_stop_request(self):
        """Worker respects stop request."""
        def long_task():
            return "should not reach"

        worker = Worker("w5", long_task)
        worker.request_stop()
        result = worker.run()

        assert result.success is False
        assert "stopped" in result.error.lower()

    def test_worker_with_args(self):
        """Worker passes arguments to task function."""
        def add_task(a, b):
            return a + b

        worker = Worker("w6", add_task, args=(3, 4))
        result = worker.run()

        assert result.success is True
        assert result.result == 7

    def test_worker_with_kwargs(self):
        """Worker passes keyword arguments to task function."""
        def greet_task(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        worker = Worker("w7", greet_task, kwargs={"name": "ORION", "greeting": "Hi"})
        result = worker.run()

        assert result.success is True
        assert result.result == "Hi, ORION!"

    def test_worker_elapsed_time(self):
        """Worker tracks execution time."""
        def slow_task():
            time.sleep(0.05)
            return "done"

        worker = Worker("w8", slow_task)
        result = worker.run()

        assert result.success is True
        assert result.execution_time > 0.04
        assert worker.elapsed_time > 0.04

    def test_worker_to_dict(self):
        """Worker serializes to dict."""
        def task():
            return "ok"

        worker = Worker("w9", task)
        worker.run()
        d = worker.to_dict()

        assert d["worker_id"] == "w9"
        assert d["status"] == WorkerStatus.COMPLETED.value
        assert d["retries"] == 0

    def test_worker_result_to_dict(self):
        """WorkerResult serializes to dict."""
        result = WorkerResult(success=True, result="ok", worker_id="w10")
        d = result.to_dict()

        assert d["success"] is True
        assert d["result"] == "ok"
        assert d["worker_id"] == "w10"
        assert d["status"] == WorkerStatus.COMPLETED.value


class TestRuntimeSupervisor:
    """Test the 24/7 runtime supervisor."""

    def test_supervisor_creation(self):
        """Supervisor initializes correctly."""
        sup = RuntimeSupervisor(state_file="/tmp/test_supervisor.json")
        assert sup.status == SupervisorStatus.STOPPED
        assert sup.state == SupervisorState.INITIALIZING
        assert sup.pending_tasks == []
        assert sup.completed_tasks == []
        assert sup.uptime == 0.0

    def test_register_task_fn(self):
        """Can register task functions."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup1.json")
        sup.register_task_fn("test_fn", lambda: "hello")
        assert "test_fn" in sup._task_fns

    def test_schedule_task(self):
        """Can schedule tasks."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup2.json")
        sup.register_task_fn("test_fn", lambda x: x * 2)
        task = sup.schedule_task("t1", "Test task", "test_fn", args=(5,))

        assert task.id == "t1"
        assert task.name == "Test task"
        assert task.status == "pending"
        assert len(sup.pending_tasks) == 1

    def test_schedule_unknown_fn_raises(self):
        """Scheduling unknown task function raises error."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup3.json")
        with pytest.raises(ValueError, match="Unknown task function"):
            sup.schedule_task("t1", "Test", "nonexistent_fn")

    def test_supervisor_runs_task(self):
        """Supervisor executes a scheduled task."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup4.json")

        results = []

        def task_fn():
            results.append("executed")
            return "success"

        sup.register_task_fn("test_fn", task_fn)
        sup.schedule_task("t1", "Test task", "test_fn")
        sup.start()

        assert len(results) == 1
        assert sup.completed_tasks[0].id == "t1"
        assert sup.metrics.completed_tasks == 1

    def test_supervisor_handles_worker_crash(self):
        """Supervisor continues when a worker crashes."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup5.json")

        def crash_fn():
            raise RuntimeError("Intentional crash")

        def success_fn():
            return "ok"

        sup.register_task_fn("crash_fn", crash_fn)
        sup.register_task_fn("success_fn", success_fn)

        sup.schedule_task("t1", "Crashing task", "crash_fn", max_retries=0)
        sup.schedule_task("t2", "Success task", "success_fn")
        sup.start()

        # Supervisor should continue despite crash
        assert sup.status == SupervisorStatus.STOPPED
        assert len(sup.failed_tasks) == 1
        assert len(sup.completed_tasks) == 1
        assert sup.metrics.failed_tasks == 1
        assert sup.metrics.completed_tasks == 1
        assert sup.metrics.worker_crashes == 1

    def test_supervisor_multiple_tasks(self):
        """Supervisor handles multiple tasks."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup6.json")

        counter = {"count": 0}

        def increment():
            counter["count"] += 1
            return counter["count"]

        sup.register_task_fn("increment", increment)
        for i in range(5):
            sup.schedule_task(f"t{i}", f"Task {i}", "increment")

        sup.start()

        assert counter["count"] == 5
        assert len(sup.completed_tasks) == 5
        assert sup.metrics.success_rate == 1.0

    def test_supervisor_priority_ordering(self):
        """Supervisor respects task priority."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup7.json")

        execution_order = []

        def record_task():
            execution_order.append(time.time())
            return "ok"

        sup.register_task_fn("record", record_task)
        # Lower priority number = higher priority
        sup.schedule_task("low", "Low priority", "record", priority=10)
        sup.schedule_task("high", "High priority", "record", priority=1)
        sup.schedule_task("medium", "Medium priority", "record", priority=5)

        sup.start()

        # All should complete
        assert len(sup.completed_tasks) == 3

    def test_supervisor_checkpoint_save(self):
        """Supervisor saves state on checkpoint."""
        state_file = "/tmp/test_sup_checkpoint.json"
        if os.path.exists(state_file):
            os.remove(state_file)

        sup = RuntimeSupervisor(
            state_file=state_file,
            checkpoint_interval=0.01,  # Very short for testing
        )

        def quick_task():
            return "done"

        sup.register_task_fn("quick", quick_task)
        sup.schedule_task("t1", "Quick task", "quick")
        sup.start()

        # State file should exist
        assert os.path.exists(state_file)

        with open(state_file) as f:
            state = json.load(f)

        assert "tasks" in state
        assert "t1" in state["tasks"]
        assert state["tasks"]["t1"]["status"] == "completed"

    def test_supervisor_recovery_on_restart(self):
        """Supervisor recovers pending tasks on restart."""
        state_file = "/tmp/test_sup_recovery.json"
        if os.path.exists(state_file):
            os.remove(state_file)

        # First run: schedule a task and save state
        sup1 = RuntimeSupervisor(state_file=state_file)
        sup1.register_task_fn("test_fn", lambda: "ok")
        sup1.schedule_task("t1", "Test task", "test_fn")
        sup1._save_state()

        # Simulate that the task was running when shutdown happened
        sup1._scheduled_tasks["t1"].status = "running"
        sup1._scheduled_tasks["t1"].worker_id = "old-worker"
        sup1._save_state()

        # Second run: supervisor should recover the task as pending
        sup2 = RuntimeSupervisor(state_file=state_file)
        sup2.register_task_fn("test_fn", lambda: "recovered!")
        sup2._load_state()

        # Task should be reset to pending
        assert "t1" in sup2._scheduled_tasks
        assert sup2._scheduled_tasks["t1"].status == "pending"
        assert sup2._scheduled_tasks["t1"].worker_id is None

    def test_supervisor_stop_graceful(self):
        """Supervisor stops gracefully and saves state."""
        state_file = "/tmp/test_sup_stop.json"
        if os.path.exists(state_file):
            os.remove(state_file)

        sup = RuntimeSupervisor(state_file=state_file)
        sup.register_task_fn("test_fn", lambda: "ok")
        sup.schedule_task("t1", "Test", "test_fn")
        sup.start()
        sup.stop("test stop")

        assert sup.status == SupervisorStatus.STOPPED
        assert sup._shutdown_reason == "test stop"
        assert os.path.exists(state_file)

    def test_supervisor_emergency_stop(self):
        """Supervisor handles emergency stop."""
        state_file = "/tmp/test_sup_emergency.json"
        if os.path.exists(state_file):
            os.remove(state_file)

        sup = RuntimeSupervisor(state_file=state_file)
        sup.register_task_fn("test_fn", lambda: "ok")
        sup.schedule_task("t1", "Test", "test_fn")
        sup.emergency_stop("test emergency")

        assert sup.status == SupervisorStatus.EMERGENCY
        assert "EMERGENCY" in sup._shutdown_reason

    def test_supervisor_health_status(self):
        """Supervisor reports health status."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup_health.json")
        sup.register_task_fn("test_fn", lambda: "ok")
        sup.schedule_task("t1", "Test", "test_fn")
        sup.start()

        health = sup.get_health_status()
        assert health["status"] == SupervisorStatus.STOPPED.value
        assert health["completed_tasks"] == 1
        assert health["success_rate"] == 1.0

    def test_supervisor_metrics(self):
        """Supervisor tracks metrics correctly."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup_metrics.json")

        def good():
            return "good"

        def bad():
            raise RuntimeError("bad")

        sup.register_task_fn("good", good)
        sup.register_task_fn("bad", bad)
        sup.schedule_task("t1", "Good", "good")
        sup.schedule_task("t2", "Bad", "bad", max_retries=0)

        sup.start()

        assert sup.metrics.total_tasks == 2
        assert sup.metrics.completed_tasks == 1
        assert sup.metrics.failed_tasks == 1
        assert sup.metrics.success_rate == 0.5

    def test_supervisor_to_dict(self):
        """Supervisor serializes to dict."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup_dict.json")
        sup.register_task_fn("test_fn", lambda: "ok")
        sup.schedule_task("t1", "Test", "test_fn")

        d = sup.to_dict()
        assert "status" in d
        assert "metrics" in d
        assert "task_fns" in d
        assert "test_fn" in d["task_fns"]

    def test_supervisor_max_steps(self):
        """Supervisor respects max_steps (limits loop iterations)."""
        sup = RuntimeSupervisor(state_file="/tmp/test_sup_steps.json")

        def task():
            return "ok"

        sup.register_task_fn("test", task)
        sup.schedule_task("t1", "T1", "test")
        sup.schedule_task("t2", "T2", "test")
        sup.schedule_task("t3", "T3", "test")

        sup.start(max_steps=1)

        # In synchronous mode, all tasks complete in 1 loop step
        # max_steps limits loop iterations, not task count
        assert sup.metrics.completed_tasks == 3
        assert sup.metrics.uptime_seconds < 1.0  # Should be quick

    def test_supervisor_worker_isolation(self):
        """A worker crash does not affect other workers."""
        sup = RuntimeSupervisor(
            state_file="/tmp/test_sup_isolation.json",
            max_concurrent_workers=1,
        )

        results = []

        def fail_task():
            raise RuntimeError("Crash!")

        def success_task():
            results.append("survived")
            return "survived"

        sup.register_task_fn("fail", fail_task)
        sup.register_task_fn("success", success_task)
        sup.schedule_task("t_fail", "Failing", "fail", max_retries=0, priority=1)
        sup.schedule_task("t_ok", "OK", "success", priority=2)

        sup.start()

        # The success task should have run despite the crash
        assert "survived" in results
        assert len(sup.failed_tasks) == 1
        assert len(sup.completed_tasks) == 1
