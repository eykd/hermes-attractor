# Implementation Plan: Attractor on Hermes Kanban (Plugin)

**Branch**: `001-attractor-kanban` | **Spec**: [spec.md](./spec.md) |
**Date**: 2026-05-28

## Technical Context

- **Language/Version**: Python 3.11 (pinned; `requires-python = ">=3.11,<3.12"`).
- **Primary Dependencies**:
  - `pydot` — adapter-only DOT (de)serialization (research R-DOT); never imported by the
    domain.
  - Standard library `sqlite3` — plugin-owned durable run state (research D6); no ORM.
  - Standard library `subprocess`/`git` invocation behind the `PipelineStore` adapter for
    git-tracked `.dot` files (FR-003).
  - Hermes runtime (host) — provides the Kanban board, dispatcher, profile workers, the
    `post_tool_call` hook surface, the CLI command surface, and the durable `task_events`
    log. Coupling is confined to `plugin/` + the kanban/event-log adapters.
  - No Temporal, no second orchestrator (FR-015; research D1).
  - No mandatory system Graphviz binary — the FR-005 summary is pure Python (research
    R-RENDER); image rendering is optional/runtime-detected.
- **Storage**:
  - Pipelines: git-tracked `.dot` files, local-only repo fallback (FR-003).
  - Run state: plugin-owned SQLite DB, separate from the kanban DB — `plugin_runs` /
    `plugin_run_nodes` (research D6). Durability of *work* (retries/recovery) stays on the
    kanban board (FR-015).
- **Testing**: `pytest`, branch coverage at **100%** (enforced pre-commit + CI). Ports are
  coverage-omitted. ATDD outer loop per the Acceptance Test Strategy below.
- **Constraints** (CLAUDE.md / constitution): hexagonal layering (deps point inward);
  `ruff` (120-char, py311) clean; `pyright` strict + paranoid; Google docstrings; no
  `print` in library code; domain exceptions from `domain/exceptions.py`; `plugin/tools.py`
  handlers always return JSON and never raise.

### Decisions encoded from grounded research (do not re-litigate)

- **D1** Kanban board is the sole durable substrate; the plugin is a deterministic
  traversal engine / reducer over completion events.
- **D2** Advancement = `post_tool_call` hook (primary, in-worker) + `reconcile` CLI
  (recovery, replays `task_events WHERE id > last_seen_event_id`). No daemon, no kanban
  completion hook.
- **D3** Per-node model = per-node Hermes profile (profile `config.yaml` `model.default`).
  Do not depend on per-task `model_override`.
- **D4** Goal-gate loops via acyclic dynamic iteration cards (each attempt a new DAG
  segment); never create cyclic kanban links.
- **D5** Idempotency key `attractor:<run_id>:<node_id>:attempt:<n>`.
- **D6** Plugin-owned SQLite state (`plugin_runs` / `plugin_run_nodes`) with a durable
  `last_seen_event_id` cursor.
- **R-EP** Entry-point group is `hermes_agent.plugins` (reconcile from the repo's current
  `hermes.plugins`).

## Constitution Check

The constitution is an unratified template seeded from CLAUDE.md; the plan honors each
seeded principle:

- **I. Hexagonal Architecture** — PASS. Domain (Pipeline/Node/Edge/Context/Outcome/Run) has
  zero external deps; `pydot`, `sqlite3`, git, and all kanban/Hermes calls live in adapters
  behind ports; only `plugin/` imports Hermes. See Architecture below. Validated via
  `/architecture-review` before merge.
- **II. Test-First, 100% Coverage** — PASS (planned). ATDD outer loop + TDD inner loop;
  100% branch coverage retained. Acceptance Test Strategy lists the outer-loop specs.
- **III. Strict Typing & Linting** — PASS (planned). All new code fully typed; `pyright`
  strict; suppressions narrow + justified (`# pyright: ignore[...]`).
