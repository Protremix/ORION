# LUNA REVIEW PACKAGE — Round 11

## PROJECT
ORION — Physical Intelligence OS

## PHASE
001B — Security Recovery (Round 11)

## COMMIT SHA
(to be set after commit)

## BRANCH
main

## TASK
Fix Luna Round 10 finding: Replay cache must use 10,000-entry cap with FIFO eviction (not 1,000-entry rejection).

## ACCEPTANCE CRITERIA
1. Replay cache cap at 10,000 entries with FIFO eviction (popitem(last=False))
2. Adversarial test verifies eviction behavior (oldest evicted, new accepted)
3. Full test suite passes (0 failures)
4. Ruff clean, Mypy clean

## REQUIRED CHANGES ADDRESSED

### #1: Replay cache — 10,000-entry cap with FIFO eviction
**Round 10 finding:** Cache was capped at 1,000 with rejection (not eviction). Luna required 10,000-entry cap with `popitem(last=False)` eviction.
**Fix:** Changed `MAX_REPLAY_CACHE` from 1,000 to 10,000. Replaced rejection logic with eviction:
- Pre-check: `while len(cache) > MAX_REPLAY_CACHE: popitem(last=False)` — evicts oldest before replay check
- Post-insertion: `while len(cache) > MAX_REPLAY_CACHE: popitem(last=False)` — evicts oldest after adding new credential
- OrderedDict preserves insertion order — oldest evicted first (FIFO)
- Prevents memory exhaustion while allowing continued operation
**Files:** `src/domains/vehicle/vehicle_simulator.py`

### #2: Adversarial test for eviction behavior
**Round 10 finding:** Test didn't verify eviction semantics (threshold, FIFO, continued acceptance).
**Fix:** `test_replay_cache_evicts_oldest_at_cap`:
1. Pre-populates cache with 10,001 entries (directly, to avoid slow 10,100 propose_action calls)
2. Calls `propose_action` with a new valid credential — triggers production pruning + eviction
3. Asserts cache ≤ 10,000 entries (eviction ran)
4. Asserts oldest entry (first_cred) was evicted (FIFO verified)
5. Asserts new credential was accepted into cache (continued operation verified)
**Files:** `tests/unit/test_round5_adversarial.py`

## TEST RESULTS
- **Total:** 701 collected, 701 passed, 9 skipped, 0 failed
- **Adversarial:** 55/55 passing
- **Command:** `python3 -m pytest --timeout=30 -q --ignore=tests/load --ignore=tests/unit/test_live_gpt4o.py`

## CI RESULTS
- Ruff: clean (0 errors)
- Mypy: clean (0 issues, 62 source files)

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
