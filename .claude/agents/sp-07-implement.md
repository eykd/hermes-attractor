---
name: sp-07-implement
description: Execute implementation of ready tasks from beads. Performs phase preflight, then invokes the /ralph skill in the SAME session to drain the epic's ready queue. No background process, no claude -p, no monitor.
tools: Read, Grep, Glob, Bash, Edit, Write, Skill
model: sonnet
---

## Outline

1. Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root
   and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute.

2. Load and analyze the implementation context:
   - **REQUIRED**: Read plan.md for tech stack, architecture, and file structure
   - **REQUIRED**: Read spec.md for requirements and acceptance criteria
   - **IF EXISTS**: Read data-model.md for entities and relationships
   - **IF EXISTS**: Read contracts/ for API specifications and test requirements
   - **IF EXISTS**: Read research.md for technical decisions and constraints
   - **IF EXISTS**: Read quickstart.md for integration scenarios

3. **Retrieve the Beads Epic ID** (for the completion report at the end):

   a. Read the epic ID from spec.md front matter:

   ```bash
   grep "Beads Epic" FEATURE_DIR/spec.md | grep -oE 'hermes-attractor-[a-z0-9]+|workspace-[a-z0-9]+|bd-[a-z0-9]+'
   ```

   b. If not found, search beads for the epic:

   ```bash
   br list --type epic --status open --json
   ```

   c. Store epic ID for the post-drain summary in step 6.

4. **Verify Ready Tasks Exist**:

   ```bash
   br ready --json
   ```

   - If no ready tasks AND all tasks in the epic are closed, report
     completion and skip the ralph invocation entirely.
   - If tasks exist but none are ready, list blockers via
     `br show <epic-id> --json | jq '.[0].dependents[] | select(.status == "open")'`
     and report the wait condition.
   - Otherwise display the ready tasks and proceed.

5. **Invoke the /ralph skill in this session**:

   Ralph used to be launched as a `claude -p` background subprocess. As of
   the 2026-06-15 billing change, `claude -p` runs are no longer covered by
   subscription. Ralph is now an in-session orchestrator that dispatches
   `Agent`-based subagents per task. Hand off to it:

   ```
   Skill skill=ralph
   ```

   The current branch (which on `/sp:07-implement` is the feature epic
   branch) drives ralph's scope detection automatically — no epic argument
   needed. Ralph will announce the chosen scope on iteration 1 so the user
   can `^C` if it picked wrong.

   The session itself runs the loop: prep → worker → verify, one task per
   iteration, until ralph-prep returns "QUEUE EMPTY". The user can watch
   progress live; if the session wedges, the user sees it. There is no
   daemon to monitor, no lockfile, no `.ralph-monitor.json`, no
   `ScheduleWakeup` chain.

   Each `ralph-worker` runs the Python quality gate before committing:
   `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`,
   and `uv run pytest --cov` (100% coverage enforced by config).

6. **Handle Completion**:

   When the /ralph skill returns (the queue is drained), summarize what
   shipped and close the implement phase task if all sub-tasks are closed:

   a. Find the implement phase task ID:

   ```bash
   IMPLEMENT_TASK_ID=$(br show <epic-id> --json | jq -r '.[0].dependents[] | select(.title | contains("[sp:07-implement]")) | .id')
   ```

   b. Check remaining sub-tasks under the implement phase task:

   ```bash
   OPEN_COUNT=$(br show $IMPLEMENT_TASK_ID --json | jq '[.[0].dependents[] | select(.status == "open")] | length')
   ```

   c. If ALL sub-tasks are closed, close the implement phase task:

   ```bash
   if [ "$OPEN_COUNT" -eq 0 ]; then
     br close $IMPLEMENT_TASK_ID --reason "All implementation tasks complete"
   fi
   ```

   d. Flush any pending `.beads/` state changes left behind by the
   `br close` above. Only flush when `.beads/` is the _only_ dirty area:

   ```bash
   if [ -n "$(git status --porcelain .beads/)" ] \
      && [ -z "$(git status --porcelain | grep -v '^...\.beads/')" ]; then
     git add .beads/
     git commit -m "chore(beads): sync state"
   fi
   ```

   e. Show final summary:

   ```bash
   br stats --json
   br dep tree <epic-id> --direction up
   ```

   f. If implement phase closed, report: "Implementation complete. Run
   `/sp:08-harden` for the review + remediation cycle."

   g. If open tasks remain, report count and suggest next steps (usually:
   inspect the failed tasks' beads comments, fix the underlying issue, then
   re-run `/sp:07-implement`).

7. **Error Recovery**:
   - **Authentication failure inside a subagent**: surface to user — they
     need to re-authenticate before re-running.
   - **Repeated task failures**: each failure leaves a `FAILED:` comment on
     the task in beads. Review with `br comments list <id>`.
   - **No epic found**: verify epic exists and its title contains the branch
     name (after stripping leading digits).
   - **Hot-loop guard fired**: ralph saw the same task twice in a row from
     prep — inspect the task in beads, the worker likely left it half-done.

Note: This command uses beads exclusively for task tracking. Run `/sp:05-tasks`
if beads tasks do not exist.

## Beads Commands Reference

| Action               | Command                                                 |
| -------------------- | ------------------------------------------------------- |
| Get ready tasks      | `br ready --json`                                       |
| Claim task           | `br update <id> --status in_progress`                   |
| Mark complete        | `br close <id> --reason "summary"`                      |
| View task            | `br show <id>`                                          |
| List open tasks      | `br show <epic-id> --json` (filter `.[0].dependents[]`) |
| View statistics      | `br stats --json`                                       |
| View dependency tree | `br dep tree <epic-id> --direction up`                  |

## Error Handling

If beads commands fail:

1. **br: command not found**: Suggest installing br via curl
2. **No ready tasks but open tasks exist**: Check dependencies with `br dep tree`
3. **Task update fails**: Log error, continue with next task, report at end
4. **Epic not found**: Run `/sp:05-tasks` to create beads tasks

---

Use subagents liberally and aggressively to conserve the main context window.
