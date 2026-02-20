# Domain Authoring Guide for tau2-bench

This guide covers everything you need to know to write a new domain from scratch. It's written from hard-won experience building library, smart_home, hosting, bank, and clinic domains on the Recipe Engine pipeline.

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

**What is the service?** (library helpdesk, bank customer service, clinic scheduling, etc.)

**What entities exist?** List the main objects and their relationships:
- Primary entities (books, accounts, appointments)
- Secondary entities (patrons, customers, doctors)
- Their relationships (a book is checked out by a patron)

**What can go wrong?** These become your fault layers:
- State faults (overdue book, expired membership, low balance)
- Missing/incorrect data (wrong address, stale cache)
- Policy violations (can't checkout with fines, can't schedule during blackout)

**What can the agent do?** These become your agent tools:
- READ tools: look up records, search, check status
- WRITE tools: modify state (return book, waive fine, update record)
- GENERIC tools: transfer_to_human

**What can the agent NOT do?** These become unfixable layers (transfer_to_human):
- Update personal information (email, address, phone)
- Handle requests outside the system (interlibrary loan, wire transfer)
- Override hard policy limits

**What can the user do on their end?** These become user-side WRITE tools and `user_actions`:
- Device toggles (airplane mode, restart device)
- Account confirmations (verify settings, accept changes)
- The agent instructs the user to perform these actions

**What can the user observe?** This becomes your user_db and user tools:
- Account status, balance, membership
- Result of agent's actions (book returned, fine waived)

### 3.2 Create the Agent Database

**`data/tau2/domains/{domain}/db.json`**

Design principles:
- **Small but rich**: 15-20 primary entities, 5-10 secondary entities
- **Pre-seeded variety**: Include entities in different states (some active, some expired; some with fines, some without)
- **Relationships matter more than volume**: A patron with 2 checked-out books creates more task variety than 50 patrons with 0
- **Ensure every fault layer has at least 2-3 applicable entities**: If you have an "overdue" fault, you need at least 2-3 patrons who have checked-out books that can be set to overdue
- **Avoid special characters in names**: No apostrophes, accents, or non-ASCII characters (e.g. use "Kevin Brooks" not "Kevin O'Brien", "Napoli Pizzeria" not "Napoli's Pizzeria"). LLMs reliably send curly/smart quotes instead of straight apostrophes, causing exact-match lookups to fail.

Example structure:
```json
{
  "books": [
    {"book_id": "B001", "title": "The Great Gatsby", "author": "F. Scott Fitzgerald",
     "status": "available", "borrower_id": null},
    {"book_id": "B002", "title": "1984", "author": "George Orwell",
     "status": "checked_out", "borrower_id": "P001"}
  ],
  "patrons": [
    {"patron_id": "P001", "name": "Alice Johnson", "email": "alice@email.com",
     "membership": "active", "fines_owed": 0.0},
    {"patron_id": "P005", "name": "Eve Martinez", "email": "eve@email.com",
     "membership": "expired", "fines_owed": 3.00}
  ]
}
```

**`src/tau2/domains/{domain}/data_model.py`**

```python
from typing import List, Optional
from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra

class Book(BaseModelNoExtra):
    book_id: str
    title: str
    author: str
    status: str  # "available", "checked_out", "overdue"
    borrower_id: Optional[str] = None

class Patron(BaseModelNoExtra):
    patron_id: str
    name: str
    email: str
    membership: str  # "active", "expired"
    fines_owed: float = 0.0

class LibraryDB(DB):
    books: List[Book]
    patrons: List[Patron]
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
  "patron_name": null,
  "patron_id": null,
  "checked_out_books": [],
  "fines_visible": 0.0,
  "membership_status": "active"
}
```

**`src/tau2/domains/{domain}/user_data_model.py`**

```python
from typing import List, Optional
from tau2.environment.db import DB

class LibraryUserDB(DB):
    patron_name: Optional[str] = None
    patron_id: Optional[str] = None
    checked_out_books: List[str] = []
    fines_visible: float = 0.0
    membership_status: str = "active"
```

Design principle: The user DB is a **projection** of the agent DB. It contains only what the user can see or verify. The `sync_tools()` method (Step 3.7) keeps it in sync.

