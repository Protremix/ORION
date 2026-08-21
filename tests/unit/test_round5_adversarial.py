"""
Adversarial tests for Luna Round 5 security bypass vectors.
Each test attempts to exploit a previously identified bypass vector
and verifies it is now blocked.

Change #11 (Luna Round 5): Adversarial tests for all 12 required changes.
"""

import hashlib
import hmac
import json
import math
import os
import time
from unittest.mock import patch

import pytest

from src.contracts.contracts import (
    ActionProposal,
    ExecutionOutcome,
    RiskTier,
    generate_contract_id,
    issue_safety_token,
)
from src.api.permissions import PermissionChecker, PermissionLevel
from src.domains.drone.drone_simulator import DroneSimulation as DroneSimulator
from src.domains.home.home_simulator import HomeSimulation as HomeSimulator
from src.domains.vehicle.vehicle_simulator import VehicleSimulation as VehicleSimulator
from src.domains.industrial.industrial_simulator import IndustrialSimulation as IndustrialSimulator
from src.models import VisionRequest
from src.models.gpt4o_adapters import GPT4oVisionAdapter


class TestActionCategoryServerSideReclassification:
    """Vector 4/10: caller declares DIGITAL without device_id to bypass physical classification."""

    def test_digital_action_with_device_id_reclassified_as_physical(self):
        """An action declared as DIGITAL but with a device_id must be treated as PHYSICAL."""
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="unlock",
            action_category="DIGITAL",  # Caller tries to bypass
            risk_tier=RiskTier.MEDIUM,
            safety_approved=False,
            parameters={"device_id": "front_door"},
        )
        result = sim.execute_action(proposal)
        # Should be rejected because safety_approved is False, even though caller said DIGITAL
        assert result.outcome == ExecutionOutcome.REJECTED.value

    def test_physical_action_without_device_id_rejected(self):
        """An action declared as PHYSICAL without device_id must be rejected."""
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="set_temperature",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=False,
            parameters={},  # No device_id
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED.value


