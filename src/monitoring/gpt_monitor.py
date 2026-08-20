"""ORION GPT-4o Integration Monitor & Alert System (Phase 2 → Phase 3 bridge).

Addresses Luna's Phase 3 Condition #2: Monitoring and Alerts for GPT-4o integration.

Tracks GPT-4o API call health metrics, detects anomalies (latency spikes,
error bursts, quality degradation, fallback frequency), and raises alerts
that can be consumed by the Safety Enforcement Plane or surfaced to the
Supervisor/Founder.

Design principles:
- Zero coupling to the Cognitive Plane internals (subscribes via callbacks)
- Thread-safe metric collection
- Deterministic alert thresholds (no LLM needed to detect LLM problems)
- Alert log persisted to SQLite via StorageManager if available
- Apache 2.0 licensed, stdlib-only
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Severity levels for GPT integration alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertType(str, Enum):
    """Types of GPT-4o integration anomalies."""
    LATENCY_SPIKE = "latency_spiike"
    ERROR_BURST = "error_burst"
    FALLBACK_RATE_HIGH = "fallback_rate_high"
    EMPTY_RESPONSE = "empty_response"
    MALFORMED_JSON = "malformed_json"
    CONFIDENCE_DROP = "confidence_drop"
    RATE_LIMIT_HIT = "rate_limit_hit"
    TOKEN_USAGE_SPIKE = "token_usage_spike"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"


class CircuitState(str, Enum):
    """Circuit breaker states for GPT-4o calls."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Calls blocked, fallback only
    HALF_OPEN = "half_open" # Testing if GPT-4o recovered


@dataclass
class GPTCallRecord:
    """Record of a single GPT-4o API call."""
    timestamp: float
    duration_ms: float
    success: bool
    error: Optional[str] = None
    token_count: int = 0
    response_has_goals: bool = False
    response_has_proposals: bool = False
    confidence: float = 0.0
    used_fallback: bool = False


@dataclass
class GPTAlert:
    """An alert raised by the monitor."""
    id: str
    timestamp: float
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


