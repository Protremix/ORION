# ORION Security Audit Report

**Date:** 2026-08-20  
**Target Repository:** ORION Physical Intelligence OS (`orion/implementation/`)  
**Version:** 0.6.0  
**Audit Scope:** Comprehensive Repository Security Review  

---

## Executive Summary

This document presents a comprehensive security audit of the ORION Physical Intelligence OS repository located at `orion/implementation/`. The audit evaluated code security, authentication/authorization mechanisms, secret management, process isolation, network/file-system operations, container privileges, and agent permission enforcement.

### Severity Summary Table

| Severity | Findings Count | Key Areas Impacted |
| :--- | :---: | :--- |
| **CRITICAL** | 1 | ~~Unenforced authentication~~ **FIXED** & permission checks on public `ORIONAPI` methods |
| **HIGH** | 5 | Arbitrary file read in vision adapter, auto-disabled API auth when key is missing, default fallback secret for policy signing, Docker running as root, database ports bound to `0.0.0.0` |
| **MEDIUM** | 5 | SSRF risk in image URL loading, lack of token rotation/invalidation, hardcoded DB credentials in Compose, ephemeral in-memory permission registry, lack of resource-scoped RBAC |
| **LOW** | 5 | Lack of centralized env var schema validation, direct local storage writes, `tempfile.mktemp()` usage in test suite, dev dependencies in Docker image, missing Docker resource limits & healthchecks |
| **INFO** | 5 | Safe constant-time HMAC comparison, HTTPS enforcement in OpenAI adapter, no subprocess/eval calls in production code, parameterized database queries, 4-tier permission hierarchy definition |

---

## 1. Secrets & Credentials

### Methodology
Static analysis was conducted across all codebase configuration and source files (`.py`, `.yml`, `.yaml`, `.json`, `.toml`):
```bash
grep -r 'sk-\|ghp_\|password.*=.*["'\'']\|secret.*=.*["'\'']\|api_key.*=.*["'\'']' --include='*.py' --include='*.yml' --include='*.json' --include='*.toml' .
```

### Findings

#### Finding 1.1: Default Policy Signing Secret Key Fallback
* **Classification:** **HIGH**
* **Location:** `src/config/policy_manager.py:52`, `src/config/policy_manager.py:138`
* **Evidence:**
  ```python
  DEFAULT_SECRET_KEY = "orion_phase1_safety_key_change_in_production"
  self.secret_key = secret_key or os.environ.get("ORION_POLICY_SECRET_KEY", DEFAULT_SECRET_KEY)
  ```
* **Description:** If `ORION_POLICY_SECRET_KEY` is omitted from the environment, the policy manager defaults to a hardcoded key. An attacker aware of this open-source default can forge valid policy signatures and tamper with safety boundaries.
* **Remediation:** Require `ORION_POLICY_SECRET_KEY` to be explicitly set in non-test environments or raise an exception on initialization if missing.

#### Finding 1.2: Hardcoded Database Credentials in Compose and CI Workflows
* **Classification:** **MEDIUM**
* **Location:** `docker-compose.yml:8,19`, `.github/workflows/ci.yml:25,32`
* **Evidence:**
  ```yaml
  POSTGRES_PASSWORD: "test"
  ORION_PG_PASSWORD: test
  ORION_API_KEY: ci-test-key
  ```
* **Description:** Development and CI configurations contain static credentials. While appropriate for isolated CI runners, deploying these compose files into production creates default credential exposure.
* **Remediation:** Parameterize `docker-compose.yml` to inject credentials from environment variables or secrets management vaults.

#### Finding 1.3: Default Blank Password Parameters in Storage Initializers
* **Classification:** **LOW**
* **Location:** `src/persistence/postgres_storage.py:69`, `src/persistence/pgvector_store.py:115`
* **Evidence:** `password: str = ""` in `PostgresStorage.__init__` and `PGVectorStore.__init__`.
* **Description:** Initializing database clients with empty password defaults can encourage unauthenticated database deployments.
* **Remediation:** Enforce non-empty password arguments when establishing database connections outside test fixtures.

