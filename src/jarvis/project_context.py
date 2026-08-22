"""
ORION Phase 010 — Project Context Manager. License: Apache 2.0.

Maintains context across interactions: current project, state, and history.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProjectContextManager:
    """Manages project context and interaction history."""

    def __init__(self) -> None:
        self._context: Dict[str, Any] = {
            "current_project": None,
            "current_phase": None,
            "user_preferences": {},
            "active_tasks": [],
            "environment": "simulation",
        }
        self._history: List[Dict[str, Any]] = []
        self._max_history = 100

    def get_context(self) -> Dict[str, Any]:
        """Get the current project context."""
        return dict(self._context)

    def set_context(self, key: str, value: Any) -> None:
        """Set a context value."""
        self._context[key] = value
        logger.info("Context updated: %s", key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a specific context value."""
        return self._context.get(key, default)

    def delete(self, key: str) -> bool:
        """Delete a context value."""
        if key not in self._context:
            return False
        del self._context[key]
        return True

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the interaction history."""
        return list(self._history)

    def add_history(self, entry: Dict[str, Any]) -> None:
        """Add an entry to the interaction history."""
        entry = {**entry, "timestamp": time.time()}
        self._history.append(entry)
        # Trim history if too long
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def clear_history(self) -> int:
        """Clear interaction history. Returns count cleared."""
        count = len(self._history)
        self._history.clear()
        return count

    def get_recent_history(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent history entries."""
        return self._history[-count:] if count > 0 else []

    def search_history(self, query: str) -> List[Dict[str, Any]]:
        """Search interaction history for a query."""
        query_lower = query.lower()
        return [
            entry for entry in self._history
            if query_lower in str(entry).lower()
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context": dict(self._context),
            "history_count": len(self._history),
            "recent": self.get_recent_history(5),
        }
