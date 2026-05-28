# Feature Specification: Attractor on Temporal (Hermes Plugin)

**Feature Branch**: `001-attractor-temporal`
**Created**: 2026-05-28
**Status**: Draft
**Brainstorm**: specs/brainstorms/2026-05-28-attractor-hermes-temporal-requirements.md
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
restarts), and **choose a model per stage** (cheap models for routing, strong models for
hard work). StrongDM's *Attractor* defines exactly this — a directed graph of nodes,
traversed by a deterministic engine that invokes agentic work at each node — but ships
only a specification, with hand-rolled durability.

This feature implements Attractor's semantics as a **Hermes agent plugin**. Its headline
value is **authoring and versioning** pipelines: a Hermes agent composes, validates,
visualizes, and versions workflows through structured tools, with Graphviz **DOT** as the
canonical stored artifact. Its second capability is **durable execution on Temporal**:
graph traversal runs as a deterministic Temporal workflow and each node's work runs as a
Temporal activity, so runs recover automatically from failure. Each LLM ("codergen") node
executes via a **Hermes agent session**, and the per-node model selection determines which
model that session uses.

The reference pipeline that anchors acceptance is **self-hosting**: this project's own
`sp` development workflow (specify → plan → red-team → tasks → implement → review/harden)
expressed as an Attractor graph. It exercises every v1 capability — per-node models, goal
gates, parallel fan-out/fan-in, human-in-the-loop, and tool nodes — and demonstrates that
graph topology plus Temporal's durable history replace the external task queue (beads) that
the manual workflow uses today.

## User Scenarios & Testing

### Primary User Story

A developer, working through a Hermes agent, asks the agent to build a pipeline. The agent
uses authoring tools to add nodes (each a stage of work), connect them with edges (some
conditional, some weighted), assign models to nodes (directly or via a stylesheet), and
mark exit-blocking goal gates. The agent validates the pipeline, sees a readable summary of
its structure, and the definition is saved as a versioned `.dot` file. The developer then
asks the agent to run it; the pipeline executes durably, pausing for human approval where
required and recovering transparently if the worker restarts mid-run. The developer can
check status and retrieve the final outcome.

### Acceptance Scenarios

1. **Given** an empty repository, **When** the agent authors a multi-node pipeline with a
   branch and a goal gate, **Then** the pipeline validates clean and is saved as a
   git-tracked `.dot` file (a local-only repository is initialized if none was provided).
2. **Given** a pipeline whose nodes specify different models (some via a model stylesheet,
   one via a per-node override), **When** it runs, **Then** each node's work is performed by
   a Hermes agent session using the model resolved for that node, and the override takes
   precedence over the stylesheet default.
3. **Given** a running pipeline, **When** the executing worker is killed and restarted
   mid-run, **Then** the run resumes without re-executing already-completed nodes and
   reaches the same outcome.
4. **Given** a pipeline containing a human-in-the-loop node, **When** traversal reaches that
   node, **Then** the run pauses awaiting human input, survives a restart while paused, and
   resumes when the input is supplied.
5. **Given** a pipeline with a parallel fan-out and fan-in, **When** it runs, **Then** the
   independent branches execute concurrently and their context contributions are merged
   before traversal continues.
6. **Given** a pipeline with a goal-gated node that has not yet succeeded, **When** traversal
   would otherwise reach the exit, **Then** the run is routed back per the gate's retry
   target rather than exiting, and exits only once the gated node reaches success or
   partial success.
7. **Given** a pipeline containing a tool node, **When** traversal reaches it, **Then** the
   deterministic tool work runs as a graph stage and its result updates the shared context.
8. **Given** the self-hosting reference pipeline (the `sp` workflow as a graph), **When** it
   runs end-to-end, **Then** it produces the expected per-phase outputs, routes review
   lenses in parallel, pauses at approval gates, and exits only when its review goal gates
   are satisfied.

### Edge Cases

- An invalid graph (no start node, multiple exits, an unreachable node, an edge to a missing
  node, or a goal gate with no reachable retry target) is rejected by validation with an
  actionable error and is not runnable.
- A node exhausts its allowed retries → the run records a terminal failure outcome and stops
  cleanly with a reported reason.
- Parallel branches produce conflicting updates to the same context key → resolved by a
  defined, documented merge rule rather than silently.
- A human-in-the-loop node receives no input for an extended period → the run remains
  durably paused (no busy-waiting, no data loss) until input arrives.
- Authoring tools receive a malformed request (e.g., an edge referencing a node that does
  not exist) → the tool returns a structured error and the stored definition is unchanged.

