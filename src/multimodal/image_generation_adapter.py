"""
ORION Phase 008 — Simulated Image Generation Adapter. License: Apache 2.0.

Image generation and editing.
Simulation mode — returns metadata describing the generated/edited image.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, Optional

from src.api import ModelDescriptor, ModelType

logger = logging.getLogger(__name__)


class SimulatedImageGenerationAdapter:
    """Simulated image generation and editing adapter."""

    def __init__(self) -> None:
        self._call_count = 0
        self._total_latency = 0.0

    def get_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            model_id="simulated-image-gen",
            name="Simulated Image Gen",
            model_type=ModelType.IMAGE,
            version="1.0.0",
            provider="ORION-sim",
        )

    def generate(self, prompt: str, size: str = "1024x1024",
                 style: str = "natural") -> Dict[str, Any]:
        """Generate an image from a text prompt (simulated)."""
        start = time.time()
        self._call_count += 1

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        elapsed = (time.time() - start) * 1000
        self._total_latency += elapsed

        return {
            "image_id": f"sim_img_{prompt_hash}",
            "prompt": prompt,
            "size": size,
            "style": style,
            "url": f"sim://images/{prompt_hash}.png",
            "status": "generated",
            "adapter": "simulated",
        }

    def edit(self, image_data: Dict[str, Any], prompt: str,
             mask: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Edit an existing image with a prompt (simulated)."""
        start = time.time()
        self._call_count += 1

        original_id = image_data.get("image_id", "unknown")
        edit_hash = hashlib.sha256(
            (str(original_id) + prompt).encode()
        ).hexdigest()[:16]

        elapsed = (time.time() - start) * 1000
        self._total_latency += elapsed

        return {
            "image_id": f"sim_edit_{edit_hash}",
            "original_image_id": original_id,
            "edit_prompt": prompt,
            "mask_applied": mask is not None,
            "url": f"sim://images/edited_{edit_hash}.png",
            "status": "edited",
            "adapter": "simulated",
        }

    def health_check(self) -> bool:
        return True

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "avg_latency_ms": self._total_latency / max(1, self._call_count),
        }
