# Luna Phase 004 Guidance

**Model:** gpt-5.6-luna
**Date:** 2026-08-22
**Phase:** Phase 004 (ORION Core) Specification
**Context:** Phase 003 VERIFIED, proceeding to Phase 004

# ORION Phase 004 — ORION Core Specification Baseline

**Specification status:** PROPOSED  
**Evidence status:** Phase 003 model results are reported as VERIFIED in the supplied project history. Repository implementation status for Phase 004 is UNKNOWN until inspected and tested.

## 0. Governance and phase-state inconsistency

The supplied roadmap states:

> Current phase: PHASE 001 — REPOSITORY AUDIT & RECOVERY

However, the project status also states that Phase 003 was verified and approved in Round 7, commit `e7f855b`.

This must be reconciled in the project records before Phase 004 is declared active. The contradiction does not require Founder approval; it is a documentation and evidence-registry correction. The Phase 004 implementation may be designed now, but Phase 004 completion must depend on verified evidence that Phases 001–003 satisfy their acceptance criteria.

---

# 1. PHASE 004 SCOPE

## 1.1 Objective

Build the central digital reasoning, planning, permission, execution, observation, correction, and audit engine for ORION.

ORION Core must implement the lifecycle:

```text
GOAL
  → PLAN
  → EXECUTE
  → OBSERVE
  → EVALUATE
  → CORRECT
  → REMEMBER
```

For Phase 004, “remember” means maintaining task-local execution state and auditable history. Full persistent memory, semantic retrieval, episodic memory, and world-state memory belong to Phase 005.

## 1.2 In scope

Phase 004 should deliver:

1. **Supervisor**
   - Receives a goal.
   - Classifies the goal and required capabilities.
   - Creates and manages a task.
   - Coordinates planning, execution, observation, evaluation, and recovery.
   - Does not ask the Founder to continue during ordinary digital execution.

2. **Task engine**
   - Task creation and lifecycle management.
   - Step and dependency tracking.
   - Cancellation, timeout, retry, pause, resume, and failure states.
   - Idempotency and duplicate-execution protection.

3. **Planner interface**
   - Converts goals into structured plans.
   - Produces explicit steps, dependencies, required tools, expected outputs, risks, and permissions.
   - Supports plan validation before execution.

4. **Permission system**
   - Determines whether an operation is allowed, denied, or requires approval.
   - Enforces least privilege and scope restrictions.
   - Separates planning permission from execution permission.

5. **Policy engine**
   - Applies safety, security, privacy, resource, and authorization policies.
   - Provides deterministic decisions independent of model output.
   - Denies unknown or ambiguous high-impact operations by default.

6. **Execution engine**
   - Invokes registered tools and digital actions.
   - Validates arguments.
   - Enforces timeouts, quotas, sandboxing, and cancellation.
   - Returns structured results rather than untrusted free-form text.

7. **Tool registry**
   - Registers available tools and their metadata.
   - Defines schemas, capabilities, permissions, risk level, side effects, timeout, and rollback behavior.
   - Prevents arbitrary model-generated tool invocation.

8. **Agent registry**
   - Registers specialist agents or agent adapters.
   - Defines capabilities, model requirements, permissions, health state, and invocation contract.
   - Phase 004 may support registry and orchestration without requiring the complete specialist-agent ecosystem planned for Phase 009.

9. **Audit logging**
   - Records goals, plans, policy decisions, approvals, tool calls, results, errors, retries, state transitions, and termination.
   - Provides correlation IDs and causality links.
   - Makes security-relevant records tamper-evident or append-only where practical.

10. **Error recovery**
    - Handles tool failure, malformed output, timeout, unavailable model, policy denial, partial completion, and contradictory observations.
    - Uses bounded retries and alternate plans.
    - Escalates when safe recovery is impossible.

11. **State management**
    - Stores task state, plan state, step state, execution context, permissions, and event history.
    - Must support crash recovery and deterministic reconstruction of task status.

