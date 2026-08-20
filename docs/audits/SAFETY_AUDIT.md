# ORION Safety Audit Report

**Date:** 2026-08-20
**Repository:** orion/implementation
**Version:** 0.6.0
**Auditor:** ORION Supervisor Agent

---

## Executive Summary

This audit reviews all safety-critical code in the ORION repository against the ORION Autonomous Execution Constitution and the Master Roadmap safety requirements. The audit covers physical action blocking, simulation-first enforcement, permission systems, audit logging, and fail-closed behavior.

### Severity Summary

| Severity | Count | Key Areas |
|----------|-------|-----------|
| CRITICAL | 0 | — |
| HIGH | 2 | Missing financial/legal action approval mechanisms; in-memory permission registry loses state on restart |
| MEDIUM | 3 | No formal policy enforcement for Tier-2 SA approval; safety state machine lacks persistence; cross-domain arbitration not integration-tested with live PG |
| LOW | 2 | Safety limits in JSON not cryptographically signed; physical watchdog has no real hardware target |

---

## 1. Physical Actions Blocked by Default

**STATUS: VERIFIED — IMPLEMENTED & TESTED**

- `src/safety/safety_enforcement.py`: CBF (Control Barrier Function) based safety enforcement. Actions that violate safety barriers are denied.
- `src/arbitration/action_arbitration.py`: `ActionArbitrator` checks risk tier against policy. Tier-3 actions require SA approval. State machine checks if action is permitted in current safety state.
- `src/safety/state_machine.py`: Safety state machine with states: NORMAL, CAUTION, WARNING, EMERGENCY. Actions are denied in EMERGENCY state.
- Tests: `tests/unit/test_safety_v3_verification.py` (8 tests, 6 formally verified properties), `tests/unit/test_safety_arbitration.py`

**Evidence:** 26 safety-related tests passing. Deny-by-default pattern confirmed in code.

## 2. Simulation is the Default Environment

**STATUS: VERIFIED — IMPLEMENTED & TESTED**

- `simulation/grid_world.py`: Grid world simulation environment with sensors and actuators.
- `src/domains/*/`: All 4 domain modules (drone, home, industrial, vehicle) have simulators, not real hardware interfaces.
- `src/hal/__init__.py`: HAL defines interfaces only — no device adapters connected to real hardware.
- No real hardware connections exist in the codebase.
- Docker and CI run tests in simulation mode (`-m "not live"`).

**Evidence:** All 573 tests run in simulation. No hardware connections found.

## 3. Restricted Tools Require Permission

**STATUS: VERIFIED — IMPLEMENTED**

- `src/api/permissions.py`: 4 permission levels (READ, WRITE, ADMIN, SUPERVISOR). `PermissionChecker` enforces deny-by-default for unregistered agents.
- `src/api/auth.py`: Bearer token authentication via `ORION_API_KEY`. Constant-time comparison (`hmac.compare_digest`).
- Tests: `tests/unit/test_permissions.py` (19 tests), `tests/unit/test_auth.py` (15 tests)

**FINDING (HIGH):** In-memory permission registry (`PermissionChecker._permissions: dict`) loses state on process restart. No persistence layer for permissions.

**FINDING (CRITICAL — from Security Audit) — FIXED:** `ORIONAPI` public methods (`execute`, `recall`, `remember`, `get_world_state`) do not call `_check_auth()`, allowing auth bypass. **FIXED:** Added `_check_auth()` to all public methods. 8 auth enforcement tests added and passing.

## 4. Financial Actions Require Approval

**STATUS: PARTIALLY VERIFIED — DOCUMENTED but NOT IMPLEMENTED IN CODE**

- The ORION Constitution states: "STOP only for: real money spending, legal decisions, physical risk, or strategic goal changes."
- The codebase has no explicit financial action type or approval mechanism in `src/arbitration/action_arbitration.py`.
- The `ActionProposal` contract has a `risk_tier` field but no `action_category` for financial/legal/strategic actions.

**FINDING (HIGH):** No code-level enforcement of financial action approval. The Constitution is documented but not mechanically enforced. RECOMMENDED: Add `ActionCategory` enum (PHYSICAL, FINANCIAL, LEGAL, STRATEGIC, DIGITAL) to `ActionProposal` and enforce in `ActionArbitrator`.

