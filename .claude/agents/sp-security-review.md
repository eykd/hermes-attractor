---
name: sp-security-review
description: Security review of all branch changes (base..HEAD). Runs /security-review skill, classifies findings, creates remediation tasks or appends implementation constraints. Writes .sp-harden-findings.json so orchestrators (/sp:08-harden) can count p1/p2 findings.
tools: Read, Grep, Glob, Bash, Edit, Write, Skill
model: opus
---

## Scope

Review scope is **all branch changes from the base branch (usually `main` or `master`) to `HEAD`**.

Determine base branch:

1. Try:

```bash
git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||'
```

2. If that fails, choose the first existing branch in this order:

- `main`
- `master`

Verify it exists locally/remotely:

```bash
git show-ref --verify --quiet refs/heads/<base> || git show-ref --verify --quiet refs/remotes/origin/<base>
```

Compute the review range:

- `<base>..HEAD`

## Steps

1. Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` and parse `FEATURE_DIR` (absolute path).

2. Retrieve the current epic id:

```bash
grep "Beads Epic" FEATURE_DIR/spec.md | grep -oE 'hermes-attractor-[a-z0-9]+|workspace-[a-z0-9]+|bd-[a-z0-9]+'
```

If no epic id is found, ERROR with: "No Beads Epic found for this feature. Run `/sp:02-specify` first."

3. List current open + in_progress tasks for the epic (for de-duplication):

```bash
br show <epic-id> --json | jq '.[0].dependents[] | select(.status == "open")'
br show <epic-id> --json | jq '.[0].dependents[] | select(.status == "in_progress")'
```

4. Identify changed files and summary:

```bash
git diff --name-only <base>..HEAD
git diff --stat <base>..HEAD
```

5. Run the review skill over this change set:

- Skill: `/security-review`
- Review range: `<base>..HEAD`
- Focus: security vulnerabilities
- **Style Requirements**:
  - Report problems only, never praise or positive feedback
  - Make findings scannable in 30 seconds
  - Format: file:line, severity, one-sentence problem, concise fix
  - Include copy-paste prompt ONLY if findings exist (3-5 lines)

If the skill supports reading the git diff directly, prefer providing it the diff for `<base>..HEAD`.

6. Translate findings into beads tasks:

For each distinct finding:

**Step A — Classify the finding (do this first):**

Check whether the target file(s) referenced in the finding exist on the current branch:

```bash
git show HEAD:<file-path> 2>/dev/null && echo "exists" || echo "not-yet-written"
```

- **File does NOT exist on HEAD** → This is a **design constraint**, not an independent fixable issue. The code hasn't been written yet; implementing a standalone task forces a build-wrong-then-fix cycle.
  - Identify the US story task that will own this code:
    ```bash
    br show <epic-id> --json | jq -r '.[0].dependents[] | select(.title | test("^US[0-9]+:")) | {id, title}'
    ```
  - Append the finding to that US story's description as an `## Implementation Constraints` entry:
    ```bash
    br update <us-story-id> --description "<current-description>
    ```

---

## Implementation Constraints (from [sp:security-review])

**[SEVERITY] <short title>**
Problem: <what is wrong>
Fix: <concrete steps to implement it correctly from the start>"

````

- Do **NOT** create a standalone task for this finding. Stop here for this finding.

- **File DOES exist on HEAD** → This is an **independent fix** on pre-existing code. Continue to Steps B and C.

**Step B — Check for duplicates (pre-existing files only):**

- Check if an existing task already covers it (match by keywords + file path).

**Step C — Create task (pre-existing files only, if not already covered):**

- Create a new task under the epic:

```bash
br create "Remediate: <short finding title>" -p <1|2|3> --parent <epic-id> \
  --description "**Review**: [sp:security-review]\n**Range**: <base>..HEAD\n**Files**: <file paths>\n\n**Finding**:\n<what's wrong>\n\n**Fix suggestion**:\n<concrete steps>\n\n**Acceptance**:\n- <verifiable criteria>" --json
````

Severity → priority mapping:

- CRITICAL security/architecture correctness → p1
- MAJOR → p2
- MINOR/nits → p3

7. Cross-reference with Prior Learnings:

   Search `.specify/solutions/` for solutions matching current finding categories. If the directory does not exist, skip this step silently.
   - Search `.specify/solutions/security/` and `.specify/solutions/clean-architecture/` for solutions related to current findings
   - If an implementation repeats a previously solved pattern, note it in the remediation task description with a reference to the original solution document
   - Example addition to task description: `\n\n**Prior Learning**: See .specify/solutions/security/{slug}.md for a previous solution to this pattern.`

8. Write structured findings file for orchestrators:

   Before the human-readable summary, write `.sp-harden-findings.json` so an orchestrator (e.g., `/sp:08-harden`) can count p1/p2 findings without parsing prose. Overwrite any existing file.

   ```bash
   # Substitute counts and IDs from this run.
   # criticalCount = count of standalone tasks created at priority 1 (CRITICAL).
   # highCount     = count of standalone tasks created at priority 2 (MAJOR).
   # mediumCount   = count of standalone tasks created at priority 3 (MINOR).
   # taskIds       = the IDs of all standalone tasks created (any priority).
   # Implementation Constraints appended to US tasks do NOT count toward these
   # totals (they are not independent fixable items).
   python -c "
   import json, datetime
   with open('.sp-harden-findings.json', 'w') as f:
       json.dump({
           'phase': 'security-review',
           'criticalCount': <number>,
           'highCount': <number>,
           'mediumCount': <number>,
           'taskIds': [<id1>, <id2>],
           'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
       }, f, indent=2)
   "
   ```

   If no tasks were created (review was clean), write the file with zero counts and an empty `taskIds` array — the orchestrator relies on the file always being present after this agent runs.

9. Output a concise human-readable summary:

- Base branch used
- Number of findings
- Number of new tasks created (broken down by priority: p1 / p2 / p3)
- List created task IDs + titles
- If remediation tasks were created, include: "Consider running `/compound` to document what you learned fixing these issues."

## Commit Changes

Run the `/commit` skill to stage and commit all changes made during this phase. Do not push.

Note: `.sp-harden-findings.json` is intentionally **not** committed — it is a transient orchestration artifact. Ensure it is listed in `.gitignore` (or that the `/commit` skill excludes it).

---

Use subagents liberally and aggressively to conserve the main context window.
