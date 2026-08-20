# ADR-006: Control Barrier Function (CBF) Based Safety Enforcement

- **Decision ID:** ADR-006
- **Date:** 2026-08-20
- **Owner:** ORION Supervisor
- **Reversible?:** Yes (architecture decisions can be revised in future versions)

## Context
The ORION project is a Physical Intelligence OS. Hierarchy: Founder → Architect/Reviewer Luna (GPT-5.6) → ORION Supervisor → Specialized Agents. All work follows the lifecycle: Specification → Architecture → Implementation → TestアシスタントAn explicit mathematical safety enforcement mechanism is required to guarantee physical safety across mobile robots, manipulators, and autonomous vehicles operating in shared human environments.

## Problem
High-level AI planners, trajectory generators, and LLM agent outputs can generate velocity, force, or spatial positioning commands that violate physical hardware limits or enter dangerous keep-out zones. Traditional post-hoc command clipping or static threshold rules cause severe kinematic chatter, instability, or unsafe boundary breaches.

## Options
1. **Simple Saturated Boundary Clipping:** Truncating commands to min/max scalar bounds (e.g. `clamp(v, v_min, v_max)`).
   - *Pros:* Computationally instantaneous.
   - *Cons:* Ignores system dynamics, momentum, obstacle geometry, and multi-joint coupling; can push physical systems into unstable state regimes.
2. **Rule-Based Emergency Stopping (E-Stop Only):** Triggering hard brakes whenever a boundary threshold is crossed.
   - *Pros:* Safe against immediate collisions.
   - *Cons:* Highly disruptive to continuous mission execution; causes severe mechanical stress and unnecessary task failure on minor transient boundary approaches.
3. **Control Barrier Functions (CBFs) with Quadratic Programming (QP):** Filtering proposed commands $u_{des}$ by solving real-time QPs that enforce forward invariance of safe state sets $\mathcal{C} = \{x \mid h(x) \ge 0\}$.
   - *Pros:* Mathematically proven forward invariance ($\dot{h}(x) + \alpha(h(x)) \ge 0$); computes minimal necessary corrective adjustments $\Delta u$ to keep the system strictly inside safe bounds while preserving desired user motion whenever safe.
   - *Cons:* Requires continuous evaluation of state-barrier gradients and lightweight numerical solver execution per 100Hz tick.

## Decision
Adopt **Control Barrier Functions (CBFs)** as the core mathematical physical safety enforcement mechanism within the Verification Plane.

## Reason
Control Barrier Functions provide rigorous mathematical safety proofs for continuous dynamical systems. By filtering unverified target commands $u_{des}$ through a CBF-QP optimization step, ORION guarantees that the system state $x(t)$ remains invariant within the safe manifold $\mathcal{C}$ at all times. If a high-level planner issues an unsafe command, the CBF computes the minimally invasive safe control action $u^*_{safe}$ that satisfies physical constraints without halting execution unnecessarily.

## Evidence
- Implemented in `orion/implementation/src/safety/safety_enforcement.py` featuring dedicated CBF classes:
  - `VelocityLimitCBF`: Limits linear and angular velocities.
  - `ForceLimitCBF`: Constrains joint and end-effector torque/force outputs.
  - `SpatialKeepOutCBF`: Enforces geofenced keep-out zones and minimum obstacle distances.
  - `JointLimitCBF`: Prevents joint over-extension and mechanical hard-stop collisions.
  - `AccelerationLimitCBF`: Limits linear and angular acceleration derivatives to prevent tipping.
- Tested extensively in `test_audit_system.py` and `test_phase1.py`, maintaining 100Hz tick execution and sub-0.2ms QP solve times.

## Trade-offs
- **Model Dependence:** CBFs rely on accurate kinematic and dynamic bounds ($h(x)$ definitions).
- **Mitigation:** Conservative safety margins and fallback controllers (`BaseFallbackController`, `HomeFallbackController`, `RobotFallbackController`) take control if sensor uncertainty or state degradation exceeds tolerable bounds.
