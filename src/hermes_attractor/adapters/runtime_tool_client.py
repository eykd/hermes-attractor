"""RuntimeToolClient: a HermesToolClient backed by the Hermes tool registry's dispatch.

Wraps the verified runtime dispatch seam ``tools.registry.registry.dispatch(name, args)``
(hermes-agent 0.15.2), which returns a JSON string. This adapter parses that string back
into a dict so the kanban adapters receive a structured response.

The ``dispatch`` callable is injected (not imported) so this module never imports
``tools.registry``: production wiring passes ``registry.dispatch`` from the plugin shim,
while unit tests pass a fake dispatch. See
``specs/001-attractor-kanban/research-hermes-kanban.md`` §Phase 1 (A).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["RuntimeToolClient"]

_log = logging.getLogger(__name__)


class RuntimeToolClient:
    """HermesToolClient that dispatches tools through the runtime registry.

    Attributes:
        _dispatch: Callable matching ``registry.dispatch(name, args, **kwargs) -> str``.
    """

    def __init__(self, dispatch: Callable[..., str]) -> None:
        """Initialise with the registry dispatch callable.

        Args:
            dispatch: A callable ``(tool_name, args_dict, **kwargs) -> json_str`` — the
                runtime's ``registry.dispatch``.
        """
        super().__init__()
        self._dispatch = dispatch

    def call(self, tool_name: str, **kwargs: Any) -> Any:  # noqa: ANN401
        """Invoke a Hermes tool by name and return its parsed (decoded) response.

        Args:
            tool_name: The Hermes tool identifier (e.g. ``"kanban_create"``).
            **kwargs: Tool-specific arguments forwarded as the dispatch ``args`` dict.

        Returns:
            The tool's response payload, JSON-decoded (typically a dict).
        """
        raw = self._dispatch(tool_name, dict(kwargs))
        return json.loads(raw)
