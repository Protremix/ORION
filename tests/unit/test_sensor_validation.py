"""
Unit tests for Sensor Validation Pipeline (ORION Safety Layer v3).

Covers all 5 validation stages:
1. RangeCheck
2. RateCheck
3. ConsistencyCheck
4. PoisoningCheck
5. ConfidenceScore

And specific scenarios:
- Range check pass/fail
- Rate check pass/fail (too fast, too slow, normal)
- Consistency check between two sensors
- Poisoning detection (statistical anomaly)
- Confidence score calculation
- Full pipeline: valid data passes all stages
- Full pipeline: invalid data rejected at appropriate stage
- Multiple sensor types with different range bounds
- Pipeline with missing sensor (graceful degradation)
- Pipeline with stuck sensor (same value repeatedly)
- Pipeline with noisy sensor (high variance)
- Edge case: boundary values (exactly at limit)
"""

import time
import pytest
from src.safety.sensor_validation import (
    ValidationStageType,
    SensorReading,
    StageResult,
    SensorValidationResult,
    SensorConfig,
    ConsistencyRule,
    SensorValidationPipeline,
    check_range,
    check_rate,
    check_consistency,
    check_poisoning,
    compute_confidence,
)


class TestSensorValidationPipeline:
    """Test suite covering the 5-stage sensor validation pipeline."""

    def test_range_check_pass_and_fail(self):
        """Test RangeCheck stage pass and fail conditions."""
        config = SensorConfig(sensor_type="pressure", min_value=0.0, max_value=100.0)

        # Valid reading
        valid_reading = SensorReading("p1", "pressure", value=50.0)
        res_valid = check_range(valid_reading, config)
        assert res_valid.passed is True
        assert res_valid.stage == ValidationStageType.RANGE
        assert res_valid.score == 1.0

        # Out of bounds reading (too high)
        invalid_high = SensorReading("p1", "pressure", value=150.0)
        res_high = check_range(invalid_high, config)
        assert res_high.passed is False
        assert res_high.score == 0.0

        # Out of bounds reading (too low)
        invalid_low = SensorReading("p1", "pressure", value=-10.0)
        res_low = check_range(invalid_low, config)
        assert res_low.passed is False
        assert res_low.score == 0.0

    def test_rate_check_fast_slow_normal(self):
        """Test RateCheck stage pass/fail for too fast, too slow, and normal updates."""
        config = SensorConfig(
            sensor_type="temp",
            min_interval=0.1,  # minimum 100ms
            max_interval=2.0   # maximum 2s
        )

        # 1. First reading passes
        r1 = SensorReading("t1", "temp", value=22.0, timestamp=10.0)
        res1 = check_rate(r1, config, last_timestamp=None)
        assert res1.passed is True

        # 2. Too fast (dt = 0.02s < 0.1s)
        r_fast = SensorReading("t1", "temp", value=22.1, timestamp=10.02)
        res_fast = check_rate(r_fast, config, last_timestamp=10.0)
        assert res_fast.passed is False
        assert "too high" in res_fast.message.lower()

        # 3. Too slow (dt = 5.0s > 2.0s)
        r_slow = SensorReading("t1", "temp", value=22.2, timestamp=15.0)
        res_slow = check_rate(r_slow, config, last_timestamp=10.0)
        assert res_slow.passed is False
        assert "too low" in res_slow.message.lower() or "stale" in res_slow.message.lower()

        # 4. Normal (dt = 0.5s)
        r_normal = SensorReading("t1", "temp", value=22.3, timestamp=10.5)
        res_normal = check_rate(r_normal, config, last_timestamp=10.0)
        assert res_normal.passed is True

    def test_consistency_check_between_two_sensors(self):
        """Test ConsistencyCheck stage cross-sensor validation."""
        rule = ConsistencyRule(
            rule_id="imu_gps_speed",
            primary_sensor_type="imu",
            secondary_sensor_type="gps",
            check_fn=lambda imu_val, gps_val: (abs(imu_val - gps_val) <= 5.0, "Speed discrepancy > 5.0")
        )

        imu_reading = SensorReading("imu_1", "imu", value=20.0)

        # Consistent GPS reading
        ctx_pass = {"gps_1": SensorReading("gps_1", "gps", value=22.0)}
        res_pass = check_consistency(imu_reading, ctx_pass, [rule])
        assert res_pass.passed is True

        # Inconsistent GPS reading
        ctx_fail = {"gps_1": SensorReading("gps_1", "gps", value=35.0)}
        res_fail = check_consistency(imu_reading, ctx_fail, [rule])
        assert res_fail.passed is False
        assert "Speed discrepancy" in res_fail.message

    def test_poisoning_detection_z_score(self):
        """Test PoisoningCheck stage statistical anomaly (Z-score) detection."""
        config = SensorConfig(sensor_type="temp", z_score_threshold=3.0, min_history_samples=5)
        history = [20.0, 20.1, 19.9, 20.2, 20.0, 19.8, 20.1, 20.0]

        # Normal reading (Z-score ~ 0)
        normal_reading = SensorReading("t1", "temp", value=20.1)
        res_normal = check_poisoning(normal_reading, config, history, stuck_counter=1)
        assert res_normal.passed is True

        # Anomalous / poisoned reading (Z-score > 3.0)
        poisoned_reading = SensorReading("t1", "temp", value=50.0)
        res_poisoned = check_poisoning(poisoned_reading, config, history, stuck_counter=1)
        assert res_poisoned.passed is False
        assert "poisoning" in res_poisoned.message.lower() or "anomaly" in res_poisoned.message.lower()

    def test_confidence_score_calculation(self):
        """Test Stage 5 ConfidenceScore calculation with weighted stages."""
        config = SensorConfig(sensor_type="pressure", base_reliability=0.90)
        weights = {
            ValidationStageType.RANGE: 0.30,
            ValidationStageType.RATE: 0.20,
            ValidationStageType.CONSISTENCY: 0.25,
            ValidationStageType.POISONING: 0.25,
        }

        stage_results_all_pass = {
            ValidationStageType.RANGE: StageResult(ValidationStageType.RANGE, True, score=1.0),
            ValidationStageType.RATE: StageResult(ValidationStageType.RATE, True, score=1.0),
            ValidationStageType.CONSISTENCY: StageResult(ValidationStageType.CONSISTENCY, True, score=1.0),
            ValidationStageType.POISONING: StageResult(ValidationStageType.POISONING, True, score=1.0),
        }

        conf_all_pass, _ = compute_confidence(config, stage_results_all_pass, weights)
        assert conf_all_pass == pytest.approx(0.90, abs=1e-3)

        # One stage failed (RangeCheck failed => score 0.0)
        stage_results_one_fail = {
            ValidationStageType.RANGE: StageResult(ValidationStageType.RANGE, False, score=0.0),
            ValidationStageType.RATE: StageResult(ValidationStageType.RATE, True, score=1.0),
            ValidationStageType.CONSISTENCY: StageResult(ValidationStageType.CONSISTENCY, True, score=1.0),
            ValidationStageType.POISONING: StageResult(ValidationStageType.POISONING, True, score=1.0),
        }

        conf_one_fail, _ = compute_confidence(config, stage_results_one_fail, weights)
        # Expected: 0.90 * (0.20*1 + 0.25*1 + 0.25*1) = 0.90 * 0.70 = 0.63
        assert conf_one_fail == pytest.approx(0.63, abs=1e-3)

    def test_full_pipeline_valid_data(self):
        """Test full pipeline execution when valid data passes all 5 stages."""
        pipeline = SensorValidationPipeline()

        # Prime pipeline with history
        t = 100.0
        for i in range(10):
            reading = SensorReading("pressure_sensor_1", "pressure", value=50.0 + (i % 3) * 0.1, timestamp=t)
            res = pipeline.validate(reading)
            t += 0.5

        # Valid reading
        final_reading = SensorReading("pressure_sensor_1", "pressure", value=50.2, timestamp=t)
        final_res = pipeline.validate(final_reading)

        assert final_res.is_valid is True
        assert final_res.failed_stage is None
        assert final_res.confidence_score >= 0.70
        assert all(stg.passed for stg in final_res.stage_results.values())

    def test_full_pipeline_invalid_data_rejected_at_appropriate_stage(self):
        """Test full pipeline rejection at specific failed stages."""
        pipeline = SensorValidationPipeline()
        config = SensorConfig(sensor_type="pressure", min_value=0.0, max_value=100.0, min_interval=0.1, max_interval=2.0)
        pipeline.set_config("pressure", config)

        t = 100.0
        r1 = SensorReading("p1", "pressure", value=50.0, timestamp=t)
        pipeline.validate(r1)

        # 1. Out of range value -> rejected at RANGE stage
        r_range_fail = SensorReading("p1", "pressure", value=250.0, timestamp=t + 0.5)
        res_range = pipeline.validate(r_range_fail)
        assert res_range.is_valid is False
        assert res_range.failed_stage == ValidationStageType.RANGE

        # 2. Too fast interval -> rejected at RATE stage
        r_rate_fail = SensorReading("p1", "pressure", value=50.0, timestamp=t + 0.501)
        res_rate = pipeline.validate(r_rate_fail)
        assert res_rate.is_valid is False
        assert res_rate.failed_stage == ValidationStageType.RATE

    def test_multiple_sensor_types_different_bounds(self):
        """Test pipeline handling different sensor types with distinct bounds."""
        pipeline = SensorValidationPipeline()

        p_config = SensorConfig(sensor_type="pressure", min_value=0.0, max_value=200.0)
        t_config = SensorConfig(sensor_type="temperature", min_value=-50.0, max_value=100.0)
        pipeline.set_config("pressure", p_config)
        pipeline.set_config("temperature", t_config)

        # Value 150.0 is valid for pressure, but invalid for temperature if max is 100
        p_read = SensorReading("p1", "pressure", value=150.0)
        t_read = SensorReading("t1", "temperature", value=150.0)

        p_res = pipeline.validate(p_read)
        t_res = pipeline.validate(t_read)

        assert p_res.is_valid is True
        assert t_res.is_valid is False
        assert t_res.failed_stage == ValidationStageType.RANGE

    def test_pipeline_missing_sensor_graceful_degradation(self):
        """Test pipeline graceful degradation when correlated sensor is missing."""
        pipeline = SensorValidationPipeline()
        rule = ConsistencyRule(
            rule_id="pressure_vs_temp",
            primary_sensor_type="pressure",
            secondary_sensor_type="temperature",
            check_fn=lambda p, t: (True, "OK")
        )
        pipeline.register_consistency_rule(rule)

        # Pressure reading without temperature in context
        p_read = SensorReading("p1", "pressure", value=100.0)
        res = pipeline.validate(p_read, context_readings={})

        assert res.is_valid is True
        assert res.stage_results[ValidationStageType.CONSISTENCY].passed is True
        assert "skipped" in res.stage_results[ValidationStageType.CONSISTENCY].message.lower() or "graceful" in res.stage_results[ValidationStageType.CONSISTENCY].message.lower()

    def test_pipeline_stuck_sensor(self):
        """Test pipeline detection of stuck sensor (same value repeatedly)."""
        pipeline = SensorValidationPipeline()
        config = SensorConfig(sensor_type="pressure", max_stuck_samples=4)
        pipeline.set_config("pressure", config)

        t = 100.0
        # Send same value 4 times
        for i in range(3):
            r = SensorReading("p1", "pressure", value=10.0, timestamp=t + i * 0.5)
            res = pipeline.validate(r)
            assert res.is_valid is True

        # 4th sample with same value should trigger stuck sensor detection
        r_stuck = SensorReading("p1", "pressure", value=10.0, timestamp=t + 1.5)
        res_stuck = pipeline.validate(r_stuck)

        assert res_stuck.is_valid is False
        assert res_stuck.failed_stage == ValidationStageType.POISONING
        assert "stuck" in res_stuck.stage_results[ValidationStageType.POISONING].message.lower()

    def test_pipeline_noisy_sensor(self):
        """Test pipeline detection of noisy sensor (excessive variance)."""
        pipeline = SensorValidationPipeline()
        config = SensorConfig(sensor_type="temp", max_noise_std=2.0, min_history_samples=5)
        pipeline.set_config("temp", config)

        t = 100.0
        # Feed high-variance noisy readings: alternating between 10.0 and 30.0
        noisy_values = [10.0, 30.0, 10.0, 30.0, 10.0, 30.0]
        for val in noisy_values[:-1]:
            r = SensorReading("t1", "temp", value=val, timestamp=t)
            pipeline.validate(r)
            t += 0.5

        # Next noisy reading triggers max_noise_std violation
        r_noisy = SensorReading("t1", "temp", value=noisy_values[-1], timestamp=t)
        res_noisy = pipeline.validate(r_noisy)

        assert res_noisy.is_valid is False
        assert res_noisy.failed_stage == ValidationStageType.POISONING
        assert "noisy" in res_noisy.stage_results[ValidationStageType.POISONING].message.lower()

    def test_edge_case_boundary_values(self):
        """Test edge cases: boundary values exactly at minimum and maximum limits pass."""
        pipeline = SensorValidationPipeline()
        config = SensorConfig(sensor_type="altitude", min_value=0.0, max_value=120.0)
        pipeline.set_config("altitude", config)

        # Exactly at min boundary
        r_min = SensorReading("alt_1", "altitude", value=0.0, timestamp=10.0)
        res_min = pipeline.validate(r_min)
        assert res_min.stage_results[ValidationStageType.RANGE].passed is True
        assert res_min.is_valid is True

        # Exactly at max boundary
        r_max = SensorReading("alt_1", "altitude", value=120.0, timestamp=11.0)
        res_max = pipeline.validate(r_max)
        assert res_max.stage_results[ValidationStageType.RANGE].passed is True
        assert res_max.is_valid is True
