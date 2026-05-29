# Phase 0 Research: Attractor on Hermes Kanban

**Branch**: `001-attractor-kanban` | **Spec**: [spec.md](./spec.md) |
**Date**: 2026-05-28

This note consolidates Phase 0 research decisions for the implementation plan. The
**Hermes-substrate** decisions were already verified against `NousResearch/hermes-agent`
source — see [research-hermes-kanban.md](./research-hermes-kanban.md) for evidence — and
are recorded here as **resolved** with their rationale and rejected alternatives. The
remaining entries resolve the spec's *Deferred-to-Planning* questions.

## Carried-forward decisions (verified; do not re-litigate)

### D1. No second durable orchestrator (Temporal dropped)

- **Decision**: The Hermes Kanban board is the sole durable execution substrate. The
  plugin is a **deterministic traversal engine** — a reducer over kanban completion
  events — and owns only its own bookkeeping.
- **Rationale**: The board already supplies durability, automatic retries, parent/child
  dependency sequencing, crash recovery, and human-in-the-loop. A second orchestrator
  duplicates all of it and forces a two-system consistency problem. (FR-015.)
- **Alternatives rejected**: Temporal Workflows/Activities (brainstorm R14-R17) — dropped
  because the board is mandatory anyway and makes Temporal pure redundancy; an in-plugin
  custom checkpoint store — forbidden by FR-015.

### D2. Run advancement = `post_tool_call` hook (primary) + `reconcile` CLI (recovery)

- **Decision**: Advance a run by reacting to kanban task completion. **Primary path**: a
  `post_tool_call` hook fires inside the just-finished worker after `kanban_complete` /
  `kanban_block`, evaluates edge selection / goal gate, and creates the next card(s)
  inline. **Recovery path**: a registered CLI command replays
  `task_events WHERE id > last_seen_event_id` and advances any run that missed its event
  (worker crashed before the hook ran). No daemon, no first-class kanban completion hook.
