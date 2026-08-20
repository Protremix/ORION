# ORION Safety Layer v3 Specification
## Phase 6 — W6-6
## Date: August 20, 2026
## Status: DRAFT — Specification Only (No Implementation)

---

## 1. Overview

Safety Layer v3 extends the formally-verified Safety Layer v2 (Phase 4) to support physical hardware deployment. It adds hardware-in-the-loop verification, real-time constraints, sensor fusion safety, and physical watchdog support while preserving all v2 properties.

### Relationship to v2

| Property | v2 (Simulation) | v3 (Physical) |
|----------|-----------------|---------------|
| CBF forward invariance | Mathematically proven | Proven + verified on hardware |
| CBF filter correctness | Mathematically proven | Proven + latency-bounded |
| Emergency cascade | Software-only | Software + hardware E-stop |
| Priority ordering | Proven | Proven + sensor-aware |
| Audit hash chain | Proven | Proven + tamper-evident storage |
| Battery threshold | Proven | Proven + physical battery model |
| **NEW: Real-time bounds** | N/A | < 1ms CBF, < 100ms E-stop |
| **NEW: Sensor validation** | N/A | All sensor inputs validated |
| **NEW: Actuator verification** | N/A | All actuator commands verified |
| **NEW: Physical watchdog** | N/A | Hardware timer, independent |

## 2. Real-Time Constraints

### 2.1 Hard Real-Time (must never exceed)
| Operation | Constraint | Rationale |
|-----------|-----------|-----------|
| CBF filter computation | < 1ms | Control loop frequency requires deterministic filtering |
| E-stop trigger (software) | < 10ms | Emergency must propagate faster than physical damage |
| E-stop trigger (hardware) | < 100ms | Physical E-stop button to actuator power cutoff |
| Emergency cascade | < 10ms | All domains must enter safe state simultaneously |
| Watchdog heartbeat check | < 5ms | Detect failure before uncontrolled action |

### 2.2 Soft Real-Time (should not exceed)
| Operation | Constraint | Rationale |
|-----------|-----------|-----------|
| Sensor data validation | < 50ms | Sensor data must be fresh for safety decisions |
| Cross-domain arbitration | < 5ms | Inter-domain conflicts must be resolved quickly |
| Audit log entry | < 5ms | Safety events must be recorded without blocking |
| Memory retrieval | < 50ms | Cognitive decisions need context promptly |

## 3. Sensor Fusion Safety

### 3.1 Sensor Validation Pipeline
```
Raw Sensor Data
      ↓
  [Range Check] — values within physical plausibility
      ↓
  [Rate Check] — update frequency within expected bounds
      ↓
  [Consistency Check] — cross-sensor consistency (e.g., IMU vs GPS)
      ↓
  [Poisoning Check] — anomaly detection against historical patterns
      ↓
  [Confidence Score] — weighted by sensor reliability
      ↓
  Validated Sensor Data → Safety Enforcement Plane
```

### 3.2 Sensor Failure Modes
| Failure Mode | Detection | Response |
|-------------|-----------|----------|
| Sensor offline (no data) | Timeout > 3× expected update rate | Fallback to redundant sensor or safe state |
| Sensor stuck (same value) | Consecutive identical readings > threshold | Flag as suspect, cross-check, degrade |
| Sensor drifting | Calibration check against reference | Recalibrate or flag for maintenance |
| Sensor spoofed | Anomaly detection (statistical) | Reject data, enter safe state, audit log |
| Sensor noisy | Signal-to-noise ratio check | Apply Kalman filter or reject if too noisy |

### 3.3 Redundancy Requirements
- Safety-critical sensors: minimum 2 independent sources
- Cross-domain sensors: 1 primary + 1 secondary from different modality
- E-stop: 1 physical button + 1 software command + 1 watchdog timeout

## 4. Actuator Command Verification

### 4.1 Command Validation Pipeline
```
Cognitive Plane Output
      ↓
  [CBF Filter] — Control Barrier Function constraint check
      ↓
  [Rate Limit] — Maximum rate of change enforcement
      ↓
  [Range Limit] — Physical actuator limits (force, speed, position)
      ↓
  [Authority Check] — Safety Enforcement Plane has authority?
      ↓
  [Audit Log] — Record command with hash chain
      ↓
  Verified Command → Actuator
```

### 4.2 Actuator Safety Constraints
| Domain | Constraint | Value | Enforcement |
|--------|-----------|-------|-------------|
| Industrial | Max force | Domain-specific | ForceLimitCBF |
| Industrial | E-stop | Immediate power cutoff | Hardware relay |
| Vehicle | Max velocity | Domain-specific | VelocityLimitCBF |
| Vehicle | Min braking distance | Calculated | VelocityLimitCBF |
| Drone | Max altitude | Domain-specific | SpatialKeepOutCBF |
| Drone | Min battery for return | 20% | BatteryThreshold |
| Smart Home | Max power per circuit | Domain-specific | ForceLimitCBF |
| Smart Home | Emergency unlock | On E-stop | Safe state |

## 5. Physical Watchdog

### 5.1 Hardware Watchdog Timer
- Independent hardware timer (not software-emulated)
- Timeout: 200ms (10× CBF loop time)
- Reset: Heartbeat from Safety Enforcement Plane every 100ms
- Action on timeout: Hardware E-stop (power cutoff to all actuators)

### 5.2 Software Watchdog (Defense in Depth)
- Monitors Safety Enforcement Plane thread
- Timeout: 500ms
- Action: Software emergency cascade + alert
- Does NOT replace hardware watchdog

### 5.3 Watchdog Hierarchy
```
Hardware Watchdog (200ms) → Physical E-stop → Power cutoff
       ↑ monitored by
Software Watchdog (500ms) → Emergency cascade → Safe state
       ↑ monitored by
Safety Enforcement Plane → CBF filters → Actuator commands
       ↑ monitored by
Cognitive Plane → Reasoning → Planning
```

## 6. Safety Layer v3 Verification Requirements

### 6.1 Properties to Verify (extends v2's 6 properties)

**Property 7: Real-Time Boundedness**
- CBF filter computation completes within 1ms on target hardware
- E-stop propagation completes within 100ms (hardware path)
- Verification: HIL measurement with oscilloscope/logic analyzer

**Property 8: Sensor Validation Completeness**
- All sensor inputs pass through 5-stage validation pipeline
- No raw sensor data reaches Safety Enforcement Plane without validation
- Verification: Code audit + fuzz testing with invalid sensor data

**Property 9: Actuator Command Safety**
- All actuator commands pass through CBF filter + range/rate limits
- No unfiltered command reaches any physical actuator
- Verification: HIL testing with actuator command interception

**Property 10: Watchdog Independence**
- Hardware watchdog operates independently of software
- Software crash does not disable hardware watchdog
- Verification: Deliberate software crash + verify hardware E-stop fires

**Property 11: Graceful Degradation**
- Loss of any single sensor does not cause unsafe action
- Loss of any single domain does not affect other domains' safety
- Verification: Fault injection testing (remove sensors one at a time)

**Property 12: Physical Recovery**
- System can recover from power loss without entering unsafe state
- All actuators return to safe position on power restoration
- Verification: Power cycle test with actuator position monitoring

## 7. Implementation Note

This specification defines requirements only. Implementation requires:
1. Founder approval for hardware purchase (Section 3A)
2. Founder approval for physical deployment (Section 3C)
3. Luna approval of this specification
4. Safety certification checklist completion (W6-1)
5. HIL testing per hardware compatibility plan (W6-2)

No code for Safety Layer v3 should be written until items 1-5 are complete.
