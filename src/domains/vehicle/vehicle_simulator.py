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

"""Vehicle Domain Simulator for ORION Physical Intelligence OS.

Simulates road environment with GridWorld backend, managing lanes, intersections, traffic lights,
autonomous ego vehicle, obstacle vehicles, scenario runner (highway, urban, parking),
and action proposal arbitration matching ORION SC-2 safety standards.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional

from simulation.grid_world import GridWorld
from src.contracts.contracts import (
    ActionExecutionResult,
    ActionProposal,
    ExecutionOutcome,
    ExecutionStage,
    generate_contract_id,
)
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


class VehicleSimulation:
    """Road environment simulation with full autonomous vehicle control and safety logging."""

    def __init__(
        self,
        road_length: float = 200.0,
        num_lanes: int = 3,
        lane_width: float = 3.5,
    ) -> None:
        self.road_length: float = road_length
        self.num_lanes: int = num_lanes
        self.lane_width: float = lane_width

        # Underlying 2D Kinematic GridWorld environment
        world_height = num_lanes * lane_width + 10.0
        self.world: GridWorld = GridWorld(width=road_length, height=world_height)

        # Primary Ego Vehicle
        ego_y = 0.5 * lane_width
        self.ego_vehicle: VehicleEntity = VehicleEntity(
            entity_id="ego_vehicle",
            position=[0.0, ego_y, 0.0],
            heading=0.0,
            lane_position=0,
            gear="DRIVE",
            state="IDLE",
        )
        self.world.add_entity(
            entity_id="ego_vehicle",
            x=0.0,
            y=ego_y,
            heading=0.0,
            radius=1.0,
            max_speed=self.ego_vehicle.max_speed,
        )

        # Ego Autonomous Sensors & Controllers
        self.lane_sensor: LaneSensor = LaneSensor("lane_sensor_ego", lane_width=lane_width, num_lanes=num_lanes)
        self.obstacle_sensor: ObstacleSensor = ObstacleSensor("obstacle_sensor_ego")
        self.traffic_light_sensor: TrafficLightSensor = TrafficLightSensor("traffic_light_sensor_ego")
        self.speed_controller: SpeedController = SpeedController("speed_controller_ego")
        self.steering_controller: SteeringController = SteeringController("steering_controller_ego")
        self.aeb_controller: AEBController = AEBController("aeb_controller_ego")
        self.collision_avoidance: CollisionAvoidance = CollisionAvoidance("cbf_avoidance_ego")
        self.acc: AdaptiveCruiseControl = AdaptiveCruiseControl("acc_ego")

        # Entity Registry
        self.vehicles: Dict[str, VehicleEntity] = {self.ego_vehicle.entity_id: self.ego_vehicle}
        self.traffic_lights: List[Dict[str, Any]] = []

        self.system_status: str = "NOMINAL"  # NOMINAL, DEGRADED, EMERGENCY, AUTONOMOUS
        self.autonomous_mode: bool = True
        self.time_elapsed: float = 0.0
        self.state_revision: int = 1
        self.safety_events: List[Dict[str, Any]] = []

    def increment_state_revision(self) -> int:
        self.state_revision += 1
        return self.state_revision

    def spawn_vehicle(
        self,
        vehicle_id: str,
        x: float,
        lane: int,
        speed: float = 0.0,
        gear: str = "DRIVE",
        heading: float = 0.0,
    ) -> VehicleEntity:
        """Spawn an auxiliary vehicle on the road."""
        lane_y = (lane + 0.5) * self.lane_width
        veh = VehicleEntity(
            entity_id=vehicle_id,
            position=[x, lane_y, 0.0],
            heading=heading,
            lane_position=lane,
            gear=gear,
            state="MOVING" if speed > 0 else "STOPPED",
        )
        veh.speed = speed
        self.vehicles[vehicle_id] = veh

        self.world.add_entity(
            entity_id=vehicle_id,
            x=x,
            y=lane_y,
            heading=heading,
            radius=1.0,
            max_speed=veh.max_speed,
        )
        self.increment_state_revision()
        return veh

    def add_traffic_light(
        self,
        light_id: str,
        x: float,
        lane: int = 0,
        state: str = "RED",
    ) -> Dict[str, Any]:
        """Add a traffic light signal to the simulation environment."""
        lane_y = (lane + 0.5) * self.lane_width
        tl = {
            "id": light_id,
            "position": [x, lane_y, 0.0],
            "state": state.upper(),
            "lane": lane,
        }
        self.traffic_lights.append(tl)
        self.increment_state_revision()
        return tl

    def set_traffic_light_state(self, light_id: str, state: str) -> None:
        """Change state of specified traffic light."""
        for tl in self.traffic_lights:
            if tl["id"] == light_id:
                tl["state"] = state.upper()
                self.increment_state_revision()
                break

    def log_safety_event(self, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log safety event with timestamp and state context."""
        event = {
            "timestamp": self.time_elapsed,
            "event_type": event_type,
            "details": details or {},
            "state_revision": self.state_revision,
        }
        self.safety_events.append(event)

    def step(self, dt: float = 0.1) -> Dict[str, Any]:
        """Advance vehicle simulation by dt seconds.

        Executes full autonomous driving loop (sensors -> plan -> safety check -> act -> verify)
        when autonomous_mode is enabled.
        """
        self.time_elapsed += dt
        current_events: List[str] = []

        # 1. Update auxiliary non-ego vehicles
        for v_id, veh in list(self.vehicles.items()):
            if v_id == "ego_vehicle":
                continue
            veh.update_kinematics(acceleration=0.0, steering_angle=0.0, dt=dt)
            gw_ent = self.world.entities.get(v_id)
            if gw_ent:
                gw_ent.x = veh.position[0]
                gw_ent.y = veh.position[1]
                gw_ent.vx = veh.speed * math.cos(veh.heading)
                gw_ent.vy = veh.speed * math.sin(veh.heading)

        # 2. Autonomous Cycle for Ego Vehicle
        if self.autonomous_mode and self.ego_vehicle.state != "EMERGENCY":
            # A. Sensor Sampling
            lane_info = self.lane_sensor.detect_lanes(self.ego_vehicle.position)
            if lane_info["departure_warning"]:
                current_events.append("LANE_DEPARTURE_WARNING")
                self.log_safety_event("LANE_DEPARTURE_WARNING", {"lane_offset": lane_info["lane_offset"]})

            obstacles_list = [
                {"id": v_id, "position": v.position, "speed": v.speed}
                for v_id, v in self.vehicles.items()
                if v_id != "ego_vehicle"
            ]
            obs_dict = self.obstacle_sensor.scan(self.ego_vehicle.position, self.ego_vehicle.heading, obstacles_list)

            tl_info = self.traffic_light_sensor.detect_light(
                self.traffic_lights, self.ego_vehicle.position, self.ego_vehicle.heading
            )

            # B. Plan & Desired Control Synthesis
            desired_accel = 0.0
            desired_steering = 0.0

            # Traffic Light Compliance
            if self.traffic_light_sensor.should_stop():
                desired_accel = self.speed_controller.compute_control(0.0, dt)
                current_events.append("TRAFFIC_LIGHT_STOP")
                self.log_safety_event("TRAFFIC_LIGHT_STOP", {"light_state": tl_info["light_state"]})
            else:
                # ACC (Adaptive Cruise Control)
                front_dist = self.obstacle_sensor.get_min_distance("front")
                lead_obs = obs_dict["front"][0] if obs_dict["front"] else None
                lead_speed = lead_obs["speed"] if lead_obs else None

                desired_accel = self.acc.compute_acceleration(
                    self.ego_vehicle.speed,
                    front_dist if lead_obs else None,
                    lead_speed,
                    dt,
                )
                if lead_obs and front_dist < 50.0:
                    current_events.append("ACC_DISTANCE_ADJUSTMENT")

            # Steering / Lane Keeping
            target_lane_y = (self.steering_controller.target_lane + 0.5) * self.lane_width
            desired_steering = self.steering_controller.compute_steering(
                self.ego_vehicle.position[1], target_lane_y, self.ego_vehicle.heading
            )

            # C. Safety & CBF Arbitration
            # Check AEB
            front_dist = self.obstacle_sensor.get_min_distance("front")
            lead_obs = obs_dict["front"][0] if obs_dict["front"] else None
            rel_speed = (self.ego_vehicle.speed - lead_obs["speed"]) if lead_obs else 0.0

            aeb_triggered, aeb_decel = self.aeb_controller.evaluate(
                self.ego_vehicle.speed, front_dist, relative_speed=rel_speed
            )
            if aeb_triggered:
                desired_accel = aeb_decel
                self.ego_vehicle.set_state("EMERGENCY")
                self.system_status = "EMERGENCY"
                current_events.append("AEB_TRIGGERED")
                current_events.append("EMERGENCY_BRAKE")
                self.log_safety_event("AEB_TRIGGERED", {"obstacle_dist": front_dist, "decel": aeb_decel})

            # Check CBF Collision Avoidance
            min_dists = {z: self.obstacle_sensor.get_min_distance(z) for z in ["front", "side_left", "side_right", "rear"]}
            safe_accel, safe_steering, cbf_modified = self.collision_avoidance.filter_control(
                self.ego_vehicle.speed, desired_accel, desired_steering, min_dists
            )

            if cbf_modified and not aeb_triggered:
                desired_accel = safe_accel
                desired_steering = safe_steering
                current_events.append("COLLISION_AVOIDANCE_CBF_INTERVENTION")
                self.log_safety_event("CBF_INTERVENTION", {"min_distances": min_dists})

            # D. Actuation & Kinematics Update
            self.ego_vehicle.update_kinematics(desired_accel, desired_steering, dt)

            # Synchronize GridWorld representation
            ego_gw = self.world.entities.get("ego_vehicle")
            if ego_gw:
                ego_gw.x = self.ego_vehicle.position[0]
                ego_gw.y = self.ego_vehicle.position[1]
                ego_gw.vx = self.ego_vehicle.speed * math.cos(self.ego_vehicle.heading)
                ego_gw.vy = self.ego_vehicle.speed * math.sin(self.ego_vehicle.heading)
                ego_gw.heading = self.ego_vehicle.heading

        # 3. Collision Verification in GridWorld
        gw_events = self.world.step(0.0)
        for gw_e in gw_events:
            if gw_e.get("type") == "collision":
                current_events.append("COLLISION_DETECTED")
                self.ego_vehicle.set_state("EMERGENCY")
                self.system_status = "EMERGENCY"
                self.log_safety_event("COLLISION_DETECTED", gw_e)

        self.increment_state_revision()

        return {
            "time_elapsed": self.time_elapsed,
            "system_status": self.system_status,
            "state_revision": self.state_revision,
            "events": current_events,
            "ego_vehicle": self.ego_vehicle.to_dict(),
            "vehicles": {k: v.to_dict() for k, v in self.vehicles.items()},
            "traffic_lights": list(self.traffic_lights),
        }

    def run_scenario(
        self,
        scenario_name: str,
        duration_sec: float = 10.0,
        dt: float = 0.1,
    ) -> Dict[str, Any]:
        """Execute a structured test scenario (highway, urban, parking)."""
        scenario_lower = scenario_name.lower()
        self.time_elapsed = 0.0
        self.safety_events = []
        self.vehicles = {self.ego_vehicle.entity_id: self.ego_vehicle}
        self.traffic_lights = []
        self.system_status = "NOMINAL"

        if scenario_lower == "highway":
            self.ego_vehicle.position = [0.0, 1.75, 0.0]
            self.ego_vehicle.speed = 25.0
            self.ego_vehicle.set_gear("DRIVE")
            self.ego_vehicle.set_state("MOVING")

            self.spawn_vehicle("lead_car", x=30.0, lane=0, speed=15.0)
            self.acc.set_target_speed(25.0)

        elif scenario_lower == "urban":
            self.ego_vehicle.position = [0.0, 1.75, 0.0]
            self.ego_vehicle.speed = 12.0
            self.ego_vehicle.set_gear("DRIVE")
            self.ego_vehicle.set_state("MOVING")

            self.add_traffic_light("tl_intersection", x=35.0, lane=0, state="RED")

        elif scenario_lower == "parking":
            self.ego_vehicle.position = [0.0, 1.75, 0.0]
            self.ego_vehicle.speed = 3.0
            self.ego_vehicle.set_gear("DRIVE")

            self.spawn_vehicle("parked_car", x=5.0, lane=0, speed=0.0)

        else:
            raise ValueError(f"Unknown scenario '{scenario_name}'. Allowed: 'highway', 'urban', 'parking'")

        steps = int(duration_sec / dt)
        step_history = []

        for _ in range(steps):
            res = self.step(dt)
            step_history.append(res)

            if scenario_lower == "urban" and self.time_elapsed >= 5.0:
                self.set_traffic_light_state("tl_intersection", "GREEN")

        return {
            "scenario": scenario_name,
            "duration_sec": self.time_elapsed,
            "safety_events": list(self.safety_events),
            "final_ego_state": self.ego_vehicle.to_dict(),
            "total_steps": len(step_history),
        }

    def _get_front_distance(self) -> Optional[float]:
        """Get distance to nearest front obstacle."""
        try:
            return self.obstacle_sensor.get_min_distance("front")
        except Exception:
            return None

    def propose_action(self, proposal: ActionProposal) -> ActionExecutionResult:
        """Arbitrate and execute an ActionProposal through the ORION pipeline."""
        lease_id = generate_contract_id()
        action_type = proposal.action_type
        params = proposal.action_parameters or {}

        # 1. Emergency state rejection
        if self.system_status == "EMERGENCY" and action_type != "reset_emergency":
            return ActionExecutionResult(
                lease_id=lease_id,
                outcome=ExecutionOutcome.REJECTED.value,
                execution_stage=ExecutionStage.COMPLETED.value,
                actual_duration=0,
                actual_effects={"system_status": self.system_status},
                deviation={"error": "Action rejected: System is in EMERGENCY state"},
                deviation_reason="Vehicle system in EMERGENCY state",
            )

        # 2. Input validation — reject NaN, infinity, negative speed
        try:
            if action_type == "accelerate":
                accel = float(params.get("acceleration", 1.0))
                if math.isnan(accel) or math.isinf(accel):
                    return ActionExecutionResult(
                        lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                        execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                        actual_effects={}, deviation={"error": "Invalid acceleration: NaN/inf"},
                        deviation_reason="Invalid input")
            elif action_type == "brake":
                decel = float(params.get("deceleration", -2.0))
                if math.isnan(decel) or math.isinf(decel):
                    return ActionExecutionResult(
                        lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                        execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                        actual_effects={}, deviation={"error": "Invalid deceleration: NaN/inf"},
                        deviation_reason="Invalid input")
            elif action_type == "steer":
                angle = float(params.get("steering_angle", 0.0))
                if math.isnan(angle) or math.isinf(angle):
                    return ActionExecutionResult(
                        lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                        execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                        actual_effects={}, deviation={"error": "Invalid steering: NaN/inf"},
                        deviation_reason="Invalid input")
            elif action_type == "set_speed":
                target_speed = float(params.get("target_speed", 20.0))
                if math.isnan(target_speed) or math.isinf(target_speed) or target_speed < 0:
                    return ActionExecutionResult(
                        lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                        execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                        actual_effects={}, deviation={"error": "Invalid target speed: NaN/inf/negative"},
                        deviation_reason="Invalid input")
        except (ValueError, TypeError):
            return ActionExecutionResult(
                lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                actual_effects={}, deviation={"error": "Invalid numeric parameter"},
                deviation_reason="Invalid input")

        # 3. AEB/CBF pre-check — reject actions that would cause collision
        if action_type in ("accelerate", "steer", "lane_change", "set_speed"):
            front_dist = self._get_front_distance()
            if front_dist is not None and front_dist < 5.0:
                should_trigger, aeb_decel = self.aeb_controller.evaluate(
                    current_speed=self.ego_vehicle.speed, obstacle_distance=front_dist
                )
                if should_trigger and abs(aeb_decel) > 0:
                    return ActionExecutionResult(
                        lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                        execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                        actual_effects=self.ego_vehicle.to_dict(),
                        deviation={"error": f"AEB active: obstacle at {front_dist:.1f}m, action rejected"},
                        deviation_reason="AEB collision risk",
                    )

        # 4. Action execution
        start_time = time.monotonic()

        try:
            if action_type == "accelerate":
                accel = float(params.get("acceleration", 1.0))
                self.ego_vehicle.update_kinematics(acceleration=accel, steering_angle=0.0, dt=0.1)
                effects = self.ego_vehicle.to_dict()

            elif action_type == "brake":
                decel = float(params.get("deceleration", -2.0))
                self.ego_vehicle.update_kinematics(acceleration=decel, steering_angle=0.0, dt=0.1)
                effects = self.ego_vehicle.to_dict()

            elif action_type == "steer":
                angle = float(params.get("steering_angle", 0.0))
                self.ego_vehicle.update_kinematics(acceleration=0.0, steering_angle=angle, dt=0.1)
                effects = self.ego_vehicle.to_dict()

            elif action_type == "set_gear":
                gear = str(params.get("gear", "DRIVE"))
                self.ego_vehicle.set_gear(gear)
                effects = self.ego_vehicle.to_dict()

            elif action_type == "lane_change":
                direction = str(params.get("direction", "LEFT"))
                target_lane = int(params.get("target_lane", self.steering_controller.target_lane + (1 if direction.upper() == "LEFT" else -1)))
                self.steering_controller.initiate_lane_change(direction, target_lane)
                effects = self.steering_controller.to_dict()

            elif action_type == "set_speed":
                target_speed = float(params.get("target_speed", 20.0))
                self.speed_controller.set_target_speed(target_speed)
                self.acc.set_target_speed(target_speed)
                effects = self.speed_controller.to_dict()

            elif action_type == "enable_autonomous":
                enabled = bool(params.get("enabled", True))
                self.autonomous_mode = enabled
                effects = {"autonomous_mode": self.autonomous_mode}

            elif action_type == "trigger_aeb":
                self.aeb_controller.evaluate(current_speed=self.ego_vehicle.speed, obstacle_distance=1.0)
                self.ego_vehicle.set_state("EMERGENCY")
                self.system_status = "EMERGENCY"
                effects = self.ego_vehicle.to_dict()

            elif action_type == "reset_emergency":
                # Require HMAC authorization to reset emergency state
                hmac_credential = params.get("hmac_credential", None)
                if not hmac_credential:
                    return ActionExecutionResult(
                        lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                        execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                        actual_effects=self.ego_vehicle.to_dict(),
                        deviation={"error": "Emergency reset requires HMAC credential"},
                        deviation_reason="Unauthorized emergency reset — no credential",
                    )
                import hashlib
                import hmac as hmac_mod
                import os
                expected_key = os.environ.get("ORION_EMERGENCY_HMAC_KEY", "")
                if not expected_key:
                    return ActionExecutionResult(
                        lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                        execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                        actual_effects=self.ego_vehicle.to_dict(),
                        deviation={"error": "ORION_EMERGENCY_HMAC_KEY not configured"},
                        deviation_reason="Cannot verify credential — key not configured",
                    )
                expected_hmac = hmac_mod.new(expected_key.encode(), b"reset_emergency", hashlib.sha256).hexdigest()
                if not hmac_mod.compare_digest(str(hmac_credential), expected_hmac):
                    return ActionExecutionResult(
                        lease_id=lease_id, outcome=ExecutionOutcome.REJECTED.value,
                        execution_stage=ExecutionStage.COMPLETED.value, actual_duration=0,
                        actual_effects=self.ego_vehicle.to_dict(),
                        deviation={"error": "Invalid HMAC credential for emergency reset"},
                        deviation_reason="Unauthorized emergency reset — invalid credential",
                    )
                self.aeb_controller.reset()
                self.ego_vehicle.set_state("STOPPED")
                self.system_status = "NOMINAL"
                effects = self.ego_vehicle.to_dict()

            else:
                return ActionExecutionResult(
                    lease_id=lease_id,
                    outcome=ExecutionOutcome.FAILED.value,
                    execution_stage=ExecutionStage.COMPLETED.value,
                    actual_duration=0,
                    actual_effects={},
                    deviation={"error": f"Unknown action type '{action_type}'"},
                    deviation_reason=f"Action '{action_type}' unsupported",
                )

            duration = time.monotonic() - start_time
            self.increment_state_revision()

            return ActionExecutionResult(
                lease_id=lease_id,
                outcome=ExecutionOutcome.COMPLETED.value,
                execution_stage=ExecutionStage.COMPLETED.value,
                actual_duration=duration,
                actual_effects=effects,
                deviation=None,
                deviation_reason=None,
            )

        except Exception as e:
            return ActionExecutionResult(
                lease_id=lease_id,
                outcome=ExecutionOutcome.FAILED.value,
                execution_stage=ExecutionStage.COMPLETED.value,
                actual_duration=0,
                actual_effects={},
                deviation={"error": str(e)},
                deviation_reason=f"Execution error: {str(e)}",
            )
