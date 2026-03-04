# Step 9: Policy

## Purpose

Write the agent's instructions — the policy document that tells the agent how
to behave, what tools to use, and what procedures to follow. This is generated
LAST because it must be grounded on actual tools (Step 6) and actual faults (Step 8).

The policy is what the agent sees. It should reflect the gate structure (progressive
disclosure), the rules (constraints on actions), and the fault groups (what can
go wrong) — without revealing information the agent should discover on its own.


## Input (locked from Steps 1-8)

- Full schema (Steps 1-2)
- Gate structure (Step 3) — informs "check X before accessing Y"
- Rules (Step 4) — informs preconditions and protocols
- Tool suite (Step 6) — every tool referenced must exist
- Fault groups (Step 8) — every fault should have a resolution path
- Resolution instruction (Step 8) — the overall outcome


## Output

A `PolicySpec` object.

### PolicySpec
```
structured_rules: list[PolicyRule]  # For verification (machine-readable)
prose: str                          # Full policy document (given to agent)
```

### PolicyRule
```
condition: str               # When this rule applies
action: str                  # What the agent should do
tools_referenced: list[str]  # Tools involved (must exist in tool suite)
priority: int = 0            # Higher = more important
```


## Key Principle: REACTIVE, Not PRESCRIPTIVE

The most important rule for writing policies:

**REACTIVE**: "When X is wrong, do Y"
**PRESCRIPTIVE**: "Always do Y"

Prescriptive language causes runtime failures because of selective faults.
If the policy says "always check the loyalty points" but only some tasks have
broken loyalty points, the agent wastes time on correct data and may overwrite
it with wrong values.

```
# BAD (prescriptive):
"In every interaction, verify the customer's account status, check their
order history, review loyalty points, and confirm subscription details."

# GOOD (reactive):
"When the customer reports account access issues, check account_status using
get_customer. If suspended or frozen, reactivate with update_customer_account_status.
When the customer reports order problems, retrieve order details with get_order."
```


## Structure of a Good Policy

### 1. Role and Purpose
Brief description of the agent's role. Draw from Tau2Concept (Step 1).

### 2. Authentication / Entry Protocol
Reflects actor gates from Step 3. "Before accessing sensitive account details,
request identity verification."

### 3. Diagnostic Workflow
Reflects gate structure: "Start by checking the customer's account status.
If the account is active, proceed to check orders." This mirrors the graph
traversal the agent will actually perform.

### 4. Resolution Procedures
One section per fault category. Each describes the reactive pattern:
"When [condition], use [tool] to [fix]."

### 5. Escalation
For unfixable faults: "If [condition that can't be fixed], transfer to
a specialist."

### 6. Available Tools Reference
List of tools the agent has access to, briefly described.


## Examples

### Customer Service Policy (excerpt)
```markdown
# Coffee Shop Support Policy

## Your Role
You are a customer support agent for BeanBrew Coffee. Help customers
resolve issues with their accounts, orders, loyalty programs, and subscriptions.

## Authentication
Before accessing loyalty account or subscription details, ask the customer
to verify their identity. Do not access these sections until identity is confirmed.

## Diagnostic Approach
1. Start by retrieving the customer's profile with get_customer(customer_id)
2. If the account is suspended or frozen, reactivate it with
   update_customer_account_status before proceeding
3. Once the account is active, check for order issues with get_order
4. Check loyalty account only if the customer reports points or tier issues
5. Check subscription only if the customer reports subscription issues

## Resolution Procedures

### Account Issues
When the customer's account_status is "suspended" or "frozen":
- Use update_customer_account_status to set it back to "active"
- Confirm with the customer that they can now access their account

### Order Issues
When an order shows incorrect status:
- Use update_order_status to correct it

### Loyalty Issues
When loyalty points are incorrect:
- Look up the correct points value from the account history
- Use update_loyalty_account_points to restore the correct amount

When the loyalty tier is wrong:
- Use update_loyalty_account_tier to set the correct tier

## Tools Available
- get_customer(customer_id) — retrieve customer profile
- get_order(order_id) — retrieve order details
- get_loyalty_account(loyalty_id) — retrieve loyalty info
- update_customer_account_status(customer_id, account_status) — fix account
- update_order_status(order_id, status) — fix order
- update_loyalty_account_points(loyalty_id, points) — fix points
- update_loyalty_account_tier(loyalty_id, tier) — fix tier
```

