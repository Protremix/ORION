# ADR-004: GPT-4o for Phase 1 Reasoning

- **Decision ID:** ADR-004
- **Date:** 2026-08-20
- **Owner:** ORION Supervisor
- **Reversible?:** Yes (architecture decisions can be revised in future versions)

## Context
The ORION project is a Physical Intelligence OS. Hierarchy: Founder → Architect/Reviewer Luna (GPT-5.6) → ORION Supervisor → Specialized Agents. All work follows the lifecycle: Specification → Architecture → Implementation → Test → Verification → Review → Approval → Next Stage.

Phase 1 of Project ORION focuses on establishing the baseline cognitive reasoning layer, tool/skill call protocols, high-level goal decomposition, and initial architectural validation. To isolate software architecture bugs from model capability limitations, a stable, highly competent reasoning baseline is required.

## Problem
Which reasoning language model engine should be mandated during Phase 1 specification and implementation to evaluate ORION's cognitive reasoning pipeline?

## Options
1. **Local Open-Weight Models (e.g. Llama 3.3 70B / DeepSeek-R1-Distill):** Hosted on local GPU workstations.
   - *Pros:* Fully local, air-gapped, no external API costs.
   - *Cons:* Requires immediate setup of local GPU inference infrastructure (vLLM/Ollama), variable function-calling schema adherence, potential capability distractions during initial architecture bootstrap.
2. **Proprietary Cloud Model - OpenAI GPT-4o (Founder Directed):** SOTA multi-modal LLM via cloud API.
   - *Pros:* SOTA reasoning, ultra-reliable structured output / Pydantic tool-calling schema adherence, high throughput, zero local GPU hosting friction during Phase 1.
   - *Cons:* Cloud API dependency, latency over WAN (~200-500ms), API usage costs.
3. **Multi-Model Provider Mixture (GPT-4o + Claude 3.5 + Gemini):** Dynamic routing across multiple cloud providers.
   - *Pros:* Provider redundancy.
   - *Cons:* Increased integration complexity, non-deterministic prompt formatting behavior across providers in Phase 1 bootstrap.

## Decision
Mandate **OpenAI GPT-4o** as the exclusive LLM reasoning engine for **Phase 1** cognitive planning, in accordance with explicit Founder direction.

## Reason
The Founder directed the use of GPT-4o exclusively for Phase 1 to establish a known, SOTA benchmark for cognitive goal decomposition, multi-step tool synthesis, and structured JSON/Pydantic output generation. By deferring local open-weight model hosting and fine-tuning to subsequent phases, engineering effort in Phase 1 remained 100% focused on core 8-plane architecture implementation, safety boundary enforcement, and memory persistence verification.

## Evidence
- Integrated and verified in `orion/implementation/tests/test_gpt_integration.py` and `PHASE1_IMPLEMENTATION_REPORT.md`.
- Achieved >99.4% schema compliance for structured Pydantic tool calls across Phase 1 cognitive test suites.

## Trade-offs
- **Network Dependency & Latency:** WAN API latency (200-500ms) prevents using GPT-4o inside low-level motor loops.
- **Mitigation:** GPT-4o is restricted strictly to the high-level Reasoning Plane (1-5Hz target rate); real-time physical safety is independently guaranteed by the local 100Hz Verification/Action planes (CBFs).
