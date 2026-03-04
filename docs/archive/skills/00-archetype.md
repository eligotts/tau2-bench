# Step 0.5: Domain Archetype Classification

Before writing any domain files, classify the domain concept into an **archetype**. The archetype determines which patterns to use for tools, policies, fault layers, and user interactions. Different archetypes test fundamentally different agent capabilities.

## The Four Archetypes

### Archetype A: Sequential Diagnostic (auto_repair-style)

**Core pattern:** The agent discovers problems progressively through gated tool access. Fixing upstream faults unlocks visibility into downstream faults.

**Agent learns:** Sequential prerequisite reasoning, error-as-information parsing, progressive tool access, multi-protocol user coordination.

**Characteristics:**
- READ tools have state-dependent output (information hiding) — upstream faults mask downstream details. READ tools MUST filter output based on upstream state. Never return `model_dump()` — explicitly select which fields to expose.
- Policy describes an iterative diagnostic workflow ("fix X before you can see Y")
- Difficulty scales with gate chain depth + parallel faults at each tier
- User actions are confirmations/acknowledgments (agent-driven)
- **Information necessity mechanism: Gated visibility** — READ tools block until upstream is fixed. The agent literally CANNOT SEE downstream issues until the gate is cleared.

**When to use:** The domain has natural dependency hierarchies — account access gates record access, registration gates service access, diagnostics reveal hidden state.

**Examples:** Auto repair, IT infrastructure management, insurance claims processing.

**Reference:** `src/tau2/domains/auto_repair/` — all files.

**Key metrics:** 8-10 fault groups, 2 atoms/layer (agent fix + user confirm), 2-3 gate_tier levels with per-tier diagnostics, 4+ distinct user WRITE tools, median ≥8 actions/task.

---

### Archetype B: Branching Troubleshooter (telecom-style)

**Core pattern:** The agent follows branching diagnostic decision trees, acting through the user who performs physical/device-side actions. The agent cannot directly observe or modify the problem — it must instruct the user to run diagnostics and apply fixes.

**Agent learns:** Hypothesis-driven diagnosis, indirect observation through proxy, clear instruction giving, layered fault discovery through testing, protocol adherence under user frustration.

**Characteristics:**
- READ tools are backend-transparent but physically-opaque. Agent diagnostic tools MUST NOT reveal physical/user-observable state. Use the observability boundary pattern: server sees "unreachable" but not whether the cause is a cable, router crash, or power issue.
- User has many WRITE tools (toggles, resets, reboots, tests) — the user is the instrument
- Policy describes branching decision trees ("if X, check Y; if Y is fine, check Z")
- Difficulty scales with tree depth + number of simultaneous faults across branches
- Agent must interpret user-reported tool outputs to decide next steps
- **Information necessity mechanism: Observability boundary** — agent sees the backend, user sees the physical world. Neither alone has enough information to complete the task.

**When to use:** The domain involves physical systems the agent can't directly control — devices, appliances, equipment. The user must perform actions on their end while the agent guides the process.

**Examples:** Telecom tech support, smart home troubleshooting, medical device support, network diagnostics.

**Reference snippets below + `src/tau2/domains/auto_repair/` for structural patterns (adapt the tool/policy architecture).

**Key metrics:** 7-9 fault groups, 1-3 atoms/layer (diagnostic + user fix + optional confirm), 8+ user WRITE tools + 3+ diagnostic READ, branching policy structure, 2-3 gate_tier levels with per-tier diagnostics, median ≥6 actions/task (≥8 achievable with per-tier diagnostics).

---

### Archetype C: Transaction Processor (banking-style)

**Core pattern:** The agent sees all relevant information upfront (transparent READ tools) and must execute a correct sequence of operations following strict protocols. Difficulty comes from protocol complexity, numeric computation, and knowing what NOT to do.

**Agent learns:** Protocol adherence, numeric computation, precondition verification, multi-step transaction sequencing, denial/refusal when policy prohibits action.

**Characteristics:**
- READ tools return full entity state (no information hiding)
- Policy is prescriptive — describes mandatory steps for each transaction type
- WRITE tools have strict preconditions (check status before modifying). WRITE tool preconditions create computed dependencies — the correct input value must come from a prior READ tool's output, not from the task template.
- Some faults require the agent to DENY a request per policy, not fix it
- Difficulty scales with protocol complexity + number of concurrent transactions
- User role is minimal — mostly providing information and confirming
- **Information necessity mechanism: Computed dependency** — correct value at step N requires output from step N-1. The agent CANNOT compute the correct amount without reading the invoice.

