# Step 1: Domain Specification

Generate a structured JSON specification for the domain. This spec drives all subsequent steps.

## Reference

- Read `docs/domain-authoring-guide.md` lines 79-115 (Design Concept) and 714-1123 (Recipe Engine)

## Output

Save the JSON to `data/tau2/domains/<domain_name>/domain_spec.json`.

## Required JSON Structure

```json
{
  "domain_name": "<snake_case_name>",
  "description": "<one-sentence description>",
  "entities": [
    {
      "name": "<EntityName>",
      "fields": [{"name": "<field>", "type": "<type>", "description": "<desc>"}],
      "is_primary": true
    }
  ],
  "tools": [
    {"name": "<tool_name>", "type": "READ|WRITE|GENERIC", "description": "<desc>", "args": [{"name": "<arg>", "type": "<type>"}]}
  ],
  "user_tools": [
    {"name": "<tool_name>", "type": "READ|WRITE", "description": "<desc>", "args": [{"name": "<arg>", "type": "<type>"}]}
  ],
  "fault_groups": [
    {
      "group_name": "<group>",
      "faults": [
        {"name": "<fault>", "description": "<desc>", "init_action": "<what breaks>", "fix_tool": "<tool>", "entity_field_affected": "<field>", "unfixable": false, "user_fix_tools": ["<optional user tools>"]}
      ]
    }
  ],
  "policy_sections": ["<section titles>"],
  "sync_rules": [
    {"agent_field": "<field>", "user_field": "<field>", "description": "<desc>"}
  ],
  "assertion_helpers": [
    {"name": "<assert_*>", "description": "<desc>", "env_type": "assistant|user"}
  ],
  "setup_helpers": [
    {"name": "<set_*>", "description": "<desc>", "env_type": "assistant|user"}
  ]
}
```

## Requirements

### Entities
- Include 3-5 entity types. At least one primary entity.
- Primary entity is the "customer" — the entity the user identifies as.

### Tools
- At least 3 READ tools (lookups by ID, by name, get children by parent ID)
- At least 3 WRITE tools (fix actions for faults)
- 1 GENERIC tool: `transfer_to_human`
- Entity navigation: for every child entity with a foreign key to the primary entity, include a READ tool that looks up children by parent ID

### User Tools
- 3-5 WRITE tools for user-side actions (confirmations, acknowledgments, device toggles)
- These are actions the agent instructs the user to perform on their end
- Design distinct tools for different fault groups to avoid action deduplication

### Fault Groups
- 6-8 fault groups. At least 3 groups should have 2+ faults each.
- Target ~300+ combinations per entity (product of (1+layers) per group, minus 1).
- Sweet spot: [2,2,2,1,1,1,2] = 7 groups giving 647 combos/entity.

### Difficulty Calibration
- Each fixable fault should require 2 actions (atoms) to resolve:
  1. Agent-side fix action (e.g. reinstate_hold)
  2. User-side confirmation action (e.g. confirm_hold_pickup)
- This 2-atom-per-layer pattern creates challenging tasks — with 4-5 groups active, tasks average 8-10 total actions.
- Do NOT create layers with only 1 action (just the fix) — those produce trivially easy tasks.

### Semantic Distinctness
- Each fault group must be SEMANTICALLY DISTINCT — different DB fields, different fix tools, different reasoning.
- Do NOT create layers that are the same tool with a different amount (e.g. '$40 credit' and '$75 credit' both using issue_credit).
- Within a group, mutually exclusive layers should differ in resolution strategy.

### Unfixable Faults
- Some faults should be marked `unfixable: true` — issues no available tool can resolve.
- Do NOT mix unfixable faults into the same groups as fixable faults.
- List them in a SEPARATE section — they become a separate FaultLayerConfig with max_faults=1 and max_tasks_per_bin=1.
- Target 2-3 unfixable faults.
