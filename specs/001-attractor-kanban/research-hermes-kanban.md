# Research: Hermes Kanban as Attractor's Execution Substrate

**Status**: Grounded (verified against `NousResearch/hermes-agent` source, 2026-05-28)
**Audience**: `/sp:03-plan` (input for plan.md / data-model.md / contracts)
**Spec**: [spec.md](./spec.md)

This note records verified Hermes facts and the resulting architecture direction, so the
plan phase does not have to re-derive them. Verdicts are from reading the actual source;
exact identifiers should still be re-confirmed against the installed version before coding.

## Verified findings

| # | Claim | Verdict | Evidence (source paths) |
|---|-------|---------|-------------------------|
| 1 | `task_events` durable event log; tail by `id > last_seen_event_id` | **TRUE** | `hermes_cli/kanban_db.py:913` (`task_events(id INTEGER PK AUTOINCREMENT, task_id, run_id, kind, payload, created_at)`); cursor `kanban_notify_subs.last_event_id:963`; tail query `read_unseen_events`/`claim_unseen_events_for_sub:6484` |
| 2 | No first-class plugin hook for kanban completion | **TRUE** | `plugins.py:128` `VALID_HOOKS` (17 hooks, listed below); notifier `_kanban_notifier_watcher` is gateway-internal (`gateway/run.py:4804,4389`), not plugin-registrable |
| 3 | Per-task `model_override` column + dispatcher `-m` | **PARTIAL** | column `kanban_db.py:884`; dispatcher `if task.model_override: cmd.extend(["-m", task.model_override])` `:5996`. **Public create surface does NOT expose it** (tool/CLI/REST create have no model param) |
| 4 | `idempotency_key` on create dedupes | **TRUE** | accepted by `kanban_create` tool, `POST /tasks`, CLI `--idempotency-key`; dedup `create_task:1856` returns existing non-archived task id |
| 5 | Per-profile `model.default` config; worker spawned as profile | **TRUE** | `profiles.py:468` reads per-profile `config.yaml` `model.default`; dispatcher `cmd=[..., "-p", profile_arg, "--accept-hooks"]:5960`, `env[HERMES_PROFILE]`, `env[HERMES_HOME]=resolve_profile_env(...)` |
| 6 | Plugin can run a persistent in-gateway watcher daemon | **PARTIAL** | A plugin may open its own SQLite DB, but there is **no plugin API to register a background loop / timer / startup daemon**. Lifecycle = `register(ctx)`, tools, hooks (17), cli/commands, providers, `register_auxiliary_task`, platform, skill |

**Plugin hooks available** (`VALID_HOOKS`): `pre_tool_call`, `post_tool_call`,
`transform_terminal_output`, `transform_tool_result`, `transform_llm_output`,
`pre_llm_call`, `post_llm_call`, `pre_api_request`, `post_api_request`,
`on_session_start`, `on_session_end`, `on_session_finalize`, `on_session_reset`,
`subagent_stop`, `pre_gateway_dispatch`, `pre_approval_request`, `post_approval_response`.

**Kanban event kinds** (`_append_event`, `kanban_db.py:2270`): created, edited, assigned,
promoted, promoted_manual, reprioritized, claimed, claim_rejected, claim_extended,
reclaimed, scheduled, spawned, respawn_guarded, completed, blocked, unblocked, decomposed,
linked, unlinked, commented, specified, archived, heartbeat, stale, timed_out, crashed,
protocol_violation, gave_up, completion_blocked_hallucination,
suspected_hallucinated_references, tip_scratch_workspace.
*(Note: legacy `spawn_auto_blocked` was renamed to `gave_up`; `ready`→`promoted`.)*
Gateway notifier terminal filter: `("completed", "blocked", "gave_up", "crashed",
"timed_out")` (`run.py:4830`).

## Architecture direction (for plan.md)

Responsibility split (from the hermes-agent design, confirmed feasible):

- **Plugin** = deterministic workflow state machine. Parses the DOT pipeline, creates the
  initial kanban card(s), owns durable run state, advances on node completion, dynamically
  creates iteration/branch cards, and enforces idempotency.
- **Kanban board** = durable execution substrate. Task queue, worker spawning, parent/child
  dependency enforcement, audit trail (`task_events`), comments, blocks, completions.
