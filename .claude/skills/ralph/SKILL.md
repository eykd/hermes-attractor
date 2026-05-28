---
name: ralph
description: Drain the beads ready queue from the user's current Claude Code session by dispatching one short-lived subagent per stage (prep → worker → verify) per task. Replaces the old `claude -p` background loop. Use when you want autonomous task processing inside the subscription envelope.
---

# Ralph Orchestrator (single-session, subagent-driven)

Ralph drains the beads ready queue **one task at a time** by dispatching
three subagents per iteration — `ralph-prep`, `ralph-worker`, `ralph-verify`
— from the user's current Claude Code session. There is no daemon, no
background process, no `claude -p` invocation, and no `.ralph.lock` /
`.ralph-monitor.json` state file. The session being visible to the user **is**
the monitor.

## Why this exists

Anthropic begins billing `claude -p` runs as overage on 2026-06-15. The old
ralph (a `claude -p` background driver) spawned a fresh `claude -p` child per
task and is no longer financially viable. This skill replaces it with a
pure-orchestrator model: every task starts in a fresh subordinate **subagent**
context (covered by the subscription), and the orchestrator's own context only
grows by ~180 tokens per task (three dispatch prompts + three one-line replies).

## When to use

- `/sp:07-implement` invokes this skill after its preflight checks. The
  current branch (the feature's epic branch) drives scope detection
  automatically.
- `/ralph` invokes this skill directly for ad-hoc work. On a
  `NNN-feature-name` branch with a matching epic, it scopes to that epic;
  otherwise it drains every ready task.

## Do not use this skill for

- Single tasks. Just do them directly.
- Tasks requiring interactive decisions.
- Exploratory work without a clear acceptance criterion in beads.

## How it works

```
Orchestrator (this session)
   loop {
     ① Agent(ralph-prep)    → "READY <id> SCOPE=<x>" | "QUEUE EMPTY SCOPE=<x>"
     ② Agent(ralph-worker)  → "OK <id>"   | "FAILED <id>: <reason>"
     ③ Agent(ralph-verify)  → "VERIFIED"  | "RECOVERED <id>"
     break if ① said "QUEUE EMPTY"
   }
```

The orchestrator never runs Bash, edits files, or reads files itself. Its
entire job is dispatching the three `Agent` calls and reading their
one-line returns.

## Orchestration prompt

Run this prompt verbatim in the current session (no slash-command needed —
you ARE the orchestrator once this skill is invoked):

```
You are the ralph orchestrator for this session. Drain the beads ready queue
by dispatching three subagents per task — prep, worker, verify — in strict
sequence, until prep reports the queue is empty.

YOU MUST NOT run Bash, read files, edit files, or otherwise do task work
yourself. Your entire job is dispatching Agent calls and reading their
one-line returns. If you find yourself about to call Bash, stop — that work
belongs in a subagent.

State variables you maintain in your head (NOT in files):
  - lastPrepId: the task ID prep returned last iteration (or null)
  - sameIdRepeats: how many consecutive iterations prep returned the same id
  - iterationCount: total iterations so far

Loop:

1. Dispatch: Agent(subagent_type="ralph-prep", description="ralph prep tick",
                   prompt="prep")
   Reply will be exactly "READY <id> SCOPE=<x>" or "QUEUE EMPTY SCOPE=<x>".
   - If iterationCount == 0: announce the chosen scope to the user verbatim
     ("Draining scope: <x>") so they can ^C if it's wrong.
   - If "QUEUE EMPTY": announce "Queue drained (scope=<x>)" and stop.
   - If <id> == lastPrepId: increment sameIdRepeats. If sameIdRepeats >= 2,
     stop and surface to the user: "Hot loop on <id> — stopping. Investigate
     manually." Otherwise continue.
   - Else: set lastPrepId = <id>, sameIdRepeats = 1.

2. Dispatch: Agent(subagent_type="ralph-worker", description="ralph worker tick",
                   prompt="Implement task <id>.")
   Reply will be exactly "OK <id>" or "FAILED <id>: <one-line>".

3. Dispatch: Agent(subagent_type="ralph-verify", description="ralph verify tick",
                   prompt="Verify task <id>.")
   Reply will be exactly "VERIFIED" or "RECOVERED <id>".

4. Speak one short line to the user (e.g. "✓ <id>" on VERIFIED,
   "↻ <id> recovered" on RECOVERED, "✗ <id>: <reason>" on FAILED-not-recovered).
   No commentary, no analysis, no plans.

5. Increment iterationCount. Goto 1.
```

## Scope detection

`ralph-prep` re-detects the scope every iteration:

1. Read `git branch --show-current`.
2. Strip leading `NNN-` digits, lowercase, replace hyphens with spaces.
3. Search `br list --type epic --status open --json` for an epic whose title
   (also lowercased / hyphens→spaces) contains that string.
4. If matched → scope = that epic ID, drain only its recursive descendants.
5. Otherwise → scope = `ALL`, drain every ready task.

Switching branches mid-run automatically follows the new branch's scope.

## Failure modes the orchestrator handles

| Symptom                            | Resolution                                                        |
| ---------------------------------- | ----------------------------------------------------------------- |
| worker returns `FAILED <id>: ...`  | verify releases the claim; orchestrator moves on (next prep tick) |
| prep returns the same `<id>` twice | hot-loop guard fires; orchestrator stops and surfaces             |
| prep returns `QUEUE EMPTY`         | orchestrator announces "Queue drained" and stops                  |
| user `^C`                          | session ends; no daemon to kill, no lockfile to clean             |

## What goes away vs. the old ralph

- The old `claude -p` background driver script and its helper directory
- `.ralph.lock`, `.ralph.log`, `.ralph.exit`, `.ralph-monitor.json`
- The 8-status monitor classifier (DONE/CRASHED/STRANDED/ZOMBIE/HOT_LOOP/…)
- The 15-minute `ScheduleWakeup` chain
- All `claude -p` invocations

## What stays the same

- Beads is still the single source of truth for task state.
- Per-task TDD/ATDD workflow is unchanged; it just runs inside the
  `ralph-worker` subagent now. US-prefixed tasks use the
  `pytest-acceptance-tests` skill for the acceptance loop and
  `/test-driven-development` for the inner cycle; other tasks use
  `/test-driven-development` + `pytest-unit-tests`. The full quality gate the
  worker runs before committing is the Python toolchain:
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`,
  `uv run pytest --cov` (100% coverage enforced).
- Commit + push + `br close` happen once per task, in order, same as before.
- `/sp:07-implement` is still the spec-kit entry point; it now calls this
  skill in-session after its preflight checks instead of spawning a daemon.

## Examples

### Drain the current branch's epic

```
/ralph
```

(Assuming you're sitting on `012-plugin-registration` and there is an
open epic with `plugin registration` in its title.)

### Drain every ready task across the repo

```
git checkout main
/ralph
```

(No matching epic on `main` → scope falls back to `ALL`.)
