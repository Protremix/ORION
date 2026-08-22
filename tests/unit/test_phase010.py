"""
ORION Phase 010 — JARVIS Interface Test Suite. License: Apache 2.0.

Tests: NLCommandParser, TaskManager, NotificationManager, ComputerInterface,
VoiceInterface, ProjectContextManager, JARVISInterface.
"""
from __future__ import annotations

import pytest

from src.jarvis import JARVISInterface, JARVISResponse
from src.jarvis.command_parser import CommandType, NLCommandParser, ParsedCommand
from src.jarvis.computer_interface import ComputerInterface
from src.jarvis.notification_manager import NotificationManager
from src.jarvis.project_context import ProjectContextManager
from src.jarvis.task_manager import TaskManager, TaskStatus
from src.jarvis.voice_interface import VoiceInterface

# ============================================================================
# NLCommandParser Tests (AC1, AC2)
# ============================================================================

class TestNLCommandParser:
    def test_parse_query(self):
        """AC1: NLCommandParser parses natural language into structured commands."""
        parser = NLCommandParser()
        result = parser.parse("What is the status of the project?")
        assert result.command_type in (CommandType.QUERY, CommandType.STATUS)
        assert result.raw_text == "What is the status of the project?"
        assert result.confidence > 0

    def test_parse_action(self):
        parser = NLCommandParser()
        result = parser.parse("Run the test suite")
        assert result.command_type == CommandType.ACTION
        assert "run" in result.intent

    def test_parse_create(self):
        parser = NLCommandParser()
        result = parser.parse("Create a new task for data analysis")
        assert result.command_type == CommandType.CREATE
        assert "create" in result.intent

    def test_parse_search(self):
        parser = NLCommandParser()
        result = parser.parse("Search for information about quantum computing")
        assert result.command_type == CommandType.SEARCH

    def test_parse_analyze(self):
        parser = NLCommandParser()
        result = parser.parse("Analyze the performance metrics")
        assert result.command_type == CommandType.ANALYZE

    def test_parse_plan(self):
        parser = NLCommandParser()
        result = parser.parse("Plan a roadmap for the new feature")
        assert result.command_type == CommandType.PLAN

    def test_parse_execute(self):
        parser = NLCommandParser()
        result = parser.parse("Execute the deployment script")
        assert result.command_type == CommandType.EXECUTE

    def test_parse_status(self):
        parser = NLCommandParser()
        result = parser.parse("What is the status?")
        assert result.command_type == CommandType.STATUS

    def test_parse_notification(self):
        parser = NLCommandParser()
        result = parser.parse("Notify me when the build completes")
        assert result.command_type == CommandType.NOTIFICATION

    def test_parse_help(self):
        parser = NLCommandParser()
        result = parser.parse("Help me understand the system")
        assert result.command_type == CommandType.HELP

    def test_classify_unknown(self):
        """AC2: NLCommandParser classifies command types."""
        parser = NLCommandParser()
        result = parser.parse("xyzzy foobar")
        assert result.command_type == CommandType.UNKNOWN

    def test_parse_extracts_parameters(self):
        parser = NLCommandParser()
        result = parser.parse('Create a file called "test.py" with 100 lines')
        assert "quoted_args" in result.parameters
        assert "test.py" in result.parameters["quoted_args"]

    def test_parse_extracts_subtasks(self):
        parser = NLCommandParser()
        result = parser.parse("Research the topic then generate a report")
        assert len(result.subtasks) >= 2

    def test_parse_empty(self):
        parser = NLCommandParser()
        result = parser.parse("")
        assert result.command_type == CommandType.UNKNOWN

    def test_parse_strips_prefixes(self):
        parser = NLCommandParser()
        result = parser.parse("Please create a new project")
        assert result.command_type == CommandType.CREATE


# ============================================================================
# TaskManager Tests (AC3, AC4, AC5)
# ============================================================================