#### Finding 1.4: Unit Test Mock API Keys and Secrets
* **Classification:** **INFO**
* **Location:** `tests/unit/test_auth.py`, `tests/unit/test_phase8.py`, `tests/test_audit_system.py`
* **Evidence:** Hardcoded test strings (`"secret123"`, `"test-key"`, `"secret-abc"`).
* **Description:** Mock keys are strictly isolated to test fixtures and do not expose production secrets.

#### Finding 1.5: Absence of Active Production Cloud Keys in Repository
* **Classification:** **INFO**
* **Evidence:** No live OpenAI (`sk-...`), GitHub (`ghp_...`), or private cloud provider credentials were detected in version control.

---

## 2. Environment Variables

### Methodology
Inspected all environment variable accesses across the Python codebase:
```bash
grep -r 'os.environ\|os.getenv' --include='*.py' .
```

### Environment Variable Inventory

| Environment Variable | Module / Location | Purpose | Default / Fallback |
| :--- | :--- | :--- | :--- |
| `OPENAI_API_KEY` | `cognitive_plane.py`, `memory_system.py`, `gpt4o_adapters.py` | OpenAI API access | None (falls back to mock/hash embedding) |
| `OPENAI_PROJECT_KEY` | `cognitive_plane.py`, `gpt4o_adapters.py` | Alternate OpenAI Project key | None |
| `ORION_API_KEY` | `src/api/auth.py:46` | API bearer token auth | `None` (Disables auth) |
| `ORION_POLICY_SECRET_KEY` | `src/config/policy_manager.py:138` | Policy HMAC signature key | `"orion_phase1_safety_key_change_in_production"` |
| `ORION_PG_HOST` | `test_live_postgres.py` | Postgres database host | `"localhost"` |
| `ORION_PG_PORT` | `test_live_postgres.py` | Postgres database port | `5432` |
| `ORION_PG_USER` | `test_live_postgres.py` | Postgres database user | `"postgres"` |
| `ORION_PG_PASSWORD` | `test_live_postgres.py` | Postgres database password | `"test"` |
| `ORION_PG_DB` | `test_live_postgres.py` | Postgres database name | `"orion"` |

### Findings

#### Finding 2.1: Automatic Authentication Disablement when `ORION_API_KEY` is Missing
* **Classification:** **HIGH**
* **Location:** `src/api/auth.py:44-50`
* **Evidence:**
  ```python
  env_key = os.environ.get("ORION_API_KEY")
  config = AuthConfig(
      enabled=bool(env_key),  # Auto-enable if key is set
      api_key=env_key,
  )
  ```
* **Description:** If `ORION_API_KEY` is not explicitly set in the environment, `AuthManager` defaults to `enabled=False`. In a production environment, missing this environment variable completely opens the API to unauthenticated requests.
* **Remediation:** Default `enabled` to `True` in production mode (`ORION_ENV=production`) and fail startup if `ORION_API_KEY` is not specified.

#### Finding 2.2: Decentralized Direct Environment Variable Reads
* **Classification:** **LOW**
* **Location:** Spread across `src/cognitive/`, `src/memory/`, `src/models/`, `src/config/`
* **Description:** Environment variables are queried ad-hoc via `os.environ.get()` throughout the codebase without centralized validation or type parsing (e.g. via Pydantic `BaseSettings`).
* **Remediation:** Centralize configuration loading into a unified `src/config/settings.py` module.

---

## 3. Subprocess Execution & Dynamic Code Execution

### Methodology
Scanned source files for process execution, shell invocation, and dynamic evaluation primitives:
```bash
grep -r 'subprocess\|os.system\|eval(\|exec(' --include='*.py' .
```

### Findings

#### Finding 3.1: Zero Subprocess or Dynamic Execution in Core Application
* **Classification:** **INFO**
* **Location:** Entire `src/` directory
* **Description:** The core application contains no references to `subprocess`, `os.system`, `os.popen`, `eval()`, or `exec()`. System execution risk is exceptionally low.

#### Finding 3.2: Input Validation Defense Against Injection
* **Classification:** **INFO**
* **Location:** `tests/unit/test_validation.py:70-75`
* **Evidence:** Unit tests verify that `InputValidator.validate_goal` rejects strings containing `eval(...)` and `exec(...)` patterns.

---

## 4. File System Access