- **Profiles** = worker identity + tools + skills + **model** config. A node names its
  profile; the profile's `model.default` is the node's model.

### Run advancement — how the engine is driven (resolves #1/#6)

There is no daemon and no kanban hook, so use two complementary paths:

1. **Primary (in-worker):** register a `post_tool_call` hook that fires after
   `kanban_complete` / `kanban_block`. Because workers run with `--accept-hooks` and load
   plugins, the just-finished worker advances the run inline — evaluates edge selection /
   goal gate, then creates the next card(s) with idempotency keys.
2. **Recovery (reconciler):** register a CLI command (e.g. `hermes attractor reconcile`)
   that replays `task_events WHERE id > last_seen_event_id` and advances any run that missed
   an event (worker crashed before the hook ran). Drive it opportunistically (e.g.
   `on_session_start` / `pre_gateway_dispatch`) and/or via a **profile cron job**.

Both paths are safe to run repeatedly because creation is idempotent (below). Treat
completion handling as **replayable**; never rely on in-memory plugin state.

### Plugin-owned durable state (resolves persistence)

Plugin opens its own SQLite DB (separate from kanban):

```
plugin_runs(run_id, spec_id, state, root_task_id, last_seen_event_id, created_at, updated_at)
plugin_run_nodes(run_id, node_id, task_id, status, attempt, parent_node_ids,
                 goal_gate_policy, output_ref)
```

On start/reconcile: open kanban DB + plugin DB → load active runs → read
`task_events.id > last_seen_event_id` → advance state machine → persist
`last_seen_event_id` after successful handling → create next cards with idempotency keys.

### Idempotency-key scheme

Deterministic keys so replay never duplicates cards:

```
attractor:<run_id>:<node_id>:attempt:<n>
attractor:<run_id>:<gate_id>:attempt:<n>
```

### Goal-gate loops on an acyclic DAG (resolves #3 loop concern)

Never create cyclic kanban links. Each retry is a **new** DAG segment:

```
implement (attempt 1) → gate (attempt 1) ──pass──→ finalize
                                          └─fail──→ implement (attempt 2) → gate (attempt 2) → …
```

Gate cards complete with a structured result the plugin reads, e.g.:

```json
{ "gate": "fail", "score": 0.72,
  "reasons": ["missing test coverage"],
  "required_changes": ["Add regression test for X"] }
```

Plugin decision on gate completion: `pass` → create downstream node; `fail` &&
attempts_remaining → create next correction card; `fail` && max reached → **block** the run
for human review.

### Per-node model selection (resolves #3 model surface)

- **v1 (chosen):** per-node = per-node **profile**; model comes from the profile's
  `config.yaml` `model.default`. Operators define model-specific profiles
  (`planner-sonnet`, `coder-gpt5`, `reviewer-opus`, …).
- **Roadmap (Option B):** `tasks.model_override` + dispatcher `-m` already exist; only the
  public *create* surface lacks the param. A small upstream change (add `model_override` to
  `kanban_create` / `POST /tasks` / CLI) unlocks per-node arbitrary models without profile
  explosion. Until then, do **not** depend on per-task model override.

## Residual risks / to confirm at implementation

- A register-time `post_tool_call` hook must reliably observe `kanban_complete` in the
  worker process and have time to create follow-up cards before the worker exits (the
  `running`→exit `protocol_violation` guard must not fire first). Confirm ordering.
- Exact kanban tool/REST field names and the `create_task` signature on the installed
  version (names drift; e.g. `gave_up` rename).
