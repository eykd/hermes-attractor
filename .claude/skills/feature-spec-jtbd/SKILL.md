---
name: feature-spec-jtbd
description: "Use when: (1) Stakeholders request features without explaining problems, (2) Vague requirements lack concrete success criteria, (3) Unclear why a feature is needed, (4) Determining whether to build/defer/reject, (5) Translating messy ideas into job stories, (6) Distinguishing symptoms from root causes."
---

# Feature Specification Using Jobs-to-be-Done

Use Socratic questioning to transform vague feature requests into concrete jobs-to-be-done statements. This approach uncovers root causes, desired outcomes, and whether to build at all.

## Core Principle

People don't want features—they want to make progress in a specific circumstance. A job-to-be-done has three dimensions:
- **Functional**: The practical task to accomplish
- **Emotional**: How they want to feel
- **Social**: How they want to be perceived

## When to Apply This Skill

Apply this systematically when:
- Stakeholders request solutions without explaining problems ("We need a mobile app")
- Requirements lack concrete success criteria or measurable outcomes
- Multiple stakeholders have conflicting views on priorities
- The "why" behind a feature request is unclear
- Determining whether to build, defer, or reject a feature

## Five-Phase Interview Structure

### Phase 1: Establish Context (The Circumstance)

**Goal**: Understand when and why the need arises

Key questions:
- "Tell me about the last time you encountered [situation]."
- "What was happening that made you think about this?"
- "What triggered your need to [do something]?"
- "How often does this situation come up?"

Listen for:
- The circumstance that creates the need
- Frequency and predictability
- Environmental factors that change the norm

### Phase 2: Explore Current Approach

**Goal**: Understand existing solutions and their limitations

Key questions:
- "What did you do to handle that situation?"
- "What other approaches have you tried?"
- "What was frustrating or insufficient about it?"
- "What workarounds have you developed?"

When they mention pain, probe deeper:
- "Can you give a specific example of when that happened?"
- "What did that cost you?" (time, money, stress, opportunity)
- "How did that make you feel?"
- "Who else was affected?"

Listen for:
- Existing "jobs" they're hiring different solutions for
- Compensating behaviors (strong signal of unmet needs)
- Pain severity (mild annoyance vs. critical blocker)
- Trade-offs they're willing to make

### Phase 3: Uncover Desired Outcomes

**Goal**: Identify what "done" looks like and success criteria

Key questions:
- "When you say you want to [goal], what does success look like?"
- "How will you know when you've achieved this?"
- "What becomes possible for you if you can solve this?"
- "If you couldn't solve this at all, what would that mean?"

Emotional and social dimensions:
- "How would solving this make you feel?"
- "Who do you answer to about this?"
- "What would be embarrassing or risky if this went wrong?"

Listen for:
- Concrete success metrics
- Emotional motivators
- Status and perception concerns
- Hidden stakeholders

### Phase 4: Challenge Assumptions

**Goal**: Test understanding and expose hidden constraints

Key questions:
- "Let me play back what I heard—is this accurate: [summary]?"
- "You mentioned [X]. Help me understand why [X] instead of [Y]?"
- "If you could only have one part of what you described, which would it be?"
- "What am I not asking about that I should be?"
- "What limits your options here?"
- "If you could only solve one of these problems, which would it be?"
- "What's the cost of not solving this for another 6 months?"

Listen for:
- Misunderstandings to correct
- Hidden constraints (technical, political, resource)
- Priority signals (words vs. actual importance)
- Scope boundaries

### Phase 5: Synthesize and Validate

**Goal**: Confirm understanding and document the job

Document the job statement together:
**"When I [circumstance], I want to [motivation], so I can [desired outcome]."**

Validate:
- "Based on what you've shared, it sounds like you're trying to [job statement]. Is that right?"
- "The main obstacles preventing you are [barriers]. What am I missing?"
- "If we could help you [outcome], would that solve the problem?"
- "Who else faces this challenge that I should talk to?"

Listen for:
- Confirmation or correction
- Energy level when you state the problem (enthusiasm = good signal)
- Confidence in the framing

## Critical Techniques

### The Five Whys
Ask "why" up to five times to reach root causes:
- User: "I want a dashboard."
- You: "Why do you want a dashboard?"
- User: "To see our metrics."
- You: "Why do you need to see metrics?"
- User: "To know if we're on track."
- You: "Why do you need to know that?"
- User: "So I can explain our progress to my boss."
- You: "Why does your boss need that information?"
- User: "She has to report to the board monthly and gets questions I can't currently answer."

**Root cause**: Need to provide defensible board-level reporting (not "need a dashboard").

