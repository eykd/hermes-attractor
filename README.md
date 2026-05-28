# hermes-attractor

A [Hermes Agent](https://github.com/) plugin (`attractor`) built on a hexagonal core.

The plugin's real logic lives in `src/hermes_attractor/` as a hexagonal package
(`domain → ports → adapters → use_cases`); the Hermes coupling is isolated to a thin
`plugin/` shim. It ships via a pip entry point and is symlinked into `.hermes/plugins/`
for local development.

## Quick start

```sh
just install      # uv sync --all-groups
just lint         # ruff check + ruff format --check + pyright (strict)
just test         # pytest at 100% coverage
just ci           # lint + test
just hooks        # install pre-commit hooks
```

## Conventions

Project conventions, architecture rules, and the agent-driven development workflow
(spec-kit `sp/` phases, the `ralph` orchestrator, and skills) are documented in
`CLAUDE.md` and the `.claude/` harness. Toolchain: Python 3.11, `uv`, `ruff`,
`pyright` (strict), `pytest` (100% coverage), `pre-commit`, and `br` (beads) for tasks.
