# ORION Core Architecture — Phase 004

**License: Apache 2.0**

## Overview

ORION Core is the central reasoning, planning, execution, and audit engine.
It implements the lifecycle: GOAL → PLAN → EXECUTE → OBSERVE → EVALUATE → CORRECT → REMEMBER.

Key principle (Luna Phase 004 spec): ORION Core is a **deterministic control plane
around probabilistic models**. Models may propose; only validated, authorized,
policy-approved actions may execute.

## 12 Core Components

| # | Component | Module | Responsibility |
|---|-----------|--------|----------------|
| 1 | Supervisor | `src/core/supervisor.py` | Receives goals, coordinates lifecycle |
| 2 | Task Engine | `src/core/task_engine.py` | Task lifecycle, steps, dependencies, retry, cancel, resume |
| 3 | Planner | `src/core/model_gateway.py` | Goal → structured plan via model gateway |
| 4 | Permission Engine | `src/core/policy_engine.py` | Least privilege, read/write/irreversible separation |
| 5 | Policy Engine | `src/core/policy_engine.py` | Deterministic decisions, deny-by-default |
| 6 | Execution Engine | `src/core/execution_engine.py` | Validated tool invocation, timeouts, sandboxing |
| 7 | Tool Registry | `src/core/tool_registry.py` | Schemas, permissions, risk levels, rollback |
| 8 | Agent Registry | TBD | Specialist agents, health, invocation contracts |
| 9 | Audit Logger | `src/core/audit_logger.py` | Tamper-evident, correlation IDs, full lifecycle |
| 10 | Error Recovery | `src/core/error_recovery.py` | Bounded retries, alternate plans, escalation |
| 11 | State Manager | `src/core/task_engine.py` | Crash recovery, deterministic reconstruction |
| 12 | Model Gateway | `src/core/model_gateway.py` | Model-independent interface for reasoning |

## Lifecycle

```
GOAL
  ↓
[Supervisor] creates Task in TaskEngine
  ↓
[ModelGateway] generates plan (structured JSON)
  ↓
[PolicyEngine] validates plan (deny-by-default)
  ↓
[TaskEngine] creates TaskSteps from plan
  ↓
[ExecutionEngine] executes steps in dependency order
  ↓
[ErrorRecovery] handles failures (retry → skip → escalate)
  ↓
[AuditLogger] records all events with hash chain
  ↓
COMPLETED / FAILED / CANCELLED
```

## Safety Constraints

- **Deny-by-default**: Unknown tools and unmatched policy rules are denied
- **Physical tools blocked**: All `ToolCategory.PHYSICAL` tools rejected in Phase 004
- **Forbidden risk level**: `ToolRiskLevel.FORBIDDEN` tools cannot be registered
- **High-risk requires approval**: MEDIUM/HIGH/CRITICAL tools require explicit approval
- **Tamper-evident audit**: SHA-256 hash chain detects any modification of past events
- **Idempotency**: Tasks with the same idempotency key are not duplicated
- **Bounded retries**: Steps have configurable max_retries; exhaustion triggers escalation

## Integration with Existing Modules

- `src/runtime/supervisor.py` — 24/7 runtime manager (wraps Core Supervisor)
- `src/planning/__init__.py` — Autonomous planner (integrated via Model Gateway)
- `src/safety/safety_enforcement.py` — Physical safety enforcement (not invoked in Phase 004)
- `src/contracts/contracts.py` — Normative data contracts (used by audit logger)
- `src/audit/audit_system.py` — Existing audit system (extended by Core Audit Logger)
- `src/api/permissions.py` — Permission system (integrated via Policy Engine)

## Testing

48 tests in `tests/unit/test_phase004.py` covering all components:
- TaskEngine: 11 tests (lifecycle, idempotency, dependencies, retry, cancel, pause, resume)
- ToolRegistry: 8 tests (registration, validation, blocking, listing)
- PolicyEngine: 7 tests (deny-by-default, deterministic, risk levels)
- ExecutionEngine: 5 tests (policy enforcement, timeout, validation, rollback)
- ModelGateway: 5 tests (registration, fallback, JSON parsing)
- ErrorRecovery: 3 tests (retry, skip, escalate)
- AuditLogger: 6 tests (hash chain, tamper detection, filtering)
- CoreSupervisor: 3 tests (full lifecycle, audit trail, policy enforcement)
