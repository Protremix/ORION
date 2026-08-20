# ORION Regulatory Compliance Preliminary Review
## Phase 6 — W6-5
## Date: August 20, 2026
## Status: DRAFT — NOT LEGAL ADVICE

---

## ⚠️ IMPORTANT NOTICE

This document is a **preliminary technical review** conducted by the ORION Supervisor (AI agent). It is **NOT legal advice**. All regulatory and legal decisions require Founder approval (Constitution Section 3B) and should be reviewed by qualified legal counsel before any filing, submission, or public deployment.

---

## 1. Scope

This review identifies regulatory frameworks that may apply to ORION's physical deployment across its four domains: Industrial, Vehicle, Drone, and Smart Home. It maps ORION's existing safety architecture to regulatory requirements and identifies gaps.

## 2. Domain-Specific Regulatory Frameworks

### 2.1 Industrial Domain (SC-1)
| Framework | Scope | ORION Relevance | Current Status |
|-----------|-------|-----------------|----------------|
| ISO 13849 | Safety of machinery — safety-related parts of control systems | CBF-based safety enforcement maps to Performance Level (PL) requirements | Simulation verified; PL rating pending hardware |
| IEC 62061 | Functional safety of safety-related electrical/electronic control systems | Safety Enforcement Plane architecture designed for functional safety | Architecture aligned; certification pending |
| ISO 12100 | General principles for design — risk assessment and risk reduction | Risk Assessment Matrix (W6-4) maps to this standard | In progress (Phase 6) |
| OSHA 1910 | Occupational safety (US) | E-stop, lockout/tagout procedures | Emergency procedures documented (W6-3) |

### 2.2 Vehicle Domain (SC-2)
| Framework | Scope | ORION Relevance | Current Status |
|-----------|-------|-----------------|----------------|
| ISO 26262 | Road vehicles — functional safety | ASIL (Automotive Safety Integrity Level) classification needed | CBF architecture maps to ASIL D concepts |
| UN ECE R157 | Automated Lane Keeping Systems (ALKS) | If vehicle domain operates on public roads | N/A (simulation only) |
| NHTSA FMVSS | Federal Motor Vehicle Safety Standards (US) | If deployed in US market | N/A (simulation only) |
| SAE J3016 | Taxonomy of driving automation levels | ORION vehicle domain = Level 4 (full autonomous in ODD) | Architecture supports L4 |

### 2.3 Drone Domain (SC-2)
| Framework | Scope | ORION Relevance | Current Status |
|-----------|-------|-----------------|----------------|
| EASA Specific Category | European drone regulations — specific operations | If deployed in EU (Founder location: Europe/Madrid) | SORA (Specific Operations Risk Assessment) needed |
| FAA Part 107 | Small Unmanned Aircraft Systems (US) | If deployed in US | Remote Pilot Certificate required |
| EASA U-space | U-space airspace management | If operating in U-space airspace | Not applicable until deployment |
| ASTM F3322 | Standard for drone parachutes | Emergency parachute recovery system | CBF + parachute in emergency procedures |

### 2.4 Smart Home Domain (SC-3)
| Framework | Scope | ORION Relevance | Current Status |
|-----------|-------|-----------------|----------------|
| IEC 60335 | Household appliances safety | Smart home actuator control | Safety layer provides safe-state fallback |
| GDPR | General Data Protection Regulation (EU) | Memory system stores user data | Memory poisoning resistance + audit log |
| EU AI Act | Artificial Intelligence Act (EU) | ORION is a high-risk AI system | Compliance framework needed (see Section 3) |
| EN 303 645 | Cyber security for consumer IoT | Smart home communication security | Not yet implemented |

## 3. Cross-Cutting: EU AI Act Compliance

### 3.1 Risk Classification
ORION likely falls under **High-Risk AI System** (Annex III) due to:
- Safety components of products (industrial machinery, vehicles, aircraft)
- Potential to cause harm to persons

### 3.2 Key Requirements
| Requirement | ORION Status | Gap |
|-------------|-------------|-----|
| Risk management system | ✅ Risk Assessment Matrix (W6-4) | Continuous monitoring needed |
| Data governance | ✅ Memory poisoning resistance, audit trail | Training data provenance documentation |
| Technical documentation | ✅ Phase 1-5 documentation | Conformity assessment documentation |
| Record-keeping | ✅ Hash-chained audit log | Log retention policy (7 years) |
| Transparency | ✅ Safety Enforcement Plane decisions logged | User notification framework |
| Human oversight | ✅ Founder/Architect hierarchy | Physical emergency stop (pending hardware) |
| Accuracy, robustness, cybersecurity | ✅ Formal verification, CBF safety | Penetration testing (pending) |
| Post-market monitoring | ⏳ Monitoring dashboard (Phase 5) | Incident reporting procedure |

### 3.3 Compliance Path
1. Technical documentation file (Phase 6 contribution)
2. Conformity assessment (notified body — requires Founder legal approval)
3. CE marking (if deployed in EU)
4. Registration in EU database
5. Post-market monitoring system

**NOTE:** All steps require Founder legal approval (Section 3B). This review is preparatory only.

## 4. Identified Gaps

| Gap ID | Description | Domain | Severity | Mitigation |
|--------|-------------|--------|----------|-----------|
| GAP-1 | No ASIL classification for vehicle domain | Vehicle | High | Requires ISO 26262 analysis (post-hardware) |
| GAP-2 | No SORA for drone operations | Drone | High | Requires EASA-specific risk assessment |
| GAP-3 | No conformity assessment | All | High | Requires notified body + Founder approval |
| GAP-4 | No cybersecurity certification | All | Medium | EN 303 645 / IEC 62443 review needed |
| GAP-5 | No data protection impact assessment | Smart Home | Medium | GDPR DPIA needed before deployment |
| GAP-6 | No operator certification framework | All | Medium | Training program documentation needed |
| GAP-7 | No insurance/liability framework | All | High | Requires legal counsel + Founder approval |

## 5. Recommendations

1. **Do not deploy physically** until all HIGH severity gaps are addressed
2. **Engage legal counsel** for EU AI Act conformity assessment (Founder decision — Section 3B)
3. **Schedule ISO 26262 analysis** for vehicle domain (after hardware procurement)
4. **Complete SORA** for drone domain (after defining operational scenario)
5. **Implement cybersecurity framework** before any network-connected deployment
6. **Obtain liability insurance** before physical deployment (Founder decision — Section 3A/3B)

## 6. Disclaimer

This preliminary review was conducted by an AI agent (ORION Supervisor) based on publicly available regulatory information as of August 2026. Regulations change frequently. **No regulatory decision should be made based on this document alone.** All legal and regulatory decisions require Founder approval and qualified legal counsel.
