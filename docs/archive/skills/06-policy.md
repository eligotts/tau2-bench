# Step 6: Policy Document (policy.md)

Generate the agent policy document — the instructions the AI agent follows when handling customer issues.

## Reference

- Read `docs/domain-authoring-guide.md` lines 209-256 (Policy section)
- Read `data/tau2/domains/auto_repair/policy.md` for the reference format (note how it names every user tool explicitly)
- Read `docs/skills/00-archetype.md` for your domain's archetype-specific policy pattern

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json` — especially `tools`, `policy_sections`, and `archetype`

## Output

Write to `data/tau2/domains/<domain_name>/policy.md`.

## Requirements

1. **Start with** `# <Domain> Support Policy` (e.g. `# Library Support Policy`).

2. **Identity Verification section:** Must include a section about verifying the customer's identity before making changes.

3. **Reference tool names specifically:** The policy should mention when to use each tool by name. This is critical — the agent uses the policy to decide which tool to call.

4. **Troubleshooting/Investigation workflow:** Describe the step-by-step process for diagnosing and resolving issues. The STRUCTURE of this workflow depends on the archetype (see below).

5. **Transfer to human section:** Describe situations the agent cannot resolve (maps to unfixable faults).

6. **Per-tool conditions:** Be specific about conditions for each operation:
   - When to use each WRITE tool
   - What preconditions must be met
   - What the agent should tell the user after each action

