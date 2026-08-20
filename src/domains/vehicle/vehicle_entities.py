# Copyright 2026 ORION Physical Intelligence OS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Vehicle domain entity models for ORION Physical Intelligence OS.

Defines physical vehicle entities, sensors, safety controllers (ACC, AEB, CBF),
and state revision tracking for SC-2 safety-critical full autonomous driving simulation.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from src.safety.safety_enforcement import ControlBarrierFunction
except ImportError:
    class ControlBarrierFunction:  # type: ignore
        """Fallback definition if src.safety is not on sys.path."""
        def __init__(self, name: str, gamma: float = 1.0):
            self.name = name
            self.gamma = gamma

        def h(self, state: Dict[str, Any]) -> float:
            raise NotImplementedError

        def dh_dt(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
            raise NotImplementedError


class VehicleDomainEntity:
    """Base class for all vehicle domain entities in ORION.

    Provides state_revision tracking, unique identification, status tracking,
    and state export for the ORION State Plane.
    """

    def __init__(
        self,
        entity_id: str,
        entity_type: str,
        position: Optional[List[float]] = None,
        status: str = "NOMINAL",
    ) -> None:
        self.entity_id: str = entity_id
        self.entity_type: str = entity_type
        self.position: List[float] = list(position) if position else [0.0, 0.0, 0.0]
        self.status: str = status
        self.state_revision: int = 1
        self.last_updated_ns: int = time.monotonic_ns()

    def increment_state_revision(self) -> int:
        """Increment the state revision counter when entity state changes."""
        self.state_revision += 1
        self.last_updated_ns = time.monotonic_ns()
        return self.state_revision

    def set_status(self, new_status: str) -> None:
        """Update entity status and increment revision if changed."""
        if self.status != new_status:
            self.status = new_status
            self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        """Export state representation dictionary for state plane fusion."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "position": list(self.position),
            "status": self.status,
            "state_revision": self.state_revision,
            "last_updated_ns": self.last_updated_ns,
        }


class VehicleEntity(VehicleDomainEntity):
    """Simulated autonomous vehicle entity with kinematic updates, state machine, and gears."""

    VALID_GEARS = {"PARK", "REVERSE", "DRIVE"}
    VALID_STATES = {"IDLE", "MOVING", "BRAKING", "STOPPED", "EMERGENCY"}
    VALID_TURN_SIGNALS = {"OFF", "LEFT", "RIGHT", "HAZARD"}

    def __init__(
        self,
        entity_id: str = "ego_vehicle",
        position: Optional[List[float]] = None,
        heading: float = 0.0,
        lane_position: int = 0,
        gear: str = "PARK",
        state: str = "IDLE",
        wheelbase: float = 2.5,
        max_speed: float = 35.0,  # m/s (~126 km/h)
        max_acceleration: float = 3.0,  # m/s^2
        max_deceleration: float = 8.0,  # m/s^2
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="vehicle",
            position=position or [0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.speed: float = 0.0  # m/s
        self.heading: float = heading  # radians
        self.lane_position: int = lane_position
        gear_upper = gear.upper()
        if gear_upper not in self.VALID_GEARS:
            raise ValueError(f"Invalid gear: {gear}. Must be one of {self.VALID_GEARS}")
        self.gear: str = gear_upper

        state_upper = state.upper()
        if state_upper not in self.VALID_STATES:
            raise ValueError(f"Invalid state: {state}. Must be one of {self.VALID_STATES}")
        self.state: str = state_upper

        self.steering_angle: float = 0.0  # radians
        self.turn_signal: str = "OFF"
        self.wheelbase: float = wheelbase
        self.max_speed: float = max_speed
        self.max_acceleration: float = max_acceleration
        self.max_deceleration: float = max_deceleration

    def set_gear(self, gear: str) -> None:
        """Set vehicle transmission gear (PARK, REVERSE, DRIVE)."""
        gear_upper = gear.upper()
        if gear_upper not in self.VALID_GEARS:
            raise ValueError(f"Invalid gear '{gear}'. Allowed: {self.VALID_GEARS}")
        if gear_upper == "PARK" and self.speed > 0.1:
            raise ValueError(f"Cannot engage PARK while moving at speed {self.speed:.2f} m/s")
        if self.gear != gear_upper:
            self.gear = gear_upper
            self.increment_state_revision()

    def set_state(self, state: str) -> None:
        """Update vehicle operating state (IDLE, MOVING, BRAKING, STOPPED, EMERGENCY)."""
        state_upper = state.upper()
        if state_upper not in self.VALID_STATES:
            raise ValueError(f"Invalid vehicle state '{state}'. Allowed: {self.VALID_STATES}")
        if self.state != state_upper:
            self.state = state_upper
            if self.state == "EMERGENCY":
                self.set_status("EMERGENCY")
            elif self.status == "EMERGENCY" and self.state != "EMERGENCY":
                self.set_status("NOMINAL")
            self.increment_state_revision()

    def set_turn_signal(self, signal: str) -> None:
        """Set turn signal state (OFF, LEFT, RIGHT, HAZARD)."""
        signal_upper = signal.upper()
        if signal_upper not in self.VALID_TURN_SIGNALS:
            raise ValueError(f"Invalid turn signal '{signal}'. Allowed: {self.VALID_TURN_SIGNALS}")
        if self.turn_signal != signal_upper:
            self.turn_signal = signal_upper
            self.increment_state_revision()

    def update_kinematics(self, acceleration: float, steering_angle: float, dt: float) -> List[float]:
        """Update vehicle speed, position, heading, and state using kinematic bicycle model."""
        if dt <= 0.0:
            return self.position

        # Clamp acceleration within vehicle limits
        clamped_accel = max(-self.max_deceleration, min(acceleration, self.max_acceleration))

        # Clamp steering angle [-0.6 rad, 0.6 rad] (~34 deg)
        self.steering_angle = max(-0.6, min(steering_angle, 0.6))

        # Kinematic speed update depending on gear
        if self.gear == "PARK":
            self.speed = 0.0
            accel_applied = 0.0
        elif self.gear == "REVERSE":
            self.speed = max(0.0, min(self.speed + clamped_accel * dt, 5.0))  # reverse max 5 m/s
            accel_applied = clamped_accel
        else:  # DRIVE
            self.speed = max(0.0, min(self.speed + clamped_accel * dt, self.max_speed))
            accel_applied = clamped_accel

        # Auto state transition based on motion
        if self.state != "EMERGENCY":
            if self.speed == 0.0:
                self.state = "STOPPED" if self.gear in ("DRIVE", "REVERSE") else "IDLE"
            elif accel_applied < -0.5:
                self.state = "BRAKING"
            else:
                self.state = "MOVING"

        # Position & Heading update
        direction = -1.0 if self.gear == "REVERSE" else 1.0
        dist = direction * self.speed * dt

        if abs(self.steering_angle) > 1e-4 and self.speed > 1e-3:
            omega = (dist / self.wheelbase) * math.tan(self.steering_angle)
            self.heading += omega
            self.heading = math.atan2(math.sin(self.heading), math.cos(self.heading))

        dx = dist * math.cos(self.heading)
        dy = dist * math.sin(self.heading)

        self.position[0] += dx
        self.position[1] += dy

        self.increment_state_revision()
        return self.position

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "speed": self.speed,
            "heading": self.heading,
            "lane_position": self.lane_position,
            "gear": self.gear,
            "state": self.state,
            "steering_angle": self.steering_angle,
            "turn_signal": self.turn_signal,
            "wheelbase": self.wheelbase,
            "max_speed": self.max_speed,
            "max_acceleration": self.max_acceleration,
            "max_deceleration": self.max_deceleration,
        })
        return data


class LaneSensor(VehicleDomainEntity):
    """Sensor for detecting lane boundaries, current lane, offset, and departure warnings."""

    def __init__(
        self,
        sensor_id: str = "lane_sensor_1",
        lane_width: float = 3.5,
        num_lanes: int = 3,
        departure_warning_threshold: float = 0.5,
    ) -> None:
        super().__init__(
            entity_id=sensor_id,
            entity_type="lane_sensor",
            position=[0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.lane_width: float = lane_width
        self.num_lanes: int = num_lanes
        self.departure_warning_threshold: float = departure_warning_threshold
        self.current_lane: int = 0
        self.lane_offset: float = 0.0  # meters from lane center
        self.departure_warning: bool = False
        self.detected_lanes: List[Dict[str, Any]] = []

    def detect_lanes(self, vehicle_pos: List[float], road_y_start: float = 0.0) -> Dict[str, Any]:
        """Detect lane parameters based on vehicle lateral coordinate."""
        y_pos = vehicle_pos[1] - road_y_start

        lane_idx = int(math.floor(y_pos / self.lane_width))
        lane_idx = max(0, min(lane_idx, self.num_lanes - 1))
        self.current_lane = lane_idx

        lane_center_y = road_y_start + (lane_idx + 0.5) * self.lane_width
        self.lane_offset = vehicle_pos[1] - lane_center_y

        self.departure_warning = abs(self.lane_offset) > self.departure_warning_threshold
        if self.departure_warning:
            self.set_status("DEPARTURE_WARNING")
        else:
            self.set_status("NOMINAL")

        self.detected_lanes = [
            {
                "lane_index": i,
                "center_y": road_y_start + (i + 0.5) * self.lane_width,
                "is_current": (i == self.current_lane),
            }
            for i in range(self.num_lanes)
        ]

        self.position = list(vehicle_pos)
        self.increment_state_revision()
        return self.to_dict()

    def check_departure(self, lane_offset: float) -> bool:
        """Check if a given lateral offset triggers lane departure warning."""
        return abs(lane_offset) > self.departure_warning_threshold

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "lane_width": self.lane_width,
            "num_lanes": self.num_lanes,
            "current_lane": self.current_lane,
            "lane_offset": self.lane_offset,
            "departure_warning": self.departure_warning,
            "departure_warning_threshold": self.departure_warning_threshold,
            "detected_lanes": self.detected_lanes,
        })
        return data


class ObstacleSensor(VehicleDomainEntity):
    """Multi-zone sensor measuring distances to obstacles (front, side_left, side_right, rear)."""

    def __init__(
        self,
        sensor_id: str = "obstacle_sensor_1",
        front_range: float = 50.0,
        side_range: float = 15.0,
        rear_range: float = 20.0,
    ) -> None:
        super().__init__(
            entity_id=sensor_id,
            entity_type="obstacle_sensor",
            position=[0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.front_range: float = front_range
        self.side_range: float = side_range
        self.rear_range: float = rear_range
        self.detected_obstacles: Dict[str, List[Dict[str, Any]]] = {
            "front": [],
            "side_left": [],
            "side_right": [],
            "rear": [],
        }

    def scan(
        self,
        vehicle_pos: List[float],
        vehicle_heading: float,
        obstacles: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Scan obstacles and categorize by body-frame zone and distance."""
        self.detected_obstacles = {
            "front": [],
            "side_left": [],
            "side_right": [],
            "rear": [],
        }

        vx, vy = vehicle_pos[0], vehicle_pos[1]
        cos_h = math.cos(vehicle_heading)
        sin_h = math.sin(vehicle_heading)

        for obs in obstacles:
            obs_id = obs.get("id", obs.get("entity_id", "unknown"))
            pos = obs.get("position", [0.0, 0.0, 0.0])
            ox, oy = pos[0], pos[1]

            dx = ox - vx
            dy = oy - vy
            dist = math.hypot(dx, dy)

            # Transform into vehicle local body frame
            local_x = dx * cos_h + dy * sin_h
            local_y = -dx * sin_h + dy * cos_h

            obs_info = {
                "id": obs_id,
                "distance": dist,
                "local_x": local_x,
                "local_y": local_y,
                "speed": obs.get("speed", 0.0),
                "position": [ox, oy, 0.0],
            }

            # Zone classification
            if local_x > 0 and abs(local_y) <= 2.0 and local_x <= self.front_range:
                self.detected_obstacles["front"].append(obs_info)
            elif local_x < 0 and abs(local_y) <= 2.0 and abs(local_x) <= self.rear_range:
                self.detected_obstacles["rear"].append(obs_info)
            elif local_y > 0.5 and abs(local_x) <= 10.0 and local_y <= self.side_range:
                self.detected_obstacles["side_left"].append(obs_info)
            elif local_y < -0.5 and abs(local_x) <= 10.0 and abs(local_y) <= self.side_range:
                self.detected_obstacles["side_right"].append(obs_info)

        for z in self.detected_obstacles:
            self.detected_obstacles[z].sort(key=lambda x: x["distance"])

        self.position = list(vehicle_pos)
        self.increment_state_revision()
        return self.detected_obstacles

    def get_min_distance(self, zone: str = "front") -> float:
        """Get minimum detected obstacle distance in specified zone."""
        obs_list = self.detected_obstacles.get(zone, [])
        if not obs_list:
            if zone == "front":
                return self.front_range
            elif zone in ("side_left", "side_right"):
                return self.side_range
            else:
                return self.rear_range
        return obs_list[0]["distance"]

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "front_range": self.front_range,
            "side_range": self.side_range,
            "rear_range": self.rear_range,
            "detected_obstacles": self.detected_obstacles,
            "min_distances": {
                z: self.get_min_distance(z) for z in ["front", "side_left", "side_right", "rear"]
            },
        })
        return data


