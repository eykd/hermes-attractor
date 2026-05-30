# Phase 1 Data Model: Attractor on Hermes Kanban

**Branch**: `001-attractor-kanban` | **Spec**: [spec.md](./spec.md) |
**Date**: 2026-05-28

Entities use the **Ubiquitous Language** from [docs/glossary.md](../../docs/glossary.md).
Layer placement follows the hexagonal rule (`domain <- use_cases -> ports`, `adapters ->
ports`, only `plugin/` knows Hermes). Domain types are pure: zero external deps, no I/O, no
kanban/Hermes awareness.

## Layer map

| Concept | Layer | Location |
|---------|-------|----------|
| Pipeline, Node, Edge, Context, Outcome, Stylesheet, NodeShape, EdgeSelector, GoalGatePolicy, exceptions | domain | `domain/` |
| Run, RunNode, RunStatus, NodeRunStatus, IdempotencyKey | domain | `domain/run.py` (pure state record + transitions) |
| Card, CardResult (DTOs crossing the port) | domain (value objects) | `domain/card.py` |
| `KanbanBoard`, `PipelineStore`, `RunStateStore`, `EventLog`, `Clock`, `PluginContext`, `Renderer`, `ToolNodeRegistry` | ports | `ports/` |
| pydot serializer, git store, SQLite run store, kanban client, kanban event-log reader, pure-Python renderer | adapters | `adapters/` |
| Authoring use cases, validation, run launch/advance/reconcile/status | use_cases | `use_cases/` |
| tool schemas + handlers, hooks, CLI command, registration | plugin | `plugin/` |

---

## Domain entities & value objects

### NodeShape (enum)

Selects a node's handler (FR-006). Stored as the DOT `shape` attribute via the serializer.

| Member | DOT shape | Role |
|--------|-----------|------|
| `START` | `Mdiamond` | unique entry |
| `EXIT` | `Msquare` | unique terminus |
| `CODERGEN` | `box` | agent work via a Card |
| `CONDITIONAL` | `diamond` | guard-based routing |
| `TOOL` | `parallelogram` | deterministic non-agent stage |
| `FAN_OUT` | `component` | spawn concurrent branches |
| `FAN_IN` | `tripleoctagon` | merge branch contexts |
| `HUMAN` | `hexagon` | durable pause for human input |

*Invariant*: exactly one `START` and exactly one `EXIT` per Pipeline (FR-004).

### Node (entity)

A single stage (glossary: **Node**). Identity = `node_id` (DOT node id).

- `node_id: str` — unique within the pipeline; non-empty.
- `shape: NodeShape`.
- `prompt: str | None` — codergen/human body template; supports `$var` expansion (FR-022).
- `profile: str | None` — per-node profile override (FR-019); resolved against the
  Stylesheet when absent.
- `retry_limit: int` — `>= 0`; governs card retries before terminal node failure (FR-016).
- `goal_gate: GoalGatePolicy | None` — present iff this node is a goal gate (FR-009).
- `node_class: str | None` — selector class for the Stylesheet (FR-020).

*Invariants*: `node_id` non-empty; `retry_limit >= 0`; START/EXIT carry no `prompt`,
`profile`, or `goal_gate`.

### GoalGatePolicy (value object)

Encodes a goal gate's retry routing (FR-009). Acyclic-loop policy from research D4.

- `retry_target: str` — node id traversal routes to on an unsatisfied gate; must be a
  reachable node (FR-004 goal-gate retry-target sanity).
- `max_attempts: int` — `>= 1`; on exhaustion the Run is blocked for human review.

### Edge (entity)

A directed transition (glossary: **Edge**). Identity = `(source_id, target_id, label)`.

- `source_id: str`, `target_id: str` — must reference existing nodes (FR-004 dangling-edge).
- `condition: str | None` — guard evaluated against the Context (FR-011).
- `label: str | None` — preferred routing label.
- `weight: int` — priority; default `0`.

### EdgeSelector (domain service)

Deterministic edge selection (FR-007). Pure function over `(candidate edges, Context,
Outcome)`. Priority order, each a tiebreak for the previous:

1. matching `condition` guard,
2. preferred `label` (from the Outcome's routing hint),
3. suggested next node id(s) (from the Outcome),
4. highest `weight`,
5. stable **lexical** tiebreak on `target_id`.

*Invariant*: total and deterministic — identical inputs always yield the same edge (load-
bearing for replay, FR-024).

### Pipeline (aggregate root)

A directed graph (glossary: **Pipeline**). Canonical stored form is DOT.

- `spec_id: str` — stable identity (derived from the `.dot` path / graph name).
- `nodes: Mapping[str, Node]`.
- `edges: Sequence[Edge]`.
- `stylesheet: Stylesheet`.

*Validation rules (FR-004 / SC-007)* — `Pipeline.validate()` returns a list of structured
errors (never raises for validation failures; see error-handling design):

- exactly one START and one EXIT node;
- every edge endpoint references an existing node (no dangling edges);
- full reachability from START; no unreachable nodes;
- every goal gate's `retry_target` exists and is reachable;
- every node's resolved profile is non-empty (a node names a profile directly or the
  Stylesheet resolves one); unknown/empty profile is an error.

*Profile resolution*: `Pipeline.resolve_profile(node)` returns the per-node `profile` if
set, else the Stylesheet match (FR-019 overrides FR-020).

