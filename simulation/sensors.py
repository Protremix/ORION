"""ORION Simulated Sensors (Phase 1 Cloud Simulation).

Provides simulated Camera, Lidar, IMU, and GPS sensor models that sample state
from a GridWorld instance and produce normative Observation contracts for the State Plane.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional

from simulation.grid_world import GridWorld, SimEntity
from src.contracts import (
    Envelope,
    Observation,
    current_monotonic_ns,
)


class SimulatedSensor:
    """Base class for all simulated sensors in ORION."""

    def __init__(
        self,
        sensor_id: str,
        sensor_type: str,
        sample_rate_hz: float = 10.0,
        noise_std: float = 0.01,
    ) -> None:
        """Initialize simulated sensor.

        Args:
            sensor_id: Unique string identifier for sensor.
            sensor_type: Type of sensor ("camera", "lidar", "imu", "gps").
            sample_rate_hz: Sampling frequency in Hz.
            noise_std: Standard deviation of Gaussian measurement noise.
        """
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self.sample_rate_hz = sample_rate_hz
        self.noise_std = noise_std
        self.last_sample_ns: int = 0

    def read(self, world: GridWorld, entity_id: str) -> Observation:
        """Sample world state and produce an Observation contract.

        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement read()")


class SimulatedGPS(SimulatedSensor):
    """Simulated GPS sensor providing global position measurements."""

    def __init__(
        self,
        sensor_id: str = "gps_primary",
        noise_std: float = 0.05,
    ) -> None:
        super().__init__(sensor_id=sensor_id, sensor_type="gps", noise_std=noise_std)

    def read(self, world: GridWorld, entity_id: str) -> Observation:
        now_ns = current_monotonic_ns()
        entity = world.entities.get(entity_id)

        if entity is None:
            raw_pos = [0.0, 0.0, 0.0]
        else:
            raw_pos = [
                entity.x + random.gauss(0, self.noise_std),
                entity.y + random.gauss(0, self.noise_std),
                0.0,
            ]

        processed_data = {
            "position": raw_pos,
            "hdop": 0.8,
            "num_satellites": 12,
        }
        return Observation(
            sensor_id=self.sensor_id,
            sensor_type="gps",
            raw_data={"gps_str": f"{raw_pos[0]:.4f},{raw_pos[1]:.4f}"},
            processed_data=processed_data,
            confidence=0.98,
            timestamp_sensor=now_ns,
            latency=1_000_000,  # 1ms
        )


class SimulatedIMU(SimulatedSensor):
    """Simulated IMU sensor providing acceleration, angular velocity, and orientation."""

    def __init__(
        self,
        sensor_id: str = "imu_primary",
        noise_std: float = 0.02,
    ) -> None:
        super().__init__(sensor_id=sensor_id, sensor_type="imu", noise_std=noise_std)

    def read(self, world: GridWorld, entity_id: str) -> Observation:
        now_ns = current_monotonic_ns()
        entity = world.entities.get(entity_id)

        if entity is None:
            vx, vy, ax, ay, heading, omega = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        else:
            vx = entity.vx + random.gauss(0, self.noise_std)
            vy = entity.vy + random.gauss(0, self.noise_std)
            ax = entity.ax + random.gauss(0, self.noise_std)
            ay = entity.ay + random.gauss(0, self.noise_std)
            heading = entity.heading + random.gauss(0, self.noise_std * 0.1)
            omega = entity.omega + random.gauss(0, self.noise_std)

        # Convert 2D heading to 3D quaternion [x, y, z, w]
        qz = math.sin(heading / 2.0)
        qw = math.cos(heading / 2.0)
        orientation = [0.0, 0.0, qz, qw]

        processed_data = {
            "linear_acceleration": [ax, ay, 9.81],
            "angular_velocity": [0.0, 0.0, omega],
            "velocity": [vx, vy, 0.0],
            "orientation": orientation,
        }
        return Observation(
            sensor_id=self.sensor_id,
            sensor_type="imu",
            raw_data={"accel": [ax, ay], "gyro": [0.0, 0.0, omega]},
            processed_data=processed_data,
            confidence=0.99,
            timestamp_sensor=now_ns,
            latency=500_000,  # 0.5ms
        )


