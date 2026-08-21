"""
Tests for the ORION API/SDK interfaces — Master Spec §12.
"""

import os

import pytest

from src.api import (
    ORIONAPI,
    AgentDescriptor,
    AgentProtocol,
    AgentResult,
    AgentRole,
    AgentTask,
    ModelAdapter,
    ModelDescriptor,
    ModelType,
    ORIONResponse,
    ORIONStatus,
    SimulationConfig,
    SimulationInterface,
    SimulationResult,
    SkillDescriptor,
    SkillInterface,
    ToolDescriptor,
    ToolInterface,
)
from src.api.auth import AuthConfig, AuthManager
from src.hal import ConnectionType, DeviceDescriptor, DeviceType, HardwareAbstractionLayer, SimulationAdapter


def make_test_api(**kwargs):
    """Create ORIONAPI with test auth configured."""
    auth = AuthManager(AuthConfig(enabled=True, api_key="test_key"))
    from src.api.permissions import PermissionChecker, PermissionLevel
    PermissionChecker.clear()
    PermissionChecker.register_agent_permissions("test_agent", [PermissionLevel.SUPERVISOR])
    PermissionChecker.register_agent_permissions("supervisor", [PermissionLevel.SUPERVISOR])
    return ORIONAPI(auth_manager=auth, **kwargs)


# ============================================================================
# ORION API Tests
# ============================================================================

class TestORIONAPI:
    def test_api_init_empty(self):
        api = ORIONAPI()
        assert api._safety is None
        assert api._hal is None
        assert api._memory is None

    def test_observe(self):
        api = make_test_api()
        resp = api.observe("sim", {"type": "grid"}, agent_id="test_agent", token="test_key")
        assert resp.ok
        assert resp.data["source"] == "sim"

    def test_observe_invalid_input_rejected(self):
        """Invalid input (None source) should be rejected."""
        api = make_test_api()
        resp = api.observe(None, {"type": "grid"}, agent_id="test_agent", token="test_key")
        assert not resp.ok
        assert "Invalid" in resp.error

    def test_get_world_state_no_supervisor(self):
        api = make_test_api()
        resp = api.get_world_state(agent_id="test_agent", token="test_key")
        assert resp.ok
        assert resp.data == {}

    def test_recall_no_memory(self):
        api = make_test_api()
        resp = api.recall("test query", agent_id="test_agent", token="test_key")
        assert resp.ok
        assert resp.data == []

    def test_remember_no_memory(self):
        api = make_test_api()
        resp = api.remember({"event": "test"}, agent_id="test_agent", token="test_key")
        assert resp.ok
        assert resp.data["stored"] is False

    def test_plan(self):
        api = make_test_api()
        resp = api.plan("move robot to position", agent_id="test_agent", token="test_key")
        assert resp.ok
        assert resp.data["goal"] == "move robot to position"

    def test_simulate(self):
        api = make_test_api()
        resp = api.simulate({"command": "move", "x": 1.0}, agent_id="test_agent", token="test_key")
        assert resp.ok
        assert resp.data["result"] == "simulated"

    def test_execute_no_safety_rejected(self):
        """Without safety gateway, execute should reject hardware actions."""
        api = make_test_api()
        resp = api.execute({"device_id": "d1", "command_type": "move"}, simulate_first=False, agent_id="test_agent", token="test_key")
        assert resp.status == ORIONStatus.UNAUTHORIZED

    def test_emergency_stop_no_hal(self):
        api = make_test_api()
        resp = api.emergency_stop(agent_id="supervisor", token="test_key")
        assert resp.ok
        assert resp.data["estop"] == "no_hardware"

    def test_emergency_stop_with_hal(self):
        from src.api.permissions import PermissionChecker, PermissionLevel
        auth = AuthManager(AuthConfig(enabled=True, api_key="test_key"))
        PermissionChecker.clear()
        PermissionChecker.register_agent_permissions("supervisor", [PermissionLevel.SUPERVISOR])
        hal = HardwareAbstractionLayer(safety_gateway=None)
        desc = DeviceDescriptor(
            device_id="robot_01", name="Robot", manufacturer="ORION",
            model="R1", device_type=DeviceType.ROBOT, connection_type=ConnectionType.SIMULATION,
        )
        adapter = SimulationAdapter(desc)
        hal.register_adapter(adapter)
        hal.connect_device("robot_01")
        api = ORIONAPI(hal=hal, auth_manager=auth)
        resp = api.emergency_stop(agent_id="supervisor", token="test_key")
        assert resp.ok
        assert "robot_01" in resp.data

    def test_debug_mode_does_not_bypass_auth(self):
        """Debug mode must NOT bypass authentication."""
        auth = AuthManager(AuthConfig(enabled=True, api_key="test_key", debug_mode=True))
        # Even with debug_mode=True, authenticate must still check token
        assert not auth.authenticate(None)  # No token -> denied
        assert not auth.authenticate("wrong_key")  # Wrong key -> denied
        assert auth.authenticate("test_key")  # Right key -> allowed

    def test_physical_without_device_id_rejected(self):
        """PHYSICAL action without device_id must be rejected."""
        api = make_test_api()
        resp = api.execute(
            {"action_category": "PHYSICAL", "command": "move_robot"},
            simulate_first=False,
            agent_id="test_agent",
            token="test_key",
        )
        assert not resp.ok
        assert "device_id" in resp.error


