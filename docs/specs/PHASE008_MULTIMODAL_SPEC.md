# ORION Phase 008 — Multimodal Specification

**Phase:** 008
**Status:** DRAFT
**License:** Apache 2.0
**Roadmap Reference:** ORION_MASTER_ROADMAP_v1.0 Phase 008

## 1. Goal

Integrate multiple modalities into ORION: vision, image, video, audio, documents.

Capabilities:
- Image understanding (existing GPT4oVisionAdapter)
- Image generation (NEW)
- Image editing (NEW)
- Video understanding (NEW)
- Video generation (NEW)
- Audio understanding (NEW — speech-to-text, sound classification)
- Speech (NEW — text-to-speech)
- Document understanding (NEW — text extraction, summarization, Q&A)

**Acceptance Criterion:** ORION can coordinate multiple modalities for one task.

All external models must be recorded in LICENSE_REGISTRY.

## 2. Current State (VERIFIED FACT)

Existing components:
- `ModelRegistry` (src/models/__init__.py) — registry for text, vision, audio, video, world_model, embedding adapters. Has registration slots for all 6 modality types.
- `TextModelAdapter`, `VisionModelAdapter`, `AudioModelAdapter`, `VideoModelAdapter` — abstract base classes already defined
- `GPT4oTextAdapter`, `GPT4oVisionAdapter`, `OpenAIEmbeddingAdapter` — concrete adapters implemented
- `AudioRequest`/`AudioResponse`, `VideoRequest`/`VideoResponse` — data classes defined
- `LICENSE_REGISTRY.md` — maintained, tracks all external models
- No audio, video, or document adapters implemented yet
- No multimodal coordination layer exists

**Gap:**
1. No concrete AudioAdapter (speech-to-text, sound classification)
2. No concrete VideoAdapter (temporal understanding, action recognition)
3. No DocumentAdapter (text extraction, understanding)
4. No ImageGenerationAdapter (DALL-E or equivalent)
5. No MultimodalCoordinator to orchestrate multiple modalities for a single task

## 3. Architecture

### 3.1 New Component: MultimodalCoordinator

```
                    ┌─────────────────────────────┐
                    │  MultimodalCoordinator       │
                    │                             │
  Task ───────────►│  1. Analyze task             │
                    │  2. Select modalities       │
                    │  3. Dispatch to adapters     │──► VisionAdapter
                    │  4. Collect results         │──► AudioAdapter
                    │  5. Fuse results            │──► VideoAdapter
                    │  6. Return unified output   │──► DocumentAdapter
                    └─────────────────────────────┘──► TextAdapter (reasoning)
```

#### MultimodalCoordinator
- **Purpose:** Orchestrate multiple modalities for a single task
- **Input:** `MultimodalTask` (task description, input modalities, data)
- **Output:** `MultimodalResult` (fused results from all modalities)
- **Key methods:**
  - `execute(task: MultimodalTask) -> MultimodalResult`
  - `select_modalities(task: MultimodalTask) -> List[ModalityType]`
  - `fuse_results(results: Dict[ModalityType, Any]) -> MultimodalResult`

#### MultimodalTask
- **Data class:** description, inputs (Dict[ModalityType, Any]), constraints, context

#### MultimodalResult
- **Data class:** task, modality_results (Dict[ModalityType, Any]), fused_output, confidence, metadata

#### ModalityType (Enum)
- TEXT, VISION, IMAGE_GENERATION, IMAGE_EDITING, VIDEO, AUDIO, SPEECH, DOCUMENT

### 3.2 New Adapters

#### SimulatedAudioAdapter
- **Purpose:** Audio understanding (speech-to-text, sound classification)
- **Mode:** Simulation (no real API calls in tests)
- **Key methods:** `transcribe(audio_data) -> str`, `classify_sound(audio_data) -> Dict`

#### SimulatedVideoAdapter
- **Purpose:** Video understanding (temporal analysis, action recognition)
- **Mode:** Simulation
- **Key methods:** `analyze(video_data) -> Dict`, `detect_actions(video_data) -> List`

#### SimulatedDocumentAdapter
- **Purpose:** Document understanding (text extraction, summarization, Q&A)
- **Mode:** Simulation
- **Key methods:** `extract_text(document_data) -> str`, `summarize(text) -> str`, `answer_question(text, question) -> str`

#### SimulatedImageGenerationAdapter
- **Purpose:** Image generation and editing
- **Mode:** Simulation
- **Key methods:** `generate(prompt) -> Dict`, `edit(image_data, prompt) -> Dict`