12. **Model gateway**
    - Provides a model-independent interface for planning, reasoning, extraction, and evaluation.
    - Integrates the qualified 7B and 14B models without coupling core logic to a specific provider.

## 1.3 Out of scope

The following must not be silently pulled into Phase 004:

- Persistent long-term memory and semantic retrieval.
- General multimodal perception.
- Physical-world actuation.
- Unbounded computer control.
- Real vehicle, robot, drone, industrial, or home-device control.
- Training a new foundation model.
- Autonomous policy modification.
- Unrestricted self-modification.
- Phase 009’s complete dynamic specialist-agent ecosystem.
- Claims of general intelligence based on a successful demo.

---

# 2. PHASE 004 ACCEPTANCE CRITERIA

Phase 004 is complete only when all criteria below are satisfied and documented.

## 2.1 Functional acceptance

### A. Multi-step digital task

The Supervisor must autonomously execute a predefined multi-step digital task without asking the Founder to continue.

Minimum demonstration:

```text
Goal
  → decompose into at least 3 steps
  → inspect available tools
  → request or infer required permissions
  → execute steps in dependency order
  → observe results
  → detect at least one injected recoverable failure
  → retry or choose a safe alternative
  → verify final output
  → emit a complete audit trail
```

The demonstration must run in a deterministic local test environment, not against uncontrolled external systems.

### B. Permission discipline

The system must:

- deny an unauthorized operation;
- distinguish read from write access;
- distinguish reversible from irreversible actions;
- prevent a model from bypassing the permission engine;
- require explicit approval for configured approval-gated actions;
- never treat natural-language claims such as “the user already approved this” as proof of approval.

### C. Policy enforcement

The policy engine must:

- make deterministic decisions for identical inputs;
- deny unknown tools and malformed requests;
- reject out-of-scope targets;
- enforce resource and time limits;
- block physical actions entirely in Phase 004;
- reject policy-changing requests from the model or supervisor unless handled by an external governance process.

### D. Error recovery

The core must safely handle:

- transient tool failure;
- timeout;
- malformed model output;
- invalid tool arguments;
- unavailable model;
- duplicate request;
- partial task completion;
- policy denial;
- contradictory observation;
- process restart during execution.

### E. Auditability

For every task, the system must be able to reconstruct:

- original goal;
- normalized goal;
- selected model;
- generated plan;
- plan validation result;
- permission decisions;
- policy decisions;
- each tool invocation;
- tool arguments or a protected representation;
- outputs;
- retries;
- corrections;
- final result;
- failure or termination reason.

### F. Reproducibility

A test run must record:

- repository commit;
- configuration version;
- model name and version;
- prompt/template version;
- tool registry version;
- policy version;
- test-case version;
- hardware/runtime information;
- timestamps and latency;
- result and failure classification.

## 2.2 Quality acceptance

Recommended initial targets:

| Area | Minimum requirement |
|---|---|
| Test suite | All Phase 004 tests pass |
| Lint/type checks | Ruff and mypy clean under project policy |
| Deterministic policy tests | 100% pass |
| Unknown-tool handling | 100% denied |
| Physical-action attempts | 100% denied |
| Invalid tool arguments | 100% rejected before execution |
| Audit completeness | 100% of lifecycle events correlated |
| Crash recovery | No silent task loss in tested scenarios |
| Duplicate execution | Idempotency behavior demonstrated |
| Recovery benchmark | Measured success rate on injected failures |
| Unauthorized action benchmark | Zero unauthorized executions |
| Model output parsing | Invalid outputs never reach execution |

Targets are proposed engineering thresholds and must be recorded as such until measured.

## 2.3 Documentation acceptance

Required documents:

