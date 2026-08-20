"""
ORION API / SDK — Master Spec §12

Standardized interfaces for external interaction with ORION.

Interfaces:
    - ORION API: Programmatic access to ORION capabilities
    - ORION SDK: Python library for building on ORION
    - Agent Protocol: For specialized agents to communicate with ORION
    - Skill Interface: For modular skills
    - Tool Interface: For tools ORION can use
    - Hardware Interface: Via the HAL (src/hal/)
    - Simulation Interface: For simulation environments

License: Apache 2.0
"""

from __future__ import annotations

import abc
import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union, Protocol
from src.api.auth import AuthManager, AuthConfig, get_auth_manager
from src.api.permissions import PermissionLevel, Permission, PermissionChecker, get_permission_checker

logger = logging.getLogger(__name__)


# ============================================================================
# Common Types
# ============================================================================

class ORIONStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    PENDING = "pending"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"


@dataclass
class ORIONResponse:
    """Standard response wrapper for all ORION API calls."""
    status: ORIONStatus
    data: Any = None
    error: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == ORIONStatus.OK


# ============================================================================
# ORION API (§12)
# ============================================================================

class ORIONAPI:
    """
    ORION API — top-level programmatic interface.
    
    This is the main entry point for external systems to interact with ORION.
    All operations go through the Safety Gateway where applicable.
    """

    def __init__(
        self,
        safety_gateway: Optional[Any] = None,
        hal: Optional[Any] = None,
        memory: Optional[Any] = None,
        supervisor: Optional[Any] = None,
        auth_manager: Optional[AuthManager] = None,
        permission_checker: Optional[PermissionChecker] = None,
    ) -> None:
        self._safety = safety_gateway
        self._hal = hal
        self._memory = memory
        self._supervisor = supervisor
        self._auth = auth_manager or get_auth_manager()
        self._permissions = permission_checker or get_permission_checker()

    def _check_auth(
        self,
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> ORIONResponse:
        """Check authentication, permissions, and rate limit. Returns error response if failed."""
        if not self._auth.authenticate(token):
            return ORIONResponse(status=ORIONStatus.UNAUTHORIZED, error="Invalid or missing API key")
        if not self._auth.check_rate_limit(token):
            return ORIONResponse(status=ORIONStatus.RATE_LIMITED, error="Rate limit exceeded")
        if agent_id is not None and action is not None:
            if not self._permissions.check_permission(agent_id, action):
                return ORIONResponse(
                    status=ORIONStatus.UNAUTHORIZED,
                    error=f"Agent '{agent_id}' does not have permission for action '{action}'",
                )
        return ORIONResponse(status=ORIONStatus.OK)

    # --- Observation ---
    def observe(self, source: str, query: Dict[str, Any]) -> ORIONResponse:
        """Observe a digital or physical environment."""
        # TODO: Connect to perception plane
        return ORIONResponse(status=ORIONStatus.OK, data={"source": source, "query": query})

    # --- World State ---
    def get_world_state(self, domain: Optional[str] = None) -> ORIONResponse:
        """Get current world state."""
        if self._supervisor:
            try:
                state = self._supervisor.get_world_state(domain)
                return ORIONResponse(status=ORIONStatus.OK, data=state)
            except Exception as e:
                return ORIONResponse(status=ORIONStatus.ERROR, error=str(e))
        return ORIONResponse(status=ORIONStatus.OK, data={})

    # --- Memory ---
    def recall(
        self,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> ORIONResponse:
        """Recall memories matching a query."""
        if self._memory:
            try:
                results = self._memory.search(query, memory_type=memory_type, limit=limit)
                return ORIONResponse(status=ORIONStatus.OK, data=results)
            except Exception as e:
                return ORIONResponse(status=ORIONStatus.ERROR, error=str(e))
        return ORIONResponse(status=ORIONStatus.OK, data=[])

    def remember(
        self,
        content: Any,
        memory_type: str = "episodic",
        metadata: Optional[Dict] = None,
    ) -> ORIONResponse:
        """Store a new memory."""
        if self._memory:
            try:
                entry = self._memory.store(content, memory_type=memory_type, metadata=metadata)
                return ORIONResponse(status=ORIONStatus.OK, data=entry)
            except Exception as e:
                return ORIONResponse(status=ORIONStatus.ERROR, error=str(e))
        return ORIONResponse(status=ORIONStatus.OK, data={"stored": False})

    # --- Planning ---
    def plan(self, goal: str, constraints: Optional[Dict] = None) -> ORIONResponse:
        """Generate a plan for a goal."""
        # TODO: Connect to planning plane
        return ORIONResponse(
            status=ORIONStatus.OK,
            data={"goal": goal, "constraints": constraints, "plan": []},
        )

    # --- Simulation ---
    def simulate(
        self,
        action: Dict[str, Any],
        domain: str = "industrial",
    ) -> ORIONResponse:
        """Simulate an action before executing it."""
        # TODO: Connect to simulation plane
        return ORIONResponse(
            status=ORIONStatus.OK,
            data={"action": action, "domain": domain, "result": "simulated"},
        )

    # --- Action ---
    def execute(
        self,
        action: Dict[str, Any],
        domain: str = "industrial",
        simulate_first: bool = True,
    ) -> ORIONResponse:
        """Execute an action (optionally simulate first)."""
        if simulate_first:
            sim = self.simulate(action, domain)
            if not sim.ok:
                return sim

        # Safety Gateway check — required for any hardware action
        if action.get("device_id"):
            if self._safety:
                approved = self._safety.approve_action(
                    device_id=action.get("device_id", ""),
                    command_type=action.get("command_type", ""),
                    parameters=action.get("parameters", {}),
                    priority=action.get("priority", 0),
                )
                if not approved:
                    return ORIONResponse(
                        status=ORIONStatus.UNAUTHORIZED,
                        error="Action rejected by Safety Gateway",
                    )
            else:
                return ORIONResponse(
                    status=ORIONStatus.UNAUTHORIZED,
                    error="No Safety Gateway configured — hardware actions denied by default",
                )

        # Route through HAL if it's a hardware action
        if self._hal and action.get("device_id"):
            from src.hal import DeviceCommand
            cmd = DeviceCommand(
                device_id=action["device_id"],
                command_type=action.get("command_type", "execute"),
                parameters=action.get("parameters", {}),
                priority=action.get("priority", 0),
            )
            resp = self._hal.send_command(cmd)
            return ORIONResponse(
                status=ORIONStatus.OK if resp.success else ORIONStatus.ERROR,
                data=resp.data,
                error=resp.error,
            )

        return ORIONResponse(status=ORIONStatus.OK, data={"executed": True})

    # --- Emergency ---
    def emergency_stop(self, domain: Optional[str] = None) -> ORIONResponse:
        """Trigger an emergency stop."""
        if self._hal:
            if domain:
                # Stop specific domain devices
                results = {}
                for desc in self._hal.list_devices():
                    if desc.device_type.value == domain or domain in desc.metadata.get("domain", ""):
                        results[desc.device_id] = self._hal.get_device(desc.device_id).emergency_stop()
            else:
                results = self._hal.emergency_stop_all()
            return ORIONResponse(status=ORIONStatus.OK, data=results)
        return ORIONResponse(status=ORIONStatus.OK, data={"estop": "no_hardware"})


# ============================================================================
# Agent Protocol (§12, §15)
# ============================================================================

class AgentRole(str, Enum):
    RESEARCH = "research"
    ENGINEERING = "engineering"
    ML = "ml"
    VISION = "vision"
    WORLD_MODEL = "world_model"
    MEMORY = "memory"
    SIMULATION = "simulation"
    DATA = "data"
    EVALUATION = "evaluation"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    HARDWARE = "hardware"
    CODING = "coding"
    BROWSER = "browser"
    ROBOTICS = "robotics"
    AUTOMOTIVE = "automotive"
    DRONE = "drone"
    HOME = "home"
    INDUSTRIAL = "industrial"


@dataclass
class AgentDescriptor:
    """Describes a specialized agent in the ORION system."""
    agent_id: str
    name: str
    role: AgentRole
    capabilities: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    domain: Optional[str] = None
    safety_level: str = "SC_3"
    max_concurrent_tasks: int = 1
    timeout_seconds: float = 300.0


@dataclass
class AgentTask:
    """A task assigned to an agent."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    task_type: str = ""
    description: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    deadline: Optional[float] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class AgentResult:
    """Result from an agent task."""
    task_id: str
    agent_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentProtocol(abc.ABC):
    """
    Protocol for specialized agents — Master Spec §15.
    
    Each agent must have explicit capabilities, permissions, tools, logging, and evaluation.
    """

    @abc.abstractmethod
    def get_descriptor(self) -> AgentDescriptor:
        """Return this agent's descriptor."""
        ...

    @abc.abstractmethod
    def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a task and return the result."""
        ...

    @abc.abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of capabilities this agent supports."""
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Check if this agent is healthy and ready."""
        ...


# ============================================================================
# Skill Interface (§12, §15)
# ============================================================================

@dataclass
class SkillDescriptor:
    """Describes a modular skill in ORION."""
    skill_id: str
    name: str
    description: str
    version: str = "0.1.0"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    domain: Optional[str] = None
    safety_level: str = "SC_3"
    requires_hardware: bool = False
    requires_simulation: bool = False


class SkillInterface(abc.ABC):
    """
    Interface for modular skills — Master Spec §15.
    Skills should be modular and replaceable.
    """

    @abc.abstractmethod
    def get_descriptor(self) -> SkillDescriptor:
        """Return this skill's descriptor."""
        ...

    @abc.abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the skill and return output."""
        ...

    @abc.abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input against the skill's input schema."""
        ...


# ============================================================================
# Tool Interface (§12)
# ============================================================================

@dataclass
class ToolDescriptor:
    """Describes a tool ORION can use."""
    tool_id: str
    name: str
    description: str
    tool_type: str  # "api", "cli", "library", "hardware", "simulation"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    requires_auth: bool = False
    safety_level: str = "SC_3"


class ToolInterface(abc.ABC):
    """Interface for tools ORION can use — Master Spec §12."""

    @abc.abstractmethod
    def get_descriptor(self) -> ToolDescriptor:
        """Return this tool's descriptor."""
        ...

    @abc.abstractmethod
    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the tool and return the result."""
        ...

    @abc.abstractmethod
    def validate_permissions(self) -> bool:
        """Check if the tool has the required permissions."""
        ...


# ============================================================================
# Simulation Interface (§12, §10)
# ============================================================================

@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""
    domain: str = "industrial"
    duration_seconds: float = 60.0
    time_step: float = 0.1
    initial_state: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    safety_checks: bool = True
    record_trace: bool = True


@dataclass
class SimulationResult:
    """Result of a simulation run."""
    success: bool
    final_state: Dict[str, Any] = field(default_factory=dict)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    safety_events: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SimulationInterface(abc.ABC):
    """
    Interface for simulation environments — Master Spec §10, §12.
    Simulation-first approach for all physical tasks.
    """

    @abc.abstractmethod
    def configure(self, config: SimulationConfig) -> bool:
        """Configure the simulation."""
        ...

    @abc.abstractmethod
    def run(self, actions: List[Dict[str, Any]]) -> SimulationResult:
        """Run the simulation with a list of actions."""
        ...

    @abc.abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get current simulation state."""
        ...

    @abc.abstractmethod
    def reset(self) -> bool:
        """Reset the simulation to initial state."""
        ...


# ============================================================================
# Model Adapter (§12 — Models should be replaceable through adapters)
# ============================================================================

class ModelType(str, Enum):
    LLM = "llm"
    VISION = "vision"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    WORLD_MODEL = "world_model"
    EMBEDDING = "embedding"


@dataclass
class ModelDescriptor:
    """Describes an AI model adapter."""
    model_id: str
    name: str
    model_type: ModelType
    provider: str = "unknown"
    version: str = "0.1.0"
    max_tokens: int = 4096
    supports_streaming: bool = False
    requires_api_key: bool = True
    cost_per_1k_tokens: float = 0.0
    latency_ms: float = 0.0


class ModelAdapter(abc.ABC):
    """
    Model adapter — Master Spec §12.
    Models should be replaceable through adapters.
    """

    @abc.abstractmethod
    def get_descriptor(self) -> ModelDescriptor:
        """Return model descriptor."""
        ...

    @abc.abstractmethod
    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the model and return output."""
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Check if the model is available and responsive."""
        ...
