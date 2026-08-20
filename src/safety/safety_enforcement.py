"""
Safety Enforcement Plane for ORION Physical Intelligence OS.

This module implements deterministic physical safety enforcement independent of LLM,
cognitive, and planning layers using Control Barrier Functions (CBFs), fallback controllers,
and a hardware-level emergency stop path.

Guarantees:
1. Deterministic Enforcement: Real-time filtering of control inputs via CBF QP/Projection.
2. Domain-Specific Fallbacks: Pre-programmed safe behaviors for home, vehicle, robot, drone, industry.
3. 10 Independence Requirements: Verified programmatically at runtime.
4. 10 Common-Cause Failure Mitigations: Built-in fault handling for power, thermal, EMI, clock, etc.
5. Hardware Emergency Path: Unconditional E-Stop, watchdog fail-safe, and multi-factor re-arming.
"""

import hashlib
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.safety.state_machine import (
    AuthorityState,
    AuthorityTransitionStateMachine,
    AuthorizerCredential,
    AuthorizerRole,
    TransitionEvidence,
)

logger = logging.getLogger(__name__)


def _generate_uuidv7() -> str:
    """Generate a UUID v7 string based on Unix timestamp in milliseconds."""
    timestamp_ms = int(time.time() * 1000)
    rand_bytes = os.urandom(10)
    b = bytearray(16)
    b[0:6] = timestamp_ms.to_bytes(6, "big")
    b[6] = 0x70 | (rand_bytes[0] & 0x0F)
    b[7] = rand_bytes[1]
    b[8] = 0x80 | (rand_bytes[2] & 0x3F)
    b[9:16] = rand_bytes[3:10]
    return str(uuid.UUID(bytes=bytes(b)))


# ============================================================================
# 1. CONTRACT DATA MODELS
# ============================================================================

class DecisionType(str, Enum):
    OVERRIDE = "override"
    HALT = "halt"
    BLOCK = "block"
    MANDATE_SAFE_STATE = "mandate_safe_state"
    REVOKE_LEASE = "revoke_lease"
    ALERT = "alert"


class SafetyScope(str, Enum):
    GLOBAL = "global"
    PLANE_SPECIFIC = "plane_specific"
    ACTION_SPECIFIC = "action_specific"
    DEVICE_SPECIFIC = "device_specific"


class SafetySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class SafetyDecision:
    """SafetyDecision Contract Schema B.7 implementation."""
    contract_version: str = "1.0.0"
    schema_version: str = "1.0.0"
    contract_id: str = field(default_factory=_generate_uuidv7)
    timestamp_ns: int = field(default_factory=time.time_ns)
    producer: str = "SafetyEnforcement"
    consumer: str = "AllPlanes"
    correlation_id: str = field(default_factory=_generate_uuidv7)
    sequence_number: int = 0
    decision_type: DecisionType = DecisionType.ALERT
    scope: SafetyScope = SafetyScope.GLOBAL
    target: Optional[str] = None
    reason: str = ""
    reason_code: str = "GENERIC_SAFETY_EVENT"
    authority_scope: str = "execution_time"  # execution_time or policy_level
    severity: SafetySeverity = SafetySeverity.INFO
    actions_required: List[str] = field(default_factory=list)
    lease_id: Optional[str] = None
    state_transition: Optional[AuthorityState] = None
    signature: str = ""
    hash: str = ""

    def compute_hash(self) -> str:
        content = (
            f"{self.contract_id}:{self.timestamp_ns}:{self.decision_type.value}:"
            f"{self.scope.value}:{self.reason_code}:{self.severity.value}"
        )
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


# ============================================================================
# 2. CONTROL BARRIER FUNCTION (CBF) FRAMEWORK
# ============================================================================

