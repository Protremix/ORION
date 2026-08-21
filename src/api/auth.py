"""
ORION API Authentication — Basic bearer token auth + rate limiting.

License: Apache 2.0
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    max_requests: int = 100
    window_seconds: float = 60.0


@dataclass
class AuthConfig:
    """Authentication configuration."""
    enabled: bool = True
    api_key: Optional[str] = None
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    debug_mode: bool = False


class AuthManager:
    """
    Manages API authentication and rate limiting for ORION API.

    Authentication: Bearer token via ORION_API_KEY env var or explicit config.
    Rate limiting: Sliding window per-token.
    """

    def __init__(self, config: Optional[AuthConfig] = None) -> None:
        if config is None:
            env_key = os.environ.get("ORION_API_KEY")
            debug_mode = os.environ.get("ORION_DEBUG_MODE", "").lower() in ("1", "true", "yes")
            config = AuthConfig(
                enabled=True,
                api_key=env_key,
                debug_mode=debug_mode,
            )
        self._config = config
        self._request_times: dict[str, Deque[float]] = {}

    def authenticate(self, token: Optional[str]) -> bool:
        """Verify a bearer token. Returns True if authenticated."""
        if self._config.debug_mode:
            return True  # Explicit debug/test mode allows open access

        if not self._config.enabled:
            return False  # Fail-closed

        if not token or not self._config.api_key:
            return False  # Fail-closed if missing API key or token

        # Constant-time comparison to prevent timing attacks
        provided = hashlib.sha256(token.encode()).digest()
        expected = hashlib.sha256(self._config.api_key.encode()).digest()
        return hmac.compare_digest(provided, expected)

    def check_rate_limit(self, token: Optional[str] = None) -> bool:
        """Check if request is within rate limit. Returns True if allowed."""
        if self._config.debug_mode or not self._config.enabled:
            return True

        key = token or "anonymous"
        now = time.time()
        window = self._config.rate_limit.window_seconds
        max_req = self._config.rate_limit.max_requests

        if key not in self._request_times:
            self._request_times[key] = deque()

        times = self._request_times[key]

        # Remove expired entries
        while times and times[0] < now - window:
            times.popleft()

        if len(times) >= max_req:
            logger.warning(f"Rate limit exceeded for token: {key[:8]}...")
            return False

        times.append(now)
        return True

    def extract_token(self, auth_header: Optional[str]) -> Optional[str]:
        """Extract bearer token from Authorization header."""
        if not auth_header:
            return None
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        return None


# Global singleton for convenience
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get or create the global AuthManager singleton."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def set_auth_manager(manager: Optional[AuthManager]) -> None:
    """Set the global AuthManager (for testing)."""
    global _auth_manager
    _auth_manager = manager