### 3.4 Write the Policy

**`data/tau2/domains/{domain}/policy.md`**

The policy is the agent's instruction manual. It's injected as the system prompt. Structure it with these sections:

```markdown
# {Domain} Support Policy

## Identity Verification
Always verify the caller's identity before making any account changes.
Ask for their name and look up their account to confirm.

## {Core Operations}
### {Operation 1} (e.g., Book Checkout)
- Conditions: what must be true before this action
- Restrictions: when this action is blocked
- Steps: what the agent should do

### {Operation 2} (e.g., Fine Waiver)
- When to waive, amounts, conditions

## Troubleshooting / Account Investigation
When a patron reports a general issue:
1. Look up their account
2. Check for overdue books
3. Check for outstanding fines
4. Check membership status
5. Address each issue found

## Escalation
Transfer to a human agent if:
- You cannot resolve the patron's issue with available tools
- The patron requests a service not available through the system
- (List specific scenarios: email updates, special requests, etc.)

## Communication
- Explain what you find on the account
- Confirm actions taken
- Be professional and helpful
```

Tips:
- **Be specific about when to escalate.** If the policy says "transfer if you can't resolve," but the agent has tools for everything, it will never transfer. You need unresolvable scenarios.
- **Define a troubleshooting order.** This creates policy-following behavior that the benchmark can test.
- **List what the agent can and cannot do.** This implicitly defines escalation triggers.
- **Include verification steps.** "After returning a book, confirm with the patron" creates COMMUNICATE evaluation opportunities.

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
    def search_catalog(self, query: str) -> List[Dict[str, Any]]:
        """
        Search the library catalog by title or author.

        Args:
            query: Search string to match against titles and authors.

        Returns:
            List of matching books with their details.
        """
        # Implementation...

    @is_tool(ToolType.WRITE)
    def return_book(self, book_id: str) -> str:
        """
        Return a checked-out book to the library.

        Args:
            book_id: The book identifier to return.

        Returns:
            Confirmation message.
        """
        # Implementation...

    @is_tool(ToolType.GENERIC)
    def transfer_to_human(self, summary: str) -> str:
        """
        Transfer the call to a human agent.

        Args:
            summary: Brief description of the issue for the human agent.

        Returns:
            Confirmation of transfer.
        """
        return f"Call transferred to human agent. Summary: {summary}"

    # =============================================
    # ASSERTION HELPERS — called by verify, not decorated
    # =============================================

    def assert_book_status(self, book_id: str, expected: str) -> bool:
        """Assert a book has the expected status."""
        book = self._find_book(book_id)
        return book is not None and book.status == expected

    def assert_patron_fines(self, patron_id: str, expected: float) -> bool:
        """Assert a patron's fines match expected amount."""
        patron = self._find_patron(patron_id)
        return patron is not None and abs(patron.fines_owed - expected) < 0.01

    def assert_membership_status(self, patron_id: str, expected: str) -> bool:
        """Assert patron membership status."""
        patron = self._find_patron(patron_id)
        return patron is not None and patron.membership == expected

    # =============================================
    # SETUP HELPERS — called by scenarios for init, not decorated
    # =============================================

    def set_book_status(self, book_id: str, status: str) -> None:
        """Set a book's status directly (for scenario init)."""
        book = self._find_book(book_id)
        if book is None:
            raise ValueError(f"Book {book_id} not found")
        book.status = status

    def set_patron_fines(self, patron_id: str, amount: float) -> None:
        """Set a patron's fines directly (for scenario init)."""
        patron = self._find_patron(patron_id)
        if patron is None:
            raise ValueError(f"Patron {patron_id} not found")
        patron.fines_owed = amount

    def set_patron_membership(self, patron_id: str, status: str) -> None:
        """Set patron membership status (for scenario init)."""
        patron = self._find_patron(patron_id)
        if patron is None:
            raise ValueError(f"Patron {patron_id} not found")
        patron.membership = status

    # =============================================
    # PRIVATE HELPERS
    # =============================================

    def _find_book(self, book_id: str) -> Optional[Book]:
        return next((b for b in self.db.books if b.book_id == book_id), None)

    def _find_patron(self, patron_id: str) -> Optional[Patron]:
        return next((p for p in self.db.patrons if p.patron_id == patron_id), None)
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

