# Domain Authoring Guide for tau2-bench

This guide covers everything you need to know to write a new domain from scratch. It's written from hard-won experience building auto_repair, library, fitness_gym, and other domains on the Recipe Engine pipeline.

**Domains come in different archetypes** — sequential diagnostic (auto_repair), branching troubleshooter (telecom), transaction processor (banking), triage/classification (helpdesk). See `docs/skills/00-archetype.md` for the full classification system. This guide presents patterns for ALL archetypes; auto_repair examples illustrate Archetype A, but other patterns are equally valid.

---

## Table of Contents

1. [Overview: What Is a Domain?](#1-overview-what-is-a-domain)
2. [File Checklist](#2-file-checklist)
3. [Step-by-Step Implementation](#3-step-by-step-implementation)
   - [3.1 Design the Domain Concept](#31-design-the-domain-concept)
   - [3.2 Create the Agent Database (db.json + data_model.py)](#32-create-the-agent-database)
   - [3.3 Create the User Database (user_db.json + user_data_model.py)](#33-create-the-user-database)
   - [3.4 Write the Policy (policy.md)](#34-write-the-policy)
   - [3.5 Implement Agent Tools (tools.py)](#35-implement-agent-tools)
   - [3.6 Implement User Tools (user_tools.py)](#36-implement-user-tools)
   - [3.7 Wire Up the Environment (environment.py)](#37-wire-up-the-environment)
   - [3.8 Define Path Constants (utils.py)](#38-define-path-constants)
   - [3.9 Register the Domain (registry.py)](#39-register-the-domain)
   - [3.10 Build Task Generation (scenarios.py)](#310-build-task-generation)
   - [3.11 Write Tests](#311-write-tests)
4. [The Recipe Engine: FaultLayer System](#4-the-recipe-engine-faultlayer-system)
5. [Evaluation Dimensions](#5-evaluation-dimensions)
6. [Verification System](#6-verification-system)
7. [Critical Gotchas](#7-critical-gotchas)
8. [Task Diversity Checklist](#8-task-diversity-checklist)
9. [Quality Checklist](#9-quality-checklist)
10. [Common Mistakes](#10-common-mistakes)

---

## 1. Overview: What Is a Domain?

A domain in tau2-bench is a simulated customer-service environment where an AI agent interacts with a user (also simulated by an LLM) to resolve problems. The benchmark evaluates whether the agent takes the correct actions, produces the right state changes, and communicates properly.

Each domain has:
- A **database** (agent-side state the agent queries/modifies)
- A **user database** (the user's observable view of the world)
- **Agent tools** (functions the agent can call: look things up, make changes)
- **User tools** (functions the simulated user can call to verify results)
- A **policy** (instructions for the agent on how to handle requests)
- A **sync mechanism** (how agent actions affect what the user sees)
- **Tasks** (scenarios with expected actions, assertions, and evaluation criteria)

---

## 2. File Checklist

Every domain requires these files:

```
src/tau2/domains/{domain_name}/
├── __init__.py              # Empty or minimal
├── data_model.py            # Agent-side DB schema (Pydantic models)
├── user_data_model.py       # User-side DB schema (Pydantic models)
├── tools.py                 # Agent tools (ToolKitBase subclass)
├── user_tools.py            # User tools (ToolKitBase subclass)
├── environment.py           # Environment subclass + get_environment() + get_tasks()
├── utils.py                 # Path constants
└── scenarios.py             # Task generation with Recipe Engine

data/tau2/domains/{domain_name}/
├── db.json                  # Initial agent DB state
├── user_db.json             # Initial user DB state
├── policy.md                # Agent policy document
└── tasks.json               # Generated tasks (output of scenarios.py)

tests/test_domains/test_{domain_name}/
├── __init__.py
└── test_{domain_name}.py    # Domain tests
```

And one modification to an existing file:
- `src/tau2/registry.py` — import and register the domain

---

## 3. Step-by-Step Implementation

### 3.1 Design the Domain Concept

Before writing code, answer these questions:

**What is the service?** (auto repair center, library helpdesk, bank customer service, clinic scheduling, etc.)

**What archetype fits?** See `docs/skills/00-archetype.md` to classify your domain. This determines the information architecture, policy style, tool patterns, and difficulty source. The archetype drives most downstream design decisions.

**What entities exist?** List the main objects and their relationships:
- Primary entities (customers, vehicles, service orders, invoices)
- Secondary entities (warranty plans, diagnostic records)
- Their relationships (a customer owns vehicles, a vehicle has service orders, an order generates an invoice)

**What can go wrong?** These become your fault layers:
- State faults (suspended account, expired registration, worn brake pads, low battery)
- Missing/incorrect data (wrong service date, wrong labor charges, missing discount)
- Policy violations (can't view vehicles with suspended account, can't view orders with expired registration)

**What can the agent do?** These become your agent tools:
- READ tools: look up customer, get vehicles, get service orders, run diagnostic, get invoices
- WRITE tools: modify state (reactivate account, replace brake pads, adjust labor charge)
- GENERIC tools: transfer_to_human

**What can the agent NOT do?** These become unfixable layers (transfer_to_human):
- Handle manufacturer safety recalls (requires factory-authorized repair)
- Fix structural/frame damage (requires specialized body shop)
- Any issue outside standard service capabilities

**What can the user do on their end?** These become user-side WRITE tools and `user_actions`:
- Confirmations: approve_repairs, confirm_warranty_renewal
- Acknowledgments: acknowledge_resolution
- Payments: make_payment
- **The agent instructs the user to perform these actions.** The agent cannot see the user's tools — it learns about them ONLY from the policy.

**What can the user observe?** This becomes your user_db and user tools:
- Account status, vehicle registration status
- Result of agent's actions (repairs completed, billing corrected)

**How does the agent guide the user?** This is the agent→user tool chain — a critical design element:
- The **policy** tells the agent: "After completing repairs, instruct the customer to use their approve_repairs tool"
- The **agent** says in conversation: "Please use your approve_repairs tool to authorize the work"
- The **user sim** follows the agent's instruction and calls the tool
- The agent CANNOT see the user's tool list. The policy is the ONLY bridge. Every user WRITE tool must have a corresponding instruction in the policy.

**How does the agent discover problems?** The information architecture depends on the domain's archetype (see `docs/skills/00-archetype.md`):

- **Archetype A (Sequential Diagnostic) — State-dependent / information-hiding:** READ tools' outputs depend on other state. `get_vehicles()` returns "Account suspended" when the account isn't active. The agent must fix upstream faults before downstream ones become visible, creating progressive discovery even though faults are sampled by flat cartesian product.

  Design guidance:
  - Identify a **state hierarchy**: which conditions gate visibility of other conditions?
  - Example: `account_active → can_view_vehicles → registration_current → can_view_orders → can_run_diagnostic`
  - Make each READ tool check upstream conditions and return degraded output when they're broken

- **Archetype B (Branching Troubleshooter) — Transparent backend, user-side diagnostics:** Agent-side READ tools return full entity state. The challenge is interpreting user-reported diagnostics and choosing the right troubleshooting path. The user has diagnostic tools (`check_network_status`, `run_speed_test`) and the agent must decide which to ask for.

- **Archetype C (Transaction Processor) — Transparent with guarded writes:** READ tools return full state. Difficulty comes from protocol complexity, numeric computation, and precondition checking — not from hidden state.

- **Archetype D (Triage / Classification) — Mix of transparent and search:** Some READ tools return full state, others return search/classification results the agent must interpret (knowledge base search, category lookup). Difficulty comes from classification ambiguity.

Each pattern is valid and tests different agent capabilities. The key requirement: **task success must depend on the agent doing the right thing.**

### 3.2 Create the Agent Database

**`data/tau2/domains/{domain}/db.json`**

Design principles:
- **Small but rich**: 10-15 primary entities (customers), with related entities per customer (vehicles, service orders, invoices)
- **Pre-seeded variety**: Include entities in different states (some active accounts, some with warranties; different vehicle types)
- **Relationships matter more than volume**: A customer with a vehicle, service order, and invoice creates rich task variety
- **Ensure every fault layer has at least 2-3 applicable entities**: If you have a "warranty" fault, you need at least 2-3 customers with warranty plans
- **Avoid special characters in names**: No apostrophes, accents, or non-ASCII characters (e.g. use "Kevin Brooks" not "Kevin O'Brien", "Napoli Pizzeria" not "Napoli's Pizzeria"). LLMs reliably send curly/smart quotes instead of straight apostrophes, causing exact-match lookups to fail.

Example structure (from auto_repair):
```json
{
  "customers": [
    {"customer_id": "C001", "name": "Marcus Chen", "phone": "555-0101",
     "email": "marcus.chen@email.com", "account_status": "active"},
    {"customer_id": "C002", "name": "Sarah Okafor", "phone": "555-0102",
     "email": "sarah.okafor@email.com", "account_status": "active"}
  ],
  "vehicles": [
    {"vehicle_id": "V001", "customer_id": "C001", "make": "Toyota", "model": "Camry",
     "year": 2021, "mileage": 45000, "registration_status": "current",
     "brake_pad_thickness": 8.0, "oil_life_pct": 65, "battery_voltage": 12.6}
  ],
  "service_orders": [
    {"order_id": "SO001", "vehicle_id": "V001", "service_type": "brake_inspection",
     "scheduled_date": "2025-03-15", "technician": "Mike R.", "status": "open"}
  ],
  "invoices": [
    {"invoice_id": "INV001", "order_id": "SO001", "customer_id": "C001",
     "labor_hours": 2.0, "labor_rate": 95.0, "parts_cost": 150.0,
     "discount_pct": 10.0, "total": 321.0, "status": "pending"}
  ]
}
```

**`src/tau2/domains/{domain}/data_model.py`**

```python
from typing import List, Optional
from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra

class Customer(BaseModelNoExtra):
    customer_id: str
    name: str
    phone: str
    email: str
    account_status: str  # "active", "suspended", "flagged"

class Vehicle(BaseModelNoExtra):
    vehicle_id: str
    customer_id: str
    make: str
    model: str
    year: int
    mileage: int
    registration_status: str  # "current", "expired"
    # Diagnostic fields (modified by fault layers)
    brake_pad_thickness: float = 8.0
    oil_life_pct: int = 65
    battery_voltage: float = 12.6

class AutoRepairDB(DB):
    customers: List[Customer]
    vehicles: List[Vehicle]
    service_orders: List[ServiceOrder]
    invoices: List[Invoice]
```

Rules:
- All models inherit from `BaseModelNoExtra` (Pydantic with `extra="forbid"`)
- The top-level DB class inherits from `DB` (which gives you `load()`, `dump()`, `get_hash()`)
- All fields must be JSON-serializable
- Use `Optional` for nullable fields with `= None` default

### 3.3 Create the User Database

**`data/tau2/domains/{domain}/user_db.json`**

The user DB represents what the user can observe. It starts mostly empty and gets populated during task setup.

```json
{
  "customer_name": null,
  "customer_id": null,
  "repair_approved": false,
  "payment_made": false,
  "warranty_renewal_confirmed": false,
  "resolution_acknowledged": false
}
```

**`src/tau2/domains/{domain}/user_data_model.py`**

```python
from typing import Optional
from tau2.environment.db import DB

class AutoRepairUserDB(DB):
    customer_name: Optional[str] = None
    customer_id: Optional[str] = None
    repair_approved: bool = False
    payment_made: bool = False
    warranty_renewal_confirmed: bool = False
    resolution_acknowledged: bool = False
```

Design principle: The user DB is a **projection** of the agent DB plus **user action tracking fields**. It contains only what the user can see or verify, plus boolean flags that record whether the user has performed required actions (approve_repairs, make_payment, etc.). The `sync_tools()` method (Step 3.7) keeps it in sync.

### 3.4 Write the Policy

**`data/tau2/domains/{domain}/policy.md`**

The policy is the agent's instruction manual. It's injected as the system prompt. The policy serves two critical functions:

1. **Guides the agent's diagnostic workflow** — what to check, in what order, how to fix issues
2. **Bridges the agent to user tools** — the agent CANNOT see the user's tool list, so the policy is the ONLY way the agent learns what user tools exist and when to instruct the user to call them

Structure the policy with these sections (example from auto_repair):

```markdown
# Precision Auto Service Center - Support Policy

## Identity Verification
Before making any account changes or accessing vehicle records, verify the
customer's identity by looking up their name and confirming their customer ID.

## Diagnostic Workflow
Follow this diagnostic process for every customer interaction:
1. Look up the customer's account first. If the account is suspended or flagged,
   resolve the account issue BEFORE proceeding — you cannot access vehicle records
   while the account is in a restricted state.
2. Once the account is accessible, look up the customer's vehicles. If a vehicle
   has expired registration, update it before viewing service details.
3. With vehicle records accessible, run a diagnostic on the service order to
   identify mechanical or electrical issues.
4. After identifying issues, resolve them one at a time. After completing repairs,
   instruct the customer to use their approve_repairs tool to authorize the work.
5. Review invoices for billing accuracy. If labor charges are incorrect, use
   adjust_labor_charge. If a discount is missing, use apply_discount.
6. After resolving billing issues, instruct the customer to use their make_payment
   tool to complete payment.

## Account Issues
When a customer's account is suspended, use reactivate_account to restore access.
After resolving any account issue, instruct the customer to use their
acknowledge_resolution tool to confirm.

## Warranty Issues
When a warranty has expired and the customer wants to renew, use renew_warranty.
After renewing, instruct the customer to use their confirm_warranty_renewal tool.

## Transfer to Human
Transfer to a human specialist using transfer_to_human when:
- The vehicle has an active manufacturer safety recall
- The vehicle has structural or frame damage
- Any issue falls outside standard service center capabilities
```

Tips:
- **Be specific about when to escalate.** If the policy says "transfer if you can't resolve," but the agent has tools for everything, it will never transfer. You need unresolvable scenarios.
- **Match policy style to archetype.** Archetype A: diagnostic workflow (fix upstream before downstream). Archetype B: decision tree (if symptom X, try fix Y). Archetype C: prescriptive protocol (for every request, follow steps 1-N). Archetype D: classification criteria (gather info, categorize, route). See `docs/skills/06-policy.md` for detailed patterns.
- **Name every user tool explicitly.** The policy MUST mention every user WRITE tool by its exact name — the agent has no other way to discover them. Write "instruct the customer to use their approve_repairs tool" not "confirm the repair with the customer."
- **Place user tool instructions after the corresponding agent action.** "After completing repairs, instruct the customer to use their approve_repairs tool" — this creates the correct agent→user flow.
- **List what the agent can and cannot do.** This implicitly defines escalation triggers.
- **If using prescriptive policy, guard WRITE tools.** If the policy says "always do X" but the fault that breaks X is only sometimes active, the agent overwrites correct data. Add overwrite guards to WRITE tools (see Section 3.5).

### 3.5 Implement Agent Tools

**`src/tau2/domains/{domain}/tools.py`**

```python
from typing import Any, Dict, List, Optional
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool
from tau2.domains.{domain}.data_model import {Domain}DB

class {Domain}Tools(ToolKitBase):
    db: {Domain}DB

    def __init__(self, db: {Domain}DB):
        super().__init__(db)

    # =============================================
    # PUBLIC TOOLS — visible to the agent LLM
    # =============================================

    @is_tool(ToolType.READ)
    def get_customer_by_name(self, name: str) -> Dict[str, Any]:
        """Look up a customer by name.
        Args:
            name: Customer's full name.
        Returns:
            Customer details including ID, contact info, and account status.
        """
        customer = self._find_customer_by_name(name)
        if customer is None:
            raise ValueError(f"No customer found with name '{name}'.")
        return {"customer_id": customer.customer_id, "name": customer.name,
                "account_status": customer.account_status}

    @is_tool(ToolType.READ)
    def get_vehicles(self, customer_id: str) -> Any:
        """Get all vehicles registered to a customer.
        Returns an error message if the account is not active.
        """
        customer = self._find_customer(customer_id)
        # INFORMATION HIDING: account status gates vehicle access
        if customer.account_status == "suspended":
            return f"Account {customer_id} is suspended. Reactivate before accessing vehicles."
        if customer.account_status == "flagged":
            return f"Account {customer_id} is flagged. Clear flag before accessing vehicles."
        return [{"vehicle_id": v.vehicle_id, "make": v.make, "model": v.model,
                 "registration_status": v.registration_status}
                for v in self.db.vehicles if v.customer_id == customer_id]

    @is_tool(ToolType.READ)
    def run_diagnostic(self, order_id: str) -> Dict[str, Any]:
        """Run a diagnostic scan on the vehicle. Checks brakes, engine, tires, electrical."""
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        issues = []
        if vehicle.brake_pad_thickness < 3.0:
            issues.append(f"Worn brake pads ({vehicle.brake_pad_thickness:.1f}mm)")
        if vehicle.battery_voltage < 12.4:
            issues.append(f"Battery voltage low ({vehicle.battery_voltage:.1f}V)")
        # ... check all diagnostic fields
        return {"issues_detected": issues, "status": "issues_found" if issues else "all_clear"}

    @is_tool(ToolType.WRITE)
    def replace_brake_pads(self, order_id: str) -> str:
        """Replace worn brake pads on the vehicle in a service order."""
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.brake_pad_thickness = 12.0
        return f"Brake pads replaced on vehicle {vehicle.vehicle_id}."

    @is_tool(ToolType.GENERIC)
    def transfer_to_human(self, summary: str) -> str:
        """Transfer the call to a human specialist."""
        return f"Call transferred to human specialist. Summary: {summary}"

    # =============================================
    # ASSERTION HELPERS — called by verify, not decorated
    # =============================================

    def assert_account_status(self, customer_id: str, expected: str) -> bool:
        customer = self._find_customer(customer_id)
        return customer.account_status == expected

    def assert_brake_pad_thickness(self, vehicle_id: str, min_thickness: float) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.brake_pad_thickness >= min_thickness

    # =============================================
    # SETUP HELPERS — called by scenarios for init, not decorated
    # =============================================

    def set_account_status(self, customer_id: str, status: str) -> None:
        self._find_customer(customer_id).account_status = status

    def set_brake_pad_thickness(self, vehicle_id: str, thickness: float) -> None:
        self._find_vehicle(vehicle_id).brake_pad_thickness = thickness
```

**Three categories of methods:**

| Category | Decorator | Called by | Purpose |
|----------|-----------|-----------|---------|
| **Public tools** | `@is_tool(ToolType.READ/WRITE/GENERIC)` | Agent LLM during conversation | The agent's interface to the system |
| **Assertion helpers** | None | `verify.py` and env_assertions | Post-condition checks (return bool) |
| **Setup helpers** | None | `scenarios.py` init_calls | Inject faults before task begins |

Critical rules:
- **Docstrings are mandatory** on public tools — they become the tool description the LLM sees
- **Type hints on arguments** — they become the tool parameter schema
- **Return JSON-serializable types** — str, int, float, bool, list, dict
- **Raise ValueError for bad input** — the framework catches and returns error to agent
- Assertion helpers must return `bool`
- Setup helpers should be direct state mutations (no validation needed)

**Entity navigation tools are required.** For every child entity type that has a foreign key to the primary entity (e.g. `Vehicle.customer_id`, `Invoice.customer_id`), include a READ tool that lets the agent look up children by parent ID:

```python
@is_tool(ToolType.READ)
def get_vehicles(self, customer_id: str) -> Any:
    """Get all vehicles registered to a customer."""
    self._find_customer(customer_id)  # Validate customer exists
    return [v for v in self.db.vehicles if v.customer_id == customer_id]

@is_tool(ToolType.READ)
def get_invoices(self, customer_id: str) -> Any:
    """Get all invoices for a customer."""
    self._find_customer(customer_id)
    return [i for i in self.db.invoices if i.customer_id == customer_id]
```

Without these navigation tools, the agent knows the customer's name/ID from the conversation but has no way to discover related entity IDs (vehicle IDs, order IDs, invoice IDs). It will guess IDs, get errors, and fail every fixable task. The pipeline validates this automatically — if 2+ child collections share a foreign key but no READ tool accepts that key as a parameter, the validation gate raises an error.

**READ tool patterns depend on archetype.** Choose the pattern that matches your domain (see `docs/skills/07-tools.md` for full examples):

**Archetype A (Sequential Diagnostic) — State-dependent / information-hiding:**

```python
# Upstream fault masks downstream details:
@is_tool(ToolType.READ)
def get_vehicles(self, customer_id: str) -> Any:
    """Get all vehicles registered to a customer."""
    customer = self._find_customer(customer_id)
    if customer.account_status == "suspended":
        return f"Account {customer_id} is suspended. Reactivate before accessing vehicles."
    return [{"vehicle_id": v.vehicle_id, "make": v.make, "model": v.model,
             "registration_status": v.registration_status}
            for v in self.db.vehicles if v.customer_id == customer_id]
```

**Archetype B (Branching Troubleshooter) — Transparent backend:**

```python
# Agent sees full state — challenge is interpreting user diagnostics:
@is_tool(ToolType.READ)
def get_customer_account(self, customer_id: str) -> Dict[str, Any]:
    """Get all account details for a customer."""
    customer = self._find_customer(customer_id)
    return customer.model_dump()  # No gating — full state
```

**Archetype C (Transaction Processor) — Transparent with guarded writes:**

```python
@is_tool(ToolType.WRITE)
def process_refund(self, transaction_id: str, amount: float) -> str:
    """Process a refund for a transaction."""
    txn = self._find_transaction(transaction_id)
    if txn.status == "refunded":
        return f"Transaction {transaction_id} already refunded. No changes made."
    if amount > txn.amount:
        return f"Refund ${amount:.2f} exceeds transaction ${txn.amount:.2f}."
    txn.refund_amount = amount
    txn.status = "refunded"
    return f"Refund of ${amount:.2f} processed."
```

Each pattern is valid. The key: task difficulty should come from the RIGHT source for the archetype — gate depth (A), decision tree breadth (B), protocol complexity (C), or classification ambiguity (D).

**Diagnostic tools** are READ tools that probe the system's current state rather than returning stored fields. They're especially useful for Archetype A but can be used in any domain:

```python
@is_tool(ToolType.READ)
def run_diagnostic(self, order_id: str) -> Dict[str, Any]:
    """Run a diagnostic scan on the vehicle. Checks brakes, engine, tires, electrical."""
    order = self._find_order(order_id)
    vehicle = self._find_vehicle(order.vehicle_id)
    issues = []
    if vehicle.brake_pad_thickness < 3.0:
        issues.append(f"Worn brake pads ({vehicle.brake_pad_thickness:.1f}mm, min: 3.0mm)")
    if vehicle.brake_fluid_level == "low":
        issues.append("Brake fluid level is low - flush needed")
    if vehicle.oil_life_pct < 20:
        issues.append(f"Oil change overdue (oil life: {vehicle.oil_life_pct}%)")
    if vehicle.battery_voltage < 12.4:
        issues.append(f"Battery voltage low ({vehicle.battery_voltage:.1f}V, min: 12.4V)")
    if vehicle.alternator_output == "faulty":
        issues.append("Alternator output abnormal - replacement recommended")
    return {"issues_detected": issues, "issue_count": len(issues),
            "status": "issues_found" if issues else "all_clear"}
```

The key insight: **diagnostic tools return computed results, not stored fields.** The computation naturally hides deeper issues behind shallower ones, creating the layered discovery pattern without any special task generation logic. The `run_diagnostic` tool checks ALL vehicle subsystems in one call — the agent must interpret the results, decide which repairs to perform, and fix them one by one.

### 3.6 Implement User Tools

**`src/tau2/domains/{domain}/user_tools.py`**

```python
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool
from tau2.domains.{domain}.user_data_model import {Domain}UserDB

class {Domain}UserTools(ToolKitBase):
    db: {Domain}UserDB

    def __init__(self, db: {Domain}UserDB):
        super().__init__(db)

    # =============================================
    # PUBLIC USER TOOLS — visible to user LLM
    # =============================================

    @is_tool(ToolType.WRITE)
    def approve_repairs(self, order_id: str) -> str:
        """Approve repair work performed on your vehicle."""
        self.db.repair_approved = True
        return "Repairs approved."

    @is_tool(ToolType.WRITE)
    def make_payment(self, invoice_id: str) -> str:
        """Make payment on an invoice."""
        self.db.payment_made = True
        return "Payment submitted."

    @is_tool(ToolType.WRITE)
    def acknowledge_resolution(self, customer_id: str) -> str:
        """Acknowledge that an account or registration issue has been resolved."""
        self.db.resolution_acknowledged = True
        return "Resolution acknowledged."

    @is_tool(ToolType.WRITE)
    def confirm_warranty_renewal(self, warranty_id: str) -> str:
        """Confirm your warranty renewal."""
        self.db.warranty_renewal_confirmed = True
        return "Warranty renewal confirmed."

    # =============================================
    # USER ASSERTIONS — called by evaluation, not decorated
    # =============================================

    def assert_repair_approved(self, order_id: str) -> bool:
        return self.db.repair_approved

    def assert_payment_made(self, invoice_id: str) -> bool:
        return self.db.payment_made

    def assert_resolution_acknowledged(self, customer_id: str) -> bool:
        return self.db.resolution_acknowledged

    # =============================================
    # SETUP HELPERS — called by scenarios, not decorated
    # =============================================

    def set_customer_info(self, name: str, customer_id: str) -> None:
        """Set the user's identity for this scenario."""
        self.db.customer_name = name
        self.db.customer_id = customer_id
```

User tools serve three purposes:
1. **User-side WRITE tools** — actions the agent instructs the user to perform (approve repairs, make payment, acknowledge resolution)
2. **User-side assertions** — check that the user performed the required actions
3. **Setup helpers** — called during init to set user identity

**The agent→user tool chain:**
The agent CANNOT see the user's tool list — it only sees its own tools and the policy. The ONLY way user tools get called is through this chain:
1. The **policy** tells the agent: "instruct the customer to use their approve_repairs tool"
2. The **agent** says in conversation: "Please use your approve_repairs tool to authorize the work"
3. The **user sim** follows the agent's instruction and calls the tool

This means every user WRITE tool MUST have a corresponding instruction in the policy. If the policy doesn't mention a user tool, the agent will never ask the user to call it, and the task will fail the user action evaluation.

### 3.7 Wire Up the Environment

**`src/tau2/domains/{domain}/environment.py`**

```python
from typing import Optional
from tau2.data_model.tasks import Task
from tau2.environment.environment import Environment
from tau2.utils.utils import load_file
from tau2.domains.{domain}.data_model import {Domain}DB
from tau2.domains.{domain}.user_data_model import {Domain}UserDB
from tau2.domains.{domain}.tools import {Domain}Tools
from tau2.domains.{domain}.user_tools import {Domain}UserTools
from tau2.domains.{domain}.utils import (
    {DOMAIN}_DB_PATH, {DOMAIN}_USER_DB_PATH,
    {DOMAIN}_POLICY_PATH, {DOMAIN}_TASK_SET_PATH,
)


class {Domain}Environment(Environment):
    tools: {Domain}Tools
    user_tools: {Domain}UserTools

    def __init__(self, domain_name, policy, tools, user_tools):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """Synchronize user-side view with agent-side DB state.

        This is called after EVERY tool call (both during init and
        during the actual conversation). Design this to be idempotent.
        """
        customer_id = self.user_tools.db.customer_id
        if customer_id is None:
            return

        # Find customer in agent DB
        customer = next(
            (c for c in self.tools.db.customers if c.customer_id == customer_id),
            None,
        )
        if customer is None:
            return

        # Project agent state → user-visible state
        # (User action tracking fields like repair_approved are NOT
        # overwritten here — they're set by user tools only)


def get_environment(
    db=None, user_db=None, solo_mode=False
) -> AutoRepairEnvironment:
    """Factory function — called by registry and by task generation."""
    if db is None:
        db = AutoRepairDB.load(AUTO_REPAIR_DB_PATH)
    tools = AutoRepairTools(db)

    if user_db is None:
        user_db = AutoRepairUserDB.load(AUTO_REPAIR_USER_DB_PATH)
    user_tools = AutoRepairUserTools(user_db)

    policy = load_file(AUTO_REPAIR_POLICY_PATH)

    env = AutoRepairEnvironment(
        domain_name="auto_repair",
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    """Load tasks from tasks.json — called by registry."""
    if not AUTO_REPAIR_TASK_SET_PATH.exists():
        return []
    tasks = load_file(AUTO_REPAIR_TASK_SET_PATH)
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    return [Task.model_validate(task) for task in tasks]
```

**sync_tools() is the most important method.** It defines how agent actions affect the user's world. Get this wrong and your tasks will fail verification.

### 3.8 Define Path Constants

**`src/tau2/domains/{domain}/utils.py`**

```python
from tau2.utils.utils import DATA_DIR

{DOMAIN}_DATA_DIR = DATA_DIR / "tau2" / "domains" / "{domain}"
{DOMAIN}_DB_PATH = {DOMAIN}_DATA_DIR / "db.json"
{DOMAIN}_USER_DB_PATH = {DOMAIN}_DATA_DIR / "user_db.json"
{DOMAIN}_POLICY_PATH = {DOMAIN}_DATA_DIR / "policy.md"
{DOMAIN}_TASK_SET_PATH = {DOMAIN}_DATA_DIR / "tasks.json"
```

### 3.9 Register the Domain

Add to `src/tau2/registry.py`:

```python
# At the top, with other imports:
from tau2.domains.{domain}.environment import (
    get_environment as {domain}_domain_get_environment,
)
from tau2.domains.{domain}.environment import get_tasks as {domain}_domain_get_tasks

# Inside the try block, with other registrations:
registry.register_domain({domain}_domain_get_environment, "{domain}")
registry.register_tasks({domain}_domain_get_tasks, "{domain}")
```

### 3.10 Build Task Generation

**`src/tau2/domains/{domain}/scenarios.py`**

This is the most complex file. See [Section 4](#4-the-recipe-engine-faultlayer-system) for the full guide.

### 3.11 Write Tests

**`tests/test_domains/test_{domain}/test_{domain}.py`**

Required test categories:

```python
class TestEnvironment(unittest.TestCase):
    """Environment loads and tools are present."""

    def test_environment_loads(self):
        env = get_environment()
        self.assertIsNotNone(env)
        self.assertEqual(env.domain_name, "auto_repair")

    def test_agent_tools_exist(self):
        env = get_environment()
        tools = env.tools.get_tools()
        for name in ["get_customer_by_name", "get_vehicles", "run_diagnostic",
                      "replace_brake_pads", "transfer_to_human", ...]:
            self.assertIn(name, tools)

    def test_user_tools_exist(self):
        env = get_environment()
        tools = env.user_tools.get_tools()
        for name in ["approve_repairs", "make_payment", "acknowledge_resolution", ...]:
            self.assertIn(name, tools)

    def test_sync_tools_propagates(self):
        """Agent action → sync → user sees change."""
        env = get_environment()
        env.user_tools.set_customer_info("Marcus Chen", "C001")
        env.sync_tools()
        # Do agent action
        env.tools.reactivate_account("C001")
        env.sync_tools()
        # Verify agent DB state changed
        self.assertEqual(env.tools.assert_account_status("C001", "active"), True)


class TestIndexes(unittest.TestCase):
    """Index builder produces correct counts."""

    def test_build_indexes(self):
        db = get_db()
        idx = build_indexes(db)
        self.assertEqual(len(idx.available_books), 3)
        self.assertEqual(len(idx.checked_out_books), 5)


class TestTaskGeneration(unittest.TestCase):
    """Task generation produces valid tasks."""

    def test_creates_tasks(self):
        tasks = create_tasks(verify=False)
        self.assertGreater(len(tasks), 0)

    def test_task_count(self):
        """Expected: N specs × N_personas tasks."""
        tasks = create_tasks(verify=False)
        self.assertEqual(len(tasks), EXPECTED_COUNT)

    def test_tasks_have_valid_structure(self):
        tasks = create_tasks(verify=False)
        for task in tasks:
            self.assertIn("[auto_repair]", task.id)
            self.assertTrue(
                task.evaluation_criteria.actions
                or task.evaluation_criteria.env_assertions
            )

    def test_action_counts(self):
        """Tasks should have 1-N actions depending on fault count."""
        tasks = create_tasks(verify=False)
        for task in tasks:
            n = len(task.evaluation_criteria.actions)
            self.assertGreaterEqual(n, 1)
            self.assertLessEqual(n, MAX_EXPECTED_ACTIONS)

    def test_tasks_verify_clean(self):
        """Tasks pass verification (most important test)."""
        tasks = create_tasks(verify=False)
        report = verify_tasks(tasks, get_environment)
        errors = {
            tid: [i for i in issues if i.startswith("ERROR:")]
            for tid, issues in report.items()
        }
        errors = {tid: errs for tid, errs in errors.items() if errs}
        self.assertEqual(errors, {})

    def test_deterministic(self):
        """Same seed → same tasks."""
        t1 = create_tasks(verify=False)
        t2 = create_tasks(verify=False)
        self.assertEqual([t.id for t in t1], [t.id for t in t2])

    def test_cartesian_correctness(self):
        """Verify combo counts per entity match expected."""
        # Calculate expected count per entity based on
        # number of applicable groups
        pass

    def test_transfer_to_human_tasks(self):
        """Some tasks require transfer_to_human (from unfixable layers)."""
        tasks = create_tasks(verify=False)
        transfer = [t for t in tasks
                     if any(a.name == "transfer_to_human"
                            for a in t.evaluation_criteria.actions)]
        self.assertGreater(len(transfer), 0)

    def test_persona_coverage(self):
        """Each spec produces one task per persona."""
        tasks = create_tasks(verify=False)
        persona_names = {t.id.split("[PERSONA:")[1].rstrip("]") for t in tasks}
        self.assertGreater(len(persona_names), 1)


class TestRegistry(unittest.TestCase):
    def test_registered(self):
        from tau2.registry import registry
        self.assertIn("auto_repair", registry.get_domains())
```

---

## 4. The Recipe Engine: FaultLayer System

The Recipe Engine generates tasks by combining **fault layers** across **entities**. This is the recommended approach for new domains.

### Core Concepts

**Entity**: A database record (or combination of records) that becomes the subject of a task. One customer with their vehicle, service order, and invoice = one entity.

**FaultLayer**: One thing that can go wrong. It defines:
- How to inject the fault (init_calls)
- How the agent should fix it (actions)
- How to verify it was fixed (assertions)
- What the user knows about it (known_info_fragment)

**FaultLayerGroup**: Mutually exclusive fault layers. You pick 0 or 1 from each group. Use this when two faults would conflict (e.g., "account locked" and "account suspended" can't both be true).

**FaultLayerConfig**: The full specification. Defines which entities to use, which groups to combine, and how to format the task.

### Cartesian Product

The engine generates the **cartesian product** across all groups for each entity:

```
Entity: Marcus Chen (1 vehicle, 1 order, 1 invoice, 1 warranty)

FIXABLE CONFIG (bulk of tasks):
Groups: [account, registration, scheduling, brakes, engine, tires, electrical, warranty, billing]
Per group: pick 0 or 1 layer (all fixable)
  account:      [None, suspended, flagged]    → 3 options
  registration: [None, expired]               → 2 options
  scheduling:   [None, wrong_date, wrong_type]→ 3 options
  brakes:       [None, worn_pads, low_fluid]  → 3 options
  engine:       [None, oil_overdue, clogged]  → 3 options
  tires:        [None, low_pressure, misalign]→ 3 options
  electrical:   [None, weak_batt, bad_alt]    → 3 options
  warranty:     [None, expired_warranty]       → 2 options
  billing:      [None, overcharge, no_disc]   → 3 options

Total combos: 3×2×3×3×3×3×3×2×3 - 1 = 8747 fixable specs per entity
Sampled to max_total_tasks=1200

TRANSFER CONFIG (small set):
Groups: [unfixable_issue]
  unfixable_issue: [safety_recall, structural_damage] → 2 options
  max_faults=1, max_total_tasks=16

Result: ~98% fixable, ~2% transfer
```

### Building a FaultLayerConfig

```python
from tau2.generators.recipe import (
    ActionSpec, AssertionSpec, FaultAtom, FaultLayer, FaultLayerConfig,
    FaultLayerGroup, InitCall, RecipeBook, generate_recipe_tasks,
)

# Step 1: Define entity query
# Returns list of dicts, each dict is one entity with all template fields
def _build_entities(db: AutoRepairDB) -> list[dict]:
    entities = []
    for customer in db.customers:
        vehicle = ...  # join customer → vehicle → order → invoice
        entity = {
            "customer_id": customer.customer_id,
            "customer_name": customer.name,
            "vehicle_id": vehicle.vehicle_id,
            "vehicle_make": vehicle.make,
            "vehicle_model": vehicle.model,
            "order_id": order.order_id,
            "invoice_id": invoice.invoice_id,
            "original_labor_hours": invoice.labor_hours,
            "has_warranty": warranty is not None,
            # Include ALL fields any fault layer might need
        }
        entities.append(entity)
    return entities


# Step 2: Define base init (set user identity)
_BASE_INIT: list[InitCall] = [
    InitCall("user", "set_customer_info", {
        "name": "{customer_name}", "customer_id": "{customer_id}",
    }),
]


# Step 3: Define fault layers using the ATOMS interface
# Each FaultAtom = (init, fix, check). Atoms compose into FaultLayers.
_suspended_account = FaultLayer(
    name="suspended_account",
    known_info_fragment="My account appears to be suspended.",
    atoms=[
        # Atom 1: Agent-side fix
        FaultAtom(
            init=InitCall("assistant", "set_account_status",
                {"customer_id": "{customer_id}", "status": "suspended"}),
            fix=ActionSpec(tool_name="reactivate_account",
                args={"customer_id": "{customer_id}"}, compare_args=["customer_id"]),
            check=AssertionSpec(func_name="assert_account_status",
                args={"customer_id": "{customer_id}", "expected": "active"},
                env_type="assistant"),
        ),
        # Atom 2: User-side confirmation
        FaultAtom(
            fix=ActionSpec(tool_name="acknowledge_resolution",
                args={"customer_id": "{customer_id}"},
                requestor="user", compare_args=[]),
            check=AssertionSpec(func_name="assert_resolution_acknowledged",
                args={"customer_id": "{customer_id}"}, env_type="user"),
        ),
    ],
    resource_scope="account:{customer_id}",
)

_safety_recall = FaultLayer(
    name="safety_recall",
    unfixable=True,
    known_info_fragment="I received a safety recall notice on my {vehicle_make} {vehicle_model}.",
    atoms=[],
    resource_scope="recall:{vehicle_id}",
)


# Step 4: Group fault layers into TWO configs
_fixable_config = FaultLayerConfig(
    name="auto_repair",
    entity_query=lambda db: _build_entities(db),
    groups=[
        FaultLayerGroup(name="account_issues", layers=[_suspended_account, _flagged_account]),
        FaultLayerGroup(name="registration_issues", layers=[_expired_registration]),
        FaultLayerGroup(name="brake_issues", layers=[_worn_brake_pads, _low_brake_fluid]),
        FaultLayerGroup(name="engine_issues", layers=[_overdue_oil_change, _clogged_air_filter]),
        # ... 9 groups total
    ],
    base_init_calls=_BASE_INIT,
    base_known_info_template=(
        "You are {customer_name}. Your vehicle is a {vehicle_year} {vehicle_make} "
        "{vehicle_model}. {fault_descriptions}"
    ),
    base_ticket_template="Customer {customer_name} (ID: {customer_id}): {fault_descriptions}.",
    reason_for_call="You are contacting Precision Auto Service Center.",
    purpose="Test resolution of auto repair support issues.",
    entity_id_field="customer_id",
    min_faults=1,
    max_faults=9,
    max_total_tasks=1200,
)

# TRANSFER config — unfixable layers only (small set)
_transfer_config = FaultLayerConfig(
    name="auto_repair_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[
        FaultLayerGroup(name="unfixable_issues", layers=[_safety_recall, _structural_damage]),
    ],
    base_init_calls=_BASE_INIT,
    base_known_info_template="You are {customer_name}. {fault_descriptions}.",
    base_ticket_template="Customer {customer_name}: {fault_descriptions}.",
    reason_for_call="You are contacting about a vehicle issue.",
    purpose="Test transfer-to-human for issues outside scope.",
    entity_id_field="customer_id",
    min_faults=1,
    max_faults=1,
    max_total_tasks=16,
)


# Step 5: Build RecipeBook and create_tasks
RECIPE_BOOK = RecipeBook(fault_layer_configs=[_fixable_config, _transfer_config])

def create_tasks(verify=True, save=False):
    return generate_recipe_tasks(
        recipe_book=RECIPE_BOOK,
        build_indexes=lambda db: db,
        get_db=lambda: AutoRepairDB.load(AUTO_REPAIR_DB_PATH),
        user_template=USER_TEMPLATE,
        personas=PERSONAS,
        seed=42,
    )
```

### User-Side Actions

Some faults require user-side confirmation after the agent acts. In the atoms interface, user actions are defined as separate FaultAtoms with `requestor="user"`:

```python
_worn_brake_pads = FaultLayer(
    name="worn_brake_pads",
    known_info_fragment="The brakes on my {vehicle_make} {vehicle_model} feel spongy.",
    atoms=[
        # Atom 1: Agent performs the repair
        FaultAtom(
            init=InitCall("assistant", "set_brake_pad_thickness",
                {"vehicle_id": "{vehicle_id}", "thickness": 1.5}),
            fix=ActionSpec(tool_name="replace_brake_pads",
                args={"order_id": "{order_id}"}, compare_args=["order_id"]),
            check=AssertionSpec(func_name="assert_brake_pad_thickness",
                args={"vehicle_id": "{vehicle_id}", "min_thickness": 3.0},
                env_type="assistant"),
        ),
        # Atom 2: User approves the repair (agent instructs user via policy)
        FaultAtom(
            fix=ActionSpec(tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user", compare_args=[]),
            check=AssertionSpec(func_name="assert_repair_approved",
                args={"order_id": "{order_id}"}, env_type="user"),
        ),
    ],
    resource_scope="brakes:{vehicle_id}",
)
```

Agent actions come first, user actions come second in the evaluation criteria. This matches the natural flow: agent acts at backend, then instructs user to confirm.

**The agent→user tool chain for user actions:**
1. The **policy** says: "After completing repairs, instruct the customer to use their approve_repairs tool"
2. The **agent** says: "I've replaced your brake pads. Please use your approve_repairs tool to authorize the work."
3. The **user sim** follows the instruction and calls `approve_repairs`

The user sim's task_instructions should be generic and agent-driven: "Follow the agent's instructions. When the agent asks you to use one of your tools, do so." The agent is the one that must learn which user tool to request — it gets this from the policy.

**Feasibility checklist for user actions:**
1. The policy must explicitly name the user tool and tell the agent to instruct the user. "instruct the customer to use their approve_repairs tool" — NOT "confirm the repair with the customer" (agent doesn't know which tool).
2. Prefer zero-arg user tools with `compare_args=[]` — these have the highest pass rate because the user simulator only needs to call the right tool, not guess argument values.
3. If a user action needs args, those values must appear in the agent's response to the user.
4. The `verify_user_action_feasibility` check runs at generation time and flags missing policy instructions.

### Sampling Strategies

When you have many groups (8-10) and entities (15-20), the cartesian product
can produce thousands of combinations. Two sampling strategies are available
(mutually exclusive — set one or neither, not both):

**`max_total_tasks=N`** — Proportional sampling (recommended). Groups combos
by fault_count tier and allocates budget proportionally. Middle tiers (2-4
faults) keep more tasks than edge tiers (1-fault, max-fault), preserving the
natural C(N,K) bell-curve distribution. Use this when you want a realistic
difficulty spread:

```python
_config = FaultLayerConfig(
    ...
    max_total_tasks=420,  # total specs budget; bell curve preserved
)
```

**`max_tasks_per_bin=N`** — Uniform bin sampling. Bins combos by
`(entity_id, fault_count)` and keeps at most N per bin. This flattens the
distribution so each tier gets roughly equal representation:

```python
_config = FaultLayerConfig(
    ...
    max_tasks_per_bin=3,  # at most 3 specs per (entity, fault_count) bin
)
```

When neither is set (both `None`), all combos are emitted — existing behavior
unchanged.

With 8 groups × 20 entities × `max_tasks_per_bin=3`, you'd get at most
`20 entities × 8 fault_counts × 3 = 480` specs (× N_personas = total tasks).

### Key Design Decisions

**Personas iterate per spec:**
- Every task spec produces one task per persona (e.g., 2 personas = 2× tasks).
- All personas get the **same known_info** — the user always knows what their problem is.
- Difficulty comes from the **persona** behavioral overlay only:
  - Cooperative personas (friendly, provides clear info)
  - Challenging personas (confused, gives emotional responses, needs reassurance)
- Define 2-4 personas with distinct interaction styles. Each persona should vary on a behavioral dimension (cooperativeness, verbosity, technical literacy).

**known_info_fragment must express clear intent:**
- The user simulator LLM interprets the fragment literally. If the fragment says "my invoice total looks wrong," the simulator may describe the wrong issue. Write fragments that make the expected action unambiguous: "I think the labor charges on my invoice are too high — I was quoted {original_labor_hours} hours of labor." This applies to any fault where the fix action isn't the only reasonable response to knowing about the problem.

**known_info_fragment must disambiguate which resource:**
- When an entity has multiple resources of the same type (e.g. two service orders, two invoices), the fragment MUST specify which one the user is referring to. Use entity template variables to identify the specific resource by date, type, or other distinguishing detail.
- BAD: `"My service order has the wrong date"` — the agent can't tell which service order.
- GOOD: `"My service appointment for the {vehicle_make} {vehicle_model} is scheduled for the wrong date. It should be on {original_scheduled_date}."` — unambiguous, the agent knows exactly which resource to act on.
- This is especially critical when a layer targets a `second_*` resource to avoid conflicts with another layer that targets `first_*`. Without disambiguation, the agent will naturally pick the first/earliest resource.

**Unfixable layers (transfer_to_human via composition):**
- Mark `unfixable=True` on layers where no available tool can resolve the fault
- Must have `actions=[]` and `assertions=[]` but non-empty `init_calls`
- **CRITICAL: Do NOT put unfixable layers in the same FaultLayerConfig as fixable layers.**
  The cartesian product means ANY combo containing an unfixable layer becomes a transfer task.
  Mixing them in poisons a huge fraction of combos (e.g. 1 unfixable in a 3-option group
  makes 1/3 of ALL tasks unfixable; with 2 such groups it's 5/9 = 56% unfixable).
- Instead, put all unfixable layers in a **separate FaultLayerConfig** with `max_faults=1`
  and `max_total_tasks=16`. This produces a small set of transfer tasks (~5% of total).
- Both configs go in the same `RecipeBook(fault_layer_configs=[fixable_config, transfer_config])`
- The recipe engine auto-generates a single `transfer_to_human` action with `compare_args=[]`
- Target 2-3 unfixable layers per domain for realistic transfer rates (~5-10%)

**compare_args on ActionSpec:**
- `None` (default): All arguments must match exactly
- `["patron_id"]`: Only patron_id must match; other args ignored
- `[]`: Match by tool name only. Use for `transfer_to_human` where the summary text is freeform

**min_faults / max_faults:**
- Controls difficulty. `min_faults=1` means every task has at least one problem.
- `min_faults=2` would skip single-fault tasks (only multi-fault combos).
- Use this to control task count and difficulty distribution.

**How many groups and layers to create:**

Aim for **8-10 fault groups** per FaultLayerConfig, with **2-3 mutually exclusive layers per group**. This produces a bell-curve difficulty distribution that matches the proven telecom benchmark shape (peak at ~N/2 faults). Each additional group adds ~5 cross-file touchpoints (init helper, fix tool, assertion, user tool, policy section) — every group must be semantically distinct. Reference table:

| Groups | Layers/group | Combos/entity | Max faults | Difficulty ceiling |
|--------|-------------|---------------|------------|-------------------|
| 6 | [2,2,2,1,1,2] | 323 | 6 | Below target — distribution peaks too low |
| 7 | [2,2,2,1,1,1,2] | 647 | 7 | Marginal — left-shifted bell curve |
| 8 | [3,2,2,2,1,1,1,2] | 1727 | 8 | **Minimum target** — use `max_total_tasks=1200` |
| 9 | [3,2,2,2,2,1,1,1,2] | 3455 | 9 | **Recommended** — use `max_total_tasks=1200` |
| 10 | [3,2,2,2,2,2,1,1,1,2] | 6911 | 10 | Rich domain — use `max_total_tasks=1200` |

The **max difficulty** of your domain equals the number of groups — that's how many faults fire simultaneously when all groups are active. Design your groups so that the all-active combination is a realistic (if difficult) customer service scenario.

**Think of groups as independent problem dimensions (fixable config only):**
Example from auto_repair (9 groups):
- Group 1: Account status (suspended/flagged) — UPSTREAM GATE: blocks vehicle access
- Group 2: Registration (expired) — SECOND GATE: blocks service order access
- Group 3: Service scheduling (wrong date/wrong type)
- Group 4: Brakes (worn pads/low fluid) — mechanical, discovered via diagnostic
- Group 5: Engine (overdue oil change/clogged air filter) — mechanical
- Group 6: Tires (low pressure/wheel misalignment) — mechanical
- Group 7: Electrical (weak battery/faulty alternator) — electrical
- Group 8: Warranty (expired warranty) — predicated on has_warranty
- Group 9: Billing (overcharged labor/missing discount)

Put unfixable layers (locked out, lost item, specialist referral) in a **separate transfer config**, not in these groups. This keeps the fixable config clean and avoids combinatorial poisoning.

Each group should represent a genuinely independent axis of failure. If two faults would conflict in the DB (e.g., "account locked" and "account suspended" modify the same field), they belong in the **same group** as mutually exclusive layers, not separate groups.

**Use `resource_scope` to catch conflicts automatically.** Every FaultLayer that modifies a specific resource instance should declare what it touches:

```python
_room_downgrade_layer = FaultLayer(
    name="room_downgrade",
    resource_scope="reservation:{first_reservation_id}",
    ...
)
_cancelled_reservation_layer = FaultLayer(
    name="cancelled_reservation",
    resource_scope="reservation:{first_reservation_id}",
    ...
)
```

If these two layers are in **different** groups, `_generate_fault_layer_specs` raises `ValueError` at generation time with a clear message explaining the conflict and how to fix it. If they're in the **same** group (mutually exclusive), no error — they can never both be active.

### Difficulty Target

The right number of fault groups and user tools depends on the archetype:

| Archetype | Fault Groups | Atoms/Layer | User WRITE Tools | Combos/Entity |
|-----------|-------------|-------------|------------------|---------------|
| A: Sequential Diagnostic | 6-10 | 2 | 3-5 | 500-5000 |
| B: Branching Troubleshooter | 5-9 | 1-2 | 5-15 | 200-2000 |
| C: Transaction Processor | 5-8 | 1-2 | 1-3 | 200-1000 |
| D: Triage / Classification | 4-7 | 1 | 1-2 | 100-500 |

Use `max_total_tasks=1200` for proportional sampling that preserves the natural
bell-curve distribution (many medium tasks, fewer easy/hard). Each group adds
~5 cross-file touchpoints — every group must be semantically distinct (different
DB fields, different fix tools, different reasoning).

**Semantic diversity matters more than count.** Each fault group must affect a
different DB field, require a different fix tool, or demand different reasoning.
Two layers that both call `issue_credit` with different amounts ($40 vs $75)
add combinatorial volume but NOT difficulty — the agent uses the same strategy
for both. Instead, design layers that vary the resolution strategy:

| Good diversity (different reasoning) | Bad diversity (same tool, different args) |
|--------------------------------------|------------------------------------------|
| `expired` → `renew_membership` | `small_fine` → `waive_fine($5)` |
| `suspended` → `reactivate_membership` | `large_fine` → `waive_fine($15)` |
| `overcharge` → `issue_credit` | `minibar_charge` → `issue_credit($40)` |
| `policy_violation` → deny + explain | `room_charge` → `issue_credit($75)` |
| `lost_book(unfixable)` → auto `transfer_to_human` | |

Within a group, mutually exclusive layers should require different tools or
different preconditions (e.g. `expired` vs `suspended` both affect membership
status but use different tools with different validation logic).

---

## 5. Evaluation Dimensions

Every task is scored on multiple dimensions, **multiplied together**. If any dimension scores 0, the total score is 0.

| Dimension | What It Checks | How It's Checked | When to Use |
|-----------|---------------|------------------|-------------|
| **ACTION** | Did the agent call the right tools with the right args? | Exact name + arg matching | Always. Every task needs expected actions. |
| **ENV_ASSERTION** | Is the database in the correct state after the agent acts? | Run assertion functions on the environment | When state changes matter (account reactivated, brakes replaced, labor adjusted). |
| **COMMUNICATE** | Did the agent tell the user important information? | Case-insensitive substring search in agent messages | Avoid — brittle exact-substring matching causes false negatives. Use NL_ASSERTION instead. |
| **DB** | Does the full database hash match the expected state? | Hash comparison of agent DB + user DB | Strict mode. Usually too rigid for complex domains. |
| **NL_ASSERTION** | Did the agent follow behavioral guidelines? | LLM-as-judge evaluates the conversation | WIP — not currently scored by default evaluator. |

**The Recipe Engine automatically sets reward_basis** to `[ACTION, ENV_ASSERTION]` when you provide actions and assertions. Use NL_ASSERTION for behavioral checks instead of COMMUNICATE.

**Composite / outcome-based assertions.** Instead of one assertion per fault, you can write a single boolean function that checks the entire system outcome. This is especially powerful with state-dependent READ tools — the composite check validates that ALL faults were fixed, regardless of which specific combination was active:

```python
# Instead of per-fault assertions:
#   assert_account_active, assert_registration_current, assert_brakes_ok

# Use a composite assertion:
def assert_vehicle_healthy(self, customer_id: str, vehicle_id: str) -> bool:
    """Assert the customer's vehicle and account are in a fully healthy state."""
    customer = self._find_customer(customer_id)
    if customer.account_status != "active":
        return False
    vehicle = self._find_vehicle(vehicle_id)
    if vehicle.registration_status != "current":
        return False
    if vehicle.brake_pad_thickness < 3.0:
        return False
    if vehicle.battery_voltage < 12.4:
        return False
    return True
```

Composite assertions have two advantages:
1. **Simpler task definitions** — one assertion per task instead of N assertions for N faults
2. **Validates the whole chain** — if any upstream fault wasn't fixed, the composite fails

You can use composite assertions alongside per-fault assertions, or as the sole ENV_ASSERTION. When used alone with `reward_basis=["ENV_ASSERTION"]` (no ACTION), the task evaluates purely on outcome — did the agent get the system to a healthy state? This is the pattern the telecom domain uses to great effect.

---

## 6. Verification System

When you call `create_tasks(verify=True)`, the framework runs 4 verification passes:

### Pass 1: Reward Basis (static)
- Checks reward_basis values are valid enum members
- Warns about compare_args referencing non-existent argument names

### Pass 2: Tool Schema (static, needs environment)
- Checks every action's tool_name exists in the appropriate toolkit
- Validates argument names match tool parameter schemas
- Ensures required parameters are present
- Validates env_assertion func_names exist

### Pass 3: Argument Reachability (runtime)
- For each expected action, checks if argument values are:
  - Present in the ticket text or known_info, OR
  - Discoverable by calling READ tools
- Warns if values can't be found through either path
- This catches tasks where the agent would need to "guess" a value

### Pass 4: Task Execution (runtime, optional)
- Creates fresh environment
- Runs init_actions (should break the environment)
- Runs expected fix actions (should repair it)
- Runs all assertions (should all pass)
- For transfer_to_human tasks: verifies the environment is NOT fixed (since the agent is escalating, not fixing)

**Always run with verify=True during development.** Only use verify=False in unit tests for speed.

---

## 7. Critical Gotchas

### sync_tools() Runs Between Every Init Step

`Environment.run_env_function_call()` calls `sync_tools()` after EACH call. So if your init has 3 steps:

```
Step 1: set_account_status(C001, "active")         → sync_tools() runs
Step 2: set_registration_status(V001, "current")   → sync_tools() runs
Step 3: set_brake_pad_thickness(V001, 1.5)         → sync_tools() runs
```

If your `sync_tools()` resets fields based on the DB state, earlier changes might get overwritten by later syncs. **Design sync_tools() to only project state, never modify agent-side state.** And design init steps to be order-independent where possible.

### Base Init Must Normalize Before Faults

The base_init_calls must bring the entity to a "healthy" state before fault layers inject problems. Otherwise, an entity whose DB state already has a fault value will have that fault even in tasks where the fault isn't active. In auto_repair, the base init just sets user identity since the DB starts healthy:

```python
_BASE_INIT = [
    # Set user identity
    InitCall("user", "set_customer_info", {
        "name": "{customer_name}", "customer_id": "{customer_id}",
    }),
]
```

Then fault layers inject problems on top:
```python
_suspended_account = FaultLayer(
    ...,
    atoms=[FaultAtom(
        init=InitCall("assistant", "set_account_status",
            {"customer_id": "{customer_id}", "status": "suspended"}),
        ...
    )],
)
```

### Entity Dict Must Contain All Fields Any Layer Needs

Every FaultLayer's `{field}` templates resolve against the same entity dict. If `_expired_warranty` uses `{warranty_id}` but an entity doesn't have a warranty plan, template resolution will crash. Use predicates to skip inapplicable entities:

```python
_expired_warranty = FaultLayer(
    ...
    predicate_field="has_warranty",  # entity["has_warranty"] must be truthy
)
```

### User Identity Must Be Set in Init

The user simulator needs to know who they are. Always include a `set_customer_info` (or `set_user_info`) call in `base_init_calls`:

```python
InitCall("user", "set_customer_info", {"name": "{customer_name}", "customer_id": "{customer_id}"})
```

### Persona Design

All personas get the same `known_info`. Difficulty comes solely from the persona's communication style (cooperative vs anxious/confused). Define 2-4 personas per domain with distinct behavioral dimensions.

### Prescriptive Policies Require Guarded WRITE Tools

Both reactive and prescriptive policies are valid — the right choice depends on the archetype:

- **Reactive policies** ("When X is broken, fix it"): Best for **Archetype A** (sequential diagnostic). The agent only acts when the situation calls for it.
- **Prescriptive policies** ("For every call, follow steps 1-N"): Valid for **Archetype C** (transaction processor) where the protocol is always the same. **BUT** you must add overwrite guards to WRITE tools.
- **Branching policies** ("If X, check Y; else check Z"): Best for **Archetype B** (branching troubleshooter).
- **Classification policies** ("Gather info, then categorize"): Best for **Archetype D** (triage).

**The danger: prescriptive policy + selective fault = agent overwrites correct data.** If the policy says "always assess the concern" but the `concern_unassessed` fault is only sometimes active, the agent calls `assess_concern` on every task — including tasks where the concern is already correct. In one domain, this caused 34% of all task failures.

**The key safety rule: if the policy prescribes calling a WRITE tool, that tool must guard against overwriting already-correct values:**

```python
@is_tool(ToolType.WRITE)
def assess_concern(self, case_id: str, concern_type: str) -> str:
    case = self._find_case(case_id)
    # Guard: don't overwrite an already-assessed concern
    if case.concern_type != "unassessed":
        return f"Case {case_id} already assessed as {case.concern_type}. No changes made."
    case.concern_type = concern_type
    return f"Concern assessed as {concern_type}."
```

**Test by mental simulation.** For every WRITE tool the policy tells the agent to call, ask: "What happens if the agent calls this tool when the corresponding fault is NOT active?" If the answer is "it overwrites correct data," add a guard.

### Assertions Must Be Deterministically Solvable

For every env_assertion that checks a specific expected value, you must prove the agent can derive **exactly** that value from the information available to it: policy rules + DB state + known_info.

If the expected value requires a judgment call that could reasonably go either way, the assertion is too strict and will produce false negatives (correct agent behavior scored as failure).

**Bad example — ambiguous risk level:**
```python
# Policy says: "moderate = struggling but functioning, high = significantly impaired"
# Expected: grief + high severity → moderate risk
# But an agent seeing "high severity grief" could reasonably set "high" risk
# This assertion will fail 50%+ of the time even for good agents
AssertionSpec(func_name="assert_risk_level",
    args={"caller_id": "{caller_id}", "expected_level": "moderate"})
```

**Good alternatives:**
```python
# Option 1: Lenient assertion — any non-initial value is acceptable
AssertionSpec(func_name="assert_risk_level_updated",
    args={"caller_id": "{caller_id}"})  # just checks it's not "low" (the init value)

# Option 2: Include expected value in known_info so agent can derive it
known_info_fragment="Your risk level should be assessed as moderate based on..."

# Option 3: Remove the assertion entirely if the mapping is ambiguous
```

**The solvability test:** For each assertion, ask: "If I gave 10 different humans the same policy and information, would they all produce the same value?" If not, either relax the assertion or provide more information.

### Information Architecture Must Match Archetype

The READ tool pattern is one of the most important design decisions, and the right choice depends on the archetype:

**Archetype A (Sequential Diagnostic):** Use **state-dependent** READ tools where upstream faults mask downstream state. This creates progressive discovery — the agent iterates through a diagnostic loop. Example: `get_vehicles()` returns "Account suspended" instead of vehicle list when the account isn't active.

**Archetype B (Branching Troubleshooter):** Use **transparent** agent-side READ tools. The challenge is NOT discovering backend state — it's interpreting user-reported diagnostics and choosing the right troubleshooting branch. The user has diagnostic tools; the agent must decide which to ask for.

**Archetype C (Transaction Processor):** Use **transparent** READ tools with **guarded** WRITE tools. Difficulty comes from protocol complexity and numeric computation, not from hidden state.

**Archetype D (Triage / Classification):** Use a **mix** of transparent READ tools and classification/search tools that return ambiguous results the agent must interpret.

**The key insight:** information hiding is just ONE way to create difficulty. A branching troubleshooter domain with transparent backend state can be just as challenging as a sequential diagnostic domain with deep gate chains — the difficulty comes from decision tree breadth instead of gate depth. Match the difficulty source to the archetype.

### Conditional User Action Instructions Cause Simulator Failures

The `task_instructions` field tells the user simulator how to behave. It must be **agent-driven** — the user sim follows the agent's lead, not a pre-baked checklist.

**Bad — baked-in tool mapping (user sim doesn't need the agent):**
```
"After the agent completes repairs, use your approve_repairs tool.
After the agent resolves a billing issue, use your make_payment tool."
```

**Good — agent-driven (user sim follows the agent's instructions):**
```
"Follow the agent's instructions throughout the conversation.
When the agent asks you to perform an action or use one of your tools, do so.
You must actually call the tool — describing the action in words is not sufficient.
You will consider your issues resolved when the agent confirms all problems have been addressed."
```

The agent learns about user tools from the **policy**, not from task_instructions. The policy says "instruct the customer to use their approve_repairs tool" → agent tells the user → user sim follows. This ensures the agent must learn to guide the user through every action, which is the training signal we want.

### Agent Tools Must Require User Action Preconditions

When a FaultLayer has both `actions` (agent-side) and `user_actions`, the agent tool **must fail** if the user hasn't acted yet. Without this precondition, the agent bypasses the user action entirely — the task scores ACTION:0.0 / ENV_ASSERTION:1.0 because the agent never tells the user to do anything.

**Pattern**: user action sets a `user_db` field → `sync_tools` bridges it to `agent_db` → agent tool checks the bridged field and raises if not set.

```python
# user_tools.py — user action sets a flag
@is_tool(ToolType.WRITE)
def make_payment(self, invoice_id: str, amount: float) -> str:
    invoice = self._find_invoice(invoice_id)
    invoice.payment_received = True
    return "Payment submitted."

# environment.py — sync_tools bridges user_db → agent_db
def sync_tools(self):
    ...
    # Bridge payment status from user to agent
    for inv in self.user_tools.db.invoices:
        agent_inv = self._find_agent_invoice(inv.invoice_id)
        if agent_inv and inv.payment_received:
            agent_inv.payment_confirmed = True

# tools.py — agent tool checks the bridged field
@is_tool(ToolType.WRITE)
def process_payment(self, invoice_id: str) -> str:
    invoice = self._find_invoice(invoice_id)
    if not invoice.payment_confirmed:
        raise ValueError(
            "Cannot process: customer has not made payment yet. "
            "Please instruct the customer to make their payment first."
        )
    invoice.status = "paid"
    return "Payment processed."
```

The `verify_user_action_redundancy` check catches missing preconditions at generation time — if the agent tool succeeds without the user action, it emits a WARNING.

### transfer_to_human Needs compare_args=[]

The `transfer_to_human` tool takes a `summary` argument that's freeform text. The agent will write their own summary, which won't match your template exactly. Use `compare_args=[]` to match by tool name only:

```python
ActionSpec(
    tool_name="transfer_to_human",
    args={"summary": "..."},
    compare_args=[],  # Don't compare the summary text
)
```

### Shuffle Tasks Before Saving

Tasks are generated in entity order (C001 first, then C002, etc.). If someone runs `--num-tasks 5`, they'll get 5 tasks for the same customer. Shuffle before saving:

```python
import random
random.seed(42)  # Deterministic shuffle
random.shuffle(tasks)
```

---

## 8. Task Diversity Checklist

A good domain should have diversity across these dimensions:

### Fault Count Distribution
- [ ] Single-fault tasks (1 action): Simple baseline tasks
- [ ] Two-fault tasks (2 actions): Moderate multi-step
- [ ] Three+ fault tasks (3-5 actions): Complex multi-step
- Aim for a good spread, not all concentrated in one tier

### Fault Type Coverage
- [ ] State faults: Something is wrong in the DB (overdue, expired, low balance)
- [ ] Unfixable faults: Agent must transfer to human (from unfixable layers)
- [ ] Combined: State faults + unfixable layers producing transfer_to_human

### Entity Coverage
- [ ] At least 3-4 distinct entities (patrons, customers, etc.)
- [ ] Entities with different attributes (with warranty vs without, different vehicle types)
- [ ] Each entity appears in multiple task combinations

### Persona Coverage
- [ ] Each spec produces one task per persona
- [ ] At least 2 personas with distinct interaction styles (cooperative vs challenging)

### Evaluation Dimension Coverage
- [ ] ACTION: Every task has expected actions
- [ ] ENV_ASSERTION: Most tasks have state assertions (both agent-side and user-side)
- [ ] COMMUNICATE: Do not use (brittle substring matching). Use NL_ASSERTION for behavioral checks.

### Information Architecture (archetype-dependent)
- [ ] **Archetype A:** State-dependent READ tools gate downstream state on upstream faults. Policy describes a diagnostic workflow matching the gate hierarchy.
- [ ] **Archetype B:** Transparent agent-side READ tools. User has diagnostic tools. Policy describes a branching decision tree.
- [ ] **Archetype C:** Transparent READ tools. Guarded WRITE tools prevent overwriting correct data. Policy describes prescriptive protocols with precondition checks.
- [ ] **Archetype D:** Mix of transparent and search/classification READ tools. Policy describes classification criteria and routing rules.
- [ ] Difficulty comes from the RIGHT source for the archetype (gate depth, decision tree breadth, protocol complexity, or classification ambiguity)

### Policy Coverage
- [ ] Tasks that test identity verification
- [ ] Tasks that test policy restrictions (can't do X when Y)
- [ ] Tasks with unfixable layers that require transfer_to_human
- [ ] Tasks that require multi-step troubleshooting

### Task Count Guidelines

| Domain Size | Specs | × Personas | Total Tasks |
|-------------|-------|------------|-------------|
| Minimal | 20-40 | ×2 | 40-80 |
| Medium | 50-120 | ×2 | 100-240 |
| Large | 150+ | ×2 | 300+ |

"Specs" = unique fault-entity combinations. Each persona multiplies the count (e.g., 2 personas = 2× tasks).

---

## 9. Quality Checklist

Before shipping a domain, verify:

### Environment
- [ ] `get_environment()` returns a working environment
- [ ] All expected agent tools are present with `@is_tool` decorator
- [ ] All expected user tools are present with `@is_tool` decorator
- [ ] `sync_tools()` correctly projects agent state to user state
- [ ] Agent WRITE tools actually modify DB state
- [ ] Agent READ tools return useful information for diagnosis

### Data
- [ ] `db.json` loads without errors
- [ ] `user_db.json` loads without errors
- [ ] DB entities have enough variety for fault layers
- [ ] No entity IDs or sensitive data leak into known_info

### Policy
- [ ] Policy covers all operations the agent can perform
- [ ] Policy defines when to transfer to human
- [ ] Policy includes identity verification requirement
- [ ] Policy is specific enough to create testable behavior
- [ ] **Policy names every user WRITE tool explicitly** — the agent has no other way to discover them
- [ ] Policy style matches archetype: diagnostic workflow (A), decision tree (B), prescriptive protocol (C), classification criteria (D)
- [ ] Policy instructions for user tools say "instruct the customer to use their {tool_name} tool" (exact name)
- [ ] If policy is prescriptive, all corresponding WRITE tools have overwrite guards

### Task Generation
- [ ] `create_tasks(verify=True)` passes with 0 errors AND 0 warnings
- [ ] Task count matches expected (entity count × combo count × N_personas)
- [ ] Tasks are deterministic (same seed → same output)
- [ ] Tasks have valid structure (id, ticket, evaluation_criteria)
- [ ] All tasks have at least 1 action
- [ ] communicate_info is NOT set (use assertions instead)
- [ ] Each persona appears in task IDs with [PERSONA:name] suffix
- [ ] transfer_to_human actions use compare_args=[]

### Agent→User Tool Chain
- [ ] Every user WRITE tool is mentioned by exact name in the policy
- [ ] task_instructions are agent-driven: "Follow the agent's instructions. When the agent asks you to use a tool, do so."
- [ ] task_instructions do NOT contain tool-specific mappings (no "After X, use your Y tool")
- [ ] User atoms use `compare_args=[]` for zero-arg matching
- [ ] Simulation run shows user tools being called (not skipped) — 65%+ pass rate expected

### Tests
- [ ] Environment tests: loads, tools exist, sync works
- [ ] Index tests: correct entity counts
- [ ] Generation tests: counts, structure, variants, cartesian correctness
- [ ] Verification test: all tasks pass verify_tasks()
- [ ] Determinism test: two runs produce identical output
- [ ] Registry test: domain is registered

### Benchmark Run
- [ ] `tau2 run --domain {domain} --num-tasks 10` completes
- [ ] At least some tasks pass (30%+ is reasonable for a good model)
- [ ] Failures are agent failures, not task setup failures (agent skipped a step, not "tool doesn't exist")
- [ ] Agent instructs user to use tools by name (check simulation logs)
- [ ] User sim actually calls tools when instructed (not just describing the action)
- [ ] Tasks for all defined personas appear in the sample

---

## 10. Common Mistakes

### Mistake: Assertion helper on wrong toolkit
```python
# WRONG: user assertion on agent toolkit
AssertionSpec(func_name="assert_repair_approved", args=..., env_type="assistant")
# RIGHT: user assertion on user toolkit
AssertionSpec(func_name="assert_repair_approved", args=..., env_type="user")
```

### Mistake: Forgetting to normalize in base_init
```python
# WRONG: Customer C005 starts with "suspended" account_status in db.json
# If your base_init doesn't normalize it, even tasks without the
# "suspended_account" fault will have a suspended account
```

### Mistake: Entity dict missing fields for conditional layers
```python
# WRONG: expired_warranty layer uses e["warranty_id"] but
# customer C003 has no warranty plan
# RIGHT: add predicate_field="has_warranty"  (truthy check)
```

### Mistake: Using compare_args=None for transfer_to_human
```python
# WRONG: Agent's summary won't match your template exactly
ActionSpec(tool_name="transfer_to_human",
           args={"summary": "exact text"})

# RIGHT: Match by name only
ActionSpec(tool_name="transfer_to_human",
           args={"summary": "exact text"},
           compare_args=[])
```

### Mistake: Using communicate_templates

Do **not** set `communicate_templates` on FaultLayers. The communicate evaluator uses exact substring matching which causes false negatives when agents use synonyms (e.g. "reinstated" vs "reactivated"). Actions + ENV_ASSERTIONs are sufficient to verify the agent did the right thing.

### Mistake: Not testing with actual benchmark run
```
Unit tests passing ≠ benchmark works
Always run: tau2 run --domain auto_repair --num-tasks 10 --agent-llm gpt-4o-mini
Then analyze: are failures agent failures or task setup failures?
Key checks: Does the agent instruct the user to use their tools? Does the user sim follow?
```

### Mistake: All tasks clustered on one entity
```
# WRONG: First 5 tasks in tasks.json are all P001
# When user runs --num-tasks 5, they get no diversity
# RIGHT: Shuffle tasks before saving
```

### Mistake: Two layers in different groups both target the same entity resource
```python
# WRONG: "apply_discount" and "cancel_appointment" are in different groups
# but both use e["first_appointment_id"]. When composed, the task expects
# the agent to cancel the appointment AND apply a discount to it — contradiction.
# The verification system WON'T catch this because it executes actions directly
# with god-knowledge of IDs. But a real agent can't see a cancelled appointment
# to apply a discount to it.
FaultLayer(name="missing_discount",
    resource_scope="appointment:{first_appointment_id}",
    actions=[ActionSpec(tool_name="apply_discount",
        args={"appointment_id": "{first_appointment_id}"})],
    ...)
FaultLayer(name="wrong_service",
    resource_scope="appointment:{first_appointment_id}",
    actions=[ActionSpec(tool_name="cancel_appointment",
        args={"appointment_id": "{first_appointment_id}"})],
    ...)

# FIX 1: Put conflicting layers in the SAME group (mutually exclusive).
# FIX 2: Target DIFFERENT resources (use second_appointment_id with predicate).
FaultLayer(name="missing_discount",
    resource_scope="appointment:{second_appointment_id}",
    predicate_field="has_second_appointment",
    actions=[ActionSpec(tool_name="apply_discount",
        args={"appointment_id": "{second_appointment_id}"})],
    ...)
```

**Always set `resource_scope`** on layers that modify specific resources. The recipe engine validates cross-group overlaps at generation time and raises `ValueError` with actionable fix suggestions.

### Mistake: User actions the simulator can't perform

User actions fail when:
1. **The agent never instructs the user to do it** — e.g., "confirm the appointment with the patient" means the *agent* confirms verbally, not a user portal action.
2. **The user can't discover the argument values** — e.g., `update_my_notification_preference(preference="email")` requires the user to know which preference, but the agent just says "update your settings."
3. **The user says "I'll do that later" and stops** — the user simulator often sends `###STOP###` instead of calling the tool.

```python
# WRONG: user action with args the user can't discover
FaultLayer(name="wrong_notifications",
    actions=[ActionSpec(tool_name="update_notification_preference",
        args={"patient_id": "{patient_id}", "preference": "{pref}"})],
    user_actions=[
        ActionSpec(tool_name="update_my_notification_preference",
            args={"preference": "{pref}"}),  # user must guess "email"
    ],
    ...)

# RIGHT: use compare_args=[] for name-only matching on zero-arg user tools
FaultLayer(name="portal_locked",
    actions=[ActionSpec(tool_name="unlock_patient_portal",
        args={"patient_id": "{patient_id}"})],
    user_actions=[
        ActionSpec(tool_name="reset_portal_password",
            compare_args=[]),  # name-only match — no args to guess
    ],
    ...)
```

**Rules for reliable user actions:**
- Prefer zero-arg user tools with `compare_args=[]` (70%+ of telecom user actions take no args)
- Only add user_actions when the policy explicitly says "instruct the user to X" — not "confirm with the patient"
- If args are needed, the agent's response must contain the exact values
- The `verify_user_action_feasibility` check catches these at generation time

### Mistake: Agent Tool Works Without User Action Precondition

If `process_payment` succeeds without the user calling `make_payment` first, the agent never instructs the user to pay — it just processes payment directly. The task scores ACTION:0.0 (user action never happens) even though ENV_ASSERTION:1.0 (the DB ends up correct).

**Fix**: Add a bridged field that `sync_tools` sets only when the user acts, and check it in the agent tool:

1. User tool sets `user_db.invoice.payment_received = True`
2. `sync_tools` bridges: `agent_db.invoice.payment_confirmed = user_db.invoice.payment_received`
3. Agent tool raises if `not invoice.payment_confirmed`

The `verify_user_action_redundancy` check catches this at generation time — if an agent action succeeds without the corresponding user action, it emits a WARNING

### Mistake: READ tool pattern doesn't match archetype

**Archetype A with transparent READ tools:** If your domain is sequential diagnostic but all READ tools return full state, the agent sees every fault at once and fixes them in any order — no diagnostic reasoning required. Add state-dependent gating to create progressive discovery.

**Archetype B with state-dependent READ tools:** If your domain is a branching troubleshooter but agent-side READ tools hide state, you're mixing metaphors. The difficulty should come from the decision tree (which diagnostic to run, which fix to instruct), not from information hiding.

**Archetype C with no overwrite guards:** If your domain is a transaction processor with prescriptive policy but WRITE tools don't guard against overwriting, the agent corrupts correct data on tasks where the fault isn't active.

Match the READ/WRITE tool pattern to the archetype. See `docs/skills/07-tools.md` for detailed examples per archetype.

### Mistake: Policy style doesn't match archetype

The policy structure must match the domain's archetype and information architecture:

- **Archetype A** needs a diagnostic workflow with gates: "Fix account BEFORE proceeding to vehicles" — because state-dependent READ tools enforce this ordering.
- **Archetype B** needs a decision tree: "If airplane mode is on, instruct toggle_airplane_mode; if SIM not detected, instruct reseat_sim_card" — because the user performs different fixes based on diagnostics.
- **Archetype C** needs a prescriptive protocol: "For every refund: verify not already refunded, check eligibility, confirm amount, process" — with overwrite guards on WRITE tools.
- **Archetype D** needs classification criteria: "Hardware issues → route to hardware team; software → software team" — with clear category definitions.

A flat checklist policy ("1. Look up account, 2. Check vehicles, 3. Run diagnostics") is only wrong for Archetype A where state-dependent tools enforce ordering. For Archetype C, a step-by-step protocol IS the correct policy style. See `docs/skills/06-policy.md` for complete patterns.

