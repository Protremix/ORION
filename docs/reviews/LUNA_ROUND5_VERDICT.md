# Independent Security Review — Commit `11f2289`

## Verdict: **REQUIRES_CHANGES**

The fixes address several of the previously reported issues, but they do not establish a reliable fail-closed security boundary. Multiple bypasses remain, including a direct bypass of physical-action classification and safety-gateway enforcement.

The reported test result is not sufficient evidence of security closure: the tests primarily verify caller-supplied flags and do not test adversarial inputs against the actual authorization boundaries.

---

## 1. Assessment of vectors 1–10

Because the package does not reproduce the exact Round 4 vector definitions, I map the vectors to the numbered/security areas explicitly identified in the changed code and review summary.

### Vector 1 — Permission persistence integrity

**Status: Partially fixed — inadequate**

The permission rows are HMAC-protected in `src/api/permissions.py`, and loading fails closed when the key is absent. That portion is genuine.

However, permission revocation is not persisted correctly:

- `PermissionChecker.clear()` only clears the in-memory registry.
- `save_to_storage()` performs `INSERT OR REPLACE` for current agents but never deletes database rows for agents removed from the registry.
- On restart, `load_from_storage()` restores those stale rows.

Relevant locations:

- `src/api/permissions.py`, `PermissionChecker.clear()`
- `src/api/permissions.py`, `PermissionChecker.save_to_storage()`
- `src/api/permissions.py`, `PermissionChecker.load_from_storage()`

**Bypass:** revoke or remove an agent’s permissions, restart the process, and the previously authorized agent is restored from the stale database row.

**Severity: High**

Additional issue: `register_agent_permissions()` automatically calls `save_to_storage()` but ignores the boolean failure result. The in-memory authorization state can therefore diverge silently from persistent state.

---

### Vector 2 — Audit signatures and audit-chain integrity

**Status: Partially fixed — inadequate**

The HMAC-SHA256 chain and sequence-number validation are implemented correctly for ordinary commands. Deep-copying results from `get_entries()` also prevents ordinary callers from mutating returned objects and changing the internal log.

But there is a remaining NaN bypass:

```python
if command.command_type in ("zero_command", "emergency_stop", "stop", "safe_state"):
    return StageResult(... passed=True ...)
```

The rate stage returns before the finite-number check. `RangeLimitStage.verify()` then checks:

```python
if val < limit.min_val or val > limit.max_val:
```

For `float("nan")`, both comparisons are false, so a NaN parameter can pass the range stage for a stop-type command.

Relevant locations:

- `src/safety/actuator_verification.py`, `RateLimitStage.verify()`
- `src/safety/actuator_verification.py`, `RangeLimitStage.verify()`

**Bypass:** submit a stop/emergency command containing a NaN parameter. The command can pass rate and range validation and proceed to authority/audit handling.

**Severity: High**

There is also no immutable internal representation. `AuditLogEntry` remains mutable through internal/private access, and external storage receives the mutable object directly:

```python
self.external_storage.append(entry)
```

That is weaker than a true append-only or immutable audit sink.

---

### Vector 3 — API input validation

**Status: Inadequate**

Validation is present on several public methods, but it is not comprehensive and is mostly shallow.

Examples:

- `get_world_state()` does not validate `domain`.
- `emergency_stop()` does not validate `domain`.
- `recall()` does not validate `memory_type`.
- `remember()` does not validate `memory_type` or `metadata`.
- `execute()` validates only that `action` is a non-empty dictionary; nested fields such as `command_type`, `parameters`, `priority`, and action-specific values are not validated.
- `simulate()` similarly accepts arbitrary nested action contents.
- `validate_api_payload()` accepts any non-empty dictionary, including unexpected fields and dangerous nested structures.

Relevant locations:

- `src/api/__init__.py`, `ORIONAPI.get_world_state()`
- `src/api/__init__.py`, `ORIONAPI.emergency_stop()`
- `src/api/__init__.py`, `ORIONAPI.recall()`
- `src/api/__init__.py`, `ORIONAPI.remember()`
- `src/api/__init__.py`, `ORIONAPI.execute()`
- `src/api/__init__.py`, `ORIONAPI.simulate()`

**Severity: Medium**, potentially High where validated values are later used to control hardware or domain behavior.

---

### Vector 4 — PHYSICAL actions and `device_id`

