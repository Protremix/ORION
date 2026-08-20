"""
Tests for OPIB Benchmark Scenarios — ORION Physical Intelligence Benchmark.

License: Apache 2.0
"""

import pytest
from eval import OPIB, OPIBScenario, OPIBResult, EvalCategory, EvalStatus
from eval.opib_scenarios import (
    create_vehicle_scenarios,
    create_industrial_scenarios,
    create_home_scenarios,
    create_drone_scenarios,
    create_cross_domain_scenarios,
    create_all_scenarios,
    OPIBTestSystem,
)


class TestOPIBScenarioCreation:
    """Test scenario creation for each domain."""

    def test_vehicle_scenarios(self):
        scenarios = create_vehicle_scenarios()
        assert len(scenarios) == 3
        assert all(s.domain == "vehicle" for s in scenarios)
        assert scenarios[0].scenario_id == "veh-001"
        assert scenarios[1].scenario_id == "veh-002"
        assert scenarios[2].scenario_id == "veh-003"

    def test_industrial_scenarios(self):
        scenarios = create_industrial_scenarios()
        assert len(scenarios) == 2
        assert all(s.domain == "industrial" for s in scenarios)
        assert scenarios[0].scenario_id == "ind-001"
        assert scenarios[1].scenario_id == "ind-002"

    def test_home_scenarios(self):
        scenarios = create_home_scenarios()
        assert len(scenarios) == 2
        assert all(s.domain == "home" for s in scenarios)

    def test_drone_scenarios(self):
        scenarios = create_drone_scenarios()
        assert len(scenarios) == 2
        assert all(s.domain == "drone" for s in scenarios)

    def test_cross_domain_scenarios(self):
        scenarios = create_cross_domain_scenarios()
        assert len(scenarios) == 1
        assert "domains" in scenarios[0].initial_state

    def test_all_scenarios(self):
        scenarios = create_all_scenarios()
        assert len(scenarios) == 10  # 3 + 2 + 2 + 2 + 1
        domains = {s.domain for s in scenarios}
        assert "vehicle" in domains
        assert "industrial" in domains
        assert "home" in domains
        assert "drone" in domains

    def test_scenarios_have_phases(self):
        scenarios = create_all_scenarios()
        for s in scenarios:
            assert len(s.phases) > 0
            assert "observe" in s.phases
            assert "act" in s.phases

    def test_scenarios_have_initial_state(self):
        scenarios = create_all_scenarios()
        for s in scenarios:
            assert len(s.initial_state) > 0

    def test_scenarios_have_expected_outcome(self):
        scenarios = create_all_scenarios()
        for s in scenarios:
            assert len(s.expected_outcome) > 0
            assert "completed" in s.expected_outcome

    def test_difficulty_levels(self):
        scenarios = create_all_scenarios()
        difficulties = {s.difficulty for s in scenarios}
        assert "easy" in difficulties
        assert "medium" in difficulties
        assert "hard" in difficulties