**When to use:** The domain involves structured business processes with clear rules — financial transactions, order management, benefits administration. The challenge is executing the right steps in the right order with the right values.

**Examples:** Banking operations, insurance underwriting, HR benefits enrollment, order fulfillment.

**Reference snippets below + `src/tau2/domains/auto_repair/` for structural patterns.

**Key metrics:** 7-9 fault groups, 1-2 atoms/layer, prescriptive policy with guards, WRITE tools with overwrite guards, numeric assertions, 3+ distinct user WRITE tools, median ≥6 actions/task.

---

### Archetype D: Triage / Classification (helpdesk-style)

**Core pattern:** The agent must gather information from the user, classify the situation, and route to the correct resolution — which may not involve fixing anything. Some tasks test whether the agent correctly denies requests, escalates, or provides information rather than taking action.

**Agent learns:** Information gathering, classification under ambiguity, policy-based denial, correct routing/escalation, distinguishing similar-but-different situations.

**Characteristics:**
- Mix of transparent and partially-hidden READ tools. Classification requires evidence from multiple READ sources — no single tool should provide enough info for correct routing.
- Policy describes classification criteria and routing rules
- Some faults are "non-fix" — correct behavior is to deny, inform, or escalate
- User provides information progressively through conversation (not through tools)
- Difficulty scales with classification ambiguity + number of similar-seeming categories
- Fewer user tools (mostly acknowledgment/confirmation)
- **Information necessity mechanism: Evidence threshold** — classification requires combining multiple partial sources. Any single source is insufficient for correct routing.

**When to use:** The domain involves judgment calls, categorization, or situations where the correct action depends on subtle policy distinctions. Not everything the user asks for should be granted.

**Examples:** IT helpdesk triage, medical intake, compliance review, permit applications.

**Reference snippets below + `src/tau2/domains/auto_repair/` for structural patterns.

**Key metrics:** 6-8 fault groups, 1-2 atoms/layer, mix of fixable and denial/escalation faults, lenient assertions (check "not default" rather than exact values), 3+ distinct user WRITE tools, median ≥5 actions/task.

---

## Difficulty Floor Requirements (All Archetypes)

A domain can satisfy every structural requirement and still be trivially easy. The following six **Difficulty Invariants (DI-1 through DI-6)** close that gap by requiring compound difficulty mechanisms. Every generated domain must satisfy these.

### DI-1: Diagnostic Disambiguation

**What it prevents:** 1:1 fault→tool mapping where the agent never reasons about *which* fix to apply.

- **Anti-pattern:** Each fault has its own dedicated fix tool with an obvious name. The agent just pattern-matches fault→tool.
- **Required:** At least 2 faults must share a fix tool with different computed args, OR the domain must have diagnostic/information-hiding READ tools that require investigation before fixing.

### DI-2: Value Computation

**What it prevents:** All fix tool arguments are direct pass-throughs from the ticket/complaint — the agent never computes anything.

- **Anti-pattern:** The user says "my balance is wrong, it should be $50" and the agent calls `set_balance(amount=50)`. Zero reasoning.
- **Required:** At least one fault group must require the agent to compute, derive, or look up a value that is NOT directly stated in the ticket (e.g., calculate a refund from transaction history, derive a date from policy rules, determine a category from symptoms).

### DI-3: Ordering Dependency

**What it prevents:** All faults are independent — any order works, no re-querying needed.

- **Anti-pattern:** The agent can fix all faults in any order with a single pass through the tool list.
- **Required:** At least one ordering constraint: a gate chain (A must be fixed before B is visible), a strict fix ordering (policy says do X before Y), or a user action that must precede an agent action.

### DI-4: Multi-Property Assertions

**What it prevents:** Single assertion per fault — too easy to pass by calling any relevant tool.

- **Anti-pattern:** Each fault has exactly one assertion checking one field. The agent can pass by calling the right tool with any args.
- **Required:** ≥40% of fixable layers must have 2+ assertions (or composite assertions that check multiple conditions).

### DI-5: Active User Participation

**What it prevents:** 1-2 generic confirmation tools reused across all faults.

