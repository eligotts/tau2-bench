"""Recipe engine: declarative, correct-by-construction task generation.

A Recipe + entity pair deterministically derives every field on a task.
No field is independently authored, so disagreement is structurally impossible.
"""

import itertools
import random
import re
from dataclasses import asdict, dataclass, field, fields as dc_fields
from typing import Any, Callable, Optional, Sequence

from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall, Task
from tau2.environment.environment import Environment
from tau2.generators.diversity import DiversityTracker
from tau2.generators.entity_engine import (
    GeneratedTaskSpec,
    TaskTier,
    _spec_to_task,
)
from tau2.generators.types import Persona, UserTemplate


# ---------------------------------------------------------------------------
# Template resolution
# ---------------------------------------------------------------------------


def _resolve_args(template: dict[str, Any], entity: dict) -> dict:
    """Resolve {field} references in a template dict against an entity.

    Pure references like "{customer_id}" preserve the entity's type (int, str, etc).
    Mixed strings like "prefix {field}" do string interpolation.
    Non-string values pass through unchanged.
    """
    result = {}
    for k, v in template.items():
        if isinstance(v, str):
            m = re.fullmatch(r"\{(\w+)\}", v)
            if m:
                result[k] = entity[m.group(1)]  # preserves type
            elif "{" in v:
                result[k] = v.format(**entity)  # string interpolation
            else:
                result[k] = v
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ActionSpec:
    """Declarative specification for a single goal action."""

    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)  # {field} templates
    requestor: str = "assistant"
    compare_args: Optional[list[str]] = None


@dataclass
class AssertionSpec:
    """Declarative specification for a post-condition assertion."""

    func_name: str
    args: dict[str, Any] = field(default_factory=dict)  # {field} templates
    env_type: str = "user"
    assert_value: bool = True
    message_template: Optional[str] = None  # can use {entity_field}


@dataclass
class InitCall:
    """One initialization call, declaratively."""

    env_type: str  # "assistant" or "user"
    func_name: str
    args: dict[str, Any] = field(default_factory=dict)  # {field} templates


@dataclass
class Fault:
    """Specification for how to break something so the agent must fix it."""

    init_calls: list[InitCall]


def _resolve_init_calls(init_calls: list[InitCall], entity: dict) -> list[EnvFunctionCall]:
    """Resolve a list of InitCalls against an entity into EnvFunctionCalls."""
    return [
        EnvFunctionCall(
            env_type=ic.env_type,
            func_name=ic.func_name,
            arguments=_resolve_args(ic.args, entity),
        )
        for ic in init_calls
    ]


@dataclass
class Recipe:
    """Single-step recipe: a declarative task specification.

    fault=None means "do a thing" (no breakage).
    fault set means "fix a thing" (init breaks, agent fixes).
    """

    name: str
    entity_query: Callable[[Any], list[Any]]  # indexes -> entities
    goal_actions: list[ActionSpec]
    post_assertions: list[AssertionSpec]
    known_info_template: str
    ticket_template: str
    reason_for_call: str
    purpose: str
    tier: TaskTier = TaskTier.TIER_3
    fault: Optional[Fault] = None
    description_template: Optional[str] = None
    nl_assertion_templates: list[str] = field(default_factory=list)
    compare_args_map: Optional[dict[str, Optional[list[str]]]] = None
    entity_id_field: Optional[str] = None


@dataclass
class ComposedRecipe:
    """Multi-step recipe composed from individual Recipe steps."""

    name: str
    steps: list[Recipe]
    entity_query: Callable[[Any], list[tuple]]  # indexes -> entity-tuples
    known_info_template: str
    ticket_template: str
    reason_for_call: str
    purpose: str
    tier: TaskTier = TaskTier.TIER_4
    description_template: Optional[str] = None
    nl_assertion_templates: list[str] = field(default_factory=list)
    entity_id_field: Optional[str] = None


@dataclass
class DiversityConfig:
    """Budget and weighting for recipe task generation."""

    target_count: int = 0  # 0 = use all entities, >0 = budget
    type_weights: dict[str, float] = field(
        default_factory=lambda: {
            "single_do": 0.30,
            "single_fix": 0.30,
            "composed": 0.40,
        }
    )
    min_per_entity: int = 1
    min_per_recipe: int = 1


@dataclass
class FaultAtom:
    """One break→fix→check triple.  Smallest unit of fault injection.

    Authored as a single unit so the correspondence between what breaks,
    what fixes it, and what verifies the fix is structural, not positional.

    Three natural atom types:
      - init + fix + check  : primary fault (something breaks, agent fixes, verify)
      - None + fix + check  : consequence action (no separate init, needed to complete fix)
      - None + fix + None   : terminal follow-up (e.g. reboot, no independent assertion)

    ``init`` can be a single InitCall or a list when setting up one fault
    requires multiple DB mutations (e.g. set status + set amount + zero paid).

    Ordering fields:
      - ``phase``: execution order within a layer. Lower phases run first.
        Within the same phase, requestor is a tiebreaker (user=0, agent=1).
      - ``step_type``: declares the atom's role in the resolution sequence:
        - ``"fix"`` — state-changing WRITE action (default)
        - ``"diagnostic"`` — information-gathering READ action, part of the
          golden path but doesn't change DB state
        - ``"confirm"`` — user acknowledgment action
    """

    fix: ActionSpec                                              # required: the tool call
    check: Optional[AssertionSpec] = None                        # verify this step
    init: Optional[InitCall | list[InitCall]] = None             # break something
    phase: int = 0                                               # execution order within layer
    step_type: str = "fix"                                       # "fix" | "diagnostic" | "confirm"

    def get_init_list(self) -> list[InitCall]:
        """Return init as a flat list (0, 1, or N items)."""
        if self.init is None:
            return []
        if isinstance(self.init, list):
            return self.init
        return [self.init]