class TrafficLightSensor(VehicleDomainEntity):
    """Sensor detecting traffic light state (RED/YELLOW/GREEN) and stop line distance."""

    def __init__(
        self,
        sensor_id: str = "traffic_light_sensor_1",
        detection_range: float = 40.0,
    ) -> None:
        super().__init__(
            entity_id=sensor_id,
            entity_type="traffic_light_sensor",
            position=[0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.detection_range: float = detection_range
        self.light_state: str = "OFF"  # RED, YELLOW, GREEN, OFF
        self.distance_to_light: float = float("inf")
        self.stop_line_pos: Optional[List[float]] = None

    def detect_light(
        self,
        traffic_lights: List[Dict[str, Any]],
        vehicle_pos: List[float],
        vehicle_heading: float,
    ) -> Dict[str, Any]:
        """Detect closest traffic light in front of vehicle within detection range."""
        self.light_state = "OFF"
        self.distance_to_light = float("inf")
        self.stop_line_pos = None

        vx, vy = vehicle_pos[0], vehicle_pos[1]
        cos_h = math.cos(vehicle_heading)
        sin_h = math.sin(vehicle_heading)

        min_dist = self.detection_range

        for tl in traffic_lights:
            pos = tl.get("position", [0.0, 0.0, 0.0])
            tx, ty = pos[0], pos[1]
            dx = tx - vx
            dy = ty - vy
            local_x = dx * cos_h + dy * sin_h

            if local_x > 0 and local_x < min_dist:
                min_dist = local_x
                self.distance_to_light = local_x
                self.light_state = tl.get("state", "RED").upper()
                self.stop_line_pos = list(pos)

        self.position = list(vehicle_pos)
        self.increment_state_revision()
        return self.to_dict()

    def should_stop(self) -> bool:
        """Determine if vehicle should stop based on traffic light state and distance."""
        if self.light_state == "RED" and self.distance_to_light <= self.detection_range:
            return True
        if self.light_state == "YELLOW" and self.distance_to_light <= 15.0:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "detection_range": self.detection_range,
            "light_state": self.light_state,
            "distance_to_light": self.distance_to_light,
            "stop_line_pos": self.stop_line_pos,
            "should_stop": self.should_stop(),
        })
        return data


