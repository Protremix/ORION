"""Integration test for ORION Phase 1 Cognitive Plane, State Plane, and Simulation Environment."""

import unittest
from typing import List

from simulation.actuators import SimulatedMobileBase
from simulation.grid_world import GridWorld
from simulation.sensors import (
    SimulatedCamera,
    SimulatedGPS,
    SimulatedIMU,
    SimulatedLidar,
)
from src.cognitive.cognitive_plane import CognitivePlane
from src.contracts import (
    ActionExecutionResult,
    ActionProposal,
    BeliefState,
    Goal,
    Observation,
)
from src.state.state_plane import StatePlane


class TestPhase1Orion(unittest.TestCase):

    def setUp(self):
        # 1. Initialize 2D GridWorld (10m x 10m)
        self.world = GridWorld(width=10.0, height=10.0, resolution=0.1)
        self.robot = self.world.add_entity(entity_id="mobile_base_0", x=1.0, y=1.0, heading=0.0)

        # Add obstacles and target
        self.world.add_obstacle("obs_1", "circle", {"x": 3.0, "y": 3.0, "radius": 0.5})
        self.world.add_target("target_1", x=8.0, y=8.0)

        # 2. Initialize Sensors
        self.gps = SimulatedGPS(sensor_id="gps_0")
        self.imu = SimulatedIMU(sensor_id="imu_0")
        self.lidar = SimulatedLidar(sensor_id="lidar_0")
        self.camera = SimulatedCamera(sensor_id="cam_0")

        # 3. Initialize Actuator
        self.actuator = SimulatedMobileBase(actuator_id="mobile_base_0")

        # 4. Initialize State Plane & Cognitive Plane
        self.state_plane = StatePlane(initial_position=[1.0, 1.0, 0.0])
        self.cognitive_plane = CognitivePlane(enable_llm=False)  # Test deterministic pipeline

    def test_full_cognitive_simulation_cycle(self):
        # Step A: Sample sensors
        obs_gps = self.gps.read(self.world, "mobile_base_0")
        obs_imu = self.imu.read(self.world, "mobile_base_0")
        obs_lidar = self.lidar.read(self.world, "mobile_base_0")
        obs_cam = self.camera.read(self.world, "mobile_base_0")

        self.assertIsInstance(obs_gps, Observation)
        self.assertIsInstance(obs_imu, Observation)
        self.assertIsInstance(obs_lidar, Observation)
        self.assertIsInstance(obs_cam, Observation)

        # Step B: Process observations in State Plane
        belief_state = self.state_plane.process_observations([obs_gps, obs_imu, obs_lidar, obs_cam])
        self.assertIsInstance(belief_state, BeliefState)
        self.assertEqual(belief_state.state_revision, 1)

        # Step C: Cognitive Plane processes BeliefState and High-Level Instruction
        instruction = "Navigate to position (5.0, 5.0) safely."
        output = self.cognitive_plane.process_belief_state(belief_state, instruction)

        goals = output["goals"]
        proposals = output["action_proposals"]

        self.assertTrue(len(goals) > 0)
        self.assertTrue(len(proposals) > 0)

        goal = goals[0]
        proposal = proposals[0]

        self.assertIsInstance(goal, Goal)
        self.assertIsInstance(proposal, ActionProposal)

        # Verify contract compliance
        self.assertIn("risk_tier", proposal.risk_assessment)
        self.assertIn(proposal.risk_tier, (1, 2, 3))
        self.assertIsNotNone(proposal.expected_outcome)
        self.assertIsNotNone(proposal.preconditions)

        # Step D: Execute ActionProposal via Simulated Actuator
        exec_result = self.actuator.execute_proposal(proposal, self.world)
        self.assertIsInstance(exec_result, ActionExecutionResult)
        self.assertIn(exec_result.result, ("completed", "partial", "failed"))

        # Step E: State Plane updates state from Execution Result
        updated_belief = self.state_plane.update_from_execution_result(exec_result)
        self.assertEqual(updated_belief.state_revision, 2)
        self.assertNotEqual(updated_belief.position, [1.0, 1.0, 0.0])


if __name__ == "__main__":
    unittest.main()