@dataclass
class FaultLayer:
    """A single injectable fault: what breaks, how to fix it, and what to communicate.

    **Preferred interface** — use ``atoms``: a list of :class:`FaultAtom` triples.
    Each atom bundles its init, fix, and check together so the correspondence
    is structural, not positional.  The pipeline unfolds atoms into flat lists
    for spec generation.

    **Legacy interface** — set ``init_calls``, ``actions``, ``assertions``, and
    ``user_actions`` directly.  Supported for backward compatibility.  If
    ``atoms`` is non-empty it takes precedence and the flat lists are ignored.

    When unfixable=True, no tool can resolve this fault — the entire combo
    becomes a transfer_to_human task.  Unfixable layers must have empty
    atoms (or actions/assertions) but should still inject the fault via init.
    """

    name: str
    known_info_fragment: str  # e.g. "I have an overdue book ..."

    # ── Completion & preference fragments ─────────────────────────────
    # These compose into user_task_instructions automatically.
    # completion_fragment: the user-observable inverse of known_info_fragment.
    #   Half-sentence describing what "fixed" looks like from the user's
    #   perspective.  Joined with " and " across active layers into:
    #   "You will consider your issues resolved when <X> and <Y>."
    #   MUST reference the same DB field / user tool that the assertion
    #   checks — this is the contractual link between stop condition and
    #   task correctness.
    #   GOOD: "your speed test shows excellent results"
    #   BAD:  "You will consider the issue resolved when..."  (framework adds frame)
    #   BAD:  "your bill shows the correct amount"  (for a speed fault — wrong field)
    completion_fragment: str = ""

    # ── Primary interface: atoms ──────────────────────────────────────
    atoms: list[FaultAtom] = field(default_factory=list)

    # ── Legacy interface: parallel lists (ignored when atoms is set) ──
    init_calls: list[InitCall] = field(default_factory=list)
    actions: list[ActionSpec] = field(default_factory=list)
    assertions: list[AssertionSpec] = field(default_factory=list)
    user_actions: list[ActionSpec] = field(default_factory=list)

    unfixable: bool = False
    gate_tier: int = 0  # execution order across composed layers; tier-0 before tier-1
    # NOTE: fragment is formatted via .format(**entity_fields). When targeting a
    # specific resource among multiples of the same type (e.g. second appointment),
    # ALWAYS use template variables to disambiguate:
    #   GOOD: "for {second_pet_name}'s appointment on {second_appointment_date}"
    #   BAD:  "for my upcoming appointment"  (agent can't tell which one)
    communicate_templates: list[str] = field(default_factory=list)
    nl_assertion_templates: list[str] = field(default_factory=list)
    predicate_field: Optional[str] = None  # entity[field] must be truthy
    predicate_ne: Optional[tuple[str, Any]] = None  # entity[field] != value
    resource_scope: Optional[str] = None  # template like "router:{customer_id}"

    # ── Unfold helpers ────────────────────────────────────────────────

    def get_init_calls(self) -> list[InitCall]:
        """Return init calls — from atoms if set, else from flat list."""
        if self.atoms:
            result: list[InitCall] = []
            for a in self.atoms:
                result.extend(a.get_init_list())
            return result
        return self.init_calls

    def get_actions(self) -> list[ActionSpec]:
        """Return fix actions in order — from atoms if set, else from flat list."""
        if self.atoms:
            return [a.fix for a in self.atoms]
        return self.actions

    def get_user_actions(self) -> list[ActionSpec]:
        """Return user-side fix actions — derived from atoms or from flat list."""
        if self.atoms:
            return [a.fix for a in self.atoms if a.fix.requestor == "user"]
        return self.user_actions

    def get_agent_actions(self) -> list[ActionSpec]:
        """Return agent-side fix actions — derived from atoms or from flat list."""
        if self.atoms:
            return [a.fix for a in self.atoms if a.fix.requestor != "user"]
        return self.actions

    def get_assertions(self) -> list[AssertionSpec]:
        """Return post-condition assertions — atom checks + layer-level assertions."""
        if self.atoms:
            result = [a.check for a in self.atoms if a.check is not None]
            # Merge any layer-level assertions (for secondary checks not tied to a specific atom)
            result.extend(self.assertions)
            return result
        return self.assertions


def _check_predicate(layer: FaultLayer, entity: Any) -> bool:
    """Evaluate a FaultLayer's predicate against an entity."""
    entity_fields = _entity_to_fields(entity) if not isinstance(entity, dict) else entity
    if layer.predicate_field:
        return bool(entity_fields.get(layer.predicate_field))
    if layer.predicate_ne:
        field_name, value = layer.predicate_ne
        return entity_fields.get(field_name) != value
    return True


@dataclass
class FaultLayerGroup:
    """Mutually exclusive fault layers; pick 0 or 1."""

    name: str
    layers: list[FaultLayer]
    resolution_category: str = ""  # e.g. "connectivity", "billing"


@dataclass
class FaultLayerConfig:
    """Cartesian fault composition config: entity × fault-combo → tasks."""

    name: str
    entity_query: Callable[[Any], list[Any]]
    groups: list[FaultLayerGroup]
    base_init_calls: list[InitCall]
    base_known_info_template: str  # must contain {fault_descriptions}
    base_ticket_template: str
    reason_for_call: str
    purpose: str
    base_actions: list[ActionSpec] = field(default_factory=list)
    base_user_actions: list[ActionSpec] = field(default_factory=list)
    base_assertions: list[AssertionSpec] = field(default_factory=list)
    base_communicate_templates: list[str] = field(default_factory=list)
    base_nl_assertion_templates: list[str] = field(default_factory=list)
    entity_id_field: Optional[str] = None
    min_faults: int = 1
    max_faults: int = 99
    max_tasks_per_bin: Optional[int] = None  # cap N specs per (entity, fault_count) bin
    max_total_tasks: Optional[int] = None  # global budget, proportional sampling per tier
    required_groups: list[str] = field(default_factory=list)  # combos must include ≥1 layer from these groups
    # Domain-level tool grounding block appended to every task's user_task_instructions.
    # Tells user sim to ground responses on tool call results, not make things up.
    # Example: "Whenever the agent asks about your device, always ground your
    #  responses on the results of tool calls. Never make up tool call results."
    tool_grounding_block: str = ""


@dataclass
class RecipeBook:
    """Collection of recipes for a domain.

    resolution_instruction: A single sentence describing the customer's
        desired end-state (e.g. "your internet connection is working
        properly and any billing issues have been addressed").  Used as
        the stopping criterion in composed task_instructions instead of
        AND-chaining per-layer completion_fragments.  Fragments become
        context for the user sim (what to complain about), while
        resolution_instruction is the outcome the user sim waits for.
        If empty, falls back to AND-chaining fragments (backward compat).
    """

    recipes: list[Recipe] = field(default_factory=list)
    composed_recipes: list[ComposedRecipe] = field(default_factory=list)
    fault_layer_configs: list[FaultLayerConfig] = field(default_factory=list)
    diversity_config: Optional[DiversityConfig] = None
    resolution_instruction: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMMON_ID_FIELDS = ("id", "account_id", "patient_id", "device_id", "user_id", "name")


def _entity_to_fields(entity: Any) -> dict:
    """Extract template-substitutable fields from an entity."""
    if isinstance(entity, dict):
        return entity
    # Pydantic model
    if hasattr(entity, "model_dump"):
        return entity.model_dump()
    # dataclass
    if hasattr(entity, "__dataclass_fields__"):
        return asdict(entity)
    # plain object
    return vars(entity)


def _get_entity_id(recipe: Any, entity: Any, index: int) -> str:
    """Determine a unique ID string for an entity."""
    if recipe.entity_id_field is not None:
        fields = _entity_to_fields(entity) if not isinstance(entity, dict) else entity
        return str(fields[recipe.entity_id_field])

    fields = _entity_to_fields(entity) if not isinstance(entity, tuple) else {}
    for field_name in _COMMON_ID_FIELDS:
        if field_name in fields and fields[field_name] is not None:
            return str(fields[field_name])

    return str(index)


# ---------------------------------------------------------------------------
# Core: recipe -> spec
# ---------------------------------------------------------------------------


