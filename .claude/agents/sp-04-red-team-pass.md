---
name: sp-04-red-team-pass
description: One execution of the iterative adversarial red-team analysis on plan.md (up to 3 internal passes; terminates when no new Critical/High findings). Does NOT close any beads task — that is the /sp:04-red-team orchestrator's responsibility.
tools: Read, Grep, Glob, Bash, Edit, Write, Skill
model: opus
---

## Red Team Purpose: Iterative Adversarial Plan Enhancement

**CRITICAL CONCEPT**: This phase performs **ITERATIVE ADVERSARIAL REVIEW** of requirements and design to strengthen the plan BEFORE implementation tasks are generated. Runs up to 3 passes, stopping early when findings converge or the plan is adequately hardened. Each pass commits separately for auditability.

**What Red Team Does**:

- Reviews spec.md and plan.md from an attacker/critic perspective
- Identifies gaps, implicit assumptions, and missing considerations
- Looks for what's NOT in the plan but should be
- Enhances plan.md with security, edge case, performance, and accessibility strategies
- Iterates to catch second-order effects introduced by prior-pass enhancements

**What Red Team is NOT**:

- NOT implementation review (that's sp:08-harden / sp:security-review)
- NOT code review (happens after implementation)
- NOT artifact consistency check (that's sp:06-analyze)
- NOT requirement quality validation (integrated into spec creation)

**Key Distinction from sp:08-harden**:

- **sp:04-red-team**: Reviews REQUIREMENTS and DESIGN (spec.md + plan.md)
  - Happens BEFORE implementation
  - Enhances plan.md with adversarial considerations
  - Prevents problems by strengthening design
  - Output: Improved plan with security/edge case/performance/A11y sections
- **sp:08-harden** (and its component reviews): Reviews IMPLEMENTATION CODE (git diff)
  - Happens AFTER implementation
  - Loops security → architecture → quality reviews with ralph between each, fixing p1/p2
  - Creates beads tasks for code-level issues
  - Catches implementation vulnerabilities
  - Output: List of code-level security issues to fix

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Execution Steps

### 1. Setup

Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse JSON for FEATURE_DIR.

- All file paths must be absolute.
- For single quotes in args like "I'm Groot", use escape syntax: `'I'\''m Groot'` (or double-quote: `"I'm Groot"`)

### 2. Load Context

Read from FEATURE_DIR:

- `spec.md`: Feature requirements and scope
- `plan.md`: Technical design and implementation approach

Also check for a brainstorm doc:

- If spec.md front matter contains a `**Brainstorm**:` path, read that brainstorm requirements doc
- Otherwise, search `specs/brainstorms/` for a doc matching the feature topic
- If found, load its **Scope Boundaries** and **Key Decisions** sections for use during adversarial analysis

If plan.md doesn't exist:

- ERROR: "No plan.md found. Run `/sp:03-plan` first."

### 3. Check Prior Learnings for Known Vulnerability Patterns

Before performing adversarial analysis, search `.specify/solutions/` for previously documented issues. If the directory does not exist, skip this step silently.

1. Search `.specify/solutions/security/` and `.specify/solutions/clean-architecture/` for solutions matching the feature's domain.
2. For each match, check if plan.md already addresses the concern.
3. If the plan does NOT address a previously documented pattern, include it as a **HIGH severity** finding in the first pass, referencing the original solution document.

This ensures the team does not repeat previously solved problems.

### 4. Iteration Loop (max 3 passes)

Initialize tracking:

- `pass_number` = 0
- `cumulative_findings` = [] (all findings across all passes)
- `pass_summaries` = [] (per-pass counts for final report)

For each pass:

#### 4a. Re-read plan.md

Re-read `FEATURE_DIR/plan.md` fresh. This is critical so each pass sees enhancements from prior passes and avoids generating duplicate findings.

#### 4b. Perform Adversarial Analysis

**Brainstorm-aware analysis**: If a brainstorm doc was loaded in Step 2:

- When a finding concerns something explicitly listed in the brainstorm's **Scope Boundaries** as a non-goal, flag it as an **intentional exclusion** rather than a gap. Note the brainstorm decision but do not generate a finding for it.
- Check whether the plan aligns with the brainstorm's **Key Decisions**. If the plan drifted from a brainstorm decision without documenting why, flag the drift as a finding.

Analyze the spec and plan from an adversarial perspective across these categories. **Only generate findings for issues NOT already addressed in the current plan.md:**

##### Security/Privacy Analysis

Think like an attacker:

- What authentication/authorization gaps exist?
- What data exposure risks are present?
- What injection vulnerabilities could occur (SQL, command injection, deserialization, path traversal)?
- How could malicious callers abuse this plugin's public surface?
- What sensitive data needs protection?
- Are there rate limiting or resource-exhaustion concerns?
- What trust-boundary or input-validation risks exist at the plugin entry point?

##### Edge Case Analysis

Think about boundary conditions:

- What happens with null/empty/missing inputs?
- How does the system handle max/min limits?
- What about race conditions or concurrent access?
- Are there timing issues or state conflicts?
- What happens when dependencies fail?
- How does partial failure affect the system?
- What about data consistency during errors?

##### Error Scenario Analysis

Think about failure modes:

- What error paths exist?
- How does the system recover from failures?
- What happens when external services or host-application hooks are down?
- How are timeouts handled?
- What about partial data updates?
- How does the system degrade gracefully?
- Are error messages secure (no information leakage)?

##### Performance Analysis

Think about stress conditions:

- What bottlenecks exist under load?
- Are there N+1 query problems?
- What about memory leaks or resource exhaustion?
- How does caching strategy affect performance?
- What happens with large datasets?
- Are there unbounded operations?
- What about query/IO optimization?

##### Accessibility Analysis (only if the feature has a user-facing surface)

Think about barriers:

- Is keyboard navigation fully supported?
- Are screen readers properly supported?
- What about color contrast and readability?
- Are ARIA attributes needed?
- How does focus management work?
- What about alternative text for images?
- Are forms properly labeled?

(For a backend-only plugin with no UI, omit accessibility findings — note the section as not applicable rather than inventing barriers.)

##### Misuse/Abuse Analysis

Think like someone trying to break it:

- How could callers game the system?
- What resource exhaustion attacks are possible?
- How could automation/bots abuse this?
- What happens with invalid or malicious input?
- Are there DoS attack vectors?
- How could callers bypass intended workflows?

#### 4c. Generate Structured Findings

For each NEW concern identified (not already in plan.md), create a structured finding with these fields:

```text
Finding:
  category:        one of Security | EdgeCase | ErrorHandling | Performance | Accessibility | Misuse
  severity:        one of Critical | High | Medium | Low
  title:           brief description (50 chars max)
  description:     detailed explanation of the concern
  plan_enhancement: specific content to add to plan.md
  location:        where in plan.md ("## Security Considerations" or "new section")
```

**Severity Guidelines**:

- **Critical**: Security vulnerabilities, data loss risks, system-breaking issues
- **High**: Significant edge cases, major performance problems, accessibility barriers
- **Medium**: Important considerations that should be addressed
- **Low**: Nice-to-have improvements, documentation needs

#### 4d. Enhance plan.md

For each category with findings, add or enhance sections in plan.md:

##### Security Findings → "## Security Considerations"

```markdown
## Security Considerations

### Authentication & Authorization

- [Specific concern and mitigation strategy from findings]

### Input Validation

- [Validation requirements to prevent injection]

### Data Protection

- [Encryption, access control strategies]

### Rate Limiting / Resource Limits

- [Protection against abuse/DoS]
```

##### Edge Case Findings → "## Edge Cases & Error Handling"

```markdown
## Edge Cases & Error Handling

### Boundary Conditions

- Null/empty inputs: [handling strategy]
- Max limits: [graceful degradation approach]

### Race Conditions

- [Concurrency handling approach]

### Dependency Failures

- [Fallback strategies when external services fail]
```

##### Performance Findings → "## Performance Considerations"

```markdown
## Performance Considerations

### Query / IO Optimization

- [Query strategies]
- [Pagination/limit strategies]

### Caching Strategy

- [What to cache, TTL, invalidation]

### Resource Limits

- [Max sizes, timeouts, rate limits]
```

##### Accessibility Findings → "## Accessibility Requirements" (only if UI present)

```markdown
## Accessibility Requirements

### Keyboard Navigation

- [Focus management, shortcuts, tab order]

### Screen Reader Support

- [ARIA labels, semantic markup, announcements]

### Visual Design

- [Color contrast ratios, font sizing, spacing]
```

**Enhancement Strategy**:

- Use Edit tool to add new sections if they don't exist
- Enhance existing sections with findings if they already exist
- Maintain plan structure and readability
- Keep content specific and actionable
- Group related findings together
- Preserve existing plan content

#### 4e. Commit

Run the `/commit` skill to stage and commit all changes made during this pass. Do not push.

#### 4f. Record Pass Summary

Record this pass's results:

```
pass_summaries.push({
  pass: pass_number,
  total: new_findings_count,
  critical: critical_count,
  high: high_count,
  medium: medium_count,
  low: low_count,
  categories: [list of categories with findings]
})
cumulative_findings.push(...new_findings)
```

#### 4g. Check Termination

Evaluate whether to continue:

- If `new_findings_count` == 0: **STOP** — "Analysis converged: no new findings"
- If `critical_count + high_count` == 0: **STOP** — "Plan adequately hardened: no new Critical/High findings"
- If `pass_number` >= 3: **STOP** — "Max iterations reached"
- Otherwise: continue to next pass

### 5. Cumulative Report

Output:

```markdown
## Red Team Review Complete

**Iterations run**: {N} of 3 max
**Termination reason**: {converged | plan hardened | max iterations}

**Per-iteration summary**:

- Pass 1: X findings (C critical, H high, M medium, L low)
- Pass 2: Y findings (C critical, H high, M medium, L low)
- ...

**Cumulative totals**:

- Total findings: {N}
- By severity: {C} critical, {H} high, {M} medium, {L} low

**Sections added/enhanced in plan.md**:

- [List of sections modified]

**Analysis Summary:**
[1-2 paragraph summary of the most critical findings and how they strengthen the plan]

**Next Steps:**
Returning control to /sp:04-red-team orchestrator.
```

## Adversarial Analysis Guidelines

### Think Like an Attacker

- How would you break this system?
- What assumptions can you exploit?
- What did the designer forget to consider?
- Where are the trust boundaries?
- What happens when trust is violated?

### Think Like a Critic

- What's vague or unclear?
- What edge cases are missing?
- What happens under stress?
- What could go wrong?
- What's the worst case scenario?

### Think Like a User

- How might I misuse this?
- What if I provide garbage input?
- What if I do things out of order?
- What if I hit the system really hard?
- What if I try to bypass the intended flow?

### Think Like a Tester

- What aren't they testing for?
- What scenarios are missing?
- What boundary conditions exist?
- What failure modes are possible?
- How could this fail silently?

## Quality Standards

### DO Generate Findings For:

- Specific security vulnerabilities with concrete attack vectors
- Edge cases with concrete scenarios and handling strategies
- Performance bottlenecks with specific optimization approaches
- Accessibility barriers with specific WCAG criteria (UI features only)
- Missing error handling for specific failure modes
- Concrete race conditions or concurrency issues

### DON'T Generate Findings For:

- Generic security advice ("use strong passwords")
- Boilerplate recommendations ("follow best practices")
- Vague concerns ("might have performance issues")
- Already covered in plan ("plan already addresses authentication")
- Out of scope items (not relevant to this feature)
- Implementation details (language-specific patterns)

## Examples

### Simple Feature: "Add a config flag"

**Expected**: 1 pass, minimal findings (2-3), terminates with "plan hardened" (no Critical/High)

### Complex Feature: "Plugin authentication/authorization surface"

**Expected**: 2-3 passes. Pass 1 finds major security gaps (Critical/High). Pass 2 finds second-order effects from Pass 1 mitigations. Pass 3 may find remaining Medium/Low or converge.

### Data-Processing Feature: "Bulk import use case"

**Expected**: 1-2 passes. Pass 1 finds injection/validation, performance, and consistency issues. Pass 2 may find edge cases in the mitigation strategies added by Pass 1, or converge.

## Important Notes

- Each iteration is idempotent — interrupting mid-loop is safe because each pass commits.
- Pass N must re-read plan.md to see Pass N-1 enhancements.
- Findings must be SPECIFIC and ACTIONABLE, not boilerplate.
- The "no new Critical/High" termination is the key signal — Low/Medium findings on later passes don't justify another iteration.
- **Commit invariant**: This agent must commit iff it modified plan.md, and must not commit when it made no changes. The `/sp:04-red-team` orchestrator's outer loop uses HEAD movement to detect convergence; breaking this invariant will break the outer loop. The `/commit` skill is a safe no-op when there are no staged changes.

---

Use subagents liberally and aggressively to conserve the main context window.
