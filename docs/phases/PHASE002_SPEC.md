# ORION Phase 002 — Specification: ORION Evaluation System

**Date:** 2026-08-21
**Status:** SPECIFICATION
**Author:** ORION Supervisor Agent
**Reviewer:** Luna (GPT-5.6) — pending

---

## Goal

Create the official ORION benchmark system (ORION EVAL) with 12 benchmark categories. Every result must include full metadata (model, version, hardware, latency, memory, cost, failure reason). No invented results. Benchmark must run automatically and produce reproducible reports.

## Current State

- `ORIONEval` class exists with `run_all()`, `run_category()`
- `EvalCategory` enum has 10 values — missing 7 required by roadmap
- `OPIB` class exists with 5 domain scenarios (vehicle, industrial, home, drone, cross-domain)
- `EvalResult` has metric, status, value, max_value — missing required metadata fields
- 48 existing eval tests

## Required Changes

### 1. Add Missing EvalCategory Values (7)

| Required | Enum Name | Description |
|----------|-----------|-------------|
| Task decomposition | `TASK_DECOMPOSITION` | Can the system break complex goals into sub-tasks? |
| Safety decisions | `SAFETY_DECISIONS` | Does the system make correct safety-critical decisions? |
| Permission discipline | `PERMISSION_DISCIPLINE` | Does the system respect permission boundaries? |
| Tool selection | `TOOL_SELECTION` | Does the system select appropriate tools for tasks? |
| World-state understanding | `WORLD_STATE_UNDERSTANDING` | Does the system understand and track world state? |
| Uncertainty calibration | `UNCERTAINTY_CALIBRATION` | Are confidence estimates well-calibrated? |
| Agent coordination | `AGENT_COORDINATION` | Can multiple agents coordinate effectively? |

### 2. Add Result Metadata Fields

Every `EvalResult` must include:

```python
@dataclass
class EvalResult:
    # Existing
    metric: EvalMetric
    status: EvalStatus
    value: float
    max_value: float

    # NEW — Required metadata (Phase 002)
    model: str = ""              # e.g. "gpt-4o-2024-08-06"
    version: str = ""            # ORION version
    hardware: str = ""           # e.g. "cloud-api" or "RTX-5090"
    prompt: str = ""             # The actual prompt/task
    test_version: str = ""       # Test definition version
    latency_ms: float = 0.0      # Execution time in milliseconds
    memory_usage_mb: float = 0.0 # Peak memory usage
    cost_estimate: float = 0.0  # API cost in USD
    failure_reason: str = ""     # Why it failed (empty if passed)
```

### 3. Create Concrete Benchmark Tests (12 categories)

Each category needs at least 2 concrete `EvaluationTest` implementations:

1. **Reasoning** — Logical inference, causal reasoning, counterfactual reasoning
2. **Planning** — Goal-directed planning, multi-step planning, contingency planning
3. **Task decomposition** — Break complex goals into sub-tasks
4. **Safety decisions** — Correct safety-critical choices (brake, stop, deny)
5. **Permission discipline** — Respect permission boundaries, deny-by-default
6. **Tool selection** — Select appropriate tool for task
7. **Memory** — Store, recall, and use memory effectively
8. **World-state understanding** — Track and predict world state
9. **Error recovery** — Recover from errors gracefully
10. **Uncertainty calibration** — Confidence estimates match accuracy
11. **Multimodal understanding** — Cross-modal reasoning (text + image)
12. **Agent coordination** — Multi-agent coordination protocols

### 4. Automated Report Generation

- `ORIONEval.generate_report() -> EvalReport` — Full report with all metadata
- Report format: JSON + Markdown (human-readable)
- Reproducible: same input → same output (deterministic metrics only)
- Include summary statistics: pass rate, avg latency, avg cost, category breakdown

### 5. CLI Runner

```bash
python -m eval.run --categories all --output report.json --format json+md
python -m eval.run --categories reasoning,planning --output report.md
```

## Acceptance Criteria

1. All 12 benchmark categories have concrete tests
2. Every result includes all required metadata fields
3. `ORIONEval.run_all()` produces a complete reproducible report
4. CLI runner works: `python -m eval.run` generates a report
5. No invented results — all metrics are measured
6. All new tests pass
7. Existing tests still pass
8. Lint clean, type clean

## Dependencies

- Existing `ORIONEval`, `OPIB` framework
- `src/contracts/contracts.py` — ActionProposal, Goal, BeliefState
- `src/safety/` — SafetyEnforcement for safety decision tests
- `src/api/permissions.py` — PermissionChecker for permission tests
- `src/memory/memory_system.py` — MemorySystem for memory tests
- `src/cognitive/cognitive_plane.py` — CognitivePlane for reasoning tests

## License

Apache 2.0
