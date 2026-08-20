# ORION Phase 6 Specification
## Physical Deployment Preparation & Safety Certification
## Version: 1.0-DRAFT
## Date: August 20, 2026
## Author: ORION Supervisor
## Status: DRAFT — Pending Luna Review & Founder Approval

---

## 1. Objective

Phase 6 prepares ORION for the transition from simulation-only operation to controlled physical deployment. This phase produces **documentation, checklists, and risk assessments only** — no physical hardware is purchased, connected, or activated. Actual physical deployment remains gated behind Founder approval of this phase's deliverables.

## 2. Scope

### In Scope
- Safety Layer certification checklist (paper-based, simulation-verified)
- Hardware compatibility verification plan (Tier B: 2× RTX 5090 or 1× RTX 6000 Ada)
- Emergency shutdown procedure documentation
- Risk assessment matrix for physical deployment
- Regulatory compliance preliminary review
- Deployment architecture for hardware-in-the-loop (HIL) testing
- Safety Layer v3 specification (formal verification on physical hardware)

### Out of Scope
- Purchasing hardware (requires Founder money approval — Section 3A)
- Connecting to physical equipment (requires separate Founder approval — Section 3C)
- Regulatory filing or legal commitments (Section 3B)
- Any action that could cause physical harm

---

## 3. Work Items

### W6-1: Safety Certification Checklist
**Deliverable:** `docs/SAFETY_CERTIFICATION_CHECKLIST.md`

Comprehensive checklist covering:
- [ ] CBF forward invariance verified on target hardware
- [ ] Emergency cascade completeness tested with real latency measurements
- [ ] Hardware E-stop response time < 100ms (simulated target)
- [ ] Independence requirements (IND-1 through IND-10) verified for physical deployment
- [ ] Power loss recovery procedure documented and tested in simulation
- [ ] Watchdog heartbeat timeout calibrated for hardware latency
- [ ] All 6 formal verification properties hold under hardware-in-the-loop conditions
- [ ] Audit log hash chain integrity verified under concurrent physical events
- [ ] Cross-domain arbitration priority ordering verified with real sensor data
- [ ] Battery threshold monotonicity verified for drone domain with physical battery model

### W6-2: Hardware Compatibility Verification Plan
**Deliverable:** `docs/HARDWARE_COMPATIBILITY_PLAN.md`

- Tier B hardware specification validation
  - GPU: 2× RTX 5090 32GB or 1× RTX 6000 Ada 48GB
  - CPU: Threadripper Pro
  - RAM: 256GB ECC
  - Storage: NVMe for PostgreSQL + embeddings
- Software stack compatibility
  - CUDA version compatibility with asyncpg/pgvector
  - Docker containerization for isolation
  - Real-time kernel considerations for safety enforcement
- Performance projections
  - Inference latency targets (GPT-4o API + local fallback)
  - CBF filter latency on target hardware (< 1ms target)
  - Memory retrieval latency with pgvector on NVMe
- HIL testing architecture
  - Simulated sensors → ORION → Simulated actuators
  - Gradual replacement: simulated → physical, one component at a time

### W6-3: Emergency Shutdown Procedures
**Deliverable:** `docs/EMERGENCY_SHUTDOWN_PROCEDURES.md`

- Normal shutdown sequence
- Emergency shutdown sequence (E-stop triggered)
- Power loss recovery procedure
- Watchdog timeout handling
- Graceful degradation modes
- Per-domain emergency procedures:
  - Industrial: E-stop, depressurize, lock actuators
  - Vehicle: Brake to stop, hazard lights, disengage autopilot
  - Drone: Controlled descent, motor cutoff, parachute deployment
  - Smart Home: Safe state (off), unlock doors for egress
- Communication failure procedures
- Partial system failure procedures

### W6-4: Risk Assessment Matrix
**Deliverable:** `docs/RISK_ASSESSMENT_MATRIX.md`

Risk categories:
1. **Physical harm to humans** — Severity: Critical, Probability: Low (mitigated by CBF)
2. **Equipment damage** — Severity: High, Probability: Low (mitigated by E-stop)
3. **Data loss/corruption** — Severity: Medium, Probability: Very Low (mitigated by hash chain)
4. **Software malfunction** — Severity: High, Probability: Medium (mitigated by testing)
5. **Communication failure** — Severity: Medium, Probability: Medium (mitigated by fallbacks)
6. **Power failure** — Severity: High, Probability: Low (mitigated by UPS + recovery)
7. **Adversarial input** — Severity: High, Probability: Low (mitigated by poisoning resistance)
8. **GPU failure** — Severity: Medium, Probability: Low (mitigated by fallback to CPU)
9. **Network unavailability** — Severity: Low, Probability: Medium (mitigated by local models)
10. **Concurrency race condition** — Severity: Medium, Probability: Very Low (mitigated by testing)

