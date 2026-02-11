from typing import Optional

from tau2.data_model.message import ToolCall
from tau2.data_model.tasks import EnvAssertion, EnvFunctionCall
from tau2.domains.smart_home.environment import SmartHomeEnvironment
from tau2.generators.types import Persona, Scenario, ScenarioGroup, UserTemplate

# === Personas ===

PERSONAS = [
    Persona(name="None", description=None),
    Persona(
        name="elderly",
        description="You are a 72-year-old retired teacher. You are not very comfortable with technology and prefer simple, step-by-step instructions. You may ask the agent to repeat things.",
    ),
    Persona(
        name="tech_savvy",
        description="You are a 30-year-old software engineer. You are very comfortable with technology and prefer concise, technical responses. You may suggest your own troubleshooting steps.",
    ),
]

# === User Template ===

USER_TEMPLATE = UserTemplate(
    domain="smart_home",
    reason_for_call="Your smart home is not working properly. Devices are misbehaving: the temperature may be wrong, lights may not be working, devices may be unresponsive, or you may have network/hub issues.",
    known_info="You are {name} (user ID: {user_id}). Your home has devices in the living room, bedroom, and kitchen.",
    task_instructions="If the agent asks you to check something in your home, use your tools to check and report back. If the agent asks you to physically interact with a device (power cycle, restart router, etc.), use your tools to do so. You will consider the issue resolved only when your home environment matches what you expect: correct temperature, correct lighting, responsive devices, and healthy network. If a device cannot be fixed, you expect the agent to escalate to a human technician.",
    ticket="User {name} (ID: {user_id}) is reporting issues with their smart home devices. Devices may have incorrect settings, be offline, have firmware issues, or there may be network/hub problems. The user expects the home to be comfortable with correct temperature, lighting, and all systems operational.",
    purpose="Test resolution of smart home device issues including thermostat, lighting, connectivity, network, hub, and firmware problems.",
)


# === Environment setup ===

def set_surrounding(*args, **kwargs) -> list[EnvFunctionCall]:
    """Set user identity for the scenario."""
    return [
        EnvFunctionCall(
            env_type="user",
            func_name="set_user_info",
            arguments={"name": "Alice Johnson", "user_id": "U001"},
        )
    ]


def get_template_vars(env: SmartHomeEnvironment) -> dict[str, str]:
    """Get template variables from the environment state."""
    return {
        "name": env.user_tools.db.user_name or "Unknown",
        "user_id": env.user_tools.db.user_id or "Unknown",
    }


# === Env Assertions ===

def get_env_assertions(expected_success: bool) -> list[EnvAssertion]:
    """Get environment assertions to check if the home is in a good state."""
    if expected_success:
        return [
            EnvAssertion(
                env_type="user",
                func_name="assert_room_temp_in_range",
                arguments={"room_name": "living_room", "min_temp": 68.0, "max_temp": 76.0},
                message="Living room temperature should be in comfortable range.",
            ),
            EnvAssertion(
                env_type="user",
                func_name="assert_light_state",
                arguments={"room_name": "living_room", "expected_on": True, "expected_brightness": 100},
                message="Living room lights should be on at full brightness.",
            ),
            EnvAssertion(
                env_type="user",
                func_name="assert_wifi_connected",
                arguments={"expected": True},
                message="WiFi should be connected.",
            ),
            EnvAssertion(
                env_type="user",
                func_name="assert_hub_online",
                arguments={"expected": True},
                message="Smart hub should be online.",
            ),
            EnvAssertion(
                env_type="user",
                func_name="assert_system_healthy",
                arguments={},
                message="System should be healthy (WiFi up, hub online, all indicators green).",
            ),
        ]
    else:
        return [
            EnvAssertion(
                env_type="assistant",
                func_name="assert_device_status",
                arguments={"device_id": "D001", "expected_status": "online"},
                assert_value=False,
                message="Device should still be offline (unfixable).",
            ),
        ]


def is_fixed(env: SmartHomeEnvironment) -> bool:
    """Check if the smart home is in a fully working state."""
    assertions = get_env_assertions(expected_success=True)
    success = True
    for assertion in assertions:
        success = success and env.run_env_assertion(
            assertion, raise_assertion_error=False
        )
    return success


# === Task Validator ===

def make_task_validator(min_scenarios: int = 2, max_scenarios: Optional[int] = None):
    """Create a validator that filters by scenario count.

    Difficulty guide:
      Easy:   min=1, max=2  (~60 tasks, avg ~3 fix actions)
      Medium: min=2, max=3  (~210 tasks, avg ~7 fix actions)
      Hard:   min=3, max=5  (~530 tasks, avg ~14 fix actions)
      Expert: min=4, max=6  (~420 tasks, avg ~17 fix actions)
    """
    def task_validator(scenarios: list[Optional[Scenario]]) -> bool:
        active = [s for s in scenarios if s is not None]
        if len(active) < min_scenarios:
            return False
        if max_scenarios is not None and len(active) > max_scenarios:
            return False
        return True
    return task_validator


