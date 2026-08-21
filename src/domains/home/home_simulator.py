"""Smart Home Simulation Environment for ORION Phase 4.

Simulates a smart home containing:
- Multiple RoomEntity instances (living room, kitchen, bedroom)
- HVACController per zone
- LightingController per room
- SecuritySensors (door, window, motion)
- SmartLock (front door, fail-safe)
- SmokeDetector per room
- EnergyMonitor (whole house)
- EvacuationController (coordinates emergency response)

Features state_revision tracking, safety event logging, and
action proposal -> execution pipeline integration.

Safety Criticality: SC-3 (lowest, but human occupancy)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.contracts.contracts import (
    ActionExecutionResult,
    ActionProposal,
    ExecutionOutcome,
    ExecutionStage,
    RiskTier,
    generate_contract_id,
)
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


class HomeSimulation:
    """Smart home simulation managing entities and safety responses."""

    def __init__(self) -> None:
        # Rooms
        self.living_room = RoomEntity("room_living", "Living Room", 25.0, 0, 22.0, 45.0, 1)
        self.kitchen = RoomEntity("room_kitchen", "Kitchen", 15.0, 0, 20.0, 50.0, 0)
        self.bedroom = RoomEntity("room_bedroom", "Bedroom", 18.0, 1, 21.0, 40.0, 0)

        # HVAC — one per zone (ground floor, first floor)
        self.hvac_ground = HVACController("hvac_ground", "room_living", 22.0, "auto")
        self.hvac_first = HVACController("hvac_first", "room_bedroom", 20.0, "auto")
        self.hvac_ground.add_zone("room_kitchen")

        # Lighting
        self.light_living = LightingController("light_living", "room_living", 60, 3000, "warm")
        self.light_kitchen = LightingController("light_kitchen", "room_kitchen", 80, 4000, "bright")
        self.light_bedroom = LightingController("light_bedroom", "room_bedroom", 20, 2700, "reading")

        # Security sensors
        self.front_door = SecuritySensor("sec_front_door", "room_living", "door")
        self.kitchen_window = SecuritySensor("sec_kitchen_window", "room_kitchen", "window")
        self.motion_living = SecuritySensor("sec_motion_living", "room_living", "motion")

        # Smart lock (front door)
        self.front_lock = SmartLock("lock_front", "room_living", is_locked=True)

        # Smoke detectors
        self.smoke_living = SmokeDetector("smoke_living", "room_living")
        self.smoke_kitchen = SmokeDetector("smoke_kitchen", "room_kitchen")
        self.smoke_bedroom = SmokeDetector("smoke_bedroom", "room_bedroom")

        # Energy monitor (whole house)
        self.energy = EnergyMonitor("energy_1", "whole_house")

        # Evacuation controller
        self.evacuation = EvacuationController("evacuation_1")

        # Entity registry
        self.entities: Dict[str, HomeEntity] = {
            self.living_room.entity_id: self.living_room,
            self.kitchen.entity_id: self.kitchen,
            self.bedroom.entity_id: self.bedroom,
            self.hvac_ground.entity_id: self.hvac_ground,
            self.hvac_first.entity_id: self.hvac_first,
            self.light_living.entity_id: self.light_living,
            self.light_kitchen.entity_id: self.light_kitchen,
            self.light_bedroom.entity_id: self.light_bedroom,
            self.front_door.entity_id: self.front_door,
            self.kitchen_window.entity_id: self.kitchen_window,
            self.motion_living.entity_id: self.motion_living,
            self.front_lock.entity_id: self.front_lock,
            self.smoke_living.entity_id: self.smoke_living,
            self.smoke_kitchen.entity_id: self.smoke_kitchen,
            self.smoke_bedroom.entity_id: self.smoke_bedroom,
            self.energy.entity_id: self.energy,
            self.evacuation.entity_id: self.evacuation,
        }

        self.system_status: str = "NOMINAL"
        self.time_elapsed: float = 0.0
        self.state_revision: int = 1
        self.safety_events: List[Dict[str, Any]] = []
        self._safety_gate_active: bool = False  # Set True by execute_action, checked by direct methods

    def increment_state_revision(self) -> int:
        self.state_revision += 1
        return self.state_revision

    def get_all_rooms(self) -> List[RoomEntity]:
        return [self.living_room, self.kitchen, self.bedroom]

    def get_room_by_id(self, room_id: str) -> Optional[RoomEntity]:
        for room in self.get_all_rooms():
            if room.entity_id == room_id:
                return room
        return None

    def _log_safety_event(self, event_type: str, source: str, details: Dict[str, Any]) -> None:
        event = {
            "event_type": event_type,
            "source": source,
            "timestamp": time.time(),
            "details": details,
        }
        self.safety_events.append(event)

    def _require_safety_gate(self) -> None:
        """Guard: prevent direct calls bypassing execute_action() (Luna Round 7 #1)."""
        if not self._safety_gate_active:
            raise PermissionError(
                "Direct mutation blocked: use execute_action() or run_scenario() "
                "- Safety Gateway authorization required (Luna Round 7 #1)"
            )

    def update_hvac(self) -> None:
        """Update all HVAC controllers based on room temperatures."""
        self._require_safety_gate()
        self.hvac_ground.update(self.living_room.temperature)
        self.hvac_first.update(self.bedroom.temperature)
        self.increment_state_revision()

    def trigger_fire_emergency(self, room_id: str = "room_kitchen") -> Dict[str, Any]:
        """
        Trigger fire emergency: smoke detector → unlock doors → evacuation lighting → HVAC shutdown.

        Returns summary of actions taken.
        """
        self._require_safety_gate()
        room = self.get_room_by_id(room_id)
        if not room:
            return {"error": "Room not found"}

        actions = []

        # 1. Trigger smoke detector
        smoke_detector = None
        if room_id == "room_living":
            smoke_detector = self.smoke_living
        elif room_id == "room_kitchen":
            smoke_detector = self.smoke_kitchen
        elif room_id == "room_bedroom":
            smoke_detector = self.smoke_bedroom

        if smoke_detector:
            smoke_detector.update_levels(smoke=150.0, co=120.0)
            smoke_detector.trigger_evacuation()
            actions.append(f"Smoke detector {smoke_detector.entity_id}: CRITICAL")

        # 2. Fail-safe unlock all doors
        self.front_lock.fail_safe_unlock()
        actions.append(f"Front door {self.front_lock.entity_id}: FAIL-SAFE UNLOCKED")

        # 3. Activate evacuation lighting in all rooms
        self.light_living.activate_evacuation_mode()
        self.light_kitchen.activate_evacuation_mode()
        self.light_bedroom.activate_evacuation_mode()
        actions.append("All lights: EVACUATION MODE (100% brightness)")

        # 4. Shutdown HVAC (prevent smoke spread)
        self.hvac_ground.shutdown()
        self.hvac_first.shutdown()
        actions.append("All HVAC: SHUTDOWN")

        # 5. Activate evacuation controller
        all_room_ids = [r.entity_id for r in self.get_all_rooms()]
        self.evacuation.activate(f"smoke_detector:{room_id}", all_room_ids)
        actions.append(f"Evacuation controller: ACTIVE (source: {room_id})")

        # 6. Update system status
        self.system_status = "EMERGENCY"

        # 7. Log safety event
        self._log_safety_event("fire_emergency", room_id, {
            "actions": actions,
            "smoke_level": smoke_detector.smoke_level if smoke_detector else 0,
            "co_level": smoke_detector.co_level if smoke_detector else 0,
        })

        self.increment_state_revision()
        return {"status": "EMERGENCY", "actions": actions}

    def clear_emergency(self, hmac_credential: Optional[str] = None, timestamp: Optional[float] = None) -> None:
        """Clear emergency state and reset all systems to normal. Requires HMAC authorization with replay protection.

        Args:
            hmac_credential: HMAC-SHA256 of f"clear_emergency:{timestamp}" using ORION_EMERGENCY_HMAC_KEY
            timestamp: Unix timestamp (seconds). Must be within 60 seconds of current time (replay window).
        """
        if not hmac_credential or not hmac_credential.strip():
            raise PermissionError("HMAC credential required to clear emergency — deny by default")
        if timestamp is None:
            raise PermissionError("Timestamp required for replay protection — deny by default")
        import time as _time
        if abs(_time.time() - timestamp) > 60.0:
            raise PermissionError("HMAC timestamp outside replay window — emergency clearing denied")
        import hashlib
        import hmac as hmac_mod
        import os
        expected_key = os.environ.get("ORION_EMERGENCY_HMAC_KEY", "")
        if not expected_key:
            raise PermissionError("ORION_EMERGENCY_HMAC_KEY not configured — cannot authorize emergency clearing")
        expected_message = f"clear_emergency:{timestamp}".encode()
        expected_hmac = hmac_mod.new(expected_key.encode(), expected_message, hashlib.sha256).hexdigest()
        if not hmac_mod.compare_digest(hmac_credential, expected_hmac):
            raise PermissionError("Invalid HMAC credential — emergency clearing denied")
        self.system_status = "NOMINAL"
        self.evacuation.deactivate()

        # Reset smoke detectors
        self.smoke_living.reset()
        self.smoke_kitchen.reset()
        self.smoke_bedroom.reset()

        # Reset lock
        self.front_lock.reset_fail_safe()
        self.front_lock.lock()

        # Reset lighting
        self.light_living.set_scene("warm")
        self.light_kitchen.set_scene("bright")
        self.light_bedroom.set_scene("reading")

        # Restart HVAC
        self.hvac_ground.set_mode("auto")
        self.hvac_first.set_mode("auto")

        self._log_safety_event("emergency_cleared", "system", {})
        self.increment_state_revision()

    def trigger_intrusion(self, sensor_id: str = "sec_motion_living") -> Dict[str, Any]:
        """Trigger intrusion detection via security sensor."""
        self._require_safety_gate()
        sensor = self.entities.get(sensor_id)
        if not sensor or not isinstance(sensor, SecuritySensor):
            return {"error": "Sensor not found"}

        actions = []
        if sensor.is_motion():
            sensor.trigger_motion()
            actions.append(f"Motion detected: {sensor.entity_id}")
        elif sensor.is_door():
            sensor.open()
            actions.append(f"Door opened: {sensor.entity_id}")
        elif sensor.is_window():
            sensor.open()
            actions.append(f"Window opened: {sensor.entity_id}")

        # Ensure locks stay engaged during intrusion
        if not self.front_lock.fail_safe_unlocked:
            self.front_lock.lock()
            actions.append("Front door: LOCKED (intrusion response)")

        self._log_safety_event("intrusion_detected", sensor_id, {"actions": actions})
        self.increment_state_revision()
        return {"status": "ALERT", "actions": actions}

    def run_normal_cycle(self) -> Dict[str, Any]:
        """Run a normal operation cycle: sensor → state → plan → act → verify."""
        self._require_safety_gate()
        # Phase 1: Sense (read all sensor states)
        room_temps = {
            self.living_room.entity_id: self.living_room.temperature,
            self.kitchen.entity_id: self.kitchen.temperature,
            self.bedroom.entity_id: self.bedroom.temperature,
        }

        # Phase 2: State (update HVAC based on temps)
        hvac_actions = []
        for hvac in [self.hvac_ground, self.hvac_first]:
            for room_id in hvac.zones:
                if room_id in room_temps:
                    action = hvac.update(room_temps[room_id])
                    if action != "idle":
                        hvac_actions.append(f"{hvac.entity_id}: {action}")

        # Phase 3: Plan (check for safety issues)
        safety_checks = []
        for sd in [self.smoke_living, self.smoke_kitchen, self.smoke_bedroom]:
            if sd.is_warning():
                safety_checks.append(f"{sd.entity_id}: WARNING")
            elif sd.is_critical():
                safety_checks.append(f"{sd.entity_id}: CRITICAL")

        # Phase 4: Act (if no emergencies, update energy)
        if self.system_status == "NOMINAL":
            total_power = sum(h.fan_speed * 0.01 for h in [self.hvac_ground, self.hvac_first])
            total_power += sum(lt.brightness * 0.005 for lt in [self.light_living, self.light_kitchen, self.light_bedroom])
            self.energy.update_usage(total_power)

        # Phase 5: Verify
        self.time_elapsed += 1.0
        self.increment_state_revision()

        return {
            "cycle": "normal",
            "hvac_actions": hvac_actions,
            "safety_checks": safety_checks,
            "power_usage": self.energy.power_usage_kw,
            "system_status": self.system_status,
        }

    def create_action_proposal(
        self,
        action_type: str,
        target_entity: str,
        action_params: Dict[str, Any],
        risk_tier: RiskTier = RiskTier.TIER_1,
    ) -> ActionProposal:
        """Create an ActionProposal for smart home domain actions."""
        return ActionProposal(
            action_id=generate_contract_id(),
            action_type=action_type,
            target_entity=target_entity,
            action_parameters=action_params,
            risk_tier=risk_tier,
            producer="HomeSimulation",
            consumer="ActionArbitration",
        )

    def execute_action(self, proposal: ActionProposal) -> ActionExecutionResult:
        """Execute an action proposal."""
        # Safety Gateway enforcement: reject actions not approved by Safety Gateway
        # ALL home actions are physical — they affect the physical environment (HVAC, lighting, locks, etc.)
        # ALL home actions affect physical environment (HVAC, lighting, locks, evacuation)
        # SC-3: human occupancy — every action must go through Safety Gateway
        physical_actions = {
            "lock", "unlock", "trigger_evacuation", "clear_emergency",
            "set_temperature", "set_brightness", "set_hvac_mode",
        }
        if proposal.action_type in physical_actions and not (
            getattr(proposal, "safety_approved", False) is True
            and getattr(proposal, "has_valid_safety_auth", lambda: False)()
        ):
            return ActionExecutionResult(
                outcome=ExecutionOutcome.REJECTED,
                execution_stage=ExecutionStage.COMPLETED,
                deviation_reason=f"Safety Gateway rejection: action '{proposal.action_type}' requires valid safety authorization token (Change #3: mutable boolean no longer sufficient)",
                producer="HomeSimulation",
                consumer="ActionArbitration",
            )

        # Safety check: block non-emergency actions during emergency state
        if self.system_status == "EMERGENCY" and proposal.action_type not in ("trigger_evacuation", "clear_emergency"):
            return ActionExecutionResult(
                outcome=ExecutionOutcome.REJECTED,
                execution_stage=ExecutionStage.COMPLETED,
                deviation_reason="System in EMERGENCY state — non-emergency actions blocked",
                producer="HomeSimulation",
                consumer="ActionArbitration",
            )

        entity = self.entities.get(proposal.target_entity)
        success = False
        error_msg = ""
        self._safety_gate_active = True

        if entity is None:
            error_msg = f"Entity {proposal.target_entity} not found"
        else:
            params = proposal.action_parameters or {}
            action = proposal.action_type

            try:
                if action == "set_temperature" and isinstance(entity, HVACController):
                    entity.set_target_temp(params.get("temperature", 22.0))
                    success = True
                elif action == "set_brightness" and isinstance(entity, LightingController):
                    entity.set_brightness(params.get("brightness", 0))
                    success = True
                elif action == "lock" and isinstance(entity, SmartLock):
                    entity.lock()
                    success = True
                elif action == "unlock" and isinstance(entity, SmartLock):
                    entity.unlock()
                    success = True
                elif action == "set_hvac_mode" and isinstance(entity, HVACController):
                    entity.set_mode(params.get("mode", "auto"))
                    success = True
                elif action == "trigger_evacuation":
                    result = self.trigger_fire_emergency(params.get("room_id", "room_kitchen"))
                    success = result.get("status") == "EMERGENCY"
                else:
                    error_msg = f"Unsupported action {action} for entity {entity.entity_type}"
            except Exception as e:
                error_msg = str(e)

        self._safety_gate_active = False
        return ActionExecutionResult(
            outcome=ExecutionOutcome.COMPLETED if success else ExecutionOutcome.FAILED,
            execution_stage=ExecutionStage.VERIFIED if success else ExecutionStage.EXECUTING,
            deviation_reason=error_msg if error_msg else None,
            producer="HomeSimulation",
            consumer="ActionArbitration",
        )

    def run_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Run a predefined scenario."""
        self._safety_gate_active = True  # Internal pipeline — safety gate armed
        try:
            if scenario_name == "normal":
                return self.run_normal_cycle()
            elif scenario_name == "fire":
                return self.trigger_fire_emergency("room_kitchen")
            elif scenario_name == "intrusion":
                return self.trigger_intrusion("sec_motion_living")
            elif scenario_name == "energy_optimization":
                # Turn off lights in unoccupied rooms
                actions = []
                for room, light in [
                    (self.living_room, self.light_living),
                    (self.kitchen, self.light_kitchen),
                    (self.bedroom, self.light_bedroom),
                ]:
                    if not room.is_occupied:
                        light.set_brightness(0)
                        actions.append(f"{light.entity_id}: turned off (unoccupied)")
                return {"scenario": "energy_optimization", "actions": actions}
            else:
                return {"error": f"Unknown scenario: {scenario_name}"}
        finally:
            self._safety_gate_active = False