```text
docs/architecture/ORION_CORE.md
docs/architecture/ORION_CORE_STATE_MACHINE.md
docs/architecture/ORION_CORE_INTERFACES.md
docs/safety/ORION_CORE_SAFETY_CASE.md
docs/evaluation/PHASE_004_EVALUATION.md
docs/evidence/PHASE_004_EVIDENCE.md
docs/decisions/ADR-004-*.md
```

The final phase report must classify every result as:

- VERIFIED
- PARTIALLY VERIFIED
- PROPOSED
- HYPOTHESIS
- UNKNOWN

---

# 3. ARCHITECTURE GUIDANCE

## 3.1 Recommended logical architecture

```text
                    ┌─────────────────────┐
                    │   User/API Layer    │
                    └──────────┬──────────┘
                               │ Goal
                    ┌──────────▼──────────┐
                    │      Supervisor     │
                    └──────┬─────┬────────┘
                           │     │
                 ┌─────────▼─┐ ┌─▼──────────────┐
                 │ Task Engine│ │ Model Gateway │
                 └──────┬────┘ └──────┬────────┘
                        │             │
                 ┌──────▼──────┐ ┌────▼─────────┐
                 │ Plan Manager│ │ Output Parser│
                 └──────┬──────┘ └────┬─────────┘
                        │              │
                 ┌──────▼──────────────▼──────┐
                 │   Plan / Action Validator  │
                 └──────┬──────────────┬──────┘
                        │              │
                 ┌──────▼──────┐ ┌─────▼────────┐
                 │ Policy Engine│ │ Permissions  │
                 └──────┬──────┘ └─────┬────────┘
                        └──────┬───────┘
                               │ Decision
                    ┌──────────▼──────────┐
                    │   Execution Engine  │
                    └──────┬──────┬───────┘
                           │      │
                 ┌─────────▼─┐ ┌──▼───────────┐
                 │ Tool Registry│ │ Agent Registry│
                 └─────────┬─┘ └──┬───────────┘
                           │       │
                    ┌──────▼───────▼──────┐
                    │ Digital Tool Adapters│
                    └─────────────────────┘

                    ┌─────────────────────┐
                    │ State Store / Events│
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Audit Logger     │
                    └─────────────────────┘
```

The model may propose plans and actions. It must not directly execute them.

## 3.2 Core principle: model proposes, deterministic code disposes

The language model should be treated as an untrusted probabilistic component.

```text
Model output
  → schema validation
  → semantic validation
  → policy evaluation
  → permission evaluation
  → execution
```

No path should exist where model text is interpreted as executable instructions without passing through these gates.

## 3.3 Suggested module boundaries

A possible package structure:

```text
orion_core/
    supervisor/
        supervisor.py
        lifecycle.py
    tasks/
        models.py
        task_engine.py
        state_machine.py
    planning/
        planner.py
        plan_models.py
        validator.py
    execution/
        executor.py
        action_models.py
        retry.py
        cancellation.py
    policy/
        engine.py
        rules.py
        decisions.py
    permissions/
        manager.py
        grants.py
        approvals.py
    tools/
        registry.py
        schemas.py
        adapters.py
    agents/
        registry.py
        contracts.py
    models/
        gateway.py
        providers.py
        routing.py
        output_parser.py
    state/
        store.py
        events.py
        projections.py
    audit/
        logger.py
        redaction.py
        integrity.py
    recovery/
        recovery_manager.py
        failure_classifier.py
    safety/
        boundaries.py
        validators.py
```

The exact package names are implementation choices. The boundaries are architectural requirements.

## 3.4 Canonical data objects

At minimum, define typed schemas for:

- `Goal`
- `Task`
- `Plan`
- `PlanStep`
- `ActionRequest`
- `ToolManifest`
- `AgentManifest`
- `PermissionRequest`
- `PermissionDecision`
- `PolicyDecision`
- `Observation`
- `Evaluation`
- `RecoveryAttempt`
- `TaskEvent`
- `TaskResult`
- `AuditRecord`

Every object should include:

- unique identifier;
- task correlation ID;
- schema version;
- creation timestamp;
- producer;
- security classification where relevant;
- provenance;
- validation status.

