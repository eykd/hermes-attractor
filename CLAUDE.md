# hermes-attractor Development Conventions

## What this is

`hermes-attractor` is a **Hermes Agent plugin** (`attractor`) built on a hexagonal core.
The plugin's real logic lives in `src/hermes_attractor/` as pure Python; the Hermes
runtime coupling is isolated to a thin `plugin/` shim. It ships via a pip entry point
(`hermes_agent.plugins` group) and is symlinked into `.hermes/plugins/attractor` for local dev.

## Active Technologies

- **Language**: Python 3.11 (pinned via `.python-version`; `requires-python = ">=3.11,<3.12"`)
- **Package/Env manager**: `uv`
- **Linting/format**: `ruff` (120-char line length, `py311` target)
- **Type checking**: `pyright` in **strict mode** + paranoid escalations (run `uv run pyright`)
- **Testing**: `pytest` with a **100% coverage** requirement (branch coverage on)
- **Pre-commit**: ruff, ruff-format, pyright, pytest (100%) — never bypass
- **Tasks**: `br` (beads) — task graph in `.beads/` (git-tracked)

## Architecture

Hexagonal (ports & adapters). Dependencies point inward: `domain ← use_cases`,
`use_cases → ports`, `adapters → ports`, and only `plugin/` knows about Hermes.

```
src/hermes_attractor/
├── domain/      # Entities, value objects, exceptions. ZERO external deps. Pure rules.
├── ports/       # Protocols / interfaces (coverage-omitted). Contracts for the outside.
├── adapters/    # Concrete implementations of ports (system clock, I/O, clients).
├── use_cases/   # Application orchestration over domain + ports.
└── plugin/      # Hermes entry shim — the ONLY Hermes-coupled layer.
    ├── plugin.yaml   # Manifest (name/version/description/provides_tools/requires_env)
    ├── __init__.py   # register(ctx): wires schemas -> handlers
    ├── schemas.py    # LLM-facing tool JSON schemas
    └── tools.py      # Handlers: call use_cases, return a JSON string, NEVER raise
```

**The `plugin/tools.py` contract**: every handler takes parsed tool input, **always
returns a JSON string, and never raises** (it catches `Exception` and returns an error
payload). This is why `tools.py` carries a targeted ruff per-file-ignore (`BLE001`,
`ARG001`). Keep handlers thin — delegate real work to `use_cases`.

## Code Conventions

- **Imports**: absolute from the package root, e.g. `from hermes_attractor.domain.exceptions import AttractorError`.
- **Type hints**: complete and strict. Type-only imports go under `if TYPE_CHECKING:`
  (enforced by ruff `TC`). Use `# pyright: ignore[reportX]` (not `# type: ignore`) when a
  suppression is genuinely needed — `reportUnnecessaryTypeIgnoreComment` is an error.
- **Errors**: raise domain exceptions from `hermes_attractor.domain.exceptions`
  (`AttractorError` base). Use `msg = "..."; raise XError(msg)` (ruff `EM`).
- **Docstrings**: Google style; module/class/function docstrings required (ruff `D`).
- **No `print`** in library code (ruff `T20`); use `logging`.

## Quality gate (always)

`ruff check` + `ruff format --check` + `uv run pyright` (strict) + `uv run pytest` (100%).
Enforced in pre-commit AND via PostToolUse hooks after every Edit/Write. **Never** use
`--no-verify` / `--no-gpg-sign`; fix the underlying issue.

```bash
just install   # uv sync --all-groups
just lint       # ruff check + ruff format --check + pyright
just format     # ruff format + ruff check --fix
just test       # pytest at 100% coverage
just ci         # lint + test
just hooks      # install pre-commit hooks
```

## Development workflow

This repo uses the spec-kit (`sp/`) phases, the `ralph` in-session orchestrator, and
beads, all wired through the `.claude/` harness.

- **Spec-kit**: `/sp:next` advances the workflow; phases run constitution → brainstorm →
  specify → plan → red-team → tasks → analyze → implement → harden. Tasks land in beads.
- **ralph**: `/ralph` drains the beads ready-queue, dispatching prep → worker → verify
  per task within the session.
- **TDD loop**: RED (write a failing test via `/pytest-*` or `/test-driven-development`)
  → GREEN (minimal code; use `/prefactoring` first) → REFACTOR (use `/refactoring`,
  keep 100% coverage) → commit (`/commit`).

### Required skill usage
- **`/prefactoring`** when designing modules, types, or APIs.
- **`/ddd-domain-modeling`** when building the domain layer (entities, value objects, ports).
- **`/refactoring`** during the REFACTOR step.
- **`/error-handling-patterns`** when designing exception hierarchies / safe responses.
- **`/architecture-review`** to validate hexagonal boundaries before merging.

## Beads task tracking (`br`)

```bash
br ready                 # tasks ready to work (no blockers)
br list                  # all tasks
br create "Task"         # create a task
br show <id>             # task details
br close <id>            # close a completed task
br dep <id> blocks <id>  # add a dependency
br sync --flush-only     # flush state to .beads/ (git-friendly JSONL)
```

The `.beads/` directory is git-tracked.

## Open items (Hermes runtime integration)

The `hermes` CLI is **not yet installed**, so live plugin loading is unverified:
- The entry-point group has been reconciled to `hermes_agent.plugins` (was `hermes.plugins`)
  based on research findings (R-EP). The `plugin.yaml` manifest schema is still an assumption
  — reconcile with Hermes docs/source once available.
- `src/hermes_attractor/ports/hermes.py::PluginContext` encodes our assumed registration
  API. Revisit when the real Hermes context is available.
- Local dev discovery uses the `.hermes/plugins/attractor` symlink (no entry point needed).

## Meta-conventions

- **Do NOT** track the active tech stack as a changelog here — update only on genuine change.
- **Do NOT** record recent changes in CLAUDE.md; it is for conventions, not history.