**Status: **Not fixed — direct bypass remains**

The implementation validates the syntax of a supplied `device_id`, which is good. It also rejects:

- PHYSICAL without a `device_id`
- a supplied `device_id` classified as DIGITAL

However, classification is still caller-controlled when `device_id` is omitted:

```python
if action.get("device_id"):
    ...
else:
    if caller_cat == "PHYSICAL":
        return ...
    norm_cat = caller_cat
```

An attacker can submit an arbitrary hardware-like action without a `device_id` and label it `DIGITAL`. The API then reaches:

```python
return ORIONResponse(status=ORIONStatus.OK, data={"executed": True, "category": norm_cat})
```

Relevant location:

- `src/api/__init__.py`, `ORIONAPI.execute()`, action-category classification and final DIGITAL execution path

Example bypass:

```python
api.execute(
    {
        "action_type": "move_robot",
        "command_type": "activate_motor",
        "action_category": "DIGITAL",
    },
    ...
)
```

No server-side classification determines whether this is actually physical. The fix only prevents downgrading an action that already contains `device_id`.

**Severity: Critical**

This directly violates the requirement that physical actions require `device_id` and Safety Gateway enforcement.

---

### Vector 5 — Direct domain-simulator access / Safety Gateway enforcement

**Status: **Not fixed — bypass remains**

The simulators trust a caller-controlled boolean:

```python
getattr(proposal, "safety_approved", False) is True
```

There is no cryptographic authorization, gateway object identity check, lease validation, or call to an actual Safety Gateway. Any caller able to construct or mutate an `ActionProposal` can set:

```python
proposal.safety_approved = True
```

and bypass the claimed gateway boundary.

Relevant locations:

- `src/domains/home/home_simulator.py`, `HomeSimulation.execute_action()`
- `src/domains/vehicle/vehicle_simulator.py`, `VehicleSimulation.propose_action()`
- `src/domains/drone/drone_simulator.py`, `DroneSimulation.execute_action()`
- `src/domains/industrial/industrial_simulator.py`, `IndustrialSimulation.propose_action()`

There are also direct mutating methods that are not consistently gate-protected:

- `HomeSimulation.trigger_fire_emergency()`
- `HomeSimulation.trigger_intrusion()`
- `DroneSimulation.emergency_land()`
- `DroneSimulation.step()`
- `DroneSimulation.set_wind()`
- multiple vehicle and industrial mutators

The drone simulator additionally sets `_safety_gate_active = True` in `run_scenario()` and does not reliably clear it afterward, leaving a persistent authorization state.

**Severity: Critical**

The tests only verify that the boolean defaults to false. They do not demonstrate that an untrusted caller cannot set it to true.

---

### Vector 6 — Vision path traversal / TOCTOU

**Status: Partially fixed — inadequate against races**

The path boundary check, final-component `O_NOFOLLOW`, and parent symlink checks improve the situation. However, this is not actually TOCTOU-safe:

1. Parent directories are checked using path names.
2. An attacker can replace or rename a parent directory after validation.
3. `os.open(str(resolved), ...)` resolves the path again by name.
4. The file is read before the post-open realpath check.

The post-open check is too late; sensitive contents may already have been read.

Relevant location:

- `src/models/gpt4o_adapters.py`, `validate_image_path()`

A robust implementation needs directory-descriptor-based traversal using `openat`-style operations with `O_DIRECTORY | O_NOFOLLOW`, or an equivalent trusted storage abstraction.

**Severity: High**

---

### Vector 7 — Vision URL SSRF

**Status: Partially fixed — bypass remains**

The code checks URL schemes and attempts local DNS resolution, but this does not reliably protect the eventual OpenAI-side fetch:

```python
return url
```

The URL is passed to OpenAI, which may resolve it independently. Local DNS validation does not prevent:

- DNS rebinding
- resolution differences between the ORION host and OpenAI infrastructure
- private-address resolution after the local validation step
- IPv6 private/reserved addresses in the DNS-result branch, where only `is_private`, `is_loopback`, and `is_link_local` are checked

The DNS result path omits `is_reserved` and `is_multicast`, despite checking those properties for direct IP literals.

Relevant location:

- `src/models/gpt4o_adapters.py`, `GPT4oVisionAdapter._prepare_image()`

**Severity: High**

