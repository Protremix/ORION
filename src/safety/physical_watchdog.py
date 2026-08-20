"""
Safety Layer v3 — Physical Watchdog System for ORION Physical Intelligence OS.

This module implements a dual watchdog hierarchy for hardware power cutoff
and software defense-in-depth emergency cascades.

Watchdog Hierarchy:
- Level 1: Hardware Watchdog (200ms) -> Physical E-stop -> Power cutoff
- Level 2: Software Watchdog (500ms) -> Emergency cascade -> Safe state
- Level 3: Safety Enforcement Plane -> CBF filters -> Actuator commands
- Level 4: Cognitive Plane -> Reasoning -> Planning
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class HardwareWatchdog:
    """
    Simulated Hardware Watchdog.

    Timeout: 200ms (10x CBF loop time)
    Reset: heartbeat from Safety Enforcement Plane every 100ms
    Action on timeout: hardware E-stop (power cutoff to all actuators)
    Independent of software (runs in dedicated background thread/process).
    """

    def __init__(
        self,
        timeout_ms: float = 200.0,
        heartbeat_interval_ms: float = 100.0,
        on_estop: Optional[Callable[[], None]] = None,
    ):
        self.timeout_ms = timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.on_estop = on_estop

        self._last_heartbeat = time.time()
        self._triggered = False
        self._power_cutoff = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._heartbeat_count = 0

    @property
    def is_triggered(self) -> bool:
        with self._lock:
            return self._triggered

    @property
    def power_cutoff(self) -> bool:
        with self._lock:
            return self._power_cutoff

    @property
    def last_heartbeat(self) -> float:
        with self._lock:
            return self._last_heartbeat

    @property
    def heartbeat_count(self) -> int:
        with self._lock:
            return self._heartbeat_count

    def heartbeat(self, source: str = "safety_enforcement_plane") -> None:
        """Reset watchdog timer on heartbeat."""
        with self._lock:
            if not self._power_cutoff:
                self._last_heartbeat = time.time()
                self._heartbeat_count += 1

    def check_timeout(self, current_time: Optional[float] = None) -> bool:
        """Check if hardware watchdog has timed out."""
        now = current_time if current_time is not None else time.time()
        with self._lock:
            if self._triggered:
                return True
            elapsed_ms = (now - self._last_heartbeat) * 1000.0
            if elapsed_ms > self.timeout_ms:
                self._trigger_estop_locked()
                return True
            return False

    def _trigger_estop_locked(self) -> None:
        self._triggered = True
        self._power_cutoff = True
        logger.critical("HARDWARE WATCHDOG TIMEOUT: Hardware E-stop triggered! Power cutoff to all actuators.")
        if self.on_estop is not None:
            try:
                self.on_estop()
            except Exception as e:
                logger.error(f"Error executing hardware E-stop callback: {e}")

    def trigger_estop(self) -> None:
        """Manually trigger hardware E-stop."""
        with self._lock:
            self._trigger_estop_locked()

    def reset(self) -> None:
        """Reset watchdog state after physical recovery."""
        with self._lock:
            self._triggered = False
            self._power_cutoff = False
            self._last_heartbeat = time.time()

    def start(self, poll_interval_ms: float = 10.0) -> None:
        """Start background thread monitoring."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._last_heartbeat = time.time()

        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(poll_interval_ms / 1000.0,),
            daemon=True,
            name="HardwareWatchdogThread",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background thread monitoring."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def _monitor_loop(self, poll_interval_sec: float) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
            self.check_timeout()
            time.sleep(poll_interval_sec)