- **Anti-pattern:** Every fault ends with the user calling `confirm_resolution()`. Zero user-side diversity.
- **Required:** Multiple distinct user WRITE tools mapped to different fault domains (see per-archetype minimums below).

### DI-6: Effective Action Density

**What it prevents:** Median task has too few actions (too few reasoning steps).

- **Anti-pattern:** Most tasks have 3-4 actions. The agent barely needs to think.
- **Required:** Median task must meet the per-archetype action floor (see table below).

### Per-Archetype Difficulty Minimums

| Invariant | A (Sequential Diagnostic) | B (Branching Troubleshooter) | C (Transaction Processor) | D (Triage / Classification) |
|-----------|--------------------------|------------------------------|---------------------------|----------------------------|
| **DI-1** | 1+ info-hiding READ + 1+ diagnostic tool | Policy decision tree with 3+ branches | 2+ faults share a fix tool with different computed args | 3+ classification categories needing info gathering |
| **DI-2** | Diagnostic returns computed values agent must interpret | User diagnostic returns data agent interprets | Agent computes amounts/dates/thresholds | Agent determines category from ambiguous symptoms |
| **DI-3** | 2-3 gate chain levels | 1+ strict fix ordering (A then B) | 1+ user action precondition gate | Classification precedes routing |
| **DI-4** | 60%+ layers with 2+ assertions | 50%+ | 50%+ | 40%+ |
| **DI-5** | 4+ distinct user WRITE | 8+ user WRITE + 3+ diagnostic READ | 3+ distinct WRITE, 1+ precondition gate | 3+ distinct WRITE |
| **DI-6** | Median ≥8 actions | Median ≥6 | Median ≥6 | Median ≥5 |
| **Fault groups** | 8-10 | 7-9 | 7-9 | 6-8 |

---

## How to Classify Your Domain

Ask these questions about the domain concept:

1. **Does the domain have natural dependency hierarchies?** (account → records → details)
   - Yes → Lean toward **Archetype A** (Sequential Diagnostic)

2. **Does the user need to perform physical/device-side actions?** (toggle, reboot, test)
   - Yes → Lean toward **Archetype B** (Branching Troubleshooter)

3. **Is the domain primarily about executing structured transactions correctly?** (payments, enrollments, orders)
   - Yes → Lean toward **Archetype C** (Transaction Processor)

4. **Does the domain involve classification, routing, or judgment calls?** (triage, approvals, categorization)
   - Yes → Lean toward **Archetype D** (Triage / Classification)

Most domains are a blend. Pick the PRIMARY archetype and note secondary influences. For example, "hotel front desk" is primarily **C** (transaction processor — check-in, billing, room changes) with **A** influences (room availability gates booking options).

## Save Your Classification

Add the archetype to `domain_spec.json`:

```json
{
  "domain_name": "...",
  "archetype": "sequential_diagnostic | branching_troubleshooter | transaction_processor | triage_classification",
  "archetype_notes": "Brief explanation of why this archetype fits and any secondary influences.",
  ...
}
```

## Reference Snippets by Archetype

### Archetype B Snippet: Branching Troubleshooter (User-as-Instrument)

**tools.py — User diagnostic and fix tools dominate:**
```python
# Agent has backend READ tools (transparent — no information hiding):
@is_tool(ToolType.READ)
def get_customer_account(self, customer_id: str) -> Dict[str, Any]:
    """Look up customer account details."""
    customer = self._find_customer(customer_id)
    return customer.model_dump()  # Return everything — no gating

# User has many WRITE tools (the user IS the instrument):
# In user_tools.py:
@is_tool(ToolType.WRITE)
def toggle_airplane_mode(self) -> str:
    """Toggle airplane mode on/off."""
    self.db.airplane_mode = not self.db.airplane_mode
    self._simulate_network()  # cascading state change
    return f"Airplane mode is now {'ON' if self.db.airplane_mode else 'OFF'}."

@is_tool(ToolType.WRITE)
def reboot_device(self) -> str:
    """Reboot the device."""
    self._simulate_network()
    return "Device rebooted successfully."

@is_tool(ToolType.READ)
def check_network_status(self) -> Dict[str, Any]:
    """Check current network connection status."""
    return {
        "signal_strength": self.db.signal_strength,
        "network_type": self.db.network_type,
        "connected": self.db.is_connected,
    }
```

