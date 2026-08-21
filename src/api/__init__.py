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
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.api.auth import AuthConfig, AuthManager, get_auth_manager
from src.api.permissions import Permission, PermissionChecker, PermissionLevel, get_permission_checker

__all__ = [
    'AuthConfig', 'AuthManager', 'get_auth_manager',
    'Permission', 'PermissionChecker', 'PermissionLevel', 'get_permission_checker',
    'validate_input', 'sanitize_string', 'validate_api_payload',
]

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
# Validation Helpers
# ============================================================================

def validate_input(data: Any) -> bool:
    """Validate input data — non-None and non-empty."""
    if data is None:
        return False
    if isinstance(data, str) and not data.strip():
        return False
    return True


def sanitize_string(val: str) -> str:
    """Sanitize string input by stripping whitespace."""
    if not isinstance(val, str):
        return ""
    return val.strip()


def validate_api_payload(payload: Dict[str, Any]) -> bool:
    """Validate API payload structure — must be a non-empty dict."""
    if not isinstance(payload, dict):
        return False
    if len(payload) == 0:
        return False
    return True


def validate_string_param(value: Any, max_length: int = 10000) -> bool:
    """Validate a string parameter using InputValidator."""
    from src.api.validation import InputValidator
    result = InputValidator.validate_string(value, max_length=max_length)
    return result.valid


def validate_domain_param(domain: Any) -> bool:
    """Validate a domain parameter using InputValidator."""
    from src.api.validation import InputValidator
    result = InputValidator.validate_domain(domain)
    return result.valid


def validate_goal_param(goal: Any) -> bool:
    """Validate a goal parameter using InputValidator."""
    from src.api.validation import InputValidator
    result = InputValidator.validate_goal(goal)
    return result.valid


def validate_action_param(action: Any) -> bool:
    """Validate an action parameter using InputValidator."""
    from src.api.validation import InputValidator
    result = InputValidator.validate_action(action)
    return result.valid


# ============================================================================
# Server-Side Action Classification (Luna Round 5, Change #1)
# ============================================================================

# Known physical action types that ALWAYS require device_id + Safety Gateway.
# The server classifies these as PHYSICAL regardless of caller's declared category.
# Any action_type matching these patterns cannot be downgraded to DIGITAL.
PHYSICAL_ACTION_TYPES = frozenset({
    # Vehicle domain
    "move", "drive", "accelerate", "brake", "steer", "turn", "stop_vehicle",
    "emergency_stop", "reset_emergency", "park", "reverse", "lane_change",
    # Drone domain
    "takeoff", "land", "fly", "hover", "return_to_base", "set_waypoints",
    "emergency_land", "set_altitude",
    # Home domain
    "lock", "unlock", "set_temperature", "set_hvac_mode", "set_brightness",
    "trigger_fire_emergency", "trigger_intrusion", "clear_emergency",
    "set_thermostat",
    # Industrial domain
    "set_motor_speed", "set_pressure", "set_valve", "emergency_shutdown",
    "set_conveyor_speed", "open_valve", "close_valve", "activate_actuator",
    # General physical
    "activate_motor", "move_robot", "set_position", "set_velocity",
    "set_force", "set_torque", "engage", "disengage",
})

# Action types that are inherently DIGITAL (read-only, no physical effect)
DIGITAL_ACTION_TYPES = frozenset({
    "observe", "get_world_state", "recall", "remember", "query", "search",
    "list", "get", "read", "status", "diagnose", "report", "analyze",
    "evaluate", "benchmark", "test_connection", "ping",
})