### 3.3 Existing Components (Reuse)

| Component | Role | Phase |
|---|---|---|
| ModelRegistry | Adapter registration and lookup | 002 |
| GPT4oTextAdapter | Text reasoning | 002 |
| GPT4oVisionAdapter | Image understanding | 002 |
| OpenAIEmbeddingAdapter | Semantic embeddings | 002 |
| WorldState (Phase 006) | World state input | 006 |
| SimulationEngine (Phase 007) | Action simulation | 007 |

### 3.4 Integration Points

1. **Phase 007 (Simulation):** SimulationEngine can use multimodal inputs
2. **Phase 006 (World Model):** WorldState can incorporate multimodal observations
3. **Phase 005 (Memory):** Multimodal results stored in memory
4. **Phase 004 (Core):** CoreSupervisor can dispatch multimodal tasks
5. **Phase 009 (Agent System):** Future — agents use multimodal coordinator

## 4. Acceptance Criteria

| AC | Description | Verification |
|---|---|---|
| AC1 | AudioAdapter transcribes simulated audio data | Unit test: transcribe() returns text |
| AC2 | AudioAdapter classifies simulated sound types | Unit test: classify_sound() returns classification |
| AC3 | VideoAdapter analyzes simulated video frames | Unit test: analyze() returns analysis dict |
| AC4 | VideoAdapter detects actions in simulated video | Unit test: detect_actions() returns action list |
| AC5 | DocumentAdapter extracts text from simulated documents | Unit test: extract_text() returns text |
| AC6 | DocumentAdapter summarizes text | Unit test: summarize() returns summary |
| AC7 | ImageGenerationAdapter generates from prompt (simulation) | Unit test: generate() returns result dict |
| AC8 | ImageGenerationAdapter edits image (simulation) | Unit test: edit() returns result dict |
| AC9 | MultimodalCoordinator selects appropriate modalities for a task | Unit test: select_modalities() returns expected types |
| AC10 | MultimodalCoordinator dispatches to multiple adapters | Unit test: execute() calls 2+ adapters |
| AC11 | MultimodalCoordinator fuses results from multiple modalities | Unit test: fused_output contains data from 2+ modalities |
| AC12 | ORION coordinates vision + text for an image understanding task | Integration test: image + question -> answer |
| AC13 | ORION coordinates audio + document for a transcription task | Integration test: audio + document -> text |
| AC14 | All new adapters registered in ModelRegistry | Unit test: registry.list_models() includes new types |
| AC15 | All external models recorded in LICENSE_REGISTRY | Documentation check |
| AC16 | All tests pass | pytest -q (zero failures) |
| AC17 | Ruff/mypy clean | ruff check + mypy |

## 5. File Structure

```
src/multimodal/
    __init__.py                 — NEW: MultimodalCoordinator, MultimodalTask, MultimodalResult, ModalityType
    audio_adapter.py            — NEW: SimulatedAudioAdapter
    video_adapter.py             — NEW: SimulatedVideoAdapter
    document_adapter.py          — NEW: SimulatedDocumentAdapter
    image_generation_adapter.py  — NEW: SimulatedImageGenerationAdapter

tests/unit/
    test_phase008.py             — NEW: all Phase 008 tests
```

## 6. Test Plan (~40 tests)

### Unit Tests (~30)
- AudioAdapter: transcribe, classify_sound, error handling, health_check
- VideoAdapter: analyze, detect_actions, error handling, health_check
- DocumentAdapter: extract_text, summarize, answer_question, health_check
- ImageGenerationAdapter: generate, edit, health_check
- MultimodalCoordinator: select_modalities, execute, fuse_results, single modality, multi modality
- ModelRegistry: new adapters registered and retrievable

### Integration Tests (~10)
- Vision + Text: image understanding task (GPT4oVisionAdapter + GPT4oTextAdapter simulation)
- Audio + Document: transcription verification task
- Multi-modal: vision + audio + text coordinated task
- SimulationEngine + MultimodalCoordinator: multimodal input to simulation
- Edge cases: no adapters available, all adapters fail, single modality fallback

## 7. Scope

### IN SCOPE
- MultimodalCoordinator orchestration layer
- Simulated audio, video, document, image generation adapters
- Multi-modality coordination and result fusion
- ModelRegistry integration
- LICENSE_REGISTRY update
- Simulation-only (no real API calls in tests)

### OUT OF SCOPE
- Real API integration for audio/video/generation (Phase 011+)
- Real-time video stream processing
- Training custom models
- Multi-agent multimodal coordination (Phase 009)
