# Step 7: Agent Tools (tools.py)

Generate the agent-side toolkit — the tools available to the AI agent for looking up data and resolving issues.

## Reference

- Read `docs/domain-authoring-guide.md` lines 257-403 (Agent Tools) and 1172-1257 (Gotchas)
- Read `src/tau2/domains/auto_repair/tools.py` for the class structure and method categories (READ/WRITE/GENERIC tools, setup helpers, assertion helpers)
- Read `docs/skills/00-archetype.md` for your archetype-specific tool patterns

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json` — including `archetype`
- Read `src/tau2/domains/<domain_name>/data_model.py`
- Read `data/tau2/domains/<domain_name>/policy.md` (for tool requirements)

## Output

Write to `src/tau2/domains/<domain_name>/tools.py`.

## Requirements

### Imports

```python
from typing import Any, Dict, List, Optional
from tau2.domains.<domain_name>.data_model import <DomainClass>DB, <Entity1>, <Entity2>, ...
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool
```

Replace `<domain_name>` and `<DomainClass>` with actual values.

### Class Structure

```python
class <DomainClass>Tools(ToolKitBase):
    db: <DomainClass>DB

    def __init__(self, db: <DomainClass>DB):
        super().__init__(db)
```

### Tool Categories

1. **Internal helpers** (prefixed with `_`, no decorator):
   - `_find_<entity>(self, id: str)` — lookup by ID
   - `_find_<entity>_by_name(self, name: str)` — lookup by name
   - `_normalize_str(s: str)` — normalize strings for comparison

2. **READ tools** (`@is_tool(ToolType.READ)`):
   - At least 3 READ tools
   - `get_<entity>_by_name(name)` — lookup by name
   - `get_<entity>_by_id(id)` — lookup by ID
   - ENTITY NAVIGATION: For every child entity type with a foreign key to the primary entity, include `get_<children>(parent_id)` — e.g. `get_vehicles(customer_id)`, `get_invoices(customer_id)`
   - Without navigation tools, the agent cannot discover entity IDs and will fail tasks

3. **WRITE tools** (`@is_tool(ToolType.WRITE)`):
   - At least 3 WRITE tools
   - Each corresponds to a fix action from the fault groups
   - Every tool must have proper docstring with Args and Returns

4. **GENERIC tools** (`@is_tool(ToolType.GENERIC)`):
   - `transfer_to_human(summary: str)` — transfers to human specialist

5. **Setup helpers** (no decorator, used by scenario init):
   - `set_<field>(self, entity_id, value)` — sets a DB field directly
   - One per mutable field that fault layers need to initialize

6. **Assertion helpers** (no decorator, used by verification):
   - `assert_<field>(self, entity_id, expected_value) -> bool`
   - CRITICAL: For each WRITE tool, ensure a matching assertion helper that checks the EXACT field that tool modifies
   - If `reassign_dentist` changes `appointment.dentist`, there must be `assert_appointment_dentist`
   - The verification system runs fix actions then checks assertions

### Precondition Pattern

When a WRITE tool depends on a user action (e.g. `process_payment` requires user to call `make_payment` first):
- The tool MUST check a bridged field that `sync_tools` sets when the user acts
- Without this precondition, the agent bypasses the user action entirely (ACTION:0.0)
- Pattern: user tool sets `user_db` field -> `sync_tools` bridges to `agent_db` -> agent WRITE tool checks the bridged field and raises `ValueError` if not set

### Overwrite Guards on WRITE Tools

**CRITICAL:** Any WRITE tool that modifies a field initialized by a fault layer MUST guard against overwriting already-correct values. If the field has a "default/broken" value (e.g. `"unassessed"`, `None`, `"pending"`) that the fault layer sets, the tool should check if the field is still at that default before modifying it:

```python
@is_tool(ToolType.WRITE)
def assess_concern(self, case_id: str, concern_type: str, severity: str) -> str:
    case = self._find_case(case_id)
    # Guard: don't overwrite an already-assessed concern
    if case.concern_type != "unassessed":
        return f"Case {case_id} already assessed as {case.concern_type}. No changes made."
    case.concern_type = concern_type
    ...
```

Without this guard, a prescriptive policy ("always assess the concern") will cause the agent to overwrite correct data on tasks where the fault is not active. This is especially important for **Archetype C** (transaction processor) domains with prescriptive policies.

### READ Tool Patterns by Archetype

The READ tool design depends on your domain's archetype:

**Archetype A (Sequential Diagnostic) — State-dependent / Information-hiding:**

READ tools whose output depends on other DB state. Upstream faults mask downstream details:

```python
@is_tool(ToolType.READ)
def get_vehicles(self, customer_id: str) -> Any:
    customer = self._find_customer(customer_id)
    if customer.account_status == "suspended":
        return f"Account {customer_id} is suspended. Reactivate before accessing vehicles."
    return [{"vehicle_id": v.vehicle_id, "make": v.make, "model": v.model,
            "registration_status": v.registration_status}
            for v in self.db.vehicles if v.customer_id == customer_id]
