"""
Tests for ORION Multimodal Adapters — Master Spec §12, §15.
"""

import pytest

from src.api import ModelDescriptor, ModelType
from src.models import (
    AudioModelAdapter,
    AudioRequest,
    AudioResponse,
    EmbeddingModelAdapter,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelRegistry,
    TextModelAdapter,
    TextRequest,
    TextResponse,
    VideoModelAdapter,
    VideoRequest,
    VideoResponse,
    VisionModelAdapter,
    VisionRequest,
    VisionResponse,
    WorldModelAdapter,
    WorldModelRequest,
    WorldModelResponse,
)

# ============================================================================
# Mock Adapters
# ============================================================================

class MockTextAdapter(TextModelAdapter):
    def get_descriptor(self):
        return ModelDescriptor(model_id="mock-text", name="Mock Text", model_type=ModelType.LLM, provider="test")
    def generate(self, request):
        return TextResponse(text="Mock response", tokens_used=10)
    async def generate_async(self, request):
        return TextResponse(text="Mock async response", tokens_used=10)
    def health_check(self):
        return True


class MockVisionAdapter(VisionModelAdapter):
    def get_descriptor(self):
        return ModelDescriptor(model_id="mock-vision", name="Mock Vision", model_type=ModelType.VISION, provider="test")
    def process(self, request):
        return VisionResponse(description="A test image", objects=[{"label": "box", "confidence": 0.95}])
    def health_check(self):
        return True


class MockAudioAdapter(AudioModelAdapter):
    def get_descriptor(self):
        return ModelDescriptor(model_id="mock-audio", name="Mock Audio", model_type=ModelType.AUDIO, provider="test")
    def process(self, request):
        return AudioResponse(transcript="Hello world", language="en")
    def health_check(self):
        return True


class MockVideoAdapter(VideoModelAdapter):
    def get_descriptor(self):
        return ModelDescriptor(model_id="mock-video", name="Mock Video", model_type=ModelType.VIDEO, provider="test")
    def process(self, request):
        return VideoResponse(summary="A test video", actions=[{"action": "walking", "start": 0, "end": 5}])
    def health_check(self):
        return True


class MockWorldModelAdapter(WorldModelAdapter):
    def get_descriptor(self):
        return ModelDescriptor(model_id="mock-wm", name="Mock World Model", model_type=ModelType.WORLD_MODEL, provider="test")
    def predict(self, request):
        return WorldModelResponse(predicted_states=[{"step": 1, "state": "predicted"}], uncertainty=0.1)
    def health_check(self):
        return True


class MockEmbeddingAdapter(EmbeddingModelAdapter):
    def get_descriptor(self):
        return ModelDescriptor(model_id="mock-emb", name="Mock Embedding", model_type=ModelType.EMBEDDING, provider="test")
    def embed(self, request):
        return EmbeddingResponse(vector=[0.1, 0.2, 0.3], dimensions=3)
    def health_check(self):
        return True


# ============================================================================
# Request/Response Tests
# ============================================================================

class TestRequestResponseTypes:
    def test_text_request_defaults(self):
        req = TextRequest(prompt="Hello")
        assert req.max_tokens == 4096
        assert req.temperature == 0.7
        assert req.stream is False

    def test_text_response(self):
        resp = TextResponse(text="Hello back", tokens_used=5)
        assert resp.text == "Hello back"
        assert resp.finish_reason == "stop"

    def test_vision_request_defaults(self):
        req = VisionRequest(image_url="http://example.com/img.png")
        assert req.task == "describe"

    def test_vision_response(self):
        resp = VisionResponse(description="A scene", objects=[{"label": "car", "confidence": 0.9}])
        assert resp.objects[0]["label"] == "car"

    def test_audio_request_defaults(self):
        req = AudioRequest(audio_path="/tmp/test.wav")
        assert req.task == "transcribe"

    def test_video_request_defaults(self):
        req = VideoRequest(video_path="/tmp/test.mp4")
        assert req.task == "understand"

    def test_world_model_request_defaults(self):
        req = WorldModelRequest(current_state={"pos": 0}, proposed_action={"move": 1})
        assert req.horizon == 1
        assert req.domain == "industrial"

    def test_embedding_request(self):
        req = EmbeddingRequest(text="test text")
        assert req.text == "test text"
        assert req.image is None


# ============================================================================
# Mock Adapter Tests
# ============================================================================

