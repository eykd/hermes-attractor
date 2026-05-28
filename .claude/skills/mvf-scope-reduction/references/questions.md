# Comprehensive Question Bank for MVF Scope Reduction

Organized by interview phase and scope reduction pattern. Use when you need deeper questioning strategies beyond the core interview questions in SKILL.md.

## Phase 1: Confirming the Core Job

### Understanding Frequency and Stakes
- "When was the last time this situation came up?"
- "How many times does this happen per week/month?"
- "How many people on your team face this?"
- "Walk me through what happens when [circumstance occurs]"
- "What's the cost if this doesn't get solved?"
- "Is this a daily pain or occasional annoyance?"

### Identifying Primary Users
- "Who specifically will use this feature?"
- "Are there different types of users with different needs?"
- "Which user group has the most urgent need?"
- "If you could only build this for one user type, which would it be?"

### Validating the Problem
- "What makes this hard right now?"
- "What have you tried that didn't work?"
- "Why hasn't this been solved already?"
- "What changed that makes this important now?"

## Phase 2: Understanding Current Pain

### Quantifying Pain
- "How much time does the current approach take?"
- "How much does this cost in [time/money/opportunity]?"
- "What percentage of your week is spent on this?"
- "How many people are affected by this problem?"
- "What happens when this goes wrong?"

### Identifying Workarounds
- "What shortcuts have you developed?"
- "What do you do when the normal process doesn't work?"
- "How do you handle this when you're in a rush?"
- "What parts of the process do you skip when you can?"

### Finding the Critical Bottleneck
- "Of all the steps in your current process, which is the worst?"
- "If you could fix just one thing, what would it be?"
- "Where do you spend the most time?"
- "Where do mistakes usually happen?"
- "Which step makes you say 'I wish there was a better way'?"

## Phase 3: Ruthless Prioritization

### Forcing Trade-offs
- "You can have A or B, but not both right now. Which do you choose?"
- "If building X delays Y by 3 months, is X worth it?"
- "Would you rather have [simple solution now] or [complex solution later]?"
- "What's the minimum that would make your life better?"

### Testing Necessity
- "What happens if we don't include [feature]?"
- "Can you accomplish your goal without [capability]?"
- "Is this a must-have or a nice-to-have?"
- "Would you still use this if it didn't have [feature]?"
- "What's the workaround if this isn't available?"

### Revealing Hidden Priorities
- "You mentioned [A, B, C]. If you had to rank them, what's the order?"
- "Which of these keeps you up at night?"
- "If I could only give you one of these, which would disappoint you most to lose?"
- "Where's the biggest risk if we get this wrong?"

### Understanding Edge Cases
- "How often does [edge case] actually happen?"
- "What percentage of users would hit this scenario?"
- "Can you give me an example of when this occurred?"
- "Is this something that happens weekly or yearly?"
- "What do you do when [edge case] happens now?"

## Phase 4: Challenging Integrations

### Testing Integration Necessity
- "What problem does integrating with [system] solve?"
- "Could users export/import data instead?"
- "What's the manual process if this integration doesn't exist?"
- "How many clicks would the manual approach take?"
- "Is this integration critical or convenient?"

### Understanding Integration Complexity
- "What data needs to flow between systems?"
- "Does this need to be real-time or can it be batched?"
- "What happens if the integration fails?"
- "How often does the data change?"
- "Could we start with a one-way sync?"

### Deferral Testing for Integrations
- "What if we just had an export button for now?"
- "Could you copy/paste this information initially?"
- "Would a daily sync work instead of real-time?"
- "Can we add this integration after we validate demand?"

## Phase 5: Testing Reduced Scope

### Gauging Value
- "Would you actually use this MVF?"
- "Does this solve your core problem?"
- "Is this better than what you have now?"
- "Would you be disappointed if we shipped this?"
- "On a scale of 1-10, how valuable is this reduced scope?"

### Identifying Missing Pieces
- "What's missing that you absolutely can't live without?"
- "Is there something I cut that breaks the whole thing?"
- "What would make this unusable?"
- "What's the minimum viable addition to make this work?"

### Building Confidence
- "Can you walk me through using this MVF?"
- "Tell me about the first time you'd use this"
- "How would this change your daily work?"
- "What becomes possible with this that isn't possible now?"