### Methodology
Audited file opening (`open()`), file unlinking (`os.remove`, `os.unlink`), directory manipulations (`shutil`), and temporary file creation (`tempfile`).

### Findings

#### Finding 4.1: Arbitrary Local File Read via `GPT4oVisionAdapter`
* **Classification:** **HIGH**
* **Location:** `src/models/gpt4o_adapters.py:191-194`
* **Evidence:**
  ```python
  elif request.image_path:
      with open(request.image_path, "rb") as f:
          b64 = base64.b64encode(f.read()).decode()
      return f"data:image/png;base64,{b64}"
  ```
* **Description:** The `GPT4oVisionAdapter` opens file paths specified in `request.image_path` without path traversal validation or canonicalization. An attacker supplying a path like `/etc/passwd` or `/root/.ssh/id_rsa` can induce the system to read arbitrary server files and upload their base64 representation to external LLM APIs.
* **Remediation:** Validate that `image_path` is confined within an allowed base directory (e.g. using `Path.resolve()` and checking `is_relative_to()`), or restrict input to explicit image byte buffers / URLs.

#### Finding 4.2: Direct Local File Writes for Audit Logs and State Persistence
* **Classification:** **LOW**
* **Location:** `src/audit/audit_system.py:321`, `src/runtime/supervisor.py:409`, `src/persistence/task_state.py:186`
* **Description:** Audit logs and supervisor state files are written directly to disk. While path inputs are system-generated, lack of file lock handling during concurrent process writes could lead to file corruption.
* **Remediation:** Implement atomic file writes using temporary file swap (`tempfile` + `os.replace`) and file locking.

#### Finding 4.3: Insecure Temporary File Creation in Test Suites
* **Classification:** **LOW**
* **Location:** `tests/unit/test_audit_replication.py:66,116,167,195`
* **Evidence:** `self.replica_path = tempfile.mktemp(suffix=".db")`
* **Description:** `tempfile.mktemp()` is deprecated and vulnerable to race conditions / symlink creation before file opening.
* **Remediation:** Replace `tempfile.mktemp()` with `tempfile.NamedTemporaryFile()` or `tempfile.TemporaryDirectory()`.

---

## 5. Network Access

### Methodology
Audited networking libraries (`requests`, `urllib`, `httpx`, `socket`, `aiohttp`) across core application and test modules.

### Findings

#### Finding 5.1: Potential SSRF via Image URL Loading in Vision Processing
* **Classification:** **MEDIUM**
* **Location:** `src/models/gpt4o_adapters.py:186-188`, `tests/unit/test_live_gpt4o.py:255-256`
* **Evidence:**
  ```python
  img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
  with urllib.request.urlopen(img_req, timeout=10) as img_resp:
  ```
* **Description:** When vision processing accepts arbitrary external `image_url` strings, the application fetches external HTTP resources. If an attacker passes internal endpoints (e.g. `http://169.254.169.254/latest/meta-data/` or `http://localhost:5432`), the server may perform Server-Side Request Forgery (SSRF).
* **Remediation:** Implement URL validation blocking private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.169.254`).

#### Finding 5.2: Protocol Validation & TLS Enforcement in OpenAI Client
* **Classification:** **INFO**
* **Location:** `src/models/gpt4o_adapters.py:46-49`
* **Evidence:**
  ```python
  url = f"https://api.openai.com/v1/{endpoint}"
  if not url.startswith("https://"):
      raise ValueError(f"ORION security: only HTTPS URLs allowed, got {url}")
  ```
* **Description:** OpenAI API calls strictly enforce `https://` URLs and utilize standard Python TLS verification.

---

## 6. Docker Privileges

### Methodology
Inspected container build instructions in `Dockerfile` and deployment compositions in `docker-compose.yml`.

### Findings

#### Finding 6.1: Container Executes as Root User (UID 0)
* **Classification:** **HIGH**
* **Location:** `Dockerfile`
* **Evidence:** Absence of `USER` directive in `Dockerfile`.
* **Description:** The container process defaults to `root` user execution. If an application vulnerability (e.g. arbitrary file read) is exploited, the attacker inherits full root privileges inside the container, increasing container breakout risk.
* **Remediation:** Create a dedicated non-root user (e.g. `RUN useradd -m orionuser && USER orionuser`) in the Dockerfile.

