# ADR-007: Simulation-First Domain Progression

- **Decision ID:** ADR-007
- **Date:** 2026-08-20
- **Owner:** ORION Supervisor
- **Reversible?:** Yes (architecture decisions can be revised in future versions)

## Context
The ORION project is a Physical Intelligence OS. Hierarchy: Founder → Architect/Reviewer Luna (GPT-5.6) → ORION Supervisor → Specialized Agents. All work follows the lifecycle: Specification → Architecture → Implementation → Test → Verification → Review → Approval → Next Stage.

Deploying unverified autonomous physical intelligence software directly onto high-torque, physical hardware poses extreme risks of catastrophic equipment destruction, financial loss, and severe personal injury.

## Problem
What structured lifecycle progression must software features, planning algorithms, and agent control policies undergo before being authorized for execution on physical hardware in open real-world environments?

## Options
1. **Direct Physical Testing with Emergency Stop Oversight:** Deploying code directly onto physical hardware while a human operator holds a physical E-stop button.
   - *Pros:* Immediate exposure to real-world physics.
   - *Cons:* Extremely high risk of physical damage, high operational cost, non-reproducible edge-case testing.
2. **Dual-Mode Unit Testing + Hardware Verification:** Combining standard unit tests with benchtop motor runs.
   - *Pros:* Faster development than physical field testing.
   - *Cons:* Fails to validate complex multi-body physics, sensor noise pipelines, or real-time HIL timing jitter prior to hardware energization.
3. **Mandatory 5-Stage Simulation-First Domain Progression:** Enforcing a rigorous, staged progression lifecycle across five distinct operational domains:
   - *Stage 1: Pure Digital Simulation* (GridWorld / Abstract mathematical models)
   - *Stage 2: High-Fidelity Virtual Environments* (Physics engines / MuJoCo / Gazebo / PyBullet)
   - *Stage 3: Hardware-in-the-Loop (HIL) Simulation* (Real embedded compute & microcontrollers connected to simulated physics)
   - *Stage 4: Controlled Physical Environment* (Tethered, caged, or safety-netted physical hardware tests)
   - *Stage 5: Open Real-World Deployment* (Full autonomous operation in unconstrained production environments)

## Decision
Mandate the **5-Stage Simulation-First Domain Progression** pipeline for all ORION capabilities, control policies, and agent behaviors. Transition between stages requires explicit formal review and approval from Architect/Reviewer Luna (GPT-5.6) and ORION Supervisor.

## Reason
The 5-stage progression minimizes hardware risk and ensures full verification before physical deployment. Running algorithms through Stage 1 & Stage 2 validates cognitive goal synthesis, planning, and state logic. Stage 3 (HIL) verifies real-time 100Hz execution deadlines, CAN bus latency, and physical watchdog behavior on real target processors. Stage 4 ensures physical safety under supervised tethered conditions before Stage 5 real-world release.

## Evidence
- Enforced across Phase 1 through Phase 7 architecture specifications (`ORION_ARCHITECTURE_V0.1.md` through `V0.6.md`, `ORION_PHASE5_SPEC.md`, `ORION_PHASE6_SPEC.md`).
- Implemented simulation environments in `orion/implementation/simulation/grid_world.py`, `sensors.py`, `actuators.py`, and verified in `conftest.py`.

## Trade-offs
- **Sim-to-Real Gap:** Physics simulators cannot model 100% of real-world friction, compliance, and thermal dynamics.
- **Mitigation:** Domain randomization in Stage 2/3 and 5-stage sensor validation (ADR-012) ensure robustness against real-world domain shifts.