- **IV. Safe Plugin Contract** — PASS. All ~13 tool handlers + the hook handler return JSON
  / never raise (FR-023); kept thin, delegating to use cases.

No deviations. (Principle V is an unfilled placeholder; nothing to satisfy.)

## Brainstorm Context

**Source**: [specs/brainstorms/2026-05-28-attractor-hermes-temporal-requirements.md](../brainstorms/2026-05-28-attractor-hermes-temporal-requirements.md)

### Key Decisions Carried Forward

- DOT is canonical, authored via structured tools (not hand-written) — encoded in the
  authoring tool contract and the `DotSerializer` port.
- Git-tracked `.dot` files with a local-only repo fallback — `PipelineStore` port (FR-003).
- Full Attractor feature set for v1, built as a thin vertical slice first then widened —
  reflected in the Phases below.
- Deterministic edge-selection priority (condition -> label -> suggested -> weight ->
  lexical) — `EdgeSelector` domain service (FR-007).

### Deferred Questions (resolved during planning)

- *Can a node spawn an agent session inside an activity?* -> Obsolete: nodes execute via
  kanban cards assigned to profiles (D1/D3); no in-process sessions, no Temporal.
- *Entry-point group reconciliation* -> `hermes_agent.plugins` (research R-EP).
- *Parallel fan-in merge rule* -> deterministic disjoint-union + branch-order conflict
  resolution recorded under `_merge_conflicts` (research R-MERGE).
- *Human-in-the-loop surface* -> create+block a card; human unblocks/completes; same
  advancement path (research R-HITL).
- *Reference workflow* -> the self-hosting `sp` workflow as an Attractor graph (SC-006).

## Architecture

Hexagonal. Dependencies point inward; only `plugin/` and the kanban/event-log adapters know
Hermes.

```
plugin/  ── register(ctx): tools + post_tool_call hook + reconcile CLI ──┐
   │ (Hermes-coupled shim; thin handlers, never raise)                   │
   ▼                                                                      ▼
use_cases/                                                          ports/ (Protocols)
   authoring (create/add/remove/set/validate/summary)        KanbanBoard, EventLog,
   run (launch, advance_on_completion, reconcile, status)    PipelineStore, DotSerializer,
   │            │                                            RunStateStore, Renderer,
   ▼            ▼                                            ToolNodeRegistry, Clock,
domain/ (pure)         ──────────────────────────────────►  PluginContext
   Pipeline (aggregate), Node, Edge, EdgeSelector,                  ▲
   Context, Outcome, Stylesheet, GoalGatePolicy,           adapters/ (implement ports)
   Run, RunNode, IdempotencyKey, exceptions                pydot serializer, git store,
                                                            sqlite run store, kanban client,
                                                            kanban event-log reader,
                                                            pure-python renderer
```

- **domain** — pure traversal + validation + run state machine. The `EdgeSelector` and the
  `Run`/`RunNode` transitions are the deterministic, replay-safe core (FR-007/FR-024).
- **use_cases** — orchestrate domain over ports. The `advance_on_completion` and
  `reconcile` use cases share one **advance** core so the hook path and the recovery path
  produce identical effects (the reducer property, D2).
- **adapters** — confine `pydot`, `sqlite3`, git, and every kanban tool/REST/event call.
  Research risk R2 (field-name drift) lives entirely in the kanban + event-log adapters.
- **plugin** — registers tools, the `post_tool_call` hook, and the `reconcile` CLI command;
  wires concrete adapters; honors the never-raise contract.

## Data Model

See [data-model.md](./data-model.md). Summary: `Pipeline` (aggregate) of `Node` + `Edge`
with a `Stylesheet`; `EdgeSelector` domain service; `Context`/`Outcome` value objects; the
durable `Run`/`RunNode` records mapping to `plugin_runs` / `plugin_run_nodes`;
`IdempotencyKey` as the single source of the `attractor:<run_id>:<node_id>:attempt:<n>`
scheme; `Card`/`CardResult` DTOs crossing the kanban port. Exception hierarchy extends
`AttractorError`.

