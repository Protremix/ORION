# ORION Phase 010 — JARVIS Interface Specification

**Phase:** 010
**Status:** DRAFT
**License:** Apache 2.0
**Roadmap Reference:** ORION_MASTER_ROADMAP_v1.0 Phase 010

## 1. Goal

Create a unified interaction layer enabling JARVIS-like behavior (functional, not fictional).
The Founder can give a complex high-level goal and ORION can autonomously plan and execute the digital parts.

Capabilities:
- Natural language understanding
- Voice interaction (text-to-speech, speech-to-text interfaces)
- Visual interface (dashboard data)
- Project context (persistent state across interactions)
- Persistent memory (Phase 005 integration)
- Computer interaction (file ops, command execution, web browsing interfaces)
- Task management (create, track, update, complete tasks)
- Notifications (alerts, reminders, status updates)
- Multimodal interaction (Phase 008 integration)

**Acceptance Criterion:** Founder can give a complex high-level goal and ORION can autonomously plan and execute the digital parts of the task.

## 2. Current State (VERIFIED FACT)

Existing components available for integration:
- `CoreSupervisor` (Phase 004/005) — lifecycle: GOAL → PLAN → EXECUTE → OBSERVE → EVALUATE → CORRECT → REMEMBER
- `MemoryManager` (Phase 005) — persistent memory
- `MultimodalCoordinator` (Phase 008) — multi-modality coordination
- `AgentCoordinator` (Phase 009) — agent selection and task decomposition
- `SimulationEngine` (Phase 007) — action simulation
- `WorldStateManager` (Phase 005) — world state tracking
- `ModelGateway` (Phase 004) — model-independent LLM interface

Gaps:
1. No unified interaction layer (JARVIS)
2. No natural language command parser
3. No project context manager
4. No task management interface
5. No notification system
6. No computer interaction interface
7. No voice interaction interface

## 3. Architecture

```
                    ┌─────────────────────────────┐
                    │  JARVIS Interface           │
                    │                             │
  User ───────────►│  1. Parse natural language   │
                    │  2. Load project context     │
                    │  3. Plan via CoreSupervisor  │
                    │  4. Execute (agents/tools)   │
                    │  5. Report results           │──► User (text/voice)
                    │  6. Update memory           │
                    │  7. Send notifications       │
                    └─────────────────────────────┘
```

### 3.1 New Components

#### JARVISInterface
- **Purpose:** Unified entry point for all ORION interactions
- **Input:** Natural language command (text or voice-transcribed)
- **Output:** Response (text, structured data, notifications)
- **Key methods:**
  - `process_command(command: str, context: Optional[Dict] = None) -> JARVISResponse`
  - `get_project_context() -> Dict[str, Any]`
  - `set_project_context(context: Dict[str, Any]) -> None`

#### NLCommandParser
- **Purpose:** Parse natural language into structured commands
- **Key methods:**
  - `parse(text: str) -> ParsedCommand`
  - `classify(text: str) -> CommandType`

#### TaskManager
- **Purpose:** Create, track, update, and complete tasks
- **Key methods:**
  - `create_task(description: str, priority: int) -> Task`
  - `update_task(task_id: str, status: str) -> bool`
  - `list_tasks(status: Optional[str] = None) -> List[Task]`
  - `get_task(task_id: str) -> Optional[Task]`

#### NotificationManager
- **Purpose:** Send alerts, reminders, and status updates
- **Key methods:**
  - `notify(message: str, level: str = "info") -> str`
  - `get_notifications() -> List[Notification]`
  - `mark_read(notification_id: str) -> bool`

#### ComputerInterface
- **Purpose:** File operations, command execution, web browsing (simulation)
- **Key methods:**
  - `read_file(path: str) -> str`
  - `write_file(path: str, content: str) -> bool`
  - `execute_command(command: str) -> Dict`
  - `browse(url: str) -> Dict`

#### VoiceInterface
- **Purpose:** Text-to-speech and speech-to-text interfaces
- **Key methods:**
  - `text_to_speech(text: str) -> Dict`
  - `speech_to_text(audio_data: Dict) -> str`