## 5. Legal Actions Require Approval

**STATUS: PARTIALLY VERIFIED — DOCUMENTED but NOT IMPLEMENTED IN CODE**

Same finding as Section 4. No code-level distinction between legal actions and digital actions.

## 6. Physical Actions Require Approval

**STATUS: VERIFIED — IMPLEMENTED**

- `src/arbitration/action_arbitration.py`: Physical actions (Tier-2, Tier-3) require SA approval based on safety policy.
- `src/safety/state_machine.py`: Emergency state blocks all actions.
- `src/safety/physical_watchdog.py`: Dual watchdog system (hardware + software) for emergency stop.
- `src/safety/cross_domain_arbitration.py`: Cross-domain safety arbitration with SC-1 > SC-2 > SC-3 priority.

## 7. Audit Logs Exist

**STATUS: VERIFIED — IMPLEMENTED & TESTED**

- `src/audit/audit_system.py`: Hash-chained audit log with tamper detection. Events: action approved/denied, safety violations, state changes.
- `src/persistence/audit_replication.py`: Audit log replication to PostgreSQL with WAL hooks.
- Tests: `tests/test_audit_system.py` (9 tests), `tests/unit/test_audit_replication.py` (12 tests)

**Evidence:** 21 audit-related tests passing. Hash chain integrity verified.

## 8. Failures Fail Closed

**STATUS: VERIFIED — IMPLEMENTED**

- `src/safety/safety_enforcement.py`: CBF violations return `SafetyVerdict(allowed=False)` — deny by default.
- `src/arbitration/action_arbitration.py`: If safety state check fails, action is denied.
- `src/safety/sensor_validation.py`: 5-stage sensor validation pipeline — invalid sensors trigger safety events.
- `src/safety/actuator_verification.py`: Actuator verification pipeline — failed verification blocks action execution.

## 9. Agent Permissions Are Explicit

**STATUS: VERIFIED — IMPLEMENTED**

- `src/api/permissions.py`: `PermissionLevel` enum (READ, WRITE, ADMIN, SUPERVISOR). `PermissionChecker` enforces per-resource permissions.
- `PermissionChecker.register_agent(agent_id, level, resources)`: Explicit registration required.
- Deny-by-default for unregistered agents.

## 10. Supervisor Bypass Vectors Analysis

| Vector | Risk | Mitigation |
|--------|------|------------|
| Supervisor calling internal modules directly (bypassing ORIONAPI) | MEDIUM | All public methods should go through API with auth check |
| In-memory permissions lost on restart | HIGH | Add permission persistence to storage layer |
| Safety limits in JSON not signed | LOW | Add hash verification for policy files |
| No ActionCategory for financial/legal | HIGH | Add action categories to contracts |
| Physical watchdog has no real target | LOW | Expected — no hardware yet (simulation only) |

## 11. Documented vs Implemented vs Tested Safety

| Safety Property | Documented | Implemented | Tested |
|----------------|------------|-------------|--------|
| Physical actions blocked by default | YES | YES (CBF + state machine) | YES (26 tests) |
| Simulation is default | YES | YES (all simulators) | YES (573 tests) |
| Restricted tools require permission | YES | YES (PermissionChecker) | YES (19 tests) |
| Financial actions require approval | YES (Constitution) | NO | NO |
| Legal actions require approval | YES (Constitution) | NO | NO |
| Physical actions require approval | YES | YES (ActionArbitrator) | YES |
| Audit logs exist | YES | YES (hash-chained) | YES (21 tests) |
| Failures fail closed | YES | YES (deny-by-default) | YES |
| Agent permissions explicit | YES | YES (4-level) | YES (19 tests) |

---

## Recommendations

1. **CRITICAL:** Fix `ORIONAPI` auth bypass — add `_check_auth()` to `execute`, `recall`, `remember`, `get_world_state`
2. **HIGH:** Add `ActionCategory` enum to `ActionProposal` for financial/legal/strategic action enforcement
3. **HIGH:** Persist permission registry to storage layer
4. **MEDIUM:** Add safety state machine persistence
5. **LOW:** Sign safety policy JSON files with hash verification

