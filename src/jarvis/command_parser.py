"""
ORION Phase 010 — Natural Language Command Parser. License: Apache 2.0.

Parses natural language into structured commands.
Classifies command types and extracts parameters.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommandType(str, Enum):
    """Types of commands ORION can process."""
    QUERY = "query"
    ACTION = "action"
    CREATE = "create"
    SEARCH = "search"
    ANALYZE = "analyze"
    PLAN = "plan"
    EXECUTE = "execute"
    STATUS = "status"
    NOTIFICATION = "notification"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    """Result of parsing a natural language command."""
    raw_text: str
    command_type: CommandType
    intent: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    subtasks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "command_type": self.command_type.value,
            "intent": self.intent,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "subtasks": self.subtasks,
        }


# Keyword patterns for command classification.
# Order matters: more specific types are checked first to win ties.
# Weight = pattern length (longer = more specific = higher score).
_CLASSIFICATION_PATTERNS: List[tuple[CommandType, List[str]]] = [
    # Specific types first
    (CommandType.STATUS, ["what is the status", "status report", "status", "progress", "state check"]),
    (CommandType.NOTIFICATION, ["notify", "alert", "remind", "warn me", "ping me"]),
    (CommandType.HELP, ["help me", "how do i", "explain how", "tutorial", "guide me"]),
    (CommandType.ANALYZE, ["analyze", "examine", "evaluate", "assess", "inspect", "diagnose"]),
    (CommandType.PLAN, ["plan", "prepare", "design a", "strategy", "roadmap", "schedule"]),
    (CommandType.SEARCH, ["search for", "find information", "look up", "lookup", "research"]),
    (CommandType.CREATE, ["create", "make a", "build a", "generate a", "set up", "new task", "add a"]),
    (CommandType.EXECUTE, ["execute", "implement", "deploy", "apply", "commit", "push"]),
    # Generic types last
    (CommandType.ACTION, ["run", "perform", "start", "stop", "restart", "update", "fix"]),
    (CommandType.QUERY, ["what", "who", "where", "when", "why", "how", "which", "is it", "are there", "does it", "can it"]),
]


class NLCommandParser:
    """Parses natural language into structured commands."""

    def __init__(self) -> None:
        self._parse_count = 0

    def parse(self, text: str) -> ParsedCommand:
        """Parse natural language text into a structured command."""
        self._parse_count += 1
        text_clean = text.strip()
        cmd_type = self.classify(text_clean)
        intent = self._extract_intent(text_clean, cmd_type)
        params = self._extract_parameters(text_clean, cmd_type)
        subtasks = self._extract_subtasks(text_clean)
        confidence = self._compute_confidence(text_clean, cmd_type)

        return ParsedCommand(
            raw_text=text_clean,
            command_type=cmd_type,
            intent=intent,
            parameters=params,
            confidence=confidence,
            subtasks=subtasks,
        )

    def classify(self, text: str) -> CommandType:
        """Classify the command type from text.

        Uses weighted scoring: longer pattern matches (more specific)
        contribute more weight. Specific types are checked first
        so they win ties against generic types.
        """
        text_lower = text.lower()

        best_type = CommandType.UNKNOWN
        best_score = 0.0

        for cmd_type, patterns in _CLASSIFICATION_PATTERNS:
            type_score = 0.0
            for p in patterns:
                if p in text_lower:
                    # Weight by pattern length — longer = more specific
                    type_score += len(p) / 10.0
            if type_score > best_score:
                best_score = type_score
                best_type = cmd_type

        return best_type

    def _extract_intent(self, text: str, cmd_type: CommandType) -> str:
        """Extract the intent/action from the text."""
        text_lower = text.lower()
        prefixes = ["please", "can you", "could you", "i want to", "i need to", "help me"]
        cleaned = text_lower
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        return cleaned[:100]

    def _extract_parameters(self, text: str, cmd_type: CommandType) -> Dict[str, Any]:
        """Extract parameters from the text."""
        params: Dict[str, Any] = {"original_text": text}

        quotes = re.findall(r'"([^"]*)"', text)
        if quotes:
            params["quoted_args"] = quotes

        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
        if numbers:
            params["numbers"] = [float(n) for n in numbers]

        paths = re.findall(r'[\w/]+\.\w+', text)
        if paths:
            params["file_paths"] = paths

        urls = re.findall(r'https?://[^\s]+', text)
        if urls:
            params["urls"] = urls

        return params

    def _extract_subtasks(self, text: str) -> List[str]:
        """Extract subtasks from compound commands."""
        parts = re.split(r'\b(?:and then|then|also|after that|additionally|furthermore)\b', text, flags=re.IGNORECASE)
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]
        return []

    def _compute_confidence(self, text: str, cmd_type: CommandType) -> float:
        """Compute confidence score for the classification."""
        if cmd_type == CommandType.UNKNOWN:
            return 0.3
        text_lower = text.lower()
        for ct, patterns in _CLASSIFICATION_PATTERNS:
            if ct == cmd_type:
                matches = sum(1 for p in patterns if p in text_lower)
                return min(0.5 + matches * 0.15, 0.95)
        return 0.5

    def get_statistics(self) -> Dict[str, Any]:
        return {"total_parses": self._parse_count}