class TestTaskManager:
    def test_create_task(self):
        """AC3: TaskManager creates tasks."""
        tm = TaskManager()
        task = tm.create_task("Test task", priority=1)
        assert task.id == "task_1"
        assert task.description == "Test task"
        assert task.priority == 1
        assert task.status == TaskStatus.PENDING

    def test_create_multiple(self):
        tm = TaskManager()
        t1 = tm.create_task("Task 1")
        t2 = tm.create_task("Task 2")
        assert t1.id != t2.id

    def test_update_task_status(self):
        """AC4: TaskManager updates task status."""
        tm = TaskManager()
        task = tm.create_task("Test task")
        assert tm.update_task(task.id, TaskStatus.IN_PROGRESS) is True
        assert tm.get_task(task.id).status == TaskStatus.IN_PROGRESS

    def test_update_task_result(self):
        tm = TaskManager()
        task = tm.create_task("Test task")
        tm.update_task(task.id, result={"output": "done"})
        assert tm.get_task(task.id).result == {"output": "done"}

    def test_update_nonexistent(self):
        tm = TaskManager()
        assert tm.update_task("nonexistent", TaskStatus.COMPLETED) is False

    def test_list_tasks(self):
        """AC5: TaskManager lists and filters tasks."""
        tm = TaskManager()
        tm.create_task("Task 1")
        tm.create_task("Task 2")
        assert len(tm.list_tasks()) == 2

    def test_list_tasks_by_status(self):
        tm = TaskManager()
        t1 = tm.create_task("Task 1")
        t2 = tm.create_task("Task 2")
        tm.update_task(t1.id, TaskStatus.COMPLETED)
        assert len(tm.list_tasks(TaskStatus.COMPLETED)) == 1
        assert len(tm.list_tasks(TaskStatus.PENDING)) == 1

    def test_get_pending(self):
        tm = TaskManager()
        tm.create_task("Task 1")
        tm.create_task("Task 2")
        assert len(tm.get_pending()) == 2

    def test_delete_task(self):
        tm = TaskManager()
        task = tm.create_task("Test")
        assert tm.delete_task(task.id) is True
        assert tm.get_task(task.id) is None

    def test_task_count(self):
        tm = TaskManager()
        tm.create_task("Task 1")
        assert tm.task_count() == 1


# ============================================================================
# NotificationManager Tests (AC6, AC7)
# ============================================================================

class TestNotificationManager:
    def test_notify(self):
        """AC6: NotificationManager sends notifications."""
        nm = NotificationManager()
        notif_id = nm.notify("Test notification", level="info")
        assert notif_id is not None
        assert nm.get_notification(notif_id) is not None

    def test_notify_levels(self):
        nm = NotificationManager()
        nm.notify("Info", level="info")
        nm.notify("Warning", level="warning")
        nm.notify("Error", level="error")
        nm.notify("Success", level="success")
        assert len(nm.get_notifications()) == 4

    def test_mark_read(self):
        """AC7: NotificationManager tracks read/unread state."""
        nm = NotificationManager()
        nid = nm.notify("Test")
        assert nm.get_notification(nid).read is False
        assert nm.mark_read(nid) is True
        assert nm.get_notification(nid).read is True

    def test_mark_all_read(self):
        nm = NotificationManager()
        nm.notify("A")
        nm.notify("B")
        count = nm.mark_all_read()
        assert count == 2
        assert nm.unread_count() == 0

    def test_unread_count(self):
        nm = NotificationManager()
        nm.notify("A")
        nm.notify("B")
        assert nm.unread_count() == 2
        nm.mark_read(nm.get_notifications()[0].id)
        assert nm.unread_count() == 1

    def test_get_unread_only(self):
        nm = NotificationManager()
        nid = nm.notify("A")
        nm.notify("B")
        nm.mark_read(nid)
        unread = nm.get_notifications(unread_only=True)
        assert len(unread) == 1

    def test_clear(self):
        nm = NotificationManager()
        nm.notify("A")
        nm.notify("B")
        count = nm.clear()
        assert count == 2
        assert len(nm.get_notifications()) == 0


# ============================================================================
# ComputerInterface Tests (AC8, AC9)
# ============================================================================

