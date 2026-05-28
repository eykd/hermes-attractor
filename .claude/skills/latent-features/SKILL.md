---
name: latent-features
description: "Use when: (1) defining feature specs (/sp:02-specify), (2) planning implementations (/sp:03-plan), (3) implementing authentication/sessions, (4) security-sensitive features. Surfaces implied (latent) requirements. NOT for simple CRUD or bug fixes."
allowed-tools: [Read, Bash]
---

# Latent Features Skill

**Purpose**: Surface the implied ("latent") requirements that ride along with security-sensitive features, via token-efficient progressive disclosure of comprehensive implementation patterns.

A request for "login" silently implies password hashing, session expiry, CSRF protection, rate limiting, secure cookies, and audit logging. This skill makes those latent requirements explicit during specification and planning so they are not discovered late, during review or in production.

---

## When to Use This Skill

**REQUIRED when**:

- Defining feature specifications (`/sp:02-specify`)
- Planning feature implementations (`/sp:03-plan`)
- Implementing authentication or session management
- Working with security-sensitive features

**DO NOT use for**:

- Simple bug fixes or refactoring
- Non-security utility functions
- Basic CRUD without authentication

---

## Available Patterns

### 0. Adding New Patterns (Meta-Pattern)

**Triggers**: create pattern, add pattern, new pattern, extend latent-features

**Covers**: Step-by-step guide for adding new patterns to this skill with progressive disclosure

**Quick start**: Read `reference/meta/adding-patterns.md`

**What you get**:

- Pattern structure requirements
- Step-by-step process (6 steps)
- File templates for all components
- Progressive disclosure guidelines
- Token efficiency best practices
- Example walkthrough
- Anti-patterns and checklist

**Use this when**:

- Adding new implementation patterns to latent-features skill
- Understanding the pattern structure and rationale
- Need templates for PATTERN.md, architecture/, implementation/ files

---

### 1. Secure Session-Based Authentication

**Triggers**: authentication, login, logout, session, password, user registration, auth

**Covers**: OWASP-compliant session auth in Python (FastAPI/Starlette + Authlib/itsdangerous + passlib/argon2-cffi) with defense-in-depth security, wired through hexagonal layers

**Latent requirements this surfaces**:

- Password hashing with Argon2id (`argon2-cffi`) or bcrypt (`passlib`) — never plaintext or fast hashes
- Session lifecycle: creation, expiry, refresh, server-side revocation
- Secure cookies: `HttpOnly`, `Secure`, `SameSite`, signed via `itsdangerous`
- CSRF protection for state-changing form posts
- Rate limiting on login/register endpoints (IP-based, with IPv6 normalization)
- Output encoding / template autoescaping to prevent XSS
- Security headers (CSP, HSTS, X-Frame-Options)
- Open-redirect prevention on login/register callbacks
- Audit logging of auth events (login, logout, failed attempts)

**Layering** (hexagonal):

- `domain/` — `User`, `Session` entities; `Password`, `EmailAddress` value objects
- `ports/` — `UserRepository`, `SessionStore`, `PasswordHasher` Protocols
- `adapters/` — SQLAlchemy/repository implementations, argon2 hasher, signed-cookie session store
- `use_cases/` — `RegisterUser`, `Authenticate`, `Logout` orchestrators
- `plugin/` — HTTP route handlers / middleware wiring

**Quick start**: Read `reference/secure-auth/PATTERN.md` (add via Pattern 0 if not yet present)

---

### 2. Webhook Integration

**Triggers**: webhook, callback, signature verification, third-party events, inbound integration

**Covers**: Verifying and handling inbound webhooks (HMAC signature verification, replay protection, idempotency)

**Latent requirements this surfaces**:

- HMAC signature verification using `hmac.compare_digest` (constant-time compare)
- Timestamp/nonce checks to prevent replay attacks
- Idempotency keys so duplicate deliveries are processed once
- Raw-body capture before any framework parsing (signatures sign the raw bytes)
- Fast acknowledgement + async processing (return 2xx promptly, do work off the request path)
- Dead-letter handling and retry semantics

**Layering** (hexagonal):

- `domain/` — event entities and value objects for the integration
- `ports/` — `WebhookVerifier`, `EventProcessor`, `IdempotencyStore` Protocols
- `adapters/` — HMAC verifier, persistence-backed idempotency store
- `use_cases/` — `HandleInboundEvent` orchestrator
- `plugin/` — webhook route handler (raw-body aware)

**Quick start**: Read `reference/webhooks/PATTERN.md` (add via Pattern 0 if not yet present)

---

### 3. Payments Integration

**Triggers**: payments, checkout, subscription, billing, invoicing, usage-based

**Covers**: Payment integration in Python (e.g. the `stripe` Python SDK or a payment-provider adapter) with checkout, subscriptions, and webhook reconciliation

**Latent requirements this surfaces**:

