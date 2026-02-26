"""Tests for the recipe engine."""

import unittest
from unittest.mock import MagicMock, patch

from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall
from tau2.generators.entity_engine import GeneratedTaskSpec, TaskTier
from tau2.generators.recipe import (
    ActionSpec,
    AssertionSpec,
    ComposedRecipe,
    DiversityConfig,
    Fault,
    FaultLayer,
    FaultLayerConfig,
    FaultLayerGroup,
    InitCall,
    Recipe,
    RecipeBook,
    _bin_sample,
    _check_predicate,
    _entity_to_fields,
    _fault_layers_to_spec,
    _generate_fault_layer_specs,
    _get_entity_id,
    _proportional_sample,
    _resolve_args,
    _validate_resource_scopes,
    composed_recipe_to_spec,
    generate_recipe_tasks,
    recipe_to_spec,
)
from tau2.generators.types import Persona, UserTemplate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_entity(**kwargs):
    """Create a simple dict entity."""
    defaults = {"id": "E001", "name": "Alice", "balance": 100.0}
    defaults.update(kwargs)
    return defaults


def _make_recipe(
    name="test_recipe",
    fault=None,
    compare_args_map=None,
    entity_id_field=None,
    nl_templates=None,
):
    return Recipe(
        name=name,
        entity_query=lambda idx: [_make_entity()],
        goal_actions=[
            ActionSpec(
                tool_name="update_balance",
                args={"account_id": "{id}", "amount": "{balance}"},
            ),
        ],
        post_assertions=[
            AssertionSpec(
                func_name="assert_balance",
                args={"account_id": "{id}", "expected": "{balance}"},
                message_template="Balance for {name} should be {balance}",
            ),
        ],
        known_info_template="Account {id} for {name}",
        ticket_template="Update balance for {name} to {balance}",
        reason_for_call="Balance update needed",
        purpose="Test balance update",
        fault=fault,
        compare_args_map=compare_args_map,
        entity_id_field=entity_id_field,
        nl_assertion_templates=nl_templates or [],
    )


def _make_user_template():
    return UserTemplate(
        domain="test",
        reason_for_call="Testing",
        known_info="Test info",
        task_instructions="Do the thing",
        ticket="Test ticket",
        purpose="Test purpose",
    )


def _make_personas():
    return [
        Persona(name="friendly", description="A friendly user"),
        Persona(name="impatient", description="An impatient user"),
    ]


# ---------------------------------------------------------------------------
# TestRecipeToSpec
# ---------------------------------------------------------------------------


class TestRecipeToSpec(unittest.TestCase):
    def test_do_recipe_no_fault(self):
        """fault=None -> empty init_actions, actions/assertions populated."""
        recipe = _make_recipe()
        entity = _make_entity()
        spec = recipe_to_spec(recipe, entity)

        self.assertEqual(spec.init_actions, [])
        self.assertEqual(len(spec.actions), 1)
        self.assertEqual(spec.actions[0]["name"], "update_balance")
        self.assertEqual(len(spec.env_assertions), 1)
        self.assertEqual(spec.env_assertions[0].func_name, "assert_balance")

    def test_fix_recipe_with_fault(self):
        """fault set -> init_actions from fault.init_calls."""
        fault = Fault(init_calls=[
            InitCall(env_type="user", func_name="break_balance", args={"account_id": "{id}"}),
        ])
        recipe = _make_recipe(fault=fault)
        entity = _make_entity()
        spec = recipe_to_spec(recipe, entity)

        self.assertEqual(len(spec.init_actions), 1)
        self.assertEqual(spec.init_actions[0].func_name, "break_balance")
        self.assertEqual(spec.init_actions[0].arguments["account_id"], "E001")

    def test_template_formatting(self):
        """known_info/ticket templates format from entity fields."""
        recipe = _make_recipe()
        entity = _make_entity(id="X42", name="Bob", balance=200.0)
        spec = recipe_to_spec(recipe, entity)

        self.assertEqual(spec.known_info, "Account X42 for Bob")
        self.assertEqual(spec.description, "Update balance for Bob to 200.0")

    def test_entity_id_from_field(self):
        """Custom entity_id_field used in task_id."""
        recipe = _make_recipe(entity_id_field="name")
        entity = _make_entity(name="Carol")
        spec = recipe_to_spec(recipe, entity)

        self.assertEqual(spec.task_id, "test_recipe_Carol")

    def test_entity_id_fallback(self):
        """Falls back to common field names (id)."""
        recipe = _make_recipe()
        entity = _make_entity(id="ACC99")
        spec = recipe_to_spec(recipe, entity)

        self.assertEqual(spec.task_id, "test_recipe_ACC99")

    def test_compare_args_precedence(self):
        """ActionSpec.compare_args > recipe.compare_args_map."""
        # ActionSpec level wins
        recipe = _make_recipe(compare_args_map={"update_balance": ["amount"]})
        recipe.goal_actions[0].compare_args = ["account_id"]
        entity = _make_entity()
        spec = recipe_to_spec(recipe, entity)
        self.assertEqual(spec.actions[0]["compare_args"], ["account_id"])

        # Recipe map level used when ActionSpec is None
        recipe2 = _make_recipe(compare_args_map={"update_balance": ["amount"]})
        entity2 = _make_entity()
        spec2 = recipe_to_spec(recipe2, entity2)
        self.assertEqual(spec2.actions[0]["compare_args"], ["amount"])

    def test_nl_assertions_formatted(self):
        """Templates produce strings with entity values."""
        recipe = _make_recipe(nl_templates=["{name} has balance {balance}"])
        entity = _make_entity(name="Dan", balance=50.0)
        spec = recipe_to_spec(recipe, entity)

        self.assertEqual(spec.nl_assertions, ["Dan has balance 50.0"])



# ---------------------------------------------------------------------------
# TestComposedRecipeToSpec
# ---------------------------------------------------------------------------


