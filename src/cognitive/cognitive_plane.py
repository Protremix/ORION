"""ORION Cognitive Plane Implementation (Architecture v0.5).

The Cognitive Plane is responsible for high-level reasoning, goal decomposition,
multi-step planning, constraint satisfaction, and risk assessment.

In Phase 1, it operates in a cloud-only simulation environment using OpenAI GPT models
(GPT-4o / GPT-5.6). It consumes BeliefState contracts from the State Plane and
produces Goal and ActionProposal contracts. Crucially, it NEVER directly commands
actuators; all proposed actions are routed to Action Arbitration.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Lazy import - openai is only loaded when GPT reasoning is actually invoked.
# This prevents sys.modules pollution that would trigger safety independence test failures.
HAS_OPENAI = True

from src.monitoring.gpt_monitor import GPTIntegrationMonitor

def _get_openai_client():
    """Lazily import and create OpenAI client only when needed."""
    from openai import OpenAI
    return OpenAI(api_key=os.environ.get("OPENAI_PROJECT_KEY"))

from src.contracts import (
    ActionProposal,
    BeliefState,
    Envelope,
    Goal,
    GoalSource,
    GoalType,
    generate_uuid,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are the Cognitive Plane of ORION (Physical Intelligence OS v0.5).
Your role is high-level reasoning, task decomposition, multi-step action planning, constraint satisfaction, and risk assessment.

CRITICAL ARCHITECTURAL INVARIANTS:
1. You do NOT directly command actuators. You ONLY produce candidate ActionProposals for Action Arbitration.
2. For EVERY ActionProposal you MUST include:
   - risk_tier: 1 (Low), 2 (Medium), or 3 (High/Critical)
   - hazards: array of strings identifying physical or operational risks
   - mitigations: array of strings describing safety mitigations
   - preconditions: object specifying required physical state before execution
   - expected_postconditions: object describing expected outcome after execution
   - cognitive_confidence: float between 0.0 and 1.0

Output MUST be a valid JSON object with the following format:
{
  "goals": [
    {
      "goal_type": "reach_state" | "maintain_state" | "avoid_state" | "optimize",
      "goal_parameters": { ... },
      "priority": 1 | 2 | 3 | 4,
      "source": "operator" | "autonomous" | "founder" | "safety",
      "justification": "Explanation of goal creation"
    }
  ],
  "action_proposals": [
    {
      "action_type": "move_to" | "set_velocity" | "rotate" | "scan" | "stop",
      "target_entity": "string entity id",
      "action_parameters": { ... },
      "expected_duration": uint32_ms,
      "risk_tier": 1 | 2 | 3,
      "hazards": ["hazard 1", "hazard 2"],
      "mitigations": ["mitigation 1"],
      "preconditions": { ... },
      "expected_postconditions": { ... },
      "cognitive_confidence": 0.0 to 1.0
    }
  ]
}
"""


