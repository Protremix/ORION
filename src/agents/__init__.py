"""
ORION Phase 009 — Agent & Skill System. License: Apache 2.0.

SkillRegistry: register, validate, and execute modular skills.
AgentCoordinator: decompose tasks, select agents, dispatch, collect, verify.

ORION must know:
- WHAT IT CAN DO (registered agents/skills/tools)
- WHAT IT CANNOT DO (unregistered, forbidden, permission-denied)
- WHAT TOOL IS REQUIRED (tool registry lookup)
- WHAT PERMISSION IS REQUIRED (permission engine check)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from src.agents.coding_agent import CodingAgent
from src.agents.research_agent import ResearchAgent
from src.agents.security_agent import SecurityAgent
from src.agents.simulation_agent import SimulationAgent
from src.agents.verification_agent import VerificationAgent
from src.agents.vision_agent import VisionAgent
from src.api import (
    AgentDescriptor,
    AgentProtocol,
    AgentResult,
    AgentRole,
    AgentTask,
    SkillDescriptor,
    SkillInterface,
)
from src.core.agent_registry import AgentCapability, AgentDefinition, AgentRegistry
from src.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# Skill Registry
# ============================================================================

class SkillRegistry:
    """
    Central registry for modular skills.
    Skills are self-contained, replaceable units of capability.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, SkillInterface] = {}
        self._descriptors: Dict[str, SkillDescriptor] = {}

    def register(self, skill: SkillInterface) -> bool:
        """Register a skill. Returns False if already registered."""
        desc = skill.get_descriptor()
        if desc.skill_id in self._skills:
            logger.warning("Skill already registered: %s", desc.skill_id)
            return False
        self._skills[desc.skill_id] = skill
        self._descriptors[desc.skill_id] = desc
        logger.info("Registered skill: %s", desc.skill_id)
        return True

    def unregister(self, skill_id: str) -> bool:
        if skill_id not in self._skills:
            return False
        del self._skills[skill_id]
        del self._descriptors[skill_id]
        return True

    def get(self, skill_id: str) -> Optional[SkillInterface]:
        return self._skills.get(skill_id)

    def get_descriptor(self, skill_id: str) -> Optional[SkillDescriptor]:
        return self._descriptors.get(skill_id)

    def list_skills(self) -> List[str]:
        return list(self._skills.keys())

    def list_by_domain(self, domain: str) -> List[str]:
        return [sid for sid, desc in self._descriptors.items()
                if desc.domain == domain]

    def execute(self, skill_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a skill by ID. Returns dict with success status."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"Unknown skill: {skill_id}"}
        if not skill.validate_input(input_data):
            return {"success": False, "error": f"Input validation failed for: {skill_id}"}
        try:
            result = skill.execute(input_data)
            return {"success": True, "result": result, "skill_id": skill_id}
        except Exception as e:
            logger.exception("Skill execution failed: %s", skill_id)
            return {"success": False, "error": str(e), "skill_id": skill_id}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_count": len(self._skills),
            "skills": {sid: {
                "name": d.name,
                "description": d.description,
                "version": d.version,
                "domain": d.domain,
            } for sid, d in self._descriptors.items()},
        }


# ============================================================================
# Task Decomposition
# ============================================================================

@dataclass
class SubTask:
    """A subtask resulting from task decomposition."""
    subtask_id: str
    description: str
    required_capabilities: List[str] = field(default_factory=list)
    required_role: Optional[AgentRole] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0


# Capability → Agent role mapping
_CAPABILITY_ROLE_MAP: Dict[str, AgentRole] = {
    "information_gathering": AgentRole.RESEARCH,
    "analysis": AgentRole.RESEARCH,
    "web_search": AgentRole.RESEARCH,
    "summarization": AgentRole.RESEARCH,
    "code_generation": AgentRole.CODING,
    "code_review": AgentRole.CODING,
    "refactoring": AgentRole.CODING,
    "bug_fixing": AgentRole.CODING,
    "image_analysis": AgentRole.VISION,
    "object_detection": AgentRole.VISION,
    "scene_understanding": AgentRole.VISION,
    "visual_qa": AgentRole.VISION,
    "physics_simulation": AgentRole.SIMULATION,
    "what_if_analysis": AgentRole.SIMULATION,
    "predictive_modeling": AgentRole.SIMULATION,
    "safety_simulation": AgentRole.SIMULATION,
    "safety_analysis": AgentRole.SECURITY,
    "permission_checks": AgentRole.SECURITY,
    "risk_assessment": AgentRole.SECURITY,
    "threat_detection": AgentRole.SECURITY,
    "result_validation": AgentRole.EVALUATION,
    "test_execution": AgentRole.EVALUATION,
    "quality_checks": AgentRole.EVALUATION,
    "consistency_verification": AgentRole.EVALUATION,
}