class SpeedController(VehicleDomainEntity):
    """Speed controller managing target speed, acceleration, braking, and cruise control."""

    def __init__(
        self,
        controller_id: str = "speed_controller_1",
        target_speed: float = 20.0,
        max_acceleration: float = 3.0,
        max_deceleration: float = 8.0,
        kp: float = 0.8,
    ) -> None:
        super().__init__(
            entity_id=controller_id,
            entity_type="speed_controller",
            position=[0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.target_speed: float = target_speed
        self.max_acceleration: float = max_acceleration
        self.max_deceleration: float = max_deceleration
        self.kp: float = kp
        self.cruise_control_active: bool = False

    def set_target_speed(self, speed: float) -> None:
        """Set desired target cruising speed."""
        self.target_speed = max(0.0, speed)
        self.increment_state_revision()

    def enable_cruise_control(self, target_speed: Optional[float] = None) -> None:
        """Enable cruise control system."""
        if target_speed is not None:
            self.set_target_speed(target_speed)
        self.cruise_control_active = True
        self.set_status("CRUISE_ACTIVE")

    def disable_cruise_control(self) -> None:
        """Disable cruise control system."""
        self.cruise_control_active = False
        self.set_status("NOMINAL")

    def compute_control(self, current_speed: float, dt: float) -> float:
        """Compute acceleration/deceleration control command to reach target speed."""
        error = self.target_speed - current_speed
        accel_cmd = self.kp * error
        clamped_accel = max(-self.max_deceleration, min(accel_cmd, self.max_acceleration))
        self.increment_state_revision()
        return clamped_accel

    def emergency_brake(self) -> float:
        """Issue full emergency braking acceleration command (-max_deceleration)."""
        self.disable_cruise_control()
        self.set_status("EMERGENCY_BRAKING")
        return -self.max_deceleration

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "target_speed": self.target_speed,
            "max_acceleration": self.max_acceleration,
            "max_deceleration": self.max_deceleration,
            "cruise_control_active": self.cruise_control_active,
        })
        return data