## Contracts

See [contracts/](./contracts/): `ports.md` (the 8 port Protocols), `tools.md` (the
authoring + execution tool surface, the `post_tool_call` hook, and the `reconcile` CLI),
and `card-result.schema.json` (the structured card/gate verdict the engine parses into an
`Outcome`).

## Phases / Milestones

Thin vertical slice first, then widen (brainstorm key decision). Each milestone is RED ->
GREEN -> REFACTOR with 100% coverage maintained.

1. **M0 — Foundation & reconciliation.** Reconcile the entry-point group to
   `hermes_agent.plugins` (pyproject, `plugin.yaml`, CLAUDE.md note); extend `PluginContext`
   with hook + command registration; add domain exceptions; add `pydot` dependency.
2. **M1 — Authoring core (pure).** Domain `Pipeline`/`Node`/`Edge`/`Stylesheet`/
   `EdgeSelector`; `Pipeline.validate()` (FR-004/SC-007); `DotSerializer` port + `pydot`
   adapter (FR-001/FR-002); `PipelineStore` port + git adapter with local-only fallback
   (FR-003); `Renderer` summary (FR-005). Authoring tools (FR-001).
3. **M2 — Linear run slice.** `Run`/`RunNode` state machine + `IdempotencyKey`;
   `RunStateStore` port + SQLite adapter (D6); `KanbanBoard` port + adapter; the shared
   **advance** use case; `attractor_run`/`status`/`result` for a linear codergen graph with
   per-node profile resolution (FR-014/FR-018/FR-019/FR-021/FR-022). `post_tool_call` hook.
4. **M3 — Durability & recovery.** `EventLog` port + adapter; `reconcile` CLI + use case;
   `last_seen_event_id` cursor; replay idempotency (FR-024/SC-003); wire reconcile from
   `on_session_start`.
5. **M4 — Widen semantics.** Conditional routing (FR-011), tool nodes (FR-012),
   goal-gated acyclic loops (FR-009/D4), retry-limit exhaustion -> block (FR-016).
6. **M5 — Concurrency & human-in-the-loop.** Fan-out/fan-in with deterministic
   clone/merge (FR-010/R-MERGE/SC-005); human-in-the-loop create+block/resume
   (FR-013/FR-017/R-HITL/SC-004).
7. **M6 — Self-hosting reference pipeline.** Author the `sp` workflow as an Attractor graph
   and run it end-to-end (SC-006) — exercises every v1 capability.

## Acceptance Test Strategy (ATDD outer loop)

Each user story with acceptance scenarios in the spec maps to one acceptance spec file.
`sp:05-tasks` creates the files; this section documents the outer loop. Acceptance specs go
under `specs/acceptance-specs/`.

| User story (spec scenario) | Acceptance spec file | Scenarios |
|----------------------------|----------------------|-----------|
| Author + validate + version a branched, goal-gated pipeline (Scenario 1; SC-001) | `specs/acceptance-specs/US01-author-validate-version.txt` | 1 (+ invalid-graph edge cases) |
| Per-node profile resolution, override beats stylesheet (Scenario 2; SC-002) | `specs/acceptance-specs/US02-profile-resolution.txt` | 1 |
| Crash recovery: restart mid-run, no re-execution (Scenario 3; SC-003) | `specs/acceptance-specs/US03-crash-recovery.txt` | 1 |
| Human-in-the-loop pause/resume across restart (Scenario 4; SC-004) | `specs/acceptance-specs/US04-human-in-the-loop.txt` | 1 |
| Parallel fan-out/fan-in concurrency + merge (Scenario 5; SC-005) | `specs/acceptance-specs/US05-parallel-fanout-fanin.txt` | 1 |
| Goal-gate routes back until satisfied (Scenario 6) | `specs/acceptance-specs/US06-goal-gate-loop.txt` | 1 |
| Tool node runs deterministic work into context (Scenario 7) | `specs/acceptance-specs/US07-tool-node.txt` | 1 |
| Self-hosting `sp` reference pipeline end-to-end (Scenario 8; SC-006) | `specs/acceptance-specs/US08-self-hosting-sp.txt` | 1 |
| Invalid pipeline rejected naming the offending element (SC-007; Edge Cases) | `specs/acceptance-specs/US09-validation-rejection.txt` | 1 (multiple invalid forms) |

