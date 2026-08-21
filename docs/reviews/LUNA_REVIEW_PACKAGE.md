# LUNA REVIEW PACKAGE — Phase 002 (ORION Evaluation System) — Round 6

## PROJECT
ORION — Physical Intelligence OS

## PHASE
002 — ORION Evaluation System

## COMMIT SHA
(to be filled after commit)

## BRANCH
main

## TASK
Create the official ORION benchmark system (ORION EVAL) with 12 benchmark categories, full result metadata, automated report generation, and CLI runner.

## PREVIOUS LUNA REVIEWS
- Round 1: REQUIRES_CHANGES — 8 findings. All fixed.
- Round 2: REQUIRES_CHANGES — 4 findings. All fixed.
- Round 3: REQUIRES_CHANGES — 7 findings. All fixed.
- Round 4: REQUIRES_CHANGES — 6 findings. All fixed.
- Round 5: REQUIRES_CHANGES — 1 finding (metadata normalization). Fixed in this commit.

## LUNA ROUND 5 FINDING + FIX

### R5 Finding: Metadata normalization incomplete for None/empty values
**Fix:** 
- `_ensure_metadata()` now uses a `_clean()` helper that treats `None`, empty string `""`, and whitespace-only strings as missing.
- System attribute fallbacks use `getattr(system, attr, None)` and apply `_clean()` — so `model_name=None`, `version=""`, `hardware="  "` all fall back to `"unknown"`.
- Added `BENCHMARK_VERSION = "1.0.0"` constant. Custom results with the silent dataclass default `test_version="1.0"` are overridden with `BENCHMARK_VERSION`.
- 2 new regression tests: None/empty system metadata gets "unknown" fallback, test_version uses BENCHMARK_VERSION not "1.0".

## ACCEPTANCE CRITERIA
1. All 12 benchmark categories have concrete tests ✅
2. Every result includes all required metadata fields ✅ (robust _ensure_metadata with None/empty handling)
3. ORIONEval.run_all() produces a complete reproducible report ✅ (try/finally lifecycle)
4. CLI runner works with filtered categories ✅ (nonzero exit on error, rejects empty)
5. No invented results — all metrics are measured ✅ (OPIB default-success removed)
6. All tests pass ✅ (739 passed, 9 skipped, 0 failed)
7. Existing tests still pass ✅ (700 original + 39 new acceptance)
8. Lint clean, type clean ✅

## TEST RESULTS
- **Total:** 739 collected, 739 passed, 9 skipped, 0 failed
- **Acceptance tests:** 39/39 passing (including 6 R3 + 6 R4 + 2 R5 regression tests)
- **Benchmark:** 12/12 categories passing
- **Command:** `python3 -m pytest --timeout=30 -q --ignore=tests/load --ignore=tests/unit/test_live_gpt4o.py`

## LUNA ROUND 5 REGRESSION TESTS
- test_none_system_metadata_gets_fallback: None model_name, empty version, whitespace hardware all get "unknown"
- test_test_version_uses_benchmark_version: dataclass default "1.0" overridden with BENCHMARK_VERSION "1.0.0"

## SECURITY RESULTS
No security changes — evaluation framework only.

## SAFETY RESULTS
Safety decision tests with negated-response and missing-interface validation.

## LICENSE RESULTS
All ORION-owned code: Apache 2.0. No new dependencies.

## CI RESULTS
- Ruff: clean (0 errors)
- Mypy: clean (0 issues, 62 source files)

## KNOWN LIMITATIONS
- Mock system used for benchmark testing (no live model calls)
- Cost estimation is heuristic (latency-based), not actual API billing
- Multimodal test uses mock perception (no real image processing)
- 9 legacy enum categories intentionally deferred to future phases
- Report IDs and timestamps are nondeterministic (time-based)
- Latency/memory measurements vary (performance counters)

## REPRODUCTION COMMANDS
```bash
pip install -e ".[dev]"
ORION_LEASE_SIGNING_KEY=test-lease-signing-key \
ORION_AUDIT_KEY=test-audit-key \
ORION_EMERGENCY_HMAC_KEY=test-emergency-hmac-key \
ORION_SAFETY_AUTH_KEY=test-safety-key \
python3 -m pytest --timeout=30 -q --ignore=tests/load --ignore=tests/unit/test_live_gpt4o.py
python3 -m ruff check src/ tests/
python3 -m mypy src/ --ignore-missing-imports
PYTHONPATH=src python3 -m eval.run --categories all --output /tmp/eval_report.json --format json
PYTHONPATH=src python3 -m eval.run --categories temporal_reasoning,planning --output /tmp/eval_filtered.json --format json
```
