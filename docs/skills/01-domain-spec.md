# Step 1: Domain Specification

Generate a structured JSON specification for the domain. This spec drives all subsequent steps.

## Reference

- Read `docs/domain-authoring-guide.md` lines 79-115 (Design Concept) and 714-1123 (Recipe Engine)
- Read `docs/skills/00-archetype.md` for your domain's archetype patterns

## Output

Save the JSON to `data/tau2/domains/<domain_name>/domain_spec.json`.

## Required JSON Structure

```json
{
  "domain_name": "<snake_case_name>",
  "description": "<one-sentence description>",
  "archetype": "sequential_diagnostic | branching_troubleshooter | transaction_processor | triage_classification",
  "archetype_notes": "<why this archetype fits + any secondary influences>",
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

The number and type of user tools depend on the domain archetype:

| Archetype | User WRITE Tools | Typical Pattern |
|-----------|-----------------|-----------------|
| A: Sequential Diagnostic | 4-6 | Confirmations, acknowledgments, payments — distinct per fault domain |
| B: Branching Troubleshooter | 8-15 | Diagnostic tools, device toggles, resets, tests + 3+ diagnostic READ |
| C: Transaction Processor | 3-5 | Confirmations + precondition gates — distinct per transaction type |
| D: Triage / Classification | 3-4 | Acknowledgments + info-providing tools — distinct per classification |

For all archetypes:
- Design distinct tools for different fault groups to avoid action deduplication
- Prefer zero-arg or single-arg tools for reliability (user sim passes args more accurately)

### Fault Groups

- **5-10 fault groups.** The right number depends on the archetype and domain complexity.
- At least 3 groups should have 2+ faults each for variety within groups.
- Each additional fault group adds ~5 cross-file touchpoints (init helper, fix tool, assertion, user tool, policy section). Don't add groups just to hit a target number — each group must be semantically distinct.

**Rough targets by archetype:**

| Archetype | Fault Groups | Combos/Entity Target |
|-----------|-------------|---------------------|
| A: Sequential Diagnostic | 8-10 | 500-5000 |
| B: Branching Troubleshooter | 7-9 | 200-2000 |
| C: Transaction Processor | 7-9 | 200-1000 |
| D: Triage / Classification | 6-8 | 100-500 |

### Difficulty Calibration

The number of atoms (actions) per fault layer depends on the archetype:

- **Archetype A (Sequential Diagnostic):** 2 atoms per layer — agent-side fix action + user-side confirmation. With 4-5 groups active, tasks average 8-10 total actions.
- **Archetype B (Branching Troubleshooter):** 1-2 atoms per layer — often just a user-side fix (the user toggles/reboots/tests). Some layers may add an agent-side backend action. With 3-5 groups active, tasks average 5-10 actions.
- **Archetype C (Transaction Processor):** 1-2 atoms per layer — agent-side fix + optional user confirmation. With 3-4 groups active, tasks average 4-8 actions.
- **Archetype D (Triage / Classification):** 1 atom per layer — agent classifies or routes. With 2-4 groups active, tasks average 3-6 actions.

Single-atom layers are valid when the user action IS the resolution (Archetype B) or when the agent action is self-contained (Archetype D). Ensure the overall task difficulty comes from the RIGHT source for the archetype — gate depth (A), decision tree breadth (B), protocol complexity (C), or classification ambiguity (D).

### Information Architecture

The READ tool pattern depends on the archetype:

- **Archetype A:** Design a **state hierarchy** — which conditions gate visibility of other conditions? Example: `account_active → can_view_vehicles → registration_current → can_view_orders`. At least some READ tools should return degraded output when upstream faults are active. Include at least 1 "diagnostic" tool that returns computed results.
- **Archetype B:** READ tools are mostly transparent (agent sees full backend state). The USER has diagnostic READ tools for checking device/physical state. The policy describes which diagnostic to run when.
- **Archetype C:** READ tools are transparent — agent sees full state. Difficulty comes from protocol complexity and numeric computation, not from hidden state.
- **Archetype D:** Mix of transparent READ tools and classification-oriented tools (knowledge base search, category lookup). Some tools may return ambiguous results the agent must interpret.

### Semantic Distinctness
- Each fault group must be SEMANTICALLY DISTINCT — different DB fields, different fix tools, different reasoning.
- Do NOT create layers that are the same tool with a different amount (e.g. '$40 credit' and '$75 credit' both using issue_credit).
- Within a group, mutually exclusive layers should differ in resolution strategy.

### Unfixable Faults
- Some faults should be marked `unfixable: true` — issues no available tool can resolve.
- Do NOT mix unfixable faults into the same groups as fixable faults.
- List them in a SEPARATE section — they become a separate FaultLayerConfig with max_faults=1 and max_total_tasks=16.
- Target 2-3 unfixable faults.

### Difficulty Invariant Checklist

Before finalizing the domain spec, verify that the design satisfies all six difficulty invariants (see `docs/skills/00-archetype.md` for full descriptions). Fill in each checkbox:

- [ ] **DI-1 (Diagnostic Disambiguation):** At least 2 faults share a fix tool OR domain has information-hiding/diagnostic READ tools. Which faults share tools? Which READ tools hide info? ___
- [ ] **DI-2 (Value Computation):** At least 1 fault group requires the agent to compute/derive a value not directly in the ticket. Which group? What computation? ___
- [ ] **DI-3 (Ordering Dependency):** At least 1 ordering constraint exists (gate chain, fix ordering, or user action precondition). What is the dependency chain? ___
- [ ] **DI-4 (Multi-Property Assertions):** ≥40% of fixable layers will have 2+ assertions. Estimated percentage: ___
- [ ] **DI-5 (Active User Participation):** User tool count meets archetype minimum (A: 4+, B: 8+, C: 3+, D: 3+). Planned count: ___
- [ ] **DI-6 (Effective Action Density):** With planned group count and atoms/layer, median actions meets floor (A: ≥8, B: ≥6, C: ≥6, D: ≥5). Estimated median: ___

### Anti-Patterns That Always Produce Easy Domains

These patterns are **banned** — if the spec exhibits any of them, redesign before proceeding:

1. **1:1 Fault→Tool Mapping:** Every fault has its own unique fix tool. The agent just pattern-matches names. Fix: make 2+ faults share a tool with different computed args.
2. **Ticket Pass-Through Args:** Every fix tool argument is stated verbatim in the user's complaint. Zero computation. Fix: require the agent to look up, calculate, or derive at least one argument.
3. **No Information Hiding or Gating:** All READ tools return full state regardless of other faults. The agent sees everything immediately. Fix: add at least one state-dependent READ tool or diagnostic.
4. **Universal Confirm Tool:** A single user tool (e.g., `confirm_resolution`) is used for every fault. Zero user-side diversity. Fix: design distinct user tools per fault domain.
5. **All Faults Independent:** No ordering constraints, no gate chains, no preconditions. Agent fixes everything in one pass. Fix: add at least one dependency (gate, ordering, or precondition).
6. **Flat Assertions:** Every fault has exactly one assertion checking one field. Fix: add composite or multi-field assertions to ≥40% of layers.
7. **Trivial Action Count:** Fewer than 6 groups with 1 atom each = median 3 actions. Fix: increase groups or atoms/layer to meet the archetype floor.
