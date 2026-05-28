# Field-Level Detection

**Purpose**: Identify sensitive fields by key names for automatic redaction or masking.

## Redaction Field Sets

Fields that should be completely redacted (replaced with `[REDACTED]`):

```python
# src/hermes_attractor/adapters/logging/redaction.py

REDACT_FIELDS: frozenset[str] = frozenset({
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credit_card",
    "creditcard",
    "card_number",
    "cardnumber",
    "cvv",
    "ssn",
    "social_security",
    "socialsecurity",
})
```

**Rationale**: These fields contain authentication credentials or highly sensitive data that should never appear in logs, even partially.

## Masking Field Sets

Fields that should be partially visible (show limited characters):

```python
MASK_FIELDS: frozenset[str] = frozenset({"email", "phone", "ip", "ip_address", "ipaddress"})
```

**Rationale**: These fields contain PII that is useful for correlation but should not be fully exposed. Masking preserves debugging capability while protecting privacy.

## Detection Logic

```python
from collections.abc import Mapping
from typing import Any


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

**Key design decisions**:

- **Case-insensitive matching**: uses `str.lower()` to catch `Email`, `EMAIL`, `email`
- **Type checking**: only mask `str` values (numbers, booleans, etc. pass through unchanged)
- **Recursive redaction**: non-sensitive fields still undergo recursive redaction for nested sensitive data

## Masking Strategies

### Email Masking

```python
def mask_string(text: str, field_type: str) -> str:
    if field_type == "email":
        local, _, domain = text.partition("@")
        if local and domain:
            return f"{local[0]}***@{domain}"
```

**Output**: `john.doe@example.com` → `j***@example.com`

**Rationale**: Preserves the domain for debugging (e.g. checking corporate vs personal email) while hiding user identity.

### Phone/IP Masking

```python
    if field_type in {"phone", "ip", "ip_address"}:
        return text[:3] + "***" + text[-2:]
```

**Output**: `555-123-4567` → `555***67`

**Rationale**: Shows the prefix (useful for area code/subnet analysis) and suffix for uniqueness checking.

### Generic Masking

```python
    # Default: show first and last characters
    if len(text) > 4:
        return text[0] + "***" + text[-1]

    return REDACTED
```

**Output**: `hunter2` → `h***2`

**Rationale**: Preserves minimal information for correlation while protecting the actual value. Short strings (≤4 chars) are fully redacted to prevent trivial brute force.

## Custom Field Detection

### Adding Project-Specific Fields

```python
PROJECT_REDACT_FIELDS = REDACT_FIELDS | {"internal_api_key", "webhook_secret", "encryption_key"}
PROJECT_MASK_FIELDS = MASK_FIELDS | {"employee_id", "customer_code"}
```

### Pattern-Based Field Detection

For dynamic field names:

```python
import re

_SECRET_SUFFIX = re.compile(r"_(secret|key|token)$")
_SECRET_PREFIX = re.compile(r"^(api|auth|secret)_")


def should_redact_field(key: str) -> bool:
    lower_key = key.lower()
    if lower_key in REDACT_FIELDS:
        return True
    return bool(_SECRET_SUFFIX.search(lower_key) or _SECRET_PREFIX.search(lower_key))
```

**Common patterns**:

- Fields ending in `_secret`, `_key`, `_token`
- Fields starting with `api_`, `auth_`, `secret_`
- Fields containing `password`, `credential`, `private`

## Nested Mapping Handling

Field detection works recursively:

```python
data = {
    "user": {
        "name": "John",
        "credentials": {"password": "secret", "email": "john@example.com"},
    },
}

redact_value(data)
# {
#   "user": {
#     "name": "John",
#     "credentials": {"password": "[REDACTED]", "email": "j***@example.com"},
#   },
# }
```

## Sequence Handling

Lists and tuples are mapped element-wise:

```python
data = {"users": [{"name": "John", "password": "secret1"}, {"name": "Jane", "password": "secret2"}]}

redact_value(data)
# {"users": [{"name": "John", "password": "[REDACTED]"}, {"name": "Jane", "password": "[REDACTED]"}]}
```

## Performance Considerations

- **Set lookups**: `O(1)` average case for field detection
- **Case conversion**: adds overhead; consider pre-computing lowercase keys for hot paths
- **Deep recursion**: extremely nested structures may hit the recursion limit (consider an iterative approach for adversarial input)

## Testing Field Detection

```python
# tests/unit/adapters/logging/test_field_detection.py
import pytest

from hermes_attractor.adapters.logging.redaction import redact_mapping


@pytest.mark.parametrize("key", ["password", "Password", "PASSWORD"])
def test_redacts_password_fields_case_insensitively(key: str):
    assert redact_mapping({key: "secret"}) == {key: "[REDACTED]"}


def test_masks_email_fields():
    assert redact_mapping({"email": "john@example.com"})["email"] == "j***@example.com"


def test_handles_nested_sensitive_fields():
    data = {"user": {"credentials": {"password": "secret"}}}
    result = redact_mapping(data)
    assert result["user"]["credentials"]["password"] == "[REDACTED]"
```
