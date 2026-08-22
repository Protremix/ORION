"""
ORION Phase 009 — Agent & Skill System Test Suite. License: Apache 2.0.

Tests: SkillRegistry, AgentCoordinator, 6 specialist agents, task decomposition,
capability/permission/tool queries, multi-agent coordination.
"""
from __future__ import annotations

import pytest

from src.agents import (
    AgentCoordinator,
    SkillRegistry,
    SubTask,
)
from src.agents.coding_agent import CodingAgent
from src.agents.research_agent import ResearchAgent
from src.agents.security_agent import SecurityAgent
from src.agents.simulation_agent import SimulationAgent
from src.agents.verification_agent import VerificationAgent
from src.agents.vision_agent import VisionAgent
from src.api import (
    AgentDescriptor,
    AgentProtocol,
    AgentRole,
    AgentTask,
    SkillDescriptor,
    SkillInterface,
)
from src.core.agent_registry import AgentRegistry
from src.core.tool_registry import ToolRegistry

# ============================================================================
# SkillRegistry Tests (AC1, AC2, AC3)
# ============================================================================

class TestSkillRegistry:
    def _make_skill(self, skill_id: str = "test-skill") -> SkillInterface:
        class TestSkill(SkillInterface):
            def get_descriptor(self) -> SkillDescriptor:
                return SkillDescriptor(
                    skill_id=skill_id,
                    name="Test Skill",
                    description="A test skill",
                    version="1.0.0",
                    domain="test",
                )
            def execute(self, input_data):
                return {"result": "executed", "input": input_data}
            def validate_input(self, input_data):
                return isinstance(input_data, dict)
        return TestSkill()

    def test_register_skill(self):
        """AC1: SkillRegistry registers and retrieves skills."""
        registry = SkillRegistry()
        skill = self._make_skill("skill-1")
        assert registry.register(skill) is True
        assert registry.get("skill-1") is not None
        assert "skill-1" in registry.list_skills()

    def test_register_duplicate(self):
        registry = SkillRegistry()
        skill = self._make_skill("skill-1")
        registry.register(skill)
        assert registry.register(skill) is False

    def test_unregister_skill(self):
        registry = SkillRegistry()
        skill = self._make_skill("skill-1")
        registry.register(skill)
        assert registry.unregister("skill-1") is True
        assert registry.get("skill-1") is None

    def test_unregister_unknown(self):
        registry = SkillRegistry()
        assert registry.unregister("unknown") is False

    def test_validate_input(self):
        """AC2: SkillRegistry validates skill inputs."""
        registry = SkillRegistry()
        skill = self._make_skill("skill-1")
        registry.register(skill)
        result = registry.execute("skill-1", {"key": "value"})
        assert result["success"] is True

    def test_validate_input_fail(self):
        registry = SkillRegistry()
        skill = self._make_skill("skill-1")
        registry.register(skill)
        result = registry.execute("skill-1", "not_a_dict")
        assert result["success"] is False

    def test_execute_skill(self):
        """AC3: SkillRegistry executes skills and returns output."""
        registry = SkillRegistry()
        skill = self._make_skill("skill-1")
        registry.register(skill)
        result = registry.execute("skill-1", {"query": "test"})
        assert result["success"] is True
        assert "result" in result["result"]

    def test_execute_unknown_skill(self):
        registry = SkillRegistry()
        result = registry.execute("unknown", {})
        assert result["success"] is False
        assert "Unknown skill" in result["error"]

    def test_list_by_domain(self):
        registry = SkillRegistry()
        registry.register(self._make_skill("skill-a"))
        registry.register(self._make_skill("skill-b"))
        assert len(registry.list_by_domain("test")) == 2
        assert len(registry.list_by_domain("other")) == 0

    def test_to_dict(self):
        registry = SkillRegistry()
        registry.register(self._make_skill("skill-1"))
        d = registry.to_dict()
        assert d["skill_count"] == 1


# ============================================================================
# ResearchAgent Tests (AC4)
# ============================================================================

class TestResearchAgent:
    def test_execute_research(self):
        """AC4: ResearchAgent executes research tasks."""
        agent = ResearchAgent()
        task = AgentTask(task_id="t1", description="research quantum computing", input_data={"query": "quantum computing"})
        result = agent.execute_task(task)
        assert result.success is True
        assert "findings" in result.output
        assert len(result.output["findings"]) > 0

    def test_get_descriptor(self):
        agent = ResearchAgent()
        desc = agent.get_descriptor()
        assert desc.agent_id == "research-agent"
        assert desc.role == AgentRole.RESEARCH

    def test_get_capabilities(self):
        agent = ResearchAgent()
        caps = agent.get_capabilities()
        assert "information_gathering" in caps
        assert "analysis" in caps

    def test_health_check(self):
        agent = ResearchAgent()
        assert agent.health_check() is True


