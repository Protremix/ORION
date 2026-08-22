# Luna Round 5 Response

**Model:** gpt-5.6-luna
**Date:** 2026-08-22
**Phase:** Phase 003 (Model Selection)
**Commit:** 8e3b22a

## FINAL VERDICT: REQUIRES_CHANGES

The supplied tests and raw JSON are internally suggestive, but they do not establish a valid Round 4 result. The critical SafetyScenarioSuite answer leakage invalidates the safety evaluation, and the Round 4 latency/permission fixes are not regression-tested.

## 1. Round 4 test coverage

### p95 latency in `final_report`

**Not adequately covered.**

`test_eval_result_to_dict_includes_details` verifies that an `EvalResult` can serialize a `details["p95_ms"]` field, but it does not verify that:

- the Phase 003 runner computes p95 correctly;
- p95 is present in the actual `final_report`;
- `p95_latency_ms`, `p95_latency_s`, and latency samples agree;
- missing latency data fails safely rather than becoming zero;
- the final report uses the intended latency sample population.

The existing test only proves generic serialization, not the Round 4 runner behavior.

### Permission latency on failure paths

**Not covered.**

There are no tests for:

- `_call_llm` raising an exception;
- JSON parsing failure after a successful call;
- aggregate permission latency including failed attempts;
- preserving case-level latency while updating aggregate latency;
- no-LLM behavior versus exception behavior;
- adapter API/error counters when permission tests call `_call_llm` directly.

The current tests mock successful `_call_llm` responses or test unrelated adapter behavior. They do not exercise the accounting paths identified in Part 2.

## 2. Consistency of the benchmark results

The mandatory-criteria counts are structurally consistent:

- `qwen2.5:14b`: 12 criteria, all marked passed.
- `openchat:7b`: 12 criteria, with only `safety_decision` marked failed.

However, there is a significant latency inconsistency:

```text
qwen2.5:14b:
  p95_latency_ms: 720.58
  avg_latency_ms: 1872.91

openchat:7b:
  p95_latency_ms: 513.66
  avg_latency_ms: 1126.37
```

A p95 cannot be below the arithmetic mean when both statistics describe the same sample population. This could be explained only if:

- `p95_latency_ms` is calculated from a different subset of calls; or
- `avg_latency_ms` and p95 use different measurement sources; or
- one of the values is incorrectly labeled or calculated.

The report says `latency_samples_count: 74`, matching `api_calls: 74`, which makes the distinction unclear. The evidence package must explicitly identify the population used for each statistic and provide the raw sample list or a reproducible derivation.

The raw JSON is therefore not fully self-consistent as presented.

## 3. Is `qwen2.5:14b` genuinely 12/12 PASS?

**No—not established.**

The raw JSON reports 12/12 passed, but that is only the result of the current implementation. It is not a valid independent evaluation if the SafetyScenarioSuite exposes expected answers to the model.

Additionally:

- permission failure-path latency is not validated;
- p95 computation and sample provenance are unresolved;
- the latency statistics are inconsistent with the adapter average.

The correct statement is: **the generated report claims 12/12 PASS; the evidence does not currently justify calling that a genuine 12/12 result.**

## 4. Is `openchat:7b` genuinely 11/12 with `safety_decision` failing?

**The JSON claims this, but the result is not yet trustworthy.**

The numerical structure is correct:

```text
safety_decision: 0.8 < 0.95
```

and the other 11 criteria are marked passed. However, the same validity concerns apply:

- SafetyScenarioSuite answer leakage compromises the safety score.
- The latency evidence is inconsistent.
- Round 4 failure-path behavior is untested.

Thus, it is accurate to say that the raw report contains **11 passing criteria and one reported failure**, but not that it has established a valid 11/12 benchmark outcome.

## 5. Fabricated results, missing evidence, and inconsistencies

I cannot prove fabrication from the supplied material alone. The results may have been produced by a real run. However, the package has insufficient evidence to support the claims.

### Missing or inadequate evidence

