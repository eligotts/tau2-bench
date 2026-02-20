"""Tech Support scenario definitions using the Recipe Engine (FaultLayerConfig).

Generates tasks via cartesian product of fault groups across entities.
Each entity is a dict built from joined DB records (customer + device + plan).

6 fault groups (fixable) + 1 transfer config (3 unfixable layers).
User-heavy domain: most faults are resolved by the user performing physical
troubleshooting steps, guided by the agent's diagnosis.
"""

from pathlib import Path
from typing import Any, Callable, Optional

from tau2.domains.tech_support.data_model import TechSupportDB
from tau2.domains.tech_support.environment import get_environment
from tau2.domains.tech_support.utils import (
    TECH_SUPPORT_DB_PATH,
    TECH_SUPPORT_POLICY_PATH,
    TECH_SUPPORT_TASK_SET_PATH,
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


# ===================================================================
# Personas
# ===================================================================

PERSONAS = [
    Persona(name="calm_customer", description=(
        "You are a calm and cooperative customer. You clearly describe your "
        "internet issues and follow the agent's troubleshooting instructions "
        "without hesitation. You provide all requested information promptly."
    )),
    Persona(name="anxious_customer", description=(
        "You are an anxious customer who relies heavily on your internet for work. "
        "You sometimes give vague or panicky descriptions of the problem and may "
        "express frustration, but you ultimately cooperate when given clear "
        "step-by-step instructions."
    )),
]


# ===================================================================
# User Template
# ===================================================================

USER_TEMPLATE = UserTemplate(
    domain="tech_support",
    reason_for_call=(
        "You are contacting NetConnect ISP technical support because you are "
        "having problems with your internet connection."
    ),
    known_info=(
        "You are {customer_name} (customer ID: {customer_id}). {fault_descriptions}"
    ),
    task_instructions=(
        "When the agent asks you to restart your router, use your restart_router tool. "
        "When the agent asks you to factory reset your router, use your factory_reset_router tool. "
        "When the agent asks you to check your cable connections, use your check_cable_connections tool. "
        "When the agent asks you to switch your WiFi band, use your switch_wifi_band tool. "
        "When the agent asks you to clear your DNS cache, use your clear_dns_cache tool. "
        "When the agent asks you to run a speed test, use your run_speed_test tool. "
        "You will consider the issue resolved only when the agent confirms the problem has been fixed."
    ),
    ticket=(
        "Customer {customer_name} (ID: {customer_id}) contacting about internet issues. "
        "{fault_descriptions}"
    ),
    purpose=(
        "Test ISP tech support troubleshooting with user-guided device actions "
        "including router restarts, cable checks, WiFi band switching, DNS clearing, "
        "firmware updates, network resets, and speed verification."
    ),
)


# ===================================================================
# Entity construction
# ===================================================================

def _build_entities(db: TechSupportDB) -> list[dict[str, Any]]:
    """Build entity dicts by joining customer + device + service plan.

    Each entity represents one customer, enriched with their primary
    device and service plan. This gives fault layers enough fields to
    template against.
    """
    tier_order = ["basic_50", "standard_100", "premium_200", "ultra_500"]

    entities = []
    for customer in db.customers:
        # Find the customer's device
        device = next(
            (d for d in db.devices if d.customer_id == customer.customer_id),
            None,
        )
        if device is None:
            continue

        # Find the customer's plan
        plan = next(
            (p for p in db.service_plans if p.customer_id == customer.customer_id),
            None,
        )
        if plan is None:
            continue

        # Precompute escalated speed tier
        current_idx = tier_order.index(plan.speed_tier) if plan.speed_tier in tier_order else -1
        can_escalate = 0 <= current_idx < len(tier_order) - 1
        escalated_tier = tier_order[current_idx + 1] if can_escalate else plan.speed_tier

        entity: dict[str, Any] = {
            # Customer fields
            "customer_id": customer.customer_id,
            "customer_name": customer.name,
            "customer_email": customer.email,
            "customer_phone": customer.phone,
            "area_code": customer.area_code,
            # Device fields
            "device_id": device.device_id,
            "device_type": device.device_type,
            "device_model": device.model,
            # Plan fields
            "plan_id": plan.plan_id,
            "plan_name": plan.plan_name,
            "speed_tier": plan.speed_tier,
            "escalated_speed_tier": escalated_tier,
            # Predicate flags
            "can_escalate": can_escalate,
        }
        entities.append(entity)

    return entities


# ===================================================================
# Base init calls (normalize to healthy state)
# ===================================================================

_BASE_INIT: list[InitCall] = [
    # Normalize device state
    InitCall(
        env_type="assistant", func_name="set_device_status",
        args={"device_id": "{device_id}", "status": "online"},
    ),
    InitCall(
        env_type="assistant", func_name="set_device_firmware_status",
        args={"device_id": "{device_id}", "status": "current"},
    ),
    InitCall(
        env_type="assistant", func_name="set_device_wifi_band",
        args={"device_id": "{device_id}", "band": "5ghz"},
    ),
    InitCall(
        env_type="assistant", func_name="set_device_channel_congested",
        args={"device_id": "{device_id}", "congested": False},
    ),
    InitCall(
        env_type="assistant", func_name="set_device_cable_status",
        args={"device_id": "{device_id}", "status": "connected"},
    ),
    # Normalize customer state
    InitCall(
        env_type="assistant", func_name="set_customer_dns_config",
        args={"customer_id": "{customer_id}", "config": "normal"},
    ),
    InitCall(
        env_type="assistant", func_name="set_customer_network_profile",
        args={"customer_id": "{customer_id}", "profile": "normal"},
    ),
    InitCall(
        env_type="assistant", func_name="set_customer_account_status",
        args={"customer_id": "{customer_id}", "status": "active"},
    ),
    # Normalize plan state
    InitCall(
        env_type="assistant", func_name="set_plan_speed_status",
        args={"customer_id": "{customer_id}", "status": "normal"},
    ),
    # Set user identity LAST
    InitCall(
        env_type="user", func_name="set_user_info",
        args={"name": "{customer_name}", "customer_id": "{customer_id}"},
    ),
]


# ===================================================================
# Fault Layers
# ===================================================================

# --- Group 1: Router/Firmware Issues (3 mutually exclusive) ---
# Resource scope: device_status or device_firmware on the same device.
# router_hung and router_corrupted/outdated_firmware modify different fields
# but are grouped together since they represent the primary device issue axis.

router_hung = FaultLayer(
    name="router_hung",
    known_info_fragment=(
        "my router seems completely frozen - no internet and the lights are stuck"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_device_status",
                args={"device_id": "{device_id}", "status": "unresponsive"},
            ),
            fix=ActionSpec(
                tool_name="restart_router", args={},
                requestor="user", compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_router_restarted", args={},
                env_type="user",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_device_status",
            args={"device_id": "{device_id}", "expected": "online"},
            env_type="assistant",
            message_template="Device {device_id} should be online after restart.",
        ),
        AssertionSpec(
            func_name="assert_connection_status",
            args={"expected": "online"},
            env_type="user",
            message_template="User should see connection status as online.",
        ),
    ],
    resource_scope="device_primary:{device_id}",
)

