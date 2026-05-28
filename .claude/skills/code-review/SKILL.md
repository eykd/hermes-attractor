---
name: code-review
description: "Use when: (1) Orchestrating parallel code reviews across the current branch's changes, (2) Running quality-review and architecture-review agents together, (3) Deduplicating findings against existing beads tasks, (4) Creating beads tasks for review findings under a branch epic."
---

# Code Review Orchestration Skill

Orchestrate parallel code reviews using specialized review agents. Creates beads tasks for all findings.

## Workflow

1. **Detect or create epic** from current git branch
2. **Launch parallel reviews** (2 concurrent Haiku agents):
   - `quality-review` - Correctness, tests, standards, CLI security
   - `architecture-review` - Hexagonal layer boundaries
3. **Collect findings** from both agents
4. **Deduplicate** against existing beads tasks
5. **Create beads tasks** for new findings
6. **Report summary** to user

## Usage

```bash
# From CLI
/code-review

# Or use review.sh for automation
./review.sh
./review.sh --skills quality-review
./review.sh --files src/hermes_attractor/domain/concept.py
```

## Epic Detection

- Strips numeric prefix from branch name: `001-add-feature` → `add-feature`
- Creates epic in beads if not exists
- All finding tasks created under this epic

## Review Agent Invocation

Launches agents with:
- Model: Haiku (fast, cost-effective)
- File content to review
- Open tasks list for deduplication
- Skill-specific instructions

## Output Format

Each agent should output:

```
Created task: [task-id] - [title]
Created task: [task-id] - [title]
No new findings for [file-path]
```

## Deduplication Logic

Before creating task, check if similar finding exists:
- Compare against open tasks under same epic
- Match on file path + finding type
- Only create if genuinely new

## Priority Mapping

| Severity | Beads Priority |
|----------|----------------|
| Critical | 0 |
| High | 1 |
| Medium | 2 |
| Low | 3 |

## Task Template

```bash
npx bd create "[skill] Finding title" \
  --description "File: [path]
Line: [line-number]
Severity: [severity]
Skill: [skill-name]

Problem:
[problem description]

Fix:
[fix steps]" \
  --priority [0-3] \
  --parent [epic-id]
```

## Integration with ralph.sh

After code review creates tasks:
1. Run `ralph.sh` to auto-fix findings
2. Ralph processes tasks one by one
3. Each fix is committed separately
4. Repeat until all findings resolved

## References

- quality-review skill - Quality review patterns
- architecture-review skill - Architecture validation
- review.sh - Automated review script
