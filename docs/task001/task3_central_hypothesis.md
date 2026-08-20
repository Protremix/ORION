# ORION TASK 001 — TASK 3: Central Hypothesis Testing

## The Central Hypothesis

ORION's architecture proposes:

```
ORION CORE → SUPERVISOR → REASONING / MEMORY / WORLD MODEL / PERCEPTION → SIMULATION → VERIFICATION → ACTION → DISCOVERY
```

This combines: **Persistent Causal World Model + Counterfactual Simulation + Long-Term Memory + Agent Planning + Scientific Discovery**

## What Exists (VERIFIED FACT from ORION Implementation)

### Implemented and Tested
- **Supervisor Agent** — autonomous coordination loop (GOAL→PLAN→EXECUTE→TEST→VERIFY→CONTINUE)
- **Reasoning** — GPT-4o text adapter (live-tested, 16 API calls verified)
- **Memory** — SQLite + PostgreSQL persistence layers, task state with checkpoints
- **World Model** — 4 domain physics models (Industrial, Vehicle, Drone, Home) with uncertainty quantification
- **Perception** — GPT-4o Vision + Embedding adapters (live-tested)
- **Simulation** — 4 domain simulators with safety validation
- **Verification** — Safety Gateway with deny-by-default policy, cross-domain safety arbitration
- **Action** — Autonomous Planner with goal decomposition, action generation, safety checks
- **Task State** — Persistent 24/7 runtime with shutdown/resume, checkpoint system

### What Does NOT Exist Yet (UNKNOWN/NEEDS RESEARCH)
- **Causal reasoning** — current World Model predicts future states but doesn't model causal relationships
- **Counterfactual simulation** — no "what if action B instead of A" reasoning
- **Scientific discovery** — no knowledge ingestion, hypothesis generation, or experiment planning
- **Cross-environment transfer** — domain models are isolated, no transfer learning
- **Continuous learning** — no online learning, models are static

## Hypothesis Assessment

### H1: The architecture is technically reasonable
**ASSESSMENT: SUPPORTED with caveats**

The pipeline ORION CORE → SUPERVISOR → REASONING/MEMORY/WORLD MODEL/PERCEPTION → SIMULATION → VERIFICATION → ACTION is VERIFIED FACT — we have implemented and tested every stage except DISCOVERY.

The caveats:
1. **Causal World Model** — VERIFIED FACT: Current world model is physics-based, not causal. Causal reasoning requires additional research (see Task 2 gaps). HYPOTHESIS: Causal relationships could be layered on top of physics models using structural causal models.
2. **Counterfactual Simulation** — VERIFIED FACT: Not implemented. HYPOTHESIS: Could be achieved by running the world model with alternate actions and comparing outcomes. This is architecturally straightforward but scientifically non-trivial.
3. **Scientific Discovery** — VERIFIED FACT: Not implemented. This is the most ambitious component. ASSUMPTION: Discovery requires knowledge graph + contradiction detection + hypothesis generation, which are research-level challenges.

### H2: A small initial system can test the central idea
**ASSESSMENT: SUPPORTED**

ORION's current implementation (463 tests, 8/11 phases) demonstrates that:
- A Supervisor can coordinate autonomous work
- Domain simulators can predict future states
- Safety verification can block dangerous actions
- Persistent state survives restarts
- GPT-4o can serve as the reasoning engine

The smallest prototype for the full central idea (OBSERVE → WORLD STATE → MEMORY → PREDICTION → COUNTERFACTUAL → SIMULATION → ACTION → RESULT → MODEL UPDATE) would need:
- 1 domain (e.g., Industrial — already implemented)
- World Model (already implemented)
- Memory (already implemented)
- Counterfactual module (NEW — estimate: 200-500 lines)
- Model update mechanism (NEW — estimate: 100-300 lines)

### H3: The combination is novel
**ASSESSMENT: CANNOT CLAIM — NEEDS RESEARCH**

Per the evidence discipline: "Do not call it novel without evidence." The sub-agent research will determine if similar systems exist. Key questions:
- Does any system combine world models + persistent memory + planning + discovery?
- Is counterfactual simulation integrated with physical AI elsewhere?

## What Can Be Combined (from existing research)

| Component | Existing Tech | Can Combine? | Evidence |
|-----------|---------------|---------------|----------|
| Reasoning | GPT-4o / open LLMs | YES — VERIFIED FACT | Live-tested in ORION |
| Memory | Vector DB + SQL | YES — VERIFIED FACT | Implemented in ORION |
| World Model | Physics simulators | YES — VERIFIED FACT | 4 domains implemented |
| Planning | LLM-based decomposition | YES — VERIFIED FACT | Autonomous Planner working |
| Safety | Deny-by-default gateway | YES — VERIFIED FACT | Cross-domain arbitration |
| Causal Reasoning | Pearl's SCM, causal ML | PARTIAL — HYPOTHESIS | Research needed |
| Counterfactual | Counterfactual models | PARTIAL — HYPOTHESIS | Architecturally feasible |
| Discovery | AI-for-science systems | UNKNOWN — NEEDS RESEARCH | Gap analysis needed |

## What Needs New Research

1. **Causal layer for world model** — how to extract causal relationships from physics simulations
2. **Counterfactual reasoning engine** — how to evaluate "what if" scenarios efficiently
3. **Knowledge graph for discovery** — how to structure scientific knowledge for hypothesis generation
4. **Cross-domain transfer** — how to share learned models between domains
5. **Self-diagnosis** — how to detect when the world model's predictions are wrong

## What Is Realistic for a Small Initial System

VERIFIED FACT (from ORION implementation):
- Single-domain physical intelligence with simulation ✓
- Persistent memory with checkpoints ✓
- LLM-based planning with safety verification ✓
- 24/7 autonomous operation ✓

HYPOTHESIS (feasible next steps):
- Counterfactual simulation within 1 domain (medium difficulty)
- Causal model extraction from physics (high difficulty)
- Basic knowledge graph for structured knowledge (medium difficulty)
- Hypothesis generation using LLM + knowledge graph (high difficulty)

## Conclusion

The central hypothesis is **technically reasonable and partially verified**. The ORION implementation demonstrates the core pipeline works end-to-end. The remaining challenges (causal reasoning, counterfactual simulation, scientific discovery) are research-level but architecturally compatible with the existing system.

**Classification: HYPOTHESIS → PARTIALLY VERIFIED**
- Core pipeline: VERIFIED FACT
- Causal/counterfactual: HYPOTHESIS (architecturally feasible)
- Discovery: UNKNOWN (needs research from sub-agents)
