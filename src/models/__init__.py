"""
ORION Multimodal Adapters — Master Spec §12, §15

Models should be replaceable through adapters. This module provides
the concrete adapter interfaces for different modalities:
- Text/LLM (reasoning, planning)
- Vision (image understanding, object detection)
- Audio (speech-to-text, sound classification)
- Video (temporal understanding, action recognition)
- World Model (physics simulation, prediction)
- Embedding (semantic search, memory)

Each adapter wraps a specific model provider and exposes a uniform interface.
The core intelligence NEVER depends on a single provider — adapters are swappable.

License: Apache 2.0
"""

from __future__ import annotations

import abc
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, AsyncIterator, Callable

from src.api import ModelAdapter, ModelDescriptor, ModelType, ORIONResponse, ORIONStatus

logger = logging.getLogger(__name__)


# ============================================================================
# Modality-Specific Request/Response Types
# ============================================================================

@dataclass
class TextRequest:
    """Request to a text/LLM model."""
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 1.0
    stop: Optional[List[str]] = None
    stream: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextResponse:
    """Response from a text/LLM model."""
    text: str
    tokens_used: int = 0
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VisionRequest:
    """Request to a vision model."""
    image_data: Optional[bytes] = None
    image_url: Optional[str] = None
    image_path: Optional[str] = None
    task: str = "describe"  # describe, detect, classify, segment, answer
    prompt: Optional[str] = None  # Question for VQA
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VisionResponse:
    """Response from a vision model."""
    description: Optional[str] = None
    objects: List[Dict[str, Any]] = field(default_factory=list)  # [{label, confidence, bbox}]
    classification: Optional[Dict[str, float]] = None  # {label: confidence}
    answer: Optional[str] = None  # For VQA
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioRequest:
    """Request to an audio model."""
    audio_data: Optional[bytes] = None
    audio_path: Optional[str] = None
    task: str = "transcribe"  # transcribe, classify, detect
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioResponse:
    """Response from an audio model."""
    transcript: Optional[str] = None
    language: Optional[str] = None
    segments: List[Dict[str, Any]] = field(default_factory=list)
    sounds: List[Dict[str, Any]] = field(default_factory=list)  # For sound classification
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoRequest:
    """Request to a video model."""
    video_data: Optional[bytes] = None
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    task: str = "understand"  # understand, detect_actions, summarize, predict
    prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoResponse:
    """Response from a video model."""
    summary: Optional[str] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)  # [{action, start, end, confidence}]
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldModelRequest:
    """Request to a world model (physics/prediction)."""
    current_state: Dict[str, Any]
    proposed_action: Dict[str, Any]
    horizon: int = 1  # How many steps ahead to predict
    domain: str = "industrial"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldModelResponse:
    """Response from a world model."""
    predicted_states: List[Dict[str, Any]] = field(default_factory=list)
    safety_assessment: Optional[Dict[str, Any]] = None
    uncertainty: float = 0.0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingRequest:
    """Request to an embedding model."""
    text: Optional[str] = None
    image: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    """Response from an embedding model."""
    vector: List[float] = field(default_factory=list)
    dimensions: int = 0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Abstract Multimodal Adapters
# ============================================================================

class TextModelAdapter(abc.ABC):
    """Adapter for text/LLM models (GPT-4o, Claude, Llama, etc.)."""

    @abc.abstractmethod
    def get_descriptor(self) -> ModelDescriptor:
        ...

    @abc.abstractmethod
    def generate(self, request: TextRequest) -> TextResponse:
        ...

    @abc.abstractmethod
    async def generate_async(self, request: TextRequest) -> TextResponse:
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        ...


class VisionModelAdapter(abc.ABC):
    """Adapter for vision models (GPT-4o vision, CLIP, YOLO, etc.)."""

    @abc.abstractmethod
    def get_descriptor(self) -> ModelDescriptor:
        ...

    @abc.abstractmethod
    def process(self, request: VisionRequest) -> VisionResponse:
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        ...


class AudioModelAdapter(abc.ABC):
    """Adapter for audio models (Whisper, etc.)."""

    @abc.abstractmethod
    def get_descriptor(self) -> ModelDescriptor:
        ...

    @abc.abstractmethod
    def process(self, request: AudioRequest) -> AudioResponse:
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        ...


class VideoModelAdapter(abc.ABC):
    """Adapter for video models (temporal understanding, action recognition)."""

    @abc.abstractmethod
    def get_descriptor(self) -> ModelDescriptor:
        ...

    @abc.abstractmethod
    def process(self, request: VideoRequest) -> VideoResponse:
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        ...


class WorldModelAdapter(abc.ABC):
    """Adapter for world models (physics simulation, future prediction)."""

    @abc.abstractmethod
    def get_descriptor(self) -> ModelDescriptor:
        ...

    @abc.abstractmethod
    def predict(self, request: WorldModelRequest) -> WorldModelResponse:
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        ...


