# tau2 Domain Creation Guide

How to build synthetic task domains for the tau2 benchmark. This guide captures lessons learned from building the smart_home domain and patterns from the telecom domain.

## Architecture

### The Two-DB Pattern

Every domain has two databases that represent different views of the world:

- **Agent DB** (`data_model.py`) — Backend state the agent can read/modify. Device settings, account data, network status, firmware versions. The agent has full access.
- **User DB** (`user_data_model.py`) — Physical world state the user observes. Room temperature, LED indicator colors, device responsiveness, WiFi connectivity. The user has full access.

These are bridged by **sync rules** in `environment.py`. Sync is the "physics engine" — it propagates backend state to the physical world deterministically after every tool call.

### Tool Division

- **Agent tools** (`tools.py`) — Backend operations: read device status, modify settings, reboot devices, check logs, manage infrastructure. Decorated with `@is_tool(ToolType.READ/WRITE)`.
- **User tools** (`user_tools.py`) — Physical world interactions: check room temperature, power-cycle devices, restart router, run diagnostics, verify comfort. Also `@is_tool`.

**The rule**: Agent can never do physical things. User can never do backend things. If an action could go either way, your tool division is fuzzy and needs rethinking.

### Fix Action Roles

Every fix action falls into one of three categories:

1. **Agent diagnostic** (read-only): `check_device_logs`, `check_home_network` — agent gathers info before acting.
2. **Agent repair** (write): `reboot_device`, `update_device_firmware`, `restart_hub` — agent fixes backend state.
3. **User verification/action** (physical): `power_cycle_device`, `restart_router`, `verify_room_comfort` — user acts in the physical world.

### Scenario Composition

The generators framework composes tasks from independent scenario groups:

1. **ScenarioGroup** — A set of mutually exclusive failure scenarios for one dimension (e.g., "thermostat issues" with variants: wrong_mode, wrong_temp, thermostat_off).
2. **compose_scenarios()** — Takes the cartesian product across groups (with None option per group), producing all valid combinations.
3. **Task validator** — Filters combinations (e.g., require at least 2 simultaneous issues).
4. **generate_tasks()** — Composes scenarios, applies personas, generates task objects.

Each scenario has:
- `init_funcs` — List of functions that return `EnvFunctionCall` lists to break the environment.
- `fix_funcs` — List of functions that return `ToolCall` lists to repair the environment.

## File Structure

```
src/tau2/domains/<domain_name>/
  __init__.py
  data_model.py        # Agent DB schema (extends DB)
  user_data_model.py   # User DB schema (extends DB)
  tools.py             # Agent toolkit (extends ToolKitBase)
  user_tools.py        # User toolkit (extends ToolKitBase)
  environment.py       # Environment + sync_tools() + get_environment()
  scenarios.py         # Personas, groups, init/fix functions, validator
  utils.py             # Paths and constants
  create_tasks.py      # Task generation script

data/tau2/domains/<domain_name>/
  db.json              # Default agent DB state
  user_db.json         # Default user DB state
  policy.md            # Agent policy document
  tasks.json           # Generated tasks (output)

tests/test_domains/test_<domain_name>/
  __init__.py
  test_tools.py
  test_user_tools.py
  test_environment.py
```

## The Knobs (Difficulty Levers)

### 1. Number of Scenario Groups
Each group is an independent failure dimension. More groups = higher combinatorial ceiling.
- Smart home: 6 groups (WiFi, hub, connectivity, firmware, thermostat, lighting)
- Telecom: 7+ groups

### 2. Scenarios per Group
Variants within a group add variety without increasing per-task difficulty. 2-3 scenarios per group is typical.

### 3. Scenario Count per Task (the primary difficulty dial)
Controlled by `make_task_validator(min_scenarios, max_scenarios)`. This single knob controls:
- Number of fix actions (more scenarios = more steps)
- Coordination complexity (more interleaving of agent/user actions)
- Infrastructure dependencies (more likely to include WiFi/hub issues)

Difficulty presets:
| Level  | min | max | Typical tasks | Avg fix actions |
|--------|-----|-----|---------------|-----------------|
| Easy   | 1   | 2   | ~60           | ~4              |
| Medium | 2   | 3   | ~210          | ~8              |
| Hard   | 3   | 5   | ~530          | ~14             |
| Expert | 4   | 6   | ~420          | ~17             |

### 4. Multi-Party Action Split
The ratio of `requestor="user"` vs `requestor="assistant"` in fix sequences. Higher user-side percentage = harder tasks because the agent must instruct rather than just act.
- Smart home: 55% user-side
- Telecom: 76% user-side

### 5. Personas
Add behavioral friction orthogonal to the task itself. A "tech_savvy" user cooperates efficiently. An "elderly" user needs step-by-step guidance and may confuse the agent. Personas consistently affect pass rates more than task complexity.

