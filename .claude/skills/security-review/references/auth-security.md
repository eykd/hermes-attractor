# Secrets & Authentication Security

## Table of Contents

- [Password Hashing](#password-hashing)
- [Token & Session Generation](#token--session-generation)
- [Timing Attack Prevention](#timing-attack-prevention)
- [Secrets Management](#secrets-management)
- [Account Enumeration Prevention](#account-enumeration-prevention)

## Password Hashing

### Required: Argon2id

OWASP recommendation. Protects against GPU and side-channel attacks. Use the `argon2-cffi` library — it handles salting, parameters, and the encoded hash string for you.

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Defaults follow OWASP guidance (memory_cost ~ 64 MiB, time_cost 3, parallelism 4).
hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return hasher.hash(password)  # returns "$argon2id$v=19$m=...$...$..."


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
```

If `argon2-cffi` is unavailable, the stdlib fallback is `hashlib.scrypt` (memory-hard) — never a bare digest.

### Flag These as Critical

- `hashlib.md5(...)`, `hashlib.sha1(...)`, `hashlib.sha256(...)` used to hash passwords (fast, often unsalted) — ruff `S324`
- Plain-text passwords stored or logged
- Reversible encryption for passwords
- `bcrypt` is acceptable but prefer Argon2id for new code

### Password Requirements

- Minimum 12 characters (NIST 800-63B)
- Maximum 128 characters (cap input length before hashing to avoid DoS)
- Check against a common-password list
- No arbitrary complexity rules (per NIST)

## Token & Session Generation

Use the `secrets` module for all security-sensitive randomness — never `random`.

```python
import secrets


def generate_session_id() -> str:
    return secrets.token_urlsafe(32)  # 256 bits of entropy


def generate_csrf_token() -> str:
    return secrets.token_hex(32)
```

### Flag These as High

- `random.random()` / `random.choice()` for tokens, IDs, or salts (predictable) — use `secrets`
- Tokens shorter than 128 bits
- Tokens generated client-side

## Timing Attack Prevention

### Constant-Time Comparison

```python
import hmac


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)  # also accepts bytes
```

### Use For

- Password/hash verification (`PasswordHasher.verify` is already constant-time)
- CSRF token validation
- API key comparison
- Session ID comparison
- Any security-sensitive string/bytes comparison

### Flag These as High

- `==` / `!=` for tokens, secrets, or hashes
- Early return on first mismatched character
- Comparing secrets with `str.startswith`/`in`

## Secrets Management

### Environment Variables / Secret Stores

```python
import os

# ✅ Read secrets from the environment (or a secret manager), never source.
api_key = os.environ["API_SECRET"]
db_password = os.environ.get("DB_PASSWORD")
```

```python
# ❌ CRITICAL - hardcoded secrets (ruff S105/S106/S107)
API_KEY = "sk-abc123..."
DB_PASSWORD = "password123"
```

### Configuration Files

- Never commit secrets to `pyproject.toml`, `settings.py`, or any tracked file.
- Use a `.env` (git-ignored) for local development, loaded by your tooling, and a secret manager in production.
- Different secrets per environment.

### Flag These as Critical

- Secrets in source code (ruff `S105`, `S106`, `S107`)
- Secrets in committed config files
- API keys embedded in client-distributable code
- Secrets in error messages or logs (see the pii-redaction skill)

### Secrets Checklist

- [ ] No hardcoded secrets
- [ ] Secrets read from `os.environ` or a secret manager
- [ ] Secrets not logged (redaction layer in place)
- [ ] Secrets not in error responses or tracebacks shown to users
- [ ] Different secrets per environment
- [ ] Secret rotation capability

## Account Enumeration Prevention

### Generic Error Messages

```python
# ❌ Wrong - reveals which accounts exist
if user is None:
    raise AuthError("User not found")
if not valid_password:
    raise AuthError("Invalid password")

# ✅ Correct - generic message
if user is None or not valid_password:
    raise AuthError("Invalid email or password")
```

### Consistent Timing

```python
from argon2 import PasswordHasher

hasher = PasswordHasher()
# Pre-computed dummy hash so verification cost is paid even when the user is missing.
_DUMMY_HASH = hasher.hash("placeholder")


def login(email: str, password: str) -> User:
    user = find_user(email)
    stored = user.password_hash if user else _DUMMY_HASH

    valid = verify_password(stored, password)  # constant-ish cost either way

    if user is None or not valid:
        raise AuthError("Invalid email or password")
    return user
```
