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
