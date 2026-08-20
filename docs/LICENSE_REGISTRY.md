# ORION License Registry

**Date:** 2026-08-20
**Maintainer:** ORION Supervisor
**ORION License:** Apache 2.0

---

## Runtime Dependencies

| # | Dependency | Version Constraint | Source | License | Commercial Use | Modification | Redistribution | Attribution | Restrictions | Verification Source |
|---|------------|-------------------|--------|---------|----------------|-------------|----------------|-------------|-------------|---------------------|
| 1 | asyncpg | >=0.29.0 | [PyPI](https://pypi.org/project/asyncpg/) | Apache 2.0 | YES | YES | YES | YES (LICENSE file) | None | https://github.com/MagicStack/asyncpg/blob/master/LICENSE |
| 2 | openai | >=1.0 | [PyPI](https://pypi.org/project/openai/) | Apache 2.0 | YES | YES | YES | YES | None | https://github.com/openai/openai-python/blob/main/LICENSE |

## Development Dependencies (not shipped in production)

| # | Dependency | Version Constraint | Source | License | Commercial Use | Modification | Redistribution | Attribution | Restrictions | Verification Source |
|---|------------|-------------------|--------|---------|----------------|-------------|----------------|-------------|-------------|---------------------|
| 2 | pytest | >=7.0 | [PyPI](https://pypi.org/project/pytest/) | MIT | YES | YES | YES | YES (MIT license header) | None | https://docs.pytest.org/en/stable/license.html |
| 3 | pytest-asyncio | >=0.21.0 | [PyPI](https://pypi.org/project/pytest-asyncio/) | MIT | YES | YES | YES | YES | None | https://github.com/pytest-dev/pytest-asyncio/blob/main/LICENSE |
| 4 | ruff | >=0.1.0 | [PyPI](https://pypi.org/project/ruff/) | MIT | YES | YES | YES | YES | None | https://github.com/astral-sh/ruff/blob/main/LICENSE |
| 5 | mypy | >=1.0 | [PyPI](https://pypi.org/project/mypy/) | MIT | YES | YES | YES | YES | None | https://github.com/python/mypy/blob/master/LICENSE |

## Infrastructure

| # | Component | Version | Source | License | Commercial Use | Modification | Redistribution | Attribution | Restrictions | Verification Source |
|---|-----------|---------|--------|---------|----------------|-------------|----------------|-------------|-------------|---------------------|
| 6 | Python | >=3.10 | [python.org](https://python.org) | PSF License (BSD-derived) | YES | YES | YES | Minimal (retain copyright notice) | None | https://docs.python.org/3/license.html |
| 7 | PostgreSQL | 16 | [postgresql.org](https://postgresql.org) | PostgreSQL License (BSD-like) | YES | YES | YES | YES (copyright notice) | None | https://www.postgresql.org/about/licence/ |
| 8 | pgvector | >=0.7 | [github.com/pgvector](https://github.com/pgvector/pgvector) | PostgreSQL License | YES | YES | YES | YES | None | https://github.com/pgvector/pgvector/blob/master/LICENSE |

## Docker Images

| # | Image | License | Source |
|---|-------|---------|--------|
| 9 | python:3.12-slim | PSF License | Docker Hub |
| 10 | postgres:16 | PostgreSQL License | Docker Hub |
| 11 | pgvector/pgvector:pg16 | PostgreSQL License | Docker Hub |

## External Services (not bundled, accessed via API)

| Service | Provider | License | Commercial Use | Notes |
|---------|----------|---------|----------------|-------|
| GPT-4o API | OpenAI | [OpenAI API Terms of Use](https://openai.com/policies/terms-of-use) | YES (paid) | Cloud service. Replaceable via adapter pattern. Not bundled with ORION. |
| text-embedding-3-small | OpenAI | OpenAI API Terms of Use | YES (paid) | Cloud service. Fallback: hash-based embeddings. |

## ORION-Owned Code

| Component | License | Owner | Notes |
|-----------|---------|-------|-------|
| All ORION source code | Apache 2.0 | ORION Project | See LICENSE file in repository root |

## License Compatibility Assessment

All runtime and development dependencies use Apache 2.0, MIT, or BSD-derived licenses. These are all compatible with ORION's Apache 2.0 license.

**No GPL, AGPL, LGPL, or copyleft dependencies found.**

No dependencies require source code disclosure or place restrictions on commercial use.

## Dependencies with UNKNOWN License Status

None — all dependencies have verified licenses.

