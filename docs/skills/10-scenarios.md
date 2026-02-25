# Step 10: Scenarios (scenarios.py)

Generate the task generation module — this is the MOST COMPLEX file. It defines fault layers, entity construction, and the `create_tasks()` entry point using the Recipe Engine.

## Reference

- Read `docs/domain-authoring-guide.md` lines 583-713 (Scenarios), 714-1123 (Recipe Engine), 1172-1257 (Gotchas), and 1355-1475 (Common Mistakes)
- Read `src/tau2/domains/auto_repair/scenarios.py` for the Recipe Engine structure (Personas, UserTemplate, _build_entities, FaultLayer/FaultAtom, FaultLayerConfig, RecipeBook, create_tasks)
- Read `docs/skills/00-archetype.md` for your archetype-specific fault layer patterns and snippets

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json` — including `archetype`
- Read `src/tau2/domains/<domain_name>/data_model.py`
- Read `src/tau2/domains/<domain_name>/tools.py` (IMPORTANT — use exact method names)
- Read `src/tau2/domains/<domain_name>/user_tools.py`
- Read `data/tau2/domains/<domain_name>/db.json` (know the entity structure)

## Output

Write to `src/tau2/domains/<domain_name>/scenarios.py`.

## Imports

```python
from pathlib import Path
from typing import Any, Callable, Optional

from tau2.domains.<domain_name>.data_model import <DomainClass>DB
from tau2.domains.<domain_name>.environment import get_environment
from tau2.domains.<domain_name>.utils import (
    <UPPER>_DB_PATH,
    <UPPER>_POLICY_PATH,
    <UPPER>_TASK_SET_PATH,
)
from tau2.generators.recipe import (
    ActionSpec,
    AssertionSpec,
    FaultAtom,
    FaultLayer,
    FaultLayerConfig,
    FaultLayerGroup,
    InitCall,
    RecipeBook,
    generate_recipe_tasks,
    verify_completion_fragments,
    verify_fault_atoms,
)
from tau2.generators.types import Persona, UserTemplate
from tau2.generators.verify import verify_tasks
from tau2.generators.verify_authoring import (
    collect_authored_files,
    verify_authoring,
    verify_authoring_with_llm,
)
from tau2.utils import dump_file
```

**CRITICAL:** Import path constants from `tau2.domains.<domain_name>.utils`. Do NOT define your own paths with `Path(__file__)` — db.json and other data files live in `data/tau2/domains/`, not in the source directory.

## Structure

### 1. Personas

Define 2-4 personas with different interaction styles. Every task spec produces one task per persona:

```python
PERSONAS = [
    Persona(name="friendly_customer", description="You are a friendly..."),
    Persona(name="frustrated_customer", description="You are frustrated..."),
]
```

### 2. User Template

Define the template that generates user instructions per task:

```python
USER_TEMPLATE = UserTemplate(
    domain="<domain_name>",
    reason_for_call="You are contacting <service> because...",
    known_info="You are {customer_name} (ID: {customer_id}). {fault_descriptions}",
    task_instructions=(
        "Follow the agent's instructions throughout the conversation. "
        "When the agent asks you to perform an action or use one of your tools, do so. "
        "You must actually call the tool — describing the action in words is not sufficient. "
        "You will consider your issues resolved when the agent confirms all problems have been addressed."
    ),
    ticket="Customer {customer_name} (ID: {customer_id}): {fault_descriptions}",
    purpose="Test resolution of <domain> support issues...",
)
```

**CRITICAL: task_instructions must be agent-driven, not prescriptive.**

The user sim should be a pure follower — it does what the agent tells it, nothing more. This ensures the agent (the model being tested) must learn to guide the user through every step.

- **WRONG:** "After the agent resolves an issue, use your acknowledge_resolution tool." (bakes in which tool to call — user sim doesn't need the agent)
- **RIGHT:** "Follow the agent's instructions. When the agent asks you to use one of your tools, do so." (agent must explicitly guide the user)

The agent learns about user tools from the **policy** (step 6), not from task_instructions. The policy says "instruct the customer to use their acknowledge_resolution tool" -> agent tells the user -> user sim follows.

### 3. Entity Construction

```python
def _build_entities(db: <DomainClass>DB) -> list[dict[str, Any]]:
    """Build entity dicts by joining primary entity + related records."""
