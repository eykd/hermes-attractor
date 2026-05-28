---
name: sp-05-tasks
description: Generate implementation tasks organized by user story. Creates beads tasks with dependencies, skill references, and acceptance criteria. Generates acceptance spec files.
tools: Read, Grep, Glob, Bash, Edit, Write, Skill
model: sonnet
---

## Outline

1. **Setup**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

2. **Load design documents**: Read from FEATURE_DIR:
   - **Required**: plan.md (tech stack, libraries, structure), spec.md (user stories with priorities)
   - **Optional**: data-model.md (entities), contracts/ (port/interface contracts), research.md (decisions), quickstart.md (test scenarios)
   - Note: Not all projects have all documents. Generate tasks based on what's available.

3. **Retrieve Beads Epic ID**:

   a. Read the epic ID from spec.md front matter:

   ```bash
   grep "Beads Epic" FEATURE_DIR/spec.md | grep -oE 'hermes-attractor-[a-z0-9]+|workspace-[a-z0-9]+|bd-[a-z0-9]+'
   ```

   b. If not found in spec.md, search beads for epic by feature name:

   ```bash
   br list --type epic --status open --json
   ```

   - Parse JSON to find epic matching the feature branch name
   - Extract the epic ID

   c. If no epic exists, create one:

   ```bash
   br create "Feature: <feature-name>" -t epic -p 0 --description "Epic for <feature-name> feature" --json
   ```

   - Store the returned ID for use in task creation

   d. Store epic ID for subsequent task creation steps

4. **Execute task generation workflow**:
   - Load plan.md and extract tech stack, libraries, and project structure (the hexagonal layout under `src/hermes_attractor/{domain,ports,adapters,use_cases,plugin}/`). Also extract any `## Presentation Design` section if present (only relevant when the feature ships user-facing UI) and the `## Acceptance Test Strategy` section if present (user stories with acceptance scenarios and planned spec file paths). Map any presentation requirements to the user stories they serve.
   - Load spec.md and extract user stories with their priorities (P1, P2, P3, etc.)
   - If data-model.md exists: Extract entities and map to user stories
   - If contracts/ exists: Map port/interface contracts to user stories
   - If research.md exists: Extract decisions for setup tasks
   - Generate tasks organized by user story (see Task Generation Rules below)
   - Generate dependency graph showing user story completion order
   - Create parallel execution examples per user story
   - Validate task completeness (each user story has all needed tasks, independently testable)

