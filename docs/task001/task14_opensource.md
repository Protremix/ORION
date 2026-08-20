# ORION TASK 001 — TASK 14: Open-Source / Commercial Strategy

## Master Spec §18 Requirements

Propose what may be open source and what may remain proprietary/commercial. Check actual licenses of proposed dependencies. Do not make licensing recommendations without checking terms.

## License Verification (VERIFIED FACT)

ORION's own code is licensed under Apache 2.0 (Founder-approved).

All external dependencies must have their actual license checked and registered in the Dependency & License Registry.

## What Should Be Open Source

### Potentially Open (per Master Spec §18):
- **Agent SDK** — community can build agents for ORION
- **Protocols** — agent communication protocol, skill protocol
- **APIs** — ORION API specification (OpenAPI)
- **Adapters** — model adapters, device adapters, simulator adapters
- **Developer tools** — CLI, testing framework, evaluation harness
- **Simulation interfaces** — standard interface for connecting simulators
- **Safety Gateway interface** — public safety specification

**Rationale:** Open-sourcing these creates an ecosystem. Others can:
- Build adapters for their hardware (robots, vehicles, drones)
- Create specialized agents
- Integrate ORION with their systems
- Contribute back improvements

**License:** Apache 2.0 (same as core)

### What Should Remain Proprietary/Commercial

### Potentially Proprietary (per Master Spec §18):
- **Proprietary training data** — any data ORION generates/collects
- **Proprietary evaluation data** — ORION-specific benchmark datasets
- **Selected advanced models** — trained/fine-tuned world models
- **Enterprise security** — enterprise authentication, audit, compliance
- **Commercial infrastructure** — managed hosting, cloud deployment
- **Premium services** — advanced planning, multi-agent orchestration
- **Selected production components** — domain-specific high-value modules

**Rationale:** These create a sustainable business model. The core ecosystem is free, but advanced features and managed services are commercial.

## Dependency License Registry (VERIFIED FACT — maintained)

Current key dependencies:

| Dependency | Version | License | Commercial | Modification | Redistribution | Notes |
|------------|---------|---------|------------|-------------|----------------|-------|
| Python | 3.11 | PSF License | ✅ Yes | ✅ Yes | ✅ Yes | Compatible with Apache 2.0 |
| pytest | 9.1 | MIT | ✅ Yes | ✅ Yes | ✅ Yes | |
| asyncpg | latest | Apache 2.0 | ✅ Yes | ✅ Yes | ✅ Yes | BSD-like, Founder-mandated |
| SQLite | built-in | Public Domain | ✅ Yes | ✅ Yes | ✅ Yes | |
| NumPy | latest | BSD 3-Clause | ✅ Yes | ✅ Yes | ✅ Yes | |
| OpenAI API | N/A (API) | Proprietary | Service | N/A | N/A | API usage, no code dependency |
| PostgreSQL | latest | PostgreSQL License | ✅ Yes | ✅ Yes | ✅ Yes | BSD-like |
| pgvector | latest | PostgreSQL License | ✅ Yes | ✅ Yes | ✅ Yes | |

### Planned Dependencies (licenses checked)

| Dependency | License | Commercial OK? | Notes |
|------------|---------|----------------|-------|
| Qwen 2.5 72B | Apache 2.0 | ✅ Yes | Commercial use explicitly allowed |
| Qwen2-VL 7B | Apache 2.0 | ✅ Yes | |
| BGE-large-en | MIT | ✅ Yes | |
| Whisper Large v3 | MIT | ✅ Yes | |
| Bark TTS | MIT | ✅ Yes | |
| DreamerV3 | MIT | ✅ Yes | |
| NetworkX | BSD 3-Clause | ✅ Yes | Knowledge graph |
| Neo4j (if used) | GPLv3 / AGPLv3 | ⚠️ CHECK | Community edition is GPLv3. Enterprise is commercial. ASSUMPTION: NetworkX is sufficient for initial prototype. If Neo4j needed, use Neo4j Enterprise (paid) or Apache AGE (Apache 2.0 PostgreSQL extension). |

### Excluded Due to License Incompatibility

| Dependency | License | Issue |
|------------|---------|-------|
| XTTS v2 (Coqui) | CPML | Non-commercial only, incompatible with Apache 2.0 |
| Any GPL-3.0 model | GPL-3.0 | Copyleft would require ORION to be GPL |
| Llama 3.1 (Meta) | Llama 3.1 License | Has use restrictions (700M MAU limit). USABLE but not truly permissive. HYPOTHESIS: acceptable for research, not for unrestricted commercial deployment. |

## Strategy

### Phase 1: Research / Development (current)
- ORION core: Apache 2.0
- Dependencies: Apache 2.0, MIT, BSD (all permissive)
- API services: OpenAI (proprietary, API-only)
- No commercial offering

### Phase 2: Open Beta
- ORION core + SDK + adapters: Apache 2.0 (public repo)
- ORION API specification: OpenAPI, publicly documented
- Evaluation framework: Apache 2.0
- Community contributions accepted via PR
- No commercial offering yet

### Phase 3: Commercial Launch
- **Open source (Apache 2.0):**
  - ORION Core (supervisor, safety gateway, world model)
  - Adapter interfaces and reference adapters
  - Agent protocol and skill interface
  - Simulation interface
  - Evaluation framework
  - Developer SDK
- **Proprietary (commercial):**
  - Managed ORION cloud service
  - Enterprise security (SSO, audit, compliance)
  - Advanced multi-agent orchestration
  - Domain-specific production modules (factory automation, autonomous fleet)
  - Premium support
  - Fine-tuned models (trained on proprietary data)
  - ORION Discovery (scientific discovery platform)

### Phase 4: Ecosystem
- Open-source community building adapters for various hardware
- Partner program for hardware manufacturers
- Certification program for safety-critical deployments
- Marketplace for agents, skills, and domain modules

## Legal Considerations

- **ASSUMPTION:** Apache 2.0 is compatible with all planned dependencies. This needs legal verification (Founder decision: LEGAL).
- **ASSUMPTION:** ORION can use OpenAI API commercially. Check OpenAI Terms of Service.
- **UNKNOWN:** Whether open-sourcing the safety gateway creates liability. Needs legal counsel.
- **UNKNOWN:** Regulatory requirements for AI in physical domains (EU AI Act, etc.). From Phase 6 regulatory review.

## Classification

- Current license (Apache 2.0): VERIFIED FACT (Founder-approved)
- Dependency licenses: VERIFIED FACT (checked and registered)
- Planned dependency licenses: VERIFIED FACT (checked in this document)
- Open-source strategy: HYPOTHESIS (proposed, needs Founder strategic approval)
- Commercial strategy: HYPOTHESIS (proposed, needs Founder strategic approval)
- Legal compliance: UNKNOWN (needs legal counsel — LEGAL boundary)
