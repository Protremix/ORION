"""
Tests for ORION API Authentication.

License: Apache 2.0
"""

import os
import time
import pytest
from src.api.auth import AuthManager, AuthConfig, RateLimitConfig


class TestAuthManager:
    """Test authentication manager."""

    def test_auth_disabled_allows_all(self):
        """When auth is disabled, all requests pass."""
        auth = AuthManager(AuthConfig(enabled=False))
        assert auth.authenticate(None) is True
        assert auth.authenticate("anything") is True

    def test_auth_enabled_requires_token(self):
        """When auth is enabled, missing token is rejected."""
        auth = AuthManager(AuthConfig(enabled=True, api_key="secret123"))
        assert auth.authenticate(None) is False
        assert auth.authenticate("") is False

    def test_auth_valid_token(self):
        """Valid token passes authentication."""
        auth = AuthManager(AuthConfig(enabled=True, api_key="secret123"))
        assert auth.authenticate("secret123") is True

    def test_auth_invalid_token(self):
        """Invalid token is rejected."""
        auth = AuthManager(AuthConfig(enabled=True, api_key="secret123"))
        assert auth.authenticate("wrong") is False
        assert auth.authenticate("secret1234") is False

    def test_auth_no_key_configured(self):
        """Auth enabled but no key configured — rejects all."""
        auth = AuthManager(AuthConfig(enabled=True, api_key=None))
        assert auth.authenticate("anything") is False

    def test_extract_bearer_token(self):
        """Extract token from Bearer header."""
        auth = AuthManager(AuthConfig(enabled=False))
        assert auth.extract_token("Bearer abc123") == "abc123"
        assert auth.extract_token("Bearer  ") == ""
        assert auth.extract_token("abc123") is None
        assert auth.extract_token(None) is None

    def test_env_var_auto_enable(self):
        """AuthManager auto-enables when ORION_API_KEY is set."""
        old = os.environ.get("ORION_API_KEY")
        try:
            os.environ["ORION_API_KEY"] = "env-secret"
            auth = AuthManager()
            assert auth._config.enabled is True
            assert auth.authenticate("env-secret") is True
            assert auth.authenticate("wrong") is False
        finally:
            if old is not None:
                os.environ["ORION_API_KEY"] = old
            else:
                os.environ.pop("ORION_API_KEY", None)


class TestRateLimiting:
    """Test rate limiting."""

    def test_rate_limit_allows_within_limit(self):
        """Requests within limit are allowed."""
        auth = AuthManager(AuthConfig(
            enabled=True,
            api_key="key",
            rate_limit=RateLimitConfig(max_requests=5, window_seconds=60),
        ))
        for _ in range(5):
            assert auth.check_rate_limit("key") is True

    def test_rate_limit_blocks_over_limit(self):
        """Requests over limit are blocked."""
        auth = AuthManager(AuthConfig(
            enabled=True,
            api_key="key",
            rate_limit=RateLimitConfig(max_requests=3, window_seconds=60),
        ))
        for _ in range(3):
            assert auth.check_rate_limit("key") is True
        assert auth.check_rate_limit("key") is False

    def test_rate_limit_disabled(self):
        """Rate limiting disabled when auth is off."""
        auth = AuthManager(AuthConfig(enabled=False))
        for _ in range(100):
            assert auth.check_rate_limit() is True

    def test_rate_limit_window_expiry(self):
        """Rate limit resets after window expires."""
        auth = AuthManager(AuthConfig(
            enabled=True,
            api_key="key",
            rate_limit=RateLimitConfig(max_requests=2, window_seconds=0.1),
        ))
        assert auth.check_rate_limit("key") is True
        assert auth.check_rate_limit("key") is True
        assert auth.check_rate_limit("key") is False
        time.sleep(0.15)
        assert auth.check_rate_limit("key") is True

    def test_rate_limit_per_token(self):
        """Rate limit is per-token."""
        auth = AuthManager(AuthConfig(
            enabled=True,
            api_key="key",
            rate_limit=RateLimitConfig(max_requests=2, window_seconds=60),
        ))
        assert auth.check_rate_limit("token1") is True
        assert auth.check_rate_limit("token1") is True
        assert auth.check_rate_limit("token1") is False
        # Different token has its own limit
        assert auth.check_rate_limit("token2") is True


class TestAPIWithAuth:
    """Test ORION API with authentication."""

    def test_api_works_without_auth_enabled(self):
        """API works when auth is disabled (dev mode)."""
        from src.api import ORIONAPI, ORIONStatus
        auth = AuthManager(AuthConfig(enabled=False))
        api = ORIONAPI(auth_manager=auth)
        result = api.observe("test", {"q": 1})
        assert result.ok is True

    def test_api_rejects_unauthorized(self):
        """API rejects requests when auth fails."""
        from src.api import ORIONAPI, ORIONStatus
        auth = AuthManager(AuthConfig(enabled=True, api_key="secret"))
        api = ORIONAPI(auth_manager=auth)
        # Without token — should be rejected
        check = api._check_auth(None)
        assert check.status == ORIONStatus.UNAUTHORIZED

    def test_api_accepts_valid_token(self):
        """API accepts requests with valid token."""
        from src.api import ORIONAPI, ORIONStatus
        auth = AuthManager(AuthConfig(enabled=True, api_key="secret"))
        api = ORIONAPI(auth_manager=auth)
        check = api._check_auth("secret")
        assert check.ok is True