**policy.md — Branching decision tree structure:**
```markdown
## Troubleshooting: No Service

Follow this diagnostic path when the customer reports no service:

1. Ask the customer to use their check_network_status tool and report the results.
2. If airplane mode is on, instruct the customer to use their toggle_airplane_mode tool.
   Then ask them to check_network_status again.
3. If the SIM card is not detected, instruct the customer to reseat it using
   their reseat_sim_card tool, then reboot using reboot_device.
4. If the network shows "no signal" with SIM present, check for line suspension
   in the backend using get_line_details. If suspended due to overdue bill,
   follow the Bill Payment workflow.
5. If all device-side checks pass but service is still unavailable, transfer to
   a network specialist using transfer_to_human.
```

**scenarios.py — FaultLayers with user-side fix actions:**
```python
airplane_mode_on = FaultLayer(
    name="airplane_mode_on",
    known_info_fragment="My phone shows no service at all.",
    # completion_fragment = observable inverse of known_info_fragment.
    # "no service" → "status bar shows signal". Both reference the same
    # underlying state (network connectivity) that the assertion checks.
    completion_fragment="your status bar shows signal",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="user",  # NOTE: user-side init — sets device state
                func_name="set_airplane_mode",
                args={"enabled": True},
            ),
            fix=ActionSpec(
                tool_name="toggle_airplane_mode",  # User tool — user does the fix
                args={},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_airplane_mode_off",
                args={},
                env_type="user",
            ),
        ),
        # No second atom — the user fix IS the resolution
        # (1-atom layers are fine for user-as-instrument domains)
    ],
    resource_scope="device_mode:{line_id}",
)
```

**Key differences from Archetype A:**
- Init calls target `env_type="user"` (breaking user-side device state, not agent DB)
- Fix actions have `requestor="user"` (user performs the fix, not agent)
- Layers often have 1 atom (user fix only) — no separate agent fix needed
- Policy guides agent through diagnosis, but user executes all physical actions
- More user WRITE tools (5-15) than agent WRITE tools (3-5)

---

### Archetype C Snippet: Transaction Processor (Protocol-Driven)

**tools.py — Transparent READ, guarded WRITE:**
```python
# Transparent READ — agent sees everything upfront:
@is_tool(ToolType.READ)
def get_account_details(self, account_id: str) -> Dict[str, Any]:
    """Get full account details including balances and status."""
    account = self._find_account(account_id)
    return account.model_dump()  # All fields visible

@is_tool(ToolType.READ)
def get_transactions(self, account_id: str) -> List[Dict[str, Any]]:
    """Get all transactions for an account."""
    return [t.model_dump() for t in self.db.transactions
            if t.account_id == account_id]

# Guarded WRITE — precondition checks prevent overwrites:
@is_tool(ToolType.WRITE)
def process_refund(self, transaction_id: str, amount: float) -> str:
    """Process a refund for a transaction.

    Args:
        transaction_id: The transaction to refund.
        amount: The refund amount (must not exceed original amount).
    """
    txn = self._find_transaction(transaction_id)
    if txn.status == "refunded":
        return f"Transaction {transaction_id} already refunded. No changes made."
    if amount > txn.amount:
        return f"Refund amount ${amount:.2f} exceeds transaction amount ${txn.amount:.2f}."
    txn.refund_amount = amount
    txn.status = "refunded"
    account = self._find_account(txn.account_id)
    account.balance += amount
    return f"Refund of ${amount:.2f} processed for transaction {transaction_id}."
```

**policy.md — Prescriptive protocol with guards:**
```markdown
## Refund Processing Protocol

For every refund request, follow these steps in order:

1. Look up the transaction using get_transactions. Verify the transaction exists
   and has not already been refunded.
2. Confirm the refund amount with the customer. The refund cannot exceed the
   original transaction amount.
3. Process the refund using process_refund with the verified amount.
4. After processing, instruct the customer to use their confirm_refund tool
   to acknowledge the refund.

## Requests to Deny

Do NOT process refunds for:
- Transactions older than 90 days (check transaction_date)
- Transactions flagged as "disputed" (use transfer_to_human instead)
- Gift card purchases (inform customer these are non-refundable per policy)
```

