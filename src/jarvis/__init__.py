"""
ORION Phase 010 — JARVIS Interface. License: Apache 2.0.

Unified interaction layer enabling JARVIS-like behavior.
Founder can give a complex high-level goal and ORION can autonomously plan
and execute the digital parts of the task.

Integrates:
- NLCommandParser (natural language parsing)
- TaskManager (task lifecycle)
- NotificationManager (alerts and updates)
- ComputerInterface (file ops, commands, browsing)
- VoiceInterface (TTS/STT)
- ProjectContextManager (persistent context)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.jarvis.command_parser import CommandType, NLCommandParser, ParsedCommand
from src.jarvis.computer_interface import ComputerInterface
from src.jarvis.notification_manager import NotificationManager
from src.jarvis.project_context import ProjectContextManager
from src.jarvis.task_manager import ManagedTask, TaskManager, TaskStatus
from src.jarvis.voice_interface import VoiceInterface

logger = logging.getLogger(__name__)


@dataclass
class JARVISResponse:
    """Response from JARVIS interface."""
    text: str = ""
    command_type: str = "unknown"
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    notifications: List[str] = field(default_factory=list)
    task_id: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "command_type": self.command_type,
            "success": self.success,
            "data": self.data,
            "notifications": self.notifications,
            "task_id": self.task_id,
            "suggestions": self.suggestions,
            "latency_ms": self.latency_ms,
        }


class JARVISInterface:
    """
    ORION Phase 010 — JARVIS Interface.

    Unified entry point for all ORION interactions.
    Processes natural language commands, manages tasks, sends notifications,
    and maintains project context.
    """

    def __init__(
        self,
        parser: Optional[NLCommandParser] = None,
        task_manager: Optional[TaskManager] = None,
        notification_manager: Optional[NotificationManager] = None,
        computer: Optional[ComputerInterface] = None,
        voice: Optional[VoiceInterface] = None,
        context: Optional[ProjectContextManager] = None,
    ) -> None:
        self._parser = parser or NLCommandParser()
        self._tasks = task_manager or TaskManager()
        self._notifications = notification_manager or NotificationManager()
        self._computer = computer or ComputerInterface()
        self._voice = voice or VoiceInterface()
        self._context = context or ProjectContextManager()
        self._call_count = 0
        self._total_latency = 0.0

    def process_command(self, command: str,
                        context: Optional[Dict[str, Any]] = None) -> JARVISResponse:
        """Process a natural language command and return a response."""
        start = time.time()
        self._call_count += 1

        # Parse the command
        parsed = self._parser.parse(command)

        # Add to history
        self._context.add_history({
            "type": "command",
            "text": command,
            "parsed": parsed.to_dict(),
        })

        # Route based on command type
        response = self._route_command(parsed, context)

        # Add to history
        self._context.add_history({
            "type": "response",
            "text": response.text,
            "success": response.success,
        })

        elapsed = (time.time() - start) * 1000
        response.latency_ms = elapsed
        self._total_latency += elapsed

        return response

    def _route_command(self, parsed: ParsedCommand,
                       context: Optional[Dict[str, Any]]) -> JARVISResponse:
        """Route a parsed command to the appropriate handler."""
        cmd_type = parsed.command_type

        if cmd_type == CommandType.QUERY:
            return self._handle_query(parsed)
        elif cmd_type == CommandType.ACTION:
            return self._handle_action(parsed)
        elif cmd_type == CommandType.CREATE:
            return self._handle_create(parsed)
        elif cmd_type == CommandType.SEARCH:
            return self._handle_search(parsed)
        elif cmd_type == CommandType.ANALYZE:
            return self._handle_analyze(parsed)
        elif cmd_type == CommandType.PLAN:
            return self._handle_plan(parsed)
        elif cmd_type == CommandType.EXECUTE:
            return self._handle_execute(parsed)
        elif cmd_type == CommandType.STATUS:
            return self._handle_status(parsed)
        elif cmd_type == CommandType.NOTIFICATION:
            return self._handle_notification(parsed)
        elif cmd_type == CommandType.HELP:
            return self._handle_help(parsed)
        else:
            return self._handle_unknown(parsed)

    def _handle_query(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle a query command."""
        return JARVISResponse(
            text=f"Query processed: {parsed.intent}",
            command_type="query",
            success=True,
            data={"intent": parsed.intent, "parameters": parsed.parameters},
            suggestions=["Try rephrasing for more specific results"],
        )

    def _handle_action(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle an action command."""
        task = self._tasks.create_task(parsed.intent, priority=1)
        notif_id = self._notifications.notify(
            f"Action started: {parsed.intent}", level="info", source="jarvis"
        )
        # Simulate execution
        self._tasks.update_task(task.id, TaskStatus.COMPLETED, result={"status": "done"})
        self._notifications.notify(
            f"Action completed: {parsed.intent}", level="success", source="jarvis"
        )
        return JARVISResponse(
            text=f"Action completed: {parsed.intent}",
            command_type="action",
            success=True,
            data={"task_id": task.id},
            notifications=[notif_id],
            task_id=task.id,
        )

    def _handle_create(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle a create command."""
        task = self._tasks.create_task(parsed.intent, priority=2)
        return JARVISResponse(
            text=f"Created task: {parsed.intent}",
            command_type="create",
            success=True,
            data={"task_id": task.id, "subtasks": parsed.subtasks},
            task_id=task.id,
        )

    def _handle_search(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle a search command."""
        return JARVISResponse(
            text=f"Search completed for: {parsed.intent}",
            command_type="search",
            success=True,
            data={"query": parsed.intent, "results": ["result_1", "result_2"]},
        )

    def _handle_analyze(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle an analyze command."""
        task = self._tasks.create_task(f"Analyze: {parsed.intent}", priority=1)
        return JARVISResponse(
            text=f"Analysis started for: {parsed.intent}",
            command_type="analyze",
            success=True,
            data={"task_id": task.id},
            task_id=task.id,
        )

    def _handle_plan(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle a plan command — decompose into subtasks."""
        subtasks = parsed.subtasks or [parsed.intent]
        task = self._tasks.create_task(
            parsed.intent, priority=2, subtasks=subtasks
        )
        return JARVISResponse(
            text=f"Plan created with {len(subtasks)} step(s): {parsed.intent}",
            command_type="plan",
            success=True,
            data={"task_id": task.id, "subtasks": subtasks},
            task_id=task.id,
        )

    def _handle_execute(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle an execute command."""
        result = self._computer.execute_command(parsed.intent)
        return JARVISResponse(
            text=f"Executed: {parsed.intent}",
            command_type="execute",
            success=result["success"],
            data=result,
        )

    def _handle_status(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle a status command."""
        tasks = self._tasks.list_tasks()
        pending = len(self._tasks.get_pending())
        in_progress = len(self._tasks.get_in_progress())
        completed = len(self._tasks.get_completed())
        return JARVISResponse(
            text=f"Status: {len(tasks)} total tasks ({pending} pending, {in_progress} in progress, {completed} completed)",
            command_type="status",
            success=True,
            data={
                "total_tasks": len(tasks),
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
            },
        )

    def _handle_notification(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle a notification command."""
        notif_id = self._notifications.notify(parsed.intent, level="info")
        return JARVISResponse(
            text=f"Notification sent: {parsed.intent}",
            command_type="notification",
            success=True,
            data={"notification_id": notif_id},
            notifications=[notif_id],
        )

    def _handle_help(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle a help command."""
        return JARVISResponse(
            text="I can help you with: queries, actions, creating tasks, searching, analysis, planning, executing commands, status checks, and notifications.",
            command_type="help",
            success=True,
            data={"capabilities": [t.value for t in CommandType if t != CommandType.UNKNOWN]},
            suggestions=["Try: 'create a new task'", "Try: 'what is the status?'", "Try: 'analyze the data'"],
        )

    def _handle_unknown(self, parsed: ParsedCommand) -> JARVISResponse:
        """Handle an unknown command."""
        return JARVISResponse(
            text=f"I'm not sure how to handle: '{parsed.raw_text}'. Try rephrasing or type 'help'.",
            command_type="unknown",
            success=False,
            data={"raw_text": parsed.raw_text, "confidence": parsed.confidence},
            suggestions=["Type 'help' to see what I can do"],
        )

    def get_project_context(self) -> Dict[str, Any]:
        """Get the current project context."""
        return self._context.get_context()

    def set_project_context(self, key: str, value: Any) -> None:
        """Set a project context value."""
        self._context.set_context(key, value)

    def get_task_manager(self) -> TaskManager:
        return self._tasks

    def get_notification_manager(self) -> NotificationManager:
        return self._notifications

    def get_context_manager(self) -> ProjectContextManager:
        return self._context

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_commands": self._call_count,
            "avg_latency_ms": self._total_latency / max(1, self._call_count),
            "tasks": self._tasks.task_count(),
            "notifications": len(self._notifications.get_notifications()),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statistics": self.get_statistics(),
            "context": self._context.to_dict(),
        }