5. **Create Beads Tasks** (as children of the [sp:07-implement] phase task):

   **First, find the implement phase task** (created by `/sp:02-specify`):

   ```bash
   IMPLEMENT_TASK_ID=$(br show <epic-id> --json | jq -r '.[0].dependents[] | select(.title | contains("[sp:07-implement]")) | .id')
   ```

   Store this ID - all user story tasks will be created as children of this task.

   **Skill Mapping Reference** - Use these skills based on task type (Python toolchain):

   | Task Pattern                                          | Skills                                                          |
   | ----------------------------------------------------- | -------------------------------------------------------------- |
   | `US\d+.*` (user-story / acceptance task)              | `pytest-acceptance-tests` (outer loop) + `/test-driven-development` |
   | `Create.*entity`, `.*domain model`                    | `/test-driven-development`, `pytest-unit-tests`                |
   | `Implement.*adapter`, `.*repository`                  | `/test-driven-development`, `pytest-unit-tests` (integration)  |
   | `Implement.*use case`, `.*application service`        | `/test-driven-development`, `pytest-unit-tests`                |
   | `Define.*port`, `.*Protocol`, `.*interface`           | `/test-driven-development` (contract tests)                    |
   | `Register.*plugin`, `.*entry point`                   | `/test-driven-development`, `pytest-unit-tests` (contract)     |
   | `Write.*test`, `.*test_.*`                            | `pytest-unit-tests`                                            |
   | `Setup.*`, `Configure.*`                              | `/test-driven-development` (config validation)                 |
   | `.*documentation`, `.*docstring`                      | (write + `uv run ruff check` docstring rules)                  |

   For each user story from spec.md:

   a. Create a task for the user story **as a child of the implement task** with description:

   ```bash
   br create "US<N>: <user-story-title>" -p <priority> --parent $IMPLEMENT_TASK_ID \
     --description "**Spec**: specs/$BRANCH/spec.md §US-<N>
   **Goal**: <user-story-goal-from-spec>
   **Acceptance**: <acceptance-criteria-summary>

   ## Implementation Constraints
   _(Review findings for unwritten code in this story are merged here by sp:06/08. Read this section before writing any code.)_" --json
   ```

   - `<N>`: User story number (1, 2, 3...)
   - `<priority>`: Map P1→1, P2→2, P3→3, etc.
   - `--parent $IMPLEMENT_TASK_ID`: Link to the **implement phase task** (NOT the epic)

   b. For each implementation step within the user story, create a sub-task with description:

   ```bash
   br create "<step-description>" -p <priority> --parent <user-story-task-id> \
     --description "**Spec**: specs/$BRANCH/spec.md §US-<N>, plan.md §<section>
   **Skills**: <skill-list-from-mapping>
   **Files**: <target-file-paths>
   **Acceptance**: <specific-criteria>" --json
   ```

   - `<user-story-task-id>`: The user story task ID from step (a)
   - `<skill-list-from-mapping>`: Skills from the mapping table above
   - `<target-file-paths>`: Specific files to create/modify (e.g., `src/hermes_attractor/use_cases/foo.py`, `tests/unit/use_cases/test_foo.py`)
   - `<specific-criteria>`: Measurable acceptance criteria

   c. Establish dependencies between sequential tasks:

   ```bash
   br dep add <dependent-task-id> <blocking-task-id>
   ```

   - Add dependencies where one task must complete before another
   - Tasks marked [P] should NOT have dependencies between them (parallel execution)

   d. For parallel tasks (marked [P] in task plan):
   - Create without dependencies between them
   - They will all appear in `br ready` once their common parent is ready

6. **Generate Acceptance Spec Files** (ATDD outer loop setup):

   For each user story in spec.md that has **Acceptance Scenarios**, extract the GWT scenarios and write them as structured `.txt` files in `specs/acceptance-specs/`. This sets up the outer ATDD loop so ralph can run the inner TDD cycle during `sp:07-implement`.

   a. Determine the next available US number by scanning existing files:

   ```bash
   ls specs/acceptance-specs/US*.txt 2>/dev/null | sed 's/.*US0*//' | sed 's/-.*//' | sort -n | tail -1
   ```

   Start numbering from the next available number (e.g., if US15 exists, start at US16).

   b. For each user story, create a `.txt` file in `specs/acceptance-specs/` using this format:

   ```text
   ;=============================================
   ; <scenario title in sentence case>.
   ;=============================================
   GIVEN <precondition>.
   WHEN <action>.
   THEN <expected outcome>.
   THEN <additional assertion if needed>.
   ```

   - File naming: `US<NN>-<kebab-case-slug>.txt` (e.g., `US16-register-plugin.txt`)
   - Each scenario gets its own `;=====` header block
   - Each GIVEN/WHEN/THEN line ends with a period
   - Keep scenarios behavioral (what the user does/sees), not implementation-specific
   - Extract scenarios directly from the spec's **Acceptance Scenarios** sections

   c. Run the acceptance pipeline to generate test stubs:

   ```bash
   just acceptance 2>&1 || true
   ```

   If `just acceptance` is not available, run the equivalent parse + generate
   steps for the project's acceptance harness (e.g. the project's acceptance
   spec parser that emits pytest stubs under `tests/acceptance/`). Skip this
   sub-step if the project has no acceptance pipeline yet — the `.txt` specs
   are still the durable artifact.

   d. Verify generated stubs exist and are in the RED state (the generated
   pytest test bodies should fail or be marked "acceptance test not yet bound").

   e. Record acceptance spec file paths in the report for reference.

   **Important**: The acceptance spec files must exist BEFORE ralph processes `US<N>` tasks, because ralph's ATDD cycle (via the `pytest-acceptance-tests` skill) requires them. If spec.md has no acceptance scenarios for a user story, skip that story (no spec file needed).

