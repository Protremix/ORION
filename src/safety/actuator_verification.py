"""
Safety Layer v3 — Actuator Command Verification Pipeline for ORION Physical Intelligence OS.

This module implements the 5-stage actuator command verification pipeline:
1. CBFFilter — Control Barrier Function constraint check (delegated to SafetyEnforcement)
2. RateLimit — Maximum rate of change enforcement (actuator can't change too fast)
3. RangeLimit — Physical actuator limits (force, speed, position bounds per domain)
4. AuthorityCheck — Verify Safety Enforcement Plane has authority to issue commands
5. AuditLog — Record command with cryptographic hash chain

Designed in pure Python with dataclasses to support simulation and hardware-in-the-loop (HIL).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from safety.safety_enforcement import (
        DecisionType,
        SafetyDecision,
        SafetyEnforcement,
        SafetySeverity,
    )
    from safety.state_machine import (
        AuthorityState,
        AuthorityTransitionStateMachine,
    )
except ImportError:
    try:
        from src.safety.safety_enforcement import (
            DecisionType,
            SafetyDecision,
            SafetyEnforcement,
            SafetySeverity,
        )
        from src.safety.state_machine import (
            AuthorityState,
            AuthorityTransitionStateMachine,
        )
    except ImportError:
        from .safety_enforcement import (
            DecisionType,
            SafetyEnforcement,
            SafetySeverity,
        )
        from .state_machine import (
            AuthorityState,
            AuthorityTransitionStateMachine,
        )

logger = logging.getLogger(__name__)


class VerificationStage(str, Enum):
    """Pipeline stages in Safety Layer v3 Actuator Command Verification."""
    CBF_FILTER = "cbf_filter"
    RATE_LIMIT = "rate_limit"
    RANGE_LIMIT = "range_limit"
    AUTHORITY_CHECK = "authority_check"
    AUDIT_LOG = "audit_log"


@dataclass
class ActuatorCommand:
    """Represents a command targeted at a physical or simulated actuator."""
    actuator_id: str
    domain: str = "industrial"  # "industrial", "vehicle", "drone", "home"
    command_type: str = "velocity"
    parameters: Dict[str, float] = field(default_factory=dict)
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    issuing_authority: str = "SafetyEnforcementPlane"
    is_emergency: bool = False
    risk_tier: int = 1  # Tier 1 (low/degraded), Tier 2 (standard), Tier 3 (high)


@dataclass
class StageResult:
    """Result of an individual pipeline stage execution."""
    stage: VerificationStage
    passed: bool
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLogEntry:
    """An entry in the tamper-evident cryptographic audit log."""
    entry_id: str
    sequence_number: int
    timestamp: float
    actuator_id: str
    domain: str
    command_type: str
    parameters: Dict[str, float]
    passed: bool
    rejected_stage: Optional[str]
    reason: str
    previous_hash: str
    hash: str


@dataclass
class VerificationResult:
    """Result of full actuator command verification pipeline execution."""
    command_id: str
    actuator_id: str
    domain: str
    passed: bool
    rejected_stage: Optional[VerificationStage] = None
    reason: str = ""
    verified_parameters: Dict[str, float] = field(default_factory=dict)
    stage_results: Dict[VerificationStage, StageResult] = field(default_factory=dict)
    audit_hash: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def __getitem__(self, item: str) -> Any:
        """Backwards compatibility for dict-style access."""
        if item in ("command_safe", "verified"):
            return self.passed
        elif item == "safe_command":
            return self.verified_parameters
        elif item == "raw_command":
            return self.verified_parameters
        elif item == "rejected":
            return not self.passed
        elif item == "actuator_id":
            return self.actuator_id
        elif item == "domain":
            return self.domain
        elif item == "reason":
            return self.reason
        elif item in ("hash", "audit_hash"):
            return self.audit_hash
        elif item == "rejected_stage":
            return self.rejected_stage.value if self.rejected_stage else None
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default


@dataclass
class ParameterLimit:
    """Min/Max physical bounds and maximum rate of change for a parameter."""
    min_val: float
    max_val: float
    max_rate_of_change: Optional[float] = None  # units per second


DEFAULT_DOMAIN_LIMITS: Dict[str, Dict[str, ParameterLimit]] = {
    "industrial": {
        "force": ParameterLimit(min_val=0.0, max_val=1000.0, max_rate_of_change=500.0),
        "velocity": ParameterLimit(min_val=-5.0, max_val=5.0, max_rate_of_change=2.0),
        "torque": ParameterLimit(min_val=-500.0, max_val=500.0, max_rate_of_change=250.0),
        "position": ParameterLimit(min_val=0.0, max_val=2.0, max_rate_of_change=0.5),
        "speed": ParameterLimit(min_val=-5.0, max_val=5.0, max_rate_of_change=2.0),
    },
    "vehicle": {
        "velocity": ParameterLimit(min_val=-10.0, max_val=50.0, max_rate_of_change=10.0),
        "brake": ParameterLimit(min_val=0.0, max_val=100.0, max_rate_of_change=100.0),
        "steering_angle": ParameterLimit(min_val=-45.0, max_val=45.0, max_rate_of_change=30.0),
        "acceleration": ParameterLimit(min_val=-10.0, max_val=10.0, max_rate_of_change=5.0),
        "speed": ParameterLimit(min_val=-10.0, max_val=50.0, max_rate_of_change=10.0),
    },
    "drone": {
        "motor": ParameterLimit(min_val=0.0, max_val=100.0, max_rate_of_change=50.0),
        "altitude": ParameterLimit(min_val=0.0, max_val=120.0, max_rate_of_change=10.0),
        "velocity": ParameterLimit(min_val=-15.0, max_val=15.0, max_rate_of_change=10.0),
        "pitch": ParameterLimit(min_val=-45.0, max_val=45.0, max_rate_of_change=60.0),
        "thrust": ParameterLimit(min_val=0.0, max_val=100.0, max_rate_of_change=50.0),
    },
    "home": {
        "power": ParameterLimit(min_val=0.0, max_val=3500.0, max_rate_of_change=1000.0),
        "current": ParameterLimit(min_val=0.0, max_val=16.0, max_rate_of_change=5.0),
        "temperature": ParameterLimit(min_val=10.0, max_val=30.0, max_rate_of_change=2.0),
        "brightness": ParameterLimit(min_val=0.0, max_val=100.0, max_rate_of_change=100.0),
    },
}


def _get_parameter_limit(
    domain: str,
    param_name: str,
    custom_limits: Optional[Dict[str, Dict[str, ParameterLimit]]] = None
) -> Optional[ParameterLimit]:
    """Helper to retrieve ParameterLimit for a given domain and parameter name."""
    if custom_limits and domain in custom_limits and param_name in custom_limits[domain]:
        return custom_limits[domain][param_name]

    domain_map = DEFAULT_DOMAIN_LIMITS.get(domain.lower(), {})
    if param_name in domain_map:
        return domain_map[param_name]

    p_lower = param_name.lower()
    for key, limit in domain_map.items():
        if key in p_lower or p_lower in key:
            return limit

    return None


class CBFFilterStage:
    """Stage 1: Control Barrier Function envelope check (delegates to SafetyEnforcement)."""

    def __init__(self, safety_enforcement: Optional[SafetyEnforcement] = None):
        self.safety_enforcement = safety_enforcement or SafetyEnforcement()

    def verify(
        self,
        command: ActuatorCommand,
        current_state: Optional[Dict[str, Any]] = None
    ) -> StageResult:
        state = current_state or {}
        safe_control, decisions = self.safety_enforcement.evaluate_and_filter_action(state, command.parameters)

        for decision in decisions:
            if decision.decision_type in (DecisionType.HALT, DecisionType.BLOCK, DecisionType.REVOKE_LEASE) or \
               decision.severity == SafetySeverity.EMERGENCY:
                return StageResult(
                    stage=VerificationStage.CBF_FILTER,
                    passed=False,
                    reason=f"CBF Filter HALT/BLOCK: {decision.reason}",
                    details={"decisions": decisions}
                )

        return StageResult(
            stage=VerificationStage.CBF_FILTER,
            passed=True,
            reason="CBF Envelope verified",
            details={"filtered_parameters": safe_control, "decisions": decisions}
        )


class RateLimitStage:
    """Stage 2: Maximum rate of change enforcement."""

    def __init__(self, limits: Optional[Dict[str, Dict[str, ParameterLimit]]] = None):
        self.limits = limits
        self._last_command_map: Dict[str, Tuple[Dict[str, float], float]] = {}

    def verify(self, command: ActuatorCommand) -> StageResult:
        if command.is_emergency or command.command_type in ("zero_command", "emergency_stop", "stop", "safe_state"):
            return StageResult(
                stage=VerificationStage.RATE_LIMIT,
                passed=True,
                reason="Emergency / zero command bypasses rate limit check"
            )

        if not command.parameters:
            return StageResult(
                stage=VerificationStage.RATE_LIMIT,
                passed=True,
                reason="No numeric parameters to rate limit"
            )

        if all(val == 0.0 for val in command.parameters.values()):
            return StageResult(
                stage=VerificationStage.RATE_LIMIT,
                passed=True,
                reason="Zero command passes rate limit"
            )

        actuator_id = command.actuator_id
        if actuator_id not in self._last_command_map:
            return StageResult(
                stage=VerificationStage.RATE_LIMIT,
                passed=True,
                reason="First command for actuator, no previous rate baseline"
            )

        last_params, last_timestamp = self._last_command_map[actuator_id]
        dt = command.timestamp - last_timestamp
        if dt <= 0.0:
            dt = 0.001

        for param_name, new_val in command.parameters.items():
            if param_name in last_params:
                old_val = last_params[param_name]
                delta = abs(new_val - old_val)
                rate = delta / dt

                limit = _get_parameter_limit(command.domain, param_name, self.limits)
                if limit and limit.max_rate_of_change is not None:
                    if rate > limit.max_rate_of_change + 1e-6:
                        return StageResult(
                            stage=VerificationStage.RATE_LIMIT,
                            passed=False,
                            reason=(
                                f"Rate limit exceeded for parameter '{param_name}': "
                                f"rate {rate:.2f}/s exceeds max allowed rate {limit.max_rate_of_change:.2f}/s"
                            ),
                            details={"calculated_rate": rate, "max_rate": limit.max_rate_of_change, "dt": dt}
                        )

        return StageResult(
            stage=VerificationStage.RATE_LIMIT,
            passed=True,
            reason="Rate of change within limits"
        )

    def record_last_command(self, command: ActuatorCommand) -> None:
        """Update last valid command state for rate tracking."""
        self._last_command_map[command.actuator_id] = (
            dict(command.parameters),
            command.timestamp
        )

    def reset_tracking(self, actuator_id: Optional[str] = None) -> None:
        """Reset command history baseline."""
        if actuator_id:
            self._last_command_map.pop(actuator_id, None)
        else:
            self._last_command_map.clear()


class RangeLimitStage:
    """Stage 3: Physical actuator bounds check (force, speed, position)."""

    def __init__(self, limits: Optional[Dict[str, Dict[str, ParameterLimit]]] = None):
        self.limits = limits

    def verify(self, command: ActuatorCommand) -> StageResult:
        for param_name, val in command.parameters.items():
            limit = _get_parameter_limit(command.domain, param_name, self.limits)
            if limit is not None:
                if val < limit.min_val or val > limit.max_val:
                    return StageResult(
                        stage=VerificationStage.RANGE_LIMIT,
                        passed=False,
                        reason=(
                            f"Parameter '{param_name}' value {val} out of bounds "
                            f"[{limit.min_val}, {limit.max_val}] for domain '{command.domain}'"
                        ),
                        details={"param": param_name, "val": val, "min": limit.min_val, "max": limit.max_val}
                    )

        return StageResult(
            stage=VerificationStage.RANGE_LIMIT,
            passed=True,
            reason="Parameters within physical bounds"
        )


class AuthorityCheckStage:
    """Stage 4: Verification that Safety Enforcement Plane has authority."""

    DEFAULT_AUTHORIZED_AUTHORITIES = [
        "SafetyEnforcementPlane",
        "SEP",
        "SafetyEnforcement",
        "EmergencySystem",
        "HardwareInterlock",
        "ManualOverride",
    ]

    def __init__(
        self,
        state_machine: Optional[AuthorityTransitionStateMachine] = None,
        authorized_authorities: Optional[List[str]] = None,
    ):
        self.state_machine = state_machine
        self.authorized_authorities = (
            authorized_authorities or list(self.DEFAULT_AUTHORIZED_AUTHORITIES)
        )

    def verify(self, command: ActuatorCommand) -> StageResult:
        auth = command.issuing_authority
        is_auth_ok = auth in self.authorized_authorities or any(
            auth.startswith(prefix) for prefix in ("SafetyEnforcement", "SEP", "Emergency", "Manual")
        )
        if not is_auth_ok:
            return StageResult(
                stage=VerificationStage.AUTHORITY_CHECK,
                passed=False,
                reason=f"Issuing authority '{auth}' is unauthorized to command actuators directly"
            )

        if self.state_machine is not None:
            curr_state = self.state_machine.current_state

            if curr_state == AuthorityState.EMERGENCY:
                if not command.is_emergency and command.command_type not in (
                    "emergency_stop", "estop", "halt", "zero_command", "safe_state"
                ):
                    return StageResult(
                        stage=VerificationStage.AUTHORITY_CHECK,
                        passed=False,
                        reason="System in EMERGENCY state; non-emergency commands rejected"
                    )

            elif curr_state == AuthorityState.SHUTDOWN:
                return StageResult(
                    stage=VerificationStage.AUTHORITY_CHECK,
                    passed=False,
                    reason="System in SHUTDOWN state; commands rejected"
                )

            elif curr_state in (AuthorityState.DEGRADED, AuthorityState.FALLBACK):
                if command.risk_tier > 1 and not command.is_emergency and command.command_type not in (
                    "fallback", "degraded", "safe_state", "zero_command", "stop"
                ):
                    return StageResult(
                        stage=VerificationStage.AUTHORITY_CHECK,
                        passed=False,
                        reason=f"High risk tier ({command.risk_tier}) command rejected in {curr_state.value} state"
                    )

        return StageResult(
            stage=VerificationStage.AUTHORITY_CHECK,
            passed=True,
            reason="Authority verified"
        )


class AuditLogStage:
    """Stage 5: Record verified/rejected command with cryptographic hash chain."""

    def __init__(self, external_storage: Optional[Any] = None):
        self.external_storage = external_storage
        self._entries: List[AuditLogEntry] = []
        self._last_hash: str = "0" * 64

    def record(self, command: ActuatorCommand, result: VerificationResult) -> AuditLogEntry:
        seq = len(self._entries) + 1
        prev_hash = self._last_hash
        entry_id = str(uuid.uuid4())

        entry_data = {
            "entry_id": entry_id,
            "sequence_number": seq,
            "timestamp": command.timestamp,
            "actuator_id": command.actuator_id,
            "domain": command.domain,
            "command_type": command.command_type,
            "parameters": command.parameters,
            "passed": result.passed,
            "rejected_stage": result.rejected_stage.value if result.rejected_stage else None,
            "reason": result.reason,
            "previous_hash": prev_hash,
        }

        serialized = json.dumps(entry_data, sort_keys=True)
        entry_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        entry = AuditLogEntry(
            entry_id=entry_id,
            sequence_number=seq,
            timestamp=command.timestamp,
            actuator_id=command.actuator_id,
            domain=command.domain,
            command_type=command.command_type,
            parameters=dict(command.parameters),
            passed=result.passed,
            rejected_stage=result.rejected_stage.value if result.rejected_stage else None,
            reason=result.reason,
            previous_hash=prev_hash,
            hash=entry_hash,
        )

        self._entries.append(entry)
        self._last_hash = entry_hash

        if self.external_storage is not None:
            try:
                if hasattr(self.external_storage, "append"):
                    self.external_storage.append(entry)
                elif hasattr(self.external_storage, "write"):
                    self.external_storage.write(entry)
            except Exception as e:
                logger.warning(f"Failed to record audit entry to external storage: {e}")

        return entry

    def get_entries(self) -> List[AuditLogEntry]:
        return list(self._entries)

    def verify_hash_chain(self) -> bool:
        """Verify the cryptographic hash chain integrity across all logged entries."""
        if not self._entries:
            return True

        current_prev_hash = "0" * 64

        for entry in self._entries:
            if entry.previous_hash != current_prev_hash:
                return False

            entry_data = {
                "entry_id": entry.entry_id,
                "sequence_number": entry.sequence_number,
                "timestamp": entry.timestamp,
                "actuator_id": entry.actuator_id,
                "domain": entry.domain,
                "command_type": entry.command_type,
                "parameters": entry.parameters,
                "passed": entry.passed,
                "rejected_stage": entry.rejected_stage,
                "reason": entry.reason,
                "previous_hash": entry.previous_hash,
            }

            serialized = json.dumps(entry_data, sort_keys=True)
            expected_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

            if entry.hash != expected_hash:
                return False

            current_prev_hash = entry.hash

        return True


class ActuatorVerificationPipeline:
    """
    Safety Layer v3 — Actuator Command Verification Pipeline.

    Sequentially executes:
    1. CBFFilter
    2. RateLimit
    3. RangeLimit
    4. AuthorityCheck
    5. AuditLog
    """

    def __init__(
        self,
        safety_enforcement: Optional[SafetyEnforcement] = None,
        state_machine: Optional[AuthorityTransitionStateMachine] = None,
        custom_limits: Optional[Dict[str, Dict[str, ParameterLimit]]] = None,
        authorized_authorities: Optional[List[str]] = None,
        external_audit_storage: Optional[Any] = None,
    ):
        self.safety_enforcement = safety_enforcement or SafetyEnforcement(state_machine=state_machine)
        self.state_machine = state_machine or self.safety_enforcement.state_machine

        # Initialize Pipeline Stages
        self.cbf_stage = CBFFilterStage(safety_enforcement=self.safety_enforcement)
        self.rate_limit_stage = RateLimitStage(limits=custom_limits)
        self.range_limit_stage = RangeLimitStage(limits=custom_limits)
        self.authority_stage = AuthorityCheckStage(
            state_machine=self.state_machine,
            authorized_authorities=authorized_authorities,
        )
        self.audit_log_stage = AuditLogStage(external_storage=external_audit_storage)

    def verify_command(
        self,
        actuator_id_or_cmd: Union[str, ActuatorCommand, Dict[str, Any]],
        command: Optional[Union[Dict[str, Any], ActuatorCommand]] = None,
        current_state: Optional[Dict[str, Any]] = None,
        power_state: str = "NORMAL",
        domain: str = "industrial",
        issuing_authority: str = "SafetyEnforcementPlane",
    ) -> VerificationResult:
        """
        Main pipeline entry point. Verifies command against all 5 stages.
        """
        # Normalize command representation
        if isinstance(actuator_id_or_cmd, ActuatorCommand):
            cmd = actuator_id_or_cmd
        elif isinstance(actuator_id_or_cmd, dict) and command is None:
            raw_dict = actuator_id_or_cmd
            actuator_id = raw_dict.get("actuator_id", "default_actuator")
            cmd_domain = raw_dict.get("domain", domain)
            params = {k: float(v) for k, v in raw_dict.items() if isinstance(v, (int, float)) and not k.endswith(("_min", "_max", "_limit"))}
            cmd = ActuatorCommand(
                actuator_id=actuator_id,
                domain=cmd_domain,
                command_type=raw_dict.get("command_type", "velocity"),
                parameters=params,
                issuing_authority=raw_dict.get("issuing_authority", issuing_authority),
                is_emergency=raw_dict.get("is_emergency", False),
                risk_tier=raw_dict.get("risk_tier", 1),
            )
        else:
            actuator_id = str(actuator_id_or_cmd)
            if isinstance(command, ActuatorCommand):
                cmd = command
            elif isinstance(command, dict):
                raw_dict = command
                cmd_domain = raw_dict.get("domain", domain)
                params = {k: float(v) for k, v in raw_dict.items() if isinstance(v, (int, float)) and not k.endswith(("_min", "_max", "_limit"))}
                cmd = ActuatorCommand(
                    actuator_id=actuator_id,
                    domain=cmd_domain,
                    command_type=raw_dict.get("command_type", "velocity"),
                    parameters=params,
                    issuing_authority=raw_dict.get("issuing_authority", issuing_authority),
                    is_emergency=raw_dict.get("is_emergency", False),
                    risk_tier=raw_dict.get("risk_tier", 1),
                )
            else:
                cmd = ActuatorCommand(
                    actuator_id=actuator_id,
                    domain=domain,
                    issuing_authority=issuing_authority,
                )

        stage_results: Dict[VerificationStage, StageResult] = {}
        pipeline_passed = True
        rejected_stage: Optional[VerificationStage] = None
        rejection_reason = ""
        verified_params = dict(cmd.parameters)

        # Check physical power cutoff / E-Stop state
        if power_state in ("ESTOP", "POWER_CUTOFF") or self.safety_enforcement._hardware_estop_triggered:
            pipeline_passed = False
            rejected_stage = VerificationStage.AUTHORITY_CHECK
            rejection_reason = f"System in {power_state} state"
            verified_params = {k: 0.0 for k in cmd.parameters}

        # Stage 1: CBFFilter
        if pipeline_passed:
            cbf_res = self.cbf_stage.verify(cmd, current_state)
            stage_results[VerificationStage.CBF_FILTER] = cbf_res
            if not cbf_res.passed:
                pipeline_passed = False
                rejected_stage = VerificationStage.CBF_FILTER
                rejection_reason = cbf_res.reason
            else:
                if "filtered_parameters" in cbf_res.details and cbf_res.details["filtered_parameters"]:
                    verified_params = cbf_res.details["filtered_parameters"]
                    cmd.parameters = dict(verified_params)

        # Stage 2: RateLimit
        if pipeline_passed:
            rate_res = self.rate_limit_stage.verify(cmd)
            stage_results[VerificationStage.RATE_LIMIT] = rate_res
            if not rate_res.passed:
                pipeline_passed = False
                rejected_stage = VerificationStage.RATE_LIMIT
                rejection_reason = rate_res.reason

        # Stage 3: RangeLimit
        if pipeline_passed:
            range_res = self.range_limit_stage.verify(cmd)
            stage_results[VerificationStage.RANGE_LIMIT] = range_res
            if not range_res.passed:
                pipeline_passed = False
                rejected_stage = VerificationStage.RANGE_LIMIT
                rejection_reason = range_res.reason

        # Stage 4: AuthorityCheck
        if pipeline_passed:
            auth_res = self.authority_stage.verify(cmd)
            stage_results[VerificationStage.AUTHORITY_CHECK] = auth_res
            if not auth_res.passed:
                pipeline_passed = False
                rejected_stage = VerificationStage.AUTHORITY_CHECK
                rejection_reason = auth_res.reason

        # Record state for rate tracking if all stages passed
        if pipeline_passed:
            self.rate_limit_stage.record_last_command(cmd)

        res = VerificationResult(
            command_id=cmd.command_id,
            actuator_id=cmd.actuator_id,
            domain=cmd.domain,
            passed=pipeline_passed,
            rejected_stage=rejected_stage,
            reason=rejection_reason or "All stages passed",
            verified_parameters=verified_params,
            stage_results=stage_results,
            timestamp=cmd.timestamp,
        )

        # Stage 5: AuditLog (Always recorded)
        entry = self.audit_log_stage.record(cmd, res)
        res.audit_hash = entry.hash

        return res


# Alias for backwards compatibility
ActuatorVerifier = ActuatorVerificationPipeline
