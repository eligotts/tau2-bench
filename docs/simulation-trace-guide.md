# Simulation Trace File Guide

This guide explains the structure of tau2-bench simulation trace files so you can quickly diagnose failures without exploratory reads.

## File Location and Naming

Simulation traces live in `data/simulations/` with the naming pattern:
```
{timestamp}_{domain}_llm_agent_{agent_model}_user_simulator_{user_model}.json
```

Example: `2026-02-24T16:51:45.593355_online_shopping_llm_agent_gpt-5-mini_user_simulator_gpt-4.1-mini.json`

## Top-Level Structure

```json
{
  "timestamp": "ISO datetime of simulation start",
  "info": { ... },         // Run configuration
  "tasks": [ ... ],        // Task definitions (from tasks.json)
  "simulations": [ ... ]   // Actual simulation results (1:1 with tasks when num_trials=1)
}
```

The two main sections you care about: **`tasks`** (what was expected) and **`simulations`** (what happened).

## `info` — Run Configuration

```json
{
  "git_commit": "sha",
  "num_trials": 1,              // How many times each task was run
  "max_steps": 200,             // Max conversation turns before timeout
  "max_errors": 10,             // Max tool errors before abort
  "user_info": {
    "implementation": "user_simulator",
    "llm": "gpt-4.1-mini",
    "llm_args": { "temperature": 0.0 },
    "global_simulation_guidelines": "..."   // System prompt for user simulator
  },
  "agent_info": {
    "implementation": "llm_agent",
    "llm": "gpt-5-mini",
    "llm_args": { "temperature": 0.0 }
  },
  "environment_info": {
    "domain_name": "online_shopping",
    "policy": "...",            // Full policy text the agent sees
    "tool_defs": null           // Tool definitions (null = loaded at runtime)
  },
  "seed": 300
}
```

## `tasks[i]` — Task Definition

Each task defines the scenario setup and success criteria.

```json
{
  "id": "[domain]fault_layers_CUSTOMERID[PERSONA:name]",
  "description": {
    "purpose": "Human-readable description of what is being tested",
    "relevant_policies": null,
    "notes": null
  },
  "user_scenario": {
    "persona": "Personality description for the user simulator",
    "instructions": {
      "domain": "online_shopping",
      "reason_for_call": "Why the user is contacting support",
      "known_info": "Facts the user knows (name, IDs, complaints)",
      "unknown_info": null,       // Info the user does NOT know
      "task_instructions": "What the user should do during the conversation"
    }
  },
  "ticket": "The opening message/complaint the user presents",
  "initial_state": {
    "initialization_data": null,
    "initialization_actions": [   // DB mutations to set up the fault
      {
        "env_type": "user|assistant",
        "func_name": "set_account_status",
        "arguments": { "customer_id": "CST013", "status": "locked" }
      }
      // ... more init actions
    ],
    "message_history": null       // Pre-seeded conversation (rarely used)
  },
  "evaluation_criteria": {
    "actions": [ ... ],           // Expected tool calls (see below)
    "env_assertions": [ ... ],    // Expected DB state after resolution
    "communicate_info": null,     // Info agent must communicate to user
    "nl_assertions": null,        // Natural language assertions
    "reward_basis": ["ENV_ASSERTION", "ACTION"]  // Which dimensions count
  }
}
```

### `evaluation_criteria.actions[i]` — Expected Actions

Each action represents a tool call that must happen during the conversation.

```json
{
  "action_id": "0",
  "requestor": "user|assistant",     // Who must call this tool
  "name": "confirm_pricing_update",  // Tool name
  "arguments": { "order_id": "ORD013" },
  "info": null,
  "compare_args": []                 // Which args to check ([] = any args match)
}
```

**Key field — `compare_args`:**
- `["order_id"]` — the tool must be called with exactly that `order_id`
- `[]` — any call to this tool name counts as a match (args ignored)

**Key field — `requestor`:**
- `"assistant"` — the agent must call this tool
- `"user"` — the user simulator must call this tool (typically confirmation tools)

### `evaluation_criteria.env_assertions[i]` — Expected Final DB State

```json
{
  "env_type": "assistant|user",
  "func_name": "assert_unit_price",
  "arguments": { "order_id": "ORD013", "expected": 89.99 },
  "assert_value": true,
  "message": "Order ORD013 unit price should be $89.99."
}
```

- `env_type: "assistant"` — assertion runs on the agent's DB (e.g. order data)
- `env_type: "user"` — assertion runs on the user's DB (e.g. was confirmation tool called)

## `simulations[i]` — Simulation Results

Each simulation is a completed run of one task. With `num_trials=1`, there is exactly one simulation per task.

