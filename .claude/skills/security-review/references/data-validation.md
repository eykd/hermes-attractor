# Input Validation & Request Metadata

## Table of Contents

- [Server-Side Validation](#server-side-validation)
- [Allowlist Validation](#allowlist-validation)
- [Mass Assignment Protection](#mass-assignment-protection)
- [Request Size & Metadata](#request-size--metadata)
- [Rate Limiting](#rate-limiting)

## Server-Side Validation

Validate every input on the server, regardless of any client-side checks. Prefer a declarative schema (`pydantic`, `attrs` + validators, or `dataclasses` with explicit checks) so the boundary is typed and enforced.

```python
from __future__ import annotations

from dataclasses import dataclass


class ValidationError(Exception):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


@dataclass(frozen=True, slots=True)
class CreateUserRequest:
    email: str
    display_name: str

    def __post_init__(self) -> None:
        email = self.email.strip().lower()
        if not _EMAIL_RE.match(email) or len(email) > 254:
            raise ValidationError("email", "Invalid email")
        name = self.display_name.strip()
        if not (1 <= len(name) <= 100):
            raise ValidationError("display_name", "Must be 1-100 characters")
        object.__setattr__(self, "email", email)
        object.__setattr__(self, "display_name", name)


import re

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
```

With `pydantic`, the equivalent model gets validation, length limits, and coercion for free:

```python
from pydantic import BaseModel, EmailStr, Field


class CreateUserRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
```

### Flag These as High

- Trusting client-side validation only
- Type coercion from request data without validation (e.g. `int(request.params["n"])` with no bounds)
- Missing length limits on strings (DoS / storage abuse)
- Catching `Exception` around parsing and silently continuing

## Allowlist Validation

For fixed-set inputs (enums, modes, sort fields), reject anything not on the allowlist.

```python
from enum import StrEnum


class Status(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


def parse_status(raw: str) -> Status:
    try:
        return Status(raw)
    except ValueError as exc:
        msg = "Invalid status"
        raise ValidationError("status", msg) from exc
```

## Mass Assignment Protection

Never splat untrusted data into an entity — an attacker can set fields you didn't intend (e.g. `is_admin`, `role`, `user_id`).

```python
# ❌ HIGH - sets whatever keys the client sent
def update_user(user: User, data: dict[str, object]) -> None:
    for key, value in data.items():
        setattr(user, key, value)

# ✅ CORRECT - explicit, typed allowlist of mutable fields
@dataclass(frozen=True, slots=True)
class UpdateUserRequest:
    display_name: str | None = None
    email: str | None = None
    # no `role`, `is_admin`, `id`, or `created_at`


def update_user(user: User, request: UpdateUserRequest) -> None:
    if request.display_name is not None:
        user.display_name = request.display_name
    if request.email is not None:
        user.email = request.email
```

Server-controlled fields (`id`, `created_at`, `user_id` from the session) are set on the server, never from the request body.

### Flag These as High

- `setattr` / `**data` / `model(**request_body)` spreading raw request data into a domain object without an allowlist
- `dict.update(entity.__dict__, request_body)` patterns

## Request Size & Metadata

If the code reads request bodies or uploads, enforce limits **before** buffering the whole payload, to prevent memory exhaustion and decompression bombs.

```python
MAX_JSON_BYTES = 10 * 1024          # 10 KB
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


def read_json_body(content_length: int | None, body_reader) -> bytes:
    if content_length is None:
        msg = "Content-Length required"
        raise ValidationError("content_length", msg)
    if content_length > MAX_JSON_BYTES:
        msg = "Request body too large"
        raise ValidationError("content_length", msg)
    return body_reader.read(MAX_JSON_BYTES)  # cap the read regardless
```

Recommended limits: JSON 10 KB, form 50 KB, image upload 5 MB, document 10 MB.

For file uploads, validate **before** processing: size cap, MIME-type allowlist, extension allowlist, and reject directory traversal in the filename (see deserialization-security.md → Path Traversal). Never allow executables/scripts (`.exe`, `.sh`, `.py`, `.html`, `.svg`).

### Flag These as High

- Reading an entire request body / file with no size cap
- File uploads without size + type validation
- Decompressing untrusted archives without member validation (zip-slip / zip-bomb)

## Rate Limiting

If the application exposes authentication or other abuse-prone endpoints, throttle by identifier (IP and/or account) **before** doing the expensive work.

```python
import time
from dataclasses import dataclass, field


@dataclass
class SlidingWindowLimiter:
    max_attempts: int
    window_seconds: float
    _hits: dict[str, list[float]] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        hits = [t for t in self._hits.get(key, []) if t > cutoff]
        if len(hits) >= self.max_attempts:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True
```

Use a shared store (e.g. Redis) instead of in-process state when running multiple workers. Apply the limit **before** verifying credentials so brute force is throttled. Suggested auth limits: login 5/IP per 15 min, 10/account per hour; registration 3/IP per hour.

### Flag These as High

- Auth endpoints with no rate limiting
- Rate-limit check performed *after* password verification (too late)
- In-process counters in a multi-process deployment (ineffective)