## Requirements

### Functional Requirements

**Authoring & Versioning**

- **FR-001**: The plugin MUST let a Hermes agent author pipelines via structured tools
  (create graph; add/remove node; add/remove edge; set node, edge, and graph attributes;
  set a node's model) rather than by hand-writing DOT text.
- **FR-002**: Graphviz DOT MUST be the canonical, portable, stored representation of a
  pipeline; the structured authoring tools emit and patch DOT.
- **FR-003**: Pipelines MUST be stored as git-tracked `.dot` files in a repository the agent
  can access; versioning is delegated to git. If no repository is provided, the plugin MUST
  operate on a local-only repository it initializes.
- **FR-004**: The plugin MUST validate a pipeline against structural and Attractor rules
  (exactly one start node and one exit node, legal node/edge attributes, full reachability,
  goal-gate retry-target sanity) and return actionable errors identifying the offending
  element.
- **FR-005**: The plugin MUST produce a human-readable summary/visualization of a pipeline's
  structure.

**Pipeline Semantics**

- **FR-006**: Node behavior MUST be selected by node shape, supporting at minimum: start,
  exit, codergen (LLM), conditional, tool, parallel fan-out, parallel fan-in, and
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
- **FR-012**: Tool nodes MUST invoke deterministic (non-LLM) work as a graph stage and feed
  its result into the context.
- **FR-013**: Human-in-the-loop nodes MUST pause the run for human input and resume when the
  input is supplied.

**Execution & Durability**

- **FR-014**: Graph traversal MUST execute as a deterministic durable workflow, and each
  node's work MUST execute as a separately recorded unit, so that completed nodes are never
  re-executed on recovery.
- **FR-015**: The orchestrator MUST provide durability, automatic retries, and crash
  recovery for runs, replacing any need for the plugin to hand-roll checkpointing or backoff.
- **FR-016**: A node's configured retry limit MUST govern how many times its work is retried
  before the run records a terminal failure for that node.
- **FR-017**: A paused human-in-the-loop run MUST survive restarts of the executing process
  and resume correctly when input arrives (no polling, no lost state).
- **FR-018**: The agent MUST be able to launch a run, query its status, and retrieve its
  result/outcome.

**Model Selection**

- **FR-019**: Each node MUST support model selection via node attributes (model, provider,
  and reasoning-effort intent).
- **FR-020**: A graph-level model stylesheet MUST set model defaults using selectors by
  universal scope, shape, class, and id with documented specificity precedence; per-node
  attributes (FR-019) override stylesheet defaults.

**Node Execution Backend**

- **FR-021**: Codergen (and other LLM) nodes MUST perform their work via a Hermes agent
  session; the model resolved for the node (FR-019/FR-020) determines the model that session
  uses.
- **FR-022**: Node prompts MUST support variable expansion from the context (e.g., a goal
  placeholder).

**Plugin Integration**

- **FR-023**: The capability MUST be delivered as a Hermes agent plugin that registers the
  authoring and execution tools; every tool handler returns a JSON result and never raises
  (per the project's `plugin/tools.py` contract).

### Key Entities

- **Pipeline (Graph)**: A directed graph defining a multi-stage workflow. Has exactly one
  start node and one exit node, plus task nodes and directed edges. Stored as a `.dot` file.
- **Node**: A single stage. Carries a shape (selecting its handler), an optional prompt,
  model-selection attributes, a retry limit, and an optional goal-gate flag.
- **Edge**: A directed transition between nodes. Carries an optional condition (guard), an
  optional routing label, and a weight (priority).
- **Context**: The shared key/value state threaded through the run; nodes read it and return
  updates to it.
- **Outcome**: A node's result — a status (e.g., success / partial / fail / retry), optional
  routing hints (preferred label, suggested next nodes), and context updates.
- **Model Stylesheet**: A graph-level set of selector→model rules with specificity
  precedence that establishes per-node model defaults.
- **Run**: A single durable execution of a pipeline, with status and a retrievable outcome.

## Success Criteria

- **SC-001**: A Hermes agent can, from a natural-language request, author a multi-node
  pipeline (including at least one branch and one goal gate) that validates clean and is
  persisted as a versioned `.dot` file.
- **SC-002**: A pipeline using a model stylesheet plus one per-node override runs with at
  least two distinct models actually used across its nodes, and the override is honored over
  the stylesheet default.
- **SC-003**: Killing and restarting the executing process during a run resumes the run
  without re-executing completed nodes and yields the same final outcome.
- **SC-004**: A human-in-the-loop node pauses a run that, after a process restart, resumes
  to completion once human input is supplied.
- **SC-005**: A pipeline with a fan-out of N independent branches completes with all N branch
  contributions merged into the context, and the branches run concurrently rather than
  strictly sequentially.
- **SC-006**: The self-hosting reference pipeline (the `sp` workflow as a graph) runs
  end-to-end, demonstrating per-node models, goal-gated review loops, parallel review lenses,
  human approval gates, and a tool node — with no external task queue required for
  orchestration.
- **SC-007**: An invalid pipeline (missing start/exit, unreachable node, or dangling edge) is
  rejected at validation with an error that names the offending element, and cannot be run.

## Scope

### In Scope

- Authoring tools, DOT canonical format, git-tracked storage with local-only fallback, and
  validation/visualization (FR-001–FR-005).
- The node shapes and traversal semantics in FR-006–FR-013, including parallel fan-out/in,
  human-in-the-loop, and tool nodes.
- Durable execution, recovery, retries, and run control on the durable orchestrator
  (FR-014–FR-018).
- Per-node model selection and the model stylesheet (FR-019–FR-020).
- Hermes-agent-session node execution backend (FR-021–FR-022).
- Delivery as a Hermes plugin honoring the safe-handler contract (FR-023).
- The self-hosting `sp`-workflow reference pipeline as the acceptance anchor.

### Out of Scope (Deferred to Roadmap)

- Attractor's coding-agent inner-loop spec beyond what a Hermes agent session already
  provides (mid-task steering, loop detection, history truncation).
- Pluggable execution environments (Docker / Kubernetes / WASM / RemoteSSH).
- Context fidelity modes (full / compact / summary tiers) beyond a sane default.
- The supervisor `manager_loop` node.
- A direct (non-Hermes) LLM client backend.
- A standalone CLI or GUI — the interface is the Hermes plugin.
- A plugin-managed workflow registry — git-tracked `.dot` files only.
- Using beads (or any external task queue) for orchestration *inside* a run.

## Clarifications

### Session 2026-05-28

- Q: What is the plugin's headline job? → A: Authoring and versioning pipelines is primary;
  durable execution is the secondary-but-real capability.
- Q: What executes each LLM node's work (what does a per-node model select)? → A: A Hermes
  agent session per node; the per-node model is that session's model.
- Q: Which capabilities beyond the core are must-haves for v1? → A: All of model stylesheet,
  parallel fan-out/fan-in, human-in-the-loop, and tool nodes (full Attractor feature set),
  built as a thin vertical slice first then widened.
- Q: What is the canonical workflow definition format? → A: DOT is canonical and stored;
  authored via structured tools, not hand-written.
- Q: Where do pipelines live and how are they versioned? → A: Git-tracked `.dot` files in a
  repo the agent can access; a local-only repo is initialized if none is provided.
- Q: What concrete reference workflow anchors acceptance? → A: The self-hosting `sp`
  development workflow (specify → plan → red-team → tasks → implement → review/harden)
  expressed as an Attractor graph; beads is NOT used for orchestration inside a run —
  graph topology plus the durable orchestrator's history replace it, and the "tasks" phase
  becomes a dynamic parallel fan-out over decomposed work items.

## Assumptions

- The Hermes runtime can spawn/drive an agent session programmatically with a caller-chosen
  model. This is load-bearing for FR-021 and is currently **unverified** (the Hermes CLI is
  not yet installed). *(Deferred to planning: feasibility, process model, auth, concurrency.)*
- The real plugin entry-point group is `hermes_agent.plugins` (research finding); the repo's
  current `hermes.plugins` assumption must be reconciled. *(Deferred to planning.)*
- A durable-execution orchestrator (Temporal) and its worker are available in the target
  environment. *(Deferred to planning: runtime ownership, dev server vs hosted, worker
  lifecycle.)*
- A Graphviz renderer (or pure-Python equivalent) is available for FR-005.
- Context clone/merge conflict-resolution rules for parallel fan-in will be specified in
  planning. *(Deferred to planning.)*
- The human-in-the-loop interaction surface (how a human is prompted and how the response
  reaches the paused run) will be specified in planning. *(Deferred to planning.)*
- Exact Attractor spec identifiers (attribute names, status enums, fidelity strings) will be
  verified against the raw NLSpec markdown before being encoded. *(Deferred to planning.)*

## Dependencies

- **Hermes agent runtime** — host for the plugin and backend for node execution (unverified).
- **Temporal** (durable execution orchestrator) plus a worker process.
- **Graphviz** (or equivalent) for visualization.
- **Git** for pipeline versioning.
