# /sp:04-red-team — Iterative Deepen-Plan + Red-Team Orchestrator

## User Input

```text
$ARGUMENTS
```

You **MUST** forward the user input above verbatim to both subagents on every outer iteration, and consider it yourself when deciding orchestrator behaviour (if not empty).

## Purpose

Drive an **outer iteration loop** that alternates `deepen-plan-loop` and `sp-04-red-team-pass` until one full cycle produces no further changes to `plan.md`. This catches cross-agent second-order effects (deepen-plan resolving uncertainties may open new attack surface; red-team mitigations may introduce new vague language) without the user babysitting the workflow.

**Order each outer cycle**: deepen-plan first, then red-team. Concretize so the attacker has a concrete plan to review.

**Outcome**: a single `/sp:04-red-team` invocation produces a plan that is both fully concretized (no `NEEDS CLARIFICATION` / `TBD` / `TODO` / vague language) and adversarially hardened (no new Critical/High findings), with both conditions stable simultaneously.

## Important Invariant

Convergence relies on each inner subagent committing **iff** it modified `plan.md`, and not committing when it made no changes. Both `deepen-plan-loop` and `sp-04-red-team-pass` satisfy this via the `/commit` skill (which is a no-op when there are no staged changes). The orchestrator detects convergence by comparing `git rev-parse HEAD` before and after each subagent call — if HEAD did not advance, the subagent made no changes. **Do not change this invariant without also updating the convergence logic below.**

## Execution Steps

Run all of the following directly in the main conversation. Do NOT delegate this orchestration to another agent.

### Step 1 — Setup

Run `.specify/scripts/bash/check-prerequisites.sh --json` from the repo root and parse the JSON for `FEATURE_DIR`.

- All file paths must be absolute.
- Verify `FEATURE_DIR/plan.md` exists. If not, ERROR: "No plan.md found. Run `/sp:03-plan` first." and stop. Do **not** proceed to Step 3 (phase task close) on error.

Record `branch_start_head=$(git rev-parse HEAD)` for the final report.

Initialise:

- `outer_iteration = 0`
- `outer_summaries = []` (list of `{iteration, deepen_summary, deepen_changed, redteam_summary, redteam_changed}`)
- `termination_reason = null`

### Step 2 — Outer Iteration Loop (max 3 outer iterations)

Repeat the following until termination. The cap of 3 is a safety net; the common case is 1 outer iteration.

#### 2a. Snapshot HEAD before deepen-plan

```bash
pre_deepen_head=$(git rev-parse HEAD)
```

#### 2b. Launch deepen-plan-loop

Use the Agent tool to launch the `deepen-plan-loop` agent. Prompt:

```
<the original $ARGUMENTS verbatim>

Context: Called from /sp:04-red-team outer iteration <N>. Run one full execution and return your standard report.
```

Capture the returned report into `deepen_summary_<N>`.

#### 2c. Snapshot HEAD after deepen-plan / error check

```bash
post_deepen_head=$(git rev-parse HEAD)
```

If the subagent's report indicates an error (e.g. missing `plan.md`, prerequisite failure), **abort the orchestrator immediately**. Do not run red-team. Do not close the beads phase task. Surface the error to the user and stop.

#### 2d. Launch sp-04-red-team-pass

Use the Agent tool to launch the `sp-04-red-team-pass` agent. Prompt:

```
<the original $ARGUMENTS verbatim>

Context: Called from /sp:04-red-team outer iteration <N>. Run one full execution and return your standard report.
```

Capture the returned report into `redteam_summary_<N>`.

#### 2e. Snapshot HEAD after red-team / error check

```bash
post_redteam_head=$(git rev-parse HEAD)
```

If the subagent's report indicates an error, **abort the orchestrator immediately**. Do not close the beads phase task. Surface the error to the user and stop.

#### 2f. Compute change flags

```
deepen_changed  = (pre_deepen_head    != post_deepen_head)
redteam_changed = (post_deepen_head   != post_redteam_head)
outer_changed   = deepen_changed || redteam_changed
```

Append `{iteration: N, deepen_summary, deepen_changed, redteam_summary, redteam_changed}` to `outer_summaries`.

#### 2g. Termination check

- If `outer_changed == false`: set `termination_reason = "Converged: neither agent modified the plan."` and **stop**.
- Else if `outer_iteration >= 3`: set `termination_reason = "Max outer iterations reached (3)."` and **stop**.
- Otherwise: increment `outer_iteration` and continue from Step 2a.

### Step 3 — Close Phase Task

Only reached if Step 2 terminated normally (no subagent error).

a. Read the epic ID from `FEATURE_DIR/spec.md` front matter:

```bash
grep "Beads Epic" $FEATURE_DIR/spec.md | grep -oE 'hermes-attractor-[a-z0-9]+|workspace-[a-z0-9]+|bd-[a-z0-9]+'
```

b. Find the red team phase task:

```bash
br show <epic-id> --json | jq -r '.[0].dependents[] | select(.title | contains("[sp:04-red-team]")) | .id'
```

c. Close the task with a summary including outer-iteration count and branch HEAD advance:

```bash
br close <red-team-task-id> --reason "Iterative red-team complete: <N> outer iteration(s), HEAD advanced from <branch_start_head> to $(git rev-parse HEAD)"
```

Substitute `<N>` and `<branch_start_head>` with their captured values. Do not close the task more than once.

### Step 4 — Cumulative Report

Compute the final uncertainty marker count cheaply:

```bash
grep -cE 'NEEDS CLARIFICATION|TBD|TODO|\b(might|could|possibly|consider)\b' "$FEATURE_DIR/plan.md"
```

Then output a single markdown report to the user:

```markdown
## Iterative Red Team Complete

**Outer iterations run**: {N} of 3 max
**Termination reason**: {converged | max iterations}
**HEAD advance**: `{branch_start_head}` → `{current HEAD}`
**Remaining uncertainty markers in plan.md**: {count}

### Outer Iteration {1}

- **Deepen-plan**: {"no changes" if !deepen_changed else deepen_summary_1}
- **Red-team**: {"no changes" if !redteam_changed else redteam_summary_1}

### Outer Iteration {2}

- ...

### Outer Iteration {N}

- ...

**Next Steps:**

- Review the enhanced plan in `$FEATURE_DIR/plan.md`.
- Run `/sp:next` to proceed to `[sp:05-tasks]`.
```

When a subagent did not advance HEAD on a given outer iteration, render that subagent's row as `"no changes"` rather than its full report (the report is still captured but is redundant when nothing changed). When it did advance HEAD, include the sub-report's headline/summary lines — not the full multi-page output — to keep main-conversation context bounded.

## Notes

- This orchestrator never commits directly. All commits originate from the two inner subagents via the `/commit` skill.
- The `/sp:next` flow that triggers `/sp:04-red-team` is unaffected; `/sp:next` invokes this command by emitting it as the next command from its main-conversation output.
- For a standalone, mid-plan concretization pass without adversarial review, users can still run `/deepen-plan` directly.
