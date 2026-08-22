# ORION Phase 004 — Core System (Draft Plan)

## PREREQUISITE
- Phase 003 (Model Selection) must be VERIFIED by Luna
- At least one model must pass ALL mandatory criteria OR Founder approves model with known limitations

## SCOPE
Phase 004 implements the ORION Core — central orchestration:
1. Integrates selected model(s) as reasoning engine
2. Goal -> plan -> execute -> verify loop
3. Connects Safety Layer, Memory, World Model, Action execution
4. Supervisor interface for autonomous operation

## WORK ITEMS
W1: Model Integration Layer (bind model, switching, token budget, retry)
W2: Core Orchestrator (goal ingestion, plan gen, safety check, execution, verify)
W3: Safety Integration (deny-by-default, post-audit, emergency stop, audit log)
W4: Memory Integration (6-tier memory, context window, retrieval, consolidation)
W5: World Model Integration (state estimation, prediction, uncertainty, domains)
W6: Action Execution Pipeline (plan->action, HAL, simulation mode, feedback)
W7: Supervisor Interface (24/7, state persistence, checkpoints, watchdog)
W8: Testing (unit, integration, safety, performance, regression)

## ACCEPTANCE CRITERIA
1. Core can ingest a goal and produce a verified plan
2. Safety Layer denies all hazardous actions
3. Memory stores and retrieves context during planning
4. World Model predicts outcomes with uncertainty
5. Simulation mode executes without physical actuation
6. 24/7 operation with state persistence and recovery
7. All tests pass (unit + integration + safety)
8. Ruff + mypy clean
9. Luna review PASSED

## DEPENDENCIES
- Phase 003 model selection (IN PROGRESS)
- Phase 002 evaluation system (VERIFIED)
- Phase 001 repository audit (COMPLETE)
