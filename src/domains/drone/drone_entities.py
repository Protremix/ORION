"""Drone domain entity models for ORION Physical Intelligence OS.

Defines entities for a simulated drone environment including the drone itself,
IMU/altitude sensors, geofencing, collision avoidance, battery management,
and flight mode controllers.

Safety Criticality: SC-2 (physical risk to people/property below)
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple


class DroneEntity:
    """Base drone entity with position, velocity, battery, and state."""

    def __init__(
        self,
        entity_id: str = "drone_1",
        position: List[float] = None,
        velocity: List[float] = None,
        altitude: float = 0.0,
        battery_pct: float = 100.0,
    ) -> None:
        self.entity_id = entity_id
        self.entity_type = "drone"
        self.position = list(position) if position else [0.0, 0.0, 0.0]
        self.velocity = list(velocity) if velocity else [0.0, 0.0, 0.0]
        self.altitude = altitude
        self.battery_pct = battery_pct
        self.state = "IDLE"  # IDLE, HOVERING, FLYING, RETURNING, LANDING, EMERGENCY_LANDING, CRASHED
        self.flight_mode = "idle"  # idle, hover, waypoint, return_to_base, emergency_landing
        self.wind_speed = 0.0
        self.state_revision = 1
        self.last_updated_ns = time.monotonic_ns()

    def increment_state_revision(self) -> int:
        self.state_revision += 1
        self.last_updated_ns = time.monotonic_ns()
        return self.state_revision

    def set_state(self, new_state: str) -> None:
        if self.state != new_state:
            self.state = new_state
            self.increment_state_revision()

    def set_flight_mode(self, mode: str) -> None:
        self.flight_mode = mode
        self.increment_state_revision()

    def update_position(self, dt: float = 0.1) -> None:
        """Update position based on velocity."""
        for i in range(3):
            self.position[i] += self.velocity[i] * dt
        self.altitude = self.position[2]
        self.increment_state_revision()

    def set_velocity(self, vx: float, vy: float, vz: float) -> None:
        self.velocity = [vx, vy, vz]
        self.increment_state_revision()

    def drain_battery(self, amount: float) -> None:
        self.battery_pct = max(0.0, self.battery_pct - amount)
        self.increment_state_revision()

    def is_low_battery(self, threshold: float = 20.0) -> bool:
        return self.battery_pct <= threshold

    def is_critical_battery(self, threshold: float = 10.0) -> bool:
        return self.battery_pct <= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "position": list(self.position),
            "velocity": list(self.velocity),
            "altitude": self.altitude,
            "battery_pct": self.battery_pct,
            "state": self.state,
            "flight_mode": self.flight_mode,
            "state_revision": self.state_revision,
        }


class IMUSensor:
    """Inertial Measurement Unit sensor for orientation and acceleration."""

    def __init__(self, sensor_id: str = "imu_1") -> None:
        self.sensor_id = sensor_id
        self.sensor_type = "imu"
        self.orientation = [0.0, 0.0, 0.0]  # roll, pitch, yaw
        self.acceleration = [0.0, 0.0, 0.0]
        self.angular_velocity = [0.0, 0.0, 0.0]
        self.is_healthy = True

    def update(self, orientation: List[float], accel: List[float], gyro: List[float]) -> None:
        self.orientation = list(orientation)
        self.acceleration = list(accel)
        self.angular_velocity = list(gyro)

    def detect_tilt(self, threshold: float = 15.0) -> bool:
        """Detect if drone is tilted beyond threshold (degrees)."""
        roll, pitch, _ = self.orientation
        return abs(roll) > threshold or abs(pitch) > threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "orientation": list(self.orientation),
            "acceleration": list(self.acceleration),
            "angular_velocity": list(self.angular_velocity),
            "is_healthy": self.is_healthy,
        }


class AltitudeSensor:
    """Altitude sensor (barometer-based)."""

    def __init__(self, sensor_id: str = "alt_1", max_altitude: float = 120.0) -> None:
        self.sensor_id = sensor_id
        self.sensor_type = "altitude"
        self.current_altitude = 0.0
        self.max_altitude = max_altitude
        self.is_healthy = True

    def update(self, altitude: float) -> None:
        self.current_altitude = altitude

    def is_above_limit(self) -> bool:
        return self.current_altitude > self.max_altitude

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "current_altitude": self.current_altitude,
            "max_altitude": self.max_altitude,
            "is_healthy": self.is_healthy,
        }


class GeofenceController:
    """Geofencing controller using CBF barrier functions."""

    def __init__(
        self,
        boundary_min: Tuple[float, float, float] = (-100.0, -100.0, 0.0),
        boundary_max: Tuple[float, float, float] = (100.0, 100.0, 120.0),
        safety_margin: float = 5.0,
    ) -> None:
        self.boundary_min = boundary_min
        self.boundary_max = boundary_max
        self.safety_margin = safety_margin
        self.violations: List[Dict[str, Any]] = []

    def check_position(self, position: List[float]) -> Tuple[bool, str]:
        """Check if position is within geofence. Returns (is_safe, reason)."""
        for i, (p, p_min, p_max, axis) in enumerate(
            zip(position, self.boundary_min, self.boundary_max, ["x", "y", "z"])
        ):
            if p < p_min + self.safety_margin:
                self.violations.append({"axis": axis, "direction": "min", "value": p, "limit": p_min + self.safety_margin})
                return False, f"Geofence violation: {axis}={p:.1f} < {p_min + self.safety_margin:.1f}"
            if p > p_max - self.safety_margin:
                self.violations.append({"axis": axis, "direction": "max", "value": p, "limit": p_max - self.safety_margin})
                return False, f"Geofence violation: {axis}={p:.1f} > {p_max - self.safety_margin:.1f}"
        return True, "OK"

    def compute_safe_velocity(self, position: List[float], desired_velocity: List[float]) -> List[float]:
        """Filter velocity to stay within geofence (CBF projection)."""
        safe_v = list(desired_velocity)
        for i in range(3):
            p = position[i]
            p_min = self.boundary_min[i] + self.safety_margin
            p_max = self.boundary_max[i] - self.safety_margin

            # If near min boundary and moving towards it
            if p < p_min + 2.0 and safe_v[i] < 0:
                safe_v[i] = 0.0
            # If near max boundary and moving towards it
            if p > p_max - 2.0 and safe_v[i] > 0:
                safe_v[i] = 0.0

        return safe_v

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_min": list(self.boundary_min),
            "boundary_max": list(self.boundary_max),
            "safety_margin": self.safety_margin,
            "violation_count": len(self.violations),
        }


class CollisionAvoidance3D:
    """3D collision avoidance using Control Barrier Functions."""

    def __init__(self, safe_distance: float = 3.0, max_decel: float = 5.0) -> None:
        self.safe_distance = safe_distance
        self.max_decel = max_decel
        self.obstacles: List[Dict[str, Any]] = []

    def add_obstacle(self, position: List[float], radius: float = 1.0, obstacle_id: str = "") -> None:
        self.obstacles.append({
            "id": obstacle_id or f"obstacle_{len(self.obstacles)}",
            "position": list(position),
            "radius": radius,
        })

    def clear_obstacles(self) -> None:
        self.obstacles = []

    def check_safety(self, drone_pos: List[float], drone_vel: List[float]) -> Tuple[bool, Optional[str]]:
        """Check if current trajectory is safe. Returns (is_safe, reason)."""
        for obs in self.obstacles:
            dist = math.sqrt(sum((p - o) ** 2 for p, o in zip(drone_pos, obs["position"])))
            if dist < self.safe_distance + obs["radius"]:
                return False, f"Collision risk: {dist:.1f}m from {obs['id']}"
            # Check if moving towards obstacle
            direction = [o - p for p, o in zip(drone_pos, obs["position"])]
            dist_full = math.sqrt(sum(d ** 2 for d in direction))
            if dist_full > 0:
                vel_dot = sum(v * d for v, d in zip(drone_vel, direction)) / dist_full
                if vel_dot > 0 and dist < self.safe_distance * 2:
                    # Moving towards obstacle and close
                    stopping_dist = sum(v ** 2 for v in drone_vel) / (2 * self.max_decel)
                    if dist - stopping_dist < self.safe_distance + obs["radius"]:
                        return False, f"Will collide: {dist:.1f}m, stopping={stopping_dist:.1f}m"
        return True, None

    def filter_velocity(self, drone_pos: List[float], desired_vel: List[float]) -> List[float]:
        """Filter velocity to avoid collisions (CBF projection).

        Instead of fully stopping, redirects velocity around the obstacle
        by adding a lateral component perpendicular to the obstacle direction.
        """
        safe_v = list(desired_vel)
        for obs in self.obstacles:
            direction = [p - o for p, o in zip(drone_pos, obs["position"])]
            dist = math.sqrt(sum(d ** 2 for d in direction))
            if dist == 0:
                continue
            if dist < self.safe_distance * 2:
                # Check if moving towards obstacle
                vel_dot = sum(v * d for v, d in zip(safe_v, direction)) / dist
                if vel_dot < 0:  # Moving towards obstacle
                    # Scale down the component towards the obstacle
                    factor = max(0.1, (dist - self.safe_distance - obs["radius"]) / self.safe_distance)
                    # Decompose velocity into radial and tangential
                    unit_dir = [d / dist for d in direction]
                    radial_component = vel_dot
                    # Reduce radial component, add tangential
                    for i in range(3):
                        radial_v = radial_component * unit_dir[i]
                        tangential_v = safe_v[i] - radial_v
                        safe_v[i] = tangential_v + radial_v * factor
        return safe_v

    def to_dict(self) -> Dict[str, Any]:
        return {
            "safe_distance": self.safe_distance,
            "max_decel": self.max_decel,
            "obstacle_count": len(self.obstacles),
        }


class BatteryManager:
    """Battery management with return-to-base logic."""

    def __init__(
        self,
        capacity_pct: float = 100.0,
        low_threshold: float = 20.0,
        critical_threshold: float = 10.0,
        home_position: List[float] = None,
    ) -> None:
        self.capacity_pct = capacity_pct
        self.low_threshold = low_threshold
        self.critical_threshold = critical_threshold
        self.home_position = list(home_position) if home_position else [0.0, 0.0, 0.0]
        self.discharge_rate_per_sec = 0.05  # % per second in flight

    def drain(self, seconds: float, is_hovering: bool = False) -> float:
        """Drain battery. Hovering uses less power than flying."""
        rate = self.discharge_rate_per_sec * (0.7 if is_hovering else 1.0)
        self.capacity_pct = max(0.0, self.capacity_pct - rate * seconds)
        return self.capacity_pct

    def should_return_to_base(self) -> bool:
        """Check if battery is low enough to trigger return-to-base."""
        return self.capacity_pct <= self.low_threshold

    def should_emergency_land(self) -> bool:
        """Check if battery is critically low — must land immediately."""
        return self.capacity_pct <= self.critical_threshold

    def compute_return_time(self, current_pos: List[float]) -> float:
        """Estimate time to return to base (seconds)."""
        dist = math.sqrt(sum((p - h) ** 2 for p, h in zip(current_pos, self.home_position)))
        avg_speed = 5.0  # m/s
        return dist / avg_speed if avg_speed > 0 else 0.0

    def has_enough_battery_to_return(self, current_pos: List[float]) -> bool:
        """Check if enough battery remains to return to base."""
        return_time = self.compute_return_time(current_pos)
        needed_battery = return_time * self.discharge_rate_per_sec + 5.0  # 5% margin
        return self.capacity_pct > needed_battery

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capacity_pct": self.capacity_pct,
            "low_threshold": self.low_threshold,
            "critical_threshold": self.critical_threshold,
            "should_return": self.should_return_to_base(),
            "should_emergency_land": self.should_emergency_land(),
        }


class FlightController:
    """Flight mode controller for the drone."""

    HOVER = "hover"
    WAYPOINT = "waypoint"
    RETURN_TO_BASE = "return_to_base"
    EMERGENCY_LANDING = "emergency_landing"

    def __init__(self, home_position: List[float] = None) -> None:
        self.home_position = list(home_position) if home_position else [0.0, 0.0, 0.0]
        self.current_mode = "idle"
        self.waypoints: List[List[float]] = []
        self.current_waypoint_idx = 0
        self.target_position: List[float] = list(self.home_position)
        self.cruise_speed: float = 5.0  # m/s

    def set_hover(self, position: List[float]) -> None:
        self.current_mode = self.HOVER
        self.target_position = list(position)

    def set_waypoints(self, waypoints: List[List[float]]) -> None:
        self.current_mode = self.WAYPOINT
        self.waypoints = [list(wp) for wp in waypoints]
        self.current_waypoint_idx = 0
        if waypoints:
            self.target_position = list(waypoints[0])

    def set_return_to_base(self) -> None:
        self.current_mode = self.RETURN_TO_BASE
        self.target_position = list(self.home_position)

    def set_emergency_landing(self, position: List[float]) -> None:
        self.current_mode = self.EMERGENCY_LANDING
        self.target_position = [position[0], position[1], 0.0]  # Land at current x,y

    def compute_velocity(self, current_pos: List[float]) -> List[float]:
        """Compute velocity to reach target position."""
        direction = [t - c for t, c in zip(self.target_position, current_pos)]
        dist = math.sqrt(sum(d ** 2 for d in direction))
        if dist < 0.1:
            # Reached target
            if self.current_mode == self.WAYPOINT and self.current_waypoint_idx < len(self.waypoints) - 1:
                self.current_waypoint_idx += 1
                self.target_position = list(self.waypoints[self.current_waypoint_idx])
                return self.compute_velocity(current_pos)
            return [0.0, 0.0, 0.0]

        # Normalize and scale by cruise speed
        speed = min(self.cruise_speed, dist / 0.1)  # Don't overshoot
        return [d / dist * speed for d in direction]

    def has_reached_target(self, current_pos: List[float]) -> bool:
        dist = math.sqrt(sum((t - c) ** 2 for t, c in zip(self.target_position, current_pos)))
        return dist < 0.5

    def is_mission_complete(self) -> bool:
        if self.current_mode == self.WAYPOINT:
            return self.current_waypoint_idx >= len(self.waypoints) - 1
        return self.current_mode in ("hover",)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_mode": self.current_mode,
            "target_position": list(self.target_position),
            "waypoint_count": len(self.waypoints),
            "current_waypoint_idx": self.current_waypoint_idx,
        }
