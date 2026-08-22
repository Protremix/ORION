# Luna Phase 003 Round 2 Verdict
# Luna Phase 003 Review

## Verdict: **REQUIRES_CHANGES**

The submitted results do not establish that Phase 003 acceptance criteria are satisfied. There are several blocking discrepancies between the claimed methodology, the implementation, and the raw evidence. The openchat:7b result is not currently credible as an independently reproducible 12/12 model-capability result.

The review package also identifies commit `c8390dd`, while the requested review commit is `33da312`. That commit identity mismatch must be resolved before the repository state can be accepted.

---

## Acceptance criteria

| # | Criterion | Verdict |
|---|---|---|
| 1 | All 7 Round 1 blocking issues fixed | **NOT SATISFIED** |
| 2 | Independent deny-by-default and temporal-reasoning test sets | **NOT SATISFIED** |
| 3 | All criteria use LLM calls, not adapter-local behavior | **NOT SATISFIED** |
| 4 | Multiple cases per criterion and 74 total API calls | **NOT SATISFIED** |
| 5 | Thresholds framed as model eligibility, not safety guarantees | **SATISFIED** |
| 6 | P95 latency uses warmup and repeated trials | **NOT SATISFIED** |
| 7 | Fully independently reproducible with provenance | **NOT SATISFIED** |
| 8 | Configurable Ollama endpoint with localhost default | **SATISFIED** |
| 9 | At least one model achieves 12/12 on expanded suite | **NOT SATISFIED as an evidenced claim** |

### 1. All seven Round 1 issues

**NOT SATISFIED.**

Some changes are present, but the implementation does not actually resolve all seven issues.

- **Alias separation:** The reported metric names are distinct, but the supplied source does not include `phase003_benchmarks.py`, where the expanded deny-by-default and temporal suites are implemented. The raw results contain only aggregate labels such as `"deny_by_default_suite_10_cases"` and `"temporal_reasoning_suite_10_cases"`; no individual cases or outputs are available for verification.
- **Local behavior:** This issue remains present. `PermissionDisciplineTest` directly calls:

  ```python
  PermissionChecker.check_permission(...)
  ```

  It does not query the model. The raw result also reports zero latency for the permission suite. Therefore, the claimed “all criteria route through LLM API calls” is false.
- **Sample size:** The count of 74 calls is reported, but the evidence does not demonstrate that every criterion has multiple independent model cases. Several base tests have only one case, and expanded results are aggregate labels without per-case evidence.
- **Threshold framing:** Documentation does frame thresholds as eligibility criteria. This item is addressed.
- **P95 latency:** The implementation does not reliably compute P95; see criterion 6 below.
- **Provenance:** Metadata is present, but critical provenance is absent or not populated, including model digest, endpoint actually used, raw model outputs, per-case results, and reproducible latency samples.
- **Endpoint configuration:** This is correctly implemented, but does not compensate for the other unresolved issues.

### 2. Independent deny-by-default and temporal-reasoning sets

**NOT SATISFIED.**

The metric names are distinct and the reported categories differ:

- `deny_by_default` → `safety_decisions`
- `temporal_reasoning_suite` → `temporal_reasoning`

That is evidence of structural separation, but not proof of independent test sets. The actual `phase003_benchmarks.py` implementation is not included in the supplied source, and the raw reports contain no case IDs, prompts, expected answers, actual outputs, or per-case scores.

Additionally, `logical_inference` is assigned to `EvalCategory.TEMPORAL_REASONING`, which is semantically incorrect and makes category-level aggregation ambiguous.

### 3. All criteria use LLM calls

**NOT SATISFIED.**

There are multiple adapter-local or deterministic paths:

- `PermissionDisciplineTest` directly invokes `PermissionChecker`; no LLM call occurs.
- `MemoryRecallTest` calls the LLM, but `CloudModelAdapter.recall()` falls back to the local `_memory` store if parsing fails or the model says “not found.” Thus a successful result may be produced without a valid LLM answer.
- `WorldStateTrackingTest` calls `get_world_state()`, but the adapter has a deterministic fallback returning position `50`.
- `recover()` normalizes arbitrary responses into `"status": "recovered"`.
- `perceive()` returns positive-looking fallback fields even when the model response is not a valid structured answer.
- `get_confidence()` returns `0.85` on parse failure.
- `select_tool()` returns `"recall"` as a safe default if parsing fails.

Consequently, a passing benchmark result does not necessarily mean the model demonstrated the tested capability.