router_corrupted = FaultLayer(
    name="router_corrupted",
    known_info_fragment=(
        "my router has been acting up since a power outage and now nothing works properly"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_device_firmware_status",
                args={"device_id": "{device_id}", "status": "corrupted"},
            ),
            fix=ActionSpec(
                tool_name="factory_reset_router", args={},
                requestor="user", compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_factory_reset_done", args={},
                env_type="user",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_device_firmware",
            args={"device_id": "{device_id}", "expected": "current"},
            env_type="assistant",
            message_template="Device {device_id} firmware should be current after factory reset.",
        ),
        AssertionSpec(
            func_name="assert_firmware_status",
            args={"expected": "current"},
            env_type="user",
            message_template="User should see firmware as current.",
        ),
    ],
    resource_scope="device_primary:{device_id}",
)

outdated_firmware = FaultLayer(
    name="outdated_firmware",
    known_info_fragment=(
        "I heard there might be a firmware update available for my router "
        "and I'd like it installed"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_device_firmware_status",
                args={"device_id": "{device_id}", "status": "outdated"},
            ),
            fix=ActionSpec(
                tool_name="push_firmware_update",
                args={"device_id": "{device_id}"},
                compare_args=["device_id"],
            ),
            check=AssertionSpec(
                func_name="assert_device_firmware",
                args={"device_id": "{device_id}", "expected": "current"},
                env_type="assistant",
                message_template="Device {device_id} firmware should be current after update.",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_firmware_status",
            args={"expected": "current"},
            env_type="user",
            message_template="User should see firmware as current.",
        ),
    ],
    resource_scope="device_primary:{device_id}",
)