# ============================================================================
# Agent Protocol Tests
# ============================================================================

class TestAgentProtocol:
    def test_agent_descriptor_defaults(self):
        desc = AgentDescriptor(
            agent_id="agent_01",
            name="Research Agent",
            role=AgentRole.RESEARCH,
        )
        assert desc.capabilities == []
        assert desc.permissions == []
        assert desc.tools == []
        assert desc.safety_level == "SC_3"
        assert desc.max_concurrent_tasks == 1

    def test_agent_task_defaults(self):
        task = AgentTask(agent_id="agent_01", task_type="research", description="Test")
        assert task.task_id
        assert task.priority == 0
        assert task.input_data == {}

    def test_agent_result(self):
        result = AgentResult(
            task_id="t1",
            agent_id="agent_01",
            success=True,
            output={"findings": "test"},
        )
        assert result.success is True
        assert result.output["findings"] == "test"
        assert result.error is None

    def test_agent_roles_enum(self):
        assert AgentRole.RESEARCH == "research"
        assert AgentRole.ENGINEERING == "engineering"
        assert AgentRole.VISION == "vision"
        assert AgentRole.DRONE == "drone"


# ============================================================================
# Skill Interface Tests
# ============================================================================

class TestSkillInterface:
    def test_skill_descriptor_defaults(self):
        desc = SkillDescriptor(
            skill_id="skill_01",
            name="Test Skill",
            description="A test skill",
        )
        assert desc.version == "0.1.0"
        assert desc.input_schema == {}
        assert desc.requires_hardware is False
        assert desc.safety_level == "SC_3"

    def test_skill_descriptor_with_hardware(self):
        desc = SkillDescriptor(
            skill_id="skill_02",
            name="Robot Control",
            description="Control a robot arm",
            requires_hardware=True,
            safety_level="SC_1",
        )
        assert desc.requires_hardware is True
        assert desc.safety_level == "SC_1"


# ============================================================================
# Tool Interface Tests
# ============================================================================

class TestToolInterface:
    def test_tool_descriptor_defaults(self):
        desc = ToolDescriptor(
            tool_id="tool_01",
            name="Web Search",
            description="Search the web",
            tool_type="api",
        )
        assert desc.requires_auth is False
        assert desc.safety_level == "SC_3"
        assert desc.input_schema == {}

    def test_tool_descriptor_with_auth(self):
        desc = ToolDescriptor(
            tool_id="tool_02",
            name="Email Sender",
            description="Send emails",
            tool_type="api",
            requires_auth=True,
            safety_level="SC_2",
        )
        assert desc.requires_auth is True
        assert desc.safety_level == "SC_2"


# ============================================================================
# Simulation Interface Tests
# ============================================================================

class TestSimulationInterface:
    def test_simulation_config_defaults(self):
        config = SimulationConfig()
        assert config.domain == "industrial"
        assert config.duration_seconds == 60.0
        assert config.time_step == 0.1
        assert config.safety_checks is True
        assert config.record_trace is True

    def test_simulation_config_custom(self):
        config = SimulationConfig(
            domain="vehicle",
            duration_seconds=10.0,
            time_step=0.01,
            seed=42,
            safety_checks=False,
        )
        assert config.domain == "vehicle"
        assert config.seed == 42
        assert config.safety_checks is False

    def test_simulation_result_defaults(self):
        result = SimulationResult(success=True)
        assert result.final_state == {}
        assert result.trace == []
        assert result.safety_events == []


# ============================================================================
# Model Adapter Tests
# ============================================================================

class TestModelAdapter:
    def test_model_descriptor_defaults(self):
        desc = ModelDescriptor(
            model_id="gpt-4o",
            name="GPT-4o",
            model_type=ModelType.LLM,
            provider="OpenAI",
        )
        assert desc.max_tokens == 4096
        assert desc.supports_streaming is False
        assert desc.requires_api_key is True
        assert desc.cost_per_1k_tokens == 0.0

    def test_model_types_enum(self):
        assert ModelType.LLM == "llm"
        assert ModelType.VISION == "vision"
        assert ModelType.WORLD_MODEL == "world_model"
        assert ModelType.EMBEDDING == "embedding"


# ============================================================================
# ORIONResponse Tests
# ============================================================================

class TestORIONResponse:
    def test_ok_response(self):
        resp = ORIONResponse(status=ORIONStatus.OK, data={"key": "value"})
        assert resp.ok is True
        assert resp.data["key"] == "value"
        assert resp.error is None

    def test_error_response(self):
        resp = ORIONResponse(status=ORIONStatus.ERROR, error="Something went wrong")
        assert resp.ok is False
        assert resp.error == "Something went wrong"

    def test_response_has_request_id(self):
        resp = ORIONResponse(status=ORIONStatus.OK)
        assert resp.request_id

    def test_unique_request_ids(self):
        resp1 = ORIONResponse(status=ORIONStatus.OK)
        resp2 = ORIONResponse(status=ORIONStatus.OK)
        assert resp1.request_id != resp2.request_id
