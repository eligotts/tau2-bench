"""CLI for depgraph fan-out sampling."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tau2.generators.depgraph.loaders import load_graph_contract, load_sampling_request
from tau2.generators.depgraph.sampler import sample_task_intents, sampled_to_task_specs


def main() -> int:
    parser = argparse.ArgumentParser(description="Sample depgraph task intents")
    parser.add_argument("--graph-contract", required=True)
    parser.add_argument("--sampling-request", required=True)
    parser.add_argument("--out-task-specs", required=False)
    args = parser.parse_args()

    contract = load_graph_contract(args.graph_contract)
    request = load_sampling_request(args.sampling_request)
    sampled = sample_task_intents(contract, request)
    specs = sampled_to_task_specs(sampled)

    print(f"Sampled passing tasks: {len(sampled)}")
    for sampled_task in sampled:
        task = sampled_task.task
        print(
            f"- {task.task_id}: plan_len={task.min_plan_length}, "
            f"terminal={task.terminal_profile_id}, "
            f"goals_world={len(task.goal_world)}, "
            f"required_actions={len(task.required_actions)}"
        )

    if args.out_task_specs:
        out_path = Path(args.out_task_specs)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml.safe_dump(specs.model_dump(mode="python"), sort_keys=False))
        print(f"Wrote sampled task specs to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
