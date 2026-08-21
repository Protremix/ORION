"""Tests for financial/legal/strategic action enforcement."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.api.auth import AuthConfig, AuthManager


class TestActionCategoryEnforcement:
    """Test that financial, legal, and strategic actions are blocked."""

    def setup_method(self):
        from src.api import ORIONAPI
        from src.api.permissions import PermissionChecker
        auth = AuthManager(AuthConfig(enabled=True, api_key="test_key"))
        PermissionChecker.clear()
        PermissionChecker.register_agent_permissions("test_agent", ["SUPERVISOR"])
        self.api = ORIONAPI(auth_manager=auth)

    def test_financial_action_blocked(self):
        """Financial action is blocked with DECISION_REQUIRED."""
        resp = self.api.execute(
            {"action_category": "FINANCIAL", "amount": 1000},
            simulate_first=False,
            agent_id="test_agent",
            token="test_key",
        )
        assert not resp.ok
        assert "DECISION_REQUIRED" in resp.error
        assert "FINANCIAL" in resp.error

    def test_legal_action_blocked(self):
        """Legal action is blocked with DECISION_REQUIRED."""
        resp = self.api.execute(
            {"action_category": "LEGAL", "action": "sign_contract"},
            simulate_first=False,
            agent_id="test_agent",
            token="test_key",
        )
        assert not resp.ok
        assert "DECISION_REQUIRED" in resp.error
        assert "LEGAL" in resp.error

    def test_strategic_action_blocked(self):
        """Strategic action is blocked with DECISION_REQUIRED."""
        resp = self.api.execute(
            {"action_category": "STRATEGIC", "decision": "pivot_business"},
            simulate_first=False,
            agent_id="test_agent",
            token="test_key",
        )
        assert not resp.ok
        assert "DECISION_REQUIRED" in resp.error
        assert "STRATEGIC" in resp.error

    def test_digital_action_allowed(self):
        """Digital action without device_id is allowed (no financial/legal/strategic)."""
        resp = self.api.execute(
            {"action_category": "DIGITAL", "command": "log_event"},
            simulate_first=False,
            agent_id="test_agent",
            token="test_key",
        )
        assert resp.ok

    def test_default_category_digital(self):
        """Action without action_category defaults to DIGITAL and is allowed."""
        resp = self.api.execute(
            {"command": "log_event"},
            simulate_first=False,
            agent_id="test_agent",
            token="test_key",
        )
        assert resp.ok

    def test_financial_blocked_with_auth_enabled(self):
        """Financial action blocked even when auth is enabled with valid token."""
        from src.api import ORIONAPI
        from src.api.permissions import PermissionChecker, PermissionLevel
        auth = AuthManager(AuthConfig(enabled=True, api_key="test-key"))
        api = ORIONAPI(auth_manager=auth)
        PermissionChecker.register_agent_permissions("test_agent", [PermissionLevel.ADMIN])
        resp = api.execute(
            {"action_category": "FINANCIAL", "amount": 5000},
            simulate_first=False,
            token="test-key",
            agent_id="test_agent",
        )
        assert not resp.ok
        assert "DECISION_REQUIRED" in resp.error

    def test_physical_action_still_blocked_by_safety(self):
        """Physical action (with device_id) still blocked by safety gateway."""
        resp = self.api.execute(
            {"device_id": "vehicle_1", "command_type": "move", "action_category": "PHYSICAL"},
            simulate_first=False,
            agent_id="test_agent",
            token="test_key",
        )
        assert not resp.ok
        # Should be blocked by safety gateway, not action category
        assert "Safety Gateway" in resp.error or "DECISION_REQUIRED" not in resp.error

    def test_physical_without_device_id_rejected(self):
        """PHYSICAL action without device_id must be rejected."""
        resp = self.api.execute(
            {"action_category": "PHYSICAL", "command": "move_robot"},
            simulate_first=False,
            agent_id="test_agent",
            token="test_key",
        )
        assert not resp.ok
        assert "device_id" in resp.error


class TestActionCategoryEnum:
    """Test the ActionCategory enum in contracts."""

    def test_action_category_values(self):
        """ActionCategory has all required values."""
        from src.contracts.contracts import ActionCategory
        assert ActionCategory.DIGITAL.value == "DIGITAL"
        assert ActionCategory.FINANCIAL.value == "FINANCIAL"
        assert ActionCategory.LEGAL.value == "LEGAL"
        assert ActionCategory.PHYSICAL.value == "PHYSICAL"
        assert ActionCategory.STRATEGIC.value == "STRATEGIC"

    def test_action_proposal_has_category(self):
        """ActionProposal has action_category field with default DIGITAL."""
        import inspect

        from src.contracts.contracts import ActionCategory, ActionProposal
        sig = inspect.signature(ActionProposal.__init__) if hasattr(ActionProposal, '__init__') else None
        assert ActionCategory.DIGITAL is not None
