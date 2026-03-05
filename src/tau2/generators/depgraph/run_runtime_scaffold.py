"""Generate deterministic runtime scaffold + narrative briefs from sampled task intents."""

from __future__ import annotations

import argparse

from tau2.generators.depgraph.context_bindings import load_task_context_bindings
from tau2.generators.depgraph.loaders import load_graph_contract, load_task_specs
from tau2.generators.depgraph.runtime_scaffold import (
    generate_runtime_scaffold,
    load_persona_pool,
    load_runtime_defaults,
    write_yaml,
)
from tau2.generators.depgraph.stop_gate import load_stop_gate_map


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate runtime scaffold and narrative briefs from sampled depgraph specs"
    )
    parser.add_argument("--graph-contract", required=True)
    parser.add_argument("--task-specs-sampled", required=True)
    parser.add_argument("--personas", required=True)
    parser.add_argument("--domain", required=False)
    parser.add_argument("--runtime-defaults", required=False)
    parser.add_argument("--context-bindings", required=False)
    parser.add_argument("--stop-gate-map", required=False)
    parser.add_argument("--out-runtime-scaffold", required=True)
    parser.add_argument("--out-narrative-briefs", required=True)
    args = parser.parse_args()

    contract = load_graph_contract(args.graph_contract)
    sampled = load_task_specs(args.task_specs_sampled)
    personas = load_persona_pool(args.personas)
    runtime_defaults = (
        load_runtime_defaults(args.runtime_defaults) if args.runtime_defaults else None
    )
    context_bindings = (
        load_task_context_bindings(args.context_bindings)
        if args.context_bindings
        else None
    )
    stop_gate_map = load_stop_gate_map(args.stop_gate_map) if args.stop_gate_map else None

    domain = args.domain or (runtime_defaults.domain if runtime_defaults else None)
    if not domain:
        print(
            "[FAIL] Missing domain. Provide --domain or set domain in runtime_defaults.yaml."
        )
        return 1

    result = generate_runtime_scaffold(
        sampled=sampled,
        contract=contract,
        personas=personas,
        domain=domain,
        runtime_defaults=runtime_defaults,
        context_bindings=context_bindings,
        stop_gate_map=stop_gate_map,
    )

    write_yaml(
        args.out_runtime_scaffold,
        result.runtime_scaffold.model_dump(mode="python"),
    )
    write_yaml(args.out_narrative_briefs, result.narrative_briefs)

    print(f"[PASS] Runtime scaffold written: {args.out_runtime_scaffold}")
    print(f"[PASS] Narrative briefs written: {args.out_narrative_briefs}")
    print(f"[INFO] Tasks scaffolded: {len(result.runtime_scaffold.tasks)}")
    print("[INFO] Editable runtime fields per task: reason_for_call, known_info, ticket")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
