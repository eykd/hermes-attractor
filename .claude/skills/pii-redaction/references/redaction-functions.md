# Redaction Functions

**Purpose**: Core helpers for redacting and masking sensitive data in log entries.

## Primary Redaction Function

```python
# src/hermes_attractor/adapters/logging/redaction.py
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"


def redact_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, (list, tuple)) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes))
    ):
        return [redact_value(item) for item in value]
    return value
```

**Design**: Type-based dispatch handles primitives, strings, mappings, and sequences recursively. Booleans are checked before `int` because `bool` is a subclass of `int` in Python.

## String Redaction

```python
def redact_string(text: str) -> str:
    for pattern in SENSITIVE_PATTERNS.values():
        text = pattern.sub(REDACTED, text)
    return text
```

**Behavior**:

- Applies every compiled regex from `SENSITIVE_PATTERNS`
- Multiple matches in the same string are all replaced
- Patterns are applied in dict order (insertion order is preserved in Python 3.7+)

**Example**:

```python
redact_string('api_key: "sk_live_abc123", token: "eyJhbGc..."')
# → 'api_key: "[REDACTED]", token: "[REDACTED]"'
```

## Mapping Redaction

```python
def redact_mapping(obj: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in obj.items():
        lower_key = key.lower()
        if lower_key in REDACT_FIELDS:
            result[key] = REDACTED
        elif lower_key in MASK_FIELDS and isinstance(value, str):
            result[key] = mask_string(value, lower_key)
        else:
            result[key] = redact_value(value)
    return result
```

**Key features**:

- **Field-level redaction**: checks key names against `REDACT_FIELDS`
- **Field-level masking**: checks key names against `MASK_FIELDS`
- **Recursive redaction**: applies `redact_value` to non-sensitive fields
- **Preserves key names**: only values are redacted, keys remain unchanged

**Example**:

```python
redact_mapping({
    "username": "john",
    "password": "secret123",
    "email": "john@example.com",
    "metadata": {"token": "abc123"},
})
# → {
#   "username": "john",
#   "password": "[REDACTED]",
#   "email": "j***@example.com",
#   "metadata": {"token": "[REDACTED]"},
# }
```

## Masking Function

```python
def mask_string(text: str, field_type: str) -> str:
    if field_type == "email":
        local, _, domain = text.partition("@")
        if local and domain:
            return f"{local[0]}***@{domain}"

    if field_type in {"phone", "ip", "ip_address"}:
        return text[:3] + "***" + text[-2:]

    # Default: show first and last characters
    if len(text) > 4:
        return text[0] + "***" + text[-1]

    return REDACTED
```

**Masking strategies**:

- **Email**: shows first character of the local part and the full domain
- **Phone/IP**: shows prefix (3 chars) and suffix (2 chars)
- **Generic**: shows first and last character for strings longer than 4 chars
- **Short strings**: fully redacted if ≤4 characters

## Integration with the logging pipeline

Wire redaction in either (preferably both) of two places:

### As a logging.Filter (boundary defense)

```python
import logging


class RedactionFilter(logging.Filter):
    """Scrub structured fields on every record before it reaches a handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        fields = getattr(record, "fields", None)
        if isinstance(fields, Mapping):
            record.fields = redact_mapping(fields)  # type: ignore[attr-defined]
        return True


handler = logging.StreamHandler()
handler.addFilter(RedactionFilter())
```

### In the SafeLoggerAdapter

```python
# Inside SafeLoggerAdapter.process() — see the structured-logging skill
if self._is_production:
    fields = redact_value(fields)
```

**Environment-aware redaction**:

- **Production**: full recursive redaction via `redact_value()`
- **Development**: critical fields only (preserves debugging info)
- **Debug logs**: suppressed entirely in production via the logger level

## Performance Optimization

### Compile patterns once

`SENSITIVE_PATTERNS` should hold pre-compiled `re.Pattern` objects (see sensitive-patterns.md), not raw strings, so they are not recompiled on every call.

### Memoization

For repeated redaction of identical static strings:

```python
from functools import lru_cache


@lru_cache(maxsize=1024)
def memoized_redact_string(text: str) -> str:
    return redact_string(text)
```

**Warning**: `lru_cache` bounds memory with `maxsize`. Never cache attacker-controlled, unbounded input without a bound.

## Testing Redaction Functions

```python
# tests/unit/adapters/logging/test_redaction.py
from hermes_attractor.adapters.logging.redaction import redact_value


def test_redacts_api_keys_in_strings():
    result = redact_value('api_key: "sk_live_abcdef123456789012345678"')
    assert result == 'api_key: "[REDACTED]"'


def test_redacts_jwt_tokens():
    jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    )
    assert redact_value(jwt) == "[REDACTED]"


def test_redacts_credit_card_numbers():
    assert redact_value("Card: 4111-1111-1111-1111") == "Card: [REDACTED]"


def test_redacts_sensitive_mapping_fields():
    result = redact_value({"username": "john", "password": "secret123", "token": "abc123"})
    assert result == {"username": "john", "password": "[REDACTED]", "token": "[REDACTED]"}


def test_masks_email_addresses():
    result = redact_value({"email": "john.doe@example.com"})
    assert result["email"] == "j***@example.com"


def test_handles_nested_mappings():
    result = redact_value({"user": {"name": "John", "credentials": {"password": "secret"}}})
    assert result["user"]["credentials"]["password"] == "[REDACTED]"
    assert result["user"]["name"] == "John"


def test_handles_sequences():
    result = redact_value([{"name": "John", "password": "secret1"}, {"name": "Jane", "password": "secret2"}])
    assert result[0]["password"] == "[REDACTED]"
    assert result[1]["password"] == "[REDACTED]"
```

## Error Handling

Redaction must never raise inside the logging path:

```python
def safe_redact_value(value: Any) -> Any:
    try:
        return redact_value(value)
    except Exception:  # noqa: BLE001 — logging must not crash the app
        return "[REDACTION_ERROR]"
```

**Rationale**: Logging failures should not crash the application. Prefer partial data over no data. (If you enable ruff's `BLE001`, this is the one place a blind `except` is justified — annotate with `# noqa: BLE001`.)
