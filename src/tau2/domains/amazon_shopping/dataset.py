"""Dataset builder for Amazon Shopping domain.

Loads BFS-sampled tasks, generates entities and descriptions for each,
and produces a structured dataset ready for evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from tau2.utils.utils import DATA_DIR

from .descriptions import generate_task_description
from .entity_sampler import sample_entities


_DOMAIN_DATA_DIR = DATA_DIR / "tau2" / "domains" / "amazon_shopping"
_SAMPLED_TASKS_PATH = _DOMAIN_DATA_DIR / "task_specs.sampled.yaml"

# Non-monotonic goal_world paths to skip in rubric scoring.
# These are navigation artifacts, not agent accomplishments.
SKIP_GOAL_PATHS = {"page.type", "page.current_product"}


def load_sampled_tasks(path: Path | None = None) -> list[dict]:
    """Load sampled tasks from YAML."""
    path = path or _SAMPLED_TASKS_PATH
    with open(path) as f:
        data = yaml.full_load(f)
    return data.get("tasks", [])


def _extract_start_world(task: dict) -> dict[str, Any]:
    """Convert start_world list to a flat dict."""
    result = {}
    for entry in task.get("start_world", []):
        result[entry["path"]] = entry["set"]
    return result


def _extract_goal_world(task: dict) -> list[dict]:
    """Extract goal_world predicates, filtering out non-monotonic paths."""
    raw = task.get("goal_world", [])
    return [g for g in raw if g["path"] not in SKIP_GOAL_PATHS]


def _extract_goal_world_full(task: dict) -> list[dict]:
    """Extract all goal_world predicates including non-monotonic ones."""
    return task.get("goal_world", [])


def build_task(task: dict) -> dict[str, Any]:
    """Build a single evaluation task from a sampled task spec.

    Returns a dict with:
        - task_id: str
        - prompt: list of message dicts
        - entities: TaskEntitySet (serialized)
        - goal_world: filtered predicates for rubric
        - goal_world_full: all predicates including page.*
        - start_world: flat config dict
        - required_actions: action sequence
        - description: natural language task instruction
    """
    task_id = task["task_id"]
    start_world = _extract_start_world(task)
    goal_world = _extract_goal_world(task)
    goal_world_full = _extract_goal_world_full(task)

    # Generate entities deterministically from task_id
    entities = sample_entities(task_id, start_world)

    # Generate task description from goal requirements + entities
    description = generate_task_description(
        task_id, start_world, goal_world, entities,
    )

    return {
        "task_id": task_id,
        "prompt": [{"role": "user", "content": description}],
        "description": description,
        "entities": entities.model_dump(),
        "start_world": start_world,
        "goal_world": goal_world,
        "goal_world_full": goal_world_full,
        "required_actions": task.get("required_actions", []),
        "terminal_profile_id": task.get("terminal_profile_id"),
    }


def build_dataset(
    tasks_path: Path | None = None,
    max_tasks: int | None = None,
) -> list[dict[str, Any]]:
    """Build the full evaluation dataset.

    Args:
        tasks_path: Path to task_specs.sampled.yaml. Uses default if None.
        max_tasks: Limit number of tasks (for testing). None = all.

    Returns:
        List of task dicts ready for evaluation.
    """
    sampled = load_sampled_tasks(tasks_path)
    if max_tasks:
        sampled = sampled[:max_tasks]

    dataset = []
    for task in sampled:
        dataset.append(build_task(task))

    return dataset


def export_dataset(
    output_path: str | Path,
    tasks_path: Path | None = None,
    max_tasks: int | None = None,
) -> int:
    """Build dataset and write to JSON file.

    Returns number of tasks written.
    """
    dataset = build_dataset(tasks_path, max_tasks)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2, default=str)
    return len(dataset)