class TestComposedRecipeToSpec(unittest.TestCase):
    def _make_step(self, name, tool_name, fault=None):
        return Recipe(
            name=name,
            entity_query=lambda idx: [],
            goal_actions=[
                ActionSpec(
                    tool_name=tool_name,
                    args={"id": "{id}"},
                ),
            ],
            post_assertions=[
                AssertionSpec(
                    func_name=f"assert_{tool_name}",
                    args={"id": "{id}"},
                ),
            ],
            known_info_template="Step info for {id}",
            ticket_template="Step ticket for {id}",
            reason_for_call="Step reason",
            purpose="Step purpose",
            fault=fault,
        )

    def _make_composed(self, steps):
        return ComposedRecipe(
            name="composed_test",
            steps=steps,
            entity_query=lambda idx: [],
            known_info_template="Combined: {step0_name} and {step1_name}",
            ticket_template="Do {step0_id} then {step1_id}",
            reason_for_call="Multi-step",
            purpose="Composed purpose",
        )

    def test_two_step_composition(self):
        """Actions/assertions concatenated from both steps."""
        steps = [self._make_step("s1", "tool_a"), self._make_step("s2", "tool_b")]
        composed = self._make_composed(steps)
        entities = (
            {"id": "A1", "name": "Alice"},
            {"id": "B2", "name": "Bob"},
        )
        spec = composed_recipe_to_spec(composed, entities)

        self.assertEqual(len(spec.actions), 2)
        self.assertEqual(spec.actions[0]["name"], "tool_a")
        self.assertEqual(spec.actions[0]["action_id"], "0")
        self.assertEqual(spec.actions[1]["name"], "tool_b")
        self.assertEqual(spec.actions[1]["action_id"], "1")
        self.assertEqual(len(spec.env_assertions), 2)

    def test_init_actions_merged(self):
        """Both faults' init_calls present."""
        steps = [
            self._make_step("s1", "tool_a", fault=Fault(init_calls=[
                InitCall(env_type="user", func_name="break_a", args={"x": 1}),
            ])),
            self._make_step("s2", "tool_b", fault=Fault(init_calls=[
                InitCall(env_type="user", func_name="break_b", args={"y": 2}),
            ])),
        ]
        composed = self._make_composed(steps)
        entities = ({"id": "A1", "name": "X"}, {"id": "B2", "name": "Y"})
        spec = composed_recipe_to_spec(composed, entities)

        self.assertEqual(len(spec.init_actions), 2)
        func_names = {a.func_name for a in spec.init_actions}
        self.assertIn("break_a", func_names)
        self.assertIn("break_b", func_names)

    def test_combined_fields(self):
        """step0_X and step1_X available in templates."""
        steps = [self._make_step("s1", "tool_a"), self._make_step("s2", "tool_b")]
        composed = self._make_composed(steps)
        entities = (
            {"id": "A1", "name": "Alice"},
            {"id": "B2", "name": "Bob"},
        )
        spec = composed_recipe_to_spec(composed, entities)

        self.assertEqual(spec.known_info, "Combined: Alice and Bob")
        self.assertEqual(spec.description, "Do A1 then B2")

    def test_mismatched_steps_raises(self):
        """len(steps) != len(tuple) -> AssertionError."""
        steps = [self._make_step("s1", "tool_a")]
        composed = self._make_composed(steps)
        # Give 2 entities for 1 step
        with self.assertRaises(AssertionError):
            composed_recipe_to_spec(composed, ({"id": "A"}, {"id": "B"}))


# ---------------------------------------------------------------------------
# TestGenerateRecipeTasks
# ---------------------------------------------------------------------------


class TestGenerateRecipeTasks(unittest.TestCase):
    def _make_book(self, n_entities=3, with_fault=False, composed=False):
        entities = [_make_entity(id=f"E{i:03d}", name=f"User{i}") for i in range(n_entities)]

        recipe = Recipe(
            name="single",
            entity_query=lambda idx, ents=entities: ents,
            goal_actions=[
                ActionSpec(
                    tool_name="do_thing",
                    args={"id": "{id}"},
                ),
            ],
            post_assertions=[
                AssertionSpec(
                    func_name="assert_thing",
                    args={"id": "{id}"},
                ),
            ],
            known_info_template="Info for {id}",
            ticket_template="Ticket for {name}",
            reason_for_call="Reason",
            purpose="Purpose",
            fault=Fault(init_calls=[
                InitCall(env_type="user", func_name="break_it", args={"id": "{id}"}),
            ]) if with_fault else None,
        )

        book = RecipeBook(recipes=[recipe])

        if composed:
            pairs = [(entities[i], entities[(i + 1) % len(entities)]) for i in range(len(entities))]
            step_a = Recipe(
                name="step_a",
                entity_query=lambda idx: [],
                goal_actions=[ActionSpec(tool_name="act_a", args={"id": "{id}"})],
                post_assertions=[AssertionSpec(func_name="check_a", args={"id": "{id}"})],
                known_info_template="A: {id}",
                ticket_template="A ticket {id}",
                reason_for_call="A reason",
                purpose="A purpose",
            )
            step_b = Recipe(
                name="step_b",
                entity_query=lambda idx: [],
                goal_actions=[ActionSpec(tool_name="act_b", args={"id": "{id}"})],
                post_assertions=[AssertionSpec(func_name="check_b", args={"id": "{id}"})],
                known_info_template="B: {id}",
                ticket_template="B ticket {id}",
                reason_for_call="B reason",
                purpose="B purpose",
            )
            comp = ComposedRecipe(
                name="comp",
                steps=[step_a, step_b],
                entity_query=lambda idx, p=pairs: p,
                known_info_template="Composed: {step0_id} + {step1_id}",
                ticket_template="Composed ticket",
                reason_for_call="Composed reason",
                purpose="Composed purpose",
            )
            book.composed_recipes = [comp]

        return book

    def test_all_entities_when_no_budget(self):
        """target_count=0 uses every entity."""
        book = self._make_book(n_entities=5)
        tasks = generate_recipe_tasks(
            recipe_book=book,
            build_indexes=lambda db: db,
            get_db=lambda: {},
            user_template=_make_user_template(),
            personas=_make_personas(),
        )
        self.assertEqual(len(tasks), 10)  # 5 entities * 2 personas

    def test_diversity_tracking(self):
        """Entities used across tasks (basic check that all show up)."""
        book = self._make_book(n_entities=4)
        tasks = generate_recipe_tasks(
            recipe_book=book,
            build_indexes=lambda db: db,
            get_db=lambda: {},
            user_template=_make_user_template(),
            personas=_make_personas(),
        )
        # Each entity should produce 2 tasks (one per persona)
        self.assertEqual(len(tasks), 8)
        # Each entity ID appears in exactly 2 task IDs
        task_ids = [t.id for t in tasks]
        self.assertEqual(len(set(task_ids)), 8)

    def test_deterministic_seed(self):
        """Same seed -> identical output."""
        book = self._make_book(n_entities=4)
        kwargs = dict(
            recipe_book=book,
            build_indexes=lambda db: db,
            get_db=lambda: {},
            user_template=_make_user_template(),
            personas=_make_personas(),
            seed=123,
        )
        tasks1 = generate_recipe_tasks(**kwargs)
        tasks2 = generate_recipe_tasks(**kwargs)
        ids1 = [t.id for t in tasks1]
        ids2 = [t.id for t in tasks2]
        self.assertEqual(ids1, ids2)

    def test_mixed_book(self):
        """RecipeBook with single + composed recipes."""
        book = self._make_book(n_entities=3, composed=True)
        tasks = generate_recipe_tasks(
            recipe_book=book,
            build_indexes=lambda db: db,
            get_db=lambda: {},
            user_template=_make_user_template(),
            personas=_make_personas(),
        )
        # (3 single + 3 composed) * 2 personas = 12
        self.assertEqual(len(tasks), 12)


# ---------------------------------------------------------------------------
# TestEntityToFields
# ---------------------------------------------------------------------------


class TestEntityToFields(unittest.TestCase):
    def test_dict_passthrough(self):
        self.assertEqual(_entity_to_fields({"a": 1}), {"a": 1})

    def test_pydantic_model(self):
        from pydantic import BaseModel

        class M(BaseModel):
            x: int = 5

        self.assertEqual(_entity_to_fields(M())["x"], 5)


# ---------------------------------------------------------------------------
# TestDomainConfigIntegration
# ---------------------------------------------------------------------------


