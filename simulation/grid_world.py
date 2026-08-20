"""ORION GridWorld Simulation Environment (Phase 1 Cloud Simulation).

GridWorld provides a lightweight 2D physics and kinematic simulation environment
for testing ORION's Cognitive and State Planes without external heavy simulation dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SimEntity:
    """A physical entity operating in the GridWorld environment."""

    entity_id: str
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    ax: float = 0.0
    ay: float = 0.0
    heading: float = 0.0  # radians
    omega: float = 0.0  # rad/s angular velocity
    radius: float = 0.25  # bounding radius in meters
    max_speed: float = 2.0  # m/s
    max_accel: float = 1.0  # m/s^2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "position": [self.x, self.y, 0.0],
            "velocity": [self.vx, self.vy, 0.0],
            "acceleration": [self.ax, self.ay, 0.0],
            "heading": self.heading,
            "angular_velocity": self.omega,
            "radius": self.radius,
        }


@dataclass
class Obstacle:
    """Obstacle in GridWorld."""

    obstacle_id: str
    obstacle_type: str = "circle"  # "circle" or "rectangle"
    # For "circle": {"x": float, "y": float, "radius": float}
    # For "rectangle": {"min_x": float, "max_x": float, "min_y": float, "max_y": float}
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.obstacle_id,
            "type": self.obstacle_type,
            "params": self.params,
        }


class GridWorld:
    """2D Kinematic GridWorld Simulation Environment."""

    def __init__(
        self,
        width: float = 10.0,
        height: float = 10.0,
        resolution: float = 0.1,
    ) -> None:
        """Initialize GridWorld environment.

        Args:
            width: World width in meters (0 to width).
            height: World height in meters (0 to height).
            resolution: Grid cell resolution in meters.
        """
        self.width = width
        self.height = height
        self.resolution = resolution
        self.entities: Dict[str, SimEntity] = {}
        self.obstacles: Dict[str, Obstacle] = {}
        self.targets: Dict[str, List[float]] = {}
        self.time_elapsed: float = 0.0

    def add_entity(
        self,
        entity_id: str,
        x: float,
        y: float,
        heading: float = 0.0,
        radius: float = 0.25,
        max_speed: float = 2.0,
    ) -> SimEntity:
        """Add a physical entity to the simulation."""
        entity = SimEntity(
            entity_id=entity_id,
            x=x,
            y=y,
            heading=heading,
            radius=radius,
            max_speed=max_speed,
        )
        self.entities[entity_id] = entity
        return entity

    def add_obstacle(
        self,
        obstacle_id: str,
        obstacle_type: str,
        params: Dict[str, Any],
    ) -> Obstacle:
        """Add an obstacle to the simulation."""
        obs = Obstacle(obstacle_id=obstacle_id, obstacle_type=obstacle_type, params=params)
        self.obstacles[obstacle_id] = obs
        return obs

    def add_target(self, target_id: str, x: float, y: float) -> None:
        """Add a goal target coordinate."""
        self.targets[target_id] = [x, y]

    def check_collision(
        self,
        x: float,
        y: float,
        radius: float,
        ignore_entity_id: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Check if a circle at (x, y) with given radius collides with boundaries or obstacles."""
        collided = False
        collided_ids: List[str] = []

        # 1. Boundary check
        if (x - radius) < 0 or (x + radius) > self.width or (y - radius) < 0 or (y + radius) > self.height:
            collided = True
            collided_ids.append("boundary_wall")

        # 2. Obstacle check
        for obs_id, obs in self.obstacles.items():
            if obs.obstacle_type == "circle":
                ox = obs.params.get("x", 0.0)
                oy = obs.params.get("y", 0.0)
                orad = obs.params.get("radius", 0.5)
                dist = math.hypot(x - ox, y - oy)
                if dist < (radius + orad):
                    collided = True
                    collided_ids.append(obs_id)

            elif obs.obstacle_type == "rectangle":
                min_x = obs.params.get("min_x", 0.0)
                max_x = obs.params.get("max_x", 1.0)
                min_y = obs.params.get("min_y", 0.0)
                max_y = obs.params.get("max_y", 1.0)

                # Closest point on rectangle to circle center
                closest_x = max(min_x, min(x, max_x))
                closest_y = max(min_y, min(y, max_y))
                dist = math.hypot(x - closest_x, y - closest_y)
                if dist < radius:
                    collided = True
                    collided_ids.append(obs_id)

        # 3. Entity check
        for e_id, ent in self.entities.items():
            if ignore_entity_id and e_id == ignore_entity_id:
                continue
            dist = math.hypot(x - ent.x, y - ent.y)
            if dist < (radius + ent.radius):
                collided = True
                collided_ids.append(f"entity_{e_id}")

        return collided, collided_ids

    def step(self, dt: float) -> List[Dict[str, Any]]:
        """Advance the kinematic simulation by dt seconds.

        Args:
            dt: Time step in seconds.

        Returns:
            List of event dicts (e.g., collisions).
        """
        events: List[Dict[str, Any]] = []
        self.time_elapsed += dt

        for e_id, ent in self.entities.items():
            # Kinematic acceleration & velocity update
            ent.vx += ent.ax * dt
            ent.vy += ent.ay * dt

            speed = math.hypot(ent.vx, ent.vy)
            if speed > ent.max_speed:
                scale = ent.max_speed / speed
                ent.vx *= scale
                ent.vy *= scale

            # Heading update
            ent.heading += ent.omega * dt
            ent.heading = math.atan2(math.sin(ent.heading), math.cos(ent.heading))

            # Proposed position step
            new_x = ent.x + ent.vx * dt
            new_y = ent.y + ent.vy * dt

            # Collision detection
            is_collision, c_ids = self.check_collision(new_x, new_y, ent.radius, ignore_entity_id=e_id)

            if is_collision:
                events.append({
                    "type": "collision",
                    "entity_id": e_id,
                    "position": [new_x, new_y],
                    "collided_with": c_ids,
                    "time": self.time_elapsed,
                })
                # Zero out velocity on collision (simple rigid stop)
                ent.vx = 0.0
                ent.vy = 0.0
                ent.ax = 0.0
                ent.ay = 0.0
            else:
                ent.x = new_x
                ent.y = new_y

        return events

    def get_world_state(self) -> Dict[str, Any]:
        """Return full current snapshot of world state."""
        return {
            "time_elapsed": self.time_elapsed,
            "dimensions": [self.width, self.height],
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "obstacles": {k: v.to_dict() for k, v in self.obstacles.items()},
            "targets": self.targets,
        }
