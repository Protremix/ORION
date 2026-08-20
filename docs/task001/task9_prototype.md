# ORION TASK 001 — TASK 9: First Prototype

## Mission

Recommend the smallest prototype capable of testing:

```
OBSERVE → WORLD STATE → MEMORY → PREDICTION → COUNTERFACTUAL → SIMULATION → ACTION → RESULT → MODEL UPDATE
```

Must run digitally/in simulation. No real vehicle or robot.

## Current State (VERIFIED FACT)

ORION already implements most of this loop:
- ✅ OBSERVE — GPT-4o Vision + sensor data
- ✅ WORLD STATE — StateSnapshot with entities, relations
- ✅ MEMORY — SQLite/PostgreSQL + TaskStateManager
- ✅ PREDICTION — WorldModel (4 domains, uncertainty quantification)
- ❌ COUNTERFACTUAL — Not implemented
- ✅ SIMULATION — 4 domain simulators
- ✅ ACTION — Autonomous Planner with safety gateway
- ✅ RESULT — Simulation results with metrics
- ❌ MODEL UPDATE — No learning/update mechanism

## Recommended First Prototype

### Domain: Industrial (factory floor)

**Why industrial?** Already fully implemented (IndustrialSimulation + IndustrialPhysics + safety checks). Lowest risk, highest test coverage.

### Scope

```
[1] OBSERVE:      IndustrialSimulation.step() → StateSnapshot
                   ↓
[2] WORLD STATE:   StateSnapshot with machines, temperature, wear
                   ↓
[3] MEMORY:        Store observation in TaskStateManager
                   ↓
[4] PREDICTION:    WorldModel.predict(state, action, horizon=5)
                   ↓
[5] COUNTERFACTUAL: WorldModel.predict(state, ALTERNATIVE_action, horizon=5)
                    Compare to [4] — what if we did B instead of A?
                   ↓
[6] SIMULATION:    IndustrialSimulator.simulate_plan(action_sequence)
                   ↓
[7] ACTION:        Execute safest action via SafetyGateway
                   ↓
[8] RESULT:        IndustrialSimulator.step() → new state
                   ↓
[9] MODEL UPDATE:  Compare predicted [4] vs actual [8]
                    Update prediction confidence
                    Adjust model parameters if error > threshold
```

### New Components Needed

#### 1. Counterfactual Module (~200 lines)
```python
class CounterfactualEngine:
    def compare(self, state: StateSnapshot, 
                action_a: dict, action_b: dict,
                horizon: int) -> CounterfactualResult:
        """Predict outcomes for both actions and compare."""
        result_a = world_model.predict(state, action_a, horizon)
        result_b = world_model.predict(state, action_b, horizon)
        return CounterfactualResult(
            outcome_a=result_a,
            outcome_b=result_b,
            difference=self._compute_difference(result_a, result_b),
            recommendation=self._recommend_better(result_a, result_b),
        )
```

#### 2. Model Update Module (~150 lines)
```python
class ModelUpdater:
    def update(self, prediction: PredictionResult, actual: StateSnapshot):
        """Compare predicted vs actual state and update model."""
        error = self._compute_error(prediction, actual)
        if error > threshold:
            self._adjust_parameters(prediction, actual, error)
        self._update_confidence(prediction, error)
```

#### 3. Integration Loop (~100 lines)
```python
class PrototypeLoop:
    def run(self, domain: str, iterations: int):
        for i in range(iterations):
            state = simulator.step()          # [1] OBSERVE
            memory.remember(state)            # [2,3] WORLD STATE + MEMORY
            action = self._select_action(state)  # [4,5,6,7]
            result = simulator.step(action)    # [8] RESULT
            model_updater.update(prediction, result)  # [9] MODEL UPDATE
```

### Estimated Effort

| Component | Lines | Difficulty | Time |
|-----------|-------|------------|------|
| Counterfactual module | ~200 | Medium | 2-3 hours |
| Model update module | ~150 | Medium | 1-2 hours |
| Integration loop | ~100 | Low | 1 hour |
| Tests | ~200 | Low | 1-2 hours |
| **Total** | **~650** | **Medium** | **5-8 hours** |

### Success Criteria

1. The prototype completes the full loop 100 times without crash
2. Counterfactual comparison produces meaningful differences between actions
3. Model update reduces prediction error over iterations (learning signal)
4. Safety gateway blocks all dangerous actions throughout
5. State persists across simulated restarts

### What This Proves

- The central architecture works end-to-end in simulation
- Counterfactual reasoning is computationally feasible
- The system can detect and reduce prediction errors
- Safety is maintained throughout autonomous operation

### What This Does NOT Prove

- Real-world safety (simulation ≠ reality)
- Generalization across domains (only industrial tested)
- Scalability to complex multi-agent scenarios
- Scientific discovery capability

## Classification

- Prototype feasibility: VERIFIED FACT (most components exist)
- New work needed: HYPOTHESIS (counterfactual + model update — estimated 650 lines)
- Risk: LOW (all in simulation)
- Priority: HIGH (validates central hypothesis)