class TestDomainConfigIntegration(unittest.TestCase):
    def test_recipe_strategy_dispatches(self):
        """RECIPE strategy calls generate_recipe_tasks."""
        from tau2.generators.domain_config import (
            DomainConfig,
            GenerationStrategy,
            create_domain_tasks,
        )

        book = RecipeBook(
            recipes=[
                Recipe(
                    name="test_r",
                    entity_query=lambda idx: [{"id": "T1", "name": "Test"}],
                    goal_actions=[
                        ActionSpec(
                            tool_name="do_it",
                            args={"id": "{id}"},
                        ),
                    ],
                    post_assertions=[
                        AssertionSpec(
                            func_name="check_it",
                            args={"id": "{id}"},
                        ),
                    ],
                    known_info_template="Info {id}",
                    ticket_template="Ticket {name}",
                    reason_for_call="Reason",
                    purpose="Purpose",
                ),
            ]
        )

        config = DomainConfig(
            strategy=GenerationStrategy.RECIPE,
            user_template=_make_user_template(),
            personas=_make_personas(),
            recipe_book=book,
            build_indexes=lambda db: db,
            get_db=lambda: {},
            verify=False,  # skip verification (no real env)
        )

        tasks = create_domain_tasks(config)
        self.assertEqual(len(tasks), 2)  # 1 spec * 2 personas
        self.assertIn("test_r_T1", tasks[0].id)

    def test_missing_recipe_book_raises(self):
        """recipe_book=None -> AssertionError."""
        from tau2.generators.domain_config import (
            DomainConfig,
            GenerationStrategy,
            create_domain_tasks,
        )

        config = DomainConfig(
            strategy=GenerationStrategy.RECIPE,
            user_template=_make_user_template(),
            personas=_make_personas(),
            build_indexes=lambda db: db,
            get_db=lambda: {},
            verify=False,
        )

        with self.assertRaises(AssertionError):
            create_domain_tasks(config)


# ---------------------------------------------------------------------------
# TestFaultLayersToSpec
# ---------------------------------------------------------------------------


def _make_fault_entity(**kwargs):
    """Create an entity dict for fault-layer tests."""
    defaults = {
        "id": "P001",
        "name": "Alice",
        "book_id": "B001",
        "book_title": "Test Book",
    }
    defaults.update(kwargs)
    return defaults


def _make_fault_layer(name="test_fault", predicate_field=None, predicate_ne=None, communicate=None, nl=None, resource_scope=True):
    """Create a simple FaultLayer for testing.

    resource_scope=True (default) auto-generates a scope from the name.
    resource_scope=None disables it. resource_scope=string uses it directly.
    """
    if resource_scope is True:
        _scope = f"{name}:{{id}}"
    else:
        _scope = resource_scope
    return FaultLayer(
        name=name,
        init_calls=[
            InitCall(
                env_type="assistant",
                func_name=f"break_{name}",
                args={"id": "{id}"},
            ),
        ],
        actions=[
            ActionSpec(
                tool_name=f"fix_{name}",
                args={"id": "{id}"},
            ),
        ],
        assertions=[
            AssertionSpec(
                func_name=f"assert_{name}_fixed",
                args={"id": "{id}"},
            ),
        ],
        known_info_fragment=f"I have a {name} problem",
        communicate_templates=communicate or [],
        nl_assertion_templates=nl or [],
        predicate_field=predicate_field,
        predicate_ne=predicate_ne,
        resource_scope=_scope,
    )


def _make_fault_layer_config(
    groups=None,
    min_faults=1,
    max_faults=99,
    entity_query=None,
    base_communicate=None,
    base_nl=None,
):
    """Create a FaultLayerConfig for testing."""
    if groups is None:
        groups = [
            FaultLayerGroup(name="g1", layers=[_make_fault_layer("fault_a")]),
            FaultLayerGroup(name="g2", layers=[_make_fault_layer("fault_b")]),
        ]
    return FaultLayerConfig(
        name="test_config",
        entity_query=entity_query or (lambda idx: [_make_fault_entity()]),
        groups=groups,
        base_init_calls=[
            InitCall(
                env_type="user",
                func_name="set_identity",
                args={"name": "{name}"},
            ),
        ],
        base_known_info_template="I'm {name}. {fault_descriptions}.",
        base_ticket_template="Fix for {name}: {fault_descriptions}.",
        reason_for_call="Need help",
        purpose="Test purpose",
        base_communicate_templates=base_communicate or [],
        base_nl_assertion_templates=base_nl or [],
        entity_id_field="id",
        min_faults=min_faults,
        max_faults=max_faults,
    )


class TestFaultLayersToSpec(unittest.TestCase):
    def test_single_fault(self):
        """Single active fault -> correct init, actions, assertions."""
        layer = _make_fault_layer("fault_a")
        flc = _make_fault_layer_config(min_faults=1)
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer])

        # Init: 1 base + 1 fault
        self.assertEqual(len(spec.init_actions), 2)
        self.assertEqual(spec.init_actions[0].func_name, "set_identity")
        self.assertEqual(spec.init_actions[1].func_name, "break_fault_a")

        # 1 action
        self.assertEqual(len(spec.actions), 1)
        self.assertEqual(spec.actions[0]["name"], "fix_fault_a")

        # 1 assertion
        self.assertEqual(len(spec.env_assertions), 1)
        self.assertEqual(spec.env_assertions[0].func_name, "assert_fault_a_fixed")

        # Tier
        self.assertEqual(spec.tier, TaskTier.TIER_3)

    def test_two_faults(self):
        """Two active faults -> tier 4, both actions concatenated."""
        layer_a = _make_fault_layer("fault_a")
        layer_b = _make_fault_layer("fault_b")
        flc = _make_fault_layer_config()
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer_a, layer_b])

        self.assertEqual(len(spec.actions), 2)
        self.assertEqual(spec.actions[0]["name"], "fix_fault_a")
        self.assertEqual(spec.actions[1]["name"], "fix_fault_b")
        self.assertEqual(spec.tier, TaskTier.TIER_4)

    def test_three_faults_tier5(self):
        """Three+ active faults -> tier 5."""
        layers = [_make_fault_layer(f"f{i}") for i in range(3)]
        flc = _make_fault_layer_config()
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, layers)

        self.assertEqual(spec.tier, TaskTier.TIER_5)

    def test_known_info_formatting(self):
        """Fault descriptions joined and formatted into known_info."""
        layer_a = _make_fault_layer("fault_a")
        layer_b = _make_fault_layer("fault_b")
        flc = _make_fault_layer_config()
        entity = _make_fault_entity(name="Bob")
        spec = _fault_layers_to_spec(flc, entity, [layer_a, layer_b])

        self.assertIn("Bob", spec.known_info)
        self.assertIn("fault_a problem", spec.known_info)
        self.assertIn("fault_b problem", spec.known_info)

    def test_task_id_includes_layers_and_entity(self):
        """Task ID has config name, layer names, and entity ID."""
        layer = _make_fault_layer("fault_a")
        flc = _make_fault_layer_config()
        entity = _make_fault_entity(id="X42")
        spec = _fault_layers_to_spec(flc, entity, [layer])

        self.assertEqual(spec.task_id, "test_config_fault_a_X42")

    def test_task_id_multiple_layers(self):
        """Multiple layers joined with | in task ID."""
        layers = [_make_fault_layer("a"), _make_fault_layer("b")]
        flc = _make_fault_layer_config()
        entity = _make_fault_entity(id="E1")
        spec = _fault_layers_to_spec(flc, entity, layers)

        self.assertEqual(spec.task_id, "test_config_a|b_E1")

    def test_communicate_info(self):
        """Communicate templates from layers + base are formatted."""
        layer = _make_fault_layer("fault_a", communicate=["{book_title}"])
        flc = _make_fault_layer_config(
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            base_communicate=["hello {name}"],
            min_faults=1,
        )
        entity = _make_fault_entity(name="Carol", book_title="My Book")
        spec = _fault_layers_to_spec(flc, entity, [layer])

        self.assertEqual(spec.communicate_info, ["My Book", "hello Carol"])

    def test_nl_assertions(self):
        """NL assertion templates from layers + base are formatted."""
        layer = _make_fault_layer("fault_a", nl=["Check {name}"])
        flc = _make_fault_layer_config(
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            base_nl=["Verify identity"],
            min_faults=1,
        )
        entity = _make_fault_entity(name="Dan")
        spec = _fault_layers_to_spec(flc, entity, [layer])

        self.assertEqual(spec.nl_assertions, ["Check Dan", "Verify identity"])