### The Counterfactual
Test boundaries with hypotheticals:
- "What if you had unlimited budget for this?"
- "What if this took 2 hours instead of 2 days?"
- "What if [constraint] didn't exist?"

### The Contrast
Reveal priorities through differences:
- "How is this different from [similar thing]?"
- "Why is this more important than [alternative]?"
- "What makes a good outcome versus a great one?"

## Red Flags and Responses

### Solution Disguised as Problem
**They say**: "We need a mobile app."
**Response**: "Help me understand—what are you trying to accomplish that you can't do now?"

### Feature Request from Sales/Leadership
**They say**: "The CEO wants a real-time dashboard."
**Response**: "What problem is the CEO trying to solve? What decision will they make with that information?"

### "Users Are Asking For..."
**They say**: "Users keep requesting [feature X]."
**Response**: "Can you connect me with a couple of those users? I'd love to understand what they're trying to accomplish."

### Vague Outcomes
**They say**: "We need to improve efficiency."
**Response**: "What does efficiency mean in this context? How would you measure it? What's the impact of current inefficiency?"

### Anchored to Existing Solutions
**They say**: "We need something like [competitor feature]."
**Response**: "What problem does that feature solve for their users? Is that the same problem we're facing?"

## Common Mistakes to Avoid

- **Asking leading questions**: "Don't you think it would be better if...?"
- **Jumping to solutions**: "What if we built...?"
- **Accepting jargon**: Always ask for clarification
- **Interviewing only one stakeholder**: Triangulate across multiple people
- **Stopping at the first answer**: Push deeper with follow-ups
- **Skipping specific examples**: Generalities hide the truth
- **Forgetting to listen**: 80/20 rule—listen more than you talk

## Decision Framework: Build or Don't Build

After 5-7 stakeholder conversations, evaluate signals:

**Strong signals to build**:
- ✅ Job is frequent and consequential
- ✅ Current solutions are expensive or painful workarounds
- ✅ Multiple stakeholders describe the same job independently
- ✅ Strong emotional response to the problem
- ✅ Clear, measurable success criteria
- ✅ Willingness to pay or change behavior

**Weak signals—investigate further**:
- ⚠️ Only one person mentions it
- ⚠️ Low frequency or severity
- ⚠️ No workarounds currently in place (maybe it's not important)
- ⚠️ Vague outcomes or success criteria
- ⚠️ Stakeholders can't describe a recent specific example

**Signals not to build**:
- ❌ Solution in search of a problem
- ❌ Political request without user need
- ❌ Can be solved adequately with existing tools
- ❌ Success depends on changing user behavior in unlikely ways

## Pattern Recognition Across Interviews

Look for:
- **Consistent jobs** across multiple stakeholders
- **High-frequency pain points** mentioned repeatedly
- **Strong emotional language** indicating severity
- **Compensating behaviors** suggesting unmet needs
- **Disagreements** between stakeholders that need resolution

## Synthesize Into Job Stories

Transform insights into job stories using this format:

**When** [situation], **I want to** [motivation], **so I can** [expected outcome].

**Example**: When I'm preparing for a quarterly business review with limited time, I want to quickly assess which projects are at risk, so I can focus my preparation on addressing executive concerns before they're raised.

## Documentation Template

For each conversation, document:

1. **Job Statement**: When [circumstance], I want to [motivation], so I can [outcome]
2. **Functional Jobs**: Practical tasks to accomplish
3. **Emotional Jobs**: How they want to feel
4. **Social Jobs**: How they want to be perceived
5. **Current Solutions**: What they're "hiring" today
6. **Obstacles**: What prevents the job from being done well
7. **Success Criteria**: What "done" looks like with specific metrics
8. **Priority Level**: High/Medium/Low based on decision framework

## Working with Claude Code

When clarifying a feature spec in Claude Code:

1. **Start with questions, not assumptions**: Even if the request seems clear, use Phase 1-2 questions to validate understanding
2. **Document as you go**: Create a `discovery-notes.md` file to capture insights
3. **Synthesize before speccing**: Write the job statement before writing technical requirements
4. **Reference the job in the spec**: Every feature requirement should trace back to a job dimension
5. **Include the decision logic**: Document why this should be built (or not) based on the framework

## Quick Reference: Essential Questions

**Context**: "Tell me about the last time..." / "What triggered this need?"

**Current approach**: "What did you do?" / "What was frustrating about it?"

**Outcomes**: "What does success look like?" / "How will you know you're done?"

**Challenge**: "Why is that important?" / "If you could only have one thing..."

**Validate**: "Is this accurate: [summary]?" / "Who else should I talk to?"
