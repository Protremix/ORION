"""ORION Phase 1 - Configuration and Policy Management System.

This module implements the PolicyManager and versioned Policy engine specified in
the ORION Architecture v0.5 baseline (Sections 8 and 19).

Key Capabilities:
- Versioned safety limits (speed, force, temperature, spatial bounds, CBF margins).
- Capability tier enforcement (Tier 0 Minimal through Tier 4 Critical).
- Risk tier classification and approval requirements (minimal, low, moderate, high, critical).
- Cryptographic policy signing (HMAC-SHA256) and signature verification.
- Enforced immutability for active policy snapshots.
- Signed policy rollbacks with atomic swapping and system state transition to DEGRADED.
- Last-known-safe conflict resolution with fallback safe state and EMERGENCY state.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enums and Constants
# -----------------------------------------------------------------------------

class PolicyStatus(str, Enum):
    """Lifecycle states of a Safety Policy (v0.5 Section 8.1)."""
    DRAFT = "DRAFT"
    SIGNED = "SIGNED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    ROLLED_BACK = "ROLLED_BACK"
    EMERGENCY = "EMERGENCY"


class SystemSafetyState(str, Enum):
    """Global system safety operational state."""
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    EMERGENCY = "EMERGENCY"


# Hardcoded Minimal Fallback Safe Policy for Last-Known-Safe Conflict Resolution (Section 8.4)
DEFAULT_FALLBACK_SAFE_POLICY_DICT: Dict[str, Any] = {
    "policy_id": "policy-fallback-safe-state",
    "version": "0.0.1-fallback",
    "description": "Hardcoded Minimal Fallback Safe Policy for emergency degradation",
    "status": PolicyStatus.SIGNED.value,
    "signer": "SafetyAssuranceCore",
    "signature": "",  # Fallback policy has no signature — must be verified independently
    "created_at": 0,
    "is_last_known_safe": True,
    "safety_limits": {
        "linear_velocity_m_s": {"max": 0.1, "warning": 0.1, "default": 0.05},
        "angular_velocity_rad_s": {"max": 0.2, "warning": 0.2, "default": 0.1},
        "joint_torque_Nm": {"max": 5.0, "warning": 4.0},
        "end_effector_force_N": {"max": 5.0, "warning": 4.0, "default": 1.0},
        "temperature_celsius": {"max": 60.0, "warning": 50.0, "critical": 70.0},
        "cbf_safety_margin_m": {"min": 0.5, "warning": 0.6, "critical": 0.3},
        "spatial_bounds": {"x_min": -2.0, "x_max": 2.0, "y_min": -2.0, "y_max": 2.0, "z_min": 0.0, "z_max": 1.5},
        "execution_timeout_ms": {"max": 2000, "default": 1000},
        "clock_skew_tolerance_ms": 2.0
    },
    "capability_tiers": {
        "tier_0_minimal": {
            "allowed_actions": ["observe", "estimate_state", "diagnose", "ping", "audit_log"],
            "max_velocity_m_s": 0.0,
            "max_force_N": 0.0
        },
        "tier_1_low": {
            "allowed_actions": ["observe", "estimate_state", "diagnose", "soft_stop"],
            "max_velocity_m_s": 0.1,
            "max_force_N": 5.0
        }
    },
    "risk_tiers": {
        "minimal": {"level": 1, "permitted_channels": ["realtime", "async"]},
        "low": {"level": 2, "permitted_channels": ["realtime", "async"]}
    }
}


# -----------------------------------------------------------------------------
# Policy Dataclass
# -----------------------------------------------------------------------------

@dataclass
class Policy:
    """Versioned Safety Policy definition."""
    policy_id: str = field(default_factory=lambda: f"policy-{uuid.uuid4()}")
    version: str = "1.0.0"
    description: str = "ORION Safety Policy"
    safety_limits: Dict[str, Any] = field(default_factory=dict)
    capability_tiers: Dict[str, Any] = field(default_factory=dict)
    risk_tiers: Dict[str, Any] = field(default_factory=dict)
    status: str = PolicyStatus.DRAFT.value
    signer: Optional[str] = None
    signature: Optional[str] = None
    created_at: int = field(default_factory=lambda: int(time.time()))
    activated_at: Optional[int] = None
    is_last_known_safe: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert Policy to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Policy":
        """Instantiate Policy from dictionary."""
        return cls(**data)


# -----------------------------------------------------------------------------
# PolicyManager Class
# -----------------------------------------------------------------------------

class PolicyManager:
    """Manages Policy creation, signing, activation, enforcement, and rollback."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        policy_dir: Optional[str] = None
    ):
        """Initialize PolicyManager with signing key and policy directory."""
        is_production = os.environ.get("ORION_ENV") == "production"
        env_key = os.environ.get("ORION_POLICY_KEY") or os.environ.get("ORION_POLICY_SECRET_KEY")

        if secret_key:
            self.secret_key = secret_key
        elif env_key:
            self.secret_key = env_key
        else:
            # Fail-closed: no policy key means no policies can be signed or activated
            # All actions will be denied
            self.secret_key = None
            logger.warning("No policy signing key provided (ORION_POLICY_KEY not set). Policy enforcement is fail-closed — all actions will be denied.")
        self.policy_dir = policy_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "policies"
        )

        self._policy_registry: Dict[str, Policy] = {}
        self._active_policy: Optional[Policy] = None
        self._last_known_safe_policy: Optional[Policy] = None
        self._system_state: str = SystemSafetyState.NORMAL.value
        self._policy_history: List[Dict[str, Any]] = []

        # Attempt auto-loading default configuration files if available
        self._initialize_default_policies()

    @property
    def system_state(self) -> str:
        """Current global system safety operational state."""
        return self._system_state

    # -------------------------------------------------------------------------
    # Policy Hashing and Cryptographic Signing
    # -------------------------------------------------------------------------

    def compute_policy_hash(self, policy: Policy) -> str:
        """Compute deterministic SHA-256 hash of policy content."""
        content = {
            "policy_id": policy.policy_id,
            "version": policy.version,
            "safety_limits": policy.safety_limits,
            "capability_tiers": policy.capability_tiers,
            "risk_tiers": policy.risk_tiers,
        }
        canonical_json = json.dumps(content, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def sign_policy(
        self,
        policy: Policy,
        secret_key: Optional[str] = None,
        signer_id: str = "SafetyAssurance"
    ) -> Policy:
        """Cryptographically sign a safety policy (Section 8.2)."""
        key = secret_key or self.secret_key
        policy_hash = self.compute_policy_hash(policy)

        mac = hmac.new(
            key.encode("utf-8"),
            policy_hash.encode("utf-8"),
            hashlib.sha256
        )
        policy.signer = signer_id
        policy.signature = mac.hexdigest()
        policy.status = PolicyStatus.SIGNED.value

        self._policy_registry[policy.version] = policy
        logger.info("Policy %s (v%s) signed by %s", policy.policy_id, policy.version, signer_id)
        return policy

    def verify_policy_signature(
        self,
        policy: Policy,
        secret_key: Optional[str] = None
    ) -> bool:
        """Verify HMAC-SHA256 signature of a policy."""
        if not policy.signature or not policy.signer:
            return False

        key = secret_key or self.secret_key
        policy_hash = self.compute_policy_hash(policy)
        expected_mac = hmac.new(
            key.encode("utf-8"),
            policy_hash.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(policy.signature, expected_mac)

    # -------------------------------------------------------------------------
    # Policy Lifecycle & Activation Rules (Section 8.5)
    # -------------------------------------------------------------------------

    def activate_policy(
        self,
        policy_or_version: Any,
        secret_key: Optional[str] = None
    ) -> Policy:
        """Activate a signed policy with atomic swap and immutability (Section 8.5).

        Rules:
        1. No unsigned policy.
        2. Version monotonicity (new_version >= active_version unless rollback).
        3. Atomic activation & immutable snapshot storage.
        """
        if isinstance(policy_or_version, str):
            if policy_or_version not in self._policy_registry:
                raise ValueError(f"Policy version '{policy_or_version}' not found in registry")
            target_policy = self._policy_registry[policy_or_version]
        elif isinstance(policy_or_version, Policy):
            target_policy = policy_or_version
        else:
            raise TypeError("policy_or_version must be a version string or Policy instance")

        # Rule 1: No unsigned or invalid-signature policy loaded
        if not self.verify_policy_signature(target_policy, secret_key):
            raise ValueError(f"Policy '{target_policy.version}' has invalid or missing signature and cannot be activated")

        # Rule 2: Version monotonicity check
        if self._active_policy and self._system_state == SystemSafetyState.NORMAL.value:
            if target_policy.version < self._active_policy.version:
                raise ValueError(
                    f"Version monotonicity violation: target version {target_policy.version} "
                    f"< current active version {self._active_policy.version}"
                )

        # Archive old active policy if exists
        if self._active_policy:
            self._active_policy.status = PolicyStatus.ARCHIVED.value

        # Prepare new active policy
        now = int(time.time())
        active_copy = deepcopy(target_policy)
        active_copy.status = PolicyStatus.ACTIVE.value
        active_copy.activated_at = now
        active_copy.is_last_known_safe = True

        # Atomic Swap
        self._active_policy = active_copy
        self._last_known_safe_policy = deepcopy(active_copy)
        self._system_state = SystemSafetyState.NORMAL.value

        # Audit history tracking
        self._policy_history.append({
            "action": "ACTIVATE",
            "policy_id": active_copy.policy_id,
            "version": active_copy.version,
            "activated_at": now,
            "signer": active_copy.signer
        })

        logger.info("Activated safety policy v%s (ID: %s)", active_copy.version, active_copy.policy_id)
        return deepcopy(self._active_policy)

    def get_active_policy(self) -> Policy:
        """Get an immutable deep copy of the current active policy."""
        if not self._active_policy:
            raise RuntimeError("No active policy loaded in PolicyManager")
        return deepcopy(self._active_policy)

    # -------------------------------------------------------------------------
    # Policy Rollback & Last-Known-Safe Conflict Resolution (Section 8.3 & 8.4)
    # -------------------------------------------------------------------------

    def rollback_policy(
        self,
        target_version: Optional[str] = None,
        reason: str = "Defective policy rollback initiated"
    ) -> Tuple[Policy, str]:
        """Rollback active policy to last-known-safe or target signed policy.

        Transitions system to DEGRADED state (or EMERGENCY if conflict resolution fails).
        Returns (activated_policy, system_state).
        """
        logger.warning("Initiating policy rollback. Reason: %s", reason)
        target_policy: Optional[Policy] = None

        if target_version and target_version in self._policy_registry:
            cand = self._policy_registry[target_version]
            if self.verify_policy_signature(cand):
                target_policy = cand

        if not target_policy and self._last_known_safe_policy:
            if self.verify_policy_signature(self._last_known_safe_policy):
                target_policy = self._last_known_safe_policy

        # Section 8.4: Conflict Resolution (Priority: Hardware safe-state > last-known-safe policy > no policy)
        if not target_policy:
            logger.error("Last-known-safe policy missing or invalid. Entering EMERGENCY state — all actions denied.")
            self._system_state = SystemSafetyState.EMERGENCY.value
            return None

        # Archive broken active policy
        if self._active_policy:
            self._active_policy.status = PolicyStatus.ROLLED_BACK.value

        # Activate rollback policy in DEGRADED mode
        now = int(time.time())
        active_copy = deepcopy(target_policy)
        active_copy.status = PolicyStatus.ROLLED_BACK.value
        active_copy.activated_at = now

        self._active_policy = active_copy
        self._system_state = SystemSafetyState.DEGRADED.value

        self._policy_history.append({
            "action": "ROLLBACK",
            "policy_id": active_copy.policy_id,
            "version": active_copy.version,
            "reason": reason,
            "timestamp": now
        })

        logger.warning("System entered DEGRADED state with active rollback policy v%s", active_copy.version)
        return deepcopy(self._active_policy), self._system_state

    def trigger_emergency_state(self, reason: str = "Hardware E-Stop / Policy Conflict") -> str:
        """Trigger emergency system safety state."""
        self._system_state = SystemSafetyState.EMERGENCY.value
        if self._active_policy:
            self._active_policy.status = PolicyStatus.EMERGENCY.value

        self._policy_history.append({
            "action": "EMERGENCY_TRIGGER",
            "reason": reason,
            "timestamp": int(time.time())
        })
        logger.critical("EMERGENCY STATE TRIGGERED: %s", reason)
        return self._system_state

    # -------------------------------------------------------------------------
    # Action Enforcement & Safety Limits Validation
    # -------------------------------------------------------------------------

    def check_action_allowed(
        self,
        action_type: str,
        risk_tier: str,
        capability_tier: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate candidate action parameters against active policy rules.

        Returns:
            Dict containing 'allowed' (bool), 'reason' (str), and applicable 'constraints'.
        """
        if self._system_state == SystemSafetyState.EMERGENCY.value:
            if action_type not in ["emergency_stop", "isolate_power", "mandate_safe_state"]:
                return {
                    "allowed": False,
                    "reason": f"System in EMERGENCY state. Action '{action_type}' rejected.",
                    "constraints": {}
                }

        policy = self.get_active_policy()
        limits = policy.safety_limits
        cap_tiers = policy.capability_tiers
        risk_tiers = policy.risk_tiers

        # 1. Capability Tier Verification
        cap_def = cap_tiers.get(capability_tier, {})
        allowed_actions = cap_def.get("allowed_actions", [])
        if action_type not in allowed_actions:
            return {
                "allowed": False,
                "reason": f"Action '{action_type}' not permitted under capability tier '{capability_tier}'",
                "constraints": {}
            }

        # 2. Capability Tier Motion Speed & Force Boundaries
        max_cap_vel = cap_def.get("max_velocity_m_s", limits.get("linear_velocity_m_s", {}).get("max", 1.5))
        max_cap_force = cap_def.get("max_force_N", limits.get("end_effector_force_N", {}).get("max", 50.0))

        # 3. Parameter Boundary Validation
        constraints = {}

        # Linear Velocity Check
        req_vel = parameters.get("linear_velocity", parameters.get("speed", None))
        if req_vel is not None:
            max_vel = min(limits.get("linear_velocity_m_s", {}).get("max", 1.5), max_cap_vel)
            if float(req_vel) > max_vel:
                return {
                    "allowed": False,
                    "reason": f"Requested velocity ({req_vel} m/s) exceeds policy limit ({max_vel} m/s)",
                    "constraints": {"max_velocity": max_vel}
                }
            constraints["max_velocity"] = max_vel

        # Force Limit Check
        req_force = parameters.get("force", parameters.get("end_effector_force", None))
        if req_force is not None:
            max_force = min(limits.get("end_effector_force_N", {}).get("max", 50.0), max_cap_force)
            if float(req_force) > max_force:
                return {
                    "allowed": False,
                    "reason": f"Requested force ({req_force} N) exceeds policy limit ({max_force} N)",
                    "constraints": {"max_force": max_force}
                }
            constraints["max_force"] = max_force

        # Temperature Limit Check
        current_temp = parameters.get("temperature", None)
        if current_temp is not None:
            max_temp = limits.get("temperature_celsius", {}).get("max", 75.0)
            if float(current_temp) >= max_temp:
                return {
                    "allowed": False,
                    "reason": f"System temperature ({current_temp} °C) violates max limit ({max_temp} °C)",
                    "constraints": {"max_temperature": max_temp}
                }

        # Spatial Bounds Check
        pos = parameters.get("position", None)
        if pos and len(pos) == 3:
            sb = limits.get("spatial_bounds", {})
            x, y, z = pos[0], pos[1], pos[2]
            if not (sb.get("x_min", -10) <= x <= sb.get("x_max", 10) and
                    sb.get("y_min", -10) <= y <= sb.get("y_max", 10) and
                    sb.get("z_min", 0) <= z <= sb.get("z_max", 3)):
                return {
                    "allowed": False,
                    "reason": f"Target position {pos} violates spatial bounds {sb}",
                    "constraints": {"spatial_bounds": sb}
                }
            constraints["spatial_bounds"] = sb

        # 4. Risk Tier Requirements
        risk_def = risk_tiers.get(risk_tier, {})
        req_channel = risk_def.get("permitted_channels", ["realtime", "async"])

        return {
            "allowed": True,
            "reason": f"Action '{action_type}' permitted under policy v{policy.version}",
            "constraints": constraints,
            "permitted_channels": req_channel,
            "requires_safety_assurance": risk_def.get("requires_safety_assurance", False)
        }

    # -------------------------------------------------------------------------
    # Helper & Auto-Initialization Methods
    # -------------------------------------------------------------------------

    def create_policy(
        self,
        version: str,
        safety_limits: Dict[str, Any],
        capability_tiers: Dict[str, Any],
        risk_tiers: Dict[str, Any],
        description: str = "New Safety Policy",
        policy_id: Optional[str] = None
    ) -> Policy:
        """Create a new Policy in DRAFT status."""
        pid = policy_id or f"policy-v{version}-{uuid.uuid4().hex[:8]}"
        policy = Policy(
            policy_id=pid,
            version=version,
            description=description,
            safety_limits=safety_limits,
            capability_tiers=capability_tiers,
            risk_tiers=risk_tiers,
            status=PolicyStatus.DRAFT.value
        )
        self._policy_registry[version] = policy
        return policy

    def load_policy_from_file(self, filepath: str) -> Policy:
        """Load policy object from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        policy = Policy.from_dict(data)
        self._policy_registry[policy.version] = policy
        return policy

    def _initialize_default_policies(self) -> None:
        """Load default safety limits and capability tiers if config files exist.
        Fail-closed: if no key or no config files, no policy is activated."""
        if self.secret_key is None:
            logger.warning("No policy signing key — skipping default policy initialization (fail-closed).")
            return

        try:
            limits_file = os.path.join(self.policy_dir, "default_safety_limits.json")
            caps_file = os.path.join(self.policy_dir, "capability_tiers.json")

            if os.path.exists(limits_file) and os.path.exists(caps_file):
                with open(limits_file, "r", encoding="utf-8") as f:
                    limits_data = json.load(f)
                with open(caps_file, "r", encoding="utf-8") as f:
                    caps_data = json.load(f)

                default_policy = Policy(
                    policy_id=limits_data.get("policy_id", "default-safety-v1"),
                    version=limits_data.get("version", "1.0.0"),
                    description=limits_data.get("description", "Default Safety Policy"),
                    safety_limits=limits_data.get("safety_limits", {}),
                    capability_tiers=caps_data.get("capability_tiers", {}),
                    risk_tiers=caps_data.get("risk_tiers", {}),
                    status=PolicyStatus.DRAFT.value
                )
                self.sign_policy(default_policy, signer_id="SafetyAssurance")
                self.activate_policy(default_policy)
            else:
                logger.warning("Default policy config files not found. No policy activated (fail-closed).")
        except Exception as exc:
            logger.error("Could not auto-initialize default policies: %s. No policy activated (fail-closed).", exc)
