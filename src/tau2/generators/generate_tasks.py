"""Generate tasks for a domain by running its create_tasks() function.

Usage:
    python -m tau2.generators.generate_tasks <domain_name> [--no-verify] [--save]
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from tau2.generators.code_utils import try_import_module

_PROJECT_ROOT = Path(__file__).parents[3]
_DATA_DOMAINS = _PROJECT_ROOT / "data" / "tau2" / "domains"


def generate_tasks(
    domain_name: str,
    verify: bool = True,
    save: bool = False,
    seed: int = 42,
) -> list:
    """Generate tasks for a domain.

    Args:
        domain_name: The domain to generate tasks for.
        verify: Run verification passes on generated tasks.
        save: Write tasks.json to disk.
        seed: Random seed for shuffling.

    Returns:
        List of generated Task objects.
    """
    module_path = f"tau2.domains.{domain_name}.scenarios"
    module, import_errors = try_import_module(module_path)
    if import_errors:
        print(f"Error importing {module_path}:")
        for e in import_errors:
            print(f"  {e}")
        sys.exit(1)

    if not hasattr(module, "create_tasks"):
        print(f"Error: {module_path} missing create_tasks() function")
        sys.exit(1)

    print(f"Generating tasks for '{domain_name}' (verify={verify})...")
    try:
        tasks = module.create_tasks(verify=verify)
    except Exception as e:
        print(f"Error: create_tasks(verify={verify}) failed: {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"Generated {len(tasks)} tasks.")

    # Print difficulty distribution
    difficulties = Counter()
    for task in tasks:
        ec = task.evaluation_criteria
        if ec and ec.actions:
            n_actions = len(ec.actions)
            difficulties[n_actions] += 1
    if difficulties:
        print("Difficulty distribution (actions per task):")
        for n_actions in sorted(difficulties):
            print(f"  {n_actions} actions: {difficulties[n_actions]} tasks")

    if save:
        data_dir = _DATA_DOMAINS / domain_name
        data_dir.mkdir(parents=True, exist_ok=True)
        tasks_path = data_dir / "tasks.json"

        # Shuffle with fixed seed
        rng = random.Random(seed)
        rng.shuffle(tasks)

        task_dicts = [t.model_dump(mode="json") for t in tasks]
        tasks_path.write_text(json.dumps(task_dicts, indent=2))
        print(f"Saved {len(tasks)} tasks to {tasks_path}")

    return tasks


def main():
    parser = argparse.ArgumentParser(description="Generate tasks for a tau2-bench domain")
    parser.add_argument("domain_name", help="Domain name")
    parser.add_argument("--no-verify", action="store_true", help="Skip verification")
    parser.add_argument("--save", action="store_true", help="Save tasks.json to disk")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for shuffling")
    args = parser.parse_args()

    generate_tasks(
        args.domain_name,
        verify=not args.no_verify,
        save=args.save,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