**scenarios.py — Denial faults alongside fix faults:**
```python
# A denial fault — correct behavior is NOT to fix, but to deny:
# NOTE: unfixable layers do NOT need completion_fragment (the task ends
# when the agent transfers, not when a fault is "fixed").
expired_refund_request = FaultLayer(
    name="expired_refund_request",
    known_info_fragment=(
        "I want a refund for my purchase (transaction {transaction_id}) "
        "from {transaction_date}."
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_transaction_date",
                args={"transaction_id": "{transaction_id}",
                      "date": "2024-01-15"},  # > 90 days ago
            ),
            # The fix is to NOT refund — agent should inform customer
            # Use transfer_to_human or a deny action
            fix=ActionSpec(
                tool_name="transfer_to_human",
                args={"summary": "Customer requesting refund for expired transaction"},
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_transaction_not_refunded",
                args={"transaction_id": "{transaction_id}"},
                env_type="assistant",
                assert_value=True,  # Transaction should NOT be refunded
                message_template="Transaction {transaction_id} should remain un-refunded.",
            ),
        ),
    ],
    unfixable=True,  # Mark as unfixable — correct behavior is transfer
    resource_scope="refund:{transaction_id}",
)
```

**Key differences from Archetype A:**
- READ tools return full state (no information hiding)
- WRITE tools have overwrite guards (check status before modifying)
- Policy is prescriptive ("for every X, do Y") — but tools guard against overwrites
- Some faults test DENIAL — correct behavior is to refuse, not fix
- Numeric computation in assertions (amounts, dates, percentages)
- Fewer user tools (1-3), mostly confirmations

---

### Archetype D Snippet: Triage / Classification (Judgment-Based)

**tools.py — Mix of transparent and classification-oriented:**
```python
@is_tool(ToolType.READ)
def get_ticket_details(self, ticket_id: str) -> Dict[str, Any]:
    """Get full ticket details including symptoms and history."""
    ticket = self._find_ticket(ticket_id)
    return ticket.model_dump()

@is_tool(ToolType.READ)
def search_knowledge_base(self, keywords: str) -> List[Dict[str, Any]]:
    """Search the knowledge base for matching articles."""
    # Returns relevant articles — agent must interpret and choose
    results = []
    for article in self.db.kb_articles:
        if any(kw.lower() in article.content.lower()
               for kw in keywords.split()):
            results.append({"article_id": article.article_id,
                           "title": article.title,
                           "category": article.category})
    return results

# Classification action — agent assigns a category:
@is_tool(ToolType.WRITE)
def classify_ticket(self, ticket_id: str, category: str,
                    priority: str) -> str:
    """Classify a support ticket by category and priority.

    Args:
        ticket_id: The ticket to classify.
        category: One of: hardware, software, network, account, billing.
        priority: One of: low, medium, high, critical.
    """
    ticket = self._find_ticket(ticket_id)
    if ticket.category != "unclassified":
        return f"Ticket {ticket_id} already classified as {ticket.category}."
    ticket.category = category
    ticket.priority = priority
    return f"Ticket {ticket_id} classified as {category} ({priority} priority)."

# Routing action — agent assigns to team:
@is_tool(ToolType.WRITE)
def route_ticket(self, ticket_id: str, team: str) -> str:
    """Route a classified ticket to the appropriate team."""
    ticket = self._find_ticket(ticket_id)
    if ticket.category == "unclassified":
        return "Cannot route unclassified ticket. Classify first."
    ticket.assigned_team = team
    return f"Ticket {ticket_id} routed to {team} team."
```

**scenarios.py — Lenient assertions for judgment calls:**
```python
misclassified_ticket = FaultLayer(
    name="misclassified_ticket",
    known_info_fragment=(
        "I submitted a ticket about {symptom_description} but it was "
        "categorized incorrectly as {wrong_category}."
    ),
    # Archetype D: use lenient completion — "reassigned" not "assigned to team X"
    # Matches the lenient assertion pattern (assert_ticket_not_category checks
    # "not wrong" rather than "exactly right").
    completion_fragment="your ticket has been reclassified",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_ticket_category",
                args={"ticket_id": "{ticket_id}",
                      "category": "{wrong_category}"},
            ),
            fix=ActionSpec(
                tool_name="classify_ticket",
                args={"ticket_id": "{ticket_id}",
                      "category": "{correct_category}",
                      "priority": "{expected_priority}"},
                compare_args=["ticket_id"],  # Don't check exact category/priority
            ),
            # Lenient assertion — just check it's not the wrong category anymore
            check=AssertionSpec(
                func_name="assert_ticket_not_category",
                args={"ticket_id": "{ticket_id}",
                      "wrong_category": "{wrong_category}"},
                env_type="assistant",
                message_template="Ticket should not be {wrong_category}.",
            ),
        ),
    ],
    resource_scope="classification:{ticket_id}",
)
```

