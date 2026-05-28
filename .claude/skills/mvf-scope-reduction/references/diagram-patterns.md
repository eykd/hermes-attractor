# Diagram Patterns for MVF Scope Reduction

Graphviz/DOT examples for visualizing scope reduction decisions. Use when creating decision tree or scope reduction diagrams.

## Pattern 1: Simple Scope Reduction Tree

Shows which capabilities are core vs. deferred with rationale.

```dot
digraph simple_scope {
    rankdir=TB;
    node [shape=box, style=rounded];

    // Proposed feature
    FEATURE [label="Proposed Feature:\nComprehensive Customer Portal",
             style="rounded,filled", fillcolor="#e3f2fd"];

    // Core job
    JOB [label="Core Job:\nWhen customers need support,\nthey want to check ticket status,\nso they can plan their work",
         style="rounded,filled", fillcolor="#fff3e0"];

    // Capabilities
    C1 [label="View Ticket Status", style="rounded,filled", fillcolor="#c8e6c9"];
    C2 [label="View Ticket History", style="rounded,filled", fillcolor="#c8e6c9"];
    C3 [label="Submit New Tickets", style="rounded,filled", fillcolor="#ffcdd2"];
    C4 [label="Live Chat Support", style="rounded,filled", fillcolor="#ffcdd2"];
    C5 [label="Knowledge Base Search", style="rounded,filled", fillcolor="#ffcdd2"];

    // Outcomes
    MVF [label="MVF (v1):\nView Status + History",
         style="rounded,filled", fillcolor="#4caf50", fontcolor="white", penwidth=2];
    DEFER [label="Deferred:\nSubmit, Chat, KB",
           style="rounded,filled", fillcolor="#ff9800", fontcolor="white"];

    // Connections
    FEATURE -> JOB [label="Extract core job"];
    JOB -> C1 [label="Core: 90% of inquiries"];
    JOB -> C2 [label="Core: Understand context"];
    JOB -> C3 [label="Secondary job"];
    JOB -> C4 [label="5% of cases"];
    JOB -> C5 [label="Solves different job"];

    C1 -> MVF;
    C2 -> MVF;
    C3 -> DEFER [label="Email works for now"];
    C4 -> DEFER [label="Rarely needed"];
    C5 -> DEFER [label="Out of scope"];
}
```

## Pattern 2: Frequency-Based Reduction

Shows scope decisions based on frequency of use.

```dot
digraph frequency_scope {
    rankdir=LR;
    node [shape=box, style=rounded];

    START [label="All Proposed\nCapabilities", style="rounded,filled", fillcolor="#bbdefb"];

    // Frequency nodes
    HIGH [label="High Frequency\n(Daily use)", shape=diamond, style=filled, fillcolor="#fff9c4"];
    MED [label="Medium Frequency\n(Weekly use)", shape=diamond, style=filled, fillcolor="#fff9c4"];
    LOW [label="Low Frequency\n(<Monthly)", shape=diamond, style=filled, fillcolor="#fff9c4"];

    // Outcomes
    MVF [label="MVF Scope\n(Ship now)", style="rounded,filled", fillcolor="#4caf50", fontcolor="white"];
    V2 [label="Version 2\n(After validation)", style="rounded,filled", fillcolor="#2196f3", fontcolor="white"];
    DEFER [label="Deferred\n(Reconsider later)", style="rounded,filled", fillcolor="#ff9800", fontcolor="white"];

    START -> HIGH;
    HIGH -> MVF [label="Yes"];
    HIGH -> MED [label="No"];
    MED -> V2 [label="Yes"];
    MED -> LOW [label="No"];
    LOW -> DEFER [label="Yes"];
}
```

## Pattern 3: Dependency Chain

Shows the natural sequence of capabilities and which to ship first.

```dot
digraph dependency_chain {
    rankdir=TB;
    node [shape=box, style=rounded];

    // Capabilities with dependencies
    C1 [label="Display Reports", style="rounded,filled", fillcolor="#c8e6c9"];
    C2 [label="Filter Reports", style="rounded,filled", fillcolor="#ffecb3"];
    C3 [label="Custom Report Builder", style="rounded,filled", fillcolor="#ffcdd2"];
    C4 [label="Share Reports", style="rounded,filled", fillcolor="#ffecb3"];
    C5 [label="Schedule Reports", style="rounded,filled", fillcolor="#ffcdd2"];

    // Dependencies
    C1 -> C2 [label="Requires"];
    C2 -> C3 [label="Requires"];
    C1 -> C4 [label="Requires"];
    C4 -> C5 [label="Requires"];

    // MVF boundary
    subgraph cluster_mvf {
        label="MVF (v1)";
        style=filled;
        fillcolor="#e8f5e9";
        C1;
    }

    subgraph cluster_v2 {
        label="Version 2";
        style=filled;
        fillcolor="#fff9e6";
        C2; C4;
    }

    subgraph cluster_defer {
        label="Deferred";
        style=filled;
        fillcolor="#ffebee";
        C3; C5;
    }
}
```

