# Feature Specification: Attractor on Hermes Kanban (Plugin)

**Feature Branch**: `001-attractor-kanban`
**Created**: 2026-05-28
**Status**: Draft
**Brainstorm**: specs/brainstorms/2026-05-28-attractor-hermes-temporal-requirements.md
**Research**: specs/001-attractor-kanban/research-hermes-kanban.md (grounded Hermes Kanban findings)
**Beads Epic**: `hermes-attractor-zym`

**Beads Phase Tasks**:

- plan: `hermes-attractor-zym.1`
- red-team: `hermes-attractor-zym.2`
- tasks: `hermes-attractor-zym.3`
- analyze: `hermes-attractor-zym.4`
- implement: `hermes-attractor-zym.5`
- harden: `hermes-attractor-zym.6`

## Overview

Teams building multi-stage AI/agent pipelines need to **declare** a workflow as a graph
(rather than write imperative glue code), **run** it durably (surviving crashes and
restarts), and **choose who does the work per node** (a cheap, fast agent profile for
routing; a strong profile for hard work). StrongDM's *Attractor* defines exactly this — a
directed graph of nodes, traversed by a deterministic engine that invokes agentic work at
each node — but ships only a specification.

This feature implements Attractor's semantics as a **Hermes agent plugin**. Its headline
value is **authoring and versioning** pipelines: a Hermes agent composes, validates,
visualizes, and versions workflows through structured tools, with Graphviz **DOT** as the
canonical stored artifact. Its second capability is **durable execution on the Hermes
Kanban board**: the plugin acts as a deterministic engine that walks the graph and, for
each work node, **creates a kanban card assigned to that node's Hermes profile**. The
Hermes kanban dispatcher spawns the assigned profile as a worker to perform the work, and
the board provides durability, retries, dependency sequencing, crash recovery, and
human-in-the-loop — so no separate orchestrator is required. **Per-node model selection is
expressed as per-node profile selection**: a node names the profile that works it, and that
profile's configuration determines the model used.

The reference pipeline that anchors acceptance is **self-hosting**: this project's own
`sp` development workflow (specify → plan → red-team → tasks → implement → review/harden)
expressed as an Attractor graph. It exercises every v1 capability — per-node profiles, goal
gates, parallel fan-out/fan-in, human-in-the-loop, and tool nodes — and demonstrates that
the graph plus the kanban board's durable state replace the external task queue the manual
workflow uses today.

## User Scenarios & Testing

### Primary User Story

A developer, working through a Hermes agent, asks the agent to build a pipeline. The agent
uses authoring tools to add nodes (each representing a unit of work), connect them with edges (some
conditional, some weighted), assign a profile to each work node (directly or via a
stylesheet), and mark exit-blocking goal gates. The agent validates the pipeline, sees a
readable summary of its structure, and the definition is saved as a versioned `.dot` file.
The developer then asks the agent to run it; the pipeline executes durably as kanban cards
worked by the assigned profiles, pausing for human approval where required and recovering
transparently if the Hermes gateway restarts mid-run. The developer can check status and
retrieve the final outcome.

### Acceptance Scenarios

1. **Given** an empty repository, **When** the agent authors a multi-node pipeline with a
   branch and a goal gate, **Then** the pipeline validates clean and is saved as a
   git-tracked `.dot` file (a local-only repository is initialized if none was provided).
2. **Given** a pipeline whose nodes name different profiles (some via a stylesheet, one via
   a per-node override), **When** it runs, **Then** each work node is performed by a kanban
   card assigned to the resolved profile, and the per-node override takes precedence over the
   stylesheet default.
3. **Given** a running pipeline, **When** the Hermes gateway is killed and restarted
   mid-run, **Then** the run resumes without re-executing already-completed nodes and
   reaches the same outcome.
4. **Given** a pipeline containing a human-in-the-loop node, **When** traversal reaches that
   node, **Then** the run pauses (the card is blocked / awaiting human action), survives a
   restart while paused, and resumes when a human supplies input.
5. **Given** a pipeline with a parallel fan-out and fan-in, **When** it runs, **Then** the
   independent branches execute concurrently (sibling cards) and their context contributions
   are merged before traversal continues.
6. **Given** a pipeline with a goal-gated node that has not yet succeeded, **When** traversal
   would otherwise reach the exit, **Then** the run is routed back per the gate's retry
   target rather than exiting, and exits only once the gated node reaches success or
   partial success.
7. **Given** a pipeline containing a tool node, **When** traversal reaches it, **Then** the
   deterministic tool work runs as a pipeline node and its result updates the shared context.
