"""Auto repair scenario definitions using the Recipe Engine.

9 fault groups with information-hiding state hierarchy:
  - Account status (suspended/flagged) gates vehicle/invoice access
  - Registration status (expired) gates service order access
  - Diagnostic tool reveals mechanical/electrical issues

Cartesian product produces 8747 combos/entity (with warranty) or 4373 (without).
Sampled to max_total_tasks=1200, x2 personas = 2400 tasks.

2 unfixable layers in a separate transfer config.
"""

from pathlib import Path
from typing import Any, Callable, Optional

from tau2.domains.auto_repair.data_model import AutoRepairDB
from tau2.domains.auto_repair.environment import get_environment
from tau2.domains.auto_repair.utils import (
    AUTO_REPAIR_DB_PATH,
    AUTO_REPAIR_POLICY_PATH,
    AUTO_REPAIR_TASK_SET_PATH,
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
from tau2.generators.types import Persona, UserTemplate
from tau2.generators.verify import verify_tasks
from tau2.generators.verify_authoring import (
    collect_authored_files,
    verify_authoring,
    verify_authoring_with_llm,
)
from tau2.utils import dump_file


# ===================================================================
# Personas
# ===================================================================

PERSONAS = [
    Persona(
        name="straightforward_customer",
        description=(
            "You are a straightforward, no-nonsense customer. You describe your "
            "vehicle issues clearly and follow the service advisor's instructions "
            "without hesitation. You provide requested information promptly."
        ),
    ),
    Persona(
        name="anxious_customer",
        description=(
            "You are worried about your car and anxious about repair costs. You "
            "sometimes describe symptoms vaguely or emotionally (e.g. 'it sounds "
            "terrible' instead of specific details). You cooperate but ask "
            "questions about what each repair involves and costs."
        ),
    ),
]


# ===================================================================
# User Template
# ===================================================================

USER_TEMPLATE = UserTemplate(
    domain="auto_repair",
    reason_for_call=(
        "You are contacting Precision Auto Service Center because you have "
        "issues with your vehicle, your account, or a recent service visit."
    ),
    known_info=(
        "You are {customer_name} (customer ID: {customer_id}). "
        "Your vehicle is a {vehicle_year} {vehicle_make} {vehicle_model}. "
        "{fault_descriptions}"
    ),
    task_instructions=(
        "Follow the agent's instructions throughout the conversation. "
        "When the agent asks you to perform an action or use one of your tools, do so. "
        "You must actually call the tool — describing the action in words is not sufficient. "
        "You will consider your issues resolved when the agent confirms all problems have been addressed."
    ),
    ticket=(
        "Customer {customer_name} (ID: {customer_id}), "
        "vehicle: {vehicle_year} {vehicle_make} {vehicle_model}. "
        "{fault_descriptions}"
    ),
    purpose=(
        "Test resolution of auto repair support issues including account access, "
        "vehicle registration, service scheduling, mechanical diagnostics, "
        "warranty management, and billing accuracy."
    ),
)


# ===================================================================
# Entity construction
# ===================================================================

def _build_entities(db: AutoRepairDB) -> list[dict[str, Any]]:
    """Build entity dicts: one per customer, joining vehicle + order + invoice + warranty."""
    vehicle_by_customer = {}
    for v in db.vehicles:
        if v.customer_id not in vehicle_by_customer:
            vehicle_by_customer[v.customer_id] = v

    order_by_vehicle = {}
    for o in db.service_orders:
        if o.vehicle_id not in order_by_vehicle and o.status == "open":
            order_by_vehicle[o.vehicle_id] = o

    invoice_by_order = {}
    for i in db.invoices:
        if i.order_id not in invoice_by_order:
            invoice_by_order[i.order_id] = i

    warranty_by_vehicle = {}
    for w in db.warranty_plans:
        if w.vehicle_id not in warranty_by_vehicle:
            warranty_by_vehicle[w.vehicle_id] = w

    entities = []
    for customer in db.customers:
        vehicle = vehicle_by_customer.get(customer.customer_id)
        if vehicle is None:
            continue
        order = order_by_vehicle.get(vehicle.vehicle_id)
        if order is None:
            continue
        invoice = invoice_by_order.get(order.order_id)
        if invoice is None:
            continue
        warranty = warranty_by_vehicle.get(vehicle.vehicle_id)

        entity: dict[str, Any] = {
            # Customer
            "customer_id": customer.customer_id,
            "customer_name": customer.name,
            "customer_phone": customer.phone,
            "customer_email": customer.email,
            # Vehicle (surface)
            "vehicle_id": vehicle.vehicle_id,
            "vehicle_make": vehicle.make,
            "vehicle_model": vehicle.model,
            "vehicle_year": vehicle.year,
            "vehicle_mileage": vehicle.mileage,
            # Service order
            "order_id": order.order_id,
            "service_type": order.service_type,
            "original_service_type": order.service_type,
            "scheduled_date": order.scheduled_date,
            "original_scheduled_date": order.scheduled_date,
            "technician": order.technician,
            # Invoice
            "invoice_id": invoice.invoice_id,
            "original_labor_hours": invoice.labor_hours,
            "original_discount_pct": invoice.discount_pct,
            "original_total": invoice.total,
            # Warranty (optional)
            "warranty_id": warranty.warranty_id if warranty else None,
            "warranty_coverage_type": warranty.coverage_type if warranty else None,
            "original_warranty_coverage": warranty.coverage_type if warranty else None,
            # Predicate flags
            "has_warranty": warranty is not None,
        }
        entities.append(entity)

    return entities


# ===================================================================
# Fault Layers
# ===================================================================

# --- Group 1: Account Issues (2 mutually exclusive) ---
# UPSTREAM GATE: blocks get_vehicles(), get_invoices()

suspended_account = FaultLayer(
    name="suspended_account",
    known_info_fragment=(
        "My account appears to be suspended — I cannot access anything in the online portal."
    ),
    completion_fragment="your online portal is accessible and your account is active",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_account_status",
                args={"customer_id": "{customer_id}", "status": "suspended"},
            ),
            fix=ActionSpec(
                tool_name="reactivate_account",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
            check=AssertionSpec(
                func_name="assert_account_status",
                args={"customer_id": "{customer_id}", "expected": "active"},
                env_type="assistant",
                message_template="Account {customer_id} should be active.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"customer_id": "{customer_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"customer_id": "{customer_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="account:{customer_id}",
)

flagged_account = FaultLayer(
    name="flagged_account",
    known_info_fragment=(
        "My account seems to be flagged for some reason — I cannot access my vehicle records."
    ),
    completion_fragment="your account flag has been removed and your vehicle records are accessible",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_account_status",
                args={"customer_id": "{customer_id}", "status": "flagged"},
            ),
            fix=ActionSpec(
                tool_name="clear_account_flag",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
            check=AssertionSpec(
                func_name="assert_account_status",
                args={"customer_id": "{customer_id}", "expected": "active"},
                env_type="assistant",
                message_template="Account {customer_id} should be active.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"customer_id": "{customer_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"customer_id": "{customer_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="account:{customer_id}",
)

account_group = FaultLayerGroup(
    name="account_issues",
    layers=[suspended_account, flagged_account],
)


# --- Group 2: Registration Issues (1 layer) ---
# SECOND GATE: blocks get_service_orders()

expired_registration = FaultLayer(
    name="expired_registration",
    known_info_fragment=(
        "I think the registration on my {vehicle_make} {vehicle_model} may have expired."
    ),
    completion_fragment="your vehicle registration for the {vehicle_make} {vehicle_model} shows as current",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_registration_status",
                args={"vehicle_id": "{vehicle_id}", "status": "expired"},
            ),
            fix=ActionSpec(
                tool_name="update_registration",
                args={"vehicle_id": "{vehicle_id}"},
                compare_args=["vehicle_id"],
            ),
            check=AssertionSpec(
                func_name="assert_registration_status",
                args={"vehicle_id": "{vehicle_id}", "expected": "current"},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} registration should be current.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"customer_id": "{customer_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"customer_id": "{customer_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="registration:{vehicle_id}",
)

registration_group = FaultLayerGroup(
    name="registration_issues",
    layers=[expired_registration],
)


# --- Group 3: Service Scheduling (2 mutually exclusive) ---

wrong_service_date = FaultLayer(
    name="wrong_service_date",
    known_info_fragment=(
        "My service appointment for the {vehicle_make} {vehicle_model} is scheduled "
        "for the wrong date. It should be on {original_scheduled_date}."
    ),
    completion_fragment="your service appointment shows the correct date of {original_scheduled_date}",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_service_date",
                args={"order_id": "{order_id}", "date": "2025-12-31"},
            ),
            fix=ActionSpec(
                tool_name="reschedule_service",
                args={
                    "order_id": "{order_id}",
                    "new_date": "{original_scheduled_date}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_service_date",
                args={
                    "order_id": "{order_id}",
                    "expected_date": "{original_scheduled_date}",
                },
                env_type="assistant",
                message_template="Order {order_id} should be scheduled for {original_scheduled_date}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"customer_id": "{customer_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"customer_id": "{customer_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="schedule:{order_id}",
)

wrong_service_type = FaultLayer(
    name="wrong_service_type",
    known_info_fragment=(
        "My service order for the {vehicle_make} {vehicle_model} has the wrong "
        "service type. It should be {original_service_type}, not what is listed."
    ),
    completion_fragment="your service order shows the correct service type of {original_service_type}",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_service_type",
                args={"order_id": "{order_id}", "service_type": "miscellaneous"},
            ),
            fix=ActionSpec(
                tool_name="update_service_type",
                args={
                    "order_id": "{order_id}",
                    "service_type": "{original_service_type}",
                },
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_service_type",
                args={
                    "order_id": "{order_id}",
                    "expected_type": "{original_service_type}",
                },
                env_type="assistant",
                message_template="Order {order_id} should have service type {original_service_type}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"customer_id": "{customer_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"customer_id": "{customer_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="schedule:{order_id}",
)

scheduling_group = FaultLayerGroup(
    name="scheduling_issues",
    layers=[wrong_service_date, wrong_service_type],
)


# --- Group 4: Brake Issues (2 mutually exclusive) ---

worn_brake_pads = FaultLayer(
    name="worn_brake_pads",
    known_info_fragment=(
        "The brakes on my {vehicle_make} {vehicle_model} have been feeling spongy "
        "and the stopping distance seems longer than usual."
    ),
    completion_fragment="the brake inspection on your {vehicle_make} {vehicle_model} shows adequate pad thickness",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_brake_pad_thickness",
                args={"vehicle_id": "{vehicle_id}", "thickness": 1.5},
            ),
            fix=ActionSpec(
                tool_name="replace_brake_pads",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_brake_pad_thickness",
                args={"vehicle_id": "{vehicle_id}", "min_thickness": 3.0},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} brake pads should be >= 3.0mm.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_repair_approved",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="brakes:{vehicle_id}",
)

low_brake_fluid = FaultLayer(
    name="low_brake_fluid",
    known_info_fragment=(
        "The brake pedal on my {vehicle_make} {vehicle_model} feels soft and goes "
        "further to the floor than it should."
    ),
    completion_fragment="the brake fluid level on your {vehicle_make} {vehicle_model} shows as normal",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_brake_fluid_level",
                args={"vehicle_id": "{vehicle_id}", "level": "low"},
            ),
            fix=ActionSpec(
                tool_name="flush_brake_fluid",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_brake_fluid_level",
                args={"vehicle_id": "{vehicle_id}", "expected": "normal"},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} brake fluid should be normal.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_repair_approved",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="brakes:{vehicle_id}",
)

brake_group = FaultLayerGroup(
    name="brake_issues",
    layers=[worn_brake_pads, low_brake_fluid],
)


# --- Group 5: Engine Issues (2 mutually exclusive) ---

overdue_oil_change = FaultLayer(
    name="overdue_oil_change",
    known_info_fragment=(
        "My {vehicle_make} {vehicle_model} has not had an oil change in a while "
        "and the oil life indicator is very low."
    ),
    completion_fragment="the oil life indicator on your {vehicle_make} {vehicle_model} shows a healthy reading",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_oil_life",
                args={"vehicle_id": "{vehicle_id}", "pct": 5},
            ),
            fix=ActionSpec(
                tool_name="perform_oil_change",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_oil_life",
                args={"vehicle_id": "{vehicle_id}", "min_pct": 20},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} oil life should be >= 20%.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_repair_approved",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="engine:{vehicle_id}",
)

clogged_air_filter = FaultLayer(
    name="clogged_air_filter",
    known_info_fragment=(
        "My {vehicle_make} {vehicle_model} has reduced acceleration and the engine "
        "seems to be running rough."
    ),
    completion_fragment="the air filter on your {vehicle_make} {vehicle_model} shows as clean",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_air_filter_status",
                args={"vehicle_id": "{vehicle_id}", "status": "clogged"},
            ),
            fix=ActionSpec(
                tool_name="replace_air_filter",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_air_filter_status",
                args={"vehicle_id": "{vehicle_id}", "expected": "clean"},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} air filter should be clean.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_repair_approved",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="engine:{vehicle_id}",
)

engine_group = FaultLayerGroup(
    name="engine_issues",
    layers=[overdue_oil_change, clogged_air_filter],
)


# --- Group 6: Tire Issues (2 mutually exclusive) ---

low_tire_pressure = FaultLayer(
    name="low_tire_pressure",
    known_info_fragment=(
        "The tire pressure warning light has been on in my {vehicle_make} {vehicle_model}."
    ),
    completion_fragment="the tire pressure on your {vehicle_make} {vehicle_model} is within normal range",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_tire_pressure",
                args={"vehicle_id": "{vehicle_id}", "psi": 22},
            ),
            fix=ActionSpec(
                tool_name="inflate_tires",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_tire_pressure",
                args={"vehicle_id": "{vehicle_id}", "min_psi": 30},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} tire pressure should be >= 30 PSI.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_repair_approved",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="tires:{vehicle_id}",
)

wheel_misalignment = FaultLayer(
    name="wheel_misalignment",
    known_info_fragment=(
        "My {vehicle_make} {vehicle_model} pulls to one side when driving straight "
        "and the steering wheel vibrates."
    ),
    completion_fragment="the wheel alignment on your {vehicle_make} {vehicle_model} shows as properly aligned",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_wheel_alignment",
                args={"vehicle_id": "{vehicle_id}", "alignment": "misaligned"},
            ),
            fix=ActionSpec(
                tool_name="align_wheels",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_wheel_alignment",
                args={"vehicle_id": "{vehicle_id}", "expected": "aligned"},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} wheels should be aligned.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_repair_approved",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="tires:{vehicle_id}",
)

tire_group = FaultLayerGroup(
    name="tire_issues",
    layers=[low_tire_pressure, wheel_misalignment],
)


# --- Group 7: Electrical Issues (2 mutually exclusive) ---

weak_battery = FaultLayer(
    name="weak_battery",
    known_info_fragment=(
        "My {vehicle_make} {vehicle_model} has been slow to start and the "
        "headlights seem dimmer than usual."
    ),
    completion_fragment="the battery voltage on your {vehicle_make} {vehicle_model} shows adequate charge",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_battery_voltage",
                args={"vehicle_id": "{vehicle_id}", "voltage": 11.8},
            ),
            fix=ActionSpec(
                tool_name="replace_battery",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_battery_voltage",
                args={"vehicle_id": "{vehicle_id}", "min_voltage": 12.4},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} battery should be >= 12.4V.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_repair_approved",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="electrical:{vehicle_id}",
)

faulty_alternator = FaultLayer(
    name="faulty_alternator",
    known_info_fragment=(
        "My {vehicle_make} {vehicle_model} battery keeps dying even after being "
        "charged. The dashboard warning light comes on while driving."
    ),
    completion_fragment="the alternator output on your {vehicle_make} {vehicle_model} shows as normal",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_alternator_output",
                args={"vehicle_id": "{vehicle_id}", "output": "faulty"},
            ),
            fix=ActionSpec(
                tool_name="replace_alternator",
                args={"order_id": "{order_id}"},
                compare_args=["order_id"],
            ),
            check=AssertionSpec(
                func_name="assert_alternator_output",
                args={"vehicle_id": "{vehicle_id}", "expected": "normal"},
                env_type="assistant",
                message_template="Vehicle {vehicle_id} alternator should be normal.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="approve_repairs",
                args={"order_id": "{order_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_repair_approved",
                args={"order_id": "{order_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="electrical:{vehicle_id}",
)

electrical_group = FaultLayerGroup(
    name="electrical_issues",
    layers=[weak_battery, faulty_alternator],
)


# --- Group 8: Warranty Issues (1 layer, predicated on has_warranty) ---

expired_warranty = FaultLayer(
    name="expired_warranty",
    known_info_fragment=(
        "My warranty on the {vehicle_make} {vehicle_model} appears to have expired "
        "but I thought I had {original_warranty_coverage} coverage. I would like to renew it."
    ),
    completion_fragment="your warranty status shows as active with {original_warranty_coverage} coverage",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_warranty_status",
                args={"warranty_id": "{warranty_id}", "status": "expired"},
            ),
            fix=ActionSpec(
                tool_name="renew_warranty",
                args={
                    "warranty_id": "{warranty_id}",
                    "coverage_type": "{original_warranty_coverage}",
                },
                compare_args=["warranty_id"],
            ),
            check=AssertionSpec(
                func_name="assert_warranty_status",
                args={"warranty_id": "{warranty_id}", "expected": "active"},
                env_type="assistant",
                message_template="Warranty {warranty_id} should be active.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_warranty_renewal",
                args={"warranty_id": "{warranty_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_warranty_renewal_confirmed",
                args={"warranty_id": "{warranty_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_warranty",
    resource_scope="warranty:{warranty_id}",
)

warranty_group = FaultLayerGroup(
    name="warranty_issues",
    layers=[expired_warranty],
)


# --- Group 9: Billing Issues (2 mutually exclusive) ---

overcharged_labor = FaultLayer(
    name="overcharged_labor",
    known_info_fragment=(
        "I think the labor charges on my invoice are too high — I was quoted "
        "{original_labor_hours} hours of labor but the invoice shows more."
    ),
    completion_fragment="your invoice shows the correct labor charge of {original_labor_hours} hours",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_labor_hours",
                args={"invoice_id": "{invoice_id}", "hours": 8.0},
            ),
            fix=ActionSpec(
                tool_name="adjust_labor_charge",
                args={
                    "invoice_id": "{invoice_id}",
                    "labor_hours": "{original_labor_hours}",
                },
                compare_args=["invoice_id"],
            ),
            check=AssertionSpec(
                func_name="assert_labor_hours",
                args={
                    "invoice_id": "{invoice_id}",
                    "expected_hours": "{original_labor_hours}",
                },
                env_type="assistant",
                message_template="Invoice {invoice_id} should show {original_labor_hours} labor hours.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="make_payment",
                args={"invoice_id": "{invoice_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_payment_made",
                args={"invoice_id": "{invoice_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="billing:{invoice_id}",
)

missing_discount = FaultLayer(
    name="missing_discount",
    known_info_fragment=(
        "My invoice is missing the {original_discount_pct}% discount I was "
        "promised for my service."
    ),
    completion_fragment="your invoice reflects the {original_discount_pct}% discount",
        atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_discount_pct",
                args={"invoice_id": "{invoice_id}", "pct": 0.0},
            ),
            fix=ActionSpec(
                tool_name="apply_discount",
                args={
                    "invoice_id": "{invoice_id}",
                    "discount_pct": "{original_discount_pct}",
                },
                compare_args=["invoice_id"],
            ),
            check=AssertionSpec(
                func_name="assert_discount_pct",
                args={
                    "invoice_id": "{invoice_id}",
                    "expected_pct": "{original_discount_pct}",
                },
                env_type="assistant",
                message_template="Invoice {invoice_id} should have {original_discount_pct}% discount.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="make_payment",
                args={"invoice_id": "{invoice_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_payment_made",
                args={"invoice_id": "{invoice_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="billing:{invoice_id}",
)

billing_group = FaultLayerGroup(
    name="billing_issues",
    layers=[overcharged_labor, missing_discount],
)


# ===================================================================
# Unfixable layers (separate transfer config)
# ===================================================================

safety_recall = FaultLayer(
    name="safety_recall",
    unfixable=True,
    known_info_fragment=(
        "I received a notice about a manufacturer safety recall on my "
        "{vehicle_make} {vehicle_model}. I need to get it addressed."
    ),
    atoms=[],
    resource_scope="recall:{vehicle_id}",
)

structural_damage = FaultLayer(
    name="structural_damage",
    unfixable=True,
    known_info_fragment=(
        "My {vehicle_make} {vehicle_model} has frame damage from an accident "
        "that I need repaired."
    ),
    atoms=[],
    resource_scope="structure:{vehicle_id}",
)

unfixable_group = FaultLayerGroup(
    name="unfixable_issues",
    layers=[safety_recall, structural_damage],
)


# ===================================================================
# FaultLayerConfigs
# ===================================================================

FIXABLE_CONFIG = FaultLayerConfig(
    name="auto_repair",
    entity_query=lambda db: _build_entities(db),
    groups=[
        account_group,       # Group 1: account (2 layers) — upstream gate
        registration_group,  # Group 2: registration (1 layer) — second gate
        scheduling_group,    # Group 3: scheduling (2 layers)
        brake_group,         # Group 4: brakes (2 layers)
        engine_group,        # Group 5: engine (2 layers)
        tire_group,          # Group 6: tires (2 layers)
        electrical_group,    # Group 7: electrical (2 layers)
        warranty_group,      # Group 8: warranty (1 layer, predicated)
        billing_group,       # Group 9: billing (2 layers)
    ],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_customer_info",
            args={"name": "{customer_name}", "customer_id": "{customer_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {customer_name}. Your customer ID is {customer_id}. "
        "Your vehicle is a {vehicle_year} {vehicle_make} {vehicle_model}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Customer {customer_name} (ID: {customer_id}), "
        "vehicle: {vehicle_year} {vehicle_make} {vehicle_model}. "
        "{fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting Precision Auto Service Center because you have "
        "issues with your vehicle, your account, or a recent service visit."
    ),
    purpose=(
        "Test resolution of auto repair support issues with progressive "
        "discovery through information-hiding READ tools."
    ),
    entity_id_field="customer_id",
    min_faults=1,
    max_faults=9,
    max_total_tasks=1200,
)

TRANSFER_CONFIG = FaultLayerConfig(
    name="auto_repair_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[unfixable_group],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_customer_info",
            args={"name": "{customer_name}", "customer_id": "{customer_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {customer_name}. Your customer ID is {customer_id}. "
        "Your vehicle is a {vehicle_year} {vehicle_make} {vehicle_model}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Customer {customer_name} (ID: {customer_id}), "
        "vehicle: {vehicle_year} {vehicle_make} {vehicle_model}. "
        "{fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting Precision Auto Service Center about a vehicle issue."
    ),
    purpose="Test transfer-to-human for issues outside service center scope.",
    entity_id_field="customer_id",
    min_faults=1,
    max_faults=1,
    max_total_tasks=16,
)


# ===================================================================
# RecipeBook
# ===================================================================

RECIPE_BOOK = RecipeBook(
    fault_layer_configs=[FIXABLE_CONFIG, TRANSFER_CONFIG],
)


# ===================================================================
# Task generation entry point
# ===================================================================

def create_tasks(
    verify: bool = True,
    save: bool = False,
    seed: int = 42,
    llm_verify: bool = False,
    llm_call_fn: Optional[Callable[[str], str]] = None,
) -> list:
    """Generate tasks from the recipe book, optionally verify and save."""
    def get_db():
        return AutoRepairDB.load(AUTO_REPAIR_DB_PATH)

    if verify:
        authoring_issues = verify_authoring(RECIPE_BOOK, get_environment, get_db)
        auth_errors = [i for i in authoring_issues if i.startswith("ERROR:")]
        auth_warnings = [i for i in authoring_issues if i.startswith("WARNING:")]
        print(f"Authoring verification: {len(auth_errors)} error(s), {len(auth_warnings)} warning(s)")
        for i in authoring_issues:
            print(f"  {i}")
        if auth_errors:
            raise ValueError(f"Authoring verification failed: {len(auth_errors)} error(s)")

        if llm_verify and llm_call_fn:
            authored_files = collect_authored_files(
                file_paths={
                    "tools.py": str(Path(__file__).parent / "tools.py"),
                    "scenarios.py": str(Path(__file__).parent / "scenarios.py"),
                    "data_model.py": str(Path(__file__).parent / "data_model.py"),
                    "user_tools.py": str(Path(__file__).parent / "user_tools.py"),
                    "environment.py": str(Path(__file__).parent / "environment.py"),
                    "policy.md": str(AUTO_REPAIR_POLICY_PATH),
                },
                db_path=str(AUTO_REPAIR_DB_PATH),
            )
            verify_authoring_with_llm(
                RECIPE_BOOK, authored_files, authoring_issues, llm_call_fn
            )

    tasks = generate_recipe_tasks(
        recipe_book=RECIPE_BOOK,
        build_indexes=lambda db: db,
        get_db=get_db,
        user_template=USER_TEMPLATE,
        personas=PERSONAS,
        seed=seed,
    )

    print(f"Generated {len(tasks)} tasks.")

    if verify:
        atom_issues = verify_fault_atoms(
            FIXABLE_CONFIG, get_environment, get_db, sample_size=2
        )
        if atom_issues:
            raise ValueError(
                f"Atom verification failed: {len(atom_issues)} issue(s)."
            )

        policy_text = Path(AUTO_REPAIR_POLICY_PATH).read_text()
        report = verify_tasks(tasks, get_environment, policy_text=policy_text)
        errors = {}
        warnings_count = 0
        for task_id, issues in report.items():
            errs = [i for i in issues if i.startswith("ERROR:")]
            warns = [i for i in issues if i.startswith("WARNING:")]
            warnings_count += len(warns)
            if errs:
                errors[task_id] = errs
        print(f"Verification: {len(errors)} tasks with errors, {warnings_count} warnings.")
        if errors:
            for task_id, errs in list(errors.items())[:10]:
                print(f"\n  Task {task_id}:")
                for e in errs:
                    print(f"    {e}")
            raise ValueError(
                f"Verification failed: {len(errors)} task(s) have errors."
            )

    if save:
        task_dicts = [t.model_dump() for t in tasks]
        dump_file(AUTO_REPAIR_TASK_SET_PATH, task_dicts)
        print(f"Saved {len(tasks)} tasks to {AUTO_REPAIR_TASK_SET_PATH}")

    return tasks
