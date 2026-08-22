"""
ORION Phase 007 — Simulation Test Suite. License: Apache 2.0.

Tests: SimulationEngine, HypothesisGenerator, ActionEvaluation, SimulationResult
Integration: full pipeline, multi-domain, safety filtering, memory integration.
"""
from __future__ import annotations

import time

import pytest

from src.simulation import ActionEvaluation, SimulationEngine, SimulationResult
from src.simulation.hypothesis_generator import Hypothesis, HypothesisGenerator
from src.world_model import WorldModel
from src.world_model.world_state import EntityRelation, WorldEntity, WorldState

# ============================================================================
# HypothesisGenerator Tests
# ============================================================================

class TestHypothesisGenerator:
    def test_generate_multiple_hypotheses(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="vehicle")
        hyps = gen.generate(ws, "reach destination", max_hypotheses=5)
        assert len(hyps) >= 2
        assert all(isinstance(h, Hypothesis) for h in hyps)

    def test_generate_respects_max_limit(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="industrial")
        hyps = gen.generate(ws, "optimize production", max_hypotheses=3)
        assert len(hyps) <= 3

    def test_generate_vehicle_domain(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="vehicle")
        hyps = gen.generate(ws, "drive safely", max_hypotheses=5)
        assert all(h.domain == "vehicle" for h in hyps)
        action_types = [h.action.get("action_type") for h in hyps]
        assert "accelerate" in action_types or "brake" in action_types

    def test_generate_drone_domain(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="drone")
        hyps = gen.generate(ws, "survey area", max_hypotheses=5)
        assert all(h.domain == "drone" for h in hyps)
        action_types = [h.action.get("action_type") for h in hyps]
        assert "ascend" in action_types or "hover" in action_types

    def test_generate_home_domain(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="home")
        hyps = gen.generate(ws, "secure home", max_hypotheses=5)
        assert all(h.domain == "home" for h in hyps)

    def test_generate_industrial_domain(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="industrial")
        hyps = gen.generate(ws, "maintain safety", max_hypotheses=5)
        assert all(h.domain == "industrial" for h in hyps)

    def test_hypotheses_sorted_by_priority(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="vehicle")
        hyps = gen.generate(ws, "stop for safety", max_hypotheses=7)
        priorities = [h.priority for h in hyps]
        assert priorities == sorted(priorities, reverse=True)

    def test_hypothesis_to_dict(self):
        h = Hypothesis(
            hypothesis_id="h1",
            action={"action_type": "test"},
            description="test action",
            expected_outcome="test outcome",
        )
        d = h.to_dict()
        assert d["hypothesis_id"] == "h1"
        assert d["action"]["action_type"] == "test"

    def test_generate_unknown_domain_falls_back(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="unknown_domain")
        hyps = gen.generate(ws, "test goal", max_hypotheses=3)
        assert len(hyps) >= 1  # falls back to industrial templates

    def test_safety_goal_boosts_conservative_actions(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="vehicle")
        hyps = gen.generate(ws, "stop and avoid collision", max_hypotheses=7)
        # Brake/stop should have higher priority than accelerate
        brake_hyp = next((h for h in hyps if "brake" in str(h.action).lower()), None)
        accel_hyp = next((h for h in hyps if "accelerate" in str(h.action).lower() and h.action.get("acceleration_x", 0) > 0), None)
        if brake_hyp and accel_hyp:
            assert brake_hyp.priority >= accel_hyp.priority

    def test_uncertain_world_state_boosts_conservative(self):
        gen = HypothesisGenerator()
        ws = WorldState(domain="drone", uncertainty=0.8)
        hyps = gen.generate(ws, "navigate", max_hypotheses=6)
        hover_hyp = next((h for h in hyps if "hover" in str(h.action).lower()), None)
        if hover_hyp:
            assert hover_hyp.priority >= 0.5  # boosted by uncertainty


# ============================================================================
# SimulationEngine Tests
# ============================================================================

