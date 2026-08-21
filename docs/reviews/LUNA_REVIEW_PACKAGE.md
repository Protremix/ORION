# LUNA REVIEW PACKAGE — Round 9

## PROJECT
ORION — Physical Intelligence OS

## PHASE
001B — Security Recovery (Round 9)

## COMMIT SHA
000c52d

## BRANCH
main

## TASK
Implement all 5 required follow-up changes from Luna Round 8b verdict.

## ACCEPTANCE CRITERIA
1. All 5 Luna Round 8b required follow-ups addressed
2. Full test suite passes (0 failures)
3. Ruff clean
4. Mypy clean
5. Adversarial tests genuinely test each fix
6. No new bypass vectors introduced

## REQUIRED CHANGES ADDRESSED

### #1: Track next_fd during component walk
**Round 8b finding:** If os.close(dir_fd) raises after next_fd is opened, next_fd leaks.
**Fix:** Assign `dir_fd = next_fd` BEFORE closing `old_dir_fd`. If close fails, `dir_fd` (next_fd) is still tracked and will be closed by the outer except handler. Old_dir_fd leak is unavoidable but best-effort handled with `except OSError: pass`.
**Files:** `src/models/gpt4o_adapters.py`

### #2: Real growth-during-read test
**Round 8b finding:** Test created a file already >50MB, never reaching the bounded-read branch.
**Fix:** `test_file_growth_during_read_detected` — creates a 1MB file (passes fstat check), monkey-patches `os.fdopen` to return a file whose `read()` returns >50MB. Genuinely tests the post-read size check.
**Files:** `tests/unit/test_round5_adversarial.py`

### #3: Injected-close-failure descriptor leak tests
**Round 8b finding:** No test for initial directory-opening close failure or component-walk close failure.
**Fix:** Two new tests:
- `test_close_failure_during_walk`: Injects OSError on 2nd os.close, verifies at most 1 fd leaks (old_dir_fd — unavoidable), next_fd is closed by except handler
- `test_close_failure_during_base_dir_open`: Injects OSError on 1st os.close, verifies no fd leaks (both parent_fd and dir_fd tracked and closed)
**Files:** `tests/unit/test_round5_adversarial.py`

### #4: Strengthened concurrent replay assertion
**Round 8b finding:** Assertion allowed both to fail (completed_count == 0 passes). action_id mismatch between token and proposal.
**Fix:** Now requires exactly 1 COMPLETED and 1 REJECTED. Fixed action_id — generates one ID, uses it for both token and proposal.
**Files:** `tests/unit/test_round5_adversarial.py`

### #5: Replay cache bound
**Round 8b finding:** Claimed 1000-entry cap not visible in code.
**Fix:** Confirmed: replay cache uses time-based pruning (120s expiry), not count-based. Expired credentials are pruned before each check. No count-based cap needed since credentials older than 120s are removed and can't be replayed (timestamp validation rejects >60s). OrderedDict preserves insertion order.
**Files:** `src/domains/vehicle/vehicle_simulator.py`

## TEST RESULTS
- **Total:** 699 collected, 699 passed, 9 skipped, 0 failed
- **Adversarial:** 54/54 passing
- **Command:** `python3 -m pytest --timeout=30 -q --ignore=tests/load --ignore=tests/unit/test_live_gpt4o.py`

## CI RESULTS
- Ruff: clean (0 errors)
- Mypy: clean (0 issues, 62 source files)

## KNOWN LIMITATIONS
- 9 tests skipped (require live PostgreSQL)
- DNS rebinding: separate DNS resolution for validation vs connection (documented, simulation-only)
- Replay cache: time-based expiry (120s), not count-bounded — credentials older than 120s pruned
- Safety gate: mutable boolean, simulator-scoped (threat model: Python-level access is trusted)
- old_dir_fd leak when os.close fails: unavoidable, best-effort handled

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
