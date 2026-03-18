"""Generate deterministic concrete context bindings for sampled depgraph tasks."""

from __future__ import annotations

import argparse

from tau2.generators.depgraph.context_bindings import (
    dump_task_context_bindings,
    generate_cloud_ir_context_bindings,
    generate_daily_planner_context_bindings,
    generate_ev_context_bindings,
)
from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic task context bindings from domain DB"
    )
    parser.add_argument("--domain", required=True)
    parser.add_argument("--graph-contract", required=True)
    parser.add_argument("--task-specs-sampled", required=True)
    parser.add_argument("--db-json", required=True)
    parser.add_argument("--out-context-bindings", required=True)
    args = parser.parse_args()

    contract = load_graph_contract(args.graph_contract)
    sampled = load_task_specs(args.task_specs_sampled)

    if args.domain == "ev_charging_support":
        doc = generate_ev_context_bindings(
            sampled=sampled,
            contract=contract,
            db_json_path=args.db_json,
            domain=args.domain,
        )
    elif args.domain == "cloud_incident_response":
        doc = generate_cloud_ir_context_bindings(
            sampled=sampled,
            contract=contract,
            db_json_path=args.db_json,
            domain=args.domain,
        )
    elif args.domain == "daily_planner":
        doc = generate_daily_planner_context_bindings(
            sampled=sampled,
            contract=contract,
            db_json_path=args.db_json,
            domain=args.domain,
        )
    else:
        print(f"[FAIL] run_context_bindings does not support domain={args.domain}.")
        return 1
    dump_task_context_bindings(doc, args.out_context_bindings)

    print(f"[PASS] Wrote context bindings: {args.out_context_bindings}")
    print(f"[INFO] Tasks bound: {len(doc.tasks)}")
    print(f"[INFO] Strategy: {doc.strategy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

