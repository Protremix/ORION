# LUNA ROUND 6 VERDICT

Model: gpt-5.6-luna
Commit: dc07108 (review package)
Code commit: 4398e70

## VERDICT

VERDICT: REQUIRES_CHANGES

The claimed Round 6 fixes are not sufficient to satisfy Phase 001B acceptance criteria.

1. **HIGH — Public home-simulator mutation methods bypass the Safety Gateway**  
   **File:** `home_simulator.py`  
   **Lines:** approximately 113–124, 128–193, 195–248, 250–277  
   **Description:** `update_hvac()`, `trigger_fire_emergency()`, `clear_emergency()`, and `trigger_intrusion()` directly mutate physical state without validating a cryptographic safety token or enforcing the safety gate. `_safety_gate_active` is only assigned and is not used as an authorization check. An attacker able to invoke these public methods can bypass `execute_action()` and physical-action authorization.  
   **Suggested fix:** Make mutation methods private and callable only by the authenticated dispatcher, or enforce the same server-side authorization and cryptographic token validation at every physical mutation boundary. Do not rely on a mutable boolean gate.

2. **HIGH — Vehicle simulator exposes unauthenticated physical-state mutation paths**  
   **File:** `vehicle_simulator.py`  
   **Lines:** approximately 92–128, 131–234, and 419–437  
   **Description:** Public methods including `spawn_vehicle()`, `add_traffic_light()`, `set_traffic_light_state()`, `step()`, and `run_scenario()` mutate simulation state without Safety Gateway authorization. Public entity registries and objects also remain directly mutable. This permits bypassing the intended action-classification and safety controls.  
   **Suggested fix:** Separate trusted simulation internals from externally callable command APIs. Make state private or immutable to untrusted callers, and require all externally initiated physical mutations to pass through authenticated, server-side authorization.

3. **HIGH — Emergency-reset replay protection is not atomic**  
   **File:** `vehicle_simulator.py`  
   **Lines:** approximately 486–535  
   **Description:** The implementation checks whether a credential is in `_used_reset_credentials` and adds it later as separate operations. Concurrent requests using the same valid credential can both pass the check before either request records the credential.  
   **Suggested fix:** Protect validation and credential insertion with a lock or atomic compare-and-insert operation. Consume the credential before performing the reset mutation, with appropriate failure handling.

4. **MEDIUM — Emergency-reset timestamp validation accepts future-dated credentials**  
   **File:** `vehicle_simulator.py`  
   **Lines:** approximately 477–485  
   **Description:** `abs(now - cred_timestamp) > 60.0` permits credentials timestamped up to 60 seconds in the future. This weakens freshness validation and permits pre-generated credentials to become valid before their intended issuance time.  
   **Suggested fix:** Reject future timestamps explicitly, for example when `cred_timestamp > now + allowed_clock_skew`, and separately enforce the maximum credential age.

5. **HIGH — SSRF protection is bypassable through redirects and DNS rebinding**  
   **File:** `gpt4o_adapters.py`  
   **Lines:** approximately 302–365, `GPT4oVisionAdapter._prepare_image()`  
   **Description:** The initial hostname and DNS result are validated, but `urllib.request.urlopen()` follows redirects without revalidating each destination. A public URL can redirect to an internal, HTTP, or metadata-service address. The connection is also not bound to the previously validated IP, allowing DNS rebinding. DNS validation does not consistently reject all reserved, multicast, unspecified, or carrier-grade address ranges.  
   **Suggested fix:** Disable automatic redirects or revalidate every redirect and require HTTPS. Resolve and connect to a validated IP while preserving the required Host/SNI behavior. Reject private, loopback, link-local, reserved, multicast, unspecified, and carrier-grade ranges for IPv4 and IPv6. Enforce response-size limits during streaming reads.

6. **MEDIUM — Descriptor-based vision opening is not fully TOCTOU-safe**  
   **File:** `gpt4o_adapters.py`  
   **Lines:** approximately 88–143, `validate_image_path()`  
   **Description:** Child components are opened with `O_NOFOLLOW`, but `base_dir` is first resolved and then opened by absolute path. If an attacker can modify an ancestor of `base_dir`, the trusted boundary can still be changed between validation and opening. The final descriptor is also not verified as a regular file, allowing special files such as FIFOs or devices.  
   **Suggested fix:** Open a trusted root directory descriptor first and walk the configured base path relative to that descriptor using `O_NOFOLLOW | O_DIRECTORY`. Use `fstat()` on the final descriptor and require a regular file with an appropriate size limit.