class TestGenerateFaultLayerSpecs(unittest.TestCase):
    def test_cartesian_product(self):
        """Two groups with 1 layer each + min_faults=2 → 1 combo."""
        flc = _make_fault_layer_config(min_faults=2)
        specs = _generate_fault_layer_specs(flc, None)

        self.assertEqual(len(specs), 1)
        self.assertEqual(len(specs[0].actions), 2)

    def test_min_faults_filters(self):
        """min_faults=2 excludes single-fault combos."""
        flc = _make_fault_layer_config(min_faults=2)
        specs = _generate_fault_layer_specs(flc, None)

        # With 2 groups and min_faults=2, only the both-on combo passes
        self.assertEqual(len(specs), 1)

    def test_min_faults_1_includes_singles(self):
        """min_faults=1 includes single-fault combos."""
        flc = _make_fault_layer_config(min_faults=1)
        specs = _generate_fault_layer_specs(flc, None)

        # 2 groups: (a,None) × (b,None) = 4 combos
        # Filter ≥1: a+None, None+b, a+b = 3
        self.assertEqual(len(specs), 3)

    def test_max_faults_filters(self):
        """max_faults=1 excludes multi-fault combos."""
        flc = _make_fault_layer_config(min_faults=1, max_faults=1)
        specs = _generate_fault_layer_specs(flc, None)

        # Only single-fault combos: a, b
        self.assertEqual(len(specs), 2)

    def test_predicate_filters_layers(self):
        """Layers with failing predicate excluded for that entity."""
        layer_a = _make_fault_layer("a")
        layer_b = _make_fault_layer("b", predicate_field="has_b")
        groups = [
            FaultLayerGroup(name="g1", layers=[layer_a]),
            FaultLayerGroup(name="g2", layers=[layer_b]),
        ]
        flc = _make_fault_layer_config(groups=groups, min_faults=1)

        # Entity WITHOUT has_b: layer_b predicate fails
        specs = _generate_fault_layer_specs(flc, None)
        # g1: [a, None], g2: [None] (b excluded)
        # Combos ≥1: just (a, None) = 1
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].task_id, "test_config_a_P001")

    def test_predicate_passes(self):
        """Layers with passing predicate included."""
        layer_a = _make_fault_layer("a")
        layer_b = _make_fault_layer("b", predicate_field="has_b")
        groups = [
            FaultLayerGroup(name="g1", layers=[layer_a]),
            FaultLayerGroup(name="g2", layers=[layer_b]),
        ]
        flc = _make_fault_layer_config(
            groups=groups,
            min_faults=1,
            entity_query=lambda idx: [_make_fault_entity(has_b=True)],
        )

        specs = _generate_fault_layer_specs(flc, None)
        # Both layers applicable: 3 combos (a, b, a+b)
        self.assertEqual(len(specs), 3)

    def test_multiple_entities(self):
        """Multiple entities each get all valid combos."""
        entities = [
            _make_fault_entity(id="E1", name="A"),
            _make_fault_entity(id="E2", name="B"),
        ]
        flc = _make_fault_layer_config(
            min_faults=1,
            entity_query=lambda idx, e=entities: e,
        )
        specs = _generate_fault_layer_specs(flc, None)

        # 3 combos per entity × 2 entities = 6
        self.assertEqual(len(specs), 6)

    def test_integration_with_generate_recipe_tasks(self):
        """FaultLayerConfig specs included in generate_recipe_tasks output."""
        entities = [_make_fault_entity(id="E1")]
        flc = _make_fault_layer_config(
            min_faults=1,
            entity_query=lambda idx, e=entities: e,
        )
        book = RecipeBook(fault_layer_configs=[flc])
        tasks = generate_recipe_tasks(
            recipe_book=book,
            build_indexes=lambda db: db,
            get_db=lambda: {},
            user_template=_make_user_template(),
            personas=_make_personas(),
        )
        # 3 specs from fault layers * 2 personas = 6
        self.assertEqual(len(tasks), 6)


