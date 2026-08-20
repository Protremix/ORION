"""
Unit tests for Agent Permission Enforcement (Security P2).

License: Apache 2.0
"""

import pytest
from src.api.permissions import (
    PermissionLevel,
    Permission,
    PermissionChecker,
    _get_level_rank,
)
from src.api import AgentDescriptor, AgentRole


@pytest.fixture(autouse=True)
def cleanup_permissions():
    """Clear registered permissions before and after each test."""
    PermissionChecker.clear()
    yield
    PermissionChecker.clear()


# ============================================================================
# PermissionLevel & Helper Tests
# ============================================================================

def test_permission_level_enum_values():
    assert PermissionLevel.READ == "READ"
    assert PermissionLevel.WRITE == "WRITE"
    assert PermissionLevel.ADMIN == "ADMIN"
    assert PermissionLevel.SUPERVISOR == "SUPERVISOR"


def test_permission_level_ranks():
    assert _get_level_rank(PermissionLevel.READ) == 1
    assert _get_level_rank(PermissionLevel.WRITE) == 2
    assert _get_level_rank(PermissionLevel.ADMIN) == 3
    assert _get_level_rank(PermissionLevel.SUPERVISOR) == 4
    assert _get_level_rank("read") == 1
    assert _get_level_rank("WRITE") == 2
    assert _get_level_rank("invalid") == 0


# ============================================================================
# Permission Class Tests
# ============================================================================

def test_permission_class_default_mappings():
    # READ
    assert Permission.DEFAULT_MAPPINGS["query_memory"] == PermissionLevel.READ
    assert Permission.DEFAULT_MAPPINGS["query_audit"] == PermissionLevel.READ
    assert Permission.DEFAULT_MAPPINGS["get_world_state"] == PermissionLevel.READ
    assert Permission.DEFAULT_MAPPINGS["get_belief_state"] == PermissionLevel.READ
    assert Permission.DEFAULT_MAPPINGS["health_check"] == PermissionLevel.READ

    # WRITE
    assert Permission.DEFAULT_MAPPINGS["store_memory"] == PermissionLevel.WRITE
    assert Permission.DEFAULT_MAPPINGS["update_world_state"] == PermissionLevel.WRITE
    assert Permission.DEFAULT_MAPPINGS["propose_action"] == PermissionLevel.WRITE
    assert Permission.DEFAULT_MAPPINGS["log_audit"] == PermissionLevel.WRITE

    # ADMIN
    assert Permission.DEFAULT_MAPPINGS["create_agent"] == PermissionLevel.ADMIN
    assert Permission.DEFAULT_MAPPINGS["delete_agent"] == PermissionLevel.ADMIN
    assert Permission.DEFAULT_MAPPINGS["modify_permissions"] == PermissionLevel.ADMIN
    assert Permission.DEFAULT_MAPPINGS["deploy_model"] == PermissionLevel.ADMIN

    # SUPERVISOR
    assert Permission.DEFAULT_MAPPINGS["approve_action"] == PermissionLevel.SUPERVISOR
    assert Permission.DEFAULT_MAPPINGS["override_safety"] == PermissionLevel.SUPERVISOR
    assert Permission.DEFAULT_MAPPINGS["shutdown_system"] == PermissionLevel.SUPERVISOR
    assert Permission.DEFAULT_MAPPINGS["modify_config"] == PermissionLevel.SUPERVISOR


def test_permission_class_init():
    p1 = Permission("query_memory", PermissionLevel.READ)
    assert p1.action == "query_memory"
    assert p1.required_level == PermissionLevel.READ

    p2 = Permission("store_memory", "WRITE")
    assert p2.required_level == PermissionLevel.WRITE

    with pytest.raises(ValueError):
        Permission("bad_action", "INVALID_LEVEL")


def test_permission_get_required_level():
    assert Permission.get_required_level("query_memory") == PermissionLevel.READ
    assert Permission.get_required_level("STORE_MEMORY") == PermissionLevel.WRITE
    assert Permission.get_required_level("create_agent") == PermissionLevel.ADMIN
    assert Permission.get_required_level("shutdown_system") == PermissionLevel.SUPERVISOR
    assert Permission.get_required_level("non_existent_action") is None
    assert Permission.get_required_level(None) is None