class SimulatedLidar(SimulatedSensor):
    """Simulated 2D Lidar scanner performing raycasts against obstacles."""

    def __init__(
        self,
        sensor_id: str = "lidar_2d",
        num_beams: int = 36,
        max_range: float = 10.0,
        fov_rad: float = 2 * math.pi,
        noise_std: float = 0.01,
    ) -> None:
        super().__init__(sensor_id=sensor_id, sensor_type="lidar", noise_std=noise_std)
        self.num_beams = num_beams
        self.max_range = max_range
        self.fov_rad = fov_rad

    def read(self, world: GridWorld, entity_id: str) -> Observation:
        now_ns = current_monotonic_ns()
        entity = world.entities.get(entity_id)

        ranges: List[float] = []
        angles: List[float] = []

        if entity is not None:
            start_angle = entity.heading - (self.fov_rad / 2.0)
            angle_step = self.fov_rad / max(1, self.num_beams)

            for i in range(self.num_beams):
                angle = start_angle + i * angle_step
                angles.append(angle)

                # Raycast simulation step-by-step
                r = self.max_range
                for step in range(1, 100):
                    test_r = (step / 100.0) * self.max_range
                    rx = entity.x + test_r * math.cos(angle)
                    ry = entity.y + test_r * math.sin(angle)

                    collided, _ = world.check_collision(rx, ry, radius=0.01, ignore_entity_id=entity_id)
                    if collided:
                        r = test_r + random.gauss(0, self.noise_std)
                        break
                ranges.append(max(0.0, r))

        processed_data = {
            "num_beams": len(ranges),
            "ranges": ranges,
            "angles": angles,
            "min_range": min(ranges) if ranges else self.max_range,
            "max_range": self.max_range,
        }
        return Observation(
            sensor_id=self.sensor_id,
            sensor_type="lidar",
            raw_data={"beam_count": len(ranges)},
            processed_data=processed_data,
            confidence=0.96,
            timestamp_sensor=now_ns,
            latency=2_000_000,  # 2ms
        )


class SimulatedCamera(SimulatedSensor):
    """Simulated Camera sensor detecting visible objects and targets in visual FOV."""

    def __init__(
        self,
        sensor_id: str = "camera_front",
        fov_deg: float = 90.0,
        max_dist: float = 8.0,
        noise_std: float = 0.02,
    ) -> None:
        super().__init__(sensor_id=sensor_id, sensor_type="camera", noise_std=noise_std)
        self.fov_rad = math.radians(fov_deg)
        self.max_dist = max_dist

    def read(self, world: GridWorld, entity_id: str) -> Observation:
        now_ns = current_monotonic_ns()
        entity = world.entities.get(entity_id)

        detected_objects: List[Dict[str, Any]] = []

        if entity is not None:
            # Check obstacles in FOV
            for obs_id, obs in world.obstacles.items():
                if obs.obstacle_type == "circle":
                    ox = obs.params.get("x", 0.0)
                    oy = obs.params.get("y", 0.0)
                    dx, dy = ox - entity.x, oy - entity.y
                    dist = math.hypot(dx, dy)

                    if dist <= self.max_dist:
                        angle_to_obj = math.atan2(dy, dx)
                        angle_diff = math.atan2(
                            math.sin(angle_to_obj - entity.heading),
                            math.cos(angle_to_obj - entity.heading),
                        )
                        if abs(angle_diff) <= (self.fov_rad / 2.0):
                            detected_objects.append({
                                "id": obs_id,
                                "type": "obstacle",
                                "position": [ox + random.gauss(0, self.noise_std), oy + random.gauss(0, self.noise_std), 0.0],
                                "confidence": 0.95,
                            })

            # Check target objects
            for tgt_id, target_pos in world.targets.items():
                tx, ty = target_pos[0], target_pos[1]
                dx, dy = tx - entity.x, ty - entity.y
                dist = math.hypot(dx, dy)
                if dist <= self.max_dist:
                    angle_to_tgt = math.atan2(dy, dx)
                    angle_diff = math.atan2(
                        math.sin(angle_to_tgt - entity.heading),
                        math.cos(angle_to_tgt - entity.heading),
                    )
                    if abs(angle_diff) <= (self.fov_rad / 2.0):
                        detected_objects.append({
                            "id": tgt_id,
                            "type": "target",
                            "position": [tx, ty, 0.0],
                            "confidence": 0.99,
                        })

        processed_data = {
            "detected_objects": detected_objects,
            "object_count": len(detected_objects),
        }
        return Observation(
            sensor_id=self.sensor_id,
            sensor_type="camera",
            raw_data={"frame_id": random.randint(1000, 9999)},
            processed_data=processed_data,
            confidence=0.95,
            timestamp_sensor=now_ns,
            latency=5_000_000,  # 5ms
        )
