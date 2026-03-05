"""CLI for strict runtime author-surface validation."""

from __future__ import annotations

import argparse

from tau2.generators.depgraph.loaders import load_task_specs
from tau2.generators.depgraph.runtime_surface import check_runtime_author_surface


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that authored runtime specs changed only allowed narrative fields"
    )
    parser.add_argument("--scaffold", required=True)
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args()

    scaffold_doc = load_task_specs(args.scaffold)
    runtime_doc = load_task_specs(args.runtime)

    issues = check_runtime_author_surface(scaffold_doc, runtime_doc)
    if issues:
        print("[FAIL] Runtime author-surface check failed")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("[PASS] Runtime author-surface check passed")
    print("[INFO] Only allowed runtime fields changed: reason_for_call, known_info, ticket")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
