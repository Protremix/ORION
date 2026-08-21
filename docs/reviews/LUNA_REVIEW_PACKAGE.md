# LUNA REVIEW PACKAGE — Round 10

## PROJECT
ORION — Physical Intelligence OS

## PHASE
001B — Security Recovery (Round 10)

## COMMIT SHA
9a09831

## BRANCH
main

## TASK
Implement 2 remaining required changes from Luna Round 9 verdict.

## REQUIRED CHANGES ADDRESSED

### #1: Component-walk adversarial test must exercise the exception path
**Round 9 finding:** Test injected close failure which was swallowed — never forced a subsequent exception to verify next_fd cleanup.
**Fix:** Test now injects BOTH `flaky_close` (2nd close fails, swallowed by `except OSError: pass`) AND `failing_fstat` (raises OSError after next_fd is assigned to dir_fd). This forces the outer except handler to run, which must close `dir_fd` (next_fd). Verifies at most 1 fd leaks (old_dir_fd — unavoidable).
**Files:** `tests/unit/test_round5_adversarial.py`

### #2: Replay cache must have count-based bound
**Round 9 finding:** Time-based pruning prevents replay but doesn't prevent memory exhaustion from unlimited valid credentials.
**Fix:** Added count-based cap (10000 entries). After time-based pruning, if cache exceeds 10000, evicts oldest entries via `OrderedDict.popitem(last=False)` (insertion-order eviction). Prevents unbounded memory growth while preserving replay protection for recently-used credentials.
**Files:** `src/domains/vehicle/vehicle_simulator.py`

## TEST RESULTS
- 699 passed, 9 skipped, 0 failed
- Adversarial: 54/54 passing
- Ruff: clean
- Mypy: clean (62 source files)

## REPRODUCTION COMMANDS
```bash
pip install -e ".[dev]"
ORION_LEASE_SIGNING_KEY=test-lease-signing-key \
ORION_AUDIT_KEY=test-audit-key \
ORION_EMERGENCY_HMAC_KEY=test-emergency-hmac-key \
ORION_SAFETY_AUTH_KEY=test-safety-key \
python3 -m pytest --timeout=30 -q --ignore=tests/load --ignore=tests/unit/test_live_gpt4o.py
python3 -m ruff check src/ tests/
python3 -m mypy src/ --ignore-missing-imports
```
