# Step 6: Policy Document (policy.md)

Generate the agent policy document — the instructions the AI agent follows when handling customer issues.

## Reference

- Read `docs/domain-authoring-guide.md` lines 209-256 (Policy section)
- Read `data/tau2/domains/library/policy.md` for the reference format

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json` — especially `tools` and `policy_sections`

## Output

Write to `data/tau2/domains/<domain_name>/policy.md`.

## Requirements

1. **Start with** `# <Domain> Support Policy` (e.g. `# Library Support Policy`).

2. **Identity Verification section:** Must include a section about verifying the customer's identity before making changes.

3. **Reference tool names specifically:** The policy should mention when to use each tool by name. This is critical — the agent uses the policy to decide which tool to call.

4. **Troubleshooting/Investigation workflow:** Describe the step-by-step process for diagnosing and resolving issues.

5. **Transfer to human section:** Describe situations the agent cannot resolve (maps to unfixable faults).

6. **Per-tool conditions:** Be specific about conditions for each operation:
   - When to use each WRITE tool
   - What preconditions must be met
   - What the agent should tell the user after each action

7. **User action instructions:** For each user confirmation tool, the policy should explicitly say "instruct the user to..." or "ask the customer to...". This is critical for user action feasibility.

8. **No code fences** — write raw markdown content.

## Alignment with Fault Layers

The policy must align with the fault layers in scenarios.py:
- For each fixable fault: the policy describes a workflow that leads to the correct fix tool
- For each unfixable fault: the policy says to transfer to a human
- The policy should NOT prescribe a different resolution than what the fault layer expects

## Validation

The validator will:
- Check length >= 100 characters
- Check for "identity" or "verification" mention
- Check that tool names from the domain spec are mentioned (>= 2)