def test_permission_get_endpoint_level():
    assert Permission.get_endpoint_level("/api/v1/memory/query") == PermissionLevel.READ
    assert Permission.get_endpoint_level("/api/v1/memory/store") == PermissionLevel.WRITE
    assert Permission.get_endpoint_level("/api/v1/agents/create") == PermissionLevel.ADMIN
    assert Permission.get_endpoint_level("/api/v1/system/shutdown") == PermissionLevel.SUPERVISOR
    assert Permission.get_endpoint_level("/api/v1/unknown") is None
    assert Permission.get_endpoint_level(None) is None


# ============================================================================
# Permission Registration & Lookup Tests
# ============================================================================

def test_permission_registration_and_lookup():
    checker = PermissionChecker()
    checker.register_agent_permissions("agent_01", [PermissionLevel.READ, PermissionLevel.WRITE])
    perms = checker.get_agent_permissions("agent_01")
    assert PermissionLevel.READ in perms
    assert PermissionLevel.WRITE in perms


def test_permission_registration_via_descriptor():
    desc = AgentDescriptor(
        agent_id="agent_desc_1",
        name="Research Agent",
        role=AgentRole.RESEARCH,
        permissions=["READ", "query_memory"],
    )
    PermissionChecker.register_agent_permissions(desc)
    perms = PermissionChecker.get_agent_permissions("agent_desc_1")
    assert "READ" in perms
    assert "query_memory" in perms


def test_unregistered_agent_returns_empty_and_denies():
    perms = PermissionChecker.get_agent_permissions("unknown_agent")
    assert perms == []
    assert PermissionChecker.check_permission("unknown_agent", "query_memory") is False
    assert PermissionChecker.check_api_access("unknown_agent", "/api/v1/memory/query") is False


def test_clear_permissions():
    PermissionChecker.register_agent_permissions("a1", [PermissionLevel.READ])
    assert PermissionChecker.get_agent_permissions("a1") == [PermissionLevel.READ]
    PermissionChecker.clear()
    assert PermissionChecker.get_agent_permissions("a1") == []


# ============================================================================
# Permission Level Action Enforcement Tests
# ============================================================================

def test_read_level_allows_read_actions_denies_higher():
    PermissionChecker.register_agent_permissions("read_agent", [PermissionLevel.READ])

    # READ actions allowed
    read_actions = ["query_memory", "query_audit", "get_world_state", "get_belief_state", "health_check"]
    for action in read_actions:
        assert PermissionChecker.check_permission("read_agent", action) is True, f"Failed for {action}"

    # Higher actions denied
    higher_actions = ["store_memory", "update_world_state", "create_agent", "shutdown_system"]
    for action in higher_actions:
        assert PermissionChecker.check_permission("read_agent", action) is False, f"Should deny {action}"


def test_write_level_allows_read_and_write_denies_higher():
    PermissionChecker.register_agent_permissions("write_agent", [PermissionLevel.WRITE])

    # READ and WRITE allowed
    allowed = ["query_memory", "get_world_state", "store_memory", "update_world_state", "propose_action", "log_audit"]
    for action in allowed:
        assert PermissionChecker.check_permission("write_agent", action) is True, f"Failed for {action}"

    # ADMIN and SUPERVISOR denied
    denied = ["create_agent", "delete_agent", "modify_permissions", "deploy_model", "approve_action", "shutdown_system"]
    for action in denied:
        assert PermissionChecker.check_permission("write_agent", action) is False, f"Should deny {action}"


def test_admin_level_allows_read_write_admin_denies_supervisor():
    PermissionChecker.register_agent_permissions("admin_agent", [PermissionLevel.ADMIN])

    # READ, WRITE, ADMIN allowed
    allowed = ["query_memory", "store_memory", "create_agent", "delete_agent", "modify_permissions", "deploy_model"]
    for action in allowed:
        assert PermissionChecker.check_permission("admin_agent", action) is True, f"Failed for {action}"

    # SUPERVISOR denied
    denied = ["approve_action", "override_safety", "shutdown_system", "modify_config"]
    for action in denied:
        assert PermissionChecker.check_permission("admin_agent", action) is False, f"Should deny {action}"


