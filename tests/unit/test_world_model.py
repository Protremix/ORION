"""
Tests for ORION World Model — Phase 4 (Physics Simulation, Prediction, Uncertainty)
"""

import math
import time

import pytest

from src.world_model import (
    DronePhysics,
    HomePhysics,
    IndustrialPhysics,
    PredictionConfidence,
    PredictionResult,
    StateSnapshot,
    VehiclePhysics,
    WorldModel,
)

# ============================================================================
# Physics Model Tests
# ============================================================================

class TestIndustrialPhysics:
    def test_predict_basic(self):
        state = StateSnapshot(domain="industrial", entities={
            "machine_1": {"wear": 0.1, "temperature": 25.0, "status": "running"}
        })
        predictions = IndustrialPhysics.predict(state, {}, steps=5)
        assert len(predictions) == 5
        # Temperature should increase
        assert predictions[-1].entities["machine_1"]["temperature"] > 25.0
        # Wear should increase
        assert predictions[-1].entities["machine_1"]["wear"] > 0.1

    def test_predict_idle_machine(self):
        state = StateSnapshot(domain="industrial", entities={
            "machine_1": {"wear": 0.1, "temperature": 25.0, "status": "idle"}
        })
        predictions = IndustrialPhysics.predict(state, {}, steps=3)
        # Idle machine should not heat up
        assert predictions[-1].entities["machine_1"]["temperature"] == 25.0

    def test_safety_check_overheating(self):
        states = [StateSnapshot(domain="industrial", entities={
            "machine_1": {"wear": 0.1, "temperature": 105.0, "status": "running"}
        })]
        result = IndustrialPhysics.check_safety(states)
        assert not result["safe"]
        assert len(result["violations"]) == 1
        assert "overheating" in result["violations"][0]

    def test_safety_check_wear(self):
        states = [StateSnapshot(domain="industrial", entities={
            "machine_1": {"wear": 0.95, "temperature": 50.0, "status": "running"}
        })]
        result = IndustrialPhysics.check_safety(states)
        assert not result["safe"]
        assert "excessive wear" in result["violations"][0]

    def test_safety_check_safe(self):
        states = [StateSnapshot(domain="industrial", entities={
            "machine_1": {"wear": 0.1, "temperature": 30.0, "status": "running"}
        })]
        result = IndustrialPhysics.check_safety(states)
        assert result["safe"]
        assert len(result["violations"]) == 0

    def test_temperature_capped(self):
        state = StateSnapshot(domain="industrial", entities={
            "machine_1": {"wear": 0.1, "temperature": 119.0, "status": "running"}
        })
        predictions = IndustrialPhysics.predict(state, {}, steps=10)
        # Temperature should be capped at 120
        assert all(p.entities["machine_1"]["temperature"] <= 120.0 for p in predictions)


class TestVehiclePhysics:
    def test_predict_basic_movement(self):
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 0, "vy": 0})
        action = {"acceleration_x": 1.0, "acceleration_y": 0.0}
        predictions = VehiclePhysics.predict(state, action, steps=10)
        assert len(predictions) == 10
        # Vehicle should move in x direction
        assert predictions[-1].entities["x"] > 0
        assert predictions[-1].entities["vx"] > 0

    def test_predict_drag(self):
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 10, "vy": 0})
        predictions = VehiclePhysics.predict(state, {"acceleration_x": 0, "acceleration_y": 0}, steps=20)
        # Speed should decrease due to drag
        assert predictions[-1].entities["vx"] < 10

    def test_speed_limit(self):
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 0, "vy": 0})
        action = {"acceleration_x": 50.0, "acceleration_y": 0, "max_speed": 10.0}
        predictions = VehiclePhysics.predict(state, action, steps=20)
        # Speed should be limited
        assert all(p.entities.get("speed", 0) <= 10.01 for p in predictions)

    def test_safety_check_speeding(self):
        states = [StateSnapshot(domain="vehicle", entities={"speed": 40.0})]
        result = VehiclePhysics.check_safety(states)
        assert not result["safe"]
        assert "Speed" in result["violations"][0]

    def test_safety_check_safe(self):
        states = [StateSnapshot(domain="vehicle", entities={"speed": 20.0})]
        result = VehiclePhysics.check_safety(states)
        assert result["safe"]


