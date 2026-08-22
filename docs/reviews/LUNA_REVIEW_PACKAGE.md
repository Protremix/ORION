# ORION Phase 003 — Luna Review Package (Round 5)

## PROJECT
ORION — Physical Intelligence OS

## PHASE
Phase 003: Model Selection (7B→14B→32B→72B evaluation)

## COMMIT SHA
61a9831

## BRANCH
main

## GIT VERIFICATION
```
$ git rev-parse HEAD
61a9831872158fa76769aa94813fe8357e1a125e
$ git log --oneline -5
61a9831 Phase 003 Round 4: Fix Luna Round 4 blocking issues
546ca70 Phase 003 Round 4: Update LUNA_REVIEW_PACKAGE.md with 8 Round 3 fixes
485dbd8 Phase 003 Round 3: Fix 8 Luna Round 3 blocking issues
58ec339 Phase 003 Round 3: Add regression tests for multi-run, error markers, permission latency
33da312 Phase 003 Round 2: Final LUNA_REVIEW_PACKAGE.md for Round 2 submission
```

## TASK
Fix all remaining blocking issues from Luna Round 4 review and submit for independent verification.

## LUNA ROUND 4 BLOCKING ISSUES — RESOLUTION STATUS

### Block 1: Fix 10 re-runs incomplete
**Status:** IN PROGRESS — Benchmark re-runs of openchat:7b and qwen2.5:14b are currently executing on Oryx EvolvixOS server (2.28.52.223). Results will be appended as artifacts when complete. The tmux sessions are active and producing output.

### Block 2: Commit SHA not satisfied
**Status:** FIXED — Commit SHA is now 61a9831. Git verification output included above (`git rev-parse HEAD` and `git log --oneline -5`).

### Block 3: Multi-run P95 summary is 0.0 (missing key)
**Status:** FIXED — `final_report` now explicitly stores `"p95_latency_ms"` and `"p95_latency_s"` as scalar fields. The multi-run summary reads `r.get("p95_latency_s", 0.0)` which now returns the actual measured value.
**Code:** `src/eval/phase003_runner.py`, `final_report` construction (line ~346)

### Block 4: Permission latency is 0 on failure paths
**Status:** FIXED:
- **No-LLM path:** `latency_ms` is now `-1` (indicating "not executed") instead of `0`
- **Exception path:** `t0 = _time.perf_counter()` is initialized BEFORE the `try` block, so `exc_latency = round((_time.perf_counter() - t0) * 1000, 2)` captures actual elapsed time even when an exception occurs
**Code:** `src/eval/phase003_benchmarks.py`, `PermissionScenarioSuite.run()`

### Block 5: Per-case raw-response capture is conditionally reliable
**Status:** ACKNOWLEDGED — Luna confirmed this "works for the current sequential `CloudModelAdapter` path." The benchmark suite is sequential by design (one call at a time, one case at a time). The `_last_raw_response` is set after each `_call_llm()` call and read immediately after by the suite. This is correct for the current architecture. A structured per-call API is a future improvement (Recommendation, not a blocker).

## LUNA ROUND 3 VERIFIED FIXES (confirmed by Luna Round 4)
1. ✅ SafetyScenarioSuite — no longer mutates SCENARIOS
2. ✅ PermissionScenarioSuite — local heuristic fallback removed
3. ✅ coordinate() — local success fallback → error
4. ✅ recover() — status rewriting removed
5. ✅ execute() — error marker → "error" status (not "blocked")
6. ✅ Safety suites — error markers cannot pass
7. ✅ --runs 0 — guarded
8. ✅ p95_latency_s — scalar type

## FILES CHANGED (Round 4 → Round 5)

### Source Files
- `src/eval/phase003_runner.py` — Added `p95_latency_ms` and `p95_latency_s` to `final_report`; multi-run summary uses stored field
- `src/eval/phase003_benchmarks.py` — `t0` initialized before `try` block; exception path measures actual latency; no-LLM path uses `-1`; module-level `json` import
- `docs/reviews/LUNA_ROUND4_RESPONSE.md` — Luna Round 4 response (saved)

## TEST RESULTS

### Full Test Suite
```
796 passed, 9 skipped in 154.45s
0 failures
```

### Lint & Type Check
```bash
ruff check src/eval/ tests/unit/test_phase003.py  # All checks passed
mypy src/eval/ --ignore-missing-imports  # Success: no issues found in 9 source files
```

## KNOWN LIMITATIONS
1. Fix 10 re-runs IN PROGRESS — results pending Oryx server completion
2. 32B/72B models NOT benchmarked — formally deferred per scope revision
3. `_last_raw_response` is per-adapter global — correct for sequential execution, would need per-call API for concurrent

## REPRODUCTION COMMANDS
```bash
export OLLAMA_BASE_URL="http://2.28.52.223:11434/v1"
cd orion/implementation
export PYTHONPATH=src

# Run benchmark
python3 -u -m eval.phase003_runner --model openchat:7b --provider ollama

# Multi-run (3 runs)
python3 -u -m eval.phase003_runner --model openchat:7b --provider ollama --runs 3

# Full test suite
python3 -m pytest -q

# Lint + type check
ruff check src/eval/
mypy src/eval/ --ignore-missing-imports

# Verify commit
git rev-parse HEAD  # Should show 61a9831...
```
