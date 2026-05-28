<!--
Sync Impact Report
- Version: 0.0.0 (UNRATIFIED TEMPLATE — fill via /sp:00-constitution)
- This is a placeholder scaffold. Principles below are seeded from CLAUDE.md
  conventions as starting points; ratify and refine them with /sp:00-constitution.
- Dependent artifacts to re-check after ratification: spec-template.md,
  plan-template.md, tasks-template.md.
-->

# hermes-attractor Constitution

**Version**: 0.0.0 (unratified template)
**Ratified**: [DATE]
**Last Amended**: [DATE]

## Core Principles

### I. Hexagonal Architecture (Dependencies Point Inward)

Domain has zero external dependencies. Dependencies flow `domain ← use_cases`,
`use_cases → ports`, `adapters → ports`; only `plugin/` knows about Hermes.
[Refine via /sp:00-constitution.]

### II. Test-First, 100% Coverage

TDD red-green-refactor is mandatory. Branch coverage at 100% is enforced in
pre-commit and CI. [Refine.]

### III. Strict Typing & Linting

`ruff` clean and `pyright` strict must pass. Suppressions are justified and
narrow. [Refine.]

### IV. Safe Plugin Contract

`plugin/tools.py` handlers always return a JSON string and never raise.
[Refine.]

### V. [PRINCIPLE_5_NAME]

[PRINCIPLE_5_DESCRIPTION]

## Governance

[Amendment procedure, versioning policy, and compliance review expectations.
Fill via /sp:00-constitution.]
