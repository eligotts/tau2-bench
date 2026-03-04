# Step 1: Concept + Topology Targets

## Purpose

Define what the domain is about, how many entities it has, and what structural
complexity to target. This is the only unconstrained step — everything after
this is locked to the entity names and topology you choose here.


## Input

A domain idea (freeform text), e.g. "coffee shop", "SRE infrastructure", "HR onboarding".


## Output

Three objects:

### WorldConcept
```
name: str              # alphanumeric + underscores, lowercase (e.g. "coffee_shop")
description: str       # 2-3 sentences describing the domain
entity_names: list[str]  # 4-8 PascalCase entity type names
```

### TopologyTargets
```
min_depth: int = 3         # 2-4. Longest gated path from entry to deepest node.
min_width: int = 4         # 4-6. Minimum breakable fields for perturbation diversity.
gating_density: str        # "low" | "medium" | "high"
branching: str             # "narrow" | "moderate" | "wide"
```

### Tau2Concept
```
archetype: str        # "diagnostic" | "troubleshoot" | "transaction" | "triage"
agent_role: str       # e.g. "customer support agent", "SRE on-call engineer"
user_role: str        # e.g. "customer", "new hire" (empty if agent-only)
agent_purpose: str    # 1-2 sentences
```

### Archetype Guide

- **diagnostic** — Sequential info-hiding. Agent discovers problems layer by layer.
  Gates hide downstream issues. (Customer service, auto repair)
- **troubleshoot** — Branching with user-as-instrument. User performs physical actions.
  Agent diagnoses, user executes fixes. (Tech support, device troubleshooting)
- **transaction** — Transparent state, guarded writes. Agent sees everything but must
  follow protocols and preconditions. (Online shopping, banking)
- **triage** — Classify and route. Agent gathers information, makes judgment calls,
  routes to correct destination. (Wellness helpline, intake)


## Constraints

- `name` must be alphanumeric with underscores, all lowercase
- `entity_names` must be unique PascalCase strings
- At least 2 entities (4+ recommended for diversity)
- `min_depth` must be <= number of entities (can't have depth 5 with 3 entities)
- `gating_density` must be one of: "low", "medium", "high"
- `branching` must be one of: "narrow", "moderate", "wide"


## Examples

### Coffee Shop (diagnostic, depth 3)
```yaml
WorldConcept:
  name: "coffee_shop"
  description: "A specialty coffee shop with loyalty program and subscriptions.
    Customers order drinks and food, earn loyalty points, and can subscribe
    to monthly plans."
  entity_names: [Customer, Order, MenuItem, LoyaltyAccount, Subscription]

TopologyTargets:
  min_depth: 3
  min_width: 4
  gating_density: "medium"
  branching: "moderate"

Tau2Concept:
  archetype: "diagnostic"
  agent_role: "coffee shop customer support agent"
  user_role: "customer"
  agent_purpose: "Resolve order issues, manage loyalty accounts, handle subscriptions"
```

### SRE Infrastructure (diagnostic, depth 4, agent-only)
```yaml
WorldConcept:
  name: "sre_infrastructure"
  description: "A Kubernetes cluster with deployments, pods, services, and monitoring.
    Agent diagnoses infrastructure issues by tracing alerts to root causes across
    config maps, deployments, and services."
  entity_names: [Cluster, Namespace, Deployment, Pod, ConfigMap, Service, Ingress,
                 Secret, MonitoringStack]

TopologyTargets:
  min_depth: 4
  min_width: 6
  gating_density: "high"
  branching: "moderate"

Tau2Concept:
  archetype: "diagnostic"
  agent_role: "SRE on-call engineer"
  user_role: ""
  agent_purpose: "Diagnose and fix infrastructure issues by tracing alerts through
    multi-layer Kubernetes stack to root causes"
```

### HR Onboarding (multi-actor, depth 3)
```yaml
WorldConcept:
  name: "hr_onboarding"
  description: "Employee onboarding workflow spanning IT setup, facilities,
    payroll, and manager approvals. Agent coordinates between multiple actors
    to complete the new hire process."
  entity_names: [Employee, Department, Manager, ITSetup, FacilitiesSetup,
                 PayrollRecord, OnboardingTask]

TopologyTargets:
  min_depth: 3
  min_width: 5
  gating_density: "high"
  branching: "wide"

Tau2Concept:
  archetype: "transaction"
  agent_role: "HR coordinator"
  user_role: "new hire"
  agent_purpose: "Coordinate the complete onboarding process across IT, facilities,
    payroll, and management"
```


## Anti-Patterns

**Too few entities (< 4)**
```yaml
# BAD: Only 2 entities — tasks will be flat and boring
entity_names: [Customer, Order]
```
With 2 entities there's only one relationship, one possible gate, depth 1.

**Unreachable depth target**
```yaml
# BAD: Can't have depth 5 with only 3 entities
entity_names: [Customer, Order, Product]
min_depth: 5
```
Depth = sequential gates, and gates live on edges between entities.

**Wrong archetype**
```yaml
# BAD: SRE is not "triage" — there's no routing decision.
# It's "diagnostic" — agent traces symptoms to root cause.
archetype: "triage"
```


## Verification

`verify_concept_with_topology()` checks:

| Check              | Severity | What It Catches                             |
|--------------------|----------|---------------------------------------------|
| `valid_name`       | ERROR    | Name has spaces, uppercase, or special chars |
| `min_entities`     | ERROR    | Fewer than 2 entity types                   |
| `unique_entities`  | ERROR    | Duplicate entity names                       |
| `entity_diversity` | WARNING  | Fewer than 4 entities (limits task variety)  |
| `depth_feasible`   | ERROR    | min_depth > entity count                     |
| `valid_gating_density` | ERROR | Not one of "low"/"medium"/"high"          |
| `valid_branching`  | ERROR    | Not one of "narrow"/"moderate"/"wide"        |


## Common Failures & Fixes

**"depth_feasible" error**: Reduce `min_depth` or add more entities. Each entity
adds at most one level of depth (one edge = one possible gate).

**"entity_diversity" warning**: Add more entity types. Think about what sub-objects
exist in the domain. A "coffee_shop" has Customers, Orders, OrderItems, MenuItems,
LoyaltyAccounts, Subscriptions — not just "Customer" and "Order".

**Choosing the right archetype**: Ask yourself: does the agent discover problems
layer by layer (diagnostic)? Does the user perform physical actions (troubleshoot)?
Does the agent follow protocols with transparent state (transaction)? Does the
agent classify and route (triage)?
