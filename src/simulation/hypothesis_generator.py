"""
ORION Phase 007 — Hypothesis Generator. License: Apache 2.0.

Generates candidate action hypotheses from world state + goal.
Each hypothesis is a proposed action with expected outcome.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.world_model.world_state import WorldState

logger = logging.getLogger(__name__)


@dataclass
class Hypothesis:
    """A candidate action with expected outcome."""
    hypothesis_id: str
    action: Dict[str, Any]
    description: str
    expected_outcome: str
    domain: str = "industrial"
    priority: float = 0.5  # [0, 1] — higher = more promising
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "action": self.action,
            "description": self.description,
            "expected_outcome": self.expected_outcome,
            "domain": self.domain,
            "priority": self.priority,
            "created_at": self.created_at,
        }


class HypothesisGenerator:
    """
    Generates candidate actions from world state + goal.

    Strategy:
    1. Analyze world state for relevant entities and relationships
    2. Map goal to domain-specific action templates
    3. Generate variations (intensities, directions, targets)
    4. Prioritize by heuristic (proximity, feasibility, safety hint)
    """

    # Domain-specific action templates
    _ACTION_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
        "industrial": [
            {"action_type": "adjust_speed", "speed_delta": -0.1},
            {"action_type": "adjust_speed", "speed_delta": 0.1},
            {"action_type": "adjust_speed", "speed_delta": 0.0},
            {"action_type": "stop", "target": "all"},
            {"action_type": "route_change", "destination": "maintenance"},
        ],
        "vehicle": [
            {"action_type": "accelerate", "acceleration_x": 1.0},
            {"action_type": "accelerate", "acceleration_x": -1.0},
            {"action_type": "accelerate", "acceleration_x": 0.5},
            {"action_type": "brake", "deceleration": 2.0},
            {"action_type": "lane_change", "direction": "left"},
            {"action_type": "lane_change", "direction": "right"},
            {"action_type": "maintain", "keep_speed": True},
        ],
        "drone": [
            {"action_type": "ascend", "altitude_delta": 5.0},
            {"action_type": "descend", "altitude_delta": -5.0},
            {"action_type": "hover", "hold_position": True},
            {"action_type": "move_forward", "velocity_x": 2.0},
            {"action_type": "move_backward", "velocity_x": -2.0},
            {"action_type": "rotate", "angular_velocity": 0.5},
        ],
        "home": [
            {"action_type": "set_temperature", "target_temp": 20.0},
            {"action_type": "set_temperature", "target_temp": 22.0},
            {"action_type": "set_temperature", "target_temp": 24.0},
            {"action_type": "toggle_lights", "state": "on"},
            {"action_type": "toggle_lights", "state": "off"},
            {"action_type": "lock_doors", "state": "locked"},
        ],
    }

    def __init__(self, max_hypotheses: int = 5) -> None:
        self._max_hypotheses = max_hypotheses
        self._generation_count = 0

    def generate(self, world_state: WorldState, goal: str,
                max_hypotheses: Optional[int] = None) -> List[Hypothesis]:
        """Generate candidate hypotheses from world state + goal."""
        start = time.time()
        limit = max_hypotheses or self._max_hypotheses
        domain = world_state.domain

        templates = self._ACTION_TEMPLATES.get(domain, self._ACTION_TEMPLATES["industrial"])

        # Generate hypotheses from templates
        hypotheses: List[Hypothesis] = []
        for i, template in enumerate(templates[:limit]):
            h_id = f"hyp_{self._generation_count}_{i}"
            description = f"Action: {template.get('action_type', 'unknown')} in {domain}"
            expected = self._predict_outcome(template, goal)

            # Compute priority based on goal relevance
            priority = self._compute_priority(template, goal, world_state)

            hypotheses.append(Hypothesis(
                hypothesis_id=h_id,
                action=dict(template),
                description=description,
                expected_outcome=expected,
                domain=domain,
                priority=priority,
            ))

        # Sort by priority (highest first)
        hypotheses.sort(key=lambda h: h.priority, reverse=True)

        self._generation_count += 1
        elapsed = (time.time() - start) * 1000
        logger.debug("HypothesisGenerator: %d hypotheses, %.1fms", len(hypotheses), elapsed)
        return hypotheses

    def _predict_outcome(self, action: Dict[str, Any], goal: str) -> str:
        """Generate a simple expected outcome description."""
        action_type = action.get("action_type", "unknown")
        if "speed" in action_type or "accelerate" in action_type:
            return f"Adjust velocity to progress toward: {goal}"
        elif "brake" in action_type or "stop" in action_type:
            return f"Reduce speed for safety regarding: {goal}"
        elif "lane_change" in action_type or "route" in action_type:
            return f"Change path to optimize: {goal}"
        elif "ascend" in action_type or "descend" in action_type:
            return f"Adjust altitude for: {goal}"
        elif "hover" in action_type or "maintain" in action_type:
            return f"Maintain current state for: {goal}"
        elif "temperature" in action_type:
            return f"Adjust environment for: {goal}"
        else:
            return f"Execute {action_type} for: {goal}"

    def _compute_priority(self, action: Dict[str, Any], goal: str,
                          world_state: WorldState) -> float:
        """Compute heuristic priority for an action given goal and world state."""
        base = 0.5
        goal_lower = goal.lower()

        # Boost safety-related actions
        if any(kw in goal_lower for kw in ["safe", "stop", "avoid", "prevent"]):
            if any(kw in str(action).lower() for kw in ["brake", "stop", "lock", "hover"]):
                base += 0.2

        # Boost movement actions if goal mentions movement
        if any(kw in goal_lower for kw in ["move", "go", "reach", "arrive", "travel"]):
            if any(kw in str(action).lower() for kw in ["accelerate", "move", "forward", "ascend"]):
                base += 0.2

        # Boost efficiency actions
        if any(kw in goal_lower for kw in ["optimize", "efficient", "best"]):
            if any(kw in str(action).lower() for kw in ["maintain", "keep", "route"]):
                base += 0.15

        # Consider world state uncertainty
        if world_state.uncertainty > 0.5:
            if "maintain" in str(action).lower() or "hover" in str(action).lower():
                base += 0.1  # Conservative when uncertain

        return min(1.0, base)

    def get_statistics(self) -> Dict[str, Any]:
        return {"total_generations": self._generation_count}
