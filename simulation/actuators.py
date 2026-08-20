"""ORION Simulated Actuators (Phase 1 Cloud Simulation).

Provides simulated actuator models (e.g., Mobile Base) that execute ActionProposals
on a GridWorld instance and produce normative ActionExecutionResult contracts.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, Optional, Tuple

from simulation.grid_world import GridWorld, SimEntity
from src.contracts import (
    ActionExecutionResult,
    ActionProposal,
    Envelope,
    ExecutionOutcome,
    ExecutionStage,
    generate_uuid,
)

logger = logging.getLogger(__name__)


class SimulatedActuator:
    """Base class for simulated actuators in ORION."""

    def __init__(
        self,
        actuator_id: str,
        actuator_type: str,
    ) -> None:
        self.actuator_id = actuator_id
        self.actuator_type = actuator_type

    def execute_proposal(
        self,
        proposal: ActionProposal,
        world: GridWorld,
        lease_id: Optional[str] = None,
    ) -> ActionExecutionResult:
        """Execute an ActionProposal on the simulation world."""
        raise NotImplementedError("Subclasses must implement execute_proposal()")


class SimulatedMobileBase(SimulatedActuator):
    """Simulated mobile robot base supporting 2D kinematics (differential drive / omnidirectional)."""

    def __init__(
        self,
        actuator_id: str = "mobile_base_0",
        max_linear_velocity: float = 2.0,
        max_angular_velocity: float = 1.5,
    ) -> None:
        super().__init__(actuator_id=actuator_id, actuator_type="mobile_base")
        self.max_linear_velocity = max_linear_velocity
        self.max_angular_velocity = max_angular_velocity

    def execute_proposal(
        self,
        proposal: ActionProposal,
        world: GridWorld,
        lease_id: Optional[str] = None,
    ) -> ActionExecutionResult:
        """Execute an ActionProposal in the GridWorld.

        Args:
            proposal: ActionProposal contract to execute.
            world: GridWorld simulation environment.
            lease_id: Optional lease ID from Action Authorization.

        Returns:
            ActionExecutionResult contract.
        """
        effective_lease_id = lease_id or generate_uuid()
        target_entity_id = proposal.target_entity

        entity = world.entities.get(target_entity_id)
        if entity is None:
            # Entity not found in world
            return ActionExecutionResult(
                lease_id=effective_lease_id,
                outcome=ExecutionOutcome.FAILED.value,
                execution_stage=ExecutionStage.COMPLETED.value,
                actual_duration=0,
                actual_effects={"status": "entity_not_found"},
                deviation={"error": f"Entity '{target_entity_id}' not found in simulation world"},
                deviation_reason=f"Target entity '{target_entity_id}' absent",
            )

        action_type = proposal.action_type
        params = proposal.action_parameters
        expected_duration_ms = proposal.expected_duration

        start_time_ms = time.monotonic() * 1000.0

        if action_type == "move_to":
            return self._execute_move_to(
                proposal, world, entity, params, expected_duration_ms, effective_lease_id
            )
        elif action_type == "set_velocity":
            return self._execute_set_velocity(
                proposal, world, entity, params, expected_duration_ms, effective_lease_id
            )
        elif action_type == "stop":
            return self._execute_stop(
                proposal, world, entity, effective_lease_id
            )
        else:
            # Unknown action type
            return ActionExecutionResult(
                lease_id=effective_lease_id,
                outcome=ExecutionOutcome.REJECTED.value,
                execution_stage=ExecutionStage.COMPLETED.value,
                actual_duration=0,
                actual_effects=entity.to_dict(),
                deviation={"error": f"Unsupported action type '{action_type}'"},
                deviation_reason="Unsupported action",
            )

    def _execute_move_to(
        self,
        proposal: ActionProposal,
        world: GridWorld,
        entity: SimEntity,
        params: Dict[str, Any],
        expected_duration_ms: int,
        lease_id: str,
    ) -> ActionExecutionResult:
        """Simulate closed-loop movement toward target x, y."""
        target_x = float(params.get("target_x", params.get("x", entity.x)))
        target_y = float(params.get("target_y", params.get("y", entity.y)))
        speed = min(float(params.get("linear_velocity", params.get("speed", 1.0))), self.max_linear_velocity)

        sim_dt = 0.05  # 50ms simulation steps
        max_steps = max(1, int((expected_duration_ms / 1000.0) / sim_dt) + 20)

        collided = False
        collision_info = []

        actual_steps = 0
        for step in range(max_steps):
            actual_steps += 1
            dx = target_x - entity.x
            dy = target_y - entity.y
            dist = math.hypot(dx, dy)

            if dist < 0.05:
                # Target reached
                entity.vx = 0.0
                entity.vy = 0.0
                break

            # Compute heading toward target
            target_heading = math.atan2(dy, dx)
            entity.heading = target_heading

            # Set velocity vector
            entity.vx = speed * math.cos(target_heading)
            entity.vy = speed * math.sin(target_heading)

            # Step world simulation
            events = world.step(sim_dt)

            for evt in events:
                if evt.get("type") == "collision" and evt.get("entity_id") == entity.entity_id:
                    collided = True
                    collision_info = evt.get("collided_with", [])
                    break

            if collided:
                break

        actual_duration_ms = int(actual_steps * sim_dt * 1000.0)
        final_dist = math.hypot(target_x - entity.x, target_y - entity.y)

        status = ExecutionOutcome.COMPLETED.value
        stage = ExecutionStage.VERIFIED.value
        deviation = None
        deviation_reason = None

        if collided:
            status = ExecutionOutcome.FAILED.value
            deviation = {"collision": collision_info, "final_distance": final_dist}
            deviation_reason = f"Collision detected during motion with {collision_info}"
        elif final_dist > 0.2:
            status = ExecutionOutcome.PARTIAL.value
            deviation = {"target": [target_x, target_y], "actual": [entity.x, entity.y], "distance_rem": final_dist}
            deviation_reason = f"Execution timed out with remaining distance {final_dist:.2f}m"
        return ActionExecutionResult(
            lease_id=lease_id,
            outcome=status,
            execution_stage=stage,
            actual_duration=actual_duration_ms,
            actual_effects={
                "position": [entity.x, entity.y, 0.0],
                "velocity": [entity.vx, entity.vy, 0.0],
                "heading": entity.heading,
            },
            deviation=deviation,
            deviation_reason=deviation_reason,
            sensor_verification={
                "verified_by_gps": True,
                "position_error": final_dist if not collided else 0.0,
            },
        )

    def _execute_set_velocity(
        self,
        proposal: ActionProposal,
        world: GridWorld,
        entity: SimEntity,
        params: Dict[str, Any],
        expected_duration_ms: int,
        lease_id: str,
    ) -> ActionExecutionResult:
        """Simulate setting linear and angular velocity for duration."""
        vx = float(params.get("vx", params.get("linear_x", 0.0)))
        vy = float(params.get("vy", params.get("linear_y", 0.0)))
        omega = float(params.get("omega", params.get("angular_z", 0.0)))

        entity.vx = min(max(vx, -self.max_linear_velocity), self.max_linear_velocity)
        entity.vy = min(max(vy, -self.max_linear_velocity), self.max_linear_velocity)
        entity.omega = min(max(omega, -self.max_angular_velocity), self.max_angular_velocity)

        sim_dt = 0.05
        duration_s = expected_duration_ms / 1000.0
        steps = int(duration_s / sim_dt)

        collided = False
        collision_info = []

        for _ in range(steps):
            events = world.step(sim_dt)
            for evt in events:
                if evt.get("type") == "collision" and evt.get("entity_id") == entity.entity_id:
                    collided = True
                    collision_info = evt.get("collided_with", [])
                    break
            if collided:
                break
        return ActionExecutionResult(
            lease_id=lease_id,
            outcome=ExecutionOutcome.FAILED.value if collided else ExecutionOutcome.COMPLETED.value,
            execution_stage=ExecutionStage.VERIFIED.value,
            actual_duration=expected_duration_ms,
            actual_effects={
                "position": [entity.x, entity.y, 0.0],
                "velocity": [entity.vx, entity.vy, 0.0],
                "heading": entity.heading,
            },
            deviation={"collision": collision_info} if collided else None,
            deviation_reason=f"Collision detected with {collision_info}" if collided else None,
        )

    def _execute_stop(
        self,
        proposal: ActionProposal,
        world: GridWorld,
        entity: SimEntity,
        lease_id: str,
    ) -> ActionExecutionResult:
        """Halt entity motion immediately."""
        entity.vx = 0.0
        entity.vy = 0.0
        entity.ax = 0.0
        entity.ay = 0.0
        entity.omega = 0.0

        world.step(0.01)
        return ActionExecutionResult(
            lease_id=lease_id,
            outcome=ExecutionOutcome.COMPLETED.value,
            execution_stage=ExecutionStage.VERIFIED.value,
            actual_duration=10,
            actual_effects={
                "position": [entity.x, entity.y, 0.0],
                "velocity": [0.0, 0.0, 0.0],
                "heading": entity.heading,
            },
        )