## 3.5 State machine

A task state machine should be explicit rather than inferred from log text.

Example:

```text
CREATED
  → ANALYZING
  → PLANNED
  → VALIDATING
  → AWAITING_APPROVAL
  → READY
  → EXECUTING
  → OBSERVING
  → EVALUATING
  → CORRECTING
  → COMPLETED
```

Terminal and exceptional states:

```text
CANCELLED
FAILED
BLOCKED
TIMED_OUT
EXPIRED
PARTIALLY_COMPLETED
```

Invalid transitions must be rejected. State changes must produce events.

## 3.6 Tool contract

Each tool should declare:

```json
{
  "name": "example.read_file",
  "version": "1.0",
  "input_schema": "...",
  "output_schema": "...",
  "capabilities": ["filesystem.read"],
  "risk_level": "low",
  "side_effects": false,
  "reversible": true,
  "allowed_targets": ["workspace"],
  "timeout_seconds": 10,
  "requires_approval": false,
  "supports_idempotency": true,
  "rollback": null
}
```

Tools must be invoked through adapters. The model must not supply arbitrary executable code, shell fragments, network destinations, or filesystem paths outside the declared scope.

---

# 4. SAFETY REQUIREMENTS

## 4.1 Hard boundaries

Phase 004 must enforce:

1. **Simulation and digital execution only.**
2. **No physical actuation interfaces.**
3. **No uncontrolled network access.**
4. **No arbitrary shell execution by default.**
5. **No unrestricted filesystem access.**
6. **No credential extraction or secret disclosure.**
7. **No self-modification of policy, permissions, audit logic, or safety gates.**
8. **No silent escalation from read to write or from reversible to irreversible action.**
9. **No execution based solely on model-generated approval claims.**
10. **No hidden tool calls outside the audit system.**

## 4.2 Deny-by-default policy

The policy engine must deny:

- unregistered tools;
- unknown tool versions;
- malformed arguments;
- missing user/task authorization;
- out-of-scope resources;
- actions exceeding quotas;
- actions with unknown side effects;
- physical-world actions;
- attempts to alter policy or permission rules;
- attempts to disable logging or safety checks.

## 4.3 Approval model

Approval should be:

- explicit;
- tied to a task and action;
- scoped to a specific resource and operation;
- time-limited;
- non-transferable;
- recorded in the audit log;
- invalidated if the action materially changes.

Approval for one step must not automatically authorize a different step.

## 4.4 Prompt-injection resistance

External content must be treated as data, not authority.

Documents, web pages, tool output, and model-generated text must not be allowed to:

- redefine system policy;
- grant permissions;
- alter task ownership;
- change safety thresholds;
- instruct the executor to bypass validation.

The system should preserve provenance so that instructions from untrusted content remain distinguishable from trusted system instructions.

## 4.5 Resource controls

Every task and action should have bounded:

- execution time;
- retry count;
- token/model budget;
- tool-call count;
- output size;
- filesystem scope;
- network scope;
- concurrency;
- recursion or delegation depth.

## 4.6 Audit and privacy

Audit logs must be protected against:

- deletion by the executing task;
- modification by the model;
- accidental secret leakage;
- ambiguous event ordering.

Sensitive values should be redacted or stored by reference, while retaining enough information to reproduce and investigate behavior.

---

# 5. MODEL INTEGRATION

## 5.1 Required abstraction

Models must be accessed through a provider-neutral gateway:

```python
class ModelGateway(Protocol):
    async def generate(
        self,
        request: ModelRequest,
        *,
        timeout: float,
    ) -> ModelResponse:
        ...
```

The gateway should expose:

- model identifier;
- model version or digest;
- prompt/template version;
- structured-output mode;
- timeout;
- token usage;
- latency;
- error classification;
- safety metadata;
- request and response correlation IDs.

## 5.2 Model roles