7. **Verify Task Hierarchy**:

   ```bash
   br dep tree <epic-id> --direction up
   ```

   - Note: `--direction up` shows dependents/children (default `down` shows blockers, which is empty for an epic)
   - Verify the hierarchy: Epic → User Story Tasks → Implementation Sub-tasks
   - Check for any circular dependencies: `br dep cycles`

8. **Close Phase Task in Beads**:

   After creating all implementation tasks, close the 05-tasks phase task to unblock the implement phase.

   a. Find the tasks phase task:

   ```bash
   br show <epic-id> --json | jq -r '.[0].dependents[] | select(.title | contains("[sp:05-tasks]") and .status == "open") | .id'
   ```

   b. Close the task with a completion summary:

   ```bash
   br close <tasks-task-id> --reason "Created <N> tasks across <M> user stories under [sp:07-implement]"
   ```

   c. The [sp:06-analyze] phase task is now ready (its dependency on 05-tasks is satisfied).

   d. Report: "Phase [sp:05-tasks] complete. Run `/sp:next` or `/sp:06-analyze` to validate artifacts."

9. **Report**: Output summary including:
   - **Beads epic ID** and total tasks created in beads
   - **Implement task ID** (`$IMPLEMENT_TASK_ID`) containing all user story tasks
   - Task count per user story (with task IDs)
   - **Acceptance spec files** created in `specs/acceptance-specs/` (with file paths)
   - **Generated test stubs** (RED state confirmed) if an acceptance pipeline ran
   - Parallel opportunities identified
   - Independent test criteria for each story
   - Suggested MVP scope (typically just User Story 1)
   - **Next step**: Run `/sp:next` or `/sp:06-analyze` to validate cross-artifact consistency
   - **How to view ready tasks**: `br ready --json`

The tasks should be immediately executable via beads - each task must be specific enough that an LLM can complete it without additional context.

## Task Generation Rules

**CRITICAL**: Tasks MUST be organized by user story to enable independent implementation and testing.

**CRITICAL**: Task descriptions are the ONLY context ralph passes to the worker subagent. They must be fully self-contained — a fresh worker session must be able to implement the task without exploring the codebase from scratch.

### Task Type Classification

Classify each piece of work per `/beads-task-chains` taxonomy (Types A-E) and apply the corresponding chain pattern. Quick reference:

- **Type A: Testable code** — full ATDD + TDD chain (acceptance → red → green → refactor → ... → verify)
- **Type B: Static pages** — build + visual verify (rare for a backend plugin; only if UI present)
- **Type C: Design & style** — build + visual verify (only if UI present)
- **Type D: Documentation** — write + lint (`uv run ruff check`)
- **Type E: Configuration** — change + validate

See `/beads-task-chains` for full chain construction patterns and `references/description-templates.md` for parameterized task description templates.

### Behavior Decomposition (for Type A tasks)

Read plan.md + spec.md at task generation time to identify behaviors:

- Each domain entity/model = 1 behavior
- Each use case / application service = 1 behavior
- Each port + its adapter implementation = 1 behavior
- Each cross-cutting concern = 1 behavior

### Dependency Chain Construction

Construct chains per `/beads-task-chains` patterns. For Type A (testable code), use the full ATDD/TDD chain. For Types B-E, use the corresponding lightweight pattern.

### Task Description Templates

Use templates from `/beads-task-chains` — see `references/description-templates.md` for all parameterized templates (WRITE_ACCEPTANCE_TEST, RED, GREEN, REFACTOR, VERIFY_ACCEPTANCE, STATIC_PAGE, DESIGN_STYLE, DOCUMENTATION, CONFIGURATION).

### Beads Task Format

