"""
ORION Phase 008 — Simulated Document Adapter. License: Apache 2.0.

Document understanding: text extraction, summarization, Q&A.
Simulation mode — operates on text content provided in input data.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.api import ModelDescriptor, ModelType

logger = logging.getLogger(__name__)


class SimulatedDocumentAdapter:
    """Simulated document adapter for text extraction, summarization, and Q&A."""

    def __init__(self) -> None:
        self._call_count = 0
        self._total_latency = 0.0

    def get_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            model_id="simulated-document",
            name="Simulated Document",
            model_type=ModelType.LLM,
            version="1.0.0",
            provider="ORION-sim",
        )

    def extract_text(self, document_data: Dict[str, Any]) -> str:
        """Extract text from a document."""
        start = time.time()
        self._call_count += 1

        text = document_data.get("text", document_data.get("content", document_data.get("body", "")))

        elapsed = (time.time() - start) * 1000
        self._total_latency += elapsed

        return text or "No text content found in document."

    def summarize(self, text: str, max_length: int = 200) -> str:
        """Summarize text."""
        start = time.time()
        self._call_count += 1

        if not text or len(text) <= max_length:
            result = text
        else:
            sentences = text.split(". ")
            summary_parts: List[str] = []
            current_len = 0
            for s in sentences:
                if current_len + len(s) > max_length:
                    break
                summary_parts.append(s)
                current_len += len(s) + 2
            result = ". ".join(summary_parts) if summary_parts else text[:max_length]

        elapsed = (time.time() - start) * 1000
        self._total_latency += elapsed
        return result

    def answer_question(self, text: str, question: str) -> str:
        """Answer a question based on document text."""
        start = time.time()
        self._call_count += 1

        question_lower = question.lower()
        question_words = [w for w in question_lower.split()
                         if len(w) > 3 and w not in ("what", "where", "when", "which", "does", "this", "that")]
        relevant_sentences: List[str] = []
        for sentence in text.split(". "):
            sentence_lower = sentence.lower()
            if any(word in sentence_lower for word in question_words):
                relevant_sentences.append(sentence)

        elapsed = (time.time() - start) * 1000
        self._total_latency += elapsed

        if relevant_sentences:
            return ". ".join(relevant_sentences[:2])
        return f"Based on the document: no direct answer found for '{question}'."

    def classify_document(self, document_data: Dict[str, Any]) -> str:
        """Classify document type."""
        self._call_count += 1
        doc_type = document_data.get("type", "unknown")
        if doc_type != "unknown":
            return doc_type
        text = document_data.get("text", "")
        if any(kw in text.lower() for kw in ["invoice", "payment", "amount"]):
            return "invoice"
        if any(kw in text.lower() for kw in ["report", "analysis", "summary"]):
            return "report"
        if any(kw in text.lower() for kw in ["contract", "agreement", "party"]):
            return "contract"
        return "general"

    def health_check(self) -> bool:
        return True

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "avg_latency_ms": self._total_latency / max(1, self._call_count),
        }
