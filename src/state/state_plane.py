"""ORION State Plane Implementation (Architecture v0.5).

The State Plane owns perception, world modeling, and state estimation.
It consumes raw/processed Observation contracts from sensors, fuses them, and produces
normative BeliefState contracts for the Cognitive Plane, Action Arbitration, and
Safety Enforcement. It also consumes ActionExecutionResult contracts to update state
following actuation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.contracts import (
    ActionExecutionResult,
    BeliefState,
    Observation,
    current_monotonic_ns,
)

logger = logging.getLogger(__name__)


class StatePlane:
    """State Plane class managing state estimation and perception fusion."""

    def __init__(
        self,
        initial_position: Optional[List[float]] = None,
        initial_orientation: Optional[List[float]] = None,
    ) -> None:
        """Initialize State Plane with baseline state estimates.

        Args:
            initial_position: Starting position vec3 [x, y, z] (default: [0.0, 0.0, 0.0]).
            initial_orientation: Starting orientation quat [x, y, z, w] (default: [0.0, 0.0, 0.0, 1.0]).
        """
        self._state_revision: int = 0
        self._position: List[float] = initial_position or [0.0, 0.0, 0.0]
        self._orientation: List[float] = initial_orientation or [0.0, 0.0, 0.0, 1.0]
        self._velocity: List[float] = [0.0, 0.0, 0.0]
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._sensor_last_seen: Dict[str, int] = {}
        self._sensor_health: Dict[str, str] = {}
        self._last_update_ns: int = current_monotonic_ns()

        # Variance/Covariance tracking
        self._position_variance = [0.01, 0.01, 0.01]
        self._orientation_variance = [0.01, 0.01, 0.01]

    @property
    def state_revision(self) -> int:
        return self._state_revision

    def process_observation(self, observation: Observation) -> BeliefState:
        """Process a single sensor observation and increment state revision."""
        return self.process_observations([observation])

    def process_observations(self, observations: List[Observation]) -> BeliefState:
        """Fuse a batch of sensor observations into an updated BeliefState.

        Args:
            observations: List of Observation contracts from sensors (Camera, Lidar, IMU, GPS).

        Returns:
            Updated normative BeliefState contract.
        """
        now_ns = current_monotonic_ns()

        for obs in observations:
            sensor_id = obs.sensor_id
            sensor_type = obs.sensor_type
            self._sensor_last_seen[sensor_id] = obs.timestamp_sensor

            # Assess sensor health
            staleness = now_ns - obs.timestamp_sensor
            if staleness < 1_000_000_000:  # < 1 second
                self._sensor_health[sensor_id] = "nominal"
            else:
                self._sensor_health[sensor_id] = "degraded"

            payload_data = obs.processed_data or {}
            if not payload_data and isinstance(obs.raw_data, dict):
                payload_data = obs.raw_data

            confidence = obs.confidence

            # Sensor-specific fusion logic
            if sensor_type == "gps":
                if "position" in payload_data:
                    p = payload_data["position"]
                    # Weighted blend based on confidence
                    alpha = min(0.9, max(0.1, confidence))
                    self._position[0] = (1 - alpha) * self._position[0] + alpha * p[0]
                    self._position[1] = (1 - alpha) * self._position[1] + alpha * p[1]
                    if len(p) > 2:
                        self._position[2] = (1 - alpha) * self._position[2] + alpha * p[2]

            elif sensor_type == "imu":
                if "velocity" in payload_data:
                    v = payload_data["velocity"]
                    self._velocity = [float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0]
                if "orientation" in payload_data:
                    o = payload_data["orientation"]
                    self._orientation = [float(o[i]) for i in range(min(4, len(o)))]

            elif sensor_type in ("camera", "lidar"):
                if "detected_objects" in payload_data:
                    for obj in payload_data["detected_objects"]:
                        obj_id = obj.get("id", f"obj_{len(self._objects)}")
                        self._objects[obj_id] = {
                            "id": obj_id,
                            "type": obj.get("type", "unknown"),
                            "position": obj.get("position", [0.0, 0.0, 0.0]),
                            "confidence": obj.get("confidence", confidence),
                            "last_seen_ns": now_ns,
                        }

        # Evict old objects (not seen in > 5 seconds)
        expired_keys = [
            k for k, v in self._objects.items() if (now_ns - v["last_seen_ns"]) > 5_000_000_000
        ]
        for k in expired_keys:
            del self._objects[k]

        self._state_revision += 1
        self._last_update_ns = now_ns

        return self.get_current_belief_state()

    def update_from_execution_result(self, result: ActionExecutionResult) -> BeliefState:
        """Update state estimate based on reported ActionExecutionResult from Control Plane.

        Args:
            result: ActionExecutionResult contract from control plane execution.

        Returns:
            Updated normative BeliefState contract.
        """
        now_ns = current_monotonic_ns()
        final_state = result.final_state

        if "position" in final_state:
            pos = final_state["position"]
            self._position = [float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0]

        if "velocity" in final_state:
            vel = final_state["velocity"]
            self._velocity = [float(vel[0]), float(vel[1]), float(vel[2]) if len(vel) > 2 else 0.0]

        if "orientation" in final_state:
            ori = final_state["orientation"]
            self._orientation = [float(ori[i]) for i in range(min(4, len(ori)))]

        self._state_revision += 1
        self._last_update_ns = now_ns

        logger.info(f"StatePlane updated revision to {self._state_revision} from execution result: {result.result}")
        return self.get_current_belief_state()

    def get_current_belief_state(self) -> BeliefState:
        """Construct and return the current BeliefState contract."""
        now_ns = current_monotonic_ns()
        staleness = now_ns - self._last_update_ns
        obj_list = list(self._objects.values())

        uncertainty = {
            "position_covariance": [
                [self._position_variance[0], 0.0, 0.0],
                [0.0, self._position_variance[1], 0.0],
                [0.0, 0.0, self._position_variance[2]],
            ],
            "orientation_covariance": [
                [self._orientation_variance[0], 0.0, 0.0],
                [0.0, self._orientation_variance[1], 0.0],
                [0.0, 0.0, self._orientation_variance[2]],
            ],
            "classification_confidence": 0.95,
        }

        return BeliefState(
            state_revision=self._state_revision,
            position=list(self._position),
            orientation=list(self._orientation),
            velocity=list(self._velocity),
            objects=obj_list,
            uncertainty=uncertainty,
            staleness=staleness,
            sensor_health=dict(self._sensor_health),
        )
