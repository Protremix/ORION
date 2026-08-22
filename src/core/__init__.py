"""
ORION Core — Phase 004: Central reasoning, planning, execution, and audit engine.

The Core implements the lifecycle:
    GOAL → PLAN → EXECUTE → OBSERVE → EVALUATE → CORRECT → REMEMBER

Key principle (Luna Phase 004 spec): ORION Core is a deterministic control plane
around probabilistic models. Models may propose
only validated, authorized,
policy-approved actions may execute.

Components:
    - Supervisor: Receives goals, coordinates lifecycle
    - TaskEngine: Task lifecycle, steps, dependencies, retry, cancel, resume
    - Planner: Goal → structured plan with validation
    - PermissionEngine: Least privilege, read/write/irreversible separation
    - PolicyEngine: Deterministic decisions, deny-by-default
    - ExecutionEngine: Validated tool invocation, timeouts, sandboxing
    - ToolRegistry: Schemas, permissions, risk levels, rollback
    - AgentRegistry: Specialist agents, health, invocation contracts
    - AuditLogger: Tamper-evident, correlation IDs, full lifecycle
    - ErrorRecovery: Bounded retries, alternate plans, escalation
    - StateManager: Crash recovery, deterministic reconstruction
    - ModelGateway: Model-independent interface for reasoning

License: Apache 2.0
"""
