"""Inject strict stop-gate initialization/actions into runtime task specs."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tau2.generators.depgraph.loaders import load_task_specs
from tau2.generators.depgraph.stop_gate import inject_stop_gates, load_stop_gate_map


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject stop-gate criteria into runtime task specs")
    parser.add_argument("--task-specs", required=True)
    parser.add_argument("--stop-gate-map", required=True)
    parser.add_argument("--out", required=False)
    parser.add_argument(
        "--no-instruction-update",
        action="store_true",
        help="Inject set_stop_gate only (do not modify task_instructions)",
    )
    args = parser.parse_args()

    task_doc = load_task_specs(args.task_specs)
    stop_gate_map = load_stop_gate_map(args.stop_gate_map)
    issues = inject_stop_gates(
        task_doc,
        stop_gate_map,
        update_instructions=not args.no_instruction_update,
    )
    if issues:
        print("[FAIL] Stop-gate injection issues:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    out_path = Path(args.out or args.task_specs)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = task_doc.model_dump(mode="python")
    out_path.write_text(yaml.safe_dump(payload, sort_keys=False))
    print(f"[PASS] Wrote stop-gate injected task specs to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
