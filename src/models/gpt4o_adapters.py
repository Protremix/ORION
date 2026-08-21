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
from pathlib import Path
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
# OpenAI API Helper & Path Validation
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


def validate_image_path(path: str) -> bytes:
    """
    Validate an image file path against path traversal and directory boundary restrictions
    using descriptor-based opening to prevent TOCTOU (time-of-check-time-of-use) attacks.

    Change #9 (Luna Round 5): Uses os.open with dir_fd parameter to walk each path
    component relative to its parent directory descriptor. This eliminates the TOCTOU
    race window between checking parent directories for symlinks and opening the file.
    Each component is opened with O_NOFOLLOW, rejecting symlinks at every level.

    Allowed base directory is controlled by ORION_VISION_DATA_DIR env var (defaults to 'data/vision/').
    Returns the file contents as bytes if safe, or raises ValueError if unsafe.
    """
    if not path or not isinstance(path, str):
        raise ValueError("Image path must be a non-empty string")

    base_dir_env = os.environ.get("ORION_VISION_DATA_DIR", "data/vision/")
    try:
        base_dir = Path(base_dir_env).resolve()
    except Exception as e:
        raise ValueError(f"Invalid vision base directory setting: {e}") from e

    # Luna Round 7 #6: Do NOT resolve symlinks before descriptor walk.
    # .resolve() follows symlinks, which defeats O_NOFOLLOW in the descriptor walk.
    # Instead, reject ".." components outright and validate containment via component analysis.
    try:
        p = Path(path)
    except Exception as e:
        raise ValueError(f"Invalid image path '{path}': {e}") from e

    # Reject absolute paths that don't start with base_dir
    if p.is_absolute():
        try:
            rel = p.relative_to(base_dir)
        except ValueError:
            raise ValueError(f"Access denied: absolute path '{path}' not under base directory '{base_dir}'")
        # Reject ".." components
        if ".." in rel.parts:
            raise ValueError(f"Access denied: path '{path}' contains '..' — directory traversal rejected")
        # Use rel components for the walk (no .resolve() to avoid following symlinks)
        walk_parts = list(rel.parts)
    else:
        # Relative path: reject ".." components, then walk from base_dir
        if ".." in p.parts:
            raise ValueError(f"Access denied: path '{path}' contains '..' — directory traversal rejected")
        walk_parts = list(p.parts)

    # Validate containment by checking that the resolved path is within base_dir
    # (only for validation, NOT for the descriptor walk)
    try:
        resolved = (base_dir / p).resolve()
        if not resolved.is_relative_to(base_dir):
            raise ValueError(f"Access denied: path '{path}' escapes allowed vision directory '{base_dir}'")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid image path '{path}': {e}") from e

    import errno

    # Change #9: Descriptor-based path traversal defense.
    # Walk from base_dir down to the target file, opening each component
    # relative to its parent directory fd. This is TOCTOU-safe because
    # each open is relative to a fixed directory descriptor that cannot
    # be replaced between check and use.
    # Luna Round 7 #6: Open parent first, then walk to base_dir with O_NOFOLLOW
    parent_fd = None
    dir_fd = None
    try:
        parent_fd = os.open(str(base_dir.parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        dir_fd = os.open(base_dir.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        os.close(parent_fd)
        parent_fd = None  # Already closed — don't double-close in except
    except OSError as e:
        for fd in (parent_fd, dir_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        raise ValueError(f"Cannot open base directory '{base_dir}': {e}") from e

    # Luna Round 7 #6: Use original (unresolved) components for O_NOFOLLOW walk
    components = walk_parts

    try:
        for i, component in enumerate(components):
            is_last = (i == len(components) - 1)
            flags = os.O_RDONLY | os.O_NOFOLLOW
            if not is_last:
                flags |= os.O_DIRECTORY  # Intermediate components must be directories

            try:
                next_fd = os.open(component, flags, dir_fd=dir_fd)
            except OSError as e:
                if e.errno == errno.ELOOP:
                    raise ValueError(
                        f"Access denied: path component '{component}' is a symlink "
                        f"(rejected by O_NOFOLLOW at component {i})"
                    ) from e
                if e.errno == errno.ENOTDIR:
                    raise ValueError(
                        f"Access denied: path component '{component}' is not a directory "
                        f"(expected directory at component {i})"
                    ) from e
                raise ValueError(f"Cannot open path component '{component}': {e}") from e

            # Close parent directory fd and move to the next level
            os.close(dir_fd)
            dir_fd = next_fd

        # dir_fd now points to the final file.
        # Luna Round 7 #6: Verify it's a regular file (not FIFO, device, etc.)
        import stat as _stat
        st = os.fstat(dir_fd)
        if not _stat.S_ISREG(st.st_mode):
            raise ValueError(
                f"Access denied: path is not a regular file (mode={oct(st.st_mode)}) "
                f"- special files rejected (Luna Round 7 #6)"
            )
        if st.st_size > 50 * 1024 * 1024:
            raise ValueError("Image file too large: maximum 50MB allowed (Luna Round 7 #6)")
        with os.fdopen(dir_fd, "rb") as f:
            data = f.read(50 * 1024 * 1024 + 1)  # Bounded read (Luna Round 8)
            if len(data) > 50 * 1024 * 1024:
                raise ValueError("Image file grew during read — exceeds 50MB limit (Luna Round 8)")
    except ValueError:
        try:
            os.close(dir_fd)
        except (OSError, UnboundLocalError):
            pass
        raise
    except Exception as e:
        try:
            os.close(dir_fd)
        except (OSError, UnboundLocalError):
            pass
        raise ValueError(f"Failed to read image file '{path}': {e}") from e

    return data


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
            # Validate URL scheme — only allow https:// and data: URLs
            url = request.image_url
            if not (url.startswith("https://") or url.startswith("data:image/")):
                raise ValueError("Unsafe image URL scheme rejected: only https:// and data:image/ allowed")

            # Vector #8: Validate data URL format and content
            if url.startswith("data:image/"):
                import re as _re
                # Check format: data:image/<type>;base64,<valid_base64>
                match = _re.match(
                    r'^data:image/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=]+)$',
                    url
                )
                if not match:
                    raise ValueError(
                        "Invalid data URL: must be data:image/<png|jpeg|jpg|gif|webp>;base64,<valid_base64>"
                    )
                # Limit size to 10MB to prevent memory exhaustion
                if len(url) > 10 * 1024 * 1024:
                    raise ValueError("Data URL too large: maximum 10MB allowed")

            # Data URLs are safe after validation — return directly
            if url.startswith("data:image/"):
                return url

            # Change #10: Controlled download with SSRF protection — no arbitrary URL passthrough.
            # Instead of passing HTTPS URLs to OpenAI (which would make OpenAI fetch them,
            # enabling SSRF via the API provider), we download locally with full IP validation,
            # then convert to base64 data URL. This ensures only safe, validated image bytes
            # reach the API.
            if url.startswith("https://"):
                import ipaddress
                import re as _re
                import socket
                import urllib.parse
                import urllib.request

                parsed = urllib.parse.urlparse(url)
                hostname = parsed.hostname
                if not hostname:
                    raise ValueError("Invalid URL: no hostname")

                # Check for direct IP addresses
                try:
                    ip = ipaddress.ip_address(hostname)
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                        raise ValueError(
                            f"SSRF protection: URL hostname '{hostname}' is internal/private — rejected"
                        )
                except ValueError as ve:
                    if "SSRF" in str(ve):
                        raise
                    # Not a direct IP — check for obvious internal hostnames
                    internal_patterns = [
                        r'^localhost$', r'^127\.', r'^10\.', r'^172\.(1[6-9]|2[0-9]|3[01])\.',
                        r'^192\.168\.', r'^169\.254\.', r'^0\.0\.0\.0$',
                    ]
                    for pattern in internal_patterns:
                        if _re.match(pattern, hostname, _re.IGNORECASE):
                            raise ValueError(
                                f"SSRF protection: URL hostname '{hostname}' matches internal pattern — rejected"
                            )
                    # DNS resolution to catch internal addresses
                    try:
                        addr_info = socket.getaddrinfo(hostname, None)
                        for _, _, _, _, sockaddr in addr_info:
                            resolved_ip = ipaddress.ip_address(sockaddr[0])
                            if resolved_ip.is_private or resolved_ip.is_loopback or resolved_ip.is_link_local or resolved_ip.is_unspecified or resolved_ip.is_reserved or resolved_ip.is_multicast:
                                raise ValueError(
                                    f"SSRF protection: URL hostname '{hostname}' resolves to "
                                    f"internal address {resolved_ip} — rejected"
                                )
                    except (socket.gaierror, ValueError) as dns_err:
                        if "SSRF" in str(dns_err):
                            raise
                        # Can't resolve — reject (fail-closed, don't pass to OpenAI)
                        raise ValueError(
                            f"SSRF protection: cannot resolve hostname '{hostname}' — rejected (fail-closed)"
                        )

                # Luna Round 7 #5: Disable redirects — no redirect following at all
                class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, req, fp, code, msg, headers, newurl):
                        raise ValueError(
                            f"SSRF protection: HTTP redirect to '{newurl}' blocked "
                            f"- redirects not allowed (Luna Round 7 #5)"
                        )

                # Download the image locally with SSRF-safe validation (no redirects)
                try:
                    opener = urllib.request.build_opener(NoRedirectHandler)
                    req = urllib.request.Request(url, headers={"User-Agent": "ORION-Vision/1.0"})
                    with opener.open(req, timeout=10) as resp:
                        content_type = resp.headers.get("Content-Type", "")
                        if not content_type.startswith("image/"):
                            raise ValueError(f"SSRF protection: URL returned non-image content type '{content_type}' — rejected")
                        image_bytes = resp.read(10 * 1024 * 1024)  # Max 10MB
                        if len(image_bytes) >= 10 * 1024 * 1024:
                            raise ValueError("Downloaded image too large: maximum 10MB allowed")
                except ValueError:
                    raise
                except Exception as e:
                    raise ValueError(f"Failed to download image from URL: {e}") from e

                # Convert to base64 data URL and return (no arbitrary URL passthrough to OpenAI)
                b64 = base64.b64encode(image_bytes).decode()
                return f"data:image/{content_type.split('/')[-1]};base64,{b64}"
        elif request.image_data:
            b64 = base64.b64encode(request.image_data).decode()
            return f"data:image/png;base64,{b64}"
        elif request.image_path:
            # validate_image_path returns bytes directly (TOCTOU-safe)
            image_data = validate_image_path(request.image_path)
            b64 = base64.b64encode(image_data).decode()
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
