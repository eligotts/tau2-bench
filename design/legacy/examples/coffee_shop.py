"""
Coffee Shop Domain: Concrete example showing framework + tau2 adapter.

Demonstrates the two-layer split:
- Framework types (format-agnostic): WorldConcept, WorldSchema, SeedData
- tau2 adapter types: Tau2Concept, FaultDeclaration, FaultGroup, etc.

Exercises: schema → verify → tools → faults → composition safety verify
→ task generation → tau2 rendering.

A coding-agent rendering would reuse the framework layer, replace tau2.
"""

from design.framework import (
    Cardinality,
    EntitySpec,
    FieldSpec,
    FieldType,
    RelationshipSpec,
    SeedData,
    WorldConcept,
    WorldSchema,
    compose_blueprints,
    verify_concept,
    verify_perturbation_space,
    verify_schema,
    verify_seed_data,
)
from design.legacy.tau2 import (
    Archetype,
    FaultDeclaration,
    FaultGroup,
    FaultSpace,
    Tau2Concept,
    UnfixableFault,
    UserConfirmation,
    derive_entity_builder,
    derive_tool_signatures,
    render_tau2_task,
    verify_fault_space,
)


# ══════════════════════════════════════════════════════════════════════
# STEP 1: Concept  (FRAMEWORK — format-agnostic)
# ══════════════════════════════════════════════════════════════════════

concept = WorldConcept(
    name="coffee_shop",
    description=(
        "A specialty coffee shop where customers order drinks, earn loyalty "
        "points, and manage subscriptions."
    ),
    entity_names=["Customer", "Order", "MenuItem", "LoyaltyAccount", "Subscription"],
)

# tau2-specific interaction model (layered on top of core concept):
tau2_concept = Tau2Concept(
    archetype=Archetype.TRANSACTION,
    agent_role="customer support agent",
    user_role="customer",
    agent_purpose="Resolve order issues, manage loyalty accounts and subscriptions.",
)

# VERIFY (framework)
assert verify_concept(concept).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 2: Schema  (FRAMEWORK — format-agnostic)
# ══════════════════════════════════════════════════════════════════════

schema = WorldSchema(
    concept=concept,
    entities=[
        EntitySpec(
            name="Customer",
            description="A coffee shop customer.",
            identity_field="customer_id",
            fields=[
                FieldSpec(name="customer_id", type=FieldType.STRING,
                          description="Unique ID", mutable=False),
                FieldSpec(name="name", type=FieldType.STRING,
                          description="Customer name", mutable=False),
                FieldSpec(name="account_status", type=FieldType.ENUM,
                          description="Account state", mutable=True, breakable=True,
                          enum_values=["active", "suspended", "frozen"],
                          normal_value="active", broken_values=["suspended", "frozen"]),
            ],
        ),
        EntitySpec(
            name="Order",
            description="A coffee order.",
            identity_field="order_id",
            fields=[
                FieldSpec(name="order_id", type=FieldType.STRING,
                          description="Unique ID", mutable=False),
                FieldSpec(name="customer_id", type=FieldType.STRING,
                          description="FK to Customer", mutable=False),
                FieldSpec(name="total", type=FieldType.FLOAT,
                          description="Order total", mutable=True, breakable=True,
                          normal_value=None, broken_values=[]),
                FieldSpec(name="status", type=FieldType.ENUM,
                          description="Order status", mutable=True, breakable=True,
                          enum_values=["pending", "preparing", "ready", "completed", "cancelled"],
                          normal_value="completed", broken_values=["cancelled"]),
            ],
        ),
        EntitySpec(
            name="MenuItem",
            description="A menu item.",
            identity_field="item_id",
            fields=[
                FieldSpec(name="item_id", type=FieldType.STRING,
                          description="Unique ID", mutable=False),
                FieldSpec(name="name", type=FieldType.STRING,
                          description="Item name", mutable=False),
                FieldSpec(name="available", type=FieldType.BOOL,
                          description="In stock?", mutable=True, breakable=True,
                          normal_value=True, broken_values=[False]),
            ],
        ),
        EntitySpec(
            name="LoyaltyAccount",
            description="Customer loyalty points.",
            identity_field="loyalty_id",
            fields=[
                FieldSpec(name="loyalty_id", type=FieldType.STRING,
                          description="Unique ID", mutable=False),
                FieldSpec(name="customer_id", type=FieldType.STRING,
                          description="FK to Customer", mutable=False),
                FieldSpec(name="points", type=FieldType.INT,
                          description="Points balance", mutable=True, breakable=True,
                          normal_value=None, broken_values=[]),
                FieldSpec(name="tier", type=FieldType.ENUM,
                          description="Loyalty tier", mutable=True, breakable=True,
                          enum_values=["bronze", "silver", "gold", "platinum"],
                          normal_value=None, broken_values=[]),
            ],
        ),
        EntitySpec(
            name="Subscription",
            description="Monthly coffee subscription.",
            identity_field="subscription_id",
            fields=[
                FieldSpec(name="subscription_id", type=FieldType.STRING,
                          description="Unique ID", mutable=False),
                FieldSpec(name="customer_id", type=FieldType.STRING,
                          description="FK to Customer", mutable=False),
                FieldSpec(name="status", type=FieldType.ENUM,
                          description="Subscription status", mutable=True, breakable=True,
                          enum_values=["active", "paused", "cancelled"],
                          normal_value="active", broken_values=["paused", "cancelled"]),
                FieldSpec(name="monthly_charge", type=FieldType.FLOAT,
                          description="Monthly billing", mutable=True, breakable=True,
                          normal_value=None, broken_values=[]),
            ],
        ),
    ],
    relationships=[
        RelationshipSpec("Customer", "Order", Cardinality.ONE_TO_MANY,
                         "customer_id", "Customer has many orders"),
        RelationshipSpec("Customer", "LoyaltyAccount", Cardinality.ONE_TO_ONE,
                         "customer_id", "Customer has one loyalty account"),
        RelationshipSpec("Customer", "Subscription", Cardinality.ONE_TO_ONE,
                         "customer_id", "Customer has at most one subscription"),
    ],
)

