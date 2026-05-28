# Mermaid Workflow Diagram Patterns

Load this file when creating workflow diagrams. It provides templates and examples for common workflow visualization patterns using Mermaid.

## Basic Sequential Workflow

Simple linear process with no branches:

```mermaid
graph TD
    A[Customer submits form]
    B[Receive notification]
    C[Review submission]
    D[Process request]
    E[Send confirmation]

    A --> B
    B --> C
    C --> D
    D --> E
```

## Decision Point Workflow

Process with conditional branches:

```mermaid
graph TD
    A[Start: Receive request]
    B{Check amount}
    C[Auto-approve]
    D[Manager review needed]
    E[Finance review needed]
    F[Notify requester]

    A --> B
    B -->|< $5K| C
    B -->|$5K - $25K| D
    B -->|> $25K| E
    C --> F
    D --> F
    E --> F
```

## Approval Workflow with Rejection Path

Process with approval/rejection loops:

```mermaid
graph TD
    A[Submit document]
    B[Manager reviews]
    C{Approved?}
    D[Legal review]
    E{Legal approved?}
    F[Publish]
    G[Request changes]
    H[Reject with reason]

    A --> B
    B --> C
    C -->|Yes| D
    C -->|No| G
    G --> A
    D --> E
    E -->|Yes| F
    E -->|No| H
```

## Parallel Process Workflow

Steps that can happen simultaneously:

```mermaid
graph TD
    A[Start project]
    B[Design phase]
    C[Development]
    D[Documentation]
    E[Testing]
    F[Integration]
    G[Launch]

    A --> B
    B --> C
    B --> D
    C --> E
    D --> E
    E --> F
    F --> G
```

## Multi-Actor Swimlane Workflow

Using subgraphs to show who does what:

```mermaid
graph TD
    subgraph Customer
        A[Submit request]
        F[Receive response]
    end

    subgraph Support_Team
        B[Triage ticket]
        C{Complexity?}
    end

    subgraph Technical_Team
        D[Investigate issue]
        E[Implement solution]
    end

    A --> B
    B --> C
    C -->|Simple| Support_Team
    C -->|Complex| D
    D --> E
    E --> F
```

## Error Handling and Retry Logic

Process with failure paths:

```mermaid
graph TD
    A[API request]
    B{Success?}
    C[Process data]
    D{Retry?}
    E[Log error]
    F[Alert team]
    G[Manual intervention]

    A --> B
    B -->|Yes| C
    B -->|No| D
    D -->|< 3 attempts| A
    D -->|>= 3 attempts| E
    E --> F
    F --> G
```

## Long-Running Process with Checkpoints

Process with save points:

```mermaid
graph TD
    A[Start]
    B[Phase 1: Planning]
    C[Checkpoint: Save draft]
    D[Phase 2: Execution]
    E[Checkpoint: Review milestone]
    F[Phase 3: Completion]
    G[Final delivery]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G

    C -.Can resume here.-> D
    E -.Can resume here.-> F
```

## Workflow with Handoffs and Wait States

Showing bottlenecks and waiting periods:

```mermaid
graph TD
    A[Create request]
    B[Submit for approval]
    C[Wait: Manager review]
    D{Approved?}
    E[Wait: Legal review]
    F{Legal approved?}
    G[Execute]
    H[Return to requester]

    A --> B
    B --> C
    C --> D
    D -->|Yes| E
    D -->|No| H
    E --> F
    F -->|Yes| G
    F -->|No| H
    G --> Complete

    style C fill:#ffcccc
    style E fill:#ffcccc
```

## Color Coding for Workflow States

Use colors to indicate different types of steps:

```mermaid
graph TD
    A[Normal step]
    B{Decision point}
    C[Automated step]
    D[Bottleneck]
    E[Manual step]
    F[End state]

    A --> B
    B --> C
    B --> D
    D --> E
    E --> F

    style A fill:#90EE90
    style B fill:#ffffcc
    style C fill:#87CEEB
    style D fill:#ffcccc
    style E fill:#DDA0DD
    style F fill:#98FB98
```

## Style Reference

Common color codes for workflow elements:

- `style X fill:#90EE90` - Normal/happy path (light green)
- `style X fill:#ffcccc` - Bottleneck/problem area (light red)
- `style X fill:#ffffcc` - Decision point (light yellow)
- `style X fill:#87CEEB` - Automated step (light blue)
- `style X fill:#DDA0DD` - Manual/human step (light purple)
- `style X fill:#FFE4B5` - Waiting state (moccasin)
- `style X fill:#98FB98` - Completion (pale green)

## Arrow Types

Different arrow styles for different relationships:

```mermaid
graph TD
    A[Step 1]
    B[Step 2]
    C[Step 3]
    D[Step 4]
    E[Step 5]

    A --> B
    A -.Optional.-> C
    B ==> D
    D --> E
    C -.-> E
```

- `-->` Solid arrow (normal flow)
- `-.->` Dotted arrow (optional/conditional)
- `==>` Thick arrow (primary/critical path)

## Complex Real-World Example: Purchase Request Process

```mermaid
graph TD
    A[Employee creates request]
    B[Submit to system]
    C{Amount check}
    D[Auto-approve]
    E[Manager reviews]
    F{Manager decision}
    G[Finance reviews]
    H{Finance decision}
    I[Director reviews]
    J{Director decision}
    K[Vendor contacted]
    L[PO generated]
    M[Goods received]
    N[Invoice matched]
    O[Payment processed]
    P[Requester notified]
    Q[Rejection - resubmit]
    R[Rejection - cancel]

    A --> B
    B --> C
    C -->|< $500| D
    C -->|$500-$5K| E
    C -->|> $5K| G

    D --> K

    E --> F
    F -->|Approve| K
    F -->|Request changes| Q
    F -->|Reject| R

    G --> H
    H -->|Approve| I
    H -->|Request changes| Q
    H -->|Reject| R

    I --> J
    J -->|Approve| K
    J -->|Request changes| Q
    J -->|Reject| R

    Q --> A
    R --> P

    K --> L
    L --> M
    M --> N
    N --> O
    O --> P

    style C fill:#ffffcc
    style F fill:#ffffcc
    style H fill:#ffffcc
    style J fill:#ffffcc
    style E fill:#ffcccc
    style G fill:#ffcccc
    style I fill:#ffcccc
    style K fill:#87CEEB
    style L fill:#87CEEB
    style O fill:#87CEEB
```

## Tips for Effective Diagrams

1. **Keep nodes concise**: Use short labels (< 5 words)
2. **Show the critical path**: Use thicker arrows or colors
3. **Highlight pain points**: Use red/orange for bottlenecks
4. **Limit complexity**: Break very complex workflows into multiple diagrams
5. **Add a legend**: When using colors, explain what they mean
6. **Test rendering**: Verify the diagram displays correctly
7. **Use consistent direction**: Top-to-bottom (TD) is most common
8. **Group related steps**: Use subgraphs for different actors or systems

## When to Use Which Pattern

- **Sequential**: Simple, linear processes without branches
- **Decision Point**: Processes with clear branching logic
- **Approval**: Document review and approval workflows
- **Parallel**: Tasks that can happen simultaneously
- **Swimlane**: When showing responsibilities across teams
- **Error Handling**: Processes with retry/failure logic
- **Checkpoints**: Long processes with save points
- **Handoffs**: When highlighting waiting periods and bottlenecks
