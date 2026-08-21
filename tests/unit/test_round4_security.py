"""
Tests for Luna Round 4 security fixes:
- Domain simulator safety gate enforcement
- Action category server-side reclassification
- Task state HMAC integrity
- TOCTOU-safe vision path
- Image URL scheme validation
"""

import json
import os
from unittest.mock import patch

import pytest

from src.contracts.contracts import (
    ActionProposal,
    ExecutionOutcome,
    RiskTier,
    generate_contract_id,
)
from src.domains.drone.drone_simulator import DroneSimulation as DroneSimulator
from src.domains.home.home_simulator import HomeSimulation as HomeSimulator
from src.models import VisionRequest
from src.models.gpt4o_adapters import GPT4oVisionAdapter, validate_image_path
from src.persistence.task_state import CheckpointType, TaskStateManager, TaskStatus


class TestDomainSimulatorSafetyGate:
    """Domain simulators must reject physical actions without safety_approved=True."""

    def test_home_unlock_without_safety_approved_rejected(self):
        sim = HomeSimulator()
        proposal = sim.create_action_proposal(
            action_type="unlock",
            target_entity="lock_front",
            action_params={},
        )
        assert not proposal.safety_approved
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED
        assert "Safety Gateway" in result.deviation_reason

    def test_home_lock_without_safety_approved_rejected(self):
        sim = HomeSimulator()
        proposal = sim.create_action_proposal(
            action_type="lock",
            target_entity="lock_front",
            action_params={},
        )
        assert not proposal.safety_approved
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED
        assert "Safety Gateway" in result.deviation_reason

    def test_home_unlock_with_safety_approved_executes(self):
        sim = HomeSimulator()
        proposal = sim.create_action_proposal(
            action_type="unlock",
            target_entity="lock_front",
            action_params={},
        )
        proposal.safety_approved = True
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.COMPLETED

    def test_home_set_temperature_without_safety_approved_allowed(self):
        """Non-physical actions (set_temperature) don't require safety_approved."""
        sim = HomeSimulator()
        proposal = sim.create_action_proposal(
            action_type="set_temperature",
            target_entity="hvac_ground",
            action_params={"temperature": 22.0},
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.COMPLETED

    def test_drone_action_without_safety_approved_rejected(self):
        sim = DroneSimulator()
        proposal = ActionProposal(
            action_id=generate_contract_id(),
            action_type="takeoff",
            target_entity="drone_1",
            action_parameters={"altitude": 10.0},
            risk_tier=RiskTier.TIER_1,
        )
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.REJECTED
        assert "Safety Gateway" in result.deviation_reason

    def test_drone_action_with_safety_approved_executes(self):
        sim = DroneSimulator()
        proposal = ActionProposal(
            action_id=generate_contract_id(),
            action_type="takeoff",
            target_entity="drone_1",
            action_parameters={"altitude": 10.0},
            risk_tier=RiskTier.TIER_1,
        )
        proposal.safety_approved = True
        result = sim.execute_action(proposal)
        assert result.outcome == ExecutionOutcome.COMPLETED


class TestActionCategoryServerSide:
    """API must server-side reclassify action_category based on device_id."""

    def test_action_with_device_id_must_be_physical(self):
        from src.api import ORIONAPI, ORIONResponse, ORIONStatus
        from src.api.auth import AuthConfig, AuthManager
        from src.api.permissions import PermissionChecker, PermissionLevel
        # Use explicit auth manager to avoid singleton caching issues
        auth = AuthManager(AuthConfig(enabled=True, api_key="test-api-key-round4"))
        api = ORIONAPI(auth_manager=auth)
        PermissionChecker.register_agent_permissions("test-agent", [PermissionLevel.WRITE])
        response = api.execute(
            action={"action_type": "move", "device_id": "robot_1", "action_category": "DIGITAL"},
            domain="vehicle",
            token="test-api-key-round4",
            agent_id="test-agent",
        )
        assert response.status == ORIONStatus.UNAUTHORIZED
        assert "PHYSICAL" in response.error

    def test_physical_without_device_id_rejected(self):
        from src.api import ORIONAPI, ORIONResponse, ORIONStatus
        from src.api.auth import AuthConfig, AuthManager
        from src.api.permissions import PermissionChecker, PermissionLevel
        auth = AuthManager(AuthConfig(enabled=True, api_key="test-api-key-round4"))
        api = ORIONAPI(auth_manager=auth)
        PermissionChecker.register_agent_permissions("test-agent", [PermissionLevel.WRITE])
        response = api.execute(
            action={"action_type": "move", "action_category": "PHYSICAL"},
            domain="vehicle",
            token="test-api-key-round4",
            agent_id="test-agent",
        )
        assert response.status == ORIONStatus.UNAUTHORIZED
        assert "device_id" in response.error


class TestTaskStateHMAC:
    """Task state must have HMAC integrity protection."""

    def test_state_saved_with_hmac(self, tmp_path):
        path = str(tmp_path / "state.json")
        mgr = TaskStateManager(path)
        mgr.create_task("Test", "test task")
        # Verify file exists and has HMAC
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert "hmac" in data
        assert "state" in data
        assert data["hmac"]  # non-empty

    def test_state_load_verifies_hmac(self, tmp_path):
        path = str(tmp_path / "state.json")
        mgr1 = TaskStateManager(path)
        t = mgr1.create_task("Persistent", "survives")
        mgr1.start_task(t.id)

        # New manager should load successfully
        mgr2 = TaskStateManager(path)
        assert len(mgr2.list_tasks()) == 1
        loaded = mgr2.get_task(t.id)
        assert loaded.name == "Persistent"

    def test_tampered_state_rejected(self, tmp_path):
        path = str(tmp_path / "state.json")
        mgr1 = TaskStateManager(path)
        mgr1.create_task("Original", "original task")

        # Tamper with the state file
        with open(path) as f:
            data = json.load(f)
        data["state"]["tasks"][list(data["state"]["tasks"].keys())[0]]["name"] = "Tampered"
        with open(path, "w") as f:
            json.dump(data, f)

        # Loading should fail HMAC verification — manager starts fresh (no tasks loaded)
        mgr2 = TaskStateManager(path)
        # State was rejected, so no tasks should be loaded
        assert len(mgr2.list_tasks()) == 0


class TestVisionSecurity:
    """TOCTOU-safe vision path and URL scheme validation."""

    def test_validate_image_path_returns_bytes(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()
        img = base_dir / "test.png"
        img.write_bytes(b"fake image")
        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            result = validate_image_path("test.png")
            assert isinstance(result, bytes)
            assert result == b"fake image"

    def test_unsafe_url_scheme_rejected(self):
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError, match="Unsafe image URL scheme"):
            adapter._prepare_image(VisionRequest(image_url="http://example.com/img.png"))

    def test_http_url_rejected(self):
        adapter = GPT4oVisionAdapter(api_key="test-key")
        with pytest.raises(ValueError, match="Unsafe image URL scheme"):
            adapter._prepare_image(VisionRequest(image_url="ftp://example.com/img.png"))

    def test_https_url_allowed(self):
        adapter = GPT4oVisionAdapter(api_key="test-key")
        result = adapter._prepare_image(VisionRequest(image_url="https://example.com/img.png"))
        assert result == "https://example.com/img.png"

    def test_data_url_allowed(self):
        adapter = GPT4oVisionAdapter(api_key="test-key")
        result = adapter._prepare_image(VisionRequest(image_url="data:image/png;base64,iVBORw0KGgo="))
        assert result.startswith("data:image/png;base64,")
