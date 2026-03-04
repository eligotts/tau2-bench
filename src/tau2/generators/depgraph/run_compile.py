"""CLI for depgraph preflight + compile to tau2 tasks json.

Optional strict stop-gate validation can be enabled via --stop-gate-map.
"""

from __future__ import annotations

import argparse

from tau2.generators.depgraph.compiler import dump_tasks_json, preflight_and_compile
from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs
from tau2.generators.depgraph.runtime_checks import (
    check_contract_against_environment,
    check_runtime_against_environment,
    check_stop_gate_runtime,
)
from tau2.registry import registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight and compile depgraph tasks")
    parser.add_argument("--graph-contract", required=True)
    parser.add_argument("--task-specs", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-depth", type=int, default=20)
    parser.add_argument("--domain", required=False)
    parser.add_argument(
        "--stop-gate-map",
        required=False,
        help="Optional stop-gate map YAML to validate strict user-stop wiring",
    )
    parser.add_argument(
        "--strict-tool-coverage",
        action="store_true",
        help="Require all domain tools to be represented in contracts",
    )
    args = parser.parse_args()

    contract = load_graph_contract(args.graph_contract)
    task_doc = load_task_specs(args.task_specs)

    if args.domain:
        env_constructor = registry.get_env_constructor(args.domain)
        contract_issues = check_contract_against_environment(
            contract,
            env_constructor,
            strict_full_coverage=args.strict_tool_coverage,
        )
        runtime_issues = check_runtime_against_environment(task_doc, env_constructor)
        if contract_issues:
            print("[FAIL] Contract/runtime alignment issues:")
            for issue in contract_issues:
                print(f"  - {issue}")
            return 1
        if runtime_issues:
            print("[FAIL] Runtime task alignment issues:")
            for issue in runtime_issues:
                print(f"  - {issue}")
            return 1
        print("[PASS] Contract/runtime alignment checks")

    if args.stop_gate_map:
        stop_gate_issues = check_stop_gate_runtime(task_doc, args.stop_gate_map)
        if stop_gate_issues:
            print("[FAIL] Stop-gate runtime alignment issues:")
            for issue in stop_gate_issues:
                print(f"  - {issue}")
            return 1

    result = preflight_and_compile(
        contract,
        task_doc,
        max_depth=args.max_depth,
        require_runtime=True,
    )
    if result.errors:
        print("[FAIL] Compile checks")
        for error in result.errors:
            print(f"  - {error}")
        return 1

    dump_tasks_json(result.tasks, args.out)
    print(f"[PASS] Compiled {len(result.tasks)} tasks to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
