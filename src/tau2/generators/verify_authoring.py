"""Pre-generation authoring verification.

Inspects authored source files (tools.py, scenarios.py, policy.md, db.json)
BEFORE task generation, catching bugs at the source before wasting compute
on broken recipes.

Two entry points:
  - verify_authoring()           — 10 structural code checks
  - verify_authoring_with_llm()  — LLM semantic review of raw source files
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Optional

from tau2.environment.environment import Environment
from tau2.environment.toolkit import TOOL_TYPE_ATTR, ToolType
from tau2.generators.recipe import (
    ActionSpec,
    AssertionSpec,
    FaultAtom,
    FaultLayer,
    FaultLayerConfig,
    FaultLayerGroup,
    InitCall,
    RecipeBook,
    _check_predicate,
    _resolve_args,
)
from tau2.generators.verify import parse_llm_verification_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_toolkit(env: Environment, env_type: str):
    """Return the correct toolkit for an env_type string."""
    if env_type == "user":
        return env.user_tools
    return env.tools


def _get_toolkit_for_requestor(env: Environment, requestor: str):
    """Return the correct toolkit for a requestor string."""
    if requestor == "user":
        return env.user_tools
    return env.tools


def _all_layers(recipe_book: RecipeBook) -> list[tuple[FaultLayerConfig, FaultLayerGroup, FaultLayer]]:
    """Yield (config, group, layer) triples from a RecipeBook."""
    results = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                results.append((flc, group, layer))
    return results


def _find_sample_entity(
    flc: FaultLayerConfig,
    get_db: Callable[[], Any],
    layer: Optional[FaultLayer] = None,
) -> Optional[dict]:
    """Find a sample entity that passes the layer's predicate (if any).

    If layer is None, returns the first entity overall.
    """
    db = get_db()
    entities = flc.entity_query(db)
    if not entities:
        return None
    for ent in entities:
        e = ent if isinstance(ent, dict) else (ent.model_dump() if hasattr(ent, "model_dump") else vars(ent))
        if layer is None or _check_predicate(layer, e):
            return e
    # Fallback: return first entity even if predicate fails
    ent = entities[0]
    return ent if isinstance(ent, dict) else (ent.model_dump() if hasattr(ent, "model_dump") else vars(ent))


def _all_template_fields(text: str) -> list[str]:
    """Extract all {field} references from a string."""
    return re.findall(r"\{(\w+)\}", text)


def _resolve_args_safe(template: dict[str, Any], entity: dict) -> tuple[dict, Optional[str]]:
    """Try _resolve_args, return (result, None) or ({}, error_message)."""
    try:
        result = _resolve_args(template, entity)
        return result, None
    except (KeyError, IndexError) as exc:
        return {}, str(exc)


def _resolve_template_safe(template: str, entity: dict) -> Optional[str]:
    """Try template.format(**entity), return error string or None."""
    try:
        template.format(**entity)
        return None
    except KeyError as exc:
        return str(exc)


# ---------------------------------------------------------------------------
# Check 1: init_func_exists
# ---------------------------------------------------------------------------


def _check_init_func_exists(
    env: Environment,
    flc: FaultLayerConfig,
    layer: FaultLayer,
) -> list[str]:
    """Every InitCall.func_name exists as a method on the correct toolkit."""
    issues = []
    all_init_calls = layer.get_init_calls() + flc.base_init_calls
    for ic in all_init_calls:
        toolkit = _get_toolkit(env, ic.env_type)
        if not hasattr(toolkit, ic.func_name):
            issues.append(
                f"ERROR: [{layer.name}] init func '{ic.func_name}' not found "
                f"on {'user_tools' if ic.env_type == 'user' else 'tools'}"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 2: fix_tool_exists
# ---------------------------------------------------------------------------


def _check_fix_tool_exists(
    env: Environment,
    layer: FaultLayer,
) -> list[str]:
    """Every ActionSpec.tool_name exists as an @is_tool method on the correct toolkit."""
    issues = []
    for action in layer.get_actions():
        toolkit = _get_toolkit_for_requestor(env, action.requestor)
        tools = toolkit.get_tools()
        if action.tool_name not in tools:
            issues.append(
                f"ERROR: [{layer.name}] fix tool '{action.tool_name}' not found "
                f"on {'user_tools' if action.requestor == 'user' else 'tools'}"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 3: assertion_func_exists
# ---------------------------------------------------------------------------


def _check_assertion_func_exists(
    env: Environment,
    layer: FaultLayer,
) -> list[str]:
    """Every AssertionSpec.func_name exists as a method on the correct toolkit."""
    issues = []
    for aspec in layer.get_assertions():
        toolkit = _get_toolkit(env, aspec.env_type)
        if not hasattr(toolkit, aspec.func_name):
            issues.append(
                f"ERROR: [{layer.name}] assertion func '{aspec.func_name}' not found "
                f"on {'user_tools' if aspec.env_type == 'user' else 'tools'}"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 4: template_vars_valid
# ---------------------------------------------------------------------------


def _check_template_vars_valid(
    flc: FaultLayerConfig,
    layer: FaultLayer,
    entity: dict,
) -> list[str]:
    """All {field} references in args resolve against a sample entity."""
    issues = []

    # Layer init calls
    for ic in layer.get_init_calls():
        _, err = _resolve_args_safe(ic.args, entity)
        if err:
            issues.append(
                f"ERROR: [{layer.name}] init func '{ic.func_name}' "
                f"has unresolvable template var: {err}"
            )

    # Layer actions
    for action in layer.get_actions():
        _, err = _resolve_args_safe(action.args, entity)
        if err:
            issues.append(
                f"ERROR: [{layer.name}] action '{action.tool_name}' "
                f"has unresolvable template var: {err}"
            )

    # Layer assertions
    for aspec in layer.get_assertions():
        _, err = _resolve_args_safe(aspec.args, entity)
        if err:
            issues.append(
                f"ERROR: [{layer.name}] assertion '{aspec.func_name}' "
                f"has unresolvable template var: {err}"
            )

    # Base init calls
    for ic in flc.base_init_calls:
        _, err = _resolve_args_safe(ic.args, entity)
        if err:
            issues.append(
                f"ERROR: [base] init func '{ic.func_name}' "
                f"has unresolvable template var: {err}"
            )

    return issues


# ---------------------------------------------------------------------------
# Check 5: predicate_fields_exist
# ---------------------------------------------------------------------------


def _check_predicate_fields_exist(
    layer: FaultLayer,
    entity: dict,
) -> list[str]:
    """predicate_field and predicate_ne fields exist in sample entity dicts."""
    issues = []
    if layer.predicate_field and layer.predicate_field not in entity:
        issues.append(
            f"ERROR: [{layer.name}] predicate_field '{layer.predicate_field}' "
            f"not found in entity keys: {sorted(entity.keys())}"
        )
    if layer.predicate_ne:
        field_name, _ = layer.predicate_ne
        if field_name not in entity:
            issues.append(
                f"ERROR: [{layer.name}] predicate_ne field '{field_name}' "
                f"not found in entity keys: {sorted(entity.keys())}"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 6: resource_scope_resolves
# ---------------------------------------------------------------------------


def _check_resource_scope_resolves(
    layer: FaultLayer,
    entity: dict,
) -> list[str]:
    """resource_scope templates resolve against sample entities without KeyError."""
    issues = []
    if layer.resource_scope:
        err = _resolve_template_safe(layer.resource_scope, entity)
        if err:
            issues.append(
                f"ERROR: [{layer.name}] resource_scope has unresolvable "
                f"template var: {err}"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 7: set_assert_coverage
# ---------------------------------------------------------------------------


def _check_set_assert_coverage(
    env: Environment,
) -> list[str]:
    """For each set_* on agent toolkit, check if a matching assert_* exists."""
    issues = []
    toolkit = env.tools
    methods = [m for m in dir(toolkit) if m.startswith("set_") and callable(getattr(toolkit, m))]
    for method_name in methods:
        suffix = method_name[4:]  # strip "set_"
        assert_name = f"assert_{suffix}"
        if not hasattr(toolkit, assert_name):
            issues.append(
                f"WARNING: tools has '{method_name}' but no matching "
                f"'{assert_name}' — verify assertions use the correct name"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 8: requestor_toolkit_match
# ---------------------------------------------------------------------------


def _check_requestor_toolkit_match(
    env: Environment,
    layer: FaultLayer,
) -> list[str]:
    """User actions reference user_tools, agent actions reference agent toolkit."""
    issues = []
    agent_tools = env.tools.get_tools()
    user_tools = env.user_tools.get_tools()

    for action in layer.get_actions():
        if action.requestor == "user":
            if action.tool_name not in user_tools and action.tool_name in agent_tools:
                issues.append(
                    f"ERROR: [{layer.name}] action '{action.tool_name}' has "
                    f"requestor='user' but tool only exists on agent toolkit"
                )
        else:
            if action.tool_name not in agent_tools and action.tool_name in user_tools:
                issues.append(
                    f"ERROR: [{layer.name}] action '{action.tool_name}' has "
                    f"requestor='assistant' but tool only exists on user toolkit"
                )
    return issues


# ---------------------------------------------------------------------------
# Check 9: fix_tool_is_write
# ---------------------------------------------------------------------------


def _check_fix_tool_is_write(
    env: Environment,
    layer: FaultLayer,
) -> list[str]:
    """Agent-side fix actions use WRITE or GENERIC tools, not READ."""
    issues = []
    for action in layer.get_agent_actions():
        toolkit = env.tools
        if hasattr(toolkit, action.tool_name):
            tool_method = toolkit.tools.get(action.tool_name)
            if tool_method is not None:
                tt = getattr(tool_method, TOOL_TYPE_ATTR, None)
                if tt == ToolType.READ:
                    issues.append(
                        f"WARNING: [{layer.name}] agent fix action "
                        f"'{action.tool_name}' is a READ tool — "
                        f"it cannot modify state"
                    )
    return issues


# ---------------------------------------------------------------------------
# Check 10: known_info_fragment_templates
# ---------------------------------------------------------------------------


def _check_known_info_fragment_templates(
    flc: FaultLayerConfig,
    layer: FaultLayer,
    entity: dict,
) -> list[str]:
    """Template refs in known_info_fragment and base templates all resolve."""
    issues = []

    # Layer-level fragment
    err = _resolve_template_safe(layer.known_info_fragment, entity)
    if err:
        issues.append(
            f"ERROR: [{layer.name}] known_info_fragment has unresolvable "
            f"template var: {err}"
        )

    # communicate_templates
    for i, tmpl in enumerate(layer.communicate_templates):
        err = _resolve_template_safe(tmpl, entity)
        if err:
            issues.append(
                f"ERROR: [{layer.name}] communicate_templates[{i}] has "
                f"unresolvable template var: {err}"
            )

    # nl_assertion_templates
    for i, tmpl in enumerate(layer.nl_assertion_templates):
        err = _resolve_template_safe(tmpl, entity)
        if err:
            issues.append(
                f"ERROR: [{layer.name}] nl_assertion_templates[{i}] has "
                f"unresolvable template var: {err}"
            )

    # assertion message_templates
    for aspec in layer.get_assertions():
        if aspec.message_template:
            err = _resolve_template_safe(aspec.message_template, entity)
            if err:
                issues.append(
                    f"ERROR: [{layer.name}] assertion '{aspec.func_name}' "
                    f"message_template has unresolvable var: {err}"
                )

    # Base-level templates (check once per flc, but safe to re-check)
    err = _resolve_template_safe(flc.base_known_info_template, {**entity, "fault_descriptions": "..."})
    if err:
        issues.append(
            f"ERROR: [base] base_known_info_template has unresolvable "
            f"template var: {err}"
        )

    err = _resolve_template_safe(flc.base_ticket_template, {**entity, "fault_descriptions": "..."})
    if err:
        issues.append(
            f"ERROR: [base] base_ticket_template has unresolvable "
            f"template var: {err}"
        )

    for i, tmpl in enumerate(flc.base_communicate_templates):
        err = _resolve_template_safe(tmpl, entity)
        if err:
            issues.append(
                f"ERROR: [base] base_communicate_templates[{i}] has "
                f"unresolvable template var: {err}"
            )

    for i, tmpl in enumerate(flc.base_nl_assertion_templates):
        err = _resolve_template_safe(tmpl, entity)
        if err:
            issues.append(
                f"ERROR: [base] base_nl_assertion_templates[{i}] has "
                f"unresolvable template var: {err}"
            )

    return issues


# ---------------------------------------------------------------------------
# Check base-level specs (actions/assertions on FaultLayerConfig itself)
# ---------------------------------------------------------------------------


def _check_base_specs(
    env: Environment,
    flc: FaultLayerConfig,
    entity: dict,
) -> list[str]:
    """Check base_actions, base_user_actions, base_assertions on FaultLayerConfig."""
    issues = []
    agent_tools = env.tools.get_tools()
    user_tools = env.user_tools.get_tools()

    # base_actions
    for action in flc.base_actions:
        toolkit = _get_toolkit_for_requestor(env, action.requestor)
        tools = toolkit.get_tools()
        if action.tool_name not in tools:
            issues.append(
                f"ERROR: [base] base_actions tool '{action.tool_name}' not found "
                f"on {'user_tools' if action.requestor == 'user' else 'tools'}"
            )
        _, err = _resolve_args_safe(action.args, entity)
        if err:
            issues.append(
                f"ERROR: [base] base_actions '{action.tool_name}' "
                f"has unresolvable template var: {err}"
            )

    # base_user_actions
    for action in flc.base_user_actions:
        if action.tool_name not in user_tools:
            issues.append(
                f"ERROR: [base] base_user_actions tool '{action.tool_name}' "
                f"not found on user_tools"
            )
        _, err = _resolve_args_safe(action.args, entity)
        if err:
            issues.append(
                f"ERROR: [base] base_user_actions '{action.tool_name}' "
                f"has unresolvable template var: {err}"
            )

    # base_assertions
    for aspec in flc.base_assertions:
        toolkit = _get_toolkit(env, aspec.env_type)
        if not hasattr(toolkit, aspec.func_name):
            issues.append(
                f"ERROR: [base] base_assertions func '{aspec.func_name}' "
                f"not found on {'user_tools' if aspec.env_type == 'user' else 'tools'}"
            )
        _, err = _resolve_args_safe(aspec.args, entity)
        if err:
            issues.append(
                f"ERROR: [base] base_assertions '{aspec.func_name}' "
                f"has unresolvable template var: {err}"
            )

    return issues


# ---------------------------------------------------------------------------
# Main: verify_authoring
# ---------------------------------------------------------------------------


def verify_authoring(
    recipe_book: RecipeBook,
    get_env: Callable[[], Environment],
    get_db: Callable[[], Any],
) -> list[str]:
    """Run 10 structural checks on authored definitions before task generation.

    Returns a list of issue strings with ERROR: or WARNING: prefixes.
    """
    issues: list[str] = []
    env = get_env()

    # Set/assert coverage is global (check 7)
    issues.extend(_check_set_assert_coverage(env))

    for flc, group, layer in _all_layers(recipe_book):
        # Find a sample entity that passes this layer's predicate
        entity = _find_sample_entity(flc, get_db, layer)
        if entity is None:
            issues.append(
                f"ERROR: [{layer.name}] no entities returned by entity_query"
            )
            continue

        # Check 1: init_func_exists
        issues.extend(_check_init_func_exists(env, flc, layer))

        # Check 2: fix_tool_exists
        issues.extend(_check_fix_tool_exists(env, layer))

        # Check 3: assertion_func_exists
        issues.extend(_check_assertion_func_exists(env, layer))

        # Check 4: template_vars_valid
        issues.extend(_check_template_vars_valid(flc, layer, entity))

        # Check 5: predicate_fields_exist
        issues.extend(_check_predicate_fields_exist(layer, entity))

        # Check 6: resource_scope_resolves
        issues.extend(_check_resource_scope_resolves(layer, entity))

        # Check 8: requestor_toolkit_match
        issues.extend(_check_requestor_toolkit_match(env, layer))

        # Check 9: fix_tool_is_write
        issues.extend(_check_fix_tool_is_write(env, layer))

        # Check 10: known_info_fragment_templates
        issues.extend(_check_known_info_fragment_templates(flc, layer, entity))

    # Base-level spec checks (once per FaultLayerConfig)
    for flc in recipe_book.fault_layer_configs:
        entity = _find_sample_entity(flc, get_db)
        if entity is not None:
            issues.extend(_check_base_specs(env, flc, entity))

    return issues


# ---------------------------------------------------------------------------
# File collection helper
# ---------------------------------------------------------------------------


def collect_authored_files(
    file_paths: dict[str, str],
    db_path: str,
    max_db_entities: int = 3,
) -> dict[str, str]:
    """Read authored source files and a truncated db.json sample.

    Args:
        file_paths: {label: path} for source files (e.g. {"tools.py": "/path/to/tools.py"}).
        db_path: Path to db.json.
        max_db_entities: Max entities per collection to include from db.json.

    Returns:
        {filename: content} dict suitable for passing to verify_authoring_with_llm.
    """
    result: dict[str, str] = {}

    for label, path in file_paths.items():
        p = Path(path)
        if p.exists():
            result[label] = p.read_text()
        else:
            result[label] = f"[FILE NOT FOUND: {path}]"

    # Truncated db.json
    db_p = Path(db_path)
    if db_p.exists():
        try:
            db_data = json.loads(db_p.read_text())
            truncated = {}
            if isinstance(db_data, dict):
                for key, value in db_data.items():
                    if isinstance(value, list) and len(value) > max_db_entities:
                        truncated[key] = value[:max_db_entities]
                        truncated[f"__{key}_total_count"] = len(value)
                    else:
                        truncated[key] = value
            else:
                truncated = db_data
            result["db.json (sample)"] = json.dumps(truncated, indent=2, default=str)
        except Exception as e:
            result["db.json (sample)"] = f"[ERROR reading db.json: {e}]"
    else:
        result["db.json (sample)"] = f"[FILE NOT FOUND: {db_path}]"

    return result


# ---------------------------------------------------------------------------
# Recipe structure summary
# ---------------------------------------------------------------------------


def _build_recipe_summary(recipe_book: RecipeBook) -> str:
    """Build a human-readable summary of the recipe structure."""
    lines = ["## Recipe Book Structure\n"]

    for flc in recipe_book.fault_layer_configs:
        lines.append(f"### FaultLayerConfig: {flc.name}")
        lines.append(f"  entity_id_field: {flc.entity_id_field}")
        lines.append(f"  min_faults: {flc.min_faults}, max_faults: {flc.max_faults}")
        lines.append(f"  base_init_calls: {len(flc.base_init_calls)}")
        lines.append(f"  base_actions: {len(flc.base_actions)}")
        lines.append(f"  base_user_actions: {len(flc.base_user_actions)}")
        lines.append(f"  base_assertions: {len(flc.base_assertions)}")
        lines.append("")

        for group in flc.groups:
            lines.append(f"  Group: {group.name} ({len(group.layers)} layers)")
            for layer in group.layers:
                atoms = layer.atoms
                init_calls = layer.get_init_calls()
                actions = layer.get_actions()
                assertions = layer.get_assertions()
                lines.append(f"    Layer: {layer.name}")
                lines.append(f"      unfixable: {layer.unfixable}")
                lines.append(f"      atoms: {len(atoms)}")
                lines.append(f"      init_calls: {[ic.func_name for ic in init_calls]}")
                lines.append(f"      actions: {[(a.tool_name, a.requestor) for a in actions]}")
                lines.append(f"      assertions: {[a.func_name for a in assertions]}")
                if layer.predicate_field:
                    lines.append(f"      predicate_field: {layer.predicate_field}")
                if layer.predicate_ne:
                    lines.append(f"      predicate_ne: {layer.predicate_ne}")
                if layer.resource_scope:
                    lines.append(f"      resource_scope: {layer.resource_scope}")
                lines.append(f"      known_info_fragment: {layer.known_info_fragment[:80]}...")
            lines.append("")

    for recipe in recipe_book.recipes:
        lines.append(f"### Recipe: {recipe.name}")
        lines.append(f"  actions: {[(a.tool_name, a.requestor) for a in recipe.goal_actions]}")
        lines.append(f"  assertions: {[a.func_name for a in recipe.post_assertions]}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM Semantic Review
# ---------------------------------------------------------------------------


_AUTHORING_LLM_PROMPT_TEMPLATE = """\
You are a verification engine for a task-generation pipeline. You are reviewing
the RAW AUTHORED SOURCE FILES that define a domain — not the generated output.
Your job is to find bugs in these definitions BEFORE tasks are generated.

