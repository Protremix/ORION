# ORION Roadmap for De-scoped Features

**Date:** 2026-08-20
**Decision:** Founder approved de-scoping Discovery and Causal Reasoning (Luna concurred)
**Status:** Deferred — not abandoned. Will be revisited when core system is stable.

---

## De-scoped Features

### 1. Discovery System (Master Spec Phase 10)

**What was planned:**
- Scientific research agent
- Knowledge ingestion from papers/data
- Evidence tracking and hypothesis generation
- Contradiction detection across sources
- Experiment planning and execution
- Domain-specific: biology, medicine, drug discovery, protein design

**Why de-scoped:**
- Zero implementation existed (documentation only)
- Core physical intelligence (safety, planning, simulation) is priority
- Significant effort required (~2000+ lines)
- No clear ROI for physical intelligence use case

**Roadmap for re-introduction:**
1. **When:** After ORION achieves reliable 24/7 autonomous operation with HIL
2. **Prerequisites:**
   - Runtime layer (supervisor, watchdog) operational
   - At least 1 domain deployed with HIL
   - Memory system proven at scale
3. **Implementation plan:**
   - Phase A: Knowledge ingestion pipeline (PDF parsing, data import)
   - Phase B: Evidence tracking + contradiction detection (reuse Memory ContradictionDetector)
   - Phase C: Hypothesis generation (LLM-based, via existing adapter pattern)
   - Phase D: Experiment planning (reuse AutonomousPlanner)
   - Phase E: Domain-specific modules (biology, medicine, etc.)

### 2. Causal Reasoning (Master Spec Phase 11)

**What was planned:**
- Causal models and causal graphs
- Counterfactual reasoning ("what-if" simulation)
- Model-mismatch detection (prediction vs reality)
- Online model updating and correction

**Why de-scoped:**
- Zero implementation existed (not even interfaces)
- Physics-based prediction (World Model) is sufficient for current domains (kinematic models)
- Causal reasoning is needed for complex multi-agent environments, not for single-domain control
- Significant effort and specialized expertise required

**Roadmap for re-introduction:**
1. **When:** When ORION handles multi-agent environments or complex scenarios where physics-only prediction fails
2. **Prerequisites:**
   - World Model proven reliable for single-domain prediction
   - At least 1 domain with HIL data for model validation
   - Performance benchmarks established (OPIB)
3. **Implementation plan:**
   - Phase A: Causal graph data structure (DAG with confounders)
   - Phase B: Interventional reasoning (do-calculus)
   - Phase C: Counterfactual simulation (reuse World Model infrastructure)
   - Phase D: Model-mismatch detection (prediction vs observed outcomes)
   - Phase E: Online model updating (Bayesian or gradient-based)

### 3. Continuous Learning (Master Spec Phase 9)

**What was planned:**
- Online learning from execution results
- Model fine-tuning from experience
- Adaptive behavior improvement

**Why not yet implemented:**
- Requires HIL data for meaningful learning
- Current models are cloud-based (GPT-4o) — fine-tuning is OpenAI's responsibility
- Local model fine-tuning requires GPU hardware (deferred by Founder)

**Roadmap for re-introduction:**
1. **When:** After hardware purchase and local model deployment
2. **Prerequisites:**
   - GPU hardware available (Tier B or better)
   - Local models running (Qwen 2.5 or similar)
   - HIL data collected from at least 1 domain
3. **Implementation plan:**
   - Phase A: Experience replay buffer (reuse Memory episodic storage)
   - Phase B: Reward signal from safety + task success
   - Phase C: Fine-tuning pipeline (LoRA or QLoRA)
   - Phase D: Online adaptation (continuous weight updates)

---

## Summary

| Feature | Master Spec Phase | Status | Target |
|----------|-------------------|--------|--------|
| Discovery | Phase 10 | DE-SCOPED | Post-HIL deployment |
| Causal Reasoning | Phase 11 | DE-SCOPED | Multi-agent environment |
| Continuous Learning | Phase 9 | BLOCKED | Post-hardware purchase |

These features are deferred, not abandoned. The core ORION architecture (8 planes, safety system, domain simulators) is designed to accommodate them as extension modules when the time comes.