class SteeringController(VehicleDomainEntity):
    """Steering controller for lane keeping, lane change, and turn signal management."""

    def __init__(
        self,
        controller_id: str = "steering_controller_1",
        max_steering_angle: float = 0.5,
        kp_lateral: float = 0.5,
        kp_heading: float = 1.0,
    ) -> None:
        super().__init__(
            entity_id=controller_id,
            entity_type="steering_controller",
            position=[0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.max_steering_angle: float = max_steering_angle
        self.kp_lateral: float = kp_lateral
        self.kp_heading: float = kp_heading
        self.turn_signal: str = "OFF"
        self.is_changing_lanes: bool = False
        self.target_lane: int = 0

    def set_turn_signal(self, signal: str) -> None:
        """Set turn signal state (OFF, LEFT, RIGHT, HAZARD)."""
        self.turn_signal = signal.upper()
        self.increment_state_revision()

    def initiate_lane_change(self, direction: str, target_lane: int) -> None:
        """Initiate lane change maneuver to target_lane."""
        direction_upper = direction.upper()
        self.is_changing_lanes = True
        self.target_lane = target_lane
        self.set_turn_signal("LEFT" if direction_upper == "LEFT" else "RIGHT")
        self.set_status("LANE_CHANGING")

    def compute_steering(
        self,
        current_y: float,
        target_y: float,
        current_heading: float,
        target_heading: float = 0.0,
    ) -> float:
        """Compute steering angle for lane keeping / lane changing."""
        lateral_error = target_y - current_y
        heading_error = math.atan2(
            math.sin(target_heading - current_heading),
            math.cos(target_heading - current_heading),
        )

        steering = self.kp_lateral * lateral_error + self.kp_heading * heading_error
        clamped_steering = max(-self.max_steering_angle, min(steering, self.max_steering_angle))

        if self.is_changing_lanes and abs(lateral_error) < 0.1:
            self.is_changing_lanes = False
            self.set_turn_signal("OFF")
            self.set_status("NOMINAL")

        self.increment_state_revision()
        return clamped_steering

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "max_steering_angle": self.max_steering_angle,
            "turn_signal": self.turn_signal,
            "is_changing_lanes": self.is_changing_lanes,
            "target_lane": self.target_lane,
        })
        return data


