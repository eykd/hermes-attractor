---
name: sentry-integration
description: "Use when: (1) Integrating Sentry via sentry-sdk as an optional, no-op-by-default adapter, (2) Configuring sentry_sdk.init with environment-aware sampling, (3) Adding custom context/tags or breadcrumbs, (4) Capturing errors manually with request_id/trace_id correlation."
---

# Sentry Integration

**Use when:** Integrating Sentry for rich error tracking with breadcrumbs and context while maintaining structured-log correlation.

## Overview

This skill guides you through integrating Sentry with a Python application using the `sentry-sdk` package. It covers `sentry_sdk.init` configuration with environment-specific sampling, custom context (user/tags/extra), breadcrumb patterns for debugging, and manual error capture with metadata. All patterns integrate with the structured-logging skill via `request_id`/`trace_id` correlation.

**This project adds NO hard dependency on Sentry.** Treat `sentry-sdk` as an optional adapter:

- Keep all Sentry code behind a lazy import in an adapter module (`src/hermes_attractor/adapters/observability/`), guarded by `try/except ImportError`.
- If `sentry-sdk` is not installed or no DSN is configured, the adapter becomes a no-op so the application runs unchanged.
- Add `sentry-sdk` only to an optional dependency group (e.g. `[project.optional-dependencies] observability`), never to the core `dependencies`.

## Decision Tree

### Need to set up Sentry?

**When**: Configuring initial Sentry integration with `sentry_sdk.init` and environment variables
**Go to**: [references/init-setup.md](./references/init-setup.md)

### Need to add custom context?

**When**: Setting user context, tags, or request metadata for error correlation
**Go to**: [references/context-management.md](./references/context-management.md)

### Need to track events?

**When**: Adding breadcrumbs to understand the sequence of events leading to errors
**Go to**: [references/breadcrumbs.md](./references/breadcrumbs.md)

### Need to capture errors manually?

**When**: Capturing exceptions with custom tags, extra data, and severity levels
**Go to**: [references/error-capture.md](./references/error-capture.md)

## Quick Example

```python
# src/hermes_attractor/adapters/observability/sentry.py
from __future__ import annotations

import os
from typing import Any


def init_sentry() -> bool:
    """Initialize Sentry if available and configured. Returns True if active."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        return False  # optional dependency not installed → no-op

    environment = os.environ.get("ENVIRONMENT", "development")
    sentry_sdk.init(
        dsn=dsn,
        release=os.environ.get("APP_VERSION"),
        environment=environment,
        traces_sample_rate=0.1 if environment == "production" else 1.0,
        send_default_pii=False,
        integrations=[LoggingIntegration(level=None, event_level=None)],
        before_send=_before_send,
    )
    return True


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    # Redact sensitive headers before the event leaves the process.
    headers = event.get("request", {}).get("headers")
    if isinstance(headers, dict):
        for name in ("authorization", "cookie", "x-api-key"):
            if name in headers:
                headers[name] = "[REDACTED]"
    return event
```

## Cross-References

- **[structured-logging](../structured-logging/SKILL.md)**: Correlate Sentry events with structured logs via `request_id` and `trace_id`
- **[pii-redaction](../pii-redaction/SKILL.md)**: Reuse redaction helpers in `before_send`/`before_breadcrumb` hooks

## Reference Files

- [references/init-setup.md](./references/init-setup.md) - Configure `sentry_sdk.init` with environment-specific settings and optional dependency
- [references/context-management.md](./references/context-management.md) - Set user context, tags, and custom context for error correlation
- [references/breadcrumbs.md](./references/breadcrumbs.md) - Add breadcrumbs to track event sequences and user actions
- [references/error-capture.md](./references/error-capture.md) - Manually capture exceptions with tags, extra data, and severity levels