def recipe_to_spec(
    recipe: Recipe,
    entity: Any,
    index: int = 0,
) -> GeneratedTaskSpec:
    """Convert a (Recipe, entity) pair into a GeneratedTaskSpec.

    This is the correctness heart: every field is derived from the pair,
    so nothing can disagree.
    """
    entity_fields = _entity_to_fields(entity)
    entity_id = _get_entity_id(recipe, entity, index)

    # 1. init_actions from fault
    init_actions: list[EnvFunctionCall] = []
    if recipe.fault is not None:
        init_actions = _resolve_init_calls(recipe.fault.init_calls, entity_fields)

    # 2. actions from ActionSpecs
    actions: list[dict] = []
    for i, aspec in enumerate(recipe.goal_actions):
        action: dict[str, Any] = {
            "action_id": str(i),
            "name": aspec.tool_name,
            "requestor": aspec.requestor,
            "arguments": _resolve_args(aspec.args, entity_fields),
        }
        # compare_args precedence: ActionSpec > recipe map > omitted
        ca = aspec.compare_args
        if ca is None and recipe.compare_args_map is not None:
            ca = recipe.compare_args_map.get(aspec.tool_name)
        if ca is not None:
            action["compare_args"] = ca
        actions.append(action)

    # 3. env_assertions from AssertionSpecs
    env_assertions: list[EnvAssertion] = []
    for aspec in recipe.post_assertions:
        msg = None
        if aspec.message_template is not None:
            msg = aspec.message_template.format(**entity_fields)
        env_assertions.append(
            EnvAssertion(
                env_type=aspec.env_type,
                func_name=aspec.func_name,
                arguments=_resolve_args(aspec.args, entity_fields),
                assert_value=aspec.assert_value,
                message=msg,
            )
        )

    # 4. text fields from templates
    known_info = recipe.known_info_template.format(**entity_fields)
    ticket = recipe.ticket_template.format(**entity_fields)
    description = (
        recipe.description_template.format(**entity_fields)
        if recipe.description_template
        else ticket
    )
    nl_assertions = [t.format(**entity_fields) for t in recipe.nl_assertion_templates]

    task_id = f"{recipe.name}_{entity_id}"

    return GeneratedTaskSpec(
        task_id=task_id,
        description=description,
        purpose=recipe.purpose,
        known_info=known_info,
        reason_for_call=recipe.reason_for_call,
        actions=actions,
        env_assertions=env_assertions,
        nl_assertions=nl_assertions,
        init_actions=init_actions,
        tier=recipe.tier,
    )


def composed_recipe_to_spec(
    composed: ComposedRecipe,
    entity_tuple: tuple,
    index: int = 0,
) -> GeneratedTaskSpec:
    """Convert a (ComposedRecipe, entity_tuple) into a GeneratedTaskSpec.

    Each step[i] is paired with entity_tuple[i]. Results are concatenated.
    """
    assert len(composed.steps) == len(entity_tuple), (
        f"ComposedRecipe '{composed.name}' has {len(composed.steps)} steps "
        f"but entity_tuple has {len(entity_tuple)} elements"
    )

    # Build sub-specs
    sub_specs = [
        recipe_to_spec(step, ent, index)
        for step, ent in zip(composed.steps, entity_tuple)
    ]

    # Concatenate init_actions, actions (re-numbered), env_assertions
    all_init: list[EnvFunctionCall] = []
    all_actions: list[dict] = []
    all_env_assertions: list[EnvAssertion] = []
    all_nl: list[str] = []
    action_counter = 0

    for sub in sub_specs:
        all_init.extend(sub.init_actions)
        for act in sub.actions:
            renumbered = dict(act)
            renumbered["action_id"] = str(action_counter)
            all_actions.append(renumbered)
            action_counter += 1
        all_env_assertions.extend(sub.env_assertions)
        all_nl.extend(sub.nl_assertions)

    # Build combined template fields: step0_X, step1_X, plus un-prefixed from first entity
    combined_fields: dict[str, Any] = {}
    for i, ent in enumerate(entity_tuple):
        ent_fields = _entity_to_fields(ent)
        for k, v in ent_fields.items():
            combined_fields[f"step{i}_{k}"] = v
        if i == 0:
            combined_fields.update(ent_fields)

    # Format composed-level text
    known_info = composed.known_info_template.format(**combined_fields)
    ticket = composed.ticket_template.format(**combined_fields)
    description = (
        composed.description_template.format(**combined_fields)
        if composed.description_template
        else ticket
    )
    nl_assertions = [
        t.format(**combined_fields) for t in composed.nl_assertion_templates
    ] + all_nl

    entity_id = _get_entity_id(composed, entity_tuple, index)
    task_id = f"{composed.name}_{entity_id}"

    return GeneratedTaskSpec(
        task_id=task_id,
        description=description,
        purpose=composed.purpose,
        known_info=known_info,
        reason_for_call=composed.reason_for_call,
        actions=all_actions,
        env_assertions=all_env_assertions,
        nl_assertions=nl_assertions,
        init_actions=all_init,
        tier=composed.tier,
    )


# ---------------------------------------------------------------------------
# Fault-layer composition
# ---------------------------------------------------------------------------


def _freeze_value(v: object) -> str:
    """Deterministic string key for an action/assertion argument value."""
    if isinstance(v, (list, tuple)):
        return repr(sorted(str(x) for x in v))
    return str(v)


def _dedup_actions(actions: list[dict]) -> list[dict]:
    """Remove duplicate actions (same name, requestor, resolved arguments).

    When multiple fault layers produce identical user actions (e.g. two layers
    both require acknowledge_treatment_plan for the same pet), only the first
    copy is kept.  Action IDs are renumbered after dedup.
    """
    seen: set[tuple] = set()
    result: list[dict] = []
    for action in actions:
        frozen_args = tuple(sorted(
            (k, _freeze_value(v)) for k, v in action["arguments"].items()
        ))
        key = (action["name"], action["requestor"], frozen_args)
        if key in seen:
            continue
        seen.add(key)
        result.append(action)
    # Renumber action_ids
    for i, a in enumerate(result):
        a["action_id"] = str(i)
    return result


def _dedup_assertions(assertions: list[EnvAssertion]) -> list[EnvAssertion]:
    """Remove duplicate assertions (same func_name, env_type, arguments, assert_value)."""
    seen: set[tuple] = set()
    result: list[EnvAssertion] = []
    for a in assertions:
        frozen_args = tuple(sorted(
            (k, _freeze_value(v)) for k, v in (a.arguments or {}).items()
        ))
        key = (a.func_name, a.env_type, frozen_args, a.assert_value)
        if key in seen:
            continue
        seen.add(key)
        result.append(a)
    return result