**Key differences from other archetypes:**
- Assertions are lenient — check "not wrong" rather than "exactly right"
- Agent must gather information through conversation, not just tool calls
- Some faults test whether agent correctly identifies the situation
- Fewer WRITE tools, more READ tools (information gathering > state mutation)
- `compare_args` uses selective matching (check ticket_id but not exact category)
- User provides information through conversation, not through user tools

---

## Archetype Selection Affects Every Step

| Step | Archetype A | Archetype B | Archetype C | Archetype D |
|------|------------|------------|------------|------------|
| **READ tools** | State-dependent (gated) | Transparent (backend) + user diagnostic tools | Transparent (full state) | Mix + knowledge base search |
| **WRITE tools** | Fix tools per fault | Few agent WRITE, many user WRITE | Guarded WRITE with preconditions | Classification + routing tools |
| **User tools** | 3-5 confirmation tools | 5-15 diagnostic + fix tools | 1-3 confirmation tools | 1-2 acknowledgment tools |
| **Policy style** | Iterative diagnostic workflow | Branching decision tree | Prescriptive protocol with guards | Classification criteria + routing rules |
| **Fault layers** | 2 atoms (agent fix + user confirm) | 1-2 atoms (often user-only fix) | 1-2 atoms (agent fix + optional confirm) | 1 atom (agent classify/route) |
| **Fault groups** | 8-10 (info-hiding tiers) | 7-9 (diagnostic branches) | 7-9 (transaction types) | 6-8 (classification categories) |
| **Difficulty source** | Gate chain depth | Tree depth + breadth | Protocol complexity + numerics | Ambiguity + similar categories |
| **Assertions** | Exact field match | Device state check | Numeric + exact match | Lenient (not-wrong) |

## completion_fragment by Archetype

Each archetype has a natural pattern for what "fixed" looks like to the user. The completion_fragment should match the archetype's assertion style:

| Archetype | Assertion Style | completion_fragment Pattern | Example |
|-----------|----------------|---------------------------|---------|
| **A: Sequential Diagnostic** | Exact field match | User READ tool shows correct state | `"your account shows no outstanding fines"` |
| **B: Branching Troubleshooter** | Device state check | User diagnostic tool returns expected result | `"your speed test shows excellent results"` |
| **C: Transaction Processor** | Numeric/exact match | Transaction state matches expected value | `"your order total shows {original_amount}"` |
| **D: Triage / Classification** | Lenient (not-wrong) | Existence check, not exact value | `"your ticket has been reassigned to a new team"` |

**Multi-fault composition:** When a task has 3 active layers, the user sees:

> You will consider your issues resolved when **your speed test shows excellent results** and **your status bar shows signal** and **your MMS sends successfully**.

Each fragment is a half-sentence — the framework joins with " and " and wraps in the frame sentence.

## Verification Loop by Archetype

The verification loop (composite verification tool + `tool_grounding_block` + `resolution_instruction`) gives the user sim concrete probing behavior and a clear stop signal. Not every archetype benefits equally:

| Archetype | Composite Verification Tool? | `tool_grounding_block` Pattern | `resolution_instruction` Pattern |
|-----------|------------------------------|-------------------------------|----------------------------------|
| **A: Sequential Diagnostic** | Yes — synced scalar fields map to overall health check | Verification loop | Tool-referencing (`"your check_my_status tool shows 'All clear'"`) |
| **B: Branching Troubleshooter** | Yes — tech_support reference implementation (`check_my_connection`) | Verification loop | Tool-referencing (`"your check_my_connection tool shows 'All systems working normally'"`) |
| **C: Transaction Processor** | Consider — if entity summaries have health indicators (order status, payment status) | Either pattern (verification loop if composite tool exists, grounding-only otherwise) | Tool-referencing or broad outcome (`"your order issues have been resolved"`) |
| **D: Triage / Classification** | Unlikely — user receives information, doesn't verify system state | Grounding-only or omit | Broad outcome (`"your ticket has been classified and routed"`) |

