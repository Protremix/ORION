# ORION Hardware Planning — Detailed VRAM & Cost/Performance Analysis

## Принцип (Founder directive)
Не выбирать GPU по общему объёму VRAM. Сначала:
1. Определить конкретные модели и workload ORION
2. Требования VRAM каждого workload
3. Возможность model parallelism/offloading
4. Рассчитать стоимость/производительность

---

## 1. Конкретные модели и workload ORION

### Workload definitions

| Workload | Model | Priority | Concurrency | Latency req | Always loaded? |
|----------|-------|----------|-------------|-------------|----------------|
| W1: Safety reasoning | Qwen 2.5 7B/32B/72B | Tier 1 | Always | < 2s | YES |
| W2: Complex reasoning | Qwen 2.5 72B (or GPT-4o API) | Tier 1 | On demand | < 5s | If local |
| W3: Vision processing | Qwen2-VL 7B/72B | Tier 2 | On demand | < 5s | NO (swap) |
| W4: Embeddings | BGE-large-en | Tier 2 | Batch | < 1s | YES (small) |
| W5: Speech-to-Text | Whisper Large v3 | Tier 2 | On demand | < 3s | NO (swap) |
| W6: World Model (neural) | DreamerV3 (future) | Tier 3 | On demand | < 100ms | Future |
| W7: TTS | Bark (future) | Tier 3 | On demand | < 5s | Future |

### Critical question: What model size for safety reasoning?

**UNKNOWN — NEEDS TEST.** ORION needs benchmarks comparing Qwen 2.5:
- 7B (fits on any modern GPU)
- 14B (fits on 16GB+ GPU)
- 32B (fits on 24GB+ GPU at INT4, 48GB+ at FP16)
- 72B (needs 40GB+ at INT4, 144GB+ at FP16)

**HYPOTHESIS:** For safety-critical decisions, 7B may be insufficient. 32B is likely the sweet spot. 72B is premium.
**EVIDENCE:** Qwen 2.5 MATH benchmark: 7B=75.5, 72B=83.1 (7.6 point gap). For ORION safety reasoning, this difference may matter.
**CLASSIFICATION:** NEEDS TEST — benchmark ORION-specific tasks (safety decisions, planning decomposition, hazard identification) across model sizes.

---

## 2. VRAM требования каждого workload

### Model VRAM at different precisions

Source: apxml.com, spheron.network, vLLM benchmarks (VERIFIED FACT from web research)

| Model | Params | FP16 VRAM | INT8 VRAM | INT4 (AWQ) VRAM | KV cache (4K ctx) | KV cache (32K ctx) |
|-------|--------|-----------|-----------|-----------------|--------------------|--------------------|
| Qwen 2.5 7B | 7B | 15.2 GB | 8.1 GB | 5.2 GB | 0.8 GB | 4.2 GB |
| Qwen 2.5 14B | 14B | 29.4 GB | 15.2 GB | 9.5 GB | 1.2 GB | 6.5 GB |
| Qwen 2.5 32B | 32B | 67.0 GB | 34.5 GB | 21.0 GB | 1.8 GB | 9.8 GB |
| Qwen 2.5 72B | 72B | 153.0 GB | 78.5 GB | 42.0 GB | 3.5 GB | 18.0 GB |
| Qwen2-VL 7B | 7B+vision | 17.0 GB | 9.0 GB | 5.8 GB | 0.8 GB | 4.2 GB |
| Qwen2-VL 72B | 72B+vision | 165.0 GB | 85.0 GB | 46.0 GB | 3.5 GB | 18.0 GB |
| BGE-large-en | 335M | 1.3 GB | 0.7 GB | 0.4 GB | N/A | N/A |
| Whisper Large v3 | 1.5B | 3.1 GB | 1.6 GB | 1.0 GB | N/A | N/A |
| Bark TTS | 1B | 2.0 GB | 1.1 GB | 0.7 GB | N/A | N/A |
| DreamerV3 | ~50M-1B | 2-4 GB | 1-2 GB | 0.5-1 GB | N/A | N/A |

### ORION VRAM budget per scenario