# VERIFY (framework)
assert verify_schema(schema).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 5: Seed Data  (FRAMEWORK — format-agnostic)
# ══════════════════════════════════════════════════════════════════════

seed_data = SeedData(
    records={
        "Customer": [
            {"customer_id": "C001", "name": "Maya Chen", "account_status": "active"},
            {"customer_id": "C002", "name": "James Rivera", "account_status": "active"},
            {"customer_id": "C003", "name": "Priya Patel", "account_status": "active"},
            {"customer_id": "C004", "name": "Alex Kim", "account_status": "active"},
            {"customer_id": "C005", "name": "Sarah Johnson", "account_status": "active"},
            {"customer_id": "C006", "name": "Marcus Brown", "account_status": "active"},
            {"customer_id": "C007", "name": "Lin Wei", "account_status": "active"},
            {"customer_id": "C008", "name": "Emma Davis", "account_status": "active"},
        ],
        "Order": [
            {"order_id": "ORD001", "customer_id": "C001", "total": 9.50, "status": "completed"},
            {"order_id": "ORD002", "customer_id": "C002", "total": 4.00, "status": "completed"},
            {"order_id": "ORD003", "customer_id": "C003", "total": 12.75, "status": "completed"},
            {"order_id": "ORD004", "customer_id": "C004", "total": 6.50, "status": "completed"},
            {"order_id": "ORD005", "customer_id": "C005", "total": 8.25, "status": "completed"},
            {"order_id": "ORD006", "customer_id": "C006", "total": 5.00, "status": "completed"},
            {"order_id": "ORD007", "customer_id": "C007", "total": 15.00, "status": "completed"},
            {"order_id": "ORD008", "customer_id": "C008", "total": 7.75, "status": "completed"},
        ],
        "MenuItem": [
            {"item_id": "MI001", "name": "Latte", "available": True},
            {"item_id": "MI002", "name": "Espresso", "available": True},
            {"item_id": "MI003", "name": "Cappuccino", "available": True},
            {"item_id": "MI004", "name": "Cold Brew", "available": True},
            {"item_id": "MI005", "name": "Matcha", "available": True},
            {"item_id": "MI006", "name": "Chai", "available": True},
            {"item_id": "MI007", "name": "Mocha", "available": True},
            {"item_id": "MI008", "name": "Americano", "available": True},
        ],
        "LoyaltyAccount": [
            {"loyalty_id": "L001", "customer_id": "C001", "points": 1200, "tier": "gold"},
            {"loyalty_id": "L002", "customer_id": "C002", "points": 300, "tier": "silver"},
            {"loyalty_id": "L003", "customer_id": "C003", "points": 50, "tier": "bronze"},
            {"loyalty_id": "L004", "customer_id": "C004", "points": 2500, "tier": "platinum"},
            {"loyalty_id": "L005", "customer_id": "C005", "points": 800, "tier": "gold"},
            {"loyalty_id": "L006", "customer_id": "C006", "points": 150, "tier": "bronze"},
            {"loyalty_id": "L007", "customer_id": "C007", "points": 400, "tier": "silver"},
            {"loyalty_id": "L008", "customer_id": "C008", "points": 1800, "tier": "platinum"},
        ],
        "Subscription": [
            {"subscription_id": "S001", "customer_id": "C001", "status": "active", "monthly_charge": 29.99},
            {"subscription_id": "S002", "customer_id": "C002", "status": "active", "monthly_charge": 14.99},
            {"subscription_id": "S003", "customer_id": "C003", "status": "active", "monthly_charge": 29.99},
            {"subscription_id": "S004", "customer_id": "C004", "status": "active", "monthly_charge": 49.99},
            {"subscription_id": "S005", "customer_id": "C005", "status": "active", "monthly_charge": 14.99},
            {"subscription_id": "S006", "customer_id": "C006", "status": "active", "monthly_charge": 29.99},
            {"subscription_id": "S007", "customer_id": "C007", "status": "active", "monthly_charge": 49.99},
            {"subscription_id": "S008", "customer_id": "C008", "status": "active", "monthly_charge": 14.99},
        ],
    },
)

