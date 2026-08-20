# ORION Hardware Compatibility Verification Plan
## Phase 6 — W6-2
## Date: August 20, 2026
## Status: DRAFT

---

## 1. Target Hardware (Tier B — Founder Approved)

| Component | Specification | Quantity | Purpose |
|-----------|--------------|----------|---------|
| GPU | RTX 5090 32GB OR RTX 6000 Ada 48GB | 2× or 1× | Inference, vision processing, embeddings |
| CPU | AMD Threadripper Pro | 1× | General compute, safety enforcement, I/O |
| RAM | 256GB ECC DDR5 | — | Model loading, PostgreSQL cache, simulation |
| Storage | 2TB NVMe Gen5 | 1× | PostgreSQL + pgvector, OS, models |
| Storage | 4TB NVMe Gen4 | 1× | Audit logs, backups, datasets |
| Network | 10GbE | — | API calls, remote monitoring |
| UPS | 1500VA double-conversion | 1× | Power failure grace period |

## 2. Software Stack Compatibility

### 2.1 GPU Stack
- CUDA 12.x compatible with selected GPU
- PyTorch 2.x with CUDA support (for future local model inference)
- asyncpg + pgvector on CUDA-accelerated PostgreSQL (optional)
- Docker with NVIDIA Container Toolkit for GPU passthrough

### 2.2 Safety Stack
- Safety Enforcement Plane on dedicated CPU core (real-time priority)
- CBF computation on CPU (deterministic latency, no GPU dependency for safety)
- Hardware E-stop on separate GPIO circuit (not dependent on software)
- Watchdog timer on hardware timer (not software-emulated)

### 2.3 Data Stack
- PostgreSQL 16 with pgvector extension
- Docker Compose for service isolation
- asyncpg connection pool (min 1, max 10 connections)
- NVMe for low-latency vector search

### 2.4 Compatibility Matrix

| Component | Version | License | Hardware Compatible | Notes |
|-----------|---------|---------|---------------------|-------|
| CUDA | 12.x | CUDA EULA | ✅ RTX 5090/6000 Ada | Check specific driver version |
| asyncpg | 0.29+ | BSD (Apache 2.0 compat) | ✅ CPU-only | No GPU dependency |
| pgvector | 0.7+ | PostgreSQL License | ✅ CPU + optional GPU | Vector search acceleration |
| Docker | 24+ | Apache 2.0 | ✅ | Container isolation |
| Python | 3.11+ | PSF | ✅ | All ORION code |
| PostgreSQL | 16 | PostgreSQL License | ✅ | Primary database |

## 3. Performance Projections

### 3.1 Safety Enforcement (CPU, real-time)
| Operation | Simulation (current) | Target (hardware) | Constraint |
|-----------|---------------------|-------------------|------------|
| CBF velocity filter | ~8µs | < 50µs | < 1ms hard limit |
| CBF force filter | ~5µs | < 50µs | < 1ms hard limit |
| Cross-domain arbitration | ~15µs | < 100µs | < 5ms hard limit |
| Emergency cascade | < 1ms (sim) | < 10ms (hardware) | < 100ms hard limit |
| E-stop trigger | simulated | < 50ms (physical) | < 100ms hard limit |

### 3.2 Cognitive Plane (GPU + API)
| Operation | Simulation (current) | Target (hardware) | Constraint |
|-----------|---------------------|-------------------|------------|
| GPT-4o reasoning call | ~500ms (API) | ~500ms (API) | < 2s soft limit |
| Embedding generation | ~100ms (API) | ~100ms (API) | < 500ms soft limit |
| Vector search (pgvector) | N/A (Python fallback) | < 10ms (NVMe) | < 50ms soft limit |
| Memory store + hash | ~900µs (SQLite) | < 500µs (PostgreSQL) | < 5ms soft limit |

### 3.3 Simulation (CPU + GPU)
| Operation | Simulation (current) | Target (hardware) | Constraint |
|-----------|---------------------|-------------------|------------|
| Industrial sim step | < 10ms | < 5ms | 100ms cycle |
| Vehicle sim step | < 10ms | < 5ms | 50ms cycle |
| Drone sim step | < 10ms | < 5ms | 20ms cycle |
| Home sim step | < 10ms | < 5ms | 1000ms cycle |

## 4. Hardware-in-the-Loop (HIL) Testing Architecture

### 4.1 HIL Phases

**Phase A: Pure Simulation (COMPLETE)**
- All sensors simulated
- All actuators simulated
- Safety layer verified in software-only environment
- 198 tests passing

**Phase B: Software-in-the-Loop (SIL)**
- ORION runs on target hardware (Tier B)
- Sensors still simulated (software-generated data)
- Actuators still simulated (software receives commands)
- Verify: performance targets met, no resource constraints, latency within bounds
- Exit criteria: All performance projections validated

**Phase C: Sensor-in-the-Loop**
- Real sensors connected (cameras, IMU, LiDAR, temperature, pressure)
- Actuators still simulated
- Verify: sensor data validation, fusion, poisoning resistance
- Exit criteria: Sensor pipeline validated, data integrity confirmed

**Phase D: Actuator-in-the-Loop**
- Sensors from Phase C
- Real actuators connected (motors, brakes, relays) — in controlled environment
- Verify: CBF filtering on real actuator commands, E-stop response time
- Exit criteria: Physical safety verified, E-stop < 100ms

**Phase E: Full HIL**
- All real sensors and actuators
- Safety observer present (human with physical E-stop)
- Controlled environment (test track, lab, isolated room)
- Exit criteria: All safety procedures validated, full operation for 24h without incident

### 4.2 HIL Safety Requirements
- Human safety observer with physical E-stop button at all times during Phase D-E
- All testing in controlled, isolated environment
- Maximum speed/force/power limited to 25% of operational limits during testing
- All test sessions time-limited (max 4 hours without review)
- All events logged to audit trail
- Emergency procedures rehearsed before each session

## 5. Verification Checklist

- [ ] Target hardware procured (Founder approval required — Section 3A)
- [ ] CUDA drivers installed and verified
- [ ] Docker + NVIDIA Container Toolkit configured
- [ ] PostgreSQL 16 + pgvector deployed on NVMe
- [ ] All 198 existing tests pass on target hardware
- [ ] Performance benchmarks run on target hardware
- [ ] CBF latency < 1ms on target hardware
- [ ] E-stop response < 100ms with physical button
- [ ] Watchdog timer configured on hardware timer
- [ ] UPS grace period verified (>= 10 minutes)
- [ ] Thermal monitoring operational
- [ ] Network redundancy configured (if required)
- [ ] Safety observer trained and present for HIL phases D-E