Each risk includes:
- Description
- Severity (1-5)
- Probability (1-5)
- Risk score (Severity × Probability)
- Mitigation strategy
- Residual risk
- Verification method

### W6-5: Regulatory Compliance Preliminary Review
**Deliverable:** `docs/REGULATORY_PRELIMINARY_REVIEW.md`

- Domain-specific regulatory frameworks:
  - Automotive: ISO 26262 (functional safety), UN ECE R157 (automated lane keeping)
  - Drone: EASA Open/Specific category, FAA Part 107
  - Industrial: ISO 13849 (safety of machinery), IEC 62061
  - Smart Home: GDPR (data), IEC 60335 (household appliances)
- Cross-cutting: EU AI Act compliance framework
- NOTE: This is a preliminary review only. Legal decisions require Founder (Section 3B).

### W6-6: Safety Layer v3 Specification
**Deliverable:** `docs/SAFETY_LAYER_V3_SPEC.md`

- Extension of Safety Layer v2 (formally verified in Phase 4) for physical hardware
- Hardware-in-the-loop verification protocol
- Real-time constraint specification (< 1ms CBF filter, < 100ms E-stop)
- Sensor fusion safety requirements
- Actuator command validation pipeline
- Physical watchdog implementation specification
- Safety certification evidence collection framework

---

## 4. Safety Considerations

**CRITICAL:** Phase 6 produces documentation and plans ONLY. No physical actions.

- All work items are paper-based or simulation-extended
- No hardware purchases (Section 3A gate)
- No physical connections (Section 3C gate)
- No regulatory filings (Section 3B gate)
- Safety Layer v3 spec describes requirements but does not implement physical code

## 5. Dependencies

- All Phase 1-5 deliverables (complete)
- No new software dependencies
- No new hardware (planning only)

## 6. Success Criteria

- All 6 work items produce deliverable documents
- Luna reviews and approves the Phase 6 package
- Founder reviews and approves the safety certification checklist
- Risk assessment matrix covers all 10 risk categories
- Emergency shutdown procedures cover all 4 domains
- No physical actions taken without separate Founder approval

## 7. Estimated Effort

| Work Item | Type | Est. Output |
|-----------|------|-------------|
| W6-1: Safety Checklist | Documentation | ~200 lines |
| W6-2: Hardware Plan | Documentation + simulation tests | ~300 lines |
| W6-3: Emergency Procedures | Documentation | ~400 lines |
| W6-4: Risk Assessment | Documentation | ~300 lines |
| W6-5: Regulatory Review | Documentation | ~500 lines |
| W6-6: Safety Layer v3 Spec | Documentation | ~400 lines |

## 8. Post-Phase 6 Gates

After Phase 6 documentation is approved:
1. Founder approves hardware purchase (money gate — Section 3A)
2. Founder approves physical deployment (physical risk gate — Section 3C)
3. Luna approves Safety Layer v3 implementation
4. Regulatory compliance review by legal counsel (legal gate — Section 3B)
5. Only then: Phase 7 — Physical Deployment Execution

---

## Architecture Decision Log

### AD-6.1: Documentation-only Phase 6
**Decision:** Phase 6 produces plans and checklists only, no physical actions.
**Reason:** Constitution Section 3C requires explicit Founder approval before any physical risk. Phase 6 prepares the evidence for that approval decision.
**Date:** August 20, 2026

### AD-6.2: HIL testing as intermediate step
**Decision:** Hardware-in-the-loop (HIL) testing as intermediate step between simulation and full deployment.
**Reason:** Gradual replacement of simulated components with physical ones allows isolation of failure modes.
**Date:** August 20, 2026

### AD-6.3: Per-domain emergency procedures
**Decision:** Each domain gets its own emergency shutdown procedure.
**Reason:** Physical actuation differs fundamentally across domains (brakes vs motors vs actuators). Generic procedures are insufficient for physical safety.
**Date:** August 20, 2026