# VERIFY (framework)
assert verify_seed_data(seed_data, schema).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 6: Tool Signatures  (TAU2 — derived from schema)
# ══════════════════════════════════════════════════════════════════════

tools = derive_tool_signatures(schema)
# Produces: get_customer, update_customer_account_status, get_order,
# update_order_total, update_order_status, get_loyalty_account,
# update_loyalty_account_points, update_loyalty_account_tier,
# get_subscription, update_subscription_status, ...
# + init tools: set_customer_account_status, set_order_status, ...
# + assertion tools: assert_customer_account_status, ...
# + user tools: acknowledge_resolution


# ══════════════════════════════════════════════════════════════════════
# STEP 8: Fault Space  (FRAMEWORK perturbations + TAU2 fix semantics)
# ══════════════════════════════════════════════════════════════════════

fault_space = FaultSpace(
    groups=[
        FaultGroup(
            name="account_issues", category="account",
            perturbations=[
                FaultDeclaration(
                    name="suspended_account",
                    description="my account appears to be suspended",
                    fixed_description="your account is active again",
                    entity="Customer", field="account_status",
                    broken_value="suspended",
                    fix_tool="update_customer_account_status",
                    fix_args={"customer_id": "{customer_id}", "account_status": "active"},
                ),
                FaultDeclaration(
                    name="frozen_account",
                    description="my account has been frozen",
                    fixed_description="your account is active again",
                    entity="Customer", field="account_status",
                    broken_value="frozen",
                    fix_tool="update_customer_account_status",
                    fix_args={"customer_id": "{customer_id}", "account_status": "active"},
                ),
            ],
            user_confirmation=UserConfirmation(tool_name="acknowledge_resolution"),
        ),
        FaultGroup(
            name="order_status_issues", category="orders",
            perturbations=[
                FaultDeclaration(
                    name="cancelled_order",
                    description="my order {order_id} was cancelled by mistake",
                    fixed_description="your order has been reinstated",
                    entity="Order", field="status", broken_value="cancelled",
                    fix_tool="update_order_status",
                    fix_args={"order_id": "{order_id}", "status": "preparing"},
                ),
            ],
        ),
        FaultGroup(
            name="loyalty_points_issues", category="loyalty",
            perturbations=[
                FaultDeclaration(
                    name="missing_points",
                    description="my loyalty points are wrong",
                    fixed_description="your loyalty points are correct",
                    entity="LoyaltyAccount", field="points",
                    broken_value=0,
                    fix_tool="update_loyalty_account_points",
                    fix_args={"loyalty_id": "{loyalty_id}", "points": "{correct_points}"},
                    check_value="{correct_points}",
                ),
            ],
        ),
        FaultGroup(
            name="loyalty_tier_issues", category="loyalty",
            perturbations=[
                FaultDeclaration(
                    name="wrong_tier",
                    description="my loyalty tier was downgraded",
                    fixed_description="your loyalty tier has been corrected",
                    entity="LoyaltyAccount", field="tier",
                    broken_value="bronze",
                    fix_tool="update_loyalty_account_tier",
                    fix_args={"loyalty_id": "{loyalty_id}", "tier": "{correct_tier}"},
                    check_value="{correct_tier}",
                ),
            ],
        ),
        FaultGroup(
            name="subscription_status_issues", category="subscription",
            perturbations=[
                FaultDeclaration(
                    name="paused_subscription",
                    description="my subscription was paused without my request",
                    fixed_description="your subscription is active again",
                    entity="Subscription", field="status", broken_value="paused",
                    fix_tool="update_subscription_status",
                    fix_args={"subscription_id": "{subscription_id}", "status": "active"},
                    requires_field="subscription_id",
                ),
            ],
        ),
        FaultGroup(
            name="subscription_billing_issues", category="billing",
            perturbations=[
                FaultDeclaration(
                    name="wrong_charge",
                    description="my subscription charge is wrong",
                    fixed_description="your subscription charge is correct",
                    entity="Subscription", field="monthly_charge",
                    broken_value=99.99,
                    fix_tool="update_subscription_monthly_charge",
                    fix_args={"subscription_id": "{subscription_id}",
                              "monthly_charge": "{correct_charge}"},
                    check_value="{correct_charge}",
                    requires_field="subscription_id",
                ),
            ],
        ),
        FaultGroup(
            name="menu_availability_issues", category="menu",
            perturbations=[],
            unfixable_fault=UnfixableFault(
                name="item_unavailable",
                description="a menu item is unavailable",
                entity="MenuItem", field="available", broken_value=False,
            ),
        ),
    ],
    min_perturbations=1,
    max_perturbations=5,
    max_total_tasks=400,
    resolution_instruction=(
        "your account is in good standing, any order or billing issues "
        "have been corrected, your loyalty points are accurate, and "
        "your subscription is working properly"
    ),
)