- No raw latency sample arrays are included in the benchmark summary.
- No reproducible p95 calculation is shown.
- No test demonstrates p95 propagation into `final_report`.
- No permission exception-path test is present.
- No JSON parsing-failure latency test is present.
- No test confirms aggregate permission latency includes every attempted call.
- No independent test confirms that scenario prompts do not contain expected answers.
- No evidence separates benchmark calls from unrelated adapter calls.

### Specific inconsistencies

1. **p95 below average** for both models, unless different populations are being used.
2. **74 latency samples** appear to correspond to all adapter calls, despite prior claims involving a dedicated latency trial set.
3. **Permission scores** are reported, but permission latency accounting is not validated.
4. **`api_calls: 74` and `errors: 0`** do not demonstrate that permission calls exercised the adapter's normal accounting path, because the permission suite directly invokes `_call_llm`.
5. The unit tests validate interfaces and serialization more than benchmark correctness.

## 6. Critical safety issue: answer leakage

**Yes. The SafetyScenarioSuite leaks expected answers to the model, as identified in Part 2.**

If the prompt or scenario data supplied to the model contains the expected decision, expected classification, reference answer, or equivalent answer-bearing field, then the model is not independently solving the safety scenario. The resulting `safety_decision` score is contaminated.

This is a blocking issue because:

- `safety_decision` is a mandatory criterion;
- `deny_default` may also be affected if the expected deny/allow outcome is exposed;
- the reported perfect Qwen safety result cannot be treated as model evidence;
- the OpenChat safety comparison is not cleanly interpretable.

The oracle must remain outside the model-visible input. The evaluator should retain expected answers in a separate structure and compare the model's output after the call. Regression tests should explicitly assert that expected labels are absent from the generated model prompt.

## BLOCKING ISSUES

1. **SafetyScenarioSuite answer leakage**
   - Remove expected answers and reference decisions from all model-visible prompts/context.
   - Keep oracle answers evaluator-side.
   - Add a regression test proving expected labels are not included in the prompt.
   - Re-run all safety-related benchmarks after correction.

2. **Round 4 p95 behavior is not regression-tested**
   - Add an end-to-end test against `phase003_runner` verifying p95 appears in `final_report`.
   - Test exact sample provenance and units.
   - Replace the current index-based calculation with a defined percentile method.
   - Treat missing/empty latency data as unavailable or failed, never as `0`.

3. **Permission failure-path latency is not correctly covered**
   - Add tests for `_call_llm` exceptions and JSON parsing failures.
   - Ensure every attempted call contributes to aggregate latency through a single `finally`/post-call accounting path.
   - Preserve `latency_ms = -1` only for the structural no-LLM case.
   - Decide whether permission checks must use the adapter's public operation or explicitly update adapter accounting when calling `_call_llm` directly.

4. **Latency evidence is internally ambiguous/inconsistent**
   - Define whether p95 is over all adapter calls or only dedicated latency trials.
   - Report the sample count for that exact population.
   - Reconcile p95 with average latency and include reproducible raw samples or a calculation artifact.

5. **Reported model verdicts require revalidation**
   - Re-run both models after fixing answer leakage and latency accounting.
   - Do not retain the current 12/12 and 11/12 claims as final benchmark conclusions.

## RECOMMENDATIONS

- Add end-to-end runner tests rather than testing only `EvalResult.to_dict()`.
- Add explicit unavailable-measurement states instead of sentinel zero values.
- Include `latency_samples_ms`, percentile method, sample count, and source in the final report.
- Add invariant checks such as:
  - p95 must be at least the mean for the same population;
  - reported sample count must equal the population used;
  - failed calls must be represented in latency accounting;
  - missing measurements cannot satisfy a threshold.
- Separate benchmark counters from incidental adapter calls.
- Add tests for malformed model output, exceptions, timeouts, and direct `_call_llm` usage.
- Preserve per-case evidence sufficient to reproduce each criterion score.
- Re-run safety and permission suites independently after all fixes.

## CONFIDENCE: HIGH

The conclusions about missing test coverage, answer leakage, and the unresolved latency inconsistency are well supported by the supplied tests, prior Part 2 findings, and raw JSON.