## Applied Skills (planning lenses)

- **/prefactoring** — named all types per the glossary up front; isolated the idempotency
  scheme behind `IdempotencyKey`; made `EdgeSelector` a pure total function; split
  advancement into one shared **advance** core reused by both the hook and the reconciler.
- **/ddd-domain-modeling** — `Pipeline` aggregate root with validation invariants; value
  objects (`Context`, `Outcome`, `Stylesheet`, `GoalGatePolicy`, `IdempotencyKey`); ports as
  the repository/gateway boundary; zero external deps in the domain.
- **/glossary** — entity/type names match `docs/glossary.md` (Pipeline, Node, Edge, Context,
  Outcome, Profile, Card, Goal Gate, Stylesheet, Run, Fan-out/Fan-in, Human-in-the-loop);
  avoided the listed synonyms.
- **/latent-features** — surfaced implied requirements now planned explicitly: deterministic
  fan-in conflict recording (`_merge_conflicts`), the durable replay cursor as the *last*
  write of an advancement, the hook-vs-`protocol_violation` ordering guard (R4), and a
  manual reconcile command as the always-available recovery lever.
- **/error-handling-patterns** — `validate()` returns structured issues (non-raising) for
  authoring while a `PipelineValidationError` exists for hard-failure boundaries; adapter
  failures translate to safe JSON payloads; the plugin never raises (FR-023).

## Security Considerations

Added by red-team Pass 1. The plugin's trust boundaries are: (a) DOT pipeline definitions
(git-tracked, may originate from any repo the agent can reach — treat as untrusted input),
(b) the run `Context` (seeded by the caller and grown from worker-written card results), and
(c) the kanban port (card bodies and parsed card results). These mitigations are
load-bearing and MUST be designed into the relevant ports/use cases, not bolted on.

### Guard / condition evaluation (FR-011) — no arbitrary code execution

- Edge `condition` and conditional-node guards are strings sourced from DOT (untrusted) and
  evaluated against the `Context` (worker-influenced). They MUST NOT be evaluated with
  `eval`/`exec`/`compile` or any Python execution path.
- Define a **restricted, total guard mini-language** evaluated by a pure domain evaluator:
  comparison + boolean ops over context keys and literals only (no attribute access, no
  calls, no indexing into arbitrary objects, no imports). Unknown/undefined keys evaluate to
  a defined falsy result, never an exception that escapes the domain.
- The guard evaluator is a pure, total domain function (replay-safe like `EdgeSelector`); an
  unparseable guard is a **validation error** (FR-004), not a runtime surprise.

### Prompt / `$var` expansion (FR-022) — template, not interpolation

- Context values expanded into card bodies (which become downstream agent prompts) are an
  injection surface (a malicious or compromised upstream node can write context that steers
  a downstream worker). Expansion MUST be a literal, non-recursive substitution of known
  `$var` placeholders only — never a templating engine that evaluates expressions, and never
  re-expanded on the substituted result.
- Undefined placeholders are surfaced as a structured authoring/validation issue or
  rendered as an explicit empty/marker token; they never leak the raw context object or
  adjacent keys.

### Path / repo handling (FR-003) — `spec_id` and `repo_path` are untrusted

- `spec_id` resolves to a `.dot` path under the repo and `repo_path` selects the git repo;
  both arrive from tool input. The `PipelineStore` adapter MUST confine all reads/writes to
  the configured repo root: reject `spec_id`/path components containing `..`, absolute
  paths, or path separators that escape the root; normalize then verify the resolved real
  path is inside the root. No symlink-following out of the root.