```

- Returns a list of flat dicts, one per primary entity
- Each dict has prefixed keys for template formatting
- Include `has_<relation>` boolean flags for predicate filtering
- Include `original_<field>` copies for fields that init_calls will modify

### 4. Fault Layers by Archetype

The fault layer structure depends on the domain archetype. See `docs/skills/00-archetype.md` for annotated snippets.

**Archetype A (Sequential Diagnostic) — 2 atoms per layer:**

```python
some_fault = FaultLayer(
    name="some_fault",
    known_info_fragment="Description of complaint using {template_vars}...",
    completion_fragment="your account shows no outstanding issues for {entity_name}",
    atoms=[
        # Atom 1: Agent-side fix
        FaultAtom(
            init=InitCall(env_type="assistant", func_name="set_<field>",
                         args={"entity_id": "{entity_id}", "value": "broken_value"}),
            fix=ActionSpec(tool_name="fix_tool", args={"entity_id": "{entity_id}"},
                          compare_args=["entity_id"]),
            check=AssertionSpec(func_name="assert_<field>",
                              args={"entity_id": "{entity_id}", "expected": "{original_value}"},
                              env_type="assistant"),
        ),
        # Atom 2: User-side confirmation
        FaultAtom(
            fix=ActionSpec(tool_name="acknowledge_resolution",
                          args={"customer_id": "{customer_id}"},
                          requestor="user", compare_args=[]),
            check=AssertionSpec(func_name="assert_resolution_acknowledged",
                              args={"customer_id": "{customer_id}"},
                              env_type="user"),
        ),
    ],
    resource_scope="<resource_type>:{entity_id}",
)
```

**Archetype B (Branching Troubleshooter) — 1-2 atoms, user-side fixes:**

```python
airplane_mode_fault = FaultLayer(
    name="airplane_mode_on",
    known_info_fragment="My phone shows no service at all.",
    completion_fragment="your status bar shows signal",
    atoms=[
        FaultAtom(
            init=InitCall(env_type="user", func_name="set_airplane_mode",
                         args={"enabled": True}),
            fix=ActionSpec(tool_name="toggle_airplane_mode", args={},
                          requestor="user", compare_args=[]),
            check=AssertionSpec(func_name="assert_airplane_mode_off",
                              args={}, env_type="user"),
        ),
        # No second atom needed — user fix IS the resolution
    ],
    resource_scope="device_mode:{line_id}",
)
```

**Archetype C (Transaction Processor) — 1-2 atoms, guarded fixes:**

```python
wrong_amount = FaultLayer(
    name="wrong_charge_amount",
    known_info_fragment="I was charged {charged_amount} but it should be {original_amount}.",
    completion_fragment="your order total shows {original_amount}",
    atoms=[
        FaultAtom(
            init=InitCall(env_type="assistant", func_name="set_charge_amount",
                         args={"transaction_id": "{transaction_id}", "amount": 999.99}),
            fix=ActionSpec(tool_name="adjust_charge",
                          args={"transaction_id": "{transaction_id}",
                                "amount": "{original_amount}"},
                          compare_args=["transaction_id"]),
            check=AssertionSpec(func_name="assert_charge_amount",
                              args={"transaction_id": "{transaction_id}",
                                    "expected": "{original_amount}"},
                              env_type="assistant"),
        ),
    ],
    resource_scope="charge:{transaction_id}",
)
```

**Archetype D (Triage / Classification) — 1 atom, lenient assertions:**

```python
misrouted_ticket = FaultLayer(
    name="misrouted_ticket",
    known_info_fragment="My {symptom_description} ticket was sent to the wrong team.",
    completion_fragment="your ticket has been reassigned to a new team",
    atoms=[
        FaultAtom(
            init=InitCall(env_type="assistant", func_name="set_ticket_team",
                         args={"ticket_id": "{ticket_id}", "team": "{wrong_team}"}),
            fix=ActionSpec(tool_name="route_ticket",
                          args={"ticket_id": "{ticket_id}", "team": "{correct_team}"},
                          compare_args=["ticket_id"]),
            check=AssertionSpec(func_name="assert_ticket_not_team",
                              args={"ticket_id": "{ticket_id}",
                                    "wrong_team": "{wrong_team}"},
                              env_type="assistant"),
        ),
    ],
    resource_scope="routing:{ticket_id}",
)
```

### 5. Fault Layer Groups

```python
some_group = FaultLayerGroup(
    name="some_issues",
    layers=[fault_variant_1, fault_variant_2],  # Mutually exclusive within group
)
```

### 6. FaultLayerConfig

```python
FIXABLE_CONFIG = FaultLayerConfig(
    name="<domain_name>",
    entity_query=lambda db: _build_entities(db),
    groups=[group1, group2, ...],
    base_init_calls=[
        InitCall(env_type="user", func_name="set_user_info",
                 args={"name": "{customer_name}", "customer_id": "{customer_id}"}),
    ],
    base_known_info_template="You are {customer_name}. {fault_descriptions}",
    base_ticket_template="Customer {customer_name} (ID: {customer_id}): {fault_descriptions}",
    reason_for_call="You are contacting...",
    purpose="Test resolution of...",
    entity_id_field="customer_id",
    min_faults=1,
    max_faults=9,  # Match to your number of groups
    max_total_tasks=1200,  # Proportional sampling
    tool_grounding_block=(
        "Whenever the agent asks you about your account or status, "
        "always ground your responses on the results of tool calls. "
        "Never make up the results of tool calls, always ground your "
        "responses on the results of tool calls. If you are unsure about "
        "whether an action is necessary, always ask the agent for "
        "clarification."
    ),
)
```

**`tool_grounding_block`** — A domain-level constant appended to every task's user_task_instructions. Tells the user sim to ground responses on actual tool call results. This is the same for every task in the config — write it once. If the domain has no user READ/diagnostic tools, leave it empty.

### 7. Unfixable Config (separate)

If you have unfixable faults, create a SECOND FaultLayerConfig:

```python
TRANSFER_CONFIG = FaultLayerConfig(
    name="<domain_name>_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[FaultLayerGroup(name="unfixable", layers=[unfixable_layer_1, ...])],
    max_faults=1,
    max_total_tasks=16,
    ...
)
```

Unfixable layers use: `unfixable=True`, `atoms=[]`, `init_calls=[...]`.

### 8. RecipeBook

```python
RECIPE_BOOK = RecipeBook(
    fault_layer_configs=[FIXABLE_CONFIG],  # Add TRANSFER_CONFIG if applicable
)
```

### 9. create_tasks()

Follow the auto_repair example's `create_tasks()` function structure — it handles verification, atom verification, and optional saving.

## Critical Rules

### Template Variables
- All `{field}` references must match keys from `_build_entities()` entity dicts exactly
- Pure `{field}` references preserve the entity's type (int, str, etc.)

### Method Names
- `InitCall.func_name` must match the EXACT method name in tools.py or user_tools.py
- `ActionSpec.tool_name` must match an `@is_tool`-decorated method
- `AssertionSpec.func_name` must match an `assert_*` method (no decorator)

### Chain Verification
For every FaultLayer, trace: init breaks field X -> fix modifies field X -> assertion checks field X.

### Difficulty Calibration by Archetype

| Archetype | Atoms/Layer | Groups | Median Actions/Task |
|-----------|------------|--------|---------------------|
| A: Sequential Diagnostic | 2 | 8-10 | ≥8 |
| B: Branching Troubleshooter | 1-2 | 7-9 | ≥6 |
| C: Transaction Processor | 2 | 7-9 | ≥6 |
| D: Triage / Classification | 1-2 | 6-8 | ≥5 |

Single-atom layers are valid when the user action IS the resolution (Archetype B) or when the agent action is self-contained (Archetype C, D). The key requirement: **task success must depend on the agent doing the right thing.**

### User Action Feasibility
- PREFER zero-arg user tools with `compare_args=[]`
- ONLY add user atoms when the policy EXPLICITLY says "instruct the user to X"
- NEVER add user atoms that duplicate what an agent atom already fixes

**WARNING — compare_args=[] + assertion blind spot:** When a user action has `compare_args=[]`, the ACTION evaluator passes regardless of what args the user sim provides (name-only match). But if the corresponding user-side ENV_ASSERTION checks a specific argument value (e.g. `payment_id="PAY001"`), the user sim must still provide that exact value — and it can only do so if the value appears in `known_info_fragment` or the agent's conversation. If the assertion checks an arg that the user can't discover, ACTION=1.0 but ENV_ASSERTION=0.0 — a silent split-brain failure.

**Rule:** For every user atom with `compare_args=[]`, check its paired assertion. If the assertion checks a specific arg value (not just a boolean flag), ensure that value appears in `known_info_fragment` via a template variable like `{payment_method_id}`. The `verify_user_assertion_arg_discoverability` check catches this at generation time.

### Resource Conflicts
- Layers in DIFFERENT groups get composed (cartesian product)
- If two layers target the same entity resource, their actions may contradict
- Use `resource_scope` on every layer for conflict detection
- Put conflicting layers in the same group (mutually exclusive) or use different resources

### Shared Fix Tools Across Groups
Before placing a layer in a group, check: **does any layer in a DIFFERENT group use the same agent fix tool?** If so, when both layers compose in the same task, both init on the same DB field and expect the same tool to fix it — the second fix becomes a no-op. Additionally, if the two layers expect different user confirmations, the policy cannot route the agent to the correct one.

**Rule:** Layers that share an agent fix tool OR modify the same DB field MUST be in the same group (mutually exclusive). The `_check_cross_layer_confirmation_consistency` static check catches the confirmation routing variant. The `resource_scope` conflict detection catches resource conflicts — but only if the scopes match. Use the SAME `resource_scope` prefix for layers that touch the same DB field, even if they have different semantic categories.

### known_info_fragment
- Must express clear user INTENT, not just state
- Write "I have fines that I'd like waived" NOT just "I have fines"
- Must DISAMBIGUATE which resource when entity has multiples
- Use template variables like `{second_appointment_date}` to identify specific resources

### completion_fragment (REQUIRED for fixable layers)

The **contractual link** between the user sim's stop condition and the task's actual success criteria. This is what tells the user sim when the problem is SOLVED — if it's wrong, the user sim stops at the wrong time and the task is broken.

**What it is:** A half-sentence describing what "fixed" looks like from the user's perspective. The framework wraps it: `"You will consider your issues resolved when <fragment>."` For multi-fault tasks, fragments are joined with " and ".

**The complement rule:** `completion_fragment` MUST be the observable inverse of `known_info_fragment`. They describe the same fault from opposite ends:

| Field | Perspective | Example |
|-------|------------|---------|
| `known_info_fragment` | What BROKEN looks like to user | "My internet is very slow" |
| `completion_fragment` | What FIXED looks like to user | "your speed test shows excellent results" |

**The faithfulness rule:** The completion_fragment MUST reference the same DB field / user tool that the assertion (`check`) verifies. This is what makes the stop condition inextricably tied to task correctness:

```
init:                set_speed("slow")           ← breaks db.speed
check (assertion):   assert_speed("excellent")   ← verifies db.speed
user tool:           run_speed_test()             ← reads db.speed
completion_fragment: "your speed test shows excellent results"  ← user observes db.speed
```

All four reference the same underlying state. If the assertion passes, the user tool will show the expected result, and the completion criterion will be met. They cannot diverge.

**Rules:**
- Write ONLY the half-sentence — do NOT include frame words like "You will consider your issues resolved when"
- MUST reference the same field/state that the assertion checks
- MUST be observable via the user's tools (not backend-only state)
- Use template variables for entity-specific values: `"your order total shows {original_amount}"`
- For Archetype D (lenient assertions): use existence checks, not exact values: `"your ticket has been reassigned"` not `"your ticket is assigned to team X"`

**GOOD examples:**
- `"your speed test shows excellent results"` (Archetype B — user tool output)
- `"your account shows no outstanding fines"` (Archetype A — user READ tool)
- `"your order total shows {original_amount}"` (Archetype C — template variable)
- `"your ticket has been reassigned to a new team"` (Archetype D — lenient)

**BAD examples:**
- `"You will consider your issue resolved when..."` (includes frame — framework adds this)
- `"your bill shows the correct amount"` (for a speed fault — WRONG FIELD)
- `"the agent has fixed the issue"` (not user-observable — references agent, not user tool)
- `""` (empty — ERROR: every fixable layer needs a completion_fragment)

### Shared Agent Tools Across Layers Must Have Consistent Confirmations
If two fault layers in different groups share the same agent fix tool (e.g. `adjust_shipping_cost`) but expect different user confirmation tools (`confirm_shipping_update` vs `confirm_billing_correction`), the agent cannot distinguish which confirmation to instruct — it reads the policy, finds the tool, and follows whichever section it lands on. This causes systematic failures for whichever layer the policy doesn't naturally route to.

**Rule:** If two layers share an agent fix tool, they MUST expect the same user confirmation — or you must use different agent tools so the policy can route unambiguously. The `_check_cross_layer_confirmation_consistency` static check catches this at authoring time.

### Overwrite Guards on Tools
If the policy tells the agent to ALWAYS call a tool (prescriptive policy), but the corresponding fault layer only SOMETIMES breaks the field, the agent will overwrite correct data on tasks where the fault is inactive. WRITE tools that modify fields initialized by fault layers MUST guard against overwriting non-default values.

### Composite / Outcome-Based Assertions

Instead of one assertion per fault, consider a single boolean function that checks the entire system outcome:

```python
AssertionSpec(
    func_name="assert_account_healthy",
    args={"patron_id": "{patron_id}"},
    env_type="assistant",
    message_template="Patron {patron_id} account should be fully healthy.",
),
```

Composite assertions validate the whole chain — if any upstream fault wasn't fixed, the composite fails.

### Assertion Solvability
Every assertion checking a specific expected value must be deterministically derivable from policy + DB + known_info. If 10 humans given the same info would produce different values, use a lenient assertion (e.g. `assert_risk_updated` that checks "not the default" instead of `assert_risk_level` checking an exact value). **Archetype D domains should lean heavily on lenient assertions.**

### Difficulty Invariant Verification

Before running `create_tasks()`, verify that the scenarios satisfy all six difficulty invariants. Fill in each item concretely — do not leave blanks.

**DI-1 (Diagnostic Disambiguation):** List the faults that share a fix tool, or the READ tools that require diagnostic reasoning:
- Shared fix tool: ___ used by faults: ___
- Diagnostic/info-hiding READ tool: ___
- If neither applies → REDESIGN before proceeding.

**DI-2 (Value Computation):** List the fault(s) where the agent must compute a value NOT directly in the ticket:
- Fault: ___ requires computing: ___ (from source: ___)
- If zero → REDESIGN: add at least one computed-arg fault group.

**DI-3 (Ordering Dependency):** List the ordering constraints:
- Gate chain: ___ must be fixed before ___ is visible
- Fix ordering: policy requires ___ before ___
- Precondition gate: user must call ___ before agent can call ___
- If zero → REDESIGN: add at least one ordering constraint.

**DI-4 (Multi-Property Assertions):** Count layers with 2+ assertions:
- Total fixable layers: ___. Layers with 2+ assertions: ___. Percentage: ___%
- Archetype minimum: A=60%, B=50%, C=50%, D=40%.
- If below minimum → add composite or multi-field assertions.

**DI-5 (Active User Participation):** Count distinct user WRITE tools in fault atoms:
- Distinct user WRITE tools: ___. Names: ___
- Most-used single tool: ___ (appears in ___% of layers)
- Archetype minimum: A=4, B=8, C=3, D=3. >50% sharing one tool is banned.
- If below minimum → add distinct user tools per fault domain.

**DI-6 (Effective Action Density):** Estimate median actions:
- Groups: ___. Median faults/task (at max_faults/2): ___. Avg atoms/layer: ___
- Estimated median actions: ___ × ___ = ___
- Archetype minimum: A=8, B=6, C=6, D=5.
- If below minimum → increase groups or atoms/layer.

### Do NOT
- Set `communicate_templates` on FaultLayers (brittle exact-substring matching)
- Put unfixable layers in the same FaultLayerConfig as fixable layers
- Define path constants with `Path(__file__)` — import from utils
- Bake tool-specific instructions into task_instructions — the user sim should follow the agent's lead
- Dismiss validation warnings about conditional user actions — they predict real failures
- Include frame sentences in `completion_fragment` like "You will consider your issues resolved when" — the framework adds these automatically
- Leave `completion_fragment` empty on fixable layers with atoms — this is an ERROR (the user sim needs a task-specific stop condition)
- Write `completion_fragment` that references a different field/state than the assertion checks — this breaks the contractual link between stop condition and task correctness

## Validation

The validator will:
- Check Python syntax
- Check no self-defined path constants
- Import the module
- Check `create_tasks()` exists
- Run `create_tasks(verify=False)` — must return tasks
- Check for [PERSONA:] suffixes in task IDs
- Check for resource conflicts in multi-fault tasks
- Run `verify_completion_fragments()` on each FaultLayerConfig — checks that every fixable layer has a completion_fragment, no frame phrases, no conditional preferences