# Keywords that trigger capabilities
_CAPABILITY_KEYWORDS: Dict[str, List[str]] = {
    "information_gathering": ["research", "find", "gather", "search", "look up"],
    "analysis": ["analyze", "examine", "evaluate", "assess"],
    "summarization": ["summarize", "summarise", "brief", "overview"],
    "code_generation": ["generate code", "write code", "create function", "implement"],
    "code_review": ["review code", "audit code", "check code"],
    "refactoring": ["refactor", "restructure", "clean up"],
    "bug_fixing": ["fix bug", "debug", "resolve error"],
    "image_analysis": ["analyze image", "process image", "examine image"],
    "object_detection": ["detect objects", "find objects", "identify objects"],
    "scene_understanding": ["understand scene", "describe scene", "scene analysis"],
    "physics_simulation": ["simulate physics", "physics simulation"],
    "what_if_analysis": ["what if", "predict outcome", "simulate scenario"],
    "safety_simulation": ["safety simulation", "safety check", "verify safety"],
    "safety_analysis": ["safety analysis", "analyze safety", "safety review"],
    "risk_assessment": ["risk assessment", "assess risk", "evaluate risk"],
    "threat_detection": ["threat detection", "detect threats", "security scan"],
    "result_validation": ["validate result", "verify result", "check result"],
    "test_execution": ["run tests", "execute tests", "test suite"],
    "quality_checks": ["quality check", "quality assurance", "qa"],
}


# ============================================================================
# Agent Coordinator
# ============================================================================

