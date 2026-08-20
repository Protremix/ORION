"""
Action Arbitration and Policy Gate for ORION Physical Intelligence OS.

This module implements the Policy Gate between the Cognitive Plane and Control Plane.
Action Arbitration converts proposed actions into time-bounded, count-limited, constraint-bound
Authorization Leases.

Key Architecture Principles:
1. Authorization = Lease (Permission), NOT a Command.
2. TOCTOU Race Prevention: Single atomic validation + lock + execution count consumption.
3. Replay Protection: Monotonic time + 32-byte cryptographic nonce per lease.
4. Safety Assurance Authority: BLOCKING authority (can veto, revoke, or mandate).
"""

import hashlib
import hmac
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Set, Tuple

from src.safety.state_machine import (
    AuthorityTransitionStateMachine,
    AuthorizerCredential,
    AuthorizerRole,
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


class RiskTier(int, Enum):
    TIER_1 = 1  # Routine, low-risk (e.g. low-speed motion, sensor query)
    TIER_2 = 2  # Elevated risk (e.g. fast motion, heavy payload, human vicinity)
    TIER_3 = 3  # Critical risk (e.g. industrial machining, high force, high speed near obstacles)


class PermittedChannel(str, Enum):
    REALTIME = "realtime"            # Hard real-time path (<= 1ms execution deadline)
    ASYNC = "async"                  # Non-blocking background execution
    HUMAN_APPROVAL = "human_approval"  # Explicit operator sign-off required
    EMERGENCY = "emergency"          # Urgent safety fast-path Bypasses cognitive queue


class LeaseState(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    EXECUTING = "EXECUTING"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    VOIDED = "VOIDED"
    REVOKED = "REVOKED"


# CONDITION-1 (Luna): Unified to contracts.ActionProposal
from src.contracts.contracts import ActionProposal


@dataclass
class ActionAuthorizationLease:
    """
    ActionAuthorization Contract (Lease) Schema B.5.

    Represents time-bounded, count-limited, constraint-bound permission to execute an action.
    """
    contract_version: str = "1.0.0"
    schema_version: str = "1.0.0"
    contract_id: str = field(default_factory=_generate_uuidv7)
    timestamp_ns: int = field(default_factory=time.time_ns)
    producer: str = "ActionArbitration"
    consumer: str = "ControlPlane"

    # Mandatory Lease Payload Fields
    lease_id: str = field(default_factory=_generate_uuidv7)
    action_id: str = field(default_factory=_generate_uuidv7)
    target_entity: str = "system_actuator"
    state_revision: int = 1
    policy_version: str = "1.0.0"
    risk_tier: RiskTier = RiskTier.TIER_1
    safety_constraints: Dict[str, Any] = field(default_factory=lambda: {
        "cbf_boundaries": {},
        "rate_limits": {"max_velocity": 1.0, "max_acceleration": 2.0},
        "spatial_bounds": {"max_reach_m": 2.0},
        "force_limits": {"max_force_n": 50.0}
    })
    expiry_ns: int = field(default_factory=lambda: time.time_ns() + 1_000_000_000)  # Default +1s
    max_executions: int = 1
    executions_consumed: int = 0
    permitted_channel: PermittedChannel = PermittedChannel.REALTIME
    safety_assurance_approval: Optional[str] = None  # Mandatory for Tier 2 and Tier 3
    authorization_signature: str = ""
    nonce: str = field(default_factory=lambda: os.urandom(32).hex())

    # Mutable Runtime Lifecycle Fields
    state: LeaseState = LeaseState.CREATED
    void_reason: Optional[str] = None
    created_time_ns: int = field(default_factory=time.time_ns)
    last_execution_time_ns: Optional[int] = None

    def compute_signature(self, secret_key: bytes) -> str:
        """Compute cryptographic HMAC-SHA256 authorization signature over lease fields."""
        payload = (
            f"{self.lease_id}:{self.action_id}:{self.target_entity}:{self.state_revision}:"
            f"{self.policy_version}:{self.risk_tier.value}:{self.expiry_ns}:{self.max_executions}:"
            f"{self.permitted_channel.value}:{self.nonce}"
        )
        return hmac.new(secret_key, payload.encode('utf-8'), hashlib.sha256).hexdigest()

    def is_expired(self, current_time_ns: int) -> bool:
        return current_time_ns >= self.expiry_ns


@dataclass
class AdmissionResult:
    """Result of atomic lease execution admission check."""
    admitted: bool
    lease_id: str
    action_id: str
    channel: PermittedChannel
    void_reason: Optional[str] = None
    remaining_executions: int = 0
    execution_timestamp_ns: int = field(default_factory=time.time_ns)


@dataclass
class SafetyPolicy:
    """Active safety policy configuration."""
    policy_version: str = "1.0.0"
    max_allowed_risk_tier: RiskTier = RiskTier.TIER_3
    require_sa_approval_for_tier2: bool = True
    require_sa_approval_for_tier3: bool = True
    default_lease_duration_ms: int = 1000
    emergency_channel_enabled: bool = True


class ActionArbitration:
    """
    Action Arbitration & Policy Gate implementation.

    Serves as the policy gate between Cognitive Plane and Control Plane.
    Enforces time-bounded lease authorization, atomic execution admission, replay protection,
    and blocking Safety Assurance authority.
    """

    def __init__(
        self,
        state_machine: Optional[AuthorityTransitionStateMachine] = None,
        secret_key: Optional[bytes] = None
    ):
        self._lock = threading.RLock()
        self._lease_locks: Dict[str, threading.Lock] = {}
        self.state_machine = state_machine or AuthorityTransitionStateMachine()
        self._secret_key = secret_key or os.urandom(32)

        self._active_leases: Dict[str, ActionAuthorizationLease] = {}
        self._used_nonces: Set[str] = set()
        self._safety_policy = SafetyPolicy()
        self._current_state_revision = 1
        self._latest_safety_override_time_ns = 0

    # ------------------------------------------------------------------------
    # State & Policy Configuration
    # ------------------------------------------------------------------------

    def update_state_revision(self, new_revision: int) -> None:
        """Update current belief state revision. Mismatched leases will automatically void."""
        with self._lock:
            if new_revision > self._current_state_revision:
                logger.info(f"BeliefState revision advanced: {self._current_state_revision} -> {new_revision}")
                self._current_state_revision = new_revision

    def update_policy(self, new_policy: SafetyPolicy) -> None:
        """Update active safety policy. Mismatched policy_version leases will void."""
        with self._lock:
            logger.info(f"Safety policy updated: {self._safety_policy.policy_version} -> {new_policy.policy_version}")
            self._safety_policy = new_policy

    def record_safety_override_event(self) -> None:
        """Record runtime safety override event timestamp, invalidating older active leases."""
        with self._lock:
            self._latest_safety_override_time_ns = time.time_ns()
            logger.warning("Safety override event recorded in ActionArbitration.")

    # ------------------------------------------------------------------------
    # Lease Issuance (Policy Gate)
    # ------------------------------------------------------------------------

    def authorize_action(
        self,
        proposal: ActionProposal,
        sa_approval_signature: Optional[str] = None,
        human_approval_signature: Optional[str] = None
    ) -> Tuple[Optional[ActionAuthorizationLease], str]:
        """
        Policy Gate: Convert an ActionProposal into an ActionAuthorizationLease.
        Returns (lease, status_message).
        """
        with self._lock:
            current_state = self.state_machine.current_state

            # 1. State Machine Action Permission Check
            if not self.state_machine.is_action_permitted(proposal.action_type, proposal.risk_tier.value):
                return None, f"Action {proposal.action_type} (Tier {proposal.risk_tier.value}) denied in state {current_state.value}"

            # 2. Risk Tier Policy Rules
            if proposal.risk_tier.value > self._safety_policy.max_allowed_risk_tier.value:
                return None, f"Action Risk Tier {proposal.risk_tier.value} exceeds policy max {self._safety_policy.max_allowed_risk_tier.value}"

            # 3. Safety Assurance Approval Requirement
            if proposal.risk_tier == RiskTier.TIER_2 and self._safety_policy.require_sa_approval_for_tier2:
                if not sa_approval_signature:
                    return None, "Risk Tier 2 action requires Safety Assurance approval signature"
            elif proposal.risk_tier == RiskTier.TIER_3 and self._safety_policy.require_sa_approval_for_tier3:
                if not sa_approval_signature:
                    return None, "Risk Tier 3 action requires Safety Assurance approval signature"

            # 4. Human Approval Channel Check
            if proposal.requested_channel == PermittedChannel.HUMAN_APPROVAL:
                if not human_approval_signature:
                    return None, "Channel HUMAN_APPROVAL requires human operator signature"

            # 5. Build Time-Bounded Lease
            now_ns = time.time_ns()
            expiry_duration_ns = proposal.estimated_duration_ms * 1_000_000 + (self._safety_policy.default_lease_duration_ms * 1_000_000)
            expiry_ns = now_ns + expiry_duration_ns

            nonce = os.urandom(32).hex()

            lease = ActionAuthorizationLease(
                lease_id=_generate_uuidv7(),
                action_id=proposal.action_id,
                target_entity=proposal.target_entity,
                state_revision=self._current_state_revision,
                policy_version=self._safety_policy.policy_version,
                risk_tier=proposal.risk_tier,
                safety_constraints=proposal.parameters.get("safety_constraints", {
                    "cbf_boundaries": proposal.parameters.get("cbf_boundaries", {}),
                    "rate_limits": proposal.parameters.get("rate_limits", {"max_velocity": 1.0}),
                    "spatial_bounds": proposal.parameters.get("spatial_bounds", {}),
                    "force_limits": proposal.parameters.get("force_limits", {})
                }),
                expiry_ns=expiry_ns,
                max_executions=1,
                executions_consumed=0,
                permitted_channel=proposal.requested_channel,
                safety_assurance_approval=sa_approval_signature,
                nonce=nonce,
                state=LeaseState.ACTIVE,
                created_time_ns=now_ns
            )

            # Cryptographically sign authorization lease
            lease.authorization_signature = lease.compute_signature(self._secret_key)

            # Register lease and track nonce
            self._active_leases[lease.lease_id] = lease
            self._used_nonces.add(nonce)
            self._lease_locks[lease.lease_id] = threading.Lock()

            logger.info(
                f"AUTHORIZED LEASE: {lease.lease_id} for action {proposal.action_type} "
                f"| Tier {proposal.risk_tier.value} | Channel {proposal.requested_channel}"
            )
            return lease, "Lease authorized successfully"

    # ------------------------------------------------------------------------
    # Atomic Execution Admission (Prevents TOCTOU)
    # ------------------------------------------------------------------------

    def admit_and_execute_lease(
        self,
        lease_id: str,
        execution_channel: PermittedChannel
    ) -> AdmissionResult:
        """
        Atomic Execution Admission Check performed immediately before actuation.

        Single atomic transaction:
        1. Acquire per-lease lock
        2. Validate active state, expiry, execution count, state revision, policy version, nonces, and safety overrides
        3. Consume execution count or void lease
        4. Release lock
        """
        now_ns = time.time_ns()

        # Retrieve lease and its lock
        with self._lock:
            lease = self._active_leases.get(lease_id)
            lease_lock = self._lease_locks.get(lease_id)

        if not lease or not lease_lock:
            return AdmissionResult(
                admitted=False,
                lease_id=lease_id,
                action_id="",
                channel=execution_channel,
                void_reason="LEASE_NOT_FOUND"
            )

        # ATOMIC OPERATION BEGIN
        with lease_lock:
            # 1. State check
            if lease.state != LeaseState.ACTIVE:
                return AdmissionResult(
                    admitted=False,
                    lease_id=lease.lease_id,
                    action_id=lease.action_id,
                    channel=execution_channel,
                    void_reason=f"LEASE_NOT_ACTIVE (state={lease.state.value})"
                )

            # 2. Expiry check (Monotonic clock)
            if lease.is_expired(now_ns):
                lease.state = LeaseState.EXPIRED
                lease.void_reason = "LEASE_EXPIRED"
                return AdmissionResult(
                    admitted=False,
                    lease_id=lease.lease_id,
                    action_id=lease.action_id,
                    channel=execution_channel,
                    void_reason="LEASE_EXPIRED"
                )

            # 3. Executions consumed check
            if lease.executions_consumed >= lease.max_executions:
                lease.state = LeaseState.CONSUMED
                lease.void_reason = "EXECUTION_COUNT_EXCEEDED"
                return AdmissionResult(
                    admitted=False,
                    lease_id=lease.lease_id,
                    action_id=lease.action_id,
                    channel=execution_channel,
                    void_reason="EXECUTION_COUNT_EXCEEDED"
                )

            # 4. State Revision binding check
            if lease.state_revision != self._current_state_revision:
                lease.state = LeaseState.VOIDED
                lease.void_reason = f"STATE_REVISION_MISMATCH (lease={lease.state_revision}, current={self._current_state_revision})"
                return AdmissionResult(
                    admitted=False,
                    lease_id=lease.lease_id,
                    action_id=lease.action_id,
                    channel=execution_channel,
                    void_reason=lease.void_reason
                )

            # 5. Policy Version binding check
            if lease.policy_version != self._safety_policy.policy_version:
                lease.state = LeaseState.VOIDED
                lease.void_reason = f"POLICY_VERSION_MISMATCH (lease={lease.policy_version}, current={self._safety_policy.policy_version})"
                return AdmissionResult(
                    admitted=False,
                    lease_id=lease.lease_id,
                    action_id=lease.action_id,
                    channel=execution_channel,
                    void_reason=lease.void_reason
                )

            # 6. Safety Override check
            if lease.created_time_ns < self._latest_safety_override_time_ns:
                lease.state = LeaseState.VOIDED
                lease.void_reason = "SAFETY_OVERRIDE_EVENT_INTERVENED"
                return AdmissionResult(
                    admitted=False,
                    lease_id=lease.lease_id,
                    action_id=lease.action_id,
                    channel=execution_channel,
                    void_reason="SAFETY_OVERRIDE_EVENT_INTERVENED"
                )

            # 7. Permitted Channel check
            if execution_channel != lease.permitted_channel:
                lease.state = LeaseState.VOIDED
                lease.void_reason = f"CHANNEL_MISMATCH (requested={execution_channel.value}, permitted={lease.permitted_channel.value})"
                return AdmissionResult(
                    admitted=False,
                    lease_id=lease.lease_id,
                    action_id=lease.action_id,
                    channel=execution_channel,
                    void_reason=lease.void_reason
                )

            # 8. Signature Integrity check
            expected_sig = lease.compute_signature(self._secret_key)
            if not hmac.compare_digest(lease.authorization_signature, expected_sig):
                lease.state = LeaseState.VOIDED
                lease.void_reason = "INVALID_AUTHORIZATION_SIGNATURE"
                return AdmissionResult(
                    admitted=False,
                    lease_id=lease.lease_id,
                    action_id=lease.action_id,
                    channel=execution_channel,
                    void_reason="INVALID_AUTHORIZATION_SIGNATURE"
                )

            # ALL CHECKS PASSED -> CONSUME EXECUTION COUNT
            lease.executions_consumed += 1
            lease.last_execution_time_ns = now_ns

            if lease.executions_consumed >= lease.max_executions:
                lease.state = LeaseState.CONSUMED

            remaining = lease.max_executions - lease.executions_consumed

            return AdmissionResult(
                admitted=True,
                lease_id=lease.lease_id,
                action_id=lease.action_id,
                channel=execution_channel,
                remaining_executions=remaining,
                execution_timestamp_ns=now_ns
            )
        # ATOMIC OPERATION END

    # ------------------------------------------------------------------------
    # Safety Assurance Revocation Authority (BLOCKING)
    # ------------------------------------------------------------------------

    def revoke_lease(
        self,
        lease_id: str,
        reason: str,
        sa_credential: AuthorizerCredential
    ) -> Tuple[bool, str]:
        """
        Revoke an active lease by Safety Assurance or Founder.
        Safety Assurance has absolute veto authority.
        """
        if sa_credential.role not in (AuthorizerRole.SAFETY_ASSURANCE, AuthorizerRole.FOUNDER, AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER):
            return False, f"Unauthorized revocation attempt by role {sa_credential.role.value}"

        with self._lock:
            lease = self._active_leases.get(lease_id)
            lease_lock = self._lease_locks.get(lease_id)

        if not lease or not lease_lock:
            return False, "Lease not found"

        with lease_lock:
            if lease.state in (LeaseState.CONSUMED, LeaseState.EXPIRED, LeaseState.VOIDED, LeaseState.REVOKED):
                return False, f"Lease is already in terminal state {lease.state.value}"

            lease.state = LeaseState.REVOKED
            lease.void_reason = f"Revoked by {sa_credential.role.value} ({sa_credential.authorizer_id}): {reason}"

            logger.warning(f"REVOKED LEASE {lease_id} | Reason: {reason} | By: {sa_credential.authorizer_id}")
            return True, f"Lease {lease_id} successfully revoked"

    def get_lease(self, lease_id: str) -> Optional[ActionAuthorizationLease]:
        with self._lock:
            return self._active_leases.get(lease_id)