7. **MEDIUM — Required adversarial test coverage is incomplete**  
   **File:** `test_round5_adversarial.py`  
   **Lines:** approximately 14–29, 289–318, and subsequent tests  
   **Description:** The required adversarial suite does not provide coverage for stale agent permission removal (fix 4) or descriptor-based vision opening (fix 9). The HTTPS/SSRF test is also effectively vacuous and does not demonstrate protection against redirects, DNS rebinding, or internal-address resolution. Therefore the repository does not establish that all 12 bypass vectors are blocked.  
   **Suggested fix:** Add executable tests for every listed bypass vector, including revocation with already-issued agent permissions, symlink/TOCTOU and special-file attacks, redirect-to-private-IP attacks, DNS rebinding, concurrent reset replay, future timestamps, NaN/Inf values, exact permission and actuator matching, and exception-to-audited-rejection behavior.

The remaining claimed changes may be present in isolated code paths, but the exposed bypasses above mean the complete Phase 001B acceptance criteria are not satisfied.

## CHUNK RESPONSES

### Chunk 1

Received chunk 1 of 3. I’ll wait for the remaining source files before issuing the independent verdict.

### Chunk 2

VERDICT: REQUIRES_CHANGES

Findings from the supplied source:

1. **HIGH** — Public physical-state mutation methods bypass the Safety Gateway.  
   **File:** `home_simulator.py`  
   **Lines:** approximately 113–124, 128–193, 195–248, 250–277  
   **Description:** `update_hvac()`, `trigger_fire_emergency()`, `clear_emergency()`, and `trigger_intrusion()` directly mutate physical entities without checking a cryptographic authorization token or enforcing `_safety_gate_active`. The `_safety_gate_active` field is only assigned; it is never validated by these methods. An attacker can invoke these methods directly instead of using `execute_action()`. This defeats the physical-action gating requirement for HVAC, lighting, locks, and emergency operations.  
   **Suggested fix:** Make all physical mutation methods private/internal, or enforce a common server-side authorization guard in every physical mutation entry point. Do not rely on a mutable `_safety_gate_active` boolean. Route all externally callable actions through one authenticated dispatcher.

2. **HIGH** — Vehicle simulator exposes direct physical mutation paths outside the Safety Gateway.  
   **File:** `vehicle_simulator.py`  
   **Lines:** approximately 92–128, 131–234, 419–437  
   **Description:** Methods such as `spawn_vehicle()`, `add_traffic_light()`, `set_traffic_light_state()`, `step()`, and `run_scenario()` mutate simulation state directly and do not enforce safety authorization. The comment claims direct methods are protected, but no such checks exist. In addition, the public `ego_vehicle`, controllers, and entity registries remain directly mutable.  
   **Suggested fix:** Separate trusted simulation internals from external APIs; expose only authenticated command methods, enforce authorization at the mutation boundary, and make internal state private or immutable from untrusted callers.

3. **HIGH** — Emergency-reset replay protection is not atomic and can be bypassed under concurrent requests.  
   **File:** `vehicle_simulator.py`  
   **Lines:** approximately 486–535  
   **Description:** The code checks `cred_str in self._used_reset_credentials` and later adds the credential in separate operations. Concurrent requests using the same valid credential can both pass the check before either adds the credential. The reset operation therefore has a time-of-check/time-of-use race.  
   **Suggested fix:** Protect credential validation and insertion with a lock or use an atomic compare-and-insert operation. Mark the credential consumed before performing the reset mutation, with rollback semantics if reset fails.

4. **MEDIUM** — Emergency-reset timestamp validation accepts future-dated credentials.  
   **File:** `vehicle_simulator.py`  
   **Lines:** approximately 477–485  
   **Description:** `abs(now - cred_timestamp) > 60.0` permits timestamps up to 60 seconds in the future. A credential generated for a future timestamp can be accepted and reused throughout its future validity interval.  
   **Suggested fix:** Require `0 <= now - cred_timestamp <= 60.0`, or use an explicit bounded clock-skew policy that separately limits future timestamps.

