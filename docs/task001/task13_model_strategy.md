# ORION TASK 001 — TASK 13: Model Strategy

## Principle

Do NOT assume ORION needs a 30B or 100B model immediately. Research open-weight options. Define adapters. Recommend the smallest practical initial stack.

## Current Stack (VERIFIED FACT)

ORION currently uses:
- **Reasoning:** GPT-4o (via OpenAI API) — live-tested, 16 API calls
- **Vision:** GPT-4o Vision (via OpenAI API) — live-tested
- **Embeddings:** text-embedding-3-small (via OpenAI API) — live-tested
- **World Model:** Custom physics-based (no neural model) — 37 tests
- **Planner:** GPT-4o for decomposition + rule-based fallback — tested

## Model Categories & Options

### 1. LLM (Reasoning)

| Model | Org | Size | Open? | License | VRAM | Good for |
|-------|-----|------|-------|---------|------|----------|
| GPT-4o | OpenAI | ~unknown | Closed | Proprietary | API | Current ORION reasoning ✅ |
| Claude 3.5 Sonnet | Anthropic | ~unknown | Closed | Proprietary | API | Alternative reasoning |
| Llama 3.1 70B | Meta | 70B | Yes | Llama 3.1 License | 40GB | Local reasoning, research |
| Llama 3.1 8B | Meta | 8B | Yes | Llama 3.1 License | 6GB | Edge/small reasoning |
| Qwen 2.5 72B | Alibaba | 72B | Yes | Apache 2.0 | 40GB | Local reasoning (Apache!) |
| Qwen 2.5 7B | Alibaba | 7B | Yes | Apache 2.0 | 6GB | Edge reasoning |
| DeepSeek V3 | DeepSeek | 671B (MoE) | Yes | MIT | 40GB (active) | High quality, efficient |
| Phi-3.5 Mini | Microsoft | 3.8B | Yes | MIT | 3GB | Ultra-small, edge |

**Recommended initial stack:**
- **Cloud:** GPT-4o (current, VERIFIED FACT)
- **Local (when hardware available):** Qwen 2.5 72B (Apache 2.0, 40GB VRAM — fits on RTX 6000 Ada 48GB)
- **Edge:** Qwen 2.5 7B or Phi-3.5 Mini (Apache 2.0 / MIT, fits on 8GB VRAM)

### 2. Vision

| Model | Org | Size | Open? | License | VRAM | Good for |
|-------|-----|------|-------|---------|------|----------|
| GPT-4o Vision | OpenAI | ~unknown | Closed | Proprietary | API | Current ORION vision ✅ |
| LLaVA 1.6 | Community | 13B | Yes | Apache 2.0 | 14GB | Local vision |
| Qwen2-VL 7B | Alibaba | 7B | Yes | Apache 2.0 | 8GB | Local vision, efficient |
| InternVL 2 | Shanghai AI Lab | 8B-108B | Yes | MIT | 8-60GB | High quality vision |

**Recommended:**
- **Cloud:** GPT-4o Vision (current)
- **Local:** Qwen2-VL 7B (Apache 2.0, 8GB VRAM — fits on any modern GPU)

### 3. Embeddings

| Model | Org | Size | Open? | License | VRAM | Good for |
|-------|-----|------|-------|---------|------|----------|
| text-embedding-3-small | OpenAI | small | Closed | Proprietary | API | Current ORION embeddings ✅ |
| BGE-large-en | BAAI | 335M | Yes | MIT | 2GB | Local embeddings |
| E5-large-v2 | Microsoft | 335M | Yes | MIT | 2GB | Local embeddings |
| Nomic-Embed | Nomic | 137M | Yes | Apache 2.0 | 1GB | Efficient local |

**Recommended:**
- **Cloud:** OpenAI text-embedding-3 (current)
- **Local:** BGE-large-en (MIT, 2GB VRAM — trivial to run)

### 4. World Model

| Model | Org | Size | Open? | License | VRAM | Good for |
|-------|-----|------|-------|---------|------|----------|
| ORION Physics WM | ORION | 0 (no NN) | Yes | Apache 2.0 | 0 | Current — 4 domains ✅ |
| DreamerV3 | Hafner et al. | varies | Yes | MIT | varies | Learned world model |
| Genie | DeepMind | unknown | Closed | Proprietary | N/A | Concept reference only |
| UniSim | DeepMind | unknown | Closed | Proprietary | N/A | Concept reference only |