class TestUnfixableLayers(unittest.TestCase):
    """Tests for the unfixable FaultLayer feature."""

    def test_unfixable_layer_generates_transfer(self):
        """A single unfixable layer → transfer_to_human action, empty assertions."""
        layer = FaultLayer(
            name="lost_item",
            unfixable=True,
            init_calls=[
                InitCall(
                    env_type="assistant",
                    func_name="set_item_lost",
                    args={"id": "{id}"},
                ),
            ],
            actions=[],
            assertions=[],
            known_info_fragment="my item is marked as lost",
            resource_scope="item:{id}",
        )
        groups = [FaultLayerGroup(name="g1", layers=[layer])]
        flc = _make_fault_layer_config(groups=groups, min_faults=1)
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer])

        # Should have a single transfer_to_human action
        self.assertEqual(len(spec.actions), 1)
        self.assertEqual(spec.actions[0]["name"], "transfer_to_human")
        self.assertEqual(spec.actions[0]["compare_args"], [])

        # Should have empty assertions
        self.assertEqual(len(spec.env_assertions), 0)

    def test_unfixable_mixed_combo(self):
        """Combo with fixable + unfixable layers → entire combo becomes transfer_to_human."""
        fixable = _make_fault_layer("fixable_fault")
        unfixable = FaultLayer(
            name="unfixable_fault",
            unfixable=True,
            init_calls=[
                InitCall(
                    env_type="assistant",
                    func_name="break_unfixable",
                    args={"id": "{id}"},
                ),
            ],
            actions=[],
            assertions=[],
            known_info_fragment="something unfixable happened",
            resource_scope="unfixable:{id}",
        )
        groups = [
            FaultLayerGroup(name="g1", layers=[fixable]),
            FaultLayerGroup(name="g2", layers=[unfixable]),
        ]
        flc = _make_fault_layer_config(groups=groups, min_faults=2)
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [fixable, unfixable])

        # Fixable actions should be dropped — only transfer_to_human
        self.assertEqual(len(spec.actions), 1)
        self.assertEqual(spec.actions[0]["name"], "transfer_to_human")

        # No assertions
        self.assertEqual(len(spec.env_assertions), 0)

    def test_all_fixable_unchanged(self):
        """Combos with no unfixable layers behave as before."""
        layer_a = _make_fault_layer("fault_a")
        layer_b = _make_fault_layer("fault_b")
        flc = _make_fault_layer_config()
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer_a, layer_b])

        # Normal fixable behavior
        self.assertEqual(len(spec.actions), 2)
        self.assertEqual(spec.actions[0]["name"], "fix_fault_a")
        self.assertEqual(spec.actions[1]["name"], "fix_fault_b")
        self.assertEqual(len(spec.env_assertions), 2)

    def test_unfixable_validation_actions(self):
        """unfixable=True with non-empty actions raises ValueError."""
        bad_layer = FaultLayer(
            name="bad_unfixable",
            unfixable=True,
            init_calls=[],
            actions=[ActionSpec(tool_name="should_not_exist")],
            assertions=[],
            known_info_fragment="bad layer",
        )
        groups = [FaultLayerGroup(name="g1", layers=[bad_layer])]
        flc = _make_fault_layer_config(groups=groups, min_faults=1)

        with self.assertRaises(ValueError) as ctx:
            _generate_fault_layer_specs(flc, None)
        self.assertIn("must have empty actions=[]", str(ctx.exception))

    def test_unfixable_preservation_assertions_allowed(self):
        """unfixable=True with assertions is allowed (preservation checks)."""
        layer = FaultLayer(
            name="unfixable_with_assert",
            unfixable=True,
            init_calls=[
                InitCall(
                    env_type="assistant",
                    func_name="break_something",
                    args={"id": "{id}"},
                ),
            ],
            assertions=[AssertionSpec(
                func_name="assert_still_broken",
                args={"id": "{id}"},
                env_type="assistant",
            )],
            known_info_fragment="something is unfixable",
        )
        groups = [FaultLayerGroup(name="g1", layers=[layer])]
        flc = _make_fault_layer_config(groups=groups, min_faults=1)

        specs = _generate_fault_layer_specs(flc, None)
        self.assertTrue(len(specs) > 0)
        # Transfer task should include the preservation assertion
        spec = specs[0]
        self.assertEqual(len(spec.env_assertions), 1)
        self.assertEqual(spec.env_assertions[0].func_name, "assert_still_broken")

    def test_unfixable_init_calls_preserved(self):
        """Init calls from all layers (fixable + unfixable) still execute."""
        fixable = _make_fault_layer("fixable_fault")
        unfixable = FaultLayer(
            name="unfixable_fault",
            unfixable=True,
            init_calls=[
                InitCall(
                    env_type="assistant",
                    func_name="break_unfixable",
                    args={"id": "{id}"},
                ),
            ],
            actions=[],
            assertions=[],
            known_info_fragment="unfixable problem",
            resource_scope="unfixable:{id}",
        )
        groups = [
            FaultLayerGroup(name="g1", layers=[fixable]),
            FaultLayerGroup(name="g2", layers=[unfixable]),
        ]
        flc = _make_fault_layer_config(groups=groups, min_faults=2)
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [fixable, unfixable])

        # Init: 1 base + 1 fixable + 1 unfixable = 3
        self.assertEqual(len(spec.init_actions), 3)
        func_names = [a.func_name for a in spec.init_actions]
        self.assertIn("set_identity", func_names)
        self.assertIn("break_fixable_fault", func_names)
        self.assertIn("break_unfixable", func_names)

    def test_unfixable_known_info_preserved(self):
        """known_info fragments from all layers (including unfixable) are joined."""
        fixable = _make_fault_layer("fixable_fault")
        unfixable = FaultLayer(
            name="unfixable_fault",
            unfixable=True,
            init_calls=[],
            actions=[],
            assertions=[],
            known_info_fragment="also something unfixable",
            resource_scope="unfixable:{id}",
        )
        groups = [
            FaultLayerGroup(name="g1", layers=[fixable]),
            FaultLayerGroup(name="g2", layers=[unfixable]),
        ]
        flc = _make_fault_layer_config(groups=groups, min_faults=2)
        entity = _make_fault_entity(name="Eve")
        spec = _fault_layers_to_spec(flc, entity, [fixable, unfixable])

        self.assertIn("fixable_fault problem", spec.known_info)
        self.assertIn("also something unfixable", spec.known_info)
        self.assertIn("Eve", spec.known_info)


class TestResourceScopeValidation(unittest.TestCase):
    """Tests for resource_scope conflict detection between fault layer groups."""

    def test_overlapping_scopes_across_groups_raises(self):
        """Two layers in DIFFERENT groups with overlapping resource_scope → ValueError."""
        layer_a = FaultLayer(
            name="modify_reservation_room",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_a", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="room was changed",
            resource_scope="reservation:{book_id}",
        )
        layer_b = FaultLayer(
            name="cancel_reservation",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_b", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="reservation cancelled",
            resource_scope="reservation:{book_id}",
        )
        groups = [
            FaultLayerGroup(name="room_issues", layers=[layer_a]),
            FaultLayerGroup(name="status_issues", layers=[layer_b]),
        ]
        flc = _make_fault_layer_config(groups=groups)
        entities = [_make_fault_entity()]

        with self.assertRaises(ValueError) as ctx:
            _validate_resource_scopes(flc, entities)
        self.assertIn("Resource conflict", str(ctx.exception))
        self.assertIn("modify_reservation_room", str(ctx.exception))
        self.assertIn("cancel_reservation", str(ctx.exception))

    def test_overlapping_scopes_within_same_group_ok(self):
        """Two layers in the SAME group with overlapping resource_scope → no error."""
        layer_a = FaultLayer(
            name="modify_reservation_room",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_a", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="room was changed",
            resource_scope="reservation:{book_id}",
        )
        layer_b = FaultLayer(
            name="cancel_reservation",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_b", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="reservation cancelled",
            resource_scope="reservation:{book_id}",
        )
        layer_c = FaultLayer(
            name="other_fault",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_c", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="other issue",
            resource_scope="other:E001",
        )
        groups = [
            FaultLayerGroup(name="reservation_issues", layers=[layer_a, layer_b]),
            FaultLayerGroup(name="other", layers=[layer_c]),
        ]
        flc = _make_fault_layer_config(groups=groups)
        entities = [_make_fault_entity()]

        # Should not raise — same-group layers are mutually exclusive
        _validate_resource_scopes(flc, entities)

    def test_no_resource_scope_skips_validation(self):
        """Layers without resource_scope (None) are not checked."""
        import warnings
        layer_a = _make_fault_layer("a", resource_scope=None)  # no resource_scope
        layer_b = _make_fault_layer("b", resource_scope=None)  # no resource_scope
        groups = [
            FaultLayerGroup(name="g1", layers=[layer_a]),
            FaultLayerGroup(name="g2", layers=[layer_b]),
        ]
        flc = _make_fault_layer_config(groups=groups)
        entities = [_make_fault_entity()]

        # Should not raise (warnings expected for missing scope — that's the point)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _validate_resource_scopes(flc, entities)

    def test_disjoint_scopes_across_groups_ok(self):
        """Two layers in different groups with non-overlapping resource_scope → no error."""
        layer_a = FaultLayer(
            name="first_reservation",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_a", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="first reservation issue",
            resource_scope="reservation:RES001",
        )
        layer_b = FaultLayer(
            name="second_reservation",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_b", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="second reservation issue",
            resource_scope="reservation:RES002",
        )
        groups = [
            FaultLayerGroup(name="g1", layers=[layer_a]),
            FaultLayerGroup(name="g2", layers=[layer_b]),
        ]
        flc = _make_fault_layer_config(groups=groups)
        entities = [_make_fault_entity()]

        # Should not raise — different resource instances
        _validate_resource_scopes(flc, entities)

    def test_predicate_skips_non_applicable_entities(self):
        """Conflict only checked for entities where both layers' predicates pass."""
        layer_a = FaultLayer(
            name="a",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_a", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="a problem",
            resource_scope="shared:X",
            predicate_field="has_a",
        )
        layer_b = FaultLayer(
            name="b",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_b", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="b problem",
            resource_scope="shared:X",
            predicate_field="has_b",
        )
        groups = [
            FaultLayerGroup(name="g1", layers=[layer_a]),
            FaultLayerGroup(name="g2", layers=[layer_b]),
        ]
        flc = _make_fault_layer_config(groups=groups)

        # Entity where only layer_a applies → no conflict possible
        entities = [_make_fault_entity(has_a=True, has_b=False)]
        _validate_resource_scopes(flc, entities)  # should not raise

        # Entity where both apply → conflict!
        entities = [_make_fault_entity(has_a=True, has_b=True)]
        with self.assertRaises(ValueError):
            _validate_resource_scopes(flc, entities)

    def test_generate_fault_layer_specs_calls_validation(self):
        """_generate_fault_layer_specs raises on resource conflict."""
        layer_a = FaultLayer(
            name="a",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_a", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="a problem",
            resource_scope="shared:X",
        )
        layer_b = FaultLayer(
            name="b",
            init_calls=[],
            actions=[ActionSpec(tool_name="fix_b", args={"id": "{id}"})],
            assertions=[],
            known_info_fragment="b problem",
            resource_scope="shared:X",
        )
        groups = [
            FaultLayerGroup(name="g1", layers=[layer_a]),
            FaultLayerGroup(name="g2", layers=[layer_b]),
        ]
        flc = _make_fault_layer_config(groups=groups)

        with self.assertRaises(ValueError) as ctx:
            _generate_fault_layer_specs(flc, None)
        self.assertIn("Resource conflict", str(ctx.exception))


