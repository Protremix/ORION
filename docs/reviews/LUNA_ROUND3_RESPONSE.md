# Luna Round 3 Response

**Model:** gpt-5.6-luna
**Date:** 2026-08-22
**Phase:** Phase 003 (Model Selection)

VERDICT: REQUIRES_CHANGES

SUMMARY: The repository implements several requested mechanisms correctly, including `details` serialization, distribution-based latency measurement, `_pin_model()` invocation, PermissionDisciplineTest filtering, and a formal 32B/72B scope revision. However, the scored benchmark still contains bypass/fallback paths, per-case evidence is incomplete or synthetic in places, and `--runs N` is broken after the first run because `SafetyScenarioSuite` mutates class-level scenarios.

BLOCKING ISSUES (if any):
1. **Multi-run support fails on the second run.** `SafetyScenarioSuite.run()` removes `"expected"` from each class-level scenario via `scenario.pop("expected")`; subsequent suite instances reuse the already-mutated `SCENARIOS` list and raise `KeyError`. This breaks `--runs N` as implemented.  
   **Reference:** `src/eval/phase003_benchmarks.py`, `SafetyScenarioSuite.run()`, loop over `self.SCENARIOS`, approximately lines 300–315. Use a copied scenario, e.g. `scenario = dict(raw_scenario)`, before removing fields.

2. **Adapter-local fallback remains in a scored test.** `PermissionScenarioSuite` contains a fallback to `system.reason()` with keyword heuristics when `_call_llm` is unavailable. It also includes a malformed evidence record (`{"case": i, "result": "CORRECT (heuristic)"}`) that does not satisfy the required per-case schema.  
   **Reference:** `src/eval/phase003_benchmarks.py`, `PermissionScenarioSuite.run()`, `else` branch after `if hasattr(system, "_call_llm")`, approximately lines 570–625. Remove this branch or classify the test explicitly as non-scored.

3. **Additional adapter-local behavior can fabricate scored results.** `CloudModelAdapter.coordinate()` returns a locally constructed successful coordination result when the LLM response is invalid, and `recover()` rewrites any parsed non-success status to `"recovered"`. These are bypasses inconsistent with the claim that all scored behavior requires valid LLM output.  
   **References:**  
   - `src/eval/cloud_adapter.py`, `coordinate()`, fallback return block, approximately lines 420–430.  
   - `src/eval/cloud_adapter.py`, `recover()`, status-rewriting block, approximately lines 445–455.  
   Remove these behaviors or ensure the corresponding tests are explicitly excluded from scored Phase 003 results.

4. **Transport failures can pass safety criteria without a valid model response.** `_call_llm()` converts exceptions into an `"[ERROR: ...]"` string. `execute()` converts any unparseable result—including that error marker—into `{"status": "blocked"}`. Consequently, a connection failure can count as a successful result for dangerous-action cases in `DenyByDefaultSuite` and blocked safety cases.  
   **References:**  
   - `src/eval/cloud_adapter.py`, `_call_llm()` exception handler, approximately lines 185–195.  
   - `src/eval/cloud_adapter.py`, `execute()` parse-failure return, approximately lines 285–300.  
   - `src/eval/phase003_benchmarks.py`, `DenyByDefaultSuite.run()` and `SafetyScenarioSuite.run()`, status evaluation blocks.  
   Return an explicit error result or make the benchmark distinguish fail-closed safety behavior from successful LLM evaluation.

5. **Per-case raw evidence is not consistently raw model evidence.** In `DenyByDefaultSuite` and `SafetyScenarioSuite`, `raw_response` is `str(result)` after `system.execute()` has parsed or synthesized the response; it is not the raw LLM response. The adapter’s `_last_raw_response` is global and only retains the most recent call, so it cannot reliably associate raw output with each case.  
   **References:**  
   - `src/eval/phase003_benchmarks.py`, `DenyByDefaultSuite.run()`, case result construction.  
   - `src/eval/phase003_benchmarks.py`, `SafetyScenarioSuite.run()`, case result construction.  
   - `src/eval/cloud_adapter.py`, `_last_raw_response` and `get_stats()`.  
   Expose per-call raw response and latency, or have scored suites call a structured adapter API that returns case-specific evidence.

6. **Permission case latency is fabricated as zero.** Every `PermissionScenarioSuite` case records `"latency_ms": 0` despite making an actual `_call_llm()` request. This fails the stated evidence requirement for actual per-case latency and undermines latency/evidence auditability.  
   **Reference:** `src/eval/phase003_benchmarks.py`, `PermissionScenarioSuite.run()`, all case-result append blocks, approximately lines 520–625. Measure around the call or expose the adapter’s last-call latency.

7. **Fix 10 remains incomplete and acceptance criterion 11 is therefore not satisfied.** The required post-fix re-runs for `openchat:7b` and `qwen2.5:14b` are explicitly pending. The repository contains only Round 2 results and commands, not actual corrected-suite result artifacts.  
   **Reference:** review package “Fix 10: Re-run…” and `docs/evaluation/raw_results_*.json` as described. The supplied material does not provide post-fix run evidence.

8. **Commit identity cannot be independently verified from the supplied source package.** The package states SHA `72a8c3e`, but no repository metadata or `git rev-parse HEAD` output is included in the review material.  
   **Reference:** review package header versus repository state. This must be verified directly with `git rev-parse HEAD` and the commit’s file tree before approval.

RECOMMENDATIONS (if any):
1. Add regression tests that execute `run_phase003_benchmark(..., runs=3)` or invoke the CLI with mocked calls, specifically checking that all runs complete and that scenario definitions remain unchanged.
2. Replace class-level scenario mutation with immutable definitions or copied dictionaries.
3. Add a strict evidence-schema validator asserting every case contains `case_id`, `prompt`, `expected`, `raw_response`, `parsed_result`, `pass_fail`, `latency_ms`, and `error`.
4. Ensure multi-run summaries store actual per-run P95 values; currently `run_details[*]["p95_latency_s"]` is populated with the entire `latency_samples_ms` array rather than a P95 scalar.  
   **Reference:** `src/eval/phase003_runner.py`, multi-run summary construction, `p95_latency_s` field, near the end of `main()`.
5. Validate `--runs` is at least 1; `--runs 0` currently leaves `all_results` empty and later indexes `all_results[-1]`.
6. Preserve full raw responses in per-case evidence, or document and enforce a deliberate truncation policy with a separate evidence artifact.
7. The 32B/72B scope revision document is substantive and present, but final model selection should remain explicitly provisional until the deferred evaluation is completed or formally waived.

CONFIDENCE: HIGH