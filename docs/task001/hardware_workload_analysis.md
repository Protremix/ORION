# ORION Hardware Planning — Workload Definition

## Принцип
Сначала workload → потом VRAM → потом GPU. Не выбираем GPU по общему объёму VRAM.

## ORION Workloads

### Concurrent execution requirements

ORION 24/7 runtime может одновременно выполнять:

```
[Workload 1] Reasoning (LLM) — основная нагрузка
    → Goal decomposition, planning, safety decisions, discovery
    → Must run continuously, low latency (< 2s response)

[Workload 2] Vision (VLM) — по требованию
    → Camera/sensor input processing
    →间歇ный, средний latency (< 5s)

[Workload 3] Embeddings — по требованию
    → Knowledge graph indexing, memory storage
    → Batch processing, может ждать

[Workload 4] Speech-to-Text — по требованию
    → Voice input processing
    →间歇ный, низкий latency

[Workload 5] World Model (physics) — CPU only
    → No GPU needed, runs on CPU
    → Real-time, < 100ms per prediction step

[Workload 6] World Model (neural, future) — GPU
    → DreamerV3-style learned model
    → Not in initial stack, planned for later
```

### Workload priority and concurrency

```
TIER 1 (always running):
  - Reasoning LLM (continuous, main loop)
  
TIER 2 (on demand, can queue):
  - Vision VLM
  - Embeddings
  - STT
  
TIER 3 (future, not in initial setup):
  - Neural world model
  - TTS
  - Video understanding
```

### Key question: Can workloads share one GPU?

**Option A: Single GPU for everything (sequential)**
- One large GPU (48GB+), run one model at a time, swap as needed
- Pros: Simple, no multi-GPU complexity
- Cons: Latency when swapping, can't run LLM + vision simultaneously
- Feasibility: Depends on model sizes and swap time

**Option B: Single GPU with model offloading**
- Keep LLM always loaded, offload others to CPU/RAM when not in use
- Pros: LLM always ready, other models load on demand
- Cons: Load time for offloaded models (seconds), needs enough VRAM for LLM + KV cache
- Feasibility: Good if LLM fits comfortably in VRAM

**Option C: Two GPUs (specialized)**
- GPU 1: LLM (always loaded)
- GPU 2: Vision + Embeddings + STT (shared, swap as needed)
- Pros: LLM never interrupted, vision can run in parallel
- Cons: More expensive, more power, more complexity
- Feasibility: Best for production 24/7

**Option D: Cloud API for burst + local for core**
- Local: Small LLM (7B) for always-on reasoning
- Cloud: GPT-4o for complex reasoning, vision, embeddings
- Pros: Minimal local hardware, unlimited model access
- Cons: API costs, latency, internet dependency, privacy
- Feasibility: Current approach (VERIFIED FACT)

## ORION-specific constraints

1. **24/7 operation** — can't have downtime for model loading
2. **Safety-critical** — LLM must respond in < 2s for safety decisions
3. **Latency-sensitive** — world model + planning loop must be real-time
4. **Budget-conscious** — Founder deferred hardware, cost matters
5. **Apache 2.0 license** — can't use GPL or non-commercial models
6. **Scalable** — should handle future workloads (neural world model, video)

## What models does ORION ACTUALLY need?

### Minimum viable setup (simulation-only, current):
```
Reasoning:    GPT-4o API (no local GPU needed)
Vision:        GPT-4o Vision API
Embeddings:    OpenAI API
World Model:   Physics-based (CPU only)
→ GPU needed: NONE (all cloud)
```

### HIL setup (sensors + local processing):
```
Reasoning:     Qwen 2.5 7B local (always on, safety decisions)
               GPT-4o API (complex reasoning, fallback)
Vision:        Qwen2-VL 7B local (sensor processing)
               GPT-4o API (complex vision)
Embeddings:    BGE-large-en local (fast indexing)
STT:           Whisper Large v3 local (voice input)
World Model:   Physics-based (CPU)
→ GPU needed: Enough for 7B LLM + 7B VLM + 335M embeddings + 1.5B STT
```

### Full autonomous setup (future):
```
Reasoning:     Qwen 2.5 72B local (high quality)
               GPT-4o API (burst, fallback)
Vision:        Qwen2-VL 72B local (high quality)
Embeddings:    BGE-large-en local
STT:           Whisper Large v3 local
TTS:           Bark local
World Model:   Physics + DreamerV3 (GPU)
→ GPU needed: Enough for 72B LLM + 72B VLM + embeddings + STT + TTS + world model
```

