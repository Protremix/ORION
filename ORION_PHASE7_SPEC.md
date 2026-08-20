# ORION Phase 7 Specification
## Physical Deployment Execution
## Version: 1.0-DRAFT
## Date: August 20, 2026
## Author: ORION Supervisor
## Status: DRAFT — Pending Luna Review & Founder Approval (Section 3A/3B/3C)

---

## ⚠️ GATE STATUS

**Phase 7 requires explicit Founder approval for:**
- **Section 3A:** Hardware purchase (real money)
- **Section 3B:** Regulatory/legal compliance review
- **Section 3C:** Physical deployment (physical risk)

**No physical action will be taken until ALL three gates are approved.**

---

## 1. Objective

Phase 7 executes the physical deployment plan prepared in Phase 6. This involves:
1. Procuring Tier B hardware
2. Installing and configuring the software stack on target hardware
3. Running hardware-in-the-loop (HIL) tests through 5 phases (A→E)
4. Verifying Safety Layer v3 properties on physical hardware
5. Gradual sensor and actuator integration
6. Safety certification sign-off

## 2. Prerequisites

All Phase 6 post-gate conditions must be met:
- [ ] Founder approves hardware budget (Section 3A)
- [ ] Legal counsel reviews regulatory compliance gaps (Section 3B)
- [ ] Founder approves physical deployment (Section 3C)
- [ ] Luna approves Safety Layer v3 implementation
- [ ] Safety certification checklist: all 55 items addressed (29 verified, 26 pending hardware)
- [ ] Hardware procurement specification finalized

## 3. Work Items

### W7-1: Hardware Procurement
**GATE: Section 3A (Founder money approval)**

- Finalize hardware specification
- Obtain quotes for Tier B components
  - 2× RTX 5090 32GB OR 1× RTX 6000 Ada 48GB
  - Threadripper Pro
  - 256GB ECC DDR5
  - 2TB NVMe Gen5 + 4TB NVMe Gen4
  - 10GbE network
  - 1500VA double-conversion UPS
  - Physical E-stop button + relay circuit
  - Hardware watchdog timer
- Founder approves purchase
- Order components
- Accept delivery and inventory check

### W7-2: System Assembly & Software Installation
**GATE: Section 3C (physical risk — but assembly in controlled lab)**

- Assemble hardware system
- Install OS (Linux, real-time kernel for safety enforcement)
- Install CUDA drivers
- Install Docker + NVIDIA Container Toolkit
- Install PostgreSQL 16 + pgvector on NVMe
- Deploy ORION codebase
- Run all 198 existing tests on target hardware
- Performance benchmarks on target hardware
- Verify: CBF latency < 1ms, vector search < 10ms

### W7-3: HIL Phase B — Software-in-the-Loop on Target Hardware
- ORION runs on Tier B hardware
- Sensors simulated (software-generated data)
- Actuators simulated (software receives commands)
- Verify: all performance projections met
- Verify: no resource constraints or thermal issues
- Run full test suite (198 tests + new Safety Layer v3 tests)
- Exit criteria: all performance targets validated on hardware

### W7-4: HIL Phase C — Sensor-in-the-Loop
**GATE: Section 3C (physical sensors connected)**

- Connect real sensors (cameras, IMU, temperature, pressure)
- Actuators still simulated
- Verify: sensor data validation pipeline (5-stage)
- Verify: sensor fusion consistency
- Verify: poisoning resistance with real sensor noise
- Verify: sensor failure detection (disconnect test)
- Exit criteria: sensor pipeline validated with real data

### W7-5: HIL Phase D — Actuator-in-the-Loop
**GATE: Section 3C (physical actuators in controlled environment)**

- Connect real actuators (motors, relays, brakes) in controlled lab
- Safety observer present with physical E-stop
- All actuators limited to 25% of operational limits
- Verify: CBF filtering on real actuator commands
- Verify: E-stop response time < 100ms (physical measurement)
- Verify: rate limiting, range limiting on physical actuators
- Verify: emergency shutdown procedures per domain
- Exit criteria: physical safety verified, E-stop < 100ms

### W7-6: HIL Phase E — Full Hardware-in-the-Loop
**GATE: Section 3C (full physical operation in controlled environment)**

- All real sensors and actuators
- Safety observer present at all times
- Controlled environment (test track / lab / isolated room)
- Maximum speed/force/power: 25% operational limits
- Run continuous operation test: 24 hours without incident
- Verify: all 12 formal verification properties hold on hardware
- Verify: emergency procedures for all 4 domains
- Verify: watchdog hierarchy (hardware + software)
- Verify: audit log hash chain integrity over 24h
- Exit criteria: 24h continuous operation, zero safety incidents

### W7-7: Safety Certification Sign-off
- Complete all 55 items on Safety Certification Checklist
- Luna reviews and approves physical deployment results
- Founder reviews and approves for operational use
- Legal counsel confirms regulatory compliance
- Issue Safety Certificate for ORION v1.0 (HIL-verified)

### W7-8: Documentation Update
- Update architecture documentation with hardware results
- Update performance benchmarks with real measurements
- Update risk assessment with verified mitigations
- Update regulatory compliance with confirmed status
- Finalize ORION v1.0 deployment documentation

## 4. Safety During Phase 7

### Hard Rules
- **Safety observer required** for all Phase D and E testing
- **Physical E-stop button** accessible at all times
- **25% operational limits** during all HIL testing
- **4-hour max sessions** without review break
- **All events logged** to audit trail
- **Emergency procedures rehearsed** before each session
- **Single-component-at-a-time** principle for gradual integration

### Escalation
- Any safety incident → immediate E-stop → stop all testing
- Incident report to Founder (Section 3C) and Luna
- Root cause analysis before resuming
- Founder approval required to resume testing after any incident

## 5. Estimated Timeline

| Work Item | Duration | Gate |
|-----------|----------|------|
| W7-1: Procurement | 2-4 weeks (shipping) | 3A |
| W7-2: Assembly & Install | 3-5 days | 3C |
| W7-3: HIL Phase B (SIL on HW) | 2-3 days | — |
| W7-4: HIL Phase C (Sensors) | 3-5 days | 3C |
| W7-5: HIL Phase D (Actuators) | 5-7 days | 3C |
| W7-6: HIL Phase E (Full HIL) | 1-2 days (24h test) | 3C |
| W7-7: Certification | 1-2 days | — |
| W7-8: Documentation | 1-2 days | — |

**Total estimated: 4-7 weeks** (dominated by hardware shipping)

## 6. Success Criteria

- All 55 safety certification checklist items verified
- All 12 formal verification properties hold on physical hardware
- E-stop response time < 100ms (measured)
- CBF filter latency < 1ms on target hardware (measured)
- 24-hour continuous operation without safety incident
- Luna approves physical deployment results
- Founder approves ORION v1.0 for operational use

## 7. Post-Phase 7

After Phase 7 completion:
- ORION v1.0 is HIL-verified and safety-certified
- Operational deployment decisions are Founder's (per domain, per location)
- Continuous monitoring via Phase 5 monitoring dashboard
- Regular safety audits per certification checklist
- Post-market monitoring per EU AI Act requirements
