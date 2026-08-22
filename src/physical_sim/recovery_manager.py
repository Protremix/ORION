"""
ORION Phase 011 — Recovery Manager. License: Apache 2.0.

Handles recovery from failed simulated actions.
Provides strategies for error recovery in the physical simulation environment.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecoveryStrategy(str, Enum):
    RETRY = "retry"
    ALTERNATIVE_PATH = "alternative_path"
    RESET_POSITION = "reset_position"
    RECALIBRATE = "recalibrate"
    EMERGENCY_STOP = "emergency_stop"
    REQUEST_HELP = "request_help"


@dataclass
class RecoveryAction:
    """A recovery action to be executed."""
    strategy: RecoveryStrategy
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    estimated_time: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "description": self.description,
            "parameters": self.parameters,
            "estimated_time": self.estimated_time,
        }


# Error type → recommended strategy mapping
_ERROR_STRATEGY_MAP: Dict[str, RecoveryStrategy] = {
    "collision": RecoveryStrategy.RESET_POSITION,
    "timeout": RecoveryStrategy.RETRY,
    "out_of_bounds": RecoveryStrategy.RESET_POSITION,
    "low_battery": RecoveryStrategy.REQUEST_HELP,
    "joint_error": RecoveryStrategy.RECALIBRATE,
    "path_blocked": RecoveryStrategy.ALTERNATIVE_PATH,
    "gripper_failure": RecoveryStrategy.RECALIBRATE,
    "navigation_failure": RecoveryStrategy.ALTERNATIVE_PATH,
    "unknown": RecoveryStrategy.REQUEST_HELP,
}


class RecoveryManager:
    """Manages recovery from failed simulated actions."""

    def __init__(self) -> None:
        self._recovery_count = 0
        self._success_count = 0
        self._history: List[Dict[str, Any]] = []

    def recover(self, error: str, context: Optional[Dict[str, Any]] = None) -> RecoveryAction:
        """Generate a recovery action for an error."""
        self._recovery_count += 1
        ctx = context or {}

        strategy = _ERROR_STRATEGY_MAP.get(error, RecoveryStrategy.REQUEST_HELP)

        action = RecoveryAction(
            strategy=strategy,
            description=f"Recover from {error}",
            parameters={"error": error, "context": ctx},
        )

        self._history.append({
            "error": error,
            "strategy": strategy.value,
            "context": ctx,
        })

        logger.info("Recovery action: %s for error: %s", strategy.value, error)
        return action

    def execute_recovery(self, action: RecoveryAction,
                         simulator: Any = None) -> Dict[str, Any]:
        """Execute a recovery action."""
        if action.strategy == RecoveryStrategy.RESET_POSITION:
            if simulator and hasattr(simulator, "reset"):
                simulator.reset()
                self._success_count += 1
                return {"recovered": True, "action": "reset_position"}

        elif action.strategy == RecoveryStrategy.RETRY:
            self._success_count += 1
            return {"recovered": True, "action": "retry"}

        elif action.strategy == RecoveryStrategy.ALTERNATIVE_PATH:
            self._success_count += 1
            return {"recovered": True, "action": "alternative_path"}

        elif action.strategy == RecoveryStrategy.RECALIBRATE:
            if simulator and hasattr(simulator, "reset"):
                simulator.reset()
            self._success_count += 1
            return {"recovered": True, "action": "recalibrate"}

        elif action.strategy == RecoveryStrategy.EMERGENCY_STOP:
            return {"recovered": False, "action": "emergency_stop", "halted": True}

        elif action.strategy == RecoveryStrategy.REQUEST_HELP:
            return {"recovered": False, "action": "request_help", "needs_human": True}

        return {"recovered": False, "action": "unknown"}

    def get_strategies(self) -> List[str]:
        """Return available recovery strategies."""
        return [s.value for s in RecoveryStrategy]

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_recoveries": self._recovery_count,
            "successful_recoveries": self._success_count,
            "success_rate": self._success_count / max(1, self._recovery_count),
        }

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statistics": self.get_statistics(),
            "strategies": self.get_strategies(),
            "history_count": len(self._history),
        }