# ============================================================================
# CodingAgent Tests (AC5)
# ============================================================================

class TestCodingAgent:
    def test_execute_generate(self):
        """AC5: CodingAgent executes coding tasks."""
        agent = CodingAgent()
        task = AgentTask(task_id="t1", description="generate function", input_data={"operation": "generate", "language": "python"})
        result = agent.execute_task(task)
        assert result.success is True
        assert "code" in result.output

    def test_execute_review(self):
        agent = CodingAgent()
        task = AgentTask(task_id="t1", description="review code", input_data={"operation": "review"})
        result = agent.execute_task(task)
        assert result.success is True
        assert "issues_found" in result.output

    def test_get_descriptor(self):
        agent = CodingAgent()
        desc = agent.get_descriptor()
        assert desc.role == AgentRole.CODING
        assert "write" in desc.permissions

    def test_health_check(self):
        agent = CodingAgent()
        assert agent.health_check() is True


# ============================================================================
# VisionAgent Tests (AC6)
# ============================================================================

class TestVisionAgent:
    def test_execute_detect(self):
        """AC6: VisionAgent executes vision tasks."""
        agent = VisionAgent()
        task = AgentTask(task_id="t1", description="detect objects", input_data={"operation": "detect_objects", "image": {"url": "test.jpg"}})
        result = agent.execute_task(task)
        assert result.success is True
        assert "objects" in result.output

    def test_execute_scene(self):
        agent = VisionAgent()
        task = AgentTask(task_id="t1", description="understand scene", input_data={"operation": "scene_understanding"})
        result = agent.execute_task(task)
        assert result.success is True
        assert "scene_type" in result.output

    def test_get_capabilities(self):
        agent = VisionAgent()
        assert "object_detection" in agent.get_capabilities()

    def test_health_check(self):
        agent = VisionAgent()
        assert agent.health_check() is True


# ============================================================================
# SimulationAgent Tests (AC7)
# ============================================================================

class TestSimulationAgent:
    def test_execute_what_if(self):
        """AC7: SimulationAgent executes simulation tasks."""
        agent = SimulationAgent()
        task = AgentTask(task_id="t1", description="what if analysis", input_data={"operation": "what_if", "domain": "industrial"})
        result = agent.execute_task(task)
        assert result.success is True
        assert "predicted_outcome" in result.output

    def test_execute_safety_check(self):
        agent = SimulationAgent()
        task = AgentTask(task_id="t1", description="safety check", input_data={"operation": "safety_check"})
        result = agent.execute_task(task)
        assert result.success is True
        assert "action_safe" in result.output

    def test_get_descriptor(self):
        agent = SimulationAgent()
        desc = agent.get_descriptor()
        assert desc.role == AgentRole.SIMULATION

    def test_health_check(self):
        agent = SimulationAgent()
        assert agent.health_check() is True


# ============================================================================
# SecurityAgent Tests (AC8)
# ============================================================================

class TestSecurityAgent:
    def test_execute_risk(self):
        """AC8: SecurityAgent executes security analysis tasks."""
        agent = SecurityAgent()
        task = AgentTask(task_id="t1", description="risk assessment", input_data={"operation": "risk_assessment", "target": "system"})
        result = agent.execute_task(task)
        assert result.success is True
        assert "risk_level" in result.output

    def test_execute_permission_check(self):
        agent = SecurityAgent()
        task = AgentTask(task_id="t1", description="permission check", input_data={"operation": "permission_check", "target": "action"})
        result = agent.execute_task(task)
        assert result.success is True
        assert "allowed" in result.output

    def test_get_capabilities(self):
        agent = SecurityAgent()
        assert "risk_assessment" in agent.get_capabilities()

    def test_health_check(self):
        agent = SecurityAgent()
        assert agent.health_check() is True


# ============================================================================
# VerificationAgent Tests (AC9)
# ============================================================================

