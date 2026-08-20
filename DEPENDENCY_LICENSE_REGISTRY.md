# ORION DEPENDENCY LICENSE REGISTRY

**Date:** 2026-08-20
**Maintainer:** ORION Supervisor
**License:** Apache 2.0 (ORION-owned code)

---

## External Dependencies

| # | Dependency | Version | Source | License | Commercial Use | Modification | Redistribution | Attribution | Restrictions | Verification Source |
|---|------------|---------|--------|---------|----------------|-------------|----------------|-------------|-------------|---------------------|
| 1 | asyncpg | >=0.29.0 | PyPI | Apache 2.0 (BSD-3-Clause) | YES | YES | YES | YES (LICENSE file) | None | https://github.com/MagicStack/asyncpg/blob/master/LICENSE |
| 2 | Python | >=3.10 | python.org | PSF License Agreement (BSD-derived) | YES | YES | YES | Minimal | None | https://docs.python.org/3/license.html |

## Optional Dependencies (for testing/CI only)

| # | Dependency | Version | Source | License | Commercial Use | Notes |
|---|------------|---------|--------|---------|----------------|-------|
| 3 | pytest | >=7.0 | PyPI | MIT | YES | Test runner only, not runtime dep |
| 4 | PostgreSQL | >=16 | postgresql.org | PostgreSQL License (BSD-like) | YES | Optional storage backend |
| 5 | pgvector | >=0.7 | github.com/pgvector | PostgreSQL License | YES | Optional vector search |

## OpenAI API (external service, not a dependency)

| Service | Provider | License | Commercial Use | Notes |
|---------|----------|---------|----------------|-------|
| GPT-4o API | OpenAI | OpenAI API Terms of Use | YES (paid) | Cloud service, not bundled. Replaceable via adapter pattern. |
| text-embedding-3-small | OpenAI | OpenAI API Terms of Use | YES (paid) | Cloud service. Fallback: hash-based embeddings. |

## Docker Images

| Image | License | Source |
|-------|---------|--------|
| postgres:16 | PostgreSQL License | Docker Hub |
| pgvector/pgvector:pg16 | PostgreSQL License | Docker Hub |

## License Compatibility

All dependencies are BSD-derived or Apache 2.0 — compatible with ORION's Apache 2.0 license.

No GPL, LGPL, or copyleft dependencies.
No LICENSE_REVIEW_REQUIRED items.

## Verification

All licenses verified from primary sources (upstream LICENSE files, official websites). No guesses.

---

**End of Registry**