def _compose_task_instructions(
    active_layers: list["FaultLayer"],
    flc: "FaultLayerConfig",
    entity_fields: dict,
    resolution_instruction: str = "",
) -> Optional[str]:
    """Compose user_task_instructions from per-layer completion_fragments.

    When ``resolution_instruction`` is provided (from RecipeBook), it is
    used as the stopping criterion instead of AND-chaining all fragments.
    Fragments become context (what issues the user is experiencing),
    while the resolution_instruction describes the desired outcome.

    When ``resolution_instruction`` is empty, falls back to the legacy
    behavior of AND-chaining fragments as the stopping criterion.

    Returns None if no layer provides a completion_fragment, so
    ``_spec_to_task`` falls back to ``UserTemplate.task_instructions``.
    """
    completion_fragments = [
        layer.completion_fragment.format(**entity_fields)
        for layer in active_layers
        if layer.completion_fragment
    ]

    if not completion_fragments:
        return None

    parts: list[str] = [
        "Follow the agent's instructions throughout the conversation.",
        "When the agent asks you to perform an action or use one of your"
        " tools, do so.",
        "You must actually call the tool \u2014 describing the action in"
        " words is not sufficient.",
    ]

    if resolution_instruction:
        # New: resolution_instruction is the stopping criterion,
        # fragments are context for what issues to expect
        parts.append(
            f"You will consider your issues resolved when"
            f" {resolution_instruction}."
        )
    else:
        # Legacy: AND-chain fragments as stopping criterion
        criteria = " and ".join(completion_fragments)
        parts.append(f"You will consider your issues resolved when {criteria}.")

    # Domain-level tool grounding block
    if flc.tool_grounding_block:
        parts.append(flc.tool_grounding_block)

    return " ".join(parts)


def _fault_layers_to_spec(
    flc: FaultLayerConfig,
    entity: Any,
    active_layers: list[FaultLayer],
    resolution_instruction: str = "",
) -> GeneratedTaskSpec:
    """Convert a (FaultLayerConfig, entity, active_layers) into a GeneratedTaskSpec."""
    entity_fields = _entity_to_fields(entity)

    # Check if any active layer is unfixable → whole combo becomes transfer_to_human
    has_unfixable = any(layer.unfixable for layer in active_layers)

    # Init: base normalization + fault injection (always runs, even for unfixable)
    # Sort active_layers by gate_tier for init ordering: tier-0 state set up first.
    sorted_layers = sorted(active_layers, key=lambda l: l.gate_tier)
    init_actions = list(_resolve_init_calls(flc.base_init_calls, entity_fields))
    for layer in sorted_layers:
        init_actions.extend(_resolve_init_calls(layer.get_init_calls(), entity_fields))

    if has_unfixable:
        # Unfixable combo: single transfer_to_human action.
        # Preservation assertions from unfixable layers verify the agent
        # did not modify state it shouldn't touch (like telecom's
        # assert_service_status(no_service) pattern).
        actions: list[dict] = [
            {
                "action_id": "0",
                "name": "transfer_to_human",
                "requestor": "assistant",
                "arguments": {"summary": ""},
                "compare_args": [],
            },
        ]
        # Collect preservation assertions from unfixable layers only.
        # Fixable layers' assertions are skipped because their fixes
        # won't run — the agent should transfer, not partially fix.
        unfixable_assertion_specs: list[AssertionSpec] = []
        for layer in active_layers:
            if layer.unfixable:
                unfixable_assertion_specs.extend(layer.get_assertions())

        env_assertions: list[EnvAssertion] = []
        for aspec in unfixable_assertion_specs:
            msg = None
            if aspec.message_template is not None:
                msg = aspec.message_template.format(**entity_fields)
            env_assertions.append(
                EnvAssertion(
                    env_type=aspec.env_type,
                    func_name=aspec.func_name,
                    arguments=_resolve_args(aspec.args, entity_fields),
                    assert_value=aspec.assert_value,
                    message=msg,
                )
            )
        env_assertions = _dedup_assertions(env_assertions)
        # Compose user_task_instructions from completion_fragments on
        # unfixable layers.  This gives the user sim a concrete stop
        # condition (e.g. "the agent has transferred you to a specialist")
        # instead of the generic fallback that causes infinite loops.
        # Mirrors telecom's pattern: same instruction framework for both
        # fixable and transfer tasks.
        user_task_instructions: Optional[str] = _compose_task_instructions(
            active_layers, flc, entity_fields, resolution_instruction
        )
    else:
        # Normal fixable combo: collect all atom actions with ordering metadata,
        # then stable-sort by (gate_tier, phase, requestor_priority).
        # This replaces the old 4-loop collection with a single unified sort.
        entries: list[tuple[int, int, int, ActionSpec]] = []
        for layer in sorted_layers:
            if layer.atoms:
                for atom in layer.atoms:
                    requestor_priority = 0 if atom.fix.requestor == "user" else 1
                    entries.append((layer.gate_tier, atom.phase, requestor_priority, atom.fix))
            else:
                # Legacy interface: user actions at phase 0, agent actions at phase 0
                # with requestor as tiebreaker (preserves old user-before-agent order).
                # Force requestor="user" on user_actions for backward compat.
                for aspec in layer.get_user_actions():
                    forced = ActionSpec(
                        tool_name=aspec.tool_name,
                        args=aspec.args,
                        requestor="user",
                        compare_args=aspec.compare_args,
                    )
                    entries.append((layer.gate_tier, 0, 0, forced))
                for aspec in layer.get_agent_actions():
                    entries.append((layer.gate_tier, 0, 1, aspec))

        # Base actions at synthetic final tiers (after all layer actions)
        max_tier = max((l.gate_tier for l in sorted_layers), default=0)
        for aspec in flc.base_actions:
            entries.append((max_tier + 1, 0, 1, aspec))
        for aspec in flc.base_user_actions:
            # Force requestor="user" for base_user_actions (backward compat)
            forced = ActionSpec(
                tool_name=aspec.tool_name,
                args=aspec.args,
                requestor="user",
                compare_args=aspec.compare_args,
            )
            entries.append((max_tier + 2, 0, 0, forced))

        # Stable sort — preserves layer order within same key
        entries.sort(key=lambda x: (x[0], x[1], x[2]))

        # Build action dicts from sorted entries
        actions = []
        for _, _, _, aspec in entries:
            action: dict[str, Any] = {
                "action_id": str(len(actions)),
                "name": aspec.tool_name,
                "requestor": aspec.requestor,
                "arguments": _resolve_args(aspec.args, entity_fields),
            }
            if aspec.compare_args is not None:
                action["compare_args"] = aspec.compare_args
            actions.append(action)

        # Deduplicate actions: multiple layers may produce identical user
        # actions (e.g. acknowledge_treatment_plan for the same pet_id).
        actions = _dedup_actions(actions)

        # Compose user_task_instructions from per-layer completion_fragments.
        # If any layer has completion_fragment, the framework assembles
        # the full instructions automatically.
        # Otherwise falls back to UserTemplate.task_instructions via None.
        user_task_instructions = _compose_task_instructions(
            active_layers, flc, entity_fields, resolution_instruction
        )

        # Assertions: layer assertions + base assertions
        all_assertion_specs: list[AssertionSpec] = []
        for layer in active_layers:
            all_assertion_specs.extend(layer.get_assertions())
        all_assertion_specs.extend(flc.base_assertions)

        env_assertions = []
        for aspec in all_assertion_specs:
            msg = None
            if aspec.message_template is not None:
                msg = aspec.message_template.format(**entity_fields)
            env_assertions.append(
                EnvAssertion(
                    env_type=aspec.env_type,
                    func_name=aspec.func_name,
                    arguments=_resolve_args(aspec.args, entity_fields),
                    assert_value=aspec.assert_value,
                    message=msg,
                )
            )

        # Deduplicate assertions: multiple layers may produce identical
        # checks (e.g. assert_treatment_acknowledged for same pet_id).
        env_assertions = _dedup_assertions(env_assertions)

    # communicate_info: format templates from active layers + base
    communicate_info: list[str] = []
    for layer in active_layers:
        for t in layer.communicate_templates:
            communicate_info.append(t.format(**entity_fields))
    for t in flc.base_communicate_templates:
        communicate_info.append(t.format(**entity_fields))

    # nl_assertions: format templates from active layers + base
    nl_assertions: list[str] = []
    for layer in active_layers:
        for t in layer.nl_assertion_templates:
            nl_assertions.append(t.format(**entity_fields))
    for t in flc.base_nl_assertion_templates:
        nl_assertions.append(t.format(**entity_fields))

    # Text fields
    fault_descriptions = ". ".join(
        layer.known_info_fragment.format(**entity_fields)
        for layer in active_layers
    )
    known_info = flc.base_known_info_template.format(
        fault_descriptions=fault_descriptions, **entity_fields
    )
    ticket = flc.base_ticket_template.format(
        fault_descriptions=fault_descriptions, **entity_fields
    )

    # Tier from fault count
    n = len(active_layers)
    if n <= 1:
        tier = TaskTier.TIER_3
    elif n == 2:
        tier = TaskTier.TIER_4
    else:
        tier = TaskTier.TIER_5

    # Entity ID
    if flc.entity_id_field is not None:
        entity_id = str(entity_fields[flc.entity_id_field])
    else:
        entity_id = _get_entity_id(flc, entity, 0)

    # Task ID
    layer_names = "|".join(l.name for l in active_layers)
    task_id = f"{flc.name}_{layer_names}_{entity_id}"

    return GeneratedTaskSpec(
        task_id=task_id,
        description=ticket,
        purpose=flc.purpose,
        known_info=known_info,
        reason_for_call=flc.reason_for_call,
        actions=actions,
        env_assertions=env_assertions,
        nl_assertions=nl_assertions,
        communicate_info=communicate_info,
        init_actions=init_actions,
        user_task_instructions=user_task_instructions,
        tier=tier,
    )


