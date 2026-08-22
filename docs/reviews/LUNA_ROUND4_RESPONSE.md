# Luna Round 4 Response

**Model:** gpt-5.6-luna
**Date:** 2026-08-22
**Phase:** Phase 003 (Model Selection)
**Commit:** 546ca70

VERDICT: REQUIRES_CHANGES

SUMMARY: Several implementation fixes are present: `SCENARIOS` is no longer mutated, the permission heuristic fallback was removed, adapter success fabrication was removed, and normal permission-call latency is measured. However, Fix 10 is explicitly incomplete, the supplied commit SHA is not the required `546ca70`, and the multi-run P95 summary currently records `0.0` rather than the measured scalar.

BLOCKING ISSUES (if any):

1. **Fix 10 re-runs remain incomplete.**  
   The review package explicitly states that the `openchat:7b` and `qwen2.5:14b` post-fix re-runs are “IN PROGRESS,” with no completed result artifacts supplied. Therefore the required benchmark re-validation is not complete.  
   **Reference:** `docs/reviews/LUNA_REVIEW_PACKAGE.md`, “Known Limitations,” item 1 and “Block 7: Fix 10 re-runs incomplete.”

2. **Required commit identity is not satisfied or independently verifiable.**  
   The requested commit SHA is `546ca70`, but the package identifies the current commit as `485dbd8`. The supplied material also contains no Git metadata or command output that independently verifies either SHA.  
   **Reference:** `docs/reviews/LUNA_REVIEW_PACKAGE.md`, header `COMMIT SHA: 485dbd8`; requested SHA: `546ca70`.

3. **Multi-run P95 summary is functionally incorrect.**  
   `run_phase003_benchmark()` computes `p95_latency_s` locally but does not store `p95_latency_ms` in `final_report`. The multi-run summary then reads:

   ```python
   r.get("p95_latency_ms", 0) / 1000.0
   ```

   Since that key is absent, every `run_details[*]["p95_latency_s"]` value becomes `0.0`. It is scalar, but not the measured P95 value.  
   **Reference:** `src/eval/phase003_runner.py`, `run_phase003_benchmark()`, P95 calculation around lines 260–280; `main()`, multi-run `run_details` construction around lines 480–490.

4. **Permission latency is still fabricated as zero on failure paths.**  
   Normal `_call_llm()` calls are timed correctly, but the no-LLM path records `latency_ms: 0`, and the exception path also records `latency_ms: 0` despite the call having consumed measurable time. This does not fully satisfy the requirement that every case have measured latency.  
   **Reference:** `src/eval/phase003_benchmarks.py`, `PermissionScenarioSuite.run()`, no-LLM branch around lines 555–566 and exception branch around lines 625–635. Capture elapsed time for exceptions as well; classify the no-LLM path as not executed rather than presenting zero latency as a measurement.

5. **Per-case raw-response capture remains only conditionally reliable.**  
   `DenyByDefaultSuite` and `SafetyScenarioSuite` read the adapter’s global `_last_raw_response`. This works for the current sequential `CloudModelAdapter` path, but it is not intrinsically case-bound and can be stale for systems whose `execute()` does not update that attribute or when an exception occurs. The fallback is also a serialized parsed result rather than raw model output.  
   **Reference:** `src/eval/phase003_benchmarks.py`, `DenyByDefaultSuite.run()` and `SafetyScenarioSuite.run()`, `raw_llm` assignments around lines 95–100 and 315–320; `src/eval/cloud_adapter.py`, `_last_raw_response` handling around lines 90–105 and 145–225. Prefer a per-call structured return containing raw response, parsed result, error, and latency.

VERIFIED FIXES:

- **Safety scenario mutation:** Fixed. `SafetyScenarioSuite.run()` now reads `scenario["expected"]` and constructs `scenario_prompt` without popping from `SCENARIOS`.  
  **Reference:** `src/eval/phase003_benchmarks.py`, around lines 300–305.

- **Permission heuristic fallback:** Removed. The suite uses `_call_llm()` only and records failure when that method is unavailable.  
  **Reference:** `src/eval/phase003_benchmarks.py`, `PermissionScenarioSuite.run()`, around lines 550–570.

- **`coordinate()` and `recover()` local success fallbacks:** Fixed. Invalid coordination/recovery responses now produce failed results, and `recover()` no longer rewrites an LLM status to `"recovered"`.  
  **Reference:** `src/eval/cloud_adapter.py`, `coordinate()` around lines 425–440; `recover()` around lines 450–475.

- **Transport failures passing as blocked:** Fixed for the supplied adapter path. `_call_llm()` returns an error marker, `execute()` maps it to `status: "error"`, and the safety suites reject error-marker statuses.  
  **Reference:** `src/eval/cloud_adapter.py`, `execute()` around lines 285–305; `src/eval/phase003_benchmarks.py`, safety status checks around lines 105–115 and 330–340.

- **P95 array issue:** The runner’s primary `p95_latency_s` calculation is scalar, and the multi-run field is also scalar in type. However, as noted above, the multi-run value is currently always zero because the source field is missing.

- **`--runs 0` guard:** Fixed.  
  **Reference:** `src/eval/phase003_runner.py`, `main()`, around lines 410–415.

RECOMMENDATIONS (if any):

1. Store the measured P95 explicitly in `final_report`, for example:

   ```python
   final_report["p95_latency_ms"] = p95_latency_ms
   final_report["p95_latency_s"] = p95_latency_s
   ```

   Then consume that field in the multi-run summary.

2. Replace the global `_last_raw_response` mechanism with a structured per-call API, such as:

   ```python
   {
       "raw_response": ...,
       "parsed_result": ...,
       "latency_ms": ...,
       "error": ...
   }
   ```

3. Preserve the full raw response in evidence or document the 200-character truncation policy and write the complete response to a separate artifact.

4. Add regression tests covering:
   - three consecutive suite runs;
   - transport failure in each safety suite;
   - permission-call exceptions with nonzero measured latency;
   - multi-run P95 propagation;
   - verification that the final report contains the expected commit SHA.

5. Use a robust error predicate rather than only `status.startswith("[error")` if arbitrary system implementations are supported; inspect both status and explicit error fields before awarding safety credit.

CONFIDENCE: HIGH