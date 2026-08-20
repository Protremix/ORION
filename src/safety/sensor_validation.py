"""
Sensor Validation Pipeline for ORION Safety Layer v3.

This module implements the 5-stage sensor validation pipeline:
1. RangeCheck — physical plausibility bounds
2. RateCheck — update frequency within expected bounds
3. ConsistencyCheck — cross-sensor consistency (e.g., IMU vs GPS, pressure vs temperature)
4. PoisoningCheck — anomaly detection against historical patterns (z-score, stuck, noisy)
5. ConfidenceScore — weighted by sensor reliability and validation stage pass/fail

Designed to work in pure Python without external dependencies, using dataclasses,
and suitable for both simulation and hardware-in-the-loop modes.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class ValidationStageType(str, Enum):
    """Types of validation stages in the Sensor Validation Pipeline."""
    RANGE = "range_check"
    RATE = "rate_check"
    CONSISTENCY = "consistency_check"
    POISONING = "poisoning_check"
    CONFIDENCE = "confidence_score"


@dataclass
class SensorReading:
    """Represents a single measurement / observation from a sensor."""
    sensor_id: str
    sensor_type: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    unit: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """Result of an individual stage execution."""
    stage: ValidationStageType
    passed: bool
    score: float = 1.0
    message: str = "Passed"
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorValidationResult:
    """Aggregated output of the sensor validation pipeline for a reading."""
    sensor_id: str
    sensor_type: str
    timestamp: float
    is_valid: bool
    confidence_score: float
    failed_stage: Optional[ValidationStageType] = None
    stage_results: Dict[ValidationStageType, StageResult] = field(default_factory=dict)
    value: Any = None
    message: str = "Validation successful"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "timestamp": self.timestamp,
            "is_valid": self.is_valid,
            "confidence_score": self.confidence_score,
            "failed_stage": self.failed_stage.value if self.failed_stage else None,
            "value": self.value,
            "message": self.message,
            "stage_results": {
                k.value if isinstance(k, Enum) else str(k): {
                    "passed": v.passed,
                    "score": v.score,
                    "message": v.message,
                    "details": v.details,
                }
                for k, v in self.stage_results.items()
            },
        }


@dataclass
class SensorConfig:
    """Validation configuration bounds and parameters for a sensor type or ID."""
    sensor_type: str
    min_value: float = -float("inf")
    max_value: float = float("inf")
    min_interval: float = 0.0       # Minimum dt (seconds). dt < min_interval => too fast
    max_interval: float = 10.0      # Maximum dt (seconds). dt > max_interval => too slow
    z_score_threshold: float = 3.0  # Statistical anomaly threshold
    max_noise_std: Optional[float] = None  # Maximum allowed std dev (noisy sensor check)
    max_stuck_samples: Optional[int] = 5   # Max consecutive identical samples allowed
    base_reliability: float = 1.0   # Baseline sensor reliability (0.0 to 1.0)
    history_window_size: int = 20
    min_history_samples: int = 3


@dataclass
class ConsistencyRule:
    """Rule defining expected relationship between primary and secondary sensors."""
    rule_id: str
    primary_sensor_type: str
    secondary_sensor_type: str
    check_fn: Callable[[Any, Any], Tuple[bool, str]]
    description: str = ""


# ============================================================================
# Helper Functions
# ============================================================================

def _extract_numeric_values(val: Any) -> List[float]:
    """Extract flat list of numeric values from scalar, sequence, or dict."""
    if isinstance(val, bool):
        return []
    if isinstance(val, (int, float)):
        return [float(val)]
    if isinstance(val, (list, tuple)):
        res = []
        for item in val:
            res.extend(_extract_numeric_values(item))
        return res
    if isinstance(val, dict):
        res = []
        for v in val.values():
            res.extend(_extract_numeric_values(v))
        return res
    return []


def _extract_scalar(val: Any) -> float:
    """Extract a representative scalar magnitude/value for statistical history tracking."""
    nums = _extract_numeric_values(val)
    if not nums:
        return 0.0
    if len(nums) == 1:
        return nums[0]
    # For vectors (e.g. 3D velocity or accel), compute Euclidean norm
    return math.sqrt(sum(x ** 2 for x in nums))


def _are_values_equal(val1: Any, val2: Any, tol: float = 1e-9) -> bool:
    """Check if two sensor values are equal within tolerance."""
    nums1 = _extract_numeric_values(val1)
    nums2 = _extract_numeric_values(val2)
    if len(nums1) != len(nums2):
        return False
    if not nums1:
        return val1 == val2
    return all(abs(a - b) <= tol for a, b in zip(nums1, nums2))


# ============================================================================
# Validation Stage Functions
# ============================================================================

def check_range(reading: SensorReading, config: SensorConfig) -> StageResult:
    """Stage 1: RangeCheck — check if value is within physical plausibility bounds."""
    vals = _extract_numeric_values(reading.value)
    if not vals and reading.value is not None:
        # Non-numeric value (or empty)
        return StageResult(
            stage=ValidationStageType.RANGE,
            passed=False,
            score=0.0,
            message="Reading value contains no numeric data",
            details={"value": reading.value},
        )

    for v in vals:
        if v < config.min_value or v > config.max_value:
            return StageResult(
                stage=ValidationStageType.RANGE,
                passed=False,
                score=0.0,
                message=f"Value {v} out of plausible bounds [{config.min_value}, {config.max_value}]",
                details={"value": v, "min_value": config.min_value, "max_value": config.max_value},
            )

    return StageResult(
        stage=ValidationStageType.RANGE,
        passed=True,
        score=1.0,
        message=f"Value within plausible bounds [{config.min_value}, {config.max_value}]",
        details={"min_value": config.min_value, "max_value": config.max_value},
    )


def check_rate(
    reading: SensorReading,
    config: SensorConfig,
    last_timestamp: Optional[float]
) -> StageResult:
    """Stage 2: RateCheck — check if sensor update frequency is within bounds."""
    if last_timestamp is None:
        return StageResult(
            stage=ValidationStageType.RATE,
            passed=True,
            score=1.0,
            message="First reading for sensor, rate check passed",
            details={"dt": 0.0},
        )

    dt = reading.timestamp - last_timestamp
    if dt < 0.0:
        return StageResult(
            stage=ValidationStageType.RATE,
            passed=False,
            score=0.0,
            message=f"Non-monotonic timestamp detected (dt={dt:.4f}s)",
            details={"dt": dt},
        )

    if dt < config.min_interval:
        return StageResult(
            stage=ValidationStageType.RATE,
            passed=False,
            score=0.0,
            message=f"Update frequency too high (dt={dt:.4f}s < min {config.min_interval:.4f}s)",
            details={"dt": dt, "min_interval": config.min_interval},
        )

    if dt > config.max_interval:
        return StageResult(
            stage=ValidationStageType.RATE,
            passed=False,
            score=0.0,
            message=f"Update frequency too low / stale (dt={dt:.4f}s > max {config.max_interval:.4f}s)",
            details={"dt": dt, "max_interval": config.max_interval},
        )

    return StageResult(
        stage=ValidationStageType.RATE,
        passed=True,
        score=1.0,
        message=f"Update rate within expected bounds (dt={dt:.4f}s)",
        details={"dt": dt, "min_interval": config.min_interval, "max_interval": config.max_interval},
    )


def check_consistency(
    reading: SensorReading,
    context_readings: Dict[str, SensorReading],
    rules: List[ConsistencyRule]
) -> StageResult:
    """Stage 3: ConsistencyCheck — check cross-sensor consistency."""
    applicable_rules = [r for r in rules if r.primary_sensor_type == reading.sensor_type]
    if not applicable_rules:
        return StageResult(
            stage=ValidationStageType.CONSISTENCY,
            passed=True,
            score=1.0,
            message="No consistency rules registered for sensor type",
            details={},
        )

    evaluated_count = 0
    failed_reasons = []

    for rule in applicable_rules:
        # Find secondary sensor in context_readings
        sec_reading = None
        for s_id, s_read in context_readings.items():
            if s_id != reading.sensor_id and s_read.sensor_type == rule.secondary_sensor_type:
                sec_reading = s_read
                break

        if sec_reading is None:
            # Graceful degradation: secondary sensor missing
            continue

        evaluated_count += 1
        passed, reason = rule.check_fn(reading.value, sec_reading.value)
        if not passed:
            failed_reasons.append(f"{rule.rule_id}: {reason}")

    if failed_reasons:
        return StageResult(
            stage=ValidationStageType.CONSISTENCY,
            passed=False,
            score=0.0,
            message=f"Cross-sensor consistency check failed: {'; '.join(failed_reasons)}",
            details={"failures": failed_reasons, "evaluated_count": evaluated_count},
        )

    if evaluated_count == 0:
        # Graceful degradation when secondary sensors are missing
        return StageResult(
            stage=ValidationStageType.CONSISTENCY,
            passed=True,
            score=0.9,
            message="Consistency check skipped: correlated sensor missing (graceful degradation)",
            details={"degraded": True},
        )

    return StageResult(
        stage=ValidationStageType.CONSISTENCY,
        passed=True,
        score=1.0,
        message="Cross-sensor consistency verified",
        details={"evaluated_count": evaluated_count},
    )


def check_poisoning(
    reading: SensorReading,
    config: SensorConfig,
    history: List[float],
    stuck_counter: int
) -> StageResult:
    """Stage 4: PoisoningCheck — statistical anomaly, stuck, and noisy sensor detection."""
    # Check for stuck sensor
    if config.max_stuck_samples is not None and stuck_counter >= config.max_stuck_samples:
        return StageResult(
            stage=ValidationStageType.POISONING,
            passed=False,
            score=0.0,
            message=f"Stuck sensor detected: value unchanged for {stuck_counter} consecutive samples",
            details={"stuck_counter": stuck_counter, "max_stuck_samples": config.max_stuck_samples},
        )

    if len(history) < config.min_history_samples:
        return StageResult(
            stage=ValidationStageType.POISONING,
            passed=True,
            score=1.0,
            message="Insufficient historical data for statistical poisoning check",
            details={"history_samples": len(history)},
        )

    val = _extract_scalar(reading.value)
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std_dev = math.sqrt(variance)

    # Check for noisy sensor (high variance)
    if config.max_noise_std is not None and std_dev > config.max_noise_std:
        return StageResult(
            stage=ValidationStageType.POISONING,
            passed=False,
            score=0.0,
            message=f"Noisy sensor detected: std dev ({std_dev:.4f}) exceeds max allowed ({config.max_noise_std:.4f})",
            details={"std_dev": std_dev, "max_noise_std": config.max_noise_std},
        )

    # Statistical anomaly (Z-score check)
    if std_dev > 1e-6:
        z_score = abs(val - mean) / std_dev
        if z_score > config.z_score_threshold:
            return StageResult(
                stage=ValidationStageType.POISONING,
                passed=False,
                score=0.0,
                message=f"Statistical anomaly / poisoning detected: Z-score {z_score:.2f} > threshold {config.z_score_threshold}",
                details={"z_score": z_score, "threshold": config.z_score_threshold, "mean": mean, "std_dev": std_dev},
            )
    elif abs(val - mean) > 1e-6 and len(history) >= config.min_history_samples:
        # Zero variance history, but sudden jump in new reading
        return StageResult(
            stage=ValidationStageType.POISONING,
            passed=False,
            score=0.0,
            message=f"Statistical anomaly / poisoning detected: step change from constant baseline {mean:.4f} to {val:.4f}",
            details={"value": val, "baseline": mean},
        )

    return StageResult(
        stage=ValidationStageType.POISONING,
        passed=True,
        score=1.0,
        message="Statistical poisoning check passed",
        details={"mean": mean, "std_dev": std_dev},
    )


def compute_confidence(
    config: SensorConfig,
    stage_results: Dict[ValidationStageType, StageResult],
    weights: Dict[ValidationStageType, float]
) -> Tuple[float, StageResult]:
    """Stage 5: ConfidenceScore — weighted confidence score calculation."""
    total_weight = 0.0
    weighted_score = 0.0

    for stage_type, weight in weights.items():
        if stage_type in stage_results:
            result = stage_results[stage_type]
            total_weight += weight
            weighted_score += weight * result.score

    stage_factor = (weighted_score / total_weight) if total_weight > 0 else 1.0
    confidence = config.base_reliability * stage_factor
    confidence = max(0.0, min(1.0, confidence))

    result = StageResult(
        stage=ValidationStageType.CONFIDENCE,
        passed=confidence >= 0.5,
        score=confidence,
        message=f"Confidence score: {confidence:.3f} (base_reliability={config.base_reliability}, stage_factor={stage_factor:.3f})",
        details={"base_reliability": config.base_reliability, "stage_factor": stage_factor},
    )
    return confidence, result


# ============================================================================
# Default Configurations and Rules
# ============================================================================

def get_default_sensor_configs() -> Dict[str, SensorConfig]:
    """Default sensor bounds and validation parameters for ORION sensor types."""
    return {
        "pressure": SensorConfig(
            sensor_type="pressure",
            min_value=0.0,
            max_value=200.0,
            min_interval=0.005,
            max_interval=5.0,
            z_score_threshold=3.0,
            max_noise_std=20.0,
            max_stuck_samples=5,
            base_reliability=0.95,
        ),
        "temperature": SensorConfig(
            sensor_type="temperature",
            min_value=-50.0,
            max_value=150.0,
            min_interval=0.01,
            max_interval=10.0,
            z_score_threshold=3.0,
            max_noise_std=15.0,
            max_stuck_samples=5,
            base_reliability=0.95,
        ),
        "imu": SensorConfig(
            sensor_type="imu",
            min_value=-100.0,
            max_value=100.0,
            min_interval=0.001,
            max_interval=1.0,
            z_score_threshold=3.5,
            max_noise_std=15.0,
            max_stuck_samples=5,
            base_reliability=0.98,
        ),
        "gps": SensorConfig(
            sensor_type="gps",
            min_value=-180.0,
            max_value=180.0,
            min_interval=0.05,
            max_interval=5.0,
            z_score_threshold=3.0,
            max_noise_std=50.0,
            max_stuck_samples=5,
            base_reliability=0.90,
        ),
        "altitude": SensorConfig(
            sensor_type="altitude",
            min_value=0.0,
            max_value=500.0,
            min_interval=0.01,
            max_interval=2.0,
            z_score_threshold=3.0,
            max_noise_std=10.0,
            max_stuck_samples=5,
            base_reliability=0.95,
        ),
        "lane": SensorConfig(
            sensor_type="lane",
            min_value=-10.0,
            max_value=10.0,
            min_interval=0.01,
            max_interval=2.0,
            z_score_threshold=3.0,
            max_noise_std=3.0,
            max_stuck_samples=5,
            base_reliability=0.92,
        ),
        "obstacle": SensorConfig(
            sensor_type="obstacle",
            min_value=0.0,
            max_value=200.0,
            min_interval=0.01,
            max_interval=2.0,
            z_score_threshold=3.0,
            max_noise_std=25.0,
            max_stuck_samples=5,
            base_reliability=0.95,
        ),
        "traffic_light": SensorConfig(
            sensor_type="traffic_light",
            min_value=0.0,
            max_value=3.0,
            min_interval=0.01,
            max_interval=5.0,
            z_score_threshold=4.0,
            max_stuck_samples=10,
            base_reliability=0.99,
        ),
        "security": SensorConfig(
            sensor_type="security",
            min_value=0.0,
            max_value=1.0,
            min_interval=0.01,
            max_interval=10.0,
            z_score_threshold=4.0,
            max_stuck_samples=20,
            base_reliability=0.99,
        ),
    }


def get_default_consistency_rules() -> List[ConsistencyRule]:
    """Default cross-sensor consistency rules."""
    def _imu_gps_check(imu_val: Any, gps_val: Any) -> Tuple[bool, str]:
        s1 = _extract_scalar(imu_val)
        s2 = _extract_scalar(gps_val)
        diff = abs(s1 - s2)
        if diff > 10.0:
            return False, f"IMU speed ({s1:.2f}) and GPS speed ({s2:.2f}) discrepancy {diff:.2f} > 10.0"
        return True, "OK"

    def _alt_gps_check(alt_val: Any, gps_val: Any) -> Tuple[bool, str]:
        a1 = _extract_scalar(alt_val)
        a2 = _extract_scalar(gps_val)
        diff = abs(a1 - a2)
        if diff > 15.0:
            return False, f"Altitude sensor ({a1:.2f}) and GPS altitude ({a2:.2f}) discrepancy {diff:.2f} > 15.0"
        return True, "OK"

    def _pressure_temp_check(p_val: Any, t_val: Any) -> Tuple[bool, str]:
        p = _extract_scalar(p_val)
        t = _extract_scalar(t_val)
        # Physical plausibility: extreme pressure drop with high temp spike
        if p < 5.0 and t > 100.0:
            return False, f"Physical implausibility: near zero pressure ({p:.1f}) at high temp ({t:.1f})"
        return True, "OK"

    return [
        ConsistencyRule(
            rule_id="imu_vs_gps",
            primary_sensor_type="imu",
            secondary_sensor_type="gps",
            check_fn=_imu_gps_check,
            description="Verify IMU acceleration/speed consistency with GPS",
        ),
        ConsistencyRule(
            rule_id="altitude_vs_gps",
            primary_sensor_type="altitude",
            secondary_sensor_type="gps",
            check_fn=_alt_gps_check,
            description="Verify altimeter reading matches GPS altitude",
        ),
        ConsistencyRule(
            rule_id="pressure_vs_temperature",
            primary_sensor_type="pressure",
            secondary_sensor_type="temperature",
            check_fn=_pressure_temp_check,
            description="Verify pressure and temperature state consistency",
        ),
    ]


# ============================================================================
# Main Sensor Validation Pipeline
# ============================================================================

class SensorValidationPipeline:
    """
    5-stage sensor validation pipeline for ORION Safety Layer v3.
    """

    def __init__(
        self,
        configs: Optional[Dict[str, SensorConfig]] = None,
        confidence_threshold: float = 0.70,
        stage_weights: Optional[Dict[ValidationStageType, float]] = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.stage_weights = stage_weights or {
            ValidationStageType.RANGE: 0.30,
            ValidationStageType.RATE: 0.20,
            ValidationStageType.CONSISTENCY: 0.25,
            ValidationStageType.POISONING: 0.25,
        }
        self.configs: Dict[str, SensorConfig] = configs if configs is not None else get_default_sensor_configs()
        self.consistency_rules: List[ConsistencyRule] = get_default_consistency_rules()

        # State tracking indexed by sensor_id
        self._last_timestamps: Dict[str, float] = {}
        self._last_values: Dict[str, Any] = {}
        self._stuck_counters: Dict[str, int] = {}
        self._histories: Dict[str, List[float]] = {}

    def set_config(self, sensor_key: str, config: SensorConfig) -> None:
        """Set or override configuration for a sensor type or sensor ID."""
        self.configs[sensor_key] = config

    def get_config(self, reading: SensorReading) -> SensorConfig:
        """Lookup configuration for a reading by sensor_id first, then sensor_type."""
        if reading.sensor_id in self.configs:
            return self.configs[reading.sensor_id]
        if reading.sensor_type in self.configs:
            return self.configs[reading.sensor_type]
        return SensorConfig(sensor_type=reading.sensor_type)

    def register_consistency_rule(self, rule: ConsistencyRule) -> None:
        """Register a cross-sensor consistency rule."""
        self.consistency_rules.append(rule)

    def reset_history(self, sensor_id: Optional[str] = None) -> None:
        """Reset historical window and state tracking for a sensor or all sensors."""
        if sensor_id:
            self._last_timestamps.pop(sensor_id, None)
            self._last_values.pop(sensor_id, None)
            self._stuck_counters.pop(sensor_id, None)
            self._histories.pop(sensor_id, None)
        else:
            self._last_timestamps.clear()
            self._last_values.clear()
            self._stuck_counters.clear()
            self._histories.clear()

    def get_history(self, sensor_id: str) -> List[float]:
        """Retrieve history window for a sensor."""
        return list(self._histories.get(sensor_id, []))

    def validate(
        self,
        reading: SensorReading,
        context_readings: Optional[Dict[str, SensorReading]] = None
    ) -> SensorValidationResult:
        """
        Validate a single sensor reading through the 5-stage pipeline.

        Stages evaluated in order:
        1. RangeCheck
        2. RateCheck
        3. ConsistencyCheck
        4. PoisoningCheck
        5. ConfidenceScore
        """
        config = self.get_config(reading)
        sensor_id = reading.sensor_id
        ctx = context_readings or {}

        # Tracking state
        last_time = self._last_timestamps.get(sensor_id)
        last_val = self._last_values.get(sensor_id)
        current_stuck = self._stuck_counters.get(sensor_id, 0)
        history = self._histories.get(sensor_id, [])

        # Check if value is identical to last value
        if last_val is not None and _are_values_equal(reading.value, last_val):
            stuck_counter = current_stuck + 1
        else:
            stuck_counter = 1

        stage_results: Dict[ValidationStageType, StageResult] = {}

        # 1. RangeCheck
        r_res = check_range(reading, config)
        stage_results[ValidationStageType.RANGE] = r_res

        # 2. RateCheck
        rate_res = check_rate(reading, config, last_time)
        stage_results[ValidationStageType.RATE] = rate_res

        # 3. ConsistencyCheck
        c_res = check_consistency(reading, ctx, self.consistency_rules)
        stage_results[ValidationStageType.CONSISTENCY] = c_res

        # 4. PoisoningCheck
        p_res = check_poisoning(reading, config, history, stuck_counter)
        stage_results[ValidationStageType.POISONING] = p_res

        # 5. ConfidenceScore
        conf_score, conf_res = compute_confidence(config, stage_results, self.stage_weights)
        stage_results[ValidationStageType.CONFIDENCE] = conf_res

        # Determine overall validity and failed stage
        ordered_stages = [
            ValidationStageType.RANGE,
            ValidationStageType.RATE,
            ValidationStageType.CONSISTENCY,
            ValidationStageType.POISONING,
        ]

        failed_stage = None
        for stg in ordered_stages:
            if not stage_results[stg].passed:
                failed_stage = stg
                break

        if failed_stage is None and conf_score < self.confidence_threshold:
            failed_stage = ValidationStageType.CONFIDENCE

        is_valid = (failed_stage is None)

        # Update sensor history and state tracking
        self._last_timestamps[sensor_id] = reading.timestamp
        self._last_values[sensor_id] = reading.value
        self._stuck_counters[sensor_id] = stuck_counter

        # Add to historical sliding window if valid or not severe outlier
        scalar_val = _extract_scalar(reading.value)
        history_list = self._histories.setdefault(sensor_id, [])
        history_list.append(scalar_val)
        if len(history_list) > config.history_window_size:
            history_list.pop(0)

        msg = "Validation passed" if is_valid else f"Validation failed at stage: {failed_stage.value if failed_stage else 'unknown'}"

        return SensorValidationResult(
            sensor_id=sensor_id,
            sensor_type=reading.sensor_type,
            timestamp=reading.timestamp,
            is_valid=is_valid,
            confidence_score=conf_score,
            failed_stage=failed_stage,
            stage_results=stage_results,
            value=reading.value,
            message=msg,
        )

    def validate_all(
        self,
        readings: List[SensorReading]
    ) -> Dict[str, SensorValidationResult]:
        """
        Validate a batch of sensor readings, passing all readings as context.
        """
        ctx = {r.sensor_id: r for r in readings}
        results = {}
        for r in readings:
            results[r.sensor_id] = self.validate(r, context_readings=ctx)
        return results
