# ORION TASK 001 — TASK 7: API / Hardware Abstraction Architecture

## Overview

ORION Core must remain independent from any single LLM, vision model, robot, car, drone, manufacturer, or simulator. This is achieved through adapter interfaces and a Hardware Abstraction Layer (HAL).

## Current Implementation (VERIFIED FACT)

ORION already has:
- **ModelRegistry** — swappable adapters for text, vision, embedding
- **GPT-4o adapters** — Text, Vision, Embedding (live-tested)
- **HAL interface** — defined with SafetyGateway integration
- **API/SDK** — defined interfaces for agent protocol, skill interface, tool interface
- **GitHub repository** — Protremix/ORION with CI-ready structure

## Full Architecture

### 1. ORION API

```python
# Core API for interacting with ORION
class OrionAPI:
    # Reasoning
    def reason(self, prompt: str, context: Optional[dict] = None) -> ReasoningResult
    def plan(self, goal: str, domain: str) -> ExecutionPlan
    
    # Memory
    def remember(self, entry: MemoryEntry) -> str
    def recall(self, query: str, memory_type: str) -> List[MemoryEntry]
    
    # World Model
    def predict(self, state: WorldState, action: dict, horizon: int) -> PredictionResult
    def simulate(self, plan: ExecutionPlan, domain: str) -> SimulationResult
    
    # Safety
    def check_safety(self, action: Action) -> SafetyResult
    def emergency_stop(self, domain: str) -> bool
    
    # Discovery
    def ingest_knowledge(self, source: str, content: Any) -> str
    def generate_hypothesis(self, domain: str) -> Hypothesis
    def test_hypothesis(self, hypothesis_id: str) -> TestResult
    
    # Agents
    def create_agent(self, agent_type: str, config: dict) -> Agent
    def list_agents(self) -> List[Agent]
```

### 2. ORION SDK

```python
# SDK for external developers
class OrionSDK:
    def connect(self, endpoint: str, credentials: dict) -> OrionSession
    def register_adapter(self, adapter: Adapter) -> bool
    def register_domain(self, domain: DomainModule) -> bool
    def register_agent(self, agent: AgentModule) -> bool
    
    # For device manufacturers
    def register_device(self, device: DeviceAdapter) -> bool
    def get_safety_requirements(self, device_type: str) -> SafetySpec
```

### 3. Model Adapters (VERIFIED FACT — partially implemented)

```
Model Adapter Interface
├── LLM Adapter (text reasoning)
│   ├── GPT4oTextAdapter ✅ (live-tested)
│   ├── OpenWeightLLMAdapter (planned: Llama, Qwen)
│   └── LocalLLMAdapter (planned: Ollama, vLLM)
│
├── Vision Adapter
│   ├── GPT4oVisionAdapter ✅ (live-tested)
│   ├── OpenVisionAdapter (planned: LLaVA)
│   └── LocalVisionAdapter (planned)
│
├── Embedding Adapter
│   ├── OpenAIEmbeddingAdapter ✅ (live-tested)
│   ├── OpenEmbeddingAdapter (planned: BGE, E5)
│   └── LocalEmbeddingAdapter (planned)
│
├── World Model Adapter
│   ├── PhysicsWorldModel ✅ (4 domains, Luna-approved)
│   ├── LearnedWorldModel (planned: DreamerV3-style)
│   └── HybridWorldModel (planned)
│
├── Audio Adapter (planned)
│   ├── WhisperAdapter
│   └── TTSAdapter
│
└── Video Adapter (planned)
```

### 4. Hardware Abstraction Layer (HAL)

```
ORION INTELLIGENCE
       ↓
SAFETY GATEWAY ← all physical actions must pass through
       ↓
HARDWARE ABSTRACTION LAYER
       ↓
DEVICE ADAPTERS
   ├── Robot Adapter
   │   ├── GenericRobotAdapter (ROS2)
   │   ├── ManipulatorAdapter
   │   └── MobileRobotAdapter
   ├── Vehicle Adapter
   │   ├── GenericVehicleAdapter (CAN bus)
   │   ├── SimulatorVehicleAdapter (CARLA)
   │   └── DroneVehicleAdapter
   ├── Drone Adapter
   │   ├── PX4Adapter
   │   ├── DJIAdapter
   │   └── SimulatorDroneAdapter
   ├── Home Adapter
   │   ├── MatterAdapter (smart home standard)
   │   ├── ZigbeeAdapter
   │   └── HomeAssistantAdapter
   └── Industrial Adapter
       ├── PLCAdapter (Modbus, OPC-UA)
       ├── SCADAAdapter
       └── SimulatorIndustrialAdapter ✅ (implemented)
```