class SoftwareWatchdog:
    """
    Software Watchdog (Defense in Depth).

    Monitors Safety Enforcement Plane thread.
    Timeout: 500ms
    Action: software emergency cascade + alert
    Does NOT replace hardware watchdog.
    """

    def __init__(
        self,
        timeout_ms: float = 500.0,
        monitored_thread: Optional[threading.Thread] = None,
        on_cascade: Optional[Callable[[], None]] = None,
    ):
        self.timeout_ms = timeout_ms
        self.monitored_thread = monitored_thread
        self.on_cascade = on_cascade

        self._last_heartbeat = time.time()
        self._triggered = False
        self._cascade_active = False
        self._alert_sent = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._heartbeat_count = 0

    @property
    def is_triggered(self) -> bool:
        with self._lock:
            return self._triggered

    @property
    def cascade_active(self) -> bool:
        with self._lock:
            return self._cascade_active

    @property
    def alert_sent(self) -> bool:
        with self._lock:
            return self._alert_sent

    @property
    def last_heartbeat(self) -> float:
        with self._lock:
            return self._last_heartbeat

    @property
    def heartbeat_count(self) -> int:
        with self._lock:
            return self._heartbeat_count

    def heartbeat(self, source: str = "safety_enforcement_plane") -> None:
        """Reset software watchdog timer on heartbeat."""
        with self._lock:
            self._last_heartbeat = time.time()
            self._heartbeat_count += 1

    def check_timeout(self, current_time: Optional[float] = None) -> bool:
        """Check if software watchdog timed out or monitored thread died."""
        now = current_time if current_time is not None else time.time()
        with self._lock:
            if self._triggered:
                return True

            elapsed_ms = (now - self._last_heartbeat) * 1000.0
            thread_dead = (
                self.monitored_thread is not None
                and not self.monitored_thread.is_alive()
            )

            if elapsed_ms > self.timeout_ms or thread_dead:
                self._trigger_cascade_locked()
                return True
            return False

    def _trigger_cascade_locked(self) -> None:
        self._triggered = True
        self._cascade_active = True
        self._alert_sent = True
        logger.warning("SOFTWARE WATCHDOG TIMEOUT: Software emergency cascade triggered!")
        if self.on_cascade is not None:
            try:
                self.on_cascade()
            except Exception as e:
                logger.error(f"Error executing software cascade callback: {e}")

    def trigger_cascade(self) -> None:
        """Manually trigger software cascade."""
        with self._lock:
            self._trigger_cascade_locked()

    def reset(self) -> None:
        """Reset software watchdog state."""
        with self._lock:
            self._triggered = False
            self._cascade_active = False
            self._alert_sent = False
            self._last_heartbeat = time.time()

    def start(self, poll_interval_ms: float = 20.0) -> None:
        """Start background monitoring thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._last_heartbeat = time.time()

        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(poll_interval_ms / 1000.0,),
            daemon=True,
            name="SoftwareWatchdogThread",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background monitoring thread."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def _monitor_loop(self, poll_interval_sec: float) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
            self.check_timeout()
            time.sleep(poll_interval_sec)


class WatchdogHierarchy:
    """
    Watchdog Hierarchy integrating hardware and software watchdogs.

    Hierarchy Levels:
    Level 1: Hardware Watchdog (200ms) -> Physical E-stop -> Power cutoff
    Level 2: Software Watchdog (500ms) -> Emergency cascade -> Safe state
    Level 3: Safety Enforcement Plane -> CBF filters -> Actuator commands
    Level 4: Cognitive Plane -> Reasoning -> Planning
    """

    def __init__(
        self,
        hw_timeout_ms: float = 200.0,
        sw_timeout_ms: float = 500.0,
        monitored_thread: Optional[threading.Thread] = None,
        on_hw_estop: Optional[Callable[[], None]] = None,
        on_sw_cascade: Optional[Callable[[], None]] = None,
    ):
        self.hardware_watchdog = HardwareWatchdog(
            timeout_ms=hw_timeout_ms,
            on_estop=on_hw_estop,
        )
        self.software_watchdog = SoftwareWatchdog(
            timeout_ms=sw_timeout_ms,
            monitored_thread=monitored_thread,
            on_cascade=on_sw_cascade,
        )

    def start(self) -> None:
        """Start both watchdogs."""
        self.hardware_watchdog.start()
        self.software_watchdog.start()

    def stop(self) -> None:
        """Stop both watchdogs."""
        self.hardware_watchdog.stop()
        self.software_watchdog.stop()

    def heartbeat_hardware(self, source: str = "safety_enforcement_plane") -> None:
        """Send heartbeat to hardware watchdog."""
        self.hardware_watchdog.heartbeat(source)

    def heartbeat_software(self, source: str = "safety_enforcement_plane") -> None:
        """Send heartbeat to software watchdog."""
        self.software_watchdog.heartbeat(source)

    def heartbeat_all(self, source: str = "safety_enforcement_plane") -> None:
        """Send heartbeat to both watchdogs."""
        self.hardware_watchdog.heartbeat(source)
        self.software_watchdog.heartbeat(source)

    def heartbeat(self, source: str = "safety_enforcement_plane") -> None:
        """Alias for heartbeat_all."""
        self.heartbeat_all(source)

    def check_all(self, current_time: Optional[float] = None) -> Dict[str, bool]:
        """Check status of both watchdogs."""
        hw_triggered = self.hardware_watchdog.check_timeout(current_time)
        sw_triggered = self.software_watchdog.check_timeout(current_time)
        return {
            "hardware_triggered": hw_triggered,
            "software_triggered": sw_triggered,
        }

    def reset(self) -> None:
        """Reset both watchdogs."""
        self.hardware_watchdog.reset()
        self.software_watchdog.reset()

    def get_status(self) -> Dict[str, Any]:
        """Return watchdog hierarchy status."""
        return {
            "hierarchy_levels": {
                "level_1": "Hardware Watchdog (200ms) -> Physical E-stop -> Power cutoff",
                "level_2": "Software Watchdog (500ms) -> Emergency cascade -> Safe state",
                "level_3": "Safety Enforcement Plane -> CBF filters -> Actuator commands",
                "level_4": "Cognitive Plane -> Reasoning -> Planning",
            },
            "hardware": {
                "timeout_ms": self.hardware_watchdog.timeout_ms,
                "triggered": self.hardware_watchdog.is_triggered,
                "power_cutoff": self.hardware_watchdog.power_cutoff,
                "heartbeat_count": self.hardware_watchdog.heartbeat_count,
            },
            "software": {
                "timeout_ms": self.software_watchdog.timeout_ms,
                "triggered": self.software_watchdog.is_triggered,
                "cascade_active": self.software_watchdog.cascade_active,
                "alert_sent": self.software_watchdog.alert_sent,
                "heartbeat_count": self.software_watchdog.heartbeat_count,
            },
            "system_safe": not self.hardware_watchdog.is_triggered and not self.software_watchdog.is_triggered,
        }
