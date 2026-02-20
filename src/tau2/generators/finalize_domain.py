"""Finalize a domain: shuffle tasks and update registry.

Usage:
    python -m tau2.generators.finalize_domain <domain_name> [--skip-registry]
"""

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parents[3]
_DATA_DOMAINS = _PROJECT_ROOT / "data" / "tau2" / "domains"
_SRC_DOMAINS = _PROJECT_ROOT / "src" / "tau2" / "domains"
_REGISTRY_PATH = _PROJECT_ROOT / "src" / "tau2" / "registry.py"


def _class_name(domain_name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in domain_name.split("_"))


def _update_registry(domain_name: str) -> None:
    """Append import + registration to registry.py."""
    if not _REGISTRY_PATH.exists():
        print("  Warning: registry.py not found, skipping registration")
        return

    content = _REGISTRY_PATH.read_text()
    domain = domain_name

    # Check if already registered
    if f'"{domain}"' in content and f"{domain}_domain_get_environment" in content:
        print(f"  Domain '{domain}' already registered in registry.py")
        return

    # Add import after the last domain import
    import_line = (
        f"from tau2.domains.{domain}.environment import (\n"
        f"    get_environment as {domain}_domain_get_environment,\n"
        f")\n"
        f"from tau2.domains.{domain}.environment import get_tasks as {domain}_domain_get_tasks\n"
        f"from tau2.domains.{domain}.environment import (\n"
        f"    get_tasks_split as {domain}_domain_get_tasks_split,\n"
        f")"
    )

    # Add registration before the logger.debug line
    register_lines = (
        f'\n    registry.register_domain({domain}_domain_get_environment, "{domain}")\n'
        f"    registry.register_tasks(\n"
        f"        {domain}_domain_get_tasks,\n"
        f'        "{domain}",\n'
        f"        get_task_splits={domain}_domain_get_tasks_split,\n"
        f"    )\n"
    )

    # Insert import after last 'from tau2.domains' import
    lines = content.split("\n")
    last_domain_import = -1
    for i, line in enumerate(lines):
        if line.startswith("from tau2.domains."):
            last_domain_import = i

    if last_domain_import >= 0:
        insert_idx = last_domain_import + 1
        while insert_idx < len(lines) and (
            lines[insert_idx].startswith("    ") or lines[insert_idx].startswith(")")
        ):
            insert_idx += 1
        lines.insert(insert_idx, import_line)
        content = "\n".join(lines)

    # Insert registration before logger.debug
    marker = "    logger.debug("
    if marker in content:
        content = content.replace(marker, register_lines + marker)

    _REGISTRY_PATH.write_text(content)
    print(f"  Registered '{domain}' in registry.py")


def finalize_domain(domain_name: str, skip_registry: bool = False) -> None:
    """Finalize a domain: verify tasks.json exists and update registry."""
    data_dir = _DATA_DOMAINS / domain_name
    tasks_path = data_dir / "tasks.json"

    if not tasks_path.exists():
        print(f"Error: {tasks_path} not found. Run generate_tasks --save first.", file=sys.stderr)
        sys.exit(1)

    # Load and count tasks
    tasks_data = json.loads(tasks_path.read_text())
    if isinstance(tasks_data, dict) and "tasks" in tasks_data:
        tasks_data = tasks_data["tasks"]
    task_count = len(tasks_data)

    print(f"Domain '{domain_name}' finalization:")
    print(f"  Tasks: {task_count} in {tasks_path}")
    print(f"  Source: {_SRC_DOMAINS / domain_name}")
    print(f"  Data:   {data_dir}")

    if not skip_registry:
        _update_registry(domain_name)
    else:
        print("  Skipped registry update (--skip-registry)")

    print(f"\nDomain '{domain_name}' finalized.")


def main():
    parser = argparse.ArgumentParser(description="Finalize a tau2-bench domain")
    parser.add_argument("domain_name", help="Domain name")
    parser.add_argument("--skip-registry", action="store_true", help="Skip registry update")
    args = parser.parse_args()

    finalize_domain(args.domain_name, args.skip_registry)


if __name__ == "__main__":
    main()
