"""Industrial domain entity models for ORION Physical Intelligence OS.

Defines physical entities operating on a simulated factory floor with state_revision tracking,
deterministic safety-critical behaviors, and state plane integration.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple, Union


class IndustrialEntity:
    """Base class for all industrial domain entities in ORION.

    Provides state_revision tracking, unique identification, status tracking,
    and state export for the ORION State Plane.
    """

    def __init__(
        self,
        entity_id: str,
        entity_type: str,
        position: Optional[List[float]] = None,
        status: str = "NOMINAL",
    ) -> None:
        self.entity_id: str = entity_id
        self.entity_type: str = entity_type
        self.position: List[float] = list(position) if position else [0.0, 0.0, 0.0]
        self.status: str = status
        self.state_revision: int = 1
        self.last_updated_ns: int = time.monotonic_ns()

    def increment_state_revision(self) -> int:
        """Increment the state revision counter when entity state changes."""
        self.state_revision += 1
        self.last_updated_ns = time.monotonic_ns()
        return self.state_revision

    def set_status(self, new_status: str) -> None:
        """Update entity status and increment revision if changed."""
        if self.status != new_status:
            self.status = new_status
            self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        """Export state representation dictionary for state plane fusion."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "position": list(self.position),
            "status": self.status,
            "state_revision": self.state_revision,
            "last_updated_ns": self.last_updated_ns,
        }