# VERIFY (framework + tau2)
assert verify_perturbation_space(fault_space, schema).passed
assert verify_fault_space(fault_space, schema, tools).passed


# ══════════════════════════════════════════════════════════════════════
# COMPOSITION: Framework engine generates blueprints
# ══════════════════════════════════════════════════════════════════════

# Use the derived entity builder
entity_builder = derive_entity_builder(schema)
entities = entity_builder(seed_data.records)

# Framework composition — format-agnostic
blueprints = compose_blueprints(
    space=fault_space,
    entities=entities,
    entity_id_field="customer_id",
    seed=42,
)

print(f"Generated {len(blueprints)} task blueprints")


# ══════════════════════════════════════════════════════════════════════
# STEP 10: Render to tau2 format
# ══════════════════════════════════════════════════════════════════════

tau2_tasks = [
    render_tau2_task(bp, fault_space, schema)
    for bp in blueprints
]

print(f"Rendered {len(tau2_tasks)} tau2 tasks")
# Each task has init_actions, evaluation_criteria.actions,
# evaluation_criteria.env_assertions — ready for tau2 engine


# ══════════════════════════════════════════════════════════════════════
# WHAT A CODING-AGENT RENDERING WOULD LOOK LIKE
#
# Steps 1-5 (concept, schema, gates, rules, seed_data) stay the same.
# Steps 6-10 are replaced with:
#
#   from design.coding_rendering import (
#       BugDeclaration,     # extends PerturbationSpec with mutation + test
#       derive_file_stubs,  # schema → code files (not tools)
#       bug_to_mutation,    # BugDeclaration → code diff
#       blueprint_to_swebench_task,  # TaskBlueprint → SWE-bench format
#   )
#
#   # BugDeclaration adds:
#   #   file_path: str       — which file to mutate
#   #   mutation: str         — code diff introducing the bug
#   #   test_command: str     — command to verify the fix
#
#   # The core compose_blueprints() works identically — it doesn't
#   # care how perturbations get fixed, only which ones compose.
# ══════════════════════════════════════════════════════════════════════