class TestOPIBExecution:
    """Test OPIB benchmark execution."""

    def test_run_vehicle_benchmark(self):
        """Run vehicle domain benchmark scenarios."""
        opib = OPIB()
        for scenario in create_vehicle_scenarios():
            opib.add_scenario(scenario)

        system = OPIBTestSystem()
        results = opib.run_benchmark(system, domain="vehicle")

        assert len(results) == 3
        for r in results:
            assert r.scenario.domain == "vehicle"
            assert r.time_taken_seconds >= 0.0
            assert 0.0 <= r.score <= 1.0

    def test_run_industrial_benchmark(self):
        """Run industrial domain benchmark scenarios."""
        opib = OPIB()
        for scenario in create_industrial_scenarios():
            opib.add_scenario(scenario)

        system = OPIBTestSystem()
        results = opib.run_benchmark(system, domain="industrial")

        assert len(results) == 2
        for r in results:
            assert r.scenario.domain == "industrial"

    def test_run_home_benchmark(self):
        """Run home domain benchmark scenarios."""
        opib = OPIB()
        for scenario in create_home_scenarios():
            opib.add_scenario(scenario)

        system = OPIBTestSystem()
        results = opib.run_benchmark(system, domain="home")

        assert len(results) == 2
        for r in results:
            assert r.scenario.domain == "home"

    def test_run_drone_benchmark(self):
        """Run drone domain benchmark scenarios."""
        opib = OPIB()
        for scenario in create_drone_scenarios():
            opib.add_scenario(scenario)

        system = OPIBTestSystem()
        results = opib.run_benchmark(system, domain="drone")

        assert len(results) == 2
        for r in results:
            assert r.scenario.domain == "drone"

    def test_run_all_benchmarks(self):
        """Run all benchmark scenarios."""
        opib = OPIB()
        for scenario in create_all_scenarios():
            opib.add_scenario(scenario)

        system = OPIBTestSystem()
        results = opib.run_benchmark(system)

        assert len(results) == 10
        # All should complete (even if some phases fail)
        for r in results:
            assert r.scenario is not None
            assert r.time_taken_seconds >= 0.0

    def test_benchmark_summary(self):
        """Benchmark produces summary statistics."""
        opib = OPIB()
        for scenario in create_all_scenarios():
            opib.add_scenario(scenario)

        system = OPIBTestSystem()
        opib.run_benchmark(system)
        summary = opib.summary()

        assert summary["total_scenarios"] == 10
        assert summary["passed"] >= 0
        assert summary["failed"] >= 0
        assert summary["pass_rate"] >= 0.0
        assert summary["avg_score"] >= 0.0

    def test_domain_filtering(self):
        """Benchmark can filter by domain."""
        opib = OPIB()
        for scenario in create_all_scenarios():
            opib.add_scenario(scenario)

        system = OPIBTestSystem()
        results = opib.run_benchmark(system, domain="vehicle")

        assert len(results) == 4  # 3 vehicle + 1 cross-domain (primary=vehicle)
        assert all(r.scenario.domain == "vehicle" for r in results)

    def test_scenarios_list(self):
        """Can list all scenarios."""
        opib = OPIB()
        for scenario in create_all_scenarios():
            opib.add_scenario(scenario)

        listed = opib.list_scenarios()
        assert len(listed) == 10

    def test_phases_completed(self):
        """Each result tracks completed phases."""
        opib = OPIB()
        for scenario in create_vehicle_scenarios():
            opib.add_scenario(scenario)

        system = OPIBTestSystem()
        results = opib.run_benchmark(system)

        for r in results:
            assert len(r.phases_completed) > 0
            assert "observe" in r.phases_completed

    def test_safety_events_tracking(self):
        """Results track safety events."""
        opib = OPIB()
        # Emergency braking scenario has recover phase
        opib.add_scenario(create_vehicle_scenarios()[2])  # veh-003

        system = OPIBTestSystem()
        results = opib.run_benchmark(system)

        assert len(results) == 1
        assert results[0].safety_events >= 0


class TestOPIBTestSystem:
    """Test the OPIB test system."""

    def test_system_implements_all_phases(self):
        """Test system implements all OPIB phase methods."""
        system = OPIBTestSystem()
        phases = ["opib_observe", "opib_world_state", "opib_predict",
                  "opib_plan", "opib_simulate", "opib_act",
                  "opib_result", "opib_recover"]
        for phase in phases:
            assert hasattr(system, phase)

    def test_observe_stores_state(self):
        """Observe phase stores initial state."""
        system = OPIBTestSystem()
        system.opib_observe({"test": "data", "road_length": 100})
        assert system._current_state["test"] == "data"
        assert system._current_state["road_length"] == 100

    def test_world_state_validates(self):
        """World state phase validates observations."""
        system = OPIBTestSystem()
        system.opib_observe({"road_length": 100})
        assert system.opib_world_state({}) is True

    def test_predict_with_world_model(self):
        """Predict phase uses world model when available."""
        system = OPIBTestSystem()
        system.opib_observe({"road_length": 100, "ego_speed": 20, "ego_lane": 1})
        result = system.opib_predict({})
        assert result is True

    def test_plan_with_obstacles(self):
        """Plan phase handles obstacles."""
        system = OPIBTestSystem()
        system.opib_observe({
            "obstacles": [[3, 3], [5, 5]],
            "target_pos": [9, 9],
        })
        assert system.opib_plan({}) is True

    def test_act_safety_check(self):
        """Act phase performs safety check."""
        system = OPIBTestSystem()
        system.opib_observe({"obstacles": [], "ego_lane": 0})
        assert system.opib_act({}) is True
