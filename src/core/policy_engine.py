"""
ORION Core Policy Engine — Phase 004. License: Apache 2.0
Deterministic policy decisions independent of model output. Denies by default.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.tool_registry import ToolCategory, ToolRegistry, ToolRiskLevel

logger = logging.getLogger(__name__)

class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    RATE_LIMITED = "rate_limited"

class PolicyRuleType(str, Enum):
    TOOL_RISK = "tool_risk"
    TOOL_CATEGORY = "tool_category"
    RESOURCE_LIMIT = "resource_limit"
    TIME_LIMIT = "time_limit"
    SCOPE = "scope"
    CUSTOM = "custom"

@dataclass
class PolicyRule:
    id: str
    rule_type: PolicyRuleType
    description: str
    decision: PolicyDecision
    priority: int = 0
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def matches(self, context: Dict[str, Any]) -> bool:
        for key, expected in self.conditions.items():
            actual = context.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

class PolicyEngine:
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._rules: List[PolicyRule] = []
        self._default_decision = PolicyDecision.DENY
        self._version = "1.0.0"
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        self.add_rule(PolicyRule(id="block_physical", rule_type=PolicyRuleType.TOOL_CATEGORY,
            description="Block all physical actions in Phase 004", decision=PolicyDecision.DENY,
            priority=100, conditions={"tool_category": ToolCategory.PHYSICAL.value}))
        self.add_rule(PolicyRule(id="block_forbidden", rule_type=PolicyRuleType.TOOL_RISK,
            description="Forbidden tools are never allowed", decision=PolicyDecision.DENY,
            priority=100, conditions={"tool_risk": [ToolRiskLevel.FORBIDDEN.name]}))
        self.add_rule(PolicyRule(id="require_approval_high", rule_type=PolicyRuleType.TOOL_RISK,
            description="High-risk tools require explicit approval", decision=PolicyDecision.REQUIRE_APPROVAL,
            priority=80, conditions={"tool_risk": [ToolRiskLevel.HIGH.name, ToolRiskLevel.CRITICAL.name]}))
        self.add_rule(PolicyRule(id="require_approval_medium", rule_type=PolicyRuleType.TOOL_RISK,
            description="Medium-risk tools require approval", decision=PolicyDecision.REQUIRE_APPROVAL,
            priority=70, conditions={"tool_risk": [ToolRiskLevel.MEDIUM.name]}))
        self.add_rule(PolicyRule(id="allow_safe", rule_type=PolicyRuleType.TOOL_RISK,
            description="Safe and low-risk tools are allowed", decision=PolicyDecision.ALLOW,
            priority=50, conditions={"tool_risk": [ToolRiskLevel.SAFE.name, ToolRiskLevel.LOW.name]}))

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Added policy rule: {rule.id} (priority={rule.priority})")

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.id != rule_id]
        return len(self._rules) < before

    def evaluate(self, context: Dict[str, Any]) -> PolicyDecision:
        tool_name = context.get("tool_name")
        if tool_name:
            tool = self._tool_registry.get(tool_name)
            if tool:
                context.setdefault("tool_category", tool.category.value)
                context.setdefault("tool_risk", tool.risk_level.name)
        if tool_name and not self._tool_registry.get(tool_name):
            logger.warning(f"Policy: unknown tool '{tool_name}' - denying")
            return PolicyDecision.DENY
        for rule in self._rules:
            if not rule.enabled:
                continue
            if rule.matches(context):
                logger.debug(f"Policy: rule '{rule.id}' matched -> {rule.decision.value}")
                return rule.decision
        logger.warning("Policy: no rule matched - denying by default")
        return self._default_decision

    def evaluate_tool(self, tool_name: str, args: Dict[str, Any], task_id: Optional[str] = None) -> PolicyDecision:
        context: Dict[str, Any] = {"tool_name": tool_name, "args": args}
        if task_id:
            context["task_id"] = task_id
        return self.evaluate(context)

    def is_deterministic(self) -> bool:
        test_contexts = [
            {"tool_name": "test_safe", "tool_category": "read", "tool_risk": "SAFE"},
            {"tool_name": "test_physical", "tool_category": "physical", "tool_risk": "HIGH"},
            {"tool_name": "unknown_tool"},
        ]
        for ctx in test_contexts:
            results = [self.evaluate(ctx) for _ in range(5)]
            if len(set(results)) > 1:
                return False
        return True

    def to_dict(self) -> dict:
        return {"version": self._version, "default_decision": self._default_decision.value,
                "rules": [{"id": r.id, "type": r.rule_type.value, "decision": r.decision.value,
                           "priority": r.priority, "conditions": r.conditions, "enabled": r.enabled}
                          for r in self._rules], "rule_count":
                              len(self._rules)}
