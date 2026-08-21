# Luna Review — Phase 003 Model Selection

**Model:** gpt-5.6-sol
**Date:** 2026-08-22

## Review Response

# Phase 003 Review — Model Selection

## Verdict: **REQUIRES_CHANGES**

The Phase 003 infrastructure appears directionally sound, and the reported CI results are encouraging. However, the evidence presented does **not support the conclusion that Qwen 2.5 7B has meaningfully passed 12 independent mandatory Physical AI model-selection criteria**.

The principal concern is benchmark validity: only seven LLM calls and 781 tokens underpin twelve reported passes, several criteria reuse the same metric, and some behavior is supplied by adapter-local state rather than the model. This primarily validates the adapter and benchmark plumbing, not the model’s suitability for Physical AI.

## Blocking issues

### 1. The benchmark does not sufficiently isolate model capability

The adapter implements memory, world state, agents, and potentially other benchmark-facing behavior using local fields such as:

```python
self._memory = {}
self.agents = ["agent_alpha", "agent_beta"]
self.world_model = {...}
```

The summary also acknowledges that some tests use local state. Therefore, criteria such as memory recall, world-state understanding, coordination, and possibly recovery may pass because of deterministic adapter behavior rather than Qwen inference.

Each reported criterion must identify:

- Number of model calls.
- Exact scenarios and prompts.
- Which outputs came from the model.
- Which outputs came from adapter logic.
- Scoring method and raw evidence.
- Whether a criterion measures model capability, system capability, or static interface conformance.

Model-selection claims must not attribute adapter-supplied behavior to the model.

### 2. Twelve criteria are not twelve independent measurements

At least two pairs reuse the same underlying metric:

- `safety_decision` and `deny_default` both use `safety_decision`.
- `logical_inference` and `temporal_reasoning` both use `logical_inference`.

The `deny_only` field suggests special handling, but the supplied runner excerpt does not demonstrate that this handling is implemented and tested.

Consequently, “all 12 criteria passed” is potentially misleading. Either:

1. Implement distinct datasets and scoring for each criterion, or
2. Report these as shared measurements and stop presenting them as twelve independently demonstrated capabilities.

There must also be a unit test proving that `deny_only=True` changes evaluation behavior and cannot silently fall back to the general safety score.

### 3. Seven calls are inadequate for threshold claims

Seven API calls cannot credibly establish:

- Safety accuracy ≥95%.
- Deny-by-default compliance of 100%.
- Planning accuracy ≥80%.
- Reasoning accuracy ≥75%.
- Permission discipline ≥90%.
- p95 latency below five seconds.

With such a small sample, a 1.0 score does not provide meaningful statistical confidence. In particular, a 95% safety threshold cannot be established from a handful of simplified prompts.

Before acceptance, define minimum sample counts per criterion and report:

- Numerator and denominator, not only a normalized score.
- Repeated runs.
- Confidence intervals or another stated uncertainty method.
- Failure examples.
- Per-scenario results.
- Aggregate and worst-case scores.

Safety and deny-by-default require a substantially larger, dedicated suite containing both allowed and denied actions.

### 4. Safety evidence is too weak for a Physical AI decision

The known limitations include:

- Simplified scenarios.
- No multi-turn testing.
- No adversarial prompts.
- No long-context testing.

Those are material gaps, especially for a system expected to affect the physical world. Safety evaluation should include at least:

- Prompt injection and instruction-conflict cases.
- Attempts to override safety policy.
- Ambiguous and incomplete state.
- Stale or contradictory sensor information.
- Unsafe actions disguised as benign subtasks.
- Multi-turn escalation and context poisoning.
- Tool-output injection.
- Fail-closed behavior on malformed output, timeout, unavailable model, and low confidence.
- Distinction between refusing unsafe actions and merely using safety-related language.

Phase 003 need not solve all future red-team work, but the current seven-call evaluation cannot justify a mandatory safety pass.

### 5. Latency p95 is not adequately characterized

A reported p95 of 2.63 seconds from approximately seven total calls is not a robust p95 measurement. It is also unclear whether all seven calls were included, whether a warm-up was excluded, or whether local deterministic operations were mixed with model requests.

The report must specify:

- Number of measured requests.
- Warm versus cold behavior.
- Prompt and output token distributions.
- Whether queueing and retries are included.
- Host hardware, CPU/GPU, memory, quantization, Ollama version, and model digest.
- Concurrency level.
- p50, p95, p99, maximum, and error/timeout rate.
- Exact percentile calculation.
- Whether the requirement is strictly `< 5.0` rather than `<= 5.0`.

Latency should be measured over enough repeated model requests to make a percentile meaningful.

### 6. The selected model artifact is not reproducibly identified

`qwen2.5:7b` is not sufficient identification for a model-selection ADR. Ollama tags and quantized artifacts may vary or be replaced.

ADR-005 and `MODEL_SELECTION.md` should pin:

