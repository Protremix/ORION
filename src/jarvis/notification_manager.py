"""
ORION Phase 010 — Notification Manager. License: Apache 2.0.

Sends alerts, reminders, and status updates.
Tracks read/unread state and notification levels.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    CRITICAL = "critical"


@dataclass
class Notification:
    """A notification in the JARVIS system."""
    id: str
    message: str
    level: NotificationLevel = NotificationLevel.INFO
    timestamp: float = field(default_factory=time.time)
    read: bool = False
    source: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "level": self.level.value,
            "timestamp": self.timestamp,
            "read": self.read,
            "source": self.source,
            "metadata": self.metadata,
        }


class NotificationManager:
    """Manages notifications for the JARVIS interface."""

    def __init__(self) -> None:
        self._notifications: Dict[str, Notification] = {}
        self._counter = 0

    def notify(self, message: str, level: str = "info",
               source: str = "system",
               metadata: Optional[Dict[str, Any]] = None) -> str:
        """Send a notification. Returns the notification ID."""
        self._counter += 1
        notif_id = f"notif_{self._counter}"
        notif = Notification(
            id=notif_id,
            message=message,
            level=NotificationLevel(level),
            source=source,
            metadata=metadata or {},
        )
        self._notifications[notif_id] = notif
        logger.info("Notification [%s]: %s", level, message)
        return notif_id

    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        """Get notifications, optionally only unread."""
        if unread_only:
            return [n for n in self._notifications.values() if not n.read]
        return list(self._notifications.values())

    def get_notification(self, notif_id: str) -> Optional[Notification]:
        """Get a specific notification."""
        return self._notifications.get(notif_id)

    def mark_read(self, notif_id: str) -> bool:
        """Mark a notification as read."""
        notif = self._notifications.get(notif_id)
        if not notif:
            return False
        notif.read = True
        return True

    def mark_all_read(self) -> int:
        """Mark all notifications as read. Returns count."""
        count = 0
        for notif in self._notifications.values():
            if not notif.read:
                notif.read = True
                count += 1
        return count

    def clear(self) -> int:
        """Clear all notifications. Returns count cleared."""
        count = len(self._notifications)
        self._notifications.clear()
        return count

    def unread_count(self) -> int:
        """Get count of unread notifications."""
        return sum(1 for n in self._notifications.values() if not n.read)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": len(self._notifications),
            "unread": self.unread_count(),
            "notifications": [n.to_dict() for n in self._notifications.values()],
        }