**When to build a composite tool:** If the domain has 3+ synced scalar fields on the user DB that each map to a "healthy" default, a composite tool that checks all of them is worth building. See `docs/skills/07-tools.md` for design guidance and `docs/skills/08-user-tools.md` for the annotated code pattern.

**`resolution_category` on FaultLayerGroup:** When using `resolution_instruction`, every group needs a `resolution_category` semantic tag (e.g. `"account"`, `"connection"`, `"billing"`). Multiple groups can share the same category. The `verify_resolution_instruction()` check validates that all categories are covered by the instruction text.

**Impact:** tech_support (Archetype B) went from 44% to 65% success after adopting the full verification loop. The pattern is strictly superior to grounding-only when a composite tool exists.

## Archetype Primitives: `phase`, `step_type`, and `gate_tier`

Three primitives on `FaultAtom` and `FaultLayer` give authors explicit control over action ordering and atom semantics, enabling all four archetypes from the same engine.

### `FaultAtom.phase: int = 0`

Execution order **within a layer**. Lower phases run first. Within the same phase, requestor is a tiebreaker (user=0, agent=1). Phase gives authors explicit control over interleaving — authors who want agent-then-user-then-agent set phases 0, 1, 2.

### `FaultAtom.step_type: str = "fix"`

Declares the atom's role in the resolution sequence:
- **`"fix"`** — state-changing WRITE action (default, current behavior)
- **`"diagnostic"`** — information-gathering READ action. Part of the golden path but doesn't change DB state. Verification skips the no-op check.
- **`"confirm"`** — user acknowledgment action.

### `FaultLayer.gate_tier: int = 0`

Execution order **across composed layers**. All tier-0 actions complete before tier-1 actions begin. Creates the Archetype A pattern: upstream faults gate downstream visibility.

### Action ordering: `(gate_tier, phase, requestor_priority)` — Stable Sort

The engine sorts all actions by `(gate_tier, phase, requestor_priority)` where requestor_priority is 0 for user and 1 for agent. Base actions are placed at synthetic final tiers.

### Archetype A Example: Sequential Diagnostic with `gate_tier`

```python
# Tier 0: fix account lock (must happen first)
account_locked = FaultLayer(
    name="account_locked", gate_tier=0,
    atoms=[FaultAtom(
        init=InitCall("assistant", "set_account_status", {"status": "locked"}),
        fix=ActionSpec("unlock_account", {"account_id": "{account_id}"}),
        check=AssertionSpec("assert_account_unlocked", {"account_id": "{account_id}"}),
    )],
    known_info_fragment="I can't access my account",
    completion_fragment="your account is accessible again",
    resource_scope="account:{account_id}",
)

# Tier 1: fix booking error (only visible after account unlocked)
wrong_departure = FaultLayer(
    name="wrong_departure", gate_tier=1,
    atoms=[
        FaultAtom(  # diagnostic: agent must look up the booking to see what's wrong
            fix=ActionSpec("get_booking_details", {"booking_id": "{booking_id}"}),
            step_type="diagnostic", phase=0),
        FaultAtom(  # fix: agent corrects the departure
            init=InitCall("assistant", "set_departure", {"city": "wrong_city"}),
            fix=ActionSpec("update_departure", {"booking_id": "{booking_id}", "city": "{correct_city}"}),
            check=AssertionSpec("assert_departure_correct", {"booking_id": "{booking_id}"}),
            phase=1),
    ],
    known_info_fragment="Something seems off with my booking",
    completion_fragment="your booking shows the correct departure city",
    resource_scope="booking:{booking_id}",
)
```

### Archetype B Example: Branching Troubleshooter with `phase`

```python
airplane_mode_stuck = FaultLayer(
    name="airplane_mode_stuck",
    atoms=[
        FaultAtom(  # user diagnoses
            fix=ActionSpec("check_network_status", requestor="user", compare_args=[]),
            step_type="diagnostic", phase=0),
        FaultAtom(  # user fixes
            init=InitCall("user", "set_airplane_mode", {"enabled": True}),
            fix=ActionSpec("toggle_airplane_mode", requestor="user", compare_args=[]),
            check=AssertionSpec("assert_airplane_mode_off", env_type="user"),
            step_type="fix", phase=1),
        FaultAtom(  # user verifies
            fix=ActionSpec("check_network_status", requestor="user", compare_args=[]),
            step_type="diagnostic", phase=2),
    ],
    known_info_fragment="My phone has no service",
    completion_fragment="your status bar shows signal",
    resource_scope="device_mode:{line_id}",
)
```

