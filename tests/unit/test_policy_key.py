"""Tests for policy signing key security."""

import os
import pytest
from unittest.mock import patch


class TestPolicyKeySecurity:
    """Test fallback signing key behavior."""

    def test_dev_mode_without_key_generates_ephemeral(self):
        """In dev mode without ORION_POLICY_KEY, an ephemeral key is generated with a warning."""
        with patch.dict(os.environ, {"ORION_ENV": ""}, clear=False):
            os.environ.pop("ORION_POLICY_KEY", None)
            os.environ.pop("ORION_POLICY_SECRET_KEY", None)
            os.environ.pop("ORION_ENV", None)
            from src.config.policy_manager import PolicyManager
            pm = PolicyManager()
            # Should have a generated key (hex string, 64 chars)
            assert len(pm.secret_key) >= 64
            assert pm.secret_key != "orion_phase1_safety_key_change_in_production"

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

    def test_production_mode_without_key_raises(self):
        """In production mode (ORION_ENV=production) without key, raises ValueError."""
        with patch.dict(os.environ, {"ORION_ENV": "production"}, clear=False):
            os.environ.pop("ORION_POLICY_KEY", None)
            os.environ.pop("ORION_POLICY_SECRET_KEY", None)
            from src.config.policy_manager import PolicyManager
            with pytest.raises(ValueError, match="ORION_POLICY_KEY"):
                PolicyManager()

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
            assert pm.secret_key != "orion_phase1_safety_key_change_in_production"
            assert "change_in_production" not in pm.secret_key