**Entity navigation tools are required.** For every child entity type that has a foreign key to the primary entity (e.g. `Pet.owner_id`, `Appointment.owner_id`, `Invoice.owner_id`), include a READ tool that lets the agent look up children by parent ID:

```python
@is_tool(ToolType.READ)
def get_pets_by_owner(self, owner_id: str) -> List[Pet]:
    """Get all pets belonging to a specific owner."""
    self._get_owner(owner_id)  # Validate owner exists
    return [pet for pet in self.db.pets if pet.owner_id == owner_id]

@is_tool(ToolType.READ)
def get_appointments_by_owner(self, owner_id: str) -> List[Appointment]:
    """Get all appointments for a specific owner."""
    self._get_owner(owner_id)
    return [appt for appt in self.db.appointments if appt.owner_id == owner_id]
```

Without these navigation tools, the agent knows the customer's name/ID from the conversation but has no way to discover related entity IDs (pet IDs, appointment IDs, invoice IDs). It will guess IDs, get errors, and fail every fixable task. The pipeline validates this automatically — if 2+ child collections share a foreign key but no READ tool accepts that key as a parameter, the validation gate raises an error.

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

    @is_tool(ToolType.READ)
    def check_my_account(self) -> dict:
        """Check my library account status."""
        return {
            "patron_name": self.db.patron_name,
            "checked_out_books": self.db.checked_out_books,
            "fines": self.db.fines_visible,
            "membership": self.db.membership_status,
        }

    # =============================================
    # USER ASSERTIONS — called by evaluation, not decorated
    # =============================================

    def assert_fines_equal(self, expected: float) -> bool:
        """Assert user's visible fines match expected."""
        return abs(self.db.fines_visible - expected) < 0.01

    def assert_membership_active(self) -> bool:
        """Assert user's visible membership is active."""
        return self.db.membership_status == "active"

    def assert_book_not_checked_out(self, book_id: str) -> bool:
        """Assert a book is no longer in user's checked-out list."""
        return book_id not in self.db.checked_out_books

    # =============================================
    # SETUP HELPERS — called by scenarios, not decorated
    # =============================================

    def set_user_info(self, name: str, patron_id: str) -> None:
        """Set the user's identity for this scenario."""
        self.db.patron_name = name
        self.db.patron_id = patron_id
```

User tools serve two purposes:
1. **The simulated user verifies the agent's work** (e.g., "let me check my account")
2. **User-side assertions** check the user's view is correct after the agent acts

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
        patron_id = self.user_tools.db.patron_id
        if patron_id is None:
            return

        # Find patron in agent DB
        patron = next(
            (p for p in self.tools.db.patrons if p.patron_id == patron_id),
            None,
        )
        if patron is None:
            return

        # Project agent state → user-visible state
        self.user_tools.db.checked_out_books = [
            b.book_id for b in self.tools.db.books
            if b.borrower_id == patron_id
            and b.status in ("checked_out", "overdue")
        ]
        self.user_tools.db.fines_visible = patron.fines_owed
        self.user_tools.db.membership_status = patron.membership


def get_environment(
    db=None, user_db=None, solo_mode=False
) -> {Domain}Environment:
    """Factory function — called by registry and by task generation."""
    if db is None:
        db = {Domain}DB.load({DOMAIN}_DB_PATH)
    tools = {Domain}Tools(db)

    if user_db is None:
        user_db = {Domain}UserDB.load({DOMAIN}_USER_DB_PATH)
    user_tools = {Domain}UserTools(user_db)

    policy = load_file({DOMAIN}_POLICY_PATH)

    env = {Domain}Environment(
        domain_name="{domain}",
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    """Load tasks from tasks.json — called by registry."""
    if not {DOMAIN}_TASK_SET_PATH.exists():
        return []
    tasks = load_file({DOMAIN}_TASK_SET_PATH)
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
        self.assertEqual(env.domain_name, "{domain}")

    def test_agent_tools_exist(self):
        env = get_environment()
        tools = env.tools.get_tools()
        for name in ["search_catalog", "return_book", "transfer_to_human", ...]:
            self.assertIn(name, tools)

    def test_user_tools_exist(self):
        env = get_environment()
        tools = env.user_tools.get_tools()
        for name in ["check_my_account", ...]:
            self.assertIn(name, tools)

    def test_sync_tools_propagates(self):
        """Agent action → sync → user sees change."""
        env = get_environment()
        env.user_tools.set_user_info("Alice", "P001")
        env.sync_tools()
        # Do agent action
        env.tools.return_book("B002")
        env.sync_tools()
        # Verify user sees it
        self.assertNotIn("B002", env.user_tools.db.checked_out_books)


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
        """Expected: N specs × 2 variants = 2N tasks."""
        tasks = create_tasks(verify=False)
        self.assertEqual(len(tasks), EXPECTED_COUNT)

    def test_tasks_have_valid_structure(self):
        tasks = create_tasks(verify=False)
        for task in tasks:
            self.assertIn("[{domain}]", task.id)
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

    def test_variant_b_uses_hard_persona(self):
        """VARIANT:b tasks use a hard persona (difficulty from persona only)."""
        tasks = create_tasks(verify=False)
        for t in tasks:
            if "VARIANT:b" in t.id:
                self.assertIn("anxious", t.user_scenario.persona.lower())


class TestRegistry(unittest.TestCase):
    def test_registered(self):
        from tau2.registry import registry
        self.assertIn("{domain}", registry.get_domains())
```

