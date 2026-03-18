"""CLI for dependency-graph task preflight checks.

Usage:
  uv run python -m tau2.generators.depgraph.run_preflight \
    --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
    --task-specs data/tau2/domains/<domain>/task_specs.yaml \
    [--policy data/tau2/domains/<domain>/policy.md] \
    [--stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tau2.generators.depgraph.loaders import (
    load_graph_contract,
    load_sampling_request,
    load_task_specs,
)
from tau2.generators.depgraph.preflight import run_task_preflight
from tau2.generators.depgraph.runtime_checks import (
    check_contract_against_environment,
    check_policy_against_contract,
    check_runtime_against_environment,
    check_start_bindings_visibility,
    check_stop_gate_runtime,
    check_task_runtime_fields,
    check_tool_guard_completeness,
)
from tau2.registry import registry


def _resolve_policy_path(explicit_policy: str | None, graph_contract_path: str) -> Path | None:
    if explicit_policy:
        return Path(explicit_policy)
    inferred = Path(graph_contract_path).resolve().parent / "policy.md"
    if inferred.exists():
        return inferred
    return None


def _resolve_sampling_request_path(
    explicit_sampling_request: str | None,
    graph_contract_path: str,
) -> Path | None:
    if explicit_sampling_request:
        return Path(explicit_sampling_request)
    inferred = Path(graph_contract_path).resolve().parent / "sampling_request.yaml"
    if inferred.exists():
        return inferred
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run depgraph preflight checks")
    parser.add_argument("--graph-contract", required=True)
    parser.add_argument("--task-specs", required=True)
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--domain", required=False)
    parser.add_argument(
        "--stop-gate-map",
        required=False,
        help="Optional stop-gate map YAML to validate strict user-stop wiring",
    )
    parser.add_argument(
        "--policy",
        required=False,
        help="Optional policy.md to validate against the contract-visible tool surface",
    )
    parser.add_argument("--strict-tool-coverage", action="store_true")
    parser.add_argument(
        "--sampling-request",
        required=False,
        help="Optional sampling_request.yaml to validate terminal-profile alignment",
    )
    parser.add_argument(
        "--strict-required-action-necessity",
        action="store_true",
        help="Also prove each required action is indispensable via action-ablation search",
    )
    parser.add_argument(
        "--skip-bfs",
        action="store_true",
        help="Skip per-task BFS solvability check (tasks correct by construction from sampler)",
    )
    args = parser.parse_args()

    contract = load_graph_contract(args.graph_contract)
    task_doc = load_task_specs(args.task_specs)
    max_depth = args.max_depth
    if max_depth is None:
        max_depth = max(
            20,
            max((task.min_plan_length for task in task_doc.tasks), default=0),
        )

    overall_ok = True
    if args.domain:
        env_constructor = registry.get_env_constructor(args.domain)
        contract_issues = check_contract_against_environment(
            contract,
            env_constructor,
            strict_full_coverage=args.strict_tool_coverage,
        )
        runtime_issues = check_runtime_against_environment(task_doc, env_constructor)
        guard_issues = check_tool_guard_completeness(contract, env_constructor)

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
        if guard_issues:
            overall_ok = False
            print("[FAIL] Tool guard completeness")
            for issue in guard_issues:
                print(f"  - {issue}")
        else:
            print("[PASS] Tool guard completeness")
        if not contract_issues and not runtime_issues:
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

    policy_path = _resolve_policy_path(args.policy, args.graph_contract)
    if policy_path is None or not policy_path.exists():
        if args.domain or args.policy:
            overall_ok = False
            print("[FAIL] Policy/contract alignment")
            print(
                "  - policy.md not found; pass --policy or place policy.md next to graph_contract.yaml"
            )
    else:
        policy_issues = check_policy_against_contract(contract, policy_path.read_text())
        if policy_issues:
            overall_ok = False
            print("[FAIL] Policy/contract alignment")
            for issue in policy_issues:
                print(f"  - {issue}")
        else:
            print("[PASS] Policy/contract alignment")

    binding_vis_issues = check_start_bindings_visibility(task_doc, contract)
    if binding_vis_issues:
        overall_ok = False
        print("[FAIL] Start-binding visibility in ticket")
        for issue in binding_vis_issues:
            print(f"  - {issue}")
    else:
        print("[PASS] Start-binding visibility in ticket")

    sampling_request_path = _resolve_sampling_request_path(
        args.sampling_request, args.graph_contract
    )
    terminal_profiles = None
    require_terminal_profile = False
    if sampling_request_path is None or not sampling_request_path.exists():
        if args.domain or args.sampling_request:
            overall_ok = False
            print("[FAIL] Terminal-profile alignment")
            print(
                "  - sampling_request.yaml not found; pass --sampling-request or place "
                "sampling_request.yaml next to graph_contract.yaml"
            )
    else:
        request = load_sampling_request(sampling_request_path)
        terminal_profiles = {profile.profile_id: profile for profile in request.terminal_profiles}
        require_terminal_profile = True
        print("[PASS] Terminal-profile alignment config loaded")

    skip_bfs = args.skip_bfs
    for task in task_doc.tasks:
        if not skip_bfs:
            report = run_task_preflight(
                contract,
                task,
                max_depth=max_depth,
                terminal_profiles=terminal_profiles,
                require_terminal_profile=require_terminal_profile,
                check_required_action_necessity=args.strict_required_action_necessity,
            )
        runtime_field_issues = check_task_runtime_fields(task)

        if skip_bfs:
            status = "PASS" if not runtime_field_issues else "FAIL"
            print(f"[{status}] {task.task_id}  (BFS skipped)")
        else:
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

        if skip_bfs:
            if runtime_field_issues:
                overall_ok = False
        else:
            if not report.passed or runtime_field_issues:
                overall_ok = False

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