class TestSafetyTokenCryptographic:
    """Vector 5/10 + Vector E: safety_approved is mutable boolean — replaced with cryptographic token."""

    def test_mutable_boolean_not_accepted(self):
        """A plain True boolean must not be accepted as safety authorization."""
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="unlock",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,  # Plain boolean — must not work
            parameters={"device_id": "front_door"},
        )
        result = sim.execute_action(proposal)
        # Must be rejected — plain boolean is not a cryptographic token
        assert result.outcome == ExecutionOutcome.REJECTED.value

    def test_valid_safety_token_accepted(self):
        """A valid cryptographic safety token must be accepted."""
        os.environ["ORION_SAFETY_AUTH_KEY"] = "test-safety-key"
        token = issue_safety_token("unlock", "front_door")
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="unlock",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,
            safety_token=token,
            parameters={"device_id": "front_door"},
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.COMPLETED.value

    def test_forged_safety_token_rejected(self):
        """A forged safety token must be rejected."""
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="unlock",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,
            safety_token="forged:token:12345",  # Not cryptographically valid
            parameters={"device_id": "front_door"},
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED.value

    def test_token_replay_for_different_action_rejected(self):
        """A safety token issued for one action must not work for another."""
        os.environ["ORION_SAFETY_AUTH_KEY"] = "test-safety-key"
        token = issue_safety_token("unlock", "front_door")
        sim = HomeSimulator()
        proposal = ActionProposal(
            action_type="set_temperature",  # Different action
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,
            safety_token=token,
            parameters={"device_id": "front_door"},
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED.value


class TestExactPermissionMatching:
    """Vector 9 + Change #5: substring permission matching allows execute_untrusted to match execute."""

    def test_substring_permission_does_not_grant_access(self):
        """Permission for 'execute' must NOT grant access to 'execute_untrusted'."""
        checker = PermissionChecker
        checker._registry.clear()
        checker._registry["test_agent"] = [PermissionLevel.OPERATOR]
        checker._action_permissions.clear()
        checker._action_permissions["execute"] = PermissionLevel.OPERATOR
        checker._action_permissions["execute_untrusted"] = PermissionLevel.SUPERVISOR

        # Agent has permission for "execute" but NOT "execute_untrusted"
        result = checker.check_permission("test_agent", "execute_untrusted")
        assert result is False, "Substring match must not grant access to execute_untrusted"

    def test_exact_permission_match_grants_access(self):
        """Exact match for 'execute' must grant access to 'execute'."""
        checker = PermissionChecker
        checker._registry.clear()
        checker._registry["test_agent"] = [PermissionLevel.OPERATOR]
        checker._action_permissions.clear()
        checker._action_permissions["execute"] = PermissionLevel.OPERATOR

        result = checker.check_permission("test_agent", "execute")
        assert result is True


class TestActuatorParameterAllowlist:
    """Change #7: fuzzy actuator parameter substring match."""

    def test_non_allowlisted_parameter_rejected(self):
        """A parameter not in the allowlist must be rejected, not fuzzy-matched."""
        sim = HomeSimulator()
        os.environ["ORION_SAFETY_AUTH_KEY"] = "test-safety-key"
        token = issue_safety_token("set_temperature", "hvac_ground")
        proposal = ActionProposal(
            action_type="set_temperature",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,
            safety_token=token,
            parameters={"device_id": "hvac_ground", "temperature": 22.0, "malicious_param": "evil"},
        )
        result = sim.execute_action(proposal)
        # Must reject — malicious_param is not in the allowlist
        assert result.outcome == ExecutionOutcome.REJECTED.value

    def test_allowlisted_parameter_accepted(self):
        """Only allowlisted parameters should be accepted."""
        sim = HomeSimulator()
        os.environ["ORION_SAFETY_AUTH_KEY"] = "test-safety-key"
        token = issue_safety_token("set_temperature", "hvac_ground")
        proposal = ActionProposal(
            action_type="set_temperature",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,
            safety_token=token,
            parameters={"device_id": "hvac_ground", "temperature": 22.0},
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.COMPLETED.value


class TestNonFiniteActuatorValues:
    """Change #6: NaN accepted for stop/emergency commands."""

    def test_nan_temperature_rejected(self):
        """NaN temperature must be rejected."""
        sim = HomeSimulator()
        os.environ["ORION_SAFETY_AUTH_KEY"] = "test-safety-key"
        token = issue_safety_token("set_temperature", "hvac_ground")
        proposal = ActionProposal(
            action_type="set_temperature",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,
            safety_token=token,
            parameters={"device_id": "hvac_ground", "temperature": float("nan")},
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED.value

    def test_infinity_rejected(self):
        """Infinity temperature must be rejected."""
        sim = HomeSimulator()
        os.environ["ORION_SAFETY_AUTH_KEY"] = "test-safety-key"
        token = issue_safety_token("set_temperature", "hvac_ground")
        proposal = ActionProposal(
            action_type="set_temperature",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,
            safety_token=token,
            parameters={"device_id": "hvac_ground", "temperature": float("inf")},
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED.value

    def test_negative_infinity_rejected(self):
        """Negative infinity must be rejected."""
        sim = HomeSimulator()
        os.environ["ORION_SAFETY_AUTH_KEY"] = "test-safety-key"
        token = issue_safety_token("set_temperature", "hvac_ground")
        proposal = ActionProposal(
            action_type="set_temperature",
            action_category="PHYSICAL",
            risk_tier=RiskTier.MEDIUM,
            safety_approved=True,
            safety_token=token,
            parameters={"device_id": "hvac_ground", "temperature": float("-inf")},
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED.value


class TestStalePermissionRevocation:
    """Change #4: stale permissions persist after revocation."""

    def test_revoked_agent_cannot_execute(self, tmp_path):
        """After revocation, agent must not retain permissions."""
        checker = PermissionChecker
        checker._storage_path = str(tmp_path / "perms.db")
        checker._registry.clear()
        checker._registry["agent_a"] = [PermissionLevel.OPERATOR]
        checker._registry["agent_b"] = [PermissionLevel.OPERATOR]
        checker.save_to_storage()

        # Revoke agent_a
        del checker._registry["agent_a"]
        checker.save_to_storage()

        # Reload from storage
        checker._registry.clear()
        checker.load_from_storage()

        # agent_a should NOT be in registry
        assert "agent_a" not in checker._registry
        assert "agent_b" in checker._registry


class TestVehicleEmergencyResetReplayProtection:
    """Change #8: vehicle emergency reset no replay protection."""

    def test_replayed_credential_rejected(self):
        """The same emergency reset credential must not be usable twice."""
        os.environ["ORION_EMERGENCY_HMAC_KEY"] = "test-emergency-hmac-key"
        sim = VehicleSimulator()
        lease_id = generate_contract_id()

        # Generate a valid credential
        ts = time.time()
        message = f"reset_emergency:{ts}"
        sig = hmac.new(
            os.environ["ORION_EMERGENCY_HMAC_KEY"].encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        credential = f"{ts}:{sig}"

        # First use should succeed
        proposal1 = ActionProposal(
            action_type="reset_emergency",
            action_category="PHYSICAL",
            risk_tier=RiskTier.HIGH,
            safety_approved=True,
            parameters={"hmac_credential": credential},
        )
        result1 = sim.execute_action(proposal1, lease_id=lease_id)
        # May be COMPLETED or REJECTED depending on state — but not error

        # Second use of SAME credential must be rejected (replay)
        proposal2 = ActionProposal(
            action_type="reset_emergency",
            action_category="PHYSICAL",
            risk_tier=RiskTier.HIGH,
            safety_approved=True,
            parameters={"hmac_credential": credential},
        )
        result2 = sim.execute_action(proposal2, lease_id=lease_id)
        assert result2.outcome == ExecutionOutcome.REJECTED.value
        assert "replay" in result2.deviation_reason.lower() or "already used" in result2.deviation_reason.lower()

    def test_stale_credential_rejected(self):
        """A credential with an old timestamp must be rejected."""
        os.environ["ORION_EMERGENCY_HMAC_KEY"] = "test-emergency-hmac-key"
        sim = VehicleSimulator()
        lease_id = generate_contract_id()

        # Generate a credential with an old timestamp (120 seconds ago)
        old_ts = time.time() - 120.0
        message = f"reset_emergency:{old_ts}"
        sig = hmac.new(
            os.environ["ORION_EMERGENCY_HMAC_KEY"].encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        credential = f"{old_ts}:{sig}"

        proposal = ActionProposal(
            action_type="reset_emergency",
            action_category="PHYSICAL",
            risk_tier=RiskTier.HIGH,
            safety_approved=True,
            parameters={"hmac_credential": credential},
        )
        result = sim.execute_action(proposal, lease_id=lease_id)
        assert result.outcome == ExecutionOutcome.REJECTED.value
        assert "stale" in result.deviation_reason.lower() or "expired" in result.deviation_reason.lower()

    def test_malformed_credential_rejected(self):
        """A credential without timestamp:signature format must be rejected."""
        os.environ["ORION_EMERGENCY_HMAC_KEY"] = "test-emergency-hmac-key"
        sim = VehicleSimulator()
        lease_id = generate_contract_id()

        proposal = ActionProposal(
            action_type="reset_emergency",
            action_category="PHYSICAL",
            risk_tier=RiskTier.HIGH,
            safety_approved=True,
            parameters={"hmac_credential": "just_a_plain_hash_no_timestamp"},
        )
        result = sim.execute_action(proposal, lease_id=lease_id)
        assert result.outcome == ExecutionOutcome.REJECTED.value


class TestExceptionBeforeAudit:
    """Change #12 + Vector F: exceptions escape before audit."""

    def test_exception_does_not_skip_audit(self):
        """When an exception occurs during action execution, the audit must still be recorded."""
        sim = HomeSimulator()
        lease_id = generate_contract_id()

        # Create a proposal that will cause an exception (e.g., invalid action type)
        proposal = ActionProposal(
            action_type="nonexistent_action_type",
            action_category="DIGITAL",
            risk_tier=RiskTier.LOW,
            safety_approved=False,
            parameters={},
        )
        # This should not raise — it should be caught and audited
        result = sim.execute_action(proposal, lease_id=lease_id)
        assert result.outcome == ExecutionOutcome.REJECTED.value
        # Audit log should have an entry for this rejected action
        assert sim.audit_log is not None
        assert len(sim.audit_log) > 0
        # The last audit entry should be for our rejected action
        last_entry = sim.audit_log[-1]
        assert last_entry.get("action_type") == "nonexistent_action_type" or \
               last_entry.get("outcome") == ExecutionOutcome.REJECTED.value


class TestSSRFControlledDownload:
    """Change #10: SSRF via arbitrary HTTPS URL passthrough."""

    def test_https_url_not_passed_through(self):
        """HTTPS URLs must be downloaded locally, not passed through to OpenAI."""
        adapter = GPT4oVisionAdapter(api_key="test-key")
        try:
            result = adapter._prepare_image(VisionRequest(image_url="https://example.com/img.png"))
            # If it succeeds, result must be a data URL, not the original HTTPS URL
            assert result.startswith("data:image/"), f"HTTPS URL was passed through: {result[:50]}"
        except ValueError as e:
            # Download failure is acceptable — point is it's NOT passed through
            assert "download" in str(e).lower() or "ssrf" in str(e).lower() or \
                   "not found" in str(e).lower() or "resolve" in str(e).lower()

    def test_internal_ip_rejected(self):
        """HTTPS URL pointing to internal IP must be rejected."""
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError, match="SSRF"):
            adapter._prepare_image(VisionRequest(image_url="https://127.0.0.1/img.png"))

    def test_localhost_rejected(self):
        """HTTPS URL pointing to localhost must be rejected."""
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError, match="SSRF"):
            adapter._prepare_image(VisionRequest(image_url="https://localhost/img.png"))

    def test_private_network_rejected(self):
        """HTTPS URL pointing to private network must be rejected."""
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError, match="SSRF"):
            adapter._prepare_image(VisionRequest(image_url="https://192.168.1.1/img.png"))

    def test_unresolvable_hostname_rejected(self):
        """HTTPS URL with unresolvable hostname must be rejected (fail-closed)."""
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError, match="resolve|SSRF"):
            adapter._prepare_image(VisionRequest(image_url="https://this-host-does-not-exist-ever-12345.invalid/img.png"))
