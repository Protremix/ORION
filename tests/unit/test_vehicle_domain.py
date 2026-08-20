# Copyright 2026 ORION Physical Intelligence OS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for ORION Vehicle Domain Module (Phase 2 Full Autonomous Driving Simulation)."""

import unittest
from typing import Any, Dict

from src.contracts.contracts import ActionProposal, ExecutionOutcome
from src.domains.vehicle.vehicle_entities import (
    AdaptiveCruiseControl,
    AEBController,
    CollisionAvoidance,
    LaneSensor,
    ObstacleSensor,
    SpeedController,
    SteeringController,
    TrafficLightSensor,
    VehicleEntity,
)
from src.domains.vehicle.vehicle_simulator import VehicleSimulation


class TestVehicleDomain(unittest.TestCase):
    """Test suite covering SC-2 Vehicle Domain entities, safety controllers, and simulator."""

    def test_vehicle_entity_state_transitions_and_gears(self):
        """1. Vehicle entity state transitions and gear validation."""
        veh = VehicleEntity("ego", position=[0.0, 0.0, 0.0], gear="DRIVE", state="IDLE")
        initial_rev = veh.state_revision

        # Accelerate in DRIVE
        veh.update_kinematics(acceleration=2.0, steering_angle=0.0, dt=1.0)
        self.assertEqual(veh.speed, 2.0)
        self.assertEqual(veh.state, "MOVING")
        self.assertGreater(veh.state_revision, initial_rev)

        # Brake to stop
        veh.update_kinematics(acceleration=-4.0, steering_angle=0.0, dt=1.0)
        self.assertEqual(veh.speed, 0.0)
        self.assertEqual(veh.state, "STOPPED")

        # Invalid gear engaging while moving rejection
        veh.speed = 5.0
        with self.assertRaises(ValueError):
            veh.set_gear("PARK")

        # Stopped -> engage PARK
        veh.speed = 0.0
        veh.set_gear("PARK")
        self.assertEqual(veh.gear, "PARK")

        # Invalid gear string
        with self.assertRaises(ValueError):
            veh.set_gear("FLY")

    def test_lane_sensor_detection_and_departure_warning(self):
        """2. Lane sensor detection and departure warning trigger."""
        sensor = LaneSensor("lane_0", lane_width=3.5, num_lanes=3, departure_warning_threshold=0.5)

        # Vehicle in lane 0 center (y = 1.75m)
        res = sensor.detect_lanes([10.0, 1.75, 0.0])
        self.assertEqual(sensor.current_lane, 0)
        self.assertAlmostEqual(sensor.lane_offset, 0.0, places=2)
        self.assertFalse(sensor.departure_warning)

        # Vehicle drifting off center (y = 2.4m -> offset 0.65m > 0.5m)
        res = sensor.detect_lanes([10.0, 2.4, 0.0])
        self.assertEqual(sensor.current_lane, 0)
        self.assertTrue(sensor.departure_warning)
        self.assertEqual(sensor.status, "DEPARTURE_WARNING")

    def test_obstacle_sensor_detection(self):
        """3. Obstacle sensor front, side, and rear zone categorization."""
        sensor = ObstacleSensor("obs_0", front_range=50.0, side_range=15.0, rear_range=20.0)
        vehicle_pos = [10.0, 1.75, 0.0]
        heading = 0.0

        obstacles = [
            {"id": "front_car", "position": [30.0, 1.75, 0.0], "speed": 10.0},
            {"id": "rear_car", "position": [0.0, 1.75, 0.0], "speed": 15.0},
            {"id": "side_left_car", "position": [10.0, 5.0, 0.0], "speed": 12.0},
            {"id": "side_right_car", "position": [10.0, -2.0, 0.0], "speed": 12.0},
        ]

        scanned = sensor.scan(vehicle_pos, heading, obstacles)
        self.assertEqual(len(scanned["front"]), 1)
        self.assertEqual(scanned["front"][0]["id"], "front_car")
        self.assertAlmostEqual(sensor.get_min_distance("front"), 20.0, places=2)

        self.assertEqual(len(scanned["rear"]), 1)
        self.assertEqual(scanned["rear"][0]["id"], "rear_car")

        self.assertEqual(len(scanned["side_left"]), 1)
        self.assertEqual(scanned["side_left"][0]["id"], "side_left_car")

        self.assertEqual(len(scanned["side_right"]), 1)
        self.assertEqual(scanned["side_right"][0]["id"], "side_right_car")

    def test_speed_controller(self):
        """4. Speed controller acceleration, braking, and cruise control."""
        ctrl = SpeedController("speed_ctrl", target_speed=20.0, max_acceleration=3.0, max_deceleration=8.0)

        # Accelerate from 10 m/s towards 20 m/s
        accel = ctrl.compute_control(current_speed=10.0, dt=0.1)
        self.assertGreater(accel, 0.0)
        self.assertLessEqual(accel, 3.0)

        # Cruise control enable
        ctrl.enable_cruise_control(target_speed=25.0)
        self.assertTrue(ctrl.cruise_control_active)
        self.assertEqual(ctrl.target_speed, 25.0)

        # Emergency brake command
        em_accel = ctrl.emergency_brake()
        self.assertEqual(em_accel, -8.0)
        self.assertFalse(ctrl.cruise_control_active)

    def test_steering_controller(self):
        """5. Steering controller lane keeping, lane change, and turn signal."""
        steering = SteeringController("steer_ctrl", max_steering_angle=0.5)

        # Lane keeping: on target line (y=1.75, heading=0.0) -> steering ~ 0
        angle = steering.compute_steering(current_y=1.75, target_y=1.75, current_heading=0.0)
        self.assertAlmostEqual(angle, 0.0, places=2)

        # Initiate lane change to left
        steering.initiate_lane_change("LEFT", target_lane=1)
        self.assertTrue(steering.is_changing_lanes)
        self.assertEqual(steering.turn_signal, "LEFT")

        # Compute steering for lane change
        angle_lc = steering.compute_steering(current_y=1.75, target_y=5.25, current_heading=0.0)
        self.assertGreater(angle_lc, 0.0)

        # Complete lane change
        steering.compute_steering(current_y=5.24, target_y=5.25, current_heading=0.0)
        self.assertFalse(steering.is_changing_lanes)
        self.assertEqual(steering.turn_signal, "OFF")

    def test_aeb_triggers_on_imminent_collision(self):
        """6. AEB controller triggers on critical TTC or distance threshold."""
        aeb = AEBController("aeb", ttc_threshold=2.0, critical_distance=3.0, max_aeb_deceleration=-8.0)

        # Safe distance (front obstacle at 40m, speed 15m/s) -> no trigger
        triggered, decel = aeb.evaluate(current_speed=15.0, obstacle_distance=40.0)
        self.assertFalse(triggered)
        self.assertEqual(decel, 0.0)

        # Imminent collision (front obstacle at 10m, speed 20m/s -> TTC = 0.5s < 2.0s)
        triggered, decel = aeb.evaluate(current_speed=20.0, obstacle_distance=10.0)
        self.assertTrue(triggered)
        self.assertEqual(decel, -8.0)
        self.assertTrue(aeb.is_aeb_active)

        # Critical distance trigger (< 3.0m even at low speed)
        triggered, decel = aeb.evaluate(current_speed=1.0, obstacle_distance=2.0)
        self.assertTrue(triggered)

    def test_collision_avoidance_cbf(self):
        """7. Collision avoidance CBF filtering clamps unsafe acceleration."""
        cbf = CollisionAvoidance("cbf_ctrl", safe_distance_front=5.0)

        # Safe state (front distance 30m) -> nominal control unmodified
        accel, steering, modified = cbf.filter_control(
            vehicle_speed=15.0,
            nominal_accel=2.0,
            nominal_steering=0.0,
            obstacle_distances={"front": 30.0, "side_left": 10.0, "side_right": 10.0, "rear": 10.0},
        )
        self.assertFalse(modified)
        self.assertEqual(accel, 2.0)

        # Unsafe front distance (front distance 4.0m < 5.0m safe_distance) -> modified to brake
        accel_mod, steering_mod, modified = cbf.filter_control(
            vehicle_speed=10.0,
            nominal_accel=2.0,
            nominal_steering=0.0,
            obstacle_distances={"front": 4.0, "side_left": 10.0, "side_right": 10.0, "rear": 10.0},
        )
        self.assertTrue(modified)
        self.assertLess(accel_mod, 0.0)

    def test_adaptive_cruise_control(self):
        """8. Adaptive cruise control maintains safe following distance behind lead vehicle."""
        acc = AdaptiveCruiseControl("acc", target_speed=25.0, time_gap=1.8, min_distance=4.0)

        # Free flow: no lead car -> accelerate to target speed
        accel_free = acc.compute_acceleration(current_speed=15.0, lead_distance=None, lead_speed=None, dt=0.1)
        self.assertGreater(accel_free, 0.0)

        # Following lead car too close
        accel_follow = acc.compute_acceleration(current_speed=20.0, lead_distance=10.0, lead_speed=15.0, dt=0.1)
        self.assertLess(accel_follow, 0.0)

    def test_traffic_light_compliance(self):
        """9. Traffic light sensor compliance stops vehicle on RED light."""
        sim = VehicleSimulation()
        sim.spawn_vehicle("ego_test", x=0.0, lane=0, speed=10.0)
        sim.add_traffic_light("tl_1", x=20.0, lane=0, state="RED")

        tl_data = sim.traffic_light_sensor.detect_light(
            sim.traffic_lights, sim.ego_vehicle.position, sim.ego_vehicle.heading
        )
        self.assertEqual(tl_data["light_state"], "RED")
        self.assertTrue(sim.traffic_light_sensor.should_stop())

        step_res = sim.step(dt=0.1)
        self.assertIn("TRAFFIC_LIGHT_STOP", step_res["events"])

    def test_full_autonomous_cycle(self):
        """10. Full autonomous cycle (sensor -> state -> plan -> act -> verify)."""
        sim = VehicleSimulation(road_length=200.0, num_lanes=3)
        sim.ego_vehicle.speed = 10.0
        sim.ego_vehicle.set_gear("DRIVE")
        sim.ego_vehicle.set_state("MOVING")

        sim.spawn_vehicle("slow_car", x=25.0, lane=0, speed=5.0)

        step_res = sim.step(dt=0.1)
        self.assertIn("ego_vehicle", step_res["vehicles"])
        self.assertIn("system_status", step_res)
        self.assertGreater(step_res["state_revision"], 1)

        ego_dict = step_res["ego_vehicle"]
        self.assertIn("speed", ego_dict)
        self.assertIn("position", ego_dict)

    def test_scenario_runner_and_action_proposals(self):
        """11. Scenario runner (highway, urban, parking) and action proposals arbitration."""
        sim = VehicleSimulation()

        # Highway scenario
        hw_res = sim.run_scenario("highway", duration_sec=1.0)
        self.assertEqual(hw_res["scenario"], "highway")
        self.assertGreater(hw_res["total_steps"], 0)

        # Urban scenario
        urban_res = sim.run_scenario("urban", duration_sec=1.0)
        self.assertEqual(urban_res["scenario"], "urban")

        # Parking scenario
        park_res = sim.run_scenario("parking", duration_sec=1.0)
        self.assertEqual(park_res["scenario"], "parking")

        # Action proposal arbitration (use fresh sim to avoid EMERGENCY from parking AEB)
        sim2 = VehicleSimulation()
        proposal = ActionProposal(
            action_type="set_speed",
            target_entity="ego_vehicle",
            action_parameters={"target_speed": 18.0},
        )
        exec_res = sim2.propose_action(proposal)
        self.assertEqual(exec_res.outcome, ExecutionOutcome.COMPLETED.value)
        self.assertEqual(sim2.speed_controller.target_speed, 18.0)


if __name__ == "__main__":
    unittest.main()
