"""Drone Simulation Environment for ORION Phase 4.

Simulates a drone operating in a 3D grid environment with:
- DroneEntity with position, velocity, battery, and state
- IMU and altitude sensors
- Geofencing (virtual boundary enforcement via CBF)
- 3D collision avoidance (CBF)
- Battery management (low battery → return-to-base)
- Flight modes: hover, waypoint navigation, return-to-base, emergency landing
- Wind disturbance simulation

Safety Criticality: SC-2 (physical risk to people/property below)
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Tuple

from src.contracts.contracts import (
    ActionExecutionResult,
    ActionProposal,
    ExecutionOutcome,
    ExecutionStage,
    RiskTier,
    generate_contract_id,
)
from src.domains.drone.drone_entities import (
    AltitudeSensor,
    BatteryManager,
    CollisionAvoidance3D,
    DroneEntity,
    FlightController,
    GeofenceController,
    IMUSensor,
)


class DroneSimulation:
    """Drone simulation managing entity, sensors, and safety systems."""

    def __init__(
        self,
        home_position: List[float] = None,
        geofence_min: Tuple[float, float, float] = (-100.0, -100.0, -5.0),
        geofence_max: Tuple[float, float, float] = (100.0, 100.0, 120.0),
    ) -> None:
        self.home = list(home_position) if home_position else [0.0, 0.0, 0.0]

        # Core entities
        self.drone = DroneEntity("drone_1", position=list(self.home), battery_pct=100.0)
        self.imu = IMUSensor("imu_1")
        self.altimeter = AltitudeSensor("alt_1", max_altitude=120.0)
        self.geofence = GeofenceController(geofence_min, geofence_max)
        self.collision_avoidance = CollisionAvoidance3D(safe_distance=3.0)
        self.battery = BatteryManager(
            capacity_pct=100.0,
            home_position=list(self.home),
        )
        self.flight_ctrl = FlightController(home_position=list(self.home))

        # State
        self.system_status: str = "NOMINAL"
        self.time_elapsed: float = 0.0
        self.state_revision: int = 1
        self.safety_events: List[Dict[str, Any]] = []
        self.wind = [0.0, 0.0, 0.0]  # Wind disturbance

    def increment_state_revision(self) -> int:
        self.state_revision += 1
        return self.state_revision

    def _log_safety_event(self, event_type: str, source: str, details: Dict[str, Any]) -> None:
        self.safety_events.append({
            "event_type": event_type,
            "source": source,
            "timestamp": time.time(),
            "details": details,
        })

    def set_wind(self, wx: float, wy: float, wz: float) -> None:
        """Set wind disturbance."""
        self.wind = [wx, wy, wz]

    def takeoff(self, target_altitude: float = 10.0) -> Dict[str, Any]:
        """Take off to target altitude."""
        if self.drone.state not in ("IDLE",):
            return {"status": "ERROR", "reason": f"Cannot takeoff from state {self.drone.state}"}

        self.drone.set_state("FLYING")
        self.drone.set_flight_mode("hover")
        self.flight_ctrl.set_hover([self.home[0], self.home[1], target_altitude])
        self.system_status = "NOMINAL"
        self._log_safety_event("takeoff", "drone_1", {"target_altitude": target_altitude})
        self.increment_state_revision()
        return {"status": "OK", "target_altitude": target_altitude}

    def set_waypoints(self, waypoints: List[List[float]]) -> Dict[str, Any]:
        """Set waypoint navigation mission."""
        self.drone.set_state("FLYING")
        self.drone.set_flight_mode("waypoint")
        self.flight_ctrl.set_waypoints(waypoints)
        self._log_safety_event("waypoint_mission", "drone_1", {"waypoints": len(waypoints)})
        self.increment_state_revision()
        return {"status": "OK", "waypoint_count": len(waypoints)}

    def return_to_base(self) -> Dict[str, Any]:
        """Command drone to return to base."""
        self.drone.set_state("RETURNING")
        self.drone.set_flight_mode("return_to_base")
        self.flight_ctrl.set_return_to_base()
        self._log_safety_event("return_to_base", "drone_1", {"battery": self.battery.capacity_pct})
        self.increment_state_revision()
        return {"status": "OK", "battery": self.battery.capacity_pct}

    def emergency_land(self) -> Dict[str, Any]:
        """Command emergency landing at current position."""
        self.drone.set_state("EMERGENCY_LANDING")
        self.drone.set_flight_mode("emergency_landing")
        self.flight_ctrl.set_emergency_landing(self.drone.position)
        self.system_status = "EMERGENCY"
        self._log_safety_event("emergency_landing", "drone_1", {
            "position": list(self.drone.position),
            "battery": self.battery.capacity_pct,
        })
        self.increment_state_revision()
        return {"status": "EMERGENCY", "position": list(self.drone.position)}

    def step(self, dt: float = 0.1) -> Dict[str, Any]:
        """Run one simulation step."""
        events = []

        # 1. Compute desired velocity from flight controller
        desired_vel = self.flight_ctrl.compute_velocity(self.drone.position)

        # 2. Apply geofence filter (CBF)
        safe_vel = self.geofence.compute_safe_velocity(self.drone.position, desired_vel)
        is_safe, geofence_reason = self.geofence.check_position(self.drone.position)
        if not is_safe:
            events.append(f"Geofence: {geofence_reason}")

        # 3. Apply collision avoidance filter (CBF)
        safe_vel = self.collision_avoidance.filter_velocity(self.drone.position, safe_vel)
        is_collision_safe, collision_reason = self.collision_avoidance.check_safety(self.drone.position, safe_vel)
        if not is_collision_safe:
            events.append(f"Collision: {collision_reason}")

        # 4. Apply wind disturbance
        final_vel = [v + w for v, w in zip(safe_vel, self.wind)]

        # 5. Update drone state
        self.drone.set_velocity(*final_vel)
        self.drone.update_position(dt)

        # 6. Update sensors
        self.altimeter.update(self.drone.altitude)
        self.imu.update(
            orientation=[0.0, 0.0, 0.0],  # Level flight
            accel=final_vel,
            gyro=[0.0, 0.0, 0.0],
        )

        # 7. Drain battery
        is_hovering = all(abs(v) < 0.1 for v in final_vel)
        self.battery.drain(dt, is_hovering=is_hovering)
        self.drone.drain_battery(self.battery.discharge_rate_per_sec * dt * (0.7 if is_hovering else 1.0))

        # 8. Check battery thresholds
        if self.battery.should_emergency_land() and self.drone.flight_mode != "emergency_landing":
            self.emergency_land()
            events.append("Battery CRITICAL — emergency landing initiated")
        elif self.battery.should_return_to_base() and self.drone.flight_mode not in ("return_to_base", "emergency_landing"):
            self.return_to_base()
            events.append("Battery LOW — return to base initiated")

        # 9. Check geofence
        if not is_safe and self.drone.flight_mode != "emergency_landing":
            self.system_status = "WARNING"

        # 10. Check if reached target
        if self.drone.flight_mode == "return_to_base":
            # Check if drone is near home (within 2m horizontally)
            dx = self.drone.position[0] - self.home[0]
            dy = self.drone.position[1] - self.home[1]
            horiz_dist = math.sqrt(dx*dx + dy*dy)
            if horiz_dist < 2.0 and self.drone.position[2] < 3.0:
                self.drone.set_state("LANDING")
                self.drone.set_flight_mode("idle")
                events.append("Reached home — landing")
        elif self.flight_ctrl.has_reached_target(self.drone.position):
            if self.drone.flight_mode == "emergency_landing":
                self.drone.set_state("IDLE")
                self.drone.set_flight_mode("idle")
                self.system_status = "NOMINAL"
                events.append("Emergency landing complete")
            elif self.drone.flight_mode == "waypoint":
                if self.flight_ctrl.is_mission_complete():
                    self.drone.set_state("HOVERING")
                    events.append("Waypoint mission complete — hovering")

        # 11. Log events
        for event in events:
            self._log_safety_event("flight_event", "drone_1", {"event": event})

        self.time_elapsed += dt
        self.increment_state_revision()

        return {
            "position": list(self.drone.position),
            "velocity": list(self.drone.velocity),
            "battery": self.battery.capacity_pct,
            "state": self.drone.state,
            "mode": self.drone.flight_mode,
            "events": events,
        }

    def run_full_cycle(self) -> Dict[str, Any]:
        """Run a full autonomous cycle: takeoff → waypoint → return → land."""
        results = {}

        # Takeoff
        results["takeoff"] = self.takeoff(10.0)

        # Fly to waypoint
        self.set_waypoints([[20.0, 20.0, 15.0]])
        for _ in range(200):
            self.step(0.1)
            if self.flight_ctrl.has_reached_target(self.drone.position):
                break
        results["waypoint_reached"] = self.flight_ctrl.has_reached_target(self.drone.position)

        # Return to base
        self.return_to_base()
        for _ in range(200):
            self.step(0.1)
            if self.drone.state == "LANDING":
                break
        results["returned_home"] = self.drone.state == "LANDING"

        # Land
        self.drone.set_state("IDLE")
        results["landed"] = self.drone.state == "IDLE"

        return results

    def run_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Run a predefined scenario."""
        if scenario_name == "normal_flight":
            return self.run_full_cycle()
        elif scenario_name == "low_battery":
            self.battery.capacity_pct = 15.0
            self.drone.battery_pct = 15.0
            self.takeoff(10.0)
            self.set_waypoints([[50.0, 50.0, 20.0]])
            for _ in range(100):
                self.step(0.1)
                if self.drone.flight_mode == "return_to_base":
                    return {"status": "RETURN_TO_BASE", "battery": self.battery.capacity_pct}
            return {"status": "NO_RTB_TRIGGERED", "battery": self.battery.capacity_pct}
        elif scenario_name == "critical_battery":
            self.battery.capacity_pct = 5.0
            self.drone.battery_pct = 5.0
            self.takeoff(10.0)
            self.step(0.1)
            return {"status": self.drone.state, "battery": self.battery.capacity_pct}
        elif scenario_name == "geofence_breach":
            self.takeoff(10.0)
            self.set_waypoints([[200.0, 0.0, 10.0]])  # Beyond geofence
            for _ in range(50):
                self.step(0.1)
            return {"status": self.system_status, "position": list(self.drone.position)}
        elif scenario_name == "obstacle_avoidance":
            self.takeoff(10.0)
            self.collision_avoidance.add_obstacle([10.0, 0.0, 10.0], radius=2.0)
            self.set_waypoints([[20.0, 0.0, 10.0]])
            for _ in range(200):
                self.step(0.1)
                if self.flight_ctrl.has_reached_target(self.drone.position):
                    break
            return {"status": "OK", "position": list(self.drone.position)}
        elif scenario_name == "wind_disturbance":
            self.takeoff(10.0)
            self.set_wind(2.0, -1.0, 0.0)
            self.set_waypoints([[20.0, 20.0, 15.0]])
            for _ in range(200):
                self.step(0.1)
                if self.flight_ctrl.has_reached_target(self.drone.position):
                    break
            return {"status": "OK", "position": list(self.drone.position), "wind": list(self.wind)}
        else:
            return {"error": f"Unknown scenario: {scenario_name}"}

    def create_action_proposal(
        self,
        action_type: str,
        action_params: Dict[str, Any],
        risk_tier: RiskTier = RiskTier.TIER_2,
    ) -> ActionProposal:
        """Create an ActionProposal for drone domain actions."""
        return ActionProposal(
            action_id=generate_contract_id(),
            action_type=action_type,
            target_entity="drone_1",
            action_parameters=action_params,
            risk_tier=risk_tier,
            producer="DroneSimulation",
            consumer="ActionArbitration",
        )

    def execute_action(self, proposal: ActionProposal) -> ActionExecutionResult:
        """Execute an action proposal."""
        action = proposal.action_type
        params = proposal.action_parameters or {}
        success = False

        try:
            if action == "takeoff":
                result = self.takeoff(params.get("altitude", 10.0))
                success = result["status"] == "OK"
            elif action == "set_waypoints":
                result = self.set_waypoints(params.get("waypoints", []))
                success = result["status"] == "OK"
            elif action == "return_to_base":
                result = self.return_to_base()
                success = result["status"] == "OK"
            elif action == "emergency_land":
                result = self.emergency_land()
                success = True
            elif action == "set_wind":
                self.set_wind(
                    params.get("wx", 0.0),
                    params.get("wy", 0.0),
                    params.get("wz", 0.0),
                )
                success = True
            elif action == "step":
                self.step(params.get("dt", 0.1))
                success = True
            else:
                success = False
        except Exception:
            success = False

        return ActionExecutionResult(
            outcome=ExecutionOutcome.COMPLETED if success else ExecutionOutcome.FAILED,
            execution_stage=ExecutionStage.VERIFIED if success else ExecutionStage.EXECUTING,
            producer="DroneSimulation",
            consumer="ActionArbitration",
        )