class TestMockAdapters:
    def test_text_adapter(self):
        adapter = MockTextAdapter()
        resp = adapter.generate(TextRequest(prompt="Hello"))
        assert resp.text == "Mock response"
        assert adapter.health_check() is True
        assert adapter.get_descriptor().model_type == ModelType.LLM

    def test_vision_adapter(self):
        adapter = MockVisionAdapter()
        resp = adapter.process(VisionRequest(image_url="http://test.com/img.png"))
        assert resp.description == "A test image"
        assert len(resp.objects) == 1
        assert resp.objects[0]["label"] == "box"

    def test_audio_adapter(self):
        adapter = MockAudioAdapter()
        resp = adapter.process(AudioRequest(audio_path="/tmp/test.wav"))
        assert resp.transcript == "Hello world"
        assert resp.language == "en"

    def test_video_adapter(self):
        adapter = MockVideoAdapter()
        resp = adapter.process(VideoRequest(video_path="/tmp/test.mp4"))
        assert resp.summary == "A test video"
        assert len(resp.actions) == 1

    def test_world_model_adapter(self):
        adapter = MockWorldModelAdapter()
        resp = adapter.predict(WorldModelRequest(current_state={}, proposed_action={}))
        assert len(resp.predicted_states) == 1
        assert resp.uncertainty == 0.1

    def test_embedding_adapter(self):
        adapter = MockEmbeddingAdapter()
        resp = adapter.embed(EmbeddingRequest(text="test"))
        assert resp.vector == [0.1, 0.2, 0.3]
        assert resp.dimensions == 3


# ============================================================================
# Model Registry Tests
# ============================================================================

class TestModelRegistry:
    def test_empty_registry(self):
        reg = ModelRegistry()
        models = reg.list_models()
        assert all(v == [] for v in models.values())

    def test_register_text(self):
        reg = ModelRegistry()
        reg.register_text("gpt-4o", MockTextAdapter())
        assert "gpt-4o" in reg.list_models()["text"]
        assert reg.get_text() is not None

    def test_register_text_default(self):
        reg = ModelRegistry()
        reg.register_text("model-a", MockTextAdapter())
        reg.register_text("model-b", MockTextAdapter(), default=True)
        assert reg.get_text().get_descriptor().model_id == "mock-text"

    def test_register_vision(self):
        reg = ModelRegistry()
        reg.register_vision("clip", MockVisionAdapter())
        assert "clip" in reg.list_models()["vision"]
        assert reg.get_vision() is not None

    def test_register_audio(self):
        reg = ModelRegistry()
        reg.register_audio("whisper", MockAudioAdapter())
        assert "whisper" in reg.list_models()["audio"]

    def test_register_video(self):
        reg = ModelRegistry()
        reg.register_video("video-model", MockVideoAdapter())
        assert "video-model" in reg.list_models()["video"]

    def test_register_world_model(self):
        reg = ModelRegistry()
        reg.register_world_model("wm-1", MockWorldModelAdapter())
        assert "wm-1" in reg.list_models()["world_model"]

    def test_register_embedding(self):
        reg = ModelRegistry()
        reg.register_embedding("text-embedding-3", MockEmbeddingAdapter())
        assert "text-embedding-3" in reg.list_models()["embedding"]

    def test_get_nonexistent_model(self):
        reg = ModelRegistry()
        assert reg.get_text() is None
        assert reg.get_vision() is None
        assert reg.get_audio() is None

    def test_get_specific_model_by_name(self):
        reg = ModelRegistry()
        reg.register_text("model-a", MockTextAdapter())
        reg.register_text("model-b", MockTextAdapter())
        assert reg.get_text("model-a") is not None
        assert reg.get_text("model-b") is not None
        assert reg.get_text("nonexistent") is None

    def test_health_check_all(self):
        reg = ModelRegistry()
        reg.register_text("text-1", MockTextAdapter())
        reg.register_vision("vision-1", MockVisionAdapter())
        reg.register_embedding("emb-1", MockEmbeddingAdapter())
        health = reg.health_check_all()
        assert health["text"]["text-1"] is True
        assert health["vision"]["vision-1"] is True
        assert health["embedding"]["emb-1"] is True
        assert health["audio"] == {}

    def test_list_models_all_categories(self):
        reg = ModelRegistry()
        reg.register_text("t1", MockTextAdapter())
        reg.register_vision("v1", MockVisionAdapter())
        reg.register_audio("a1", MockAudioAdapter())
        reg.register_video("vid1", MockVideoAdapter())
        reg.register_world_model("wm1", MockWorldModelAdapter())
        reg.register_embedding("e1", MockEmbeddingAdapter())
        models = reg.list_models()
        assert len(models) == 6
        assert len(models["text"]) == 1
        assert len(models["vision"]) == 1
        assert len(models["audio"]) == 1
        assert len(models["video"]) == 1
        assert len(models["world_model"]) == 1
        assert len(models["embedding"]) == 1
