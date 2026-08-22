"""
ORION Phase 008 — Multimodal Test Suite. License: Apache 2.0.

Tests: MultimodalCoordinator, SimulatedAudioAdapter, SimulatedVideoAdapter,
SimulatedDocumentAdapter, SimulatedImageGenerationAdapter.
Integration: multi-modality coordination, ModelRegistry, cross-modality tasks.
"""
from __future__ import annotations

import pytest

from src.models import ModelRegistry
from src.multimodal import (
    ModalityType,
    MultimodalCoordinator,
    MultimodalResult,
    MultimodalTask,
)
from src.multimodal.audio_adapter import SimulatedAudioAdapter
from src.multimodal.document_adapter import SimulatedDocumentAdapter
from src.multimodal.image_generation_adapter import SimulatedImageGenerationAdapter
from src.multimodal.video_adapter import SimulatedVideoAdapter

# ============================================================================
# AudioAdapter Tests (AC1, AC2)
# ============================================================================

class TestAudioAdapter:
    def test_transcribe(self):
        """AC1: AudioAdapter transcribes simulated audio data."""
        adapter = SimulatedAudioAdapter()
        result = adapter.transcribe({"transcript": "Hello world"})
        assert result == "Hello world"

    def test_transcribe_default(self):
        adapter = SimulatedAudioAdapter()
        result = adapter.transcribe({})
        assert "Simulated" in result or len(result) > 0

    def test_classify_sound(self):
        """AC2: AudioAdapter classifies simulated sound types."""
        adapter = SimulatedAudioAdapter()
        result = adapter.classify_sound({"sound_type": "speech", "confidence": 0.9})
        assert result["sound_type"] == "speech"
        assert result["confidence"] == 0.9

    def test_classify_sound_unknown(self):
        adapter = SimulatedAudioAdapter()
        result = adapter.classify_sound({})
        assert "categories" in result
        assert len(result["categories"]) >= 1

    def test_health_check(self):
        adapter = SimulatedAudioAdapter()
        assert adapter.health_check() is True

    def test_process_returns_audio_response(self):
        from src.models import AudioRequest
        adapter = SimulatedAudioAdapter()
        resp = adapter.process(AudioRequest(task="transcribe", metadata={"transcript": "test"}))
        assert resp.transcript == "test"

    def test_get_descriptor(self):
        adapter = SimulatedAudioAdapter()
        desc = adapter.get_descriptor()
        assert desc.model_id == "simulated-audio"


# ============================================================================
# VideoAdapter Tests (AC3, AC4)
# ============================================================================

class TestVideoAdapter:
    def test_analyze(self):
        """AC3: VideoAdapter analyzes simulated video frames."""
        adapter = SimulatedVideoAdapter()
        result = adapter.analyze({"frames": [1, 2, 3], "duration": 10.0})
        assert "summary" in result
        assert result["action_count"] >= 1

    def test_detect_actions(self):
        """AC4: VideoAdapter detects actions in simulated video."""
        adapter = SimulatedVideoAdapter()
        actions = adapter.detect_actions({"actions": [{"action": "walking", "start": 0, "end": 5}]})
        assert len(actions) >= 1
        assert actions[0]["action"] == "walking"

    def test_detect_actions_default(self):
        adapter = SimulatedVideoAdapter()
        actions = adapter.detect_actions({})
        assert len(actions) >= 1

    def test_health_check(self):
        adapter = SimulatedVideoAdapter()
        assert adapter.health_check() is True

    def test_process_returns_video_response(self):
        from src.models import VideoRequest
        adapter = SimulatedVideoAdapter()
        resp = adapter.process(VideoRequest(task="understand", metadata={"frames": [1, 2]}))
        assert resp.summary is not None

    def test_get_descriptor(self):
        adapter = SimulatedVideoAdapter()
        desc = adapter.get_descriptor()
        assert desc.model_id == "simulated-video"


# ============================================================================
# DocumentAdapter Tests (AC5, AC6)
# ============================================================================

class TestDocumentAdapter:
    def test_extract_text(self):
        """AC5: DocumentAdapter extracts text from simulated documents."""
        adapter = SimulatedDocumentAdapter()
        result = adapter.extract_text({"text": "This is a document."})
        assert result == "This is a document."

    def test_extract_text_from_content(self):
        adapter = SimulatedDocumentAdapter()
        result = adapter.extract_text({"content": "From content field."})
        assert result == "From content field."

    def test_extract_text_empty(self):
        adapter = SimulatedDocumentAdapter()
        result = adapter.extract_text({})
        assert "No text" in result

    def test_summarize(self):
        """AC6: DocumentAdapter summarizes text."""
        adapter = SimulatedDocumentAdapter()
        long_text = "This is sentence one. " * 50
        summary = adapter.summarize(long_text, max_length=100)
        assert len(summary) <= 102  # allow slight overage from ". "

    def test_summarize_short_text(self):
        adapter = SimulatedDocumentAdapter()
        result = adapter.summarize("Short text.")
        assert result == "Short text."

    def test_answer_question(self):
        adapter = SimulatedDocumentAdapter()
        text = "The temperature is 22 degrees Celsius. The humidity is 45 percent."
        answer = adapter.answer_question(text, "What is the temperature?")
        assert "temperature" in answer.lower()

    def test_classify_document(self):
        adapter = SimulatedDocumentAdapter()
        assert adapter.classify_document({"type": "invoice"}) == "invoice"
        assert adapter.classify_document({"text": "Payment of $500 due."}) == "invoice"
        assert adapter.classify_document({"text": "Analysis report on Q3."}) == "report"

    def test_health_check(self):
        adapter = SimulatedDocumentAdapter()
        assert adapter.health_check() is True


