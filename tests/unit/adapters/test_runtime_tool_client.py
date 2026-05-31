"""Unit tests for RuntimeToolClient.

The dispatch callable is injected, so these tests cover the full call surface with a
fake dispatch that mimics ``tools.registry.registry.dispatch`` (returns a JSON string).
"""

from __future__ import annotations

import json

import pytest

from hermes_attractor.adapters.runtime_tool_client import RuntimeToolClient

pytestmark = pytest.mark.unit


class _FakeDispatch:
    """A fake registry dispatch returning a preset JSON string and recording calls."""

    def __init__(self, response: object) -> None:
        """Initialise with the response object to JSON-encode and return.

        Args:
            response: The object the fake dispatch returns (JSON-encoded).
        """
        super().__init__()
        self._response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, tool_name: str, args: dict[str, object]) -> str:
        """Record the call and return the preset response as a JSON string.

        Args:
            tool_name: The dispatched tool name.
            args: The tool args dict.

        Returns:
            The preset response, JSON-encoded.
        """
        self.calls.append((tool_name, dict(args)))
        return json.dumps(self._response)


def test_call_forwards_tool_name_and_kwargs_as_args_dict() -> None:
    """RuntimeToolClient.call dispatches the tool name with kwargs collected into args."""
    dispatch = _FakeDispatch({"ok": True, "task_id": "t_abc"})
    client = RuntimeToolClient(dispatch=dispatch)

    result = client.call("kanban_create", title="A", assignee="coder", parents=["p1"])

    assert dispatch.calls == [("kanban_create", {"title": "A", "assignee": "coder", "parents": ["p1"]})]
    assert result == {"ok": True, "task_id": "t_abc"}


def test_call_parses_json_string_response_into_object() -> None:
    """RuntimeToolClient.call JSON-decodes the dispatch string response."""
    dispatch = _FakeDispatch({"ok": True, "run_id": 7})
    client = RuntimeToolClient(dispatch=dispatch)

    result = client.call("kanban_complete", task_id="t1", summary="done")

    assert isinstance(result, dict)
    assert result["run_id"] == 7