class AEBController(VehicleDomainEntity):
    """Automatic Emergency Braking controller triggering on imminent collision risks."""

    def __init__(
        self,
        controller_id: str = "aeb_controller_1",
        ttc_threshold: float = 2.0,  # seconds
        critical_distance: float = 3.0,  # meters
        max_aeb_deceleration: float = -8.0,  # m/s^2
    ) -> None:
        super().__init__(
            entity_id=controller_id,
            entity_type="aeb_controller",
            position=[0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.ttc_threshold: float = ttc_threshold
        self.critical_distance: float = critical_distance
        self.max_aeb_deceleration: float = max_aeb_deceleration
        self.is_aeb_active: bool = False

    def evaluate(
        self,
        current_speed: float,
        obstacle_distance: float,
        relative_speed: float = 0.0,
    ) -> Tuple[bool, float]:
        """Evaluate collision risk and return (should_trigger_aeb, deceleration_cmd)."""
        closing_speed = current_speed - relative_speed

        ttc = float("inf")
        if closing_speed > 0.01:
            ttc = obstacle_distance / closing_speed

        should_trigger = (obstacle_distance <= self.critical_distance) or (0.0 <= ttc <= self.ttc_threshold)

        if should_trigger:
            self.is_aeb_active = True
            self.set_status("AEB_ACTIVE")
            self.increment_state_revision()
            return True, self.max_aeb_deceleration
        else:
            if self.is_aeb_active:
                self.is_aeb_active = False
                self.set_status("NOMINAL")
                self.increment_state_revision()
            return False, 0.0

    def reset(self) -> None:
        """Reset AEB controller state."""
        self.is_aeb_active = False
        self.set_status("NOMINAL")
        self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "ttc_threshold": self.ttc_threshold,
            "critical_distance": self.critical_distance,
            "max_aeb_deceleration": self.max_aeb_deceleration,
            "is_aeb_active": self.is_aeb_active,
        })
        return data