# ============================================================================
# ImageGenerationAdapter Tests (AC7, AC8)
# ============================================================================

class TestImageGenerationAdapter:
    def test_generate(self):
        """AC7: ImageGenerationAdapter generates from prompt (simulation)."""
        adapter = SimulatedImageGenerationAdapter()
        result = adapter.generate("a red car on a highway")
        assert result["status"] == "generated"
        assert result["prompt"] == "a red car on a highway"
        assert "url" in result
        assert "image_id" in result

    def test_generate_deterministic(self):
        adapter = SimulatedImageGenerationAdapter()
        r1 = adapter.generate("test prompt")
        r2 = adapter.generate("test prompt")
        assert r1["image_id"] == r2["image_id"]  # Same prompt = same ID

    def test_edit(self):
        """AC8: ImageGenerationAdapter edits image (simulation)."""
        adapter = SimulatedImageGenerationAdapter()
        result = adapter.edit({"image_id": "orig123"}, "make it blue")
        assert result["status"] == "edited"
        assert result["original_image_id"] == "orig123"
        assert result["edit_prompt"] == "make it blue"

    def test_edit_with_mask(self):
        adapter = SimulatedImageGenerationAdapter()
        result = adapter.edit({"image_id": "img1"}, "remove background", mask={"region": "center"})
        assert result["mask_applied"] is True

    def test_health_check(self):
        adapter = SimulatedImageGenerationAdapter()
        assert adapter.health_check() is True


# ============================================================================
# MultimodalCoordinator Tests (AC9, AC10, AC11)
# ============================================================================

class TestMultimodalCoordinator:
    def test_select_modalities_auto(self):
        """AC9: MultimodalCoordinator selects appropriate modalities."""
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="Analyze this image and transcribe the audio",
            inputs={ModalityType.VISION: {"image": "test"}, ModalityType.AUDIO: {"audio": "test"}},
        )
        modalities = coord.select_modalities(task)
        assert ModalityType.VISION in modalities
        assert ModalityType.AUDIO in modalities

    def test_select_modalities_from_keywords(self):
        coord = MultimodalCoordinator()
        task = MultimodalTask(description="transcribe this audio recording")
        modalities = coord.select_modalities(task)
        assert ModalityType.AUDIO in modalities

    def test_select_modalities_explicit(self):
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="test",
            required_modalities=[ModalityType.VISION, ModalityType.TEXT],
        )
        modalities = coord.select_modalities(task)
        assert modalities == [ModalityType.VISION, ModalityType.TEXT]

    def test_execute_multiple_modalities(self):
        """AC10: MultimodalCoordinator dispatches to multiple adapters."""
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="Analyze image and transcribe audio",
            inputs={
                ModalityType.VISION: {"image": "test.jpg"},
                ModalityType.AUDIO: {"transcript": "Hello"},
            },
        )
        result = coord.execute(task)
        assert isinstance(result, MultimodalResult)
        assert len(result.modalities_used) >= 2

    def test_fuse_results(self):
        """AC11: MultimodalCoordinator fuses results from multiple modalities."""
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="Multi-modal task",
            inputs={
                ModalityType.AUDIO: {"transcript": "hello"},
                ModalityType.DOCUMENT: {"text": "doc content"},
            },
        )
        result = coord.execute(task)
        assert result.fused_output.get("multi_modal") is True
        assert len(result.modality_results) >= 2

    def test_execute_single_modality(self):
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="Generate an image of a sunset",
            inputs={ModalityType.IMAGE_GENERATION: {"prompt": "sunset over ocean"}},
        )
        result = coord.execute(task)
        assert len(result.modalities_used) >= 1
        assert result.confidence > 0

    def test_execute_no_inputs(self):
        coord = MultimodalCoordinator()
        task = MultimodalTask(description="Reason about this problem")
        result = coord.execute(task)
        assert ModalityType.TEXT in [ModalityType(m) for m in result.modalities_used]

    def test_result_to_dict(self):
        coord = MultimodalCoordinator()
        task = MultimodalTask(description="test", inputs={ModalityType.AUDIO: {"transcript": "hi"}})
        result = coord.execute(task)
        d = result.to_dict()
        assert "task" in d
        assert "fused_output" in d

    def test_confidence_with_errors(self):
        coord = MultimodalCoordinator()
        # Force error by passing bad input
        task = MultimodalTask(
            description="test",
            inputs={ModalityType.IMAGE_EDITING: "not_a_dict"},
        )
        result = coord.execute(task)
        assert result.confidence >= 0.0

    def test_statistics(self):
        coord = MultimodalCoordinator()
        coord.execute(MultimodalTask(description="test"))
        stats = coord.get_statistics()
        assert stats["total_calls"] == 1


