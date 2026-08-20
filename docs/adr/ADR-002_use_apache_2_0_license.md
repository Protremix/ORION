# ADR-002: Use Apache 2.0 License for ORION-Owned Code

- **Decision ID:** ADR-002
- **Date:** 2026-08-20
- **Owner:** ORION Supervisor
- **Reversible?:** Yes (architecture decisions can be revised in future versions)

## Context
The ORION project is a Physical Intelligence OS. Hierarchy: Founder → Architect/Reviewer Luna (GPT-5.6) → ORION Supervisor → Specialized Agents. All work follows the lifecycle: Specification → Architecture → Implementation → Test → Verification → Review → Approval → Next Stage.

As an open-source Physical Intelligence OS intended for widespread deployment across commercial robotics OEMs, research institutions, and industrial automation partners, ORION requires a clear, permissive, and legally robust software license. The licensing strategy directly impacts enterprise adoption, hardware driver ecosystem contributions, and third-party commercial integration without creating copyleft compliance friction.

## Problem
Which open-source license should be adopted for all core ORION-owned software repositories, SDKs, and driver interfaces to maximize global commercial adoption while protecting contributors and users from patent litigation risks?

## Options
1. **MIT License:** Permissive, extremely concise, widely understood.
   - *Pros:* Minimal legal text, highly permissive.
   - *Cons:* Lacks an explicit, affirmative patent grant and patent retaliation clause, exposing enterprise integrators to patent litigation risks.
2. **GNU General Public License v3 (GPLv3) / AGPLv3:** Strong copyleft protection.
   - *Pros:* Forces all downstream derivative works and cloud services to open-source their code modifications.
   - *Cons:* Strictly rejected by commercial robotics OEMs (e.g. Unitree, Boston Dynamics, industrial automotive integrators) who cannot mix proprietary hardware control firmware with strong copyleft code.
3. **Apache License 2.0:** Permissive open-source license with explicit patent grants and contribution frameworks.
   - *Pros:* Grants explicit patent rights from contributors to users (Section 3), includes patent litigation defense/termination clauses, permits proprietary commercial derivative works, compatible with BSD/MIT dependencies.
   - *Cons:* Slightly longer legal text requiring notice retention in NOTICE files.

## Decision
Adopt the **Apache License 2.0** for all ORION-owned core source code repositories, APIs, SDKs, and documentation.

## Reason
Apache 2.0 strikes the optimal balance between openness and legal security for physical intelligence software. Section 3 of the Apache 2.0 License provides an explicit, irrevocable patent grant covering contributions, protecting commercial OEMs and developers from patent trolling. Furthermore, Apache 2.0 allows commercial vendors to build proprietary hardware adapters, domain skills, and commercial applications on top of the ORION Physical Intelligence OS without copyleft contamination.

## Evidence
- Legal review documented in `DEPENDENCY_LICENSE_REGISTRY.md` and `LEGAL_REVIEW_CHECKLIST.md`.
- All ORION core dependencies (PostgreSQL/asyncpg: BSD; SQLite: Public Domain; Pydantic: MIT; Python standard library: PSF) are fully compatible with Apache 2.0 distribution.

## Trade-offs
- Downstream commercial entities can incorporate ORION into proprietary products without releasing their proprietary end-user application modifications back to the community.
- *Mitigation:* Community engagement, standardized HAL driver certification, and core OS feature governance encourage OEMs to upstream hardware drivers to maintain platform compatibility.
