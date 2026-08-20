# ORION Hardware Procurement Specification
## Phase 7 — W7-1
## Date: August 20, 2026
## Status: DRAFT — Pending Founder Approval (Section 3A)

---

## ⚠️ GATE: Section 3A (Founder Money Approval)

This document specifies hardware for procurement. **No purchase will be made until the Founder explicitly approves the budget.** This is a specification document only.

---

## 1. System Overview

ORION Tier B hardware platform — hybrid local compute for real-time safety enforcement, cognitive processing, and simulation. Designed for hardware-in-the-loop testing and eventual physical deployment.

## 2. Component Specifications

### 2.1 GPU (Select ONE configuration)

**Option A: Dual GPU (Recommended for parallelism)**
| Spec | Value |
|------|-------|
| Model | NVIDIA RTX 5090 |
| VRAM | 32GB GDDR7 per GPU (64GB total) |
| Quantity | 2 |
| Interface | PCIe 5.0 x16 |
| Power | 575W TDP per GPU |
| Purpose | Inference, vision processing, embeddings |
| Est. Cost | ~$2,000-$2,500 per unit |

**Option B: Single GPU (Recommended for larger model support)**
| Spec | Value |
|------|-------|
| Model | NVIDIA RTX 6000 Ada |
| VRAM | 48GB GDDR6 |
| Quantity | 1 |
| Interface | PCIe 5.0 x16 |
| Power | 300W TDP |
| Purpose | Inference, vision processing, embeddings |
| Est. Cost | ~$4,500-$6,800 |

**Recommendation:** Option A (2× RTX 5090) for Phase 7 HIL testing (better parallelism for multi-domain simulation). Option B for production (single large model inference).

### 2.2 CPU
| Spec | Value |
|------|-------|
| Model | AMD Threadripper Pro 7995WX |
| Cores | 96 cores / 192 threads |
| Base Clock | 2.5 GHz |
| Boost Clock | 5.1 GHz |
| Socket | sTR5 |
| TDP | 350W |
| Purpose | Safety enforcement (dedicated cores), general compute |
| Est. Cost | ~$9,999 |

### 2.3 Motherboard
| Spec | Value |
|------|-------|
| Socket | sTR5 (WRX90 chipset) |
| PCIe Slots | 2× PCIe 5.0 x16 (for dual GPU) |
| Memory Slots | 8× DDR5 ECC RDIMM |
| Networking | 10GbE onboard |
| Est. Cost | ~$1,000-$1,500 |

### 2.4 Memory
| Spec | Value |
|------|-------|
| Type | DDR5 ECC RDIMM |
| Capacity | 256GB (4× 64GB or 8× 32GB) |
| Speed | 5600 MHz |
| Est. Cost | ~$2,000-$3,000 |

### 2.5 Storage
| Spec | Value |
|------|-------|
| Primary | 2TB NVMe Gen5 (PostgreSQL + pgvector, OS) |
| Secondary | 4TB NVMe Gen4 (audit logs, backups, datasets) |
| Est. Cost | ~$300 + $250 |

### 2.6 Power
| Spec | Value |
|------|-------|
| PSU | 1600W 80+ Titanium (minimum for dual GPU) |
| UPS | 1500VA double-conversion online UPS |
| Est. Cost | ~$400 + $600 |

### 2.7 Safety Hardware
| Component | Purpose | Est. Cost |
|-----------|---------|-----------|
| Physical E-stop button (mushroom head, latching) | Emergency power cutoff | $50 |
| Safety relay module (force-guided contacts) | E-stop circuit implementation | $200 |
| Hardware watchdog timer (independent) | Watchdog timeout (200ms) | $150 |
| GPIO interface board | Connect E-stop and watchdog to ORION | $100 |
| Thermal sensors (multiple) | Temperature monitoring | $100 |

### 2.8 Chassis & Cooling
| Component | Purpose | Est. Cost |
|-----------|---------|-----------|
| Full tower workstation chassis | House all components | $300 |
| Liquid cooling (CPU + GPU) | Thermal management under load | $500 |
| Additional case fans (Noctua) | Airflow for dual GPU | $100 |

### 2.9 Domain-Specific Test Equipment (HIL)
| Component | Domain | Purpose | Est. Cost |
|-----------|--------|---------|-----------|
| USB camera array (3×) | All | Vision sensor input | $300 |
| IMU module (MPU-9250) | Drone/Vehicle | Inertial measurement | $50 |
| Pressure sensor module | Industrial | Pressure sensing | $100 |
| Temperature sensor (DS18B20) | Industrial/Drone | Temperature monitoring | $30 |
| Relay module (8-channel) | Smart Home | Appliance control | $50 |
| Servo motor + controller | Industrial/Drone | Actuator testing | $200 |
| LED + resistor array | Vehicle | Light control testing | $50 |
| USB GPS module | Drone/Vehicle | GPS sensor | $100 |

## 3. Budget Summary

| Category | Low Estimate | High Estimate |
|----------|--------------|---------------|
| GPU (Option A: 2× RTX 5090) | $4,000 | $5,000 |
| CPU (Threadripper Pro) | $9,999 | $9,999 |
| Motherboard | $1,000 | $1,500 |
| Memory (256GB ECC) | $2,000 | $3,000 |
| Storage (NVMe) | $550 | $600 |
| Power (PSU + UPS) | $1,000 | $1,200 |
| Safety Hardware | $600 | $700 |
| Chassis & Cooling | $900 | $1,000 |
| HIL Test Equipment | $880 | $1,100 |
| **TOTAL** | **$20,929** | **$24,099** |

**Alternative (Option B GPU):** Add ~$2,000 to GPU line for RTX 6000 Ada single configuration.

## 4. Vendor Recommendations

- GPU: NVIDIA direct or authorized reseller
- CPU: AMD direct or authorized distributor
- Other components: Standard hardware retailers (Newegg, Amazon, Mouser for safety components)
- HIL sensors: Adafruit, SparkFun, or direct from manufacturer

## 5. Lead Times

| Component | Est. Lead Time |
|-----------|----------------|
| GPU (RTX 5090) | 1-2 weeks (in stock) |
| CPU (Threadripper Pro) | 1-3 weeks |
| Memory | 1 week |
| Storage | 1 week |
| Safety hardware | 1-2 weeks |
| HIL sensors | 1 week |

**Estimated total lead time: 2-4 weeks** (CPU and GPU are the longest leads)

## 6. Approval Required

Per Constitution Section 3A, the Founder must approve:
- [ ] Total budget ($20,929 - $24,099)
- [ ] GPU configuration (Option A: dual RTX 5090 vs Option B: single RTX 6000 Ada)
- [ ] Vendor selection
- [ ] Purchase timing

No order will be placed until all items are checked.
