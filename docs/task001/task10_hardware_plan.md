# ORION TASK 001 — TASK 10: Hardware Plan

## Stages

```
DIGITAL → SIMULATION → VIRTUAL ROBOT → VIRTUAL VEHICLE → VIRTUAL DRONE → HIL → CONTROLLED HARDWARE → REAL-WORLD VALIDATION
```

## Current State (VERIFIED FACT)

ORION has completed stages 1-2:
- ✅ DIGITAL — All code, reasoning, memory, planning in digital environment
- ✅ SIMULATION — 4 domain simulators (industrial, vehicle, drone, home) with physics models
- ✅ VIRTUAL ROBOT — Industrial simulation with machine models
- ✅ VIRTUAL VEHICLE — Vehicle simulation with kinematics, collision avoidance (CBF)
- ✅ VIRTUAL DRONE — Drone simulation with altitude, battery, thrust dynamics
- ✅ VIRTUAL HOME — Home simulation with temperature, lights, door locks

Remaining: HIL → Controlled Hardware → Real-World Validation

## Stage Details

### Stage 1: DIGITAL (✅ COMPLETE)
- **Requirements:** Computer, Python, OpenAI API access
- **Risks:** None (pure code)
- **Current status:** 463 tests, 8/11 phases complete

### Stage 2: SIMULATION (✅ COMPLETE)
- **Requirements:** Same as Stage 1
- **Risks:** None (simulated environment)
- **Current status:** 4 domain simulators, World Model, Safety Layer

### Stage 3: VIRTUAL ROBOT/VEHICLE/DRONE (✅ COMPLETE)
- **Requirements:** Same as Stage 1
- **Risks:** None (virtual environments)
- **Current status:** All 4 virtual domains working with safety verification

### Stage 4: HARDWARE-IN-THE-LOOP (HIL) — BLOCKED (Founder decision)

**Requirements:**
- Tier B hardware (approved by Founder, purchase deferred):
  - 2× RTX 5090 32GB OR 1× RTX 6000 Ada 48GB
  - Threadripper Pro
  - 256GB ECC RAM
- Optional: Real sensors for data input
- Optional: Single-board computer (Raspberry Pi/Jetson) for edge testing

**What HIL tests:**
- Real sensor data → ORION processing → simulated actuation
- ORION commands → hardware interface → real actuator → sensor feedback
- Latency between ORION decisions and hardware response
- Safety gateway with real device constraints

**Risks:**
- Hardware malfunction (mitigated: test bench, no real-world deployment)
- Cost (mitigated: Founder approval required)
- Compatibility (mitigated: HAL isolates ORION from specific hardware)

**Hardware compatibility plan (from Phase 6):**
- Tier B: hybrid local + cloud
- HIL phases: A (sim+interface), B (bench), C (controlled environment), D (pilot), E (deployment)

### Stage 5: CONTROLLED HARDWARE — BLOCKED

**Requirements:**
- Physical robot/vehicle/drone in controlled environment
- Safety cage / test track / tethered flight area
- Emergency stop hardware (physical, independent of ORION)
- Human operator with kill switch

**What controlled hardware tests:**
- ORION's ability to control a real device
- Safety gateway with real physics (not simulated)
- Sensor noise and real-world imperfections
- Response time with real actuators

**Risks:**
- Physical damage to equipment (mitigated: controlled environment, low speeds)
- Injury (mitigated: safety cage, human operator, E-stop, tethered operation)
- Fire/electrical (mitigated: fire suppression, electrical isolation)

**Safety requirement:** Independent safety system (not ORION) must be able to stop all hardware.

### Stage 6: REAL-WORLD VALIDATION — BLOCKED

**Requirements:**
- Approved test site
- Regulatory compliance (varies by domain)
- Insurance/liability coverage
- Human supervisor present
- Full safety checklist completed (from Phase 6: 55 items, 29 verified)

**What real-world validation tests:**
- ORION in real traffic / factory / home / outdoor drone flight
- Unpredictable events (weather, other actors, equipment failure)
- Long-duration reliability (24/7 operation)
- Regulatory compliance

**Risks:**
- Accident causing injury or property damage
- Regulatory violation
- Public perception / privacy concerns
- System failure in uncontrolled environment

**Safety requirements:**
- Full Safety Layer v3 approval (Luna)
- Regulatory review (legal counsel)
- Founder approval (strategic decision)
- Insurance coverage
- Human supervisor with override capability

## Hardware Acquisition Plan

| Phase | Hardware | Cost (est.) | Approval |
|-------|----------|-------------|----------|
| HIL setup | Tier B workstation + sensors | $5,000-8,000 | Founder (FINANCIAL) |
| Industrial HIL | PLC + sensors + test bench | $2,000-5,000 | Founder (FINANCIAL) |
| Vehicle HIL | Simulator rig or RC vehicle | $1,000-3,000 | Founder (FINANCIAL) |
| Drone HIL | PX4 flight controller + frame | $500-2,000 | Founder (FINANCIAL) |
| Home HIL | Matter/Thread devices | $200-500 | Founder (FINANCIAL) |
| Controlled hardware | Test environment setup | $5,000-20,000 | Founder (FINANCIAL) |

**Total estimated: $13,700-38,500** — all requires Founder approval.

## Domain Priority for HIL

Founder deferred domain priority. Recommended order (based on risk and value):
1. **Industrial** — lowest risk (controlled factory environment), highest commercial value
2. **Home** — low risk (limited physical danger), mass market potential
3. **Drone** — medium risk (can start tethered), good test of spatial reasoning
4. **Vehicle** — highest risk (public roads), requires regulatory approval

## Classification

- Stages 1-3: VERIFIED FACT (complete)
- Stages 4-6: BLOCKED (Founder decision — hardware deferred)
- All hardware spending: REQUIRES FOUNDER APPROVAL (financial boundary)
- Safety: independent safety system required for all physical stages
