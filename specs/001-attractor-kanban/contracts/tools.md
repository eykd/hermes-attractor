# Contract: Plugin Tool Surface & Hooks

**Branch**: `001-attractor-kanban` | **Layer**: `src/hermes_attractor/plugin/`

The LLM-facing tools the plugin registers (FR-001, FR-018, FR-023), plus the
non-tool registrations (hook + CLI command) that drive run advancement (research D2).
Every tool handler returns a JSON string and never raises (plugin contract / FR-023).

## Authoring tools (FR-001 / FR-002 / FR-004 / FR-005)

The structured authoring surface — agents never hand-write DOT. Each mutating tool patches
the stored DOT and returns the updated structured view or a structured error (Edge Case:
malformed authoring request leaves the stored definition unchanged).

| Tool | Purpose | Key inputs | Result (`ok:true`) |
|------|---------|-----------|--------------------|
| `attractor_create_graph` | Create a new pipeline | `spec_id`, optional `repo_path` | `{spec_id}` |
| `attractor_add_node` | Add a node | `spec_id, node_id, shape, prompt?, profile?, retry_limit?, goal_gate?, class?` | updated node summary |
| `attractor_remove_node` | Remove a node | `spec_id, node_id` | confirmation |
| `attractor_add_edge` | Add an edge | `spec_id, source_id, target_id, condition?, label?, weight?` | updated edge summary |
| `attractor_remove_edge` | Remove an edge | `spec_id, source_id, target_id, label?` | confirmation |
| `attractor_set_attr` | Set node/edge/graph attribute | `spec_id, target, key, value` | updated view |
| `attractor_set_profile` | Set a node's profile | `spec_id, node_id, profile` | updated node |
| `attractor_set_stylesheet` | Set/patch the stylesheet | `spec_id, rules[]` | updated stylesheet |
| `attractor_validate` | Validate the pipeline | `spec_id` | `{valid: bool, issues:[{element, reason}]}` |
| `attractor_summary` | Human-readable summary | `spec_id` | `{summary, dot}` |

## Execution tools (FR-014 / FR-018)

| Tool | Purpose | Key inputs | Result (`ok:true`) |
|------|---------|-----------|--------------------|
| `attractor_run` | Launch a run | `spec_id`, optional initial `context` | `{run_id, status}` |
| `attractor_status` | Query run status | `run_id` | `{run_id, status, current_nodes[], context_keys[]}` |
| `attractor_result` | Retrieve outcome | `run_id` | `{run_id, status, outcome}` |

## Safe-handler envelope (all tools)

```json
{ "ok": true, "result": { ... } }
{ "ok": false, "error": "<ExceptionType>", "message": "<actionable message>" }
```

Validation errors (FR-004 / SC-007) surface inside `result.issues` for `attractor_validate`
and as `ok:false` with the offending element named for mutating tools whose change would
produce an invalid graph.

## Hook registration — `post_tool_call` (research D2, primary advancement)

```text
event:   post_tool_call
handler: advance_on_completion(tool_name, tool_input, tool_result) -> None
```

Behavior: when `tool_name in {kanban_complete, kanban_block}`, look up the run/node by the
completed `task_id`, build the `Outcome`, run the traversal use case, and **synchronously
create the follow-up card(s) before returning** (research risk R4 — must beat the
`running`->exit `protocol_violation` guard). The handler never raises; failures are logged
and left for the reconciler.

## CLI command registration — `reconcile` (research D2, recovery)

```text
command: attractor reconcile
handler: reconcile() -> None
```

Behavior: for each active run, read `EventLog.read_since(last_seen_event_id)`, advance the
state machine for any unprocessed terminal event, create follow-up cards idempotently, and
persist the cursor last. Safe to run repeatedly (idempotent). Driven from `on_session_start`
by default (research R-RECONCILE); always available as a manual command.