router_group = FaultLayerGroup(
    name="router_firmware_issues",
    layers=[router_hung, router_corrupted, outdated_firmware],
)


# --- Group 2: Cable Connection Issues (1 layer) ---

loose_cable = FaultLayer(
    name="loose_cable",
    known_info_fragment=(
        "my internet went out suddenly and I noticed the connection light "
        "on my router is off"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_device_cable_status",
                args={"device_id": "{device_id}", "status": "disconnected"},
            ),
            fix=ActionSpec(
                tool_name="check_cable_connections", args={},
                requestor="user", compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_cables_checked", args={},
                env_type="user",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_device_cable_status",
            args={"device_id": "{device_id}", "expected": "connected"},
            env_type="assistant",
            message_template="Device {device_id} cable should be connected.",
        ),
        AssertionSpec(
            func_name="assert_cable_status",
            args={"expected": "connected"},
            env_type="user",
            message_template="User should see cable as connected.",
        ),
    ],
    resource_scope="cable:{device_id}",
)

cable_group = FaultLayerGroup(
    name="cable_issues",
    layers=[loose_cable],
)


# --- Group 3: WiFi Configuration Issues (2 mutually exclusive) ---

wrong_band = FaultLayer(
    name="wrong_band",
    known_info_fragment=(
        "my WiFi is really slow - I think I might be on the wrong frequency band"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_device_wifi_band",
                args={"device_id": "{device_id}", "band": "2.4ghz"},
            ),
            fix=ActionSpec(
                tool_name="switch_wifi_band", args={},
                requestor="user", compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_wifi_band_switched", args={},
                env_type="user",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_device_wifi_band",
            args={"device_id": "{device_id}", "expected": "5ghz"},
            env_type="assistant",
            message_template="Device {device_id} should be on 5ghz band.",
        ),
        AssertionSpec(
            func_name="assert_wifi_band",
            args={"expected": "5ghz"},
            env_type="user",
            message_template="User should see 5ghz WiFi band.",
        ),
    ],
    resource_scope="wifi:{device_id}",
)