#### Finding 6.2: Database Ports Exposed to All Network Interfaces (`0.0.0.0`)
* **Classification:** **HIGH**
* **Location:** `docker-compose.yml:12,23`
* **Evidence:**
  ```yaml
  ports:
    - "5432:5432"
    - "5433:5432"
  ```
* **Description:** Binding database ports directly to `5432:5432` exposes PostgreSQL and PGVector services on all network interfaces (`0.0.0.0`), allowing external network access to the database layer.
* **Remediation:** Bind ports explicitly to localhost (`127.0.0.1:5432:5432`) or omit port publish directives for internal container networking.

#### Finding 6.3: Multi-Stage Build Copies Development Dependencies
* **Classification:** **LOW**
* **Location:** `Dockerfile:19`
* **Evidence:** `RUN pip install --no-cache-dir -e ".[dev]"`
* **Description:** Installing test/dev packages (`pytest`, `ruff`, `mypy`) in production container images increases image size and attack surface.
* **Remediation:** Use multi-stage Docker builds to separate `builder`/`test` targets from a minimal `runtime` image installing only production dependencies (`pip install .`).

#### Finding 6.4: Missing Container Resource Limits and Healthchecks
* **Classification:** **LOW**
* **Location:** `Dockerfile`, `docker-compose.yml`
* **Description:** Containers lack CPU/memory quotas (`mem_limit`) and `HEALTHCHECK` directives, making them vulnerable to Denial of Service (resource exhaustion).
* **Remediation:** Define `deploy.resources.limits` in Compose and `HEALTHCHECK` in Dockerfile.

---

## 7. Authentication & Authorization

### Methodology
Reviewed authentication handlers in `src/api/auth.py`, top-level interfaces in `src/api/__init__.py`, and permission structures in `src/api/permissions.py`.

### Findings

#### Finding 7.1: Unenforced Authentication & Authorization in Public `ORIONAPI` Methods
* **Classification:** **CRITICAL**
* **Location:** `src/api/__init__.py:110-245`
* **Evidence:**
  `ORIONAPI` defines `_check_auth(self, token, agent_id, action)` at line 110, BUT public interface methods (`observe`, `get_world_state`, `recall`, `remember`, `plan`, `simulate`, `execute`, `emergency_stop`) do not invoke `_check_auth()`.
  ```python
  def execute(self, action: Dict[str, Any], domain: str = "industrial", simulate_first: bool = True) -> ORIONResponse:
      if simulate_first:
          sim = self.simulate(action, domain)
          if not sim.ok:
              return sim
      # Direct execution without checking API key or agent permissions!
  ```
* **Description:** External callers using `ORIONAPI` can execute actions, recall/store memories, and query world state without providing a valid API key or agent permission check, completely bypassing the authentication and authorization layer.
* **Remediation:** Call `self._check_auth(token, agent_id, action)` at the beginning of every public `ORIONAPI` method.

#### Finding 7.2: Constant-Time Token Hashing Comparison
* **Classification:** **INFO**
* **Location:** `src/api/auth.py:67-68`
* **Evidence:**
  ```python
  provided = hashlib.sha256(token.encode()).digest()
  expected = hashlib.sha256(self._config.api_key.encode()).digest()
  return hmac.compare_digest(provided, expected)
  ```
* **Description:** Authentication token comparison uses SHA-256 digest comparison wrapped in `hmac.compare_digest`, effectively neutralizing timing side-channel attacks.

#### Finding 7.3: Lack of Token Rotation, Revocation, or Expiration Mechanisms
* **Classification:** **MEDIUM**
* **Location:** `src/api/auth.py`
* **Description:** API keys are static strings. There is no session expiration, key revocation list, or multi-key rotation mechanism without restarting the process.
* **Remediation:** Implement structured API keys (e.g. JWTs or hashed key records with expiration and revocation metadata in database storage).

---

## 8. Agent Tool Permissions

### Methodology
Reviewed agent permission definitions, level hierarchies, and enforcement mechanisms in `src/api/permissions.py`.

### Findings

