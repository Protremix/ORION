"""
ORION Core Model Gateway — Phase 004. License: Apache 2.0
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

class ModelProvider(Protocol):
    def generate(self, prompt: str, system_prompt: str = "", max_tokens: int = 2000, temperature: float = 0.3) -> str: ...
    @property
    def model_name(self) -> str: ...

@dataclass
class ModelInfo:
    name: str
    provider: str
    endpoint: str
    quantization: Optional[str] = None
    context_window: int = 4096
    safety_score: float = 0.0
    latency_p95_ms: float = 0.0
    qualified: bool = False
    version: str = "1.0.0"

@dataclass
class ModelResponse:
    text: str
    model: str
    latency_ms: float
    success: bool
    parsed: Optional[Any] = None
    error: Optional[str] = None

    def parse_json(self) -> Optional[Any]:
        if self.parsed is not None:
            return self.parsed
        try:

            return json.loads(self.text.strip())
        except json.JSONDecodeError:

            pass
        text = self.text.strip()
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = text.find(start_char)
            end = text.rfind(end_char) + 1
            if start >= 0 and end > start:
                try:

                    return json.loads(text[start:end])
                except json.JSONDecodeError:

                    pass
        return None

class ModelGateway:
    def __init__(self) -> None:
        self._models: Dict[str, ModelInfo] = {}
        self._providers: Dict[str, ModelProvider] = {}
        self._default_model: Optional[str] = None
        self._fallback_order: List[str] = []

    def register_model(self, info: ModelInfo, provider: ModelProvider) -> bool:
        if not info.qualified:
            logger.warning(f"Cannot register unqualified model: {info.name}")
            return False
        self._models[info.name] = info
        self._providers[info.name] = provider
        if not self._default_model:
            self._default_model = info.name
        if info.name not in self._fallback_order:
            self._fallback_order.append(info.name)
        logger.info(f"Registered model: {info.name} (provider={info.provider})")
        return True

    def set_default(self, model_name: str) -> bool:
        if model_name not in self._models:
            return False
        self._default_model = model_name
        return True

    def set_fallback_order(self, order: List[str]) -> None:
        self._fallback_order = [m for m in order if m in self._models]

    def generate(self, prompt: str, system_prompt: str = "", max_tokens: int = 2000,
                 temperature: float = 0.3, model: Optional[str] = None,
                 expect_json: bool = False) -> ModelResponse:
        target = model or self._default_model
        if not target:
            return ModelResponse(text="", model="none", latency_ms=0, success=False, error="No models registered")
        order = [target] + [m for m in self._fallback_order if m != target]
        last_error = None
        for model_name in order:
            provider = self._providers.get(model_name)
            if not provider:
                continue
            start = time.time()
            try:
                text = provider.generate(prompt=prompt, system_prompt=system_prompt,
                    max_tokens=max_tokens, temperature=temperature)
                latency_ms = (time.time()-start)*1000
                response = ModelResponse(text=text, model=model_name, latency_ms=latency_ms, success=True)
                if expect_json:
                    response.parsed = response.parse_json()
                    if response.parsed is None:
                        response.error = "Failed to parse JSON"
                        logger.warning(f"Model {model_name}: JSON parse failed")
                return response
            except Exception as e:
                latency_ms = (time.time()-start)*1000
                last_error = str(e)
                logger.warning(f"Model {model_name} failed: {e} - trying fallback")
                continue
        return ModelResponse(text="", model=target, latency_ms=0, success=False, error=last_error or "All models failed")

    def generate_plan(self, goal: str, available_tools: List[str], model: Optional[str] = None) -> ModelResponse:
        prompt = f"""You are ORION's planning module. Decompose the following goal into a structured execution plan.

Goal: {goal}
Available tools: {", ".join(available_tools)}

Return a JSON object with:
{{"steps": [{{"description": "what to do", "action_type": "tool name", "parameters": {{}}, "dependencies": []}}]}}

Return ONLY valid JSON, no prose."""
        return self.generate(prompt, system_prompt="You are ORION's planning module.",
                             max_tokens=2000, temperature=0.3, model=model, expect_json=True)

    def list_models(self) -> List[ModelInfo]:
        return list(self._models.values())

    def get_model_info(self, name: str) -> Optional[ModelInfo]:
        return self._models.get(name)

    def to_dict(self) -> dict:
        return {"default_model": self._default_model, "fallback_order": self._fallback_order,
                "models": {n: {"name": i.name, "provider": i.provider, "qualified": i.qualified,
                               "safety_score": i.safety_score, "latency_p95_ms": i.latency_p95_ms}
                           for n, i in self._models.items()}, "model_count":
                               len(self._models)}