# ---------------------------------------------------------------------------
# TestUserActions
# ---------------------------------------------------------------------------


class TestUserActions(unittest.TestCase):
    """Tests for the user_actions FaultLayer feature."""

    def _make_layer_with_user_actions(self, name="ua_fault"):
        """Create a FaultLayer with both agent and user actions."""
        return FaultLayer(
            name=name,
            init_calls=[
                InitCall(
                    env_type="assistant",
                    func_name=f"break_{name}",
                    args={"id": "{id}"},
                ),
            ],
            actions=[
                ActionSpec(
                    tool_name=f"fix_{name}",
                    args={"id": "{id}"},
                ),
            ],
            user_actions=[
                ActionSpec(
                    tool_name=f"user_toggle_{name}",
                    args={"device_id": "{id}"},
                ),
            ],
            assertions=[
                AssertionSpec(
                    func_name=f"assert_{name}_fixed",
                    args={"id": "{id}"},
                ),
            ],
            known_info_fragment=f"I have a {name} problem",
            resource_scope=f"{name}:{{id}}",
        )

    def test_user_actions_before_agent(self):
        """Layer user actions first, layer agent actions second, correct requestor."""
        layer = self._make_layer_with_user_actions()
        flc = _make_fault_layer_config(
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            min_faults=1,
        )
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer])

        # Should have 2 actions: 1 user + 1 agent
        self.assertEqual(len(spec.actions), 2)
        self.assertEqual(spec.actions[0]["name"], "user_toggle_ua_fault")
        self.assertEqual(spec.actions[0]["requestor"], "user")
        self.assertEqual(spec.actions[1]["name"], "fix_ua_fault")
        self.assertEqual(spec.actions[1]["requestor"], "assistant")

    def test_user_actions_requestor_enforced(self):
        """Engine overrides requestor to 'user' even if author set 'assistant'."""
        layer = FaultLayer(
            name="override_test",
            init_calls=[],
            actions=[],
            user_actions=[
                ActionSpec(
                    tool_name="user_tool",
                    args={"id": "{id}"},
                    requestor="assistant",  # Author mistake — engine should override
                ),
            ],
            assertions=[],
            known_info_fragment="override test",
            resource_scope="override:{id}",
        )
        flc = _make_fault_layer_config(
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            min_faults=1,
        )
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer])

        # User action requestor should be forced to "user"
        self.assertEqual(spec.actions[0]["requestor"], "user")

    def test_user_actions_unfixable_drops_all(self):
        """Unfixable combo → only transfer_to_human, no user actions."""
        unfixable = FaultLayer(
            name="unfixable",
            unfixable=True,
            init_calls=[],
            actions=[],
            assertions=[],
            known_info_fragment="unfixable issue",
            resource_scope="unfixable:{id}",
        )
        flc = _make_fault_layer_config(
            groups=[FaultLayerGroup(name="g1", layers=[unfixable])],
            min_faults=1,
        )
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [unfixable])

        self.assertEqual(len(spec.actions), 1)
        self.assertEqual(spec.actions[0]["name"], "transfer_to_human")

    def test_unfixable_with_user_actions_raises(self):
        """Unfixable layer + non-empty user_actions → ValueError."""
        bad_layer = FaultLayer(
            name="bad_unfixable",
            unfixable=True,
            init_calls=[],
            actions=[],
            user_actions=[ActionSpec(tool_name="should_fail")],
            assertions=[],
            known_info_fragment="bad layer",
        )
        groups = [FaultLayerGroup(name="g1", layers=[bad_layer])]
        flc = _make_fault_layer_config(groups=groups, min_faults=1)

        with self.assertRaises(ValueError) as ctx:
            _generate_fault_layer_specs(flc, None)
        self.assertIn("must have empty user_actions=[]", str(ctx.exception))

    def test_base_user_actions_appended_last(self):
        """Order: layer user → layer agent → base user."""
        layer = self._make_layer_with_user_actions()
        flc = FaultLayerConfig(
            name="test_config",
            entity_query=lambda idx: [_make_fault_entity()],
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            base_init_calls=[],
            base_known_info_template="I'm {name}. {fault_descriptions}.",
            base_ticket_template="Fix for {name}: {fault_descriptions}.",
            reason_for_call="Need help",
            purpose="Test purpose",
            base_user_actions=[
                ActionSpec(
                    tool_name="confirm_changes",
                    args={"id": "{id}"},
                ),
            ],
            entity_id_field="id",
            min_faults=1,
        )
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer])

        # Actions: 1 layer user (user_toggle_ua_fault) + 1 agent (fix_ua_fault) + 1 base user (confirm_changes)
        self.assertEqual(len(spec.actions), 3)
        self.assertEqual(spec.actions[0]["name"], "user_toggle_ua_fault")
        self.assertEqual(spec.actions[0]["requestor"], "user")
        self.assertEqual(spec.actions[1]["name"], "fix_ua_fault")
        self.assertEqual(spec.actions[1]["requestor"], "assistant")
        self.assertEqual(spec.actions[2]["name"], "confirm_changes")
        self.assertEqual(spec.actions[2]["requestor"], "user")

    def test_action_id_sequential(self):
        """IDs are 0, 1, 2, ... across agent + user actions."""
        layer = self._make_layer_with_user_actions()
        flc = FaultLayerConfig(
            name="test_config",
            entity_query=lambda idx: [_make_fault_entity()],
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            base_init_calls=[],
            base_known_info_template="I'm {name}. {fault_descriptions}.",
            base_ticket_template="Fix for {name}: {fault_descriptions}.",
            reason_for_call="Need help",
            purpose="Test purpose",
            base_user_actions=[
                ActionSpec(
                    tool_name="confirm_changes",
                    args={"id": "{id}"},
                ),
            ],
            entity_id_field="id",
            min_faults=1,
        )
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer])

        ids = [a["action_id"] for a in spec.actions]
        self.assertEqual(ids, ["0", "1", "2"])

    def test_spec_user_task_instructions_always_none(self):
        """Specs never auto-generate user_task_instructions (domain UserTemplate provides them)."""
        # With user actions
        layer = self._make_layer_with_user_actions()
        flc = _make_fault_layer_config(
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            min_faults=1,
        )
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [layer])
        self.assertIsNone(spec.user_task_instructions)

        # Without user actions
        layer2 = _make_fault_layer("agent_only")
        flc2 = _make_fault_layer_config(
            groups=[FaultLayerGroup(name="g1", layers=[layer2])],
            min_faults=1,
        )
        spec2 = _fault_layers_to_spec(flc2, entity, [layer2])
        self.assertIsNone(spec2.user_task_instructions)

    def test_spec_user_task_instructions_none_for_unfixable(self):
        """user_task_instructions is None for unfixable combos."""
        unfixable = FaultLayer(
            name="unfixable",
            unfixable=True,
            init_calls=[],
            actions=[],
            assertions=[],
            known_info_fragment="unfixable",
            resource_scope="unfixable:{id}",
        )
        flc = _make_fault_layer_config(
            groups=[FaultLayerGroup(name="g1", layers=[unfixable])],
            min_faults=1,
        )
        entity = _make_fault_entity()
        spec = _fault_layers_to_spec(flc, entity, [unfixable])

        self.assertIsNone(spec.user_task_instructions)

    def test_user_template_instructions_flow_to_task(self):
        """UserTemplate.task_instructions flow through to Task (telecom-style behavioral guidance)."""
        layer = self._make_layer_with_user_actions()
        entities = [_make_fault_entity()]
        flc = FaultLayerConfig(
            name="test_config",
            entity_query=lambda idx, e=entities: e,
            groups=[FaultLayerGroup(name="g1", layers=[layer])],
            base_init_calls=[],
            base_known_info_template="I'm {name}. {fault_descriptions}.",
            base_ticket_template="Fix for {name}: {fault_descriptions}.",
            reason_for_call="Need help",
            purpose="Test purpose",
            entity_id_field="id",
            min_faults=1,
        )
        book = RecipeBook(fault_layer_configs=[flc])
        ut = UserTemplate(
            domain="test",
            reason_for_call="Testing",
            known_info="Test info",
            task_instructions="If the agent asks you to confirm, use your confirm tool.",
            ticket="Test ticket",
            purpose="Test purpose",
        )
        tasks = generate_recipe_tasks(
            recipe_book=book,
            build_indexes=lambda db: db,
            get_db=lambda: {},
            user_template=ut,
            personas=_make_personas(),
        )
        self.assertTrue(len(tasks) >= 1)
        task = tasks[0]
        instructions = task.user_scenario.instructions.task_instructions
        self.assertEqual(instructions, "If the agent asks you to confirm, use your confirm tool.")