---

## 4. The Recipe Engine: FaultLayer System

The Recipe Engine generates tasks by combining **fault layers** across **entities**. This is the recommended approach for new domains.

### Core Concepts

**Entity**: A database record (or combination of records) that becomes the subject of a task. One patron with their checked-out books = one entity.

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
Entity: Alice (1 book)

FIXABLE CONFIG (bulk of tasks):
Groups: [book_status, fines, membership]
Per group: pick 0 or 1 layer (all fixable)
  book_status: [None, overdue]      → 2 options
  fines:       [None, fines]        → 2 options
  membership:  [None, expired]      → 2 options

Total combos: 2 × 2 × 2 - 1 = 7 fixable specs for Alice

TRANSFER CONFIG (small set):
Groups: [unfixable_issue]
  unfixable_issue: [lost_book, locked_out]  → 2 options
  max_faults=1, max_tasks_per_bin=1

Total: 2 transfer specs for Alice (one per unfixable layer)

Result: ~78% fixable, ~22% transfer (7 fixable + 2 transfer)
```

### Building a FaultLayerConfig

```python
from tau2.generators.recipe import (
    ActionSpec, AssertionSpec, FaultLayer, FaultLayerConfig,
    FaultLayerGroup, InitCall, RecipeBook,
)

# Step 1: Define entity query
# Returns list of dicts, each dict is one entity with all fields
# the fault layers will need
def _entity_query(indexes: MyIndexes) -> list[dict]:
    entities = []
    for patron in indexes.patrons_with_books:
        entity = {
            "patron_id": patron["patron_id"],
            "patron_name": patron["patron_name"],
            "patron_email": patron["patron_email"],
            "first_book_id": patron["books"][0]["book_id"],
            "first_book_title": patron["books"][0]["title"],
            # Include all fields any fault layer might need
        }
        if len(patron["books"]) >= 2:
            entity["second_book_id"] = patron["books"][1]["book_id"]
            # ...
        entities.append(entity)
    return entities


# Step 2: Define base init (normalize to healthy state)
# Use a list[InitCall] with {field} templates instead of a lambda.
_BASE_INIT: list[InitCall] = [
    InitCall("assistant", "set_patron_membership", {
        "patron_id": "{patron_id}", "status": "active",
    }),
    InitCall("assistant", "set_patron_fines", {
        "patron_id": "{patron_id}", "amount": 0.0,
    }),
    # Set user identity LAST
    InitCall("user", "set_user_info", {
        "name": "{patron_name}", "patron_id": "{patron_id}",
    }),
]