## Pattern 4: User Persona Reduction

Shows how reducing to one persona simplifies scope.

```dot
digraph persona_reduction {
    rankdir=TB;
    node [shape=box, style=rounded];

    FEATURE [label="Proposed:\nMulti-Role Dashboard", style="rounded,filled", fillcolor="#e3f2fd"];

    // Personas
    P1 [label="Admin\n(5% of users)", shape=ellipse, style=filled, fillcolor="#ffcdd2"];
    P2 [label="Manager\n(15% of users)", shape=ellipse, style=filled, fillcolor="#ffecb3"];
    P3 [label="End User\n(80% of users)", shape=ellipse, style=filled, fillcolor="#c8e6c9"];

    FEATURE -> P1;
    FEATURE -> P2;
    FEATURE -> P3;

    // Capabilities per persona
    A1 [label="User Management", style="rounded,filled", fillcolor="#ffcdd2"];
    A2 [label="System Config", style="rounded,filled", fillcolor="#ffcdd2"];
    M1 [label="Team Analytics", style="rounded,filled", fillcolor="#ffecb3"];
    M2 [label="Approval Queue", style="rounded,filled", fillcolor="#ffecb3"];
    U1 [label="Task List", style="rounded,filled", fillcolor="#c8e6c9"];
    U2 [label="Status Updates", style="rounded,filled", fillcolor="#c8e6c9"];

    P1 -> A1;
    P1 -> A2;
    P2 -> M1;
    P2 -> M2;
    P3 -> U1;
    P3 -> U2;

    // MVF focuses on 80%
    MVF [label="MVF:\nEnd User Features Only\n(80% of value)",
         style="rounded,filled", fillcolor="#4caf50", fontcolor="white", penwidth=2];
    U1 -> MVF;
    U2 -> MVF;

    DEFER [label="Defer:\nAdmin & Manager\nFeatures",
           style="rounded,filled", fillcolor="#ff9800", fontcolor="white"];
    A1 -> DEFER;
    A2 -> DEFER;
    M1 -> DEFER;
    M2 -> DEFER;
}
```

## Pattern 5: Manual to Automated Path

Shows progression from manual to automated features.

```dot
digraph manual_to_auto {
    rankdir=LR;
    node [shape=box, style=rounded];

    PROPOSED [label="Proposed:\nFully Automated\nReporting System", style="rounded,filled", fillcolor="#e3f2fd"];

    // Progression
    MANUAL [label="Manual Trigger\n+ Manual Export",
            style="rounded,filled", fillcolor="#c8e6c9"];
    SEMI [label="One-Click Generate\n+ Auto Export",
          style="rounded,filled", fillcolor="#ffecb3"];
    AUTO [label="Scheduled Generation\n+ Auto Distribution",
          style="rounded,filled", fillcolor="#ffcdd2"];

    PROPOSED -> MANUAL [label="Simplify"];
    MANUAL -> SEMI [label="Add automation"];
    SEMI -> AUTO [label="Full automation"];

    // Timeline
    MVF [label="MVF\n(Week 2)", shape=note, fillcolor="#4caf50", fontcolor="white"];
    V2 [label="v2\n(Week 8)", shape=note, fillcolor="#2196f3", fontcolor="white"];
    V3 [label="v3\n(Week 16)", shape=note, fillcolor="#9c27b0", fontcolor="white"];

    MANUAL -> MVF [style=dotted];
    SEMI -> V2 [style=dotted];
    AUTO -> V3 [style=dotted];
}
```

## Pattern 6: Integration Complexity

Shows how many integrations multiply complexity.