#### Scenario A: 7B models (HIL minimum)
```
Always loaded:
  W1 (safety reasoning):  Qwen 2.5 7B INT4   =  5.2 GB  + 0.8 GB KV =  6.0 GB
  W4 (embeddings):         BGE-large-en INT8  =  0.7 GB                =  0.7 GB
                                                          Subtotal =  6.7 GB

On demand (swap in/out):
  W3 (vision):             Qwen2-VL 7B INT4  =  5.8 GB  + 0.8 GB KV =  6.6 GB
  W5 (STT):                Whisper v3 INT4   =  1.0 GB                =  1.0 GB

Peak (all loaded):  6.7 + 6.6 + 1.0 = 14.3 GB
Typical (W1+W4 only): 6.7 GB
```
→ **Fits on: 16GB+ GPU (RTX 5080, RTX 4090, Jetson AGX Orin)**

#### Scenario B: 32B models (HIL recommended — HYPOTHESIS)
```
Always loaded:
  W1 (safety reasoning):  Qwen 2.5 32B INT4  = 21.0 GB  + 1.8 GB KV = 22.8 GB
  W4 (embeddings):         BGE-large-en INT8  =  0.7 GB                =  0.7 GB
                                                          Subtotal = 23.5 GB

On demand:
  W3 (vision):             Qwen2-VL 7B INT4  =  6.6 GB (swap)
  W5 (STT):                Whisper v3 INT4   =  1.0 GB (swap)

Peak (all loaded):  23.5 + 6.6 + 1.0 = 31.1 GB
Typical: 23.5 GB
```
→ **Fits on: 32GB GPU (RTX 5090) at INT4 with 4K context**
→ **Does NOT fit on: 24GB GPU (RTX 4090, RTX 4500 Ada) at INT4**

#### Scenario C: 72B models (full autonomous — HYPOTHESIS)
```
Always loaded:
  W1 (safety reasoning):  Qwen 2.5 72B INT4  = 42.0 GB  + 3.5 GB KV = 45.5 GB
  W4 (embeddings):         BGE-large-en INT8  =  0.7 GB                =  0.7 GB
                                                          Subtotal = 46.2 GB

On demand (SECOND GPU):
  W3 (vision):             Qwen2-VL 72B INT4 = 46.0 GB + 3.5 GB KV = 49.5 GB
  W5 (STT):                Whisper v3 INT4   =  1.0 GB (swap on GPU1 spare)

Peak GPU1: 46.2 + 1.0 = 47.2 GB
Peak GPU2: 49.5 GB
```
→ **Needs: 2× 48GB+ GPUs (2× RTX 6000 Ada, or 1× 48GB + cloud API for vision)**
→ **Alternative: 1× RTX 6000 Ada 48GB for 72B INT4 LLM, cloud API for vision**

#### Scenario D: 72B FP16 (maximum quality — datacenter)
```
W1: Qwen 2.5 72B FP16 = 153.0 GB + 3.5 GB KV = 156.5 GB
```
→ **Needs: 2× H100 80GB (160 GB raw, 147 GB effective with NVLink 0.92x)**
→ **Cost: $60,000+ for GPUs alone. NOT RECOMMENDED for ORION initial setup.**

---

## 3. Model parallelism / offloading analysis

### Tensor Parallelism scaling factors

Source: willitrunai.com, vLLM benchmarks (VERIFIED FACT)

| Interconnect | Scaling Factor | Overhead | Bandwidth |
|---------------|---------------|----------|-----------|
| NVLink 5.0 (B200) | 0.93x | 7% | 1800 GB/s |
| NVLink 4.0 (H100) | 0.92x | 8% | 900 GB/s |
| NVLink 3.0 (A100) | 0.90x | 10% | 600 GB/s |
| AMD Infinity Fabric | 0.88x | 12% | 896 GB/s |
| PCIe Gen5 (no NVLink) | 0.75x | 25% | 64 GB/s |

### Effective VRAM for multi-GPU configs

