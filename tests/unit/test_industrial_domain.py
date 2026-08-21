"""Unit tests for ORION Industrial Domain Module (Phase 2)."""

import unittest
from typing import Any, Dict

from src.contracts.contracts import ActionProposal, ExecutionOutcome, issue_safety_token
from src.domains.industrial.industrial_entities import (
    ConveyorBelt,
    EmergencyStopButton,
    IndustrialEntity,
    PressureSensor,
    RobotArm,
    SafetyLightCurtain,
    TankLevel,
    TemperatureSensor,
    ValveController,
)
from src.domains.industrial.industrial_simulator import IndustrialSimulation


class TestIndustrialDomain(unittest.TestCase):
    """Test suite covering Phase 2 Industrial Domain entities and simulator."""

    def test_entity_creation_and_initialization(self):
        """1. Entity creation and initialization with state_revision tracking."""
        conveyor = ConveyorBelt("conv_0", max_speed=3.0, length=12.0)
        robot = RobotArm("arm_0", base_position=[1.0, 1.0, 0.0], reach_limit=2.0)
        p_sensor = PressureSensor("p_0", threshold=150.0)
        t_sensor = TemperatureSensor("t_0", max_threshold=90.0)
        curtain = SafetyLightCurtain("lc_0")
        estop = EmergencyStopButton("es_0")
        valve = ValveController("v_0")
        tank = TankLevel("tk_0", capacity=200.0)

        entities = [conveyor, robot, p_sensor, t_sensor, curtain, estop, valve, tank]
        for ent in entities:
            self.assertIsInstance(ent, IndustrialEntity)
            self.assertGreaterEqual(ent.state_revision, 1)
            d = ent.to_dict()
            self.assertIn("entity_id", d)
            self.assertIn("state_revision", d)
            self.assertIn("status", d)

    def test_conveyor_start_stop(self):
        """2. Conveyor belt start and stop state changes."""
        sim = IndustrialSimulation()
        conveyor = sim.conveyor

        initial_rev = conveyor.state_revision
        self.assertFalse(conveyor.is_running)

        # Start conveyor
        conveyor.start(speed=1.5)
        self.assertTrue(conveyor.is_running)
        self.assertEqual(conveyor.speed, 1.5)
        self.assertEqual(conveyor.status, "RUNNING")
        self.assertGreater(conveyor.state_revision, initial_rev)

        # Stop conveyor
        rev_after_start = conveyor.state_revision
        conveyor.stop()
        self.assertFalse(conveyor.is_running)
        self.assertEqual(conveyor.speed, 0.0)
        self.assertEqual(conveyor.status, "STOPPED")
        self.assertGreater(conveyor.state_revision, rev_after_start)

    def test_robot_arm_pick_place_and_reach_limits(self):
        """3. Robot arm pick and place within limits and reach limit rejection."""
        sim = IndustrialSimulation()
        arm = sim.robot_arm  # base at [2.0, 2.0, 0.0], reach_limit=2.5

        # Valid movement within reach limit (dist to base [2,2,0] is ~0.7)
        res = arm.move_end_effector(2.5, 2.5, 0.5)
        self.assertTrue(res)

        # Pick item within reach limit
        item = {"id": "box_100", "weight_kg": 2.0}
        pick_success = arm.pick(item, [2.5, 2.5, 0.5])
        self.assertTrue(pick_success)
        self.assertFalse(arm.gripper_open)

        # Place item at valid target pos
        placed_item = arm.place([2.2, 2.2, 0.2])
        self.assertEqual(placed_item["id"], "box_100")
        self.assertTrue(arm.gripper_open)

        # Attempt movement beyond reach limit (dist from [2,2,0] to [10,10,5] is > 11m)
        with self.assertRaises(ValueError):
            arm.move_end_effector(10.0, 10.0, 5.0)

    def test_pressure_sensor_threshold_detection(self):
        """4. Pressure sensor threshold exceeded detection."""
        sim = IndustrialSimulation()
        p_sensor = sim.pressure_sensor  # threshold = 100.0

        p_sensor.set_pressure(80.0)
        self.assertFalse(p_sensor.is_threshold_exceeded())
        self.assertEqual(p_sensor.status, "NOMINAL")

        # Exceed threshold
        p_sensor.set_pressure(120.0)
        self.assertTrue(p_sensor.is_threshold_exceeded())
        self.assertEqual(p_sensor.status, "EXCEEDED")

    def test_temperature_sensor_degraded_transition(self):
        """5. Temperature sensor max threshold -> DEGRADED status transition."""
        sim = IndustrialSimulation()
        t_sensor = sim.temp_sensor  # max_threshold = 80.0

        t_sensor.set_temperature(75.0)
        self.assertFalse(t_sensor.is_out_of_bounds())
        self.assertEqual(t_sensor.status, "NOMINAL")

        # Temperature exceeds max threshold -> DEGRADED
        initial_rev = t_sensor.state_revision
        t_sensor.set_temperature(85.0)
        self.assertTrue(t_sensor.is_out_of_bounds())
        self.assertEqual(t_sensor.status, "DEGRADED")
        self.assertGreater(t_sensor.state_revision, initial_rev)

        # Verify simulation step picks up DEGRADED state
        step_result = sim.step(dt=0.1)
        self.assertEqual(step_result["system_status"], "DEGRADED")

    def test_safety_light_curtain_breach_estop(self):
        """6. Safety light curtain breach -> System E-Stop."""
        sim = IndustrialSimulation()
        self.assertEqual(sim.system_status, "NOMINAL")

        # Breach light curtain
        sim.light_curtain.breach()
        self.assertTrue(sim.light_curtain.is_breached)

        # Step simulation to process interlock
        step_res = sim.step(dt=0.1)
        self.assertEqual(sim.system_status, "ESTOP")
        self.assertIn("SYSTEM_ESTOP_TRIGGERED", step_res["events"])

    def test_valve_failsafe_closes_on_estop(self):
        """7. Valve closes on E-Stop via deterministic failsafe."""
        sim = IndustrialSimulation()
        sim.valve.open_valve(flow_rate=8.0)
        self.assertTrue(sim.valve.is_open)

        # Trigger E-Stop button
        sim.estop_button.press()

        # Step simulation to apply deterministic interlock
        sim.step(dt=0.1)

        self.assertEqual(sim.system_status, "ESTOP")
        self.assertFalse(sim.valve.is_open)
        self.assertEqual(sim.valve.status, "CLOSED")
        self.assertEqual(sim.valve.flow_rate, 0.0)

    def test_tank_overflow_protection(self):
        """8. Tank overflow protection prevents filling past max threshold."""
        sim = IndustrialSimulation()
        tank = sim.tank  # capacity=100.0, max_threshold=90.0, initial current_level=50.0

        # Attempt to add 50L (which would bring level to 100L > max_threshold 90L)
        added = tank.add_fluid(50.0)
        self.assertEqual(added, 40.0)  # Only 40L added to cap at 90.0L
        self.assertEqual(tank.current_level, 90.0)
        self.assertTrue(tank.overflow_protection_active)
        self.assertEqual(tank.status, "OVERFLOW_PREVENTED")

    def test_robot_arm_conveyor_collision_prevention(self):
        """9. Action proposal arbitration rejects robot arm movement into conveyor zone."""
        sim = IndustrialSimulation()

        # Proposal attempting to move robot arm into conveyor zone [5.0, 0.0, 0.5]
        proposal = ActionProposal(
            action_type="move_robot_arm",
            target_entity="robot_arm_1",
            action_parameters={"target_pos": [5.0, 0.0, 0.5]},
        )
        proposal.safety_approved = True
        proposal.safety_auth_token = issue_safety_token(proposal.action_id, proposal.action_type, proposal.target_entity)

        exec_res = sim.propose_action(proposal)
        self.assertEqual(exec_res.outcome, ExecutionOutcome.FAILED.value)
        self.assertIn("Collision with conveyor zone", exec_res.deviation_reason)


if __name__ == "__main__":
    unittest.main()