### Stylesheet (value object)

Selector->profile defaults with specificity (glossary: **Stylesheet**, FR-020).

- `rules: Sequence[StyleRule]` where `StyleRule = (selector, profile)`.
- Selector kinds: `universal` (`*`), `shape`, `class`, `id`, with documented specificity
  precedence **id > class > shape > universal**; ties broken by **last rule wins**.
- `resolve(node) -> str | None` — highest-specificity matching profile.

### Context (value object)

Shared key/value state threaded through a Run (glossary: **Context**, FR-008).

- `data: Mapping[str, object]` — JSON-serializable values (persisted in run state).
- `apply(updates) -> Context` — returns a new Context (immutable update).
- `clone() -> Context` — deep copy for fan-out (R-MERGE).
- `merge(branches) -> Context` — deterministic fan-in per research R-MERGE (disjoint union;
  conflicts last-writer-by-branch-order recorded under `_merge_conflicts`; same-key lists
  concatenated in branch order).
- Reserved keys: `_merge_conflicts`.

### Outcome (value object)

A node handler's result (glossary: **Outcome**, FR-007/FR-008).

- `status: NodeStatus` — `SUCCESS | PARTIAL | FAIL | RETRY`.
- `preferred_label: str | None`, `suggested_next: Sequence[str]` — routing hints.
- `context_updates: Mapping[str, object]` — applied before traversal continues.
- For gate nodes, also carries the structured gate verdict (`gate: pass|fail`, `score`,
  `reasons`, `required_changes`) parsed from the Card result (research D4).

---

## Run-state entities (durable; domain records, persisted via `RunStateStore`)

These are pure domain records describing the persisted state from research D6. The SQLite
adapter maps them to `plugin_runs` / `plugin_run_nodes`.

### RunStatus (enum)

`PENDING | RUNNING | PAUSED_HUMAN | BLOCKED | SUCCEEDED | FAILED`.

Transitions (state machine; enforced in the domain):

- `PENDING -> RUNNING` (launch).
- `RUNNING -> PAUSED_HUMAN` (reached a HUMAN node), and back to `RUNNING` on input.
- `RUNNING -> BLOCKED` (goal-gate attempts exhausted / terminal node failure awaiting
  human review).
- `RUNNING -> SUCCEEDED` (reached EXIT with all goal gates satisfied).
- `RUNNING -> FAILED` (terminal failure with no recovery, FR-016).

### NodeRunStatus (enum)

`PENDING | DISPATCHED | RUNNING | SUCCEEDED | PARTIAL | FAILED | BLOCKED`.

### Run (entity) -> `plugin_runs`

- `run_id: str` (identity), `spec_id: str`, `status: RunStatus`,
  `root_task_id: str | None`, `last_seen_event_id: int` (the durable replay cursor,
  FR-024), `context: Context`, `created_at`, `updated_at`.

### RunNode (entity) -> `plugin_run_nodes`

- `run_id: str`, `node_id: str` (composite identity with `run_id`), `task_id: str | None`
  (the Card id), `status: NodeRunStatus`, `attempt: int` (`>= 1`; the `<n>` in the
  idempotency key), `parent_node_ids: Sequence[str]`, `goal_gate_policy: GoalGatePolicy |
  None`, `output_ref: str | None`.

*Invariant*: `(run_id, node_id, attempt)` is unique and maps 1:1 to an idempotency key
`attractor:<run_id>:<node_id>:attempt:<attempt>` (research D5).

### IdempotencyKey (value object)

- `value: str` formatted `attractor:<run_id>:<node_id>:attempt:<n>`.
- `for_node(run_id, node_id, attempt) -> IdempotencyKey` factory; the single source of
  truth for the scheme (no string-building scattered across use cases).

---

## DTOs crossing the kanban port

### Card (value object) -> input to `KanbanBoard.create_card`

- `idempotency_key: IdempotencyKey`, `assignee_profile: str`, `body: str`,
  `parent_task_ids: Sequence[str]`, `retry_limit: int`, `kind: CardKind`
  (`WORK | GATE | HUMAN`).

### CardResult (value object) -> returned by `EventLog`/`KanbanBoard` on completion

- `task_id: str`, `event_id: int`, `event_kind: str` (kanban terminal kind:
  `completed | blocked | gave_up | crashed | timed_out`), `summary: str`,
  `metadata: Mapping[str, object]`.
- `to_outcome() -> Outcome` is performed by a use case (not the DTO), mapping kanban
  terminal kinds + parsed gate JSON to a domain `Outcome`.

---

## Exception hierarchy (domain) — see error-handling design

Extend `AttractorError`:

- `PipelineValidationError(AttractorError)` — aggregates structured `ValidationIssue`s
  (offending element id + reason); raised only at the boundary where a hard failure is
  required, while `validate()` returns issues for the non-raising authoring path.
- `UnknownNodeError`, `DanglingEdgeError`, `UnknownProfileError` — specific authoring/
  validation faults (FR-004 / SC-007).
- `RunStateError(AttractorError)` — illegal Run/RunNode transition.
- `TraversalError(AttractorError)` — no selectable edge / inconsistent graph at runtime.

Adapter-layer failures (kanban call failed, DOT parse failed, DB error) raise their own
adapter exceptions that use cases translate into safe tool/CLI payloads; per the plugin
contract, handlers never raise (FR-023).