```dot
digraph integration_complexity {
    rankdir=TB;
    node [shape=box, style=rounded];

    CORE [label="Core Feature", style="rounded,filled", fillcolor="#4caf50", fontcolor="white"];

    // Integrations
    I1 [label="Slack", shape=cylinder, style=filled, fillcolor="#e0e0e0"];
    I2 [label="Salesforce", shape=cylinder, style=filled, fillcolor="#e0e0e0"];
    I3 [label="Google Sheets", shape=cylinder, style=filled, fillcolor="#e0e0e0"];
    I4 [label="Jira", shape=cylinder, style=filled, fillcolor="#e0e0e0"];

    CORE -> I1 [style=dashed, label="Real-time"];
    CORE -> I2 [style=dashed, label="Bi-directional"];
    CORE -> I3 [style=dashed, label="Auto-export"];
    CORE -> I4 [style=dashed, label="Webhooks"];

    // Complexity calculation
    CALC [label="4 integrations =\n16 connection points =\n4 weeks extra",
          shape=note, style=filled, fillcolor="#fff9c4"];

    // MVF alternative
    MVF [label="MVF Alternative:\nCore Feature Only\n+ CSV Export",
         style="rounded,filled", fillcolor="#4caf50", fontcolor="white", penwidth=2];

    CSV [label="Manual Import\nto Any System", shape=cylinder, style=filled, fillcolor="#c8e6c9"];
    MVF -> CSV [label="One-way"];

    TIMELINE [label="Saves 3 weeks\nValidates need", shape=note, style=filled, fillcolor="#c8e6c9"];
}
```

## Pattern 7: Edge Case Elimination

Shows the long tail of edge cases and where to draw the line.

```dot
digraph edge_cases {
    rankdir=TB;
    node [shape=box, style=rounded];

    HAPPY [label="Happy Path\n(80% of cases)", style="rounded,filled", fillcolor="#c8e6c9"];

    COMMON [label="Common Variations\n(15% of cases)", style="rounded,filled", fillcolor="#ffecb3"];

    EDGE [label="Edge Cases\n(4% of cases)", style="rounded,filled", fillcolor="#ffcdd2"];

    RARE [label="Rare Edge Cases\n(1% of cases)", style="rounded,filled", fillcolor="#f8bbd0"];

    HAPPY -> COMMON [label="Add handling"];
    COMMON -> EDGE [label="Add handling"];
    EDGE -> RARE [label="Add handling"];

    // MVF cutoff
    MVF_LINE [label="MVF Cutoff", shape=plaintext, fontsize=14, fontcolor="red"];

    HAPPY -> MVF_LINE [style=invis];

    // Effort vs. Value
    EFFORT [label="Development Effort:\n2 weeks → 4 weeks → 6 weeks → 8 weeks",
            shape=note, style=filled, fillcolor="#fff3e0"];
    VALUE [label="User Value:\n80% → 95% → 99% → 100%",
           shape=note, style=filled, fillcolor="#e8f5e9"];

    {rank=same; HAPPY; COMMON; EDGE; RARE;}
}
```

## Pattern 8: Read-Only to Read-Write

Shows the progression from viewing to editing capabilities.

```dot
digraph readonly_to_write {
    rankdir=LR;
    node [shape=box, style=rounded];

    // Stages
    VIEW [label="View Data Only", style="rounded,filled", fillcolor="#c8e6c9"];
    EDIT [label="Edit Single Records", style="rounded,filled", fillcolor="#ffecb3"];
    BULK [label="Bulk Edit", style="rounded,filled", fillcolor="#ffcdd2"];
    IMPORT [label="Import/Export", style="rounded,filled", fillcolor="#f8bbd0"];

    VIEW -> EDIT [label="Add edit capability"];
    EDIT -> BULK [label="Add bulk operations"];
    BULK -> IMPORT [label="Add data transfer"];

    // Decision points
    D1 [label="Users request\nedit?", shape=diamond, style=filled, fillcolor="#fff9c4"];
    D2 [label="Multiple edits\nneeded?", shape=diamond, style=filled, fillcolor="#fff9c4"];
    D3 [label="Large data\ntransfer?", shape=diamond, style=filled, fillcolor="#fff9c4"];

    VIEW -> D1 [style=dashed];
    EDIT -> D2 [style=dashed];
    BULK -> D3 [style=dashed];

    // MVF
    MVF [label="MVF: View Only\n(Validate value first)",
         style="rounded,filled", fillcolor="#4caf50", fontcolor="white", penwidth=2];
    VIEW -> MVF [style=bold];
}
```

## Pattern 9: Complete Feature Breakdown

Comprehensive view showing all reduction decisions.

