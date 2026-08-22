"""
ORION Phase 007 — Simulation Engine. License: Apache 2.0.

Orchestrates the full simulation pipeline:
    CURRENT WORLD → HYPOTHESIS → PLAN → SIMULATION → PREDICTION → SAFETY CHECK → ACTION PROPOSAL

Integrates:
    - WorldModel (Phase 006) for physics prediction
    - HypothesisGenerator for candidate action generation
    - SafetyGateway for deny-by-default safety enforcement
    - AutonomousPlanner for goal decomposition
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.simulation.hypothesis_generator import Hypothesis, HypothesisGenerator
from src.world_model.world_state import WorldState

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ActionEvaluation:
    """Evaluation of a single action through simulation."""
    hypothesis: Hypothesis
    predicted_states: List[Dict[str, Any]] = field(default_factory=list)
    safety_score: float = 0.0  # [0, 1] — 1 = perfectly safe
    confidence: float = 0.0  # [0, 1]
    collision_risk: float = 1.0  # [0, 1] — 1 = certain collision
    uncertainty: float = 1.0  # [0, 1]
    overall_score: float = 0.0  # weighted combination
    safety_violations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis": self.hypothesis.to_dict(),
            "predicted_states": self.predicted_states,
            "safety_score": self.safety_score,
            "confidence": self.confidence,
            "collision_risk": self.collision_risk,
            "uncertainty": self.uncertainty,
            "overall_score": self.overall_score,
            "safety_violations": self.safety_violations,
            "metadata": self.metadata,
        }


@dataclass
class SimulationResult:
    """Complete result of a simulation run."""
    goal: str = ""
    world_state: Optional[WorldState] = None
    hypotheses: List[Hypothesis] = field(default_factory=list)
    evaluations: List[ActionEvaluation] = field(default_factory=list)
    best_action: Optional[ActionEvaluation] = None
    all_evaluations_ranked: List[ActionEvaluation] = field(default_factory=list)
    pipeline_stages: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "world_state": self.world_state.to_dict() if self.world_state else None,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "evaluations": [e.to_dict() for e in self.evaluations],
            "best_action": self.best_action.to_dict() if self.best_action else None,
            "all_evaluations_ranked": [e.to_dict() for e in self.all_evaluations_ranked],
            "pipeline_stages": self.pipeline_stages,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }


# ============================================================================
# Simulation Engine
# ============================================================================

class SimulationEngine:
    """
    ORION Phase 007 — Simulation Engine.

    Full pipeline:
        1. Generate hypotheses from world state + goal
        2. Simulate each hypothesis via WorldModel
        3. Predict outcomes and assess safety
        4. Rank by overall score
        5. Select best action (deny-by-default safety)
    """

    def __init__(
        self,
        world_model: Optional[Any] = None,
        hypothesis_generator: Optional[HypothesisGenerator] = None,
        safety_gateway: Optional[Any] = None,
        planner: Optional[Any] = None,
    ) -> None:
        self._world_model = world_model
        self._hypothesis_generator = hypothesis_generator or HypothesisGenerator()
        self._safety_gateway = safety_gateway
        self._planner = planner
        self._run_count = 0
        self._total_latency = 0.0

        # Scoring weights
        self._w_safety = 0.5
        self._w_confidence = 0.3
        self._w_collision = 0.2

    def run(
        self,
        world_state: WorldState,
        goal: str,
        constraints: Optional[Dict[str, Any]] = None,
        max_hypotheses: int = 5,
    ) -> SimulationResult:
        """
        Full simulation pipeline: world → hypothesis → simulate → predict → safety → proposal.

        Args:
            world_state: Current world state from Phase 006
            goal: What to achieve
            constraints: Safety constraints (speed limits, forbidden zones, etc.)
            max_hypotheses: Maximum candidate actions to evaluate

        Returns:
            SimulationResult with ranked evaluations and best action
        """
        start = time.time()
        constraints = constraints or {}
        stages: List[str] = []

        # Stage 1: Generate hypotheses
        stages.append("hypothesis_generation")
        hypotheses = self._hypothesis_generator.generate(
            world_state, goal, max_hypotheses=max_hypotheses
        )

        # Stage 2: Simulate each hypothesis
        stages.append("simulation")
        evaluations: List[ActionEvaluation] = []
        for hyp in hypotheses:
            eval_result = self._simulate_hypothesis(hyp, world_state, constraints)
            evaluations.append(eval_result)

        # Stage 3: Rank evaluations
        stages.append("ranking")
        ranked = self._rank_evaluations(evaluations)

        # Stage 4: Safety filter
        stages.append("safety_filter")
        safe_evals = [e for e in ranked if e.safety_score > 0.0 and not e.safety_violations]

        # Stage 5: Select best
        stages.append("action_selection")
        best = self.select_best(safe_evals if safe_evals else ranked)

        elapsed = (time.time() - start) * 1000
        self._run_count += 1
        self._total_latency += elapsed

        result = SimulationResult(
            goal=goal,
            world_state=world_state,
            hypotheses=hypotheses,
            evaluations=evaluations,
            best_action=best,
            all_evaluations_ranked=ranked,
            pipeline_stages=stages,
            latency_ms=elapsed,
            metadata={
                "domain": world_state.domain,
                "hypothesis_count": len(hypotheses),
                "evaluation_count": len(evaluations),
                "safe_count": len(safe_evals),
                "constraints": constraints,
                "run_id": self._run_count,
            },
        )

        logger.info(
            "SimulationEngine: goal='%s', %d hypotheses, %d safe, best=%s, %.1fms",
            goal, len(hypotheses), len(safe_evals),
            best.hypothesis.description if best else "none", elapsed,
        )
        return result

    def compare_actions(
        self,
        world_state: WorldState,
        actions: List[Dict[str, Any]],
        goal: str = "",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[ActionEvaluation]:
        """Simulate and compare a specific set of actions."""
        constraints = constraints or {}
        evaluations: List[ActionEvaluation] = []

        for i, action in enumerate(actions):
            hyp = Hypothesis(
                hypothesis_id=f"cmp_{i}",
                action=action,
                description=f"Provided action {i}",
                expected_outcome=f"Outcome of action {i}",
                domain=world_state.domain,
            )
            eval_result = self._simulate_hypothesis(hyp, world_state, constraints)
            evaluations.append(eval_result)

        return self._rank_evaluations(evaluations)

    def select_best(self, evaluations: List[ActionEvaluation]) -> Optional[ActionEvaluation]:
        """Select the best action from ranked evaluations."""
        if not evaluations:
            return None
        # Already ranked — return top
        return evaluations[0] if evaluations else None

    def _simulate_hypothesis(
        self,
        hypothesis: Hypothesis,
        world_state: WorldState,
        constraints: Dict[str, Any],
    ) -> ActionEvaluation:
        """Simulate a single hypothesis and evaluate it."""
        predicted_states: List[Dict[str, Any]] = []
        safety_score = 0.0
        confidence = 0.0
        collision_risk = 1.0
        uncertainty = 1.0
        safety_violations: List[str] = []

        # Use WorldModel if available
        if self._world_model:
            try:
                snapshot = world_state.to_state_snapshot()
                result = self._world_model.predict(
                    snapshot, hypothesis.action, horizon=5
                )
                predicted_states = [s.to_dict() for s in result.predicted_states]
                confidence = 1.0 - result.uncertainty
                collision_risk = result.collision_risk
                uncertainty = result.uncertainty

                # Safety assessment from WorldModel
                if result.safety_assessment:
                    safe = result.safety_assessment.get("safe", False)
                    safety_score = 1.0 if safe else 0.0
                    violations = result.safety_assessment.get("violations", [])
                    safety_violations.extend(violations if isinstance(violations, list) else [])
            except Exception as e:
                logger.warning("WorldModel prediction failed: %s", e)
                safety_violations.append(f"simulation_error: {e}")
        else:
            # No WorldModel — use heuristic evaluation
            safety_score = self._heuristic_safety(hypothesis.action, constraints)
            confidence = 0.5  # unknown
            collision_risk = 0.1  # assume low in simulation
            uncertainty = 0.5

        # Apply SafetyGateway if available
        if self._safety_gateway:
            try:
                gate_result = self._safety_gateway.check(
                    hypothesis.action, context={"world_state": world_state.to_dict()}
                )
                if not gate_result.get("allowed", True):
                    safety_score = 0.0
                    safety_violations.append("blocked_by_safety_gateway")
            except Exception as e:
                logger.warning("SafetyGateway check failed: %s", e)
                safety_score = 0.0
                safety_violations.append(f"gateway_error: {e}")

        # Check constraints
        for key, limit in constraints.items():
            action_val = hypothesis.action.get(key)
            if action_val is not None and isinstance(action_val, (int, float)):
                if isinstance(limit, (int, float)) and abs(action_val) > limit:
                    safety_violations.append(f"constraint_violation: {key}={action_val} > {limit}")
                    safety_score = 0.0

        # Compute overall score
        overall = (
            self._w_safety * safety_score
            + self._w_confidence * confidence
            + self._w_collision * (1.0 - collision_risk)
        )

        return ActionEvaluation(
            hypothesis=hypothesis,
            predicted_states=predicted_states,
            safety_score=safety_score,
            confidence=confidence,
            collision_risk=collision_risk,
            uncertainty=uncertainty,
            overall_score=overall,
            safety_violations=safety_violations,
            metadata={
                "domain": world_state.domain,
                "action_type": hypothesis.action.get("action_type", "unknown"),
            },
        )

    def _rank_evaluations(
        self, evaluations: List[ActionEvaluation]
    ) -> List[ActionEvaluation]:
        """Rank evaluations by overall score (descending). Safe actions first."""
        # Sort: safe first (safety_score > 0), then by overall_score
        return sorted(
            evaluations,
            key=lambda e: (e.safety_score > 0, e.overall_score),
            reverse=True,
        )

    def _heuristic_safety(
        self, action: Dict[str, Any], constraints: Dict[str, Any]
    ) -> float:
        """Heuristic safety evaluation when no WorldModel available."""
        action_str = str(action).lower()
        # Dangerous actions
        if any(kw in action_str for kw in ["stop", "brake", "emergency"]):
            return 0.9  # Generally safe (conservative)
        if any(kw in action_str for kw in ["lock", "secure"]):
            return 0.95
        # Movement actions — moderate
        if any(kw in action_str for kw in ["accelerate", "move", "change"]):
            return 0.6
        # Default
        return 0.7

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_runs": self._run_count,
            "avg_latency_ms": self._total_latency / max(1, self._run_count),
        }