- `ensure_repo`/`save` MUST NOT initialize a git repo or write `.dot` files outside the
  intended root, and MUST NOT operate on a caller-named arbitrary system directory.

### Subprocess / git invocation — no shell, argument arrays only

- All git invocations (init, add, commit) behind `PipelineStore` MUST use argument-vector
  `subprocess` (`shell=False`), never string interpolation into a shell. `spec_id`, file
  names, and any commit message MUST be passed as discrete args, never concatenated into a
  command line, to preclude command/option injection (including leading-dash option
  injection — use `--` separators before user-influenced positionals).

### Idempotency-key integrity — constrained `node_id` / `run_id`

- The key `attractor:<run_id>:<node_id>:attempt:<n>` is delimiter-based; a `node_id` (from
  untrusted DOT) or `run_id` containing `:` could forge a collision with another node's key,
  causing card-creation dedup to skip or merge unrelated work. Validation MUST restrict
  `node_id` to a safe charset (e.g. `[A-Za-z0-9_-]`) that excludes the `:` delimiter, and
  `run_id` MUST be plugin-generated (not caller-supplied) from a safe alphabet. The
  `IdempotencyKey` factory is the single place that enforces this invariant.

### Gate-verdict trust (FR-009) — worker output is not authoritative truth

- The goal-gate verdict (`gate: pass|fail`, plus the `additionalProperties: true` card
  result) is written by the worker performing the gated node and is therefore attacker- or
  error-influenced. The engine MUST treat a missing/malformed `gate` field on a GATE card as
  **fail** (route to retry target), never default-pass, so a silent or garbled result cannot
  bypass an exit gate. Only the whitelisted, schema-validated fields are consumed from the
  card result; unknown properties are ignored, not merged into routing/state.

### Tool-node allowlisting (FR-012)

- `ToolNodeRegistry.run(tool_name, context)` resolves `tool_name` from DOT (untrusted). The
  registry MUST resolve only an explicit allowlist of registered deterministic tools;
  an unknown `tool_name` is a **validation error** at authoring time (FR-004) and a safe
  refusal at runtime — never a dynamic import or arbitrary callable lookup.

### Resource limits

- DOT parsing (`DotSerializer.parse`) on untrusted input MUST enforce input-size and
  node/edge-count caps and reject pathological graphs before constructing a `Pipeline`,
  preventing memory/CPU exhaustion at the authoring entry point.

## Edge Cases & Error Handling

Added by red-team Pass 1.

### Concurrent advancement — the hook and the reconciler can race

- A run can be advanced from two places at once: the in-worker `post_tool_call` hook (R4)
  and the `reconcile` path (on_session_start; and potentially more than one session). Card
  *creation* is idempotent via the key, but the **plugin SQLite RunStateStore mutation**
  (advancing `RunNode.attempt`, run status, and especially the `last_seen_event_id` cursor)
  is not inherently concurrency-safe. Two advancers processing the same completion event can
  double-advance the state machine or clobber the cursor (lost update).
- Mitigation: serialize advancement **per run**. Use a per-run guard — a SQLite
  transaction with the cursor compare-and-set (only advance the cursor from the value the
  advancer read; on mismatch, re-read and re-evaluate) so concurrent advancers converge
  rather than corrupt. The advance core MUST be safe to run twice on the same event with no
  net effect beyond the first (true reducer idempotency on *state*, not only on cards).

### SQLite under multi-process access

- The plugin-owned DB is written by many worker processes (each fires the hook) plus the
  reconcile session. Default SQLite locking yields `database is locked` errors under
  contention. The SQLite adapter MUST enable WAL mode and a `busy_timeout`, wrap each
  advancement in a single transaction, and surface lock contention as a retryable safe
  failure (handed to the reconciler) rather than a raised exception crossing the plugin
  boundary.