class TestComputerInterface:
    def test_write_read_file(self):
        """AC8: ComputerInterface reads/writes files (simulation)."""
        ci = ComputerInterface()
        assert ci.write_file("/test/file.txt", "content") is True
        assert ci.read_file("/test/file.txt") == "content"

    def test_read_nonexistent(self):
        ci = ComputerInterface()
        content = ci.read_file("/nonexistent.txt")
        assert "Simulated" in content

    def test_list_files(self):
        ci = ComputerInterface()
        ci.write_file("/dir/a.txt", "a")
        ci.write_file("/dir/b.txt", "b")
        listing = ci.list_files("/dir/")
        assert listing["count"] == 2

    def test_delete_file(self):
        ci = ComputerInterface()
        ci.write_file("/test.txt", "content")
        assert ci.delete_file("/test.txt") is True
        assert ci.delete_file("/test.txt") is False

    def test_execute_command(self):
        """AC9: ComputerInterface executes commands (simulation)."""
        ci = ComputerInterface()
        result = ci.execute_command("ls -la")
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "command" in result

    def test_browse(self):
        ci = ComputerInterface()
        result = ci.browse("https://example.com")
        assert result["success"] is True
        assert result["status_code"] == 200

    def test_command_history(self):
        ci = ComputerInterface()
        ci.execute_command("echo hello")
        assert len(ci.get_command_history()) == 1

    def test_browse_history(self):
        ci = ComputerInterface()
        ci.browse("https://example.com")
        assert len(ci.get_browse_history()) == 1


# ============================================================================
# VoiceInterface Tests (AC10, AC11)
# ============================================================================

class TestVoiceInterface:
    def test_text_to_speech(self):
        """AC10: VoiceInterface converts text to speech (simulation)."""
        vi = VoiceInterface()
        result = vi.text_to_speech("Hello world")
        assert result["success"] is True
        assert result["text"] == "Hello world"
        assert result["duration_seconds"] > 0

    def test_speech_to_text(self):
        """AC11: VoiceInterface converts speech to text (simulation)."""
        vi = VoiceInterface()
        result = vi.speech_to_text({"transcript": "Hello world"})
        assert result == "Hello world"

    def test_speech_to_text_default(self):
        vi = VoiceInterface()
        result = vi.speech_to_text({})
        assert "Simulated" in result

    def test_list_voices(self):
        vi = VoiceInterface()
        voices = vi.list_voices()
        assert len(voices["voices"]) > 0

    def test_statistics(self):
        vi = VoiceInterface()
        vi.text_to_speech("test")
        vi.speech_to_text({"transcript": "test"})
        stats = vi.get_statistics()
        assert stats["tts_calls"] == 1
        assert stats["stt_calls"] == 1


# ============================================================================
# ProjectContextManager Tests (AC12, AC13)
# ============================================================================

class TestProjectContextManager:
    def test_get_set_context(self):
        """AC12: ProjectContextManager maintains context across calls."""
        pcm = ProjectContextManager()
        pcm.set_context("current_project", "ORION")
        assert pcm.get("current_project") == "ORION"
        ctx = pcm.get_context()
        assert ctx["current_project"] == "ORION"

    def test_delete_context(self):
        pcm = ProjectContextManager()
        pcm.set_context("test_key", "value")
        assert pcm.delete("test_key") is True
        assert pcm.get("test_key") is None

    def test_history_tracking(self):
        """AC13: ProjectContextManager tracks interaction history."""
        pcm = ProjectContextManager()
        pcm.add_history({"type": "command", "text": "test"})
        pcm.add_history({"type": "response", "text": "done"})
        assert len(pcm.get_history()) == 2

    def test_recent_history(self):
        pcm = ProjectContextManager()
        for i in range(15):
            pcm.add_history({"index": i})
        recent = pcm.get_recent_history(5)
        assert len(recent) == 5
        assert recent[-1]["index"] == 14

    def test_history_trim(self):
        pcm = ProjectContextManager()
        for i in range(150):
            pcm.add_history({"index": i})
        assert len(pcm.get_history()) == 100

    def test_clear_history(self):
        pcm = ProjectContextManager()
        pcm.add_history({"test": True})
        count = pcm.clear_history()
        assert count == 1
        assert len(pcm.get_history()) == 0

    def test_search_history(self):
        pcm = ProjectContextManager()
        pcm.add_history({"text": "create a new project"})
        pcm.add_history({"text": "analyze data"})
        results = pcm.search_history("create")
        assert len(results) == 1


# ============================================================================
# JARVISInterface Tests (AC14, AC15, AC16, AC17, AC18, AC19)
# ============================================================================

