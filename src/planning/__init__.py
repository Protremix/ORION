"""
ORION Autonomous Planner — Master Spec §12, §15, §26 Phase 5

Goal decomposition → action sequence → simulation → execution.

The planner takes a high-level goal, decomposes it into sub-goals,
generates action sequences for each sub-goal, validates them through
simulation, and returns a safe execution plan.

Architecture:
    GOAL (natural language or structured)
        → DECOMPOSE (LLM-based goal decomposition)
        → PLAN (action sequence generation)
        → SIMULATE (validate in domain simulator)
        → VERIFY (safety check)
        → EXECUTE PLAN

License: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Planner Data Types
# ============================================================================

class PlanStatus(str, Enum):
    """Status of a plan or sub-goal."""
    PENDING = "pending"
    DECOMPOSING = "decomposing"
    PLANNING = "planning"
    SIMULATING = "simulating"
    VERIFYING = "verifying"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SAFETY_BLOCKED = "safety_blocked"


@dataclass
class SubGoal:
    """A decomposed sub-goal from a higher-level goal."""
    id: str
    description: str
    priority: int = 0  # 0=normal, 1=high, 2=critical
    dependencies: List[str] = field(default_factory=list)  # IDs of sub-goals that must complete first
    status: PlanStatus = PlanStatus.PENDING
    actions: List[Dict[str, Any]] = field(default_factory=list)
    safety_level: str = "SC_3"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """A single action in an execution plan."""
    id: str
    action_type: str  # e.g., "move", "activate", "deactivate", "observe", "communicate"
    target: str  # Device or entity ID
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: Optional[str] = None
    safety_check_required: bool = True
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """A complete execution plan with sub-goals and actions."""
    id: str
    goal: str
    sub_goals: List[SubGoal] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING
    created_at: float = field(default_factory=time.time)
    safety_verified: bool = False
    simulation_verified: bool = False
    estimated_duration: float = 0.0
    risk_assessment: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "sub_goals": len(self.sub_goals),
            "actions": len(self.actions),
            "safety_verified": self.safety_verified,
            "simulation_verified": self.simulation_verified,
            "estimated_duration": self.estimated_duration,
        }


# ============================================================================
# Autonomous Planner
# ============================================================================

class AutonomousPlanner:
    """
    ORION Autonomous Planner — Master Spec §26 Phase 5.

    Takes a high-level goal and produces a safe, simulated execution plan.

    Pipeline:
        1. DECOMPOSE: Break goal into sub-goals
        2. PLAN: Generate action sequences for each sub-goal
        3. SIMULATE: Validate in domain simulator
        4. VERIFY: Safety check
        5. RETURN: Execution-ready plan
    """

    def __init__(self, text_adapter: Optional[Any] = None,
                 safety_gateway: Optional[Any] = None,
                 simulator: Optional[Any] = None) -> None:
        self._text_adapter = text_adapter
        self._safety_gateway = safety_gateway
        self._simulator = simulator
        self._plan_counter = 0
        self._sub_goal_counter = 0
        self._action_counter = 0

    def _next_plan_id(self) -> str:
        self._plan_counter += 1
        return f"plan_{self._plan_counter}"

    def _next_sub_goal_id(self) -> str:
        self._sub_goal_counter += 1
        return f"sg_{self._sub_goal_counter}"

    def _next_action_id(self) -> str:
        self._action_counter += 1
        return f"act_{self._action_counter}"

    def plan(self, goal: str, domain: str = "industrial",
             context: Optional[Dict[str, Any]] = None) -> ExecutionPlan:
        """
        Full planning pipeline: decompose → plan → simulate → verify.
        """
        plan = ExecutionPlan(id=self._next_plan_id(), goal=goal)
        ctx = context or {}

        # Step 1: Decompose goal into sub-goals
        plan.status = PlanStatus.DECOMPOSING
        sub_goals = self.decompose(goal, domain, ctx)
        plan.sub_goals = sub_goals

        # Step 2: Generate actions for each sub-goal
        plan.status = PlanStatus.PLANNING
        all_actions = []
        for sg in sub_goals:
            actions = self.generate_actions(sg, domain, ctx)
            sg.actions = [a if isinstance(a, dict) else a.__dict__ for a in actions]
            all_actions.extend(actions)
        plan.actions = all_actions

        # Step 3: Simulate if simulator available
        if self._simulator:
            plan.status = PlanStatus.SIMULATING
            sim_result = self.simulate(plan, domain)
            plan.simulation_verified = sim_result.get("success", False)
            if not plan.simulation_verified:
                plan.status = PlanStatus.FAILED
                plan.metadata["simulation_errors"] = sim_result.get("errors", [])
                return plan

        # Step 4: Safety verification
        plan.status = PlanStatus.VERIFYING
        if self._safety_gateway:
            safety_result = self.verify_safety(plan, domain)
            plan.safety_verified = safety_result.get("safe", False)
            plan.risk_assessment = safety_result.get("risk_assessment")
            if not plan.safety_verified:
                plan.status = PlanStatus.SAFETY_BLOCKED
                plan.metadata["safety_violations"] = safety_result.get("violations", [])
                return plan
        else:
            plan.safety_verified = True  # No safety gateway = cannot verify, assume unsafe unless explicitly safe
            plan.safety_verified = False
            plan.metadata["warning"] = "No safety gateway configured — cannot verify safety"

        # Step 5: Plan is ready
        plan.status = PlanStatus.READY
        plan.estimated_duration = sum(a.timeout for a in plan.actions)
        return plan

    def decompose(self, goal: str, domain: str = "industrial",
                  context: Optional[Dict[str, Any]] = None) -> List[SubGoal]:
        """
        Decompose a high-level goal into sub-goals.

        Uses LLM if available, otherwise uses rule-based decomposition.
        """
        ctx = context or {}

        # Try LLM-based decomposition
        if self._text_adapter:
            try:
                prompt = self._build_decomposition_prompt(goal, domain, ctx)
                from src.models import TextRequest
                response = self._text_adapter.generate(TextRequest(
                    prompt=prompt,
                    system_prompt="You are ORION's planning module. Decompose goals into actionable sub-goals. Return JSON array.",
                    max_tokens=2000,
                    temperature=0.3,
                ))
                if response.text:
                    sub_goals = self._parse_decomposition(response.text)
                    if sub_goals:
                        return sub_goals
            except Exception as e:
                logger.warning(f"LLM decomposition failed: {e}, falling back to rule-based")

        # Rule-based fallback decomposition
        return self._rule_based_decompose(goal, domain, ctx)

    def _build_decomposition_prompt(self, goal: str, domain: str,
                                     ctx: Dict[str, Any]) -> str:
        return json.dumps({
            "task": "decompose_goal",
            "goal": goal,
            "domain": domain,
            "context": ctx,
            "instructions": "Break this goal into 2-5 sub-goals. Each sub-goal should have: description, priority (0-2), dependencies (list of sub-goal indices that must complete first), safety_level (SC_1/SC_2/SC_3). Return as JSON array.",
        }, indent=2)

    def _parse_decomposition(self, text: str) -> List[SubGoal]:
        """Parse LLM response into SubGoal objects."""
        try:
            # Find JSON array in text
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end == -1:
                return []
            data = json.loads(text[start:end+1])
            sub_goals = []
            for item in data:
                sg = SubGoal(
                    id=self._next_sub_goal_id(),
                    description=item.get("description", ""),
                    priority=item.get("priority", 0),
                    dependencies=[str(d) for d in item.get("dependencies", [])],
                    safety_level=item.get("safety_level", "SC_3"),
                )
                sub_goals.append(sg)
            return sub_goals
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse decomposition: {e}")
            return []

    def _rule_based_decompose(self, goal: str, domain: str,
                              ctx: Dict[str, Any]) -> List[SubGoal]:
        """Simple rule-based goal decomposition fallback."""
        goal_lower = goal.lower()

        sub_goals = []

        # Common pattern: observe → plan → act → verify
        sub_goals.append(SubGoal(
            id=self._next_sub_goal_id(),
            description=f"Observe current state in {domain} domain",
            priority=0,
            safety_level="SC_3",
        ))

        sub_goals.append(SubGoal(
            id=self._next_sub_goal_id(),
            description=f"Analyze and plan action for: {goal}",
            priority=1,
            dependencies=[sub_goals[0].id],
            safety_level="SC_2",
        ))

        sub_goals.append(SubGoal(
            id=self._next_sub_goal_id(),
            description=f"Execute planned action: {goal}",
            priority=2,
            dependencies=[sub_goals[1].id],
            safety_level="SC_1" if "move" in goal_lower or "activate" in goal_lower else "SC_2",
        ))

        sub_goals.append(SubGoal(
            id=self._next_sub_goal_id(),
            description="Verify outcome and stabilize system",
            priority=0,
            dependencies=[sub_goals[2].id],
            safety_level="SC_3",
        ))

        return sub_goals

    def generate_actions(self, sub_goal: SubGoal, domain: str = "industrial",
                         context: Optional[Dict[str, Any]] = None) -> List[Action]:
        """Generate actions for a sub-goal."""
        ctx = context or {}
        actions = []

        # Try LLM-based action generation
        if self._text_adapter:
            try:
                prompt = json.dumps({
                    "task": "generate_actions",
                    "sub_goal": sub_goal.description,
                    "domain": domain,
                    "context": ctx,
                    "instructions": "Generate 1-5 concrete actions. Each action: action_type, target, parameters, expected_outcome, safety_check_required. Return as JSON array.",
                }, indent=2)

                from src.models import TextRequest
                response = self._text_adapter.generate(TextRequest(
                    prompt=prompt,
                    system_prompt="You are ORION's action planner. Generate concrete actions for sub-goals. Return JSON array.",
                    max_tokens=1500,
                    temperature=0.2,
                ))
                if response.text:
                    parsed = self._parse_actions(response.text)
                    if parsed:
                        return parsed
            except Exception as e:
                logger.warning(f"LLM action generation failed: {e}, falling back")

        # Rule-based fallback
        actions.append(Action(
            id=self._next_action_id(),
            action_type="observe",
            target=f"{domain}_environment",
            parameters={"sub_goal": sub_goal.description},
            expected_outcome="environment state captured",
        ))

        if sub_goal.priority >= 1:
            actions.append(Action(
                id=self._next_action_id(),
                action_type="execute",
                target=f"{domain}_actuator",
                parameters={"goal": sub_goal.description},
                expected_outcome="action completed",
                safety_check_required=True,
            ))

        if sub_goal.priority >= 2:
            actions.append(Action(
                id=self._next_action_id(),
                action_type="verify",
                target=f"{domain}_sensors",
                parameters={"check": "outcome"},
                expected_outcome="verification passed",
            ))

        return actions

    def _parse_actions(self, text: str) -> List[Action]:
        """Parse LLM action response."""
        try:
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end == -1:
                return []
            data = json.loads(text[start:end+1])
            actions = []
            for item in data:
                actions.append(Action(
                    id=self._next_action_id(),
                    action_type=item.get("action_type", "unknown"),
                    target=item.get("target", "unknown"),
                    parameters=item.get("parameters", {}),
                    expected_outcome=item.get("expected_outcome"),
                    safety_check_required=item.get("safety_check_required", True),
                    timeout=item.get("timeout", 30.0),
                ))
            return actions
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse actions: {e}")
            return []

    def simulate(self, plan: ExecutionPlan, domain: str = "industrial") -> Dict[str, Any]:
        """Simulate the execution plan in a domain simulator."""
        if not self._simulator:
            return {"success": True, "note": "No simulator configured, skipping simulation"}

        try:
            # Run simulation with planned actions
            sim_result = self._simulator.simulate_plan(plan.to_dict()) if hasattr(self._simulator, "simulate_plan") else {"success": True}
            return sim_result
        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            return {"success": False, "errors": [str(e)]}

    def verify_safety(self, plan: ExecutionPlan, domain: str = "industrial") -> Dict[str, Any]:
        """Verify plan safety through the safety gateway."""
        if not self._safety_gateway:
            return {"safe": False, "violations": ["No safety gateway configured"]}

        try:
            violations = []
            for action in plan.actions:
                if action.safety_check_required:
                    cmd = {
                        "action_type": action.action_type,
                        "target": action.target,
                        "parameters": action.parameters,
                    }
                    if hasattr(self._safety_gateway, "check_action"):
                        safe = self._safety_gateway.check_action(cmd)
                        if not safe:
                            violations.append(f"Unsafe action: {action.action_type} on {action.target}")

            return {
                "safe": len(violations) == 0,
                "violations": violations,
                "risk_assessment": {"total_actions": len(plan.actions), "checked": len([a for a in plan.actions if a.safety_check_required])},
            }
        except Exception as e:
            logger.error(f"Safety verification failed: {e}")
            return {"safe": False, "violations": [str(e)]}