class CognitivePlane:
    """Cognitive Plane orchestrating reasoning, planning, and goal decomposition."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        enable_llm: bool = True,
    ) -> None:
        """Initialize Cognitive Plane with OpenAI client or fallback planner.

        Args:
            api_key: Optional OpenAI API key. Defaults to $OPENAI_API_KEY or $OPENAI_PROJECT_KEY.
            model: OpenAI model identifier (default: "gpt-4o").
            enable_llm: Whether to attempt OpenAI LLM reasoning when API key is available.
        """
        self.model = model
        self.enable_llm = enable_llm
        self.client: Optional[Any] = None

        resolved_key = (
            api_key
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENAI_PROJECT_KEY")
        )

        if self.enable_llm and HAS_OPENAI and resolved_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=resolved_key)
                logger.info(f"Cognitive Plane initialized with OpenAI model: {self.model}")
            except Exception as err:
                logger.warning(f"Failed to initialize OpenAI client: {err}. Falling back to deterministic planner.")
                self.client = None
        else:
            if self.enable_llm and not resolved_key:
                logger.info("No OpenAI API key found in environment; Cognitive Plane running in deterministic simulation fallback mode.")
            elif not HAS_OPENAI:
                logger.info("OpenAI package not installed; running in deterministic simulation fallback mode.")

        self._active_goals: List[Goal] = []
        self._history: List[Dict[str, Any]] = []
        self.monitor = GPTIntegrationMonitor()

    def process_belief_state(
        self,
        belief_state: BeliefState,
        high_level_instruction: Optional[str] = None,
    ) -> Dict[str, List[Union[Goal, ActionProposal]]]:
        """Main entry point: process world belief state and high level instruction to generate Goals and ActionProposals.

        Args:
            belief_state: Current BeliefState contract from State Plane.
            high_level_instruction: Optional user or high-level system instruction.

        Returns:
            Dict containing 'goals' (List[Goal]) and 'action_proposals' (List[ActionProposal]).
        """
        instruction = high_level_instruction or "Navigate safely and maintain operational state."

        if self.client is not None and self.monitor.should_call_gpt():
            try:
                t0 = time.monotonic()
                result = self._reason_with_gpt(belief_state, instruction)
                elapsed_ms = (time.monotonic() - t0) * 1000

                # Record successful call
                goals = result.get("goals", [])
                proposals = result.get("action_proposals", [])
                conf = proposals[0].cognitive_confidence if proposals else 0.0

                self.monitor.record_call(
                    duration_ms=elapsed_ms,
                    success=True,
                    token_count=0,  # OpenAI response doesn't expose tokens in our wrapper
                    response_has_goals=len(goals) > 0,
                    response_has_proposals=len(proposals) > 0,
                    confidence=conf,
                    used_fallback=False,
                )

                self._active_goals = goals
                return result
            except Exception as err:
                logger.error(f"Error during OpenAI LLM reasoning: {err}. Using deterministic fallback.")
                self.monitor.record_call(
                    duration_ms=0,
                    success=False,
                    error=str(err),
                    used_fallback=True,
                )

        # Fallback deterministic planner
        result = self._reason_deterministic(belief_state, instruction)
        if self.client is not None:
            # We have a client but circuit breaker may be open
            self.monitor.record_call(
                duration_ms=0,
                success=False,
                error="circuit_breaker_open" if not self.monitor.should_call_gpt() else "no_client",
                used_fallback=True,
            )
        return result

    def decompose_goal(
        self,
        high_level_instruction: str,
        belief_state: BeliefState,
    ) -> List[Goal]:
        """Decompose a high-level instruction into structured Goal contracts."""
        res = self.process_belief_state(belief_state, high_level_instruction)
        return res["goals"]  # type: ignore

    def plan_actions(
        self,
        goals: List[Goal],
        belief_state: BeliefState,
    ) -> List[ActionProposal]:
        """Generate multi-step ActionProposals to fulfill active goals given current BeliefState."""
        res = self.process_belief_state(belief_state, f"Fulfill {len(goals)} active goals.")
        return res["action_proposals"]  # type: ignore

    def assess_risk(
        self,
        action_type: str,
        action_parameters: Dict[str, Any],
        belief_state: BeliefState,
    ) -> Dict[str, Any]:
        """Perform risk assessment and constraint satisfaction check for a proposed action.

        Returns:
            Dict with 'risk_tier' (1, 2, 3), 'hazards' list, and 'mitigations' list.
        """
        hazards: List[str] = []
        mitigations: List[str] = []
        risk_tier = 1

        # Check target position against known objects/obstacles
        target_x = action_parameters.get("target_x", action_parameters.get("x"))
        target_y = action_parameters.get("target_y", action_parameters.get("y"))

        curr_x, curr_y = belief_state.position[0], belief_state.position[1]

        if target_x is not None and target_y is not None:
            dist = math.hypot(target_x - curr_x, target_y - curr_y)
            if dist > 20.0:
                hazards.append("Long range movement outside local visual horizon")
                mitigations.append("Intermediate waypoint step and continuous lidar sensing")
                risk_tier = max(risk_tier, 2)

            # Check proximity to objects in belief state
            for obj in belief_state.objects:
                obj_x = obj.get("position", [0, 0])[0]
                obj_y = obj.get("position", [0, 0])[1]
                obj_dist = math.hypot(target_x - obj_x, target_y - obj_y)
                if obj_dist < 1.0:
                    hazards.append(f"Target location near obstacle '{obj.get('id', 'unknown')}'")
                    mitigations.append("Reduce movement speed to < 0.2 m/s and activate CBF safety boundary")
                    risk_tier = max(risk_tier, 2)
                if obj_dist < 0.3:
                    hazards.append(f"Potential immediate collision with obstacle '{obj.get('id', 'unknown')}'")
                    mitigations.append("Require Action Arbitration review and Tier 3 safety gate approval")
                    risk_tier = 3

        # Speed risk evaluation
        speed = action_parameters.get("speed", 0.0)
        if speed > 2.0:
            hazards.append("High linear velocity (> 2.0 m/s)")
            mitigations.append("Mandatory rate limiter and E-stop arming")
            risk_tier = max(risk_tier, 2)

        if action_type in ("stop", "emergency_stop"):
            risk_tier = 1
            hazards.append("Sudden halt")
            mitigations.append("Controlled deceleration profile")

        return {
            "risk_tier": risk_tier,
            "hazards": hazards,
            "mitigations": mitigations,
        }

    def _reason_with_gpt(
        self,
        belief_state: BeliefState,
        instruction: str,
    ) -> Dict[str, List[Union[Goal, ActionProposal]]]:
        """Query GPT-4o for goal decomposition, planning, and risk assessment."""
        if self.client is None:
            raise RuntimeError("OpenAI client not initialized.")

        prompt = {
            "instruction": instruction,
            "belief_state": {
                "state_revision": belief_state.state_revision,
                "position": belief_state.position,
                "velocity": belief_state.velocity,
                "orientation": belief_state.orientation,
                "objects": belief_state.objects,
                "uncertainty": belief_state.uncertainty,
                "staleness_ns": belief_state.staleness,
                "sensor_health": belief_state.sensor_health,
            },
        }

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(prompt, indent=2)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)

        return self._parse_llm_json(parsed, belief_state)

    def _parse_llm_json(
        self,
        parsed: Dict[str, Any],
        belief_state: BeliefState,
    ) -> Dict[str, List[Union[Goal, ActionProposal]]]:
        """Convert LLM JSON output into strict Goal and ActionProposal contracts."""
        goals: List[Goal] = []
        action_proposals: List[ActionProposal] = []

        correlation_id = belief_state.envelope.correlation_id

        # Parse goals
        for g_data in parsed.get("goals", []):
        
            g = Goal(
                goal_type=g_data.get("goal_type", GoalType.REACH_STATE.value),
                goal_parameters=g_data.get("goal_parameters", {}),
                priority=g_data.get("priority", 2),
                source=g_data.get("source", GoalSource.OPERATOR.value),
                justification=g_data.get("justification", "Generated via GPT reasoning"),
            )
            goals.append(g)

        # Parse action proposals
        for idx, a_data in enumerate(parsed.get("action_proposals", [])):
        

            # Ensure mandatory risk assessment structure
            risk_tier = a_data.get("risk_tier", 1)
            hazards = a_data.get("hazards", [])
            mitigations = a_data.get("mitigations", [])

            risk_assessment = {
                "risk_tier": risk_tier,
                "hazards": hazards if isinstance(hazards, list) else [str(hazards)],
                "mitigations": mitigations if isinstance(mitigations, list) else [str(mitigations)],
            }

            p_id = goals[0].envelope.contract_id if goals else generate_uuid()

            prop = ActionProposal(
                goal_id=p_id,
                action_type=a_data.get("action_type", "move_to"),
                target_entity=a_data.get("target_entity", "mobile_base_0"),
                action_parameters=a_data.get("action_parameters", {}),
                estimated_duration_ms=a_data.get("expected_duration", 1000),
                risk_assessment=risk_assessment,
                preconditions=a_data.get("preconditions", {"position": belief_state.position}),
                expected_postconditions=a_data.get("expected_postconditions", {"status": "reached"}),
                cognitive_confidence=float(a_data.get("cognitive_confidence", 0.9)),
            )
            action_proposals.append(prop)

        return {"goals": goals, "action_proposals": action_proposals}

    def _reason_deterministic(
        self,
        belief_state: BeliefState,
        instruction: str,
    ) -> Dict[str, List[Union[Goal, ActionProposal]]]:
        """Deterministic fallback planning algorithm when LLM is offline or disabled."""
        correlation_id = belief_state.envelope.correlation_id
        target_x, target_y = 5.0, 5.0

        # Parse potential coordinate in instruction (e.g. "x=8, y=8" or "(8, 8)")
        import re
        coords = re.findall(r"[-+]?\d*\.\d+|\d+", instruction)
        if len(coords) >= 2:
            try:
                target_x, target_y = float(coords[0]), float(coords[1])
            except ValueError:
                pass

        # Goal creation
        
        goal = Goal(
            goal_type=GoalType.REACH_STATE.value,
            goal_parameters={"target_position": [target_x, target_y, 0.0]},
            priority=2,
            source=GoalSource.OPERATOR.value,
            justification=f"Decomposed instruction: '{instruction}'",
        )

        curr_x, curr_y = belief_state.position[0], belief_state.position[1]
        dx, dy = target_x - curr_x, target_y - curr_y
        dist = math.hypot(dx, dy)

        action_proposals: List[ActionProposal] = []

        if dist > 0.1:
            # Plan movement
            heading = math.atan2(dy, dx)
            speed = min(1.0, dist)

            risk_eval = self.assess_risk(
                "move_to",
                {"target_x": target_x, "target_y": target_y, "speed": speed},
                belief_state,
            )
        

            expected_duration = int((dist / max(speed, 0.1)) * 1000)

            proposal = ActionProposal(
                goal_id=goal.envelope.contract_id,
                action_type="move_to",
                target_entity="mobile_base_0",
                action_parameters={
                    "target_x": target_x,
                    "target_y": target_y,
                    "target_heading": heading,
                    "linear_velocity": speed,
                },
                estimated_duration_ms=expected_duration,
                risk_assessment=risk_eval,
                preconditions={
                    "position": [curr_x, curr_y],
                    "min_battery": 0.1,
                },
                expected_postconditions={
                    "position": [target_x, target_y],
                    "status": "destination_reached",
                },
                cognitive_confidence=0.95,
            )
            action_proposals.append(proposal)
        else:
            # Reached target, proposal to stop or scan
            risk_eval = self.assess_risk("stop", {}, belief_state)
        
            proposal = ActionProposal(
                goal_id=goal.envelope.contract_id,
                action_type="stop",
                target_entity="mobile_base_0",
                action_parameters={"linear_velocity": 0.0, "angular_velocity": 0.0},
                estimated_duration_ms=500,
                risk_assessment=risk_eval,
                preconditions={"position": [curr_x, curr_y]},
                expected_postconditions={"position": [curr_x, curr_y], "status": "stopped"},
                cognitive_confidence=0.99,
            )
            action_proposals.append(proposal)

        return {"goals": [goal], "action_proposals": action_proposals}