## VRAM estimation per model (preliminary — sub-agents researching exact numbers)

| Model | Params | FP16 VRAM | INT4 VRAM | KV cache (4K ctx) | Always loaded? |
|-------|--------|-----------|-----------|-------------------|----------------|
| Qwen 2.5 7B | 7B | ~14 GB | ~5 GB | ~1 GB | Yes (safety) |
| Qwen 2.5 72B | 72B | ~144 GB | ~40 GB | ~8 GB | Yes (if local) |
| Qwen2-VL 7B | 7B | ~14 GB | ~5 GB | ~1 GB | On demand |
| Qwen2-VL 72B | 72B | ~144 GB | ~40 GB | ~8 GB | On demand |
| BGE-large-en | 335M | ~1 GB | ~0.5 GB | N/A | Yes (indexing) |
| Whisper Large v3 | 1.5B | ~3 GB | ~1 GB | N/A | On demand |
| Bark TTS | 1B | ~2 GB | ~1 GB | N/A | On demand |
| DreamerV3 | varies | ~4-8 GB | ~2-4 GB | N/A | Future |

### Scenario 1: HIL setup (7B models)
```
Always loaded:  Qwen 2.5 7B FP16 (14GB) + KV cache (1GB) = 15 GB
On demand:      Qwen2-VL 7B FP16 (14GB) = swap in when needed
On demand:      BGE-large (1GB) = can stay loaded
On demand:      Whisper v3 (3GB) = swap in when needed
Peak VRAM:      15 + 14 + 1 + 3 = 33 GB (all loaded simultaneously)
Typical VRAM:   15 + 1 = 16 GB (LLM + embeddings only)
```

### Scenario 2: Full autonomous (72B models)
```
Always loaded:  Qwen 2.5 72B INT4 (40GB) + KV cache (8GB) = 48 GB
On demand:      Qwen2-VL 72B INT4 (40GB) = needs second GPU
On demand:      BGE-large (1GB) = fits in spare VRAM
On demand:      Whisper v3 (3GB) = fits in spare VRAM
Peak VRAM:      48 + 40 + 1 + 3 = 92 GB (needs 2 GPUs or offloading)
Typical VRAM:   48 + 1 = 49 GB (LLM + embeddings only)
```

### Scenario 3: 72B with FP16 (no quantization)
```
Qwen 2.5 72B FP16 = 144 GB → needs 3-4 GPUs or 1 H100/B200
Not practical for workstation. INT4 or FP8 quantization required.
```

## Model parallelism / offloading options

### Tensor Parallelism (TP)
- Splits model layers across GPUs
- Supported by: vLLM, TGI, SGLang
- Requires: NVLink or high-speed interconnect for efficiency
- Consumer GPUs (RTX 5090): no NVLink, PCIe only → ~30-50% overhead
- Datacenter GPUs (H100): NVLink → minimal overhead

### Pipeline Parallelism (PP)
- Splits model pipeline stages across GPUs
- Less efficient than TP, simpler to implement
- Higher latency, lower throughput

### CPU offloading
- Keep model weights on CPU RAM, transfer to GPU layer-by-layer
- Supported by: llama.cpp, Ollama
- Pros: Can run 72B on 16GB GPU (if enough RAM)
- Cons: Very slow (10-20 tokens/sec vs 100+ on full GPU)
- Acceptable for: batch processing, embeddings, non-real-time

### Quantization
- INT4 (AWQ, GPTQ): ~4 bits/param, 72B → ~36GB
- INT8: ~8 bits/param, 72B → ~72GB
- FP8: ~8 bits/param (H100/B200 only), 72B → ~72GB
- Quality loss: INT4 ~1-3% accuracy drop (acceptable for most tasks)

## Key insight

The critical decision is: **What model size does ORION need for safety-critical reasoning?**

- If 7B is sufficient → single 24GB GPU works (RTX 4090/5090)
- If 32B is needed → single 48GB GPU (RTX 6000 Ada, L40S)  
- If 72B is needed → multi-GPU or quantization required
- If 72B FP16 is needed → datacenter GPU (H100, B200)

**This depends on benchmark testing that hasn't been done yet.**
NEEDS TEST: Compare Qwen 2.5 7B vs 72B on ORION-specific tasks (safety decisions, planning, decomposition).

## Classification

- Workload definition: VERIFIED FACT (based on ORION architecture)
- VRAM estimates: HYPOTHESIS (preliminary, pending sub-agent research)
- GPU selection: UNKNOWN (pending workload + VRAM analysis)
- Model size for safety: NEEDS TEST (no benchmarks yet)