#### Finding 8.1: Unenforced Permission Checking in Subsystem Tools & Handlers
* **Classification:** **HIGH**
* **Location:** `src/api/permissions.py`, `src/cognitive/`, `src/memory/`
* **Description:** While `PermissionChecker` defines permission mapping for actions (`READ`, `WRITE`, `ADMIN`, `SUPERVISOR`), tools and sub-agent execution pathways directly call lower-level modules without passing through `PermissionChecker.check_permission()`.
* **Remediation:** Apply a permission check decorator `@require_permission(level)` across all tool, memory, and cognitive action execution entrypoints.

#### Finding 8.2: Ephemeral In-Memory Permission Registry
* **Classification:** **MEDIUM**
* **Location:** `src/api/permissions.py:168`
* **Evidence:** `_registry: Dict[str, List[Union[PermissionLevel, str]]] = {}`
* **Description:** Agent permission registrations are held purely in memory (`_registry`). In multi-worker deployments or process restarts, agent permissions are wiped, defaulting agents to unregistered (denied) status or requiring re-registration.
* **Remediation:** Persist agent permission assignments in the database or config storage.

#### Finding 8.3: Lack of Resource-Scoped RBAC
* **Classification:** **MEDIUM**
* **Location:** `src/api/permissions.py:245-298`
* **Description:** `check_permission` evaluates action level ranks (e.g., whether an agent has `WRITE` access), but does not verify resource-level constraints (e.g. restricting Agent A to Device X while denying access to Device Y).
* **Remediation:** Expand `PermissionChecker.check_permission` to support Object-Level / Attribute-Based Access Control (ABAC) using resource descriptors.

#### Finding 8.4: Structured Permission Level Hierarchy
* **Classification:** **INFO**
* **Location:** `src/api/permissions.py:18-40`
* **Evidence:** Structured 4-tier enum: `READ` (rank 1) < `WRITE` (rank 2) < `ADMIN` (rank 3) < `SUPERVISOR` (rank 4).

---

## Priority Remediation Roadmap

| Rank | Issue | Severity | Effort | Target Milestone |
| :---: | :--- | :---: | :---: | :--- |
| **P0** | Enforce `_check_auth()` on all `ORIONAPI` public methods (Finding 7.1) | **CRITICAL** | Low | Immediate |
| **P0** | Prevent auto-disablement of Auth when `ORION_API_KEY` is missing in prod (Finding 2.1) | **HIGH** | Low | Immediate |
| **P1** | Sanitize and boundary-check `image_path` in `GPT4oVisionAdapter` (Finding 4.1) | **HIGH** | Low | Next Sprint |
| **P1** | Require mandatory `ORION_POLICY_SECRET_KEY` env var (Finding 1.1) | **HIGH** | Low | Next Sprint |
| **P1** | Set non-root container `USER` in `Dockerfile` (Finding 6.1) | **HIGH** | Low | Next Sprint |
| **P1** | Restrict Docker Compose Postgres ports to `127.0.0.1` (Finding 6.2) | **HIGH** | Low | Next Sprint |
| **P2** | Integrate `@require_permission` decorator across tool executors (Finding 8.1) | **HIGH** | Medium | V0.7.0 |
| **P2** | Add SSRF IP range filtering for remote image fetches (Finding 5.1) | **MEDIUM** | Medium | V0.7.0 |
| **P2** | Persist agent permission registrations in database (Finding 8.2) | **MEDIUM** | Medium | V0.7.0 |
| **P3** | Centralize environment variable schema validation (Finding 2.2) | **LOW** | Medium | V0.8.0 |

---

## Summary Assessment

ORION's safety and audit framework contains high-quality security controls in specific areas—notably constant-time HMAC key verification, SHA-256 audit log hash chains, and formal Control Barrier Functions (CBFs). 

However, **critical security gaps exist at the API edge and boundary enforcement layers**:
1. `ORIONAPI` methods fail to invoke authentication/authorization routines.
2. Missing environment variables quietly auto-disable API authentication and fall back to open defaults.
3. Path traversal in vision adapter allows reading arbitrary server files.
4. Container configuration defaults to root privileges and exposes ports externally.

Addressing the P0 and P1 remediation targets will immediately elevate ORION's security posture to production-grade standards.
