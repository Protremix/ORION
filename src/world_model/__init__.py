"""
ORION World Model — Master Spec §26 Phase 4

Physics simulation, future state prediction, and uncertainty quantification.
The World Model predicts how the environment changes given the current state
and a proposed action. This is critical for safe planning — actions are
validated against predicted outcomes before execution.

Architecture:
    CURRENT STATE + PROPOSED ACTION
        → PHYSICS SIMULATION (domain-specific)
        → PREDICTED FUTURE STATES (n steps ahead)
        → SAFETY ASSESSMENT (CBF check on predicted states)
        → UNCERTAINTY QUANTIFICATION
        → OUTPUT: WorldModelResponse

License: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# World Model Types
# ============================================================================

class PredictionConfidence(str, Enum):
    """Confidence level of a prediction."""
    HIGH = "high"        # < 10% uncertainty
    MEDIUM = "medium"    # 10-30% uncertainty
    LOW = "low"          # 30-60% uncertainty
    UNKNOWN = "unknown"  # > 60% uncertainty or no data


@dataclass
class StateSnapshot:
    """A snapshot of the environment at a point in time."""
    timestamp: float = field(default_factory=time.time)
    domain: str = "industrial"
    entities: Dict[str, Any] = field(default_factory=dict)
    sensors: Dict[str, Any] = field(default_factory=dict)
    safety_status: str = "safe"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "domain": self.domain,
            "entities": self.entities,
            "sensors": self.sensors,
            "safety_status": self.safety_status,
            "metadata": self.metadata,
        }


@dataclass
class PredictionResult:
    """Result of a world model prediction."""
    predicted_states: List[StateSnapshot] = field(default_factory=list)
    confidence: PredictionConfidence = PredictionConfidence.UNKNOWN
    uncertainty: float = 1.0  # 0.0 = certain, 1.0 = no idea
    safety_assessment: Optional[Dict[str, Any]] = None
    collision_risk: float = 0.0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "predicted_states": [s.to_dict() for s in self.predicted_states],
            "confidence": self.confidence.value,
            "uncertainty": self.uncertainty,
            "safety_assessment": self.safety_assessment,
            "collision_risk": self.collision_risk,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }


# ============================================================================
# Domain Physics Models
# ============================================================================

class IndustrialPhysics:
    """Physics model for industrial domain."""

    @staticmethod
    def predict(current: StateSnapshot, action: Dict[str, Any], steps: int = 1) -> List[StateSnapshot]:
        predictions = []
        state = dict(current.entities)

        for step in range(steps):
            new_state = dict(state)
            # Machine wear increases with operation
            for machine_id, machine_data in state.items():
                if isinstance(machine_data, dict):
                    wear = machine_data.get("wear", 0.0)
                    temp = machine_data.get("temperature", 20.0)
                    status = machine_data.get("status", "idle")

                    if status == "running":
                        wear += 0.001 * (1 + (temp - 20) / 100)
                        temp += 0.5

                    new_state[machine_id] = {
                        "wear": min(wear, 1.0),
                        "temperature": min(temp, 120.0),
                        "status": status,
                    }
            state = new_state
            predictions.append(StateSnapshot(
                domain="industrial",
                entities=dict(state),
                safety_status="safe" if all(
                    m.get("temperature", 0) < 100 for m in state.values() if isinstance(m, dict)
                ) else "warning",
            ))
        return predictions

    @staticmethod
    def check_safety(states: List[StateSnapshot]) -> Dict[str, Any]:
        violations = []
        for i, state in enumerate(states):
            for mid, mdata in state.entities.items():
                if isinstance(mdata, dict):
                    if mdata.get("temperature", 0) > 100:
                        violations.append(f"Step {i}: Machine {mid} overheating ({mdata['temperature']}°C)")
                    if mdata.get("wear", 0) > 0.9:
                        violations.append(f"Step {i}: Machine {mid} excessive wear ({mdata['wear']:.1%})")
        return {"safe": len(violations) == 0, "violations": violations}


class VehiclePhysics:
    """Physics model for vehicle domain."""

    @staticmethod
    def predict(current: StateSnapshot, action: Dict[str, Any], steps: int = 1) -> List[StateSnapshot]:
        predictions = []
        # Simple kinematic model
        x = current.entities.get("x", 0.0)
        y = current.entities.get("y", 0.0)
        vx = current.entities.get("vx", 0.0)
        vy = current.entities.get("vy", 0.0)
        dt = 0.1  # 100ms per step

        # Action: acceleration
        ax = action.get("acceleration_x", 0.0)
        ay = action.get("acceleration_y", 0.0)

        for step in range(steps):
            # Update velocity (with drag)
            vx = vx * 0.99 + ax * dt
            vy = vy * 0.99 + ay * dt

            # Speed limit
            speed = math.sqrt(vx**2 + vy**2)
            max_speed = action.get("max_speed", 30.0)
            if speed > max_speed:
                vx = (vx / speed) * max_speed
                vy = (vy / speed) * max_speed

            # Update position
            x += vx * dt
            y += vy * dt

            predictions.append(StateSnapshot(
                domain="vehicle",
                entities={"x": x, "y": y, "vx": vx, "vy": vy, "speed": math.sqrt(vx**2 + vy**2)},
                safety_status="safe" if speed < max_speed else "warning",
            ))
        return predictions

    @staticmethod
    def check_safety(states: List[StateSnapshot]) -> Dict[str, Any]:
        violations = []
        for i, state in enumerate(states):
            speed = state.entities.get("speed", 0)
            if speed > 35.0:
                violations.append(f"Step {i}: Speed {speed:.1f} exceeds limit")
        return {"safe": len(violations) == 0, "violations": violations}


class DronePhysics:
    """Physics model for drone domain."""

    @staticmethod
    def predict(current: StateSnapshot, action: Dict[str, Any], steps: int = 1) -> List[StateSnapshot]:
        predictions = []
        alt = current.entities.get("altitude", 50.0)
        vx = current.entities.get("vx", 0.0)
        vy = current.entities.get("vy", 0.0)
        vz = current.entities.get("vz", 0.0)
        battery = current.entities.get("battery", 100.0)
        dt = 0.1

        # Action: thrust, horizontal movement
        thrust = action.get("thrust", 0.0)
        target_vx = action.get("target_vx", 0.0)
        target_vy = action.get("target_vy", 0.0)

        for step in range(steps):
            # Simple dynamics
            vx = vx * 0.95 + target_vx * 0.05
            vy = vy * 0.95 + target_vy * 0.05
            vz = vz + (thrust - 9.8) * dt  # Gravity
            alt += vz * dt
            alt = max(0, alt)  # Can't go below ground

            # Battery drain
            power = abs(vx) + abs(vy) + abs(vz) + abs(thrust) * 0.1
            battery -= power * 0.001 * dt

            safe = alt > 5.0 and battery > 20.0
            predictions.append(StateSnapshot(
                domain="drone",
                entities={
                    "altitude": alt, "vx": vx, "vy": vy, "vz": vz,
                    "battery": max(0, battery),
                },
                safety_status="safe" if safe else "warning",
            ))
        return predictions

    @staticmethod
    def check_safety(states: List[StateSnapshot]) -> Dict[str, Any]:
        violations = []
        for i, state in enumerate(states):
            alt = state.entities.get("altitude", 100)
            batt = state.entities.get("battery", 100)
            if alt < 5.0:
                violations.append(f"Step {i}: Altitude {alt:.1f}m too low")
            if batt < 20.0:
                violations.append(f"Step {i}: Battery {batt:.1f}% critical")
        return {"safe": len(violations) == 0, "violations": violations}


class HomePhysics:
    """Physics model for smart home domain."""

    @staticmethod
    def predict(current: StateSnapshot, action: Dict[str, Any], steps: int = 1) -> List[StateSnapshot]:
        predictions = []
        temp = current.entities.get("temperature", 22.0)
        humidity = current.entities.get("humidity", 45.0)
        lights = current.entities.get("lights_on", False)
        doors_locked = current.entities.get("doors_locked", True)

        for step in range(steps):
            # Action effects
            if action.get("heating"):
                temp += 0.5
            elif action.get("cooling"):
                temp -= 0.5
            else:
                temp += (22.0 - temp) * 0.01  # Drift toward ambient

            if action.get("set_lights") is not None:
                lights = action["set_lights"]

            if action.get("lock_doors") is not None:
                doors_locked = action["lock_doors"]

            humidity += (45.0 - humidity) * 0.01

            safe = doors_locked and 15 < temp < 35
            predictions.append(StateSnapshot(
                domain="home",
                entities={
                    "temperature": temp, "humidity": humidity,
                    "lights_on": lights, "doors_locked": doors_locked,
                },
                safety_status="safe" if safe else "warning",
            ))
        return predictions

    @staticmethod
    def check_safety(states: List[StateSnapshot]) -> Dict[str, Any]:
        violations = []
        for i, state in enumerate(states):
            if not state.entities.get("doors_locked", True):
                violations.append(f"Step {i}: Doors unlocked")
            temp = state.entities.get("temperature", 22)
            if temp > 35 or temp < 15:
                violations.append(f"Step {i}: Temperature {temp:.1f}°C out of range")
        return {"safe": len(violations) == 0, "violations": violations}


# ============================================================================
# World Model
# ============================================================================

# Domain physics registry
_DOMAIN_PHYSICS: Dict[str, Any] = {
    "industrial": IndustrialPhysics,
    "vehicle": VehiclePhysics,
    "drone": DronePhysics,
    "home": HomePhysics,
}


class WorldModel:
    """
    ORION World Model — Master Spec §26 Phase 4.

    Predicts future states based on current state and proposed action.
    Uses domain-specific physics models for accurate prediction.

    The World Model is used by the Autonomous Planner to validate
    action sequences before execution (simulate-before-execute).
    """

    def __init__(self, default_domain: str = "industrial") -> None:
        self._default_domain = default_domain
        self._prediction_count = 0
        self._total_latency_ms = 0.0
        self._uncertainty_threshold = 0.6  # Above this = low confidence

    def predict(self, current_state: StateSnapshot,
                action: Dict[str, Any],
                horizon: int = 1,
                domain: Optional[str] = None) -> PredictionResult:
        """
        Predict future states given current state and action.

        Args:
            current_state: Current environment snapshot
            action: Proposed action (e.g., {"acceleration_x": 1.0})
            horizon: Number of steps to predict ahead
            domain: Override domain (defaults to state's domain)
        """
        start = time.time()
        dom = domain or current_state.domain or self._default_domain

        # Get domain physics model
        physics = _DOMAIN_PHYSICS.get(dom)
        if not physics:
            logger.warning(f"No physics model for domain '{dom}', using generic")
            return self._generic_predict(current_state, action, horizon)

        # Run physics simulation
        predicted_states = physics.predict(current_state, action, horizon)

        # Check safety of predicted states
        safety = physics.check_safety(predicted_states)

        # Calculate uncertainty (grows with horizon)
        base_uncertainty = 0.05
        uncertainty = min(1.0, base_uncertainty * (1 + 0.1 * horizon))

        # Determine confidence
        if uncertainty < 0.1:
            confidence = PredictionConfidence.HIGH
        elif uncertainty < 0.3:
            confidence = PredictionConfidence.MEDIUM
        elif uncertainty < 0.6:
            confidence = PredictionConfidence.LOW
        else:
            confidence = PredictionConfidence.UNKNOWN

        # Collision risk assessment
        collision_risk = 0.0
        if dom == "vehicle":
            for state in predicted_states:
                speed = state.entities.get("speed", 0)
                if speed > 30:
                    collision_risk += 0.1
        elif dom == "drone":
            for state in predicted_states:
                alt = state.entities.get("altitude", 100)
                if alt < 10:
                    collision_risk += 0.2

        latency = (time.time() - start) * 1000
        self._prediction_count += 1
        self._total_latency_ms += latency

        return PredictionResult(
            predicted_states=predicted_states,
            confidence=confidence,
            uncertainty=uncertainty,
            safety_assessment=safety,
            collision_risk=min(1.0, collision_risk),
            latency_ms=latency,
            metadata={
                "domain": dom,
                "horizon": horizon,
                "physics_model": physics.__name__,
            },
        )

    def _generic_predict(self, current: StateSnapshot, action: Dict[str, Any],
                         horizon: int) -> PredictionResult:
        """Fallback prediction when no domain physics model exists."""
        states = []
        for i in range(horizon):
            states.append(StateSnapshot(
                domain=current.domain,
                entities=dict(current.entities),
                safety_status="unknown",
            ))
        return PredictionResult(
            predicted_states=states,
            confidence=PredictionConfidence.UNKNOWN,
            uncertainty=0.9,
            safety_assessment={"safe": True, "violations": []},
            metadata={"note": "generic prediction, no domain physics"},
        )

    def batch_predict(self, current_state: StateSnapshot,
                      actions: List[Dict[str, Any]],
                      horizon: int = 1) -> List[PredictionResult]:
        """Predict outcomes for multiple candidate actions."""
        return [self.predict(current_state, action, horizon) for action in actions]

    def select_best_action(self, current_state: StateSnapshot,
                           candidate_actions: List[Dict[str, Any]],
                           horizon: int = 5) -> Tuple[Dict[str, Any], PredictionResult]:
        """
        Select the best action from candidates based on safety + confidence.

        Returns the action and its prediction result.
        Prefers: safe > low collision risk > low uncertainty.
        """
        results = self.batch_predict(current_state, candidate_actions, horizon)

        best_action = None
        best_result = None
        best_score = -1.0

        for action, result in zip(candidate_actions, results):
            if not result.safety_assessment or not result.safety_assessment.get("safe", False):
                continue  # Skip unsafe actions

            # Score: high confidence, low uncertainty, low collision risk
            score = (1.0 - result.uncertainty) * (1.0 - result.collision_risk)
            if score > best_score:
                best_score = score
                best_action = action
                best_result = result

        if best_action is None:
            # All actions unsafe — return first with lowest collision risk
            if results:
                safest_idx = min(range(len(results)), key=lambda i: results[i].collision_risk)
                return candidate_actions[safest_idx], results[safest_idx]
            return {}, PredictionResult()

        return best_action, best_result

    def get_statistics(self) -> Dict[str, Any]:
        """Get world model statistics."""
        avg_latency = self._total_latency_ms / max(1, self._prediction_count)
        return {
            "total_predictions": self._prediction_count,
            "avg_latency_ms": avg_latency,
            "supported_domains": list(_DOMAIN_PHYSICS.keys()),
        }
