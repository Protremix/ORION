# ORION TASK 001 — TASK 5: ORION World Model Architecture

## Overview

The ORION World Model represents the system's understanding of the environment: objects, people, places, geometry, motion, time, events, relationships, uncertainty, historical states, predicted states, and causal hypotheses.

## Current Implementation (VERIFIED FACT)

ORION already has a WorldModel class with:
- 4 domain physics models (Industrial, Vehicle, Drone, Home)
- State prediction (n steps ahead)
- Uncertainty quantification (grows with horizon)
- Safety assessment per prediction step
- Collision risk evaluation
- Batch prediction for multiple candidate actions
- Action selection (safest action by confidence + risk)
- 37 tests passing, Luna-approved

## Full Architecture

### Layer 1: State Representation

```python
@dataclass
class WorldState:
    timestamp: float
    domain: str
    entities: Dict[str, Entity]        # Objects, people, vehicles, etc.
    relations: Dict[str, Relation]      # Spatial, temporal, causal
    environment: Environment            # Temperature, lighting, weather
    uncertainty: Dict[str, float]       # Per-entity uncertainty
    provenance: Dict[str, str]         # Source of each entity
    history: List[WorldState]          # Previous states
```

### Layer 2: Entity Types

```
Entity (base)
├── Object (physical objects)
│   ├── Vehicle
│   ├── Robot
│   ├── Machine
│   └── Tool
├── Person (humans)
├── Place (locations, zones)
├── Sensor (data sources)
└── Event (things that happen)
```

Each entity has:
- Physical properties (position, velocity, size, mass)
- State properties (status, temperature, health)
- Relationships to other entities
- Confidence/uncertainty values
- Historical trajectory

### Layer 3: Relation Types

```
Relation
├── Spatial (near, far, inside, on-top-of, adjacent)
├── Temporal (before, after, during, concurrent)
├── Causal (causes, prevents, enables, inhibits)
├── Part-of (component hierarchy)
├── Similar-to (semantic similarity)
└── Interacts-with (physical interaction)
```

### Layer 4: Prediction Engine

**Current (VERIFIED FACT):**
- Physics-based prediction using domain models
- Uncertainty grows with horizon
- Safety assessment per step

**Proposed extensions:**
- **Causal prediction:** "If I change X, Y will change because X causes Y"
- **Counterfactual:** "What would have happened if action B was taken instead of A?"
- **Probabilistic:** Multiple possible futures with probabilities
- **Multi-entity:** Track interactions between entities over time

### Layer 5: Memory Integration

The World Model connects to ORION's memory system:
- **Working memory:** Current state + recent changes
- **Episodic memory:** Past states and events (for pattern recognition)
- **World memory:** Persistent knowledge about how the world works
- **Decision memory:** Past actions and their outcomes

## Design Alternatives (with evidence)

### Option A: Physics-Based (Current — VERIFIED FACT)
- **Approach:** Domain-specific physics models per domain
- **Pros:** Interpretable, fast, verifiable, already working
- **Cons:** Limited to known physics, no learning from data
- **Evidence:** 37 tests, Luna-approved, live GPT-4o integration

### Option B: Learned Neural World Model
- **Approach:** Train a neural network to predict state transitions (like DreamerV3, Genie)
- **Pros:** Can learn unknown dynamics, generalize across environments
- **Cons:** Black box, hard to verify safety, requires training data and GPU
- **Evidence:** DreamerV3 (Hafner et al.), Genie (Google DeepMind) show feasibility
- **Classification:** HYPOTHESIS — could be added as adapter

### Option C: Hybrid (Recommended)
- **Approach:** Physics models for known dynamics + neural model for unknown dynamics
- **Pros:** Interpretable where possible, learns where needed, safer
- **Cons:** More complex, need to reconcile two prediction systems
- **Evidence:** RT-2 (Google) uses hybrid approaches for robotics
- **Classification:** HYPOTHESIS — best long-term approach

## Causal Hypothesis Layer (NEW)

The World Model should support causal reasoning:
```python
class CausalModel:
    def add_causal_link(self, cause: str, effect: str, strength: float, evidence: Evidence)
    def predict_causal_effect(self, intervention: dict) -> dict
    def counterfactual(self, actual: WorldState, alternative_action: dict) -> WorldState
    def identify_confounders(self, cause: str, effect: str) -> List[str]
```

**Classification:** HYPOTHESIS — not implemented. Based on Pearl's structural causal models. Feasibility: MEDIUM.

## Uncertainty Quantification (VERIFIED FACT + extensions)

Current:
- Base uncertainty = 0.05, grows with horizon (0.1 × horizon)
- Confidence levels: HIGH, MEDIUM, LOW, UNKNOWN

Proposed extensions:
- Per-entity uncertainty (some things more predictable than others)
- Bayesian updating (update uncertainty based on prediction accuracy)
- Ensemble predictions (multiple models, disagreement = uncertainty)

## Benchmarks

From Master Spec §20 (ORION EVAL):
- World-state reconstruction: given observations, reconstruct the full state
- Future prediction: predict state N steps ahead, compare to actual
- Temporal reasoning: understand cause and effect over time
- Spatial reasoning: understand geometric relationships

**Scoring:** Mean squared error between predicted and actual states, weighted by uncertainty calibration (do predictions fall within confidence intervals?).

## Implementation Priority

1. **Now (simulation):** Add causal link support, counterfactual module — MEDIUM difficulty
2. **Next:** Multi-entity interaction tracking, ensemble predictions
3. **Future (with GPU):** Learned world model adapter, neural-physical hybrid

## Alternatives Evidence

| System | Approach | Open? | Relevance |
|--------|----------|-------|-----------|
| DreamerV3 | Learned world model, latent imagination | Yes (MIT) | High — adapter target |
| Genie | Generative interactive environment | Closed | Medium — concept reference |
| UniSim | Universal simulator from video | Closed | Medium — concept reference |
| Habitat | 3D simulation for embodied AI | Yes (MIT) | High — simulation env |
| Isaac Sim | Robot simulation, physics | Free (NVIDIA) | High — physics reference |

(Full landscape research from sub-agents will expand this table)
