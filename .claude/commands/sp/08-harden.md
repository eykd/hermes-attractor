# /sp:08-harden — Iterative Review + Remediation Orchestrator

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input above when deciding orchestrator behaviour. The supported argument forms are:

- empty (or no flags) → start a fresh harden run from state `r8`
- `--resume` → resume from `.sp-harden-state.json` (used after the user manually `^C`'d mid-cycle and wants to continue from the last persisted state)
- `--status` → print current state file contents and exit without doing work
- `--reset` → delete `.sp-harden-state.json` and `.sp-harden-findings.json` and exit (manual recovery)

## Purpose

Loop through three reviews — security, architecture, code quality — and drive ralph between each one to fix any p1/p2 (CRITICAL/MAJOR) findings. A fix in any review re-starts the cycle from security, because a quality fix can introduce a security regression. The orchestrator exits when **three reviews in a row produce zero p1/p2 standalone findings** (a clean cycle), or when the safety cap of 5 outer cycles is reached.

p3 (MINOR) findings are still filed as remediation tasks but do not trigger an implement step or restart the cycle. They remain open for the user to address later.

## State Machine

```
states:  r8 | r9 | r10 | i | done | failed
r8  → run sp-security-review
       if p1+p2 created > 0: state=i, returnTo=r8
       else: state=r9
r9  → run sp-architecture-review
       if p1+p2 created > 0: state=i, returnTo=r8   # restart cycle after fix
       else: state=r10
r10 → run sp-code-quality-review
       if p1+p2 created > 0: state=i, returnTo=r8
       else: state=done   # clean cycle complete
i   → invoke the /ralph skill in this session (synchronous in-session drain)
       on ralph "Queue drained" → state=returnTo, cycleCount++
       on ralph hot-loop or user ^C → state=failed
```

## Execution Steps

Run all of the following directly in the main conversation. Do NOT delegate orchestration to another agent. (Sub-agent calls for the three reviews and for `sp-ralph-drain` are launched via the Agent tool.)

### Step 0 — Argument handling and state load

a. If `--status` is passed: read `.sp-harden-state.json` if present, print its contents and the contents of `.sp-harden-findings.json`, then exit.

b. If `--reset` is passed: delete `.sp-harden-state.json` and `.sp-harden-findings.json` if they exist. Report what was deleted. Exit.

c. If `--resume` is passed: require `.sp-harden-state.json` to exist. If missing, ERROR: "Cannot --resume: no .sp-harden-state.json found. Run /sp:08-harden with no arguments to start fresh." and exit.

d. If no flags: if `.sp-harden-state.json` exists, WARN the user and ask whether to resume or reset. (If user pre-confirmed via context, default to resume.) If file does not exist, initialise:

```json
{
  "state": "r8",
  "returnTo": null,
  "cycleCount": 1,
  "cycleStartHead": "<git rev-parse HEAD>",
  "cumulativeCriticalHigh": 0,
  "epicId": "<from spec.md front matter>",
  "baseBranch": "<resolved per below>",
  "startTime": "<ISO timestamp>",
  "lastTransition": "<ISO timestamp>"
}
```

Resolve `baseBranch` once at init:

```bash
base=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
if [ -z "$base" ]; then
  for candidate in main master; do
    if git show-ref --verify --quiet "refs/heads/$candidate" || git show-ref --verify --quiet "refs/remotes/origin/$candidate"; then
      base=$candidate
      break
    fi
  done
fi
```

Resolve `epicId` from `specs/<branch>/spec.md` front matter (`grep "Beads Epic"` matched against `hermes-attractor-[a-z0-9]+|workspace-[a-z0-9]+|bd-[a-z0-9]+`). If not found, ERROR and exit.

Write the state file.

### Step 1 — Dispatch on current state

Read `.sp-harden-state.json` and dispatch:

| state  | Go to step |
| ------ | ---------- |
| r8     | Step 2     |
| r9     | Step 3     |
| r10    | Step 4     |
| i      | Step 5     |
| done   | Step 6     |
| failed | Step 7     |

### Step 2 — Run security review (state = r8)

a. Pre-cycle cap check: if `cycleCount > 5`, transition to `failed` with reason "max outer cycles exceeded" and go to Step 7.

b. Delete any stale `.sp-harden-findings.json`.

c. Launch the `sp-security-review` agent via the Agent tool. Prompt (verbatim — forward the user's original $ARGUMENTS so per-feature context propagates):

```
<original $ARGUMENTS>

Context: Called from /sp:08-harden cycle <cycleCount>, state r8.
Write .sp-harden-findings.json per your spec, then commit.
```

d. After the agent returns, read `.sp-harden-findings.json`. Compute:

```
p1p2 = criticalCount + highCount
```

e. Update state:

- If `p1p2 > 0`: set `state = i`, `returnTo = r8`. Add `p1p2` to `cumulativeCriticalHigh`. Go to Step 5.
- Else: set `state = r9`. Go to Step 3.

Persist state file. Record the transition timestamp.

### Step 3 — Run architecture review (state = r9)

Identical to Step 2 but with the `sp-architecture-review` agent. Prompt context: `cycle <cycleCount>, state r9`.

Transitions:

- If `p1p2 > 0`: `state = i`, `returnTo = r8` (restart cycle). Go to Step 5.
- Else: `state = r10`. Go to Step 4.

### Step 4 — Run code-quality review (state = r10)

Identical to Step 2 but with the `sp-code-quality-review` agent. Prompt context: `cycle <cycleCount>, state r10`.

Transitions:

- If `p1p2 > 0`: `state = i`, `returnTo = r8` (restart cycle). Go to Step 5.
- Else: `state = done`. Go to Step 6.

### Step 5 — Implement remediations (state = i)

a. Verify `returnTo` is set (must be `r8` per the state machine). If null, ERROR.

b. Check whether any ready tasks exist:

```bash
READY_COUNT=$(br ready --json | jq 'map(select(.issue_type != "epic" and (.title | startswith("[sp:") | not))) | length')
```

If `READY_COUNT == 0`, the prior review filed remediations that are all blocked or already closed — treat this as an immediate DONE for the implement step (no work to drain). Skip step 5c.

c. If `READY_COUNT > 0`, invoke the `/ralph` skill **in this session**:

```
Skill skill=ralph
```

Ralph drains synchronously: it dispatches `ralph-prep` / `ralph-worker` /
`ralph-verify` subagents per task and returns control when it announces
"Queue drained" (or when its hot-loop guard fires). No background process,
no `.ralph-drain-result.json`, no ScheduleWakeup chain.

The user can `^C` mid-drain; on the next `/sp:08-harden --resume` the state
file will still be `i` and step 5 will re-run.

d. On normal ralph return: increment `cycleCount` (this completes the outer
cycle). Set `state = returnTo` (always `r8`), `returnTo = null`. Delete
`.sp-harden-findings.json`. Persist state. Recursively continue at Step 1
to start the next cycle's r8 review.

e. On ralph hot-loop or user `^C`: leave `state = i` in the state file so a
subsequent `/sp:08-harden --resume` retries. If the same task keeps
hot-looping across resumes, set `state = failed` and go to Step 7.

### Step 6 — Done (state = done)

a. Close the `[sp:08-harden]` beads phase task:

```bash
HARDEN_TASK_ID=$(br show <epic-id> --json | jq -r '.[0].dependents[] | select(.title | contains("[sp:08-harden]")) | .id')
br close "$HARDEN_TASK_ID" --reason "Harden complete: <cycleCount> cycle(s), <cumulativeCriticalHigh> total p1/p2 remediated, HEAD advanced from <cycleStartHead> to $(git rev-parse HEAD)"
```

b. Delete orchestration state files:

```bash
rm -f .sp-harden-state.json .sp-harden-findings.json
```

c. Flush any pending `.beads/` state with the standard guarded gate (only if `.beads/` is the only dirty area).

d. Report to the user:

```markdown
## /sp:08-harden complete

**Cycles run**: <cycleCount> of 5 max
**Termination**: Clean cycle (zero p1/p2 across security, architecture, quality)
**HEAD advance**: <cycleStartHead> → <current HEAD>
**Total p1/p2 remediated**: <cumulativeCriticalHigh>

Open p3 (MINOR) tasks may still be present — they were filed but not blocking. Review with `br ready --json | jq '.[] | select(.priority == 3)'`.

**Next steps:** Run `/sp:next` to verify epic completion, or open a PR.
```

### Step 7 — Failed (state = failed)

a. Do **not** close the harden phase task — leave it open for the user to triage.

b. Surface the failure to the user with:

- Current state
- Last transition timestamp
- Failure reason (hot-loop guard message, cycle cap, or user-reported issue)
- Recommended next action: inspect the offending task with `br comments list <id>`, manually unblock it, then resume with `/sp:08-harden --resume`. Or `--reset` to start fresh.

c. Leave `.sp-harden-state.json` in place so the user can resume.

## Important Invariants

1. **The state file is the source of truth.** Every transition writes it before launching the next sub-agent. If the session is interrupted (e.g., the user `^C`s mid-cycle), `/sp:08-harden --resume` reconstructs intent from the file alone.

2. **Reviews are responsible for writing `.sp-harden-findings.json`.** If a review agent fails to write the file, treat that as `p1p2 = 0` only if it also reported zero findings in its prose summary; otherwise ERROR (do not silently advance).

3. **Cycle restart on any fix.** Per user decision, restart-on-fix is the chosen policy. A quality fix can introduce a security regression; only three clean reviews in a row prove the branch is hardened.

4. **Never modify `.beads/` directly.** All beads state changes go through `br` so its event log stays consistent. Flush-on-terminal mirrors the guard ralph already uses.

5. **Do not commit `.sp-harden-state.json` or `.sp-harden-findings.json`.** They are in `.gitignore` for that reason. The reviews' `/commit` skill calls must not stage them.

## Notes

- The cap of 5 outer cycles is a safety net; in practice convergence happens in 1–3 cycles on a healthy branch.
- p3 findings continue to be filed every cycle. This is intentional: the user benefits from a full p3 list to triage post-harden, even though p3 doesn't block the loop.
- For a single ad-hoc review without the loop, use `/sp:security-review`, `/sp:architecture-review`, or `/sp:code-quality-review` directly. Those commands skip the harden state machine entirely.
- If `br ready` returns zero non-epic, non-meta tasks when state is `i`, the orchestrator treats it as immediate DONE — this can happen if a previous run already drained the relevant tasks before harden was re-entered.
