"""ORION Phase 4 — Drone Domain Tests.

Tests the drone domain simulation including takeoff, waypoint navigation,
geofencing, collision avoidance, battery management, and emergency landing.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.contracts.contracts import ActionProposal, ExecutionOutcome, RiskTier, generate_contract_id
from src.domains.drone.drone_entities import (
    AltitudeSensor,
    BatteryManager,
    CollisionAvoidance3D,
    DroneEntity,
    FlightController,
    GeofenceController,
    IMUSensor,
)
from src.domains.drone.drone_simulator import DroneSimulation
from src.contracts.contracts import issue_safety_token


class TestDroneDomain(unittest.TestCase):
    """Test drone domain entities and simulation."""

    def setUp(self):
        self.sim = DroneSimulation()
        self.sim._safety_gate_active = True  # Arm safety gate for direct method tests

    def test_drone_entity_creation(self):
        """Drone entity is created with correct initial state."""
        drone = self.sim.drone
        self.assertEqual(drone.entity_id, "drone_1")
        self.assertEqual(drone.state, "IDLE")
        self.assertEqual(drone.flight_mode, "idle")
        self.assertEqual(drone.battery_pct, 100.0)
        self.assertEqual(drone.position, [0.0, 0.0, 0.0])

    def test_takeoff(self):
        """Drone can take off and transition to flying state."""
        result = self.sim.takeoff(10.0)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(self.sim.drone.state, "FLYING")
        self.assertEqual(self.sim.flight_ctrl.current_mode, "hover")

    def test_waypoint_navigation(self):
        """Drone can navigate to waypoints."""
        self.sim.takeoff(10.0)
        self.sim.set_waypoints([[20.0, 0.0, 10.0]])
        self.assertEqual(self.sim.drone.flight_mode, "waypoint")

        for _ in range(200):
            self.sim.step(0.1)
            if self.sim.flight_ctrl.has_reached_target(self.sim.drone.position):
                break

        dist = math.sqrt(sum((p - t) ** 2 for p, t in zip(self.sim.drone.position, [20.0, 0.0, 10.0])))
        self.assertLess(dist, 1.0, "Should reach waypoint")

    def test_geofence_enforcement(self):
        """Geofence prevents drone from leaving boundary."""
        self.sim.takeoff(10.0)
        self.sim.set_waypoints([[200.0, 0.0, 10.0]])  # Beyond geofence

        for _ in range(50):
            self.sim.step(0.1)

        # Drone should not have reached the out-of-bounds waypoint
        dist = abs(self.sim.drone.position[0])
        self.assertLess(dist, 105.0, "Geofence should prevent departure")

    def test_collision_avoidance(self):
        """Collision avoidance prevents drone from hitting obstacles."""
        self.sim.takeoff(10.0)
        self.sim.collision_avoidance.add_obstacle([10.0, 0.0, 10.0], radius=2.0)
        self.sim.set_waypoints([[20.0, 0.0, 10.0]])

        for _ in range(300):
            self.sim.step(0.1)
            if self.sim.flight_ctrl.has_reached_target(self.sim.drone.position):
                break

        # Drone should have navigated around obstacle and reached target
        dist = math.sqrt(sum((p - t) ** 2 for p, t in zip(self.sim.drone.position, [20.0, 0.0, 10.0])))
        self.assertLess(dist, 10.0, "Should reach target while avoiding obstacle")

    def test_battery_management_low_threshold(self):
        """Low battery triggers return-to-base."""
        self.sim.battery.capacity_pct = 15.0
        self.sim.drone.battery_pct = 15.0
        self.sim.takeoff(10.0)
        self.sim.set_waypoints([[50.0, 0.0, 10.0]])

        for _ in range(100):
            self.sim.step(0.1)
            if self.sim.drone.flight_mode in ("return_to_base", "idle"):
                break

        # Drone should have triggered return-to-base (or already returned)
        self.assertIn(self.sim.drone.flight_mode, ("return_to_base", "idle"))

    def test_battery_management_critical_threshold(self):
        """Critical battery triggers emergency landing."""
        self.sim.battery.capacity_pct = 5.0
        self.sim.drone.battery_pct = 5.0
        self.sim.takeoff(10.0)
        self.sim.step(0.1)

        self.assertEqual(self.sim.drone.state, "EMERGENCY_LANDING")

    def test_return_to_base(self):
        """Drone can return to base and land."""
        self.sim.takeoff(10.0)
        self.sim.set_waypoints([[30.0, 30.0, 15.0]])

        for _ in range(100):
            self.sim.step(0.1)
            if self.sim.flight_ctrl.has_reached_target(self.sim.drone.position):
                break

        self.sim.return_to_base()
        self.assertEqual(self.sim.drone.state, "RETURNING")

        for _ in range(500):
            self.sim.step(0.1)
            if self.sim.drone.state in ("LANDING", "IDLE"):
                break

        self.assertIn(self.sim.drone.state, ("LANDING", "IDLE"))

    def test_wind_disturbance(self):
        """Drone handles wind disturbance."""
        self.sim.takeoff(10.0)
        self.sim.set_wind(2.0, -1.0, 0.0)
        self.sim.set_waypoints([[20.0, 20.0, 15.0]])

        for _ in range(300):
            self.sim.step(0.1)
            if self.sim.flight_ctrl.has_reached_target(self.sim.drone.position):
                break

        # Should still reach target despite wind
        dist = math.sqrt(sum((p - t) ** 2 for p, t in zip(self.sim.drone.position, [20.0, 20.0, 15.0])))
        self.assertLess(dist, 5.0, "Should reach target despite wind")

    def test_full_autonomous_cycle(self):
        """Full autonomous cycle: takeoff -> waypoint -> return -> land."""
        results = self.sim.run_full_cycle()
        self.assertTrue(results["takeoff"]["status"] == "OK")
        self.assertTrue(results["waypoint_reached"])
        self.assertTrue(results["returned_home"])

    def test_scenario_runner(self):
        """Scenario runner handles all predefined scenarios."""
        # Normal flight
        result = self.sim.run_scenario("normal_flight")
        self.assertIn("landed", result)

        # Low battery
        result = self.sim.run_scenario("low_battery")
        self.assertEqual(result["status"], "RETURN_TO_BASE")

        # Critical battery
        result = self.sim.run_scenario("critical_battery")
        self.assertEqual(result["status"], "EMERGENCY_LANDING")

    def test_safety_events_logged(self):
        """Safety events are logged during flight."""
        self.sim.takeoff(10.0)
        self.sim.set_waypoints([[20.0, 0.0, 10.0]])
        for _ in range(50):
            self.sim.step(0.1)

        events = self.sim.safety_events
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0]["event_type"], "takeoff")

    def test_action_proposal_and_execution(self):
        """Action proposals can be created and executed."""
        proposal = self.sim.create_action_proposal(
            action_type="takeoff",
            action_params={"altitude": 15.0},
        )
        self.assertEqual(proposal.action_type, "takeoff")
        self.assertEqual(proposal.target_entity, "drone_1")

        proposal.safety_approved = True
        proposal.safety_auth_token = issue_safety_token(proposal.action_id, proposal.action_type, proposal.target_entity)  # Simulate Safety Gateway approval
        result = self.sim.execute_action(proposal)
        self.assertEqual(result.outcome, ExecutionOutcome.COMPLETED)
        self.assertEqual(self.sim.drone.state, "FLYING")

    def test_imu_sensor(self):
        """IMU sensor detects tilt."""
        imu = IMUSensor("imu_test")
        imu.update(orientation=[20.0, 5.0, 0.0], accel=[0, 0, 0], gyro=[0, 0, 0])
        self.assertTrue(imu.detect_tilt(threshold=15.0))

        imu.update(orientation=[5.0, 3.0, 0.0], accel=[0, 0, 0], gyro=[0, 0, 0])
        self.assertFalse(imu.detect_tilt(threshold=15.0))

    def test_altitude_sensor_limit(self):
        """Altitude sensor detects when above max altitude."""
        alt = AltitudeSensor("alt_test", max_altitude=120.0)
        alt.update(50.0)
        self.assertFalse(alt.is_above_limit())

        alt.update(150.0)
        self.assertTrue(alt.is_above_limit())


if __name__ == "__main__":
    unittest.main()