# ============================================================================
# Integration Tests (AC12, AC13, AC14)
# ============================================================================

class TestPhase008Integration:
    def test_vision_text_coordination(self):
        """AC12: ORION coordinates vision + text for image understanding."""
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="What objects are in this image? Explain what you see.",
            inputs={ModalityType.VISION: {"image": "street_scene.jpg"}},
        )
        result = coord.execute(task)
        assert ModalityType.VISION.value in result.modalities_used
        assert ModalityType.TEXT.value in result.modalities_used
        assert result.fused_output.get("multi_modal") is True

    def test_audio_document_coordination(self):
        """AC13: ORION coordinates audio + document for transcription task."""
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="Transcribe this audio and compare with this document",
            inputs={
                ModalityType.AUDIO: {"transcript": "The meeting is at 3 PM."},
                ModalityType.DOCUMENT: {"text": "The meeting is at 3 PM."},
            },
        )
        result = coord.execute(task)
        assert ModalityType.AUDIO.value in result.modalities_used
        assert ModalityType.DOCUMENT.value in result.modalities_used
        assert result.confidence > 0

    def test_multi_modal_three_modalities(self):
        """Integration: 3+ modalities coordinated."""
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="Analyze image, transcribe audio, and summarize document",
            inputs={
                ModalityType.VISION: {"image": "scene.jpg"},
                ModalityType.AUDIO: {"transcript": "describing the scene"},
                ModalityType.DOCUMENT: {"text": "A report about the scene."},
            },
        )
        result = coord.execute(task)
        assert len(result.modalities_used) >= 3
        assert result.fused_output.get("multi_modal") is True
        assert result.metadata["modality_count"] >= 3

    def test_registry_integration(self):
        """AC14: New adapters registered in ModelRegistry."""
        registry = ModelRegistry()
        audio = SimulatedAudioAdapter()
        video = SimulatedVideoAdapter()
        registry.register_audio("simulated-audio", audio, default=True)
        registry.register_video("simulated-video", video, default=True)
        models = registry.list_models()
        assert "simulated-audio" in models["audio"]
        assert "simulated-video" in models["video"]
        assert registry.get_audio() is not None
        assert registry.get_video() is not None

    def test_coordinator_with_registry(self):
        """Coordinator uses registry when available."""
        registry = ModelRegistry()
        coord = MultimodalCoordinator(registry=registry)
        task = MultimodalTask(
            description="Analyze this image",
            inputs={ModalityType.VISION: {"image": "test.jpg"}},
        )
        result = coord.execute(task)
        assert result.confidence > 0

    def test_image_generation_and_editing_pipeline(self):
        """Integration: generate then edit an image."""
        gen = SimulatedImageGenerationAdapter()
        generated = gen.generate("a landscape")
        assert generated["status"] == "generated"
        edited = gen.edit(generated, "add a sunset")
        assert edited["status"] == "edited"
        assert edited["original_image_id"] == generated["image_id"]

    def test_document_qa_pipeline(self):
        """Integration: extract → summarize → answer question."""
        doc = SimulatedDocumentAdapter()
        text = doc.extract_text({"text": "The server room temperature is 25C. " * 20})
        summary = doc.summarize(text, max_length=150)
        assert len(summary) <= 152
        answer = doc.answer_question(text, "What is the temperature?")
        assert "temperature" in answer.lower() or "no direct answer" in answer.lower()

    def test_video_action_detection_pipeline(self):
        """Integration: analyze → detect actions."""
        vid = SimulatedVideoAdapter()
        analysis = vid.analyze({"frames": list(range(30)), "duration": 5.0})
        assert "summary" in analysis
        actions = vid.detect_actions({"actions": [{"action": "person_walking", "start": 0, "end": 3}]})
        assert len(actions) == 1

    def test_all_adapters_health(self):
        """All adapters pass health check."""
        assert SimulatedAudioAdapter().health_check() is True
        assert SimulatedVideoAdapter().health_check() is True
        assert SimulatedDocumentAdapter().health_check() is True
        assert SimulatedImageGenerationAdapter().health_check() is True

    def test_latency_measured(self):
        """Performance: all operations complete with latency tracking."""
        coord = MultimodalCoordinator()
        task = MultimodalTask(
            description="test",
            inputs={ModalityType.AUDIO: {"transcript": "hello"}},
        )
        result = coord.execute(task)
        assert result.latency_ms > 0

    def test_modality_type_enum(self):
        """ModalityType enum has all required types."""
        assert ModalityType.TEXT.value == "text"
        assert ModalityType.VISION.value == "vision"
        assert ModalityType.AUDIO.value == "audio"
        assert ModalityType.VIDEO.value == "video"
        assert ModalityType.DOCUMENT.value == "document"
        assert ModalityType.IMAGE_GENERATION.value == "image_generation"
        assert ModalityType.IMAGE_EDITING.value == "image_editing"
        assert ModalityType.SPEECH.value == "speech"
