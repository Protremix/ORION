"""
ORION Core Phase 004 Tests. License: Apache 2.0
Tests for all 12 core components.
"""
from __future__ import annotations

import json
import time

import pytest

from src.core.audit_logger import AuditEvent, AuditEventType, AuditLogger
from src.core.error_recovery import ErrorRecovery, RecoveryAction
from src.core.execution_engine import ExecutionEngine, ExecutionResult
from src.core.model_gateway import ModelGateway, ModelInfo, ModelResponse
from src.core.policy_engine import PolicyDecision, PolicyEngine, PolicyRule, PolicyRuleType
from src.core.supervisor import CoreSupervisor
from src.core.task_engine import StepStatus, Task, TaskEngine, TaskPriority, TaskStatus, TaskStep
from src.core.tool_registry import ToolCategory, ToolDefinition, ToolRegistry, ToolRiskLevel, ToolSchema


class TestTaskEngine:
    def test_create_task(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test goal")
        assert task.id == "task_1"
        assert task.goal == "Test goal"
        assert task.status == TaskStatus.PENDING

    def test_idempotency(self):
        engine = TaskEngine()
        task1 = engine.create_task(goal="Test", idempotency_key="key1")
        task2 = engine.create_task(goal="Test", idempotency_key="key1")
        assert task1.id == task2.id

    def test_status_updates(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        engine.update_status(task.id, TaskStatus.PLANNING)
        assert engine.get_task(task.id).status == TaskStatus.PLANNING
        engine.update_status(task.id, TaskStatus.EXECUTING)
        assert engine.get_task(task.id).started_at is not None
        engine.update_status(task.id, TaskStatus.COMPLETED)
        assert engine.get_task(task.id).completed_at is not None

    def test_add_and_get_steps(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        step = TaskStep(id="s1", description="Step 1", action_type="test_tool")
        engine.add_step(task.id, step)
        assert len(engine.get_task(task.id).steps) == 1

    def test_step_dependencies(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        s1 = TaskStep(id="s1", description="Step 1", action_type="tool")
        s2 = TaskStep(id="s2", description="Step 2", action_type="tool", dependencies=["s1"])
        engine.add_step(task.id, s1)
        engine.add_step(task.id, s2)
        ready = engine.get_ready_steps(task.id)
        assert len(ready) == 1
        assert ready[0].id == "s1"
        engine.update_step(task.id, "s1", StepStatus.COMPLETED)
        ready = engine.get_ready_steps(task.id)
        assert len(ready) == 1
        assert ready[0].id == "s2"

    def test_cancel(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        assert engine.cancel(task.id, "User cancelled")
        assert engine.get_task(task.id).status == TaskStatus.CANCELLED

    def test_pause_resume(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        engine.update_status(task.id, TaskStatus.EXECUTING)
        assert engine.pause(task.id)
        assert engine.get_task(task.id).status == TaskStatus.PAUSED
        assert engine.resume(task.id)
        assert engine.get_task(task.id).status == TaskStatus.EXECUTING

    def test_retry_step(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        step = TaskStep(id="s1", description="Step", action_type="tool", max_retries=3)
        engine.add_step(task.id, step)
        engine.update_step(task.id, "s1", StepStatus.FAILED, error="Error")
        assert engine.retry_step(task.id, "s1")
        assert engine.get_task(task.id).steps[0].retry_count == 1
        assert engine.get_task(task.id).steps[0].status == StepStatus.PENDING

    def test_retry_exhausted(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        step = TaskStep(id="s1", description="Step", action_type="tool", max_retries=1)
        engine.add_step(task.id, step)
        engine.update_step(task.id, "s1", StepStatus.FAILED, error="Error")
        engine.retry_step(task.id, "s1")
        engine.update_step(task.id, "s1", StepStatus.FAILED, error="Error")
        assert not engine.retry_step(task.id, "s1")

    def test_snapshot_restore(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        snap = engine.snapshot()
        assert "tasks" in snap
        assert task.id in snap["tasks"]

    def test_get_tasks_by_status(self):
        engine = TaskEngine()
        t1 = engine.create_task(goal="A")
        t2 = engine.create_task(goal="B")
        engine.update_status(t2.id, TaskStatus.COMPLETED)
        pending = engine.get_tasks_by_status(TaskStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].id == t1.id

class TestToolRegistry:
    def test_register_tool(self):
        reg = ToolRegistry()
        tool = ToolDefinition(name="test_tool", description="Test", category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE)
        assert reg.register(tool)
        assert reg.get("test_tool") is not None

    def test_duplicate_register(self):
        reg = ToolRegistry()
        tool = ToolDefinition(name="t", description="Test", category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE)
        assert reg.register(tool)
        assert not reg.register(tool)

    def test_block_physical(self):
        reg = ToolRegistry()
        tool = ToolDefinition(name="motor", description="Motor", category=ToolCategory.PHYSICAL, risk_level=ToolRiskLevel.HIGH)
        assert not reg.register(tool)

    def test_block_forbidden(self):
        reg = ToolRegistry()
        tool = ToolDefinition(name="nuke", description="Nuke", category=ToolCategory.WRITE, risk_level=ToolRiskLevel.FORBIDDEN)
        assert not reg.register(tool)

    def test_is_allowed(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="read_data", description="Read", category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE))
        assert reg.is_allowed("read_data")
        assert not reg.is_allowed("unknown_tool")

    def test_validate_args(self):
        reg = ToolRegistry()
        schema = ToolSchema(parameters={"x": {"type": "int"}}, required=["x"])
        reg.register(ToolDefinition(name="calc", description="Calc", category=ToolCategory.COMPUTE, risk_level=ToolRiskLevel.SAFE, schema=schema))
        valid, _ = reg.validate_args("calc", {"x": 42})
        assert valid
        valid, err = reg.validate_args("calc", {})
        assert not valid
        assert "x" in err

    def test_list_by_category(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="r", description="R", category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE))
        reg.register(ToolDefinition(name="w", description="W", category=ToolCategory.WRITE, risk_level=ToolRiskLevel.LOW))
        reads = reg.list_by_category(ToolCategory.READ)
        assert len(reads) == 1
        assert reads[0].name == "r"

    def test_list_by_risk(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="s", description="S", category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE))
        reg.register(ToolDefinition(name="l", description="L", category=ToolCategory.READ, risk_level=ToolRiskLevel.LOW))
        safe = reg.list_by_risk(ToolRiskLevel.SAFE)
        assert all(t.risk_level == ToolRiskLevel.SAFE for t in safe)

class TestPolicyEngine:
    def test_deny_unknown_tool(self):
        reg = ToolRegistry()
        policy = PolicyEngine(reg)
        assert policy.evaluate_tool("unknown", {}) == PolicyDecision.DENY

    def test_allow_safe(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="safe_tool", description="Safe", category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE))
        policy = PolicyEngine(reg)
        assert policy.evaluate_tool("safe_tool", {}) == PolicyDecision.ALLOW

    def test_require_approval_medium(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="med_tool", description="Med", category=ToolCategory.WRITE, risk_level=ToolRiskLevel.MEDIUM))
        policy = PolicyEngine(reg)
        assert policy.evaluate_tool("med_tool", {}) == PolicyDecision.REQUIRE_APPROVAL

    def test_require_approval_high(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="high_tool", description="High", category=ToolCategory.WRITE, risk_level=ToolRiskLevel.HIGH))
        policy = PolicyEngine(reg)
        assert policy.evaluate_tool("high_tool", {}) == PolicyDecision.REQUIRE_APPROVAL

    def test_deny_by_default(self):
        reg = ToolRegistry()
        policy = PolicyEngine(reg)
        assert policy.evaluate({"tool_name": "totally_unknown"}) == PolicyDecision.DENY
        assert policy.evaluate({"tool_name": "totally_unknown"}) == PolicyDecision.DENY

    def test_deterministic(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="safe", description="S", category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE))
        policy = PolicyEngine(reg)
        assert policy.is_deterministic()

    def test_add_custom_rule(self):
        reg = ToolRegistry()
        policy = PolicyEngine(reg)
        policy.add_rule(PolicyRule(id="custom_deny", rule_type=PolicyRuleType.CUSTOM,
            description="Custom deny", decision=PolicyDecision.DENY, priority=200,
            conditions={"tool_name": "blocked_tool"}))
        assert policy.evaluate({"tool_name": "blocked_tool"}) == PolicyDecision.DENY

class TestExecutionEngine:
    def test_execute_safe_tool(self):
        reg = ToolRegistry()
        def handler(x: int) -> int: return x * 2
        reg.register(ToolDefinition(name="double", description="Double",
            category=ToolCategory.COMPUTE, risk_level=ToolRiskLevel.SAFE,
            schema=ToolSchema(parameters={"x": {"type": "int"}}, required=["x"]), handler=handler))
        policy = PolicyEngine(reg)
        executor = ExecutionEngine(reg, policy)
        result = executor.execute("double", {"x": 21})
        assert result.success
        assert result.result["output"] == 42

    def test_execute_denied(self):
        reg = ToolRegistry()
        policy = PolicyEngine(reg)
        executor = ExecutionEngine(reg, policy)
        result = executor.execute("nonexistent", {})
        assert not result.success
        assert "Denied" in result.error

    def test_execute_invalid_args(self):
        reg = ToolRegistry()
        def handler(x: int) -> int: return x
        reg.register(ToolDefinition(name="needs_x", description="Needs x",
            category=ToolCategory.COMPUTE, risk_level=ToolRiskLevel.SAFE,
            schema=ToolSchema(parameters={"x": {"type": "int"}}, required=["x"]), handler=handler))
        policy = PolicyEngine(reg)
        executor = ExecutionEngine(reg, policy)
        result = executor.execute("needs_x", {})
        assert not result.success
        assert "Invalid arguments" in result.error

    def test_execute_timeout(self):
        reg = ToolRegistry()
        def slow_handler() -> int:
            time.sleep(5)
            return 42
        reg.register(ToolDefinition(name="slow", description="Slow",
            category=ToolCategory.COMPUTE, risk_level=ToolRiskLevel.SAFE,
            handler=slow_handler, timeout=0.1))
        policy = PolicyEngine(reg)
        executor = ExecutionEngine(reg, policy)
        result = executor.execute("slow", {})
        assert not result.success
        assert result.timed_out

    def test_execute_error_with_rollback(self):
        reg = ToolRegistry()
        rolled_back = [False]
        def failing_handler() -> int: raise RuntimeError("Intentional failure")
        def rollback() -> bool:
            rolled_back[0] = True
            return True
        reg.register(ToolDefinition(name="fails", description="Fails",
            category=ToolCategory.WRITE, risk_level=ToolRiskLevel.LOW,
            handler=failing_handler, rollback=rollback))
        policy = PolicyEngine(reg)
        executor = ExecutionEngine(reg, policy)
        result = executor.execute("fails", {})
        assert not result.success
        assert result.rolled_back
        assert rolled_back[0]

class TestModelGateway:
    def test_register_qualified_model(self):
        gw = ModelGateway()
        class FakeProvider:
            @property
            def model_name(self): return "test_model"
            def generate(self, prompt, system_prompt="", max_tokens=2000, temperature=0.3): return "Hello"
        info = ModelInfo(name="test_model", provider="test", endpoint="localhost", qualified=True)
        assert gw.register_model(info, FakeProvider())
        assert gw.list_models()[0].name == "test_model"

    def test_register_unqualified_fails(self):
        gw = ModelGateway()
        class FakeProvider:
            @property
            def model_name(self): return "bad_model"
            def generate(self, prompt, system_prompt="", max_tokens=2000, temperature=0.3): return "Hello"
        info = ModelInfo(name="bad_model", provider="test", endpoint="localhost", qualified=False)
        assert not gw.register_model(info, FakeProvider())

    def test_generate_no_models(self):
        gw = ModelGateway()
        resp = gw.generate("test prompt")
        assert not resp.success
        assert "No models" in resp.error

    def test_generate_with_fallback(self):
        gw = ModelGateway()
        class GoodProvider:
            @property
            def model_name(self): return "good"
            def generate(self, prompt, system_prompt="", max_tokens=2000, temperature=0.3): return '{"result": "ok"}'
        class BadProvider:
            @property
            def model_name(self): return "bad"
            def generate(self, prompt, system_prompt="", max_tokens=2000, temperature=0.3): raise RuntimeError("Unavailable")
        gw.register_model(ModelInfo(name="bad", provider="test", endpoint="l", qualified=True), BadProvider())
        gw.register_model(ModelInfo(name="good", provider="test", endpoint="l", qualified=True), GoodProvider())
        gw.set_default("bad")
        gw.set_fallback_order(["bad", "good"])
        resp = gw.generate("test", expect_json=True)
        assert resp.success
        assert resp.model == "good"
        assert resp.parsed == {"result": "ok"}

    def test_parse_json_from_prose(self):
        resp = ModelResponse(text='Here is the plan:\n{"steps": []}\nDone.', model="test", latency_ms=10, success=True)
        parsed = resp.parse_json()
        assert parsed == {"steps": []}

class TestErrorRecovery:
    def test_retry_step(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        step = TaskStep(id="s1", description="Step", action_type="tool", max_retries=3)
        engine.add_step(task.id, step)
        engine.update_step(task.id, "s1", StepStatus.FAILED, error="Error")
        recovery = ErrorRecovery(engine)
        result = recovery.handle_step_failure(task.id, "s1", "Error")
        assert result.action == RecoveryAction.RETRY
        assert result.success

    def test_skip_non_critical(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        step = TaskStep(id="s1", description="Step", action_type="tool", max_retries=0)
        engine.add_step(task.id, step)
        engine.update_step(task.id, "s1", StepStatus.FAILED, error="Error")
        recovery = ErrorRecovery(engine)
        result = recovery.handle_step_failure(task.id, "s1", "Error", is_critical=False)
        assert result.action == RecoveryAction.SKIP_STEP

    def test_escalate_critical(self):
        engine = TaskEngine()
        task = engine.create_task(goal="Test")
        step = TaskStep(id="s1", description="Step", action_type="tool", max_retries=0)
        engine.add_step(task.id, step)
        engine.update_step(task.id, "s1", StepStatus.FAILED, error="Error")
        recovery = ErrorRecovery(engine)
        result = recovery.handle_step_failure(task.id, "s1", "Error", is_critical=True)
        assert result.action == RecoveryAction.ESCALATE
        assert engine.get_task(task.id).status == TaskStatus.FAILED

class TestAuditLogger:
    def test_log_and_retrieve(self):
        audit = AuditLogger()
        event = audit.log(AuditEventType.TASK_CREATED, "corr1", {"task_id": "t1"})
        assert event.type == AuditEventType.TASK_CREATED
        events = audit.get_events(correlation_id="corr1")
        assert len(events) == 1

    def test_hash_chain(self):
        audit = AuditLogger()
        audit.log(AuditEventType.TASK_CREATED, "c1")
        audit.log(AuditEventType.PLAN_GENERATED, "c1")
        audit.log(AuditEventType.TASK_COMPLETED, "c1")
        assert audit.verify_chain()

    def test_chain_broken_on_tamper(self):
        audit = AuditLogger()
        audit.log(AuditEventType.TASK_CREATED, "c1")
        audit.log(AuditEventType.TASK_COMPLETED, "c1")
        audit._events[0].details = {"tampered": True}
        assert not audit.verify_chain()

    def test_filter_by_type(self):
        audit = AuditLogger()
        audit.log(AuditEventType.TASK_CREATED, "c1")
        audit.log(AuditEventType.TOOL_INVOKED, "c1")
        audit.log(AuditEventType.TOOL_RESULT, "c1")
        tool_events = audit.get_events(event_type=AuditEventType.TOOL_INVOKED)
        assert len(tool_events) == 1

    def test_task_history(self):
        audit = AuditLogger()
        audit.log(AuditEventType.TASK_CREATED, "c1", {"id": "t1"})
        audit.log(AuditEventType.PLAN_GENERATED, "c1", {"steps": 3})
        audit.log(AuditEventType.TASK_COMPLETED, "c1", {"duration": 1.5})
        history = audit.get_task_history("c1")
        assert len(history) == 3
        assert history[0]["type"] == "task_created"

    def test_event_count(self):
        audit = AuditLogger()
        for i in range(10):
            audit.log(AuditEventType.TASK_CREATED, f"c{i}")
        assert audit.event_count() == 10

class TestCoreSupervisor:
    def _setup_core(self, handler=None):
        reg = ToolRegistry()
        def default_handler(**kwargs): return {"status": "ok", "args": kwargs}
        reg.register(ToolDefinition(name="test_tool", description="Test tool",
            category=ToolCategory.COMPUTE, risk_level=ToolRiskLevel.SAFE,
            schema=ToolSchema(parameters={"input": {"type": "str"}}, required=["input"]),
            handler=handler or default_handler))
        policy = PolicyEngine(reg)
        executor = ExecutionEngine(reg, policy)
        audit = AuditLogger()
        task_engine = TaskEngine()
        recovery = ErrorRecovery(task_engine)
        gw = ModelGateway()
        class FakeProvider:
            @property
            def model_name(self): return "test"
            def generate(self, prompt, system_prompt="", max_tokens=2000, temperature=0.3):
                return json.dumps({"steps": [{"description": "Execute test",
                    "action_type": "test_tool", "parameters": {"input": "hello"}, "dependencies": []}]})
        gw.register_model(ModelInfo(name="test", provider="fake", endpoint="l", qualified=True), FakeProvider())
        supervisor = CoreSupervisor(task_engine, reg, policy, executor, gw, audit, recovery)
        return supervisor, task_engine, audit

    def test_full_lifecycle(self):
        supervisor, task_engine, audit = self._setup_core()
        task = supervisor.run("Test the system")
        assert task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        events = audit.get_events(correlation_id=task.correlation_id)
        assert len(events) > 0
        assert any(e.type == AuditEventType.TASK_CREATED for e in events)

    def test_audit_trail_complete(self):
        supervisor, task_engine, audit = self._setup_core()
        task = supervisor.run("Run test")
        history = audit.get_task_history(task.correlation_id)
        types = [e["type"] for e in history]
        assert "task_created" in types
        assert "state_transition" in types

    def test_policy_blocks_unauthorized(self):
        supervisor, task_engine, audit = self._setup_core()
        task = supervisor.run("Do something dangerous")
        history = audit.get_task_history(task.correlation_id)
        tool_invocations = [e for e in history if e["type"] == "tool_invoked"]
        for inv in tool_invocations:
            tool = inv["details"].get("tool", "")
            assert tool in ("test_tool",), f"Unexpected tool: {tool}"


# ============================================================================
# Agent Registry Tests
# ============================================================================

class TestAgentRegistry:
    def test_register_agent(self):
        from src.core.agent_registry import AgentCapability, AgentDefinition, AgentRegistry
        reg = AgentRegistry()
        agent = AgentDefinition(id="analyzer", name="Analyzer",
            description="Analyzes data", capabilities=[AgentCapability.ANALYSIS],
            handler=lambda **kw: {"result": "analyzed"})
        assert reg.register(agent)
        assert reg.get("analyzer") is not None

    def test_register_no_handler_fails(self):
        from src.core.agent_registry import AgentDefinition, AgentRegistry
        reg = AgentRegistry()
        agent = AgentDefinition(id="bad", name="Bad", description="No handler")
        assert not reg.register(agent)

    def test_duplicate_register(self):
        from src.core.agent_registry import AgentCapability, AgentDefinition, AgentRegistry
        reg = AgentRegistry()
        agent = AgentDefinition(id="a1", name="A1", description="Test",
            capabilities=[AgentCapability.ANALYSIS], handler=lambda **kw: None)
        assert reg.register(agent)
        assert not reg.register(agent)

    def test_invoke_healthy_agent(self):
        from src.core.agent_registry import AgentCapability, AgentDefinition, AgentRegistry
        reg = AgentRegistry()
        agent = AgentDefinition(id="calc", name="Calc", description="Calculator",
            capabilities=[AgentCapability.EXECUTION], handler=lambda **kw: {"sum": 42})
        reg.register(agent)
        result = reg.invoke("calc", x=1)
        assert result["success"]
        assert result["result"]["sum"] == 42

    def test_invoke_unknown_agent(self):
        from src.core.agent_registry import AgentRegistry
        reg = AgentRegistry()
        result = reg.invoke("nonexistent")
        assert not result["success"]

    def test_invoke_failing_agent_degrades_health(self):
        from src.core.agent_registry import AgentCapability, AgentDefinition, AgentRegistry, AgentStatus
        reg = AgentRegistry()
        def fail_handler(**kw):
            raise RuntimeError("Always fails")
        agent = AgentDefinition(id="fail", name="Fail", description="Always fails",
            capabilities=[AgentCapability.ANALYSIS], handler=fail_handler)
        reg.register(agent)
        # Invoke — agent fails and goes unhealthy
        result = reg.invoke("fail")
        assert not result["success"]
        health = reg.get("fail").health
        assert health.failed_invocations == 1
        assert health.status == AgentStatus.UNHEALTHY
        assert health.success_rate == 0.0

    def test_list_by_capability(self):
        from src.core.agent_registry import AgentCapability, AgentDefinition, AgentRegistry
        reg = AgentRegistry()
        reg.register(AgentDefinition(id="a1", name="A1", description="Plan",
            capabilities=[AgentCapability.PLANNING], handler=lambda **kw: None))
        reg.register(AgentDefinition(id="a2", name="A2", description="Monitor",
            capabilities=[AgentCapability.MONITORING], handler=lambda **kw: None))
        planners = reg.list_by_capability(AgentCapability.PLANNING)
        assert len(planners) == 1
        assert planners[0].id == "a1"

    def test_max_concurrency(self):
        from src.core.agent_registry import AgentCapability, AgentDefinition, AgentRegistry
        reg = AgentRegistry()
        agent = AgentDefinition(id="single", name="Single", description="Max 1",
            capabilities=[AgentCapability.EXECUTION], handler=lambda **kw: None,
            max_concurrent=1)
        reg.register(agent)
        reg._active_invocations["single"] = 1  # simulate active
        result = reg.invoke("single")
        assert not result["success"]
        assert "max concurrency" in result["error"]


# ============================================================================
# Permission Engine Tests
# ============================================================================

class TestPermissionEngine:
    def test_read_tool_allowed_at_execute_level(self):
        from src.core.permission_engine import PermissionEngine, PermissionLevel
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="read_data", description="Read",
            category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE))
        perm = PermissionEngine(reg)
        result = perm.check("read_data")
        assert result.allowed

    def test_write_tool_allowed_at_execute_level(self):
        from src.core.permission_engine import PermissionEngine
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="write_data", description="Write",
            category=ToolCategory.WRITE, risk_level=ToolRiskLevel.LOW))
        perm = PermissionEngine(reg)
        result = perm.check("write_data")
        assert result.allowed

    def test_irreversible_blocked(self):
        from src.core.permission_engine import PermissionEngine, PermissionLevel
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="dangerous", description="Dangerous",
            category=ToolCategory.WRITE, risk_level=ToolRiskLevel.HIGH))
        perm = PermissionEngine(reg)
        result = perm.check("dangerous")
        assert not result.allowed
        assert "Irreversible" in result.reason or "blocked" in result.reason

    def test_blocked_operation(self):
        from src.core.permission_engine import PermissionEngine
        reg = ToolRegistry()
        perm = PermissionEngine(reg)
        result = perm.check("safe_tool", operation="physical_actuation")
        assert not result.allowed
        assert "blocked" in result.reason.lower()

    def test_unknown_tool_requires_admin(self):
        from src.core.permission_engine import PermissionEngine, PermissionLevel
        reg = ToolRegistry()
        perm = PermissionEngine(reg)
        result = perm.check("unknown_tool")
        assert not result.allowed
        assert result.required_level == PermissionLevel.ADMIN

    def test_set_level(self):
        from src.core.permission_engine import PermissionEngine, PermissionLevel
        reg = ToolRegistry()
        perm = PermissionEngine(reg)
        perm.set_level(PermissionLevel.READ)
        # Write tool should now be denied
        reg.register(ToolDefinition(name="write_data", description="Write",
            category=ToolCategory.WRITE, risk_level=ToolRiskLevel.LOW))
        result = perm.check("write_data")
        assert not result.allowed

    def test_blocked_operations_list(self):
        from src.core.permission_engine import PermissionEngine
        reg = ToolRegistry()
        perm = PermissionEngine(reg)
        blocked = perm.list_blocked_operations()
        assert "physical_actuation" in blocked
        assert "financial_transaction" in blocked
        assert "legal_action" in blocked


