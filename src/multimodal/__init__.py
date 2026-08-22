"""
ORION Phase 008 — Multimodal Coordinator. License: Apache 2.0.

Orchestrates multiple modalities (vision, image, video, audio, documents) for a single task.
Integrates with ModelRegistry for adapter lookup.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.models import ModelRegistry
from src.multimodal.audio_adapter import SimulatedAudioAdapter
from src.multimodal.document_adapter import SimulatedDocumentAdapter
from src.multimodal.image_generation_adapter import SimulatedImageGenerationAdapter
from src.multimodal.video_adapter import SimulatedVideoAdapter

logger = logging.getLogger(__name__)


# ============================================================================
# Data Types
# ============================================================================

class ModalityType(str, Enum):
    """Supported modality types for multimodal coordination."""
    TEXT = "text"
    VISION = "vision"
    IMAGE_GENERATION = "image_generation"
    IMAGE_EDITING = "image_editing"
    VIDEO = "video"
    AUDIO = "audio"
    SPEECH = "speech"
    DOCUMENT = "document"


@dataclass
class MultimodalTask:
    """A task requiring one or more modalities."""
    description: str
    inputs: Dict[ModalityType, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    required_modalities: Optional[List[ModalityType]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "inputs": {k.value: v for k, v in self.inputs.items()},
            "constraints": self.constraints,
            "context": self.context,
            "required_modalities": [m.value for m in self.required_modalities] if self.required_modalities else None,
        }


@dataclass
class MultimodalResult:
    """Result of a multimodal task execution."""
    task: str = ""
    modality_results: Dict[ModalityType, Any] = field(default_factory=dict)
    fused_output: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    modalities_used: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "modality_results": {k.value: v for k, v in self.modality_results.items()},
            "fused_output": self.fused_output,
            "confidence": self.confidence,
            "modalities_used": self.modalities_used,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
            "errors": self.errors,
        }


# ============================================================================
# Modality Selection Rules
# ============================================================================

# Keywords that trigger specific modalities
_MODALITY_KEYWORDS: Dict[ModalityType, List[str]] = {
    ModalityType.VISION: ["image", "picture", "photo", "see", "look", "visual", "detect", "recognize"],
    ModalityType.AUDIO: ["audio", "sound", "voice", "speech", "listen", "transcribe", "noise", "music"],
    ModalityType.VIDEO: ["video", "footage", "stream", "motion", "action", "temporal", "frame"],
    ModalityType.DOCUMENT: ["document", "text", "pdf", "read", "summarize", "extract", "contract", "report"],
    ModalityType.IMAGE_GENERATION: ["generate", "create image", "draw", "render", "produce image"],
    ModalityType.IMAGE_EDITING: ["edit", "modify image", "change image", "adjust image", "enhance"],
    ModalityType.SPEECH: ["speak", "narrate", "text to speech", "voice output", "read aloud"],
    ModalityType.TEXT: ["reason", "analyze", "plan", "decide", "think", "explain", "answer"],
}


# ============================================================================
# Multimodal Coordinator
# ============================================================================

class MultimodalCoordinator:
    """
    ORION Phase 008 — Multimodal Coordinator.

    Coordinates multiple modalities for a single task:
    1. Analyze task to determine needed modalities
    2. Dispatch to appropriate adapters
    3. Fuse results into unified output
    """

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        audio_adapter: Optional[SimulatedAudioAdapter] = None,
        video_adapter: Optional[SimulatedVideoAdapter] = None,
        document_adapter: Optional[SimulatedDocumentAdapter] = None,
        image_gen_adapter: Optional[SimulatedImageGenerationAdapter] = None,
    ) -> None:
        self._registry = registry
        self._audio = audio_adapter or SimulatedAudioAdapter()
        self._video = video_adapter or SimulatedVideoAdapter()
        self._document = document_adapter or SimulatedDocumentAdapter()
        self._image_gen = image_gen_adapter or SimulatedImageGenerationAdapter()
        self._call_count = 0
        self._total_latency = 0.0

    def select_modalities(self, task: MultimodalTask) -> List[ModalityType]:
        """Determine which modalities are needed for the task."""
        if task.required_modalities:
            return task.required_modalities

        # Auto-select based on inputs
        modalities: List[ModalityType] = []
        for modality in task.inputs:
            if modality not in modalities:
                modalities.append(modality)

        # Also check description for keyword triggers
        desc_lower = task.description.lower()
        for modality, keywords in _MODALITY_KEYWORDS.items():
            if modality not in modalities:
                if any(kw in desc_lower for kw in keywords):
                    modalities.append(modality)

        # Always include text for reasoning if any modality is selected
        if modalities and ModalityType.TEXT not in modalities:
            modalities.append(ModalityType.TEXT)

        return modalities if modalities else [ModalityType.TEXT]

    def execute(self, task: MultimodalTask) -> MultimodalResult:
        """Execute a multimodal task across selected modalities."""
        start = time.time()
        self._call_count += 1

        modalities = self.select_modalities(task)
        results: Dict[ModalityType, Any] = {}
        errors: List[str] = []

        for modality in modalities:
            try:
                result = self._dispatch(modality, task)
                if result is not None:
                    results[modality] = result
            except Exception as e:
                logger.warning("Modality %s failed: %s", modality.value, e)
                errors.append(f"{modality.value}: {e}")

        fused = self._fuse_results(results, task)
        elapsed = (time.time() - start) * 1000
        self._total_latency += elapsed

        # Compute confidence
        confidence = self._compute_confidence(results, errors)

        return MultimodalResult(
            task=task.description,
            modality_results=results,
            fused_output=fused,
            confidence=confidence,
            modalities_used=[m.value for m in modalities],
            latency_ms=elapsed,
            metadata={
                "modality_count": len(modalities),
                "result_count": len(results),
                "error_count": len(errors),
            },
            errors=errors,
        )

    def _dispatch(self, modality: ModalityType, task: MultimodalTask) -> Optional[Any]:
        """Dispatch to the appropriate adapter for a modality."""
        input_data = task.inputs.get(modality, {})

        if modality == ModalityType.AUDIO:
            if isinstance(input_data, dict):
                return self._audio.transcribe(input_data)
            return None

        elif modality == ModalityType.VIDEO:
            if isinstance(input_data, dict):
                return self._video.analyze(input_data)
            return None

        elif modality == ModalityType.DOCUMENT:
            if isinstance(input_data, dict):
                return self._document.extract_text(input_data)
            elif isinstance(input_data, str):
                return self._document.summarize(input_data)
            return None

        elif modality == ModalityType.IMAGE_GENERATION:
            prompt = input_data.get("prompt", task.description) if isinstance(input_data, dict) else task.description
            return self._image_gen.generate(prompt)

        elif modality == ModalityType.IMAGE_EDITING:
            if isinstance(input_data, dict):
                return self._image_gen.edit(
                    input_data.get("image", {}),
                    input_data.get("prompt", task.description),
                )
            return None

        elif modality == ModalityType.VISION:
            # Use existing GPT4oVisionAdapter via registry, or simulated
            if self._registry:
                vision_adapter = self._registry.get_vision()
                if vision_adapter:
                    # Would call vision_adapter.process() in real mode
                    return {"status": "vision_processed", "adapter": vision_adapter.get_descriptor().name}
            return {"status": "vision_processed", "adapter": "simulated"}

        elif modality == ModalityType.SPEECH:
            return {"status": "speech_output", "text": task.description}

        elif modality == ModalityType.TEXT:
            # Text reasoning — use registry or return description-based result
            if self._registry:
                text_adapter = self._registry.get_text()
                if text_adapter:
                    return {"status": "text_reasoned", "adapter": text_adapter.get_descriptor().name}
            return {"status": "text_reasoned", "adapter": "simulated"}

        return None

    def _fuse_results(self, results: Dict[ModalityType, Any],
                      task: MultimodalTask) -> Dict[str, Any]:
        """Fuse results from multiple modalities into a unified output."""
        fused: Dict[str, Any] = {
            "task": task.description,
            "modality_count": len(results),
        }

        for modality, result in results.items():
            key = modality.value
            if isinstance(result, str):
                fused[f"{key}_text"] = result
            elif isinstance(result, dict):
                fused[f"{key}_result"] = result
            else:
                fused[f"{key}_data"] = str(result)

        # Cross-modality synthesis
        if len(results) >= 2:
            fused["synthesis"] = f"Combined {len(results)} modalities for: {task.description}"
            fused["multi_modal"] = True
        else:
            fused["multi_modal"] = False

        return fused

    def _compute_confidence(self, results: Dict[ModalityType, Any],
                           errors: List[str]) -> float:
        """Compute overall confidence from results and errors."""
        if not results and errors:
            return 0.0
        total = len(results) + len(errors)
        return len(results) / total if total > 0 else 0.0

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "avg_latency_ms": self._total_latency / max(1, self._call_count),
        }