def _validate_resource_scopes(
    flc: FaultLayerConfig,
    entities: list[Any],
) -> None:
    """Validate that layers in different groups don't modify the same resource.

    If two layers have overlapping resource_scope, they should be in the
    same group (mutually exclusive), not in different groups (composable).
    Layers without resource_scope are skipped (opt-in check).

    Also warns if a state-modifying layer lacks resource_scope, since
    conflicts involving that layer would go undetected.
    """
    import warnings

    # Warn about state-modifying layers missing resource_scope
    if entities:
        sample_entity = entities[0]
        sample_fields = _entity_to_fields(sample_entity) if not isinstance(sample_entity, dict) else sample_entity
        for group in flc.groups:
            for layer in group.layers:
                if layer.resource_scope is not None:
                    continue
                if not _check_predicate(layer, sample_entity):
                    continue
                # Check if this layer modifies state (has init_calls)
                if layer.get_init_calls():
                    warnings.warn(
                        f"Layer '{layer.name}' (group '{group.name}') in '{flc.name}' "
                        f"modifies state via init_calls but has no resource_scope. "
                        f"Add resource_scope to enable cross-group conflict detection.",
                        stacklevel=3,
                    )

    # Check for cross-group resource overlap.
    # Layers at different gate_tiers execute sequentially, so overlapping
    # scopes are safe — only same-tier layers can conflict.
    for i, group_i in enumerate(flc.groups):
        for j, group_j in enumerate(flc.groups):
            if j <= i:
                continue
            for layer_i in group_i.layers:
                if layer_i.resource_scope is None:
                    continue
                for layer_j in group_j.layers:
                    if layer_j.resource_scope is None:
                        continue
                    # Different gate_tiers → sequential execution, no conflict
                    if layer_i.gate_tier != layer_j.gate_tier:
                        continue
                    for entity in entities:
                        entity_fields = _entity_to_fields(entity) if not isinstance(entity, dict) else entity
                        # Skip if either layer's predicate excludes this entity
                        if not _check_predicate(layer_i, entity):
                            continue
                        if not _check_predicate(layer_j, entity):
                            continue
                        scope_i = {layer_i.resource_scope.format(**entity_fields)}
                        scope_j = {layer_j.resource_scope.format(**entity_fields)}
                        overlap = scope_i & scope_j
                        if overlap:
                            raise ValueError(
                                f"Resource conflict in '{flc.name}': "
                                f"layer '{layer_i.name}' (group '{group_i.name}') "
                                f"and layer '{layer_j.name}' (group '{group_j.name}') "
                                f"both modify {overlap}. "
                                f"Move them to the same group to make them mutually exclusive, "
                                f"or use separate resource instances (e.g. first_X vs second_X), "
                                f"or use different gate_tier values for sequential execution."
                            )