### Partial failure between card creation and state persistence

- If a follow-up card is created but the process dies before the `RunNode`/cursor write, the
  attempt counter must be **re-derivable deterministically from the event log on replay**,
  not read from a pre-incremented persisted counter that was lost. Pin the `attempt` value
  as a deterministic function of the (run, node, observed prior attempts) so replay rebuilds
  the identical idempotency key and the dedup makes re-creation a no-op. Document this as the
  invariant the `save_run`-last ordering depends on.

### Goal-gate exhaustion and unbounded loops

- `max_attempts >= 1` bounds gate retries; on exhaustion the run transitions to `BLOCKED`
  (data-model). Confirm there is no path where an unsatisfied gate with a still-reachable
  retry target loops without incrementing the attempt counter (e.g. a gate whose retry
  target re-enters the gate via a different edge). The attempt counter MUST advance on every
  gate failure so exhaustion is guaranteed.

### Dependency failure — kanban / event-log unavailable

- If `KanbanBoard.create_card` or `EventLog.read_since` fails (gateway down, REST error),
  the hook/reconciler MUST leave the run in a re-processable state (cursor un-advanced,
  status unchanged) and return a safe payload; the next reconcile retries. No advancement may
  be recorded as durable until its follow-up cards are confirmed created.

## Performance Considerations

Added by red-team Pass 1.

### Bounded fan-out

- Parallel fan-out (FR-010) creates N sibling cards from a single node; N is currently
  unbounded and, for a pipeline authored from untrusted DOT, is a board-exhaustion vector.
  Enforce a configurable maximum fan-out width at validation (FR-004) and at runtime; exceed
  -> validation error / blocked run with a reported reason rather than flooding the board.

### Bounded event-log replay

- `EventLog.read_since(last_seen_event_id)` after a long outage can return a large slice of
  `task_events`. Read in bounded batches, advancing and persisting the cursor per batch, so a
  far-behind reconcile makes monotonic progress without loading the whole log into memory.

### Run-state query shape

- `RunStateStore` lookups on the hot advance path (`get_node_by_task`, `nodes_for_run`,
  `active_runs`) MUST be indexed (task_id, run_id) so per-completion advancement is not a
  full-table scan as run/node counts grow.

## Accessibility Requirements

Not applicable. This is a backend Hermes plugin with no user-facing UI surface; the only
human-facing output is structured JSON tool results and a text pipeline summary. No
keyboard/screen-reader/visual concerns apply. (Recorded explicitly rather than inventing
barriers.)

## Risks & Open Questions

Carried from the spec Assumptions and research residual risks (also tracked in
[research.md](./research.md)):

- **R1** — Entry-point group string on the *installed* Hermes may differ from
  `hermes_agent.plugins`. Mitigation: single config change isolated to `plugin.yaml` +
  `pyproject.toml`.
- **R2** — Kanban create/REST/block field names and the `create_task` signature drift by
  version (e.g. `gave_up` rename). Mitigation: confine all kanban calls to the `KanbanBoard`
  + `EventLog` adapters; integration-test against the installed version.
- **R3** — Reconcile trigger choice (`register_auxiliary_task` vs profile cron vs session
  hooks). Mitigation: default `on_session_start`; the CLI is always a manual fallback.
- **R4** — The `post_tool_call` hook must create follow-up cards **before** the worker exits,
  ahead of the `running`->exit `protocol_violation` guard. Mitigation: create follow-up
  cards synchronously inside the hook before returning; the reconciler is the safety net if
  the hook is cut short. **Load-bearing — confirm ordering at implementation.**
- The Hermes gateway (+ kanban dispatcher) must be running for `ready` cards to progress
  (assumption, not a plugin concern).
- Exact Attractor DOT attribute names / status enums to be re-confirmed against the
  Attractor NLSpec — isolated in the `DotSerializer` adapter.
