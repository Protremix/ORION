"""ORION Data Contracts Package.

Exposes all 9 normative data contracts, base contract, and common enums.
"""

from src.contracts.contracts import (
    ActionAuthorization,
    ActionExecutionResult,
    ActionProposal,
    AuditEvent,
    AuditEventType,
    AuthorityScope,
    BaseContract,
    BeliefState,
    DecisionType,
    ExecutionOutcome,
    ExecutionStage,
    Goal,
    GoalPriority,
    GoalSource,
    GoalType,
    MemoryType,
    MemoryWrite,
    Observation,
    Plane,
    RiskTier,
    SafetyDecision,
    SeverityLevel,
    current_timestamp_ns,
    current_wall_clock_ms,
    generate_contract_id,
)

__all__ = [
    "BaseContract",
    "Observation",
    "BeliefState",
    "Goal",
    "ActionProposal",
    "ActionAuthorization",
    "ActionExecutionResult",
    "SafetyDecision",
    "AuditEvent",
    "MemoryWrite",
    "Plane",
    "GoalType",
    "GoalPriority",
    "RiskTier",
    "ExecutionOutcome",
    "ExecutionStage",
    "DecisionType",
    "AuthorityScope",
    "SeverityLevel",
    "AuditEventType",
    "MemoryType",
    "generate_contract_id",
    "current_timestamp_ns",
    "current_wall_clock_ms",
]

# Compatibility aliases for modules that use alternative naming
Envelope = BaseContract  # Envelope = base contract wrapper
generate_uuid = generate_contract_id  # UUID generator alias
current_monotonic_ns = current_timestamp_ns  # Monotonic timestamp alias
ExecutionResultStatus = ExecutionOutcome  # Execution result status alias