class TestJARVISInterface:
    def test_process_simple_command(self):
        """AC14: JARVISInterface processes a simple command."""
        jarvis = JARVISInterface()
        response = jarvis.process_command("What is the status?")
        assert isinstance(response, JARVISResponse)
        assert response.success is True
        assert response.latency_ms > 0

    def test_process_action_command(self):
        jarvis = JARVISInterface()
        response = jarvis.process_command("Run the test suite")
        assert response.command_type == "action"
        assert response.success is True
        assert response.task_id is not None

    def test_process_create_command(self):
        jarvis = JARVISInterface()
        response = jarvis.process_command("Create a new data pipeline")
        assert response.command_type == "create"
        assert response.task_id is not None

    def test_process_help_command(self):
        jarvis = JARVISInterface()
        response = jarvis.process_command("Help me understand the system")
        assert response.command_type == "help"
        assert len(response.suggestions) > 0

    def test_process_unknown_command(self):
        jarvis = JARVISInterface()
        response = jarvis.process_command("xyzzy foobar baz")
        assert response.success is False
        assert response.command_type == "unknown"

    def test_process_empty_command(self):
        jarvis = JARVISInterface()
        response = jarvis.process_command("")
        assert response.command_type == "unknown"

    def test_process_complex_command(self):
        """AC15: JARVISInterface processes a complex multi-step command."""
        jarvis = JARVISInterface()
        response = jarvis.process_command("Research quantum computing then generate a report and analyze the findings")
        assert response.success is True
        assert response.command_type in ("search", "research", "plan", "create")

    def test_process_complex_goal(self):
        """AC19: Founder gives high-level goal → ORION plans and executes."""
        jarvis = JARVISInterface()
        response = jarvis.process_command("Plan a complete testing strategy for the new module then execute it")
        assert response.success is True
        assert response.task_id is not None

    def test_task_manager_integration(self):
        """AC16: JARVISInterface integrates with TaskManager."""
        jarvis = JARVISInterface()
        jarvis.process_command("Create a new project task")
        tm = jarvis.get_task_manager()
        assert tm.task_count() >= 1

    def test_notification_manager_integration(self):
        """AC17: JARVISInterface integrates with NotificationManager."""
        jarvis = JARVISInterface()
        response = jarvis.process_command("Notify me about the update")
        nm = jarvis.get_notification_manager()
        assert len(nm.get_notifications()) >= 1

    def test_context_manager_integration(self):
        """AC18: JARVISInterface integrates with ProjectContextManager."""
        jarvis = JARVISInterface()
        jarvis.set_project_context("current_project", "ORION")
        ctx = jarvis.get_project_context()
        assert ctx["current_project"] == "ORION"

    def test_context_persists_across_commands(self):
        jarvis = JARVISInterface()
        jarvis.set_project_context("test_key", "test_value")
        jarvis.process_command("What is the status?")
        jarvis.process_command("Create a task")
        ctx = jarvis.get_project_context()
        assert ctx["test_key"] == "test_value"

    def test_history_recorded(self):
        jarvis = JARVISInterface()
        jarvis.process_command("What is the status?")
        jarvis.process_command("Create a task")
        pcm = jarvis.get_context_manager()
        history = pcm.get_history()
        # Each command adds 2 entries (command + response)
        assert len(history) >= 4

    def test_statistics(self):
        jarvis = JARVISInterface()
        jarvis.process_command("test")
        stats = jarvis.get_statistics()
        assert stats["total_commands"] == 1
        assert stats["avg_latency_ms"] > 0

    def test_status_command(self):
        jarvis = JARVISInterface()
        jarvis.process_command("Create a task")
        response = jarvis.process_command("What is the status?")
        assert response.command_type == "status"
        assert response.data["total_tasks"] >= 1

    def test_search_command(self):
        jarvis = JARVISInterface()
        response = jarvis.process_command("Search for quantum computing papers")
        assert response.command_type == "search"
        assert response.success is True

    def test_analyze_command(self):
        jarvis = JARVISInterface()
        response = jarvis.process_command("Analyze the performance data")
        assert response.command_type == "analyze"
        assert response.task_id is not None

    def test_execute_command(self):
        jarvis = JARVISInterface()
        response = jarvis.process_command("Execute the deployment script")
        assert response.command_type == "execute"
        assert response.success is True