# Step 3: Define fault layers
# All fields use declarative templates — no lambdas.
# {field} references in args dicts are resolved against the entity dict.
# Pure {field} preserves the entity value's type (int, float, str).
_overdue_layer = FaultLayer(
    name="overdue",
    # How to inject the fault — list of InitCall
    init_calls=[
        InitCall("assistant", "set_book_status", {
            "book_id": "{first_book_id}", "status": "overdue",
        }),
    ],
    # What the agent should do to fix it — args is a template dict
    actions=[
        ActionSpec(tool_name="return_book", args={"book_id": "{first_book_id}"}),
    ],
    # Post-condition checks — args is a template dict
    assertions=[
        AssertionSpec(
            func_name="assert_book_status",
            args={"book_id": "{first_book_id}", "expected": "available"},
            env_type="assistant",
        ),
        AssertionSpec(
            func_name="assert_book_not_checked_out",
            args={"book_id": "{first_book_id}"},
            env_type="user",
        ),
    ],
    known_info_fragment="I have an overdue book '{first_book_title}'",
    resource_scope="book:{first_book_id}",
)

_lost_book_layer = FaultLayer(
    name="lost_book",
    unfixable=True,
    init_calls=[
        InitCall("assistant", "set_book_status", {
            "book_id": "{first_book_id}", "status": "lost",
        }),
    ],
    actions=[],
    assertions=[],
    known_info_fragment="the system says my copy of '{first_book_title}' is marked as lost but I have it right here",
    resource_scope="book:{first_book_id}",
)


# Step 4: Group fault layers into TWO configs
_fixable_config = FaultLayerConfig(
    name="patron_account",
    entity_query=_entity_query,
    groups=[
        FaultLayerGroup(name="book_status", layers=[_overdue_layer]),
        FaultLayerGroup(name="fines", layers=[_fines_layer]),
        FaultLayerGroup(name="membership", layers=[_expired_layer]),
    ],
    base_init_calls=_BASE_INIT,
    base_known_info_template="I'm {patron_name}. {fault_descriptions}.",
    base_ticket_template="Patron {patron_name}: {fault_descriptions}.",
    reason_for_call="I need help with my library account.",
    purpose="Test multi-fault account resolution",
    base_nl_assertion_templates=[
        "The assistant should verify the patron's identity before making changes",
        "The assistant should explain what issues were found on the account",
    ],
    entity_id_field="patron_id",
    min_faults=1,
    max_faults=99,
)

# TRANSFER config — unfixable layers only (small set)
_transfer_config = FaultLayerConfig(
    name="patron_account_transfer",
    entity_query=_entity_query,
    groups=[
        FaultLayerGroup(name="unfixable_issue", layers=[_lost_book_layer]),
    ],
    base_init_calls=_BASE_INIT,
    base_known_info_template="I'm {patron_name}. {fault_descriptions}.",
    base_ticket_template="Patron {patron_name}: {fault_descriptions}.",
    reason_for_call="I need help with my library account.",
    purpose="Test transfer-to-human for unsupported requests",
    entity_id_field="patron_id",
    min_faults=1,
    max_faults=1,
    max_tasks_per_bin=1,
)


# Step 5: Build RecipeBook and create_tasks
from tau2.generators.recipe import generate_recipe_tasks

RECIPE_BOOK = RecipeBook(fault_layer_configs=[_fixable_config, _transfer_config])

def create_tasks(verify=True, save=False):
    return generate_recipe_tasks(
        recipe_book=RECIPE_BOOK,
        build_indexes=build_indexes,
        get_db=get_db,
        user_template=USER_TEMPLATE,
        personas=PERSONAS,
        seed=42,
    )