class EmbeddingModelAdapter(abc.ABC):
    """Adapter for embedding models (text-embedding-3, etc.)."""

    @abc.abstractmethod
    def get_descriptor(self) -> ModelDescriptor:
        ...

    @abc.abstractmethod
    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        ...


# ============================================================================
# Model Registry — Manages all model adapters
# ============================================================================

class ModelRegistry:
    """
    Central registry for all model adapters in ORION.
    
    Models are registered by type and can be swapped at runtime.
    The core intelligence queries the registry, never hardcoding a specific model.
    """

    def __init__(self) -> None:
        self._adapters: Dict[ModelType, ModelAdapter] = {}
        self._text_adapters: Dict[str, TextModelAdapter] = {}
        self._vision_adapters: Dict[str, VisionModelAdapter] = {}
        self._audio_adapters: Dict[str, AudioModelAdapter] = {}
        self._video_adapters: Dict[str, VideoModelAdapter] = {}
        self._world_model_adapters: Dict[str, WorldModelAdapter] = {}
        self._embedding_adapters: Dict[str, EmbeddingModelAdapter] = {}
        self._default_text: Optional[str] = None
        self._default_vision: Optional[str] = None
        self._default_audio: Optional[str] = None
        self._default_video: Optional[str] = None
        self._default_world_model: Optional[str] = None
        self._default_embedding: Optional[str] = None

    def register_text(self, name: str, adapter: TextModelAdapter, default: bool = False) -> None:
        self._text_adapters[name] = adapter
        if default or self._default_text is None:
            self._default_text = name
        logger.info(f"Registered text model: {name}")

    def register_vision(self, name: str, adapter: VisionModelAdapter, default: bool = False) -> None:
        self._vision_adapters[name] = adapter
        if default or self._default_vision is None:
            self._default_vision = name
        logger.info(f"Registered vision model: {name}")

    def register_audio(self, name: str, adapter: AudioModelAdapter, default: bool = False) -> None:
        self._audio_adapters[name] = adapter
        if default or self._default_audio is None:
            self._default_audio = name
        logger.info(f"Registered audio model: {name}")

    def register_video(self, name: str, adapter: VideoModelAdapter, default: bool = False) -> None:
        self._video_adapters[name] = adapter
        if default or self._default_video is None:
            self._default_video = name
        logger.info(f"Registered video model: {name}")

    def register_world_model(self, name: str, adapter: WorldModelAdapter, default: bool = False) -> None:
        self._world_model_adapters[name] = adapter
        if default or self._default_world_model is None:
            self._default_world_model = name
        logger.info(f"Registered world model: {name}")

    def register_embedding(self, name: str, adapter: EmbeddingModelAdapter, default: bool = False) -> None:
        self._embedding_adapters[name] = adapter
        if default or self._default_embedding is None:
            self._default_embedding = name
        logger.info(f"Registered embedding model: {name}")

    def get_text(self, name: Optional[str] = None) -> Optional[TextModelAdapter]:
        key = name or self._default_text
        return self._text_adapters.get(key) if key else None

    def get_vision(self, name: Optional[str] = None) -> Optional[VisionModelAdapter]:
        key = name or self._default_vision
        return self._vision_adapters.get(key) if key else None

    def get_audio(self, name: Optional[str] = None) -> Optional[AudioModelAdapter]:
        key = name or self._default_audio
        return self._audio_adapters.get(key) if key else None

    def get_video(self, name: Optional[str] = None) -> Optional[VideoModelAdapter]:
        key = name or self._default_video
        return self._video_adapters.get(key) if key else None

    def get_world_model(self, name: Optional[str] = None) -> Optional[WorldModelAdapter]:
        key = name or self._default_world_model
        return self._world_model_adapters.get(key) if key else None

    def get_embedding(self, name: Optional[str] = None) -> Optional[EmbeddingModelAdapter]:
        key = name or self._default_embedding
        return self._embedding_adapters.get(key) if key else None

    def list_models(self) -> Dict[str, List[str]]:
        """List all registered models by type."""
        return {
            "text": list(self._text_adapters.keys()),
            "vision": list(self._vision_adapters.keys()),
            "audio": list(self._audio_adapters.keys()),
            "video": list(self._video_adapters.keys()),
            "world_model": list(self._world_model_adapters.keys()),
            "embedding": list(self._embedding_adapters.keys()),
        }

    def health_check_all(self) -> Dict[str, Dict[str, bool]]:
        """Health check all registered models."""
        results = {}
        for category, adapters in [
            ("text", self._text_adapters),
            ("vision", self._vision_adapters),
            ("audio", self._audio_adapters),
            ("video", self._video_adapters),
            ("world_model", self._world_model_adapters),
            ("embedding", self._embedding_adapters),
        ]:
            results[category] = {name: adapter.health_check() for name, adapter in adapters.items()}
        return results