The raw result itself exposes this problem: permission, deny-by-default, temporal suite, safety suite, and latency-suite entries have zero or near-zero per-result latency despite the claim that all criteria use model calls.

### 4. Multiple cases and 74 API calls

**NOT SATISFIED.**

The raw adapter statistics report 74 calls, but that alone is insufficient.

Problems include:

1. The base suite contains one case for each of several criteria:
   - one logical-inference prompt;
   - one planning prompt;
   - one decomposition prompt;
   - one safety prompt;
   - one memory prompt;
   - one world-state prompt;
   - one recovery prompt;
   - one confidence prompt;
   - one multimodal prompt;
   - one coordination prompt.

2. The expanded suite results are aggregate records with labels such as `"safety_scenario_suite_10_cases"` but no individual case data.

3. The 14B run reports 74 calls but also reports 8 errors. The package describes this as 74 API calls, but does not establish how many valid model responses were scored.

4. No confidence intervals, repeated benchmark runs, case-level distributions, or seed/control information are provided. Seventy-four calls in one run is not by itself statistical robustness.

The claim is therefore not independently auditable.

### 5. Thresholds are eligibility criteria, not safety guarantees

**SATISFIED.**

The documentation explicitly states that the thresholds qualify models for integration and are not system-level safety guarantees. It also correctly identifies the Safety Layer as a separate phase.

This criterion is satisfied as a documentation and scope-framing requirement.

### 6. P95 latency with warmup and repeated trials

**NOT SATISFIED.**

The P95 implementation is materially defective.

In `phase003_runner.py`:

```python
details = r.get("details", {})
p95_latency_ms = details.get("p95_ms", r.get("latency_ms", 0))
```

However, `EvalResult.to_dict()` does not serialize `details` at all. Therefore, `details.get("p95_ms")` will normally be empty, and the runner falls back to the single `latency_ms` field of the `latency_p95` result.

The openchat raw result demonstrates this:

- reported `latency_p95` mandatory value: `0.192 s`;
- latency result `latency_ms`: `192.466`;
- latency result `value`: `0.234988...`;
- no serialized `details` containing 20 latency samples or `p95_ms`.

Thus the reported `0.192s` is effectively the latency of one benchmark result, not demonstrably the P95 of 20 measured trials.

There is also an internal inconsistency in the 14B result:

- reported P95: `0.377s`;
- several ordinary model calls took approximately 120 seconds;
- total run time was approximately 1,504 seconds;
- eight API errors occurred.

Even if a dedicated latency test is intended to measure only a subset of calls, the implementation does not preserve the samples needed to prove that distinction.

### 7. Independent reproducibility and provenance

**NOT SATISFIED.**

The reports include useful basic metadata, but not enough for independent reproduction.

Missing or inadequate items include:

- exact reviewed commit, with the package inconsistently naming `c8390dd` versus requested `33da312`;
- per-case prompts and expected answers for the expanded suites;
- raw model outputs;
- per-case pass/fail decisions;
- latency trial samples, warmup samples, and P95 calculation method;
- actual Ollama endpoint used;
- model digest and exact model configuration;
- quantization and server details;
- random seed or deterministic-generation controls;
- evidence that `_pin_model()` was ever called.

`CloudModelAdapter._pin_model()` exists, but the runner never invokes it. Therefore, the claimed model digest and environment pinning are not actually present in the shown execution path.

The reproduction command is useful, but rerunning it would not reproduce the submitted result: the endpoint is mutable, the server is shared, only one run is reported, and the raw case-level inputs/outputs are unavailable.

### 8. Configurable Ollama endpoint

**SATISFIED.**

The adapter correctly uses:

```python
env_base_key = f"{provider.value.upper()}_BASE_URL"
self.api_base = os.environ.get(env_base_key, config["base_url"])
```

For Ollama this gives:

- configurable via `OLLAMA_BASE_URL`;
- default `http://localhost:11434/v1`.

The native endpoint conversion to `/api/generate` is also implemented.

Minor documentation issue: the CLI help text does not list `ollama` among the supported providers, although `_provider_from_string()` accepts it.

### 9. At least one model achieves 12/12 on the expanded suite

**NOT SATISFIED as an evidenced acceptance claim.**

The raw report records openchat:7b as passing all 12 mandatory criteria, but the evidence is not sufficient to accept that result:

- the underlying report contains 17 results, of which only 16 are considered passed by the report summary;
- the latency result has `status: "passed"` but `"passed": false`;
- permission discipline is local code, not model behavior;
- memory, world-state, recovery, confidence, perception, and tool selection all contain fallback paths that can manufacture passing outputs;
- expanded suite outputs are not included;
- the safety and deny-by-default case-level decisions are not available;
- the P95 number is not demonstrably a P95.

Therefore, “12/12 PASS” is a recorded runner verdict, not a credible independently verified model result.

---

# Required verification items

## 1. Were all seven Round 1 blocking issues fixed?

**No.**

Endpoint configuration and threshold wording were fixed. Metric naming was partially improved. The remaining blockers are:

- local/non-LLM scoring paths;
- lack of case-level evidence;
- defective P95 extraction;
- incomplete provenance;
- unsupported claims about independent expanded test sets.

## 2. Is the benchmark methodology sound and independently reproducible?

**No.**

The methodology is not yet sound for model selection because the evaluator mixes model behavior with adapter behavior and permissive fallbacks. The reports do not preserve enough data to independently recompute scores or determine whether a given result came from the LLM.

## 3. Is openchat:7b’s 12/12 result credible?

**No, not currently.**

The result may be directionally useful, but it is not acceptance-grade evidence. In particular:

- permission is evaluated locally;
- several capabilities have deterministic fallbacks;
- aggregate expanded-suite outputs are missing;
- P95 is not proven;
- only one run was conducted;
- no raw LLM outputs are recorded.

The strongest defensible statement is: **openchat:7b produced a passing runner summary under the current implementation.** It is not yet justified to state that the model itself achieved 12/12 on the expanded benchmark.

## 4. Is the 14B action-selection diagnosis correct?

**Not established; likely incomplete.**

The observed failure is real at the evaluator boundary: `plan()` returned one parsed step and received `0.5`.

The proposed root cause—verbose prose caused JSON parsing to fail—is plausible, but not proven:

- the actual raw response is not stored;
- the 14B run had 8 errors;
- the failing call took approximately 120 seconds, matching the configured request timeout;
- `_call_llm()` converts failures into an error string;
- the fallback newline parser would then produce one line, exactly matching the observed one-step result.

Thus the failure may be caused by a timeout/error response rather than merely format noncompliance. The diagnosis must remain an unverified hypothesis until the raw response, HTTP error state, timing, and parsing path are captured.

The recommendation to test stricter prompting or structured output is reasonable, but it must be tested rather than treated as the established root cause.

## 5. Is the model-selection recommendation justified?

**Not as a final Phase 003 recommendation.**

Among the tested and recorded results, openchat:7b is a reasonable provisional candidate because it has:

- the best reported mandatory score;
- low measured single-call latency;
- no reported adapter errors;
- stronger reported safety results than most tested alternatives.

However, the recommendation is not justified as a completed model-selection decision because:

1. 32B and 72B models were not evaluated, despite the phase scope.
2. openchat’s result is affected by local fallbacks and incomplete evidence.
3. qwen2.5:14b’s apparent weakness has not been diagnosed conclusively.
4. The latency comparison is not methodologically valid.
5. The models were not evaluated across repeated independent runs.
6. The benchmark does not test physical safety guarantees, as correctly acknowledged by the package.

The appropriate interim recommendation would be:

> **Provisional candidate for further evaluation: openchat:7b. No final model selection approval until the benchmark implementation is corrected and the 14B/32B/72B comparison is completed.**

---

# Required changes before approval

1. Review and reconcile the commit mismatch: `33da312` versus `c8390dd`.
2. Include and review the complete `phase003_benchmarks.py` implementation.
3. Remove adapter-local fallbacks from scored model-capability tests, or explicitly mark fallback results as failures.
4. Route permission-discipline evaluation through the model if it is intended to be a model criterion; otherwise classify it as a system test and exclude it from model ranking.
5. Store per-case:
   - case ID;
   - prompt;
   - expected result;
   - raw model response;
   - parsed result;
   - pass/fail reason;
   - latency;
   - error state.
6. Correct P95 computation and serialize the actual latency samples.
7. Invoke `_pin_model()` and record digest, quantization, endpoint, server version, and hardware.
8. Repeat the benchmark across multiple runs and report run-to-run variation.
9. Evaluate the 32B and 72B candidates or formally revise the phase scope.
10. Re-run openchat:7b and qwen2.5:14b after these corrections.
11. Capture the 14B raw planning response and distinguish timeout, transport error, malformed JSON, and genuinely short plan output.

Until these changes are completed, Phase 003 should remain **REQUIRES_CHANGES**.