### Testing Deferral Acceptance
- "Can we add [deferred feature] after we see how people use v1?"
- "Would you rather have [MVF now] or [full feature in 3 months]?"
- "Can you live without [deferred feature] for the first 100 users?"
- "What triggers reconsidering [deferred feature]?"

## Phase 6: Documenting Rationale

### Confirming Understanding
- "Let me play back what I heard: [summary]. Accurate?"
- "Does this capture the essence of what you need?"
- "Am I missing any critical context?"
- "Is there anything I misunderstood?"

### Establishing Next Steps
- "How will we know this MVF succeeded?"
- "What metrics should we track?"
- "When should we revisit deferred features?"
- "Who else needs to approve this scope?"

### Managing Expectations
- "What will you tell [stakeholder] about the deferred features?"
- "How do we communicate this is v1, not the final version?"
- "What happens if users ask for [deferred feature]?"
- "Are you comfortable defending this reduced scope?"

## Pattern-Specific Questions

### When Proposing Read-Only Before Read-Write
- "Would being able to see [data] but not edit it still be valuable?"
- "How often do you need to view vs. modify?"
- "Could we add editing after we validate viewing is useful?"
- "What's more painful: not seeing data or not editing it?"

### When Proposing Manual Before Automated
- "How many times would you do this manually per week?"
- "At what volume does manual become unacceptable?"
- "Could an operator handle this for the first 100 users?"
- "What's the manual time cost vs. automation development time?"

### When Reducing Multiple Personas to One
- "Which user type has the most urgent need?"
- "Which persona represents 80% of usage?"
- "Could [secondary persona] use a simplified version?"
- "Would [primary persona] alone justify building this?"

### When Cutting Edge Case Handling
- "You said this happens 5% of the time—what's the workaround?"
- "Is the edge case painful or just annoying?"
- "Can support handle edge cases manually initially?"
- "What's the cost of not handling [edge case] gracefully?"

## Red Flag Questions

### When They Say Everything is Critical
- "Imagine I tell you we can only build one thing. What breaks if you don't have [feature]?"
- "Let's remove [feature]. Now walk me through using the remaining pieces. Does it still work?"
- "What's the difference between critical and important?"

### When They Can't Provide Examples
- "Can you think of a specific time this happened?"
- "Who on your team faced this recently?"
- "Walk me through the last instance with names and details"
- "If you can't think of an example, how do we know it's a real problem?"

### When They Focus on Solutions Not Problems
- "Let's step back—what problem does [solution] solve?"
- "Why that specific solution?"
- "What other ways could we solve this problem?"
- "Help me understand the problem, not the solution you envision"

### When They Anchor to Competitor Features
- "What job does [competitor feature] accomplish for their users?"
- "Is that the same job we're solving?"
- "Could we solve that job differently?"
- "Are we competing on features or on outcome quality?"

## Escalation Questions

### When You're Stuck
- "What am I not asking that I should be?"
- "What's obvious to you that might not be obvious to me?"
- "Is there context I'm missing?"
- "What question would you ask if you were me?"

### When Resistance is High
- "Help me understand what concerns you about this reduced scope"
- "What specifically would make this unacceptable?"
- "Is this about what users need or what stakeholders expect?"
- "What are you afraid will happen if we ship this MVF?"

### When You Need Permission to Be Bold
- "What if we're even more aggressive about scope reduction?"
- "Could we ship something even smaller?"
- "What's the absolute minimum that would be useful?"
- "What if we just built [smallest possible thing]?"

## Validation Questions

### Before Creating Documentation
- "One more time—what's the core job this MVF accomplishes?"
- "What are the 2-3 capabilities we're definitely including?"
- "What are we definitely deferring and why?"
- "When will we know to add the deferred features?"

### After Presenting MVF Definition
- "Does this MVF definition match what we discussed?"
- "Are you confident this scope is achievable?"
- "Will you be able to defend this to [stakeholder]?"
- "Is there anything I documented incorrectly?"

## Learning-Oriented Questions

### Discovering What to Measure
- "What would tell us this MVF is successful?"
- "What user behavior would we observe if this works?"
- "What would make you say 'we built the wrong thing'?"
- "What's the key metric that proves value?"

### Planning Iteration
- "What will we learn from shipping this?"
- "What question will this MVF answer?"
- "How will usage patterns inform v2?"
- "What signals will tell us to add [deferred feature]?"
