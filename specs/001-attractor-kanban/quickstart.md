# Quickstart: Attractor on Hermes Kanban

**Branch**: `001-attractor-kanban` | **Spec**: [spec.md](./spec.md)

A walkthrough of the v1 capability from an operator's and an agent's point of view. This is
the "does it work" smoke path that the self-hosting reference pipeline (SC-006) exercises in
full.

## Prerequisites

- Hermes agent runtime with the **Kanban** feature enabled and the gateway/dispatcher
  running (assumption: `ready` cards do not progress without it).
- Hermes **profiles** defined for each model a pipeline needs (per-node model = per-node
  profile, e.g. `planner-sonnet`, `coder-gpt5`, `reviewer-opus`).
- The `attractor` plugin installed/discovered via the `hermes_agent.plugins` entry point (or
  the `.hermes/plugins/attractor` symlink for local dev).
- `git` available for `.dot` versioning.

## 1. Author a pipeline (agent, via tools)

The agent never hand-writes DOT. It composes structurally:

```text
attractor_create_graph(spec_id="hello")
attractor_add_node(spec_id="hello", node_id="start", shape="start")
attractor_add_node(spec_id="hello", node_id="plan",  shape="codergen",
                   profile="planner-sonnet", prompt="Plan: $goal")
attractor_add_node(spec_id="hello", node_id="gate",  shape="codergen",
                   goal_gate={"retry_target": "plan", "max_attempts": 3})
attractor_add_node(spec_id="hello", node_id="exit",  shape="exit")
attractor_add_edge(spec_id="hello", source_id="start", target_id="plan")
attractor_add_edge(spec_id="hello", source_id="plan",  target_id="gate")
attractor_add_edge(spec_id="hello", source_id="gate",  target_id="exit")
attractor_validate(spec_id="hello")   # -> {"valid": true, "issues": []}
attractor_summary(spec_id="hello")    # -> human-readable structure + canonical DOT
```

The validated pipeline is saved as a git-tracked `hello.dot` (a local-only repo is
initialized if none was provided).

## 2. Run it

```text
attractor_run(spec_id="hello", context={"goal": "ship the thing"})
# -> {"run_id": "<id>", "status": "RUNNING"}
```

The engine creates the first card assigned to the resolved profile with body
`Plan: ship the thing`. The kanban dispatcher spawns the profile worker. When the worker
calls `kanban_complete`, the `post_tool_call` hook advances the run inline and creates the
next card with idempotency key `attractor:<run_id>:gate:attempt:1`.

## 3. Goal-gate loop (acyclic)

If the gate card completes with `{"gate": "fail", "required_changes": [...]}` and attempts
remain, the engine creates a **new** `plan` segment (`attempt:2`) — never a cyclic kanban
link. On `pass`, traversal proceeds to `exit`. On exhausted attempts, the run is **blocked**
for human review.

## 4. Crash recovery (SC-003)

Kill and restart the gateway mid-run. On restart, `on_session_start` drives
`attractor reconcile`, which replays `task_events WHERE id > last_seen_event_id`, advances
any run that missed its `post_tool_call` event, and persists the cursor — completed nodes
are never re-executed. Manual recovery: run `hermes attractor reconcile`.

## 5. Status & result

```text
attractor_status(spec_id..., run_id="<id>")  # -> status + current nodes + context keys
attractor_result(run_id="<id>")              # -> final status + outcome
```

## Smoke verification checklist

- [ ] `attractor_validate` rejects a missing-start / dangling-edge / unknown-profile graph,
      naming the offending element (SC-007).
- [ ] A run with a per-node profile override beats the stylesheet default (SC-002).
- [ ] Gateway restart resumes a run without re-execution (SC-003).
- [ ] A human-in-the-loop node pauses, survives restart, resumes on input (SC-004).
- [ ] A fan-out of N branches merges all N contributions, running concurrently (SC-005).
