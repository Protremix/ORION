"""Tests for policy signing key security."""

import os
from unittest.mock import patch

import pytest


class TestPolicyKeySecurity:
    """Test policy signing key security — fail-closed when no key provided."""

    def test_dev_mode_without_key_is_fail_closed(self):
        """In dev mode without ORION_POLICY_KEY, secret_key is None (fail-closed)."""
        with patch.dict(os.environ, {}, clear=True):
            from src.config.policy_manager import PolicyManager
            pm = PolicyManager()
            # Fail-closed: no key means all actions denied
            assert pm.secret_key is None

    def test_with_explicit_key_uses_provided(self):
        """When ORION_POLICY_KEY is set, it uses the provided key."""
        with patch.dict(os.environ, {"ORION_POLICY_KEY": "my-secret-key-123456"}):
            from src.config.policy_manager import PolicyManager
            pm = PolicyManager()
            assert pm.secret_key == "my-secret-key-123456"

    def test_with_constructor_key_overrides_env(self):
        """Constructor key takes precedence over env var."""
        with patch.dict(os.environ, {"ORION_POLICY_KEY": "env-key"}):
            from src.config.policy_manager import PolicyManager
            pm = PolicyManager(secret_key="constructor-key")
            assert pm.secret_key == "constructor-key"

    def test_production_mode_without_key_is_fail_closed(self):
        """In production mode without key, secret_key is None (fail-closed, not ValueError)."""
        with patch.dict(os.environ, {"ORION_ENV": "production"}, clear=True):
            from src.config.policy_manager import PolicyManager
            pm = PolicyManager()
            # Fail-closed in production too — no key = no actions
            assert pm.secret_key is None

    def test_production_mode_with_key_works(self):
        """In production mode with ORION_POLICY_KEY set, works correctly."""
        with patch.dict(os.environ, {"ORION_ENV": "production", "ORION_POLICY_KEY": "prod-key-123456"}):
            from src.config.policy_manager import PolicyManager
            pm = PolicyManager()
            assert pm.secret_key == "prod-key-123456"

    def test_no_hardcoded_fallback_key(self):
        """Verify the old hardcoded key is not used."""
        with patch.dict(os.environ, {}, clear=True):
            from src.config.policy_manager import PolicyManager
            pm = PolicyManager()
            # secret_key is None, so hardcoded key cannot be present
            assert pm.secret_key != "orion_phase1_safety_key_change_in_production"
            if pm.secret_key is not None:
                assert "change_in_production" not in pm.secret_key
