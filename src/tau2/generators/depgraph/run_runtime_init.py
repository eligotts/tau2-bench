"""Initialize runtime task specs from deterministic scaffold."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tau2.generators.depgraph.loaders import load_task_specs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create task_specs.runtime.yaml from task_specs.runtime.scaffold.yaml"
    )
    parser.add_argument("--scaffold", required=True)
    parser.add_argument("--out-runtime", required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists",
    )
    args = parser.parse_args()

    scaffold_doc = load_task_specs(args.scaffold)
    out_path = Path(args.out_runtime)

    if out_path.exists() and not args.force:
        print(
            f"[FAIL] Output already exists: {out_path}. "
            "Use --force to overwrite, or choose a different output path."
        )
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(scaffold_doc.model_dump(mode="python"), sort_keys=False))

    print(f"[PASS] Wrote runtime file from scaffold: {out_path}")
    print("[INFO] Next step: edit ONLY runtime.reason_for_call, runtime.known_info, runtime.ticket")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