def test_supervisor_level_allows_all_actions():
    PermissionChecker.register_agent_permissions("supervisor_agent", [PermissionLevel.SUPERVISOR])

    all_actions = [
        "query_memory", "get_world_state", "store_memory", "propose_action",
        "create_agent", "deploy_model", "approve_action", "override_safety",
        "shutdown_system", "modify_config"
    ]
    for action in all_actions:
        assert PermissionChecker.check_permission("supervisor_agent", action) is True, f"Failed for {action}"


# ============================================================================
# API Access Checks
# ============================================================================

def test_api_access_checks():
    PermissionChecker.register_agent_permissions("reader", [PermissionLevel.READ])
    PermissionChecker.register_agent_permissions("writer", [PermissionLevel.WRITE])
    PermissionChecker.register_agent_permissions("admin", [PermissionLevel.ADMIN])
    PermissionChecker.register_agent_permissions("super", [PermissionLevel.SUPERVISOR])

    # READ endpoint
    read_ep = "/api/v1/memory/query"
    assert PermissionChecker.check_api_access("reader", read_ep) is True
    assert PermissionChecker.check_api_access("writer", read_ep) is True
    assert PermissionChecker.check_api_access("admin", read_ep) is True
    assert PermissionChecker.check_api_access("super", read_ep) is True

    # WRITE endpoint
    write_ep = "/api/v1/memory/store"
    assert PermissionChecker.check_api_access("reader", write_ep) is False
    assert PermissionChecker.check_api_access("writer", write_ep) is True
    assert PermissionChecker.check_api_access("admin", write_ep) is True
    assert PermissionChecker.check_api_access("super", write_ep) is True

    # ADMIN endpoint
    admin_ep = "/api/v1/agents/create"
    assert PermissionChecker.check_api_access("reader", admin_ep) is False
    assert PermissionChecker.check_api_access("writer", admin_ep) is False
    assert PermissionChecker.check_api_access("admin", admin_ep) is True
    assert PermissionChecker.check_api_access("super", admin_ep) is True

    # SUPERVISOR endpoint
    super_ep = "/api/v1/system/shutdown"
    assert PermissionChecker.check_api_access("reader", super_ep) is False
    assert PermissionChecker.check_api_access("writer", super_ep) is False
    assert PermissionChecker.check_api_access("admin", super_ep) is False
    assert PermissionChecker.check_api_access("super", super_ep) is True


# ============================================================================
# Explicit Action & Edge Case Tests
# ============================================================================

def test_explicit_action_permissions():
    # Grant ONLY query_memory permission
    PermissionChecker.register_agent_permissions("custom_agent", ["query_memory"])

    assert PermissionChecker.check_permission("custom_agent", "query_memory") is True
    # Other READ actions denied because level READ was not granted
    assert PermissionChecker.check_permission("custom_agent", "query_audit") is False
    assert PermissionChecker.check_permission("custom_agent", "store_memory") is False


def test_edge_cases_invalid_inputs():
    PermissionChecker.register_agent_permissions("valid_agent", [PermissionLevel.READ])

    # None / Empty agent_id
    assert PermissionChecker.check_permission(None, "query_memory") is False
    assert PermissionChecker.check_permission("", "query_memory") is False
    assert PermissionChecker.check_api_access(None, "/api/v1/health") is False
    assert PermissionChecker.check_api_access("", "/api/v1/health") is False

    # None / Empty action or endpoint
    assert PermissionChecker.check_permission("valid_agent", None) is False
    assert PermissionChecker.check_permission("valid_agent", "") is False
    assert PermissionChecker.check_api_access("valid_agent", None) is False
    assert PermissionChecker.check_api_access("valid_agent", "") is False

    # Unknown action
    assert PermissionChecker.check_permission("valid_agent", "unknown_action_xyz") is False


def test_case_insensitive_permission_strings():
    PermissionChecker.register_agent_permissions("str_agent", ["read", "Write"])

    assert PermissionChecker.check_permission("str_agent", "query_memory") is True
    assert PermissionChecker.check_permission("str_agent", "store_memory") is True
    assert PermissionChecker.check_permission("str_agent", "create_agent") is False


def test_wildcard_permissions():
    PermissionChecker.register_agent_permissions("god_agent", ["*"])

    assert PermissionChecker.check_permission("god_agent", "query_memory") is True
    assert PermissionChecker.check_permission("god_agent", "shutdown_system") is True
    assert PermissionChecker.check_api_access("god_agent", "/api/v1/system/shutdown") is True