| Config | Raw VRAM | Interconnect | Scaling | Effective VRAM | Can run 72B INT4 (42GB)? |
|--------|----------|--------------|---------|----------------|---------------------------|
| 1× RTX 6000 Ada 48GB | 48 GB | N/A (single) | 1.0x | 48 GB | ✅ YES (46.2 GB needed) |
| 2× RTX 5090 32GB | 64 GB | PCIe Gen5 | 0.75x | 48 GB | ⚠️ BARELY (tight) |
| 2× RTX 4090 24GB | 48 GB | PCIe Gen4 | 0.70x | 34 GB | ❌ NO |
| 2× RTX 6000 Ada 48GB | 96 GB | PCIe Gen5 | 0.75x | 72 GB | ✅ YES (+ room for vision) |
| 2× H100 80GB | 160 GB | NVLink 4.0 | 0.92x | 147 GB | ✅ YES (FP16!) |
| 1× B200 192GB | 180 GB | N/A | 1.0x | 180 GB | ✅ YES (FP16!) |
| Mac Studio M3 Ultra 192GB | 192 GB | Unified mem | ~0.85x | ~163 GB | ✅ YES (FP16!) |

### Key insight: 2× RTX 5090 vs 1× RTX 6000 Ada

**For 72B INT4:**
- 1× RTX 6000 Ada 48GB: 48 GB effective, 46.2 GB needed → **2 GB spare** (tight!)
- 2× RTX 5090 32GB: 48 GB effective (0.75×64), 42 GB model needs → **6 GB spare**

BUT: 2× RTX 5090 has 25% throughput penalty on tensor parallel workloads.
Single RTX 6000 Ada has NO parallelism overhead.

**For throughput-critical workloads (LLM inference):**
- 1× RTX 6000 Ada: full GPU speed, no communication overhead
- 2× RTX 5090: each GPU at 75% effective speed due to PCIe sync

**For VRAM-limited workloads (large models):**
- 2× RTX 5090: more raw VRAM (64 GB), can fit larger models
- 1× RTX 6000 Ada: limited to 48 GB

### CPU offloading analysis

For models that don't fit in GPU VRAM:
- **llama.cpp / Ollama:** Can offload some layers to CPU RAM
- **Performance:** 10-20 tokens/sec (vs 100+ tokens/sec on full GPU)
- **Acceptable for:** Embeddings (batch), non-real-time tasks, fallback
- **NOT acceptable for:** Safety reasoning (needs < 2s response)

---

## 4. Стоимость/производительность

### GPU options with specs and prices

| GPU | VRAM | Bandwidth | FP16 TFLOPS | TDP | Price (est.) | NVLink? |
|-----|------|----------|-------------|-----|-------------|---------|
| RTX 5090 | 32 GB | 1792 GB/s | 209 | 575W | $1,999 | NO |
| RTX 5080 | 16 GB | 960 GB/s | 118 | 400W | $999 | NO |
| RTX 6000 Ada | 48 GB | 960 GB/s | 91 | 300W | $6,800 | NO |
| RTX 4500 Ada | 24 GB | 648 GB/s | 47 | 320W | $2,200 | NO |
| RTX 4090 | 24 GB | 1008 GB/s | 83 | 450W | $1,600 | NO |
| L40S | 48 GB | 864 GB/s | 91 | 350W | $8,000 | NO |
| H100 80GB | 80 GB | 3350 GB/s | 990 | 700W | $30,000 | YES |
| B200 | 180 GB | 8000 GB/s | 2250 | 1000W | $35,000+ | YES |
| Mac Studio M3 Ultra | 192 GB | 800 GB/s | ~28 | 270W | $6,000 | Unified |
| Jetson AGX Orin | 32 GB | 205 GB/s | 5.4 | 60W | $2,000 | N/A |

### Cost/Performance for ORION scenarios

#### Scenario A: 7B models (HIL minimum)

| Config | Total VRAM | Can run? | Price | Tokens/sec (est.) | $/Mtok |
|--------|-----------|----------|-------|--------------------|--------|
| 1× RTX 5080 16GB | 16 GB | ✅ YES | $999 | ~80 | Best |
| 1× RTX 5090 32GB | 32 GB | ✅ YES (+headroom) | $1,999 | ~150 | Good |
| 1× Jetson AGX Orin 32GB | 32 GB | ✅ YES (edge) | $2,000 | ~30 | OK |
| 1× RTX 4090 24GB | 24 GB | ✅ YES | $1,600 | ~100 | Good |
| 1× RTX 4500 Ada 24GB | 24 GB | ✅ YES | $2,200 | ~60 | OK |

