"""
ORION Phase 011 — Predefined Physical Tasks. License: Apache 2.0.

Predefined simulated physical tasks for all 5 domains.
Each task has success criteria and measurable outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SimTask:
    """A predefined simulated physical task."""
    task_id: str
    domain: str
    description: str
    initial_state: Dict[str, Any] = field(default_factory=dict)
    goal_state: Dict[str, Any] = field(default_factory=dict)
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    max_steps: int = 50
    obstacles: List[Dict[str, Any]] = field(default_factory=list)
    safety_constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "domain": self.domain,
            "description": self.description,
            "initial_state": self.initial_state,
            "goal_state": self.goal_state,
            "success_criteria": self.success_criteria,
            "max_steps": self.max_steps,
            "obstacles": self.obstacles,
            "safety_constraints": self.safety_constraints,
        }


@dataclass
class TaskResult:
    """Result of executing a simulated physical task."""
    task_id: str
    domain: str
    success: bool = False
    steps_taken: int = 0
    final_state: Dict[str, Any] = field(default_factory=dict)
    success_rate: float = 0.0
    errors: List[str] = field(default_factory=list)
    recovery_actions: List[Dict[str, Any]] = field(default_factory=list)
    safety_violations: List[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "domain": self.domain,
            "success": self.success,
            "steps_taken": self.steps_taken,
            "final_state": self.final_state,
            "success_rate": self.success_rate,
            "errors": self.errors,
            "recovery_actions": self.recovery_actions,
            "safety_violations": self.safety_violations,
            "latency_ms": self.latency_ms,
        }


# ============================================================================
# Predefined Tasks
# ============================================================================

def _all_tasks() -> List[SimTask]:
    """Return all predefined tasks."""
    return [
        # Home domain
        SimTask(
            task_id="home_navigate_room",
            domain="home",
            description="Navigate from living room to kitchen",
            initial_state={"position": [0, 0, 0], "room": "living_room"},
            goal_state={"room": "kitchen", "position_reached": True},
            success_criteria={"position_reached": True},
            max_steps=20,
            safety_constraints=["no_collision", "speed_limit"],
        ),
        SimTask(
            task_id="home_pick_object",
            domain="home",
            description="Pick up a cup from the table",
            initial_state={"position": [0, 0, 0], "gripper_empty": True},
            goal_state={"gripper_holding": "cup"},
            success_criteria={"object_picked": True},
            max_steps=15,
            safety_constraints=["gentle_grip", "no_drop"],
        ),
        # Vehicle domain
        SimTask(
            task_id="vehicle_navigate_road",
            domain="vehicle",
            description="Navigate vehicle from point A to point B on road",
            initial_state={"position": [0, 0, 0], "speed": 0},
            goal_state={"position": [100, 0, 0], "speed": 0},
            success_criteria={"destination_reached": True},
            max_steps=30,
            obstacles=[{"position": [50, 0, 0], "radius": 2.0}],
            safety_constraints=["speed_limit", "lane_keeping", "no_collision"],
        ),
        SimTask(
            task_id="vehicle_avoid_obstacle",
            domain="vehicle",
            description="Navigate vehicle avoiding an obstacle",
            initial_state={"position": [0, 0, 0], "speed": 5.0},
            goal_state={"position": [100, 0, 0]},
            success_criteria={"destination_reached": True, "no_collision": True},
            max_steps=30,
            obstacles=[{"position": [50, 0, 0], "radius": 3.0}],
            safety_constraints=["no_collision"],
        ),
        # Robot domain
        SimTask(
            task_id="robot_navigate_warehouse",
            domain="robot",
            description="Robot navigates warehouse to reach target shelf",
            initial_state={"position": [0, 0, 0], "battery": 100},
            goal_state={"position": [10, 5, 0]},
            success_criteria={"target_reached": True},
            max_steps=25,
            obstacles=[{"position": [5, 2, 0], "radius": 1.0}],
            safety_constraints=["no_collision", "battery_reserve"],
        ),
        SimTask(
            task_id="robot_pick_and_place",
            domain="robot",
            description="Robot picks up a box and places it on a shelf",
            initial_state={"position": [0, 0, 0], "gripper_empty": True},
            goal_state={"box_placed": True, "position": [5, 5, 0]},
            success_criteria={"object_placed": True},
            max_steps=30,
            safety_constraints=["no_drop", "gentle_placement"],
        ),
        # Drone domain
        SimTask(
            task_id="drone_fly_to_target",
            domain="drone",
            description="Drone flies from ground to target altitude and position",
            initial_state={"position": [0, 0, 0], "altitude": 0},
            goal_state={"position": [10, 10, 20], "altitude": 20},
            success_criteria={"target_reached": True},
            max_steps=25,
            safety_constraints=["altitude_limit", "no_fly_zone"],
        ),
        SimTask(
            task_id="drone_avoid_obstacle",
            domain="drone",
            description="Drone navigates around an obstacle to reach target",
            initial_state={"position": [0, 0, 10]},
            goal_state={"position": [20, 0, 10]},
            success_criteria={"target_reached": True, "no_collision": True},
            max_steps=30,
            obstacles=[{"position": [10, 0, 10], "radius": 2.0}],
            safety_constraints=["no_collision", "safe_altitude"],
        ),
        # Industrial domain
        SimTask(
            task_id="industrial_process_control",
            domain="industrial",
            description="Maintain temperature within safe operating range",
            initial_state={"temperature": 25, "pressure": 1.0},
            goal_state={"temperature": 60, "pressure": 2.0},
            success_criteria={"temperature_in_range": True, "pressure_in_range": True},
            max_steps=20,
            safety_constraints=["temp_limit", "pressure_limit"],
        ),
        SimTask(
            task_id="industrial_emergency_stop",
            domain="industrial",
            description="Emergency stop when temperature exceeds safe limit",
            initial_state={"temperature": 90, "pressure": 5.0},
            goal_state={"system_stopped": True},
            success_criteria={"system_stopped": True, "safe_shutdown": True},
            max_steps=5,
            safety_constraints=["emergency_stop_threshold"],
        ),
    ]


_TASK_MAP: Dict[str, SimTask] = {t.task_id: t for t in _all_tasks()}


def get_task(task_id: str) -> Optional[SimTask]:
    return _TASK_MAP.get(task_id)


def list_tasks(domain: Optional[str] = None) -> List[SimTask]:
    if domain:
        return [t for t in _TASK_MAP.values() if t.domain == domain]
    return list(_TASK_MAP.values())


def list_domains() -> List[str]:
    return sorted(set(t.domain for t in _TASK_MAP.values()))