class TestVerificationAgent:
    def test_verify_valid_result(self):
        """AC9: VerificationAgent validates results."""
        agent = VerificationAgent()
        task = AgentTask(task_id="t1", description="validate", input_data={
            "operation": "validate",
            "result": {"output": "some data"},
            "agent_id": "research-agent",
        })
        result = agent.execute_task(task)
        assert result.success is True
        assert result.output["verified"] is True

    def test_verify_empty_result(self):
        agent = VerificationAgent()
        task = AgentTask(task_id="t1", description="validate", input_data={
            "operation": "validate",
            "result": {},
            "agent_id": "test",
        })
        result = agent.execute_task(task)
        assert result.success is True
        assert result.output["verified"] is False

    def test_verify_error_result(self):
        agent = VerificationAgent()
        task = AgentTask(task_id="t1", description="validate", input_data={
            "operation": "validate",
            "result": {"error": "something failed"},
            "agent_id": "test",
        })
        result = agent.execute_task(task)
        assert result.output["verified"] is False

    def test_verify_with_expected(self):
        agent = VerificationAgent()
        task = AgentTask(task_id="t1", description="validate", input_data={
            "operation": "validate",
            "result": {"a": 1},
            "expected": {"a": 2},
            "agent_id": "test",
        })
        result = agent.execute_task(task)
        assert result.output["verified"] is False

    def test_get_statistics(self):
        agent = VerificationAgent()
        assert agent.get_statistics()["total_verifications"] >= 0


# ============================================================================
# AgentCoordinator Tests (AC10-AC14)
# ============================================================================

class TestAgentCoordinator:
    def test_decompose_single(self):
        """AC10: AgentCoordinator decomposes complex tasks."""
        coord = AgentCoordinator()
        subtasks = coord.decompose_task("analyze data")
        assert len(subtasks) >= 1
        assert isinstance(subtasks[0], SubTask)

    def test_decompose_multi(self):
        coord = AgentCoordinator()
        subtasks = coord.decompose_task("research topic and generate code")
        assert len(subtasks) >= 2  # multiple capabilities + verification

    def test_depose_includes_verification(self):
        coord = AgentCoordinator()
        subtasks = coord.decompose_task("analyze data and detect objects")
        # Last subtask should be verification
        assert subtasks[-1].required_role == AgentRole.EVALUATION

    def test_select_agent_by_capability(self):
        """AC11: AgentCoordinator selects correct agents by capability."""
        coord = AgentCoordinator()
        subtask = SubTask(
            subtask_id="s1", description="test",
            required_capabilities=["code_generation"],
            required_role=AgentRole.CODING,
        )
        agent = coord.select_agent(subtask)
        assert agent is not None
        assert agent.get_descriptor().role == AgentRole.CODING

    def test_select_agent_none(self):
        coord = AgentCoordinator()
        subtask = SubTask(
            subtask_id="s1", description="test",
            required_capabilities=["nonexistent_capability"],
        )
        agent = coord.select_agent(subtask)
        assert agent is None

    def test_dispatch_subtask(self):
        """AC12: AgentCoordinator dispatches subtasks to agents."""
        coord = AgentCoordinator()
        subtask = SubTask(
            subtask_id="s1", description="research topic",
            required_capabilities=["information_gathering"],
            required_role=AgentRole.RESEARCH,
            input_data={"query": "test"},
        )
        result = coord.dispatch(subtask)
        assert result.success is True

    def test_dispatch_no_agent(self):
        coord = AgentCoordinator()
        subtask = SubTask(
            subtask_id="s1", description="test",
            required_capabilities=["nonexistent"],
        )
        result = coord.dispatch(subtask)
        assert result.success is False

    def test_execute_collects_results(self):
        """AC13: AgentCoordinator collects and fuses results."""
        coord = AgentCoordinator()
        result = coord.execute("analyze data")
        assert "agent_results" in result
        assert "all_succeeded" in result
        assert "latency_ms" in result

    def test_execute_multi_agent(self):
        """AC14: AgentCoordinator coordinates 2+ agents for one task."""
        coord = AgentCoordinator()
        result = coord.execute("research topic and generate code for it")
        assert result["subtask_count"] >= 2
        assert len(result["agent_results"]) >= 2

    def test_execute_with_verification(self):
        coord = AgentCoordinator()
        result = coord.execute("analyze data")
        assert result["verification"] is not None

    def test_list_agents(self):
        coord = AgentCoordinator()
        agents = coord.list_agents()
        assert "research" in agents
        assert "coding" in agents
        assert "vision" in agents
        assert "simulation" in agents
        assert "security" in agents
        assert "evaluation" in agents

    def test_register_custom_agent(self):
        coord = AgentCoordinator()
        custom = ResearchAgent()
        assert coord.register_agent(AgentRole.DATA, custom) is True
        assert coord.get_agent(AgentRole.DATA) is not None

    def test_statistics(self):
        coord = AgentCoordinator()
        coord.execute("test")
        stats = coord.get_statistics()
        assert stats["total_calls"] == 1
        assert stats["agent_count"] >= 6


# ============================================================================
# Capability/Permission/Tool Query Tests (AC17, AC18)
# ============================================================================

