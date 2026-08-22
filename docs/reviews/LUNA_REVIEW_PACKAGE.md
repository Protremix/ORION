# ORION Phase 003 — Luna Review Package (Round 4)

## PROJECT
ORION — Physical Intelligence OS

## PHASE
Phase 003: Model Selection (7B→14B→32B→72B evaluation)

## COMMIT SHA
485dbd8

## BRANCH
main

## TASK
Fix all 8 blocking issues from Luna Round 3 review, complete benchmark re-runs, and submit for independent verification.

## LUNA ROUND 3 BLOCKING ISSUES — RESOLUTION STATUS

### Block 1: SafetyScenarioSuite mutates class-level SCENARIOS via pop("expected")
**Status:** FIXED
**Resolution:** Changed `scenario.pop("expected")` to `scenario["expected"]` (read-only access, no mutation). Multi-run (`--runs N`) now works correctly because SCENARIOS is not mutated between runs.

### Block 2: PermissionScenarioSuite has adapter-local fallback with keyword heuristics
**Status:** FIXED
**Resolution:** Removed the entire `else` branch that used `system.reason()` with keyword matching (`"block" in result_str.lower()`). Only `_call_llm` path is used. If no `_call_llm` on system, records as failure with `"no_llm"` error — no local heuristic fallback.

### Block 3: coordinate() and recover() have local fallbacks
**Status:** FIXED
**Resolution:**
- `coordinate()`: Changed fallback from `{"status": "coordinated"}` (fake success) to `{"status": "failed", "error": "LLM coordination response unparseable"}`
- `recover()`: Removed status rewriting that forced `recovery["status"] = "recovered"` — now returns LLM response as-is

### Block 4: Transport failures can pass safety criteria via "blocked" status
**Status:** FIXED
**Resolution:**
- `execute()`: When `_call_llm` returns an error marker (`[ERROR: ...]`), now returns `{"status": "error", ...}` instead of `{"status": "blocked", ...}`. The `"error"` status does NOT match "blocked"/"denied"/"rejected" in safety suites.
- `DenyByDefaultSuite`: Added guard — `status.startswith("[error")` → `is_blocked = False`
- `SafetyScenarioSuite`: Added guard — `status.startswith("[error")` → `is_correct = False`
- `PermissionScenarioSuite`: Added guard — `status.startswith("[error")` → `is_correct = False`

### Block 5: Per-case raw_response is not actual raw LLM response
**Status:** FIXED
**Resolution:**
- `DenyByDefaultSuite` and `SafetyScenarioSuite`: Now use `getattr(system, "_last_raw_response", None)` for the raw_response field, falling back to `str(result)[:200]` only if `_last_raw_response` is None.
- `PermissionScenarioSuite`: Already uses `result_str[:200]` (the raw LLM response string before JSON parsing).
- Note: `_last_raw_response` is per-call (set after each `_call_llm` invocation), so it correctly associates with the most recent case.

### Block 6: Permission case latency is fabricated as 0
**Status:** FIXED
**Resolution:** `PermissionScenarioSuite` now measures actual latency using `time.perf_counter()` around the `_call_llm()` call. Each case records `latency_ms` with the actual measurement.

### Block 7: Fix 10 re-runs incomplete
**Status:** IN PROGRESS
**Resolution:** Re-runs of openchat:7b and qwen2.5:14b launched on Oryx EvolvixOS server (2.28.52.223). Results will be appended when complete.

### Block 8: Commit identity cannot be verified
**Status:** FIXED
**Resolution:** Commit SHA is 485dbd8. Verified via `git rev-parse HEAD`. Full file tree available on GitHub at https://github.com/Protremix/ORION.

## ADDITIONAL RECOMMENDATIONS ADDRESSED

### Rec 4: p95_latency_s should be scalar, not array
**Status:** FIXED
**Resolution:** Changed `"p95_latency_s": r.get("latency_samples_ms", [])` to `"p95_latency_s": r.get("p95_latency_ms", 0) / 1000.0` (scalar).

### Rec 5: --runs 0 guard
**Status:** FIXED
**Resolution:** Added `if args.runs < 1: print("ERROR"); raise SystemExit(1)`.

## FILES CHANGED

### Source Files (Round 4)
- `src/eval/cloud_adapter.py` — Fixed execute() error bypass, coordinate() fake success, recover() status rewriting
- `src/eval/phase003_benchmarks.py` — Fixed SafetyScenarioSuite mutation, PermissionScenarioSuite fallback removal + latency, raw LLM response capture, error marker guards
- `src/eval/phase003_runner.py` — Fixed --runs 0 guard, p95_latency_s scalar

### Documentation
- `docs/reviews/LUNA_REVIEW_PACKAGE.md` — This file (Round 4)
- `docs/reviews/LUNA_ROUND3_RESPONSE.md` — Luna Round 3 response (saved)

## TEST RESULTS

### Full Test Suite
```
796 passed, 9 skipped in 158.49s
0 failures
```

### Lint & Type Check
```bash
ruff check src/eval/ tests/unit/test_phase003.py  # All checks passed
mypy src/eval/ --ignore-missing-imports  # Success: no issues found in 9 source files
```

## SECURITY RESULTS
- No security changes in this phase (evaluation only)
- Error markers cannot pass safety criteria (4 suites guarded)
- No adapter-local fallbacks remain in scored tests

## KNOWN LIMITATIONS

1. **Fix 10 re-runs IN PROGRESS** — openchat:7b and qwen2.5:14b re-runs launched but not yet complete
2. **32B/72B models NOT benchmarked** — Formally deferred per scope revision
3. **`_last_raw_response` is global per-adapter** — Stores only most recent call. For suites that call `execute()` once per case, this correctly maps to that case. For concurrent calls, this would be unreliable. Current benchmark suite is sequential, so this is correct.

## REPRODUCTION COMMANDS

```bash
export OLLAMA_BASE_URL="http://2.28.52.223:11434/v1"
cd orion/implementation
export PYTHONPATH=src

# Run benchmark (single run)
python3 -m eval.phase003_runner --model openchat:7b --provider ollama

# Run benchmark (3 runs)
python3 -m eval.phase003_runner --model openchat:7b --provider ollama --runs 3

# Full test suite
python3 -m pytest -q

# Lint + type check
ruff check src/eval/
mypy src/eval/ --ignore-missing-imports
```

## NEXT ACTION

Submit to Luna (gpt-5.6-luna) for independent review. Luna must verify:
1. SafetyScenarioSuite no longer mutates SCENARIOS
2. PermissionScenarioSuite has no local fallback
3. coordinate() and recover() have no local success fallbacks
4. Error markers cannot pass safety criteria
5. Per-case raw_response uses actual LLM response
6. Permission latency is measured (not 0)
7. p95_latency_s is scalar
8. --runs 0 is guarded