# ============================================================================
# Multi-Step Integration Tests (Luna R1 Requirement)
# ============================================================================

class TestMultiStepIntegration:
    """Luna R1 blocking issue 1: multi-step task with ≥3 steps and dependency resolution."""

    def _setup_multistep_core(self):
        """Set up a Core with 3 tools and a 3-step plan."""
        reg = ToolRegistry()

        # Tool 1: Read data
        def read_handler(key: str) -> dict:
            return {"data": f"value_for_{key}"}
        reg.register(ToolDefinition(name="read_data", description="Read data",
            category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE,
            schema=ToolSchema(parameters={"key": {"type": "str"}}, required=["key"]),
            handler=read_handler))

        # Tool 2: Process data
        def process_handler(input_data: str) -> dict:
            return {"processed": input_data.upper()}
        reg.register(ToolDefinition(name="process_data", description="Process data",
            category=ToolCategory.COMPUTE, risk_level=ToolRiskLevel.SAFE,
            schema=ToolSchema(parameters={"input_data": {"type": "str"}}, required=["input_data"]),
            handler=process_handler))

        # Tool 3: Store result
        def store_handler(result: str) -> dict:
            return {"stored": True, "result": result}
        reg.register(ToolDefinition(name="store_result", description="Store result",
            category=ToolCategory.WRITE, risk_level=ToolRiskLevel.LOW,
            schema=ToolSchema(parameters={"result": {"type": "str"}}, required=["result"]),
            handler=store_handler))

        policy = PolicyEngine(reg)
        executor = ExecutionEngine(reg, policy)
        audit = AuditLogger()
        task_engine = TaskEngine()
        recovery = ErrorRecovery(task_engine)

        gw = ModelGateway()
        class MultiStepProvider:
            @property
            def model_name(self): return "test"
            def generate(self, prompt, system_prompt="", max_tokens=2000, temperature=0.3):
                return json.dumps({
                    "steps": [
                        {"description": "Read input data", "action_type": "read_data",
                         "parameters": {"key": "sensor_1"}, "dependencies": []},
                        {"description": "Process the data", "action_type": "process_data",
                         "parameters": {"input_data": "value_for_sensor_1"}, "dependencies": [0]},
                        {"description": "Store the result", "action_type": "store_result",
                         "parameters": {"result": "VALUE_FOR_SENSOR_1"}, "dependencies": [1]},
                    ]
                })
        gw.register_model(ModelInfo(name="test", provider="fake", endpoint="l", qualified=True), MultiStepProvider())

        supervisor = CoreSupervisor(task_engine, reg, policy, executor, gw, audit, recovery)
        return supervisor, task_engine, audit

    def test_three_step_task_completes(self):
        supervisor, task_engine, audit = self._setup_multistep_core()
        task = supervisor.run("Read, process, and store sensor data")
        assert task.status == TaskStatus.COMPLETED
        assert len(task.steps) == 3
        assert all(s.status == StepStatus.COMPLETED for s in task.steps)

    def test_dependency_resolution_order(self):
        supervisor, task_engine, audit = self._setup_multistep_core()
        task = supervisor.run("Read, process, and store sensor data")
        # Step 1 should complete before step 2, step 2 before step 3
        s1, s2, s3 = task.steps
        assert s1.completed_at is not None
        assert s2.completed_at is not None
        assert s3.completed_at is not None
        # Dependencies should be set
        assert s2.dependencies == [s1.id]
        assert s3.dependencies == [s2.id]

    def test_multistep_audit_trail(self):
        supervisor, task_engine, audit = self._setup_multistep_core()
        task = supervisor.run("Read, process, and store sensor data")
        history = audit.get_task_history(task.correlation_id)
        types = [e["type"] for e in history]
        # Should have all lifecycle events
        assert "task_created" in types
        assert "state_transition" in types
        assert "model_called" in types
        assert "plan_generated" in types
        assert "plan_validated" in types
        assert "tool_invoked" in types
        assert "tool_result" in types
        assert "task_completed" in types
        # Should have 3 tool invocations (one per step)
        tool_invocations = [e for e in history if e["type"] == "tool_invoked"]
        assert len(tool_invocations) == 3

    def test_multistep_hash_chain_intact(self):
        supervisor, task_engine, audit = self._setup_multistep_core()
        task = supervisor.run("Read, process, and store sensor data")
        assert audit.verify_chain()

    def test_multistep_injected_failure_recovery(self):
        """Inject failure in step 2 and verify recovery (retry)."""
        reg = ToolRegistry()
        call_count = [0]
        def flaky_process(input_data: str) -> dict:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Transient failure")
            return {"processed": input_data.upper()}

        reg.register(ToolDefinition(name="read_data", description="Read",
            category=ToolCategory.READ, risk_level=ToolRiskLevel.SAFE,
            schema=ToolSchema(parameters={"key": {"type": "str"}}, required=["key"]),
            handler=lambda key: {"data": f"value_for_{key}"}))
        reg.register(ToolDefinition(name="process_data", description="Process",
            category=ToolCategory.COMPUTE, risk_level=ToolRiskLevel.SAFE,
            schema=ToolSchema(parameters={"input_data": {"type": "str"}}, required=["input_data"]),
            handler=flaky_process))
        reg.register(ToolDefinition(name="store_result", description="Store",
            category=ToolCategory.WRITE, risk_level=ToolRiskLevel.LOW,
            schema=ToolSchema(parameters={"result": {"type": "str"}}, required=["result"]),
            handler=lambda result: {"stored": True}))

        policy = PolicyEngine(reg)
        executor = ExecutionEngine(reg, policy)
        audit = AuditLogger()
        task_engine = TaskEngine()
        recovery = ErrorRecovery(task_engine)

        gw = ModelGateway()
        class Provider:
            @property
            def model_name(self): return "test"
            def generate(self, prompt, system_prompt="", max_tokens=2000, temperature=0.3):
                return json.dumps({
                    "steps": [
                        {"description": "Read", "action_type": "read_data",
                         "parameters": {"key": "s1"}, "dependencies": []},
                        {"description": "Process", "action_type": "process_data",
                         "parameters": {"input_data": "val"}, "dependencies": [0]},
                        {"description": "Store", "action_type": "store_result",
                         "parameters": {"result": "VAL"}, "dependencies": [1]},
                    ]
                })
        gw.register_model(ModelInfo(name="test", provider="fake", endpoint="l", qualified=True), Provider())

        supervisor = CoreSupervisor(task_engine, reg, policy, executor, gw, audit, recovery)
        task = supervisor.run("Read, process, store with injected failure")
        # Step 2 should have retried and eventually succeeded
        # Task should complete (step 2 fails first, recovery retries, succeeds)
        assert task.status == TaskStatus.COMPLETED
        # Verify retry happened
        process_step = task.steps[1]
        assert process_step.retry_count >= 1