# ---------------------------------------------------------------------------
# TestBinSampling
# ---------------------------------------------------------------------------


class TestBinSampling(unittest.TestCase):
    """Tests for the max_tasks_per_bin bin sampling feature."""

    def _make_many_combos_config(self, n_entities=5, n_groups=4, max_per_bin=None):
        """Create a config that produces many combos for testing bin sampling."""
        entities = [
            _make_fault_entity(id=f"E{i:03d}", name=f"User{i}")
            for i in range(n_entities)
        ]
        groups = [
            FaultLayerGroup(
                name=f"g{j}",
                layers=[_make_fault_layer(f"fault_g{j}")],
            )
            for j in range(n_groups)
        ]
        return FaultLayerConfig(
            name="test_bin",
            entity_query=lambda idx, e=entities: e,
            groups=groups,
            base_init_calls=[],
            base_known_info_template="I'm {name}. {fault_descriptions}.",
            base_ticket_template="Fix: {fault_descriptions}.",
            reason_for_call="Need help",
            purpose="Test",
            entity_id_field="id",
            min_faults=1,
            max_tasks_per_bin=max_per_bin,
        )

    def test_bin_sample_reduces_count(self):
        """100+ combos → capped output with max_tasks_per_bin=2."""
        # 5 entities × 4 groups, each with 1 layer → (2^4 - 1) * 5 = 75 combos
        flc = self._make_many_combos_config(n_entities=5, n_groups=4, max_per_bin=2)
        specs = _generate_fault_layer_specs(flc, None)
        # Without sampling: 75 specs. With max_per_bin=2: at most 5*4*2 = 40
        self.assertLess(len(specs), 75)
        self.assertGreater(len(specs), 0)

    def test_bin_sample_preserves_difficulty_range(self):
        """Both 1-fault and max-fault combos present in output."""
        flc = self._make_many_combos_config(n_entities=3, n_groups=4, max_per_bin=2)
        specs = _generate_fault_layer_specs(flc, None)

        fault_counts = {len(s.actions) for s in specs}
        self.assertIn(1, fault_counts)  # 1-fault combos present
        self.assertIn(4, fault_counts)  # max-fault combos present

    def test_bin_sample_entity_coverage(self):
        """All entities represented, not just one."""
        flc = self._make_many_combos_config(n_entities=5, n_groups=4, max_per_bin=1)
        specs = _generate_fault_layer_specs(flc, None)

        entity_ids = {s.task_id.split("_")[-1] for s in specs}
        for i in range(5):
            self.assertIn(f"E{i:03d}", entity_ids)

    def test_bin_sample_none_is_noop(self):
        """max_tasks_per_bin=None → all combos generated (unchanged)."""
        flc_none = self._make_many_combos_config(n_entities=3, n_groups=3, max_per_bin=None)
        specs_none = _generate_fault_layer_specs(flc_none, None)

        # 3 groups, 1 layer each → (2^3 - 1) * 3 = 21 combos
        self.assertEqual(len(specs_none), 21)

    def test_bin_sample_deterministic(self):
        """Same inputs → same outputs."""
        flc1 = self._make_many_combos_config(n_entities=5, n_groups=4, max_per_bin=2)
        flc2 = self._make_many_combos_config(n_entities=5, n_groups=4, max_per_bin=2)
        specs1 = _generate_fault_layer_specs(flc1, None)
        specs2 = _generate_fault_layer_specs(flc2, None)

        ids1 = [s.task_id for s in specs1]
        ids2 = [s.task_id for s in specs2]
        self.assertEqual(ids1, ids2)


# ---------------------------------------------------------------------------
# TestProportionalSampling
# ---------------------------------------------------------------------------