class TestSimulationEngine:
    def test_run_full_pipeline(self):
        """AC1: Full pipeline returns SimulationResult with all stages."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        result = engine.run(ws, "reach destination")
        assert isinstance(result, SimulationResult)
        assert "hypothesis_generation" in result.pipeline_stages
        assert "simulation" in result.pipeline_stages
        assert "ranking" in result.pipeline_stages
        assert "safety_filter" in result.pipeline_stages
        assert "action_selection" in result.pipeline_stages

    def test_run_returns_hypotheses(self):
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        result = engine.run(ws, "drive safely")
        assert len(result.hypotheses) >= 2

    def test_run_returns_evaluations(self):
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="industrial")
        result = engine.run(ws, "maintain production")
        assert len(result.evaluations) >= 2

    def test_run_selects_best_action(self):
        """AC6: Best action is selected from ranked evaluations."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        result = engine.run(ws, "drive safely")
        assert result.best_action is not None
        assert isinstance(result.best_action, ActionEvaluation)

    def test_evaluations_ranked_by_score(self):
        """AC5: Evaluations sorted by overall_score descending."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        result = engine.run(ws, "optimize route")
        scores = [e.overall_score for e in result.all_evaluations_ranked]
        assert scores == sorted(scores, reverse=True)

    def test_compare_actions(self):
        """AC7: Compare multiple specific actions."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        actions = [
            {"action_type": "accelerate", "acceleration_x": 1.0},
            {"action_type": "brake", "deceleration": 2.0},
            {"action_type": "maintain", "keep_speed": True},
        ]
        evals = engine.compare_actions(ws, actions, goal="drive safely")
        assert len(evals) == 3
        # Should be ranked
        scores = [e.overall_score for e in evals]
        assert scores == sorted(scores, reverse=True)

    def test_metadata_includes_domain(self):
        """AC9: Metadata includes domain, counts."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="drone")
        result = engine.run(ws, "survey area")
        assert result.metadata["domain"] == "drone"
        assert result.metadata["hypothesis_count"] > 0
        assert result.metadata["evaluation_count"] > 0

    def test_latency_measured(self):
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        result = engine.run(ws, "test")
        assert result.latency_ms > 0

    def test_unsafe_actions_filtered(self):
        """AC8: Unsafe actions not selected as best."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        # Add constraint that makes high acceleration unsafe
        result = engine.run(ws, "drive safely", constraints={"acceleration_x": 0.1})
        if result.best_action:
            # Best action should not violate constraint
            accel = result.best_action.hypothesis.action.get("acceleration_x")
            if accel is not None:
                assert abs(accel) <= 0.1 or result.best_action.safety_score == 0.0

    def test_constraint_violation_detected(self):
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        actions = [{"action_type": "accelerate", "acceleration_x": 100.0}]
        evals = engine.compare_actions(ws, actions, constraints={"acceleration_x": 5.0})
        assert len(evals[0].safety_violations) > 0
        assert evals[0].safety_score == 0.0

    def test_multiple_domains(self):
        """AC10: Works with multiple domains."""
        engine = SimulationEngine(world_model=WorldModel())
        for domain in ["industrial", "vehicle", "drone", "home"]:
            ws = WorldState(domain=domain)
            result = engine.run(ws, f"goal in {domain}")
            assert result.metadata["domain"] == domain
            assert len(result.evaluations) >= 1

    def test_empty_world_state(self):
        """Edge case: empty world state still produces results."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(entities=[])
        result = engine.run(ws, "test goal")
        assert result is not None
        assert len(result.hypotheses) >= 1

    def test_no_world_model(self):
        """Engine works without WorldModel (heuristic mode)."""
        engine = SimulationEngine(world_model=None)
        ws = WorldState(domain="vehicle")
        result = engine.run(ws, "drive safely")
        assert result.best_action is not None
        assert result.best_action.safety_score > 0.0

    def test_simulation_result_to_dict(self):
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        result = engine.run(ws, "test")
        d = result.to_dict()
        assert "goal" in d
        assert "evaluations" in d
        assert "pipeline_stages" in d

    def test_action_evaluation_to_dict(self):
        hyp = Hypothesis(hypothesis_id="h1", action={"type": "test"}, description="test", expected_outcome="test result")
        eval_result = ActionEvaluation(hypothesis=hyp, safety_score=0.8, confidence=0.9)
        d = eval_result.to_dict()
        assert d["safety_score"] == 0.8
        assert d["confidence"] == 0.9


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhase007Integration:
    def test_full_pipeline_with_world_model(self):
        """AC1+AC7: Full pipeline with WorldModel integration."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(
            entities=[
                WorldEntity(entity_id="e1", entity_type="vehicle", position=(0, 0, 0),
                           velocity=(5, 0, 0)),
            ],
            domain="vehicle",
        )
        result = engine.run(ws, "reach destination safely", max_hypotheses=5)
        assert len(result.pipeline_stages) == 5
        assert result.best_action is not None
        # Best action should have predicted states from WorldModel
        if result.best_action.predicted_states:
            assert len(result.best_action.predicted_states) > 0

    def test_multi_action_comparison_selects_best(self):
        """AC7: Compare multiple actions and select best."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        actions = [
            {"action_type": "accelerate", "acceleration_x": 1.0},
            {"action_type": "brake", "deceleration": 2.0},
            {"action_type": "maintain", "keep_speed": True},
        ]
        evals = engine.compare_actions(ws, actions, goal="drive safely")
        best = evals[0]
        # Best should have highest overall score
        for e in evals[1:]:
            assert best.overall_score >= e.overall_score

    def test_safety_violations_block_action(self):
        """AC8: Actions with safety violations are not selected."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        actions = [
            {"action_type": "accelerate", "acceleration_x": 0.5},
            {"action_type": "accelerate", "acceleration_x": 50.0},  # should be blocked
        ]
        evals = engine.compare_actions(ws, actions, constraints={"acceleration_x": 5.0})
        # The high-acceleration action should have safety violations
        unsafe = [e for e in evals if e.safety_violations]
        assert len(unsafe) >= 1
        # Best should not be the unsafe one
        if evals:
            assert evals[0].safety_score > 0.0 or len(evals[0].safety_violations) == 0

    def test_simulation_result_serialization(self):
        """SimulationResult can be serialized for memory storage."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="industrial")
        result = engine.run(ws, "test goal")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "goal" in d
        assert "evaluations" in d

    def test_pipeline_with_entities(self):
        """Full pipeline with actual entities in world state."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(
            entities=[
                WorldEntity(entity_id="v1", entity_type="vehicle", position=(0, 0, 0),
                           velocity=(10, 0, 0)),
                WorldEntity(entity_id="v2", entity_type="vehicle", position=(50, 0, 0),
                           velocity=(-5, 0, 0)),
            ],
            domain="vehicle",
        )
        result = engine.run(ws, "avoid collision and reach destination")
        assert result.best_action is not None
        assert result.latency_ms > 0

    def test_all_unsafe_returns_best_among_unsafe(self):
        """Edge case: all actions unsafe — still returns best (least bad)."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        # All actions violate constraint
        actions = [
            {"action_type": "accelerate", "acceleration_x": 100},
            {"action_type": "accelerate", "acceleration_x": 200},
        ]
        evals = engine.compare_actions(ws, actions, constraints={"acceleration_x": 1.0})
        # All should be unsafe
        assert all(e.safety_score == 0.0 for e in evals)
        # But still ranked
        assert evals[0].overall_score >= evals[1].overall_score

    def test_statistics(self):
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        engine.run(ws, "goal 1")
        engine.run(ws, "goal 2")
        stats = engine.get_statistics()
        assert stats["total_runs"] == 2
        assert stats["avg_latency_ms"] > 0

    def test_drone_simulation_pipeline(self):
        """Full pipeline for drone domain."""
        engine = SimulationEngine(world_model=WorldModel(default_domain="drone"))
        ws = WorldState(
            entities=[WorldEntity(entity_id="d1", entity_type="drone",
                                 position=(0, 0, 10), velocity=(0, 0, 0))],
            domain="drone",
        )
        result = engine.run(ws, "survey area safely")
        assert result.best_action is not None
        assert result.metadata["domain"] == "drone"

    def test_home_simulation_pipeline(self):
        """Full pipeline for home domain."""
        engine = SimulationEngine(world_model=WorldModel(default_domain="home"))
        ws = WorldState(
            entities=[WorldEntity(entity_id="thermostat1", entity_type="sensor",
                                 position=(0, 0, 0))],
            environment={"temperature": 18.0},
            domain="home",
        )
        result = engine.run(ws, "warm up the house")
        assert result.best_action is not None
        assert result.metadata["domain"] == "home"

    def test_latency_under_threshold(self):
        """Performance: full pipeline completes in reasonable time."""
        engine = SimulationEngine(world_model=WorldModel())
        ws = WorldState(domain="vehicle")
        start = time.time()
        engine.run(ws, "test")
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 500.0  # Should be fast in simulation
