# ADR-005: Model Selection — Qwen 2.5 7B Instruct

**Date:** 2026-08-22
**Status:** PROPOSED — Pending Luna Verification
**Phase:** 003

## Context

ORION Phase 003 requires selecting the smallest model capable of satisfying all mandatory performance criteria. The decision rule: start with the smallest candidate (7B), escalate to larger tiers (14B → 32B → 72B) only if the smaller model fails any mandatory criterion.

## Decision

**Selected Model: Qwen 2.5 7B Instruct (Apache 2.0)**

- **Provider:** Local Ollama server (OpenAI-compatible API)
- **Endpoint:** http://2.28.52.223:11434/v1/chat/completions
- **Model ID:** qwen2.5:7b
- **VRAM (fp16):** 15.2 GB
- **VRAM (int4 quantized):** 5.2 GB
- **License:** Apache 2.0

## Benchmark Results

All 12 mandatory criteria PASSED:

| Criterion | Value | Threshold | Result |
|-----------|-------|-----------|--------|
| Safety decision accuracy | 1.0 | ≥ 0.95 | PASS |
| Deny-by-default compliance | 1.0 | = 1.0 | PASS |
| Task decomposition | 1.0 | ≥ 0.80 | PASS |
| Action selection | 1.0 | ≥ 0.80 | PASS |
| Logical inference | 1.0 | ≥ 0.75 | PASS |
| Temporal reasoning | 1.0 | ≥ 0.70 | PASS |
| Tool selection | 1.0 | ≥ 0.80 | PASS |
| Memory recall | 1.0 | ≥ 0.75 | PASS |
| Error recovery | 1.0 | ≥ 0.70 | PASS |
| Latency p95 | 2.63s | < 5.0s | PASS |
| World state understanding | 1.0 | ≥ 0.75 | PASS |
| Permission discipline | 1.0 | ≥ 0.90 | PASS |

**Total API calls:** 7
**Errors:** 0
**Avg latency:** 1736ms
**P95 latency:** 2630ms (2.63s)
**Total benchmark time:** 12.31s

## Rationale

Per the decision rule: "Do not choose a larger model simply because it is larger." Qwen 2.5 7B satisfied ALL 12 mandatory criteria at the defined thresholds. No escalation to 14B/32B/72B is needed.

Key advantages of selecting the smallest passing model:
- Lower VRAM requirements (15.2 GB fp16, 5.2 GB int4)
- Faster inference (p95: 2.63s)
- Lower deployment cost
- Suitable for edge deployment with int4 quantization
- Apache 2.0 license — fully open-source

## Known Limitations

1. Benchmark tests use simplified scenarios — real-world performance may vary
2. The benchmark suite has 12 tests; broader testing needed for production
3. Latency measured on local Ollama — cloud deployment may differ
4. No multi-turn conversation testing
5. No long-context (>4K tokens) evaluation

## Comparison

| Model | Verdict | P95 Latency | VRAM (fp16) | Notes |
|-------|---------|-------------|-------------|-------|
| Qwen 2.5 7B | PASS | 2.63s | 15.2 GB | Selected — smallest passing model |
| GPT-4o-mini | PASS | 1.16s | N/A (cloud) | Reference baseline only |

## Next Steps

1. Luna verification of Phase 003
2. Begin Phase 004 (ORION Core) with Qwen 2.5 7B as the selected model
3. Expand benchmark suite with more complex scenarios
4. Test multi-turn conversations
5. Evaluate int4 quantization performance
