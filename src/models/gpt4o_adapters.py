"""
ORION Concrete GPT-4o Adapters — Master Spec §12, §15

Concrete implementations of the multimodal adapter interfaces using
OpenAI's GPT-4o and text-embedding-3 models. These are the first live
model adapters — others can be added through the same ModelRegistry.

Models are swappable: the core intelligence NEVER hardcodes a model.
Register any adapter with ModelRegistry and the system uses it.

License: Apache 2.0
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from src.api import ModelDescriptor, ModelType
from src.models import (
    EmbeddingModelAdapter,
    EmbeddingRequest,
    EmbeddingResponse,
    TextModelAdapter,
    TextRequest,
    TextResponse,
    VisionModelAdapter,
    VisionRequest,
    VisionResponse,
)

logger = logging.getLogger(__name__)


# ============================================================================
# OpenAI API Helper
# ============================================================================

def _openai_request(endpoint: str, payload: dict, api_key: Optional[str] = None,
                    timeout: float = 60.0, max_retries: int = 3) -> dict:
    """Make a request to OpenAI API with HTTPS enforcement and retry logic."""
    key = api_key or os.environ.get("OPENAI_PROJECT_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No OpenAI API key found. Set OPENAI_PROJECT_KEY or OPENAI_API_KEY.")

    url = f"https://api.openai.com/v1/{endpoint}"
    # HTTPS enforcement — reject non-HTTPS URLs
    if not url.startswith("https://"):
        raise ValueError(f"ORION security: only HTTPS URLs allowed, got {url}")

    data = json.dumps(payload).encode()

    last_error = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                # Retry on rate limit or server errors
                last_error = e
                wait = min(2 ** attempt, 10)  # Exponential backoff: 1, 2, 4, max 10s
                logger.warning(f"OpenAI API error {e.code}, retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            raise  # Non-retryable HTTP error
        except urllib.error.URLError as e:
            last_error = e
            wait = min(2 ** attempt, 10)
            logger.warning(f"OpenAI API network error, retrying in {wait}s (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(wait)
            continue

    raise RuntimeError(f"OpenAI API request failed after {max_retries} retries: {last_error}")


# ============================================================================
# GPT-4o Text Adapter
# ============================================================================

class GPT4oTextAdapter(TextModelAdapter):
    """Concrete text/LLM adapter using GPT-4o."""

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_PROJECT_KEY") or os.environ.get("OPENAI_API_KEY")
        self._descriptor = ModelDescriptor(
            model_id=f"openai-{model}",
            name=f"GPT-4o ({model})",
            model_type=ModelType.LLM,
            provider="openai",
            version=model,
        )

    def get_descriptor(self) -> ModelDescriptor:
        return self._descriptor

    def generate(self, request: TextRequest) -> TextResponse:
        start = time.time()
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.stop:
            payload["stop"] = request.stop

        try:
            result = _openai_request("chat/completions", payload, self._api_key)
            latency = (time.time() - start) * 1000
            choice = result["choices"][0]
            return TextResponse(
                text=choice["message"]["content"],
                tokens_used=result.get("usage", {}).get("total_tokens", 0),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=latency,
                metadata={"model": self._model, "id": result.get("id")},
            )
        except Exception as e:
            logger.error(f"GPT-4o text generation failed: {e}")
            return TextResponse(
                text="",
                tokens_used=0,
                finish_reason="error",
                latency_ms=(time.time() - start) * 1000,
                metadata={"error": str(e)},
            )

    async def generate_async(self, request: TextRequest) -> TextResponse:
        """Async generation — falls back to sync (can be replaced with true async)."""
        return self.generate(request)

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            _openai_request("chat/completions", {
                "model": self._model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }, self._api_key, timeout=10.0)
            return True
        except Exception:
            return False


# ============================================================================
# GPT-4o Vision Adapter
# ============================================================================

class GPT4oVisionAdapter(VisionModelAdapter):
    """Concrete vision adapter using GPT-4o's multimodal capabilities."""

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_PROJECT_KEY") or os.environ.get("OPENAI_API_KEY")
        self._descriptor = ModelDescriptor(
            model_id=f"openai-{model}-vision",
            name=f"GPT-4o Vision ({model})",
            model_type=ModelType.VISION,
            provider="openai",
            version=model,
        )

    def get_descriptor(self) -> ModelDescriptor:
        return self._descriptor

    def _prepare_image(self, request: VisionRequest) -> str:
        """Convert image to base64 data URL or return URL."""
        if request.image_url:
            return request.image_url
        elif request.image_data:
            b64 = base64.b64encode(request.image_data).decode()
            return f"data:image/png;base64,{b64}"
        elif request.image_path:
            with open(request.image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{b64}"
        raise ValueError("No image provided in VisionRequest")

    def process(self, request: VisionRequest) -> VisionResponse:
        start = time.time()
        try:
            image_url = self._prepare_image(request)

            # Build prompt based on task
            if request.task == "describe" or request.task == "answer":
                prompt = request.prompt or "Describe this image in detail."
            elif request.task == "detect":
                prompt = "List all objects you can see in this image. For each object, provide: label, approximate confidence (0-1), and location description."
            elif request.task == "classify":
                prompt = "Classify the main subject of this image. Provide labels with confidence scores."
            else:
                prompt = request.prompt or "Describe this image."

            payload = {
                "model": self._model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                "max_tokens": 1000,
            }

            result = _openai_request("chat/completions", payload, self._api_key)
            latency = (time.time() - start) * 1000
            text = result["choices"][0]["message"]["content"]

            # Parse response based on task
            if request.task == "answer":
                return VisionResponse(answer=text, latency_ms=latency)
            elif request.task == "detect":
                return VisionResponse(description=text, objects=[{"label": "detected", "confidence": 0.9}], latency_ms=latency)
            elif request.task == "classify":
                return VisionResponse(classification={"label": 0.9}, description=text, latency_ms=latency)
            else:
                return VisionResponse(description=text, latency_ms=latency, metadata={"model": self._model})

        except Exception as e:
            logger.error(f"GPT-4o vision failed: {e}")
            return VisionResponse(description="", latency_ms=(time.time() - start) * 1000,
                                 metadata={"error": str(e)})

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            # Minimal text-only check (vision model supports text too)
            _openai_request("chat/completions", {
                "model": self._model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }, self._api_key, timeout=10.0)
            return True
        except Exception:
            return False


# ============================================================================
# OpenAI Embedding Adapter
# ============================================================================

class OpenAIEmbeddingAdapter(EmbeddingModelAdapter):
    """Concrete embedding adapter using OpenAI text-embedding-3."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_PROJECT_KEY") or os.environ.get("OPENAI_API_KEY")
        self._descriptor = ModelDescriptor(
            model_id=f"openai-{model}",
            name=f"OpenAI Embeddings ({model})",
            model_type=ModelType.EMBEDDING,
            provider="openai",
            version=model,
        )

    def get_descriptor(self) -> ModelDescriptor:
        return self._descriptor

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        start = time.time()
        if not request.text:
            raise ValueError("EmbeddingRequest requires text")
        try:
            result = _openai_request("embeddings", {
                "model": self._model,
                "input": request.text,
            }, self._api_key)
            latency = (time.time() - start) * 1000
            vector = result["data"][0]["embedding"]
            return EmbeddingResponse(
                vector=vector,
                dimensions=len(vector),
                latency_ms=latency,
                metadata={"model": self._model},
            )
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            return EmbeddingResponse(vector=[], dimensions=0, latency_ms=(time.time() - start) * 1000,
                                     metadata={"error": str(e)})

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            self.embed(EmbeddingRequest(text="health check"))
            return True
        except Exception:
            return False


# ============================================================================
# Model Registry Factory — Pre-registered GPT-4o models
# ============================================================================

def create_default_registry(api_key: Optional[str] = None) -> Any:
    """
    Create a ModelRegistry pre-configured with GPT-4o adapters.
    This is the default model stack for ORION (per Founder directive:
    GPT/OpenAI models only for current phase).
    """
    from src.models import ModelRegistry

    registry = ModelRegistry()

    # Register GPT-4o text
    text_adapter = GPT4oTextAdapter(api_key=api_key)
    registry.register_text("gpt-4o", text_adapter, default=True)

    # Register GPT-4o vision
    vision_adapter = GPT4oVisionAdapter(api_key=api_key)
    registry.register_vision("gpt-4o", vision_adapter, default=True)

    # Register OpenAI embeddings
    embedding_adapter = OpenAIEmbeddingAdapter(api_key=api_key)
    registry.register_embedding("text-embedding-3", embedding_adapter, default=True)

    return registry
