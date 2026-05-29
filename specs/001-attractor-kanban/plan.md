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
- The **guard mini-language** is a restricted, total, purely-domain expression language.
  Concrete grammar (EBNF notation):
  ```
  expr     ::= or_expr
  or_expr  ::= and_expr ( "or" and_expr )*
  and_expr ::= not_expr ( "and" not_expr )*
  not_expr ::= "not" not_expr | atom
  atom     ::= "(" expr ")" | comparison
  comparison ::= operand ( cmp_op operand )?
  operand  ::= KEY | STRING | NUMBER | BOOL | NULL
  cmp_op   ::= "==" | "!=" | "<" | "<=" | ">" | ">="
  KEY      ::= [A-Za-z_][A-Za-z0-9_.]*  (max 64 chars; dot for nested key path)
  STRING   ::= quoted string literal (single or double quotes, no embedded newlines)
  NUMBER   ::= integer or decimal literal
  BOOL     ::= "true" | "false"
  NULL     ::= "null"
  ```
  Supported semantics: bare `KEY` evaluates to truthy/falsy based on the context value at
  that key path (missing key = falsy, never an error). Nested key paths use dot notation
  up to 4 levels deep (`a.b.c.d`). Comparison is type-aware but never raises on type
  mismatch — a type mismatch returns `false`. Size cap: guard expression strings are
  rejected at validation if longer than 512 characters.
- No attribute access, no method calls, no indexing into arbitrary objects, no imports, no
  string operations — the grammar is the complete allowlist.
- The guard evaluator is implemented as a recursive-descent parser + evaluator in
  `domain/guard.py` — a pure, total domain function (replay-safe like `EdgeSelector`). An
  unparseable guard or a guard exceeding the size cap is a **validation error** (FR-004),
  not a runtime surprise.
