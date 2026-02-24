# Step 8: User Tools (user_tools.py)

Generate the user-side toolkit — tools available to the user (customer) for viewing their state and performing actions.

## Reference

- Read `docs/domain-authoring-guide.md` lines 404-461 (User Tools section)
- Read `src/tau2/domains/auto_repair/user_tools.py` for the structural pattern (class hierarchy, decorator usage, assertion helpers)
- Read `docs/skills/00-archetype.md` for your archetype-specific user tool patterns

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json` — including `archetype`
- Read `src/tau2/domains/<domain_name>/user_data_model.py`

## Output

Write to `src/tau2/domains/<domain_name>/user_tools.py`.

## Requirements

### Imports

```python
from typing import Any, Dict, List
from tau2.domains.<domain_name>.user_data_model import <DomainClass>UserDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool
```

### Class Structure

```python
class <DomainClass>UserTools(ToolKitBase):
    db: <DomainClass>UserDB

    def __init__(self, db: <DomainClass>UserDB):
        super().__init__(db)
```

### Tool Density by Archetype

The number and type of user tools depends on the domain archetype:

**Archetype A (Sequential Diagnostic) — 3-5 user WRITE tools:**
- Confirmations: `confirm_hold_pickup(hold_id)`, `approve_repairs(order_id)`
- Acknowledgments: `acknowledge_resolution(customer_id)`
- Payments: `make_payment(invoice_id)`
- These are agent-driven — the user calls them when the agent instructs

**Archetype B (Branching Troubleshooter) — 5-15 user WRITE tools:**
- Diagnostic tools: `check_network_status()`, `run_speed_test()`, `check_signal_strength()`
- Fix tools: `toggle_airplane_mode()`, `reboot_device()`, `reset_apn_settings()`
- Verification tools: `can_send_mms()`, `check_app_permissions()`
- The user is the instrument — they perform physical actions the agent cannot

**Archetype C (Transaction Processor) — 3-5 user WRITE tools:**
- Confirmations per transaction type: `confirm_refund()`, `confirm_transfer()`, `authorize_payment()`
- At least 1 precondition gate: user action must precede an agent action
- Distinct tools per fault domain — not a universal `confirm()` tool

**Archetype D (Triage / Classification) — 3-4 user WRITE tools:**
- Acknowledgments per classification: `acknowledge_routing()`, `confirm_escalation()`, `accept_resolution()`
- At least 1 info-providing tool where user supplies data the agent interprets

### Tool Categories

1. **READ tools** (`@is_tool(ToolType.READ)`):
   - At least 1 READ tool for the user to check their state
   - e.g. `view_my_checkouts()`, `view_my_appointments()`
   - For Archetype B: additional diagnostic READ tools

2. **WRITE tools** (`@is_tool(ToolType.WRITE)`):
   - Count depends on archetype (see above)
   - Design DISTINCT tools for different fault groups to avoid action deduplication
   - Prefer zero-arg or single-arg tools for reliability

   **How user WRITE tools get called (the agent->user chain):**
   The agent cannot see the user's tools. The only way user tools get called is:
   1. The **policy** tells the agent: "instruct the customer to use their approve_repairs tool"
   2. The **agent** says in conversation: "Please use your approve_repairs tool to authorize the work"
   3. The **user sim** follows the agent's instruction and calls the tool

   This means every user WRITE tool MUST have a corresponding instruction in the policy (step 6). If the policy doesn't mention a user tool, the agent will never ask the user to call it, and it will never be called.

   **For Archetype B (user-as-instrument):** The user has many tools and the policy explicitly references each one in the troubleshooting decision tree. The agent must know WHICH diagnostic to ask for and WHICH fix to instruct.

3. **Setup helper** (no decorator):
   - `set_user_info(name, user_id)` — sets identity fields
   - Called during scenario initialization
   - For Archetype B: additional setup helpers for device/physical state (`set_airplane_mode`, `set_signal_strength`, etc.)

4. **Assertion helpers** (no decorator, return `bool`):
   - `assert_resolution_acknowledged(customer_id) -> bool`
   - One per user action tracking field in the UserDB
   - For Archetype B: device state assertions (`assert_airplane_mode_off`, `assert_network_connected`)

### Docstrings

Every tool must have proper docstrings with Args and Returns.

### Difficulty Requirements (DI-5)

User tool design is a key difficulty lever. The following requirements prevent trivially-easy user participation:

1. **Distinct tools per fault domain:** Each fault group should use a different user tool (or at least a different subset). Do NOT design a single "universal confirm" tool that every fault shares. If >50% of fixable layers use the same user tool, the domain is too easy.

2. **At least 1 gating user tool:** For Archetypes A, B, and C, at least 1 user tool must gate an agent action (the agent cannot proceed until the user acts). This forces the agent to actively guide the user rather than ignoring them.

3. **User READ tools for diagnostic archetypes:** Archetypes A and B must have user READ tools that return state the agent needs to interpret. The agent must ask the user to run diagnostics and then decide what to do based on the results.

4. **Minimum distinct user WRITE tools by archetype:**
   - Archetype A: 4+
   - Archetype B: 8+ (user is the primary instrument)
   - Archetype C: 3+
   - Archetype D: 3+

5. **Banned: universal confirm pattern.** If a single user WRITE tool appears as the fix action in >50% of all fault layers, redesign with distinct tools.

## Validation

The validator will:
- Check Python syntax
- Import the module
- Check class exists and inherits `ToolKitBase`
- Instantiate with the UserDB
- Check at least 1 tool exists
- Check for `assert_*` methods (no decorator)
- Check for `set_*` methods (no decorator)
