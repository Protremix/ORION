"""Tests for the GPT-4o Integration Monitor & Alert System.

Tests the monitoring/alerting system that addresses Luna's Phase 3 Condition #2:
Monitoring and Alerts for GPT-4o integration anomalies.
"""

import time
import unittest

from src.monitoring.gpt_monitor import (
    AlertSeverity,
    AlertType,
    CircuitState,
    GPTAlert,
    GPTIntegrationMonitor,
)


class TestGPTIntegrationMonitor(unittest.TestCase):
    """Test the GPT-4o integration monitoring and alerting system."""

    def setUp(self):
        self.monitor = GPTIntegrationMonitor(
            window_size=20,
            latency_warn_ms=100.0,
            latency_critical_ms=500.0,
            error_rate_warn=0.15,
            error_rate_critical=0.30,
            fallback_rate_warn=0.20,
            fallback_rate_critical=0.40,
            confidence_floor=0.3,
            circuit_failure_threshold=3,
            circuit_recovery_timeout_s=0.5,
            token_spike_multiplier=3.0,
        )

    def test_initial_state(self):
        """Monitor starts in healthy state with no data."""
        summary = self.monitor.get_health_summary()
        self.assertEqual(summary["status"], "no_data")
        self.assertEqual(summary["circuit_state"], "closed")
        self.assertEqual(self.monitor.circuit_state, CircuitState.CLOSED)

    def test_record_successful_call(self):
        """Recording a successful call updates health summary."""
        self.monitor.record_call(
            duration_ms=50.0,
            success=True,
            response_has_goals=True,
            response_has_proposals=True,
            confidence=0.9,
        )
        summary = self.monitor.get_health_summary()
        self.assertEqual(summary["status"], "healthy")
        self.assertEqual(summary["total_calls"], 1)
        self.assertEqual(summary["success_rate"], 1.0)

    def test_latency_spike_alert(self):
        """High latency triggers WARNING or CRITICAL alert."""
        # Record some normal calls first
        for _ in range(5):
            self.monitor.record_call(duration_ms=20.0, success=True, confidence=0.9)

        # Record a latency spike
        alerts = self.monitor.record_call(
            duration_ms=200.0,  # Above warn threshold (100ms)
            success=True,
            confidence=0.9,
        )

        latency_alerts = [a for a in alerts if a.alert_type == AlertType.LATENCY_SPIKE]
        self.assertTrue(len(latency_alerts) > 0, "Should raise latency spike alert")
        self.assertGreaterEqual(latency_alerts[0].severity.value, "warning")

    def test_latency_critical_alert(self):
        """Critical latency triggers CRITICAL alert."""
        for _ in range(3):
            self.monitor.record_call(duration_ms=10.0, success=True, confidence=0.9)

        alerts = self.monitor.record_call(
            duration_ms=600.0,  # Above critical threshold (500ms)
            success=True,
            confidence=0.9,
        )

        latency_alerts = [a for a in alerts if a.alert_type == AlertType.LATENCY_SPIKE]
        self.assertTrue(len(latency_alerts) > 0)
        self.assertEqual(latency_alerts[0].severity, AlertSeverity.CRITICAL)

    def test_error_rate_alert(self):
        """High error rate triggers error burst alert."""
        # Record 10 calls with 5 failures = 50% error rate (above critical 30%)
        for i in range(10):
            self.monitor.record_call(
                duration_ms=50.0,
                success=(i % 2 == 0),  # Alternating success/failure
                error="simulated_error" if i % 2 else None,
                confidence=0.9,
            )

        alerts = self.monitor.get_alerts()
        error_alerts = [a for a in alerts if a.alert_type == AlertType.ERROR_BURST]
        self.assertTrue(len(error_alerts) > 0, "Should raise error burst alert")
        self.assertEqual(error_alerts[-1].severity, AlertSeverity.CRITICAL)

    def test_fallback_rate_alert(self):
        """High fallback rate triggers fallback rate alert."""
        for i in range(10):
            self.monitor.record_call(
                duration_ms=50.0,
                success=True,
                used_fallback=(i < 5),  # 50% fallback rate (above critical 40%)
                confidence=0.9,
            )

        alerts = self.monitor.get_alerts()
        fallback_alerts = [a for a in alerts if a.alert_type == AlertType.FALLBACK_RATE_HIGH]
        self.assertTrue(len(fallback_alerts) > 0, "Should raise fallback rate alert")

    def test_confidence_drop_alert(self):
        """Low average confidence triggers confidence drop alert."""
        for _ in range(5):
            self.monitor.record_call(
                duration_ms=50.0,
                success=True,
                confidence=0.1,  # Below floor of 0.3
            )

        alerts = self.monitor.get_alerts()
        conf_alerts = [a for a in alerts if a.alert_type == AlertType.CONFIDENCE_DROP]
        self.assertTrue(len(conf_alerts) > 0, "Should raise confidence drop alert")

    def test_circuit_breaker_opens_on_consecutive_failures(self):
        """Circuit breaker opens after threshold consecutive failures."""
        self.assertEqual(self.monitor.circuit_state, CircuitState.CLOSED)

        # Record 3 consecutive failures (threshold = 3)
        for _ in range(3):
            self.monitor.record_call(
                duration_ms=0,
                success=False,
                error="timeout",
            )

        self.assertEqual(self.monitor.circuit_state, CircuitState.OPEN)
        self.assertFalse(self.monitor.should_call_gpt())

        # Verify circuit breaker alert was raised
        alerts = self.monitor.get_alerts()
        cb_alerts = [a for a in alerts if a.alert_type == AlertType.CIRCUIT_BREAKER_OPEN]
        self.assertTrue(len(cb_alerts) > 0)
        self.assertEqual(cb_alerts[-1].severity, AlertSeverity.EMERGENCY)

    def test_circuit_breaker_recovers(self):
        """Circuit breaker transitions to half-open after timeout, then closes on success."""
        # Open the circuit
        for _ in range(3):
            self.monitor.record_call(duration_ms=0, success=False, error="timeout")

        self.assertEqual(self.monitor.circuit_state, CircuitState.OPEN)

        # Wait for recovery timeout (0.5s in setUp)
        time.sleep(0.6)

        # Should now be half-open
        self.assertEqual(self.monitor.circuit_state, CircuitState.HALF_OPEN)
        self.assertTrue(self.monitor.should_call_gpt())

        # Record a successful call → should close circuit
        self.monitor.record_call(duration_ms=50.0, success=True, confidence=0.9)
        self.assertEqual(self.monitor.circuit_state, CircuitState.CLOSED)

    def test_alert_deduplication(self):
        """Same alert type is not raised more than once per 30 seconds."""
        for _ in range(3):
            self.monitor.record_call(duration_ms=20.0, success=True, confidence=0.9)

        # First latency spike
        alerts1 = self.monitor.record_call(duration_ms=200.0, success=True, confidence=0.9)
        latency1 = [a for a in alerts1 if a.alert_type == AlertType.LATENCY_SPIKE]
        self.assertTrue(len(latency1) > 0)

        # Second latency spike immediately after — should be deduplicated
        alerts2 = self.monitor.record_call(duration_ms=200.0, success=True, confidence=0.9)
        latency2 = [a for a in alerts2 if a.alert_type == AlertType.LATENCY_SPIKE and not a.acknowledged]
        self.assertEqual(len(latency2), 0, "Duplicate alert should be auto-acknowledged (suppressed)")

    def test_alert_callback(self):
        """Registered callback is called when alert is raised."""
        received = []
        self.monitor.register_alert_callback(lambda alert: received.append(alert))

        for _ in range(3):
            self.monitor.record_call(duration_ms=20.0, success=True, confidence=0.9)

        self.monitor.record_call(duration_ms=600.0, success=True, confidence=0.9)

        self.assertTrue(len(received) > 0, "Callback should receive alerts")
        self.assertIsInstance(received[0], GPTAlert)

    def test_alert_acknowledgment(self):
        """Alerts can be acknowledged by ID."""
        for _ in range(3):
            self.monitor.record_call(duration_ms=20.0, success=True, confidence=0.9,
                                     response_has_goals=True, response_has_proposals=True)

        alerts = self.monitor.record_call(duration_ms=600.0, success=True, confidence=0.9,
                                           response_has_goals=True, response_has_proposals=True)
        unack = self.monitor.get_alerts(unacknowledged_only=True)
        self.assertTrue(len(unack) > 0)

        result = self.monitor.acknowledge_alert(unack[0].id)
        self.assertTrue(result)

        unack_after = self.monitor.get_alerts(unacknowledged_only=True)
        self.assertEqual(len(unack_after), 0)

    def test_health_summary_degraded(self):
        """Health summary shows degraded when circuit is open."""
        for _ in range(3):
            self.monitor.record_call(duration_ms=0, success=False, error="error")

        summary = self.monitor.get_health_summary()
        self.assertEqual(summary["status"], "degraded")
        self.assertEqual(summary["circuit_state"], "open")

    def test_empty_response_alert(self):
        """Multiple empty responses trigger empty response alert."""
        for _ in range(3):
            self.monitor.record_call(
                duration_ms=50.0,
                success=True,
                response_has_goals=False,
                response_has_proposals=False,
                confidence=0.0,
            )

        alerts = self.monitor.get_alerts()
        empty_alerts = [a for a in alerts if a.alert_type == AlertType.EMPTY_RESPONSE]
        self.assertTrue(len(empty_alerts) > 0, "Should raise empty response alert")

    def test_token_spike_alert(self):
        """Token usage spike triggers token spike alert."""
        # Record 10 normal token counts
        for _ in range(10):
            self.monitor.record_call(
                duration_ms=50.0,
                success=True,
                token_count=100,
                confidence=0.9,
            )

        # Record a spike (100 * 3.0 = 300, we send 500)
        alerts = self.monitor.record_call(
            duration_ms=50.0,
            success=True,
            token_count=500,
            confidence=0.9,
        )

        token_alerts = [a for a in alerts if a.alert_type == AlertType.TOKEN_USAGE_SPIKE]
        self.assertTrue(len(token_alerts) > 0, "Should raise token spike alert")

    def test_reset(self):
        """Reset clears all state."""
        for _ in range(5):
            self.monitor.record_call(duration_ms=50.0, success=True, confidence=0.9)

        self.monitor.record_call(duration_ms=600.0, success=True, confidence=0.9)

        self.assertTrue(len(self.monitor.get_alerts()) > 0)
        self.assertTrue(self.monitor.get_health_summary()["total_calls"] > 0)

        self.monitor.reset()

        self.assertEqual(len(self.monitor.get_alerts()), 0)
        self.assertEqual(self.monitor.get_health_summary()["total_calls"], 0)
        self.assertEqual(self.monitor.circuit_state, CircuitState.CLOSED)


if __name__ == "__main__":
    unittest.main()
