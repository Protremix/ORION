# ORION Core Interface Definitions (Phase 004)

**Document Status:** PROPOSED  
**Phase:** Phase 004 (ORION Core Baseline)  
**License:** Apache 2.0  

This document defines the normative Python `Protocol` interfaces for the 12 core components of ORION Phase 004. These interfaces enforce deterministic safety, policy, permission, and execution controls around probabilistic language models.

---

## Python Interface Specifications

```python
# Copyright 2026 ORION Project Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""ORION Core Component Protocol Interfaces (Phase 004)."""

from typing import Any, Dict, List, Optional, Protocol, Type, runtime_checkable
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Canonical Data Models (Interface Type Dependencies)
# ---------------------------------------------------------------------------

class Goal(BaseModel):
    """High-level goal or objective submitted to Supervisor."""
    goal_id: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    """Single step in a task execution plan."""
    step_id: str
    description: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    status: str = "PENDING"


class Plan(BaseModel):
    """Structured plan containing ordered steps."""
    plan_id: str
    task_id: str
    steps: List[PlanStep] = Field(default_factory=list)


class Task(BaseModel):
    """Task lifecycle record."""
    task_id: str
    goal: Goal
    state: str = "CREATED"
    plan: Optional[Plan] = None


class ActionRequest(BaseModel):
    """Request to execute a digital action or tool."""
    action_id: str
    task_id: str
    step_id: str
    tool_name: str
    arguments: Dict[str, Any]


class ToolManifest(BaseModel):
    """Metadata specification for a registered tool."""
    name: str
    description: str
    schema: Dict[str, Any]
    risk_level: str = "LOW"
    requires_approval: bool = False


class AgentManifest(BaseModel):
    """Metadata specification for a specialist agent adapter."""
    agent_id: str
    name: str
    capabilities: List[str]


class PermissionRequest(BaseModel):
    """Permission evaluation request."""
    task_id: str
    action: str
    scope: str


class PermissionDecision(BaseModel):
    """Result of permission evaluation."""
    allowed: bool
    requires_approval: bool = False
    reason: str = ""


class PolicyDecision(BaseModel):
    """Result of policy enforcement check."""
    allowed: bool
    reason: str = ""


class TaskResult(BaseModel):
    """Outcome of action or task execution."""
    success: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class AuditRecord(BaseModel):
    """Immutable audit trail log record."""
    event_id: str
    task_id: str
    event_type: str
    details: Dict[str, Any]
    timestamp: float


class ModelResponse(BaseModel):
    """Model gateway response container."""
    raw_text: str
    parsed: Optional[Any] = None


class RecoveryDecision(BaseModel):
    """Directive issued by ErrorRecovery module."""
    action: str  # "RETRY", "REPLAN", "ESCALATE"
    delay_seconds: float = 0.0


class PlanValidationResult(BaseModel):
    """Outcome of plan validation check."""
    valid: bool
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 004 Core Component Protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class SupervisorInterface(Protocol):
    """Coordinates the GOAL -> PLAN -> EXECUTE -> OBSERVE -> EVALUATE -> CORRECT -> REMEMBER lifecycle."""

    async def submit_goal(self, goal: Goal) -> Task:
        """Submit a new goal for autonomous execution."""
        ...

    async def run_task(self, task_id: str) -> TaskResult:
        """Execute the task lifecycle end-to-end without mid-execution prompting."""
        ...

    async def get_task_status(self, task_id: str) -> Task:
        """Query current state and progress of a task."""
        ...

    async def cancel_task(self, task_id: str, reason: str) -> bool:
        """Cancel an in-flight task execution."""
        ...


@runtime_checkable
class TaskEngineInterface(Protocol):
    """Manages task state transitions, step tracking, timeouts, and idempotency."""

    async def create_task(self, goal: Goal) -> Task:
        """Initialize a new task lifecycle record."""
        ...

    async def transition_state(self, task_id: str, new_state: str) -> Task:
        """Transition task state according to state machine rules."""
        ...

    async def update_step(self, task_id: str, step_id: str, status: str, result: Optional[Any] = None) -> PlanStep:
        """Update step state and execution outcome."""
        ...

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task by unique identifier."""
        ...


@runtime_checkable
class PlannerInterface(Protocol):
    """Converts high-level goals into structured plans with dependency and risk metadata."""

    async def create_plan(self, goal: Goal, available_tools: List[ToolManifest]) -> Plan:
        """Decompose goal into ordered steps with tool assignments."""
        ...

    async def validate_plan(self, plan: Plan) -> PlanValidationResult:
        """Validate plan safety, dependency ordering, and schema compliance."""
        ...

    async def replan(self, task: Task, failure_context: Dict[str, Any]) -> Plan:
        """Generate an alternate plan following step or tool failure."""
        ...


@runtime_checkable
class PermissionEngineInterface(Protocol):
    """Enforces least privilege, scope restrictions, and explicit approval gating."""

    async def evaluate_permission(self, request: PermissionRequest) -> PermissionDecision:
        """Determine whether requested operation is allowed under active grants."""
        ...

    async def grant_approval(self, approval_id: str, granted_by: str) -> bool:
        """Record explicit approval for an approval-gated action."""
        ...

    async def revoke_permission(self, scope: str) -> bool:
        """Revoke a permission grant scope."""
        ...


@runtime_checkable
class PolicyEngineInterface(Protocol):
    """Enforces deterministic safety, security, privacy, and resource policies."""

    async def evaluate_policy(self, action: ActionRequest) -> PolicyDecision:
        """Evaluate action against deterministic policy rules (deny physical/unknown actions)."""
        ...

    async def validate_tool_args(self, tool_name: str, args: Dict[str, Any]) -> PolicyDecision:
        """Validate tool invocation arguments against registered parameter constraints."""
        ...


@runtime_checkable
class ExecutionEngineInterface(Protocol):
    """Invokes registered tools in sandboxed environments with timeouts and resource quotas."""

    async def execute_action(self, action: ActionRequest) -> TaskResult:
        """Invoke a tool action and return structured output."""
        ...

    async def cancel_execution(self, action_id: str) -> bool:
        """Cancel an active in-flight action execution."""
        ...


@runtime_checkable
class ToolRegistryInterface(Protocol):
    """Maintains registered tools, parameter schemas, risk levels, and rollback behavior."""

    def register_tool(self, manifest: ToolManifest) -> None:
        """Register a new tool and its metadata specification."""
        ...

    def get_tool(self, tool_name: str) -> Optional[ToolManifest]:
        """Retrieve manifest for a registered tool."""
        ...

    def list_tools(self, capability: Optional[str] = None) -> List[ToolManifest]:
        """List registered tools matching optional capability filter."""
        ...


@runtime_checkable
class AgentRegistryInterface(Protocol):
    """Registers specialist agent adapters, invocation contracts, and health state."""

    def register_agent(self, manifest: AgentManifest) -> None:
        """Register a specialist agent adapter."""
        ...

    def get_agent(self, agent_id: str) -> Optional[AgentManifest]:
        """Retrieve manifest for a registered agent."""
        ...

    async def check_health(self, agent_id: str) -> Dict[str, Any]:
        """Check operational readiness and health of an agent adapter."""
        ...


@runtime_checkable
class AuditLoggerInterface(Protocol):
    """Records tamper-evident, correlated audit logs for all lifecycle events."""

    async def log_event(self, record: AuditRecord) -> str:
        """Write an append-only audit event record and return event hash."""
        ...

    async def get_task_audit_trail(self, task_id: str) -> List[AuditRecord]:
        """Retrieve complete correlated audit trail for a task."""
        ...

    async def verify_chain_integrity(self) -> bool:
        """Verify cryptographic hash chain integrity of the audit log."""
        ...


@runtime_checkable
class ModelGatewayInterface(Protocol):
    """Provides provider-agnostic model integration, prompt routing, and output parsing."""

    async def generate(self, prompt: str, model_tier: str = "7b", schema: Optional[Type[BaseModel]] = None) -> ModelResponse:
        """Send prompt to reasoning model and return response."""
        ...

    async def parse_output(self, raw_text: str, target_schema: Type[BaseModel]) -> BaseModel:
        """Parse and validate raw model text against target Pydantic schema."""
        ...


@runtime_checkable
class StateManagerInterface(Protocol):
    """Persists task and step states to support crash recovery and deterministic reconstruction."""

    async def save_state(self, task_id: str, state: Task) -> None:
        """Save current task state and context to persistent store."""
        ...

    async def load_state(self, task_id: str) -> Optional[Task]:
        """Load task state from persistent store."""
        ...

    async def recover_active_tasks(self) -> List[Task]:
        """Discover uncompleted tasks following process restart."""
        ...


@runtime_checkable
class ErrorRecoveryInterface(Protocol):
    """Classifies execution errors and determines bounded retry, replan, or escalation paths."""

    async def handle_failure(self, task: Task, step: PlanStep, error: Exception) -> RecoveryDecision:
        """Analyze failure and prescribe recovery strategy (retry, replan, escalate)."""
        ...

    async def classify_error(self, error: Exception) -> str:
        """Classify exception into standardized error category."""
        ...
```
