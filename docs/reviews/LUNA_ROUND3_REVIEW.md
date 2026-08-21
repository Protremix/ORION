# Luna Independent Review — Round 3

## Final Verdict: **REQUIRES_CHANGES**

The supplied source fixes several Round 2 findings, including debug-auth bypass, vision traversal, exact authority matching, API-level PHYSICAL routing, and exception handling in the first four actuator stages.

However, multiple acceptance criteria remain unsatisfied. Several claimed fixes are incomplete or only apply to one implementation while alternate repository paths remain bypassable.

## Blocking Findings

### 1. Actuator NaN/Infinity values are silently removed, not rejected

In `ActuatorVerificationPipeline.verify_command()`, dictionary inputs are normalized using:

```python
params = {k: v for k, v in params.items() if math.isfinite(v)}
```

A command such as:

```python
{"force": float("nan"), "domain": "industrial"}
```

becomes an empty parameter command and may pass the pipeline. This is still a NaN/Infinity bypass.

### 2. Unknown actuator parameters remain allowed

`RangeLimitStage.verify()` ignores parameters for which `_get_parameter_limit()` returns `None`. Therefore:

```python
{"unrecognized_actuator_output": 1000000.0}
```

can pass range validation. Unknown parameters must be rejected by an explicit per-domain allowlist.

### 3. Cross-domain emergency clearing has no authorization

`CrossDomainArbitrator.clear_emergency()` accepts no credential or authorization evidence and unconditionally restores every domain to `ACTIVE`.

Additional unauthenticated recovery paths exist:

- `HomeSimulation.clear_emergency()`
- `VehicleSimulation.propose_action()` accepts a caller-controlled `authorized=True` boolean rather than a verified credential or HMAC.

This directly fails criterion 24.

### 4. Audit records are mutable through persistence APIs

Both persistence implementations expose mutation paths:

- `StorageManager.update_audit_event()` changes event content, actor, timestamp, severity, etc.
- `StorageManager.delete_audit_event(..., admin_override=True)` deletes audit records.
- `PostgresStorageManager.update_audit_event()` permits changes including sequence number, hash, previous hash, and signature.
- `PostgresStorageManager.delete_audit_event()` deletes records without authorization.
- `AuditLog.get_events()` returns shallow copies of mutable `AuditEvent` objects.

Audit records are therefore not immutable.

### 5. HMAC audit signing is not consistently implemented

There are several unsigned or downgrade paths:

- `StorageManager.create_audit_event()` sets `signature = ""` and contains a signing TODO.
- PostgreSQL accepts a caller-supplied signature without computing or verifying it.
- `AuditLog` only signs when an optional constructor secret is provided.
- `ActuatorVerificationPipeline` falls back to plain SHA-256 when no environment key is configured.

Criterion 17 requires HMAC-SHA256 signatures, not optional signing or silent SHA-256 downgrade.

### 6. Hash-chain sequence validation is incomplete

The actuator-local audit log validates contiguous sequence numbers, but other authoritative audit implementations do not:

- SQLite verification does not require contiguous or unique sequence numbers.
- PostgreSQL accepts caller-supplied sequence numbers.
- PostgreSQL verification does not validate a genesis link or contiguous sequences.
- The database schema does not consistently enforce `UNIQUE NOT NULL` on sequence numbers.

Thus criterion 23 is not satisfied repository-wide.

### 7. Permission wildcard and exact-action bypasses remain

`SAFETY_CRITICAL_ACTIONS` is incomplete. It omits mapped supervisor operations such as:

- `approve_action`
- `modify_config`

Consequently, an agent with `"*"` or the exact string `"approve_action"` can be authorized without holding `SUPERVISOR`.

The wildcard implementation also returns `True` for any mapped non-listed action regardless of its required rank. Safety criticality should derive from the required permission level and action semantics, not only a manually maintained partial name set.

### 8. Permission persistence fails open without an HMAC key

`PermissionChecker.load_from_storage()` logs a warning but still loads unverified permission rows when no audit key is available:

```python
elif not expected_hmac:
    logger.warning("No audit key — cannot verify permission integrity on load")
```

It must refuse to load any permissions if the integrity key is unavailable.

The permission audit-log HMAC is also computed with one `time.time()` value while a separate timestamp is persisted, making independent verification impossible.

### 9. API validation is not actually wired to `InputValidator`

`src/api/validation.py` is not used by `ORIONAPI`. The API instead uses permissive helpers that only check non-`None` or `dict` type.

Examples still accepted include:

- Empty observation sources
- Non-string recall queries
- Negative or non-integer recall limits
- Unsupported domains
- Dangerous planning strings that `InputValidator.validate_goal()` would reject
- Actions without `action_type`
- Invalid command/parameter structures
- Invalid emergency-stop domains

Criterion 15 requires validation on every public API method.

### 10. Memory authorization is not comprehensive

`MemoryStore.write_memory()` now requires `actor_permissions`, but alternate paths remain:

- `StorageManager.create_memory()`
- `StorageManager.update_memory()`
- `StorageManager.delete_memory()`
- PostgreSQL equivalents

These operations have no authorization requirement.

Additionally, `ORIONAPI.remember()` calls the configured memory backend without forwarding verified authorization context. Caller-supplied permission strings such as `["admin"]` are also trusted directly by `MemoryStore`, rather than bound to an authenticated principal.

### 11. Founder approval is not cryptographically enforced

At the API layer, FINANCIAL, LEGAL, and STRATEGIC actions are denied, which is safe. However, `ActionArbitration.authorize_action()` treats any non-empty `human_approval_signature` as Founder approval and does not verify:

- signer identity,
- Founder role,
- payload binding,
- expiry,
- nonce, or
- HMAC/signature validity.

