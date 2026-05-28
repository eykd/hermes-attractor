# Decision Matrix: Where Does This Log Belong?

**Purpose**: Quick reference for categorizing logs according to Clean Architecture boundaries

## When to Use

When adding a log statement and you're uncertain whether it belongs to the domain, application, or infrastructure category. This decision matrix provides concrete questions to route logs to the correct category.

## Decision Questions

| Question                                                          | Yes → Category |
| ----------------------------------------------------------------- | -------------- |
| Does it describe a business event a stakeholder would care about? | Domain         |
| Does it describe request flow, validation, or use case execution? | Application    |
| Does it describe database, cache, or external API interaction?    | Infrastructure |
| Is it about the request/response lifecycle?                       | Application    |
| Is it about connection pooling, retries, or timeouts?             | Infrastructure |
| Would a product manager want to see this in a report?             | Domain         |

## Usage Pattern

Ask questions from top to bottom. The first "yes" answer determines the category.

```python
# Question: "Would a product manager care about this?"
# Answer: Yes → Domain log
logger.info(
    "task completed",
    extra={"event": "task.completed",
           "fields": {"category": "domain", "aggregate_type": "Task", "aggregate_id": task_id}},
)

# Question: "Is this about request flow?"
# Answer: Yes → Application log
logger.info(
    "complete task started",
    extra={"event": "use_case.complete_task.started",
           "fields": {"category": "application", "task_id": task_id}},
)

# Question: "Is this about database interaction?"
# Answer: Yes → Infrastructure log
logger.info(
    "query succeeded",
    extra={"event": "db.query.succeeded",
           "fields": {"category": "infrastructure", "table": "tasks", "duration_ms": 15}},
)
```

## Common Scenarios

### Task Completion

**Event**: User marks a task as complete
**Category**: Domain (business event)
**Why**: Stakeholders care about task completion rates

### Validation Failure

**Event**: Request fails input validation
**Category**: Application (request flow issue)
**Why**: It's about the request lifecycle, not business logic

### Database Timeout

**Event**: Database query exceeds timeout
**Category**: Infrastructure (external system issue)
**Why**: It's about infrastructure health, not business events

## Edge Cases

### Boundary Between Domain and Application

If an event describes _what happened_ in business terms: Domain
If an event describes _how the system processed_ a request: Application

**Example**: Task status changed

- Domain: `task.status.changed` (the business event)
- Application: `use_case.update_task.succeeded` (the processing event)

### Boundary Between Application and Infrastructure

If an event involves I/O or external systems: Infrastructure
If an event involves request orchestration without I/O: Application

**Example**: Caching

- Application: `use_case.get_task.cache_decision_made` (orchestration)
- Infrastructure: `cache.hit` (actual cache operation)