class FrontCollisionCBF(ControlBarrierFunction):
    """Control Barrier Function enforcing safe forward distance relative to velocity."""

    def __init__(
        self,
        name: str = "FrontCollisionCBF",
        safe_distance: float = 5.0,
        max_decel: float = 8.0,
        gamma: float = 1.5,
    ):
        super().__init__(name, gamma)
        self.safe_distance = safe_distance
        self.max_decel = max_decel

    def h(self, state: Dict[str, Any]) -> float:
        distance = state.get("front_distance", 50.0)
        speed = state.get("speed", 0.0)
        stopping_dist = (speed ** 2) / (2.0 * self.max_decel) if speed > 0 else 0.0
        return distance - stopping_dist - self.safe_distance

    def dh_dt(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
        speed = state.get("speed", 0.0)
        accel = control_input.get("acceleration", 0.0)
        if speed <= 0:
            return 0.0
        return -speed - (speed * accel) / self.max_decel


class CollisionAvoidance(VehicleDomainEntity):
    """CBF-based Collision Avoidance safety filter for front, side, and rear obstacles."""

    def __init__(
        self,
        entity_id: str = "collision_avoidance_1",
        safe_distance_front: float = 5.0,
        safe_distance_side: float = 1.5,
        safe_distance_rear: float = 3.0,
        gamma: float = 1.5,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="collision_avoidance",
            position=[0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.safe_distance_front = safe_distance_front
        self.safe_distance_side = safe_distance_side
        self.safe_distance_rear = safe_distance_rear
        self.gamma = gamma
        self.front_cbf = FrontCollisionCBF("FrontCBF", safe_distance=safe_distance_front, gamma=gamma)

    def evaluate_barriers(
        self,
        vehicle_speed: float,
        obstacle_distances: Dict[str, float],
    ) -> Dict[str, float]:
        """Evaluate Control Barrier Function h-values for each zone."""
        front_dist = obstacle_distances.get("front", 50.0)
        side_l_dist = obstacle_distances.get("side_left", 15.0)
        side_r_dist = obstacle_distances.get("side_right", 15.0)
        rear_dist = obstacle_distances.get("rear", 20.0)

        h_front = self.front_cbf.h({"front_distance": front_dist, "speed": vehicle_speed})
        h_side_left = side_l_dist - self.safe_distance_side
        h_side_right = side_r_dist - self.safe_distance_side
        h_rear = rear_dist - self.safe_distance_rear

        return {
            "h_front": h_front,
            "h_side_left": h_side_left,
            "h_side_right": h_side_right,
            "h_rear": h_rear,
        }

    def filter_control(
        self,
        vehicle_speed: float,
        nominal_accel: float,
        nominal_steering: float,
        obstacle_distances: Dict[str, float],
    ) -> Tuple[float, float, bool]:
        """Filter nominal acceleration and steering to enforce safety barrier constraints."""
        barriers = self.evaluate_barriers(vehicle_speed, obstacle_distances)
        safe_accel = nominal_accel
        safe_steering = nominal_steering
        was_modified = False

        if barriers["h_front"] < 0.0:
            max_safe_accel = -2.0 if vehicle_speed > 5.0 else -5.0
            if safe_accel > max_safe_accel:
                safe_accel = max_safe_accel
                was_modified = True

        if barriers["h_side_left"] < 0.0 and safe_steering > 0.0:
            safe_steering = 0.0
            was_modified = True

        if barriers["h_side_right"] < 0.0 and safe_steering < 0.0:
            safe_steering = 0.0
            was_modified = True

        if was_modified:
            self.set_status("CBF_ACTIVE")
        else:
            self.set_status("NOMINAL")

        self.increment_state_revision()
        return safe_accel, safe_steering, was_modified

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "safe_distance_front": self.safe_distance_front,
            "safe_distance_side": self.safe_distance_side,
            "safe_distance_rear": self.safe_distance_rear,
            "gamma": self.gamma,
        })
        return data


class AdaptiveCruiseControl(VehicleDomainEntity):
    """Adaptive Cruise Control (ACC) maintaining safe time-headway following distance."""

    def __init__(
        self,
        controller_id: str = "acc_1",
        target_speed: float = 25.0,
        time_gap: float = 1.8,
        min_distance: float = 4.0,
        kp_distance: float = 0.5,
        kp_speed: float = 0.8,
        max_acceleration: float = 2.5,
        max_deceleration: float = -4.0,
    ) -> None:
        super().__init__(
            entity_id=controller_id,
            entity_type="adaptive_cruise_control",
            position=[0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.target_speed: float = target_speed
        self.time_gap: float = time_gap
        self.min_distance: float = min_distance
        self.kp_distance: float = kp_distance
        self.kp_speed: float = kp_speed
        self.max_acceleration: float = max_acceleration
        self.max_deceleration: float = max_deceleration
        self.is_active: bool = True

    def enable(self) -> None:
        self.is_active = True
        self.set_status("ACC_ACTIVE")

    def disable(self) -> None:
        self.is_active = False
        self.set_status("NOMINAL")

    def set_target_speed(self, speed: float) -> None:
        self.target_speed = max(0.0, speed)
        self.increment_state_revision()

    def compute_acceleration(
        self,
        current_speed: float,
        lead_distance: Optional[float],
        lead_speed: Optional[float],
        dt: float,
    ) -> float:
        """Compute recommended acceleration to maintain target speed or safe following distance."""
        if not self.is_active:
            return 0.0

        if lead_distance is None or lead_distance >= 80.0:
            accel = self.kp_speed * (self.target_speed - current_speed)
        else:
            desired_distance = self.min_distance + current_speed * self.time_gap
            distance_error = lead_distance - desired_distance

            lead_v = lead_speed if lead_speed is not None else current_speed
            relative_speed = lead_v - current_speed

            accel = self.kp_distance * distance_error + self.kp_speed * relative_speed

        clamped_accel = max(self.max_deceleration, min(accel, self.max_acceleration))
        self.increment_state_revision()
        return clamped_accel

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "target_speed": self.target_speed,
            "time_gap": self.time_gap,
            "min_distance": self.min_distance,
            "is_active": self.is_active,
        })
        return data