class GPTIntegrationMonitor:
    """
    Monitors GPT-4o integration health and raises alerts on anomalies.

    Thread-safe. Designed to be called by the Cognitive Plane after each
    GPT-4o API call (success or failure) via record_call().

    Alert thresholds are configurable and deterministic — no LLM is used
    to detect LLM problems (per IND-5 independence requirement).
    """

    def __init__(
        self,
        window_size: int = 100,
        latency_warn_ms: float = 5000.0,
        latency_critical_ms: float = 15000.0,
        error_rate_warn: float = 0.15,
        error_rate_critical: float = 0.30,
        fallback_rate_warn: float = 0.20,
        fallback_rate_critical: float = 0.40,
        confidence_floor: float = 0.3,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout_s: float = 60.0,
        token_spike_multiplier: float = 3.0,
    ):
        """
        Initialize the GPT integration monitor.

        Args:
            window_size: Number of recent calls to keep in the sliding window.
            latency_warn_ms: Latency threshold for WARNING alert (ms).
            latency_critical_ms: Latency threshold for CRITICAL alert (ms).
            error_rate_warn: Error rate threshold for WARNING (0-1).
            error_rate_critical: Error rate threshold for CRITICAL (0-1).
            fallback_rate_warn: Fallback rate threshold for WARNING (0-1).
            fallback_rate_critical: Fallback rate threshold for CRITICAL (0-1).
            confidence_floor: Below this avg confidence, raise WARNING.
            circuit_failure_threshold: Consecutive failures before circuit opens.
            circuit_recovery_timeout_s: Seconds before circuit breaker tries half-open.
            token_spike_multiplier: Multiplier over avg token count for spike alert.
        """
        self._lock = threading.RLock()

        # Config
        self.window_size = window_size
        self.latency_warn_ms = latency_warn_ms
        self.latency_critical_ms = latency_critical_ms
        self.error_rate_warn = error_rate_warn
        self.error_rate_critical = error_rate_critical
        self.fallback_rate_warn = fallback_rate_warn
        self.fallback_rate_critical = fallback_rate_critical
        self.confidence_floor = confidence_floor
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_recovery_timeout_s = circuit_recovery_timeout_s
        self.token_spike_multiplier = token_spike_multiplier

        # State
        self._call_history: Deque[GPTCallRecord] = deque(maxlen=window_size)
        self._alerts: List[GPTAlert] = []
        self._alert_callbacks: List[Callable[[GPTAlert], None]] = []

        # Circuit breaker
        self._circuit_state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._circuit_opened_at: Optional[float] = None

        # Token tracking
        self._token_history: Deque[int] = deque(maxlen=window_size)

        # Alert deduplication
        self._last_alert_times: Dict[AlertType, float] = {}

    # ------------------------------------------------------------------
    # Circuit Breaker
    # ------------------------------------------------------------------

    @property
    def circuit_state(self) -> CircuitState:
        """Current circuit breaker state."""
        with self._lock:
            if self._circuit_state == CircuitState.OPEN:
                # Check if we should try half-open
                if self._circuit_opened_at is not None:
                    elapsed = time.time() - self._circuit_opened_at
                    if elapsed >= self.circuit_recovery_timeout_s:
                        self._circuit_state = CircuitState.HALF_OPEN
                        logger.info("GPT-4o circuit breaker entering HALF_OPEN state — testing recovery.")
            return self._circuit_state

    def should_call_gpt(self) -> bool:
        """Whether the Cognitive Plane should attempt a GPT-4o call."""
        state = self.circuit_state
        return state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    # ------------------------------------------------------------------
    # Call Recording
    # ------------------------------------------------------------------

    def record_call(
        self,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
        token_count: int = 0,
        response_has_goals: bool = False,
        response_has_proposals: bool = False,
        confidence: float = 0.0,
        used_fallback: bool = False,
    ) -> List[GPTAlert]:
        """
        Record a GPT-4o API call result. Returns any alerts raised.

        Called by CognitivePlane after each GPT-4o attempt (success or failure).
        """
        with self._lock:
            record = GPTCallRecord(
                timestamp=time.time(),
                duration_ms=duration_ms,
                success=success,
                error=error,
                token_count=token_count,
                response_has_goals=response_has_goals,
                response_has_proposals=response_has_proposals,
                confidence=confidence,
                used_fallback=used_fallback,
            )
            self._call_history.append(record)
            if token_count > 0:
                self._token_history.append(token_count)

            # Update circuit breaker
            if success:
                self._consecutive_failures = 0
                if self._circuit_state == CircuitState.HALF_OPEN:
                    self._circuit_state = CircuitState.CLOSED
                    logger.info("GPT-4o circuit breaker recovered → CLOSED.")
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.circuit_failure_threshold:
                    if self._circuit_state != CircuitState.OPEN:
                        self._circuit_state = CircuitState.OPEN
                        self._circuit_opened_at = time.time()
                        logger.critical(
                            f"GPT-4o circuit breaker OPENED after {self._consecutive_failures} consecutive failures."
                        )

            # Analyze for alerts
            alerts = self._analyze()

            return alerts

    # ------------------------------------------------------------------
    # Anomaly Detection (Deterministic)
    # ------------------------------------------------------------------

    def _analyze(self) -> List[GPTAlert]:
        """Analyze recent call history and raise alerts for anomalies."""
        alerts: List[GPTAlert] = []
        now = time.time()

        if len(self._call_history) < 3:
            return alerts  # Not enough data

        recent = list(self._call_history)
        window = recent[-self.window_size:]

        # --- Latency Check ---
        durations = [r.duration_ms for r in window if r.success]
        if durations:
            avg_latency = statistics.mean(durations)
            last_latency = durations[-1] if durations else 0

            if last_latency >= self.latency_critical_ms:
                alerts.append(self._make_alert(
                    AlertType.LATENCY_SPIKE, AlertSeverity.CRITICAL,
                    f"GPT-4o latency critical: {last_latency:.0f}ms (avg {avg_latency:.0f}ms)",
                    {"last_ms": last_latency, "avg_ms": avg_latency},
                    now,
                ))
            elif last_latency >= self.latency_warn_ms:
                alerts.append(self._make_alert(
                    AlertType.LATENCY_SPIKE, AlertSeverity.WARNING,
                    f"GPT-4o latency high: {last_latency:.0f}ms (avg {avg_latency:.0f}ms)",
                    {"last_ms": last_latency, "avg_ms": avg_latency},
                    now,
                ))

        # --- Error Rate Check ---
        total = len(window)
        failures = sum(1 for r in window if not r.success)
        error_rate = failures / total if total > 0 else 0

        if error_rate >= self.error_rate_critical:
            alerts.append(self._make_alert(
                AlertType.ERROR_BURST, AlertSeverity.CRITICAL,
                f"GPT-4o error rate critical: {error_rate:.0%} ({failures}/{total} calls)",
                {"error_rate": error_rate, "failures": failures, "total": total},
                now,
            ))
        elif error_rate >= self.error_rate_warn:
            alerts.append(self._make_alert(
                AlertType.ERROR_BURST, AlertSeverity.WARNING,
                f"GPT-4o error rate elevated: {error_rate:.0%} ({failures}/{total} calls)",
                {"error_rate": error_rate, "failures": failures, "total": total},
                now,
            ))

        # --- Fallback Rate Check ---
        fallbacks = sum(1 for r in window if r.used_fallback)
        fallback_rate = fallbacks / total if total > 0 else 0

        if fallback_rate >= self.fallback_rate_critical:
            alerts.append(self._make_alert(
                AlertType.FALLBACK_RATE_HIGH, AlertSeverity.CRITICAL,
                f"Fallback rate critical: {fallback_rate:.0%} ({fallbacks}/{total} calls)",
                {"fallback_rate": fallback_rate, "fallbacks": fallbacks, "total": total},
                now,
            ))
        elif fallback_rate >= self.fallback_rate_warn:
            alerts.append(self._make_alert(
                AlertType.FALLBACK_RATE_HIGH, AlertSeverity.WARNING,
                f"Fallback rate elevated: {fallback_rate:.0%} ({fallbacks}/{total} calls)",
                {"fallback_rate": fallback_rate, "fallbacks": fallbacks, "total": total},
                now,
            ))

        # --- Empty Response Check ---
        empty_count = sum(1 for r in window if r.success and not r.response_has_goals and not r.response_has_proposals)
        if empty_count >= 3:
            alerts.append(self._make_alert(
                AlertType.EMPTY_RESPONSE, AlertSeverity.WARNING,
                f"GPT-4o returned empty responses {empty_count} times in recent window",
                {"empty_count": empty_count, "window": total},
                now,
            ))

        # --- Confidence Drop Check ---
        confidences = [r.confidence for r in window if r.success and r.confidence > 0]
        if len(confidences) >= 5:
            avg_conf = statistics.mean(confidences)
            if avg_conf < self.confidence_floor:
                alerts.append(self._make_alert(
                    AlertType.CONFIDENCE_DROP, AlertSeverity.WARNING,
                    f"Average GPT-4o confidence dropped to {avg_conf:.2f} (floor: {self.confidence_floor})",
                    {"avg_confidence": avg_conf, "floor": self.confidence_floor},
                    now,
                ))

        # --- Token Usage Spike ---
        if len(self._token_history) >= 10:
            recent_tokens = list(self._token_history)
            avg_tokens = statistics.mean(recent_tokens[:-1])
            last_tokens = recent_tokens[-1]
            if avg_tokens > 0 and last_tokens > avg_tokens * self.token_spike_multiplier:
                alerts.append(self._make_alert(
                    AlertType.TOKEN_USAGE_SPIKE, AlertSeverity.WARNING,
                    f"Token usage spike: {last_tokens} tokens (avg {avg_tokens:.0f})",
                    {"last_tokens": last_tokens, "avg_tokens": avg_tokens},
                    now,
                ))

        # --- Circuit Breaker Alert ---
        if self._circuit_state == CircuitState.OPEN:
            alerts.append(self._make_alert(
                AlertType.CIRCUIT_BREAKER_OPEN, AlertSeverity.EMERGENCY,
                f"GPT-4o circuit breaker OPEN — {self._consecutive_failures} consecutive failures. "
                f"Falling back to deterministic planner.",
                {
                    "consecutive_failures": self._consecutive_failures,
                    "circuit_state": self._circuit_state.value,
                },
                now,
            ))

        # Store and dispatch alerts
        for alert in alerts:
            self._alerts.append(alert)
            self._dispatch(alert)

        return alerts

    def _make_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        metrics: Dict[str, Any],
        timestamp: float,
    ) -> GPTAlert:
        """Create an alert with deduplication (avoid spamming same alert type)."""
        import uuid
        # Deduplicate: don't raise same alert type more than once per 30s
        last = self._last_alert_times.get(alert_type, 0)
        if timestamp - last < 30.0 and last > 0:
            # Return a no-op alert that won't be stored
            return GPTAlert(
                id=str(uuid.uuid4()),
                timestamp=timestamp,
                alert_type=alert_type,
                severity=severity,
                message=message,
                metrics=metrics,
                acknowledged=True,  # Auto-ack duplicated alerts
            )
        self._last_alert_times[alert_type] = timestamp
        return GPTAlert(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            alert_type=alert_type,
            severity=severity,
            message=message,
            metrics=metrics,
        )

    def _dispatch(self, alert: GPTAlert) -> None:
        """Dispatch alert to registered callbacks."""
        if alert.acknowledged:
            return  # Deduplicated, skip dispatch
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.warning(f"Alert callback failed: {e}")

    # ------------------------------------------------------------------
    # Alert Management
    # ------------------------------------------------------------------

    def register_alert_callback(self, callback: Callable[[GPTAlert], None]) -> None:
        """Register a callback to be called when an alert is raised."""
        with self._lock:
            self._alert_callbacks.append(callback)

    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        unacknowledged_only: bool = False,
    ) -> List[GPTAlert]:
        """Retrieve alerts, optionally filtered."""
        with self._lock:
            result = self._alerts
            if severity:
                result = [a for a in result if a.severity == severity]
            if unacknowledged_only:
                result = [a for a in result if not a.acknowledged]
            return list(result)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert by ID."""
        with self._lock:
            for alert in self._alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    return True
            return False

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        with self._lock:
            self._alerts.clear()
            self._last_alert_times.clear()

    # ------------------------------------------------------------------
    # Health Summary
    # ------------------------------------------------------------------

    def get_health_summary(self) -> Dict[str, Any]:
        """Get a health summary of the GPT-4o integration."""
        with self._lock:
            recent = list(self._call_history)
            total = len(recent)
            if total == 0:
                return {
                    "status": "no_data",
                    "circuit_state": self.circuit_state.value,
                    "total_calls": 0,
                }

            successes = sum(1 for r in recent if r.success)
            fallbacks = sum(1 for r in recent if r.used_fallback)
            durations = [r.duration_ms for r in recent if r.success]
            confidences = [r.confidence for r in recent if r.success and r.confidence > 0]

            unack_alerts = sum(1 for a in self._alerts if not a.acknowledged)

            if self._circuit_state == CircuitState.OPEN:
                status = "degraded"
            elif successes / total < self.error_rate_warn:
                status = "warning"
            else:
                status = "healthy"

            return {
                "status": status,
                "circuit_state": self.circuit_state.value,
                "total_calls": total,
                "success_rate": successes / total,
                "fallback_rate": fallbacks / total if total else 0,
                "avg_latency_ms": statistics.mean(durations) if durations else 0,
                "p95_latency_ms": self._percentile(durations, 95) if durations else 0,
                "avg_confidence": statistics.mean(confidences) if confidences else 0,
                "total_tokens": sum(r.token_count for r in recent),
                "unacknowledged_alerts": unack_alerts,
            }

    @staticmethod
    def _percentile(data: List[float], pct: float) -> float:
        """Calculate percentile of a list."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * pct / 100)
        idx = min(idx, len(sorted_data) - 1)
        return sorted_data[idx]

    # ------------------------------------------------------------------
    # Reset (for testing)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all state (for testing)."""
        with self._lock:
            self._call_history.clear()
            self._alerts.clear()
            self._token_history.clear()
            self._last_alert_times.clear()
            self._circuit_state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._circuit_opened_at = None
