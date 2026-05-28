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

A `box`-shaped node whose work is performed by an LLM — in this project, via a **Hermes
agent session**. The node's resolved model determines that session's model.
*Avoid*: "LLM node" (use only descriptively), "agent step".

## Goal Gate

A flag marking a node that must reach success or partial success before the pipeline may
exit. An unsatisfied gate routes traversal to a retry target.
*Avoid*: "exit condition", "checkpoint".

## Model Stylesheet

A graph-level set of selector→model rules (universal / shape / class / id) with specificity
precedence that sets per-node model defaults. Per-node attributes override it.
*Avoid*: "model config", "model map".

## Run

A single durable execution of a pipeline on the orchestrator, with a status and a
retrievable outcome.
*Avoid*: "execution", "job", "instance" (informal).

## Fan-out / Fan-in

**Fan-out** spawns concurrent independent branches (each with a cloned context); **fan-in**
merges branch contributions back into a single context by a defined rule.
*Avoid*: "parallel/join", "split/merge".

## Human-in-the-loop (node)

A node that durably pauses a run awaiting human input and resumes when input is supplied.
*Avoid*: "wait node", "approval step" (use only descriptively).