class AgentCoordinator:
    """
    ORION Phase 009 — Agent Coordinator.

    Coordinates specialist agents for complex tasks:
    1. Decompose task into subtasks
    2. Select appropriate agents by capability
    3. Dispatch subtasks to agents
    4. Collect and fuse results
    5. Verify results via VerificationAgent
    """

    def __init__(
        self,
        agent_registry: Optional[AgentRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
        skill_registry: Optional[SkillRegistry] = None,
    ) -> None:
        self._agent_registry = agent_registry or AgentRegistry()
        self._tool_registry = tool_registry
        self._skill_registry = skill_registry
        self._specialist_agents: Dict[AgentRole, AgentProtocol] = {}
        self._verification_agent = VerificationAgent()
        self._register_default_agents()
        self._call_count = 0
        self._total_latency = 0.0

    def _register_default_agents(self) -> None:
        """Register default specialist agents."""
        defaults: Dict[AgentRole, AgentProtocol] = {
            AgentRole.RESEARCH: ResearchAgent(),
            AgentRole.CODING: CodingAgent(),
            AgentRole.VISION: VisionAgent(),
            AgentRole.SIMULATION: SimulationAgent(),
            AgentRole.SECURITY: SecurityAgent(),
            AgentRole.EVALUATION: self._verification_agent,
        }
        for role, agent in defaults.items():
            self._specialist_agents[role] = agent

    def register_agent(self, role: AgentRole, agent: AgentProtocol) -> bool:
        """Register a specialist agent for a specific role."""
        if role in self._specialist_agents:
            logger.warning("Agent already registered for role: %s", role.value)
            return False
        self._specialist_agents[role] = agent
        logger.info("Registered agent for role: %s", role.value)
        return True

    def get_agent(self, role: AgentRole) -> Optional[AgentProtocol]:
        """Get the agent for a specific role."""
        return self._specialist_agents.get(role)

    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all registered agents with their capabilities."""
        return {
            role.value: {
                "name": agent.get_descriptor().name,
                "capabilities": agent.get_capabilities(),
                "tools": agent.get_descriptor().tools,
                "permissions": agent.get_descriptor().permissions,
            }
            for role, agent in self._specialist_agents.items()
        }

    def decompose_task(self, description: str,
                       input_data: Optional[Dict[str, Any]] = None) -> List[SubTask]:
        """Decompose a complex task into subtasks based on required capabilities."""
        data = input_data or {}
        capabilities = self._infer_capabilities(description)

        # If only one capability, single subtask
        if len(capabilities) <= 1:
            role = _CAPABILITY_ROLE_MAP.get(capabilities[0]) if capabilities else None
            return [SubTask(
                subtask_id="subtask_0",
                description=description,
                required_capabilities=capabilities,
                required_role=role,
                input_data=data,
            )]

        # Multiple capabilities: create subtasks + verification subtask
        subtasks: List[SubTask] = []
        for i, cap in enumerate(capabilities):
            role = _CAPABILITY_ROLE_MAP.get(cap)
            subtasks.append(SubTask(
                subtask_id=f"subtask_{i}",
                description=f"{cap}: {description}",
                required_capabilities=[cap],
                required_role=role,
                input_data={**data, "operation": cap},
            ))

        # Add verification subtask
        subtasks.append(SubTask(
            subtask_id=f"subtask_{len(subtasks)}",
            description=f"Verify results for: {description}",
            required_capabilities=["result_validation"],
            required_role=AgentRole.EVALUATION,
            input_data={"operation": "validate"},
        ))

        return subtasks

    def select_agent(self, subtask: SubTask) -> Optional[AgentProtocol]:
        """Select the appropriate agent for a subtask."""
        if subtask.required_role:
            return self._specialist_agents.get(subtask.required_role)

        # Fallback: match by capability
        for cap in subtask.required_capabilities:
            role = _CAPABILITY_ROLE_MAP.get(cap)
            if role and role in self._specialist_agents:
                return self._specialist_agents[role]

        return None

    def dispatch(self, subtask: SubTask) -> AgentResult:
        """Dispatch a subtask to the selected agent."""
        agent = self.select_agent(subtask)
        if not agent:
            return AgentResult(
                task_id=subtask.subtask_id,
                agent_id="none",
                success=False,
                error=f"No agent available for capabilities: {subtask.required_capabilities}",
            )

        task = AgentTask(
            task_id=subtask.subtask_id,
            agent_id=agent.get_descriptor().agent_id,
            task_type=subtask.required_capabilities[0] if subtask.required_capabilities else "general",
            description=subtask.description,
            input_data=subtask.input_data,
        )

        return agent.execute_task(task)

    def execute(self, description: str,
                input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a complex task: decompose → dispatch → collect → verify."""
        start = time.time()
        self._call_count += 1

        subtasks = self.decompose_task(description, input_data)
        results: List[AgentResult] = []

        for st in subtasks:
            result = self.dispatch(st)
            results.append(result)

        # Verify results (if verification agent was not already used)
        verification_result = None
        if results and not any(
            r.agent_id == "verification-agent" for r in results
        ):
            # Collect all results for verification
            combined_output = {
                "results": [{"agent_id": r.agent_id, "success": r.success,
                             "output": r.output} for r in results],
            }
            verify_task = AgentTask(
                task_id="verify_combined",
                agent_id="verification-agent",
                task_type="result_validation",
                description=f"Verify combined results for: {description}",
                input_data={
                    "operation": "validate",
                    "result": combined_output,
                    "agent_id": "coordinator",
                },
            )
            verification_result = self._verification_agent.execute_task(verify_task)

        elapsed = time.time() - start
        self._total_latency += elapsed

        # Build fused output
        fused: Dict[str, Any] = {
            "task": description,
            "subtask_count": len(subtasks),
            "agent_results": [
                {
                    "agent_id": r.agent_id,
                    "success": r.success,
                    "output": r.output if r.success else None,
                    "error": r.error,
                }
                for r in results
            ],
            "verification": (
                verification_result.output if verification_result and verification_result.success
                else None
            ),
            "all_succeeded": all(r.success for r in results),
            "latency_ms": elapsed * 1000,
        }

        return fused

    def what_can_do(self) -> Dict[str, Any]:
        """Query what ORION can do — all registered capabilities."""
        return {
            "agents": self.list_agents(),
            "skills": self._skill_registry.to_dict() if self._skill_registry else {"skill_count": 0},
            "tools": (
                {"tool_count": len(self._tool_registry.list_tools()),
                 "tools": [t.name for t in self._tool_registry.list_tools()]}
                if self._tool_registry else {"tool_count": 0}
            ),
        }

    def what_cannot_do(self) -> Dict[str, Any]:
        """Query what ORION cannot do — missing capabilities."""
        all_roles = set(AgentRole)
        registered_roles = set(self._specialist_agents.keys())
        missing = all_roles - registered_roles
        return {
            "missing_agent_roles": [r.value for r in missing],
            "physical_tools_blocked": True,
            "forbidden_tools": True,
        }

    def what_tool_required(self, capability: str) -> Dict[str, Any]:
        """Query what tool is required for a capability."""
        role = _CAPABILITY_ROLE_MAP.get(capability)
        if not role:
            return {"capability": capability, "found": False, "tools": [], "permissions": []}

        agent = self._specialist_agents.get(role)
        if not agent:
            return {"capability": capability, "found": False, "tools": [], "permissions": []}

        desc = agent.get_descriptor()
        return {
            "capability": capability,
            "found": True,
            "agent": desc.name,
            "role": role.value,
            "tools": desc.tools,
            "permissions": desc.permissions,
        }

    def what_permission_required(self, capability: str) -> Dict[str, Any]:
        """Query what permission is required for a capability."""
        tool_info = self.what_tool_required(capability)
        return {
            "capability": capability,
            "permissions": tool_info.get("permissions", []),
            "safety_level": (
                self._specialist_agents.get(
                    _CAPABILITY_ROLE_MAP.get(capability, AgentRole.RESEARCH)
                ).get_descriptor().safety_level
                if _CAPABILITY_ROLE_MAP.get(capability) in self._specialist_agents
                else "SC_3"
            ),
        }

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "avg_latency_ms": self._total_latency / max(1, self._call_count),
            "agent_count": len(self._specialist_agents),
            "verification_stats": self._verification_agent.get_statistics(),
        }

    def _infer_capabilities(self, description: str) -> List[str]:
        """Infer required capabilities from task description."""
        desc_lower = description.lower()
        found: List[str] = []
        for cap, keywords in _CAPABILITY_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                if cap not in found:
                    found.append(cap)
        return found if found else ["analysis"]  # default to analysis