Initially, use models for bounded cognitive roles:

| Role | openchat:7b | qwen2.5:14b |
|---|---:|---:|
| Goal normalization | Candidate | Candidate |
| Basic decomposition | Candidate | Candidate |
| Plan generation | Candidate | Preferred candidate |
| Plan critique | Candidate | Preferred candidate |
| Recovery proposal | Candidate | Preferred candidate |
| Natural-language summarization | Preferred for latency | Candidate |
| Policy decision | Not authoritative | Not authoritative |

The policy engine, permission manager, schema validator, and execution engine must remain deterministic and model-independent.

These role assignments are **PROPOSED**, not new benchmark results.

## 5.3 Routing

Use a configurable router rather than hard-coding one model:

```text
simple / low-risk / latency-sensitive
    → openchat:7b

complex / ambiguous / recovery / planning-critical
    → qwen2.5:14b

high-risk policy decision
    → deterministic policy engine, never model-only
```

Routing should consider:

- task complexity;
- risk level;
- required context size;
- latency budget;
- model availability;
- failure history;
- explicit deployment configuration.

The router must not infer that a larger model is safer merely because it is larger.

## 5.4 Structured output

Require models to produce schema-constrained objects such as:

```json
{
  "goal_interpretation": "...",
  "assumptions": [],
  "steps": [
    {
      "id": "step-1",
      "description": "...",
      "tool": "tool.name",
      "arguments": {},
      "depends_on": [],
      "expected_observation": "...",
      "risk": "low"
    }
  ],
  "uncertainties": [],
  "completion_criteria": []
}
```

The parser must reject:

- unknown fields where strictness is required;
- missing required fields;
- invalid tool names;
- invalid dependency graphs;
- executable code;
- implicit permissions;
- unsupported action types.

## 5.5 Fallback behavior

If the selected model fails:

1. classify the failure;
2. retry only if the failure is retryable;
3. fall back to the alternate qualified model if allowed by policy;
4. revalidate the new output from the beginning;
5. terminate safely if no valid plan is produced.

The fallback model must not inherit unverified permissions from the failed attempt.

## 5.6 Model evidence

Every model-generated artifact must record:

- exact model name;
- model tag/digest;
- runtime/provider;
- prompt version;
- decoding parameters;
- input and output token counts if available;
- latency;
- validation outcome;
- whether the output was executed, rejected, or revised.

Phase 003’s benchmark evidence must be linked from the Phase 004 evaluation report rather than repeated as an unsupported claim.

---

# 6. TESTING STRATEGY

## 6.1 Unit tests

Required unit-test areas:

- task state transitions;
- plan dependency validation;
- schema parsing;
- malformed model outputs;
- policy rules;
- permission matching;
- approval expiry and scope;
- tool registration;
- argument validation;
- timeout and retry classification;
- idempotency keys;
- cancellation;
- audit event creation;
- event ordering;
- redaction;
- model routing;
- fallback logic.

## 6.2 Integration tests

Test complete flows using fake deterministic models and sandboxed tools:

1. successful multi-step task;
2. dependency-ordered execution;
3. failed step with bounded retry;
4. failed step with alternate recovery;
5. policy-denied action;
6. approval-required action;
7. expired approval;
8. malformed tool request;
9. unknown tool request;
10. task cancellation;
11. process restart and state recovery;
12. duplicate submission;
13. partial completion;
14. unavailable primary model with fallback;
15. prompt-injection content in tool output.

## 6.3 Safety and adversarial tests

Include adversarial cases where the model attempts to:

- call an unregistered tool;
- invoke a physical actuator;
- access `/etc`, credentials, or unrelated workspaces;
- execute shell syntax through a file or argument field;
- claim that approval exists;
- disable logging;
- modify policy rules;
- reinterpret tool output as a system instruction;
- conceal a failed action;
- continue after cancellation;
- exceed retry or budget limits.

Expected result: the action is rejected, no unauthorized side effect occurs, and the rejection is audited.

