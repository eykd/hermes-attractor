---
name: deepen-plan-loop
description: Iteratively deepen plan.md by running the deepen-plan logic in a loop until no uncertain sections remain or progress stalls. Use after /sp:03-plan for complex features with multiple uncertain areas.
tools: Read, Grep, Glob, Bash, Edit, Write, Skill
model: sonnet
---

## Purpose

Iteratively deepen the implementation plan by researching uncertain areas and incorporating prior learnings. Runs up to 3 passes, stopping early when all uncertainties are resolved or progress stalls. Each pass commits separately for auditability.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Algorithm

### 1. Setup

Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse `FEATURE_DIR`.

- All file paths must be absolute.

Read `FEATURE_DIR/plan.md`. If it does not exist, ERROR: "No plan.md found. Run `/sp:03-plan` first."

### 2. Initial Scan

Count uncertainty markers in plan.md using Grep:

- Literal markers: `NEEDS CLARIFICATION`, `TBD`, `TODO`
- Vague language (word-boundary match): `\b(might|could|possibly|consider)\b`

Record total as `previous_count`.

If `previous_count` is 0, report "Plan has no uncertain sections. No deepening needed." and exit.

### 3. Iteration Loop (max 3 passes)

For each pass:

#### 3a. Identify Uncertain Sections

Re-read `FEATURE_DIR/plan.md` and scan for:

- Sections containing "NEEDS CLARIFICATION" or "TBD" or "TODO"
- Sections with vague language ("might", "could", "possibly", "consider")
- Sections that reference technologies or patterns without concrete implementation details

List the uncertain sections found.

#### 3b. Search Prior Learnings

If `.specify/solutions/` exists, search for solutions relevant to each uncertain section:

- Match by category (e.g., uncertain plugin-registration patterns -> search `plugin/`; uncertain port/adapter boundaries -> search `clean-architecture/`)
- Match by keywords from the uncertain section
- Extract `## Solution` and `## Prevention` sections from matches

If the directory does not exist, skip this step silently.

#### 3c. Research and Expand

For each uncertain section:

1. If prior learnings exist, incorporate the concrete patterns from the solution documents
2. If no prior learnings exist, research the unknown using available tools (Grep the codebase, read reference files, use WebSearch if needed)
3. Replace vague language with concrete implementation details
4. Add code examples where helpful (Python, matching the hexagonal layout under `src/hermes_attractor/{domain,ports,adapters,use_cases,plugin}/`)

#### 3d. Update plan.md

Use the Edit tool to expand uncertain sections in plan.md with:

- Concrete implementation approaches
- Code patterns or configuration examples
- Links to referenced prior learnings

If prior learnings were applied, add or update the `## Applied Learnings` section.

#### 3e. Commit

Run the `/commit` skill to stage and commit all changes made during this pass. Do not push.

#### 3f. Check Termination

Re-scan `FEATURE_DIR/plan.md` for uncertainty markers (same patterns as Step 2). Record as `current_count`.

- If `current_count` == 0: **stop** (fully resolved)
- If `current_count` >= `previous_count`: **stop** (stalled -- no progress made)
- Otherwise: set `previous_count` = `current_count` and continue to next pass

### 4. Cumulative Report

Output:

```markdown
## Iterative Plan Deepening Complete

**Iterations run**: {N} of 3 max
**Termination reason**: {all resolved | stalled progress | max iterations}

**Per-iteration summary**:

- Pass 1: {X} uncertainties found, {Y} resolved
- Pass 2: ...
- ...

**Final state**: {0 | N} remaining uncertainties in plan.md

Run `/sp:04-red-team` to adversarially review the strengthened plan.
```

## Important Notes

- This agent does NOT create beads tasks or close any phase task.
- Each iteration is idempotent -- interrupting mid-loop is safe because each pass commits.
- Vague-language scanning uses word boundaries to avoid false positives (e.g., "considered" won't match "consider").
- If the plan uses "might"/"could"/"consider" intentionally (e.g., in a "Alternatives" section), the stall detector will catch this and stop gracefully.

---

Use subagents liberally and aggressively to conserve the main context window.
