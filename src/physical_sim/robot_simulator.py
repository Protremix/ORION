"""
ORION Phase 011 — Robot Simulator. License: Apache 2.0.

Simulates robot locomotion, manipulation, and navigation in a virtual environment.
Simplified physics: position, velocity, joint angles, gripper state.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RobotSimulator:
    """Simulates a robot with locomotion, manipulation, and navigation."""

    def __init__(self, initial_position: Optional[List[float]] = None) -> None:
        self._position: List[float] = initial_position or [0.0, 0.0, 0.0]
        self._velocity: List[float] = [0.0, 0.0, 0.0]
        self._orientation: float = 0.0  # radians
        self._joints: Dict[str, float] = {
            "arm_base": 0.0,
            "elbow": 0.0,
            "wrist": 0.0,
            "gripper": 0.0,  # 0 = open, 1 = closed
        }
        self._gripper_holding: Optional[str] = None
        self._step_count = 0
        self._battery = 100.0  # percentage
        self._collision: bool = False
        self._obstacles: List[Dict[str, Any]] = []
        self._target: Optional[List[float]] = None

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one simulation step with the given action."""
        self._step_count += 1
        action_type = action.get("type", "idle")
        self._battery = max(0.0, self._battery - 0.1)

        if action_type == "move":
            self._move(action.get("direction", [0, 0, 0]), action.get("speed", 1.0))
        elif action_type == "rotate":
            self._rotate(action.get("angle", 0.0))
        elif action_type == "move_joints":
            self._move_joints(action.get("joints", {}))
        elif action_type == "gripper":
            self._operate_gripper(action.get("action", "open"))
        elif action_type == "navigate_to":
            self._navigate(action.get("target", [0, 0, 0]))
        elif action_type == "pick":
            self._pick(action.get("object", "unknown"))
        elif action_type == "place":
            self._place(action.get("location", [0, 0, 0]))
        elif action_type == "idle":
            pass

        # Check collisions
        self._check_collisions()

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        """Return current robot state."""
        return {
            "position": list(self._position),
            "velocity": list(self._velocity),
            "orientation": self._orientation,
            "joints": dict(self._joints),
            "gripper_holding": self._gripper_holding,
            "battery": self._battery,
            "collision": self._collision,
            "step_count": self._step_count,
            "at_target": self._at_target() if self._target else False,
        }

    def reset(self, initial_position: Optional[List[float]] = None) -> None:
        """Reset the robot to initial state."""
        self._position = initial_position or [0.0, 0.0, 0.0]
        self._velocity = [0.0, 0.0, 0.0]
        self._orientation = 0.0
        self._joints = {"arm_base": 0.0, "elbow": 0.0, "wrist": 0.0, "gripper": 0.0}
        self._gripper_holding = None
        self._step_count = 0
        self._battery = 100.0
        self._collision = False
        self._target = None

    def set_obstacles(self, obstacles: List[Dict[str, Any]]) -> None:
        """Set obstacles in the environment."""
        self._obstacles = obstacles

    def set_target(self, target: List[float]) -> None:
        """Set navigation target."""
        self._target = target

    def _move(self, direction: List[float], speed: float) -> None:
        """Move in a direction at given speed."""
        for i in range(min(3, len(direction))):
            self._velocity[i] = direction[i] * speed
            self._position[i] += self._velocity[i] * 0.1  # dt=0.1s

    def _rotate(self, angle: float) -> None:
        """Rotate by a given angle."""
        self._orientation += angle

    def _move_joints(self, joint_updates: Dict[str, float]) -> None:
        """Update joint angles."""
        for joint, angle in joint_updates.items():
            if joint in self._joints:
                self._joints[joint] = angle

    def _operate_gripper(self, action: str) -> None:
        """Open or close gripper."""
        if action == "open":
            self._joints["gripper"] = 0.0
            self._gripper_holding = None
        elif action == "close":
            self._joints["gripper"] = 1.0

    def _navigate(self, target: List[float]) -> None:
        """Navigate toward a target position."""
        self._target = target
        dx = target[0] - self._position[0]
        dy = target[1] - self._position[1]
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0.01:
            self._orientation = math.atan2(dy, dx)
            speed = min(1.0, dist)
            self._move([dx / dist, dy / dist, 0], speed)
        else:
            self._velocity = [0.0, 0.0, 0.0]

    def _pick(self, obj: str) -> None:
        """Pick up an object."""
        self._operate_gripper("close")
        self._gripper_holding = obj

    def _place(self, location: List[float]) -> None:
        """Place the held object at a location."""
        if self._gripper_holding:
            self._operate_gripper("open")
            self._gripper_holding = None

    def _check_collisions(self) -> None:
        """Check for collisions with obstacles."""
        self._collision = False
        for obs in self._obstacles:
            ox, oy = obs.get("position", [0, 0])[:2]
            radius = obs.get("radius", 0.5)
            dist = math.sqrt(
                (self._position[0] - ox) ** 2 + (self._position[1] - oy) ** 2
            )
            if dist < radius:
                self._collision = True
                break

    def _at_target(self) -> bool:
        """Check if robot has reached the target."""
        if not self._target:
            return False
        dist = math.sqrt(
            (self._position[0] - self._target[0]) ** 2
            + (self._position[1] - self._target[1]) ** 2
        )
        return dist < 0.1

    def to_dict(self) -> Dict[str, Any]:
        return self.get_state()
