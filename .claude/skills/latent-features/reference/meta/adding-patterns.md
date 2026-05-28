# Adding New Patterns to Latent Features

**Purpose**: Meta-pattern guide for creating token-efficient implementation pattern references

**When to read**: When you want to add a new pattern to the latent-features skill

---

## Overview

The latent-features skill uses **progressive disclosure** to provide token-efficient access to comprehensive implementation guides. Each pattern follows a consistent structure that enables:

- **Lightweight discovery**: Quick pattern identification via SKILL.md index
- **Guided exploration**: PATTERN.md roadmap tells you what to read when
- **On-demand loading**: Load only the reference files you need for current work
- **Token efficiency**: 70-85% token savings vs loading full guides

---

## Pattern Structure

Every pattern follows this directory layout:

```
reference/[pattern-name]/
├── PATTERN.md                          # Pattern guide (350-500 lines)
│   ├── Overview and capabilities
│   ├── Progressive disclosure path
│   ├── Usage by phase
│   ├── Token efficiency comparison
│   └── Testing strategies
│
├── architecture/
│   └── overview.md                     # High-level design (100-150 lines)
│       ├── Architecture diagrams
│       ├── Threat model (for security patterns)
│       ├── Key decisions
│       └── Technology choices
│
└── implementation/
    ├── [component1].md                 # Focused implementation (250-500 lines)
    ├── [component2].md                 # One component per file
    └── [component3].md                 # Self-contained, concrete examples
```

---

## Step-by-Step Process

### 1. Create Comprehensive Guide

**File**: `docs/[pattern-name]-guide.md`

**Purpose**: Complete reference with all details (typically 2,000-5,000 lines)

**Contents**:

- Introduction and motivation
- Complete architecture explanation
- All implementation details with code examples
- Edge cases and advanced scenarios
- Complete testing strategies
- Infrastructure setup (if applicable)
- Security considerations (if applicable)

**This is your source material** - You'll extract focused reference files from this.

---

### 2. Create Pattern Directory

```bash
mkdir -p .claude/skills/latent-features/reference/[pattern-name]/{architecture,implementation}
```

---

### 3. Write PATTERN.md (Pattern Guide)

**File**: `reference/[pattern-name]/PATTERN.md`

**Target length**: 350-500 lines

**Required sections**:

```markdown
# [Pattern Name] Pattern

**Purpose**: One-sentence description

**Trigger keywords**: keyword1, keyword2, keyword3

---

## Pattern Overview

**What this pattern provides**:

- Bullet points of key capabilities

**Latent requirements this surfaces**:

- Implied requirements that ride along with the feature (the point of this skill)

**Technologies**:

- List of technologies used

**Key features**: (if security pattern)

- Security/architectural features

---

## Progressive Disclosure Path

### Level 1: Architecture Overview (~XXX lines)

**File**: `architecture/overview.md`

**When to read**: Specification phase, early planning

**What you get**:

- What the file provides (bullet points)

**Use this when**:

- When to read this file (bullet points)

---

### Level 2: [Component Name] (~XXX lines)

**File**: `implementation/[component].md`

**When to read**: [Phase name]

**What you get**:

- What the file provides

**Use this when**:

- When to read this file

---

## Usage by Phase

### Specification Phase (`/sp:02-specify`)

**Goal**: [What to accomplish]

**Steps**:

1. Load: [file]
2. Extract: [what to extract]
3. Document: [what to document]

**Token cost**: ~XXX lines

**Example output for spec**:
\`\`\`markdown
[Example spec section]
\`\`\`

---

### Planning Phase (`/sp:03-plan`)

**Goal**: [What to accomplish]

**Steps**:

1. Load: [files]
2. Extract: [what to extract]
3. Create: [what to create]

**Token cost**: ~XXX lines

**Example plan structure**:
\`\`\`markdown
[Example plan structure]
\`\`\`

---

### Implementation Phase

**Goal**: Load specific patterns as needed

[Examples of implementation tasks and which files to load]

---

## Complete Reference

**File**: `docs/[pattern-name]-guide.md` (~X,XXX lines)

**When to use**: Rarely - only when focused reference files are insufficient

---

## Token Efficiency Comparison

### Progressive Disclosure Approach

\`\`\`
Session 1: XXX lines
Session 2: XXX lines
Total: ~X,XXX lines
\`\`\`

### Monolithic Approach

\`\`\`
Session 1: Load entire guide (X,XXX lines)
\`\`\`

**Token savings**: XX% reduction

---

## Testing Strategy

[Testing patterns for this feature]

---

## Dependencies

\`\`\`toml
[project]
dependencies = [
  # List dependencies (pyproject.toml style)
]
\`\`\`

---

## Notes

- Pattern-specific notes
- OWASP/industry standard references
- Architecture assumptions
```