This is a forgeable approval bypass on a lower-level action path.

### 12. Pipeline audit failure is not fail-closed

The first four actuator stages catch exceptions, but `AuditLogStage.record()` is outside an exception boundary. External audit storage failures are swallowed while a passed command remains passed:

```python
except Exception as e:
    logger.error(...)
```

A safety-critical command must not be reported as approved when mandatory audit persistence fails.

---

# Criterion-by-Criterion Findings

| # | Acceptance Criterion | Finding |
|---|---|---|
| 1 | Clean venv install with `pip install -e ".[dev]"` | **NOT INDEPENDENTLY ESTABLISHED.** The packaging configuration appears compatible with editable installation, but no command execution evidence was independently produced in this review. Separately, the Docker build installs before copying `src`, `simulation`, and `README.md`, which likely breaks the Docker image build. |
| 2 | Zero test collection errors | **NOT INDEPENDENTLY ESTABLISHED.** No collection run was performed here. There are fragile mixed imports such as `src.eval` versus `eval` and `src.audit` versus `audit`, apparently dependent on path manipulation. |
| 3 | All tests pass; live PG may skip | **NOT INDEPENDENTLY ESTABLISHED.** Supplied result totals were not treated as independent proof. Security gaps are also not adequately covered by the tests. |
| 4 | Ruff lint clean | **NOT INDEPENDENTLY ESTABLISHED.** CI only checks `src/`, while the reproduction command checks `src/ tests/`. The Ruff configuration also suppresses several broad rules. |
| 5 | Mypy clean | **NOT INDEPENDENTLY ESTABLISHED.** Configuration suppresses multiple important error classes. No independent invocation was performed. |
| 6 | CI has no `\|\| true` failures | **PASS.** No suppressed CI command failure was found in the supplied workflow. |
| 7 | Permission persistence with integrity | **FAIL.** Unverified records load when the HMAC key is absent; audit timestamp signing is inconsistent. |
| 8 | Financial/legal/strategic enforcement | **FAIL.** API denial is safe, but arbitration accepts any non-empty, unverified approval string. |
| 9 | Environment-based signing key management; no hardcoded keys | **PASS, narrowly.** No hardcoded secret key was found in the reviewed production code; policy keys use environment variables or explicit injection. Mandatory-key handling is still inconsistent under criteria 7 and 17. |
| 10 | Docker non-root user | **PASS.** `USER orion` is configured. The Docker build order is nevertheless defective because editable installation occurs before source and README are copied. |
| 11 | Vision path traversal validation | **PASS.** Resolved-path containment and symlink escape checks are present. |
| 12 | No debug-mode bypass | **PASS.** `debug_mode` does not affect authentication. Disabled authentication also fails closed. |
| 13 | No wildcard bypass for unmapped/safety-critical actions | **FAIL.** Wildcard and exact grants still authorize supervisor-level actions omitted from `SAFETY_CRITICAL_ACTIONS`, notably `approve_action`. |
| 14 | PHYSICAL actions require `device_id` and Safety Gateway | **PASS at ORION API/HAL boundary.** PHYSICAL API actions require `device_id`, Safety Gateway, and HAL. HAL also denies normal commands without a gateway. |
| 15 | Input validation on all API methods | **FAIL.** `InputValidator` is not wired into `ORIONAPI`; numerous malformed values remain accepted. |
| 16 | Memory writes require authorization | **FAIL.** Generic SQLite/PostgreSQL memory mutation paths remain unauthenticated, and authorization is not consistently propagated from the API. |
| 17 | Audit signatures implemented using HMAC-SHA256 | **FAIL.** Multiple audit stores are unsigned or downgrade to plain SHA-256. |
| 18 | NaN/Infinity rejected in actuator checks | **FAIL.** Dictionary normalization silently drops non-finite values, allowing the resulting command to continue. |
| 19 | Unknown actuator parameters rejected | **FAIL.** Unknown parameters without a configured limit are ignored by range validation. |
| 20 | Authority check exact match | **PASS.** `AuthorityCheckStage` uses exact membership rather than prefix matching. |
| 21 | Pipeline fails closed on exceptions | **FAIL.** Stages 1–4 fail closed, but audit-stage and external-storage failures do not. |
| 22 | Audit log entries immutable | **FAIL.** SQLite and PostgreSQL expose update/delete APIs; `AuditLog` also exposes mutable event references. |
| 23 | Hash chain validates sequence numbers | **FAIL.** Only the actuator-local log validates contiguous sequences; SQLite/PostgreSQL audit verification does not do so comprehensively. |
| 24 | Cross-domain emergency clearing requires authorization | **FAIL.** `clear_emergency()` is entirely unauthenticated; other domain recovery paths are similarly weak. |

## Required Remediation Before Approval

1. Reject non-finite actuator values before normalization; never silently remove them.
2. Add strict per-domain actuator parameter allowlists and reject unknown keys.
3. Require verified authorization credentials for every emergency-clear/reset path.
4. Make all audit stores append-only by removing update/delete APIs or enforcing immutable database controls.
5. Require an environment/injected HMAC key for audit operation; fail closed if unavailable.
6. Enforce genesis, uniqueness, and contiguous sequence numbers in all audit implementations.
7. Base wildcard/exact permission decisions on required privilege rank and a complete safety classification.
8. Refuse permission persistence loading when HMAC verification cannot be performed.
9. Wire `InputValidator` into every public `ORIONAPI` method.
10. Require authenticated authorization context for every memory create, update, and delete path.
11. Cryptographically verify Founder approvals and bind them to the exact action payload.
12. Treat audit persistence failure as command rejection.
13. Correct the Docker build order by copying packaging metadata, README, and package sources before editable installation.

**Final verdict: REQUIRES_CHANGES.**