"""Hermes host boundary: the registration context a plugin's entry point receives.

API verified against ``hermes-agent==0.15.2`` (``hermes_cli.plugins.PluginContext``).
The method signatures below mirror the real runtime exactly. The entry-point
group is ``hermes_agent.plugins`` (matching ``pyproject.toml``).

Hook and CLI-command registration signatures are also verified against 0.15.2 and
included below.  Hook names available in the runtime are documented in
``hermes_cli.plugins.VALID_HOOKS`` (e.g. ``on_session_start``, ``on_session_end``,
``pre_tool_call``, ``post_tool_call``, …).

This module is dependency-free: it defines only Protocols and type aliases so the
hexagonal core stays decoupled from the installed Hermes package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable


class ToolHandler(Protocol):
    """A Hermes tool handler: accepts tool input and returns a JSON string, never raising.

    The runtime invokes handlers as ``handler(args, **kwargs)`` where kwargs
    may include ``task_id``, ``session_id``, and other runtime context values.
    Handlers must tolerate (and ignore) any unknown keyword arguments.
    """

    def __call__(self, args: dict[str, object], **kwargs: object) -> str:
        """Invoke the handler with tool input args and optional runtime kwargs."""
        ...


class PluginContext(Protocol):
    """The registration context passed to a plugin's ``register`` entry point.

    Verified against ``hermes_cli.plugins.PluginContext`` in hermes-agent 0.15.2.
    """

    def register_tool(  # noqa: PLR0913
        self,
        name: str,
        toolset: str,
        schema: dict[str, object],
        handler: ToolHandler,
        check_fn: Callable[..., object] | None = None,
        requires_env: list[str] | None = None,
        is_async: bool = False,  # noqa: FBT001, FBT002
        description: str = "",
        emoji: str = "",
        override: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Register a single LLM-facing tool with its JSON schema and handler.

        Args:
            name: Tool name (unique across the registry unless ``override`` is True).
            toolset: Logical grouping for the tool (e.g. ``"attractor"``). Required.
            schema: Tool schema dict with keys ``name``, ``description``, and
                ``parameters`` (a JSON-Schema object).
            handler: Callable that accepts ``(args: dict, **kwargs)`` and returns a
                JSON string.  Must never raise.
            check_fn: Optional availability check; called before dispatch.
            requires_env: Optional list of env-var names that must be set.
            is_async: Set to True when handler is a coroutine function.
            description: Human-readable description (falls back to schema description).
            emoji: Optional emoji prefix for display.
            override: Allow replacing an existing tool registered under the same name.
        """
        ...

    def register_hook(self, hook_name: str, callback: Callable[..., None]) -> None:
        """Register a lifecycle hook callback.

        Args:
            hook_name: One of the valid hook names (e.g. ``"on_session_start"``).
                Unknown names produce a runtime warning but are still stored.
            callback: Callable invoked with runtime-specific ``**kwargs``.
        """
        ...

    def register_cli_command(
        self,
        name: str,
        help: str,  # noqa: A002
        setup_fn: Callable[..., None],
        handler_fn: Callable[..., None] | None = None,
        description: str = "",
    ) -> None:
        """Register a CLI subcommand (e.g. ``hermes attractor ...``).

        Args:
            name: Subcommand name.
            help: Short help string shown in ``--help`` output.
            setup_fn: Receives an argparse subparser and adds arguments/sub-subparsers.
            handler_fn: If provided, set as the default dispatch function via
                ``set_defaults(func=...)``.
            description: Longer description for documentation.
        """
        ...