def _classify_action_server_side(action: Dict[str, Any]) -> str:
    """Authoritative server-side action classification.

    Returns: 'PHYSICAL', 'DIGITAL', 'FINANCIAL', 'LEGAL', 'STRATEGIC'
    Rules:
    1. If device_id present → PHYSICAL (always, no override)
    2. If action_type in PHYSICAL_ACTION_TYPES → PHYSICAL (regardless of caller)
    3. If action_type in DIGITAL_ACTION_TYPES → DIGITAL (if caller agrees)
    4. If caller declared FINANCIAL/LEGAL/STRATEGIC → that category (requires Founder approval)
    5. Otherwise → DIGITAL only if caller also says DIGITAL (no server-side upgrade)
    """
    # Check multiple possible field names for the action type
    action_type = str(
        action.get("action_type") or action.get("command_type") or action.get("command") or ""
    ).lower().strip()
    has_device_id = bool(action.get("device_id"))
    caller_cat = str(action.get("action_category", "")).upper().strip()

    # Rule 1: device_id → always PHYSICAL
    if has_device_id:
        return "PHYSICAL"

    # Rule 2: known physical action type → PHYSICAL regardless of caller
    if action_type in PHYSICAL_ACTION_TYPES:
        return "PHYSICAL"

    # Rule 4: elevated categories require Founder approval
    if caller_cat in ("FINANCIAL", "LEGAL", "STRATEGIC"):
        return caller_cat

    # Rule 3: known digital action type
    if action_type in DIGITAL_ACTION_TYPES:
        return "DIGITAL"

    # Rule 5: unknown action type — caller must say DIGITAL, but we don't upgrade
    return "DIGITAL" if caller_cat == "DIGITAL" else "UNKNOWN"


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
        if not agent_id:
            return ORIONResponse(
                status=ORIONStatus.UNAUTHORIZED,
                error="agent_id is required for permission check",
            )
        if action is not None:
            if not self._permissions.check_permission(agent_id, action):
                return ORIONResponse(
                    status=ORIONStatus.UNAUTHORIZED,
                    error=f"Agent '{agent_id}' does not have permission for action '{action}'",
                )
        return ORIONResponse(status=ORIONStatus.OK)

    # --- Observation ---
    def observe(
        self,
        source: str,
        query: Dict[str, Any],
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> ORIONResponse:
        """Observe a digital or physical environment."""
        auth = self._check_auth(token, agent_id=agent_id, action="observe")
        if not auth.ok:
            return auth
        if not validate_string_param(source) or not validate_api_payload(query):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid input parameters — source must be non-empty string, query must be non-empty dict")
        # TODO: Connect to perception plane
        return ORIONResponse(status=ORIONStatus.OK, data={"source": source, "query": query})

    # --- World State ---
    def get_world_state(
        self,
        domain: Optional[str] = None,
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> ORIONResponse:
        """Get current world state."""
        auth = self._check_auth(token, agent_id=agent_id, action="get_world_state")
        if not auth.ok:
            return auth
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
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> ORIONResponse:
        """Recall memories matching a query."""
        auth = self._check_auth(token, agent_id=agent_id, action="recall")
        if not auth.ok:
            return auth
        if not validate_string_param(query):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid query — must be non-empty string")
        if not isinstance(limit, int) or limit <= 0:
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid limit — must be positive integer")
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
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> ORIONResponse:
        """Store a new memory."""
        auth = self._check_auth(token, agent_id=agent_id, action="remember")
        if not auth.ok:
            return auth
        if not validate_input(content) or (isinstance(content, str) and not content.strip()):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid content — must be non-empty")
        if self._memory:
            try:
                # Forward verified authorization context from the auth check
                actor_perms = getattr(auth, 'permissions', None) or ["READ"]
                if hasattr(self._memory, 'write_memory'):
                    entry = self._memory.write_memory(
                        content=content, memory_type=memory_type, metadata=metadata,
                        actor_permissions=actor_perms
                    )
                else:
                    entry = self._memory.store(content, memory_type=memory_type, metadata=metadata)
                return ORIONResponse(status=ORIONStatus.OK, data=entry)
            except Exception as e:
                return ORIONResponse(status=ORIONStatus.ERROR, error=str(e))
        return ORIONResponse(status=ORIONStatus.OK, data={"stored": False})

    # --- Planning ---
    def plan(
        self,
        goal: str,
        constraints: Optional[Dict] = None,
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> ORIONResponse:
        """Generate a plan for a goal."""
        auth = self._check_auth(token, agent_id=agent_id, action="plan")
        if not auth.ok:
            return auth
        if not validate_goal_param(goal):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid goal — must be non-empty string, max 10000 chars")
        if constraints is not None and not validate_api_payload(constraints):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid constraints parameter")
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
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> ORIONResponse:
        """Simulate an action before executing it."""
        auth = self._check_auth(token, agent_id=agent_id, action="simulate")
        if not auth.ok:
            return auth
        if not validate_api_payload(action):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid action — must be non-empty dict")
        if not validate_domain_param(domain):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid domain — must be known domain string")
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
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> ORIONResponse:
        """Execute an action (optionally simulate first)."""
        auth = self._check_auth(token, agent_id=agent_id, action="execute")
        if not auth.ok:
            return auth

        if not validate_api_payload(action):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid action payload — must be non-empty dict")
        if not validate_domain_param(domain):
            return ORIONResponse(status=ORIONStatus.ERROR, error="Invalid domain — must be known domain string")

        # Vector #4: Validate device_id — strict format validation if present
        import re
        raw_device_id = action.get("device_id")
        if raw_device_id is not None:
            if not isinstance(raw_device_id, str) or not raw_device_id.strip():
                return ORIONResponse(
                    status=ORIONStatus.ERROR,
                    error="Invalid device_id — must be a non-empty string",
                )
            stripped = raw_device_id.strip()
            # Reject path traversal characters and enforce alphanumeric + _ - . format
            # Max 128 chars to prevent buffer attacks
            if not re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_\-.]{0,127}$', stripped):
                return ORIONResponse(
                    status=ORIONStatus.ERROR,
                    error="Invalid device_id — must be alphanumeric/underscore/hyphen/dot, max 128 chars, no path traversal",
                )
            action["device_id"] = stripped

        # Vector #10: action_category is REQUIRED — no default. Prevents omitting category to bypass elevated authorization.
        # Action category enforcement — SERVER-SIDE classification, not caller-supplied
        # The caller's action_category is cross-validated against actual action properties.
        # If device_id is present, the action is PHYSICAL regardless of caller declaration.
        caller_cat = action.get("action_category")
        if caller_cat is None:
            return ORIONResponse(
                status=ORIONStatus.UNAUTHORIZED,
                error="action_category is required — cannot be omitted (prevents category bypass attack)",
            )
        if hasattr(caller_cat, "value"):
            caller_cat = caller_cat.value

        if not isinstance(caller_cat, str):
            return ORIONResponse(
                status=ORIONStatus.UNAUTHORIZED,
                error="Invalid action_category: must be a string",
            )

        caller_cat = caller_cat.strip().upper()
        valid_categories = {"DIGITAL", "FINANCIAL", "LEGAL", "PHYSICAL", "STRATEGIC"}
        if not caller_cat or caller_cat not in valid_categories:
            return ORIONResponse(
                status=ORIONStatus.UNAUTHORIZED,
                error=f"Invalid action_category: '{caller_cat}' is not a valid category",
            )

        # Change #1 + #2: AUTHORITATIVE SERVER-SIDE ACTION CLASSIFICATION
        # The server classifies the action independently — the caller's declared
        # category is cross-validated but NOT trusted as authoritative.
        server_cat = _classify_action_server_side(action)

        # Cross-validate: if server says PHYSICAL but caller said something else, reject
        if server_cat == "PHYSICAL":
            if caller_cat != "PHYSICAL":
                return ORIONResponse(
                    status=ORIONStatus.UNAUTHORIZED,
                    error=f"SERVER-SIDE CLASSIFICATION MISMATCH: action_type '{action.get('action_type', '?')}' "
                          f"is classified as PHYSICAL by server, but caller declared '{caller_cat}' — "
                          f"downgrade attempt blocked",
                )
            # PHYSICAL requires device_id
            if not action.get("device_id"):
                return ORIONResponse(
                    status=ORIONStatus.UNAUTHORIZED,
                    error="PHYSICAL action requires device_id — cannot execute without hardware safety enforcement",
                )
            norm_cat = "PHYSICAL"
        elif server_cat == "UNKNOWN":
            return ORIONResponse(
                status=ORIONStatus.UNAUTHORIZED,
                error=f"Cannot classify action_type '{action.get('action_type', '?')}' — "
                      f"not in known physical or digital action registry. Deny by default.",
            )
        else:
            # Server says DIGITAL/FINANCIAL/LEGAL/STRATEGIC — cross-validate with caller
            if caller_cat != server_cat:
                # If server says FINANCIAL/LEGAL/STRATEGIC but caller says DIGITAL, block
                if server_cat in ("FINANCIAL", "LEGAL", "STRATEGIC") and caller_cat == "DIGITAL":
                    return ORIONResponse(
                        status=ORIONStatus.UNAUTHORIZED,
                        error=f"SERVER-SIDE CLASSIFICATION MISMATCH: action classified as {server_cat} "
                              f"by server, but caller declared '{caller_cat}' — downgrade blocked",
                    )
                # If caller says PHYSICAL but server says DIGITAL, that's an upgrade attempt
                if caller_cat == "PHYSICAL" and server_cat == "DIGITAL":
                    return ORIONResponse(
                        status=ORIONStatus.UNAUTHORIZED,
                        error="Cannot upgrade DIGITAL action to PHYSICAL — no device_id and action_type is digital",
                    )
            norm_cat = server_cat

        if norm_cat in ("FINANCIAL", "LEGAL", "STRATEGIC"):
            return ORIONResponse(
                status=ORIONStatus.UNAUTHORIZED,
                error=f"DECISION_REQUIRED: {norm_cat} action requires Founder approval",
            )

        # PHYSICAL actions MUST go through Safety Gateway and HAL
        if norm_cat == "PHYSICAL":
            if not action.get("device_id"):
                return ORIONResponse(
                    status=ORIONStatus.UNAUTHORIZED,
                    error="PHYSICAL action requires device_id — cannot execute without hardware safety enforcement",
                )
            if not self._safety:
                return ORIONResponse(
                    status=ORIONStatus.UNAUTHORIZED,
                    error="No Safety Gateway configured — PHYSICAL actions denied by default",
                )
            if not self._hal:
                return ORIONResponse(
                    status=ORIONStatus.UNAUTHORIZED,
                    error="No HAL configured — PHYSICAL actions denied by default",
                )

        if simulate_first:
            sim = self.simulate(action, domain, token=token, agent_id=agent_id)
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

        # Non-hardware DIGITAL action — log and confirm
        return ORIONResponse(status=ORIONStatus.OK, data={"executed": True, "category": norm_cat})

    # --- Emergency ---
    def emergency_stop(
        self,
        domain: Optional[str] = None,
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> ORIONResponse:
        """Trigger an emergency stop."""
        auth = self._check_auth(token, agent_id=agent_id, action="emergency_stop")
        if not auth.ok:
            return auth
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