7. **User action guidance (CRITICAL):** The policy is the ONLY way the agent learns about user tools. The agent cannot see the user's tool list — it only sees its own tools and the policy. For every user tool (approve, confirm, pay, acknowledge, toggle, reboot, etc.), the policy MUST explicitly tell the agent to instruct the user. Use the exact user tool name so the agent can relay it:
   - GOOD: "After completing repairs, instruct the customer to use their approve_repairs tool to authorize the work."
   - GOOD: "Ask the customer to use their check_network_status tool and report the results."
   - BAD: "The customer should confirm the repair." (agent doesn't know which tool)
   - BAD: No mention at all (agent has no way to guide the user)

   Without this, the agent cannot guide the user to call their tools, and user-side actions will never happen.

8. **No code fences** — write raw markdown content.

## Policy Style by Archetype

The policy structure must match your domain's archetype. Each archetype has a natural policy pattern:

### Archetype A (Sequential Diagnostic): Iterative Diagnostic Workflow

The policy describes a progressive investigation where the agent must fix upstream problems before investigating downstream ones:

```markdown
## Diagnostic Workflow
1. Check the customer's account status first
2. If the account is locked or suspended, resolve that BEFORE proceeding —
   you cannot view detailed records until the account is in good standing
3. Once the account is accessible, investigate outstanding issues
4. After resolving each issue, re-check — fixing one problem
   may reveal additional issues that were previously hidden
```

The policy's workflow must mirror the tool behavior: if `get_account()` returns "Account locked" when membership is expired, the policy must tell the agent to fix membership first and re-query.

### Archetype B (Branching Troubleshooter): Decision Tree

The policy describes branching diagnostic paths where the agent guides the user through testing and fixing:

```markdown
## Troubleshooting: No Service
1. Ask the customer to use their check_network_status tool and report results.
2. If airplane mode is on, instruct the customer to use their toggle_airplane_mode tool.
   Then ask them to check_network_status again.
3. If SIM card is not detected, instruct the customer to use their reseat_sim_card tool,
   then reboot using their reboot_device tool.
4. If all device checks pass but service is still unavailable,
   transfer to a network specialist using transfer_to_human.
```

### Archetype C (Transaction Processor): Prescriptive Protocol

The policy describes mandatory steps for each transaction type, with precondition checks:

```markdown
## Refund Processing
For every refund request:
1. Look up the transaction. Verify it has not already been refunded.
2. Check eligibility: transactions older than 90 days are not refundable.
   Inform the customer and do NOT process the refund.
3. Confirm the refund amount with the customer.
4. Process the refund using process_refund.
5. Instruct the customer to use their confirm_refund tool.
```

### Archetype D (Triage / Classification): Classification Criteria

The policy describes how to categorize and route issues:

```markdown
## Ticket Classification
Gather information from the customer, then classify:
- Hardware issues (physical device problems): route to hardware team
- Software issues (app crashes, errors): route to software team
- Network issues (connectivity, speed): route to network team
Use classify_ticket with the appropriate category, then route_ticket.
```

## Reactive vs Prescriptive Policies

Both reactive and prescriptive policies are valid — the right choice depends on the archetype:

- **Reactive policies** ("When X is broken, fix it"): Best for **Archetype A** (sequential diagnostic) where faults are selectively injected. The agent only acts when the situation calls for it.
- **Prescriptive policies** ("For every call, follow these steps"): Valid for **Archetype C** (transaction processor) where the protocol is always the same. **BUT** you must add overwrite guards to WRITE tools — if the policy says "always do X" but the fault that breaks X is only sometimes active, the agent will overwrite correct data. Add guards like: "If the concern is already assessed, skip this step."
- **Branching policies** ("If X, check Y; else check Z"): Best for **Archetype B** (branching troubleshooter).
- **Classification policies** ("Gather info, then categorize"): Best for **Archetype D** (triage).

The key safety rule: **if the policy prescribes calling a WRITE tool, that tool must guard against overwriting already-correct values.** This prevents cascading failures when the corresponding fault is not active.

## Alignment with Fault Layers

The policy must align with the fault layers in scenarios.py:
- For each fixable fault: the policy describes a workflow that leads to the correct fix tool
- For each unfixable fault: the policy says to transfer to a human
- The policy should NOT prescribe a different resolution than what the fault layer expects

## No Overfitting to the Agent

The policy is a real-world operating procedure, not a cheat sheet for the benchmark. It should describe WHAT the agent's job is and WHAT tools are available — not hand-hold the agent through the exact sequence of actions a specific task requires.

**Anti-patterns (overfitting):**
- "Do NOT skip the customer check" — coaching the agent to not skip a step
- "The server cannot determine the physical cause remotely" — explaining WHY the information architecture works the way it does. The agent should discover this from tool output.
- "If the diagnostic shows unreachable, you MUST ask the user to run check_my_connection" — the policy should mention the tool exists and when it's useful, but the information structure (the tool returning "unreachable" with no details) should be what forces the agent to ask.

**Correct patterns:**
- Name the tools and describe when they're relevant: "If the device is unreachable, ask the customer to check their connection using their check_my_connection tool."
- Describe the workflow naturally: "Use the customer's report to determine the specific issue."
- Let the tool output drive behavior: if `run_remote_diagnostic` returns "unreachable" with no cause, a competent agent will ask the user. The policy doesn't need to explain why.

**The principle:** Difficulty should come from the information architecture (tool design, observability boundaries, gated visibility), not from policy complexity. A well-designed domain makes the correct action obvious from the policy but IMPOSSIBLE without the right information — and the information is only available through the right sequence of tool calls.

## Difficulty-Enforcing Policy Patterns

The policy is a primary driver of domain difficulty. A policy that's too simple or too transparent produces easy domains regardless of how many fault groups exist. The following patterns are **required** for all archetypes.

### Decision Trees (All Archetypes)

Every policy must contain at least one branching section where the agent's next action depends on what it observes. Even Archetype A (reactive) and Archetype C (prescriptive) policies need decision points — not just linear checklists.

- **Anti-pattern:** "1. Check account. 2. Fix issue. 3. Confirm." (linear, no branching)
- **Required pattern:** "1. Check account status. 2. If suspended, follow Suspension Resolution. If active but restricted, follow Restriction Removal. If active and clear, investigate specific complaints." (branching)
- **Minimum:** At least 1 section with 3+ branches for Archetype B; at least 1 section with 2+ branches for all other archetypes.

### Computed Value Instructions

The policy must describe HOW the agent computes or derives at least 2 values that are not directly given by the user. This forces the agent to reason, not just relay information.

- **Anti-pattern:** "Process the refund for the amount the customer requests."
- **Required pattern:** "Calculate the refund amount as the original transaction amount minus any prior partial refunds. If the customer is in a loyalty tier, apply the tier discount rate before computing the refund."
- **Minimum:** At least 2 computation/derivation instructions across the policy.

### Ordering Constraints

When applicable, the policy must explicitly state fix ordering requirements. This prevents agents from solving everything in a single unordered pass.

- **Anti-pattern:** "Fix all reported issues." (no ordering)
- **Required pattern:** "Resolve account access issues BEFORE investigating billing discrepancies — billing tools require an active account." / "Ask the customer to run diagnostics BEFORE applying any fixes."
- **Minimum:** At least 1 explicit ordering constraint for Archetypes A, B, and C. Archetype D must have classification-before-routing.

### Denial Conditions

Every policy must include at least one section where the agent must REFUSE to act — a situation where the correct behavior is to deny the request, not fulfill it.

- **Anti-pattern:** Every section ends with the agent fixing the issue. The agent always says "yes."
- **Required pattern:** "Do NOT process refunds for transactions older than 90 days. Inform the customer of the policy and transfer to a supervisor if they insist." / "If the device is beyond warranty, do NOT offer free repair — provide paid service options only."
- **Minimum:** At least 1 denial condition. This aligns with having unfixable fault layers.

## Validation

The validator will:
- Check length >= 100 characters
- Check for "identity" or "verification" mention
- Check that tool names from the domain spec are mentioned (>= 2)
