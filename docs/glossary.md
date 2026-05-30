# Glossary — Ubiquitous Language

Canonical domain terms for `hermes-attractor`. Use these names in code, specs, and docs.
Avoid the listed synonyms.

## Pipeline

A directed graph defining a multi-stage AI/agent workflow, with exactly one start node and
one exit node. The canonical stored form is a Graphviz **DOT** file.
*Avoid*: "workflow graph", "flow", "DAG" (a pipeline may contain loops via retry routing).

## Node

A single stage of a pipeline. Its **shape** selects its handler (start, exit, codergen,
conditional, tool, fan-out, fan-in, human-in-the-loop). Carries an optional prompt,
model-selection attributes, a retry limit, and an optional goal-gate flag.
*Avoid*: "step", "stage" (informal), "task" (reserved for beads/dev-workflow tasks).

## Edge

A directed transition between two nodes, carrying an optional **condition** (guard), an
optional routing **label**, and a **weight** (priority).
*Avoid*: "link", "arrow", "transition" (informal).

## Context

The shared key/value state threaded through a run. Nodes read it and return updates.
*Avoid*: "state bag", "blackboard", "memory".

## Outcome

A node handler's result: a **status** (success / partial / fail / retry), optional routing
hints (preferred label, suggested next nodes), and context updates.
*Avoid*: "result", "return value".

## Codergen (node)

A `box`-shaped node whose work is performed by an agent — in this project, via a **Hermes
Kanban card** assigned to the node's profile. The kanban dispatcher spawns that profile as a
worker; the node's outcome is derived from the card's completion result.
*Avoid*: "LLM node" (use only descriptively), "agent step".

## Profile

A named Hermes agent configuration. A work node names the **profile** that performs it (the
card's **assignee**), and the profile's configuration determines the model used. "Select a
model per node" is realized as "select a profile per node".
*Avoid*: "agent role", "persona", "worker type".

## Card (Kanban Task)

The durable unit of work the plugin creates for a work node on the Hermes Kanban board.
Carries the assignee (profile), body (expanded prompt), status, retry limit, and result. The
node's **Outcome** is read from the card's completion summary/metadata.
*Avoid*: "ticket", "job", "kanban item".

## Goal Gate

A flag marking a node that must reach success or partial success before the pipeline may
exit. An unsatisfied gate routes traversal to a retry target.
*Avoid*: "exit condition", "checkpoint".

## Stylesheet (Profile Stylesheet)

A graph-level set of selector→profile rules (universal / shape / class / id) with specificity
precedence that sets per-node profile defaults. A per-node profile assignment overrides it.
*Avoid*: "model stylesheet", "profile config", "profile map".

## Run

A single durable execution of a pipeline, backed by the Hermes Kanban board, with persisted
state, a status, and a retrievable outcome.
*Avoid*: "execution", "job", "instance" (informal).

## Fan-out / Fan-in

**Fan-out** spawns concurrent independent branches (each with a cloned context); **fan-in**
merges branch contributions back into a single context by a defined rule.
*Avoid*: "parallel/join", "split/merge".

## Human-in-the-loop (node)

A node that durably pauses a run awaiting human input and resumes when input is supplied.
*Avoid*: "wait node", "approval step" (use only descriptively).
