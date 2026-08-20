"""
ORION Runtime Layer — 24/7 Autonomous Operation

Provides:
- RuntimeSupervisor: main loop, task scheduling, worker management
- Worker: isolated task execution with crash recovery
- HealthMonitor: system health tracking and alerting

License: Apache 2.0
"""

from runtime.supervisor import RuntimeSupervisor, SupervisorState, SupervisorStatus
from runtime.worker import Worker, WorkerStatus, WorkerResult
