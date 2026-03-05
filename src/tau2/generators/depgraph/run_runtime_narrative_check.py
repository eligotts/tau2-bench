"""CLI for runtime narrative-content validation."""

from __future__ import annotations

import argparse

from tau2.generators.depgraph.loaders import load_task_specs
from tau2.generators.depgraph.runtime_narrative_checks import (
    check_runtime_narratives,
    load_narrative_briefs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate authored runtime narrative fields against narrative briefs"
    )
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--narrative-briefs", required=True)
    args = parser.parse_args()

    runtime_doc = load_task_specs(args.runtime)
    narrative_briefs = load_narrative_briefs(args.narrative_briefs)

    issues = check_runtime_narratives(runtime_doc, narrative_briefs)
    if issues:
        print("[FAIL] Runtime narrative validation failed")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("[PASS] Runtime narrative validation passed")
    print(
        "[INFO] Authored fields are non-empty, avoid internal path leaks, and align with narrative briefs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