```dot
digraph complete_breakdown {
    rankdir=TB;
    node [shape=box, style=rounded];

    PROPOSAL [label="Original Proposal:\nEnterprise Analytics Platform",
              style="rounded,filled", fillcolor="#e3f2fd", penwidth=2];

    // Categories
    DATA [label="Data Layer", style="rounded,filled", fillcolor="#f0f0f0"];
    VIZ [label="Visualizations", style="rounded,filled", fillcolor="#f0f0f0"];
    COLLAB [label="Collaboration", style="rounded,filled", fillcolor="#f0f0f0"];
    ADMIN [label="Administration", style="rounded,filled", fillcolor="#f0f0f0"];

    PROPOSAL -> DATA;
    PROPOSAL -> VIZ;
    PROPOSAL -> COLLAB;
    PROPOSAL -> ADMIN;

    // Data capabilities
    D1 [label="Connect to DB", style=filled, fillcolor="#c8e6c9"];
    D2 [label="Real-time Sync", style=filled, fillcolor="#ffcdd2"];
    D3 [label="Data Transformations", style=filled, fillcolor="#ffcdd2"];

    DATA -> D1;
    DATA -> D2;
    DATA -> D3;

    // Viz capabilities
    V1 [label="Basic Charts", style=filled, fillcolor="#c8e6c9"];
    V2 [label="Custom Dashboards", style=filled, fillcolor="#ffecb3"];
    V3 [label="Interactive Filters", style=filled, fillcolor="#ffcdd2"];

    VIZ -> V1;
    VIZ -> V2;
    VIZ -> V3;

    // Collab capabilities
    C1 [label="Share Reports", style=filled, fillcolor="#ffecb3"];
    C2 [label="Comments", style=filled, fillcolor="#ffcdd2"];
    C3 [label="Email Scheduling", style=filled, fillcolor="#ffcdd2"];

    COLLAB -> C1;
    COLLAB -> C2;
    COLLAB -> C3;

    // Admin capabilities
    A1 [label="User Management", style=filled, fillcolor="#ffcdd2"];
    A2 [label="Permissions", style=filled, fillcolor="#ffcdd2"];
    A3 [label="Audit Logs", style=filled, fillcolor="#ffcdd2"];

    ADMIN -> A1;
    ADMIN -> A2;
    ADMIN -> A3;

    // MVF box
    subgraph cluster_mvf {
        label="MVF (2 weeks)";
        style="rounded,filled";
        fillcolor="#e8f5e9";
        penwidth=2;
        D1; V1;
    }

    // v2 box
    subgraph cluster_v2 {
        label="Version 2 (4 weeks)";
        style="rounded,filled";
        fillcolor="#fff9e6";
        V2; C1;
    }

    // Deferred box
    subgraph cluster_defer {
        label="Deferred";
        style="rounded,filled";
        fillcolor="#ffebee";
        D2; D3; V3; C2; C3; A1; A2; A3;
    }
}
```

## Creating Your Own Diagram

### Basic Template

```dot
digraph your_scope {
    rankdir=TB;  // TB=top-to-bottom, LR=left-to-right
    node [shape=box, style=rounded];

    // Define your nodes
    PROPOSAL [label="Your Feature", style="rounded,filled", fillcolor="#e3f2fd"];

    CORE1 [label="Core Capability 1", style="rounded,filled", fillcolor="#c8e6c9"];
    CORE2 [label="Core Capability 2", style="rounded,filled", fillcolor="#c8e6c9"];
    DEFER1 [label="Deferred Item 1", style="rounded,filled", fillcolor="#ffcdd2"];
    DEFER2 [label="Deferred Item 2", style="rounded,filled", fillcolor="#ffcdd2"];

    // Define connections
    PROPOSAL -> CORE1 [label="Enables core job"];
    PROPOSAL -> CORE2 [label="Enables core job"];
    PROPOSAL -> DEFER1 [label="Low frequency"];
    PROPOSAL -> DEFER2 [label="Edge case"];

    // Group into MVF
    MVF [label="MVF", style="rounded,filled", fillcolor="#4caf50", fontcolor="white"];
    CORE1 -> MVF;
    CORE2 -> MVF;
}
```

### Color Scheme

Use these colors for consistency:
- **Core/MVF**: `fillcolor="#c8e6c9"` (light green) or `fillcolor="#4caf50"` (green) for MVF box
- **Version 2**: `fillcolor="#ffecb3"` (light yellow) or `fillcolor="#2196f3"` (blue)
- **Deferred**: `fillcolor="#ffcdd2"` (light red) or `fillcolor="#ff9800"` (orange)
- **Proposals/Context**: `fillcolor="#e3f2fd"` (light blue)
- **Decision points**: `fillcolor="#fff9c4"` (pale yellow)

### Rendering

To render the diagram:

```bash
# Create .dot file
cat > scope-diagram.dot << 'EOF'
[paste your dot code here]
EOF

# Render to PNG
dot -Tpng scope-diagram.dot -o scope-diagram.png

# Or render to SVG
dot -Tsvg scope-diagram.dot -o scope-diagram.svg
```

### Tips

1. **Keep it simple**: Don't try to show every detail
2. **Use grouping**: Subgraphs and clusters help organize
3. **Add context**: Labels explain decisions
4. **Show rationale**: Edge labels explain why things are deferred
5. **Use visual hierarchy**: Size, color, and position convey importance
