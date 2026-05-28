# URL Sanitization

**Purpose**: Redact sensitive data from URLs before logging (query parameters, path segments containing tokens).

## Core URL Redaction Function

```python
# src/hermes_attractor/adapters/logging/url_redaction.py
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "[REDACTED]"

SENSITIVE_PARAMS: frozenset[str] = frozenset({
    "token",
    "key",
    "api_key",
    "apikey",
    "password",
    "secret",
    "auth",
    "access_token",
    "refresh_token",
    "code",   # OAuth codes
    "state",  # OAuth state (may contain sensitive data)
})

_TOKEN_LIKE = re.compile(r"^[a-zA-Z0-9_-]{32,}$")


def redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[INVALID_URL]"

    # Redact sensitive query parameters
    query_pairs = [
        (key, REDACTED if key.lower() in SENSITIVE_PARAMS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    query = urlencode(query_pairs)

    # Redact path segments that look like tokens
    segments = ["[ID]" if _TOKEN_LIKE.match(seg) else seg for seg in parts.path.split("/")]
    path = "/".join(segments)

    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))
```

## Query Parameter Redaction

### Sensitive Parameter Detection

Common sensitive parameters to redact:

- **Authentication**: `token`, `auth`, `api_key`, `access_token`, `refresh_token`
- **OAuth**: `code`, `state` (contain authorization codes or sensitive state)
- **Secrets**: `secret`, `password`, `key`

**Example**:

```python
redact_url("https://api.example.com/auth?token=abc123&user=john")
# → "https://api.example.com/auth?token=%5BREDACTED%5D&user=john"
```

### Custom Parameter Sets

Extend for domain-specific parameters:

```python
PROJECT_SENSITIVE_PARAMS = SENSITIVE_PARAMS | {"session_id", "webhook_secret", "api_secret"}
```

## Path Segment Redaction

### Token Detection Heuristic

Redacts path segments that match:

- Length ≥32 characters
- Only alphanumeric, underscore, or hyphen characters
- Pattern: `^[a-zA-Z0-9_-]{32,}$`

**Rationale**: Most tokens (JWT, session IDs, API keys) are long random strings. 32 characters is a conservative threshold that catches most tokens while avoiding false positives.

**Example**:

```python
redact_url("https://api.example.com/users/abc123def456ghi789jkl012mno345pqr678")
# → "https://api.example.com/users/[ID]"
```

### False Positive Mitigation

**Problem**: Some legitimate IDs may be long strings.

**Solution**: Use context-aware detection that skips known resource names:

```python
_KNOWN_RESOURCES = frozenset({"users", "tasks", "orders"})


def _redact_segment(segment: str) -> str:
    if segment in _KNOWN_RESOURCES:
        return segment
    if _TOKEN_LIKE.match(segment):
        return "[ID]"
    return segment
```

## Integration with Logging

### Request Logging

```python
from hermes_attractor.adapters.logging.url_redaction import redact_url

logger.info(
    "request received",
    extra={"event": "http.request.received",
           "fields": {"category": "application", "http_method": request.method,
                      "http_path": urlsplit(request.url).path,  # path only, no query
                      "http_url": redact_url(request.url)}},     # full URL, redacted
)
```

### Sentry Context

```python
import sentry_sdk

from hermes_attractor.adapters.logging.url_redaction import redact_url


def set_sentry_context(request: Request) -> None:
    sentry_sdk.set_context("request", {
        "method": request.method,
        "url": redact_url(request.url),
    })
```

## Advanced URL Sanitization

### Redacting All Query Parameters

For maximum safety, strip the entire query string:

```python
def strip_all_query_params(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[INVALID_URL]"
    query = "[QUERY_REDACTED]" if parts.query else ""
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
```

**Output**: `https://api.example.com/auth?token=abc&user=john` → `https://api.example.com/auth?[QUERY_REDACTED]`

## Testing URL Sanitization

```python
# tests/unit/adapters/logging/test_url_redaction.py
from hermes_attractor.adapters.logging.url_redaction import redact_url


def test_redacts_sensitive_query_parameters():
    result = redact_url("https://api.example.com/auth?token=abc123&user=john")
    assert "token=%5BREDACTED%5D" in result
    assert "user=john" in result


def test_redacts_long_path_segments():
    result = redact_url("https://api.example.com/users/abc123def456ghi789jkl012mno345pqr678")
    assert "[ID]" in result


def test_preserves_short_path_segments():
    assert redact_url("https://api.example.com/users/123") == "https://api.example.com/users/123"


def test_handles_multiple_sensitive_parameters():
    result = redact_url("https://api.example.com/oauth?code=abc&state=xyz&user=john")
    assert "code=%5BREDACTED%5D" in result
    assert "state=%5BREDACTED%5D" in result
    assert "user=john" in result
```

## Performance Considerations

- **URL parsing**: `urlsplit` is fast; it raises `ValueError` only for malformed input
- **Regex evaluation**: path segment detection adds O(n) overhead per segment
- **Query iteration**: O(n) per parameter

For high-throughput scenarios, cache redacted URLs with a bounded `lru_cache`:

```python
from functools import lru_cache


@lru_cache(maxsize=1024)
def cached_redact_url(url: str) -> str:
    return redact_url(url)
```

## Compliance Alignment

URL sanitization aligns with:

- **OWASP Logging Cheat Sheet**: never log authentication tokens or session identifiers in URLs
- **RFC 3986 Section 7.5**: URI producers should not include sensitive data in URIs
- **GDPR Article 32**: pseudonymization of personal data (URL parameters may contain PII)

## Common Pitfalls

❌ **Logging full URLs without redaction**:

```python
logger.info("request", extra={"fields": {"url": request.url}})  # may contain tokens!
```

✅ **Always redact URLs**:

```python
logger.info("request", extra={"fields": {"url": redact_url(request.url)}})
```

❌ **Only redacting one known parameter**:

```python
# Misses every other sensitive parameter
query_pairs = [(k, v) for k, v in pairs if k != "token"]
```

✅ **Comprehensive redaction via set membership**:

```python
query_pairs = [(k, REDACTED if k.lower() in SENSITIVE_PARAMS else v) for k, v in pairs]
```