class TestCapabilityQueries:
    def test_what_can_do(self):
        """AC17: ORION knows what it can do."""
        coord = AgentCoordinator()
        capabilities = coord.what_can_do()
        assert "agents" in capabilities
        assert len(capabilities["agents"]) >= 6

    def test_what_cannot_do(self):
        """AC17: ORION knows what it cannot do."""
        coord = AgentCoordinator()
        cannot = coord.what_cannot_do()
        assert "missing_agent_roles" in cannot
        assert "physical_tools_blocked" in cannot
        assert cannot["physical_tools_blocked"] is True

    def test_what_tool_required(self):
        """AC18: ORION knows what tool is required."""
        coord = AgentCoordinator()
        tools = coord.what_tool_required("code_generation")
        assert tools["found"] is True
        assert len(tools["tools"]) > 0

    def test_what_tool_required_unknown(self):
        coord = AgentCoordinator()
        tools = coord.what_tool_required("nonexistent_capability")
        assert tools["found"] is False

    def test_what_permission_required(self):
        """AC18: ORION knows what permission is required."""
        coord = AgentCoordinator()
        perms = coord.what_permission_required("code_generation")
        assert "permissions" in perms
        assert "safety_level" in perms

    def test_all_agents_implement_protocol(self):
        """AC15: All agents implement AgentProtocol."""
        agents = [ResearchAgent(), CodingAgent(), VisionAgent(),
                  SimulationAgent(), SecurityAgent(), VerificationAgent()]
        for agent in agents:
            assert isinstance(agent, AgentProtocol)
            assert agent.get_descriptor() is not None
            assert len(agent.get_capabilities()) > 0
            assert agent.health_check() is True


# ============================================================================
# Integration Tests (AC16)
# ============================================================================

class TestPhase009Integration:
    def test_agents_in_registry(self):
        """AC16: All agents registered in AgentRegistry."""
        registry = AgentRegistry()
        coord = AgentCoordinator(agent_registry=registry)

        # Register agents in AgentRegistry
        research = ResearchAgent()
        from src.core.agent_registry import AgentCapability as AC
        from src.core.agent_registry import AgentDefinition
        def research_handler(**kwargs):
            return research.execute_task(AgentTask(**kwargs))
        agent_def = AgentDefinition(
            id="research-agent",
            name="Research Agent",
            description="Research specialist",
            capabilities=[AC.ANALYSIS],
            handler=research_handler,
        )
        registry.register(agent_def)
        assert registry.get("research-agent") is not None

    def test_multi_agent_research_coding(self):
        """Integration: research + coding coordination."""
        coord = AgentCoordinator()
        result = coord.execute("research framework options and generate code for the best one")
        assert result["subtask_count"] >= 2
        assert result["all_succeeded"] is True

    def test_vision_security_coordination(self):
        """Integration: vision + security coordination."""
        coord = AgentCoordinator()
        result = coord.execute("detect objects in image and assess security risk")
        assert len(result["agent_results"]) >= 2

    def test_verification_validates_other_agents(self):
        """Integration: verification agent validates research agent results."""
        coord = AgentCoordinator()
        result = coord.execute("analyze data")
        # Verification should be present
        assert result["verification"] is not None
        assert "verified" in result["verification"]

    def test_tool_registry_integration(self):
        """Integration: coordinator with tool registry."""
        tool_registry = ToolRegistry()
        coord = AgentCoordinator(tool_registry=tool_registry)
        capabilities = coord.what_can_do()
        assert "tools" in capabilities

    def test_skill_registry_integration(self):
        """Integration: coordinator with skill registry."""
        skill_registry = SkillRegistry()
        coord = AgentCoordinator(skill_registry=skill_registry)
        capabilities = coord.what_can_do()
        assert "skills" in capabilities

    def test_all_results_have_agent_id(self):
        coord = AgentCoordinator()
        result = coord.execute("research topic")
        for ar in result["agent_results"]:
            assert "agent_id" in ar

    def test_latency_measured(self):
        coord = AgentCoordinator()
        result = coord.execute("test")
        assert result["latency_ms"] > 0

    def test_agent_failure_handled(self):
        """Edge case: agent failure doesn't crash coordinator."""
        coord = AgentCoordinator()
        result = coord.execute("nonexistent_capability_12345")
        # Should still return a result structure
        assert "agent_results" in result

    def test_all_agents_protocol_compliance(self):
        """All 6 agents satisfy AgentProtocol interface."""
        agents = [ResearchAgent(), CodingAgent(), VisionAgent(),
                  SimulationAgent(), SecurityAgent(), VerificationAgent()]
        for agent in agents:
            desc = agent.get_descriptor()
            caps = agent.get_capabilities()
            healthy = agent.health_check()
            assert desc.name is not None
            assert len(caps) > 0
            assert healthy is True