```

With this pattern, a task with `[suspended_account, expired_registration, worn_brake_pads]` forces the agent to fix the suspension first, re-query, then discover expired registration, fix it, then run diagnostics.

Also consider **diagnostic tools** that return computed results:

```python
@is_tool(ToolType.READ)
def run_diagnostic(self, order_id: str) -> Dict[str, Any]:
    order = self._find_order(order_id)
    vehicle = self._find_vehicle(order.vehicle_id)
    issues = []
    if vehicle.brake_pad_thickness < 3.0:
        issues.append(f"Worn brake pads ({vehicle.brake_pad_thickness:.1f}mm)")
    if vehicle.battery_voltage < 12.4:
        issues.append(f"Battery voltage low ({vehicle.battery_voltage:.1f}V)")
    return {"issues_detected": issues, "status": "issues_found" if issues else "all_clear"}
```

**Archetype B (Branching Troubleshooter) — Transparent backend:**

Agent-side READ tools return full entity state. The agent's challenge is interpreting user-reported diagnostics, not discovering hidden state:

```python
@is_tool(ToolType.READ)
def get_customer_account(self, customer_id: str) -> Dict[str, Any]:
    customer = self._find_customer(customer_id)
    return customer.model_dump()  # All fields — no gating
```

**Archetype C (Transaction Processor) — Transparent with guarded WRITE:**

READ tools return full state. WRITE tools have strict preconditions:

```python
@is_tool(ToolType.READ)
def get_account_details(self, account_id: str) -> Dict[str, Any]:
    return self._find_account(account_id).model_dump()

@is_tool(ToolType.WRITE)
def process_refund(self, transaction_id: str, amount: float) -> str:
    txn = self._find_transaction(transaction_id)
    if txn.status == "refunded":
        return f"Transaction {transaction_id} already refunded. No changes made."
    if amount > txn.amount:
        return f"Refund ${amount:.2f} exceeds transaction ${txn.amount:.2f}."
    txn.refund_amount = amount
    txn.status = "refunded"
    return f"Refund of ${amount:.2f} processed."
```

**Archetype D (Triage / Classification) — Mix of transparent and search:**

Some READ tools return full state, others return search/classification results the agent must interpret:

```python
@is_tool(ToolType.READ)
def search_knowledge_base(self, keywords: str) -> List[Dict[str, Any]]:
    results = [a for a in self.db.kb_articles
               if any(kw.lower() in a.content.lower() for kw in keywords.split())]
    return [{"article_id": a.article_id, "title": a.title, "category": a.category}
            for a in results]
```

### Difficulty-Enforcing Tool Patterns

These patterns are **required** to prevent trivially-easy tool designs. See DI-1 through DI-3 in `docs/skills/00-archetype.md`.

#### Diagnostic READ Tools (DI-1)

Every domain needs at least 1 READ tool that returns **computed results** rather than raw field values. This forces the agent to interpret diagnostic output, not just relay data.

```python
# GOOD: Diagnostic tool returns computed/derived information
@is_tool(ToolType.READ)
def run_account_health_check(self, account_id: str) -> Dict[str, Any]:
    """Run a diagnostic check on account health."""
    account = self._find_account(account_id)
    issues = []
    if account.balance < 0:
        issues.append(f"Negative balance: ${account.balance:.2f}")
    if account.last_payment_date < threshold_date:
        issues.append(f"Payment overdue by {days_overdue} days")
    return {"status": "issues_found" if issues else "healthy", "issues": issues}

# BAD: Just returns raw field values — zero interpretation needed
@is_tool(ToolType.READ)
def get_account(self, account_id: str) -> Dict[str, Any]:
    return self._find_account(account_id).model_dump()
```

For Archetype A: at least 1 information-hiding READ tool + 1 diagnostic tool. For all others: at least 1 diagnostic READ tool.

#### Shared Fix Tools (DI-1, DI-2)

At least 2 faults should use the **same WRITE tool** with different computed arguments. This prevents 1:1 fault→tool pattern matching.

```python
# One tool handles multiple fault types with different computed args:
@is_tool(ToolType.WRITE)
def adjust_billing(self, account_id: str, adjustment_type: str, amount: float) -> str:
    """Adjust billing for an account. Agent must determine type and amount."""
    # Used for: overcharge correction (compute difference), late fee removal
    # (look up fee amount), proration (calculate partial month)
```

#### Precondition-Gated WRITE Tools (DI-3)

At least 1 WRITE tool must check a prerequisite that forces ordering:

```python
@is_tool(ToolType.WRITE)
def process_claim(self, claim_id: str, amount: float) -> str:
    claim = self._find_claim(claim_id)
    if not claim.verified:  # Must call verify_claim first
        return "Cannot process unverified claim. Run verification first."
    # ... process
```

#### Anti-Pattern: Transparent Pass-Through Tools

**Banned:** Tools where ALL arguments come directly from the ticket/complaint with zero computation. If the user says "fix order #123" and the agent just calls `fix_order(order_id="123")`, that's a pass-through. At least 1 WRITE tool must require the agent to compute or derive an argument value.

### Docstrings

Every tool must have a proper docstring with:
```python
"""
Brief description.

Args:
    param1: Description.
    param2: Description.

Returns:
    Description of return value.
"""
```

## Validation

The validator will:
- Check Python syntax
- Import the module
- Check class exists and inherits `ToolKitBase`
- Instantiate with the DB
- Count tools by type (>= 1 READ, >= 1 WRITE, >= 1 GENERIC)
- Check for `assert_*` methods (no decorator)
- Check for `set_*` methods (no decorator)
- Check entity navigation tools exist
