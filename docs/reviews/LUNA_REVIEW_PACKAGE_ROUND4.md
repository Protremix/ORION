# LUNA REVIEW PACKAGE — Round 4 Security Fixes

## PROJECT
ORION — Physical Intelligence OS

## PHASE
Phase 001B — Security Recovery (Luna Round 4 Findings)

## COMMIT SHA
eb9d3ec

## BRANCH
main

## TASK
Fix all Luna Round 4 security findings: domain simulator safety gates, action category server-side reclassification, task state HMAC integrity, vision TOCTOU safety, image URL scheme validation.

## ACCEPTANCE CRITERIA
1. Domain simulators (home, drone) must reject physical actions without `safety_approved=True`
2. API must server-side reclassify action_category — device_id present → must be PHYSICAL
3. Task state must have HMAC-SHA256 integrity protection — tampered state rejected (fail-closed)
4. Vision path validation must be TOCTOU-safe (return bytes, not path)
5. Image URL scheme validation — only HTTPS and data:image/ allowed
6. All tests pass (0 failures, 0 errors)
7. Ruff lint clean
8. Mypy type check clean

## FILES CHANGED
- `src/api/__init__.py` — server-side action_category reclassification
- `src/arbitration/action_arbitration.py` — action category enforcement
- `src/contracts/contracts.py` — safety_approved field on ActionProposal
- `src/domains/drone/drone_simulator.py` — safety gate for physical actions
- `src/domains/home/home_simulator.py` — safety gate for physical actions (unlock, lock)
- `src/models/gpt4o_adapters.py` — TOCTOU-safe vision path, URL scheme validation
- `src/persistence/task_state.py` — HMAC-SHA256 state integrity
- `tests/conftest.py` — env var setup for all tests
- `tests/unit/test_round4_security.py` — 12 new security tests
- `tests/unit/test_drone_domain.py` — updated for safety gate
- `tests/unit/test_home_domain.py` — updated for safety gate
- `tests/unit/test_integration_phase8.py` — updated for safety gate
- `tests/unit/test_phase8.py` — updated for safety gate
- `tests/unit/test_vision_path_security.py` — updated for TOCTOU safety

## TEST RESULTS
667 passed, 9 skipped, 0 failed, 0 errors
Ruff: All checks passed
Mypy: Success: no issues found in 62 source files

## SECURITY RESULTS
- Domain safety gate: 6 tests (home unlock/lock rejected without safety_approved, drone takeoff rejected, all pass with safety_approved, non-physical actions unaffected)
- Action category reclassification: 2 tests (device_id+DIGITAL rejected, PHYSICAL without device_id rejected)
- Task state HMAC: 3 tests (HMAC saved, load verifies HMAC, tampered state rejected fail-closed)
- Vision security: 4 tests (TOCTOU-safe returns bytes, HTTP rejected, FTP rejected, HTTPS+data allowed)
- Total new security tests: 12

## SAFETY RESULTS
- All domain simulators enforce safety_approved before physical action execution
- Fail-closed behavior on tampered task state
- No bypass vectors identified in new code

## LICENSE RESULTS
- All ORION-owned code follows Apache 2.0
- No new external dependencies added

## CI RESULTS
- No suppressed failures (no `|| true` or `continue-on-error`)
- Clean install with `pip install -e ".[dev]"`

## KNOWN LIMITATIONS
- 9 tests skipped (require live PostgreSQL — Docker only)
- HMAC key sourced from `ORION_STATE_HMAC_KEY` env var (fail-closed if missing)

## KNOWN RISKS
- None identified in Round 4 fixes

## UNKNOWN ITEMS
- None

## PREVIOUS FAILURES
- Luna Round 3 found 3 security findings that Round 4 addresses

## FIXES
1. Added safety gate to HomeSimulation.execute_action() — checks safety_approved for unlock/lock
2. Added safety gate to DroneSimulation.execute_action() — checks safety_approved for all actions
3. API server-side reclassifies: device_id present → must be PHYSICAL, no device_id → cannot be PHYSICAL
4. TaskStateManager saves HMAC-SHA256 of state, verifies on load, rejects if mismatch
5. validate_image_path() now reads file bytes directly (TOCTOU-safe)
6. GPT4oVisionAdapter._prepare_image() validates URL scheme (HTTPS/data only)

## EVIDENCE
- Commit: eb9d3ec on main
- Test output: 667 passed, 9 skipped
- Ruff: All checks passed
- Mypy: Success: no issues found in 62 source files

## REPRODUCTION COMMANDS
pip install -e ".[dev]"
python -m pytest -q --tb=short
python -m pytest tests/unit/test_round4_security.py -v
python -m ruff check src/ tests/
python -m mypy src/ --ignore-missing-imports --no-strict-optional

## REVIEW REQUEST
Independently review the complete repository at commit eb9d3ec and determine whether the Round 4 security acceptance criteria are satisfied.