### SRE Policy (excerpt)
```markdown
# SRE On-Call Policy

## Your Role
You are an SRE engineer responding to infrastructure alerts. Diagnose root
causes and fix issues across the Kubernetes stack.

## Diagnostic Approach
1. Start with active alerts: get_alerts()
2. Follow alert targets to identify affected resources
3. For deployment issues: check replicas, then pod status, then logs
4. For service issues: check endpoints, then ingress configuration
5. Always trace symptoms to root cause before applying fixes

## When Deployment Has Zero Replicas
Scale up first with kubectl_scale, then check pod logs to find why pods crashed.
Often the root cause is a bad ConfigMap — check config_ref and update_configmap
if the configuration is wrong.

## When Pods Are CrashLooping
Read logs with kubectl_logs to identify the error. Common causes:
- Bad database connection string in ConfigMap
- Missing secrets
- Image version issues
```

### Structured Rules for Verification
```python
PolicySpec(
    structured_rules=[
        PolicyRule(
            condition="customer account_status is suspended or frozen",
            action="reactivate account",
            tools_referenced=["update_customer_account_status"],
            priority=1
        ),
        PolicyRule(
            condition="order status is incorrect",
            action="correct order status",
            tools_referenced=["update_order_status"],
            priority=0
        ),
        PolicyRule(
            condition="loyalty points are wrong",
            action="restore correct loyalty points",
            tools_referenced=["update_loyalty_account_points"],
            priority=0
        ),
    ],
    prose="# Coffee Shop Support Policy\n..."  # The full markdown above
)
```


## Anti-Patterns

**Prescriptive language ("always do X")**
```markdown
# BAD: Forces agent to check everything regardless of the task
"In every case, you must:
1. Always check account status
2. Always verify order history
3. Always review loyalty points"
```
This causes failures when only some of these are broken. The agent may overwrite
correct data or waste actions.

**Revealing hidden information**
```markdown
# BAD: Tells agent about the gate structure they should discover
"Note: if the account is suspended, you won't be able to see orders.
Fix the account first, then check orders."
```
This removes the progressive disclosure challenge. The agent should discover
this through tool usage (get_order fails → investigate why → find account issue).
Use lighter language: "Start by checking the customer's account status."

**Referencing non-existent tools**
```markdown
# BAD: "fix_account" doesn't exist — the real tool is update_customer_account_status
"Use fix_account() to resolve account issues."
```
Always use exact tool names from Step 6.

**Overly detailed step-by-step**
```markdown
# BAD: So prescriptive it removes all agent reasoning
"Step 1: Call get_customer(customer_id). Step 2: If account_status == 'suspended',
call update_customer_account_status(customer_id, 'active'). Step 3: ..."
```
The policy should guide, not script. Use "when X is wrong, use Y to fix it"
rather than "call X, then call Y, then call Z."


## Verification

`verify_policy()` checks:

| Check                    | Severity | What It Catches                                |
|--------------------------|----------|------------------------------------------------|
| `rule_tool_exists`       | ERROR    | Tool in tools_referenced not in tool suite     |
| `fault_resolution_coverage` | WARNING | Fault group has no resolution path in policy |
| `prescriptive_antipattern`  | WARNING | Prose contains "always call"/"always use"/"must always"/"in every case" |


## Common Failures & Fixes

**"rule_tool_exists" error**: Check tool names against the tool suite from Step 6.
Auto-derived tools follow the pattern `update_{entity}_{field}` in snake_case.
For example, `update_customer_account_status`, not `fix_account` or
`update_account_status`.

**"fault_resolution_coverage" warning**: Add a section to the policy for the
uncovered fault group's fix tool. Every fault group needs a resolution path —
a section in the policy that tells the agent when and how to use the fix tool.

**"prescriptive_antipattern" warning**: Replace "always" language with conditional
language. Instead of "always check loyalty points", write "when the customer
reports loyalty issues, check points with get_loyalty_account".