class ConveyorBelt(IndustrialEntity):
    """Simulated conveyor belt entity."""

    def __init__(
        self,
        entity_id: str = "conveyor_1",
        max_speed: float = 2.0,
        length: float = 10.0,
        position: Optional[List[float]] = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="conveyor_belt",
            position=position or [0.0, 0.0, 0.0],
            status="STOPPED",
        )
        self.max_speed: float = max_speed
        self.length: float = length
        self.speed: float = 0.0
        self.is_running: bool = False
        self.direction: str = "forward"
        self.items: List[Dict[str, Any]] = []

    def start(self, speed: Optional[float] = None) -> None:
        """Start conveyor movement at specified speed or max_speed."""
        target_speed = speed if speed is not None else (self.speed if self.speed > 0 else 1.0)
        self.speed = min(max(0.0, target_speed), self.max_speed)
        self.is_running = True
        self.status = "RUNNING"
        self.increment_state_revision()

    def stop(self) -> None:
        """Halt conveyor belt movement immediately."""
        self.is_running = False
        self.speed = 0.0
        self.status = "STOPPED"
        self.increment_state_revision()

    def set_speed(self, speed: float) -> None:
        """Set conveyor belt operational speed."""
        self.speed = min(max(0.0, speed), self.max_speed)
        if self.speed == 0.0:
            self.is_running = False
            self.status = "STOPPED"
        else:
            self.is_running = True
            self.status = "RUNNING"
        self.increment_state_revision()

    def add_item(self, item_id: str, position_on_belt: float = 0.0, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add an item to the conveyor belt."""
        item = {
            "id": item_id,
            "position_on_belt": position_on_belt,
            "data": data or {},
        }
        self.items.append(item)
        self.increment_state_revision()
        return item

    def step(self, dt: float) -> List[Dict[str, Any]]:
        """Advance items along the conveyor belt."""
        if not self.is_running or self.speed == 0.0:
            return self.items

        direction_mult = 1.0 if self.direction == "forward" else -1.0
        delta_dist = direction_mult * self.speed * dt

        retained_items = []
        for item in self.items:
            item["position_on_belt"] += delta_dist
            if 0.0 <= item["position_on_belt"] <= self.length:
                retained_items.append(item)

        self.items = retained_items
        self.increment_state_revision()
        return self.items

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "speed": self.speed,
            "max_speed": self.max_speed,
            "length": self.length,
            "is_running": self.is_running,
            "direction": self.direction,
            "item_count": len(self.items),
            "items": [dict(i) for i in self.items],
        })
        return data


class RobotArm(IndustrialEntity):
    """Simulated multi-joint robotic arm entity with reach limits and gripper."""

    def __init__(
        self,
        entity_id: str = "robot_arm_1",
        base_position: Optional[List[float]] = None,
        reach_limit: float = 2.5,
        min_reach: float = 0.2,
    ) -> None:
        bp = base_position or [2.0, 2.0, 0.0]
        super().__init__(
            entity_id=entity_id,
            entity_type="robot_arm",
            position=bp,
            status="NOMINAL",
        )
        self.base_position: List[float] = list(bp)
        self.reach_limit: float = reach_limit
        self.min_reach: float = min_reach
        self.joints: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # Initial end-effector position
        self.end_effector_pos: List[float] = [bp[0] + 0.5, bp[1], bp[2] + 0.5]
        self.gripper_open: bool = True
        self.holding_item: Optional[Dict[str, Any]] = None

    def get_reach_distance(self, target_pos: List[float]) -> float:
        """Calculate Euclidean distance from arm base to target position."""
        dx = target_pos[0] - self.base_position[0]
        dy = target_pos[1] - self.base_position[1]
        dz = target_pos[2] - self.base_position[2] if len(target_pos) > 2 and len(self.base_position) > 2 else 0.0
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def is_within_reach(self, target_pos: List[float]) -> bool:
        """Check if target position is within min/max reach limits."""
        dist = self.get_reach_distance(target_pos)
        return self.min_reach <= dist <= self.reach_limit

    def move_end_effector(self, x: float, y: float, z: float) -> bool:
        """Move end effector to target 3D coordinate, validating reach limits."""
        target_pos = [x, y, z]
        dist = self.get_reach_distance(target_pos)

        if dist > self.reach_limit:
            raise ValueError(f"Target position {target_pos} exceeds reach limit ({self.reach_limit}m, actual {dist:.2f}m)")
        if dist < self.min_reach:
            raise ValueError(f"Target position {target_pos} below minimum reach limit ({self.min_reach}m, actual {dist:.2f}m)")

        self.end_effector_pos = [x, y, z]
        if self.holding_item:
            self.holding_item["position"] = list(self.end_effector_pos)

        self.increment_state_revision()
        return True

    def pick(self, item: Dict[str, Any], item_pos: Optional[List[float]] = None) -> bool:
        """Pick an item at item_pos or item['position']."""
        pos = item_pos or item.get("position", self.end_effector_pos)
        dist = self.get_reach_distance(pos)

        if dist > self.reach_limit:
            raise ValueError(f"Pick position {pos} exceeds reach limit ({self.reach_limit}m)")
        if dist < self.min_reach:
            raise ValueError(f"Pick position {pos} below minimum reach limit ({self.min_reach}m)")
        if not self.gripper_open:
            raise ValueError("Cannot pick: gripper is closed")
        if self.holding_item is not None:
            raise ValueError("Cannot pick: arm already holding an item")

        self.end_effector_pos = list(pos)
        self.gripper_open = False
        self.holding_item = dict(item)
        self.holding_item["position"] = list(self.end_effector_pos)
        self.increment_state_revision()
        return True

    def place(self, target_pos: List[float]) -> Dict[str, Any]:
        """Place currently held item at target_pos."""
        if self.holding_item is None:
            raise ValueError("Cannot place: arm is not holding any item")

        dist = self.get_reach_distance(target_pos)
        if dist > self.reach_limit:
            raise ValueError(f"Place position {target_pos} exceeds reach limit ({self.reach_limit}m)")
        if dist < self.min_reach:
            raise ValueError(f"Place position {target_pos} below minimum reach limit ({self.min_reach}m)")

        self.end_effector_pos = list(target_pos)
        placed_item = self.holding_item
        placed_item["position"] = list(target_pos)
        self.holding_item = None
        self.gripper_open = True
        self.increment_state_revision()
        return placed_item

    def set_gripper(self, open_state: bool) -> None:
        """Open or close the end-effector gripper."""
        self.gripper_open = open_state
        self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "base_position": list(self.base_position),
            "reach_limit": self.reach_limit,
            "min_reach": self.min_reach,
            "joints": list(self.joints),
            "end_effector_pos": list(self.end_effector_pos),
            "gripper_open": self.gripper_open,
            "holding_item": dict(self.holding_item) if self.holding_item else None,
        })
        return data


class PressureSensor(IndustrialEntity):
    """Pressure monitoring sensor with threshold detection."""

    def __init__(
        self,
        entity_id: str = "pressure_sensor_1",
        threshold: float = 100.0,
        min_threshold: float = 0.0,
        unit: str = "PSI",
        position: Optional[List[float]] = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="pressure_sensor",
            position=position or [0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.current_pressure: float = 50.0
        self.threshold: float = threshold
        self.min_threshold: float = min_threshold
        self.unit: str = unit

    def read_pressure(self) -> float:
        """Read current pressure value."""
        return self.current_pressure

    def set_pressure(self, value: float) -> float:
        """Set pressure value and update threshold status."""
        self.current_pressure = value
        if self.is_threshold_exceeded():
            self.set_status("EXCEEDED")
        else:
            self.set_status("NOMINAL")
        return self.current_pressure

    def is_threshold_exceeded(self) -> bool:
        """Check if current pressure exceeds threshold boundaries."""
        return self.current_pressure > self.threshold or self.current_pressure < self.min_threshold

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "current_pressure": self.current_pressure,
            "threshold": self.threshold,
            "min_threshold": self.min_threshold,
            "unit": self.unit,
            "is_threshold_exceeded": self.is_threshold_exceeded(),
        })
        return data


class TemperatureSensor(IndustrialEntity):
    """Temperature monitoring sensor with min/max thresholds and DEGRADED state transition."""

    def __init__(
        self,
        entity_id: str = "temp_sensor_1",
        max_threshold: float = 80.0,
        min_threshold: float = 0.0,
        unit: str = "°C",
        position: Optional[List[float]] = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="temperature_sensor",
            position=position or [0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.current_temperature: float = 25.0
        self.max_threshold: float = max_threshold
        self.min_threshold: float = min_threshold
        self.unit: str = unit

    def read_temperature(self) -> float:
        """Read current temperature value."""
        return self.current_temperature

    def set_temperature(self, value: float) -> float:
        """Set temperature value. If > max_threshold, triggers DEGRADED state transition."""
        self.current_temperature = value
        if self.is_out_of_bounds():
            self.set_status("DEGRADED")
        else:
            self.set_status("NOMINAL")
        return self.current_temperature

    def is_out_of_bounds(self) -> bool:
        """Check if temperature exceeds max or falls below min threshold."""
        return self.current_temperature > self.max_threshold or self.current_temperature < self.min_threshold

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "current_temperature": self.current_temperature,
            "max_threshold": self.max_threshold,
            "min_threshold": self.min_threshold,
            "unit": self.unit,
            "is_out_of_bounds": self.is_out_of_bounds(),
        })
        return data


class SafetyLightCurtain(IndustrialEntity):
    """Optical safety light curtain entity. Triggers E-stop when breached."""

    def __init__(
        self,
        entity_id: str = "light_curtain_1",
        zone: Optional[Dict[str, float]] = None,
        position: Optional[List[float]] = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="safety_light_curtain",
            position=position or [0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.is_breached: bool = False
        self.zone: Dict[str, float] = zone or {
            "min_x": 0.0, "max_x": 5.0,
            "min_y": 0.0, "max_y": 2.0,
        }

    def breach(self, intruder_id: Optional[str] = None) -> None:
        """Trigger safety light curtain breach."""
        self.is_breached = True
        self.set_status("BREACHED")

    def reset(self) -> None:
        """Reset light curtain to clear state."""
        self.is_breached = False
        self.set_status("NOMINAL")

    def check_intrusion(self, x: float, y: float) -> bool:
        """Check if coordinate breaches light curtain boundary zone."""
        if (self.zone.get("min_x", 0.0) <= x <= self.zone.get("max_x", 0.0) and
            self.zone.get("min_y", 0.0) <= y <= self.zone.get("max_y", 0.0)):
            self.breach(f"intrusion_at_{x}_{y}")
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "is_breached": self.is_breached,
            "zone": dict(self.zone),
        })
        return data


class EmergencyStopButton(IndustrialEntity):
    """Physical or virtual Emergency Stop (E-Stop) button."""

    def __init__(
        self,
        entity_id: str = "estop_1",
        position: Optional[List[float]] = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="emergency_stop_button",
            position=position or [0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.is_pressed: bool = False

    def press(self) -> None:
        """Press E-Stop button, triggering system-wide Emergency Stop."""
        self.is_pressed = True
        self.set_status("ESTOP")

    def reset(self) -> bool:
        """Reset E-Stop button to released state."""
        self.is_pressed = False
        self.set_status("NOMINAL")
        return True

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "is_pressed": self.is_pressed,
        })
        return data


class ValveController(IndustrialEntity):
    """Flow valve controller entity with deterministic failsafe = closed."""

    def __init__(
        self,
        entity_id: str = "valve_1",
        failsafe_state: str = "CLOSED",
        max_flow_rate: float = 10.0,
        position: Optional[List[float]] = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="valve_controller",
            position=position or [0.0, 0.0, 0.0],
            status="CLOSED",
        )
        self.is_open: bool = False
        self.failsafe_state: str = failsafe_state  # Always "CLOSED"
        self.flow_rate: float = 0.0
        self.max_flow_rate: float = max_flow_rate

    def open_valve(self, flow_rate: Optional[float] = None) -> None:
        """Open valve to requested or max flow rate."""
        rate = flow_rate if flow_rate is not None else self.max_flow_rate
        self.flow_rate = min(max(0.0, rate), self.max_flow_rate)
        self.is_open = True
        self.set_status("OPEN")

    def close_valve(self) -> None:
        """Close valve and stop flow."""
        self.is_open = False
        self.flow_rate = 0.0
        self.set_status("CLOSED")

    def trigger_failsafe(self) -> None:
        """Unconditionally trigger deterministic failsafe state (closed)."""
        self.close_valve()

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "is_open": self.is_open,
            "failsafe_state": self.failsafe_state,
            "flow_rate": self.flow_rate,
            "max_flow_rate": self.max_flow_rate,
        })
        return data


class TankLevel(IndustrialEntity):
    """Liquid tank fill level monitor with min/max thresholds and overflow protection."""

    def __init__(
        self,
        entity_id: str = "tank_1",
        capacity: float = 100.0,
        min_threshold: float = 10.0,
        max_threshold: float = 90.0,
        position: Optional[List[float]] = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            entity_type="tank_level",
            position=position or [0.0, 0.0, 0.0],
            status="NOMINAL",
        )
        self.capacity: float = capacity
        self.current_level: float = 50.0
        self.min_threshold: float = min_threshold
        self.max_threshold: float = max_threshold
        self.overflow_protection_active: bool = False

    def add_fluid(self, amount: float) -> float:
        """Add fluid to tank, enforcing overflow protection at max_threshold / capacity."""
        if amount <= 0.0:
            return 0.0

        if self.current_level + amount >= self.max_threshold:
            actual_added = max(0.0, self.max_threshold - self.current_level)
            self.current_level = self.max_threshold
            self.overflow_protection_active = True
            self.set_status("OVERFLOW_PREVENTED")
            return actual_added

        self.current_level += amount
        self.overflow_protection_active = False
        if self.is_underflow_risk():
            self.set_status("WARNING_LOW")
        else:
            self.set_status("NOMINAL")
        self.increment_state_revision()
        return amount

    def remove_fluid(self, amount: float) -> float:
        """Drain fluid from tank down to 0.0."""
        if amount <= 0.0:
            return 0.0

        actual_removed = min(self.current_level, amount)
        self.current_level -= actual_removed
        self.overflow_protection_active = False

        if self.is_underflow_risk():
            self.set_status("WARNING_LOW")
        else:
            self.set_status("NOMINAL")
        self.increment_state_revision()
        return actual_removed

    def is_overflow_risk(self) -> bool:
        """Check if tank level is at or above max threshold."""
        return self.current_level >= self.max_threshold

    def is_underflow_risk(self) -> bool:
        """Check if tank level is at or below min threshold."""
        return self.current_level <= self.min_threshold

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "capacity": self.capacity,
            "current_level": self.current_level,
            "min_threshold": self.min_threshold,
            "max_threshold": self.max_threshold,
            "overflow_protection_active": self.overflow_protection_active,
            "is_overflow_risk": self.is_overflow_risk(),
            "is_underflow_risk": self.is_underflow_risk(),
        })
        return data
