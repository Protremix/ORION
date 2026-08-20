# ADR-011: Cross-Domain Safety Arbitration

- **Decision ID:** ADR-011
- **Date:** 2026-08-20
- **Owner:** ORION Supervisor
- **Reversible?:** Yes (architecture decisions can be revised in future versions)

## Context
The ORION project is a Physical Intelligence OS. Hierarchy: Founder → Architect/Reviewer Luna (GPT-5.6) → ORION Supervisor → Specialized Agents. All work follows the lifecycle: Specification → Architecture → Implementation → Test → Verification → Review → Approval → Next Stage.

Complex physical AI deployments involve multi-domain systems (e.g. an autonomous mobile base carrying a multi-axis manipulator arm and a tethered drone inspection unit). When multiple domain controllers operate concurrently, command conflicts, dynamic instability, or safety violations can cross domain boundaries.

## Problem
How should ORION arbitrate conflicting action commands or safety events originating from different domain controllers to maintain absolute physical safety without deadlocking system execution?

## Options
1. **First-Come, First-Served (FCFS) Execution:** Executing whichever domain command arrives first in the message queue.
   - *Pros:* Simple queue mechanics.
   - *Cons:* Extremely dangerous; a low-priority efficiency optimization task could override a critical collision-avoidance command.
2. **Consensus-Based Voting:** Requiring domain controllers to vote on action authorization.
   - *Pros:* Symmetric coordination.
   - *Cons:* High computational latency, risk of voting deadlocks during time-critical physical emergencies.
3. **Deterministic Hierarchical Priority Arbitration (SC-1 > SC-2 > SC-3):** Enforcing strict priority preemption based on Safety Criticality (SC) categories:
   - **SC-1 (Life & Structural Safety):** Emergency stopping, human collision avoidance, tipping prevention, mechanical over-torque protection.
   - **SC-2 (Mission & Equipment Safety):** Trajectory deviation limits, tool protection, battery preservation, geofence compliance.
   - **SC-3 (Operational Efficiency & Task Optimization):** Speed optimization, smooth motion profiling, energy saving, comfort metrics.

## Decision
Adopt **Deterministic Hierarchical Cross-Domain Safety Arbitration** enforcing strict **`SC-1 > SC-2 > SC-3`** priority preemption via the `CrossDomainArbitrator`.

## Reason
In physical intelligence systems, human safety and hardware structural integrity (SC-1) must unconditionally preempt mission execution (SC-2) and task performance optimization (SC-3). The `CrossDomainArbitrator` monitors registered domain states; if an SC-1 safety event occurs in any domain, the arbitrator immediately locks out SC-2/SC-3 commands across all linked domains, triggers preemptive fallback controllers (`BaseFallbackController`), and brings the hardware to a safe state within deterministic timing bounds.

## Evidence
- Implemented in `orion/implementation/src/safety/cross_domain_arbitration.py` (`CrossDomainArbitrator`, `SafetyCriticality`, `ArbitrationResult`).
- Tested in unit test suites verifying sub-millisecond priority preemption when an SC-1 trip overrides active SC-2/SC-3 planning loops.

## Trade-offs
- **Task Interruption:** An SC-1 preemption aborts active high-level tasks immediately, requiring task recovery and replanning in the Planning Plane once safety is restored.
- **Mitigation:** Clear arbitration result state logs enable the Planning Plane to resume or replan tasks gracefully once safety locks are released.
