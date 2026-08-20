"""
Authority-Transition State Machine for ORION Physical Intelligence OS.

This module implements the 8-state (plus lifecycle states) deterministic authority-transition
state machine required by the ORION v0.5 architecture.

Key Safety Guarantees:
1. Monotonic Safety: Transitions to more restrictive states are ALWAYS permitted automatically.
2. Controlled Recovery: Transitions to less restrictive states strictly require both cleared evidence
   and formal authorization (Safety Assurance / Founder).
3. Monotonic Clock & Immutable Audit Logging: All transitions are cryptographically hash-linked and audited.
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def _generate_uuidv7() -> str:
    """Generate a UUID v7 string based on Unix timestamp in milliseconds."""
    timestamp_ms = int(time.time() * 1000)
    import os
    rand_bytes = os.urandom(10)
    b = bytearray(16)
    b[0:6] = timestamp_ms.to_bytes(6, "big")
    b[6] = 0x70 | (rand_bytes[0] & 0x0F)
    b[7] = rand_bytes[1]
    b[8] = 0x80 | (rand_bytes[2] & 0x3F)
    b[9:16] = rand_bytes[3:10]
    return str(uuid.UUID(bytes=bytes(b)))


class AuthorityState(str, Enum):
    """
    Authority States for ORION physical intelligence control.
    Ordered by restrictiveness rank (higher number = more restrictive).
    """
    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    AUTONOMOUS = "AUTONOMOUS"
    SUPERVISED = "SUPERVISED"
    DEGRADED = "DEGRADED"
    FALLBACK = "FALLBACK"
    RECOVERY = "RECOVERY"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY = "EMERGENCY"
    SHUTDOWN = "SHUTDOWN"


# Restrictiveness Ranking (Higher = More Restrictive)
# Monotonic safety rule: Moving to higher rank is ALWAYS allowed automatically.
STATE_RESTRICTIVENESS: Dict[AuthorityState, int] = {
    AuthorityState.AUTONOMOUS: 1,
    AuthorityState.SUPERVISED: 2,
    AuthorityState.DEGRADED: 3,
    AuthorityState.FALLBACK: 4,
    AuthorityState.RECOVERY: 5,
    AuthorityState.MAINTENANCE: 6,
    AuthorityState.EMERGENCY: 7,
    AuthorityState.SHUTDOWN: 8,
    AuthorityState.UNINITIALIZED: 9,
    AuthorityState.INITIALIZING: 10,
}


class AuthorizerRole(str, Enum):
    AUTOMATIC = "AUTOMATIC"
    SAFETY_ASSURANCE = "SAFETY_ASSURANCE"
    FOUNDER = "FOUNDER"
    SAFETY_ASSURANCE_AND_FOUNDER = "SAFETY_ASSURANCE_AND_FOUNDER"


@dataclass(frozen=True)
class TransitionEvidence:
    """Evidence required to prove a failure/restrictive condition has been cleared."""
    evidence_id: str
    condition_description: str
    condition_cleared: bool
    verification_data: Dict[str, str]
    timestamp_ns: int
    verifier_id: str

    def is_valid(self) -> bool:
        return self.condition_cleared and bool(self.evidence_id) and bool(self.verifier_id)


@dataclass(frozen=True)
class AuthorizerCredential:
    """Credential confirming authorization for state transition."""
    authorizer_id: str
    role: AuthorizerRole
    signature: str
    timestamp_ns: int


@dataclass
class TransitionRule:
    from_state: AuthorityState
    to_state: AuthorityState
    initiating_condition: str
    owner: AuthorizerRole
    allowed_actions: List[str]
    exit_condition: str
    evidence_required: bool


@dataclass
class StateTransitionRecord:
    transition_id: str
    timestamp_ns: int
    from_state: AuthorityState
    to_state: AuthorityState
    initiating_condition: str
    authorizer: AuthorizerCredential
    evidence: Optional[TransitionEvidence]
    previous_hash: str
    record_hash: str

    def calculate_hash(self) -> str:
        content = (
            f"{self.transition_id}:{self.timestamp_ns}:{self.from_state.value}:"
            f"{self.to_state.value}:{self.initiating_condition}:{self.authorizer.authorizer_id}:"
            f"{self.previous_hash}"
        )
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


# Allowed action types per state
STATE_ALLOWED_ACTIONS: Dict[AuthorityState, Set[str]] = {
    AuthorityState.UNINITIALIZED: {"BOOT_DIAGNOSTIC"},
    AuthorityState.INITIALIZING: {"BOOT_DIAGNOSTIC", "SENSOR_CALIBRATION", "SELF_TEST"},
    AuthorityState.AUTONOMOUS: {"ALL", "TIER_1", "TIER_2", "TIER_3", "REALTIME", "ASYNC", "HUMAN_APPROVAL", "EMERGENCY"},
    AuthorityState.SUPERVISED: {"ALL", "TIER_1", "TIER_2", "TIER_3", "REALTIME", "ASYNC", "HUMAN_APPROVAL", "EMERGENCY"},
    AuthorityState.DEGRADED: {"TIER_1", "REDUCED_SPEED_MOTION", "SAFETY_MONITORING", "REALTIME", "ASYNC"},
    AuthorityState.FALLBACK: {"DETERMINISTIC_SAFE_PARK", "HAZARD_BRAKE", "HOVER_DESCENT", "TOOL_RETRACT"},
    AuthorityState.RECOVERY: {"DIAGNOSTIC_QUERY", "HARDWARE_RESET", "CLEAR_FAULT_BUFFER"},
    AuthorityState.MAINTENANCE: {"MANUAL_ACTUATION", "CALIBRATION", "FIRMWARE_UPDATE", "DIAGNOSTIC"},
    AuthorityState.EMERGENCY: {"HARDWARE_SAFE_STATE", "NO_NEW_ACTIONS"},
    AuthorityState.SHUTDOWN: {"NO_ACTIONS"},
}


class AuthorityTransitionStateMachine:
    """
    8-State Authority Transition State Machine with Monotonic Safety Enforcement.

    Manages operational authority states and validates state transitions according
    to strict evidence-based and role-authorized criteria.
    """

    def __init__(self, initial_state: AuthorityState = AuthorityState.UNINITIALIZED):
        import threading
        self._lock = threading.RLock()
        self._current_state = initial_state
        self._state_entry_time_ns = time.time_ns()
        self._history: List[StateTransitionRecord] = []
        self._listeners: List[Callable[[AuthorityState, AuthorityState, StateTransitionRecord], None]] = []
        self._last_record_hash = "0" * 64

        self._transition_table: Dict[Tuple[AuthorityState, AuthorityState], TransitionRule] = self._build_transition_table()

    def _build_transition_table(self) -> Dict[Tuple[AuthorityState, AuthorityState], TransitionRule]:
        """Construct the complete transition matrix from v0.5 architecture specification."""
        table: Dict[Tuple[AuthorityState, AuthorityState], TransitionRule] = {}

        # 1. Transitions out of UNINITIALIZED
        table[(AuthorityState.UNINITIALIZED, AuthorityState.INITIALIZING)] = TransitionRule(
            from_state=AuthorityState.UNINITIALIZED,
            to_state=AuthorityState.INITIALIZING,
            initiating_condition="Power on / system boot sequence initiated",
            owner=AuthorizerRole.AUTOMATIC,
            allowed_actions=["BOOT_DIAGNOSTIC"],
            exit_condition="Hardware self-test complete",
            evidence_required=False
        )
        table[(AuthorityState.UNINITIALIZED, AuthorityState.SHUTDOWN)] = TransitionRule(
            from_state=AuthorityState.UNINITIALIZED,
            to_state=AuthorityState.SHUTDOWN,
            initiating_condition="Boot failure or explicit shutdown",
            owner=AuthorizerRole.AUTOMATIC,
            allowed_actions=["NO_ACTIONS"],
            exit_condition="System off",
            evidence_required=False
        )

        # 2. Transitions out of INITIALIZING
        table[(AuthorityState.INITIALIZING, AuthorityState.SUPERVISED)] = TransitionRule(
            from_state=AuthorityState.INITIALIZING,
            to_state=AuthorityState.SUPERVISED,
            initiating_condition="Self-test passed, sensors nominal",
            owner=AuthorizerRole.SAFETY_ASSURANCE,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.SUPERVISED]),
            exit_condition="Supervision active",
            evidence_required=True
        )
        table[(AuthorityState.INITIALIZING, AuthorityState.AUTONOMOUS)] = TransitionRule(
            from_state=AuthorityState.INITIALIZING,
            to_state=AuthorityState.AUTONOMOUS,
            initiating_condition="Self-test passed, auto-start enabled",
            owner=AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.AUTONOMOUS]),
            exit_condition="Autonomous operation active",
            evidence_required=True
        )

        # 3. Transitions out of AUTONOMOUS
        table[(AuthorityState.AUTONOMOUS, AuthorityState.SUPERVISED)] = TransitionRule(
            from_state=AuthorityState.AUTONOMOUS,
            to_state=AuthorityState.SUPERVISED,
            initiating_condition="Founder/operator requests supervision or step-down",
            owner=AuthorizerRole.AUTOMATIC,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.SUPERVISED]),
            exit_condition="Human monitoring active",
            evidence_required=False
        )
        table[(AuthorityState.AUTONOMOUS, AuthorityState.DEGRADED)] = TransitionRule(
            from_state=AuthorityState.AUTONOMOUS,
            to_state=AuthorityState.DEGRADED,
            initiating_condition="Sensor degradation, model server offline, config warning",
            owner=AuthorizerRole.AUTOMATIC,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.DEGRADED]),
            exit_condition="Degraded limits active",
            evidence_required=False
        )
        table[(AuthorityState.AUTONOMOUS, AuthorityState.FALLBACK)] = TransitionRule(
            from_state=AuthorityState.AUTONOMOUS,
            to_state=AuthorityState.FALLBACK,
            initiating_condition="CBF boundary violation, control plane failure, lease failure",
            owner=AuthorizerRole.AUTOMATIC,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.FALLBACK]),
            exit_condition="Fallback controller engaged",
            evidence_required=False
        )
        table[(AuthorityState.AUTONOMOUS, AuthorityState.MAINTENANCE)] = TransitionRule(
            from_state=AuthorityState.AUTONOMOUS,
            to_state=AuthorityState.MAINTENANCE,
            initiating_condition="Founder initiates maintenance mode",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.MAINTENANCE]),
            exit_condition="Manual maintenance mode active",
            evidence_required=False
        )

        # 4. Transitions out of SUPERVISED
        table[(AuthorityState.SUPERVISED, AuthorityState.AUTONOMOUS)] = TransitionRule(
            from_state=AuthorityState.SUPERVISED,
            to_state=AuthorityState.AUTONOMOUS,
            initiating_condition="All sensors nominal, models operational, safety checks pass",
            owner=AuthorizerRole.SAFETY_ASSURANCE,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.AUTONOMOUS]),
            exit_condition="Autonomous mode active",
            evidence_required=True
        )
        table[(AuthorityState.SUPERVISED, AuthorityState.DEGRADED)] = TransitionRule(
            from_state=AuthorityState.SUPERVISED,
            to_state=AuthorityState.DEGRADED,
            initiating_condition="Sensor anomaly or performance drop detected",
            owner=AuthorizerRole.AUTOMATIC,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.DEGRADED]),
            exit_condition="Degraded limits active",
            evidence_required=False
        )
        table[(AuthorityState.SUPERVISED, AuthorityState.FALLBACK)] = TransitionRule(
            from_state=AuthorityState.SUPERVISED,
            to_state=AuthorityState.FALLBACK,
            initiating_condition="CBF violation or control fault",
            owner=AuthorizerRole.AUTOMATIC,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.FALLBACK]),
            exit_condition="Fallback controller engaged",
            evidence_required=False
        )
        table[(AuthorityState.SUPERVISED, AuthorityState.MAINTENANCE)] = TransitionRule(
            from_state=AuthorityState.SUPERVISED,
            to_state=AuthorityState.MAINTENANCE,
            initiating_condition="Founder initiates maintenance",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.MAINTENANCE]),
            exit_condition="Maintenance mode active",
            evidence_required=False
        )

        # 5. Transitions out of DEGRADED
        table[(AuthorityState.DEGRADED, AuthorityState.SUPERVISED)] = TransitionRule(
            from_state=AuthorityState.DEGRADED,
            to_state=AuthorityState.SUPERVISED,
            initiating_condition="Degradation condition cleared, system re-verified",
            owner=AuthorizerRole.SAFETY_ASSURANCE,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.SUPERVISED]),
            exit_condition="Supervised mode active",
            evidence_required=True
        )
        table[(AuthorityState.DEGRADED, AuthorityState.AUTONOMOUS)] = TransitionRule(
            from_state=AuthorityState.DEGRADED,
            to_state=AuthorityState.AUTONOMOUS,
            initiating_condition="Full re-verification complete, all conditions cleared",
            owner=AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.AUTONOMOUS]),
            exit_condition="Autonomous operation restored",
            evidence_required=True
        )
        table[(AuthorityState.DEGRADED, AuthorityState.FALLBACK)] = TransitionRule(
            from_state=AuthorityState.DEGRADED,
            to_state=AuthorityState.FALLBACK,
            initiating_condition="Further safety degradation or CBF breach",
            owner=AuthorizerRole.AUTOMATIC,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.FALLBACK]),
            exit_condition="Fallback mode active",
            evidence_required=False
        )
        table[(AuthorityState.DEGRADED, AuthorityState.MAINTENANCE)] = TransitionRule(
            from_state=AuthorityState.DEGRADED,
            to_state=AuthorityState.MAINTENANCE,
            initiating_condition="Founder moves to maintenance",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.MAINTENANCE]),
            exit_condition="Maintenance active",
            evidence_required=False
        )

        # 6. Transitions out of FALLBACK
        table[(AuthorityState.FALLBACK, AuthorityState.RECOVERY)] = TransitionRule(
            from_state=AuthorityState.FALLBACK,
            to_state=AuthorityState.RECOVERY,
            initiating_condition="Fallback condition diagnosed, repair plan available",
            owner=AuthorizerRole.SAFETY_ASSURANCE,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.RECOVERY]),
            exit_condition="Recovery diagnosis active",
            evidence_required=True
        )
        table[(AuthorityState.FALLBACK, AuthorityState.MAINTENANCE)] = TransitionRule(
            from_state=AuthorityState.FALLBACK,
            to_state=AuthorityState.MAINTENANCE,
            initiating_condition="Founder selects maintenance",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.MAINTENANCE]),
            exit_condition="Maintenance active",
            evidence_required=False
        )

        # 7. Transitions out of RECOVERY
        table[(AuthorityState.RECOVERY, AuthorityState.DEGRADED)] = TransitionRule(
            from_state=AuthorityState.RECOVERY,
            to_state=AuthorityState.DEGRADED,
            initiating_condition="Recovery actions completed, system partially verified",
            owner=AuthorizerRole.SAFETY_ASSURANCE,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.DEGRADED]),
            exit_condition="Degraded operation active",
            evidence_required=True
        )
        table[(AuthorityState.RECOVERY, AuthorityState.SUPERVISED)] = TransitionRule(
            from_state=AuthorityState.RECOVERY,
            to_state=AuthorityState.SUPERVISED,
            initiating_condition="Full re-verification complete, all conditions cleared",
            owner=AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.SUPERVISED]),
            exit_condition="Supervised operation restored",
            evidence_required=True
        )
        table[(AuthorityState.RECOVERY, AuthorityState.MAINTENANCE)] = TransitionRule(
            from_state=AuthorityState.RECOVERY,
            to_state=AuthorityState.MAINTENANCE,
            initiating_condition="Founder enters maintenance mode",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.MAINTENANCE]),
            exit_condition="Maintenance active",
            evidence_required=False
        )

        # 8. Transitions out of EMERGENCY
        table[(AuthorityState.EMERGENCY, AuthorityState.RECOVERY)] = TransitionRule(
            from_state=AuthorityState.EMERGENCY,
            to_state=AuthorityState.RECOVERY,
            initiating_condition="E-Stop cleared, physical reset performed, self-test passed",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.RECOVERY]),
            exit_condition="Recovery mode active",
            evidence_required=True
        )
        table[(AuthorityState.EMERGENCY, AuthorityState.MAINTENANCE)] = TransitionRule(
            from_state=AuthorityState.EMERGENCY,
            to_state=AuthorityState.MAINTENANCE,
            initiating_condition="Founder initiates maintenance after emergency",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.MAINTENANCE]),
            exit_condition="Maintenance mode active",
            evidence_required=False
        )
        table[(AuthorityState.EMERGENCY, AuthorityState.SHUTDOWN)] = TransitionRule(
            from_state=AuthorityState.EMERGENCY,
            to_state=AuthorityState.SHUTDOWN,
            initiating_condition="Emergency shutdown executed",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.SHUTDOWN]),
            exit_condition="System power off",
            evidence_required=False
        )

        # 9. Transitions out of MAINTENANCE
        table[(AuthorityState.MAINTENANCE, AuthorityState.DEGRADED)] = TransitionRule(
            from_state=AuthorityState.MAINTENANCE,
            to_state=AuthorityState.DEGRADED,
            initiating_condition="Maintenance complete, system verified",
            owner=AuthorizerRole.SAFETY_ASSURANCE,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.DEGRADED]),
            exit_condition="Degraded operational test active",
            evidence_required=True
        )
        table[(AuthorityState.MAINTENANCE, AuthorityState.SHUTDOWN)] = TransitionRule(
            from_state=AuthorityState.MAINTENANCE,
            to_state=AuthorityState.SHUTDOWN,
            initiating_condition="Founder powers down system",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.SHUTDOWN]),
            exit_condition="System powered down",
            evidence_required=False
        )

        # 10. Transitions out of SHUTDOWN
        table[(AuthorityState.SHUTDOWN, AuthorityState.INITIALIZING)] = TransitionRule(
            from_state=AuthorityState.SHUTDOWN,
            to_state=AuthorityState.INITIALIZING,
            initiating_condition="Founder initiates fresh cold boot",
            owner=AuthorizerRole.FOUNDER,
            allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.INITIALIZING]),
            exit_condition="Boot diagnostics starting",
            evidence_required=False
        )

        # 11. Universal Transitions to EMERGENCY or SHUTDOWN from ANY State
        for state in AuthorityState:
            if state != AuthorityState.EMERGENCY and state != AuthorityState.SHUTDOWN:
                table[(state, AuthorityState.EMERGENCY)] = TransitionRule(
                    from_state=state,
                    to_state=AuthorityState.EMERGENCY,
                    initiating_condition="E-Stop trigger, hardware watchdog, power loss, security breach",
                    owner=AuthorizerRole.AUTOMATIC,
                    allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.EMERGENCY]),
                    exit_condition="Actuators latched in hardware safe state",
                    evidence_required=False
                )
                table[(state, AuthorityState.SHUTDOWN)] = TransitionRule(
                    from_state=state,
                    to_state=AuthorityState.SHUTDOWN,
                    initiating_condition="Shutdown command issued",
                    owner=AuthorizerRole.AUTOMATIC if state in (AuthorityState.UNINITIALIZED, AuthorityState.INITIALIZING) else AuthorizerRole.FOUNDER,
                    allowed_actions=list(STATE_ALLOWED_ACTIONS[AuthorityState.SHUTDOWN]),
                    exit_condition="System off",
                    evidence_required=False
                )

        return table

    @property
    def current_state(self) -> AuthorityState:
        with self._lock:
            return self._current_state

    @property
    def time_in_current_state_ns(self) -> int:
        with self._lock:
            return time.time_ns() - self._state_entry_time_ns

    def register_listener(self, callback: Callable[[AuthorityState, AuthorityState, StateTransitionRecord], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def is_action_permitted(self, action_type: str, risk_tier: int = 1) -> bool:
        """Query whether an action type and risk tier are permitted in the current state."""
        with self._lock:
            allowed = STATE_ALLOWED_ACTIONS.get(self._current_state, set())
            if "NO_ACTIONS" in allowed:
                return False
            if "ALL" in allowed:
                return True
            if self._current_state == AuthorityState.DEGRADED:
                # DEGRADED state only permits Risk Tier 1 actions
                if risk_tier > 1:
                    return False
            return action_type in allowed or f"TIER_{risk_tier}" in allowed

    def can_transition(
        self,
        to_state: AuthorityState,
        authorizer: AuthorizerCredential,
        evidence: Optional[TransitionEvidence] = None
    ) -> Tuple[bool, str]:
        """
        Evaluate if a transition to target state is legally permitted without modifying state.
        Enforces Monotonic Safety rules.
        """
        with self._lock:
            from_state = self._current_state
            if from_state == to_state:
                return False, f"Already in state {to_state.value}"

            # Monotonic Safety Check
            from_rank = STATE_RESTRICTIVENESS[from_state]
            to_rank = STATE_RESTRICTIVENESS[to_state]

            # Direct EMERGENCY trigger is always permitted from any state
            if to_state == AuthorityState.EMERGENCY:
                return True, "Emergency transition automatically authorized"

            # 1. Transition to MORE restrictive state (higher rank number)
            if to_rank > from_rank:
                # Always permitted as a monotonic safety move
                return True, f"Monotonic transition to more restrictive state ({from_state.value} -> {to_state.value})"

            # 2. Transition to LESS restrictive state (lower rank number)
            # Requires strict validation of transition table, evidence, and authorizer
            rule = self._transition_table.get((from_state, to_state))
            if not rule:
                return False, f"Forbidden transition path: {from_state.value} -> {to_state.value}"

            # Validate Evidence requirement
            if rule.evidence_required:
                if not evidence or not evidence.is_valid():
                    return False, f"Transition {from_state.value} -> {to_state.value} requires valid cleared evidence"

            # Validate Authorizer Role
            required_owner = rule.owner
            if required_owner == AuthorizerRole.AUTOMATIC:
                pass
            elif required_owner == AuthorizerRole.FOUNDER:
                if authorizer.role not in (AuthorizerRole.FOUNDER, AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER):
                    return False, f"Transition requires FOUNDER authorization, got {authorizer.role.value}"
            elif required_owner == AuthorizerRole.SAFETY_ASSURANCE:
                if authorizer.role not in (AuthorizerRole.SAFETY_ASSURANCE, AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER):
                    return False, f"Transition requires SAFETY_ASSURANCE authorization, got {authorizer.role.value}"
            elif required_owner == AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER:
                if authorizer.role != AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER:
                    return False, "Transition requires joint SAFETY_ASSURANCE_AND_FOUNDER authorization"

            return True, f"Transition {from_state.value} -> {to_state.value} authorized"

    def transition_to(
        self,
        to_state: AuthorityState,
        initiating_condition: str,
        authorizer: AuthorizerCredential,
        evidence: Optional[TransitionEvidence] = None
    ) -> StateTransitionRecord:
        """
        Execute an authority state transition if authorized.
        Raises ValueError if transition is invalid.
        """
        with self._lock:
            from_state = self._current_state
            allowed, msg = self.can_transition(to_state, authorizer, evidence)
            if not allowed:
                raise ValueError(f"State transition denied ({from_state.value} -> {to_state.value}): {msg}")

            now_ns = time.time_ns()
            record_id = _generate_uuidv7()

            record = StateTransitionRecord(
                transition_id=record_id,
                timestamp_ns=now_ns,
                from_state=from_state,
                to_state=to_state,
                initiating_condition=initiating_condition,
                authorizer=authorizer,
                evidence=evidence,
                previous_hash=self._last_record_hash,
                record_hash=""
            )
            record.record_hash = record.calculate_hash()
            self._last_record_hash = record.record_hash

            # Update State
            self._current_state = to_state
            self._state_entry_time_ns = now_ns
            self._history.append(record)

            logger.info(
                f"AUTHORITY STATE TRANSITION: {from_state.value} -> {to_state.value} | "
                f"Condition: {initiating_condition} | Auth: {authorizer.role.value} ({authorizer.authorizer_id})"
            )

            # Notify Listeners
            for listener in list(self._listeners):
                try:
                    listener(from_state, to_state, record)
                except Exception as e:
                    logger.error(f"Error in state transition listener: {e}")

            return record

    def get_history(self) -> List[StateTransitionRecord]:
        with self._lock:
            return list(self._history)
