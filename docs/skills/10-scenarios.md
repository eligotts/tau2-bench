# Step 10: Scenarios (scenarios.py)

Generate the task generation module — this is the MOST COMPLEX file. It defines fault layers, entity construction, and the `create_tasks()` entry point using the Recipe Engine.

## Reference

- Read `docs/domain-authoring-guide.md` lines 583-713 (Scenarios), 714-1123 (Recipe Engine), 1172-1257 (Gotchas), and 1355-1475 (Common Mistakes)
- Read `src/tau2/domains/library/scenarios.py` for the COMPLETE reference pattern — follow it EXACTLY

## Context

- Read `data/tau2/domains/<domain_name>/domain_spec.json`
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
    verify_fault_atoms,
)
from tau2.generators.types import Persona, UserTemplate, VariantConfig
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

Define 2 personas with different interaction styles:

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
    task_instructions="If the agent resolves an issue and asks you to acknowledge...",
    ticket="Customer {customer_name} (ID: {customer_id}): {fault_descriptions}",
    purpose="Test resolution of <domain> support issues...",
)
```

### 3. Entity Construction

```python
def _build_entities(db: <DomainClass>DB) -> list[dict[str, Any]]:
    """Build entity dicts by joining primary entity + related records."""
```

- Returns a list of flat dicts, one per primary entity
- Each dict has prefixed keys for template formatting
- Include `has_<relation>` boolean flags for predicate filtering
- Include `original_<field>` copies for fields that init_calls will modify

### 4. Fault Layers

For each fault group from the domain spec, define `FaultLayer` instances using the **atoms interface**:

```python
some_fault = FaultLayer(
    name="some_fault",
    known_info_fragment="Description of the user's complaint using {template_vars}...",
    atoms=[
        # Atom 1: Agent-side fix
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_<field>",  # MUST match exact method name in tools.py
                args={"entity_id": "{entity_id}", "value": "broken_value"},
            ),
            fix=ActionSpec(
                tool_name="fix_tool_name",  # MUST match @is_tool method in tools.py
                args={"entity_id": "{entity_id}", "correct_value": "{original_value}"},
                compare_args=["entity_id"],
            ),
            check=AssertionSpec(
                func_name="assert_<field>",  # MUST match assert_* method in tools.py
                args={"entity_id": "{entity_id}", "expected": "{original_value}"},
                env_type="assistant",
                message_template="Entity {entity_id} should have correct value.",
            ),
        ),
        # Atom 2: User-side confirmation
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",  # MUST match @is_tool in user_tools.py
                args={"patron_id": "{patron_id}"},
                requestor="user",
                compare_args=[],  # Zero-arg matching for reliability
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",  # assert_* in user_tools.py
                args={"patron_id": "{patron_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_<relation>",  # Entity must have this truthy field
    resource_scope="<resource_type>:{entity_id}",  # For conflict detection
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
        InitCall(env_type="user", func_name="set_patron_info",
                 args={"name": "{patron_name}", "patron_id": "{patron_id}"}),
    ],
    base_known_info_template="You are {patron_name}. {fault_descriptions}",
    base_ticket_template="Customer {patron_name} (ID: {patron_id}): {fault_descriptions}",
    reason_for_call="You are contacting...",
    purpose="Test resolution of...",
    entity_id_field="patron_id",
    min_faults=1,
    max_faults=8,  # Or however many groups you have
)
```

### 7. Unfixable Config (separate)

If you have unfixable faults, create a SECOND FaultLayerConfig:

```python
TRANSFER_CONFIG = FaultLayerConfig(
    name="<domain_name>_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[FaultLayerGroup(name="unfixable", layers=[unfixable_layer_1, ...])],
    max_faults=1,
    max_tasks_per_bin=1,
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

Follow the library example's `create_tasks()` function exactly — it handles verification, atom verification, and optional saving.

## Critical Rules

### Template Variables
- All `{field}` references must match keys from `_build_entities()` entity dicts exactly
- Pure `{field}` references preserve the entity's type (int, str, etc.)

### Method Names
- `InitCall.func_name` must match the EXACT method name in tools.py or user_tools.py
- `ActionSpec.tool_name` must match an `@is_tool`-decorated method
- `AssertionSpec.func_name` must match an `assert_*` method (no decorator)

### Chain Verification
For every FaultLayer, trace: init breaks field X → fix modifies field X → assertion checks field X.

### Difficulty Calibration
- Each fixable FaultLayer should have 2 FaultAtoms (agent fix + user confirmation)
- With 3-5 groups active per task, each contributing 2 actions, tasks average 6-10 total actions
- Do NOT create layers with only 1 atom — those produce trivially easy tasks

### User Action Feasibility
- PREFER zero-arg user tools with `compare_args=[]`
- ONLY add user atoms when the policy EXPLICITLY says "instruct the user to X"
- NEVER add user atoms that duplicate what an agent atom already fixes

### Resource Conflicts
- Layers in DIFFERENT groups get composed (cartesian product)
- If two layers target the same entity resource, their actions may contradict
- Use `resource_scope` on every layer for conflict detection
- Put conflicting layers in the same group (mutually exclusive) or use different resources

### known_info_fragment
- Must express clear user INTENT, not just state
- Write "I have fines that I'd like waived" NOT just "I have fines"
- Must DISAMBIGUATE which resource when entity has multiples
- Use template variables like `{second_appointment_date}` to identify specific resources

### Do NOT
- Set `communicate_templates` on FaultLayers (brittle exact-substring matching)
- Put unfixable layers in the same FaultLayerConfig as fixable layers
- Define path constants with `Path(__file__)` — import from utils

## Validation

The validator will:
- Check Python syntax
- Check no self-defined path constants
- Import the module
- Check `create_tasks()` exists
- Run `create_tasks(verify=False)` — must return tasks
- Check for VARIANT:a and VARIANT:b
- Check for resource conflicts in multi-fault tasks
