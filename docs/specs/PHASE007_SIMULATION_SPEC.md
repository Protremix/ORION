# ORION Phase 007 — Simulation Specification

**Phase:** 007
**Status:** DRAFT
**License:** Apache 2.0
**Roadmap Reference:** ORION_MASTER_ROADMAP_v1.0 Phase 007

## 1. Goal

ORION must simulate actions before real-world execution. The full pipeline:

```
CURRENT WORLD → HYPOTHESIS → PLAN → SIMULATION → PREDICTION → SAFETY CHECK → ACTION PROPOSAL
```

No real physical hardware.

**Acceptance Criterion:** ORION can compare multiple possible actions in simulation and select the best action according to predefined criteria.

## 2. Current State (VERIFIED FACT)

Existing components:
- `WorldModel` (src/world_model/__init__.py) — physics prediction, `select_best_action()`, 37 tests
- `WorldState` / `ChangeDetector` (Phase 006) — observation → state → change detection, 53 tests
- `AutonomousPlanner` (src/planning/__init__.py) — decompose → plan → simulate → verify
- Domain simulators: Vehicle (698 lines), Drone (390), Home (446), Industrial (386)
- `GridWorld` (simulation/grid_world.py) — 2D grid backend
- Safety Gateway (src/safety/) — deny-by-default enforcement

**Gap:** No unified `SimulationEngine` that orchestrates the full pipeline. The pieces exist but aren't connected into: WorldState → Hypothesis → Plan → Simulate → Predict → Safety Check → Action Proposal.

## 3. Architecture

### 3.1 New Component: SimulationEngine

```
                    ┌─────────────────────────────┐
                    │     SimulationEngine        │
                    │                             │
  WorldState ──────►│  1. Generate hypotheses     │
  (Phase 006)       │  2. For each hypothesis:   │
                    │     a. Plan actions          │──► AutonomousPlanner
                    │     b. Simulate (WorldModel)│──► WorldModel.predict()
                    │     c. Predict outcomes     │
                    │     d. Safety check         │──► SafetyGateway
                    │  3. Compare results        │
                    │  4. Select best action      │
                    │  5. Return ActionProposal   │
                    └─────────────────────────────┘
```

#### SimulationEngine
- **Purpose:** Orchestrate the full simulation pipeline
- **Input:** `WorldState` (current world), `goal` (what to achieve), `constraints` (safety limits)
- **Output:** `SimulationResult` with ranked `ActionProposal`s
- **Key methods:**
  - `run(world_state: WorldState, goal: str, constraints: Dict) -> SimulationResult`
  - `compare_actions(world_state: WorldState, actions: List[Dict]) -> List[ActionEvaluation]`
  - `select_best(evaluations: List[ActionEvaluation]) -> ActionProposal`

#### HypothesisGenerator
- **Purpose:** Generate candidate action hypotheses from world state + goal
- **Input:** `WorldState`, `goal`
- **Output:** `List[Hypothesis]` — each hypothesis is a candidate action with expected outcome
- **Key methods:**
  - `generate(world_state: WorldState, goal: str, max_hypotheses: int = 5) -> List[Hypothesis]`

#### ActionEvaluation
- **Data class:** action, predicted_states, safety_score, confidence, collision_risk, overall_score, ranked_position

#### SimulationResult
- **Data class:** goal, world_state, hypotheses, evaluations, best_action, all_results, metadata

### 3.2 Existing Components (Reuse)

| Component | Role | Phase |
|---|---|---|
| WorldModel | Physics prediction per action | 004/006 |
| AutonomousPlanner | Goal decomposition + action generation | 004 |
| Domain simulators | Step-by-step simulation | 002 |
| SafetyGateway | Deny-by-default safety check | 002 |
| WorldState | Current world input | 006 |
| MemoryManager | Remember simulation outcomes | 005 |

### 3.3 Integration Points

1. **Phase 006 (World Model):** WorldState → SimulationEngine input
2. **Phase 005 (Memory):** SimulationResult stored in memory for learning
3. **Phase 004 (Core):** CoreSupervisor calls SimulationEngine before executing actions
4. **Phase 008 (Multimodal):** Future — real sensor data feeds WorldState

## 4. Acceptance Criteria

| AC | Description | Verification |
|---|---|---|
| AC1 | SimulationEngine runs full pipeline: world → hypothesis → simulate → predict → safety → proposal | Integration test: run() returns SimulationResult with all stages |
| AC2 | HypothesisGenerator generates multiple candidate actions from world state + goal | Unit test: generate() returns ≥ 2 hypotheses |
| AC3 | Each hypothesis is simulated via WorldModel | Unit test: each evaluation has predicted_states |
| AC4 | Each simulation result includes safety assessment | Unit test: each evaluation has safety_score |
| AC5 | Actions are ranked by overall score (safety + confidence + collision risk) | Unit test: evaluations sorted by overall_score descending |
| AC6 | Best action is selected from ranked evaluations | Unit test: select_best() returns highest-scored action |
| AC7 | SimulationEngine compares multiple actions and selects the best | Integration test: 3+ actions → best selected per criteria |
| AC8 | Unsafe actions are filtered out (deny-by-default) | Unit test: unsafe action not selected as best |
| AC9 | SimulationResult includes metadata (latency, predictions count, domain) | Unit test: metadata present and correct |
| AC10 | Works with multiple domains (industrial, vehicle, drone, home) | Unit test: run() with each domain |
| AC11 | SimulationResult can be stored in memory (Phase 005 integration) | Integration test: result → MemoryManager → retrieve |
| AC12 | All tests pass | pytest -q (zero failures) |
| AC13 | Ruff/mypy clean | ruff check + mypy |

## 5. File Structure

```
src/simulation/
    __init__.py              — NEW: SimulationEngine, SimulationResult, ActionEvaluation
    hypothesis_generator.py  — NEW: HypothesisGenerator, Hypothesis

tests/unit/
    test_phase007.py         — NEW: all Phase 007 tests
```

## 6. Test Plan (~35 tests)

### Unit Tests (~25)
- HypothesisGenerator: generate from goal, multiple hypotheses, domain-specific, max limit
- SimulationEngine: run full pipeline, compare actions, select best
- ActionEvaluation: scoring, ranking, safety filtering
- SimulationResult: construction, to_dict, metadata
- Multi-domain: industrial, vehicle, drone, home

### Integration Tests (~10)
- Full pipeline: WorldState → SimulationEngine → ActionProposal
- Safety filtering: unsafe actions excluded
- Memory integration: store/retrieve SimulationResult
- Multi-action comparison with different safety profiles
- Edge cases: empty world state, no valid actions, all unsafe

## 7. Scope

### IN SCOPE
- SimulationEngine orchestration layer
- Hypothesis generation from world state + goal
- Action comparison and ranking
- Safety filtering in simulation
- Integration with WorldModel, AutonomousPlanner, SafetyGateway
- Simulation-only (no real hardware)

### OUT OF SCOPE
- Real physical execution (Phase 012+)
- Real-time performance optimization
- Learning from simulation outcomes (Phase 009)
- Multi-agent simulation
