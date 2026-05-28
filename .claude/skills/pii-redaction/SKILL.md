---
name: pii-redaction
description: "Use when: (1) Implementing systematic PII and secret redaction in logs, (2) Classifying data sensitivity (never log / always redact / conditionally log), (3) Building regex/field-name detection or redaction helpers, (4) Sanitizing URLs, (5) Wiring a logging.Filter for defense-in-depth."
---

# PII Redaction

**Use when:** Implementing systematic PII and secret redaction for defense-in-depth data protection in logs.

## Overview

This skill provides comprehensive patterns for protecting sensitive data in logs through multiple redaction layers. It covers sensitive data classification (never log vs always redact vs conditionally log), pattern-based detection using regex for API keys/tokens/credit cards/PII, field-level detection based on key names, redaction helpers for values/dicts/strings, and URL sanitization to remove query parameters and path segments containing tokens.

In Python, redaction is wired into the standard `logging` pipeline in one of two ways:

- A `logging.Filter` that scrubs each record's structured `fields` before it reaches a handler (defense at the boundary), and/or
- The `SafeLoggerAdapter` (see the structured-logging skill) which redacts in `process()`.

Use both for defense-in-depth: even logs that bypass the adapter are scrubbed by the filter.

## Decision Tree

### Need to identify what data to redact?

**When**: Classifying data sensitivity and determining redaction requirements
**Go to**: [references/sensitive-patterns.md](./references/sensitive-patterns.md)

### Need to detect sensitive fields?

**When**: Implementing field-level detection based on key names
**Go to**: [references/field-detection.md](./references/field-detection.md)

### Need to implement redaction helpers?

**When**: Building `redact_value`, `redact_mapping`, `redact_string`, and `mask_string`
**Go to**: [references/redaction-functions.md](./references/redaction-functions.md)

### Need to sanitize URLs?

**When**: Redacting query parameters and path segments in logged URLs
**Go to**: [references/url-sanitization.md](./references/url-sanitization.md)

## Quick Example

```python
# src/hermes_attractor/adapters/logging/redaction.py
from __future__ import annotations

import re
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
    if isinstance(value, Sequence):  # str already handled above
        return [redact_value(item) for item in value]
    return value


def redact_string(text: str) -> str:
    for pattern in SENSITIVE_PATTERNS.values():
        text = pattern.sub(REDACTED, text)
    return text
```

```python
# As a logging.Filter (defense at the boundary)
import logging


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "fields"):
            record.fields = redact_mapping(record.fields)  # type: ignore[attr-defined]
        return True
```

## Cross-References

- **[structured-logging](../structured-logging/SKILL.md)**: Integrate redaction into the `SafeLoggerAdapter`/`JsonFormatter` for automatic PII protection in all logs
- **[sentry-integration](../sentry-integration/SKILL.md)**: Reuse these helpers in Sentry `before_send`/`before_breadcrumb` hooks

## Reference Files

- [references/sensitive-patterns.md](./references/sensitive-patterns.md) - Data classification and regex patterns for sensitive data detection
- [references/field-detection.md](./references/field-detection.md) - Field-level detection based on key names for redaction and masking
- [references/redaction-functions.md](./references/redaction-functions.md) - Core redaction helpers for values, mappings, strings, and masking
- [references/url-sanitization.md](./references/url-sanitization.md) - URL sanitization patterns for query parameters and path segments