```

### User-Side Actions

Some faults require the user to act (toggle airplane mode, reboot device,
confirm settings). Use `user_actions` on FaultLayer:

```python
_airplane_mode_layer = FaultLayer(
    name="airplane_mode_on",
    init_calls=[InitCall("user", "toggle_airplane_mode", {"enabled": True})],
    actions=[],  # no agent-side fix needed
    user_actions=[
        ActionSpec(tool_name="toggle_airplane_mode", args={"enabled": False}),
    ],
    assertions=[...],
    known_info_fragment="my phone is in airplane mode",
)
```

The engine auto-sets `requestor="user"` on all user_actions. Agent actions come
first, user actions come second in the evaluation criteria. This matches the
natural flow: agent acts at backend, then instructs user to act on device.

You can also use `base_user_actions` on FaultLayerConfig for user actions that
apply to every task (e.g., "confirm changes on your device"):

```python
_config = FaultLayerConfig(
    ...
    base_user_actions=[
        ActionSpec(tool_name="confirm_settings", args={"device_id": "{device_id}"}),
    ],
)
```

Base user actions appear after layer user actions.

**Feasibility checklist for user actions:**
1. The policy must explicitly instruct the agent to tell the user to perform the action (not just "confirm with the patient" — that's verbal).
2. Prefer zero-arg user tools with `compare_args=[]` — these have the highest pass rate because the user simulator only needs to call the right tool, not guess argument values.
3. If a user action needs args, those values must appear in the agent's response to the user (e.g., "please acknowledge treatment plan TP001 in your portal").
4. The `verify_user_action_feasibility` check runs at generation time and flags user actions with undiscoverable args or missing task_instructions.

### Sampling Strategies

When you have many groups (6-8) and entities (15-20), the cartesian product
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
`20 entities × 8 fault_counts × 3 = 480` specs (× 2 variants = 960 tasks).

### Key Design Decisions

**VARIANT:a vs VARIANT:b (matching telecom's PERSONA pattern):**
- Both variants get the **same known_info** — the user always knows what their problem is.
- Difficulty comes from the **persona** behavioral overlay only:
  - VARIANT:a uses an easy/cooperative persona (friendly, provides clear info)
  - VARIANT:b uses a hard/anxious persona (confused, gives emotional responses, needs reassurance)
- This matches the original telecom domain's pattern where Hard personas change *communication style*, not *information available*.

**known_info_fragment must express clear intent:**
- The user simulator LLM interprets the fragment literally. If the fragment says "I have a $25 balance on my account," the simulator may respond "I'll pay it" instead of asking for a waiver. Write fragments that make the expected action unambiguous: "I have a $25 balance on my account that I'd like waived." This applies to any fault where the fix action isn't the only reasonable response to knowing about the problem.

**known_info_fragment must disambiguate which resource:**
- When an entity has multiple resources of the same type (e.g. two appointments, two bookings, two orders), the fragment MUST specify which one the user is referring to. Use entity template variables to identify the specific resource by name, date, or other distinguishing detail.
- BAD: `"I'd like to redeem points for my upcoming appointment"` — the agent can't tell which appointment, so it may pick the wrong one, defer to a human transfer, or skip the action entirely.
- GOOD: `"I'd like to redeem points for {second_appointment_pet_name}'s {second_appointment_service_type} appointment on {second_appointment_date}"` — unambiguous, the agent knows exactly which resource to act on.
- This is especially critical when a layer targets a `second_*` resource to avoid conflicts with another layer that targets `first_*`. Without disambiguation, the agent will naturally pick the first/earliest resource.

**Unfixable layers (transfer_to_human via composition):**
- Mark `unfixable=True` on layers where no available tool can resolve the fault
- Must have `actions=[]` and `assertions=[]` but non-empty `init_calls`
- **CRITICAL: Do NOT put unfixable layers in the same FaultLayerConfig as fixable layers.**
  The cartesian product means ANY combo containing an unfixable layer becomes a transfer task.
  Mixing them in poisons a huge fraction of combos (e.g. 1 unfixable in a 3-option group
  makes 1/3 of ALL tasks unfixable; with 2 such groups it's 5/9 = 56% unfixable).
- Instead, put all unfixable layers in a **separate FaultLayerConfig** with `max_faults=1`
  and `max_tasks_per_bin=1`. This produces a small set of transfer tasks (~5% of total).
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

Aim for **6-8 fault groups** per FaultLayerConfig, with **2-3 mutually exclusive layers per group**. This is the sweet spot:

| Groups | Layers/group | Combos/entity | Max faults | Difficulty ceiling |
|--------|-------------|---------------|------------|-------------------|
| 4 | [2,1,1,2] | 35 | 4 | Below target — add groups or expand layers |
| 5 | [2,2,1,1,2] | 107 | 5 | Acceptable — good for simpler domains |
| 6 | [2,2,2,1,1,2] | 323 | 6 | **Recommended** — use max_tasks_per_bin=3 |
| 7 | [2,2,2,1,1,1,2] | 647 | 7 | High — requires bin sampling |
| 8 | [3,2,2,2,1,1,1,2] | 1727 | 8 | Telecom-level — use max_tasks_per_bin=3 |

The **max difficulty** of your domain equals the number of groups — that's how many faults fire simultaneously when all groups are active. Design your groups so that the all-active combination is a realistic (if difficult) customer service scenario.

**Think of groups as independent problem dimensions (fixable config only):**
- Group 1: Account status (expired/suspended/frozen)
- Group 2: Billing (overcharge/missing credit)
- Group 3: Core resource (cancelled reservation/missing item)
- Group 4: Secondary resource (wrong date, wrong service type)
- Group 5+ (optional): Additional complications, loyalty programs, etc.

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

Aim for 6-8 fault groups with ~300+ combinations per entity. At least 3 groups
should have 2+ mutually exclusive layers. Include 3-5 user-side WRITE tools
for device/account actions. Use `max_tasks_per_bin=3` to cap output when
combinations exceed ~200. This ensures tasks range from simple (1 fault)
to complex (6-8 simultaneous faults) and produces enough variety to avoid
ceiling effects in benchmarking.

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

**Difficulty dial pattern — default to hardest, relax downward:**

```python
def create_tasks(difficulty="hard", verify=True, save=False):
    if difficulty == "hard":
        min_f, max_f = 3, 99        # 3+ faults only
        vc = VariantConfig(easy_personas=HARD, hard_personas=HARD)
    elif difficulty == "medium":
        min_f, max_f = 2, 3
        vc = STANDARD_VARIANT_CONFIG  # mixed personas
    elif difficulty == "easy":
        min_f, max_f = 1, 1
        vc = VariantConfig(easy_personas=EASY, hard_personas=EASY)
    else:  # "all"
        min_f, max_f = 1, 99
        vc = STANDARD_VARIANT_CONFIG