### 6. Group Ordering
Groups must be ordered by dependency: infrastructure first, then device-level, then settings. Fix actions execute in group order during composition.

## Design Principles

### Sync Rules (The Physics Engine)

Sync propagates agent DB state to user DB state. It runs after every tool call.

**Sync SHOULD**:
- Propagate device settings to physical world (thermostat target_temp → room temperature)
- Reflect infrastructure state (WiFi down → devices unresponsive)
- Be deterministic and predictable

**Sync MUST NOT**:
- Replicate the effect of any explicit fix action
- Bypass the need for user physical actions
- Auto-recover state that a scenario deliberately broke

**The test**: If you can remove any fix action from a task's golden sequence and the task still passes, your sync is doing too much.

### The No-Redundancy Property

For every user fix action, there must be a state change that ONLY that action can produce. If sync or another action achieves the same effect, the fix action is redundant and will create false positives.

**Pattern: State flags for user actions**

When sync realistically auto-recovers some state (e.g., devices reconnecting after WiFi restore), use a dedicated flag that only the user action can clear:

```python
# In user_data_model.py
device_needs_reset: Dict[str, bool] = {}  # Only power_cycle_device clears this

# In scenario init
EnvFunctionCall(env_type="user", func_name="set_device_needs_reset",
                arguments={"device_id": "D001", "needs_reset": True})

# In user_tools.py power_cycle_device()
self.db.device_needs_reset[device_id] = False

# In env assertion
def assert_system_healthy(self) -> bool:
    # ... other checks ...
    for device_id, needs_reset in self.db.device_needs_reset.items():
        if needs_reset:
            return False
    return True
```

This lets sync do realistic physics while ensuring every user action is necessary.

### Policy Completeness

The agent CANNOT see user tools. The policy is its only guide for what to ask the user to do.

**Every user-side fix action must be mentioned by name in the policy.** If the policy doesn't say "instruct the user to restart_router", the agent will never ask for it, and every task requiring it will fail.

Example from smart_home policy:
```markdown
- **User actions the agent can request**: The user can physically restart_router,
  power_cycle_device, check_device_indicator, run_system_diagnostic,
  verify_room_comfort, and check_room_temperature.
```

### Init Function Design

Init functions create the broken state via `EnvFunctionCall` lists. Key rules:

1. **sync_tools() runs after each EnvFunctionCall**. If step 1 sets device mode and step 2 sets room temperature, sync may overwrite the room temp between steps.
2. **Set user-side state LAST** in init functions, after all agent-side changes, so sync doesn't overwrite it.
3. **Set state flags explicitly** — if a scenario requires `power_cycle_device` in its fix, the init must set `device_needs_reset=True`.

### Fix Function Design

Fix functions return `ToolCall` lists with explicit `requestor` fields:

```python
def fix_hub_offline(env) -> list[ToolCall]:
    return [
        ToolCall(requestor="assistant", name="restart_hub", arguments={}),
        ToolCall(requestor="user", name="power_cycle_device", arguments={"device_id": "D001"}),
        ToolCall(requestor="user", name="run_system_diagnostic", arguments={}),
    ]
```

Pattern: agent fixes backend → user verifies/acts physically → user confirms.

### Verification

Use relaxed verification that checks before/after state, not per-action:

1. Fresh environment should be "fixed" (all assertions pass)
2. After init, environment should be "broken" (at least one assertion fails)
3. After ALL fix actions, environment should be "fixed" again

Do NOT check `is_fixed()` after each individual fix action — trailing read-only actions (verify_room_comfort, check_light) run after the env is already fixed and will cause false failures.

## Anti-Patterns

### 1. Sync replicating fix actions
**Symptom**: Model skips a fix action but task still passes.
**Cause**: Sync auto-restores state that the fix action is supposed to restore.
**Fix**: Add a state flag only clearable by the fix action. Check it in env assertions.

### 2. Missing user tools from policy
**Symptom**: Agent never asks user to perform a specific action. 0% pass rate on tasks requiring it.
**Cause**: Policy doesn't mention the user tool by name.
**Fix**: Explicitly list all user tools in the policy. Automate this check.

