"""CLI for dependency-graph task preflight checks.

Usage:
  uv run python -m tau2.generators.depgraph.run_preflight \
    --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
    --task-specs data/tau2/domains/<domain>/task_specs.yaml \
    [--stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml]
"""

from __future__ import annotations

import argparse

from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs
from tau2.generators.depgraph.preflight import run_task_preflight
from tau2.generators.depgraph.runtime_checks import (
    check_contract_against_environment,
    check_runtime_against_environment,
    check_start_bindings_visibility,
    check_stop_gate_runtime,
    check_task_runtime_fields,
)
from tau2.registry import registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Run depgraph preflight checks")
    parser.add_argument("--graph-contract", required=True)
    parser.add_argument("--task-specs", required=True)
    parser.add_argument("--max-depth", type=int, default=20)
    parser.add_argument("--domain", required=False)
    parser.add_argument(
        "--stop-gate-map",
        required=False,
        help="Optional stop-gate map YAML to validate strict user-stop wiring",
    )
    parser.add_argument("--strict-tool-coverage", action="store_true")
    args = parser.parse_args()

    contract = load_graph_contract(args.graph_contract)
    task_doc = load_task_specs(args.task_specs)

    overall_ok = True
    if args.domain:
        env_constructor = registry.get_env_constructor(args.domain)
        contract_issues = check_contract_against_environment(
            contract,
            env_constructor,
            strict_full_coverage=args.strict_tool_coverage,
        )
        runtime_issues = check_runtime_against_environment(task_doc, env_constructor)
        if contract_issues:
            overall_ok = False
            print("[FAIL] Contract/runtime alignment")
            for issue in contract_issues:
                print(f"  - {issue}")
        if runtime_issues:
            overall_ok = False
            print("[FAIL] Runtime task alignment")
            for issue in runtime_issues:
                print(f"  - {issue}")
        else:
            if not contract_issues:
                print("[PASS] Contract/runtime alignment")

    if args.stop_gate_map:
        stop_gate_issues = check_stop_gate_runtime(task_doc, args.stop_gate_map)
        if stop_gate_issues:
            overall_ok = False
            print("[FAIL] Stop-gate runtime alignment")
            for issue in stop_gate_issues:
                print(f"  - {issue}")
        else:
            print("[PASS] Stop-gate runtime alignment")

    binding_vis_issues = check_start_bindings_visibility(task_doc, contract)
    if binding_vis_issues:
        overall_ok = False
        print("[FAIL] Start-binding visibility in ticket")
        for issue in binding_vis_issues:
            print(f"  - {issue}")
    else:
        print("[PASS] Start-binding visibility in ticket")

    for task in task_doc.tasks:
        report = run_task_preflight(contract, task, max_depth=args.max_depth)
        runtime_field_issues = check_task_runtime_fields(task)

        status = "PASS" if (report.passed and not runtime_field_issues) else "FAIL"
        print(f"[{status}] {task.task_id}")
        print(f"  SAT_full: {report.sat_full.sat}")
        print(
            f"  Search stats: explored={report.sat_full.explored_states}, "
            f"pruned={report.sat_full.pruned_states}"
        )
        if report.sat_full.plan:
            print(f"  Plan: {' -> '.join(report.sat_full.plan)}")
        print(f"  Required actions in SAT_full plan: {report.plan_contains_required_actions}")
        print(f"  Min plan length check: {report.min_plan_length_ok}")

        if report.required_action_unsat:
            print("  Required-action ablations (expect True):")
            for action_id, ok in report.required_action_unsat.items():
                print(f"    - {action_id}: {ok}")

        if report.issues:
            print("  Issues:")
            for issue in report.issues:
                print(f"    - {issue}")
        if runtime_field_issues:
            print("  Runtime field issues:")
            for issue in runtime_field_issues:
                print(f"    - {issue}")

        if not report.passed or runtime_field_issues:
            overall_ok = False

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
