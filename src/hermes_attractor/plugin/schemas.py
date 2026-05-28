"""LLM-facing JSON schemas for the attractor plugin's tools."""

from __future__ import annotations

HEALTH_SCHEMA: dict[str, object] = {
    "name": "health",
    "description": "Report the attractor plugin's health status and version.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

ECHO_SCHEMA: dict[str, object] = {
    "name": "echo",
    "description": "Echo a message back to the caller.",
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The message to echo."},
        },
        "required": ["message"],
        "additionalProperties": False,
    },
}