```json
{
  "id": "uuid",
  "task_id": "matches tasks[i].id",
  "timestamp": "ISO datetime of completion",
  "start_time": "...",
  "end_time": "...",
  "duration": 91.63,              // Seconds
  "termination_reason": "user_stop|max_steps|max_errors",
  "agent_cost": 0.0141,           // LLM cost for agent
  "user_cost": 0.0031,            // LLM cost for user simulator
  "reward_info": { ... },         // Scoring breakdown (see below)
  "messages": [ ... ],            // Full conversation transcript
  "trial": 0,                     // Trial index (0-based)
  "seed": 626729                  // Random seed for this simulation
}
```

**`termination_reason` values:**
- `"user_stop"` — conversation ended naturally (user sent ###STOP###)
- `"max_steps"` — hit the step limit (usually means conversation went in circles)
- `"max_errors"` — too many tool errors (usually means agent is calling tools wrong)

### `reward_info` — Scoring Breakdown

This is the most important section for diagnosing failures.

```json
{
  "reward": 1.0,                  // Final score: 0.0 = fail, 1.0 = pass
  "reward_basis": ["ENV_ASSERTION", "ACTION"],
  "reward_breakdown": {
    "ENV_ASSERTION": 1.0,         // Were all DB assertions met?
    "ACTION": 1.0                 // Were all expected actions taken?
  },
  "db_check": {
    "db_match": false,            // Legacy: full DB snapshot match
    "db_reward": 0.0
  },
  "env_assertions": [ ... ],     // Per-assertion results
  "action_checks": [ ... ],      // Per-action results
  "nl_assertions": null,
  "communicate_checks": null,
  "info": {
    "env": null,
    "nl": null,
    "communicate": { "note": "No communicate_info to evaluate" },
    "action": null
  }
}
```

**Reward formula:** `reward = min(reward_breakdown[dim] for dim in reward_basis)`. If ANY dimension is 0.0, the overall reward is 0.0.

**Dimension scores:** Each dimension score is the average of its individual checks. For example, if 11 of 12 env_assertions pass, ENV_ASSERTION = 11/12 ≈ 0.917. But the *overall* reward uses min, so if ACTION = 0.0, the task fails regardless.

### `reward_info.env_assertions[i]` — Per-Assertion Results

```json
{
  "env_assertion": {
    "env_type": "assistant",
    "func_name": "assert_unit_price",
    "arguments": { "order_id": "ORD013", "expected": 89.99 },
    "assert_value": true,
    "message": "Order ORD013 unit price should be $89.99."
  },
  "met": true,       // Did this assertion pass?
  "reward": 1.0      // 1.0 if met, 0.0 if not
}
```

### `reward_info.action_checks[i]` — Per-Action Results

```json
{
  "action": {
    "action_id": "0",
    "requestor": "user",
    "name": "acknowledge_resolution",
    "arguments": { "customer_id": "CST013" },
    "info": null,
    "compare_args": []
  },
  "action_match": true,     // Was this tool called during the conversation?
  "action_reward": 1.0      // 1.0 if matched, 0.0 if not
}
```

### `messages[i]` — Conversation Transcript

Messages follow OpenAI-style format with three roles: `assistant` (agent), `user` (user simulator), and `tool` (tool execution results).

**Assistant message (text response):**
```json
{
  "role": "assistant",
  "content": "I've unlocked your account. Please use your acknowledge_resolution tool to confirm.",
  "tool_calls": null,
  "turn_idx": 10,
  "timestamp": "...",
  "cost": 0.0012,
  "usage": { "completion_tokens": 45, "prompt_tokens": 3200 },
  "raw_data": { ... }      // Raw LLM API response
}
```

**Assistant message (tool call):**
```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "name": "unlock_account",
      "arguments": { "customer_id": "CST013" },
      "requestor": "assistant"
    }
  ],
  "turn_idx": 5,
  ...
}
```

**Tool result:**
```json
{
  "id": "call_abc123",         // Matches the tool_calls[].id above
  "role": "tool",
  "content": "{\"success\": true, \"message\": \"Account unlocked\"}",
  "requestor": "assistant",    // Who initiated this tool call
  "error": false,              // true if the tool raised an error
  "turn_idx": 6,
  "timestamp": "..."
}
```

**User message (text only):**
```json
{
  "role": "user",
  "content": "Thank you! I've confirmed the resolution.",
  "tool_calls": null,
  "turn_idx": 11,
  ...
}
```

**User message (with tool call):**
```json
{
  "role": "user",
  "content": "Let me confirm that update now.",
  "tool_calls": [
    {
      "id": "call_xyz789",
      "name": "confirm_pricing_update",
      "arguments": { "order_id": "ORD013" },
      "requestor": "user"
    }
  ],
  "turn_idx": 14,
  ...
}
```

Note: User tool calls are followed by a `tool` message with `"requestor": "user"`.

**`turn_idx`** is a sequential counter across all messages (assistant, user, tool). Use it to trace conversation flow chronologically.

## How to Diagnose a Failure

### Step 1: Find the failed simulation

```python
import json
with open("data/simulations/TRACE_FILE.json") as f:
    data = json.load(f)

for sim in data["simulations"]:
    if sim["reward_info"]["reward"] == 0.0:
        print(sim["task_id"], sim["reward_info"]["reward_breakdown"])
```

### Step 2: Identify what failed

Check `reward_breakdown` to see which dimension(s) failed:
- `ENV_ASSERTION: 0.0` → DB state is wrong after conversation ended
- `ACTION: 0.0` → Expected tool calls didn't happen

Then drill into the specific failures:

```python
# Which assertions failed?
for ea in sim["reward_info"]["env_assertions"]:
    if not ea["met"]:
        print(f"FAILED: {ea['env_assertion']['func_name']}({ea['env_assertion']['arguments']})")

# Which actions were missed?
for ac in sim["reward_info"]["action_checks"]:
    if not ac["action_match"]:
        print(f"MISSED: {ac['action']['requestor']}:{ac['action']['name']}({ac['action']['arguments']})")
```

### Step 3: Read the conversation transcript

Walk through `sim["messages"]` chronologically (by `turn_idx`) to understand what happened:

1. **Look at the agent's tool calls** — did it call the right tools in the right order?
2. **Check tool results** — did any tools return errors (`"error": true`)?
3. **Check user tool calls** — did the user simulator call confirmation tools when asked?
4. **Look at agent text responses** — did the agent instruct the user to call confirmation tools?
5. **Check the ending** — did the conversation end prematurely?

### Step 4: Classify the failure

**Task setup bug** (fix the scenario/domain):
- Tool returns unexpected error that blocks the correct workflow
- User simulator lacks info to make required tool call (missing from `known_info`)
- Assertions check a value the agent can't possibly compute (info not available)
- Policy is ambiguous/contradictory about what the agent should do

**Agent reasoning failure** (genuine benchmark difficulty):
- Agent calls tools in wrong order (e.g. adjusts tax, then changes price, doesn't re-adjust)
- Agent forgets to instruct user to call confirmation tool
- Agent uses wrong protocol (e.g. treats expired payment as wrong payment method)
- Agent miscalculates numeric values

**User simulator failure** (fix user instructions):
- User doesn't call tool despite being asked (check `task_instructions` wording)
- User calls tool with wrong arguments (check `known_info` for the arg value)
- User stops conversation prematurely (check if all `task_instructions` criteria are met)

### Quick Reference: Python Snippet for Full Failure Report

```python
import json

with open("data/simulations/TRACE_FILE.json") as f:
    data = json.load(f)

for sim in data["simulations"]:
    ri = sim["reward_info"]
    if ri["reward"] == 0.0:
        print(f"\n{'='*80}")
        print(f"TASK: {sim['task_id']}")
        print(f"REWARD: {ri['reward']}  BREAKDOWN: {ri['reward_breakdown']}")
        print(f"TERMINATION: {sim['termination_reason']}  MESSAGES: {len(sim['messages'])}")

        # Failed assertions
        for ea in ri["env_assertions"]:
            if not ea["met"]:
                a = ea["env_assertion"]
                print(f"  FAILED ASSERTION: {a['func_name']}({a['arguments']}) msg={a.get('message')}")

        # Missed actions
        for ac in ri["action_checks"]:
            if not ac["action_match"]:
                a = ac["action"]
                print(f"  MISSED ACTION: {a['requestor']}:{a['name']}({a['arguments']})")

        # Agent tool calls made
        print("  AGENT ACTIONS:")
        for m in sim["messages"]:
            if m["role"] == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    print(f"    turn {m['turn_idx']}: {tc['name']}({tc['arguments']})")

        # User tool calls made
        print("  USER ACTIONS:")
        for m in sim["messages"]:
            if m["role"] == "user" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    print(f"    turn {m['turn_idx']}: {tc['name']}({tc['arguments']})")
```

## Matching Tasks to Simulations

Tasks and simulations are linked by `task_id`:
- `data["tasks"][i]["id"]` == `data["simulations"][j]["task_id"]`

When `num_trials > 1`, multiple simulations share the same `task_id` but differ by `trial` (0-indexed). To find the task definition for a simulation:

```python
task_map = {t["id"]: t for t in data["tasks"]}
task = task_map[sim["task_id"]]
```

## Understanding Task IDs

Task IDs encode the fault composition:
```
[domain]domain_faultlayer1|faultlayer2|..._CUSTOMERID[PERSONA:name]
```

Example: `[online_shopping]online_shopping_locked_account|wrong_unit_price|wrong_tax_CST013[PERSONA:frustrated_shopper]`

- `locked_account`, `wrong_unit_price`, `wrong_tax` = active fault layers
- `CST013` = customer entity used
- `frustrated_shopper` = persona applied

The number of fault layers (pipe-separated) roughly indicates task difficulty. More layers = more issues to resolve = harder task.