- Webhook signature verification and idempotent event handling (see Pattern 2)
- Server-side amount/price validation — never trust client-supplied amounts
- Reconciliation between provider state and local order/subscription state
- Secure handling of customer/payment identifiers (no card data stored locally; PCI scope minimized)
- Refund, dispute, and failed-payment flows
- Audit trail for all money-moving operations

**Layering** (hexagonal):

- `domain/` — `Order`, `Subscription`, `Money` value object
- `ports/` — `PaymentGateway`, `OrderRepository` Protocols
- `adapters/` — payment-provider SDK adapter
- `use_cases/` — `CreateCheckout`, `ReconcilePayment` orchestrators
- `plugin/` — checkout + webhook route handlers

**Quick start**: Read `reference/payments/PATTERN.md` (add via Pattern 0 if not yet present)

---

### 4. Multi-Tenant SaaS

**Triggers**: multi-tenant, organization, authorization, tenant-isolation, org, membership, rbac, role-based, saas

**Covers**: Multi-tenant implementation with authorization, data isolation, and membership management in Python

**Latent requirements this surfaces**:

- Tenant scoping on every query (a tenant-scoped repository wrapper, not ad-hoc `WHERE org_id = ?`)
- Authorization model: Actor / Action / Resource checks in an authorization service
- Privilege-escalation prevention (a member cannot grant themselves a role they lack)
- Cross-tenant isolation audits and tests (the hardest bugs are silent leaks)
- Invitation/membership lifecycle with rate limits to prevent abuse
- Security-safe error messages (do not leak existence of other tenants' resources)
- Data-model evolution strategy as tenancy requirements grow

**Layering** (hexagonal):

- `domain/` — `Organization`, `Membership`, `Role` entities
- `ports/` — `AuthorizationService`, `TenantScopedRepository` Protocols
- `adapters/` — tenant-scoped persistence wrapper
- `use_cases/` — `InviteMember`, `AuthorizeAction` orchestrators
- `plugin/` — org-aware route handlers / middleware

**Quick start**: Read `reference/multi-tenant-saas/PATTERN.md` (add via Pattern 0 if not yet present)

---

## Usage Pattern

### 1. Read Pattern Guide First

When a pattern applies to your task, start here:

```bash
Read .claude/skills/latent-features/reference/[pattern-name]/PATTERN.md
```

This gives you:

- Pattern overview and capabilities
- Progressive disclosure roadmap
- Which files to read for your current phase
- Token efficiency guidance

### 2. Follow Progressive Disclosure Path

The pattern guide tells you which files to load based on your phase:

- **Specification**: Load architecture overview (~100-150 lines)
- **Planning**: Load domain/architecture files (~500-700 lines)
- **Implementation**: Load specific implementation files as needed (~300-500 lines each)

### 3. Access Full Reference (Rarely)

Only when focused files are insufficient:

```bash
Read docs/[pattern-name]-guide.md
```

---

## Token Efficiency

**Example workflow** (secure authentication):

```
Read PATTERN.md                          →  ~250 lines (pattern guide)
Read architecture/overview.md            →  ~130 lines (specification)
Read implementation/auth-setup.md        →  ~250 lines (planning)
Read implementation/csrf-protection.md   →  ~200 lines (implementation)

Total: ~830 lines across 4 files
vs old hand-rolled pattern: ~2,500+ lines
Savings: ~67% token reduction
```

---

## Adding New Patterns

**See Pattern 0 (Meta-Pattern) above** for complete guide: `reference/meta/adding-patterns.md`

**Quick reference**:

1. Create comprehensive guide in `docs/[pattern-name]-guide.md`
2. Extract focused reference files following pattern structure
3. Write PATTERN.md with progressive disclosure path
4. Update this SKILL.md with pattern entry

**Pattern structure**:

```
reference/[pattern-name]/
├── PATTERN.md                      # Pattern guide (350-500 lines)
├── architecture/
│   └── overview.md                 # High-level design (100-150 lines)
└── implementation/
    └── [component].md              # Focused implementation (250-500 lines)
```

---

## Best Practices

1. **Always start with PATTERN.md** - It's your roadmap
2. **Load only what you need** - Progressive disclosure saves tokens
3. **Follow the recommended path** - Each phase has optimal files
4. **Cache context efficiently** - Files stay in context once loaded
5. **Defer full guide** - Only load complete reference when necessary

---

## Notes

- All patterns follow OWASP guidelines (current as of January 2026)
- Security patterns use defense-in-depth (multiple layers)
- Implementation examples use Python (3.11+, hexagonal `src/hermes_attractor/{domain,ports,adapters,use_cases,plugin}/`)
- Tooling assumptions: uv for packaging, ruff for lint/format, pyright (strict) for types, pytest for tests
- Architecture patterns assume DDD/Clean Architecture (ports as `typing.Protocol`, adapters injected into use cases)
- All patterns include testing strategies (unit with mocked ports; integration against real infrastructure)
