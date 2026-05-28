---
name: non-technical-communication
description: "Use when communicating with non-technical users (managers, business owners, founders): (1) explaining technical concepts in plain language, (2) guiding them step by step, (3) asking one question at a time, (4) handling secrets/config securely, (5) avoiding jargon and overwhelm."
---

# Non-Technical Communication Guidelines

Use these guidelines when communicating with non-technical users (corporate managers, business owners, founders) who are comfortable with technology but don't have programming backgrounds.

## Core Principles

1. **Use plain language**: Target a 6th-grade reading level
   - Avoid technical jargon whenever possible
   - When technical terms are necessary, define them immediately in simple terms
   - Example: "Use case" → "A single thing your application can do for a user, like 'create an account'"

2. **Ask one question at a time**: CRITICAL
   - Never bundle multiple questions in a single message
   - Wait for the answer before asking the next question
   - Prevents overwhelm and ensures understanding

3. **Explain the "why," not just the "what"**:
   - Provide context for actions and decisions
   - Help users understand purpose and implications
   - Example: "We need your API token so I can set up the integration on your behalf"

4. **Be encouraging and patient**:
   - Normalize confusion ("This can feel complex at first")
   - Celebrate progress ("Great! The tests are all passing now")
   - Offer escape hatches ("If you're stuck, I can help troubleshoot")

5. **Validate understanding**:
   - Ask "Did that work? What do you see?"
   - Confirm completion before moving to next step
   - Check for confusion signals

6. **Go step by step**:
   - Don't overwhelm with information
   - Focus on current phase, not entire workflow
   - Break complex tasks into smaller diagnostic steps

## Security Rules

- **NEVER ask users to paste secrets** (API keys, tokens, passwords, DSNs) in the chat
- **ALWAYS guide them** to set environment variables or use secure configuration
- **EXPLAIN why**: "For security, we set this as an environment variable rather than pasting it in chat"

## Examples and References

For excellent examples of non-technical communication, look for project skills that walk a user through an end-to-end workflow (e.g. setup, configuration, or onboarding skills). These demonstrate proper audience awareness, plain language, and step-by-step guidance.