```

This requires zero engine changes — it's purely FaultLayerConfig params and persona selection.

---

## 5. Evaluation Dimensions

Every task is scored on multiple dimensions, **multiplied together**. If any dimension scores 0, the total score is 0.

| Dimension | What It Checks | How It's Checked | When to Use |
|-----------|---------------|------------------|-------------|
| **ACTION** | Did the agent call the right tools with the right args? | Exact name + arg matching | Always. Every task needs expected actions. |
| **ENV_ASSERTION** | Is the database in the correct state after the agent acts? | Run assertion functions on the environment | When state changes matter (book returned, fine waived). |
| **COMMUNICATE** | Did the agent tell the user important information? | Case-insensitive substring search in agent messages | Avoid — brittle exact-substring matching causes false negatives. Use NL_ASSERTION instead. |
| **DB** | Does the full database hash match the expected state? | Hash comparison of agent DB + user DB | Strict mode. Usually too rigid for complex domains. |
| **NL_ASSERTION** | Did the agent follow behavioral guidelines? | LLM-as-judge evaluates the conversation | WIP — not currently scored by default evaluator. |

**The Recipe Engine automatically sets reward_basis** to `[ACTION, ENV_ASSERTION]` when you provide actions and assertions. Use NL_ASSERTION for behavioral checks instead of COMMUNICATE.

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
Step 1: set_patron_membership(P001, "active")    → sync_tools() runs
Step 2: set_patron_fines(P001, 0.0)              → sync_tools() runs
Step 3: set_book_status(B002, "overdue")          → sync_tools() runs
```

If your `sync_tools()` resets fines based on the DB state, step 2's change might get overwritten by step 3's sync. **Design sync_tools() to only project state, never modify agent-side state.** And design init steps to be order-independent where possible.

### Base Init Must Normalize Before Faults

The base_init_calls must bring the entity to a "healthy" state before fault layers inject problems. Otherwise, a patron who starts with fines in the DB will have fines even in tasks where fines aren't a fault layer. Example:

```python
_BASE_INIT = [
    # Normalize everything to healthy
    InitCall("assistant", "set_membership", {"status": "active"}),
    InitCall("assistant", "set_fines", {"amount": 0.0}),
    InitCall("assistant", "set_book_status", {"status": "checked_out"}),
    # Then set user identity
    InitCall("user", "set_user_info", {"name": "{name}", "patron_id": "{patron_id}"}),
]
```