## Authored Files

{file_contents}

## Recipe Structure

{recipe_summary}

## Structural Issues Already Found

{structural_issues}

## Your 10 Checks

Perform each check independently. For each, output ERROR: or WARNING: lines.

1. **Set/Assert Semantic Correspondence**: Does each set_X init function break
   exactly what the corresponding assert_X checks? Cross-reference init→check
   pairs in the fault atoms. If set_foo changes field A but assert_foo checks
   field B, the atom will silently pass without testing what was broken.

2. **Policy-Scenario Alignment**: For each fault layer, does the policy document
   prescribe the workflow encoded in that layer's atoms? If the policy says
   "always ask for confirmation" but the layer has no user confirmation atom,
   the generated task will fail when agents correctly follow policy.

3. **Known Info Fragment Clarity**: Are fragments unambiguous? Do they
   disambiguate resources with template variables (e.g., "appointment
   {{appointment_id}}" not just "my appointment")? Vague fragments cause agents
   to fix the wrong resource.

4. **Init State Coherence**: Do init functions leave stale or contradictory
   fields on records? Init typically sets only targeted fields — other fields
   retain original values. Check for inconsistent field combinations.

5. **Multi-Atom Logical Sequence**: Do multi-atom layers form natural
   progressions? E.g., agent fixes → user confirms. Check that atom ordering
   makes sense and no intermediate state is contradictory.

6. **sync_tools Completeness**: Does sync_tools (in environment.py) project all
   fields the user needs to see? If a fault changes a field that sync_tools
   doesn't project, the user can't observe the problem.

7. **DB Data Quality**: Are FK relationships valid? Are there enough entities
   for meaningful test coverage? Is the data realistic?

8. **Unfixable Layer Design**: For unfixable layers, are conditions realistic?
   Do they have preservation assertions? Is transfer_to_human the correct
   response?

9. **User Tool Realism**: Do user tools match what a real user would do? Are
   the user action sequences natural?

10. **Tool Precondition Safety**: Could sync_tools or user tools invalidate
    agent tool preconditions between turns? Flag state changes that could make
    required agent tools unreachable.

Respond in this exact format:
ISSUES_FOUND: <yes|no>
<If yes, list each issue on its own line prefixed with "- ERROR:" or "- WARNING:">
"""


def verify_authoring_with_llm(
    recipe_book: RecipeBook,
    authored_files: dict[str, str],
    structural_issues: list[str],
    llm_call_fn: Callable[[str], str],
) -> list[str]:
    """Run LLM semantic review on raw authored source files.

    Args:
        recipe_book: The domain's RecipeBook.
        authored_files: {filename: content} from collect_authored_files().
        structural_issues: Issues already found by verify_authoring().
        llm_call_fn: Callable that takes a prompt string and returns LLM response.

    Returns:
        List of issue strings with LLM_REVIEW: ERROR: or LLM_REVIEW: WARNING: prefixes.
    """
    # Build file contents section
    file_sections = []
    for name, content in authored_files.items():
        file_sections.append(f"### {name}\n```\n{content}\n```\n")
    file_contents = "\n".join(file_sections)

    # Build recipe summary
    recipe_summary = _build_recipe_summary(recipe_book)

    # Format structural issues
    if structural_issues:
        structural_str = "\n".join(f"- {issue}" for issue in structural_issues)
    else:
        structural_str = "None found."

    prompt = _AUTHORING_LLM_PROMPT_TEMPLATE.format(
        file_contents=file_contents,
        recipe_summary=recipe_summary,
        structural_issues=structural_str,
    )

    try:
        response = llm_call_fn(prompt)
        issues = parse_llm_verification_response(response)
        if issues:
            print(f"\nLLM Authoring Review: {len(issues)} issue(s) found")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("\nLLM Authoring Review: no issues found")
        return issues
    except Exception as e:
        error = f"LLM_REVIEW: ERROR calling LLM: {e}"
        print(f"\n{error}")
        return [error]