- **Rationale**: `VALID_HOOKS` has no kanban-completion hook and there is no plugin API to
  register a background loop/timer (research #2, #6). Workers run with `--accept-hooks` and
  load plugins, so `post_tool_call` is the only in-process completion signal. The durable
  `task_events` log (research #1) makes a replay-based reconciler exact and idempotent.
- **Alternatives rejected**: in-gateway watcher daemon (no registration API); polling the
  board on a user-driven cadence (not durable, races restarts).

### D3. Per-node model = per-node Hermes profile

- **Decision**: A node names a **profile**; the profile's `config.yaml` `model.default`
  determines the model. Operators define model-specific profiles (`planner-sonnet`,
  `coder-gpt5`, `reviewer-opus`). (FR-019/FR-020.)
- **Rationale**: The public create surface (tool / `POST /tasks` / CLI) exposes no model
  param (research #3). The dispatcher spawns the worker as the assignee profile (research
  #5), so the profile is the only model lever on the supported surface.
- **Alternatives rejected**: per-task `model_override` — exists internally but is not on
  the public create surface; depending on it would couple v1 to an unsupported field
  (roadmap item only).

### D4. Goal-gate loops via acyclic dynamic iteration cards

- **Decision**: Never create cyclic kanban links. Each gate retry is a **new acyclic DAG
  segment** with fresh task ids: `implement(att n) -> gate(att n) --fail--> implement(att
  n+1) -> gate(att n+1)`. The plugin owns loop state; idempotency keys keep it replay-safe.
  (FR-009/FR-024.)
- **Rationale**: The board enforces parent/child DAG dependencies; a cycle is ill-formed.
  Materializing each attempt as a new segment keeps the board acyclic while the plugin's
  own `plugin_run_nodes` table records the logical loop.
- **Alternatives rejected**: cyclic kanban links (ill-formed / unsupported); re-opening a
  completed card (loses the audit trail and breaks idempotency).

### D5. Idempotency-key scheme

- **Decision**: `attractor:<run_id>:<node_id>:attempt:<n>` for node cards and
  `attractor:<run_id>:<gate_id>:attempt:<n>` for gate cards. Passed to `kanban_create`.
- **Rationale**: `idempotency_key` on create dedupes against existing non-archived tasks
  (research #4). Deterministic keys make both advancement paths (D2) safe to run
  repeatedly — replay never duplicates a card. (FR-024.)

### D6. Plugin-owned durable SQLite state (separate from kanban)

- **Decision**: The plugin opens its **own** SQLite DB, distinct from the kanban DB:
  - `plugin_runs(run_id, spec_id, state, root_task_id, last_seen_event_id, created_at,
    updated_at)`
  - `plugin_run_nodes(run_id, node_id, task_id, status, attempt, parent_node_ids,
    goal_gate_policy, output_ref)`
- **Rationale**: The plugin needs a durable cursor (`last_seen_event_id`) and a
  node->card mapping to advance idempotently after a restart (FR-014/FR-024). This is
  *traversal bookkeeping*, not a parallel orchestrator, so it does not violate FR-015 (the
  board still owns work durability/retries/recovery). The two-DB split keeps the plugin
  from mutating kanban internals.
- **Alternatives rejected**: storing traversal state inside kanban task payloads (couples
  to kanban schema, no transactional cursor); in-memory state (lost on restart — fatal for
  FR-017).

## Resolved Deferred-to-Planning questions

### R-EP. Entry-point group reconciliation

- **Decision**: Target the `hermes_agent.plugins` entry-point group. Update
  `pyproject.toml`, `plugin.yaml`, and CLAUDE.md's note; keep the `.hermes/plugins`
  symlink for local dev discovery.
- **Rationale**: Research found the real group is `hermes_agent.plugins`; the repo's
  current `hermes.plugins` is a pre-verification assumption.
- **Residual risk (R1)**: the installed Hermes version's group string is the source of
  truth — confirm at implementation; if it differs, this is a one-line change.

### R-MERGE. Parallel fan-in context merge rule

- **Decision**: Branches each receive a **deep clone** of the context at fan-out. At
  fan-in, branch updates are merged into the parent context with a **deterministic,
  documented rule**:
  1. Disjoint keys union freely.
  2. Conflicting keys (same key written by >1 branch with differing values) are resolved
     by **branch order** (the lexical order of the fan-out edge selection), last-writer
     wins, **and** the conflict is recorded under a reserved `context["_merge_conflicts"]`
     list so resolution is never silent (Edge Case: conflicting updates).
  3. List-valued keys with the same key are **concatenated in branch order** (an explicit
     accumulation channel for fan-out results).
- **Rationale**: Determinism is required for replay (FR-024) and for SC-005 reproducibility.
  Recording conflicts satisfies the spec's "resolved by a defined, documented merge rule
  rather than silently" edge case.
- **Alternatives rejected**: arbitrary dict-update order (non-deterministic under replay);
  raising on any conflict (too brittle for a fan-out whose whole point is concurrent
  contributions).

### R-HITL. Human-in-the-loop surface

- **Decision**: A human-in-the-loop node creates a card and immediately **blocks** it
  (`kanban_block`) with a structured prompt body describing the required human input. The
  run is durably paused (the card sits blocked/awaiting human action). A human supplies
  input by **unblocking/completing** the card with a result; the resulting completion event
  flows through the same advancement path (D2) as any other node.
- **Rationale**: Reuses the board's native block/unblock + completion mechanics, so a paused
  run survives a restart with zero plugin polling (FR-013/FR-017, SC-004). No bespoke signal
  channel needed.
- **Residual risk**: the exact block/unblock tool + REST field names drift by version
  (R2) — confirm at implementation.

### R-RECONCILE. Reconcile trigger

- **Decision**: v1 registers the reconcile **CLI command** and drives it opportunistically
  from `on_session_start` (cheap, replay-safe). `register_auxiliary_task` and a profile cron
  are documented fallbacks evaluated at implementation against the installed runtime.
- **Rationale**: `on_session_start` guarantees a reconcile pass whenever the gateway comes
  back, covering the restart-recovery acceptance (SC-003) without committing to an
  auxiliary-task API whose semantics are unverified.
- **Residual risk (R3)**: pick `register_auxiliary_task` vs profile cron once the installed
  runtime's scheduling surface is confirmed.

### R-RENDER. Visualization renderer (FR-005)

- **Decision**: The human-readable summary is produced in **pure Python** from the parsed
  domain model (textual structure summary + the canonical DOT text). No hard dependency on
  a system Graphviz binary for v1; rendering to an image is optional and detected at
  runtime.
- **Rationale**: Keeps the package installable without a system `dot` binary and keeps the
  summary logic in the domain (pure, 100%-testable). DOT is already the canonical artifact.
- **Alternatives rejected**: mandatory `graphviz`/`pydot` dependency (adds a system binary
  requirement for a feature whose acceptance only needs a readable summary).

### R-DOT. DOT parser/emitter library

- **Decision**: Use **`pydot`** as the adapter-level DOT (de)serializer behind a port; the
  domain never imports it. Round-trip fidelity is validated by tests. (Re-confirm exact
  Attractor attribute names / status enums against the Attractor NLSpec before encoding —
  this is an adapter concern, isolated from the domain.)
- **Rationale**: DOT parsing/emitting is non-trivial I/O that belongs in an adapter; a port
  keeps the domain pure and lets us swap the library if fidelity is insufficient.
- **Alternatives rejected**: hand-rolled DOT parser (error-prone, reinvents `pydot`);
  importing a DOT library into the domain (violates hexagonal purity).

## Residual risks tracked into the plan

| Id | Risk | Owner phase | Mitigation |
|----|------|-------------|------------|
| R1 | Entry-point group string may differ on installed Hermes | implement | Single config change; isolate in `plugin.yaml` + `pyproject.toml` |
| R2 | Kanban create/REST/block field names + `create_task` signature drift | implement | Isolate all kanban calls behind the `KanbanBoard` port; integration-test against installed version |
| R3 | Reconcile trigger choice (`register_auxiliary_task` vs profile cron vs session hooks) | implement | Default `on_session_start`; CLI is always available as manual fallback |
| R4 | `post_tool_call` hook must create follow-up cards before the worker exits, ahead of the `running`->exit `protocol_violation` guard | implement | Create follow-up cards synchronously inside the hook before returning; reconciler is the safety net if the hook is cut short |