class TestProportionalSampling(unittest.TestCase):
    """Tests for the max_total_tasks proportional sampling feature."""

    def _make_many_combos_config(self, n_entities=5, n_groups=4, max_total=None, max_per_bin=None):
        """Create a config that produces many combos for testing proportional sampling."""
        entities = [
            _make_fault_entity(id=f"E{i:03d}", name=f"User{i}")
            for i in range(n_entities)
        ]
        groups = [
            FaultLayerGroup(
                name=f"g{j}",
                layers=[_make_fault_layer(f"fault_g{j}")],
            )
            for j in range(n_groups)
        ]
        return FaultLayerConfig(
            name="test_prop",
            entity_query=lambda idx, e=entities: e,
            groups=groups,
            base_init_calls=[],
            base_known_info_template="I'm {name}. {fault_descriptions}.",
            base_ticket_template="Fix: {fault_descriptions}.",
            reason_for_call="Need help",
            purpose="Test",
            entity_id_field="id",
            min_faults=1,
            max_total_tasks=max_total,
            max_tasks_per_bin=max_per_bin,
        )

    def test_proportional_sample_reduces_count(self):
        """Total specs <= max_total_tasks."""
        # 5 entities × 4 groups → (2^4 - 1) * 5 = 75 combos
        flc = self._make_many_combos_config(n_entities=5, n_groups=4, max_total=30)
        specs = _generate_fault_layer_specs(flc, None)
        self.assertLessEqual(len(specs), 30)
        self.assertGreater(len(specs), 0)

    def test_proportional_sample_preserves_distribution(self):
        """Middle tiers have more tasks than edge tiers (bell curve)."""
        # 10 entities × 4 groups → (2^4 - 1) * 10 = 150 combos
        # Tier counts: 1-fault=C(4,1)*10=40, 2-fault=C(4,2)*10=60,
        # 3-fault=C(4,3)*10=40, 4-fault=C(4,4)*10=10
        flc = self._make_many_combos_config(n_entities=10, n_groups=4, max_total=50)
        specs = _generate_fault_layer_specs(flc, None)

        # Count specs per fault_count
        tier_counts: dict[int, int] = {}
        for s in specs:
            n = len(s.actions)
            tier_counts[n] = tier_counts.get(n, 0) + 1

        # 2-fault tier should have more than 4-fault tier
        self.assertGreater(tier_counts.get(2, 0), tier_counts.get(4, 0))

    def test_proportional_sample_deterministic(self):
        """Same inputs → same outputs."""
        flc1 = self._make_many_combos_config(n_entities=5, n_groups=4, max_total=20)
        flc2 = self._make_many_combos_config(n_entities=5, n_groups=4, max_total=20)
        specs1 = _generate_fault_layer_specs(flc1, None)
        specs2 = _generate_fault_layer_specs(flc2, None)

        ids1 = [s.task_id for s in specs1]
        ids2 = [s.task_id for s in specs2]
        self.assertEqual(ids1, ids2)

    def test_proportional_sample_entity_coverage(self):
        """All entities represented in sampled output."""
        flc = self._make_many_combos_config(n_entities=5, n_groups=4, max_total=20)
        specs = _generate_fault_layer_specs(flc, None)

        entity_ids = {s.task_id.split("_")[-1] for s in specs}
        for i in range(5):
            self.assertIn(f"E{i:03d}", entity_ids)

    def test_proportional_sample_none_is_noop(self):
        """max_total_tasks=None → all combos generated."""
        flc = self._make_many_combos_config(n_entities=3, n_groups=3, max_total=None)
        specs = _generate_fault_layer_specs(flc, None)
        # 3 groups, 1 layer each → (2^3 - 1) * 3 = 21 combos
        self.assertEqual(len(specs), 21)

    def test_mutual_exclusion(self):
        """Setting both max_tasks_per_bin and max_total_tasks raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            flc = self._make_many_combos_config(
                n_entities=3, n_groups=3, max_total=10, max_per_bin=2
            )
            _generate_fault_layer_specs(flc, None)
        self.assertIn("mutually exclusive", str(ctx.exception))


# ---------------------------------------------------------------------------
# TestResolveArgs
# ---------------------------------------------------------------------------


class TestResolveArgs(unittest.TestCase):
    """Tests for _resolve_args template resolution."""

    def test_type_preservation_int(self):
        """Pure {field} reference preserves int type."""
        result = _resolve_args({"x": "{count}"}, {"count": 42})
        self.assertEqual(result["x"], 42)
        self.assertIsInstance(result["x"], int)

    def test_type_preservation_float(self):
        """Pure {field} reference preserves float type."""
        result = _resolve_args({"x": "{amount}"}, {"amount": 3.14})
        self.assertAlmostEqual(result["x"], 3.14)
        self.assertIsInstance(result["x"], float)

    def test_string_interpolation(self):
        """Mixed string does string interpolation."""
        result = _resolve_args(
            {"label": "prefix_{name}_suffix"},
            {"name": "Alice"},
        )
        self.assertEqual(result["label"], "prefix_Alice_suffix")

    def test_literal_passthrough(self):
        """Non-template strings pass through unchanged."""
        result = _resolve_args({"key": "literal"}, {"name": "Bob"})
        self.assertEqual(result["key"], "literal")

    def test_non_string_passthrough(self):
        """Non-string values (int, bool, list) pass through unchanged."""
        result = _resolve_args(
            {"n": 5, "flag": True, "items": [1, 2]},
            {"anything": "ignored"},
        )
        self.assertEqual(result["n"], 5)
        self.assertTrue(result["flag"])
        self.assertEqual(result["items"], [1, 2])

    def test_empty_template(self):
        """Empty template dict returns empty dict."""
        result = _resolve_args({}, {"x": 1})
        self.assertEqual(result, {})

    def test_multiple_fields(self):
        """Multiple fields resolved in one template."""
        result = _resolve_args(
            {"a": "{x}", "b": "{y}"},
            {"x": 10, "y": 20},
        )
        self.assertEqual(result, {"a": 10, "b": 20})


# ---------------------------------------------------------------------------
# TestCheckPredicate
# ---------------------------------------------------------------------------


class TestCheckPredicate(unittest.TestCase):
    """Tests for _check_predicate declarative predicate evaluation."""

    def test_predicate_field_truthy(self):
        """predicate_field passes when entity field is truthy."""
        layer = FaultLayer(
            name="test",
            init_calls=[],
            actions=[],
            assertions=[],
            known_info_fragment="test",
            predicate_field="has_feature",
        )
        self.assertTrue(_check_predicate(layer, {"has_feature": True}))
        self.assertTrue(_check_predicate(layer, {"has_feature": 1}))
        self.assertTrue(_check_predicate(layer, {"has_feature": "yes"}))

    def test_predicate_field_falsy(self):
        """predicate_field fails when entity field is falsy or missing."""
        layer = FaultLayer(
            name="test",
            init_calls=[],
            actions=[],
            assertions=[],
            known_info_fragment="test",
            predicate_field="has_feature",
        )
        self.assertFalse(_check_predicate(layer, {"has_feature": False}))
        self.assertFalse(_check_predicate(layer, {"has_feature": 0}))
        self.assertFalse(_check_predicate(layer, {"has_feature": ""}))
        self.assertFalse(_check_predicate(layer, {}))  # missing key

    def test_predicate_ne_passes(self):
        """predicate_ne passes when entity field != value."""
        layer = FaultLayer(
            name="test",
            init_calls=[],
            actions=[],
            assertions=[],
            known_info_fragment="test",
            predicate_ne=("plan_id", "PLAN-BASIC"),
        )
        self.assertTrue(_check_predicate(layer, {"plan_id": "PLAN-PRO"}))
        self.assertTrue(_check_predicate(layer, {"plan_id": "PLAN-PREMIUM"}))

    def test_predicate_ne_fails(self):
        """predicate_ne fails when entity field == value."""
        layer = FaultLayer(
            name="test",
            init_calls=[],
            actions=[],
            assertions=[],
            known_info_fragment="test",
            predicate_ne=("plan_id", "PLAN-BASIC"),
        )
        self.assertFalse(_check_predicate(layer, {"plan_id": "PLAN-BASIC"}))

    def test_no_predicate_always_true(self):
        """No predicate fields → always returns True."""
        layer = FaultLayer(
            name="test",
            init_calls=[],
            actions=[],
            assertions=[],
            known_info_fragment="test",
        )
        self.assertTrue(_check_predicate(layer, {}))
        self.assertTrue(_check_predicate(layer, {"anything": "value"}))


if __name__ == "__main__":
    unittest.main()
