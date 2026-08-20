# ORION TASK 001 — TASK 11: GitHub Architecture

## Current State (VERIFIED FACT)

ORION repository: https://github.com/Protremix/ORION (private)
- 15 commits on main branch
- ~140 files, ~29,000 lines
- Apache 2.0 license
- Token stored as $GITHUB_TOKEN (sanitized from git config)

## Repository Structure

```
ORION/
├── README.md                          # Project overview
├── LICENSE                            # Apache 2.0
├── pyproject.toml                     # Project configuration
├── pytest.ini                         # Test configuration
│
├── src/                               # Source code
│   ├── core/                          # ORION Core (Supervisor, lifecycle)
│   ├── models/                        # Model adapters (GPT-4o, registry)
│   ├── planning/                      # Autonomous Planner, goals, actions
│   ├── persistence/                   # Storage (SQLite, PostgreSQL, task state)
│   ├── safety/                        # Safety Gateway, enforcement, arbitration
│   ├── domains/                       # Domain modules
│   │   ├── industrial/
│   │   ├── vehicle/
│   │   ├── drone/
│   │   └── home/
│   ├── world_model/                   # World Model (physics, prediction)
│   ├── perception/                    # Perception interfaces
│   ├── memory/                        # Memory interfaces
│   ├── hal/                           # Hardware Abstraction Layer
│   ├── api/                           # API/SDK interfaces
│   └── agents/                        # Agent framework
│
├── tests/                             # Test suite
│   ├── unit/                          # Unit tests (463 tests)
│   │   ├── test_*.py                  # Module tests
│   ├── integration/                    # Integration tests (planned)
│   └── e2e/                           # End-to-end tests (planned)
│
├── docs/                              # Documentation
│   ├── architecture/                  # Architecture Decision Records
│   ├── safety/                        # Safety documentation
│   ├── deployment/                    # Deployment guides
│   └── api/                           # API documentation
│
├── .github/                           # GitHub configuration
│   ├── workflows/                     # CI workflows
│   ├── ISSUE_TEMPLATE/               # Issue templates
│   └── PULL_REQUEST_TEMPLATE.md       # PR template
│
├── orion/                             # Research and design documents
│   ├── research/                      # Task 001 research output
│   └── implementation/                # Implementation code (legacy path)
│
├── PHASE_RECONCILIATION.md            # Master Spec phase coverage
├── DEPENDENCY_REGISTRY.md             # License registry
└── CHANGELOG.md                       # Version history
```

## Branch Strategy

```
main          — Production-ready, protected
  ↑
develop       — Integration branch
  ↑
feature/*     — Feature branches (e.g., feature/world-model)
fix/*         — Bug fix branches
research/*    — Research branches
release/*     — Release preparation
```

### Branch Protection Rules (when GitHub Pro available)
- Require PR before merge to main
- Require CI to pass before merge
- Require at least 1 review (Luna automated review counts)
- No force push to main
- No deletion of main

**Note:** Branch protection for private repos requires GitHub Pro — financial decision pending Founder approval.

## CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: ORION CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest --tb=short --maxfail=10
      - name: Run linting
        run: ruff check src/ tests/
      - name: Run type checking
        run: mypy src/ --ignore-missing-imports
```

## Security

### Secrets Policy
- **Never** commit secrets to repository
- API keys stored as environment variables ($GITHUB_TOKEN, $OPENAI_PROJECT_KEY)
- Remote URLs sanitized (no tokens in git config)
- `.gitignore` includes: `.env`, `*.key`, `*.pem`, `credentials.json`
- GitHub Secrets for CI (if needed)

### Permissions
- **ORION agent:** Read access to repo, create branches, create PRs, run CI. NO admin access. NO ability to merge to main. NO ability to delete repos.
- **Founder (owner):** Full admin access
- **Luna (reviewer):** Read + review access (automated via API, not GitHub user)
- **Collaborators:** Read + create PR. No direct push to main.

**Principle: Least privilege. ORION does not need admin credentials.**

## Issue Templates

```markdown
# .github/ISSUE_TEMPLATE/bug_report.md
---
name: Bug Report
about: Report a bug in ORION
---
## Description
## Steps to reproduce
## Expected behavior
## Actual behavior
## Environment (OS, Python version, ORION version)
## Logs/screenshots

# .github/ISSUE_TEMPLATE/feature_request.md
---
name: Feature Request
about: Request a new feature
---
## Feature description
## Use case
## Proposed implementation
## Safety considerations
## Domain (industrial/vehicle/drone/home/cross-domain)

# .github/ISSUE_TEMPLATE/safety_concern.md
---
name: Safety Concern
about: Report a safety issue
---
## Safety concern description
## Affected domain
## Risk level (low/medium/high/critical)
## Reproducibility
## Recommended mitigation
```

## PR Workflow

```markdown
# .github/PULL_REQUEST_TEMPLATE.md
## Description
## Type (feature/fix/research/safety/docs)
## Related issue
## Changes
## Tests added/modified
## Safety impact (if any)
## Checklist
- [ ] Tests pass
- [ ] Linting passes
- [ ] Documentation updated
- [ ] Dependency registry updated (if new dependencies)
- [ ] Safety review (if physical/safety-related changes)
```

## Evaluation Workflow

For PRs that affect safety, planning, or world model:
1. Run full test suite (463+ tests)
2. Run stress tests (500 tasks, 200 checkpoints)
3. Run safety-specific tests (Safety Layer v3)
4. If live API tests: run with OPENAI_PROJECT_KEY
5. Attach test results to PR
6. Luna review (automated via GPT-4o API)

## Documentation

### Architecture Decision Records (ADRs)
```
docs/architecture/
├── ADR-001-apache-2-license.md
├── ADR-002-asyncpg-for-postgresql.md
├── ADR-003-deny-by-default-safety.md
├── ADR-004-gpt4o-as-initial-reasoning.md
├── ADR-005-domain-specific-physics.md
└── ADR-template.md
```

Each ADR: Context → Decision → Rationale → Consequences → Status

## Classification

- Repository: VERIFIED FACT (github.com/Protremix/ORION)
- Branch protection: ASSUMPTION (needs GitHub Pro — financial decision)
- CI/CD: HYPOTHESIS (designed, not yet running on GitHub Actions)
- Security: VERIFIED FACT (token sanitization implemented)
- Least privilege: VERIFIED FACT (ORION has no admin access)
