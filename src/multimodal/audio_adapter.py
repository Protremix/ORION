"""
ORION Phase 008 — Simulated Audio Adapter. License: Apache 2.0.

Audio understanding: speech-to-text, sound classification.
Simulation mode — no real API calls. Uses pattern matching on input metadata.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.api import ModelDescriptor, ModelType
from src.models import AudioModelAdapter, AudioRequest, AudioResponse

logger = logging.getLogger(__name__)


class SimulatedAudioAdapter(AudioModelAdapter):
    """Simulated audio adapter for speech-to-text and sound classification."""

    def __init__(self) -> None:
        self._call_count = 0
        self._total_latency = 0.0

    def get_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            model_id="simulated-audio",
            name="Simulated Audio",
            model_type=ModelType.AUDIO,
            version="1.0.0",
            provider="ORION-sim",
        )

    def process(self, request: AudioRequest) -> AudioResponse:
        """Process audio request — transcribe or classify."""
        start = time.time()
        self._call_count += 1

        # In simulation, metadata carries the expected content
        meta = request.metadata or {}
        transcript = meta.get("transcript", meta.get("expected_text", "Simulated transcription output."))
        sound_type = meta.get("sound_type", "speech")
        language = meta.get("language", request.language or "en")
        segments = meta.get("segments", [])
        sounds = meta.get("sounds", [{"type": sound_type, "confidence": 0.85}])

        elapsed = (time.time() - start) * 1000
        self._total_latency += elapsed

        return AudioResponse(
            transcript=transcript,
            language=language,
            segments=segments,
            sounds=sounds,
            latency_ms=elapsed,
            metadata={"adapter": "simulated", "call_count": self._call_count},
        )

    def transcribe(self, audio_data: Dict[str, Any]) -> str:
        """Transcribe audio to text."""
        resp = self.process(AudioRequest(
            task="transcribe",
            metadata=audio_data,
        ))
        return resp.transcript or ""

    def classify_sound(self, audio_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify sound type from audio data."""
        sound_type = audio_data.get("sound_type", "unknown")
        confidence = audio_data.get("confidence", 0.85)
        return {
            "sound_type": sound_type,
            "confidence": confidence,
            "categories": [sound_type] if sound_type != "unknown" else ["speech", "music", "noise"],
        }

    def health_check(self) -> bool:
        return True

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "avg_latency_ms": self._total_latency / max(1, self._call_count),
        }