- Whether `register_auxiliary_task` or profile cron is the better reconcile trigger.
- Entry-point group is `hermes_agent.plugins` (not the repo's current `hermes.plugins`).

---

## Phase 1 live-API verification (zym.31) — verified against installed `hermes-agent==0.15.2`

**Status**: Grounded by empirical dispatch + DB inspection against the installed package
(`uv run --with hermes-agent==0.15.2`), 2026-05-30. Resolves the three A/B/C unknowns that
gated Part B. Durable proof lives in `tests/integration/test_reconcile_runtime.py`.

### (A) Registry / dispatch access — RESOLVED

- The tool registry is a module-global singleton in a **separate top-level package** `tools`
  (sibling to `hermes_cli`), **not** `hermes_cli.tools.registry`:
  `from tools.registry import registry`.
- Dispatch signature: `registry.dispatch(name: str, args: dict, **kwargs) -> str`. It returns a
  **JSON string** (the handler's return value, or `{"error": ...}` on unknown tool / exception).
- `registry.dispatch` does **not** consult a tool's `check_fn` — direct dispatch of kanban tools
  works in an orchestrator/CLI context (no `HERMES_KANBAN_TASK`) even though `registry.list_tools()`
  hides them from the model schema there.
- A hook callback obtains the registry by **module-global import**, not via kwargs: hooks are
  invoked as `cb(**kwargs)` (`PluginManager.invoke_hook`), and `on_session_start ∈ VALID_HOOKS`.
  CLI handlers are invoked as `handler_fn(args)` (argparse `set_defaults(func=...)`).
  ⇒ `plugin/__init__.py::_runtime` dropping runtime kwargs is irrelevant to dispatch; the seam is
  the import, wrapped by `RuntimeToolClient(dispatch=registry.dispatch)`.
- `PluginContext.register_hook(hook_name, callback)` and
  `register_cli_command(name, help, setup_fn, handler_fn=None, description="")` match `ports/hermes.py`.

### (B) Kanban tool names + params — DRIFT CONFIRMED, fixed in `adapters/kanban_board.py`

LLM-facing names are `kanban_create` / `kanban_complete` / `kanban_block` (not `create_task` / …).

- `kanban_create` **requires `title` and `assignee`**; deps are `parents` (not `parent_task_ids`);
  `idempotency_key` dedupes (returns the existing `task_id`); there is **no `retry_limit` / `kind`**
  param. Returns `{"ok": true, "task_id": "t_…", "status": "ready"}`. Our `Card` has no title, so the
  adapter synthesizes one (first body line, capped; fallback to the idempotency key).
- `kanban_complete`: `task_id`, `summary`, `metadata` (+ `result`, `created_cards`, `artifacts`).
  In orchestrator/CLI context (`HERMES_KANBAN_TASK` unset) `_enforce_worker_task_ownership` is a no-op
  and `expected_run_id=None`, so it completes a freshly-created `running|ready` task directly — this is
  how the integration test simulates a worker completion (no LLM, no key).
- `kanban_block`: `task_id`, `reason` only (no `body`); the adapter folds `body` into `reason`.

### (C) Event-log read — NO TOOL; read `task_events ⋈ task_runs` directly

- There is **no event-read tool** (only `kanban_show`/`kanban_list`). `read_task_events` does not exist.
- `task_events(id PK AUTOINCREMENT, task_id, run_id, kind, payload, created_at)`. The completion **event
  payload only carries a truncated first-line `summary` + `result_len`** — it does **not** contain the
  worker's structured `metadata` (gate verdict / `context_updates`). Those live on the **`task_runs`** row
  (`summary`, `metadata` JSON), linked by `task_events.run_id = task_runs.id` (a synthesized zero-duration
  run is created if the task was never claimed).
- The reconcile EventLog therefore reads via this query (terminal-filtered, cursor-bounded, ordered, capped):
  ```sql
  SELECT e.id AS event_id, e.task_id, e.kind, r.summary, r.metadata
  FROM task_events e LEFT JOIN task_runs r ON e.run_id = r.id
  WHERE e.id > ? AND e.kind IN ('completed','blocked','gave_up','crashed','timed_out')
  ORDER BY e.id ASC LIMIT ?
  ```
  Implemented as `adapters/task_event_reader.py::SqliteTaskEventReader` behind an injectable
  connection factory; `adapters/event_log.py::HermesEventLog` now depends on the `TaskEventReader`
  port instead of `HermesToolClient`.

### Isolated-home init for tests

`hermes_cli.kanban_db.connect(db_path=…)` (or `board`/env) **auto-creates the schema on first connect** —
no `hermes setup` and no model key needed. Tests set `HERMES_HOME` + `HERMES_KANBAN_DB` into `tmp_path`;
the first `kanban_create` dispatch creates `kanban.db`.

### Residual note (out of scope for zym.31)

`block_card` writes a terminal `blocked` event that a later reconcile will read; the HUMAN-pause /
blocked-event interaction is governed by the existing use-case tests and the deferred `post_tool_call`
hook, and is unchanged here. The zym.31 proof covers the linear `A→B` completion→advance path.