class TestDronePhysics:
    def test_predict_basic(self):
        state = StateSnapshot(domain="drone", entities={"altitude": 50, "vx": 0, "vy": 0, "vz": 0, "battery": 100})
        action = {"thrust": 9.8, "target_vx": 1.0, "target_vy": 0}
        predictions = DronePhysics.predict(state, action, steps=10)
        assert len(predictions) == 10
        # Drone should start moving horizontally
        assert predictions[-1].entities["vx"] > 0

    def test_battery_drain(self):
        state = StateSnapshot(domain="drone", entities={"altitude": 50, "vx": 5, "vy": 5, "vz": 0, "battery": 100})
        action = {"thrust": 10.0, "target_vx": 5, "target_vy": 5}
        predictions = DronePhysics.predict(state, action, steps=50)
        # Battery should drain
        assert predictions[-1].entities["battery"] < 100

    def test_ground_collision(self):
        state = StateSnapshot(domain="drone", entities={"altitude": 1, "vx": 0, "vy": 0, "vz": -5, "battery": 80})
        action = {"thrust": 0, "target_vx": 0, "target_vy": 0}
        predictions = DronePhysics.predict(state, action, steps=5)
        # Altitude should not go below 0
        assert all(p.entities["altitude"] >= 0 for p in predictions)

    def test_safety_low_altitude(self):
        states = [StateSnapshot(domain="drone", entities={"altitude": 3, "battery": 80})]
        result = DronePhysics.check_safety(states)
        assert not result["safe"]
        assert "Altitude" in result["violations"][0]

    def test_safety_low_battery(self):
        states = [StateSnapshot(domain="drone", entities={"altitude": 50, "battery": 15})]
        result = DronePhysics.check_safety(states)
        assert not result["safe"]
        assert "Battery" in result["violations"][0]


class TestHomePhysics:
    def test_predict_heating(self):
        state = StateSnapshot(domain="home", entities={"temperature": 20, "humidity": 45, "lights_on": False, "doors_locked": True})
        action = {"heating": True}
        predictions = HomePhysics.predict(state, action, steps=10)
        assert predictions[-1].entities["temperature"] > 20

    def test_predict_cooling(self):
        state = StateSnapshot(domain="home", entities={"temperature": 30, "humidity": 45, "lights_on": False, "doors_locked": True})
        action = {"cooling": True}
        predictions = HomePhysics.predict(state, action, steps=10)
        assert predictions[-1].entities["temperature"] < 30

    def test_predict_lights(self):
        state = StateSnapshot(domain="home", entities={"temperature": 22, "humidity": 45, "lights_on": False, "doors_locked": True})
        action = {"set_lights": True}
        predictions = HomePhysics.predict(state, action, steps=3)
        assert predictions[0].entities["lights_on"] is True

    def test_safety_unlocked_doors(self):
        states = [StateSnapshot(domain="home", entities={"temperature": 22, "doors_locked": False})]
        result = HomePhysics.check_safety(states)
        assert not result["safe"]
        assert "Doors unlocked" in result["violations"][0]

    def test_safety_temp_out_of_range(self):
        states = [StateSnapshot(domain="home", entities={"temperature": 40, "doors_locked": True})]
        result = HomePhysics.check_safety(states)
        assert not result["safe"]
        assert "Temperature" in result["violations"][0]


# ============================================================================
# World Model Tests
# ============================================================================

