# ORION Phase 011 — Physical AI Simulation Specification

**Phase:** 011
**Status:** DRAFT
**License:** Apache 2.0
**Roadmap Reference:** ORION_MASTER_ROADMAP_v1.0 Phase 011

## 1. Goal

Build virtual environments for home, vehicle, robot, drone, and industrial domains.
ORION must operate only inside simulation.

Capabilities: perception, world model, planning, prediction, action, recovery, safety verification.

**Acceptance Criterion:** ORION completes predefined simulated physical tasks with measurable success rates.

## 2. Current State (VERIFIED FACT)

Existing components:
- `SimulationEngine` (Phase 007) — full pipeline: hypothesis → simulate → predict → safety check
- `HypothesisGenerator` (Phase 007) — domain-specific action candidates
- `WorldModel` with 4 physics models: Industrial, Vehicle, Drone, Home (Phase 006)
- Domain simulators: `DroneSimulation`, `HomeSimulation`, `IndustrialSimulation`, `VehicleSimulation`
- `SimulationAdapter` (HAL) — simulated device adapter
- `SafetyGateway` — deny-by-default safety enforcement
- `MultimodalCoordinator` (Phase 008) — perception
- `AgentCoordinator` (Phase 009) — agent dispatch

Gaps:
1. No robot simulator (5th domain)
2. No unified PhysicalSimulationEnvironment tying domain simulators together
3. No predefined physical tasks per domain
4. No task execution pipeline (perception → plan → act → verify)
5. No measurable success rate reporting
6. No recovery mechanism for failed simulated actions

## 3. Architecture

```
                    ┌─────────────────────────────┐
                    │  PhysicalSimEnvironment     │
                    │                             │
  Task ───────────►│  1. Load domain simulator    │
                    │  2. Perceive world state     │──► HomeEnv
                    │  3. Plan action              │──► VehicleEnv
                    │  4. Predict outcome          │──► RobotEnv (NEW)
                    │  5. Safety verify            │──► DroneEnv
                    │  6. Execute action           │──► IndustrialEnv
                    │  7. Measure success          │
                    │  8. Recover if failed        │
                    └─────────────────────────────┘
```

### 3.1 New Components

#### PhysicalSimEnvironment
- **Purpose:** Unified environment for all 5 simulation domains
- **Key methods:**
  - `register_domain(name, simulator) -> bool`
  - `load_task(task_id) -> SimTask`
  - `execute_task(task_id) -> TaskResult`
  - `get_success_rates() -> Dict[str, float]`

#### RobotSimulator
- **Purpose:** Robot physics simulation (locomotion, manipulation, navigation)
- **Key methods:**
  - `step(action) -> Dict`
  - `get_state() -> Dict`
  - `reset() -> None`

#### SimTask
- **Purpose:** Predefined physical task with success criteria
- **Fields:** domain, description, initial_state, goal_state, success_criteria, max_steps

#### TaskResult
- **Purpose:** Result of executing a sim task
- **Fields:** success, steps_taken, final_state, success_rate, errors, recovery_actions

#### RecoveryManager
- **Purpose:** Recovery from failed simulated actions
- **Key methods:**
  - `recover(error, context) -> RecoveryAction`
  - `get_strategies() -> List[str]`

### 3.2 Existing Components (Reuse)

| Component | Role | Phase |
|---|---|---|
| SimulationEngine | Full simulation pipeline | 007 |
| WorldModel | Physics prediction | 006 |
| Domain simulators | Home/Vehicle/Drone/Industrial | 004/006 |
| SafetyGateway | Safety verification | 004 |
| HypothesisGenerator | Action candidates | 007 |
| MultimodalCoordinator | Perception | 008 |

## 4. Acceptance Criteria

| AC | Description | Verification |
|---|---|---|
| AC1 | PhysicalSimEnvironment registers 5 domains | Unit test |
| AC2 | PhysicalSimEnvironment loads predefined tasks | Unit test |
| AC3 | RobotSimulator simulates robot actions | Unit test |
| AC4 | RobotSimulator tracks state (position, velocity, joints) | Unit test |
| AC5 | SimTask defines success criteria | Unit test |
| AC6 | TaskResult reports success and success_rate | Unit test |
| AC7 | RecoveryManager generates recovery strategies | Unit test |
| AC8 | RecoveryManager executes recovery actions | Unit test |
| AC9 | PhysicalSimEnvironment executes home task | Integration test |
| AC10 | PhysicalSimEnvironment executes vehicle task | Integration test |
| AC11 | PhysicalSimEnvironment executes robot task | Integration test |
| AC12 | PhysicalSimEnvironment executes drone task | Integration test |
| AC13 | PhysicalSimEnvironment executes industrial task | Integration test |
| AC14 | ORION completes task: perception → plan → act → verify | Integration test |
| AC15 | ORION recovers from a failed action | Integration test |
| AC16 | Success rates are measurable and reported | Unit test |
| AC17 | Safety verification blocks unsafe actions | Integration test |
| AC18 | ORION operates only inside simulation (no real actions) | Unit test |
| AC19 | All tests pass | pytest -q |
| AC20 | Ruff/mypy clean | ruff + mypy |

## 5. File Structure

```
src/physical_sim/
    __init__.py              — NEW: PhysicalSimEnvironment, SimTask, TaskResult
    robot_simulator.py      — NEW: RobotSimulator
    recovery_manager.py     — NEW: RecoveryManager
    predefined_tasks.py     — NEW: Predefined tasks for all 5 domains

tests/unit/
    test_phase011.py         — NEW: all Phase 011 tests
```

## 6. Test Plan (~50 tests)

### Unit Tests (~35)
- PhysicalSimEnvironment: register, load, execute, success rates
- RobotSimulator: step, get_state, reset, joints, locomotion
- SimTask/TaskResult: construction, success criteria
- RecoveryManager: strategies, execute recovery
- Predefined tasks: all 5 domains have tasks

### Integration Tests (~15)
- Home task: perceive → plan → act → verify
- Vehicle task: navigation with safety
- Robot task: manipulation with recovery
- Drone task: flight with safety check
- Industrial task: process control
- Failed action recovery
- Unsafe action blocked
- Success rate reporting across multiple tasks

## 7. Scope

### IN SCOPE
- 5 domain simulation environments (home, vehicle, robot, drone, industrial)
- RobotSimulator (new)
- PhysicalSimEnvironment unifying all domains
- Predefined tasks with measurable success criteria
- Recovery from failed actions
- Safety verification in simulation
- Simulation-only — no real hardware

### OUT OF SCOPE
- Real hardware integration (Phase 012)
- Real sensor data
- Physical dynamics engine (use simplified physics)
- Multi-agent physical simulation