def _generate_fault_layer_specs(
    flc: FaultLayerConfig,
    indexes: Any,
    resolution_instruction: str = "",
) -> list[GeneratedTaskSpec]:
    """Generate specs from a FaultLayerConfig via cartesian product over groups."""
    entities = flc.entity_query(indexes)

    # Validate layer structure
    for group in flc.groups:
        for layer in group.layers:
            # Unfixable layers must have no fix actions or user actions.
            # Assertions ARE allowed — they serve as preservation checks
            # (verify the agent didn't modify state it shouldn't touch).
            if layer.unfixable:
                actions = layer.get_actions()
                if actions:
                    raise ValueError(
                        f"Unfixable layer '{layer.name}' (group '{group.name}') in "
                        f"'{flc.name}' must have empty actions=[], "
                        f"got {len(actions)}. "
                        f"Unfixable layers auto-generate transfer_to_human."
                    )
                if layer.user_actions:
                    raise ValueError(
                        f"Unfixable layer '{layer.name}' (group '{group.name}') in "
                        f"'{flc.name}' must have empty user_actions=[], "
                        f"got {len(layer.user_actions)}. "
                        f"Unfixable layers auto-generate transfer_to_human."
                    )
                # Warn if an unfixable layer injects state but has no
                # preservation assertion to verify the agent left it alone.
                if layer.get_init_calls() and not layer.get_assertions():
                    import warnings
                    warnings.warn(
                        f"Unfixable layer '{layer.name}' (group '{group.name}') "
                        f"in '{flc.name}' injects state via init but has no "
                        f"preservation assertions. Add assertions to verify the "
                        f"agent did not modify the injected state.",
                        stacklevel=3,
                    )

            # Atoms + legacy flat lists conflict (assertions allowed alongside atoms)
            if layer.atoms and (layer.init_calls or layer.actions):
                raise ValueError(
                    f"Layer '{layer.name}' (group '{group.name}') in '{flc.name}' "
                    f"has both atoms and legacy init_calls/actions. "
                    f"Use atoms for the primary interface; layer-level assertions "
                    f"are allowed for secondary checks."
                )

            # Validate step_type values
            import warnings
            _VALID_STEP_TYPES = {"fix", "diagnostic", "confirm"}
            for i, atom in enumerate(layer.atoms):
                if atom.step_type not in _VALID_STEP_TYPES:
                    raise ValueError(
                        f"Layer '{layer.name}' atom {i} "
                        f"(fix={atom.fix.tool_name}): invalid step_type "
                        f"'{atom.step_type}'. Must be one of {_VALID_STEP_TYPES}."
                    )

            # Warn if atom has init but no check (skip diagnostic atoms —
            # they gather info, not verify state change)
            for i, atom in enumerate(layer.atoms):
                if atom.init is not None and atom.check is None and atom.step_type != "diagnostic":
                    warnings.warn(
                        f"Layer '{layer.name}' atom {i} "
                        f"(fix={atom.fix.tool_name}): has init but no check. "
                        f"The init breaks something without verification.",
                        stacklevel=3,
                    )

    # Validate required_groups reference actual group names
    if flc.required_groups:
        group_names = {g.name for g in flc.groups}
        bad = [rg for rg in flc.required_groups if rg not in group_names]
        if bad:
            raise ValueError(
                f"FaultLayerConfig '{flc.name}': required_groups {bad} "
                f"don't match any group names {sorted(group_names)}."
            )

    # Validate mutual exclusion of sampling strategies
    if flc.max_tasks_per_bin is not None and flc.max_total_tasks is not None:
        raise ValueError(
            f"FaultLayerConfig '{flc.name}': max_tasks_per_bin and max_total_tasks "
            f"are mutually exclusive. Use max_tasks_per_bin for uniform sampling "
            f"across bins, or max_total_tasks for proportional sampling that "
            f"preserves the natural bell-curve distribution."
        )

    # Validate resource scopes before generating combos
    _validate_resource_scopes(flc, entities)

    # Phase 1: Build all valid combos as (entity, active_layers) tuples
    all_combos: list[tuple[Any, list[FaultLayer]]] = []

    for entity in entities:
        # Determine applicable layers per group (check predicate)
        applicable_groups: list[list] = []
        for group in flc.groups:
            applicable = [
                layer for layer in group.layers
                if _check_predicate(layer, entity)
            ]
            applicable_groups.append(applicable + [None])  # None = fault off

        # Cartesian product across groups
        for combo in itertools.product(*applicable_groups):
            active = [layer for layer in combo if layer is not None]
            if not (flc.min_faults <= len(active) <= flc.max_faults):
                continue
            # Filter: if required_groups is set, combo must include ≥1 layer
            # from each required group
            if flc.required_groups:
                active_group_names = {
                    g.name for g in flc.groups
                    for layer in g.layers
                    if layer in active
                }
                if not all(rg in active_group_names for rg in flc.required_groups):
                    continue
            all_combos.append((entity, active))

    # Phase 2: Sample if a sampling strategy is set
    if flc.max_tasks_per_bin is not None:
        all_combos = _bin_sample(all_combos, flc.max_tasks_per_bin, flc)
    elif flc.max_total_tasks is not None:
        all_combos = _proportional_sample(all_combos, flc.max_total_tasks)

    # Phase 3: Generate specs
    return [_fault_layers_to_spec(flc, entity, active, resolution_instruction) for entity, active in all_combos]


def _bin_sample(
    combos: list[tuple[Any, list[FaultLayer]]],
    max_per_bin: int,
    flc: FaultLayerConfig,
) -> list[tuple[Any, list[FaultLayer]]]:
    """Telecom-style bin sampling: group by (entity, fault_count), cap N per bin."""
    rng = random.Random(42)

    # Bin by (entity_id, fault_count)
    bins: dict[tuple[str, int], list[tuple[Any, list[FaultLayer]]]] = {}
    for entity, active in combos:
        if flc.entity_id_field is not None:
            entity_fields = _entity_to_fields(entity) if not isinstance(entity, dict) else entity
            eid = str(entity_fields[flc.entity_id_field])
        else:
            eid = str(_get_entity_id(flc, entity, 0))
        key = (eid, len(active))
        bins.setdefault(key, []).append((entity, active))

    # Sample up to max_per_bin from each bin
    sampled: list[tuple[Any, list[FaultLayer]]] = []
    for key in sorted(bins.keys()):
        items = bins[key]
        if len(items) <= max_per_bin:
            sampled.extend(items)
        else:
            sampled.extend(rng.sample(items, max_per_bin))

    return sampled


def _proportional_sample(
    combos: list[tuple[Any, list[FaultLayer]]],
    max_total: int,
) -> list[tuple[Any, list[FaultLayer]]]:
    """Proportional sampling: group by fault_count tier, allocate budget proportionally.

    This preserves the natural C(N,K) bell-curve distribution — tiers with
    more combos (middle fault counts) keep more tasks, while edge tiers
    (1-fault, max-fault) keep fewer.  Within each tier, items are sampled
    uniformly so all entities are equally likely.
    """
    if max_total >= len(combos):
        return combos

    rng = random.Random(42)

    # Group by fault_count (number of active layers)
    tiers: dict[int, list[tuple[Any, list[FaultLayer]]]] = {}
    for entity, active in combos:
        fc = len(active)
        tiers.setdefault(fc, []).append((entity, active))

    total_count = len(combos)

    # Allocate budget proportionally to each tier
    raw_budgets: dict[int, float] = {
        fc: max_total * len(items) / total_count
        for fc, items in tiers.items()
    }

    # Round and adjust so budgets sum to exactly max_total.
    # Each tier gets at least 1 if it has any combos.
    int_budgets: dict[int, int] = {}
    for fc in sorted(tiers.keys()):
        int_budgets[fc] = max(1, round(raw_budgets[fc]))

    # Adjust rounding error: trim from largest tiers or add to largest tiers
    diff = sum(int_budgets.values()) - max_total
    sorted_tiers = sorted(int_budgets.keys(), key=lambda fc: len(tiers[fc]), reverse=True)
    idx = 0
    while diff > 0 and idx < len(sorted_tiers):
        fc = sorted_tiers[idx]
        if int_budgets[fc] > 1:
            int_budgets[fc] -= 1
            diff -= 1
        idx += 1
        if idx >= len(sorted_tiers):
            idx = 0
    while diff < 0:
        fc = sorted_tiers[idx % len(sorted_tiers)]
        int_budgets[fc] += 1
        diff += 1
        idx += 1

    # Sample within each tier
    sampled: list[tuple[Any, list[FaultLayer]]] = []
    for fc in sorted(tiers.keys()):
        items = tiers[fc]
        budget = min(int_budgets[fc], len(items))
        if budget >= len(items):
            sampled.extend(items)
        else:
            sampled.extend(rng.sample(items, budget))

    return sampled


# ---------------------------------------------------------------------------
# Per-atom verification
# ---------------------------------------------------------------------------


