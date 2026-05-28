# Security Review Checklist

Quick reference for Python security audits. Check each item and flag issues by severity. Run `uv run ruff check --select S` first to surface bandit-style hits, then verify manually.

## Secrets Management

- [ ] No hardcoded secrets (ruff `S105`/`S106`/`S107`)
- [ ] Secrets read from `os.environ` or a secret manager
- [ ] Secrets not committed to config files (`pyproject.toml`, settings)
- [ ] Secrets not in logs (redaction layer in place — see pii-redaction)
- [ ] Secrets not in error messages or tracebacks shown to users
- [ ] Different secrets per environment

## Password & Token Security

- [ ] Argon2id hashing via `argon2-cffi` (not md5/sha/bare digest) — ruff `S324`
- [ ] Minimum 12-char passwords, max length capped before hashing
- [ ] Randomness from `secrets`, never `random`
- [ ] Tokens ≥128 bits
- [ ] Constant-time comparison via `hmac.compare_digest`
- [ ] Generic auth error messages (no account enumeration)

## Injection

- [ ] SQL via parameterized queries only — no f-string/`%`/`.format()` SQL (ruff `S608`)
- [ ] SQLAlchemy uses bound params, not interpolated `text()`
- [ ] Dynamic table/column names validated against an allowlist
- [ ] `subprocess` uses an argv list, never `shell=True` with user input (ruff `S602`/`S604`)
- [ ] No `os.system`/`os.popen` with dynamic input (ruff `S605`)
- [ ] No `eval`/`exec` on external input (ruff `S307`)
- [ ] Jinja2 autoescaping enabled; templates never built from user input

## Deserialization & Untrusted Data

- [ ] No `pickle`/`marshal`/`shelve` on untrusted data (ruff `S301`)
- [ ] YAML parsed with `yaml.safe_load`, not `yaml.load` (ruff `S506`)
- [ ] Untrusted XML parsed with `defusedxml`, not stdlib `xml.*`
- [ ] `ast.literal_eval` used instead of `eval` for literal parsing

## File & Path Handling

- [ ] User-controlled paths contained with `Path.resolve()` + `is_relative_to(base)`
- [ ] Upload filenames reject `..`, `/`, `\`
- [ ] Archive extraction validates member paths (zip-slip)
- [ ] No reading/writing arbitrary user-supplied paths

## Network & TLS

- [ ] TLS verification never disabled (`verify=False`) — ruff `S501`
- [ ] User-supplied URLs validated against a host allowlist before fetching (SSRF)
- [ ] HTTP clients set timeouts

## Input Validation

- [ ] Server-side validation for all inputs (schema: pydantic/attrs/dataclass)
- [ ] Allowlist validation for fixed-option fields (enums)
- [ ] Length limits on strings
- [ ] Mass-assignment prevention (explicit field allowlists, no `**request_body`)
- [ ] Request bodies/uploads size-capped before buffering

## Rate Limiting (if auth/abuse-prone endpoints exist)

- [ ] Auth endpoints rate-limited
- [ ] Limit checked before credential verification
- [ ] Shared store (not in-process counters) for multi-worker deployments

## Error Handling

- [ ] Generic error messages to users (no stack traces / internal paths)
- [ ] No database/driver errors surfaced verbatim
- [ ] No blind `except Exception: pass` hiding failures
- [ ] Fail secure (deny on error)

## Audit & Monitoring

- [ ] Security events logged (failed auth, lockouts) — structured, redacted
- [ ] Anomaly detection possible from logs

---

## Severity Guide

### Critical (Fix Immediately)

- SQL/command injection
- Insecure deserialization (`pickle`/`yaml.load` on untrusted data)
- `eval`/`exec` on external input
- Weak/absent password hashing
- Hardcoded secrets
- Authentication bypass

### High (Fix Before Release)

- Path traversal
- SSRF / fetching unvalidated URLs
- TLS verification disabled
- Timing-vulnerable secret comparison
- Mass assignment
- Missing rate limiting on auth endpoints
- Unbounded request/upload sizes
- XXE on untrusted XML

### Medium (Fix Soon)

- Missing input validation
- Verbose error messages / leaked tracebacks
- Predictable randomness (`random` for tokens)
- Partial subprocess executable paths in privileged contexts

### Low (Track for Fix)

- Missing audit logging
- Suboptimal crypto parameters
- Minor configuration hardening
