---
name: beads-task-chains
description: Construct dependency chains for beads tasks based on work type (A-D). Use when creating structured task hierarchies for ATDD/TDD, documentation, configuration, or review remediations.
---

# Beads Task Chain Patterns

Reusable chain construction patterns for beads tasks. Consumers: `sp-05-tasks`, `process-pr-reviews`, and any agent that creates structured beads tasks.

## Task Type Classification

| Type  | Name          | Description                                                            |
| ----- | ------------- | --------------------------------------------------------------------- |
| **A** | Testable code | Domain entities, use cases, ports, adapters — full ATDD + TDD         |
| **B** | Documentation | README, docs/, AGENTS.md, CLAUDE.md updates — write + lint            |
| **C** | Configuration | pyproject.toml, CI workflows, justfile, tooling — change + validate   |
| **D** | Remediation   | Review-generated fixes — TDD chain if testable, flat task otherwise   |

## Type A: ATDD/TDD Chain

For each user story with testable code, generate this dependency chain:

```
US<N>: <story title>                                (parent)
  Write acceptance test for US<N>                   (no blockers)
  Red: write failing test for <behavior-1>          (blocked by acceptance test)
  Green: make <behavior-1> pass                     (blocked by Red-1)
  Refactor: clean up <behavior-1>                   (blocked by Green-1)
  Red: write failing test for <behavior-2>          (blocked by Refactor-1)
  Green: make <behavior-2> pass                     (blocked by Red-2)
  Refactor: clean up <behavior-2>                   (blocked by Green-2)
  ...
  Verify acceptance test passes for US<N>           (blocked by last Refactor)
```

### Construction

```bash
ACCEPT_ID=$(br create "Write acceptance test for US<N>" --parent $US_ID \
  --description "..." --json | jq -r '.id')
PREV=$ACCEPT_ID

for each behavior:
  RED=$(br create "Red: write failing test for <behavior>" --parent $US_ID \
    --description "..." --json | jq -r '.id')
  br dep add $RED $PREV
  GREEN=$(br create "Green: make <behavior> pass" --parent $US_ID \
    --description "..." --json | jq -r '.id')
  br dep add $GREEN $RED
  REFACTOR=$(br create "Refactor: clean up <behavior>" --parent $US_ID \
    --description "..." --json | jq -r '.id')
  br dep add $REFACTOR $GREEN
  PREV=$REFACTOR

VERIFY=$(br create "Verify acceptance test passes for US<N>" --parent $US_ID \
  --description "..." --json | jq -r '.id')
br dep add $VERIFY $PREV
```

### Naming Convention

```text
User Story Task:  "US<N>: <title>"
ATDD sub-tasks:   "Write acceptance test for US<N>", "Verify acceptance test passes for US<N>"
TDD sub-tasks:    "Red: write failing test for <behavior>", "Green: make <behavior> pass", "Refactor: clean up <behavior>"
```

## Type B: Documentation

Single task, no chain needed:

```bash
br create "<doc description>" --parent $PARENT_ID \
  --description "..." --json
```

Validation: file exists with correct content, no broken links or formatting issues.

## Type C: Configuration

Single task, no chain needed:

```bash
br create "<config change description>" --parent $PARENT_ID \
  --description "..." --json
```

Validation: relevant dry-run or check command exits 0 (e.g. `uv run ruff check`, `uv run pyright`, `uv lock --check`).

## Type D: Remediation

For review-generated fix tasks (from security, architecture, or quality reviews).

### Testable code (module has a `tests/` sibling test)

Create a parent task with Red-Green-Refactor sub-chain:

```bash
REMEDIATE_ID=$(br create "Remediate: <finding title>" --parent $PARENT_ID \
  --description "..." --json | jq -r '.id')

RED=$(br create "Red: write failing test for <finding>" --parent $REMEDIATE_ID \
  --description "..." --json | jq -r '.id')
GREEN=$(br create "Green: fix <finding>" --parent $REMEDIATE_ID \
  --description "..." --json | jq -r '.id')
br dep add $GREEN $RED
REFACTOR=$(br create "Refactor: clean up <finding> fix" --parent $REMEDIATE_ID \
  --description "..." --json | jq -r '.id')
br dep add $REFACTOR $GREEN
```

### Non-testable (config, docs, simple fix)

Single flat task — same as Types B/C:

```bash
br create "[<review-type>] <finding title>" --parent $PARENT_ID \
  --description "..." --json
```

## Description Templates

All task description templates (parameterized with `<placeholder>` variables) are in [`references/description-templates.md`](references/description-templates.md).

**CRITICAL**: Task descriptions are the ONLY context ralph passes to claude. They must be fully self-contained — a fresh claude session must be able to implement the task without exploring the codebase from scratch.