def verify_fault_atoms(
    flc: FaultLayerConfig,
    get_env: Callable[[], Any],
    get_db: Callable[[], Any],
    sample_size: int = 1,
    seed: int = 42,
) -> list[str]:
    """Per-atom golden path verification for FaultLayerConfigs.

    For each (layer, sampled entity, atom) triple with init+check:
      1. Run base init + atom init → verify atom check FAILS (fault injected)
      2. Run base init + atom init + atom fix + sync → verify atom check PASSES

    Catches broken init→fix→check chains at the atomic level.
    Runs once per (layer, sample_entity) — not per task — so cost is
    O(layers × sample_size).

    Args:
        flc: The FaultLayerConfig to verify.
        get_env: Factory returning a fresh Environment.
        get_db: Factory returning the domain DB.
        sample_size: Number of entities to sample per layer (default 1).
        seed: Random seed for entity sampling.

    Returns:
        List of issue strings (empty if all atoms pass).
    """
    from tau2.data_model.tasks import EnvAssertion

    issues: list[str] = []
    rng = random.Random(seed)

    db = get_db()
    entities = flc.entity_query(db)

    for group in flc.groups:
        for layer in group.layers:
            if not layer.atoms:
                continue

            # Sample entities that pass this layer's predicate
            eligible = [e for e in entities if _check_predicate(layer, e)]
            if not eligible:
                continue
            sampled = rng.sample(eligible, min(sample_size, len(eligible)))

            for entity in sampled:
                entity_fields = _entity_to_fields(entity)
                eid = entity_fields.get(flc.entity_id_field or "id", "?")

                for atom_idx, atom in enumerate(layer.atoms):
                    if atom.check is None:
                        continue  # No check to verify

                    # Build resolved components
                    base_inits = _resolve_init_calls(
                        flc.base_init_calls, entity_fields
                    )
                    atom_inits = _resolve_init_calls(
                        atom.get_init_list(), entity_fields
                    )
                    check = EnvAssertion(
                        env_type=atom.check.env_type,
                        func_name=atom.check.func_name,
                        arguments=_resolve_args(atom.check.args, entity_fields),
                        assert_value=atom.check.assert_value,
                    )

                    label = (
                        f"atom {atom_idx} (fix={atom.fix.tool_name}) "
                        f"in layer '{layer.name}' (entity={eid})"
                    )

                    # Step 1: init → check should FAIL (fault was injected)
                    if atom.init is not None:
                        env = get_env()
                        env.set_state(
                            initialization_data=None,
                            initialization_actions=base_inits + atom_inits,
                            message_history=[],
                        )
                        try:
                            result = env.run_env_assertion(
                                check, raise_assertion_error=False
                            )
                        except Exception as e:
                            issues.append(
                                f"ERROR: {label}: check raised after init: {e}"
                            )
                            continue

                        if result:
                            issues.append(
                                f"ERROR: {label}: check "
                                f"'{atom.check.func_name}' PASSES after init — "
                                f"init doesn't break what check verifies"
                            )

                    # Step 2: init + fix → check should PASS
                    env = get_env()
                    env.set_state(
                        initialization_data=None,
                        initialization_actions=base_inits + atom_inits,
                        message_history=[],
                    )
                    fix_args = _resolve_args(atom.fix.args, entity_fields)
                    try:
                        env.make_tool_call(
                            atom.fix.tool_name,
                            requestor=atom.fix.requestor,
                            **fix_args,
                        )
                        env.sync_tools()
                    except Exception as e:
                        issues.append(f"ERROR: {label}: fix raised: {e}")
                        continue

                    try:
                        result = env.run_env_assertion(
                            check, raise_assertion_error=False
                        )
                    except Exception as e:
                        issues.append(
                            f"ERROR: {label}: check raised after fix: {e}"
                        )
                        continue

                    if not result:
                        issues.append(
                            f"ERROR: {label}: check "
                            f"'{atom.check.func_name}' FAILS after fix — "
                            f"fix doesn't repair what check verifies"
                        )

    # Print summary
    if issues:
        print(f"\nAtom verification: {len(issues)} issues found")
        for issue in issues:
            print(f"  - {issue}")
    else:
        atom_count = sum(
            len(layer.atoms)
            for group in flc.groups
            for layer in group.layers
        )
        print(f"\nAtom verification: all {atom_count} atoms passed")

    return issues


def verify_completion_fragments(
    flc: FaultLayerConfig,
) -> list[str]:
    """Validate completion_fragment on all layers.

    Checks:
      1. Every fixable layer with atoms MUST have a non-empty completion_fragment.
         This is the contractual link between the user sim's stop condition and
         the task's actual success criteria.  Missing = the user sim has no
         task-specific stop condition.
      2. Every unfixable layer MUST have a non-empty completion_fragment.
         Without one, transfer tasks fall back to a generic "when the agent
         confirms all problems have been addressed" instruction that causes
         infinite loops — the user sim never accepts the transfer.
      3. completion_fragment must NOT contain frame sentences — the framework
         adds "You will consider your issues resolved when ...".

    Returns:
        List of issue strings (empty if all layers pass).
    """
    issues: list[str] = []

    frame_phrases = [
        "you will consider",
        "follow the agent",
        "when the agent asks you to perform",
        "you must actually call the tool",
    ]
    for group in flc.groups:
        for layer in group.layers:
            label = f"layer '{layer.name}'"

            # Check 1: fixable layers with atoms must have completion_fragment
            if not layer.unfixable and layer.atoms:
                if not layer.completion_fragment:
                    issues.append(
                        f"ERROR: {label}: fixable layer with atoms has no "
                        f"completion_fragment. The user sim needs a "
                        f"task-specific stop condition tied to the fault's "
                        f"observable resolution."
                    )

            # Check 2: unfixable layers must have completion_fragment
            if layer.unfixable:
                if not layer.completion_fragment:
                    issues.append(
                        f"ERROR: {label}: unfixable layer has no "
                        f"completion_fragment. Without one, transfer tasks "
                        f"fall back to a generic stop condition that causes "
                        f"infinite loops. Set it to describe what 'fixed' "
                        f"would look like (e.g. 'your router is back online') "
                        f"— an impossible goal the agent cannot achieve, "
                        f"forcing it to decide to transfer on its own."
                    )

            # Check 3: completion_fragment should not include frame sentences
            if layer.completion_fragment:
                cf_lower = layer.completion_fragment.lower()
                for phrase in frame_phrases:
                    if phrase in cf_lower:
                        issues.append(
                            f"WARNING: {label}: completion_fragment contains "
                            f"frame phrase '{phrase}'. Write only the "
                            f"half-sentence (e.g. 'your speed test shows "
                            f"excellent results'), not the frame — the "
                            f"framework adds 'You will consider your issues "
                            f"resolved when ...' automatically."
                        )
                        break

            # Check 4: unfixable layers must NOT leak the transfer outcome.
            # The fragment should describe an impossible goal (what "fixed"
            # would look like), not the resolution method (transfer/escalate).
            if layer.unfixable and layer.completion_fragment:
                transfer_leak_phrases = [
                    "transferred",
                    "escalated",
                    "specialist",
                    "referred",
                    "referral",
                    "another team",
                    "another department",
                    "higher level",
                    "supervisor",
                    "manager",
                    "transfer",
                    "escalate",
                ]
                for phrase in transfer_leak_phrases:
                    if phrase in cf_lower:
                        issues.append(
                            f"ERROR: {label}: unfixable layer's "
                            f"completion_fragment contains '{phrase}', "
                            f"which leaks the transfer outcome. The user "
                            f"sim should NOT know the issue is unfixable. "
                            f"Use an impossible-goal fragment instead — "
                            f"describe what 'fixed' would look like "
                            f"(e.g. 'your router is back online'). "
                            f"The agent must figure out the issue is "
                            f"unfixable and decide to transfer on its own."
                        )
                        break

    # Print summary
    if issues:
        errors = sum(1 for i in issues if i.startswith("ERROR"))
        warnings = sum(1 for i in issues if i.startswith("WARNING"))
        print(f"\nCompletion fragment verification: {errors} errors, {warnings} warnings")
        for issue in issues:
            print(f"  - {issue}")
    else:
        layer_count = sum(
            len(layer.atoms)
            for group in flc.groups
            for layer in group.layers
            if not layer.unfixable and layer.completion_fragment
        )
        print(f"\nCompletion fragment verification: all layers OK")

    return issues