channel_congestion = FaultLayer(
    name="channel_congestion",
    known_info_fragment=(
        "my WiFi keeps dropping and is very slow, especially when my "
        "neighbors are home - I think there might be interference"
    ),
    atoms=[
        # Atom 1: Agent optimizes WiFi channel server-side
        FaultAtom(
            init=[
                InitCall(
                    env_type="assistant", func_name="set_device_channel_congested",
                    args={"device_id": "{device_id}", "congested": True},
                ),
                InitCall(
                    env_type="assistant", func_name="set_device_wifi_band",
                    args={"device_id": "{device_id}", "band": "2.4ghz"},
                ),
            ],
            fix=ActionSpec(
                tool_name="optimize_wifi_channel",
                args={"device_id": "{device_id}"},
                compare_args=["device_id"],
            ),
            check=AssertionSpec(
                func_name="assert_device_channel_congested",
                args={"device_id": "{device_id}", "expected": False},
                env_type="assistant",
                message_template="Device {device_id} channel should no longer be congested.",
            ),
        ),
        # Atom 2: User switches WiFi band to pick up new channel
        FaultAtom(
            fix=ActionSpec(
                tool_name="switch_wifi_band", args={},
                requestor="user", compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_wifi_band_switched", args={},
                env_type="user",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_device_wifi_band",
            args={"device_id": "{device_id}", "expected": "5ghz"},
            env_type="assistant",
            message_template="Device {device_id} should be on 5ghz band.",
        ),
    ],
    resource_scope="wifi:{device_id}",
)

wifi_group = FaultLayerGroup(
    name="wifi_issues",
    layers=[wrong_band, channel_congestion],
)


# --- Group 4: DNS Issues (2 mutually exclusive) ---

stale_dns = FaultLayer(
    name="stale_dns",
    known_info_fragment=(
        "some websites won't load even though my internet connection "
        "seems fine otherwise"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_customer_dns_config",
                args={"customer_id": "{customer_id}", "config": "stale_cache"},
            ),
            fix=ActionSpec(
                tool_name="clear_dns_cache", args={},
                requestor="user", compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_dns_cache_cleared", args={},
                env_type="user",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_customer_dns_config",
            args={"customer_id": "{customer_id}", "expected": "normal"},
            env_type="assistant",
            message_template="Customer {customer_id} DNS should be normal.",
        ),
        AssertionSpec(
            func_name="assert_dns_status",
            args={"expected": "normal"},
            env_type="user",
            message_template="User should see DNS status as normal.",
        ),
    ],
    resource_scope="dns:{customer_id}",
)

wrong_dns_server = FaultLayer(
    name="wrong_dns_server",
    known_info_fragment=(
        "none of my websites are loading - I keep getting DNS errors "
        "in my browser"
    ),
    atoms=[
        # Atom 1: Agent flushes server-side DNS (intermediate state verified
        # by atom-level test; no final-state check since atom 2 resolves it)
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_customer_dns_config",
                args={"customer_id": "{customer_id}", "config": "misconfigured"},
            ),
            fix=ActionSpec(
                tool_name="flush_dns_records",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
        ),
        # Atom 2: User clears local DNS cache
        FaultAtom(
            fix=ActionSpec(
                tool_name="clear_dns_cache", args={},
                requestor="user", compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_dns_cache_cleared", args={},
                env_type="user",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_customer_dns_config",
            args={"customer_id": "{customer_id}", "expected": "normal"},
            env_type="assistant",
            message_template="Customer {customer_id} DNS should be normal after full fix.",
        ),
        AssertionSpec(
            func_name="assert_dns_status",
            args={"expected": "normal"},
            env_type="user",
            message_template="User should see DNS status as normal.",
        ),
    ],
    resource_scope="dns:{customer_id}",
)

dns_group = FaultLayerGroup(
    name="dns_issues",
    layers=[stale_dns, wrong_dns_server],
)


# --- Group 5: Network Profile Issues (1 layer) ---

corrupted_profile = FaultLayer(
    name="corrupted_profile",
    known_info_fragment=(
        "my internet speeds dropped dramatically and I think something "
        "is wrong on your end"
    ),
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_customer_network_profile",
                args={"customer_id": "{customer_id}", "profile": "corrupted"},
            ),
            fix=ActionSpec(
                tool_name="reset_network_profile",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
            check=AssertionSpec(
                func_name="assert_customer_network_profile",
                args={"customer_id": "{customer_id}", "expected": "normal"},
                env_type="assistant",
                message_template="Customer {customer_id} network profile should be normal.",
            ),
        ),
    ],
    resource_scope="network_profile:{customer_id}",
)

network_profile_group = FaultLayerGroup(
    name="network_profile_issues",
    layers=[corrupted_profile],
)


# --- Group 6: Speed Issues (1 layer) ---
# Requires agent escalation + user speed test verification.

