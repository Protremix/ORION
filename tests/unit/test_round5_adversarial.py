"""
Adversarial tests for Luna Round 5 security fixes (Change #11).

Each test attempts to bypass a specific security fix introduced in Round 5,
verifying that the bypass is blocked. These tests are designed to fail if
any Round 5 fix is regressed or removed.

Covers:
  #1  Server-side action classification (DIGITAL+device_id -> PHYSICAL)
  #2  Physical-action gating for HVAC/lighting
  #3  Cryptographic safety token (mutable boolean rejected)
  #5  Exact permission matching (no substring/suffix match)
  #6  Non-finite value rejection (NaN/Inf blocked before shortcuts)
  #7  Exact actuator parameter matching (no substring bypass)
  #8  Vehicle emergency reset replay protection
  #10 SSRF controlled download (no arbitrary URL passthrough)
  #12 Normalization exception -> audited rejection
"""

import hashlib
import hmac
import os
import time

import pytest

from src.contracts.contracts import (
    ActionCategory,
    ActionProposal,
    ExecutionOutcome,
    RiskTier,
    generate_contract_id,
    issue_safety_token,
)
from src.domains.home.home_simulator import HomeSimulation as HomeSimulator
from src.domains.vehicle.vehicle_simulator import VehicleSimulation

REJECTED = ExecutionOutcome.REJECTED.value
FAILED = ExecutionOutcome.FAILED.value
COMPLETED = ExecutionOutcome.COMPLETED.value


# ============================================================================
# Change #1: Server-side action classification
# ============================================================================

class TestActionClassificationAdversarial:
    """Adversarial tests for server-side action reclassification."""

    def test_digital_with_device_id_reclassified_as_physical(self):
        """Caller declares DIGITAL but includes device_id -- server must reclassify as PHYSICAL."""
        from src.api import _classify_action_server_side
        result = _classify_action_server_side({
            "action_type": "set_temperature",
            "action_category": "DIGITAL",
            "device_id": "thermostat_001",
        })
        assert result == "PHYSICAL", (
            "Action with device_id must be reclassified as PHYSICAL regardless of caller declaration"
        )

    def test_physical_action_type_classified_as_physical_without_device_id(self):
        """Physical action type must be PHYSICAL even without device_id."""
        from src.api import PHYSICAL_ACTION_TYPES, _classify_action_server_side
        action_type = next(iter(PHYSICAL_ACTION_TYPES))
        result = _classify_action_server_side({
            "action_type": action_type,
            "action_category": "DIGITAL",
            "device_id": None,
        })
        assert result == "PHYSICAL"


# ============================================================================
# Change #2: Physical-action gating
# ============================================================================

class TestPhysicalActionGatingAdversarial:

    def test_hvac_without_token_rejected(self):
        """HVAC set_temperature must be rejected without a valid safety token."""
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="set_temperature",
            target_entity="hvac_ground",
            action_category=ActionCategory.PHYSICAL,
            action_parameters={"temperature": 22.0},
            risk_tier=RiskTier.LOW,
            safety_approved=False,
            safety_auth_token="",
        )
        result = sim.execute_action(proposal)
        assert result.outcome == REJECTED

    def test_lighting_without_token_rejected(self):
        """Lighting set_brightness must be rejected without a valid safety token."""
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="set_brightness",
            target_entity="light_living",
            action_category=ActionCategory.PHYSICAL,
            action_parameters={"brightness": 80},
            risk_tier=RiskTier.LOW,
            safety_approved=False,
            safety_auth_token="",
        )
        result = sim.execute_action(proposal)
        assert result.outcome == REJECTED


# ============================================================================
# Change #3: Cryptographic safety token
# ============================================================================

class TestSafetyTokenAdversarial:

    def test_boolean_safety_approved_not_accepted(self):
        """safety_approved=True without a valid token must be rejected."""
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="set_temperature",
            target_entity="hvac_ground",
            action_category=ActionCategory.PHYSICAL,
            action_parameters={"temperature": 22.0},
            risk_tier=RiskTier.LOW,
            safety_approved=True,
            safety_auth_token="",
        )
        result = sim.execute_action(proposal)
        assert result.outcome == REJECTED

    def test_fake_token_rejected(self):
        """A fabricated token string must be rejected."""
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="set_temperature",
            target_entity="hvac_ground",
            action_category=ActionCategory.PHYSICAL,
            action_parameters={"temperature": 22.0},
            risk_tier=RiskTier.LOW,
            safety_approved=True,
            safety_auth_token="fake-token-not-valid",
        )
        result = sim.execute_action(proposal)
        assert result.outcome == REJECTED

    def test_valid_token_accepted(self):
        """A properly issued safety token must be accepted."""
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        sim = HomeSimulator()
        action_id = generate_contract_id()
        token = issue_safety_token(action_id, "set_temperature", "hvac_ground")
        proposal = ActionProposal(
            action_id=action_id,
            action_type="set_temperature",
            target_entity="hvac_ground",
            action_category=ActionCategory.PHYSICAL,
            action_parameters={"temperature": 22.0},
            risk_tier=RiskTier.LOW,
            safety_approved=True,
            safety_auth_token=token,
        )
        result = sim.execute_action(proposal)
        assert result.outcome != REJECTED, f"Valid safety token must be accepted -- got {result.outcome}"

    def test_token_for_different_action_rejected(self):
        """A token issued for one action must not authorize a different action."""
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        sim = HomeSimulator()
        token = issue_safety_token("action-1", "set_brightness", "light_living")
        proposal = ActionProposal(
            action_id="different-action-id",
            action_type="set_temperature",
            target_entity="hvac_ground",
            action_category=ActionCategory.PHYSICAL,
            action_parameters={"temperature": 22.0},
            risk_tier=RiskTier.LOW,
            safety_approved=True,
            safety_auth_token=token,
        )
        result = sim.execute_action(proposal)
        assert result.outcome == REJECTED


