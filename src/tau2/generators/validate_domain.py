"""Validate a domain's generated files, step by step.

Usage:
    python -m tau2.generators.validate_domain <domain_name> [--step <step_name>]

Steps: domain_spec, data_model, user_data_model, db_json, user_db_json,
       policy, tools, user_tools, environment, scenarios

If --step is omitted, runs ALL validations in order, stopping on first failure.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from tau2.generators.code_utils import (
    try_import_module,
    validate_json,
    validate_python_syntax,
)
from tau2.generators.depgraph.loaders import load_graph_contract
from tau2.generators.depgraph.runtime_checks import check_policy_against_contract

_PROJECT_ROOT = Path(__file__).parents[3]
_SRC_DOMAINS = _PROJECT_ROOT / "src" / "tau2" / "domains"
_DATA_DOMAINS = _PROJECT_ROOT / "data" / "tau2" / "domains"


def _class_name(domain_name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in domain_name.split("_"))


def _normalize_class_key(name: str) -> str:
    """Normalize class names so acronym capitalization does not matter."""
    return re.sub(r"[^A-Za-z0-9]", "", name).lower()


def _resolve_class(module: object, expected_name: str) -> tuple[str | None, type | None]:
    """Resolve a class by exact name first, then by normalized name."""
    candidate = getattr(module, expected_name, None)
    if isinstance(candidate, type):
        return expected_name, candidate

    target_key = _normalize_class_key(expected_name)
    for attr_name, value in vars(module).items():
        if not isinstance(value, type):
            continue
        if _normalize_class_key(attr_name) == target_key:
            return attr_name, value

    return None, None


# ---------------------------------------------------------------------------
# Individual validators — each reads files from disk
# ---------------------------------------------------------------------------


def validate_domain_spec(domain_name: str) -> list[str]:
    """Validate domain_spec.json."""
    data_dir = _DATA_DOMAINS / domain_name
    spec_path = data_dir / "domain_spec.json"

    if not spec_path.exists():
        return [f"domain_spec.json not found at {spec_path}"]

    text = spec_path.read_text()
    parsed, parse_errors = validate_json(text)
    if parse_errors:
        return parse_errors

    if not isinstance(parsed, dict):
        return ["Expected a JSON object"]

    errors = []
    required_keys = [
        "domain_name",
        "entities",
        "tools",
        "fault_groups",
        "policy_sections",
        "sync_rules",
    ]
    for key in required_keys:
        if key not in parsed:
            errors.append(f"Missing required key: {key}")

    if "entities" in parsed and len(parsed["entities"]) < 2:
        errors.append("Need at least 2 entity types")

    if "tools" in parsed:
        tools = parsed["tools"]
        if len(tools) < 3:
            errors.append("Need at least 3 tools")
        types = {t.get("type", "").upper() for t in tools}
        if "WRITE" not in types:
            errors.append("Need at least 1 WRITE tool")

    if "fault_groups" in parsed and len(parsed["fault_groups"]) < 3:
        errors.append("Need at least 3 fault groups")

    if "domain_name" in parsed:
        name = parsed["domain_name"]
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            errors.append(f"Invalid domain_name: {name}")

    return errors


def validate_data_model(domain_name: str) -> list[str]:
    """Validate data_model.py."""
    src_dir = _SRC_DOMAINS / domain_name
    path = src_dir / "data_model.py"

    if not path.exists():
        return [f"data_model.py not found at {path}"]

    code = path.read_text()
    errors = validate_python_syntax(code)
    if errors:
        return errors

    module_path = f"tau2.domains.{domain_name}.data_model"
    module, import_errors = try_import_module(module_path)
    if import_errors:
        return import_errors

    db_cls_name = f"{_class_name(domain_name)}DB"
    actual_name, db_cls = _resolve_class(module, db_cls_name)
    if db_cls is None:
        return [f"Module missing {db_cls_name} class"]

    from tau2.environment.db import DB

    if not issubclass(db_cls, DB):
        return [f"{actual_name} must be a subclass of DB"]

    return []


def validate_user_data_model(domain_name: str) -> list[str]:
    """Validate user_data_model.py."""
    src_dir = _SRC_DOMAINS / domain_name
    path = src_dir / "user_data_model.py"

    if not path.exists():
        return [f"user_data_model.py not found at {path}"]

    code = path.read_text()
    errors = validate_python_syntax(code)
    if errors:
        return errors

    module_path = f"tau2.domains.{domain_name}.user_data_model"
    module, import_errors = try_import_module(module_path)
    if import_errors:
        return import_errors

    db_cls_name = f"{_class_name(domain_name)}UserDB"
    actual_name, db_cls = _resolve_class(module, db_cls_name)
    if db_cls is None:
        return [f"Module missing {db_cls_name} class"]

    from tau2.environment.db import DB

    if not issubclass(db_cls, DB):
        return [f"{actual_name} must be a subclass of DB"]

    # Check all fields have defaults
    for field_name, field_info in db_cls.model_fields.items():
        if field_info.default is None and field_info.default_factory is None:
            if not field_info.is_required():
                continue
            return [f"Field '{field_name}' in {actual_name} must have a default value"]

    return []


def validate_db_json(domain_name: str) -> list[str]:
    """Validate db.json against the data model."""
    data_dir = _DATA_DOMAINS / domain_name
    path = data_dir / "db.json"

    if not path.exists():
        return [f"db.json not found at {path}"]

    text = path.read_text()
    parsed, parse_errors = validate_json(text)
    if parse_errors:
        return parse_errors

    # Try loading with the DB class
    module_path = f"tau2.domains.{domain_name}.data_model"
    module, import_errors = try_import_module(module_path)
    if import_errors:
        return import_errors

    db_cls_name = f"{_class_name(domain_name)}DB"
    _, db_cls = _resolve_class(module, db_cls_name)
    if db_cls is None:
        return [f"Module missing {db_cls_name} class"]

    try:
        db = db_cls.load(path)
    except Exception as e:
        return [f"DB.load() failed: {type(e).__name__}: {e}"]

    # Check minimum entity count
    total_entities = 0
    for field_name in type(db).model_fields:
        val = getattr(db, field_name)
        if isinstance(val, list):
            total_entities += len(val)
    if total_entities < 3:
        return [f"Too few entities ({total_entities}). Need at least 3."]

    return []


def validate_user_db_json(domain_name: str) -> list[str]:
    """Validate user_db.json against the user data model."""
    data_dir = _DATA_DOMAINS / domain_name
    path = data_dir / "user_db.json"

    if not path.exists():
        return [f"user_db.json not found at {path}"]

    text = path.read_text()
    parsed, parse_errors = validate_json(text)
    if parse_errors:
        return parse_errors

    module_path = f"tau2.domains.{domain_name}.user_data_model"
    module, import_errors = try_import_module(module_path)
    if import_errors:
        return import_errors

    db_cls_name = f"{_class_name(domain_name)}UserDB"
    _, db_cls = _resolve_class(module, db_cls_name)
    if db_cls is None:
        return [f"Module missing {db_cls_name} class"]

    try:
        db_cls.load(path)
    except Exception as e:
        return [f"UserDB.load() failed: {type(e).__name__}: {e}"]

    # Check identity fields are null
    if isinstance(parsed, dict):
        for key in parsed:
            is_identity = (
                key.endswith("_name")
                or key == "name"
                or key.endswith("_id")
            )
            if is_identity:
                val = parsed[key]
                if val is not None and val != "":
                    return [f"Identity field '{key}' should be null, got {val}"]

    return []


def validate_policy(domain_name: str) -> list[str]:
    """Validate policy.md."""
    data_dir = _DATA_DOMAINS / domain_name
    path = data_dir / "policy.md"

    if not path.exists():
        return [f"policy.md not found at {path}"]

    content = path.read_text()
    errors = []

    if len(content) < 100:
        errors.append("Policy is too short (< 100 chars)")

    contract_path = data_dir / "graph_contract.yaml"
    if contract_path.exists():
        try:
            contract = load_graph_contract(str(contract_path))
        except Exception as exc:
            errors.append(f"graph_contract.yaml failed to load for policy linkage check: {exc}")
        else:
            errors.extend(check_policy_against_contract(contract, content))
        return errors

    # Fallback for non-depgraph domains: check that some tool names are mentioned.
    spec_path = data_dir / "domain_spec.json"
    if spec_path.exists():
        try:
            spec = json.loads(spec_path.read_text())
            tools = spec.get("tools", [])
            tool_names = [t["name"] for t in tools]
            mentioned = sum(1 for name in tool_names if name in content)
            if mentioned < 2:
                errors.append(
                    f"Policy should mention tool names. Found {mentioned}/{len(tool_names)}"
                )
        except (json.JSONDecodeError, KeyError):
            pass

    return errors


def validate_tools(domain_name: str) -> list[str]:
    """Validate tools.py."""
    src_dir = _SRC_DOMAINS / domain_name
    path = src_dir / "tools.py"

    if not path.exists():
        return [f"tools.py not found at {path}"]

    code = path.read_text()
    errors = validate_python_syntax(code)
    if errors:
        return errors

    module_path = f"tau2.domains.{domain_name}.tools"
    module, import_errors = try_import_module(module_path)
    if import_errors:
        return import_errors

    tools_cls_name = f"{_class_name(domain_name)}Tools"
    actual_tools_cls_name, tools_cls = _resolve_class(module, tools_cls_name)
    if tools_cls is None:
        return [f"Module missing {tools_cls_name} class"]

    # Try instantiating with the DB
    db_module_path = f"tau2.domains.{domain_name}.data_model"
    db_module, _ = try_import_module(db_module_path)
    if db_module is None:
        return ["Cannot import data_model to test tools"]

    data_dir = _DATA_DOMAINS / domain_name
    db_cls_name = f"{_class_name(domain_name)}DB"
    _, db_cls = _resolve_class(db_module, db_cls_name)
    if db_cls is None:
        return [f"Module missing {db_cls_name} class"]
    db = db_cls.load(data_dir / "db.json")

    try:
        tools_instance = tools_cls(db)
    except Exception as e:
        return [f"Failed to instantiate {actual_tools_cls_name}: {e}"]

    tools_dict = tools_instance.get_tools()
    if len(tools_dict) < 3:
        errors.append(f"Expected >= 3 tools, got {len(tools_dict)}")

    # Check tool types
    from tau2.environment.toolkit import ToolType

    type_counts = {"READ": 0, "WRITE": 0, "GENERIC": 0}
    for name in tools_dict:
        try:
            tt = tools_instance.tool_type(name)
            if tt == ToolType.READ:
                type_counts["READ"] += 1
            elif tt == ToolType.WRITE:
                type_counts["WRITE"] += 1
            elif tt == ToolType.GENERIC:
                type_counts["GENERIC"] += 1
        except Exception:
            pass

    if type_counts["WRITE"] < 1:
        errors.append("Need at least 1 WRITE tool")

    # Check for assertion helpers
    has_assert = any(
        name.startswith("assert_") and not hasattr(getattr(tools_cls, name, None), "__tool__")
        for name in dir(tools_cls)
        if not name.startswith("_")
    )
    if not has_assert:
        errors.append("Missing assertion helpers (assert_* methods returning bool)")

    # Check for setup helpers
    has_setup = any(
        name.startswith("set_") and not hasattr(getattr(tools_cls, name, None), "__tool__")
        for name in dir(tools_cls)
        if not name.startswith("_")
    )
    if not has_setup:
        errors.append("Missing setup helpers (set_* methods)")

    # Check for entity navigation tools
    from tau2.environment.toolkit import ToolType as TT

    read_tool_names = [
        name for name in tools_dict
        if tools_instance.tool_type(name) == TT.READ
    ]
    child_collections = []
    for field_name in type(db).model_fields:
        val = getattr(db, field_name)
        if isinstance(val, list) and val:
            child_collections.append((field_name, val))

    if len(child_collections) >= 2:
        fk_fields: dict[str, int] = {}
        for coll_name, items in child_collections:
            if not items:
                continue
            first_item = items[0]
            if hasattr(type(first_item), "model_fields"):
                for fname in type(first_item).model_fields:
                    if fname.endswith("_id") and fname != list(type(first_item).model_fields.keys())[0]:
                        fk_fields[fname] = fk_fields.get(fname, 0) + 1

        if fk_fields:
            primary_fk = max(fk_fields, key=fk_fields.get)
            fk_count = fk_fields[primary_fk]
            if fk_count >= 2:
                has_nav_tool = False
                for tool_name in read_tool_names:
                    tool = tools_dict[tool_name]
                    schema = tool.params.model_json_schema()
                    params = set(schema.get("properties", {}).keys())
                    if primary_fk in params:
                        has_nav_tool = True
                        break
                if not has_nav_tool:
                    errors.append(
                        f"Missing entity navigation tools: {fk_count} child entity types "
                        f"reference '{primary_fk}' but no READ tool accepts '{primary_fk}' "
                        f"as a parameter."
                    )

    return errors


def validate_user_tools(domain_name: str) -> list[str]:
    """Validate user_tools.py."""
    src_dir = _SRC_DOMAINS / domain_name
    path = src_dir / "user_tools.py"

    if not path.exists():
        return [f"user_tools.py not found at {path}"]

    code = path.read_text()
    errors = validate_python_syntax(code)
    if errors:
        return errors

    module_path = f"tau2.domains.{domain_name}.user_tools"
    module, import_errors = try_import_module(module_path)
    if import_errors:
        return import_errors

    cls_name = f"{_class_name(domain_name)}UserTools"
    actual_cls_name, cls = _resolve_class(module, cls_name)
    if cls is None:
        return [f"Module missing {cls_name} class"]

    # Instantiate
    user_db_module_path = f"tau2.domains.{domain_name}.user_data_model"
    user_db_module, _ = try_import_module(user_db_module_path)
    if user_db_module is None:
        return ["Cannot import user_data_model to test user_tools"]

    data_dir = _DATA_DOMAINS / domain_name
    user_db_cls_name = f"{_class_name(domain_name)}UserDB"
    _, user_db_cls = _resolve_class(user_db_module, user_db_cls_name)
    if user_db_cls is None:
        return [f"Module missing {user_db_cls_name} class"]
    user_db = user_db_cls.load(data_dir / "user_db.json")

    try:
        instance = cls(user_db)
    except Exception as e:
        return [f"Failed to instantiate {actual_cls_name}: {e}"]

    tools_dict = instance.get_tools()
    if len(tools_dict) < 1:
        errors.append("Need at least 1 user tool")

    # Check for assertion helpers
    has_assert = any(
        name.startswith("assert_") and not hasattr(getattr(cls, name, None), "__tool__")
        for name in dir(cls)
        if not name.startswith("_")
    )
    if not has_assert:
        errors.append("Missing assertion helpers")

    # Check for setup helper
    has_setup = any(
        name.startswith("set_") and not hasattr(getattr(cls, name, None), "__tool__")
        for name in dir(cls)
        if not name.startswith("_")
    )
    if not has_setup:
        errors.append("Missing setup helper (set_user_info or similar)")

    return errors


def validate_environment(domain_name: str) -> list[str]:
    """Validate environment.py."""
    src_dir = _SRC_DOMAINS / domain_name
    path = src_dir / "environment.py"

    if not path.exists():
        return [f"environment.py not found at {path}"]

    code = path.read_text()
    errors = []

    # Check environment.py doesn't define its own path constants
    for line in code.splitlines():
        stripped = line.strip()
        if ("_DIR" in stripped or "_PATH" in stripped) and "=" in stripped and "import" not in stripped:
            lhs = stripped.split("=")[0].strip()
            if lhs.endswith("_DIR") or lhs.endswith("_PATH"):
                return [
                    f"environment.py must NOT define its own path constants. "
                    f"Import them from tau2.domains.{domain_name}.utils instead."
                ]

    syntax_errors = validate_python_syntax(code)
    if syntax_errors:
        return [f"environment.py: {e}" for e in syntax_errors]

    env_module_path = f"tau2.domains.{domain_name}.environment"
    env_module, import_errors = try_import_module(env_module_path)
    if import_errors:
        return [f"environment.py import: {e}" for e in import_errors]

    if not hasattr(env_module, "get_environment"):
        return ["environment.py missing get_environment() function"]

    from tau2.environment.environment import Environment

    try:
        env = env_module.get_environment()
    except Exception as e:
        return [f"get_environment() failed: {type(e).__name__}: {e}"]

    if not isinstance(env, Environment):
        return [f"get_environment() returned {type(env)}, expected Environment"]

    # Check solo_mode kwarg
    try:
        env_module.get_environment(solo_mode=True)
    except TypeError as e:
        errors.append(
            f"get_environment(solo_mode=True) failed: {e}. "
            f"Add 'solo_mode=False' parameter and call env.set_solo_mode(True) when set."
        )
    except Exception:
        pass

    try:
        env.tools.get_tools()
    except Exception as e:
        errors.append(f"env.tools.get_tools() failed: {e}")

    try:
        env.sync_tools()
    except Exception as e:
        errors.append(f"env.sync_tools() failed: {e}")

    return errors


def _validate_loaded_tasks(tasks) -> list[str]:
    if not tasks:
        return ["task loader returned 0 tasks"]

    errors: list[str] = []
    # Check that tasks have persona suffixes
    task_ids = [t.id for t in tasks]
    has_persona = any("[PERSONA:" in tid for tid in task_ids)
    if not has_persona:
        print("  WARNING: Tasks don't have [PERSONA:] suffixes")

    # Check for resource conflicts in multi-fault tasks
    _DESTRUCTIVE_ACTIONS = {"cancel_appointment", "cancel_order", "remove_", "delete_"}
    conflict_count = 0
    for task in tasks[:200]:
        ec = task.evaluation_criteria
        if not ec or not ec.actions or len(ec.actions) < 2:
            continue
        resource_ops: dict[str, list[str]] = {}
        for action in ec.actions:
            if not action.arguments:
                continue
            for arg_key, arg_val in action.arguments.items():
                if arg_key.endswith("_id") and arg_key not in (
                    "client_id", "customer_id", "user_id", "member_id", "patron_id"
                ):
                    key = f"{arg_key}={arg_val}"
                    resource_ops.setdefault(key, []).append(action.name)
        for res_key, action_names in resource_ops.items():
            if len(action_names) < 2:
                continue
            has_destructive = any(
                any(d in name for d in _DESTRUCTIVE_ACTIONS)
                for name in action_names
            )
            has_non_destructive = any(
                not any(d in name for d in _DESTRUCTIVE_ACTIONS)
                for name in action_names
            )
            if has_destructive and has_non_destructive:
                conflict_count += 1
                if conflict_count <= 3:
                    errors.append(
                        f"Resource conflict: {res_key} has contradictory actions "
                        f"{action_names} in task {task.id[:80]}."
                    )
                break
        if conflict_count > 3:
            break

    return errors


def validate_scenarios(domain_name: str) -> list[str]:
    """Validate scenarios.py or compiled task loader paths."""
    src_dir = _SRC_DOMAINS / domain_name
    path = src_dir / "scenarios.py"

    if not path.exists():
        env_module_path = f"tau2.domains.{domain_name}.environment"
        env_module, import_errors = try_import_module(env_module_path)
        if import_errors:
            return import_errors

        get_tasks = getattr(env_module, "get_tasks", None)
        if not callable(get_tasks):
            return [f"scenarios.py not found at {path} and environment.py missing get_tasks()"]

        try:
            tasks = get_tasks(task_split_name=None)
        except TypeError:
            tasks = get_tasks()
        except Exception as e:
            return [f"environment.get_tasks() failed: {type(e).__name__}: {e}"]

        errors = _validate_loaded_tasks(tasks)
        print(f"  environment.get_tasks() loaded {len(tasks)} tasks")
        return errors

    code = path.read_text()
    errors = validate_python_syntax(code)
    if errors:
        return errors

    # Check scenarios.py doesn't define its own data paths
    for line in code.splitlines():
        stripped = line.strip()
        if ("_DIR" in stripped or "_PATH" in stripped) and "=" in stripped and "import" not in stripped:
            lhs = stripped.split("=")[0].strip()
            if lhs.endswith("_DIR") or lhs.endswith("_PATH"):
                domain_upper = domain_name.upper()
                return [
                    f"scenarios.py must NOT define its own path constants (like {domain_upper}_DIR or "
                    f"{domain_upper}_DB_PATH). Import them from tau2.domains.{domain_name}.utils instead."
                ]

    module_path = f"tau2.domains.{domain_name}.scenarios"
    module, import_errors = try_import_module(module_path)
    if import_errors:
        return import_errors

    if not hasattr(module, "create_tasks"):
        return ["scenarios.py missing create_tasks() function"]

    # Try generating tasks without verification
    try:
        tasks = module.create_tasks(verify=False)
    except Exception as e:
        return [f"create_tasks(verify=False) failed: {type(e).__name__}: {e}"]

    errors = _validate_loaded_tasks(tasks)
    print(f"  scenarios.py generated {len(tasks)} tasks")
    return errors


# ---------------------------------------------------------------------------
# Step registry and runner
# ---------------------------------------------------------------------------

ALL_STEPS = [
    ("domain_spec", validate_domain_spec),
    ("data_model", validate_data_model),
    ("user_data_model", validate_user_data_model),
    ("db_json", validate_db_json),
    ("user_db_json", validate_user_db_json),
    ("policy", validate_policy),
    ("tools", validate_tools),
    ("user_tools", validate_user_tools),
    ("environment", validate_environment),
    ("scenarios", validate_scenarios),
]


def run_validation(domain_name: str, step: str | None = None) -> bool:
    """Run validation for a domain. Returns True if all passed."""
    if step:
        # Run single step
        validator = dict(ALL_STEPS).get(step)
        if validator is None:
            print(f"Error: Unknown step '{step}'", file=sys.stderr)
            print(f"Valid steps: {[s[0] for s in ALL_STEPS]}", file=sys.stderr)
            return False

        print(f"Validating {step} for '{domain_name}'...")
        errors = validator(domain_name)
        if errors:
            print(f"  FAIL: {step}")
            for e in errors:
                print(f"    - {e}")
            return False
        print(f"  PASS: {step}")
        return True

    # Run all steps
    print(f"Validating all steps for '{domain_name}'...")
    all_passed = True
    for step_name, validator in ALL_STEPS:
        # domain_spec is optional for hand-crafted domains
        if step_name == "domain_spec":
            spec_path = _DATA_DOMAINS / domain_name / "domain_spec.json"
            if not spec_path.exists():
                print(f"  {step_name}... SKIP (no domain_spec.json)")
                continue
        print(f"  {step_name}...", end=" ")
        errors = validator(domain_name)
        if errors:
            print("FAIL")
            for e in errors:
                print(f"    - {e}")
            all_passed = False
            break  # Stop on first failure
        print("PASS")

    if all_passed:
        print(f"\nAll validations passed for '{domain_name}'.")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Validate a tau2-bench domain")
    parser.add_argument("domain_name", help="Domain name to validate")
    parser.add_argument("--step", help="Specific step to validate", default=None)
    args = parser.parse_args()

    success = run_validation(args.domain_name, args.step)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
