"""Smart Home domain entity models for ORION Physical Intelligence OS.

Defines entities for a simulated smart home environment including rooms,
HVAC, lighting, security sensors, smart locks, smoke/CO detectors,
energy monitors, and evacuation controllers.

Safety Criticality: SC-3 (lowest, but human occupancy)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class HomeEntity:
    """Base class for all smart home domain entities."""

    def __init__(
        self,
        entity_id: str,
        entity_type: str,
        room_id: str = "room_1",
        status: str = "NOMINAL",
    ) -> None:
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.room_id = room_id
        self.status = status
        self.state_revision = 1
        self.last_updated_ns = time.monotonic_ns()

    def increment_state_revision(self) -> int:
        self.state_revision += 1
        self.last_updated_ns = time.monotonic_ns()
        return self.state_revision

    def set_status(self, new_status: str) -> None:
        if self.status != new_status:
            self.status = new_status
            self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "room_id": self.room_id,
            "status": self.status,
            "state_revision": self.state_revision,
            "last_updated_ns": self.last_updated_ns,
        }


class RoomEntity(HomeEntity):
    """A room in a smart home with environmental sensors."""

    def __init__(
        self,
        entity_id: str = "room_1",
        name: str = "Living Room",
        area: float = 20.0,
        floor: int = 0,
        temperature: float = 22.0,
        humidity: float = 45.0,
        occupancy_count: int = 0,
    ) -> None:
        super().__init__(entity_id, "room", entity_id, "NOMINAL")
        self.name = name
        self.area = area
        self.floor = floor
        self.temperature = temperature
        self.humidity = humidity
        self.occupancy_count = occupancy_count
        self.is_occupied = occupancy_count > 0

    def set_temperature(self, temp: float) -> None:
        self.temperature = temp
        self.increment_state_revision()

    def set_humidity(self, humidity: float) -> None:
        self.humidity = max(0.0, min(100.0, humidity))
        self.increment_state_revision()

    def set_occupancy(self, count: int) -> None:
        self.occupancy_count = max(0, count)
        self.is_occupied = self.occupancy_count > 0
        self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "name": self.name,
            "area": self.area,
            "floor": self.floor,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "occupancy_count": self.occupancy_count,
            "is_occupied": self.is_occupied,
        })
        return d


class HVACController(HomeEntity):
    """HVAC controller with thermostat and zone support."""

    OFF = "off"
    HEATING = "heating"
    COOLING = "cooling"
    AUTO = "auto"

    def __init__(
        self,
        entity_id: str = "hvac_1",
        room_id: str = "room_1",
        target_temp: float = 22.0,
        mode: str = "auto",
        min_temp: float = 16.0,
        max_temp: float = 30.0,
    ) -> None:
        super().__init__(entity_id, "hvac_controller", room_id, "OFF")
        self.target_temp = target_temp
        self.mode = mode
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.current_temp = target_temp
        self.fan_speed = 0  # 0-100
        self.is_active = False
        self.zones: List[str] = [room_id]

    def set_target_temp(self, temp: float) -> None:
        self.target_temp = max(self.min_temp, min(self.max_temp, temp))
        self.increment_state_revision()

    def set_mode(self, mode: str) -> None:
        if mode in (self.OFF, self.HEATING, self.COOLING, self.AUTO):
            self.mode = mode
            if mode == self.OFF:
                self.is_active = False
                self.fan_speed = 0
                self.set_status("OFF")
            else:
                self.is_active = True
                self.set_status("ACTIVE")
            self.increment_state_revision()

    def update(self, current_temp: float) -> str:
        """Update HVAC state based on current temperature. Returns action taken."""
        self.current_temp = current_temp
        if not self.is_active or self.mode == self.OFF:
            return "idle"

        diff = self.target_temp - current_temp
        if self.mode == self.AUTO:
            if diff > 1.0:
                self.fan_speed = min(100, int(abs(diff) * 30))
                return "heating"
            elif diff < -1.0:
                self.fan_speed = min(100, int(abs(diff) * 30))
                return "cooling"
            else:
                self.fan_speed = 0
                return "idle"
        elif self.mode == self.HEATING:
            if diff > 0:
                self.fan_speed = min(100, int(diff * 30))
                return "heating"
            else:
                self.fan_speed = 0
                return "idle"
        elif self.mode == self.COOLING:
            if diff < 0:
                self.fan_speed = min(100, int(abs(diff) * 30))
                return "cooling"
            else:
                self.fan_speed = 0
                return "idle"
        return "idle"

    def add_zone(self, room_id: str) -> None:
        if room_id not in self.zones:
            self.zones.append(room_id)
            self.increment_state_revision()

    def shutdown(self) -> None:
        """Emergency shutdown of HVAC."""
        self.mode = self.OFF
        self.is_active = False
        self.fan_speed = 0
        self.set_status("SHUTDOWN")
        self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "target_temp": self.target_temp,
            "mode": self.mode,
            "current_temp": self.current_temp,
            "fan_speed": self.fan_speed,
            "is_active": self.is_active,
            "zones": list(self.zones),
        })
        return d


class LightingController(HomeEntity):
    """Lighting controller with dimming, color temp, scenes, occupancy-based control."""

    def __init__(
        self,
        entity_id: str = "light_1",
        room_id: str = "room_1",
        brightness: int = 0,
        color_temp: int = 3000,
        scene: str = "off",
    ) -> None:
        super().__init__(entity_id, "lighting_controller", room_id, "OFF")
        self.brightness = max(0, min(100, brightness))
        self.color_temp = max(2200, min(6500, color_temp))
        self.scene = scene
        self.occupancy_based = False

    def set_brightness(self, level: int) -> None:
        self.brightness = max(0, min(100, level))
        if self.brightness == 0:
            self.set_status("OFF")
        else:
            self.set_status("ON")
        self.increment_state_revision()

    def set_color_temp(self, temp: int) -> None:
        self.color_temp = max(2200, min(6500, temp))
        self.increment_state_revision()

    def set_scene(self, scene: str) -> None:
        scenes = {
            "off": 0,
            "reading": 80,
            "movie": 20,
            "bright": 100,
            "warm": 60,
            "evacuation": 100,
        }
        self.scene = scene
        if scene in scenes:
            self.brightness = scenes[scene]
            if scene == "off":
                self.set_status("OFF")
            else:
                self.set_status("ON")
        self.increment_state_revision()

    def set_occupancy_based(self, enabled: bool) -> None:
        self.occupancy_based = enabled
        self.increment_state_revision()

    def activate_evacuation_mode(self) -> None:
        """Set to maximum brightness for evacuation."""
        self.brightness = 100
        self.color_temp = 6500  # Cool white for visibility
        self.scene = "evacuation"
        self.set_status("EMERGENCY")
        self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "brightness": self.brightness,
            "color_temp": self.color_temp,
            "scene": self.scene,
            "occupancy_based": self.occupancy_based,
        })
        return d


class SecuritySensor(HomeEntity):
    """Security sensor for doors, windows, and motion detection."""

    DOOR = "door"
    WINDOW = "window"
    MOTION = "motion"

    def __init__(
        self,
        entity_id: str = "security_1",
        room_id: str = "room_1",
        sensor_type: str = "door",
    ) -> None:
        super().__init__(entity_id, "security_sensor", room_id, "CLOSED")
        self.sensor_type = sensor_type
        self.state = "closed" if sensor_type != "motion" else "no_motion"
        self.is_triggered = False
        self.last_triggered_time: Optional[float] = None

    def open(self) -> None:
        self.state = "open"
        self.is_triggered = True
        self.last_triggered_time = time.time()
        self.set_status("OPEN")

    def close(self) -> None:
        self.state = "closed"
        self.is_triggered = False
        self.set_status("CLOSED")

    def trigger_motion(self) -> None:
        self.state = "motion_detected"
        self.is_triggered = True
        self.last_triggered_time = time.time()
        self.set_status("TRIGGERED")

    def clear_motion(self) -> None:
        self.state = "no_motion"
        self.is_triggered = False
        self.set_status("NOMINAL")

    def is_door(self) -> bool:
        return self.sensor_type == self.DOOR

    def is_window(self) -> bool:
        return self.sensor_type == self.WINDOW

    def is_motion(self) -> bool:
        return self.sensor_type == self.MOTION

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "sensor_type": self.sensor_type,
            "state": self.state,
            "is_triggered": self.is_triggered,
            "last_triggered_time": self.last_triggered_time,
        })
        return d


class SmartLock(HomeEntity):
    """Smart lock with fail-safe (unlocked on emergency) and access logging."""

    def __init__(
        self,
        entity_id: str = "lock_1",
        room_id: str = "room_1",
        is_locked: bool = True,
    ) -> None:
        super().__init__(entity_id, "smart_lock", room_id, "LOCKED" if is_locked else "UNLOCKED")
        self.is_locked = is_locked
        self.fail_safe_unlocked = False
        self.access_log: List[Dict[str, Any]] = []

    def lock(self) -> None:
        if self.fail_safe_unlocked:
            return  # Cannot lock during emergency
        self.is_locked = True
        self.set_status("LOCKED")
        self.access_log.append({"action": "lock", "timestamp": time.time()})
        self.increment_state_revision()

    def unlock(self) -> None:
        self.is_locked = False
        self.set_status("UNLOCKED")
        self.access_log.append({"action": "unlock", "timestamp": time.time()})
        self.increment_state_revision()

    def fail_safe_unlock(self) -> None:
        """Emergency fail-safe: unlock all doors for evacuation."""
        self.is_locked = False
        self.fail_safe_unlocked = True
        self.set_status("FAIL_SAFE_UNLOCKED")
        self.access_log.append({"action": "fail_safe_unlock", "timestamp": time.time()})
        self.increment_state_revision()

    def reset_fail_safe(self) -> None:
        """Reset fail-safe mode after emergency is cleared."""
        self.fail_safe_unlocked = False
        self.set_status("UNLOCKED")
        self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "is_locked": self.is_locked,
            "fail_safe_unlocked": self.fail_safe_unlocked,
            "access_log_count": len(self.access_log),
        })
        return d


class SmokeDetector(HomeEntity):
    """Smoke/CO detector with warning and critical thresholds."""

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"

    def __init__(
        self,
        entity_id: str = "smoke_1",
        room_id: str = "room_1",
        smoke_threshold: float = 50.0,
        smoke_critical: float = 100.0,
        co_threshold: float = 35.0,
        co_critical: float = 100.0,
    ) -> None:
        super().__init__(entity_id, "smoke_detector", room_id, "NORMAL")
        self.smoke_level = 0.0
        self.co_level = 0.0
        self.smoke_threshold = smoke_threshold
        self.smoke_critical = smoke_critical
        self.co_threshold = co_threshold
        self.co_critical = co_critical
        self.state = self.NORMAL
        self.evacuation_triggered = False

    def update_levels(self, smoke: float, co: float) -> str:
        """Update smoke and CO levels. Returns new state."""
        self.smoke_level = smoke
        self.co_level = co
        if smoke >= self.smoke_critical or co >= self.co_critical:
            self.state = self.CRITICAL
            self.set_status("CRITICAL")
        elif smoke >= self.smoke_threshold or co >= self.co_threshold:
            self.state = self.WARNING
            self.set_status("WARNING")
        else:
            self.state = self.NORMAL
            self.set_status("NORMAL")
        self.increment_state_revision()
        return self.state

    def is_critical(self) -> bool:
        return self.state == self.CRITICAL

    def is_warning(self) -> bool:
        return self.state == self.WARNING

    def trigger_evacuation(self) -> None:
        self.evacuation_triggered = True
        self.set_status("EVACUATION")

    def reset(self) -> None:
        self.smoke_level = 0.0
        self.co_level = 0.0
        self.state = self.NORMAL
        self.evacuation_triggered = False
        self.set_status("NORMAL")
        self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "smoke_level": self.smoke_level,
            "co_level": self.co_level,
            "state": self.state,
            "evacuation_triggered": self.evacuation_triggered,
        })
        return d


class EnergyMonitor(HomeEntity):
    """Energy consumption monitor."""

    def __init__(
        self,
        entity_id: str = "energy_1",
        room_id: str = "whole_house",
    ) -> None:
        super().__init__(entity_id, "energy_monitor", room_id, "ACTIVE")
        self.power_usage_kw = 0.0
        self.daily_usage_kwh = 0.0
        self.peak_usage_kw = 0.0
        self.cost_estimate_eur = 0.0
        self.price_per_kwh = 0.25  # EUR per kWh

    def update_usage(self, power_kw: float) -> None:
        self.power_usage_kw = power_kw
        if power_kw > self.peak_usage_kw:
            self.peak_usage_kw = power_kw
        self.increment_state_revision()

    def add_daily_usage(self, kwh: float) -> None:
        self.daily_usage_kwh += kwh
        self.cost_estimate_eur = self.daily_usage_kwh * self.price_per_kwh
        self.increment_state_revision()

    def reset_daily(self) -> None:
        self.daily_usage_kwh = 0.0
        self.cost_estimate_eur = 0.0
        self.increment_state_revision()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "power_usage_kw": self.power_usage_kw,
            "daily_usage_kwh": self.daily_usage_kwh,
            "peak_usage_kw": self.peak_usage_kw,
            "cost_estimate_eur": self.cost_estimate_eur,
        })
        return d


class EvacuationController(HomeEntity):
    """Coordinates evacuation mode across all smart home devices."""

    def __init__(self, entity_id: str = "evacuation_1") -> None:
        super().__init__(entity_id, "evacuation_controller", "whole_house", "INACTIVE")
        self.is_active = False
        self.trigger_source: str = ""
        self.trigger_time: Optional[float] = None
        self.affected_rooms: List[str] = []

    def activate(self, source: str, rooms: List[str]) -> None:
        self.is_active = True
        self.trigger_source = source
        self.trigger_time = time.time()
        self.affected_rooms = list(rooms)
        self.set_status("ACTIVE")

    def deactivate(self) -> None:
        self.is_active = False
        self.trigger_source = ""
        self.trigger_time = None
        self.affected_rooms = []
        self.set_status("INACTIVE")

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "is_active": self.is_active,
            "trigger_source": self.trigger_source,
            "affected_rooms": list(self.affected_rooms),
        })
        return d
