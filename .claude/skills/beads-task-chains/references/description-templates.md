# Beads Task Description Templates

Parameterized templates for each task type. Replace `<placeholder>` variables with actual values when creating tasks.

## Type A Templates

### WRITE_ACCEPTANCE_TEST

```
**Type**: WRITE_ACCEPTANCE_TEST
**Story**: US<N> — <story title>
**Spec**: specs/$BRANCH/spec.md §US-<N>
**Acceptance scenarios**:
  1. GIVEN <precondition> WHEN <action> THEN <outcome>
  2. ...
**Acceptance spec file**: specs/acceptance-specs/US<N>-<kebab-title>.txt
**Generated test file**: tests/acceptance/test_us<N>_<snake_title>.py
**Skills**: /pytest-acceptance-tests
**Instructions**: Write the GWT acceptance spec file, then generate the pytest test stubs (one test per scenario). Bind the generated stubs with real calls into the use-case/adapter layer and assertions. Tests should FAIL (they define the target behavior).
**Done when**: Spec file exists, generated test file exists with bound implementations, `uv run pytest tests/acceptance/test_us<N>_<snake_title>.py` shows failing tests.
**Commit**: Run `/commit` then `git push`. CI on the feature branch will fail until the implementation lands in subsequent tasks — that's expected. After closing the bead, commit and push again to record the beads state change.
```

Placeholders:

- `<N>`: User story number
- `<story title>`: From spec.md
- `$BRANCH`: Current git branch name
- `<precondition>`, `<action>`, `<outcome>`: From spec acceptance scenarios
- `<kebab-title>` / `<snake_title>`: Kebab-case / snake_case slug of story title

### RED

```
**Type**: RED (write failing test)
**Story**: US<N> — <story title>
**Behavior**: <precise description of the single behavior to test>
**Spec**: specs/$BRANCH/spec.md §US-<N>
**Plan**: specs/$BRANCH/plan.md §<relevant-section>
**Test file**: <exact path, e.g. tests/unit/domain/test_user.py>
**Target module**: <exact path to the module being tested, e.g. src/hermes_attractor/domain/user.py>
**Existing patterns**: <reference to similar existing test files for style consistency>
**Layer CLAUDE.md**: <path to layer-specific instructions, e.g. src/hermes_attractor/domain/CLAUDE.md>
**Skills**: /pytest-unit-tests
**Instructions**: Write ONE failing test for this behavior. Import from the target module (create the module with just the type/function signature if it doesn't exist yet). The test must fail because the implementation doesn't exist or is incomplete, NOT because of import/syntax errors.
**Done when**: Test file exists, `uv run pytest <test-file>` fails with an assertion error (not a collection/import error).
**Commit**: DO NOT commit. Failing tests will not pass pre-commit hooks. The beads closure (from `br close`) will also remain uncommitted — the next Green task will commit the failing test, the implementation, and the accumulated beads state together.
```

Placeholders:

- `<behavior>`: One specific behavior being tested
- `<relevant-section>`: Section anchor in plan.md
- `<exact path>`: Full file path from repo root
- `<existing patterns>`: Path to a similar test file for style reference

### GREEN

```
**Type**: GREEN (minimal implementation)
**Story**: US<N> — <story title>
**Behavior**: <same behavior description as Red>
**Spec**: specs/$BRANCH/spec.md §US-<N>
**Plan**: specs/$BRANCH/plan.md §<relevant-section>
**Test file**: <exact test file path from Red task>
**Implementation files**: <exact paths to create/modify, e.g. src/hermes_attractor/use_cases/create_user.py>
**Dependencies**: <imports, protocols, or dataclasses this implementation needs>
**Layer CLAUDE.md**: <path to layer-specific instructions>
**Skills**: <skill list from mapping table, e.g. /ddd-domain-modeling>
**Instructions**: Write the MINIMAL code to make the failing test pass. Do not add code beyond what the test requires. Do not refactor yet.
**Done when**: `uv run pytest <test-file>` passes.
**Commit**: After tests pass, run `/commit` then `git push`. After closing the bead, commit and push again to record the beads state change. (This commit also sweeps up any earlier Red task's uncommitted failing test and its bead closure.)
```