Allowing arbitrary caller-controlled HTTPS URLs to be fetched by a downstream service should be replaced with an allowlisted object-storage mechanism or server-side download with pinned DNS/IP validation.

---

### Vector 8 — Data URL validation

**Status: Mostly fixed, but incomplete**

The data URL parser correctly restricts the media type and base64 syntax and applies a size limit. That is a genuine improvement.

However:

- `request.image_data` is converted to base64 without an equivalent size limit.
- The decoded image content is not checked against a maximum size or image format.
- The 10 MB limit is applied to the encoded URL string, not directly to the source byte buffer.

Relevant location:

- `src/models/gpt4o_adapters.py`, `GPT4oVisionAdapter._prepare_image()`

**Severity: Medium**

This is primarily a resource-exhaustion concern rather than a direct authorization bypass.

---

### Vector 9 — Wildcard permission bypass

**Status: Inadequate — bypass remains**

Wildcard handling itself is more restrictive, but the action-resolution logic still converts some unknown strings into mapped actions using substring matching:

```python
for action, level in cls.DEFAULT_MAPPINGS.items():
    if action in ep.lower():
        return level
```

Consequently, an unmapped action such as:

```text
execute_untrusted_payload
```

can be treated as the mapped `execute` action. An agent holding `*` or `ALL` may then receive authorization because the resolver reports a non-safety-critical mapped action.

Related permissive matching also exists in `get_endpoint_level()`:

```python
if ep.endswith(path) or path.endswith(ep):
    return level
```

Relevant locations:

- `src/api/permissions.py`, `Permission.get_endpoint_level()`
- `src/api/permissions.py`, `PermissionChecker.check_permission()`

**Severity: High**

Permission resolution must use exact canonical action identifiers or an explicit, normalized route table. No substring or suffix inference should occur for authorization.

A secondary issue is that `PermissionChecker.check_permission()` is a `classmethod` and constructs a new checker internally:

```python
checker = cls()
agent_perms = checker.registry.get(agent_id, [])
```

This ignores an instance’s `_custom_registry`. That can cause authorization-policy confusion and may become a privilege bypass when a restrictive custom checker is expected to govern access but the global registry is consulted instead.

---

### Vector 10 — Financial/legal/strategic/category bypass

**Status: Partially fixed — inadequate**

Financial, legal, and strategic categories are blocked when the caller supplies those categories. Omitting `action_category` is also rejected.

But the category is still fundamentally caller-selected. An action with no `device_id` can be declared `DIGITAL`, regardless of its actual semantics. More generally, the server does not classify based on an authoritative action schema.

Relevant location:

- `src/api/__init__.py`, `ORIONAPI.execute()`

**Severity: Critical**

This is the same core issue as Vector 4 from a category-enforcement perspective: requiring a category is not equivalent to server-side classification.

---

## 2. New bypass vectors introduced or exposed by the fixes

### New Vector A — Fuzzy actuator parameter allowlist

`_get_parameter_limit()` accepts substring matches:

```python
if key in p_lower or p_lower in key:
    return limit
```

Thus parameters such as:

```text
velocity_override
unsafe_velocity
force_limit_bypass
```

may be accepted as known parameters if they contain or are contained by an allowed key.

Relevant location:

- `src/safety/actuator_verification.py`, `_get_parameter_limit()`

**Severity: High**

Parameter names must be exact matches after strict normalization.

---

### New Vector B — NaN accepted for stop commands

As described above, stop commands bypass the finite-number check and NaN passes range comparisons.

Relevant locations:

- `src/safety/actuator_verification.py`, `RateLimitStage.verify()`
- `src/safety/actuator_verification.py`, `RangeLimitStage.verify()`

**Severity: High**

Finite-number validation must run before any emergency/rate-limit shortcut, and range validation must explicitly reject non-finite values.

---

### New Vector C — Persistent stale permissions after revocation

The HMAC protects stale data just as effectively as current data. Integrity does not solve revocation.

Relevant locations:

- `src/api/permissions.py`, `PermissionChecker.clear()`
- `src/api/permissions.py`, `PermissionChecker.save_to_storage()`

**Severity: High**

Persistence must delete absent agents or use a transactional replacement of the complete registry.

---

### New Vector D — Reusable vehicle emergency-reset credential

Vehicle reset uses a static HMAC:

```python
expected_hmac = hmac_mod.new(
    expected_key.encode(),
    b"reset_emergency",
    hashlib.sha256
).hexdigest()
```

There is no timestamp, nonce, monotonic counter, or one-time-use tracking.

Relevant location:

- `src/domains/vehicle/vehicle_simulator.py`, `reset_emergency` branch

**Severity: High**

A captured valid credential can be replayed indefinitely.

---

### New Vector E — Authorization by mutable proposal flag

` safety_approved=True` is not an authorization artifact. It is ordinary mutable proposal data.

Relevant locations:

- all four domain simulator proposal/action entry points listed under Vector 5

**Severity: Critical**

The simulator must receive a gateway-issued signed decision, lease, or capability token and verify it independently.

---

### New Vector F — Exceptions before audit recording

In `ActuatorVerificationPipeline.verify_command()`, dictionary normalization can raise before the pipeline constructs a result or reaches the audit stage:

```python
params = {k: float(v) for k, v in raw_dict.items() ...}
```

Malformed numeric input therefore escapes as an exception rather than producing a rejected, audited result.

Relevant location:

- `src/safety/actuator_verification.py`, `ActuatorVerificationPipeline.verify_command()`

**Severity: Medium**

This is not an actuator-execution bypass by itself, but it violates the claimed fail-closed/audited pipeline contract.

---

## 3. Test coverage assessment

The reported tests are insufficient for independent security acceptance.

### What is covered adequately

- Missing `action_category`
- Explicit PHYSICAL without `device_id`
- DIGITAL downgrade when a `device_id` is present
- Basic HMAC task-state tampering
- Basic image path access
- HTTP/FTP image URL rejection
- Basic HMAC emergency-clear behavior
- Basic simulator rejection when `safety_approved` is false

### Important missing tests

1. **Physical action without `device_id` declared DIGITAL**
   - This is the most important remaining API bypass.

2. **Caller-mutated `safety_approved=True`**
   - Tests currently prove only the default is false.

3. **Direct calls to simulator mutators**
   - `trigger_fire_emergency()`
   - `emergency_land()`
   - `step()`
   - vehicle and industrial direct mutators

4. **Permission revocation and restart**
   - Register agent, persist, revoke, persist, reload, verify denial.

5. **Unknown/fuzzy actuator parameters**
   - `velocity_override`
   - `unsafe_force`
   - mixed-case and whitespace variants.

6. **NaN and Infinity on emergency/stop commands**
   - Must test every pipeline entry representation.

7. **Malformed actuator dictionaries**
   - Confirm rejection result rather than escaped exception.
   - Confirm rejected commands are audited.

8. **Permission substring/suffix confusion**
   - `execute_untrusted`
   - `/evil/api/v1/agents/create`
   - `/api/v1/action/approve_extra`

9. **Vehicle emergency-reset replay**
   - Reuse the same credential after successful reset.

10. **Vision TOCTOU**
    - Parent-directory replacement race.
    - Symlink replacement after validation.
    - IPv6 private/reserved DNS responses.
    - DNS rebinding behavior.

11. **Unbounded `image_data`**
    - Verify maximum size enforcement.

12. **Actual Safety Gateway verification**
    - Tests should use a fake gateway and assert it was called.
    - `safety_approved=True` alone must not be sufficient.

The test suite is therefore validating intended happy-path flags rather than proving that the security boundaries cannot be bypassed.

---

## 4. Required changes

At minimum:

1. Implement authoritative server-side action classification.
2. Deny all actions that could affect physical systems unless a verified device target and gateway-issued authorization are present.
3. Replace `safety_approved` with signed or capability-based gateway authorization.
4. Fix permission persistence to remove stale agents transactionally.
5. Remove substring/suffix permission matching.
6. Reject non-finite actuator values before all shortcut branches.
7. Require exact actuator parameter allowlist matches.
8. Add replay protection to vehicle emergency reset.
9. Make vision file opening descriptor-relative and race-resistant.
10. Replace arbitrary HTTPS image fetching with a controlled download/allowlist design.
11. Add the adversarial tests listed above.
12. Catch command-normalization exceptions and return an audited rejection.

## Final decision

**REQUIRES_CHANGES**

The remaining Vector 4/10 category downgrade, Vector 5 mutable Safety Gateway flag, Vector 9 permission-resolution bypass, and actuator NaN/fuzzy-parameter issues are security-blocking.