---

### 4. Extract Architecture Overview

**File**: `reference/[pattern-name]/architecture/overview.md`

**Target length**: 100-150 lines

**What to include**:

- High-level architecture diagrams (ASCII art)
- Key architectural decisions with rationale
- Technology choices and why
- Threat model (for security patterns)
- Data flow diagrams
- Component interaction diagrams

**What to exclude**:

- Implementation details
- Code examples
- Step-by-step procedures

**Example structure**:

```markdown
# [Pattern Name] Architecture

**Purpose**: High-level architectural overview

**When to read**: Specification phase, early planning

---

## Architecture Overview

[Diagram and explanation]

## Key Decisions

| Decision | Rationale | Alternatives Considered |
| -------- | --------- | ----------------------- |
| Choice 1 | Why       | What else               |

## Component Diagram

[ASCII diagram showing components mapped to hexagonal layers]

## Data Flow

[How data flows through domain / ports / adapters / use_cases / plugin]

## Next Steps

- For [specific need] → Read `implementation/[file].md`
```

---

### 5. Extract Implementation Files

**Files**: `reference/[pattern-name]/implementation/[component].md`

**Target length per file**: 250-500 lines

**One file per major component/concept**

**What to include**:

- Concrete code examples
- Implementation patterns
- Configuration details
- Testing patterns for this component
- Common pitfalls
- Security considerations for this component

**What to exclude**:

- Other components (keep focused)
- High-level architecture (that's in overview.md)
- Full application examples

**Example structure**:

```markdown
# [Component Name]

**Purpose**: What this component does

**When to read**: When implementing [specific feature]

**Source**: Full implementation in `docs/[pattern]-guide.md` (lines XXX-XXX)

---

## Overview

[Brief component overview]

---

## Implementation

**File**: `src/hermes_attractor/adapters/component.py`

\`\`\`python
[Code example]
\`\`\`

**Key points**:

- Point 1
- Point 2

---

## Configuration

[Configuration details]

---

## Usage Examples

[Concrete usage examples]

---

## Security Considerations

[Security notes specific to this component]

---

## Testing Strategy

\`\`\`python
[pytest examples — unit tests mock the port, integration tests use real infra]
\`\`\`

---

## Common Pitfalls

1. **Pitfall**: Description
   - **Solution**: How to avoid

---

## Next Steps

- For [related component] → Read `[other-file].md`
```

---

### 6. Update SKILL.md

Add pattern entry to SKILL.md's "Available Patterns" section:

```markdown
### N. [Pattern Name]

**Triggers**: keyword1, keyword2, keyword3

**Covers**: Brief one-line description

**Latent requirements this surfaces**:

- Implied requirements the feature drags along

**Quick start**: Read `reference/[pattern-name]/PATTERN.md`

**Progressive disclosure**:

- Specification → `architecture/overview.md` (~XXX lines)
- Planning → `implementation/[key-file].md` (~XXX lines)
- Implementation → Choose from implementation/\*.md files (~XXX-XXX lines each)

**Reference structure**:
\`\`\`
reference/[pattern-name]/
├── PATTERN.md # Pattern guide
├── architecture/
│ └── overview.md # Architecture overview
└── implementation/
├── [component1].md # Component implementation
├── [component2].md
└── [component3].md
\`\`\`
```

---

## Progressive Disclosure Guidelines

### File Size Targets

- **SKILL.md**: Keep under 200 lines (lightweight index)
- **PATTERN.md**: 350-500 lines (roadmap and usage guide)
- **architecture/overview.md**: 100-150 lines (high-level design)
- **implementation/\*.md**: 250-500 lines per file (focused implementation)

### Splitting Implementation Files

**When to split**:

- File exceeds 500 lines
- Component covers multiple distinct responsibilities
- Implementation has multiple independent aspects

**How to split**:

- One file per major component
- One file per major feature area
- Keep related concepts together

**Example splits**:

```
# Good: Focused files
implementation/
├── domain-entities.md       # User, Session entities
├── password-security.md     # Hashing (argon2-cffi / passlib), validation
├── session-management.md    # Session store, signed cookies
├── csrf-protection.md       # CSRF middleware
└── xss-prevention.md        # Output encoding / template autoescaping

# Bad: Too granular
implementation/
├── user-entity.md           # Just User entity
├── session-entity.md        # Just Session entity
├── email-value-object.md    # Just EmailAddress value object
└── password-value-object.md # Just Password value object
```

---

## Token Efficiency Best Practices

### 1. DRY in Reference Files

**Don't repeat architecture overview in every implementation file**

```markdown
# Bad

## [Component] Implementation

First, let's review the overall architecture...
[Repeats architecture overview from overview.md]

Now for the implementation...

# Good

## [Component] Implementation

**Architecture context**: See `architecture/overview.md` for overall design

Now for the implementation...
```

### 2. Cross-Reference Related Files

**Guide readers to related content**

```markdown
## Next Steps

- For password hashing → Read `implementation/password-security.md`
- For session storage → Read `implementation/session-management.md`
- For complete examples → Read `docs/secure-authentication-guide.md`
```

### 3. Defer Complete Reference

**Always prefer focused files over full guide**

```markdown
# In PATTERN.md

**Complete Reference**: `docs/[pattern]-guide.md` (~X,XXX lines)

**When to use**: Rarely - only when focused reference files are insufficient

**Prefer**: Focused reference files above for XX% token savings
```

---

## Example Walkthrough: Adding "Rate Limiting" Pattern

### 1. Create Comprehensive Guide

Create `docs/rate-limiting-guide.md` (~2,500 lines) covering:

- Introduction to rate limiting strategies
- Sliding window vs fixed window vs token bucket
- Implementation with a `RateLimitStore` port (in-memory, Redis, or DB-backed adapter)
- Distributed rate limiting considerations
- Testing strategies (deterministic clock via a `Clock` port)
- Security considerations

### 2. Create Pattern Structure

```bash
mkdir -p .claude/skills/latent-features/reference/rate-limiting/{architecture,implementation}
```

### 3. Write PATTERN.md

Extract from guide and create `reference/rate-limiting/PATTERN.md`:

- Pattern overview
- Progressive disclosure path
- Usage by phase
- Token efficiency comparison

### 4. Extract Architecture

Create `architecture/overview.md` (~120 lines):

- Rate limiting strategies comparison
- Distributed rate limiting architecture
- Counter storage design behind a `RateLimitStore` port
- Key design decisions

### 5. Extract Implementation Files

Create focused implementation files:

- `implementation/sliding-window.md` (~280 lines)
  - Sliding window algorithm
  - `RateLimitStore` adapter implementation
  - Testing patterns (inject a fake `Clock`)

- `implementation/middleware.md` (~320 lines)
  - Rate limit middleware / dependency
  - Response headers (`Retry-After`, etc.)
  - Error handling

- `implementation/configuration.md` (~190 lines)
  - Rate limit rules configuration
  - Per-endpoint limits
  - User tier handling

### 6. Update SKILL.md

Add rate limiting entry to Available Patterns section.

### Result

**Progressive disclosure efficiency**:

- Specification: 120 lines (architecture)
- Planning: 280 lines (sliding window)
- Implementation: 320 lines (middleware) + 190 lines (config)
- **Total**: ~910 lines vs 2,500 line full guide
- **Savings**: 64% token reduction

---

## Anti-Patterns

### Don't: Create Monolithic Files

```markdown
# Bad: implementation/everything.md (2,000 lines)

- All components in one file
- Hard to load just what you need
- Token inefficient
```

### Don't: Overly Granular Files

```markdown
# Bad: 20+ tiny files

implementation/
├── user-id.md # 50 lines
├── user-email.md # 60 lines
├── user-password-hash.md # 40 lines
...
```

### Don't: Repeat Content

```markdown
# Bad: Duplicate architecture in every file

Each implementation file starts with full architecture overview
```

### Don't: Ignore Progressive Disclosure

```markdown
# Bad: PATTERN.md just says "Read the full guide"

No progressive disclosure path provided
```

---

## Do: Create Focused, Self-Contained Files

```markdown
# Good: implementation/password-security.md (295 lines)

- Complete treatment of password security
- Self-contained with examples
- References related files
- Appropriate length for on-demand loading
```

---

## Checklist for New Patterns

- [ ] Comprehensive guide created in `docs/[pattern]-guide.md`
- [ ] Pattern directory created with architecture/ and implementation/
- [ ] PATTERN.md written with progressive disclosure path
- [ ] architecture/overview.md extracted (100-150 lines)
- [ ] Implementation files extracted (250-500 lines each)
- [ ] Each implementation file is focused on one component
- [ ] Cross-references added between related files
- [ ] Token efficiency comparison documented
- [ ] Testing strategies included
- [ ] SKILL.md updated with pattern entry
- [ ] File sizes within target ranges
- [ ] Progressive disclosure path clearly documented

---

## Summary

**Key principles**:

1. Start with comprehensive guide
2. Extract focused reference files
3. Create clear progressive disclosure path
4. Keep files within token efficiency targets
5. Guide readers through the journey

**Goal**: Enable token-efficient access to comprehensive patterns through intelligent progressive disclosure.