# Default: medium-hard (2+ scenarios)
task_validator = make_task_validator(min_scenarios=2)


# === Init functions (create issues) ===

# --- Group 1: WiFi/Network issues ---

def init_wifi_router_down(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """WiFi router is down, all devices lose connectivity."""
    return [
        EnvFunctionCall(
            env_type="user",
            func_name="set_wifi_connected",
            arguments={"connected": False},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 58.0},
        ),
    ]


def init_wifi_interference(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """WiFi interference corrupted device settings and caused disconnect."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_setting",
            arguments={"device_id": "D001", "setting_name": "mode", "setting_value": "off"},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_status",
            arguments={"device_id": "D001", "status": "offline"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_device_needs_reset",
            arguments={"device_id": "D001", "needs_reset": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 58.0},
        ),
    ]


# --- Group 2: Hub issues ---

def init_hub_offline(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Smart hub is offline, hub-connected devices are unreachable."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_hub_status",
            arguments={"status": "offline"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_hub_online",
            arguments={"online": False},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_device_needs_reset",
            arguments={"device_id": "D001", "needs_reset": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 58.0},
        ),
    ]


def init_hub_firmware_corrupt(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Hub has corrupt firmware, needs restart + device firmware update."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_hub_status",
            arguments={"status": "offline"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_hub_online",
            arguments={"online": False},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_firmware",
            arguments={"device_id": "D001", "version": "1.0.0"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_device_needs_reset",
            arguments={"device_id": "D001", "needs_reset": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 58.0},
        ),
    ]


# --- Group 3: Connectivity issues ---

def init_device_offline(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Living room thermostat offline (power cycle + reboot can fix)."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_status",
            arguments={"device_id": "D001", "status": "offline"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_device_needs_reset",
            arguments={"device_id": "D001", "needs_reset": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 58.0},
        ),
    ]


# --- Group 4: Thermostat issues ---

def init_wrong_thermostat_mode(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Set thermostat to cool mode (wrong for heating season)."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_setting",
            arguments={"device_id": "D001", "setting_name": "mode", "setting_value": "cool"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 60.0},
        ),
    ]


def init_wrong_target_temp(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Set thermostat target to 55 (too cold)."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_setting",
            arguments={"device_id": "D001", "setting_name": "target_temp", "setting_value": 55},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 55.0},
        ),
    ]


def init_thermostat_off(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Thermostat mode off and device crashed."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_setting",
            arguments={"device_id": "D001", "setting_name": "mode", "setting_value": "off"},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_status",
            arguments={"device_id": "D001", "status": "offline"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_device_needs_reset",
            arguments={"device_id": "D001", "needs_reset": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 58.0},
        ),
    ]


# --- Group 5: Lighting issues ---

def init_light_off(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Turn living room light off."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_setting",
            arguments={"device_id": "D002", "setting_name": "on", "setting_value": False},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_light_state",
            arguments={"room_name": "living_room", "lights_on": False, "brightness": 0},
        ),
    ]


def init_light_too_dim(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Set living room light brightness to 10."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_setting",
            arguments={"device_id": "D002", "setting_name": "brightness", "setting_value": 10},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_light_state",
            arguments={"room_name": "living_room", "lights_on": True, "brightness": 10},
        ),
    ]


# --- Group 6: Firmware issues ---

def init_outdated_firmware(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Device has outdated firmware causing disconnect."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_firmware",
            arguments={"device_id": "D001", "version": "1.0.0"},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_status",
            arguments={"device_id": "D001", "status": "offline"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_device_needs_reset",
            arguments={"device_id": "D001", "needs_reset": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 58.0},
        ),
    ]


def init_firmware_corrupt(env: SmartHomeEnvironment) -> list[EnvFunctionCall]:
    """Device has corrupt firmware, needs factory reset + reconfigure."""
    return [
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_firmware",
            arguments={"device_id": "D001", "version": "0.0.1"},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_setting",
            arguments={"device_id": "D001", "setting_name": "mode", "setting_value": "off"},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_setting",
            arguments={"device_id": "D001", "setting_name": "target_temp", "setting_value": 0},
        ),
        EnvFunctionCall(
            env_type="assistant",
            func_name="set_device_status",
            arguments={"device_id": "D001", "status": "offline"},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_device_needs_reset",
            arguments={"device_id": "D001", "needs_reset": True},
        ),
        EnvFunctionCall(
            env_type="user",
            func_name="set_room_temperature",
            arguments={"room_name": "living_room", "temperature": 58.0},
        ),
    ]


# === Fix functions ===

# --- Group 1: WiFi/Network fixes ---

def fix_wifi_router_down(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: user restarts router, agent checks network, user runs diagnostic."""
    return [
        ToolCall(
            requestor="user",
            name="restart_router",
            arguments={},
        ),
        ToolCall(
            requestor="assistant",
            name="check_home_network",
            arguments={"user_id": "U001"},
        ),
        ToolCall(
            requestor="user",
            name="run_system_diagnostic",
            arguments={},
        ),
    ]


def fix_wifi_interference(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent resets device to defaults (brings online), user power cycles, user checks."""
    return [
        ToolCall(
            requestor="assistant",
            name="reset_device_to_defaults",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="power_cycle_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="check_device_indicator",
            arguments={"device_id": "D001"},
        ),
    ]


# --- Group 2: Hub fixes ---

def fix_hub_offline(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent restarts hub, user power cycles device, user runs diagnostic."""
    return [
        ToolCall(
            requestor="assistant",
            name="restart_hub",
            arguments={},
        ),
        ToolCall(
            requestor="user",
            name="power_cycle_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="run_system_diagnostic",
            arguments={},
        ),
    ]


def fix_hub_firmware_corrupt(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: restart hub first, then update firmware, reboot device, user verifies."""
    return [
        ToolCall(
            requestor="assistant",
            name="restart_hub",
            arguments={},
        ),
        ToolCall(
            requestor="assistant",
            name="update_device_firmware",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="assistant",
            name="reboot_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="power_cycle_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="run_system_diagnostic",
            arguments={},
        ),
    ]


# --- Group 3: Connectivity fixes ---

def fix_device_offline(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: user power cycles, agent reboots, user checks indicator."""
    return [
        ToolCall(
            requestor="user",
            name="power_cycle_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="assistant",
            name="reboot_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="check_device_indicator",
            arguments={"device_id": "D001"},
        ),
    ]


# --- Group 4: Thermostat fixes ---

def fix_wrong_thermostat_mode(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent sets mode to heat, user verifies comfort."""
    return [
        ToolCall(
            requestor="assistant",
            name="update_device_setting",
            arguments={"device_id": "D001", "setting_name": "mode", "setting_value": "heat"},
        ),
        ToolCall(
            requestor="user",
            name="verify_room_comfort",
            arguments={"room_name": "living_room"},
        ),
    ]


def fix_wrong_target_temp(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent sets target temp to 72, user verifies comfort."""
    return [
        ToolCall(
            requestor="assistant",
            name="update_device_setting",
            arguments={"device_id": "D001", "setting_name": "target_temp", "setting_value": 72},
        ),
        ToolCall(
            requestor="user",
            name="verify_room_comfort",
            arguments={"room_name": "living_room"},
        ),
    ]


def fix_thermostat_off(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent reboots device, sets mode to heat, user power cycles, user verifies."""
    return [
        ToolCall(
            requestor="assistant",
            name="reboot_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="assistant",
            name="update_device_setting",
            arguments={"device_id": "D001", "setting_name": "mode", "setting_value": "heat"},
        ),
        ToolCall(
            requestor="user",
            name="power_cycle_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="verify_room_comfort",
            arguments={"room_name": "living_room"},
        ),
    ]


# --- Group 5: Lighting fixes ---

def fix_light_off(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent turns light on, user checks light."""
    return [
        ToolCall(
            requestor="assistant",
            name="update_device_setting",
            arguments={"device_id": "D002", "setting_name": "on", "setting_value": True},
        ),
        ToolCall(
            requestor="user",
            name="check_light",
            arguments={"room_name": "living_room"},
        ),
    ]


def fix_light_too_dim(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent sets brightness to 100, user checks light."""
    return [
        ToolCall(
            requestor="assistant",
            name="update_device_setting",
            arguments={"device_id": "D002", "setting_name": "brightness", "setting_value": 100},
        ),
        ToolCall(
            requestor="user",
            name="check_light",
            arguments={"room_name": "living_room"},
        ),
    ]


# --- Group 6: Firmware fixes ---

def fix_outdated_firmware(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent checks logs, updates firmware, reboots; user power cycles and verifies."""
    return [
        ToolCall(
            requestor="assistant",
            name="check_device_logs",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="assistant",
            name="update_device_firmware",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="assistant",
            name="reboot_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="power_cycle_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="verify_room_comfort",
            arguments={"room_name": "living_room"},
        ),
    ]


def fix_firmware_corrupt(env: SmartHomeEnvironment) -> list[ToolCall]:
    """Fix: agent resets to defaults, user power cycles, user verifies."""
    return [
        ToolCall(
            requestor="assistant",
            name="reset_device_to_defaults",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="power_cycle_device",
            arguments={"device_id": "D001"},
        ),
        ToolCall(
            requestor="user",
            name="verify_room_comfort",
            arguments={"room_name": "living_room"},
        ),
    ]


# === Scenario Definitions ===

# Group 1: WiFi/Network issues (2 scenarios)
wifi_router_down_scenario = Scenario(
    name="wifi_router_down",
    description="WiFi router is down, all devices lost connectivity",
    init_funcs=[init_wifi_router_down],
    fix_funcs=[fix_wifi_router_down],
)

wifi_interference_scenario = Scenario(
    name="wifi_interference",
    description="WiFi interference corrupted device settings, needs reset and power cycle",
    init_funcs=[init_wifi_interference],
    fix_funcs=[fix_wifi_interference],
)

wifi_group = ScenarioGroup(
    scenarios=[wifi_router_down_scenario, wifi_interference_scenario]
)

# Group 2: Hub issues (2 scenarios)
hub_offline_scenario = Scenario(
    name="hub_offline",
    description="Smart hub is offline, hub-connected devices unreachable",
    init_funcs=[init_hub_offline],
    fix_funcs=[fix_hub_offline],
)

hub_firmware_corrupt_scenario = Scenario(
    name="hub_firmware_corrupt",
    description="Hub firmware is corrupt, needs restart + firmware update",
    init_funcs=[init_hub_firmware_corrupt],
    fix_funcs=[fix_hub_firmware_corrupt],
)

hub_group = ScenarioGroup(
    scenarios=[hub_offline_scenario, hub_firmware_corrupt_scenario]
)

# Group 3: Connectivity issues (1 scenario)
device_offline_scenario = Scenario(
    name="device_offline",
    description="Living room thermostat is offline (power cycle + reboot fixes it)",
    init_funcs=[init_device_offline],
    fix_funcs=[fix_device_offline],
)

connectivity_group = ScenarioGroup(
    scenarios=[device_offline_scenario]
)

# Group 4: Thermostat issues (3 scenarios)
thermostat_wrong_mode = Scenario(
    name="wrong_mode",
    description="Thermostat is in cool mode instead of heat",
    init_funcs=[init_wrong_thermostat_mode],
    fix_funcs=[fix_wrong_thermostat_mode],
)

thermostat_wrong_temp = Scenario(
    name="wrong_target_temp",
    description="Thermostat target temperature is too low (55 instead of 72)",
    init_funcs=[init_wrong_target_temp],
    fix_funcs=[fix_wrong_target_temp],
)

thermostat_off = Scenario(
    name="thermostat_off",
    description="Thermostat mode is off and device crashed",
    init_funcs=[init_thermostat_off],
    fix_funcs=[fix_thermostat_off],
)

thermostat_group = ScenarioGroup(
    scenarios=[thermostat_wrong_mode, thermostat_wrong_temp, thermostat_off]
)

# Group 5: Lighting issues (2 scenarios)
light_off_scenario = Scenario(
    name="light_off",
    description="Living room light is turned off",
    init_funcs=[init_light_off],
    fix_funcs=[fix_light_off],
)

light_too_dim_scenario = Scenario(
    name="light_too_dim",
    description="Living room light brightness is only 10%",
    init_funcs=[init_light_too_dim],
    fix_funcs=[fix_light_too_dim],
)

lighting_group = ScenarioGroup(
    scenarios=[light_off_scenario, light_too_dim_scenario]
)

# Group 6: Firmware issues (2 scenarios)
outdated_firmware_scenario = Scenario(
    name="outdated_firmware",
    description="Device has outdated firmware causing disconnect",
    init_funcs=[init_outdated_firmware],
    fix_funcs=[fix_outdated_firmware],
)

firmware_corrupt_scenario = Scenario(
    name="firmware_corrupt",
    description="Device firmware is corrupt, needs factory reset and reconfiguration",
    init_funcs=[init_firmware_corrupt],
    fix_funcs=[fix_firmware_corrupt],
)

firmware_group = ScenarioGroup(
    scenarios=[outdated_firmware_scenario, firmware_corrupt_scenario]
)

# All scenario groups - ORDER MATTERS: infrastructure first, then device-level
SCENARIO_GROUPS = [
    wifi_group,          # Group 1: WiFi fixes run first
    hub_group,           # Group 2: Hub fixes second
    connectivity_group,  # Group 3: Device connectivity third
    firmware_group,      # Group 4: Firmware fixes fourth (bring device online)
    thermostat_group,    # Group 5: Thermostat settings fifth (need device online)
    lighting_group,      # Group 6: Lighting settings last
]
