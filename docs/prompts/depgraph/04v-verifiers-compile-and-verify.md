# Prompt 04v: Verifiers Compile + Verify

> Use this step instead of Steps 04–09 when building for the **verifiers** adapter.
> The verifiers path collapses the tau2 runtime scaffold pipeline into a single compilation
> step because there is no user simulator, no personas, no sync rules, no stop-gate injection,
> and no narrative enrichment.

## Instruction

Compile sampled tasks into `DepgraphTaskConfig` objects, author system/task prompts, wire
up the `DepgraphToolEnv`, and run a smoke test.

Exact execution contract:

1. Run each command in order.
2. Check pass status/output.
3. If any command fails: fix the reported issue before continuing.
4. Never skip validation steps.

Inputs to review before authoring:

- `data/tau2/domains/<domain>/task_specs.sampled.yaml` (from Step 03)
- `data/tau2/domains/<domain>/graph_contract.yaml` (from Step 02v)
- `data/tau2/domains/<domain>/sampling_request.yaml` (from Step 03)
- `src/tau2/domains/<domain>/tools.py` (from Step 02v)

## Required Step Order

Gate policy (hard): do not proceed to step N+1 until step N exits successfully.

### 1. Run preflight on sampled tasks

Verify all sampled tasks are still solvable:

```bash
uv run python - <<'PY'
from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs, load_sampling_request
from tau2.generators.depgraph.verifiers_compiler import compile_for_verifiers
from tau2.generators.depgraph.types import TerminalProfileSpec

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")
task_doc = load_task_specs("data/tau2/domains/<domain>/task_specs.sampled.yaml")
sampling = load_sampling_request("data/tau2/domains/<domain>/sampling_request.yaml")

result = compile_for_verifiers(
    contract,
    task_doc,
    terminal_profiles=sampling.terminal_profiles,
)

print(f"Compiled: {len(result.configs)} tasks")
print(f"Skipped:  {len(result.skipped)} tasks")
if result.errors:
    for err in result.errors:
        print(f"  ERROR: {err}")
    raise SystemExit(1)
print("PASS")
PY
```

### 2. Author system prompt and task prompt factory

Create `src/tau2/domains/<domain>/verifiers_config.py`:

```python
"""Verifiers configuration for <domain>."""

from tau2.generators.depgraph.types import GraphContractSpec, TaskIntent


SYSTEM_PROMPT = """You are an agent that <domain description>.

You have access to the following tools: <brief tool overview>.

<key constraints and rules the agent should follow>
"""


def task_prompt_factory(task: TaskIntent, contract: GraphContractSpec) -> str:
    """Generate a natural-language task prompt from a task intent.

    This is shown to the agent as the user's initial message. It should
    describe what needs to be done without revealing the solution path.
    """
    # Use task.start_world to describe the initial situation
    # Use task.goal_world to hint at what "done" looks like
    # Do NOT reveal required_actions or internal state paths
    return f"<natural language task description>"
```

Requirements for prompts:

1. **System prompt**: Describe the agent's role, available tools (by name only, not
   implementation details), and constraints. Do NOT mention `db`, world paths, or internal
   state. This is the verifiers equivalent of `policy.md` + `task_instructions`.
2. **Task prompt factory**: Generate a natural-language task description from the task
   intent. This replaces tau2's `reason_for_call` + `ticket` + `known_info`. The factory
   receives the full `TaskIntent` and `GraphContractSpec` so it can condition on start
   state, but it must not leak internal paths or required actions.
3. Task prompts should describe the situation and desired outcome at the user-observable
   surface, not enumerate internal state changes.

### 3. Compile for verifiers with prompts

```bash
uv run python - <<'PY'
from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs, load_sampling_request
from tau2.generators.depgraph.verifiers_compiler import compile_for_verifiers
from tau2.domains.<domain>.verifiers_config import SYSTEM_PROMPT, task_prompt_factory

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")
task_doc = load_task_specs("data/tau2/domains/<domain>/task_specs.sampled.yaml")
sampling = load_sampling_request("data/tau2/domains/<domain>/sampling_request.yaml")

result = compile_for_verifiers(
    contract,
    task_doc,
    terminal_profiles=sampling.terminal_profiles,
    system_prompt=SYSTEM_PROMPT,
    task_prompt_factory=task_prompt_factory,
)

assert result.success, f"Compile errors: {result.errors}"
print(f"Compiled {len(result.configs)} task configs")

# Verify all configs have prompts
for config in result.configs:
    assert config.system_prompt, f"Task {config.task_id} missing system_prompt"
    assert config.task_prompt, f"Task {config.task_id} missing task_prompt"
    # Verify no internal paths leaked into task prompt
    for path in ["start_world", "goal_world", "required_actions", "effects_world"]:
        assert path not in config.task_prompt, (
            f"Task {config.task_id} task_prompt leaks '{path}'"
        )

print("PASS")
PY
```

### 4. Wire up the environment and smoke test

