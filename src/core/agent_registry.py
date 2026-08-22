"""
ORION Core Agent Registry — Phase 004. License: Apache 2.0

Registers specialist agents with health monitoring, invocation contracts,
and capability declarations. Agents are invoked by the Supervisor for
specialized tasks (planning, analysis, monitoring, etc.).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class AgentCapability(str, Enum):
    PLANNING = "planning"
    ANALYSIS = "analysis"
    MONITORING = "monitoring"
    EXECUTION = "execution"
    REASONING = "reasoning"
    OBSERVATION = "observation"


@dataclass
class AgentHealth:
    status: AgentStatus = AgentStatus.HEALTHY
    last_check: float = field(default_factory=time.time)
    success_rate: float = 1.0
    total_invocations: int = 0
    failed_invocations: int = 0

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "last_check": self.last_check,
            "success_rate": self.success_rate,
            "total_invocations": self.total_invocations,
            "failed_invocations": self.failed_invocations,
        }


@dataclass
class AgentDefinition:
    """Definition of a specialist agent."""
    id: str
    name: str
    description: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    handler: Optional[Callable[..., Any]] = None
    max_concurrent: int = 1
    timeout: float = 60.0
    health: AgentHealth = field(default_factory=AgentHealth)
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "capabilities": [c.value for c in self.capabilities],
            "max_concurrent": self.max_concurrent,
            "timeout": self.timeout,
            "health": self.health.to_dict(),
            "version": self.version,
        }


class AgentRegistry:
    """
    Registry for specialist agents available to ORION Core.

    Provides:
    - Agent registration with capability declarations
    - Health monitoring (success rate, invocation count)
    - Invocation contracts (timeout, max concurrent)
    - Capability-based lookup
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentDefinition] = {}
        self._active_invocations: Dict[str, int] = {}  # agent_id -> count
        self._version = "1.0.0"

    def register(self, agent: AgentDefinition) -> bool:
        if agent.id in self._agents:
            logger.warning(f"Agent already registered: {agent.id}")
            return False
        if not agent.handler:
            logger.warning(f"Agent has no handler: {agent.id}")
            return False
        self._agents[agent.id] = agent
        self._active_invocations[agent.id] = 0
        logger.info(f"Registered agent: {agent.id} (capabilities={[c.value for c in agent.capabilities]})")
        return True

    def unregister(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        if self._active_invocations.get(agent_id, 0) > 0:
            logger.warning(f"Cannot unregister agent with active invocations: {agent_id}")
            return False
        del self._agents[agent_id]
        del self._active_invocations[agent_id]
        return True

    def get(self, agent_id: str) -> Optional[AgentDefinition]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[AgentDefinition]:
        return list(self._agents.values())

    def list_by_capability(self, capability: AgentCapability) -> List[AgentDefinition]:
        return [a for a in self._agents.values() if capability in a.capabilities]

    def is_healthy(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        return agent.health.status in (AgentStatus.HEALTHY, AgentStatus.DEGRADED)

    def invoke(self, agent_id: str, **kwargs: Any) -> dict:
        """Invoke an agent with health tracking."""
        agent = self._agents.get(agent_id)
        if not agent:
            return {"success": False, "error": f"Unknown agent: {agent_id}"}
        if not self.is_healthy(agent_id):
            return {"success": False, "error": f"Agent unhealthy: {agent_id}"}
        if self._active_invocations[agent_id] >= agent.max_concurrent:
            return {"success": False, "error": f"Agent at max concurrency: {agent_id}"}

        self._active_invocations[agent_id] += 1
        agent.health.total_invocations += 1
        start = time.time()

        try:
            result = agent.handler(**kwargs)
            agent.health.last_check = time.time()
            agent.health.status = AgentStatus.HEALTHY
            return {"success": True, "result": result, "agent_id": agent_id,
                    "latency_ms": (time.time() - start) * 1000}
        except Exception as e:
            agent.health.failed_invocations += 1
            agent.health.success_rate = (
                1.0 - (agent.health.failed_invocations / agent.health.total_invocations)
                if agent.health.total_invocations > 0 else 0.0
            )
            if agent.health.success_rate < 0.5:
                agent.health.status = AgentStatus.UNHEALTHY
            elif agent.health.success_rate < 0.8:
                agent.health.status = AgentStatus.DEGRADED
            return {"success": False, "error": str(e), "agent_id": agent_id}
        finally:
            self._active_invocations[agent_id] -= 1

    def check_health(self) -> Dict[str, AgentHealth]:
        """Check health of all registered agents."""
        return {aid: agent.health for aid, agent in self._agents.items()}

    def to_dict(self) -> dict:
        return {
            "version": self._version,
            "agents": {aid: a.to_dict() for aid, a in self._agents.items()},
            "agent_count": len(self._agents),
            "active_invocations": dict(self._active_invocations),
        }