5. **MEDIUM** — Home emergency clearing has no used-credential tracking and is replayable.  
   **File:** `home_simulator.py`  
   **Lines:** approximately 195–229  
   **Description:** `clear_emergency()` validates an HMAC and timestamp but never records the credential as consumed. The same valid credential can be replayed repeatedly within the 60-second window. Although the Round 5 item specifically names the vehicle reset, this is the same emergency-reset class of bypass in another physical domain.  
   **Suggested fix:** Add nonce/credential tracking with atomic consumption, or use a server-issued single-use reset token. Reject future timestamps as well.

6. **HIGH** — Failed-action audit logging is best-effort rather than guaranteed before re-raise.  
   **File:** `audit_system.py`  
   **Lines:** approximately 497–533  
   **Description:** When `action_fn()` raises, the code attempts to append a `FAILED` audit event, but catches any audit failure, logs it, and then re-raises the original exception. Thus an action exception can escape without the required `FAILED` audit event. This violates the requirement for an audited rejection before re-raise.  
   **Suggested fix:** Normalize the failure path so audit persistence failure produces an explicit `AuditRollbackError`/security failure and prevents the original exception from being treated as the sole result. Use a durable fail-closed audit channel or an out-of-band failure queue that is guaranteed to record the rejection.

7. **HIGH** — Audit-log read failures are silently converted into an empty log, permitting chain discontinuity.  
   **File:** `audit_system.py`  
   **Lines:** approximately 335–341  
   **Description:** `_load_existing_events()` catches all read errors, logs them, and sets `_cache = []`. With file-backed storage, a subsequent append can proceed against a log whose existing contents were not successfully verified, creating an apparent new chain head and masking an unavailable or corrupted audit history.  
   **Suggested fix:** Fail initialization closed on storage-read or deserialization failure. Do not permit appends until the existing chain has been successfully loaded and verified.

8. **MEDIUM** — File-backed audit storage remains destructible despite the append-only requirement.  
   **File:** `audit_system.py`  
   **Lines:** approximately 270–273  
   **Description:** `FileStorageBackend.clear()` unlinks the audit file, while the in-memory backend rejects clearing. Any caller with access to the backend can erase the persistent audit log without an authorization or tamper-evident deletion event.  
   **Suggested fix:** Reject `clear()` for all production backends. If retention deletion is required, implement an authenticated archival workflow that records an immutable deletion/rotation event externally.

9. **MEDIUM** — Audit HMAC signing is optional, allowing unsigned audit events.  
   **File:** `audit_system.py`  
   **Lines:** approximately 399–405 and 548–554  
   **Description:** `append_event()` falls back to plain SHA-256 when `_hmac_secret` is absent. `verify_chain_integrity()` also treats unsigned events as valid when no key is supplied. This permits an attacker who can rewrite storage to recompute hashes without needing a secret.  
   **Suggested fix:** Require a configured HMAC key for safety/security events and fail closed if absent. Do not treat unsigned safety-relevant events as valid.

10. **LOW** — Safety-gate state can remain armed after vehicle execution exceptions.  
    **File:** `vehicle_simulator.py`  
    **Lines:** approximately 419–437 and 650–661  
    **Description:** `_safety_gate_active` is set to `True` before execution and reset only on the normal success path. If an exception occurs, the `except` block returns without clearing it. Although the shown direct methods do not currently check the flag, any future check would inherit stale authorization state.  
    **Suggested fix:** Use `try/finally` to always clear transient gate state, and replace the flag with scoped, cryptographically authenticated authorization context.

The actuator verifier does contain the claimed exact parameter matching and pre-comparison finite-value checks, and the vehicle reset contains HMAC, timestamp, and used-credential logic. However, the direct mutation paths, non-atomic replay tracking, optional audit signing, and non-guaranteed failure auditing leave the Phase 001B acceptance criteria unsatisfied.

### Chunk 3

VERDICT: REQUIRES_CHANGES

