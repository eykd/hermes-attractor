# Sensitive Data Patterns

**Purpose**: Classify data sensitivity and provide regex patterns for detecting sensitive information in logs.

## Data Classification

| Category              | Examples                                               | Action                                      |
| --------------------- | ------------------------------------------------------ | ------------------------------------------- |
| **Never Log**         | Passwords, API keys, tokens, credit card numbers, SSNs | Block at source                             |
| **Always Redact**     | Email addresses, phone numbers, IP addresses, names    | Mask or hash                                |
| **Conditionally Log** | User IDs, session IDs, request paths                   | Log in non-production, redact in production |
| **Safe to Log**       | Timestamps, error codes, aggregate counts              | Log freely                                  |

## Pattern-Based Detection

Compile patterns once at import time so they are not recompiled per log entry.

### API Keys and Tokens

```python
import re

SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    # API keys and tokens
    "api_key": re.compile(
        r"(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token)['\":\s]*[=:]\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
        re.IGNORECASE,
    ),
    "bearer_token": re.compile(r"Bearer\s+[a-zA-Z0-9_\-.]+", re.IGNORECASE),
    "jwt": re.compile(r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"),
```

**Rationale**: API keys typically follow predictable patterns with 20+ alphanumeric characters. JWT tokens always start with `eyJ` (base64-encoded `{"alg"`). Bearer tokens follow the OAuth 2.0 format.

### AWS Credentials

```python
    # AWS credentials
    "aws_access_key": re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}"),
    "aws_secret_key": re.compile(r"[a-zA-Z0-9/+=]{40}"),
```

**Rationale**: AWS access keys have specific prefixes (AKIA for IAM, ASIA for STS, etc.) followed by 16 uppercase alphanumeric characters. Secret keys are exactly 40 characters from the base64 alphabet.

### Credit Cards

```python
    # Credit cards
    "credit_card": re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b"),
```

**Rationale**: Detects 16-digit credit card numbers with optional spaces or hyphens as separators (e.g. `4111-1111-1111-1111` or `4111111111111111`).

### PII Patterns

```python
    # PII
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
```

**Rationale**:

- Email: standard RFC 5322 simplified pattern
- Phone: US phone numbers with optional country code, area code, and various separators
- SSN: US Social Security Numbers in `XXX-XX-XXXX` format (with optional separators)
- IPv4: dotted-quad notation (note: may need validation to avoid false positives like version numbers)

### Generic Secrets

```python
    # Generic secrets
    "password": re.compile(r"(?:password|passwd|pwd)['\":\s]*[=:]\s*['\"]?([^'\"\s]+)['\"]?", re.IGNORECASE),
    "secret": re.compile(r"(?:secret|private[_-]?key)['\":\s]*[=:]\s*['\"]?([^'\"\s]+)['\"]?", re.IGNORECASE),
}
```

**Rationale**: Catches common field names for passwords and secrets in various formats (JSON, query strings, log lines).

## Pattern Usage

```python
REDACTED = "[REDACTED]"


def redact_string(text: str) -> str:
    for pattern in SENSITIVE_PATTERNS.values():
        text = pattern.sub(REDACTED, text)
    return text
```

## False Positive Mitigation

**IPv4 addresses**: the IPv4 pattern may match version numbers like `1.2.3.4`. Consider context-aware detection:

```python
# Only redact if preceded by IP-related keywords
contextual_ip = re.compile(
    r"(?:ip|address|client|remote)['\":\s]*[=:]\s*['\"]?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})['\"]?",
    re.IGNORECASE,
)
```

**AWS secret keys**: the 40-character pattern may match other base64 strings. Consider requiring the key to follow an AWS access key in context.

## Pattern Testing

Always validate patterns against test cases:

```python
# tests/unit/adapters/logging/test_sensitive_patterns.py
from hermes_attractor.adapters.logging.redaction import redact_string


def test_detects_api_keys():
    assert redact_string('api_key: "sk_live_abcdef123456789012345678"') == 'api_key: "[REDACTED]"'


def test_detects_jwt_tokens():
    jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    )
    assert redact_string(jwt) == "[REDACTED]"


def test_detects_credit_card_numbers():
    assert redact_string("Card: 4111-1111-1111-1111") == "Card: [REDACTED]"
```

## Compliance Alignment

These patterns align with:

- **OWASP Logging Cheat Sheet**: never log authentication credentials, session tokens, credit cards, or PII
- **NIST SP 800-122**: PII must be protected through redaction or encryption in logs
- **GDPR Article 32**: implement appropriate technical measures to ensure the security of personal data
- **PCI DSS Requirement 3**: protect stored cardholder data (includes logs)

## Limitations

- **Patterns are not exhaustive**: new token formats emerge regularly
- **Context matters**: some patterns may need domain-specific customization
- **Performance impact**: regex operations on every log entry add overhead (benchmark in your environment)
- **No semantic analysis**: cannot detect sensitive data described in natural language (e.g. "my password is hunter2")

## Extension Pattern

To add custom patterns:

```python
SENSITIVE_PATTERNS["custom_token"] = re.compile(r"your-pattern-here")
```