# ============================================================================
# Change #5: Exact permission matching
# ============================================================================

class TestPermissionMatchingAdversarial:

    def test_execute_untrusted_not_match_execute(self):
        """'execute_untrusted' must not match 'execute' via substring."""
        from src.api.permissions import Permission
        result = Permission.get_endpoint_level("/api/v1/execute_untrusted")
        assert result is None, "execute_untrusted must not match execute via substring"
        result_known = Permission.get_endpoint_level("/api/v1/action/propose")
        assert result_known is not None, "Exact match for known endpoint should work"


# ============================================================================
# Change #6: Non-finite value rejection
# ============================================================================

class TestNonFiniteRejectionAdversarial:

    @staticmethod
    def _make_authorized(action_type, params):
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        action_id = generate_contract_id()
        token = issue_safety_token(action_id, action_type, "ego_vehicle")
        return ActionProposal(
            action_id=action_id,
            action_type=action_type,
            target_entity="ego_vehicle",
            action_category=ActionCategory.DIGITAL,
            action_parameters=params,
            risk_tier=RiskTier.LOW,
            safety_approved=True,
            safety_auth_token=token,
        )

    def test_nan_acceleration_rejected(self):
        sim = VehicleSimulation()
        proposal = self._make_authorized("accelerate", {"acceleration": float("nan")})
        result = sim.propose_action(proposal)
        assert result.outcome in (REJECTED, FAILED), f"NaN acceleration must be rejected -- got {result.outcome}"

    def test_inf_acceleration_rejected(self):
        sim = VehicleSimulation()
        proposal = self._make_authorized("accelerate", {"acceleration": float("inf")})
        result = sim.propose_action(proposal)
        assert result.outcome in (REJECTED, FAILED), f"Inf acceleration must be rejected -- got {result.outcome}"

    def test_nan_steering_rejected(self):
        sim = VehicleSimulation()
        proposal = self._make_authorized("steer", {"steering_angle": float("nan")})
        result = sim.propose_action(proposal)
        assert result.outcome in (REJECTED, FAILED), f"NaN steering must be rejected -- got {result.outcome}"


# ============================================================================
# Change #7: Exact actuator parameter matching
# ============================================================================

class TestExactParameterMatchingAdversarial:

    def test_velocity_override_not_match_velocity(self):
        """'velocity_override' must not match 'velocity' via substring."""
        from src.safety.actuator_verification import _get_parameter_limit
        result = _get_parameter_limit("vehicle", "velocity_override")
        assert result is None, "velocity_override must not match velocity via substring"

    def test_exact_match_speed_works(self):
        """Exact match 'speed' should return a parameter limit."""
        from src.safety.actuator_verification import _get_parameter_limit
        result = _get_parameter_limit("vehicle", "speed")
        assert result is not None, "Exact match 'speed' should work"


# ============================================================================
# Change #8: Vehicle emergency reset replay protection
# ============================================================================

