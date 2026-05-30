"""LLM-facing JSON schemas for the attractor plugin's tools.

Schema format: ``{"name": ..., "description": ..., "parameters": {<JSON-Schema object>}}``.
The key is ``"parameters"`` (verified against hermes-agent 0.15.2 — NOT ``"input_schema"``).
"""

from __future__ import annotations

HEALTH_SCHEMA: dict[str, object] = {
    "name": "health",
    "description": "Report the attractor plugin's health status and version.",
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

ECHO_SCHEMA: dict[str, object] = {
    "name": "echo",
    "description": "Echo a message back to the caller.",
    "parameters": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The message to echo."},
        },
        "required": ["message"],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# M1 authoring tool schemas
# ---------------------------------------------------------------------------

ATTRACTOR_CREATE_GRAPH_SCHEMA: dict[str, object] = {
    "name": "attractor_create_graph",
    "description": "Create a new empty pipeline graph with the given spec ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Unique identifier for the pipeline spec.",
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root. Defaults to cwd.",
            },
        },
        "required": ["spec_id"],
        "additionalProperties": False,
    },
}

ATTRACTOR_ADD_NODE_SCHEMA: dict[str, object] = {
    "name": "attractor_add_node",
    "description": "Add a node to an existing pipeline graph.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Pipeline spec identifier.",
            },
            "node_id": {
                "type": "string",
                "description": "Unique identifier for the new node.",
            },
            "shape": {
                "type": "string",
                "description": "Node shape: TASK, DECISION, START, or END.",
            },
            "prompt": {
                "type": "string",
                "description": "Optional prompt text for the node.",
            },
            "profile": {
                "type": "string",
                "description": "Optional profile name for the node.",
            },
            "retry_limit": {
                "type": "integer",
                "description": "Optional maximum number of retries (default 0).",
            },
            "class": {
                "type": "string",
                "description": "Optional CSS class for stylesheet styling.",
            },
            "retry_target": {
                "type": "string",
                "description": (
                    "Optional goal-gate retry target node_id. When set, this node becomes a"
                    " goal gate: if the agent returns gate=fail, the run routes back to this"
                    " node for another attempt."
                ),
            },
            "max_attempts": {
                "type": "integer",
                "description": (
                    "Optional goal-gate maximum attempt count (>= 1). Required when retry_target"
                    " is provided. Defaults to 1 if omitted."
                ),
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root.",
            },
        },
        "required": ["spec_id", "node_id", "shape"],
        "additionalProperties": False,
    },
}

ATTRACTOR_REMOVE_NODE_SCHEMA: dict[str, object] = {
    "name": "attractor_remove_node",
    "description": "Remove a node from an existing pipeline graph.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Pipeline spec identifier.",
            },
            "node_id": {
                "type": "string",
                "description": "Identifier of the node to remove.",
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root.",
            },
        },
        "required": ["spec_id", "node_id"],
        "additionalProperties": False,
    },
}

ATTRACTOR_ADD_EDGE_SCHEMA: dict[str, object] = {
    "name": "attractor_add_edge",
    "description": "Add a directed edge between two nodes in a pipeline graph.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Pipeline spec identifier.",
            },
            "source_id": {
                "type": "string",
                "description": "Source node identifier.",
            },
            "target_id": {
                "type": "string",
                "description": "Target node identifier.",
            },
            "condition": {
                "type": "string",
                "description": "Optional condition expression for the edge.",
            },
            "label": {
                "type": "string",
                "description": "Optional display label for the edge.",
            },
            "weight": {
                "type": "integer",
                "description": "Optional edge weight (default 0).",
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root.",
            },
        },
        "required": ["spec_id", "source_id", "target_id"],
        "additionalProperties": False,
    },
}

ATTRACTOR_REMOVE_EDGE_SCHEMA: dict[str, object] = {
    "name": "attractor_remove_edge",
    "description": "Remove a directed edge from a pipeline graph.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Pipeline spec identifier.",
            },
            "source_id": {
                "type": "string",
                "description": "Source node identifier.",
            },
            "target_id": {
                "type": "string",
                "description": "Target node identifier.",
            },
            "label": {
                "type": "string",
                "description": "Optional edge label to disambiguate parallel edges.",
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root.",
            },
        },
        "required": ["spec_id", "source_id", "target_id"],
        "additionalProperties": False,
    },
}

ATTRACTOR_SET_STYLESHEET_SCHEMA: dict[str, object] = {
    "name": "attractor_set_stylesheet",
    "description": "Set the visual stylesheet for a pipeline graph.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Pipeline spec identifier.",
            },
            "rules": {
                "type": "array",
                "description": "List of style rules, each with 'selector' and 'profile'.",
                "items": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "profile": {"type": "string"},
                    },
                    "required": ["selector", "profile"],
                    "additionalProperties": False,
                },
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root.",
            },
        },
        "required": ["spec_id", "rules"],
        "additionalProperties": False,
    },
}

ATTRACTOR_VALIDATE_SCHEMA: dict[str, object] = {
    "name": "attractor_validate",
    "description": "Validate a pipeline graph and report any structural issues.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Pipeline spec identifier.",
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root.",
            },
        },
        "required": ["spec_id"],
        "additionalProperties": False,
    },
}

ATTRACTOR_SUMMARY_SCHEMA: dict[str, object] = {
    "name": "attractor_summary",
    "description": "Retrieve a human-readable summary and DOT representation of a pipeline.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Pipeline spec identifier.",
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root.",
            },
        },
        "required": ["spec_id"],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# M2 execution tool schemas
# ---------------------------------------------------------------------------

ATTRACTOR_RUN_SCHEMA: dict[str, object] = {
    "name": "attractor_run",
    "description": "Launch a new pipeline run for the given spec.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "Pipeline spec identifier to run.",
            },
            "repo_path": {
                "type": "string",
                "description": "Optional path to the git repository root.",
            },
            "context": {
                "type": "object",
                "description": "Optional initial context key-value pairs for the run.",
                "additionalProperties": True,
            },
        },
        "required": ["spec_id"],
        "additionalProperties": False,
    },
}

ATTRACTOR_STATUS_SCHEMA: dict[str, object] = {
    "name": "attractor_status",
    "description": "Query the current status of a pipeline run.",
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Unique identifier of the pipeline run.",
            },
        },
        "required": ["run_id"],
        "additionalProperties": False,
    },
}

ATTRACTOR_RESULT_SCHEMA: dict[str, object] = {
    "name": "attractor_result",
    "description": "Retrieve the outcome of a completed pipeline run.",
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Unique identifier of the pipeline run.",
            },
        },
        "required": ["run_id"],
        "additionalProperties": False,
    },
}