## 6.4 Property-based and state-machine testing

Use property-based tests for:

- arbitrary invalid state transitions;
- dependency graphs;
- permission scopes;
- retry sequences;
- duplicate events;
- malformed tool arguments.

Important invariants:

```text
No execution without policy approval.
No execution without permission.
No unknown tool can execute.
No physical action can execute.
Every execution has an audit record.
A cancelled task cannot start new actions.
A completed task cannot execute additional steps.
```

## 6.5 Failure injection

Inject:

- tool timeout;
- connection loss;
- corrupt response;
- process crash;
- delayed observation;
- inconsistent output;
- unavailable model;
- audit-store failure;
- state-store failure.

The system must fail closed for safety-critical decisions. It must not report success merely because an action was requested.

## 6.6 Evaluation report

The Phase 004 benchmark should report at minimum:

- task success;
- unauthorized-action rate;
- policy bypass rate;
- recovery success;
- recovery time;
- average and percentile latency;
- model calls per task;
- tool calls per task;
- duplicate execution rate;
- audit completeness;
- crash-recovery success;
- failure reason distribution.

No metric should be reported until actually measured.

---

# 7. KEY RISKS AND MITIGATIONS

| Risk | Impact | Mitigation |
|---|---|---|
| Model hallucinates tools or arguments | Unsafe or failed execution | Strict registry, schemas, policy gate |
| Prompt injection | Unauthorized behavior | Treat external content as untrusted data; provenance and instruction isolation |
| Permission confusion | Unauthorized side effects | Separate policy, permission, approval, and execution layers |
| Retry duplicates side effects | Data corruption | Idempotency keys, side-effect metadata, rollback or approval gates |
| Partial task completion misreported as success | False claims | Explicit completion criteria and postcondition verification |
| State loss after crash | Inconsistent execution | Event log, durable state, recovery tests |
| Audit tampering or missing records | No accountability | Append-only/tamper-evident logging and execution wrapper |
| Overreliance on the 14B model | Latency/cost and false confidence | Configurable routing and measured task-level evaluation |
| Model output parser vulnerability | Validation bypass | Strict typed parsing, reject unknown/ambiguous structures |
| Scope expansion into memory/world model | Phase drift | Keep Phase 004 state task-local; record ADRs for boundary decisions |
| Tool adapter vulnerability | Sandbox escape | Minimal privileges, isolated execution, allowlisted targets |
| Policy engine becomes mutable by agents | Safety degradation | Policy configuration immutable during task execution |
| External network or credential exposure | Security/privacy incident | Deny by default, network isolation, secret redaction |
| False autonomy claims | Misleading acceptance | Reproducible scripted acceptance task and evidence registry |

---

# 8. DEPENDENCIES ON PHASES 001–003

## Phase 001: Repository Audit and Recovery

Phase 004 depends on:

- reproducible installation;
- passing baseline tests;
- working lint and type checks;
- documented security and safety constraints;
- license registry;
- evidence registry;
- architecture consistency review;
- CI verification.

The repository-status contradiction noted above must be resolved in the evidence and roadmap documents.

## Phase 002: ORION Evaluation System

Phase 004 depends on:

- reusable benchmark runner;
- standard result schema;
- deterministic test versioning;
- latency and failure measurement;
- safety, permission, recovery, and tool-use benchmark categories;
- report generation.

Phase 004 must extend the official evaluation system rather than create an unrelated test harness.

## Phase 003: Model Selection

Phase 004 depends on:

- model provider/runtime adapters;
- verified model names and versions;
- hardware/runtime metadata;
- known latency and safety results;
- model-selection report;
- documented limitations;
- a mechanism for recording model provenance.

Current supplied status:

- `openchat:7b`: 12/12 PASS;
- `qwen2.5:14b`: 12/12 PASS;
- 32B/72B: pending hardware verification.