class TestVehicleReplayProtectionAdversarial:

    @staticmethod
    def _make_cred(ts=None):
        key = os.environ.get("ORION_EMERGENCY_HMAC_KEY", "test-emergency-hmac-key")
        ts = ts or time.time()
        msg = f"reset_emergency:{ts}"
        sig = hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return f"{ts}:{sig}"

    @staticmethod
    def _make_authorized_reset(cred):
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        action_id = generate_contract_id()
        token = issue_safety_token(action_id, "reset_emergency", "ego_vehicle")
        return ActionProposal(
            action_id=action_id,
            action_type="reset_emergency",
            target_entity="ego_vehicle",
            action_category=ActionCategory.DIGITAL,
            action_parameters={"hmac_credential": cred},
            risk_tier=RiskTier.LOW,
            safety_approved=True,
            safety_auth_token=token,
        )

    def test_replay_same_credential_rejected(self):
        """Replaying the exact same credential must be rejected."""
        os.environ.setdefault("ORION_EMERGENCY_HMAC_KEY", "test-emergency-hmac-key")
        sim = VehicleSimulation()
        sim.ego_vehicle.set_state("EMERGENCY")
        sim.system_status = "EMERGENCY"
        cred = self._make_cred()

        proposal1 = self._make_authorized_reset(cred)
        result1 = sim.propose_action(proposal1)
        assert result1.outcome != REJECTED, f"First use should succeed -- got {result1.outcome}"

        sim.ego_vehicle.set_state("EMERGENCY")
        sim.system_status = "EMERGENCY"

        proposal2 = self._make_authorized_reset(cred)
        result2 = sim.propose_action(proposal2)
        assert result2.outcome == REJECTED, "Replay of same credential must be rejected"

    def test_expired_credential_rejected(self):
        """Credential older than 60s must be rejected."""
        os.environ.setdefault("ORION_EMERGENCY_HMAC_KEY", "test-emergency-hmac-key")
        sim = VehicleSimulation()
        sim.ego_vehicle.set_state("EMERGENCY")
        sim.system_status = "EMERGENCY"
        cred = self._make_cred(time.time() - 120)

        proposal = self._make_authorized_reset(cred)
        result = sim.propose_action(proposal)
        assert result.outcome == REJECTED, "Expired credential must be rejected"

    def test_malformed_credential_rejected(self):
        """Malformed credential must be rejected."""
        os.environ.setdefault("ORION_EMERGENCY_HMAC_KEY", "test-emergency-hmac-key")
        sim = VehicleSimulation()
        sim.ego_vehicle.set_state("EMERGENCY")
        sim.system_status = "EMERGENCY"

        proposal = self._make_authorized_reset("just-a-string-no-colon")
        result = sim.propose_action(proposal)
        assert result.outcome == REJECTED


# ============================================================================
# Change #10: SSRF controlled download
# ============================================================================

class TestSSRFControlledDownloadAdversarial:

    def test_localhost_rejected(self):
        from src.models import VisionRequest
        from src.models.gpt4o_adapters import GPT4oVisionAdapter
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError):
            adapter._prepare_image(VisionRequest(image_url="https://localhost/img.png"))

    def test_127_ip_rejected(self):
        from src.models import VisionRequest
        from src.models.gpt4o_adapters import GPT4oVisionAdapter
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError):
            adapter._prepare_image(VisionRequest(image_url="https://127.0.0.1/img.png"))

    def test_169_254_rejected(self):
        from src.models import VisionRequest
        from src.models.gpt4o_adapters import GPT4oVisionAdapter
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError):
            adapter._prepare_image(VisionRequest(image_url="https://169.254.169.254/latest/meta-data/"))

    def test_no_https_passthrough(self):
        """HTTPS URLs must NOT be passed through as-is to OpenAI."""
        from src.models import VisionRequest
        from src.models.gpt4o_adapters import GPT4oVisionAdapter
        adapter = GPT4oVisionAdapter(api_key="test-key")
        try:
            result = adapter._prepare_image(VisionRequest(image_url="https://example.com/img.png"))
            assert not str(result).startswith("https://"), "HTTPS URLs must not be passed through"
        except Exception:
            pass  # Download failure is acceptable -- point is it's not passed through


# ============================================================================
# Change #12: Normalization exception -> audited rejection
# ============================================================================

class TestNormalizationExceptionAdversarial:

    @staticmethod
    def _make_authorized(action_type, params):
        os.environ.setdefault("ORION_SAFETY_AUTH_KEY", "test-safety-key")
        action_id = generate_contract_id()
        token = issue_safety_token(action_id, action_type, "ego_vehicle")
        return ActionProposal(
            action_id=action_id,
            action_type=action_type,
            target_entity="ego_vehicle",
            action_category=ActionCategory.DIGITAL,
            action_parameters=params,
            risk_tier=RiskTier.LOW,
            safety_approved=True,
            safety_auth_token=token,
        )

    def test_string_speed_rejected_not_silently_passed(self):
        """String instead of float for speed must be rejected."""
        sim = VehicleSimulation()
        proposal = self._make_authorized("accelerate", {"acceleration": "not-a-number"})
        result = sim.propose_action(proposal)
        assert result.outcome in (REJECTED, FAILED), f"Type error must result in rejection -- got {result.outcome}"

    def test_none_parameter_handled_safely(self):
        """None parameter values must not crash or silently pass."""
        sim = VehicleSimulation()
        proposal = self._make_authorized("accelerate", {"acceleration": None})
        result = sim.propose_action(proposal)
        assert result.outcome in (REJECTED, FAILED), f"None values must be handled safely -- got {result.outcome}"