Placeholders:

- `<implementation files>`: Exact paths to create or modify
- `<dependencies>`: Imports, protocols, or dataclasses needed
- `<skill list>`: From sp-05-tasks skill mapping table

### REFACTOR

```
**Type**: REFACTOR (improve quality)
**Story**: US<N> — <story title>
**Behavior**: <same behavior description>
**Test file**: <exact test file path>
**Implementation files**: <exact paths>
**Layer CLAUDE.md**: <path to layer-specific instructions>
**Skills**: /refactoring
**Instructions**: Improve code quality (naming, duplication, clarity) without changing behavior. Run tests after each change to ensure they still pass. Skip if the code is already clean.
**Done when**: `uv run pytest <test-file>` still passes, `uv run ruff check` and `uv run pyright` are clean, code meets quality standards.
**Commit**: After tests pass, run `/commit` then `git push`. After closing the bead, commit and push again to record the beads state change. Skip the first commit if no refactoring changes were made.
```

### VERIFY_ACCEPTANCE

```
**Type**: VERIFY_ACCEPTANCE
**Story**: US<N> — <story title>
**Acceptance spec file**: specs/acceptance-specs/US<N>-<kebab-title>.txt
**Generated test file**: tests/acceptance/test_us<N>_<snake_title>.py
**Skills**: /pytest-acceptance-tests
**Instructions**: Run the acceptance tests for this story. If they pass, close this task. If they fail, diagnose which scenarios fail and add a comment explaining what's missing. Do NOT write new unit tests or implementation code — that work should be captured as new beads tasks if needed.
**Done when**: `uv run pytest <generated test file>` passes for this story's test file.
**Commit**: After acceptance tests pass, run `/commit` then `git push` (skip if no changes were made). After closing the bead, commit and push again to record the beads state change.
```

## Type B Template

### DOCUMENTATION

```
**Type**: DOCUMENTATION
**Files**: <exact paths>
**Instructions**: <what to document and why>
**Done when**: File exists with correct content. No broken links or formatting issues.
**Commit**: After verification passes, run `/commit` then `git push`. After closing the bead, commit and push again to record the beads state change.
```

## Type C Template

### CONFIGURATION

```
**Type**: CONFIGURATION
**Files**: <exact paths, e.g. pyproject.toml, .github/workflows/ci.yml, justfile>
**Instructions**: <what to configure and why>
**Validation command**: <e.g. uv run ruff check, uv run pyright, uv lock --check, uv run pytest --cov>
**Done when**: Validation command exits 0.
**Commit**: After verification passes, run `/commit` then `git push`. After closing the bead, commit and push again to record the beads state change.
```

## Type D Template

### REMEDIATION

```
**Type**: REMEDIATION
**Review**: <review type — security, architecture, or quality>
**Finding**: <one-sentence problem description>
**File**: <exact path>
**Line**: <line number or range>
**Severity**: <Critical|High|Medium|Low>
**Fix**: <concise description of the required fix>
**Skills**: <relevant skills for this fix>
**Instructions**: <detailed fix instructions including what to change and why>
**Done when**: Fix applied, tests pass (`uv run pytest <test-file>`), `uv run ruff check` and `uv run pyright` are clean.
**Commit**: After verification passes, run `/commit` then `git push`. After closing the bead, commit and push again to record the beads state change.
```

Placeholders:

- `<review type>`: One of: security, architecture, quality
- `<finding>`: From the review comment's problem column
- `<fix>`: From the review comment's fix column
- `<severity>`: Maps to priority (Critical→0, High→1, Medium→2, Low→3)
