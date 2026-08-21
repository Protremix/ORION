# Luna Review — Phase 003 Model Selection

**Model:** gpt-5.6-sol
**Date:** 2026-08-22

## Review Response

# Phase 003 Review Verdict: REQUIRES_CHANGES

The repository demonstrates that Phase 003 infrastructure and documentation were substantially implemented, but the evidence does **not** support the central conclusion that Qwen 2.5 7B genuinely passed all mandatory Physical AI criteria.

The reported test, lint, and type-check results are acceptable as stated, but the benchmark methodology has material validity problems.

## Acceptance-criteria assessment

| # | Criterion | Assessment |
|---|---|---|
| 1 | Define mandatory quality thresholds | **PARTIAL** — thresholds are defined, but several are not adequate for safety-critical Physical AI and some nominally separate criteria use the same measurement |
| 2 | Build cloud adapter for real APIs | **PASS WITH CONCERNS** — supports OpenAI-compatible APIs, although the Ollama endpoint is hard-coded and appears remote rather than local |
| 3 | Run full 12-category suite against Qwen 2.5 7B | **PARTIAL** — all categories are represented, but only seven LLM calls were made and several categories were handled by local deterministic adapter behavior |
| 4 | All 12 mandatory criteria pass | **NOT ESTABLISHED** — the generated evaluator says PASS, but several criteria are not independently measured and the sample size is insufficient |
| 5 | Document results in `MODEL_SELECTION.md` | **PASS**, subject to correcting the unsupported verdict |
| 6 | Document decision in ADR-005 | **PASS**, but the ADR should remain proposed until re-evaluation |
| 7 | Phase 003 infrastructure tests | **PASS AS REPORTED** — 26 passing |
| 8 | Ruff clean | **PASS AS REPORTED** |
| 9 | Mypy clean | **PASS AS REPORTED** |
| 10 | Full suite passes | **PASS AS REPORTED** — 770 passed, 9 skipped |

## Blocking issues

### 1. The benchmark does not independently measure all 12 mandatory criteria

At least two pairs of criteria are aliases of the same benchmark result:

- `safety_decision` and `deny_default` both use `safety_decision`
- `logical_inference` and `temporal_reasoning` both use `logical_inference`

The raw results consequently report identical values for measurements that are supposed to establish different capabilities.

A `deny_only` marker exists in the criteria definition, but the complete evaluation implementation was not provided, so it is not possible to verify that it actually filters and scores a meaningful set of deny-by-default cases. The artifact itself still identifies the source metric simply as `safety_decision`.

Likewise, a generic logical-inference test cannot establish temporal-reasoning performance unless it contains and separately scores a sufficient temporal case set.

**Required:** Create separate case sets and separately calculated metrics for all mandatory criteria.

### 2. Only seven model calls cannot substantiate 12 perfect capability scores

The report claims:

- 12 category scores of `1.000`
- 12 mandatory passes
- only 7 API calls
- multiple results with zero latency

The zero-latency results include:

- tool selection
- memory recall
- world-state tracking
- uncertainty calibration

These appear to be adapter-local behavior rather than model evaluation. For example, the visible unit tests explicitly expect `select_tool()` to map keywords such as “memory” to `recall` and “plan” to `plan`. This evaluates handwritten routing logic, not Qwen's tool-selection capability.

Similarly, `remember()`/`recall()` tests validate an in-memory dictionary. That does not demonstrate model context retention.

A model-selection benchmark must not credit the candidate model for capabilities implemented deterministically by the benchmark adapter.

**Required:** Ensure each model quality criterion invokes and evaluates the candidate model, or clearly reclassify adapter/system-level criteria so they are not attributed to Qwen.

### 3. The statistical sample is inadequate for percentage thresholds

A reported score of `1.0` from one or a few simplified cases does not establish:

- ≥95% safety accuracy
- 100% deny-by-default compliance
- ≥90% permission discipline
- or the other percentage thresholds

With one passing case, the observed score is 100%, but uncertainty is enormous. It does not provide evidence that the underlying success probability is at least 95%.

This is particularly critical for M2. “100%” deny-by-default compliance cannot be supported by a small finite benchmark in a general sense. The benchmark can only claim “zero violations in N specified cases,” with `N` documented.

**Required:** Define a minimum case count per criterion, preserve case-level results, and report confidence intervals or another justified statistical decision rule. Safety and permission tests require broad hazardous, ambiguous, malformed, and out-of-distribution scenarios.

### 4. The thresholds are not sufficient as Physical AI safety thresholds

The thresholds may be acceptable for an early model-screening experiment, but they are not appropriate as authorization for direct physical control:

- 95% safety accuracy permits one unsafe decision in twenty.
- 90% permission discipline permits one permission violation in ten.
- 70% error recovery permits three failed recoveries in ten.
- A 5-second latency bound is not “real-time” for many physical safety loops.
- Model inference latency does not establish bounded worst-case response time.

For Physical AI, the LLM must not be the sole safety enforcement mechanism. Safety, permissions, actuator limits, emergency stop, and timeout behavior need deterministic enforcement outside the model.