Use the naming convention from `/beads-task-chains` (US tasks, ATDD sub-tasks, TDD sub-tasks).

### Priority Mapping

| Spec Priority | Beads Priority | Description             |
| ------------- | -------------- | ----------------------- |
| Epic          | 0              | Feature-level (highest) |
| P1            | 1              | Critical user story     |
| P2            | 2              | High priority           |
| P3            | 3              | Medium priority         |
| P4+           | 4+             | Lower priority          |

### Dependency Rules

1. **Sequential tasks**: Use `br dep add <child> <parent>` to create blocking relationships
2. **Parallel tasks**: Do NOT add dependencies between them - they'll appear together in `br ready`
3. **Cross-story dependencies**: Minimize these; each story should be independently completable
4. **Setup/Foundational**: These block all user story tasks
5. **ATDD/TDD chains**: Each step blocks the next in sequence (acceptance → red → green → refactor → ... → verify)

### Task Organization

1. **From User Stories (spec.md)** - PRIMARY ORGANIZATION:
   - Each user story (P1, P2, P3...) becomes a beads task under the implement phase task
   - Classify each story's work by task type (A through E)
   - For Type A: Generate full ATDD/TDD dependency chain
   - For Types B-E: Generate appropriate task chain per type
   - Map all related components to their story:
     - Domain models needed for that story
     - Use cases / application services needed for that story
     - Ports and adapters needed for that story (from contracts/)
     - Plugin registration surface needed for that story (from plan.md)
   - Mark story dependencies (most stories should be independent)

2. **From Contracts**:
   - Map each port/interface contract → to the user story it serves
   - Each contract becomes a behavior in the Type A ATDD/TDD chain

3. **From Data Model**:
   - Map each entity to the user story(ies) that need it
   - If entity serves multiple stories: Put in earliest story or Setup phase
   - Each entity becomes a behavior in the Type A ATDD/TDD chain

4. **From Setup/Infrastructure**:
   - Shared infrastructure → Setup phase tasks (Type E)
   - Foundational/blocking tasks → Foundational phase tasks
   - Story-specific setup → within that story's sub-tasks

5. **From Plan (Presentation/UI)** — only if the feature ships user-facing UI:
   - Scan plan.md for any presentation layer requirements
   - Map each UI component/interaction to its user story
   - Classify as Type B (static page) or Type C (design/style)
   - If plan.md includes a `## Presentation Design` section, use the **UI Decisions** table to match components to stories
   - If plan.md includes a `### Quality Pass` section, generate a Design Review task in the Final Phase
   - For a backend-only plugin, this category is typically empty.

### Phase Structure

- **Phase 1**: Setup (project initialization) - Type E tasks directly under implement task
- **Phase 2**: Foundational (blocking prerequisites) - Type E tasks directly under implement task
- **Phase 3+**: User Stories in priority order (P1, P2, P3...)
  - Each user story is a task under the implement task
  - Type A stories get full ATDD/TDD chain as sub-tasks
  - Type B/C/D/E stories get appropriate task chains
  - Each phase should be a complete, independently testable increment
- **Final Phase**: Polish & Cross-Cutting Concerns
  - Design Review task if plan.md has Quality Pass section
  - This task depends on ALL user story presentation sub-tasks completing first

## Beads Error Handling

If beads commands fail during task creation:

1. **Epic not found**: Create a new epic for the feature
2. **Task creation fails**: Log error, continue with remaining tasks, report failures at end
3. **Dependency cycle detected**: Remove the problematic dependency, log warning
4. **DB cache corruption** (`UNIQUE constraint failed: blocked_issues_cache.issue_id`): Run `br doctor` to auto-repair by rebuilding caches from JSONL. Common when creating many tasks/deps rapidly.
5. **br command not found**: Suggest installing br via curl

If beads commands fail completely, report failures and suggest troubleshooting steps.

## Commit Changes

Run the `/commit` skill to stage and commit all changes made during this phase. Do not push.

---

Use subagents liberally and aggressively to conserve the main context window.
