# ORION Core State Machine — Phase 004

**License: Apache 2.0**

## Task Lifecycle States

```
                    ┌──────────┐
                    │ PENDING  │
                    └────┬─────┘
                         ↓
                    ┌──────────┐
                    │ PLANNING │
                    └────┬─────┘
                         ↓
                    ┌──────────┐     pause     ┌──────────┐
                    │ EXECUTING│──────────────→│  PAUSED   │
                    └────┬─────┘              └─────┬──────┘
                         │                          │ resume
                         ↓                          ↓
                    ┌──────────┐              ┌──────────┐
                    │ OBSERVING │              │ EXECUTING │
                    └────┬─────┘              └──────────┘
                         ↓
                    ┌──────────┐
                    │EVALUATING│
                    └────┬─────┘
                    ┌────┴────┐
                    ↓         ↓
              ┌──────────┐ ┌──────────┐
              │ COMPLETED │ │ FAILED   │
              └──────────┘ └──────────┘
```

## State Transitions

| From | To | Condition |
|------|----|-----------| 
| PENDING | PLANNING | Supervisor starts planning |
| PLANNING | EXECUTING | Plan generated and validated |
| PLANNING | FAILED | Plan generation failed |
| EXECUTING | PAUSED | User/system pause |
| PAUSED | EXECUTING | Resume with incomplete steps |
| PAUSED | COMPLETED | Resume with all steps done |
| EXECUTING | RECOVERING | Step failure detected |
| RECOVERING | EXECUTING | Retry successful |
| RECOVERING | FAILED | Escalation/abort |
| EXECUTING | COMPLETED | All steps completed |
| EXECUTING | FAILED | Critical step failure |
| EXECUTING | CANCELLED | User cancellation |
| * | CRASHED | Lost in crash recovery |

## Step States

| State | Description |
|-------|-------------|
| PENDING | Waiting for dependencies |
| RUNNING | Currently executing |
| COMPLETED | Finished successfully |
| FAILED | Error occurred |
| SKIPPED | Non-critical, skipped after retries |
| BLOCKED | Dependency failed |

## Error Recovery Flow

```
Step FAILED
    ↓
Retry? (retry_count < max_retries)
    ├─ YES → Reset to PENDING, exponential backoff
    └─ NO → Critical?
              ├─ NO → SKIP_STEP, continue task
              └─ YES → ESCALATE, mark task FAILED
```

## Crash Recovery Flow

```
System restart
    ↓
Load snapshot from TaskEngine.snapshot()
    ↓
For each task:
    ├─ Status was EXECUTING/PLANNING → mark CRASHED
    ├─ Status was COMPLETED → skip
    └─ Status was PENDING → re-queue
    ↓
Log crash event to AuditLogger
    ↓
Resume from safe checkpoint
```
