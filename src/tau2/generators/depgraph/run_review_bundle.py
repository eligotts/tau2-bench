"""Generate a deterministic depgraph review bundle for rubric-driven LLM audits."""

from __future__ import annotations

import argparse
from pathlib import Path

from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs
from tau2.generators.depgraph.review_bundle import (
    build_review_bundle_markdown,
    infer_review_source_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a depgraph review bundle")
    parser.add_argument("--graph-contract", required=True)
    parser.add_argument("--task-specs", required=True)
    parser.add_argument("--domain", required=False)
    parser.add_argument("--policy", required=False)
    parser.add_argument("--domain-scope", required=False)
    parser.add_argument("--runtime-defaults", required=False)
    parser.add_argument("--sampling-request", required=False)
    parser.add_argument("--stop-gate-map", required=False)
    parser.add_argument("--out", required=False)
    parser.add_argument("--samples-per-family", type=int, default=1)
    parser.add_argument("--max-depth", type=int, default=32)
    args = parser.parse_args()

    contract = load_graph_contract(args.graph_contract)
    task_doc = load_task_specs(args.task_specs)
    contract_path = Path(args.graph_contract).resolve()
    domain = args.domain or contract_path.parent.name
    out_path = Path(args.out).resolve() if args.out else contract_path.parent / "review_bundle.md"

    source_paths = infer_review_source_paths(
        domain=domain,
        graph_contract_path=contract_path,
        task_specs_path=args.task_specs,
        policy_path=args.policy,
        domain_scope_path=args.domain_scope,
        runtime_defaults_path=args.runtime_defaults,
        sampling_request_path=args.sampling_request,
        stop_gate_map_path=args.stop_gate_map,
    )

    bundle = build_review_bundle_markdown(
        domain=domain,
        contract=contract,
        task_doc=task_doc,
        source_paths=source_paths,
        samples_per_family=args.samples_per_family,
        max_depth=args.max_depth,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(bundle)

    print(f"[PASS] Review bundle written: {out_path}")
    print(f"[INFO] Domain: {domain}")
    print(f"[INFO] Tasks summarized: {len(task_doc.tasks)}")
    print(f"[INFO] Families sampled: {args.samples_per_family} task(s) per family")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