### Archetype D Example: Triage/Classification with `phase`

```python
misclassified_ticket = FaultLayer(
    name="misclassified_ticket",
    atoms=[
        FaultAtom(  # agent classifies
            init=InitCall("assistant", "set_category", {"category": "{wrong_category}"}),
            fix=ActionSpec("classify_ticket", {"ticket_id": "{ticket_id}",
                          "category": "{correct_category}"},
                          compare_args=["ticket_id"]),
            check=AssertionSpec("assert_not_category", {"wrong_category": "{wrong_category}"}),
            phase=0),
        FaultAtom(  # agent routes
            fix=ActionSpec("route_ticket", {"ticket_id": "{ticket_id}", "team": "{team}"},
                          compare_args=["ticket_id"]),
            check=AssertionSpec("assert_ticket_routed", {"ticket_id": "{ticket_id}"}),
            phase=1),
    ],
    known_info_fragment="My ticket was miscategorized as {wrong_category}",
    completion_fragment="your ticket has been reclassified and routed",
    resource_scope="classification:{ticket_id}",
)
```

### Primitive Selection Guide

| Want to... | Use |
|---|---|
| Force upstream fix before downstream fix across layers | `gate_tier` on FaultLayer |
| Order steps within a single layer (diagnose → fix → verify) | `phase` on FaultAtom |
| Mark a READ action as part of the golden path | `step_type="diagnostic"` |
| Mark a user acknowledgment action | `step_type="confirm"` |
| Interleave agent and user actions | Different `phase` values |
| Override the default user-before-agent ordering | Agent at phase 0, user at phase 1 |

### Per-Tier Diagnostic Atoms (Required for Archetypes A and B)

For domains with 5+ fault groups, add a **per-tier agent diagnostic atom** to every fixable layer at each tier. This is **required** to achieve action density targets (DI-6) and dependency chain depth (DI-3). Without per-tier diagnostics, domains produce flat task structures where the agent barely reasons before acting.

**Pattern:** Each tier has a signature diagnostic READ tool. Every layer at that tier gets the same diagnostic atom at phase 0, with existing atoms shifting up by 1 phase. Cross-layer same-tier dedup collapses multiple copies to one call per task.

**3-tier example (tech_support / Archetype B):**

```
Tier 0: Account    →  Tier 1: Device/Hardware  →  Tier 2: Service/Network
(lookup_customer)     (run_remote_diagnostic)     (get_service_plan, check_area_outages)
```

```python
# Every tier-1 layer gets this as phase 0:
FaultAtom(
    phase=0, step_type="diagnostic",
    fix=ActionSpec("run_remote_diagnostic",
                   args={"device_id": "{device_id}"},
                   compare_args=["device_id"]),
)
# Existing atoms shift to phase 1, 2, ...
```

**Impact:** tech_support went from mean 5.74 actions (agent 2.34) to mean 8.58 actions (agent 5.13) — nearly doubling agent reasoning steps — by adding one diagnostic atom per tier to each layer.

**Key properties:**
- Diagnostic atoms have `step_type="diagnostic"` → no init, no state mutation
- Same-tier dedup: if 3 tier-1 layers all have `run_remote_diagnostic`, it appears once in the golden path
- The diagnostic output feeds into the fix: agent must interpret results to determine correct action
- Satisfies DI-2 (value computation) when diagnostic returns data agent must extract and use
- **Must be applied uniformly:** ALL fixable layers at a tier must have the same diagnostic atom. The `_check_per_tier_diagnostic_consistency` verification catches incomplete coverage.

**Requirements for Archetypes A and B:**
- Use ≥3 gate_tier levels (e.g., 0=account, 1=device, 2=service)
- Each tier has exactly one signature diagnostic READ tool
- Every fixable layer at that tier gets the diagnostic as phase 0
- Verification checks `_check_min_gate_tier_depth` and `_check_per_tier_diagnostic_consistency` enforce this

## Validation

No automated validation for this step — the archetype is recorded in the domain_spec.json for use by subsequent steps.