```bash
uv run python - <<'PY'
import asyncio
from datasets import Dataset
from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs, load_sampling_request
from tau2.generators.depgraph.verifiers_compiler import compile_for_verifiers
from tau2.generators.depgraph.verifiers_env import DepgraphToolEnv
from tau2.generators.depgraph.verifiers_rubric import DepgraphRubric
from tau2.domains.<domain>.tools import TOOL_FUNCTIONS
from tau2.domains.<domain>.verifiers_config import SYSTEM_PROMPT, task_prompt_factory
import verifiers as vf

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")
task_doc = load_task_specs("data/tau2/domains/<domain>/task_specs.sampled.yaml")
sampling = load_sampling_request("data/tau2/domains/<domain>/sampling_request.yaml")

result = compile_for_verifiers(
    contract,
    task_doc,
    terminal_profiles=sampling.terminal_profiles,
    system_prompt=SYSTEM_PROMPT,
    task_prompt_factory=task_prompt_factory,
)

assert result.success, f"Compile errors: {result.errors}"

# Pick the first config for smoke test
config = result.configs[0]

# Build a minimal dataset
dataset = Dataset.from_dict({
    "prompt": [[{"role": "user", "content": config.task_prompt}]],
    "answer": [""],
    "example_id": [0],
})

# Construct the environment
env = DepgraphToolEnv(
    tool_functions=TOOL_FUNCTIONS,
    task_config_factory=lambda state: config,
    dataset=dataset,
)

# Verify tool registration
print(f"Registered {len(env.tool_map)} tools:")
for name in env.tool_map:
    print(f"  - {name}")

# Verify db parameter is hidden from all tool schemas
for tool_def in env.tool_defs:
    props = tool_def.parameters.get("properties", {})
    assert "db" not in props, f"Tool '{tool_def.name}' exposes 'db' in schema"
    required = tool_def.parameters.get("required", [])
    assert "db" not in required, f"Tool '{tool_def.name}' lists 'db' as required"

# Verify setup_state initializes DB correctly
async def check_setup():
    state = vf.State()
    state = await env.setup_state(state)
    assert "db" in state, "state['db'] not initialized"
    assert "task_config" in state, "state['task_config'] not initialized"
    # Check start_world was applied
    for path, value in config.start_world.items():
        assert state["db"][path] == value, (
            f"DB path '{path}' expected {value}, got {state['db'].get(path)}"
        )
    print(f"DB initialized with {len(state['db'])} paths")
    return state

state = asyncio.run(check_setup())
print("PASS")
PY
```

### 5. (Optional) Goal-checking dry run

Manually apply the expected solution to the DB and verify goal checking:

```bash
uv run python - <<'PY'
from tau2.generators.depgraph.verifiers_env import check_goal
from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs, load_sampling_request
from tau2.generators.depgraph.verifiers_compiler import compile_for_verifiers
from tau2.domains.<domain>.verifiers_config import SYSTEM_PROMPT, task_prompt_factory

contract = load_graph_contract("data/tau2/domains/<domain>/graph_contract.yaml")
task_doc = load_task_specs("data/tau2/domains/<domain>/task_specs.sampled.yaml")
sampling = load_sampling_request("data/tau2/domains/<domain>/sampling_request.yaml")

result = compile_for_verifiers(
    contract,
    task_doc,
    terminal_profiles=sampling.terminal_profiles,
    system_prompt=SYSTEM_PROMPT,
    task_prompt_factory=task_prompt_factory,
)

config = result.configs[0]

# Simulate: start with start_world, then manually set goal state
db = dict(config.start_world)
# Apply expected goal state manually:
for pred in config.goal_world:
    db[pred.path] = pred.value

bindings = set()  # Add any goal_bindings if present

reward, details = check_goal(db, bindings, config.goal_world, config.goal_bindings)
print(f"Reward: {reward}")
for k, v in details.items():
    print(f"  {k}: {'PASS' if v else 'FAIL'}")
assert reward == 1.0, f"Expected reward 1.0, got {reward}"
print("PASS")
PY
```

## Authored Files Summary

The verifiers path produces these domain-specific files:

| File | Authored by | Purpose |
|---|---|---|
| `data/tau2/domains/<domain>/graph_contract.yaml` | Coding agent (Step 02v) | Shared graph contract |
| `data/tau2/domains/<domain>/sampling_request.yaml` | Coding agent (Step 03) | Shared sampling config |
| `src/tau2/domains/<domain>/tools.py` | Coding agent (Step 02v) | Tool functions with `db` arg |
| `src/tau2/domains/<domain>/verifiers_config.py` | Coding agent (Step 04v) | System prompt + task prompt factory |
| `data/tau2/domains/<domain>/task_specs.sampled.yaml` | Generated (Step 03) | Sampled task intents |

Compare with the tau2 path which additionally requires: `personas.yaml`, `runtime_defaults.yaml`,
`stop_gate_map.yaml`, `policy.md`, `user_tools.py`, `user_data_model.py`, `data_model.py`,
`environment.py`, `task_specs.runtime.yaml`, and multiple generated intermediate files.

## What Is NOT Needed (vs tau2 path)

- No `personas.yaml` — no user simulator
- No `runtime_defaults.yaml` — no runtime scaffold
- No `stop_gate_map.yaml` — no checker-based stop; uses `no_tools_called`
- No `policy.md` — replaced by `SYSTEM_PROMPT` in `verifiers_config.py`
- No `user_tools.py` — no user actions
- No `user_data_model.py` — no user DB
- No `data_model.py` — DB is a plain dict
- No `environment.py` — replaced by `DepgraphToolEnv`
- No `task_specs.runtime.yaml` — no runtime enrichment pipeline
- No `task_context_bindings.yaml` — no entity context plumbing
- No `task_narrative_briefs.yaml` — no narrative scaffold
- No `review_bundle.md` — gap review uses simpler checks

## Report Format (required)

After running all commands, report:

1. Pass/fail per step
2. Number of compiled task configs
3. Tool registration check: all tools registered, `db` hidden
4. DB initialization check: start_world applied correctly
5. Goal-checking dry run result (if run)