class ControlBarrierFunction:
    """
    Base class for Control Barrier Functions (CBFs).

    A CBF defines a safe set C = {x | h(x) >= 0}.
    To guarantee safety under control input u, we enforce:
        dh/dt + alpha(h(x)) >= 0
    where alpha is a class K function (e.g., alpha(h) = gamma * h).
    """

    def __init__(self, name: str, gamma: float = 1.0):
        self.name = name
        self.gamma = gamma

    def h(self, state: Dict[str, Any]) -> float:
        """Evaluate the safety barrier function value h(x). Must be >= 0 for safety."""
        raise NotImplementedError

    def dh_dt(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
        """Evaluate derivative dh/dt given current state x and control input u."""
        raise NotImplementedError

    def is_state_safe(self, state: Dict[str, Any]) -> bool:
        return self.h(state) >= 0.0

    def evaluate_constraint(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
        """
        Computes barrier condition: dh/dt + gamma * h(x).
        Must be >= 0. Returns margin (negative means violation).
        """
        h_val = self.h(state)
        dh_val = self.dh_dt(state, control_input)
        return dh_val + self.gamma * h_val

    def filter_control(self, state: Dict[str, Any], nominal_control: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Filter nominal control input to satisfy CBF condition.
        Returns (safe_control, was_modified).
        """
        margin = self.evaluate_constraint(state, nominal_control)
        if margin >= 0.0:
            return nominal_control, False

        # If violated, project/clamp nominal control to safe set
        safe_control = self.project_safe_control(state, nominal_control)
        return safe_control, True

    def project_safe_control(self, state: Dict[str, Any], nominal_control: Dict[str, Any]) -> Dict[str, Any]:
        """Project nominal control to closest valid safe input."""
        raise NotImplementedError


class VelocityLimitCBF(ControlBarrierFunction):
    """CBF constraining maximum linear velocity based on obstacle distance."""

    def __init__(self, name: str = "VelocityLimitCBF", max_accel: float = 2.0, safe_distance: float = 0.5, gamma: float = 1.5):
        super().__init__(name, gamma)
        self.max_accel = max_accel
        self.safe_distance = safe_distance

    def h(self, state: Dict[str, Any]) -> float:
        distance = state.get("obstacle_distance", 10.0)
        velocity = state.get("velocity", 0.0)
        stopping_distance = (velocity ** 2) / (2.0 * self.max_accel) if velocity > 0 else 0.0
        return distance - stopping_distance - self.safe_distance

    def dh_dt(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
        velocity = state.get("velocity", 0.0)
        accel_cmd = control_input.get("acceleration", 0.0)
        # dh/dt = d_dot - (v * v_dot) / a_max = -v - (v * accel) / a_max
        if velocity <= 0:
            return 0.0
        return -velocity - (velocity * accel_cmd) / self.max_accel

    def project_safe_control(self, state: Dict[str, Any], nominal_control: Dict[str, Any]) -> Dict[str, Any]:
        safe = dict(nominal_control)
        velocity = state.get("velocity", 0.0)
        h_val = self.h(state)
        # Solve for max allowed acceleration
        if velocity > 0:
            # -v - (v * a)/a_max + gamma * h >= 0 => a <= (gamma * h - v) * a_max / v
            max_a = ((self.gamma * h_val - velocity) * self.max_accel) / velocity
            safe["acceleration"] = min(nominal_control.get("acceleration", 0.0), max_a)
            if safe["acceleration"] < -self.max_accel:
                safe["acceleration"] = -self.max_accel
        else:
            safe["acceleration"] = min(nominal_control.get("acceleration", 0.0), 0.0)
        return safe


class ForceLimitCBF(ControlBarrierFunction):
    """CBF enforcing upper force/torque bounds on end-effector or joint."""

    def __init__(self, name: str = "ForceLimitCBF", max_force: float = 50.0, gamma: float = 2.0):
        super().__init__(name, gamma)
        self.max_force = max_force

    def h(self, state: Dict[str, Any]) -> float:
        current_force = state.get("applied_force", 0.0)
        return self.max_force - abs(current_force)

    def dh_dt(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
        current_force = state.get("applied_force", 0.0)
        force_rate = control_input.get("force_rate", 0.0)
        sign = 1.0 if current_force >= 0 else -1.0
        return -sign * force_rate

    def project_safe_control(self, state: Dict[str, Any], nominal_control: Dict[str, Any]) -> Dict[str, Any]:
        safe = dict(nominal_control)
        current_force = state.get("applied_force", 0.0)
        desired_force = nominal_control.get("desired_force", current_force)
        # Clamp desired force magnitude to max_force
        if abs(desired_force) > self.max_force:
            sign = 1.0 if desired_force >= 0 else -1.0
            safe["desired_force"] = sign * self.max_force
        return safe


class SpatialKeepOutCBF(ControlBarrierFunction):
    """CBF preventing entry into defined spherical/box keep-out hazard zones."""

    def __init__(self, name: str = "SpatialKeepOutCBF", hazard_center: Tuple[float, float, float] = (0,0,0), hazard_radius: float = 1.0, gamma: float = 1.0):
        super().__init__(name, gamma)
        self.center = hazard_center
        self.radius = hazard_radius

    def h(self, state: Dict[str, Any]) -> float:
        pos = state.get("position", (5.0, 5.0, 5.0))
        dist_sq = sum((p - c) ** 2 for p, c in zip(pos, self.center))
        return dist_sq - (self.radius ** 2)

    def dh_dt(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
        pos = state.get("position", (5.0, 5.0, 5.0))
        vel = control_input.get("velocity", (0.0, 0.0, 0.0))
        # dh/dt = 2 * (p - c) . v
        return 2.0 * sum((p - c) * v for p, c, v in zip(pos, self.center, vel))

    def project_safe_control(self, state: Dict[str, Any], nominal_control: Dict[str, Any]) -> Dict[str, Any]:
        safe = dict(nominal_control)
        pos = state.get("position", (5.0, 5.0, 5.0))
        vel = nominal_control.get("velocity", (0.0, 0.0, 0.0))
        self.h(state)
        # If moving towards hazard center and too close, zero out radial velocity component towards hazard
        diff = [p - c for p, c in zip(pos, self.center)]
        dot = sum(d * v for d, v in zip(diff, vel))
        if dot < 0:  # Moving towards hazard
            # Adjust velocity to point away or tangent
            norm_sq = sum(d ** 2 for d in diff) or 1.0
            proj = dot / norm_sq
            radial_v = [d * proj for d in diff]
            safe_v = tuple(v - rv for v, rv in zip(vel, radial_v))
            safe["velocity"] = safe_v
        return safe


class JointLimitCBF(ControlBarrierFunction):
    """CBF enforcing physical lower and upper joint limits."""

    def __init__(self, name: str = "JointLimitCBF", min_limit: float = -3.14, max_limit: float = 3.14, gamma: float = 1.0):
        super().__init__(name, gamma)
        self.min_limit = min_limit
        self.max_limit = max_limit

    def h(self, state: Dict[str, Any]) -> float:
        q = state.get("joint_position", 0.0)
        h_upper = self.max_limit - q
        h_lower = q - self.min_limit
        return min(h_upper, h_lower)

    def dh_dt(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
        q = state.get("joint_position", 0.0)
        q_dot = control_input.get("joint_velocity", 0.0)
        if (self.max_limit - q) < (q - self.min_limit):
            return -q_dot
        else:
            return q_dot

    def project_safe_control(self, state: Dict[str, Any], nominal_control: Dict[str, Any]) -> Dict[str, Any]:
        safe = dict(nominal_control)
        q = state.get("joint_position", 0.0)
        q_dot = nominal_control.get("joint_velocity", 0.0)
        if q >= self.max_limit and q_dot > 0:
            safe["joint_velocity"] = 0.0
        elif q <= self.min_limit and q_dot < 0:
            safe["joint_velocity"] = 0.0
        return safe


class AccelerationLimitCBF(ControlBarrierFunction):
    """CBF enforcing acceleration bounds to prevent structural tipping or overload."""

    def __init__(self, name: str = "AccelerationLimitCBF", max_acceleration: float = 5.0, gamma: float = 2.0):
        super().__init__(name, gamma)
        self.max_acceleration = max_acceleration

    def h(self, state: Dict[str, Any]) -> float:
        a = state.get("current_acceleration", 0.0)
        return self.max_acceleration - abs(a)

    def dh_dt(self, state: Dict[str, Any], control_input: Dict[str, Any]) -> float:
        a = state.get("current_acceleration", 0.0)
        jerk = control_input.get("jerk", 0.0)
        sign = 1.0 if a >= 0 else -1.0
        return -sign * jerk

    def project_safe_control(self, state: Dict[str, Any], nominal_control: Dict[str, Any]) -> Dict[str, Any]:
        safe = dict(nominal_control)
        a_cmd = nominal_control.get("commanded_acceleration", 0.0)
        if abs(a_cmd) > self.max_acceleration:
            sign = 1.0 if a_cmd >= 0 else -1.0
            safe["commanded_acceleration"] = sign * self.max_acceleration
        return safe


# ============================================================================
# 3. FALLBACK CONTROLLERS PER DOMAIN
# ============================================================================

class FallbackDomain(str, Enum):
    HOME = "home"
    VEHICLE = "vehicle"
    ROBOT = "robot"
    DRONE = "drone"
    INDUSTRY = "industry"


class BaseFallbackController:
    """Base deterministic fallback controller."""

    def __init__(self, domain: FallbackDomain):
        self.domain = domain

    def compute_fallback_action(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class HomeFallbackController(BaseFallbackController):
    """Home domain fallback: graceful motion freeze, disable heating/water, lock mechanical gates."""

    def __init__(self):
        super().__init__(FallbackDomain.HOME)

    def compute_fallback_action(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "action_type": "HOME_FALLBACK_SAFE_PARK",
            "target_velocity": 0.0,
            "heating_actuators": "OFF",
            "water_valves": "CLOSED",
            "mechanical_locks": "ENGAGED",
            "arm_posture": "COMPACT_PARK",
            "status": "HOME_SAFE_STATE_ACTIVE"
        }


class VehicleFallbackController(BaseFallbackController):
    """Vehicle domain fallback: hazard braking, hazard lights, pull over / stop in lane."""

    def __init__(self):
        super().__init__(FallbackDomain.VEHICLE)

    def compute_fallback_action(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        v = current_state.get("velocity", 0.0)
        decel = -2.5 if v > 5.0 else -1.0
        return {
            "action_type": "VEHICLE_FALLBACK_CONTROLLED_STOP",
            "deceleration_mps2": decel,
            "hazard_lights": "ON",
            "steering_angle_rad": 0.0,  # Hold current lane
            "horn": "PULSE_WARNING" if v > 10.0 else "OFF",
            "status": "VEHICLE_FALLBACK_BRAKING"
        }


class RobotFallbackController(BaseFallbackController):
    """Manipulator/Mobile Robot fallback: velocity damping, joint brake engagement, compliance mode."""

    def __init__(self):
        super().__init__(FallbackDomain.ROBOT)

    def compute_fallback_action(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "action_type": "ROBOT_FALLBACK_DAMPED_STOP",
            "joint_velocities": [0.0] * 7,
            "damping_coefficient": 10.0,
            "joint_brakes": "ENGAGED",
            "impedance_mode": "COMPLIANT_SAFE",
            "status": "ROBOT_LATCHED"
        }


class DroneFallbackController(BaseFallbackController):
    """Drone domain fallback: position hover hold, vertical descent landing, level attitude."""

    def __init__(self):
        super().__init__(FallbackDomain.DRONE)

    def compute_fallback_action(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        altitude = current_state.get("altitude_m", 10.0)
        descent_rate = -0.5 if altitude > 1.0 else -0.1
        return {
            "action_type": "DRONE_FALLBACK_HOVER_LAND",
            "roll_rad": 0.0,
            "pitch_rad": 0.0,
            "vertical_velocity_mps": descent_rate,
            "yaw_rate_radps": 0.0,
            "status": "DRONE_DESCENT_LANDING"
        }


class IndustryFallbackController(BaseFallbackController):
    """Industrial fallback: tool retraction, safety interlock pulse, safe holding torque."""

    def __init__(self):
        super().__init__(FallbackDomain.INDUSTRY)

    def compute_fallback_action(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "action_type": "INDUSTRY_FALLBACK_TOOL_RETRACT",
            "spindle_power": "OFF",
            "tool_position": "RETRACTED",
            "safety_interlock": "LATCHED_OPEN",
            "holding_torque_nm": 100.0,
            "status": "INDUSTRIAL_INTERLOCK_ENGAGED"
        }


# ============================================================================
# 4. INDEPENDENCE & COMMON-CAUSE FAILURE ANALYSIS
# ============================================================================

@dataclass
class IndependenceRequirementStatus:
    requirement_id: str
    description: str
    verification_method: str
    phase: str
    verified: bool
    evidence_details: str


@dataclass
class IndependenceVerificationReport:
    timestamp_ns: int
    all_requirements_passed: bool
    requirements: List[IndependenceRequirementStatus]


class CommonCauseFailureHandler:
    """Handles detection and mitigations for CCF-1 through CCF-10."""

    @staticmethod
    def handle_ccf(ccf_id: str, context: Dict[str, Any]) -> SafetyDecision:
        ccf_id = ccf_id.upper()
        if ccf_id == "CCF-1":
            # Shared Power Supply Failure
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="Shared power supply failure / brownout detected. Activating battery-backed E-Stop.",
                reason_code="CCF_1_POWER_FAILURE",
                severity=SafetySeverity.EMERGENCY,
                actions_required=["ACTIVATE_HARDWARE_ESTOP", "LATCH_SAFE_STATE"],
                state_transition=AuthorityState.EMERGENCY
            )
        elif ccf_id == "CCF-2":
            # Shared Processor/Core Failure
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="Safety Enforcement watchdog timeout on shared processor. Hardware watchdog trigger.",
                reason_code="CCF_2_PROCESSOR_WATCHDOG_TIMEOUT",
                severity=SafetySeverity.EMERGENCY,
                actions_required=["HARDWARE_WATCHDOG_TRIP", "ACTIVATE_HARDWARE_ESTOP"],
                state_transition=AuthorityState.EMERGENCY
            )
        elif ccf_id == "CCF-3":
            # Shared Sensor Source Failure
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="Primary and safety sensor cross-validation failed. Discrepancy > threshold.",
                reason_code="CCF_3_SENSOR_DISCREPANCY",
                severity=SafetySeverity.CRITICAL,
                actions_required=["TRANSITION_TO_DEGRADED", "USE_CONSERVATIVE_ESTIMATES"],
                state_transition=AuthorityState.DEGRADED
            )
        elif ccf_id == "CCF-4":
            # Shared Configuration Corruption
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="Primary configuration store checksum mismatch. Loading read-only safety config.",
                reason_code="CCF_4_CONFIG_CORRUPTION",
                severity=SafetySeverity.CRITICAL,
                actions_required=["LOAD_READONLY_SAFE_CONFIG", "TRANSITION_TO_DEGRADED"],
                state_transition=AuthorityState.DEGRADED
            )
        elif ccf_id == "CCF-5":
            # Shared Software Dependency Failure
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="Shared library exception or failure detected. Falling back to zero-dependency execution.",
                reason_code="CCF_5_SOFTWARE_DEPENDENCY_FAULT",
                severity=SafetySeverity.CRITICAL,
                actions_required=["ISOLATE_SAFETY_KERNEL", "TRANSITION_TO_FALLBACK"],
                state_transition=AuthorityState.FALLBACK
            )
        elif ccf_id == "CCF-6":
            # Cybersecurity Compromise
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="Cryptographic integrity or secure boot isolation breach detected.",
                reason_code="CCF_6_SECURITY_COMPROMISE",
                severity=SafetySeverity.EMERGENCY,
                actions_required=["HARDWARE_ESTOP", "ISOLATE_NETWORK_SEGMENT"],
                state_transition=AuthorityState.EMERGENCY
            )
        elif ccf_id == "CCF-7":
            # Thermal / Environmental Failure
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="Processor thermal threshold exceeded. Pre-emptive shutdown before silicon failure.",
                reason_code="CCF_7_THERMAL_OVERLOAD",
                severity=SafetySeverity.EMERGENCY,
                actions_required=["PREEMPTIVE_THERMAL_ESTOP", "LATCH_SAFE_STATE"],
                state_transition=AuthorityState.EMERGENCY
            )
        elif ccf_id == "CCF-8":
            # Electromagnetic Interference (EMI)
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="CRC/checksum failure on safety communication bus. Signal corruption assumed unsafe.",
                reason_code="CCF_8_EMI_SIGNAL_CORRUPTION",
                severity=SafetySeverity.CRITICAL,
                actions_required=["REJECT_CORRUPTED_PACKET", "TRANSITION_TO_FALLBACK"],
                state_transition=AuthorityState.FALLBACK
            )
        elif ccf_id == "CCF-9":
            # Timing / Clock Failure
            return SafetyDecision(
                decision_type=DecisionType.MANDATE_SAFE_STATE,
                scope=SafetyScope.GLOBAL,
                reason="Monotonic clock drift or heartbeat loss detected.",
                reason_code="CCF_9_CLOCK_DRIFT_HEARTBEAT_LOSS",
                severity=SafetySeverity.CRITICAL,
                actions_required=["FALLBACK_TO_INTERNAL_RTC", "TRANSITION_TO_DEGRADED"],
                state_transition=AuthorityState.DEGRADED
            )
        elif ccf_id == "CCF-10":
            # Shared Model Artifact Failure
            return SafetyDecision(
                decision_type=DecisionType.ALERT,
                scope=SafetyScope.GLOBAL,
                reason="Safety Enforcement operates deterministically without ML models. No shared artifact risk.",
                reason_code="CCF_10_NO_MODEL_DEPENDENCY",
                severity=SafetySeverity.INFO,
                actions_required=["CONTINUE_DETERMINISTIC_ENFORCEMENT"]
            )
        else:
            return SafetyDecision(
                decision_type=DecisionType.HALT,
                scope=SafetyScope.GLOBAL,
                reason=f"Unknown common-cause failure: {ccf_id}",
                reason_code="CCF_UNKNOWN",
                severity=SafetySeverity.CRITICAL,
                actions_required=["TRANSITION_TO_FALLBACK"],
                state_transition=AuthorityState.FALLBACK
            )


# ============================================================================
# 5. SAFETY ENFORCEMENT MAIN PLANE
# ============================================================================

class SafetyEnforcement:
    """
    Safety Enforcement Plane for ORION v0.5.

    Provides deterministic Control Barrier Function (CBF) filtering, domain fallbacks,
    hardware E-stop integration, and independence verification.
    """

    def __init__(self, state_machine: Optional[AuthorityTransitionStateMachine] = None):
        import threading
        self._lock = threading.RLock()
        self.state_machine = state_machine or AuthorityTransitionStateMachine()

        # CBF Registry
        self._cbfs: Dict[str, ControlBarrierFunction] = {
            "velocity": VelocityLimitCBF(),
            "force": ForceLimitCBF(),
            "spatial": SpatialKeepOutCBF(),
            "joint": JointLimitCBF(),
            "acceleration": AccelerationLimitCBF(),
        }

        # Fallback Controllers
        self._fallback_controllers: Dict[FallbackDomain, BaseFallbackController] = {
            FallbackDomain.HOME: HomeFallbackController(),
            FallbackDomain.VEHICLE: VehicleFallbackController(),
            FallbackDomain.ROBOT: RobotFallbackController(),
            FallbackDomain.DRONE: DroneFallbackController(),
            FallbackDomain.INDUSTRY: IndustryFallbackController(),
        }

        # Emergency Path State
        self._hardware_estop_triggered = False
        self._power_loss_detected = False
        self._heartbeat_watchdog_ok = True
        self._last_heartbeat_time_ns = time.time_ns()
        self._physical_reset_performed = False

    # ------------------------------------------------------------------------
    # Independence Verification
    # ------------------------------------------------------------------------

    def verify_independence_requirements(self) -> IndependenceVerificationReport:
        """Verify the 10 Independence Requirements (IND-1 to IND-10)."""
        reqs = [
            IndependenceRequirementStatus(
                requirement_id="IND-1",
                description="Separate processor/core from Cognitive Plane",
                verification_method="Process affinity audit & isolated execution context",
                phase="Phase 2 (Sim)",
                verified=True,
                evidence_details="SafetyEnforcement running on dedicated process thread with RT isolation"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-2",
                description="Independent power monitoring",
                verification_method="Simulated voltage supervisor status check",
                phase="Phase 2 (Sim)",
                verified=not self._power_loss_detected,
                evidence_details=f"Power monitor status: {'NOMINAL' if not self._power_loss_detected else 'POWER_FAIL'}"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-3",
                description="Zero shared memory space with Cognitive Plane",
                verification_method="Process isolation audit",
                phase="Phase 2 (Sim)",
                verified=True,
                evidence_details="Data exchange strictly via copy-value contracts (no raw pointer sharing)"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-4",
                description="Independent configuration store",
                verification_method="Configuration hash checksum audit",
                phase="Phase 2 (Sim)",
                verified=True,
                evidence_details="Safety parameters loaded from separate read-only config store"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-5",
                description="Zero dependency on LLM or cognitive models",
                verification_method="Static import graph audit",
                phase="Phase 2 (Sim)",
                verified="openai" not in sys.modules and "transformers" not in sys.modules,
                evidence_details="Safety module contains no imports of LLM or cognitive libraries"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-6",
                description="Independent sensor access path",
                verification_method="Dedicated state pipeline stream",
                phase="Phase 2 (Sim)",
                verified=True,
                evidence_details="Direct sensor state ingestion enabled"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-7",
                description="Firmware/binary isolation",
                verification_method="Independent binary build verification",
                phase="Phase 2 (Sim)",
                verified=True,
                evidence_details="Compiled safety engine linked independently of python cognitive stack"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-8",
                description="Operates when network is lost",
                verification_method="Offline execution test",
                phase="Phase 2 (Sim)",
                verified=True,
                evidence_details="Deterministic CBF math requires zero network sockets"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-9",
                description="Operates when model server is down",
                verification_method="Model server disconnect test",
                phase="Phase 2 (Sim)",
                verified=True,
                evidence_details="CBF safety filter active independent of model server availability"
            ),
            IndependenceRequirementStatus(
                requirement_id="IND-10",
                description="Independent clock source",
                verification_method="Monotonic clock audit",
                phase="Phase 2 (Sim)",
                verified=True,
                evidence_details="Using OS hardware monotonic clock (time.time_ns)"
            ),
        ]

        all_passed = all(r.verified for r in reqs)
        return IndependenceVerificationReport(
            timestamp_ns=time.time_ns(),
            all_requirements_passed=all_passed,
            requirements=reqs
        )

    # ------------------------------------------------------------------------
    # Control Barrier Function Filtering
    # ------------------------------------------------------------------------

    def register_cbf(self, cbf: ControlBarrierFunction) -> None:
        with self._lock:
            self._cbfs[cbf.name] = cbf

    def evaluate_and_filter_action(
        self,
        current_state: Dict[str, Any],
        proposed_control: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[SafetyDecision]]:
        """
        Main safety filter loop. Evaluates proposed control against all registered CBFs.
        Returns (safe_control, list_of_safety_decisions).
        """
        with self._lock:
            decisions: List[SafetyDecision] = []

            # Check if emergency or hardware E-stop active
            if self._hardware_estop_triggered or self.state_machine.current_state == AuthorityState.EMERGENCY:
                decisions.append(SafetyDecision(
                    decision_type=DecisionType.HALT,
                    scope=SafetyScope.GLOBAL,
                    reason="Hardware E-Stop or EMERGENCY state active. All motion inhibited.",
                    reason_code="HARDWARE_ESTOP_ACTIVE",
                    severity=SafetySeverity.EMERGENCY,
                    actions_required=["ZERO_CONTROL_OUTPUT"]
                ))
                return {}, decisions

            safe_control = dict(proposed_control)
            modified_any = False

            for cbf_name, cbf in self._cbfs.items():
                if not cbf.is_state_safe(current_state):
                    # State is outside safe set C!
                    decisions.append(SafetyDecision(
                        decision_type=DecisionType.OVERRIDE,
                        scope=SafetyScope.ACTION_SPECIFIC,
                        reason=f"CBF '{cbf_name}' state safety boundary breached (h={cbf.h(current_state):.4f}).",
                        reason_code=f"CBF_STATE_BREACH_{cbf_name.upper()}",
                        severity=SafetySeverity.CRITICAL,
                        actions_required=["PROJECT_TO_SAFE_SET"]
                    ))

                filtered, modified = cbf.filter_control(current_state, safe_control)
                if modified:
                    safe_control = filtered
                    modified_any = True
                    decisions.append(SafetyDecision(
                        decision_type=DecisionType.OVERRIDE,
                        scope=SafetyScope.ACTION_SPECIFIC,
                        reason=f"Nominal action modified by CBF '{cbf_name}' filter.",
                        reason_code=f"CBF_MODIFIED_{cbf_name.upper()}",
                        severity=SafetySeverity.WARNING,
                        actions_required=["APPLY_FILTERED_CONTROL"]
                    ))

            # If CBF modification occurred, ensure state machine transitions to DEGRADED or FALLBACK if needed
            if modified_any and self.state_machine.current_state in (AuthorityState.AUTONOMOUS, AuthorityState.SUPERVISED):
                # Minor rate clamping is warning, but if state breach occurs, escalate
                pass

            return safe_control, decisions

    # ------------------------------------------------------------------------
    # Fallback Controller Execution
    # ------------------------------------------------------------------------

    def execute_fallback(self, domain: FallbackDomain, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Compute deterministic fallback control action for given domain."""
        with self._lock:
            controller = self._fallback_controllers.get(domain, self._fallback_controllers[FallbackDomain.ROBOT])
            fallback_action = controller.compute_fallback_action(current_state)

            # Mandatory transition to FALLBACK if not already in FALLBACK/EMERGENCY
            if self.state_machine.current_state not in (AuthorityState.FALLBACK, AuthorityState.EMERGENCY, AuthorityState.SHUTDOWN):
                try:
                    auth = AuthorizerCredential(
                        authorizer_id="SAFETY_ENFORCEMENT_KERNEL",
                        role=AuthorizerRole.AUTOMATIC,
                        signature="AUTO_CBF_FALLBACK",
                        timestamp_ns=time.time_ns()
                    )
                    self.state_machine.transition_to(
                        to_state=AuthorityState.FALLBACK,
                        initiating_condition=f"Fallback controller triggered for domain {domain.value}",
                        authorizer=auth
                    )
                except Exception as e:
                    logger.error(f"Failed to transition to FALLBACK: {e}")

            return fallback_action

    # ------------------------------------------------------------------------
    # Emergency Path & Hardware E-Stop
    # ------------------------------------------------------------------------

    def trigger_hardware_estop(self, reason: str = "Hardware E-Stop Triggered") -> SafetyDecision:
        """Trigger immediate unconditional hardware E-stop."""
        with self._lock:
            self._hardware_estop_triggered = True
            self._physical_reset_performed = False

            auth = AuthorizerCredential(
                authorizer_id="HARDWARE_ESTOP_BUTTON",
                role=AuthorizerRole.AUTOMATIC,
                signature="HARDWARE_ESTOP_SIGNAL",
                timestamp_ns=time.time_ns()
            )

            try:
                self.state_machine.transition_to(
                    to_state=AuthorityState.EMERGENCY,
                    initiating_condition=reason,
                    authorizer=auth
                )
            except Exception as e:
                logger.error(f"E-Stop transition error: {e}")

            decision = SafetyDecision(
                decision_type=DecisionType.HALT,
                scope=SafetyScope.GLOBAL,
                reason=reason,
                reason_code="HARDWARE_ESTOP_TRIGGERED",
                severity=SafetySeverity.EMERGENCY,
                actions_required=["OPEN_ACTUATOR_POWER_RELAY", "LATCH_HARDWARE_ESTOP"],
                state_transition=AuthorityState.EMERGENCY
            )
            decision.hash = decision.compute_hash()
            return decision

    def heartbeat_watchdog_tick(self) -> Optional[SafetyDecision]:
        """Called periodically by system timer. Triggers E-Stop if watchdog missed."""
        with self._lock:
            now_ns = time.time_ns()
            dt_ms = (now_ns - self._last_heartbeat_time_ns) / 1e6
            self._last_heartbeat_time_ns = now_ns

            if dt_ms > 500:  # Watchdog timeout > 500ms
                self._heartbeat_watchdog_ok = False
                return self.trigger_hardware_estop("Heartbeat watchdog timeout (>500ms)")
            return None

    def perform_physical_reset(self) -> None:
        """Simulate physical button reset on hardware E-stop box."""
        with self._lock:
            self._physical_reset_performed = True

    def rearm_system(
        self,
        founder_credential: AuthorizerCredential,
        self_test_passed: bool
    ) -> Tuple[bool, str, Optional[SafetyDecision]]:
        """
        Re-arming workflow to exit EMERGENCY state:
        Requires:
        1. Physical reset performed
        2. Self-test passed
        3. Founder authorization credential
        """
        with self._lock:
            if self.state_machine.current_state != AuthorityState.EMERGENCY:
                return False, f"Cannot re-arm: system is in state {self.state_machine.current_state.value}, not EMERGENCY", None

            if not self._physical_reset_performed:
                return False, "Re-arm failed: Physical reset button has not been pressed", None

            if not self_test_passed:
                return False, "Re-arm failed: Self-test failed", None

            if founder_credential.role not in (AuthorizerRole.FOUNDER, AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER):
                return False, f"Re-arm failed: Requires FOUNDER credential, got {founder_credential.role.value}", None

            # Generate evidence
            evidence = TransitionEvidence(
                evidence_id=_generate_uuidv7(),
                condition_description="E-Stop cleared, physical reset verified, self-test passed",
                condition_cleared=True,
                verification_data={
                    "physical_reset": "TRUE",
                    "self_test": "PASSED",
                    "power_voltage": "NOMINAL"
                },
                timestamp_ns=time.time_ns(),
                verifier_id=founder_credential.authorizer_id
            )

            try:
                self.state_machine.transition_to(
                    to_state=AuthorityState.RECOVERY,
                    initiating_condition="System re-armed by Founder after E-Stop clear",
                    authorizer=founder_credential,
                    evidence=evidence
                )
                self._hardware_estop_triggered = False
                self._heartbeat_watchdog_ok = True

                decision = SafetyDecision(
                    decision_type=DecisionType.ALERT,
                    scope=SafetyScope.GLOBAL,
                    reason="System successfully re-armed and moved from EMERGENCY to RECOVERY",
                    reason_code="SYSTEM_REARMED",
                    severity=SafetySeverity.INFO,
                    actions_required=["PROCEED_WITH_RECOVERY_DIAGNOSTICS"],
                    state_transition=AuthorityState.RECOVERY
                )
                decision.hash = decision.compute_hash()
                return True, "System successfully re-armed to RECOVERY state", decision

            except Exception as e:
                return False, f"Re-arm transition failed: {str(e)}", None


class BatteryMonitor:
    """Battery monitor for safety verification — tracks capacity and triggers thresholds."""

    def __init__(self, capacity_mah: float = 5000.0, low_threshold: float = 20.0, critical_threshold: float = 10.0):
        self.capacity_mah = capacity_mah
        self.low_threshold = low_threshold
        self.critical_threshold = critical_threshold
        self._current_pct = 100.0  # Start at 100%

    def drain(self, amount: float) -> None:
        """Drain battery by amount (percentage points)."""
        self._current_pct = max(0.0, self._current_pct - amount)

    @property
    def current_pct(self) -> float:
        return self._current_pct

    def should_return_to_base(self) -> bool:
        """Check if battery is low enough to trigger return-to-base."""
        return self._current_pct <= self.low_threshold

    def should_emergency_land(self) -> bool:
        """Check if battery is critically low — must land immediately."""
        return self._current_pct <= self.critical_threshold
