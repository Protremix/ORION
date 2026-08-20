"""Industrial Simulation Environment for ORION Phase 2.

Simulates a factory floor containing:
- 1 ConveyorBelt
- 1 RobotArm
- 2 Sensors (PressureSensor + TemperatureSensor)
- 1 SafetyLightCurtain
- 1 EmergencyStopButton
- 1 ValveController
- 1 TankLevel

Features state_revision tracking, deterministic safety monitoring, collision detection,
and action proposal -> arbitration -> execution pipeline integration.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from src.contracts.contracts import (
    ActionExecutionResult,
    ActionProposal,
    ExecutionOutcome,
    ExecutionStage,
    RiskTier,
    generate_contract_id,
)
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


class IndustrialSimulation:
    """Factory floor simulation managing entities and safety interlocks."""

    def __init__(self) -> None:
        # Create factory floor entities
        self.conveyor = ConveyorBelt("conveyor_1", max_speed=2.0, length=10.0, position=[0.0, 0.0, 0.0])
        self.robot_arm = RobotArm("robot_arm_1", base_position=[2.0, 2.0, 0.0], reach_limit=2.5, min_reach=0.2)
        self.pressure_sensor = PressureSensor("pressure_sensor_1", threshold=100.0, min_threshold=0.0)
        self.temp_sensor = TemperatureSensor("temp_sensor_1", max_threshold=80.0, min_threshold=0.0)
        self.light_curtain = SafetyLightCurtain("light_curtain_1", zone={"min_x": 0.0, "max_x": 10.0, "min_y": -0.5, "max_y": 0.5})
        self.estop_button = EmergencyStopButton("estop_1")
        self.valve = ValveController("valve_1", failsafe_state="CLOSED", max_flow_rate=10.0)
        self.tank = TankLevel("tank_1", capacity=100.0, min_threshold=10.0, max_threshold=90.0)

        # Entity lookup registry
        self.entities: Dict[str, IndustrialEntity] = {
            self.conveyor.entity_id: self.conveyor,
            self.robot_arm.entity_id: self.robot_arm,
            self.pressure_sensor.entity_id: self.pressure_sensor,
            self.temp_sensor.entity_id: self.temp_sensor,
            self.light_curtain.entity_id: self.light_curtain,
            self.estop_button.entity_id: self.estop_button,
            self.valve.entity_id: self.valve,
            self.tank.entity_id: self.tank,
        }

        # Conveyor exclusion zone for collision detection (robot arm cannot reach into conveyor zone)
        self.conveyor_zone: Dict[str, float] = {
            "min_x": 0.0, "max_x": 10.0,
            "min_y": -0.5, "max_y": 0.5,
            "min_z": 0.0, "max_z": 1.0,
        }

        self.system_status: str = "NOMINAL"  # NOMINAL, DEGRADED, ESTOP, FAULT
        self.time_elapsed: float = 0.0
        self.state_revision: int = 1

    def increment_state_revision(self) -> int:
        """Increment overall simulation state revision."""
        self.state_revision += 1
        return self.state_revision

    def check_collision(self, target_pos: List[float]) -> Tuple[bool, str]:
        """Check if target position collides with the conveyor zone.

        Robot arm end effector is restricted from reaching directly into the
        active conveyor zone without explicit synchronization.
        """
        x = target_pos[0]
        y = target_pos[1]
        z = target_pos[2] if len(target_pos) > 2 else 0.0

        in_x = self.conveyor_zone["min_x"] <= x <= self.conveyor_zone["max_x"]
        in_y = self.conveyor_zone["min_y"] <= y <= self.conveyor_zone["max_y"]
        in_z = self.conveyor_zone["min_z"] <= z <= self.conveyor_zone["max_z"]

        if in_x and in_y and in_z:
            return True, f"Position {target_pos} collides with conveyor zone"
        return False, "Clear"

    def step(self, dt: float = 0.1) -> Dict[str, Any]:
        """Advance factory floor simulation by dt seconds and execute safety monitoring.

        Returns:
            Dict summary of simulation step state and active events.
        """
        self.time_elapsed += dt
        events: List[str] = []

        # 1. Deterministic Safety Interlock Monitoring
        # Breach of light curtain or E-Stop button press -> Immediate ESTOP
        if self.light_curtain.is_breached or self.estop_button.is_pressed:
            if self.system_status != "ESTOP":
                self.system_status = "ESTOP"
                events.append("SYSTEM_ESTOP_TRIGGERED")

            # Deterministic safe state enforcement:
            # - Conveyor stops
            # - Valve failsafe closes
            if self.conveyor.is_running:
                self.conveyor.stop()
                events.append("CONVEYOR_ESTOP_HALTED")

            if self.valve.is_open:
                self.valve.trigger_failsafe()
                events.append("VALVE_FAILSAFE_CLOSED")

        # 2. Temperature Threshold Monitoring -> DEGRADED transition
        elif self.temp_sensor.is_out_of_bounds() or self.temp_sensor.current_temperature > self.temp_sensor.max_threshold:
            if self.system_status != "DEGRADED":
                self.system_status = "DEGRADED"
                self.temp_sensor.set_status("DEGRADED")
                events.append("SYSTEM_DEGRADED_HIGH_TEMP")
        elif self.pressure_sensor.is_threshold_exceeded():
            if self.system_status != "DEGRADED":
                self.system_status = "DEGRADED"
                events.append("SYSTEM_DEGRADED_PRESSURE_EXCEEDED")
        elif self.system_status == "DEGRADED":
            # Recover to NOMINAL if all sensors clear
            if not self.temp_sensor.is_out_of_bounds() and not self.pressure_sensor.is_threshold_exceeded():
                self.system_status = "NOMINAL"
                events.append("SYSTEM_RECOVERED_NOMINAL")

        # 3. Dynamic Physical Processes
        # Advance conveyor items
        if self.conveyor.is_running:
            self.conveyor.step(dt)

        # Process fluid flow if valve open and system not in ESTOP
        if self.valve.is_open and self.system_status != "ESTOP":
            flow_added = self.valve.flow_rate * (dt / 60.0)  # L/min to L per step
            actual_added = self.tank.add_fluid(flow_added)

            # Overflow protection trigger automatically closes valve
            if self.tank.overflow_protection_active:
                self.valve.close_valve()
                events.append("TANK_OVERFLOW_PROTECTION_CLOSED_VALVE")

        self.increment_state_revision()

        return {
            "time_elapsed": self.time_elapsed,
            "system_status": self.system_status,
            "state_revision": self.state_revision,
            "events": events,
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
        }

    def propose_action(self, proposal: ActionProposal) -> ActionExecutionResult:
        """Arbitrate and execute an ActionProposal through the ORION pipeline.

        Performs safety arbitration (ESTOP checks, reach limits, collision detection)
        before executing the requested action on the target entity.
        """
        lease_id = generate_contract_id()
        action_type = proposal.action_type
        target_id = proposal.target_entity
        params = proposal.action_parameters or {}

        # 1. Pipeline Arbitration: Emergency Stop Check
        if self.system_status == "ESTOP" and action_type != "reset_estop":
            return ActionExecutionResult(
                lease_id=lease_id,
                outcome=ExecutionOutcome.REJECTED.value,
                execution_stage=ExecutionStage.COMPLETED.value,
                actual_duration=0,
                actual_effects={"system_status": self.system_status},
                deviation={"error": "Action rejected: System is in emergency stop state"},
                deviation_reason="System in ESTOP mode",
            )

        # 2. Pipeline Arbitration: Target Entity Lookup
        entity = self.entities.get(target_id)
        if entity is None and target_id != "system":
            return ActionExecutionResult(
                lease_id=lease_id,
                outcome=ExecutionOutcome.FAILED.value,
                execution_stage=ExecutionStage.COMPLETED.value,
                actual_duration=0,
                actual_effects={},
                deviation={"error": f"Target entity '{target_id}' not found"},
                deviation_reason=f"Entity '{target_id}' absent",
            )

        # 3. Domain Action Execution & Safety Arbitration
        start_time = time.monotonic()

        try:
            if action_type == "start_conveyor":
                speed = float(params.get("speed", 1.0))
                self.conveyor.start(speed)
                effects = self.conveyor.to_dict()

            elif action_type == "stop_conveyor":
                self.conveyor.stop()
                effects = self.conveyor.to_dict()

            elif action_type == "move_robot_arm":
                target_pos = params.get("target_pos", [2.0, 2.0, 0.5])

                # Collision detection check
                collided, reason = self.check_collision(target_pos)
                if collided:
                    return ActionExecutionResult(
                        lease_id=lease_id,
                        outcome=ExecutionOutcome.FAILED.value,
                        execution_stage=ExecutionStage.COMPLETED.value,
                        actual_duration=0,
                        actual_effects=self.robot_arm.to_dict(),
                        deviation={"error": reason},
                        deviation_reason="Collision with conveyor zone detected",
                    )

                self.robot_arm.move_end_effector(target_pos[0], target_pos[1], target_pos[2])
                effects = self.robot_arm.to_dict()

            elif action_type == "pick_item":
                item = params.get("item", {"id": "item_1"})
                pos = params.get("target_pos")

                if pos:
                    collided, reason = self.check_collision(pos)
                    if collided:
                        return ActionExecutionResult(
                            lease_id=lease_id,
                            outcome=ExecutionOutcome.FAILED.value,
                            execution_stage=ExecutionStage.COMPLETED.value,
                            actual_duration=0,
                            actual_effects=self.robot_arm.to_dict(),
                            deviation={"error": reason},
                            deviation_reason="Collision with conveyor zone detected",
                        )

                self.robot_arm.pick(item, pos)
                effects = self.robot_arm.to_dict()

            elif action_type == "place_item":
                target_pos = params.get("target_pos", [2.0, 2.0, 0.5])

                collided, reason = self.check_collision(target_pos)
                if collided:
                    return ActionExecutionResult(
                        lease_id=lease_id,
                        outcome=ExecutionOutcome.FAILED.value,
                        execution_stage=ExecutionStage.COMPLETED.value,
                        actual_duration=0,
                        actual_effects=self.robot_arm.to_dict(),
                        deviation={"error": reason},
                        deviation_reason="Collision with conveyor zone detected",
                    )

                placed = self.robot_arm.place(target_pos)
                effects = {"placed_item": placed, "robot_arm": self.robot_arm.to_dict()}

            elif action_type == "set_pressure":
                pressure_val = float(params.get("pressure", 50.0))
                self.pressure_sensor.set_pressure(pressure_val)
                effects = self.pressure_sensor.to_dict()

            elif action_type == "set_temperature":
                temp_val = float(params.get("temperature", 25.0))
                self.temp_sensor.set_temperature(temp_val)
                effects = self.temp_sensor.to_dict()

            elif action_type == "open_valve":
                flow_rate = float(params.get("flow_rate", 10.0))
                self.valve.open_valve(flow_rate)
                effects = self.valve.to_dict()

            elif action_type == "close_valve":
                self.valve.close_valve()
                effects = self.valve.to_dict()

            elif action_type == "add_fluid":
                amount = float(params.get("amount", 10.0))
                actual_added = self.tank.add_fluid(amount)
                effects = {"actual_added": actual_added, "tank": self.tank.to_dict()}

            elif action_type == "breach_light_curtain":
                self.light_curtain.breach()
                self.step(0.01)  # Force step to apply safety interlocks
                effects = self.light_curtain.to_dict()

            elif action_type == "press_estop":
                self.estop_button.press()
                self.step(0.01)  # Force step to apply safety interlocks
                effects = self.estop_button.to_dict()

            elif action_type == "reset_estop":
                self.estop_button.reset()
                self.light_curtain.reset()
                self.system_status = "NOMINAL"
                effects = {"system_status": self.system_status}

            else:
                return ActionExecutionResult(
                    lease_id=lease_id,
                    outcome=ExecutionOutcome.REJECTED.value,
                    execution_stage=ExecutionStage.COMPLETED.value,
                    actual_duration=0,
                    actual_effects={},
                    deviation={"error": f"Unsupported action type '{action_type}'"},
                    deviation_reason="Unsupported action",
                )

            duration_ms = int((time.monotonic() - start_time) * 1000)
            self.increment_state_revision()

            return ActionExecutionResult(
                lease_id=lease_id,
                outcome=ExecutionOutcome.COMPLETED.value,
                execution_stage=ExecutionStage.VERIFIED.value,
                actual_duration=duration_ms,
                actual_effects=effects,
            )

        except Exception as exc:
            return ActionExecutionResult(
                lease_id=lease_id,
                outcome=ExecutionOutcome.FAILED.value,
                execution_stage=ExecutionStage.COMPLETED.value,
                actual_duration=0,
                actual_effects={},
                deviation={"error": str(exc)},
                deviation_reason=f"Action execution exception: {exc}",
            )
