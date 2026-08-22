# ORION Phase 009 — Agent & Skill System Specification

**Phase:** 009
**Status:** DRAFT
**License:** Apache 2.0
**Roadmap Reference:** ORION_MASTER_ROADMAP_v1.0 Phase 009

## 1. Goal

Build the ORION Agent & Skill System: skill registry, tool registry integration,
agent registry integration, dynamic task decomposition, specialist agents, supervisor
coordination, and a verification agent.

ORION must know:
- WHAT IT CAN DO (registered skills/agents)
- WHAT IT CANNOT DO (unregistered, forbidden, or permission-denied)
- WHAT TOOL IS REQUIRED (tool registry lookup)
- WHAT PERMISSION IS REQUIRED (permission engine check)

**Acceptance Criterion:** ORION can select and coordinate the correct agents automatically.

## 2. Current State (VERIFIED FACT)

Existing components (Phase 004):
- `AgentRegistry` (src/core/agent_registry.py) — register, invoke, health, capability lookup
- `ToolRegistry` (src/core/tool_registry.py) — register, validate, risk levels, categories
- `AgentProtocol` (src/api/__init__.py) — abstract: get_descriptor, execute_task, get_capabilities, health_check
- `AgentDescriptor`, `AgentTask`, `AgentResult` (src/api/__init__.py) — data classes
- `SkillDescriptor`, `SkillInterface` (src/api/__init__.py) — abstract skill interface
- `AgentRole` enum with 19 roles including RESEARCH, CODING, VISION, SECURITY, SIMULATION
- `CoreSupervisor` — orchestrates lifecycle, can be extended for agent coordination
- `MultimodalCoordinator` (Phase 008) — modality coordination
- `SimulationEngine` (Phase 007) — action simulation
- `PermissionEngine` (src/core/permission_engine.py) — permission checks

Gaps:
1. No concrete specialist agents implementing AgentProtocol
2. No SkillRegistry for skill management
3. No AgentCoordinator for automatic agent selection and coordination
4. No dynamic task decomposition for agent dispatch
5. No verification agent for result validation

## 3. Architecture

```
                    ┌─────────────────────────────┐
                    │  AgentCoordinator           │
                    │                             │
  Task ───────────►│  1. Decompose task           │
                    │  2. Select agents            │──► ResearchAgent
                    │  3. Dispatch subtasks       │──► CodingAgent
                    │  4. Collect results         │──► VisionAgent
                    │  5. Verify results          │──► SimulationAgent
                    │  6. Return unified output   │──► SecurityAgent
                    └─────────────────────────────┘──► VerificationAgent
```

### 3.1 New Component: SkillRegistry
- Register, list, lookup skills by name/domain
- Validate skill inputs against schema
- Execute skills and return results
- Integration with ToolRegistry (skills can wrap tools)

### 3.2 New Component: AgentCoordinator
- Decompose complex tasks into subtasks
- Select agents by capability/role matching
- Dispatch subtasks to specialist agents
- Collect and fuse agent results
- Verify results via VerificationAgent
- Report failures and escalate

### 3.3 Specialist Agents (implement AgentProtocol)

| Agent | Role | Capabilities |
|---|---|---|
| ResearchAgent | RESEARCH | information gathering, web search, analysis |
| CodingAgent | CODING | code generation, review, refactoring |
| VisionAgent | VISION | image analysis, object detection, scene understanding |
| SimulationAgent | SIMULATION | physics simulation, what-if analysis |
| SecurityAgent | SECURITY | safety analysis, permission checks, risk assessment |
| VerificationAgent | EVALUATION | result validation, test execution, quality checks |

### 3.4 Existing Components (Reuse)

| Component | Role | Phase |
|---|---|---|
| AgentRegistry | Agent registration, health | 004 |
| ToolRegistry | Tool schemas, permissions | 004 |
| PermissionEngine | Permission checks | 004 |
| CoreSupervisor | Lifecycle orchestration | 004/005 |
| MultimodalCoordinator | Modality coordination | 008 |
| SimulationEngine | Action simulation | 007 |

## 4. Acceptance Criteria

| AC | Description | Verification |
|---|---|---|
| AC1 | SkillRegistry registers and retrieves skills | Unit test |
| AC2 | SkillRegistry validates skill inputs | Unit test |
| AC3 | SkillRegistry executes skills and returns output | Unit test |
| AC4 | ResearchAgent executes research tasks | Unit test |
| AC5 | CodingAgent executes coding tasks | Unit test |
| AC6 | VisionAgent executes vision tasks | Unit test |
| AC7 | SimulationAgent executes simulation tasks | Unit test |
| AC8 | SecurityAgent executes security analysis tasks | Unit test |
| AC9 | VerificationAgent validates results | Unit test |
| AC10 | AgentCoordinator decomposes complex tasks | Unit test |
| AC11 | AgentCoordinator selects correct agents by capability | Unit test |
| AC12 | AgentCoordinator dispatches subtasks to agents | Unit test |
| AC13 | AgentCoordinator collects and fuses results | Unit test |
| AC14 | AgentCoordinator coordinates 2+ agents for one task | Integration test |
| AC15 | All agents implement AgentProtocol | Unit test |
| AC16 | All agents registered in AgentRegistry | Unit test |
| AC17 | ORION knows what it can/cannot do (capability query) | Unit test |
| AC18 | ORION knows what tool/permission is required | Unit test |
| AC19 | All tests pass | pytest -q |
| AC20 | Ruff/mypy clean | ruff + mypy |

## 5. File Structure

```
src/agents/
    __init__.py              — NEW: AgentCoordinator, SkillRegistry
    research_agent.py        — NEW: ResearchAgent
    coding_agent.py           — NEW: CodingAgent
    vision_agent.py           — NEW: VisionAgent
    simulation_agent.py       — NEW: SimulationAgent
    security_agent.py         — NEW: SecurityAgent
    verification_agent.py     — NEW: VerificationAgent

tests/unit/
    test_phase009.py          — NEW: all Phase 009 tests
```

## 6. Test Plan (~45 tests)

### Unit Tests (~35)
- SkillRegistry: register, get, list, validate, execute, unregister, error cases
- Each agent: get_descriptor, execute_task, get_capabilities, health_check
- AgentCoordinator: decompose, select, dispatch, collect, fuse, verify
- Capability queries: what can/cannot do, tool/permission requirements

### Integration Tests (~10)
- Multi-agent coordination (research + coding)
- Agent + tool registry integration
- Agent + permission engine integration
- Verification agent validates other agents' results
- Edge cases: no agents available, agent failure, task too complex

## 7. Scope

### IN SCOPE
- SkillRegistry implementation
- 6 specialist agents (simulation mode)
- AgentCoordinator for automatic selection and coordination
- Dynamic task decomposition
- Capability/permission/tool queries
- Simulation-only (no real external calls in tests)

### OUT OF SCOPE
- Real API integration for agents (Phase 011+)
- Multi-agent negotiation protocols
- Agent learning/adaptation
- Physical agent execution (Phase 013+)