8. **Given** the self-hosting reference pipeline (the `sp` workflow as a graph), **When** it
   runs end-to-end, **Then** it produces the expected per-phase outputs, routes review
   lenses in parallel, pauses at approval gates, and exits only when its review goal gates
   are satisfied.

### Edge Cases

- An invalid graph (no start node, multiple exits, an unreachable node, an edge to a missing
  node, or a goal gate with no reachable retry target) is rejected by validation with an
  actionable error and is not runnable.
- A work node exhausts its card's allowed retries → the run records a terminal failure
  outcome and stops cleanly with a reported reason.
- Parallel branches produce conflicting updates to the same context key → resolved by a
  defined, documented merge rule rather than silently.
- A human-in-the-loop node receives no input for an extended period → the run remains
  durably paused (no busy-waiting, no data loss) until a human acts.
- A node names a profile that does not exist → validation (or run launch) reports the unknown
  profile rather than silently dispatching.
- Authoring tools receive a malformed request (e.g., an edge referencing a node that does
  not exist) → the tool returns a structured error and the stored definition is unchanged.

## Requirements

### Functional Requirements

**Authoring & Versioning**

- **FR-001**: The plugin MUST let a Hermes agent author pipelines via structured tools
  (create graph; add/remove node; add/remove edge; set node, edge, and graph attributes;
  set a node's profile) rather than by hand-writing DOT text.
- **FR-002**: Graphviz DOT MUST be the canonical, portable, stored representation of a
  pipeline; the structured authoring tools emit and patch DOT.
- **FR-003**: Pipelines MUST be stored as git-tracked `.dot` files in a repository the agent
  can access; versioning is delegated to git. If no repository is provided, the plugin MUST
  operate on a local-only repository it initializes.
- **FR-004**: The plugin MUST validate a pipeline against structural and Attractor rules
  (exactly one start node and one exit node, legal node/edge attributes, full reachability,
  goal-gate retry-target sanity, and resolvable profiles) and return actionable errors
  identifying the offending element.
- **FR-005**: The plugin MUST produce a human-readable summary/visualization of a pipeline's
  structure.

**Pipeline Semantics**

- **FR-006**: Node behavior MUST be selected by node shape, supporting at minimum: start,
  exit, codergen (agent work), conditional, tool, parallel fan-out, parallel fan-in, and
  human-in-the-loop.
- **FR-007**: Edge selection during traversal MUST be deterministic, applying priority in
  this order: matching condition, then preferred label, then suggested next node(s), then
  highest edge weight, then a stable lexical tiebreak.
- **FR-008**: A shared context MUST be threaded through stages; each node returns context
  updates that are applied before traversal continues.
- **FR-009**: Goal gates MUST block pipeline exit until every gated node reaches success or
  partial success; an unsatisfied gate MUST route traversal to the configured retry target.
- **FR-010**: Parallel fan-out/fan-in MUST run independent branches concurrently, cloning
  context into each branch and merging branch results by a defined, documented rule.
- **FR-011**: Conditional nodes MUST route based on guards evaluated against the context.
- **FR-012**: Tool nodes MUST invoke deterministic (non-agent) work as a pipeline node and
  feed its result into the context.
- **FR-013**: Human-in-the-loop nodes MUST pause the run for human input and resume when the
  input is supplied.

**Execution & Durability (Hermes Kanban)**

- **FR-014**: The plugin MUST act as a deterministic traversal engine that advances a run in
  response to node (card) completion, persisting run state (current position, context, retry
  counts) so that completed nodes are never re-executed when the engine resumes.
- **FR-015**: Run durability, automatic retries, dependency sequencing, and crash recovery
  MUST be provided by the Hermes Kanban board; the plugin MUST NOT hand-roll its own
  checkpoint store or run a second orchestration system.
- **FR-016**: A node's configured retry limit MUST govern how many times its card's work is
  retried before the run records a terminal failure for that node.
- **FR-017**: A paused human-in-the-loop run MUST survive a restart of the Hermes gateway and
  resume correctly when a human supplies input (no polling by the user, no lost state).
- **FR-018**: The agent MUST be able to launch a run, query its status, and retrieve its
  result/outcome.
- **FR-024**: Run advancement MUST be idempotent and replayable: re-processing a completion
  event (after a restart or duplicate delivery) MUST NOT create duplicate work or double-
  advance a run. Follow-up cards MUST be created with deterministic idempotency keys, and the
  engine MUST persist a durable cursor over the kanban event log so it can resume exactly.

**Profile & Model Selection**

- **FR-019**: Each work node MUST support naming the Hermes **profile** that performs it (the
  card's assignee). The selected profile determines the model used for that node's work.
- **FR-020**: A graph-level stylesheet MUST set profile defaults using selectors by universal
  scope, shape, class, and id with documented specificity precedence; a per-node profile
  (FR-019) overrides stylesheet defaults.

**Node Execution Backend**

- **FR-021**: Codergen (agent-work) nodes MUST be executed by creating a Hermes Kanban card
  assigned to the node's resolved profile, with the expanded prompt as the card body; the
  node's outcome MUST be derived from the card's completion result (summary/metadata). The
  plugin MUST NOT attempt to spawn agent sub-sessions directly (unsupported).
- **FR-022**: Node prompts MUST support variable expansion from the context (e.g., a goal
  placeholder) when forming a card body.

**Plugin Integration**

- **FR-023**: The capability MUST be delivered as a Hermes agent plugin that registers the
  authoring and execution tools; every tool handler returns a JSON result and never raises
  (per the project's `plugin/tools.py` contract).

### Key Entities

- **Pipeline (Graph)**: A directed graph defining a multi-stage workflow. Has exactly one
  start node and one exit node, plus task nodes and directed edges. Stored as a `.dot` file.
- **Node**: A single stage. Its shape selects its handler; carries an optional prompt, a
  profile assignment, a retry limit, and an optional goal-gate flag.
- **Edge**: A directed transition between nodes, with an optional condition (guard), an
  optional routing label, and a weight (priority).
- **Context**: The shared key/value state threaded through the run; nodes read it and return
  updates to it.
- **Outcome**: A node's result — a status (success / partial / fail / retry), optional
  routing hints (preferred label, suggested next nodes), and context updates.
- **Profile**: A named Hermes agent configuration (the kanban card assignee). A node's
  profile determines who — and which model — performs the node's work.
- **Stylesheet**: A graph-level set of selector→profile rules with specificity precedence
  that establishes per-node profile defaults.
- **Card (Kanban Task)**: The durable unit of work the plugin creates for a work node;
  assigned to a profile, worked by the dispatcher-spawned profile worker, completed with a
  result the node consumes.
- **Run**: A single durable execution of a pipeline, with persisted state, a status, and a
  retrievable outcome.

## Success Criteria

- **SC-001**: A Hermes agent can, from a natural-language request, author a multi-node
  pipeline (including at least one branch and one goal gate) that validates clean and is
  persisted as a versioned `.dot` file.
- **SC-002**: A pipeline whose nodes name different profiles (via a stylesheet plus one
  per-node override) runs with the work distributed to those profiles as specified, and the
  per-node override is honored over the stylesheet default.
- **SC-003**: Killing and restarting the Hermes gateway during a run resumes the run without
  re-executing completed nodes and yields the same final outcome.
- **SC-004**: A human-in-the-loop node pauses a run that, after a gateway restart, resumes
  to completion once a human supplies input.
- **SC-005**: A pipeline with a fan-out of N independent branches completes with all N branch
  contributions merged into the context, and the branches run concurrently rather than
  strictly sequentially.
- **SC-006**: The self-hosting reference pipeline (the `sp` workflow as a graph) runs
  end-to-end, demonstrating per-node profiles, goal-gated review loops, parallel review
  lenses, human approval gates, and a tool node — with no external orchestrator beyond the
  Hermes Kanban board.
- **SC-007**: An invalid pipeline (missing start/exit, unreachable node, dangling edge, or
  unknown profile) is rejected with an error that names the offending element, and cannot be
  run.

## Scope

### In Scope

- Authoring tools, DOT canonical format, git-tracked storage with local-only fallback, and
  validation/visualization (FR-001–FR-005).
- The node shapes and traversal semantics in FR-006–FR-013, including parallel fan-out/in,
  human-in-the-loop, and tool nodes.
- Deterministic traversal driven by kanban card completion, with durability/retries/recovery
  provided by the Hermes Kanban board (FR-014–FR-018).
- Per-node profile selection and the profile stylesheet (FR-019–FR-020).
- Kanban-card node execution backend (FR-021–FR-022).
- Delivery as a Hermes plugin honoring the safe-handler contract (FR-023).
- The self-hosting `sp`-workflow reference pipeline as the acceptance anchor.

### Out of Scope (Deferred to Roadmap)

- A second durable orchestrator (e.g., Temporal): the Hermes Kanban board is the sole durable
  substrate for v1.
- Spawning agent sub-sessions directly from the plugin (unsupported by Hermes).
- Per-card / per-task model binding independent of profiles (use profiles for model choice).
- Attractor's coding-agent inner-loop spec beyond what a Hermes profile worker already
  provides (mid-task steering, loop detection, history truncation).
- Pluggable execution environments (Docker / Kubernetes / WASM / RemoteSSH) beyond kanban
  workspace options.
- Context fidelity modes (full / compact / summary tiers) beyond a sane default.
- The supervisor `manager_loop` node.
- A standalone CLI or GUI — the interface is the Hermes plugin.
- A plugin-managed workflow registry — git-tracked `.dot` files only.

## Clarifications

### Session 2026-05-28

- Q: What is the plugin's headline job? → A: Authoring and versioning pipelines is primary;
  durable execution is the secondary-but-real capability.
- Q: Which capabilities beyond the core are must-haves for v1? → A: All of the stylesheet,
  parallel fan-out/fan-in, human-in-the-loop, and tool nodes (full Attractor feature set),
  built as a thin vertical slice first then widened.
- Q: What is the canonical workflow definition format? → A: DOT is canonical and stored;
  authored via structured tools, not hand-written.
- Q: Where do pipelines live and how are they versioned? → A: Git-tracked `.dot` files in a
  repo the agent can access; a local-only repo is initialized if none is provided.
- Q: What concrete reference workflow anchors acceptance? → A: The self-hosting `sp`
  development workflow expressed as an Attractor graph; the kanban board + graph replace the
  external task queue for in-run orchestration, and the "tasks" phase becomes a dynamic
  parallel fan-out over decomposed work items.
- Q: How does a node's work get executed, given the plugin cannot spawn agent sub-sessions?
  → A: Via the Hermes Kanban board — the node creates a card assigned to its profile; the
  kanban dispatcher spawns that profile as a worker; the node consumes the card's completion
  result.
- Q: Is Temporal needed for durable execution? → A: No. The Hermes Kanban board already
  provides durability, retries, dependency sequencing, crash recovery, and human-in-the-loop,
  and it is the mandatory execution mechanism. The plugin is a deterministic traversal engine
  (a reducer over kanban completion events); Temporal is dropped from v1.
- Q: How is "select a model per node" achieved, since kanban assignee is a profile and
  per-card model binding is unavailable? → A: Per-node model selection is expressed as
  per-node **profile** selection; the named profile's configuration determines the model.

## Assumptions

The first three items were **resolved by source verification on 2026-05-28** — see
[research-hermes-kanban.md](./research-hermes-kanban.md) for evidence and the resulting
design. They are recorded here as grounded constraints, not open questions.

- **RESOLVED — Run advancement.** The plugin advances a run by reacting to kanban task
  completion: primarily via a `post_tool_call` hook firing in the worker process after
  `kanban_complete`, with a registered reconcile command that replays the durable
  `task_events` log (`id > last_seen_event_id`) to recover missed advancements. There is no
  built-in kanban plugin hook and no plugin-run daemon, so the engine owns its own durable
  state DB and treats advancement as replayable. (Load-bearing for FR-014/FR-017/FR-024.)
- **RESOLVED — Per-node model.** A Hermes profile carries its own `model.default` in its
  `config.yaml`, and the dispatcher spawns each card's worker as the assigned profile. So
  per-node model selection = per-node profile selection (FR-019/FR-020). Per-*task* model
  override exists internally (`tasks.model_override` + dispatcher `-m`) but is not on the
  public create surface, so it is a roadmap item, not a v1 dependency.
- **RESOLVED — Goal-gate loops.** Loops/conditional re-routing are realized by dynamic card
  creation: each attempt is a new acyclic DAG segment (new task ids), never a cyclic kanban
  link. The plugin owns loop state; idempotency keys keep it replay-safe (FR-009/FR-024).
- The Hermes gateway (with its kanban dispatcher) is running while pipelines execute; `ready`
  cards do not progress without it.
- The real plugin entry-point group is `hermes_agent.plugins` (research finding); the repo's
  current `hermes.plugins` assumption must be reconciled. *(Deferred to planning.)*
- A Graphviz renderer (or pure-Python equivalent) is available for FR-005.
- Context clone/merge conflict-resolution rules for parallel fan-in will be specified in
  planning. *(Deferred to planning.)*
- Exact Attractor and Hermes Kanban identifiers (DOT attribute names, status enums, kanban
  tool/REST/event field names) will be verified against source before being encoded.
  *(Deferred to planning.)*

## Dependencies

- **Hermes agent runtime** with the **Kanban** feature enabled — hosts the plugin, provides
  the durable board, the dispatcher that spawns profile workers, and the completion signal
  the traversal engine reacts to.
- **Hermes profiles** configured for the models the pipelines need.
- **Graphviz** (or equivalent) for visualization.
- **Git** for pipeline versioning.