### 3. Wrong composition order
**Symptom**: Fix actions fail because they operate on devices in wrong state (e.g., modifying settings on an offline device).
**Cause**: Groups not ordered by dependency. Device-level fixes run before infrastructure fixes.
**Fix**: Order groups: infrastructure → device-level → settings. Verify composition preserves order (don't sort alphabetically).

### 4. Init not resilient to sync
**Symptom**: Init sets room temp to 58, but after sync it's back to 72.
**Cause**: sync_tools() runs between init steps. An earlier step brings device online, sync propagates its settings, overwriting the manually set room temp.
**Fix**: Set user-side state (room temp, indicators) in the LAST init step, after all agent-side changes.

### 5. Redundant fix actions in composed scenarios
**Symptom**: Task verification passes but action checks show some golden actions weren't needed.
**Cause**: Two scenarios both include the same fix action, or sync handles recovery that a fix action was supposed to handle.
**Fix**: Run redundancy detection — drop each action one at a time, check if task still passes.

### 6. Strict per-action verification
**Symptom**: Verification reports "environment already fixed after N actions" for tasks with trailing read-only user actions.
**Cause**: Verifier checks is_fixed() after each action. Read-only actions (verify_room_comfort, check_light) don't change state.
**Fix**: Use relaxed verification (check before/after only, not per-action).

### 7. User simulator terminating early
**Symptom**: Agent gives correct instructions, user agrees, but sends ###STOP### before executing.
**Cause**: Weaker user simulator model decides the issue is "resolved" when it hears the plan, not when it's executed.
**Fix**: Use a stronger model for user simulation, or improve task_instructions to emphasize that the user should only stop after physically verifying the fix.

## Validation Checklist

Run these checks before considering a domain complete:

### Automated Checks
- [ ] All generated tasks verify (0 failures in `create_tasks.py`)
- [ ] Unit tests pass for tools, user_tools, and environment
- [ ] **Redundancy check**: For each task, drop each fix action one at a time. If task still passes, that action is redundant.
- [ ] **Policy completeness check**: For every user-side fix action name across all scenarios, verify it appears in policy.md.
- [ ] **Composition order check**: Replay fix sequences for 6-scenario tasks, verify no action fails due to wrong device state.

### Manual Checks
- [ ] Run simulation with strong model (e.g., gpt-5.2) on easy difficulty. Expect >50% pass rate.
- [ ] Run simulation with weak model on easy difficulty. Expect >0% pass rate.
- [ ] For any 0% pass rate, verify it's a model error not a logic error by replaying fix actions programmatically.
- [ ] Review failures: is the agent missing info (policy bug) or making bad decisions (model limitation)?

## Difficulty Calibration Protocol

1. Generate tasks at easy difficulty first.
2. Run with a strong model. If pass rate is <50%, there's likely a logic/policy bug.
3. Verify failing tasks by replaying golden fix actions programmatically.
4. If replay passes but model fails, it's a model error. If replay fails, it's a logic error.
5. Fix logic errors. Then scale up to medium/hard.
6. Run with target weak model. Calibrate difficulty so pass rate is 20-50% (challenging but not impossible).

## Reward System

Tasks use `reward_basis` to determine what counts:

- **ENV_ASSERTION** (recommended default): Checks end-state correctness. Rewards correct outcomes regardless of exact method. All env assertions must pass for reward=1.0.
- **DB**: Exact hash match of entire database state. Very strict — any field difference = 0. Use sparingly.
- **ACTION**: Checks if specific tool calls appeared in the transcript. Binary per-action.
- **NL_ASSERTION**: LLM-judged checks on conversation quality.
- **COMMUNICATE**: Verifies agent communicated specific information.

For most domains, **ENV_ASSERTION alone** is the right choice. It tests outcomes, not process, allowing models to find alternative valid solutions.

## Example: Creating a New Domain

### Step 1: Define the world

What is the backend? What is the physical world? What connects them?

```
Backend (agent DB):  Device settings, account data, system status
Physical (user DB):  What the user sees, feels, experiences
Sync:                Backend state → physical world (deterministic)
```

### Step 2: Define tools

What can the agent do remotely? What can only the user do physically?

```
Agent: read status, modify settings, reboot, check logs, escalate
User:  check physical indicators, power cycle, verify comfort, run diagnostics
```

### Step 3: Define failure dimensions (scenario groups)

What independent things can go wrong? Each becomes a ScenarioGroup.

```
Group 1: Network/connectivity issues
Group 2: Infrastructure issues (hub, server)
Group 3: Device-level issues (offline, firmware)
Group 4: Configuration issues (wrong settings)
Group 5: User-facing issues (comfort, display)
```

### Step 4: Define scenarios within each group

For each group, what are 2-3 variants?

```
Network: router_down, interference
Hub: offline, firmware_corrupt
Device: offline, outdated_firmware, corrupt_firmware
Config: wrong_mode, wrong_value, disabled
Display: wrong_brightness, turned_off
```

### Step 5: Write init and fix functions

For each scenario:
- Init: What state do you set to create the problem?
- Fix: What sequence of agent + user actions resolves it?
- Ensure every user action sets a flag only it can clear.

### Step 6: Write sync rules

How does backend state affect physical world? Order matters:
1. Infrastructure checks (WiFi, hub) — early return if down
2. Device state propagation (settings → room state)
3. Status indicators (online → green, offline → red)

### Step 7: Write policy

Must include:
- When to use each agent tool
- What user actions the agent can request (list by name)
- Troubleshooting order (infrastructure → device → settings)
- Escalation rules

### Step 8: Validate

Follow the validation checklist above. Generate easy tasks first, test with strong model, verify failures, scale up.