#### ProjectContextManager
- **Purpose:** Maintain context across interactions (current project, state, history)
- **Key methods:**
  - `get_context() -> Dict[str, Any]`
  - `set_context(key: str, value: Any) -> None`
  - `get_history() -> List[Dict]`
  - `add_history(entry: Dict) -> None`

### 3.2 Existing Components (Reuse)

| Component | Role | Phase |
|---|---|---|
| CoreSupervisor | Lifecycle orchestration | 004/005 |
| MemoryManager | Persistent memory | 005 |
| MultimodalCoordinator | Multimodal tasks | 008 |
| AgentCoordinator | Agent dispatch | 009 |
| SimulationEngine | Action simulation | 007 |
| ModelGateway | LLM interface | 004 |

## 4. Acceptance Criteria

| AC | Description | Verification |
|---|---|---|
| AC1 | NLCommandParser parses natural language into structured commands | Unit test |
| AC2 | NLCommandParser classifies command types (query, action, create, etc.) | Unit test |
| AC3 | TaskManager creates tasks | Unit test |
| AC4 | TaskManager updates task status | Unit test |
| AC5 | TaskManager lists and filters tasks | Unit test |
| AC6 | NotificationManager sends notifications | Unit test |
| AC7 | NotificationManager tracks read/unread state | Unit test |
| AC8 | ComputerInterface reads/writes files (simulation) | Unit test |
| AC9 | ComputerInterface executes commands (simulation) | Unit test |
| AC10 | VoiceInterface converts text to speech (simulation) | Unit test |
| AC11 | VoiceInterface converts speech to text (simulation) | Unit test |
| AC12 | ProjectContextManager maintains context across calls | Unit test |
| AC13 | ProjectContextManager tracks interaction history | Unit test |
| AC14 | JARVISInterface processes a simple command | Unit test |
| AC15 | JARVISInterface processes a complex multi-step command | Unit test |
| AC16 | JARVISInterface integrates with TaskManager | Integration test |
| AC17 | JARVISInterface integrates with NotificationManager | Integration test |
| AC18 | JARVISInterface integrates with ProjectContextManager | Integration test |
| AC19 | Founder gives high-level goal → ORION plans and executes (integration) | Integration test |
| AC20 | All tests pass | pytest -q |
| AC21 | Ruff/mypy clean | ruff + mypy |

## 5. File Structure

```
src/jarvis/
    __init__.py              — NEW: JARVISInterface
    command_parser.py       — NEW: NLCommandParser, ParsedCommand, CommandType
    task_manager.py          — NEW: TaskManager
    notification_manager.py  — NEW: NotificationManager
    computer_interface.py    — NEW: ComputerInterface
    voice_interface.py       — NEW: VoiceInterface
    project_context.py       — NEW: ProjectContextManager

tests/unit/
    test_phase010.py         — NEW: all Phase 010 tests
```

## 6. Test Plan (~50 tests)

### Unit Tests (~40)
- NLCommandParser: parse, classify, edge cases
- TaskManager: create, update, list, filter, get
- NotificationManager: notify, get, mark_read, levels
- ComputerInterface: read_file, write_file, execute_command, browse
- VoiceInterface: text_to_speech, speech_to_text
- ProjectContextManager: get/set context, history tracking
- JARVISInterface: process simple/complex commands, context integration

### Integration Tests (~10)
- JARVISInterface + TaskManager: create task via natural language
- JARVISInterface + NotificationManager: notify on task completion
- JARVISInterface + ProjectContextManager: maintain state across interactions
- Complex goal: Founder gives "research X and write a report" → ORION plans and executes
- Edge cases: empty command, unknown command type, task not found

## 7. Scope

### IN SCOPE
- All 7 new components (simulation mode)
- Natural language command parsing
- Task management and notifications
- Project context persistence
- Computer interaction (simulated)
- Voice interface (simulated)
- Integration with existing phases
- Simulation-only (no real API calls in tests)

### OUT OF SCOPE
- Real voice API integration (Phase 011+)
- Real computer control (Phase 013+)
- GUI/web interface (separate concern)
- Real-time streaming
- Multi-user support
