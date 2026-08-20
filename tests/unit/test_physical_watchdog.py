"""
Unit tests for ORION Physical Watchdog system v3.
"""

import unittest
import time
import threading
import os
import sys
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.safety.physical_watchdog import (
    HardwareWatchdog,
    SoftwareWatchdog,
    WatchdogHierarchy,
)


class TestPhysicalWatchdog(unittest.TestCase):
    """Test physical watchdog system and hierarchy."""

    def test_hardware_watchdog_heartbeat_and_estop(self):
        """1. Hardware watchdog: heartbeat resets timer, no heartbeat triggers E-stop."""
        hw = HardwareWatchdog(timeout_ms=50.0)

        # Send heartbeats, verify no E-stop
        for _ in range(3):
            hw.heartbeat()
            time.sleep(0.01)
            self.assertFalse(hw.check_timeout())
            self.assertFalse(hw.is_triggered)
            self.assertFalse(hw.power_cutoff)

        # Stop heartbeats and wait for timeout
        time.sleep(0.06)
        self.assertTrue(hw.check_timeout())
        self.assertTrue(hw.is_triggered)
        self.assertTrue(hw.power_cutoff)

    def test_software_watchdog_thread_and_cascade(self):
        """2. Software watchdog: monitors thread, triggers cascade on timeout."""
        sw = SoftwareWatchdog(timeout_ms=50.0)
        sw.heartbeat()
        self.assertFalse(sw.is_triggered)

        time.sleep(0.06)
        self.assertTrue(sw.check_timeout())
        self.assertTrue(sw.is_triggered)
        self.assertTrue(sw.cascade_active)
        self.assertTrue(sw.alert_sent)

        # Test monitored thread crash
        def dying_thread_func():
            pass

        t = threading.Thread(target=dying_thread_func)
        t.start()
        t.join()

        sw2 = SoftwareWatchdog(timeout_ms=500.0, monitored_thread=t)
        sw2.heartbeat()
        self.assertTrue(sw2.check_timeout())
        self.assertTrue(sw2.is_triggered)

    def test_watchdog_independence(self):
        """3. Watchdog independence: software crash doesn't affect hardware watchdog."""
        hw = HardwareWatchdog(timeout_ms=50.0)
        sw = SoftwareWatchdog(timeout_ms=100.0)

        hw.heartbeat()
        sw.heartbeat()

        # Software watchdog crashes / triggers
        sw.trigger_cascade()
        self.assertTrue(sw.is_triggered)
        self.assertFalse(hw.is_triggered)

        # Hardware watchdog still operates and times out independently
        time.sleep(0.06)
        hw.check_timeout()
        self.assertTrue(hw.is_triggered)
        self.assertTrue(hw.power_cutoff)

    def test_watchdog_hierarchy_timing(self):
        """4. Watchdog hierarchy: hardware fires before software (hardware 200ms vs software 500ms)."""
        hierarchy = WatchdogHierarchy(hw_timeout_ms=50.0, sw_timeout_ms=120.0)
        hierarchy.heartbeat_all()

        time.sleep(0.07)
        status = hierarchy.check_all()

        self.assertTrue(status["hardware_triggered"])
        self.assertFalse(status["software_triggered"])

        time.sleep(0.06)
        status2 = hierarchy.check_all()
        self.assertTrue(status2["software_triggered"])

    def test_heartbeat_at_various_intervals(self):
        """5. Heartbeat at various intervals (fast, medium, slow)."""
        hw = HardwareWatchdog(timeout_ms=100.0)

        for interval in [0.01, 0.03, 0.05, 0.08]:
            hw.heartbeat()
            time.sleep(interval)
            self.assertFalse(hw.check_timeout())

        time.sleep(0.12)
        self.assertTrue(hw.check_timeout())

    def test_multiple_watchdog_instances(self):
        """6. Multiple watchdog instances operating independently."""
        hw1 = HardwareWatchdog(timeout_ms=30.0)
        hw2 = HardwareWatchdog(timeout_ms=100.0)

        hw1.heartbeat()
        hw2.heartbeat()

        time.sleep(0.05)
        self.assertTrue(hw1.check_timeout())
        self.assertFalse(hw2.check_timeout())

        time.sleep(0.06)
        self.assertTrue(hw2.check_timeout())

    def test_estop_action_callback(self):
        """7. E-stop action callback is invoked when E-stop triggers."""
        callback_called = []

        def on_estop():
            callback_called.append(True)

        hw = HardwareWatchdog(timeout_ms=30.0, on_estop=on_estop)
        hw.heartbeat()
        self.assertEqual(len(callback_called), 0)

        time.sleep(0.05)
        hw.check_timeout()
        self.assertTrue(hw.is_triggered)
        self.assertEqual(len(callback_called), 1)

    def test_recovery_after_watchdog_trigger(self):
        """8. Recovery after watchdog trigger."""
        hw = HardwareWatchdog(timeout_ms=30.0)
        hw.trigger_estop()

        self.assertTrue(hw.is_triggered)
        self.assertTrue(hw.power_cutoff)

        hw.reset()
        self.assertFalse(hw.is_triggered)
        self.assertFalse(hw.power_cutoff)

        hw.heartbeat()
        self.assertFalse(hw.check_timeout())

    def test_race_condition_heartbeat_just_before_timeout(self):
        """9. Race condition: heartbeat arrives just before timeout."""
        hw = HardwareWatchdog(timeout_ms=50.0)
        hw.heartbeat()

        time.sleep(0.04)
        hw.heartbeat()

        self.assertFalse(hw.check_timeout())
        self.assertFalse(hw.is_triggered)

    def test_concurrent_heartbeat_from_multiple_sources(self):
        """10. Concurrent heartbeat from multiple sources."""
        hw = HardwareWatchdog(timeout_ms=200.0)
        threads: List[threading.Thread] = []
        errors = []

        def sender(source_id: int):
            try:
                for _ in range(20):
                    hw.heartbeat(f"source_{source_id}")
                    time.sleep(0.002)
            except Exception as e:
                errors.append(e)

        for i in range(5):
            t = threading.Thread(target=sender, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertGreater(hw.heartbeat_count, 50)
        self.assertFalse(hw.is_triggered)


if __name__ == "__main__":
    unittest.main()
