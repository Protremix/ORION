"""ORION Phase 4 — Smart Home Domain Tests.

Tests the smart home domain simulation including HVAC, lighting, security,
smart locks, smoke detectors, energy monitoring, and evacuation mode.
"""

import hashlib
import time
import hmac
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.contracts.contracts import ActionProposal, ExecutionOutcome, RiskTier, generate_contract_id
from src.domains.home.home_entities import (
    EnergyMonitor,
    EvacuationController,
    HomeEntity,
    HVACController,
    LightingController,
    RoomEntity,
    SecuritySensor,
    SmartLock,
    SmokeDetector,
)
from src.domains.home.home_simulator import HomeSimulation
from src.contracts.contracts import issue_safety_token


class TestHomeDomain(unittest.TestCase):
    """Test smart home domain entities and simulation."""

    def setUp(self):
        self.sim = HomeSimulation()

    def test_room_entity_creation_and_state(self):
        """Room entity can be created with correct properties."""
        room = self.sim.living_room
        self.assertEqual(room.name, "Living Room")
        self.assertEqual(room.area, 25.0)
        self.assertEqual(room.floor, 0)
        self.assertEqual(room.temperature, 22.0)
        self.assertEqual(room.humidity, 45.0)
        self.assertTrue(room.is_occupied)

        # Update temperature and occupancy
        room.set_temperature(25.0)
        room.set_occupancy(3)
        self.assertEqual(room.temperature, 25.0)
        self.assertEqual(room.occupancy_count, 3)
        self.assertGreater(room.state_revision, 1)

    def test_hvac_controller(self):
        """HVAC controller responds to temperature changes."""
        hvac = self.sim.hvac_ground
        hvac.set_mode("heating")
        hvac.set_target_temp(25.0)

        action = hvac.update(20.0)
        self.assertEqual(action, "heating")
        self.assertGreater(hvac.fan_speed, 0)

        action = hvac.update(25.0)
        self.assertEqual(action, "idle")
        self.assertEqual(hvac.fan_speed, 0)

    def test_hvac_cooling_mode(self):
        """HVAC cooling mode works correctly."""
        hvac = self.sim.hvac_ground
        hvac.set_mode("cooling")
        hvac.set_target_temp(18.0)

        action = hvac.update(25.0)
        self.assertEqual(action, "cooling")
        self.assertGreater(hvac.fan_speed, 0)

    def test_hvac_zone_control(self):
        """HVAC supports multiple zones."""
        hvac = self.sim.hvac_ground
        self.assertIn("room_living", hvac.zones)
        self.assertIn("room_kitchen", hvac.zones)

    def test_lighting_controller(self):
        """Lighting controller responds to brightness and scenes."""
        light = self.sim.light_living
        light.set_brightness(80)
        self.assertEqual(light.brightness, 80)
        self.assertEqual(light.status, "ON")

        light.set_brightness(0)
        self.assertEqual(light.brightness, 0)
        self.assertEqual(light.status, "OFF")

        light.set_scene("movie")
        self.assertEqual(light.scene, "movie")
        self.assertEqual(light.brightness, 20)

    def test_security_sensor_door_and_motion(self):
        """Security sensors detect door opening and motion."""
        door = self.sim.front_door
        self.assertEqual(door.state, "closed")
        door.open()
        self.assertEqual(door.state, "open")
        self.assertTrue(door.is_triggered)

        motion = self.sim.motion_living
        self.assertEqual(motion.state, "no_motion")
        motion.trigger_motion()
        self.assertEqual(motion.state, "motion_detected")
        self.assertTrue(motion.is_triggered)

    def test_smart_lock_normal_and_fail_safe(self):
        """Smart lock supports normal lock/unlock and fail-safe emergency unlock."""
        lock = self.sim.front_lock
        self.assertTrue(lock.is_locked)

        lock.unlock()
        self.assertFalse(lock.is_locked)

        lock.lock()
        self.assertTrue(lock.is_locked)

        # Fail-safe unlock
        lock.fail_safe_unlock()
        self.assertFalse(lock.is_locked)
        self.assertTrue(lock.fail_safe_unlocked)

        # Cannot lock during fail-safe
        lock.lock()
        self.assertFalse(lock.is_locked)  # Still unlocked

        # Reset fail-safe
        lock.reset_fail_safe()
        lock.lock()
        self.assertTrue(lock.is_locked)

    def test_smoke_detector_thresholds(self):
        """Smoke detector transitions through warning and critical states."""
        sd = self.sim.smoke_kitchen

        # Normal
        sd.update_levels(10.0, 5.0)
        self.assertEqual(sd.state, "normal")

        # Warning
        sd.update_levels(60.0, 40.0)
        self.assertEqual(sd.state, "warning")
        self.assertTrue(sd.is_warning())

        # Critical
        sd.update_levels(150.0, 120.0)
        self.assertEqual(sd.state, "critical")
        self.assertTrue(sd.is_critical())

    def test_energy_monitor(self):
        """Energy monitor tracks power usage and costs."""
        em = self.sim.energy
        em.update_usage(2.5)
        self.assertEqual(em.power_usage_kw, 2.5)

        em.update_usage(3.0)
        self.assertEqual(em.peak_usage_kw, 3.0)

        em.add_daily_usage(10.0)
        self.assertEqual(em.daily_usage_kwh, 10.0)
        self.assertEqual(em.cost_estimate_eur, 2.5)  # 10 * 0.25

    def test_evacuation_mode(self):
        """Fire emergency triggers full evacuation sequence."""
        result = self.sim.trigger_fire_emergency("room_kitchen")

        self.assertEqual(result["status"], "EMERGENCY")
        self.assertEqual(self.sim.system_status, "EMERGENCY")

        # Smoke detector should be critical
        self.assertTrue(self.sim.smoke_kitchen.is_critical())
        self.assertTrue(self.sim.smoke_kitchen.evacuation_triggered)

        # Front door should be fail-safe unlocked
        self.assertTrue(self.sim.front_lock.fail_safe_unlocked)
        self.assertFalse(self.sim.front_lock.is_locked)

        # All lights should be in evacuation mode
        self.assertEqual(self.sim.light_living.scene, "evacuation")
        self.assertEqual(self.sim.light_kitchen.scene, "evacuation")
        self.assertEqual(self.sim.light_bedroom.scene, "evacuation")
        self.assertEqual(self.sim.light_living.brightness, 100)

        # HVAC should be shutdown
        self.assertEqual(self.sim.hvac_ground.mode, "off")
        self.assertFalse(self.sim.hvac_ground.is_active)

        # Evacuation controller active
        self.assertTrue(self.sim.evacuation.is_active)

        # Clear emergency
        ts = time.time()
        self.sim.clear_emergency(hmac_credential=hmac.new(os.environ.get("ORION_EMERGENCY_HMAC_KEY", "test-emergency-hmac-key").encode(), f"clear_emergency:{ts}".encode(), hashlib.sha256).hexdigest(), timestamp=ts)
        self.assertEqual(self.sim.system_status, "NOMINAL")
        self.assertFalse(self.sim.evacuation.is_active)

    def test_full_autonomous_cycle(self):
        """Full autonomous cycle: sensor → state → plan → act → verify."""
        result = self.sim.run_normal_cycle()

        self.assertEqual(result["cycle"], "normal")
        self.assertEqual(result["system_status"], "NOMINAL")
        self.assertIn("power_usage", result)
        self.assertGreater(self.sim.state_revision, 1)

    def test_scenario_runner(self):
        """Scenario runner handles normal, fire, and intrusion scenarios."""
        # Normal
        result = self.sim.run_scenario("normal")
        self.assertEqual(result["cycle"], "normal")

        # Fire
        result = self.sim.run_scenario("fire")
        self.assertEqual(result["status"], "EMERGENCY")
        ts = time.time()
        self.sim.clear_emergency(hmac_credential=hmac.new(os.environ.get("ORION_EMERGENCY_HMAC_KEY", "test-emergency-hmac-key").encode(), f"clear_emergency:{ts}".encode(), hashlib.sha256).hexdigest(), timestamp=ts)

        # Intrusion
        result = self.sim.run_scenario("intrusion")
        self.assertEqual(result["status"], "ALERT")

        # Energy optimization
        result = self.sim.run_scenario("energy_optimization")
        self.assertEqual(result["scenario"], "energy_optimization")

    def test_action_proposal_and_execution(self):
        """Action proposals can be created and executed."""
        proposal = self.sim.create_action_proposal(
            action_type="set_temperature",
            target_entity="hvac_ground",
            action_params={"temperature": 24.0},
        )
        proposal.safety_approved = True
        proposal.safety_auth_token = issue_safety_token(proposal.action_id, proposal.action_type, proposal.target_entity)  # Simulate Safety Gateway approval
        self.assertEqual(proposal.action_type, "set_temperature")
        self.assertEqual(proposal.target_entity, "hvac_ground")

        result = self.sim.execute_action(proposal)
        self.assertEqual(result.outcome, ExecutionOutcome.COMPLETED)

        # Verify temperature was set
        self.assertEqual(self.sim.hvac_ground.target_temp, 24.0)

    def test_action_proposal_lighting(self):
        """Lighting action proposals execute correctly."""
        proposal = self.sim.create_action_proposal(
            action_type="set_brightness",
            target_entity="light_living",
            action_params={"brightness": 50},
        )
        proposal.safety_approved = True
        proposal.safety_auth_token = issue_safety_token(proposal.action_id, proposal.action_type, proposal.target_entity)  # Simulate Safety Gateway approval
        result = self.sim.execute_action(proposal)
        self.assertEqual(result.outcome, ExecutionOutcome.COMPLETED)
        self.assertEqual(self.sim.light_living.brightness, 50)

    def test_action_proposal_lock(self):
        """Lock/unlock action proposals execute correctly."""
        # Unlock
        proposal = self.sim.create_action_proposal(
            action_type="unlock",
            target_entity="lock_front",
            action_params={},
        )
        proposal.safety_approved = True
        proposal.safety_auth_token = issue_safety_token(proposal.action_id, proposal.action_type, proposal.target_entity)  # Simulate Safety Gateway approval
        result = self.sim.execute_action(proposal)
        self.assertEqual(result.outcome, ExecutionOutcome.COMPLETED)
        self.assertFalse(self.sim.front_lock.is_locked)

        # Lock
        proposal = self.sim.create_action_proposal(
            action_type="lock",
            target_entity="lock_front",
            action_params={},
        )
        proposal.safety_approved = True
        proposal.safety_auth_token = issue_safety_token(proposal.action_id, proposal.action_type, proposal.target_entity)  # Simulate Safety Gateway approval
        result = self.sim.execute_action(proposal)
        self.assertEqual(result.outcome, ExecutionOutcome.COMPLETED)
        self.assertTrue(self.sim.front_lock.is_locked)

    def test_safety_events_logged(self):
        """Safety events are logged during emergencies."""
        self.sim.trigger_fire_emergency("room_kitchen")
        events = self.sim.safety_events
        self.assertGreater(len(events), 0)
        self.assertEqual(events[-1]["event_type"], "fire_emergency")


if __name__ == "__main__":
    unittest.main()