Then fault layers add on top:
```python
_fines_layer = FaultLayer(
    ...,
    init_calls=[InitCall("assistant", "set_fines", {"amount": 8.0})],  # override the 0.0
)
```

### Entity Dict Must Contain All Fields Any Layer Needs

Every FaultLayer's `{field}` templates resolve against the same entity dict. If `_second_overdue_layer` uses `{second_book_id}` but an entity only has 1 book, template resolution will crash. Use predicates to skip inapplicable entities:

```python
_second_overdue_layer = FaultLayer(
    ...
    predicate_field="has_second_book",  # entity["has_second_book"] must be truthy
)
```

### User Identity Must Be Set in Init

The user simulator needs to know who they are. Always include a `set_user_info` call in `base_init_calls`:

```python
InitCall("user", "set_user_info", {"name": "{patron_name}", "patron_id": "{patron_id}"})
```

### VARIANT Difficulty Design

Both VARIANT:a and VARIANT:b get the same `known_info`. Difficulty comes solely from the persona's communication style (cooperative vs anxious/confused), matching the telecom domain's PERSONA pattern.

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

Tasks are generated in entity order (P001 first, then P002, etc.). If someone runs `--num-tasks 5`, they'll get 5 tasks for the same patron. Shuffle before saving:

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
- [ ] Entities with different attributes (1 book vs 2 books, active vs expired)
- [ ] Each entity appears in multiple task combinations

### Variant Coverage
- [ ] VARIANT:a: User has cooperative/friendly persona
- [ ] VARIANT:b: User has anxious/confused persona (same known_info as VARIANT:a)

### Evaluation Dimension Coverage
- [ ] ACTION: Every task has expected actions
- [ ] ENV_ASSERTION: Most tasks have state assertions (both agent-side and user-side)
- [ ] COMMUNICATE: Do not use (brittle substring matching). Use NL_ASSERTION for behavioral checks.

### Policy Coverage
- [ ] Tasks that test identity verification
- [ ] Tasks that test policy restrictions (can't do X when Y)
- [ ] Tasks with unfixable layers that require transfer_to_human
- [ ] Tasks that require multi-step troubleshooting

### Task Count Guidelines

| Domain Size | Specs | × Variants | Total Tasks |
|-------------|-------|------------|-------------|
| Minimal | 20-40 | ×2 | 40-80 |
| Medium | 50-120 | ×2 | 100-240 |
| Large | 150+ | ×2 | 300+ |

"Specs" = unique fault-entity combinations. "Variants" doubles it (easy/hard).

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

### Task Generation
- [ ] `create_tasks(verify=True)` passes with 0 errors
- [ ] Task count matches expected (entity count × combo count × 2 variants)
- [ ] Tasks are deterministic (same seed → same output)
- [ ] Tasks have valid structure (id, ticket, evaluation_criteria)
- [ ] All tasks have at least 1 action
- [ ] communicate_info is NOT set (use assertions instead)
- [ ] VARIANT:b tasks use hard persona but same known_info as VARIANT:a
- [ ] transfer_to_human actions use compare_args=[]

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
- [ ] Failures are model failures, not structural failures
- [ ] Both VARIANT:a and VARIANT:b tasks appear in the sample

---

## 10. Common Mistakes

### Mistake: Assertion helper on wrong toolkit
```python
# WRONG: user assertion on agent toolkit
AssertionSpec(func_name="assert_fines_equal", args=..., env_type="assistant")
# RIGHT: user assertion on user toolkit
AssertionSpec(func_name="assert_fines_equal", args=..., env_type="user")
```

### Mistake: Forgetting to normalize in base_init
```python
# WRONG: Patron P005 starts with expired membership in db.json
# If your base_init doesn't normalize it, even tasks without the
# "expired" fault will have an expired membership
```

### Mistake: Entity dict missing fields for conditional layers
```python
# WRONG: second_overdue_layer uses e["second_book_id"] but
# entity for P001 only has 1 book
# RIGHT: add predicate_field="has_second_book"  (truthy check)
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
Always run: tau2 run --domain {domain} --num-tasks 10 --agent-llm gpt-4o-mini
Then analyze: are failures structural or model failures?
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

