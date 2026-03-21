"""Smoke tests for the verifiers adapter.

Uses a tiny 3-action domain to verify:
1. DepgraphTaskConfig compiles from contract + task intent
2. DepgraphToolEnv initializes state correctly
3. Tools receive the db via update_tool_args
4. Goal checking works against db state
5. The full pipeline: contract → sampler → verifiers compile → env
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from tau2.generators.depgraph.types import (
    ActionContract,
    GraphContractSpec,
    SamplingRequestDoc,
    TaskIntent,
    TaskSpecsDoc,
    TerminalProfileSpec,
    WorldEffectSpec,
    WorldPredicateSpec,
)
from tau2.generators.depgraph.verifiers_env import (
    DepgraphTaskConfig,
    DepgraphToolEnv,
    check_goal,
    compile_task_config,
)
from tau2.generators.depgraph.verifiers_rubric import DepgraphRubric
from tau2.generators.depgraph.verifiers_compiler import (
    VerifiersCompileResult,
    compile_for_verifiers,
)
from tau2.generators.depgraph.sampler import sample_task_intents


# ---------------------------------------------------------------------------
# Tiny domain: a counter with 3 actions
#   - increment(db) -> db["counter"] += 1
#   - double(db)    -> db["counter"] *= 2
#   - read(db)      -> returns db["counter"] (knowledge-only)
# ---------------------------------------------------------------------------

def increment(db: dict) -> str:
    """Increment the counter by 1."""
    db["counter"] = db.get("counter", 0) + 1
    return f"Counter is now {db['counter']}"


def double(db: dict) -> str:
    """Double the counter value."""
    db["counter"] = db.get("counter", 0) * 2
    return f"Counter is now {db['counter']}"


def read_counter(db: dict) -> str:
    """Read the current counter value."""
    return f"Counter value: {db.get('counter', 0)}"


TOOL_FUNCTIONS = {
    "increment": increment,
    "double": double,
    "read_counter": read_counter,
}

# Minimal dataset to satisfy verifiers Environment base class.
_DUMMY_DATASET = Dataset.from_dict({
    "prompt": [[{"role": "user", "content": "Do the task."}]],
    "answer": [""],
    "example_id": [0],
})


def _make_contract() -> GraphContractSpec:
    """Build a minimal graph contract for the counter domain."""
    return GraphContractSpec(
        version=2,
        projection_fields=["counter"],
        actions=[
            ActionContract(
                action_id="do_increment",
                requestor="assistant",
                tool_name="increment",
                classification="causal",
                requires_world=[],
                effects_world=[
                    # We model increment as: counter goes from 0 -> 1
                    # For BFS this is a simplification; real tool does += 1
                    WorldEffectSpec(path="counter", set=1),
                ],
            ),
            ActionContract(
                action_id="do_double",
                requestor="assistant",
                tool_name="double",
                classification="causal",
                requires_world=[
                    WorldPredicateSpec(path="counter", value=1),
                ],
                effects_world=[
                    WorldEffectSpec(path="counter", set=2),
                ],
            ),
        ],
    )


def _make_task_intent() -> TaskIntent:
    """Build a task intent: start at counter=0, goal is counter=2."""
    return TaskIntent(
        task_id="counter_test_001",
        start_world=[WorldEffectSpec(path="counter", set=0)],
        start_bindings=[],
        goal_world=[WorldPredicateSpec(path="counter", value=2)],
        goal_capture_paths=["counter"],
        terminal_profile_id="counter_doubled",
        required_actions=["do_increment", "do_double"],
        min_plan_length=2,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompileTaskConfig:
    def test_basic_compile(self):
        contract = _make_contract()
        task = _make_task_intent()
        config = compile_task_config(contract, task, task_prompt="Double the counter")

        assert config.task_id == "counter_test_001"
        assert config.start_world == {"counter": 0}
        assert config.start_bindings == set()
        assert len(config.goal_world) == 1
        assert config.goal_world[0].path == "counter"
        assert config.goal_world[0].value == 2
        assert config.task_prompt == "Double the counter"

    def test_conflicting_start_world_raises(self):
        contract = _make_contract()
        task = TaskIntent(
            task_id="bad_task",
            start_world=[
                WorldEffectSpec(path="counter", set=0),
                WorldEffectSpec(path="counter", set=5),
            ],
            goal_world=[WorldPredicateSpec(path="counter", value=2)],
            goal_capture_paths=["counter"],
        )
        with pytest.raises(ValueError, match="conflicting"):
            compile_task_config(contract, task)


class TestCheckGoal:
    def test_all_satisfied(self):
        db = {"counter": 2}
        goal_world = [WorldPredicateSpec(path="counter", value=2)]
        reward, details = check_goal(db, goal_world)
        assert reward == 1.0
        assert all(details.values())

    def test_none_satisfied(self):
        db = {"counter": 0}
        goal_world = [WorldPredicateSpec(path="counter", value=2)]
        reward, details = check_goal(db, goal_world)
        assert reward == 0.0

    def test_partial(self):
        db = {"counter": 2, "doubled": False}
        goal_world = [
            WorldPredicateSpec(path="counter", value=2),
            WorldPredicateSpec(path="doubled", value=True),
        ]
        reward, details = check_goal(db, goal_world)
        assert reward == 0.5
        assert list(details.values()) == [True, False]

    def test_multiple_world_goals(self):
        db = {"counter": 2, "doubled": True}
        goal_world = [
            WorldPredicateSpec(path="counter", value=2),
            WorldPredicateSpec(path="doubled", value=True),
        ]
        reward, details = check_goal(db, goal_world)
        assert reward == 1.0

    def test_empty_goals(self):
        reward, details = check_goal({}, [])
        assert reward == 1.0


class TestDepgraphToolEnv:
    """Test that the env wires up correctly (no actual LLM calls)."""

    def test_construction(self):
        """Env can be constructed with tool functions."""
        config = DepgraphTaskConfig(
            task_id="test",
            start_world={"counter": 0},
            start_bindings=set(),
            goal_world=[],
        )
        env = DepgraphToolEnv(
            tool_functions=TOOL_FUNCTIONS,
            task_config_factory=lambda state: config,
            dataset=_DUMMY_DATASET,
        )
        # Should have 3 tools registered
        assert len(env.tool_map) == 3
        assert "increment" in env.tool_map
        assert "double" in env.tool_map
        assert "read_counter" in env.tool_map

    def test_tool_schemas_hide_db(self):
        """The 'db' parameter should not appear in tool schemas."""
        config = DepgraphTaskConfig(
            task_id="test",
            start_world={"counter": 0},
            start_bindings=set(),
            goal_world=[],
        )
        env = DepgraphToolEnv(
            tool_functions=TOOL_FUNCTIONS,
            task_config_factory=lambda state: config,
            dataset=_DUMMY_DATASET,
        )
        for tool_def in env.tool_defs:
            params = tool_def.parameters
            props = params.get("properties", {})
            assert "db" not in props, (
                f"Tool '{tool_def.name}' still exposes 'db' in schema"
            )
            required = params.get("required", [])
            assert "db" not in required, (
                f"Tool '{tool_def.name}' still lists 'db' as required"
            )


class TestVerifiersCompiler:
    def test_compile_with_preflight(self):
        """Tasks that pass preflight get compiled to configs."""
        contract = _make_contract()
        task_doc = TaskSpecsDoc(version=1, tasks=[_make_task_intent()])
        terminal_profiles = [
            TerminalProfileSpec(
                profile_id="counter_doubled",
                requires_world=[WorldPredicateSpec(path="counter", value=2)],
            ),
        ]

        result = compile_for_verifiers(
            contract,
            task_doc,
            terminal_profiles=terminal_profiles,
            system_prompt="You are a counter agent.",
            task_prompt_factory=lambda task, contract: f"Get counter to goal state.",
        )

        assert result.success, f"Compile errors: {result.errors}"
        assert len(result.configs) == 1
        config = result.configs[0]
        assert config.task_id == "counter_test_001"
        assert config.system_prompt == "You are a counter agent."
        assert config.task_prompt == "Get counter to goal state."

    def test_compile_failing_preflight(self):
        """Tasks that fail preflight are skipped with errors."""
        contract = _make_contract()
        # Impossible task: start at 0, goal is counter=99 (unreachable)
        bad_task = TaskIntent(
            task_id="impossible",
            start_world=[WorldEffectSpec(path="counter", set=0)],
            goal_world=[WorldPredicateSpec(path="counter", value=99)],
            goal_capture_paths=["counter"],
            min_plan_length=1,
        )
        task_doc = TaskSpecsDoc(version=1, tasks=[bad_task])

        result = compile_for_verifiers(contract, task_doc)
        assert not result.success
        assert "impossible" in result.skipped


class TestSamplerToVerifiers:
    """End-to-end: sampler → compile_for_verifiers."""

    def test_sampled_tasks_compile(self):
        contract = _make_contract()
        request = SamplingRequestDoc(
            version=1,
            max_tasks=5,
            terminal_profiles=[
                TerminalProfileSpec(
                    profile_id="counter_doubled",
                    requires_world=[WorldPredicateSpec(path="counter", value=2)],
                ),
            ],
            goal_capture_paths=["counter"],
            seed_schemas=[
                {
                    "schema_id": "counter_seeds",
                    "seed_id_template": "counter_{start_val}",
                    "allowed_terminal_profiles": ["counter_doubled"],
                    "min_depth": 2,
                    "max_depth": 5,
                    "dimensions": [
                        {
                            "dimension_id": "start_val",
                            "variants": [
                                {
                                    "variant_id": "zero",
                                    "start_world": [{"path": "counter", "set": 0}],
                                },
                            ],
                        },
                    ],
                },
            ],
        )

        sampled = sample_task_intents(contract, request)
        assert len(sampled) > 0, "Sampler found no tasks"

        from tau2.generators.depgraph.sampler import sampled_to_task_specs

        task_doc = sampled_to_task_specs(sampled)
        result = compile_for_verifiers(
            contract,
            task_doc,
            terminal_profiles=request.terminal_profiles,
        )

        assert result.success, f"Compile errors: {result.errors}"
        assert len(result.configs) > 0

        # Every config should have counter=0 start and counter=2 goal
        for config in result.configs:
            assert config.start_world["counter"] == 0
            assert any(
                g.path == "counter" and g.value == 2
                for g in config.goal_world
            )