**Best for Scenario A: 1× RTX 5080 16GB ($999) or 1× RTX 4090 24GB ($1,600)**
- 7B INT4 fits comfortably with room for vision + embeddings
- Lowest cost for HIL minimum

#### Scenario B: 32B models (HIL recommended)

| Config | Total VRAM | Can run 32B INT4 (22.8GB)? | Can run + vision (29.4GB)? | Price |
|--------|-----------|---------------------------|---------------------------|-------|
| 1× RTX 5090 32GB | 32 GB | ✅ YES | ⚠️ Tight (swap vision) | $1,999 |
| 1× RTX 6000 Ada 48GB | 48 GB | ✅ YES + headroom | ✅ YES (all loaded) | $6,800 |
| 1× RTX 4500 Ada 24GB | 24 GB | ❌ NO (23.5GB needed) | ❌ NO | $2,200 |
| 2× RTX 5090 32GB | 64 GB | ✅ YES (split) | ✅ YES | $3,998 |
| Mac Studio M3 Ultra | 192 GB | ✅ YES | ✅ YES | $6,000 |

**Best for Scenario B: 1× RTX 5090 32GB ($1,999)** — 32B fits, vision can swap
**Alternative: Mac Studio M3 Ultra 192GB ($6,000)** — everything fits with huge headroom

#### Scenario C: 72B models (full autonomous)

| Config | Raw VRAM | Effective VRAM | Can run 72B INT4 (45.5GB)? | + Vision 72B (49.5GB)? | Price |
|--------|----------|---------------|---------------------------|----------------------|-------|
| 1× RTX 6000 Ada 48GB | 48 GB | 48 GB | ⚠️ Barely (2.5GB spare) | ❌ NO | $6,800 |
| 2× RTX 5090 32GB | 64 GB | 48 GB (0.75x) | ⚠️ Barely | ❌ NO (need 2nd GPU for vision) | $3,998 |
| 2× RTX 6000 Ada 48GB | 96 GB | 72 GB (0.75x) | ✅ YES | ✅ YES (96 GB raw, split) | $13,600 |
| 2× L40S 48GB | 96 GB | 72 GB (0.75x) | ✅ YES | ✅ YES | $16,000 |
| 2× H100 80GB | 160 GB | 147 GB (0.92x) | ✅ YES (FP16!) | ✅ YES (FP16!) | $60,000 |
| 1× B200 180GB | 180 GB | 180 GB | ✅ YES (FP16!) | ✅ YES (FP16!) | $35,000+ |
| Mac Studio M3 Ultra | 192 GB | ~163 GB | ✅ YES (FP16!) | ✅ YES (FP16!) | $6,000 |

**Best for Scenario C:**
- **Budget: 2× RTX 5090 32GB ($3,998)** — 72B INT4 barely fits, use cloud API for vision
- **Balanced: 2× RTX 6000 Ada 48GB ($13,600)** — 72B INT4 + vision 72B INT4 on separate GPUs
- **Wildcard: Mac Studio M3 Ultra 192GB ($6,000)** — everything fits at FP16, but slower (28 TFLOPS vs 91+)

#### Scenario D: 72B FP16 (maximum quality)

| Config | Price | Can run? | Notes |
|--------|-------|----------|-------|
| 2× H100 80GB | $60,000 | ✅ (147 GB eff.) | Datacenter, NVLink |
| 1× B200 180GB | $35,000+ | ✅ (180 GB) | Datacenter, single GPU |
| Mac Studio M3 Ultra | $6,000 | ✅ (163 GB eff.) | Slower but cheapest |
| 3× RTX 6000 Ada 48GB | $20,400 | ✅ (108 GB eff.) | Workstation, PCIe overhead |

**Best for Scenario D: Mac Studio M3 Ultra ($6,000)** — cheapest FP16 72B, but 3-4× slower than H100

---

## 5. Рекомендации

### Phase 1: HIL Minimum (NEEDS TEST first)
**RECOMMENDATION: Benchmark model sizes BEFORE buying hardware.**

Before any GPU purchase:
1. Download Qwen 2.5 7B, 14B, 32B
2. Run ORION-specific benchmarks (safety decisions, planning, decomposition)
3. Determine minimum model size that passes safety criteria
4. THEN select GPU based on results

