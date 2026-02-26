"""Utilities for validating generated code and JSON."""

import importlib
import json
import sys
import types


def validate_python_syntax(code: str) -> list[str]:
    """Validate Python syntax. Returns list of errors (empty = valid)."""
    try:
        compile(code, "<generated>", "exec")
        return []
    except SyntaxError as e:
        return [f"SyntaxError at line {e.lineno}: {e.msg}"]


def try_import_module(module_path: str) -> tuple[types.ModuleType | None, list[str]]:
    """Try to import a module by dotted path, with forced reload.

    Returns (module, errors). Module is None if import failed.
    """
    errors = []
    try:
        # Remove from cache to force fresh import
        if module_path in sys.modules:
            del sys.modules[module_path]
        # Also remove parent modules from cache to pick up new subpackages
        parts = module_path.split(".")
        for i in range(len(parts)):
            parent = ".".join(parts[: i + 1])
            if parent in sys.modules:
                del sys.modules[parent]

        module = importlib.import_module(module_path)
        return module, []
    except Exception as e:
        errors.append(f"ImportError for {module_path}: {type(e).__name__}: {e}")
        return None, errors


def validate_json(text: str) -> tuple[dict | list | None, list[str]]:
    """Parse JSON text. Returns (parsed, errors)."""
    try:
        parsed = json.loads(text)
        return parsed, []
    except json.JSONDecodeError as e:
        return None, [f"JSON parse error: {e}"]