**HAL Interface:**
```python
class DeviceAdapter(ABC):
    @abstractmethod
    def connect(self) -> bool
    @abstractmethod
    def disconnect(self) -> bool
    @abstractmethod
    def get_state(self) -> DeviceState
    @abstractmethod
    def execute_action(self, action: Action) -> ActionResult
    @abstractmethod
    def emergency_stop(self) -> bool
    @abstractmethod
    def health_check(self) -> bool
    
    # Safety-critical: must be implemented
    @abstractmethod
    def get_safety_limits(self) -> SafetyLimits
    @abstractmethod
    def get_capabilities(self) -> DeviceCapabilities
```

### 5. Safety Gateway (VERIFIED FACT — partially implemented)

Current: Deny-by-default safety enforcement with cross-domain arbitration.

Full design:
```
ACTION REQUEST
    ↓
AUTHORIZATION CHECK — is this agent authorized?
    ↓
CAPABILITY CHECK — can this device do this?
    ↓
RISK ASSESSMENT — what's the risk level?
    ↓
DEVICE STATE CHECK — is the device in a safe state?
    ↓
LIMIT CHECK — does the action exceed safety limits?
    ↓
SIMULATION STATUS — has this been simulated?
    ↓
EMERGENCY STOP CHECK — is E-stop active?
    ↓
AUDIT REQUIREMENT — is this logged?
    ↓
APPROVE or DENY
```

**Key principle (Master Spec §13):** An LLM must NEVER be the sole safety mechanism for safety-critical control. The Safety Gateway uses rule-based checks + physics verification, not LLM judgment.

### 6. Skill Interface

```python
class Skill(ABC):
    @abstractmethod
    def name(self) -> str
    @abstractmethod
    def description(self) -> str
    @abstractmethod
    def required_permissions(self) -> List[str]
    @abstractmethod
    def execute(self, params: dict, context: OrionContext) -> SkillResult
    @abstractmethod
    def safety_check(self, params: dict) -> SafetyResult
```

### 7. Tool Interface

```python
class Tool(ABC):
    @abstractmethod
    def name(self) -> str
    @abstractmethod
    def call(self, params: dict) -> ToolResult
    @abstractmethod
    def health_check(self) -> bool
```

### 8. Agent Protocol

```python
class AgentProtocol(ABC):
    @abstractmethod
    def create_task(self, description: str, domain: str) -> str
    @abstractmethod
    def assign_task(self, task_id: str, agent_id: str) -> bool
    @abstractmethod
    def get_status(self, task_id: str) -> TaskStatus
    @abstractmethod
    def get_result(self, task_id: str) -> TaskResult
    @abstractmethod
    def cancel_task(self, task_id: str) -> bool
```

## Independence Guarantee

The ORION Core depends only on interfaces, never on concrete implementations:
- `ReasoningEngine` interface, not `GPT4oTextAdapter`
- `VisionModel` interface, not `GPT4oVisionAdapter`
- `StorageManager` interface, not `SQLiteStorageManager` or `PostgresStorageManager`
- `DeviceAdapter` interface, not `PX4Adapter` or `DJIAdapter`
- `Simulator` interface, not `CARLA` or `Isaac Sim`

This means any model, device, or simulator can be replaced without changing ORION Core.

## Dependency & License Registry

All external dependencies must be registered with license information (Master Spec §18). Current registry maintained in `DEPENDENCY_REGISTRY.md`.

## Classification

- API/SDK: HYPOTHESIS (interfaces defined, not all implemented)
- Model adapters: VERIFIED FACT (GPT-4o adapters live-tested)
- HAL: VERIFIED FACT (interface defined, simulator adapters working)
- Safety Gateway: VERIFIED FACT (deny-by-default, cross-domain arbitration)
- Device adapters: HYPOTHESIS (simulators work, real device adapters planned)