These results are **VERIFIED according to the supplied Phase 003 record**. They do not by themselves prove that either model can safely operate ORION Core. Core safety must remain deterministic and model-independent.

---

# 9. RECOMMENDED IMPLEMENTATION ORDER

## Step 1 — Reconcile project evidence

Before code work:

1. Update the roadmap’s current-phase record.
2. Link Phase 003 approval and commit `e7f855b`.
3. Verify Phase 001 and Phase 002 acceptance evidence exists.
4. Record any missing evidence as `UNKNOWN`, not as complete.

## Step 2 — Freeze the core contracts

Define and review:

- task schema;
- plan schema;
- action schema;
- tool manifest;
- policy decision;
- permission grant;
- audit event;
- state machine;
- model gateway.

Add contract tests before implementing providers.

## Step 3 — Build deterministic safety infrastructure first

Implement:

1. tool registry;
2. schema validator;
3. permission manager;
4. policy engine;
5. audit wrapper;
6. sandboxed fake tools.

Do not begin with free-form autonomous execution.

## Step 4 — Implement the task/state engine

Add:

- durable task state;
- explicit transitions;
- event emission;
- cancellation;
- timeout;
- idempotency;
- crash recovery.

## Step 5 — Add planning and execution orchestration

Implement:

```text
goal intake
→ plan generation
→ plan validation
→ policy/permission checks
→ step execution
→ observation
→ evaluation
→ correction/recovery
→ completion verification
```

## Step 6 — Integrate model adapters

Add the model gateway for `openchat:7b` and `qwen2.5:14b`.

Start with deterministic test doubles, then provider integration. Model outputs must never bypass the existing validation and policy layers.

## Step 7 — Implement recovery

Add bounded recovery strategies:

- retry;
- corrected arguments;
- alternate registered tool;
- alternate qualified model;
- replanning;
- safe termination.

Every recovery action must itself pass policy and permission checks.

## Step 8 — Build the acceptance benchmark

Create at least three canonical digital tasks:

1. successful multi-step task;
2. task with injected recoverable failure;
3. task containing unauthorized and prompt-injection attempts.

Run them through ORION Eval and produce reproducible reports.

## Step 9 — Security and safety review

Perform:

- threat-model review;
- tool-adapter review;
- permission bypass review;
- audit-integrity review;
- sandbox review;
- dependency and license review;
- failure-injection testing.

## Step 10 — Phase 004 review gate

Do not mark Phase 004 complete until:

- implementation exists;
- tests pass;
- acceptance task succeeds reproducibly;
- unauthorized actions are zero in the defined test suite;
- all failures are classified;
- documentation and evidence are committed;
- limitations and unresolved risks are recorded.

---

# 10. Phase 004 completion report template

```text
PHASE
004 — ORION CORE

STATUS
[VERIFIED / PARTIALLY VERIFIED / BLOCKED]

WORK COMPLETED
- ...

COMPONENTS
- Supervisor:
- Task engine:
- Policy engine:
- Permissions:
- Execution engine:
- Tool registry:
- Agent registry:
- Audit logging:
- Recovery:
- State management:
- Model gateway:

TESTS
- Unit:
- Integration:
- Safety:
- Adversarial:
- Failure injection:
- ORION Eval:

RESULTS
- Multi-step autonomous digital task:
- Recovery success:
- Unauthorized action rate:
- Audit completeness:
- Crash recovery:
- Latency:
- Model routing:

ERRORS
- ...

FIXES
- ...

EVIDENCE
- Commit:
- Test report:
- Evaluation report:
- Safety review:
- Security review:
- ADRs:

REMAINING RISKS
- ...

UNKNOWN
- ...

NEXT PHASE
Phase 005 only after all Phase 004 acceptance criteria are VERIFIED.
```

**Baseline architectural decision:** ORION Core should be a deterministic, auditable control plane around probabilistic models—not a model-driven execution loop. The models may reason and propose; only validated, authorized, policy-approved actions may execute.