**Recommended:**
- **Current:** Physics-based (VERIFIED FACT, 37 tests)
- **Future:** Add DreamerV3-style learned model as adapter when GPU available

### 5. Audio / Speech

| Model | Org | Size | Open? | License | VRAM | Good for |
|-------|-----|------|-------|---------|------|----------|
| Whisper Large v3 | OpenAI | 1.5B | Yes | MIT | 3GB | Speech-to-text |
| Whisper Turbo | OpenAI | 809M | Yes | MIT | 2GB | Faster STT |
| XTTS v2 | Coqui | 467M | Yes | CPML (non-commercial) | 2GB | Text-to-speech |
| Bark | Suno | 1B | Yes | MIT | 4GB | TTS + audio gen |

**Recommended:**
- **STT:** Whisper Large v3 (MIT, 3GB VRAM)
- **TTS:** Bark (MIT, 4GB VRAM) — avoid XTTS (CPML non-commercial license incompatible with Apache 2.0)

### 6. Video (future)

| Model | Org | Size | Open? | License | VRAM | Good for |
|-------|-----|------|-------|---------|------|----------|
| VideoLLaMA 2 | DAMO | 7B-13B | Yes | Apache 2.0 | 14-28GB | Video understanding |
| Qwen2-VL (video) | Alibaba | 7B | Yes | Apache 2.0 | 8GB | Video understanding |

**Recommended:** Qwen2-VL 7B (also handles images + video, Apache 2.0)

## Recommended Initial Stack

### Phase 1: Cloud-Only (current — VERIFIED FACT)
```
Reasoning:    GPT-4o (API)
Vision:       GPT-4o Vision (API)
Embeddings:   text-embedding-3-small (API)
World Model:  Physics-based (local, no GPU)
Audio:        (not implemented)
```
Cost: API usage (token costs accepted by Founder)

### Phase 2: Hybrid Local + Cloud (when hardware available)
```
Reasoning:    Qwen 2.5 72B (local, Apache 2.0, 40GB VRAM)
              GPT-4o (cloud, for complex/burst reasoning)
Vision:       Qwen2-VL 7B (local, Apache 2.0, 8GB VRAM)
              GPT-4o Vision (cloud, fallback)
Embeddings:   BGE-large-en (local, MIT, 2GB VRAM)
World Model:  Physics + DreamerV3 (local, MIT)
Audio:        Whisper Large v3 (local, MIT, 3GB VRAM)
              Bark TTS (local, MIT, 4GB VRAM)
```
Hardware: 1× RTX 6000 Ada 48GB OR 2× RTX 5090 32GB
Cost: One-time hardware purchase (Founder decision, deferred)

### Phase 3: Edge Deployment (future)
```
Reasoning:    Qwen 2.5 7B (local, Apache 2.0, 6GB VRAM)
Vision:       Qwen2-VL 7B (local, Apache 2.0, 8GB VRAM)
Embeddings:   Nomic-Embed (local, Apache 2.0, 1GB VRAM)
World Model:  Physics-based (no GPU)
Audio:        Whisper Turbo (local, MIT, 2GB VRAM)
```
Hardware: Jetson Orin Nano / any 8GB+ GPU

## License Compatibility

All recommended local models use Apache 2.0, MIT, or similar permissive licenses — compatible with ORION's Apache 2.0 license.

**Excluded due to license:**
- XTTS v2 (CPML — non-commercial, incompatible)
- Any GPL-licensed models (copyleft incompatible with Apache 2.0)

## Adapter Architecture

All models accessed through adapters (VERIFIED FACT — adapter pattern implemented):
```python
class ModelAdapter(ABC):
    @abstractmethod
    def get_descriptor(self) -> ModelDescriptor
    @abstractmethod
    def health_check(self) -> bool

# Current: GPT4oTextAdapter, GPT4oVisionAdapter, OpenAIEmbeddingAdapter
# Planned: QwenTextAdapter, QwenVisionAdapter, BGEEmbeddingAdapter, WhisperAudioAdapter
```

Adding a new model = implementing the adapter interface + registering in ModelRegistry. No ORION Core changes needed.

## Classification

- Current stack: VERIFIED FACT (GPT-4o, live-tested)
- Local model recommendations: HYPOTHESIS (licenses verified, not yet tested)
- DreamerV3 adapter: HYPOTHESIS (needs GPU)
- Edge deployment: HYPOTHESIS (needs edge hardware)
