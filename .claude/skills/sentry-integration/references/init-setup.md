# sentry_sdk.init Setup

**Purpose**: Configure Sentry integration with `sentry_sdk.init`, environment-specific settings, and an optional dependency that degrades to a no-op when unavailable.

## When to Use

Use this reference when setting up initial Sentry integration for the application, configuring environment-specific sampling rates, or enabling structured-log integration with Sentry's logging integration.

## Optional Dependency

Keep Sentry out of the core dependency set. Declare it as an optional extra:

```toml
# pyproject.toml
[project.optional-dependencies]
observability = ["sentry-sdk>=2.0"]
```

Install only when needed: `uv pip install "hermes-attractor[observability]"`. The init function below must work whether or not the package is installed.

## Pattern

```python
# src/hermes_attractor/adapters/observability/sentry.py
from __future__ import annotations

import os
from typing import Any


def init_sentry() -> bool:
    """Initialize Sentry if the SDK is installed and a DSN is configured.

    Returns True when Sentry is active, False when it is a no-op. The caller
    should not depend on Sentry being present.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        return False

    environment = os.environ.get("ENVIRONMENT", "development")

    sentry_sdk.init(
        dsn=dsn,
        release=os.environ.get("APP_VERSION"),
        environment=environment,
        # Capture 100% of errors; sample 10% of traces in production.
        traces_sample_rate=0.1 if environment == "production" else 1.0,
        # Do not auto-attach IP, headers, or cookies.
        send_default_pii=False,
        # Don't auto-capture log records as events; we control capture explicitly.
        integrations=[LoggingIntegration(level=None, event_level=None)],
        before_send=_before_send,
        before_breadcrumb=_before_breadcrumb,
    )
    return True


_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "x-api-key", "x-auth-token"})


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_HEADERS else v) for k, v in headers.items()}


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    request = event.get("request")
    if isinstance(request, dict) and isinstance(request.get("headers"), dict):
        request["headers"] = _redact_headers(request["headers"])
    return event


def _before_breadcrumb(crumb: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    if crumb.get("category") == "http":
        data = crumb.get("data")
        if isinstance(data, dict) and isinstance(data.get("headers"), dict):
            data["headers"] = _redact_headers(data["headers"])
    return crumb
```

## Environment Variables

Set these locally (e.g. in a `.env` loaded by your tooling) and in production secrets — never hard-code or commit a DSN:

```bash
SENTRY_DSN=https://<public_key>@<host>/<project_id>
ENVIRONMENT=production
APP_VERSION=1.2.3
```

## Correlating with Structured Logs

Tag every Sentry scope with the same `request_id`/`trace_id` used by the structured-logging skill so events line up across systems:

```python
import sentry_sdk

from hermes_attractor.adapters.logging.context import get_context


def tag_sentry_correlation() -> None:
    ctx = get_context()
    if ctx is None:
        return
    sentry_sdk.set_tag("request_id", ctx.request_id)
    if ctx.trace_id is not None:
        sentry_sdk.set_tag("trace_id", ctx.trace_id)
```

## Common Mistakes

### ❌ Mistake: Adding sentry-sdk to core dependencies

```toml
# Bad - forces Sentry on every install
[project]
dependencies = ["sentry-sdk>=2.0"]
```

**Why it's wrong**: The project must run without Sentry. A hard dependency couples the core to an optional observability concern.

### ✅ Correct: Optional extra + lazy import

```toml
# Good
[project.optional-dependencies]
observability = ["sentry-sdk>=2.0"]
```

```python
try:
    import sentry_sdk
except ImportError:
    return False  # no-op
```

### ❌ Mistake: send_default_pii=True

```python
# Bad - attaches IP, headers, and cookies automatically
sentry_sdk.init(dsn=dsn, send_default_pii=True)
```

**Why it's wrong**: Automatically includes PII in error reports, which may violate privacy regulations.

### ✅ Correct: Explicitly control PII with before_send

```python
# Good
sentry_sdk.init(dsn=dsn, send_default_pii=False, before_send=_before_send)
```

## Testing

```python
# tests/unit/adapters/observability/test_sentry.py
from hermes_attractor.adapters.observability.sentry import init_sentry


def test_init_is_noop_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry() is False


def test_before_send_redacts_authorization_header():
    from hermes_attractor.adapters.observability.sentry import _before_send

    event = {"request": {"headers": {"authorization": "Bearer secret", "accept": "application/json"}}}
    result = _before_send(event, {})

    assert result is not None
    assert result["request"]["headers"]["authorization"] == "[REDACTED]"
    assert result["request"]["headers"]["accept"] == "application/json"
```

## Related References

- [context-management.md](./context-management.md) - Add custom context to Sentry events
- [error-capture.md](./error-capture.md) - Manually capture errors with additional metadata
