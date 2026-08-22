"""
ORION Phase 010 — Computer Interface. License: Apache 2.0.

File operations, command execution, and web browsing (simulation mode).
Provides a safe, simulated interface for computer interaction.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ComputerInterface:
    """Simulated computer interface for file ops, commands, and browsing."""

    def __init__(self) -> None:
        self._files: Dict[str, str] = {}
        self._command_history: List[Dict[str, Any]] = []
        self._browse_history: List[Dict[str, Any]] = []

    def read_file(self, path: str) -> str:
        """Read a file (simulated)."""
        if path in self._files:
            return self._files[path]
        # Simulate reading from a virtual filesystem
        return f"# Simulated content of {path}\n# File exists in virtual filesystem.\n"

    def write_file(self, path: str, content: str) -> bool:
        """Write to a file (simulated)."""
        self._files[path] = content
        logger.info("Wrote file: %s (%d bytes)", path, len(content))
        return True

    def list_files(self, directory: str = "/") -> Dict[str, Any]:
        """List files in a directory (simulated)."""
        matching = [p for p in self._files if p.startswith(directory)]
        return {"directory": directory, "files": matching, "count": len(matching)}

    def delete_file(self, path: str) -> bool:
        """Delete a file (simulated)."""
        if path not in self._files:
            return False
        del self._files[path]
        return True

    def execute_command(self, command: str, timeout: float = 30.0) -> Dict[str, Any]:
        """Execute a shell command (simulated)."""
        start = time.time()
        result = {
            "command": command,
            "exit_code": 0,
            "stdout": f"Simulated output for: {command}",
            "stderr": "",
            "duration_ms": (time.time() - start) * 1000,
            "success": True,
        }
        self._command_history.append(result)
        return result

    def browse(self, url: str) -> Dict[str, Any]:
        """Browse a URL (simulated)."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
        result = {
            "url": url,
            "status_code": 200,
            "title": f"Simulated page for {url}",
            "content_summary": f"Simulated web content from {url}. Hash: {url_hash}",
            "links_found": 3,
            "success": True,
        }
        self._browse_history.append(result)
        return result

    def get_file_count(self) -> int:
        return len(self._files)

    def get_command_history(self) -> List[Dict[str, Any]]:
        return list(self._command_history)

    def get_browse_history(self) -> List[Dict[str, Any]]:
        return list(self._browse_history)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_count": len(self._files),
            "files": list(self._files.keys()),
            "commands_executed": len(self._command_history),
            "pages_browsed": len(self._browse_history),
        }


# Need List import
from typing import List  # noqa: E402