- **Parse-tree depth cap (second-order: the 512-char cap does not bound recursion).** The
  512-character size cap bounds the input *length* but NOT the parse-tree *depth*. Within
  512 chars an attacker-authored guard can drive the recursive-descent parser arbitrarily
  deep: ~128 chained `not ` prefixes, or up to 256 nested `(` parentheses, each consuming a
  recursion frame. Unbounded recursion turns a "pure, total" guard into a `RecursionError`
  during `validate()` or during a runtime guard eval — exactly the runtime surprise this
  section claims to preclude. Mitigation: enforce a **maximum nesting depth of 32**
  (`MAX_GUARD_DEPTH = 32` in `domain/constants.py`), tracked as an explicit integer counter
  threaded through the recursive descent (NOT relying on Python's `sys.recursionlimit`).
  Exceeding the depth is a structured `PipelineValidationError` at parse time, never an
  uncaught `RecursionError`. The depth check is part of what makes the guard *total*.
- **Dot-path traversal must be total over non-mapping intermediates (second-order: the
  EBNF KEY regex over-admits, and traversal semantics are unspecified).** The KEY production
  `[A-Za-z_][A-Za-z0-9_.]*` admits malformed paths the "4 levels deep" prose does not reject:
  trailing dot (`a.`), doubled dots (`a..b`), and paths *longer* than 4 segments (`a.b.c.d.e`
  still matches the regex). Tokenization MUST reject empty path segments and reject more than
  4 segments as a validation error, not silently accept them. Separately, evaluation of a
  nested path like `a.b.c` when an intermediate value is a non-mapping (e.g. `a` is a string,
  number, list, or `null`) has no defined behavior in the current grammar prose: a naive
  `dict`-walk would raise `TypeError`/`KeyError` at runtime, breaking totality. Mitigation:
  path resolution is total — descending into a non-mapping (or hitting a missing segment at
  any level) yields the *missing-key* result (falsy as a bare KEY; `false` in any comparison),
  never an exception. Document this as a guard-evaluator invariant covered by tests.

### Prompt / `$var` expansion (FR-022) — template, not interpolation

- Context values expanded into card bodies (which become downstream agent prompts) are an
  injection surface (a malicious or compromised upstream node can write context that steers
  a downstream worker). Expansion MUST be a literal, non-recursive substitution of known
  `$var` placeholders only — never a templating engine that evaluates expressions, and never
  re-expanded on the substituted result.
- Undefined placeholders are surfaced as a structured authoring/validation issue. At
  runtime (if a card body is expanded against an incomplete context), undefined `$var`
  references are replaced with the literal string `__UNDEFINED_VAR_<name>__` so the
  downstream worker can see an explicit marker rather than a silently-empty or missing
  value. The marker format makes it searchable in logs and is never mistakable for a valid
  context value. They never leak the raw context object or adjacent keys.
- **Sentinel must not leak into the guard mini-language's truthiness/comparison domain
  (second-order: `$var` expansion and guards read the same Context).** The
  `__UNDEFINED_VAR_<name>__` marker is a *prompt-body* artifact only — it MUST be produced
  during card-body string expansion and MUST NOT be written back into the `Context.data`
  that the guard evaluator reads. A guard referencing a missing key must follow the guard's
  own missing-key rule (falsy / `false`), and must never observe a stringified sentinel that
  would compare truthy or match a `== "__UNDEFINED_VAR_x__"` literal. Conversely, a worker
  that writes a context value literally equal to the sentinel string must not gain the
  ability to forge an "undefined" appearance downstream: expansion distinguishes
  genuinely-absent keys from present-but-equal-to-sentinel values (only absence yields the
  marker). The sentinel lives in the expansion layer, not in the persisted Context.

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
  preventing memory/CPU exhaustion at the authoring entry point. Concrete limits: raw DOT
  input size capped at **1 MiB** (1,048,576 bytes); parsed graph must have no more than
  **256 nodes** and **1,024 edges**. Exceeding any cap raises `PipelineValidationError`
  with a structured issue naming the exceeded limit — never a parser crash or OOM.

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
  contention. The SQLite adapter MUST enable WAL mode (`PRAGMA journal_mode=WAL`) and set
  `busy_timeout` to **5,000 ms** (5 seconds) via `PRAGMA busy_timeout=5000`, wrap each
  advancement in a single transaction, and surface lock contention (still locked after
  timeout) as a retryable safe failure (handed to the reconciler) rather than a raised
  exception crossing the plugin boundary.

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
  Enforce a maximum fan-out width of **16 parallel branches** at validation (FR-004) and at
  runtime. This limit is a named constant `MAX_FAN_OUT_WIDTH = 16` in `domain/constants.py`
  (not a runtime-configurable setting — it is a safety invariant, not an operational tuning
  knob). Exceeding it yields a `PipelineValidationError` at authoring time and a blocked run
  with a structured reason at runtime rather than flooding the board.
- **Nested fan-out compounding and the self-hosting `sp` reference-pipeline conflict
  (second-order: a per-node cap of 16 does not bound total card explosion, and collides with
  M6/SC-006).** `MAX_FAN_OUT_WIDTH = 16` is a *per-node* width cap; it does not bound the
  *cumulative* card count when a fan-out branch itself reaches another fan-out (16 × 16 × …),
  which an untrusted DOT graph can author. More pressingly, this concrete cap now collides
  with a concrete reference workflow: the M6/SC-006 self-hosting `sp` pipeline models ralph
  draining a *dynamic* ready-queue and the deepen-plan/red-team/review stages fanning out a
  data-dependent number of parallel sub-tasks — a count that is plausibly variable and can
  exceed 16. A hard, non-configurable safety invariant of 16 would make the capstone
  reference pipeline (which is supposed to exercise *every* v1 capability) either fail
  validation or be forced to chunk its fan-out, undermining SC-006. Resolution: (a) the
  fan-out cap bounds the count of *direct simultaneous children of a single fan-out node*,
  and the engine MUST additionally bound the *total live (non-terminal) card count per run*
  with a separate constant `MAX_LIVE_CARDS_PER_RUN` so nested fan-outs cannot compound past a
  whole-run ceiling; (b) the `sp` reference pipeline MUST model unbounded work as *sequential
  iteration over a bounded-width fan-out batch* (process ready-queue items in waves of ≤16),
  NOT as a single mega-fan-out — this is the same acyclic-iteration pattern already mandated
  for goal-gate loops (D4). M6 must demonstrate this batching pattern; if the reference graph
  cannot be expressed within the cap via batching, that is a signal to revisit the constant
  *before* M6, recorded as a risk rather than silently raising the limit.

### Bounded event-log replay

- `EventLog.read_since(last_seen_event_id)` after a long outage can return a large slice of
  `task_events`. Read in bounded batches of **100 events per batch**, advancing and
  persisting the cursor after each batch, so a far-behind reconcile makes monotonic progress
  without loading the whole log into memory. The batch size is a named constant
  `EVENT_LOG_BATCH_SIZE = 100` in `domain/constants.py`.
- **Batch-boundary correctness for fan-in aggregation (second-order: per-batch cursor
  persistence must not strand a fan-in).** A FAN_IN node resolves only after *all* its branch
  completions are observed. When branch-completion events straddle the 100-event batch
  boundary (e.g. branches 1–3 land in batch K, branch 4 in batch K+1), persisting the cursor
  at the end of batch K marks branches 1–3's events as permanently "seen". Correctness
  therefore depends on fan-in aggregation state being **durable RunNode state**, not derived
  from re-reading those events: each branch completion durably records arrival on the FAN_IN
  RunNode within the same transaction that advances the cursor, so the fan-in resolves when
  the final branch's event is processed in a later batch. This makes batch size purely a
  memory/throughput knob with no effect on aggregation correctness. State that explicitly:
  the advance core MUST never require two events from *different* batches to be in memory
  simultaneously to resolve a merge.

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