- Exact model identifier and digest/hash.
- Quantization format and level.
- Context-size configuration.
- Ollama and runtime versions.
- Generation parameters.
- Prompt template/chat template.
- Hardware and operating environment.
- Benchmark code and dataset commit.
- Date of execution and raw result artifact.

Without this information, the 1.0 scores and latency result cannot be reproduced.

### 7. The Ollama endpoint is hard-coded to an external IP

The configuration contains:

```python
"http://2.28.52.223:11434/v1"
```

This creates security, portability, and reproducibility concerns:

- It commits an environment-specific address.
- It uses unencrypted HTTP.
- It may unintentionally direct prompts to a third-party or externally accessible service.
- It prevents straightforward local configuration.
- The code labels Ollama as local despite pointing to a non-loopback address.

The default should be a local endpoint such as `http://127.0.0.1:11434/v1`, with an explicit environment variable or constructor parameter for overrides. Remote non-TLS endpoints should require explicit opt-in and generate a warning or be prohibited.

No API secrets, sensitive prompts, or physical-system state should be sent over plain HTTP to a remote host.

### 8. The submitted excerpts do not provide auditable evidence for several acceptance criteria

The summary asserts that ADR-005, `MODEL_SELECTION.md`, 26 tests, Ruff, Mypy, and the complete test suite are present and passing, but those artifacts and command outputs were not supplied. The runner and adapter excerpts are also truncated, so the following cannot be reviewed:

- Actual criterion evaluation logic.
- Error and timeout behavior.
- Metric extraction and aggregation.
- Report generation.
- `deny_only` handling.
- Latency calculation.
- Raw benchmark records.
- Whether failed or missing metrics fail closed.

For re-review, provide the complete relevant files or a reviewable commit plus the generated report and CI logs. If the shown `self._t` line is only an excerpt boundary, no syntax issue is inferred; if it exists in the source, the source is incomplete.

## Required changes for re-review

1. **Separate model-generated behavior from adapter-generated behavior.**
   - Label every criterion as model, system, or interface evaluation.
   - Do not count static attributes or local dictionary behavior as model capability.

2. **Create independent tests for independently claimed criteria.**
   - Give deny-by-default its own unsafe-action dataset.
   - Give temporal reasoning a dataset distinct from generic logical inference.
   - Verify special criterion flags through unit tests.

3. **Increase benchmark depth and sample count.**
   - Use multiple scenarios and repeated runs per criterion.
   - Report counts, raw outputs, per-case scores, uncertainty, and failures.
   - Add meaningful adversarial and multi-turn safety coverage.

4. **Produce a valid latency benchmark.**
   - Use repeated real inference calls.
   - Record environment, token sizes, warm-up policy, percentiles, and errors.
   - Enforce the strict `<5.0s` requirement explicitly.

5. **Pin the model and execution environment.**
   - Record the exact Ollama model digest, quantization, runtime, template, parameters, hardware, and benchmark revision.

6. **Remove the hard-coded remote Ollama address.**
   - Use configurable endpoint injection.
   - Default to loopback.
   - Require TLS or explicit opt-in for remote access.

7. **Make result integrity fail closed.**
   - Missing metrics, malformed responses, empty datasets, scoring exceptions, timeouts, or adapter fallbacks must not produce a pass.
   - Report errors per criterion rather than only aggregate API errors.

8. **Supply auditable artifacts.**
   - Complete `MODEL_SELECTION.md`.
   - ADR-005.
   - Machine-readable raw benchmark results.
   - Full source for scoring and report generation.
   - Relevant unit tests.
   - Ruff, Mypy, and full-suite command outputs.

## Additional recommendations

- Compare Qwen against at least one baseline under identical prompts and hardware. A threshold gate can qualify a model, but “model selection” is stronger when relative trade-offs are documented.
- Use deterministic decoding where possible and record a seed if supported. `temperature=0.1` without a seed complicates reproducibility.
- Add retry policy carefully, distinguishing transport reliability from model latency and ensuring retries cannot conceal failures.
- Store per-call prompt/output token counts and latency rather than only totals.
- Add schema-constrained or validated outputs for safety and tool decisions; free-text keyword scoring is generally too fragile.
- Correct the adapter metadata: local Ollama hardware should not be reported generically as `"cloud-api"`.
- Test authentication-header behavior, HTTP errors, invalid JSON, unexpected response schemas, truncated responses, and provider-specific rate limits.

## Conclusion

The implementation may satisfy much of the **Phase 003 infrastructure** work, and the reported clean test/lint/type-check results are positive. Nevertheless, the current benchmark is too small and too entangled with adapter-local behavior to substantiate the claimed model-quality passes. The model-selection decision should remain provisional until the blocking benchmark-validity, reproducibility, latency, and endpoint-security issues are addressed.

## Raw Response Fields

- finish_reason: stop
- content length: 10784
- reasoning length: 0
- reasoning_content length: 0

## Usage

- Total tokens: 5525
- Prompt tokens: 2859
- Completion tokens: 2666
- Completion details: {"reasoning_tokens": 512, "audio_tokens": 0, "accepted_prediction_tokens": 0, "rejected_prediction_tokens": 0}
