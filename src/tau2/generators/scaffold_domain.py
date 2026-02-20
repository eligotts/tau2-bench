"""Scaffold a new domain: create directories, __init__.py, and utils.py.

Usage:
    python -m tau2.generators.scaffold_domain <domain_name>
"""

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parents[3]
_SRC_DOMAINS = _PROJECT_ROOT / "src" / "tau2" / "domains"
_DATA_DOMAINS = _PROJECT_ROOT / "data" / "tau2" / "domains"


def scaffold_domain(domain_name: str) -> None:
    """Create directory structure and boilerplate files for a new domain."""
    src_dir = _SRC_DOMAINS / domain_name
    data_dir = _DATA_DOMAINS / domain_name

    if src_dir.exists():
        print(f"Warning: {src_dir} already exists")
    if data_dir.exists():
        print(f"Warning: {data_dir} already exists")

    # Create directories
    src_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Write __init__.py
    init_path = src_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text("")
        print(f"  Created {init_path}")
    else:
        print(f"  Skipped {init_path} (already exists)")

    # Write utils.py (deterministic template)
    utils_path = src_dir / "utils.py"
    upper = domain_name.upper()
    utils_code = (
        f"from tau2.utils.utils import DATA_DIR\n"
        f"\n"
        f"{upper}_DATA_DIR = DATA_DIR / \"tau2\" / \"domains\" / \"{domain_name}\"\n"
        f"{upper}_DB_PATH = {upper}_DATA_DIR / \"db.json\"\n"
        f"{upper}_USER_DB_PATH = {upper}_DATA_DIR / \"user_db.json\"\n"
        f"{upper}_POLICY_PATH = {upper}_DATA_DIR / \"policy.md\"\n"
        f"{upper}_TASK_SET_PATH = {upper}_DATA_DIR / \"tasks.json\"\n"
    )
    utils_path.write_text(utils_code)
    print(f"  Created {utils_path}")

    print(f"\nScaffolded domain '{domain_name}':")
    print(f"  Source: {src_dir}")
    print(f"  Data:   {data_dir}")


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new tau2-bench domain")
    parser.add_argument("domain_name", help="Snake_case domain name (e.g. hotel_resort)")
    args = parser.parse_args()

    # Validate domain name
    name = args.domain_name
    if not name.replace("_", "").isalnum() or not name[0].isalpha():
        print(f"Error: Invalid domain name '{name}'. Must be snake_case alphanumeric.", file=sys.stderr)
        sys.exit(1)

    scaffold_domain(name)


if __name__ == "__main__":
    main()
