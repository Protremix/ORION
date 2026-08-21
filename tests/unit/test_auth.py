"""
Tests for ORION API Authentication.

License: Apache 2.0
"""

import os
import time

import pytest

from src.api.auth import AuthConfig, AuthManager, RateLimitConfig


@pytest.fixture(autouse=True)
def _disable_debug_mode():
    """Disable debug mode for auth tests — we need to test real auth behavior."""
    old = os.environ.get("ORION_DEBUG_MODE")
    os.environ.pop("ORION_DEBUG_MODE", None)
    yield
    if old is not None:
        os.environ["ORION_DEBUG_MODE"] = old


class TestAuthManager:
    """Test authentication manager."""

    def test_auth_disabled_denies_all(self):
        """When auth is disabled, all requests are denied (fail-closed)."""
        auth = AuthManager(AuthConfig(enabled=False))
        assert auth.authenticate(None) is False
        assert auth.authenticate("anything") is False

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
        """Rate limiting fail-closed when auth is off."""
        auth = AuthManager(AuthConfig(enabled=False))
        # Auth disabled = fail-closed, rate limit denied
        assert auth.check_rate_limit() is False

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

    def test_api_fail_closed_when_disabled(self):
        """API denies requests when auth is disabled (fail-closed)."""
        from src.api import ORIONAPI, ORIONStatus
        auth = AuthManager(AuthConfig(enabled=False))
        api = ORIONAPI(auth_manager=auth)
        result = api.observe("test", {"q": 1}, agent_id="test")
        assert result.ok is False

    def test_api_debug_mode_does_not_bypass_auth(self):
        """Debug mode must NOT bypass authentication."""
        from src.api import ORIONAPI, ORIONStatus
        from src.api.permissions import PermissionChecker, PermissionLevel
        PermissionChecker.clear()
        PermissionChecker.register_agent_permissions("test", [PermissionLevel.SUPERVISOR])
        auth = AuthManager(AuthConfig(enabled=True, api_key="test", debug_mode=True))
        api = ORIONAPI(auth_manager=auth)
        # Without token, even debug mode must deny
        result = api.observe("test", {"q": 1}, agent_id="test")
        assert result.ok is False
        # With valid token, works normally
        result = api.observe("test", {"q": 1}, agent_id="test", token="test")
        assert result.ok is True

    def test_api_rejects_unauthorized(self):
        """API rejects requests when auth fails."""
        from src.api import ORIONAPI, ORIONStatus
        auth = AuthManager(AuthConfig(enabled=True, api_key="secret"))
        api = ORIONAPI(auth_manager=auth)
        # Without token — should be rejected
        check = api._check_auth(None, agent_id="test")
        assert check.status == ORIONStatus.UNAUTHORIZED

    def test_api_accepts_valid_token(self):
        """API accepts requests with valid token."""
        from src.api import ORIONAPI, ORIONStatus
        auth = AuthManager(AuthConfig(enabled=True, api_key="secret"))
        api = ORIONAPI(auth_manager=auth)
        check = api._check_auth("secret", agent_id="test")
        assert check.ok is True


class TestORIONAPIAuthEnforcement:
    """Test that ORIONAPI public methods enforce authentication when enabled."""

    def setup_method(self):
        """Set up auth-enabled API."""
        from src.api import ORIONAPI
        from src.api.auth import AuthConfig, AuthManager
        self.auth = AuthManager(AuthConfig(enabled=True, api_key="test-secret-key"))
        self.api = ORIONAPI(auth_manager=self.auth)
        # Register test agent with permissions for valid-token tests
        from src.api.permissions import PermissionChecker, PermissionLevel
        PermissionChecker.clear()
        PermissionChecker.register_agent_permissions("test", [PermissionLevel.ADMIN])

    def teardown_method(self):
        os.environ.pop("ORION_API_KEY", None)

    def test_observe_requires_auth(self):
        """Observe without token returns UNAUTHORIZED when auth enabled."""
        resp = self.api.observe("sim", {"type": "grid"})
        assert not resp.ok
        assert "Invalid or missing API key" in resp.error

    def test_get_world_state_requires_auth(self):
        """Get world state without token returns UNAUTHORIZED when auth enabled."""
        resp = self.api.get_world_state()
        assert not resp.ok

    def test_recall_requires_auth(self):
        """Recall without token returns UNAUTHORIZED when auth enabled."""
        resp = self.api.recall("test query")
        assert not resp.ok

    def test_remember_requires_auth(self):
        """Remember without token returns UNAUTHORIZED when auth enabled."""
        resp = self.api.remember({"event": "test"})
        assert not resp.ok

    def test_plan_requires_auth(self):
        """Plan without token returns UNAUTHORIZED when auth enabled."""
        resp = self.api.plan("move robot")
        assert not resp.ok

    def test_simulate_requires_auth(self):
        """Simulate without token returns UNAUTHORIZED when auth enabled."""
        resp = self.api.simulate({"command": "move"})
        assert not resp.ok

    def test_execute_requires_auth(self):
        """Execute without token returns UNAUTHORIZED when auth enabled."""
        resp = self.api.execute({"command": "move"}, simulate_first=False)
        assert not resp.ok

    def test_observe_with_valid_token(self):
        """Observe with valid token succeeds when auth enabled."""
        resp = self.api.observe("sim", {"type": "grid"}, token="test-secret-key", agent_id="test")
        assert resp.ok