class TestWorldModel:
    def test_predict_industrial(self):
        wm = WorldModel()
        state = StateSnapshot(domain="industrial", entities={
            "machine_1": {"wear": 0.1, "temperature": 25, "status": "running"}
        })
        result = wm.predict(state, {}, horizon=5)
        assert len(result.predicted_states) == 5
        assert result.safety_assessment is not None
        assert result.uncertainty > 0

    def test_predict_vehicle(self):
        wm = WorldModel()
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 0, "vy": 0})
        result = wm.predict(state, {"acceleration_x": 1.0}, horizon=10)
        assert len(result.predicted_states) == 10
        assert result.predicted_states[-1].entities["x"] > 0

    def test_predict_drone(self):
        wm = WorldModel()
        state = StateSnapshot(domain="drone", entities={"altitude": 50, "vx": 0, "vy": 0, "vz": 0, "battery": 100})
        result = wm.predict(state, {"thrust": 9.8, "target_vx": 1}, horizon=10)
        assert len(result.predicted_states) == 10
        assert result.predicted_states[-1].entities["battery"] < 100

    def test_predict_home(self):
        wm = WorldModel()
        state = StateSnapshot(domain="home", entities={"temperature": 20, "humidity": 45, "lights_on": False, "doors_locked": True})
        result = wm.predict(state, {"heating": True}, horizon=5)
        assert len(result.predicted_states) == 5
        assert result.predicted_states[-1].entities["temperature"] > 20

    def test_uncertainty_grows_with_horizon(self):
        wm = WorldModel()
        state = StateSnapshot(domain="industrial", entities={"m1": {"wear": 0.1, "temperature": 25, "status": "idle"}})
        short = wm.predict(state, {}, horizon=1)
        long = wm.predict(state, {}, horizon=50)
        assert long.uncertainty >= short.uncertainty

    def test_confidence_levels(self):
        wm = WorldModel()
        state = StateSnapshot(domain="industrial", entities={"m1": {"wear": 0.1, "temperature": 25, "status": "idle"}})
        result = wm.predict(state, {}, horizon=1)
        # Short horizon should have high confidence
        assert result.confidence == PredictionConfidence.HIGH

    def test_collision_risk_vehicle(self):
        wm = WorldModel()
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 0, "vy": 0})
        action = {"acceleration_x": 50, "acceleration_y": 0, "max_speed": 40}
        result = wm.predict(state, action, horizon=20)
        assert result.collision_risk > 0

    def test_collision_risk_drone(self):
        wm = WorldModel()
        state = StateSnapshot(domain="drone", entities={"altitude": 10, "vx": 0, "vy": 0, "vz": -2, "battery": 80})
        result = wm.predict(state, {"thrust": 0}, horizon=10)
        assert result.collision_risk > 0

    def test_batch_predict(self):
        wm = WorldModel()
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 0, "vy": 0})
        actions = [{"acceleration_x": 1}, {"acceleration_x": 5}, {"acceleration_x": -1}]
        results = wm.batch_predict(state, actions, horizon=5)
        assert len(results) == 3
        assert all(len(r.predicted_states) == 5 for r in results)

    def test_select_best_action_safe(self):
        wm = WorldModel()
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 0, "vy": 0})
        actions = [
            {"acceleration_x": 1, "max_speed": 20},  # Safe
            {"acceleration_x": 50, "max_speed": 50},  # Risky (high speed)
            {"acceleration_x": 0, "max_speed": 20},  # Safe (no acceleration)
        ]
        best_action, best_result = wm.select_best_action(state, actions, horizon=10)
        assert best_result.safety_assessment["safe"]

    def test_select_best_action_all_unsafe(self):
        wm = WorldModel()
        state = StateSnapshot(domain="vehicle", entities={"x": 0, "y": 0, "vx": 40, "vy": 0})
        actions = [
            {"acceleration_x": 10, "max_speed": 50},
            {"acceleration_x": 20, "max_speed": 50},
        ]
        best_action, best_result = wm.select_best_action(state, actions, horizon=10)
        # Should still return the least risky option
        assert best_action is not None or best_result is not None

    def test_generic_predict_unknown_domain(self):
        wm = WorldModel()
        state = StateSnapshot(domain="unknown_domain", entities={"x": 0})
        result = wm.predict(state, {}, horizon=3)
        assert result.confidence == PredictionConfidence.UNKNOWN
        assert result.uncertainty > 0.5

    def test_statistics(self):
        wm = WorldModel()
        state = StateSnapshot(domain="industrial", entities={"m1": {"wear": 0, "temperature": 20, "status": "idle"}})
        wm.predict(state, {}, horizon=1)
        wm.predict(state, {}, horizon=2)
        stats = wm.get_statistics()
        assert stats["total_predictions"] == 2
        assert stats["avg_latency_ms"] > 0
        assert "industrial" in stats["supported_domains"]

    def test_safety_assessment_in_result(self):
        wm = WorldModel()
        state = StateSnapshot(domain="industrial", entities={
            "m1": {"wear": 0.1, "temperature": 25, "status": "running"}
        })
        result = wm.predict(state, {}, horizon=3)
        assert result.safety_assessment is not None
        assert "safe" in result.safety_assessment
        assert "violations" in result.safety_assessment

    def test_latency_measured(self):
        wm = WorldModel()
        state = StateSnapshot(domain="home", entities={"temperature": 22, "doors_locked": True})
        result = wm.predict(state, {"heating": True}, horizon=5)
        assert result.latency_ms >= 0

    def test_metadata_includes_domain(self):
        wm = WorldModel()
        state = StateSnapshot(domain="drone", entities={"altitude": 50, "battery": 100, "vx": 0, "vy": 0, "vz": 0})
        result = wm.predict(state, {"thrust": 9.8}, horizon=5)
        assert result.metadata["domain"] == "drone"
        assert result.metadata["horizon"] == 5
        assert "physics_model" in result.metadata
