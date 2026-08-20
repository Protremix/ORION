"""
ORION API Permissions — Agent Permission Enforcement (Security P2).

Provides permission level definitions, permission mappings, and
permission checking for agent operations and API endpoints.

License: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    """Permission levels in ORION, ordered by increasing privilege."""
    READ = "READ"
    WRITE = "WRITE"
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"


_LEVEL_RANKS: Dict[PermissionLevel, int] = {
    PermissionLevel.READ: 1,
    PermissionLevel.WRITE: 2,
    PermissionLevel.ADMIN: 3,
    PermissionLevel.SUPERVISOR: 4,
}


def _get_level_rank(level: Union[PermissionLevel, str]) -> int:
    """Get the numerical rank for a permission level."""
    if isinstance(level, PermissionLevel):
        return _LEVEL_RANKS.get(level, 0)
    if isinstance(level, str):
        level_str = level.upper().strip()
        if level_str in PermissionLevel.__members__:
            return _LEVEL_RANKS[PermissionLevel[level_str]]
    return 0


class Permission:
    """
    Maps actions and endpoints to required permission levels.
    """

    # Default action to permission level mappings
    DEFAULT_MAPPINGS: Dict[str, PermissionLevel] = {
        # READ
        "query_memory": PermissionLevel.READ,
        "query_audit": PermissionLevel.READ,
        "get_world_state": PermissionLevel.READ,
        "get_belief_state": PermissionLevel.READ,
        "health_check": PermissionLevel.READ,
        "observe": PermissionLevel.READ,
        "recall": PermissionLevel.READ,

        # WRITE
        "store_memory": PermissionLevel.WRITE,
        "update_world_state": PermissionLevel.WRITE,
        "propose_action": PermissionLevel.WRITE,
        "log_audit": PermissionLevel.WRITE,
        "remember": PermissionLevel.WRITE,
        "plan": PermissionLevel.WRITE,
        "simulate": PermissionLevel.WRITE,
        "execute": PermissionLevel.WRITE,

        # ADMIN
        "create_agent": PermissionLevel.ADMIN,
        "delete_agent": PermissionLevel.ADMIN,
        "modify_permissions": PermissionLevel.ADMIN,
        "deploy_model": PermissionLevel.ADMIN,

        # SUPERVISOR
        "approve_action": PermissionLevel.SUPERVISOR,
        "override_safety": PermissionLevel.SUPERVISOR,
        "shutdown_system": PermissionLevel.SUPERVISOR,
        "modify_config": PermissionLevel.SUPERVISOR,
        "emergency_stop": PermissionLevel.SUPERVISOR,
    }

    # Endpoint to permission level mappings
    ENDPOINT_MAPPINGS: Dict[str, PermissionLevel] = {
        # READ endpoints
        "/api/v1/memory/query": PermissionLevel.READ,
        "/api/v1/audit/query": PermissionLevel.READ,
        "/api/v1/world_state": PermissionLevel.READ,
        "/api/v1/belief_state": PermissionLevel.READ,
        "/api/v1/health": PermissionLevel.READ,

        # WRITE endpoints
        "/api/v1/memory/store": PermissionLevel.WRITE,
        "/api/v1/world_state/update": PermissionLevel.WRITE,
        "/api/v1/action/propose": PermissionLevel.WRITE,
        "/api/v1/audit/log": PermissionLevel.WRITE,

        # ADMIN endpoints
        "/api/v1/agents/create": PermissionLevel.ADMIN,
        "/api/v1/agents/delete": PermissionLevel.ADMIN,
        "/api/v1/permissions/modify": PermissionLevel.ADMIN,
        "/api/v1/models/deploy": PermissionLevel.ADMIN,

        # SUPERVISOR endpoints
        "/api/v1/action/approve": PermissionLevel.SUPERVISOR,
        "/api/v1/safety/override": PermissionLevel.SUPERVISOR,
        "/api/v1/system/shutdown": PermissionLevel.SUPERVISOR,
        "/api/v1/config/modify": PermissionLevel.SUPERVISOR,
    }

    def __init__(self, action: str, required_level: Union[PermissionLevel, str]):
        self.action = action
        if isinstance(required_level, str):
            req_str = required_level.upper().strip()
            if req_str in PermissionLevel.__members__:
                self.required_level = PermissionLevel[req_str]
            else:
                raise ValueError(f"Invalid permission level: {required_level}")
        else:
            self.required_level = required_level

    @classmethod
    def get_required_level(cls, action: str) -> Optional[PermissionLevel]:
        """Get the required permission level for an action."""
        if not action or not isinstance(action, str):
            return None
        action_clean = action.lower().strip()
        return cls.DEFAULT_MAPPINGS.get(action_clean)

    @classmethod
    def get_endpoint_level(cls, endpoint: str) -> Optional[PermissionLevel]:
        """Get the required permission level for an API endpoint."""
        if not endpoint or not isinstance(endpoint, str):
            return None
        ep = endpoint.strip()
        if ep in cls.ENDPOINT_MAPPINGS:
            return cls.ENDPOINT_MAPPINGS[ep]
        if ep in cls.DEFAULT_MAPPINGS:
            return cls.DEFAULT_MAPPINGS[ep]
        ep_no_slash = ep.rstrip("/")
        if ep_no_slash in cls.ENDPOINT_MAPPINGS:
            return cls.ENDPOINT_MAPPINGS[ep_no_slash]
        for path, level in cls.ENDPOINT_MAPPINGS.items():
            if ep.endswith(path) or path.endswith(ep):
                return level
        for action, level in cls.DEFAULT_MAPPINGS.items():
            if action in ep.lower():
                return level
        return None


class PermissionChecker:
    """
    Enforces agent permissions across ORION API actions and endpoints.
    Denies access by default for unregistered agents or unmapped actions.
    """

    _registry: Dict[str, List[Union[PermissionLevel, str]]] = {}

    def __init__(self, registry: Optional[Dict[str, List[Union[PermissionLevel, str]]]] = None) -> None:
        if registry is not None:
            self._custom_registry = registry
        else:
            self._custom_registry = None

    @property
    def registry(self) -> Dict[str, List[Union[PermissionLevel, str]]]:
        if self._custom_registry is not None:
            return self._custom_registry
        return PermissionChecker._registry

    @classmethod
    def register_agent_permissions(
        cls,
        agent_id_or_descriptor: Union[str, Any],
        permissions: Optional[Union[List[Any], Set[Any], Tuple[Any, ...], Any]] = None,
    ) -> None:
        """Register permissions for an agent."""
        if agent_id_or_descriptor is None:
            return

        if hasattr(agent_id_or_descriptor, "agent_id") and hasattr(agent_id_or_descriptor, "permissions"):
            agent_id = agent_id_or_descriptor.agent_id
            perms = agent_id_or_descriptor.permissions if permissions is None else permissions
        else:
            agent_id = str(agent_id_or_descriptor)
            perms = permissions if permissions is not None else []

        if not agent_id:
            return

        if isinstance(perms, (set, tuple)):
            perms_list = list(perms)
        elif isinstance(perms, list):
            perms_list = list(perms)
        elif perms is not None:
            perms_list = [perms]
        else:
            perms_list = []

        cls._registry[agent_id] = perms_list
        # Auto-persist if storage is configured
        if cls._storage_path is not None:
            cls.save_to_storage()

    @classmethod
    def get_agent_permissions(cls, agent_id: Optional[str]) -> List[Union[PermissionLevel, str]]:
        """Get registered permissions for an agent. Returns empty list if unregistered."""
        if not agent_id or not isinstance(agent_id, str):
            return []
        return cls._registry.get(agent_id, [])

    @classmethod
    def check_permission(
        cls,
        agent_id: Optional[str],
        action: Union[str, PermissionLevel],
        resource: Optional[str] = None,
    ) -> bool:
        """
        Check if an agent has permission to perform an action on a resource.

        Returns True if authorized, False otherwise (deny by default).
        """
        if not agent_id or not isinstance(agent_id, str):
            return False

        if action is None:
            return False

        agent_perms = cls.get_agent_permissions(agent_id)
        if not agent_perms:
            return False

        required_level: Optional[PermissionLevel] = None
        action_name: Optional[str] = None

        if isinstance(action, PermissionLevel):
            required_level = action
        elif isinstance(action, str):
            action_name = action.strip()
            if not action_name:
                return False
            if action_name.upper() in PermissionLevel.__members__:
                required_level = PermissionLevel[action_name.upper()]
            else:
                required_level = Permission.get_required_level(action_name)

        # Check explicit permissions and level hierarchy
        for perm in agent_perms:
            # 1. Exact string match for action name
            if action_name and isinstance(perm, str) and perm.lower() == action_name.lower():
                return True

            # 2. Wildcard or full supervisor permission
            if isinstance(perm, str) and perm.strip() in ("*", "ALL"):
                return True

            # 3. Level hierarchy rank check
            if required_level is not None:
                agent_rank = _get_level_rank(perm)
                required_rank = _get_level_rank(required_level)
                if agent_rank > 0 and required_rank > 0 and agent_rank >= required_rank:
                    return True

        return False

    @classmethod
    def check_api_access(cls, agent_id: Optional[str], endpoint: Optional[str]) -> bool:
        """
        Check if an agent has permission to access an API endpoint.

        Returns True if authorized, False otherwise (deny by default).
        """
        if not agent_id or not isinstance(agent_id, str):
            return False

        if not endpoint or not isinstance(endpoint, str):
            return False

        required_level = Permission.get_endpoint_level(endpoint)
        if required_level is None:
            return cls.check_permission(agent_id, endpoint)

        return cls.check_permission(agent_id, required_level)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered permissions (for testing)."""
        cls._registry.clear()

    # --- Persistence ---

    _storage_path: Optional[str] = None

    @classmethod
    def set_storage_path(cls, path: str) -> None:
        """Set the SQLite storage path for permission persistence."""
        cls._storage_path = path
        # Auto-load on set
        cls.load_from_storage()

    @classmethod
    def save_to_storage(cls) -> bool:
        """Persist current permission registry to SQLite. Returns True on success."""
        if cls._storage_path is None:
            return False
        try:
            conn = sqlite3.connect(cls._storage_path)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS permissions (
                    agent_id TEXT PRIMARY KEY,
                    permissions_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            ''')
            for agent_id, perms in cls._registry.items():
                perms_serialized = json.dumps([
                    p.value if isinstance(p, PermissionLevel) else str(p) for p in perms
                ])
                conn.execute(
                    'INSERT OR REPLACE INTO permissions (agent_id, permissions_json, updated_at) VALUES (?, ?, ?)',
                    (agent_id, perms_serialized, time.time())
                )
            # Also store audit log entry
            conn.execute('''
                CREATE TABLE IF NOT EXISTS permission_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    agent_id TEXT,
                    details TEXT,
                    timestamp REAL NOT NULL
                )
            ''')
            conn.execute(
                'INSERT INTO permission_audit_log (event_type, agent_id, details, timestamp) VALUES (?, ?, ?, ?)',
                ('SAVE', None, json.dumps({'count': len(cls._registry)}), time.time())
            )
            conn.commit()
            conn.close()
            logger.info(f"Persisted {len(cls._registry)} agent permissions to {cls._storage_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to persist permissions: {e}")
            return False

    @classmethod
    def load_from_storage(cls) -> bool:
        """Load permission registry from SQLite. Returns True on success."""
        if cls._storage_path is None:
            return False
        if not os.path.exists(cls._storage_path):
            return False
        try:
            conn = sqlite3.connect(cls._storage_path)
            cursor = conn.execute('SELECT agent_id, permissions_json FROM permissions')
            loaded = 0
            for agent_id, perms_json in cursor:
                perms_list = json.loads(perms_json)
                # Reconstruct PermissionLevel objects where possible
                restored = []
                for p in perms_list:
                    if p in PermissionLevel.__members__:
                        restored.append(PermissionLevel[p])
                    else:
                        restored.append(p)
                cls._registry[agent_id] = restored
                loaded += 1
            conn.close()
            logger.info(f"Loaded {loaded} agent permissions from {cls._storage_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load permissions: {e}")
            return False

    @classmethod
    def register_and_persist(cls, agent_id: str, permissions: List) -> bool:
        """Register agent permissions and persist to storage."""
        cls.register_agent_permissions(agent_id, permissions)
        return cls.save_to_storage()


# Global singleton instance
_permission_checker: Optional[PermissionChecker] = None


def get_permission_checker() -> PermissionChecker:
    """Get global PermissionChecker instance."""
    global _permission_checker
    if _permission_checker is None:
        _permission_checker = PermissionChecker()
    return _permission_checker
