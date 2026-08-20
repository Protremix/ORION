"""Tests for persistent permission registry."""

import os
import tempfile
import pytest
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.api.permissions import PermissionChecker, PermissionLevel


class TestPermissionPersistence:
    """Test that permissions persist across restarts."""

    def setup_method(self):
        """Set up with a temporary SQLite database."""
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_permissions.db")
        PermissionChecker.clear()
        PermissionChecker.set_storage_path(self.db_path)

    def teardown_method(self):
        """Clean up."""
        PermissionChecker.clear()
        PermissionChecker._storage_path = None
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_allow_registered_agent(self):
        """Registered agent with correct permissions is ALLOWED."""
        PermissionChecker.register_agent_permissions("agent_1", [PermissionLevel.READ])
        assert PermissionChecker.check_permission("agent_1", "query_memory") is True

    def test_deny_unregistered_agent(self):
        """Unregistered agent is DENIED (deny-by-default)."""
        assert PermissionChecker.check_permission("unknown_agent", "query_memory") is False

    def test_deny_insufficient_permission(self):
        """Agent with READ only is DENIED for WRITE actions."""
        PermissionChecker.register_agent_permissions("agent_2", [PermissionLevel.READ])
        assert PermissionChecker.check_permission("agent_2", "store_memory") is False

    def test_restart_persists_permissions(self):
        """Permissions survive a restart (simulated by clearing in-memory and reloading)."""
        # Register and persist
        PermissionChecker.register_agent_permissions("agent_3", [PermissionLevel.WRITE])
        assert PermissionChecker.check_permission("agent_3", "store_memory") is True

        # Simulate restart: clear in-memory registry, but DON'T clear storage
        PermissionChecker._registry.clear()
        assert PermissionChecker.check_permission("agent_3", "store_memory") is False  # Lost in memory

        # Reload from storage
        PermissionChecker.load_from_storage()
        assert PermissionChecker.check_permission("agent_3", "store_memory") is True  # Restored!

    def test_reload_preserves_permissions(self):
        """Reload from storage restores all previously saved permissions."""
        PermissionChecker.register_agent_permissions("agent_a", [PermissionLevel.READ])
        PermissionChecker.register_agent_permissions("agent_b", [PermissionLevel.ADMIN])
        PermissionChecker.register_agent_permissions("agent_c", [PermissionLevel.SUPERVISOR])

        # Clear and reload
        PermissionChecker._registry.clear()
        PermissionChecker.load_from_storage()

        assert PermissionChecker.check_permission("agent_a", "query_memory") is True
        assert PermissionChecker.check_permission("agent_b", "deploy_model") is True
        assert PermissionChecker.check_permission("agent_c", "override_safety") is True

    def test_unauthorized_access_after_reload(self):
        """Agent not in storage is still denied after reload."""
        PermissionChecker.register_agent_permissions("agent_4", [PermissionLevel.READ])
        PermissionChecker._registry.clear()
        PermissionChecker.load_from_storage()

        # agent_4 exists in storage
        assert PermissionChecker.check_permission("agent_4", "query_memory") is True
        # unknown agent does not
        assert PermissionChecker.check_permission("agent_5", "query_memory") is False

    def test_no_silent_escalation(self):
        """Agent with READ permission cannot access WRITE/ADMIN/SUPERVISOR actions."""
        PermissionChecker.register_agent_permissions("agent_6", [PermissionLevel.READ])
        assert PermissionChecker.check_permission("agent_6", "query_memory") is True  # READ OK
        assert PermissionChecker.check_permission("agent_6", "store_memory") is False  # WRITE denied
        assert PermissionChecker.check_permission("agent_6", "deploy_model") is False  # ADMIN denied
        assert PermissionChecker.check_permission("agent_6", "override_safety") is False  # SUPERVISOR denied

    def test_register_and_persist_method(self):
        """register_and_persist explicitly saves to storage."""
        result = PermissionChecker.register_and_persist("agent_7", [PermissionLevel.ADMIN])
        assert result is True
        # Clear and reload
        PermissionChecker._registry.clear()
        PermissionChecker.load_from_storage()
        assert PermissionChecker.check_permission("agent_7", "deploy_model") is True

    def test_no_storage_path_returns_false(self):
        """Without storage path configured, save/load return False."""
        PermissionChecker._storage_path = None
        assert PermissionChecker.save_to_storage() is False
        assert PermissionChecker.load_from_storage() is False

    def test_empty_agent_id_denied(self):
        """Empty or None agent_id is denied."""
        assert PermissionChecker.check_permission("", "query_memory") is False
        assert PermissionChecker.check_permission(None, "query_memory") is False
