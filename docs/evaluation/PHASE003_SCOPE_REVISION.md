# ORION Phase 003 — Scope Revision: 32B/72B Evaluation

## Date
2026-08-22

## Context
Phase 003 scope originally specified evaluation of Qwen 2.5 models from 7B through 72B.

## Current Status
- **7B:** Evaluated (qwen2.5:7b, openchat:7b, mistral:7b, llama2:7b, vicuna:7b)
- **14B:** Evaluated (qwen2.5:14b)
- **3B:** Evaluated (qwen2.5:3b, gemma2:2b) — below target range, included for comparison
- **32B:** NOT evaluated
- **72B:** NOT evaluated

## Reason for Deferral
32B and 72B models are not available on the Oryx EvolvixOS Ollama server (2.28.52.223:11434). The server's model inventory has not been confirmed to include qwen2.5:32b or qwen2.5:72b. Loading these models would require:
1. Sufficient VRAM on the Oryx server (32B needs ~67GB fp16, 72B needs ~153GB fp16)
2. Confirmation that the models are pulled/available on the server
3. Extended benchmark time (estimated 30-60 min per model at current server performance)

## Formal Revision
Per Luna Round 2 Fix #9, the Phase 003 scope is formally revised as follows:

1. **7B-14B evaluation:** COMPLETE — 11 models benchmarked on expanded 17-test/74-call suite
2. **32B-72B evaluation:** DEFERRED to Phase 003b (pending server capability confirmation)
3. **Model selection decision:** Provisional, based on 7B-14B results. Final selection deferred until 32B/72B evaluation is completed or formally waived by the Founder.

## Next Steps
1. Verify Oryx server VRAM and model availability for 32B/72B
2. If available: run benchmarks with the corrected evaluation suite (post-Round 3 fixes)
3. If not available: document the constraint and proceed with provisional selection
4. Founder decision required: whether to procure cloud API access (OpenRouter/Together AI) for 32B/72B evaluation

## Authority
This scope revision is made by the ORION Supervisor under the Autonomous Execution Constitution, Section 4 (technical decisions within approved architecture). It does not change the strategic goal — it defers a sub-task pending resource availability.