**Required:** Reframe the criteria as model eligibility thresholds rather than system safety guarantees. Document that Qwen cannot directly authorize safety-critical actuation. Define system-level safety invariants and fail-closed enforcement.

Recommended model-screening standards include:

- zero critical unsafe authorizations in the defined safety suite;
- zero permission-boundary violations;
- separate scoring by severity;
- explicit abstention/uncertainty behavior;
- deterministic policy enforcement independent of the model;
- latency requirements tied to the intended control tier, with the LLM excluded from hard real-time loops.

### 5. The p95 latency result is not robust

The reported p95 of 2.63 seconds appears to be calculated from only seven API calls and matches the largest detailed latency shown. That sample is too small to characterize tail latency.

It also does not document:

- warm-up behavior;
- number of warm and cold runs;
- concurrent load;
- server hardware;
- quantization actually used;
- model digest;
- prompt/token distributions;
- network conditions.

**Required:** Run a meaningful latency campaign with warm-up, repeated trials, documented hardware and model digest, and enough observations to estimate p95. Report cold-start separately.

### 6. Results are not independently reproducible or sufficiently provenance-backed

The result files are internally coherent: the seven non-zero detailed latencies roughly align with the total adapter latency, and 781 tokens is plausible. I do **not** find direct evidence that the values were fabricated.

However, genuineness cannot be verified from the supplied artifacts. Missing provenance includes:

- complete case-level prompts and responses;
- model output captures;
- Ollama model digest and quantization;
- runner command and commit hash;
- host/GPU configuration;
- evaluator configuration and random seed;
- raw per-call token and latency records;
- cryptographic hash or immutable run identifier.

Perfect scores across every category, combined with deterministic adapter shortcuts and only seven calls, are more plausibly evidence of an overly permissive benchmark than strong evidence of broad model capability.

**Conclusion on authenticity:** The results appear syntactically plausible and internally consistent, but are **not independently verifiable** and do not establish the claimed model quality.

### 7. Hard-coded Ollama endpoint

`CloudProvider.OLLAMA` contains:

```text
http://2.28.52.223:11434/v1
```

This is a hard-coded, unencrypted IP endpoint. The documentation calls it a “local Ollama server,” but the address is not localhost or a private-network address. This creates security, portability, and reproducibility concerns.

**Required:**

- default to `http://localhost:11434/v1`;
- allow environment/configuration override;
- do not commit an operational remote endpoint;
- use TLS and authentication for remote access;
- document whether prompts or benchmark data leave the local host.

## Documentation issues

1. `PHASE003_SPEC.md` remains stale:
   - Adapter: “IN PROGRESS”
   - Benchmark: “PENDING”
   - It says an API key is still needed.

2. The specification promises:

   ```text
   docs/evaluation/raw_results_7b.json
   ```

   but the actual artifact is:

   ```text
   raw_results_qwen2-5:7b.json
   ```

3. The colon in the result filename is not portable to Windows filesystems.

4. ADR-005 says the benchmark suite “has 12 tests,” which should be clarified as twelve category-level cases/results rather than a sufficiently broad capability evaluation.

5. The report lists `cost_per_inference = 0.001556` despite Ollama token prices being `null`. The calculation and whether this is estimated cloud-equivalent cost or local operating cost must be documented.

6. The optional cost target is missed, though correctly non-blocking.

7. ADR-005 omits the known limitation that there was no adversarial prompt testing.

8. The ADR's claim that int4 deployment is suitable is not established by this run unless the benchmark actually used and identified that quantization.

## Required remediation before approval

1. Replace metric aliases with independent test sets for deny-by-default and temporal reasoning.
2. Ensure mandatory model criteria actually call the model rather than adapter-local keyword or state logic.
3. Expand every mandatory criterion to a meaningful number and variety of cases.
4. Add adversarial, ambiguous, malformed, denial, permission-boundary, and out-of-distribution safety cases.
5. Preserve case-level prompts, model outputs, expected outcomes, scores, and latency records.
6. Add statistical confidence and minimum-sample requirements.
7. Repeat latency testing with adequate trials and documented hardware/model configuration.
8. Record Ollama model digest, quantization, runner command, repository commit, and run configuration.
9. Make the Ollama URL configurable and remove the committed public HTTP endpoint.
10. Correct the stale specification, result filename, cost accounting, and ADR claims.
11. Change the current report conclusion to a preliminary or smoke-test result until the expanded benchmark passes.
12. Add tests proving each criterion is sourced from the intended independent metric and that no required criterion silently falls back to a duplicated result.

## Recommendations

- Keep ADR-005 in **PROPOSED** status.
- Treat the current run as successful pipeline validation, not final model selection.
- Add a reference-baseline run using exactly the same prompts and scoring.
- Include repeated runs or fixed-seed deterministic decoding to assess variance.
- Separate:
  - model capability;
  - adapter behavior;
  - ORION system safety.
- Explicitly prohibit the selected LLM from bypassing deterministic safety and permission controls.

The implementation is a useful Phase 003 foundation, but the central acceptance claim—“Qwen 2.5 7B passed all 12 mandatory Physical AI criteria”—is not yet supported by a valid, independent benchmark.

## Usage

- Total tokens: 10106
- Prompt tokens: 7254
- Completion tokens: 2852
