---
name: log-categorization
description: "Use when: (1) Deciding whether a log belongs to the domain, application, or infrastructure layer, (2) Naming loggers after Clean Architecture layers, (3) Setting the log `category` field, (4) Routing business events, request flow, or external-system logs correctly."
---

# Log Categorization

**Use when:** Determining whether logs belong to domain, application, or infrastructure layers following Clean Architecture principles

## Overview

Clean Architecture organizes code into layers with distinct responsibilities. Logs must respect these boundaries to maintain system clarity and debugging efficiency. This skill provides a decision framework to route logs to the correct category based on what the code is doing and where it lives in the architecture.

In Python, name loggers after the layer so categorization is reflected in the logger hierarchy as well as the `category` field:

- Domain: `hermes_attractor.domain`
- Application (use cases): `hermes_attractor.use_cases`
- Infrastructure (adapters/ports): `hermes_attractor.adapters`

## Decision Tree

### Need to Log a Business Event?

**When**: Recording something a stakeholder would care about - task completion, order placement, user registration

**Go to**: [references/domain-logging.md](./references/domain-logging.md)

### Need to Log Request Flow or Use Case Execution?

**When**: Tracking incoming requests, validation failures, use case orchestration, or request lifecycle

**Go to**: [references/application-logging.md](./references/application-logging.md)

### Need to Log External System Interaction?

**When**: Recording database queries, cache operations, API calls, or infrastructure health

**Go to**: [references/infrastructure-logging.md](./references/infrastructure-logging.md)

### Not Sure Which Category?

**When**: Unclear where a log belongs or need quick decision guidance

**Go to**: [references/decision-matrix.md](./references/decision-matrix.md)

## Quick Examples

```python
# Domain: business event a stakeholder cares about
logger.info(
    "task completed",
    extra={"event": "task.completed",
           "fields": {"category": "domain", "aggregate_type": "Task",
                      "aggregate_id": task_id, "domain_event": "TaskCompleted"}},
)

# Application: request flow and orchestration
logger.info(
    "complete task succeeded",
    extra={"event": "use_case.complete_task.succeeded",
           "fields": {"category": "application", "task_id": task_id,
                      "user_id": user_id, "duration_ms": 45}},
)

# Infrastructure: external system interaction
logger.info(
    "query succeeded",
    extra={"event": "db.query.succeeded",
           "fields": {"category": "infrastructure", "query_type": "UPDATE",
                      "table": "tasks", "duration_ms": 15}},
)
```

## Cross-References

- **[structured-logging](../structured-logging/SKILL.md)**: Provides the `JsonFormatter`/`SafeLoggerAdapter` implementation and base field definitions for all log categories

## Reference Files

- [references/decision-matrix.md](./references/decision-matrix.md) - Quick decision questions to determine log category
- [references/domain-logging.md](./references/domain-logging.md) - Log business events from entities and domain services
- [references/application-logging.md](./references/application-logging.md) - Log request flow and use case execution
- [references/infrastructure-logging.md](./references/infrastructure-logging.md) - Log database, cache, and external API interactions