Findings:

1. **HIGH — SSRF protection can be bypassed through redirects and DNS rebinding**  
   **File:** `gpt4o_adapters.py`  
   **Line:** Approximately 302–365 (`GPT4oVisionAdapter._prepare_image`)  
   **Description:**  
   The implementation validates the initial hostname and performs DNS checks before calling `urllib.request.urlopen()`, but the actual request is not bound to the validated IP address. `urllib` follows redirects automatically, and redirected destinations are not revalidated. A public HTTPS URL can therefore redirect to an internal address, an HTTP URL, or a cloud metadata endpoint. DNS rebinding can also cause the second resolution performed during the request to differ from the one validated previously.  
   The DNS validation additionally checks only `is_private`, `is_loopback`, and `is_link_local` for resolved addresses, while direct IP validation also checks reserved and multicast ranges.  
   **Suggested fix:**  
   Disable automatic redirects or use a custom redirect handler that revalidates every destination and permits only HTTPS. Resolve the hostname, connect to the validated IP while preserving the original Host/SNI as appropriate, and reject all private, loopback, link-local, reserved, multicast, unspecified, and carrier-grade NAT ranges for both IPv4 and IPv6. Enforce a maximum response size using `Content-Length` and a bounded streaming read.

2. **MEDIUM — Descriptor-based vision opening is not fully TOCTOU-safe at the base-directory boundary**  
   **File:** `gpt4o_adapters.py`  
   **Line:** Approximately 88–143 (`validate_image_path`)  
   **Description:**  
   The individual path components below `base_dir` are opened with `O_NOFOLLOW`, which is a good mitigation. However, `base_dir` is first canonicalized with `Path.resolve()` and then opened by absolute pathname. Ancestor components of `base_dir` are still resolved by the kernel and may be replaced between validation and opening if an attacker can modify a writable ancestor. The implementation also does not require the final descriptor to refer to a regular file; FIFOs, devices, or other special files can be opened and read.  
   **Suggested fix:**  
   Open a trusted root directory descriptor first and walk the configured base path relative to that descriptor using `O_NOFOLLOW | O_DIRECTORY`. Validate the final descriptor with `fstat()` and require a regular file, with suitable size limits. Avoid relying on a separately resolved absolute pathname as the security boundary.

3. **MEDIUM — Required adversarial coverage is incomplete and one SSRF test is vacuous**  
   **File:** `test_round5_adversarial.py`  
   **Line:** Approximately 14–29, 289–318, and 323 onward  
   **Description:**  
   Change #11 requires adversarial tests for all bypass vectors, but this test file has no adversarial test for stale agent permission removal (change #4) and no test for descriptor-based vision file opening (change #9). The `test_no_https_passthrough` test catches all exceptions and passes:

   ```python
   except Exception:
       pass
   ```

   Consequently, it passes even if `_prepare_image()` still forwards the URL unchanged, or fails for an unrelated reason. The SSRF test does not monkeypatch the network call or inspect the returned value robustly enough to prove controlled downloading.  
   **Suggested fix:**  
   Add explicit tests for permission revocation followed by use of a previously issued/in-memory agent permission, including persistence and cache cases. Add symlink, nested-symlink, traversal, and replacement-race tests for `validate_image_path()`. For SSRF, mock `urlopen()` and assert that the request is made locally, the returned value is a `data:` URL, redirects are rejected or revalidated, and unsafe destinations are never contacted. Do not use a blanket exception handler that treats every failure as success.

The supplied source does verify the presence of the following claimed mechanisms, subject to the SSRF and test-coverage issues above:

- Server-side action classification tests are present.
- HVAC and lighting gating tests are present.
- Mutable-boolean-only authorization tests are present.
- Exact permission matching test is present.
- NaN/Inf rejection tests are present.
- Exact actuator-parameter matching test is present.
- Emergency-reset replay, expiry, and malformed-credential tests are present.
- A descriptor-based opening approach using `O_NOFOLLOW` is implemented, but its root-boundary handling is not completely race-safe.
- Controlled image downloading is attempted, but the redirect/DNS validation is incomplete.
- Exception-to-audited-failure integration tests are present.