throttled_speed = FaultLayer(
    name="throttled_speed",
    known_info_fragment=(
        "my internet speed is way below what my {plan_name} plan should "
        "provide and I'd like this fixed"
    ),
    atoms=[
        # Atom 1: Agent escalates speed tier
        FaultAtom(
            init=InitCall(
                env_type="assistant", func_name="set_plan_speed_status",
                args={"customer_id": "{customer_id}", "status": "throttled"},
            ),
            fix=ActionSpec(
                tool_name="escalate_speed_tier",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
            check=AssertionSpec(
                func_name="assert_plan_speed_tier",
                args={"customer_id": "{customer_id}", "expected": "{escalated_speed_tier}"},
                env_type="assistant",
                message_template="Customer {customer_id} should be on {escalated_speed_tier} tier.",
            ),
        ),
        # Atom 2: User runs speed test to verify
        FaultAtom(
            fix=ActionSpec(
                tool_name="run_speed_test", args={},
                requestor="user", compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_speed_test_run", args={},
                env_type="user",
            ),
        ),
    ],
    assertions=[
        AssertionSpec(
            func_name="assert_plan_speed_status",
            args={"customer_id": "{customer_id}", "expected": "normal"},
            env_type="assistant",
            message_template="Customer {customer_id} speed status should be normal.",
        ),
        AssertionSpec(
            func_name="assert_speed_status",
            args={"expected": "normal"},
            env_type="user",
            message_template="User should see speed status as normal.",
        ),
    ],
    predicate_field="can_escalate",
    resource_scope="speed:{customer_id}",
)

speed_group = FaultLayerGroup(
    name="speed_issues",
    layers=[throttled_speed],
)


# ===================================================================
# Unfixable Fault Layers (separate transfer config)
# ===================================================================

hardware_failure = FaultLayer(
    name="hardware_failure",
    unfixable=True,
    known_info_fragment=(
        "my router seems completely dead - no lights at all, even after "
        "unplugging and replugging multiple times"
    ),
    init_calls=[
        InitCall(
            env_type="assistant", func_name="set_device_status",
            args={"device_id": "{device_id}", "status": "hardware_failure"},
        ),
    ],
    atoms=[],
    assertions=[
        AssertionSpec(
            func_name="assert_device_status",
            args={"device_id": "{device_id}", "expected": "hardware_failure"},
            env_type="assistant",
            message_template="Device {device_id} should still show hardware_failure (unfixable).",
        ),
    ],
    resource_scope="device_primary:{device_id}",
)

account_security_breach = FaultLayer(
    name="account_security_breach",
    unfixable=True,
    known_info_fragment=(
        "I got an email saying my account might be compromised and I need "
        "help securing it right away"
    ),
    init_calls=[
        InitCall(
            env_type="assistant", func_name="set_customer_account_status",
            args={"customer_id": "{customer_id}", "status": "flagged"},
        ),
    ],
    atoms=[],
    assertions=[
        AssertionSpec(
            func_name="assert_device_status",
            args={"device_id": "{device_id}", "expected": "online"},
            env_type="assistant",
            message_template="Device should remain unchanged (account issue, not device).",
        ),
    ],
    resource_scope="account:{customer_id}",
)

infrastructure_outage = FaultLayer(
    name="infrastructure_outage",
    unfixable=True,
    known_info_fragment=(
        "my internet has been completely down since this morning and "
        "absolutely nothing I do fixes it"
    ),
    init_calls=[
        InitCall(
            env_type="assistant", func_name="set_outage_area_code",
            args={"outage_id": "OUT003", "area_code": "{area_code}"},
        ),
    ],
    atoms=[],
    assertions=[
        AssertionSpec(
            func_name="assert_device_status",
            args={"device_id": "{device_id}", "expected": "online"},
            env_type="assistant",
            message_template="Device should remain online (outage is infrastructure, not device).",
        ),
    ],
    resource_scope="outage:{area_code}",
)


# ===================================================================
# FaultLayerConfigs
# ===================================================================

FIXABLE_CONFIG = FaultLayerConfig(
    name="tech_support",
    entity_query=lambda db: _build_entities(db),
    groups=[
        router_group,           # Group 1: router/firmware (3 layers)
        cable_group,            # Group 2: cable (1 layer)
        wifi_group,             # Group 3: wifi config (2 layers)
        dns_group,              # Group 4: dns (2 layers)
        network_profile_group,  # Group 5: network profile (1 layer)
        speed_group,            # Group 6: speed (1 layer)
    ],
    base_init_calls=_BASE_INIT,
    base_known_info_template=(
        "You are {customer_name}. Your customer ID is {customer_id}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Customer {customer_name} (ID: {customer_id}): {fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting NetConnect ISP technical support because you are "
        "having problems with your internet connection."
    ),
    purpose=(
        "Test ISP tech support troubleshooting with user-guided device actions."
    ),
    entity_id_field="customer_id",
    min_faults=1,
    max_faults=6,
    max_total_tasks=600,
)

TRANSFER_CONFIG = FaultLayerConfig(
    name="tech_support_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[
        FaultLayerGroup(
            name="unfixable_issues",
            layers=[hardware_failure, account_security_breach, infrastructure_outage],
        ),
    ],
    base_init_calls=_BASE_INIT,
    base_known_info_template=(
        "You are {customer_name}. Your customer ID is {customer_id}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Customer {customer_name} (ID: {customer_id}): {fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting NetConnect ISP technical support because you are "
        "having a serious problem with your internet service."
    ),
    purpose=(
        "Test transfer-to-human for issues that cannot be resolved remotely."
    ),
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

VARIANT_CONFIG = VariantConfig(
    easy_personas=[PERSONAS[0]],   # calm_customer
    hard_personas=[PERSONAS[1]],   # anxious_customer
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
    """Generate tasks from the recipe book, optionally verify and save.

    Args:
        verify: Run verification passes on generated tasks.
        save: Write tasks.json to disk.
        seed: Random seed for reproducibility.
        llm_verify: Run LLM semantic review of authored source files.
        llm_call_fn: Callable for LLM calls (required if llm_verify=True).

    Returns:
        List of generated Task objects.
    """
    def get_db():
        return TechSupportDB.load(TECH_SUPPORT_DB_PATH)

    if verify:
        # Pre-generation: structural checks on authored definitions
        authoring_issues = verify_authoring(RECIPE_BOOK, get_environment, get_db)
        auth_errors = [i for i in authoring_issues if i.startswith("ERROR:")]
        auth_warnings = [i for i in authoring_issues if i.startswith("WARNING:")]
        print(f"Authoring verification: {len(auth_errors)} error(s), {len(auth_warnings)} warning(s)")
        for i in authoring_issues:
            print(f"  {i}")
        if auth_errors:
            raise ValueError(f"Authoring verification failed: {len(auth_errors)} error(s)")

        # Optional: LLM review of source files
        if llm_verify and llm_call_fn:
            authored_files = collect_authored_files(
                file_paths={
                    "tools.py": str(Path(__file__).parent / "tools.py"),
                    "scenarios.py": str(Path(__file__).parent / "scenarios.py"),
                    "data_model.py": str(Path(__file__).parent / "data_model.py"),
                    "user_tools.py": str(Path(__file__).parent / "user_tools.py"),
                    "environment.py": str(Path(__file__).parent / "environment.py"),
                    "policy.md": str(TECH_SUPPORT_POLICY_PATH),
                },
                db_path=str(TECH_SUPPORT_DB_PATH),
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
        variant_config=VARIANT_CONFIG,
        seed=seed,
    )

    print(f"Generated {len(tasks)} tasks.")

    if verify:
        # Per-atom verification: test each init->fix->check triple in isolation
        atom_issues = verify_fault_atoms(
            FIXABLE_CONFIG, get_environment, get_db, sample_size=2
        )
        if atom_issues:
            raise ValueError(
                f"Atom verification failed: {len(atom_issues)} issue(s)."
            )

        # Full task verification
        report = verify_tasks(tasks, get_environment)
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
        dump_file(TECH_SUPPORT_TASK_SET_PATH, task_dicts)
        print(f"Saved {len(tasks)} tasks to {TECH_SUPPORT_TASK_SET_PATH}")

    return tasks