def verify_resolution_instruction(
    recipe_book: RecipeBook,
) -> list[str]:
    """Validate the resolution_instruction and resolution_category fields.

    Checks:
      1. If resolution_instruction is set, it must be non-empty and not
         contain tool names or frame phrases (the framework adds the frame).
      2. If resolution_instruction is set, every FaultLayerGroup should have
         a resolution_category for coverage verification.
      3. resolution_instruction must cover all distinct resolution_categories
         (heuristic: each category word should appear in the instruction).
      4. resolution_category should not be empty when resolution_instruction
         is set on the RecipeBook.

    Returns:
        List of issue strings (empty if all checks pass).
    """
    issues: list[str] = []

    ri = recipe_book.resolution_instruction.strip()

    if not ri:
        # No resolution_instruction — skip all checks
        return issues

    # Check 1: no frame phrases in resolution_instruction
    frame_phrases = [
        "you will consider",
        "follow the agent",
        "when the agent asks you to perform",
        "you must actually call the tool",
        "issues resolved when",
    ]
    ri_lower = ri.lower()
    for phrase in frame_phrases:
        if phrase in ri_lower:
            issues.append(
                f"WARNING: resolution_instruction contains frame phrase "
                f"'{phrase}'. Write only the outcome description "
                f"(e.g. 'your internet connection is working normally'), "
                f"not the frame — the framework adds 'You will consider "
                f"your issues resolved when ...' automatically."
            )
            break

    # Check 2: collect all resolution_categories and verify coverage
    categories: set[str] = set()
    groups_without_category: list[str] = []

    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            if group.resolution_category:
                categories.add(group.resolution_category)
            else:
                groups_without_category.append(group.name)

    # Check 3: groups should have resolution_category when resolution_instruction is set
    if groups_without_category:
        issues.append(
            f"WARNING: resolution_instruction is set but "
            f"{len(groups_without_category)} group(s) have no "
            f"resolution_category: {groups_without_category[:5]}"
            f"{'...' if len(groups_without_category) > 5 else ''}. "
            f"Add resolution_category to each FaultLayerGroup for "
            f"coverage verification."
        )

    # Check 4: each category should be conceptually covered by the instruction
    # Heuristic: at least one significant word from the category appears in
    # the resolution_instruction
    if categories:
        uncovered: list[str] = []
        for cat in sorted(categories):
            cat_words = {w.lower() for w in cat.replace("_", " ").split() if len(w) > 2}
            if not any(w in ri_lower for w in cat_words):
                uncovered.append(cat)
        if uncovered:
            issues.append(
                f"WARNING: resolution_instruction may not cover these "
                f"resolution_categories: {uncovered}. The instruction "
                f"should describe an outcome that encompasses all "
                f"category types. Current instruction: '{ri[:80]}...'"
            )

    # Print summary
    if issues:
        errors = sum(1 for i in issues if i.startswith("ERROR"))
        warnings = sum(1 for i in issues if i.startswith("WARNING"))
        print(f"\nResolution instruction verification: {errors} errors, {warnings} warnings")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\nResolution instruction verification: OK")

    return issues


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_recipe_tasks(
    recipe_book: RecipeBook,
    build_indexes: Callable[[Any], Any],
    get_db: Callable[[], Any],
    user_template: UserTemplate,
    personas: list[Persona],
    seed: int = 42,
) -> list[Task]:
    """Generate tasks from a RecipeBook.

    Phase 1: Single recipes (do + fix).
    Phase 2: Composed recipes.
    Phase 3: Spec -> Task conversion (one task per persona per spec).
    """
    db = get_db()
    indexes = build_indexes(db)
    tracker = DiversityTracker(seed=seed)
    rng = random.Random(seed)
    div = recipe_book.diversity_config or DiversityConfig()

    all_specs: list[GeneratedTaskSpec] = []

    # Phase 1: Single recipes
    for recipe in recipe_book.recipes:
        entities = recipe.entity_query(indexes)
        if not entities:
            continue

        if div.target_count > 0:
            # Budget mode: allocate proportionally
            rtype = "single_fix" if recipe.fault is not None else "single_do"
            weight = div.type_weights.get(rtype, 0.3)
            budget = max(div.min_per_recipe, int(div.target_count * weight))
            # Sample up to budget entities, coverage-aware
            entity_ids = [
                _get_entity_id(recipe, e, i) for i, e in enumerate(entities)
            ]
            selected_count = min(budget, len(entities))
            selected_ids = set()
            for _ in range(selected_count):
                eid = tracker.sample(recipe.name, entity_ids)
                selected_ids.add(eid)
            # Map back to entities
            id_to_entity = {
                _get_entity_id(recipe, e, i): e for i, e in enumerate(entities)
            }
            selected_entities = [
                id_to_entity[eid] for eid in selected_ids if eid in id_to_entity
            ]
        else:
            selected_entities = entities

        for i, entity in enumerate(selected_entities):
            spec = recipe_to_spec(recipe, entity, i)
            all_specs.append(spec)

    # Phase 2: Composed recipes
    for composed in recipe_book.composed_recipes:
        entity_tuples = composed.entity_query(indexes)
        if not entity_tuples:
            continue

        if div.target_count > 0:
            weight = div.type_weights.get("composed", 0.4)
            budget = max(div.min_per_recipe, int(div.target_count * weight))
            selected_tuples = entity_tuples[:budget]
        else:
            selected_tuples = entity_tuples

        for i, etuple in enumerate(selected_tuples):
            spec = composed_recipe_to_spec(composed, etuple, i)
            all_specs.append(spec)

    # Phase 2.5: Fault layer configs
    for flc in recipe_book.fault_layer_configs:
        flc_specs = _generate_fault_layer_specs(flc, indexes, recipe_book.resolution_instruction)
        all_specs.extend(flc_specs)

    print(
        f"Recipe engine: {len(all_specs)} specs from "
        f"{len(recipe_book.recipes)} recipes + "
        f"{len(recipe_book.composed_recipes)} composed + "
        f"{len(recipe_book.fault_layer_configs)} fault-layer configs"
    )

    # Phase 3: Spec -> Task (one task per persona per spec)
    tasks: list[Task] = []
    for spec in all_specs:
        for persona in personas:
            task = _spec_to_task(spec, user_template, persona)
            tasks.append(task)

    print(f"Recipe engine: {len(tasks)} tasks generated")
    return tasks
