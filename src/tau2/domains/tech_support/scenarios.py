"""Tech Support scenario definitions using the Recipe Engine (FaultLayerConfig).

Generates tasks via cartesian product of fault groups across entities.
Each entity is a dict built from joined DB records (customer + device + plan).

3-tier diagnostic decision tree mirroring real ISP troubleshooting:
  Tier 0: Account (lookup_customer) → Tier 1: Device/Hardware (run_remote_diagnostic)
  → Tier 2: Service/Network (get_service_plan, check_area_outages)

Uses all three archetype primitives:
- gate_tier: 3-tier gating (account → device → service/network)
- phase: Multi-step layers have explicit execution ordering
- step_type: Agent diagnostics ("diagnostic"), fixes ("fix"), and user verifications ("confirm")

8 fixable fault groups + 1 transfer config (3 unfixable layers).
Archetype mix: A (account gates device), B (user diagnose→fix), C (agent fixes).
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
        "Follow the agent's instructions throughout the conversation. "
        "When the agent asks you to perform an action or use one of your tools, do so. "
        "You must actually call the tool \u2014 describing the action in words is not sufficient. "
        "You will consider your issues resolved when the agent confirms all problems "
        "have been addressed."
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
    InitCall(
        env_type="assistant", func_name="set_billing_credit",
        args={"customer_id": "{customer_id}", "credit": 0.0},
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

# --- Group 0: Account Access Issues (gate_tier=0) ---
# Archetype A: account suspension gates all downstream troubleshooting.
# Agent diagnostic: lookup_customer discovers the suspension.

account_suspended = FaultLayer(
    name="account_suspended",
    gate_tier=0,
    known_info_fragment=(
        "I'm having trouble with my service and I think there might be "
        "an issue with my account"
    ),
    completion_fragment="your account is active and fully accessible",
    atoms=[
        # Phase 0: Agent looks up customer account (discovers suspension)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="lookup_customer",
                args={"name": "{customer_name}"},
                compare_args=["name"],
            ),
        ),
        # Phase 1: Agent reactivates the suspended account
        FaultAtom(
            phase=1,
            step_type="fix",
            init=InitCall(
                env_type="assistant", func_name="set_customer_account_status",
                args={"customer_id": "{customer_id}", "status": "suspended"},
            ),
            fix=ActionSpec(
                tool_name="reactivate_account",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
            check=AssertionSpec(
                func_name="assert_customer_account_status",
                args={"customer_id": "{customer_id}", "expected": "active"},
                env_type="assistant",
                message_template="Customer {customer_id} account should be active.",
            ),
        ),
    ],
    resource_scope="account:{customer_id}",
)

account_group = FaultLayerGroup(
    name="account_access",
    layers=[account_suspended],
    resolution_category="account",
)


# --- Group 1: Router/Firmware Issues (3 mutually exclusive, gate_tier=1) ---
# Archetype B for router_hung and router_corrupted: user diagnostic → user fix.
# Archetype C for outdated_firmware: agent-only fix.

router_hung = FaultLayer(
    name="router_hung",
    gate_tier=1,
    known_info_fragment=(
        "my router seems completely frozen - no internet and the lights are stuck"
    ),
    completion_fragment="your router is back online and responsive",
    atoms=[
        # Phase 0: Agent runs remote diagnostic (discovers device issues)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="run_remote_diagnostic",
                args={"device_id": "{device_id}"},
                compare_args=["device_id"],
            ),
        ),
        # Phase 1: User checks their connection (discovers the problem)
        FaultAtom(
            phase=1,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="check_my_connection", args={},
                requestor="user", compare_args=[],
            ),
        ),
        # Phase 2: User restarts router (fixes the problem)
        FaultAtom(
            phase=2,
            step_type="fix",
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
    ],
    resource_scope="device_primary:{device_id}",
)

router_corrupted = FaultLayer(
    name="router_corrupted",
    gate_tier=1,
    known_info_fragment=(
        "my router has been acting up since a power outage and now nothing works properly"
    ),
    completion_fragment="your router has been factory reset and is working properly",
    atoms=[
        # Phase 0: Agent runs remote diagnostic (discovers firmware corruption)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="run_remote_diagnostic",
                args={"device_id": "{device_id}"},
                compare_args=["device_id"],
            ),
        ),
        # Phase 1: User checks their connection (sees the problem)
        FaultAtom(
            phase=1,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="check_my_connection", args={},
                requestor="user", compare_args=[],
            ),
        ),
        # Phase 2: User factory resets router
        FaultAtom(
            phase=2,
            step_type="fix",
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
    ],
    resource_scope="device_primary:{device_id}",
)

outdated_firmware = FaultLayer(
    name="outdated_firmware",
    gate_tier=1,
    known_info_fragment=(
        "I heard there might be a firmware update available for my router "
        "and I'd like it installed"
    ),
    completion_fragment="your router firmware has been updated",
    atoms=[
        # Phase 0: Agent runs remote diagnostic (discovers outdated firmware)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="run_remote_diagnostic",
                args={"device_id": "{device_id}"},
                compare_args=["device_id"],
            ),
        ),
        # Phase 1: Agent pushes firmware update
        FaultAtom(
            phase=1,
            step_type="fix",
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
    resource_scope="device_primary:{device_id}",
)

router_group = FaultLayerGroup(
    name="router_firmware_issues",
    layers=[router_hung, router_corrupted, outdated_firmware],
    resolution_category="connection",
)


# --- Group 2: Cable Connection Issues (1 layer, gate_tier=1) ---
# Archetype B: user diagnostic → user fix.

loose_cable = FaultLayer(
    name="loose_cable",
    gate_tier=1,
    known_info_fragment=(
        "my internet went out suddenly and I noticed the connection light "
        "on my router is off"
    ),
    completion_fragment="your cable connections are secure and showing a good link",
    atoms=[
        # Phase 0: Agent runs remote diagnostic (discovers cable issue)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="run_remote_diagnostic",
                args={"device_id": "{device_id}"},
                compare_args=["device_id"],
            ),
        ),
        # Phase 1: User checks their connection (sees disconnected status)
        FaultAtom(
            phase=1,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="check_my_connection", args={},
                requestor="user", compare_args=[],
            ),
        ),
        # Phase 2: User physically checks and resecures cables
        FaultAtom(
            phase=2,
            step_type="fix",
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
    ],
    resource_scope="cable:{device_id}",
)

cable_group = FaultLayerGroup(
    name="cable_issues",
    layers=[loose_cable],
    resolution_category="connection",
)


# --- Group 3: WiFi Configuration Issues (2 mutually exclusive, gate_tier=1) ---
# wrong_band: Archetype C (user fix only).
# channel_congestion: Archetype C with explicit phase ordering
#   (agent optimizes at phase 0, user switches at phase 1).

wrong_band = FaultLayer(
    name="wrong_band",
    gate_tier=1,
    known_info_fragment=(
        "my WiFi is really slow - I think I might be on the wrong frequency band"
    ),
    completion_fragment="your WiFi is connected on the correct band",
    atoms=[
        # Phase 0: Agent runs remote diagnostic (discovers wrong band)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="run_remote_diagnostic",
                args={"device_id": "{device_id}"},
                compare_args=["device_id"],
            ),
        ),
        # Phase 1: User switches WiFi band
        FaultAtom(
            phase=1,
            step_type="fix",
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
    ],
    resource_scope="wifi:{device_id}",
)

channel_congestion = FaultLayer(
    name="channel_congestion",
    gate_tier=1,
    known_info_fragment=(
        "my WiFi keeps dropping and is very slow, especially when my "
        "neighbors are home - I think there might be interference"
    ),
    completion_fragment="your WiFi channel has been optimized and connection is stable",
    atoms=[
        # Phase 0: Agent runs remote diagnostic (discovers congestion)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="run_remote_diagnostic",
                args={"device_id": "{device_id}"},
                compare_args=["device_id"],
            ),
        ),
        # Phase 1: Agent optimizes WiFi channel server-side
        FaultAtom(
            phase=1,
            step_type="fix",
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
        # Phase 2: User switches WiFi band to pick up new channel
        FaultAtom(
            phase=2,
            step_type="fix",
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
    resolution_category="connection",
)


# --- Group 4: DNS Issues (2 mutually exclusive, gate_tier=2) ---
# Service-level issues: logically downstream of device/hardware diagnostics.
# stale_dns: Archetype C (user fix only).
# wrong_dns_server: Archetype C with explicit phase ordering
#   (agent flushes at phase 0, user clears at phase 1).

stale_dns = FaultLayer(
    name="stale_dns",
    gate_tier=2,
    known_info_fragment=(
        "some websites won't load even though my internet connection "
        "seems fine otherwise"
    ),
    completion_fragment="your DNS cache has been cleared and websites load correctly",
    atoms=[
        FaultAtom(
            phase=0,
            step_type="fix",
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
    ],
    resource_scope="dns:{customer_id}",
)

wrong_dns_server = FaultLayer(
    name="wrong_dns_server",
    gate_tier=2,
    known_info_fragment=(
        "none of my websites are loading - I keep getting DNS errors "
        "in my browser"
    ),
    completion_fragment="your DNS server settings are correct and resolving properly",
    atoms=[
        # Phase 0: Agent flushes server-side DNS
        FaultAtom(
            phase=0,
            step_type="fix",
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
        # Phase 1: User clears local DNS cache
        FaultAtom(
            phase=1,
            step_type="fix",
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
    ],
    resource_scope="dns:{customer_id}",
)

dns_group = FaultLayerGroup(
    name="dns_issues",
    layers=[stale_dns, wrong_dns_server],
    resolution_category="connection",
)


# --- Group 5: Network Profile Issues (1 layer, gate_tier=2) ---
# Service-level: downstream of device diagnostics. Archetype C: agent-only fix.

corrupted_profile = FaultLayer(
    name="corrupted_profile",
    gate_tier=2,
    known_info_fragment=(
        "my internet speeds dropped dramatically and I think something "
        "is wrong on your end"
    ),
    completion_fragment="your network profile has been reset and is working",
    atoms=[
        FaultAtom(
            phase=0,
            step_type="fix",
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
    resolution_category="connection",
)


# --- Group 6: Speed Issues (1 layer, gate_tier=2) ---
# Service-level: downstream of device diagnostics.
# Archetype C with phases: agent diagnostic (phase 0), agent fix (phase 1),
# user verify (phase 2, confirm).

throttled_speed = FaultLayer(
    name="throttled_speed",
    gate_tier=2,
    known_info_fragment=(
        "my internet speed is way below what my {plan_name} plan should "
        "provide and I'd like this fixed"
    ),
    completion_fragment="your speed test shows the expected download speed",
    atoms=[
        # Phase 0: Agent checks service plan (discovers throttling)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="get_service_plan",
                args={"customer_id": "{customer_id}"},
                compare_args=["customer_id"],
            ),
        ),
        # Phase 1: Agent escalates speed tier
        FaultAtom(
            phase=1,
            step_type="fix",
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
        # Phase 2: User runs speed test to verify (confirmation step)
        FaultAtom(
            phase=2,
            step_type="confirm",
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
    ],
    predicate_field="can_escalate",
    resource_scope="speed:{customer_id}",
)

speed_group = FaultLayerGroup(
    name="speed_issues",
    layers=[throttled_speed],
    resolution_category="connection",
)


# --- Group 7: Outage Billing Issues (1 layer, gate_tier=2) ---
# Uses check_area_outages diagnostic + apply_service_credit fix.
# Agent discovers resolved outage via diagnostic, reads credit_amount,
# then applies the correct credit to the customer account.

outage_credit = FaultLayer(
    name="outage_credit",
    gate_tier=2,
    known_info_fragment=(
        "I heard there was an outage in my area recently and I was told "
        "I should be getting a credit on my bill"
    ),
    completion_fragment="your billing credit has been applied to your account",
    atoms=[
        # Phase 0: Agent checks area outages (discovers resolved outage with credit)
        FaultAtom(
            phase=0,
            step_type="diagnostic",
            fix=ActionSpec(
                tool_name="check_area_outages",
                args={"area_code": "{area_code}"},
                compare_args=["area_code"],
            ),
        ),
        # Phase 1: Agent applies the service credit from the outage
        # Init moves OUT001 to the customer's area (runs during init, before diagnostics)
        FaultAtom(
            phase=1,
            step_type="fix",
            init=InitCall(
                env_type="assistant", func_name="set_outage_area_code",
                args={"outage_id": "OUT001", "area_code": "{area_code}"},
            ),
            fix=ActionSpec(
                tool_name="apply_service_credit",
                args={"customer_id": "{customer_id}", "amount": 15.0},
                compare_args=["customer_id", "amount"],
            ),
            check=AssertionSpec(
                func_name="assert_billing_credit",
                args={"customer_id": "{customer_id}", "expected": 15.0},
                env_type="assistant",
                message_template="Customer {customer_id} should have $15.00 billing credit.",
            ),
        ),
    ],
    resource_scope="billing:{customer_id}",
)

outage_billing_group = FaultLayerGroup(
    name="outage_billing_issues",
    layers=[outage_credit],
    resolution_category="billing",
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
    completion_fragment="your router is back online with all lights showing normal status",
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
    completion_fragment="your account security has been fully restored and verified safe",
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
    completion_fragment="your internet connection is fully restored and working normally",
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
        account_group,          # Group 0: account access (1 layer, gate_tier=0)
        router_group,           # Group 1: router/firmware (3 layers, gate_tier=1)
        cable_group,            # Group 2: cable (1 layer, gate_tier=1)
        wifi_group,             # Group 3: wifi config (2 layers, gate_tier=1)
        dns_group,              # Group 4: dns (2 layers, gate_tier=2)
        network_profile_group,  # Group 5: network profile (1 layer, gate_tier=2)
        speed_group,            # Group 6: speed (1 layer, gate_tier=2)
        outage_billing_group,   # Group 7: outage billing (1 layer, gate_tier=2)
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
    max_faults=8,
    max_total_tasks=600,
    tool_grounding_block=(
        "After each troubleshooting step the agent performs or asks you to "
        "perform, use your check_my_connection tool to verify progress and "
        "report the results back to the agent. If check_my_connection shows "
        "any issues, tell the agent what issues remain so they can continue "
        "fixing them. Before ending the conversation, you MUST call "
        "check_my_connection one final time — if it shows anything other "
        "than 'All systems working normally', do not end the conversation."
    ),
)

TRANSFER_CONFIG = FaultLayerConfig(
    name="tech_support_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[
        FaultLayerGroup(
            name="unfixable_issues",
            layers=[hardware_failure, account_security_breach, infrastructure_outage],
            resolution_category="connection",
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
    resolution_instruction=(
        "your check_my_connection tool shows 'All systems working normally' "
        "with no remaining issues"
    ),
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
        policy_text = Path(TECH_SUPPORT_POLICY_PATH).read_text()
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
        dump_file(TECH_SUPPORT_TASK_SET_PATH, task_dicts)
        print(f"Saved {len(tasks)} tasks to {TECH_SUPPORT_TASK_SET_PATH}")

    return tasks