**If 7B is sufficient:** 1× RTX 5080 16GB ($999) or 1× RTX 4090 24GB ($1,600)
**If 32B is needed:** 1× RTX 5090 32GB ($1,999)
**If 72B is needed:** 2× RTX 5090 32GB ($3,998) or 1× RTX 6000 Ada ($6,800)

### Phase 2: Full Autonomous (after Phase 1 validated)
**If 72B INT4 confirmed:**
- Option A: 2× RTX 5090 32GB ($3,998) — LLM on both GPUs via TP, vision via cloud API
- Option B: 1× RTX 6000 Ada 48GB ($6,800) — LLM on single GPU (no TP overhead), vision via cloud API
- Option C: 2× RTX 6000 Ada 48GB ($13,600) — LLM on GPU1, vision on GPU2

**If 72B FP16 needed:**
- Mac Studio M3 Ultra 192GB ($6,000) — cheapest option, slower throughput
- 2× H100 80GB ($60,000) — datacenter, maximum performance

### Edge deployment (future)
- Jetson AGX Orin 32GB ($2,000) — 7B models, low power (60W)
- RTX 5080 16GB ($999) — 7B models, desktop edge

### Key insight: Mac Studio M3 Ultra as wildcard

**Mac Studio M3 Ultra 192GB ($6,000):**
- ✅ Fits 72B FP16 (153 GB) with 39 GB spare for KV cache + other models
- ✅ Fits 72B FP16 + 7B vision + embeddings + STT all simultaneously
- ✅ Lower power (270W vs 600-1150W for dual GPU workstation)
- ✅ Cheaper than 2× RTX 6000 Ada ($6,000 vs $13,600)
- ❌ Slower inference: ~28 TFLOPS vs 91+ TFLOPS on NVIDIA GPUs
- ❌ No CUDA: uses Metal/MLX framework (less ecosystem support)
- ❌ vLLM doesn't support Apple Silicon natively (uses llama.cpp/MLX)
- ❌ Not upgradable, no NVLink, no tensor parallelism
- ❌ No Jetson/edge deployment path (can't deploy macOS to robot)

**Classification:** HYPOTHESIS — Mac Studio could work for development but not for edge deployment. Good for research/prototyping, bad for production physical AI.

---

## 6. Итоговая таблица: cost/performance ranking

| Rank | Config | Price | Max model (INT4) | Max model (FP16) | TP overhead | Power | Best for |
|------|--------|-------|-------------------|-------------------|-------------|-------|----------|
| 1 | 1× RTX 5090 32GB | $1,999 | 32B (22.8GB) | 14B (29.4GB ❌) | None | 575W | HIL with 32B |
| 2 | 2× RTX 5090 32GB | $3,998 | 72B (42GB ⚠️) | 32B (67GB ❌) | 25% | 1150W | Budget 72B INT4 |
| 3 | Mac Studio M3 Ultra | $6,000 | 72B (42GB ✅) | 72B (153GB ✅) | ~15% | 270W | Dev/prototyping |
| 4 | 1× RTX 6000 Ada 48GB | $6,800 | 72B (42GB ✅) | 32B (67GB ❌) | None | 300W | Single-GPU 72B |
| 5 | 2× RTX 6000 Ada 48GB | $13,600 | 72B+vision (96GB) | 72B (147GB ⚠️) | 25% | 600W | Full autonomous |
| 6 | 2× H100 80GB | $60,000 | Anything | 72B FP16 ✅ | 8% | 1400W | Datacenter |

---

## Classification

- VRAM numbers: VERIFIED FACT (from apxml.com, spheron.net, vLLM docs)
- TP scaling factors: VERIFIED FACT (from willitrunai.com benchmarks)
- GPU prices: APPROXIMATION (street prices, may vary)
- Model size recommendation: NEEDS TEST (no ORION-specific benchmarks yet)
- Cost/performance ranking: HYPOTHESIS (depends on which model size ORION needs)

## Founder decisions required

1. **NEEDS TEST first:** Authorize benchmark testing of 7B/14B/32B models on ORION tasks
2. **FINANCIAL:** GPU purchase after benchmark results
3. **STRATEGIC:** Mac Studio vs NVIDIA workstation (ecosystem vs VRAM/$)
4. **STRATEGIC:** Cloud API (current) vs local GPU (trade-off: cost vs latency vs privacy)
