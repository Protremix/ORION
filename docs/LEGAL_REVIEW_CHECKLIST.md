# ORION Legal Review Checklist
## For Regulatory Compliance — Phase 7 Prerequisite
## Date: August 20, 2026
## Status: DRAFT — For Legal Counsel Review

---

## ⚠️ GATE: Section 3B (Founder Legal Approval)

This document was prepared by the ORION Supervisor (AI agent) as a preliminary technical review. It is **NOT legal advice**. The Founder must engage qualified legal counsel to review these items before any regulatory filing, public deployment, or legal commitment.

---

## 1. Purpose

To provide legal counsel with a structured checklist of regulatory compliance items identified during Phase 6 (W6-5: Regulatory Compliance Preliminary Review). Each item requires professional legal assessment.

## 2. Items Requiring Legal Review

### 2.1 EU AI Act Compliance
- [ ] Confirm ORION's classification as High-Risk AI System (Annex III)
- [ ] Review conformity assessment requirements
- [ ] Determine if notified body engagement is required
- [ ] Review CE marking requirements
- [ ] Review EU database registration requirements
- [ ] Review post-market monitoring obligations
- [ ] Review transparency requirements for users
- [ ] Review risk management system documentation requirements
- [ ] Review data governance requirements (training data, validation data)
- [ ] Review technical documentation file completeness

### 2.2 Industrial Domain (ISO 13849 / IEC 62061)
- [ ] Determine applicable Performance Level (PL) requirement
- [ ] Confirm Safety Integrity Level (SIL) classification
- [ ] Review CBF-based safety enforcement against PL/SIL requirements
- [ ] Review E-stop implementation against ISO 13850
- [ ] Confirm safety-related software requirements (IEC 61508-3)
- [ ] Review lockout/tagout procedures

### 2.3 Vehicle Domain (ISO 26262)
- [ ] Determine Automotive Safety Integrity Level (ASIL) classification
- [ ] Review CBF velocity/acceleration limits against ASIL requirements
- [ ] Review brake-to-stop procedure against safety standards
- [ ] Confirm ODD (Operational Design Domain) documentation
- [ ] Review UN ECE R157 applicability (if operating on public roads)
- [ ] Review NHTSA FMVSS applicability (if US deployment)
- [ ] Review SAE J3016 level classification (Level 4 autonomous)

### 2.4 Drone Domain (EASA / FAA)
- [ ] Confirm EASA category (Open / Specific / Certified)
- [ ] Complete SORA (Specific Operations Risk Assessment) if Specific category
- [ ] Review EASA U-space requirements (if applicable)
- [ ] Review FAA Part 107 compliance (if US deployment)
- [ ] Review parachute deployment system (ASTM F3322)
- [ ] Review geofencing requirements
- [ ] Confirm Remote Pilot Certification requirements

### 2.5 Smart Home Domain (GDPR / Consumer Safety)
- [ ] Complete Data Protection Impact Assessment (DPIA)
- [ ] Review GDPR Article 9 (special category data) applicability
- [ ] Review data retention policy (7-year audit log requirement vs GDPR minimization)
- [ ] Review user consent mechanisms
- [ ] Review data subject access rights implementation
- [ ] Review IEC 60335 compliance for smart home appliances
- [ ] Review EN 303 645 (IoT cybersecurity) compliance

### 2.6 Cross-Cutting Legal Items
- [ ] Review liability insurance requirements
- [ ] Review product liability framework (EU Product Liability Directive)
- [ ] Review software liability implications
- [ ] Review warranty and support obligations
- [ ] Review open-source license compliance (Apache 2.0, BSD, PostgreSQL License)
- [ ] Review export control requirements (GPU technology, AI models)
- [ ] Review data residency requirements (if EU deployment)
- [ ] Review incident reporting obligations (EU AI Act, domain-specific)
- [ ] Review supply chain due diligence requirements

## 3. Identified Gaps (from Phase 6 W6-5)

| Gap ID | Description | Severity | Legal Action Required |
|--------|-------------|----------|----------------------|
| GAP-1 | No ASIL classification for vehicle domain | High | ISO 26262 analysis by qualified engineer |
| GAP-2 | No SORA for drone operations | High | EASA-specific risk assessment |
| GAP-3 | No conformity assessment | High | Notified body engagement |
| GAP-4 | No cybersecurity certification | Medium | EN 303 645 / IEC 62443 review |
| GAP-5 | No DPIA for smart home | Medium | GDPR DPIA completion |
| GAP-6 | No operator certification framework | Medium | Training program documentation |
| GAP-7 | No insurance/liability framework | High | Insurance procurement + legal review |

## 4. Documents Provided for Legal Review

1. `docs/REGULATORY_PRELIMINARY_REVIEW.md` — Technical regulatory mapping
2. `docs/SAFETY_CERTIFICATION_CHECKLIST.md` — 55-item safety certification
3. `docs/RISK_ASSESSMENT_MATRIX.md` — 15+ risk categories
4. `docs/EMERGENCY_SHUTDOWN_PROCEDURES.md` — Per-domain emergency procedures
5. `docs/SAFETY_LAYER_V3_SPEC.md` — Safety layer specification
6. `ORION_ARCHITECTURE_V0.5.md` — System architecture
7. `docs/DEPENDENCY_LICENSE_REGISTRY.md` — Software dependency licenses

## 5. Recommendation

Engage legal counsel with expertise in:
- EU AI Act compliance
- Product liability (EU)
- Domain-specific safety regulations (ISO 26262, EASA, ISO 13849)
- GDPR/data protection
- Open-source license compliance

**Estimated legal review effort: 20-40 hours** (depending on counsel familiarity with AI systems)

## 6. Disclaimer

This checklist was prepared by an AI agent (ORION Supervisor) based on publicly available regulatory information as of August 2026. Regulations change frequently. **No legal decision should be made based on this document alone.** All legal decisions require Founder approval (Section 3B) and qualified legal counsel.
