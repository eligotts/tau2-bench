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
    """Agent-side fix actions use WRITE or GENERIC tools, not READ.

    Skips atoms with step_type="diagnostic" — they are intentionally READ.
    """
    issues = []
    # Collect diagnostic tool names from atoms
    diagnostic_tools: set[str] = set()
    for atom in layer.atoms:
        if atom.step_type == "diagnostic":
            diagnostic_tools.add(atom.fix.tool_name)

    for action in layer.get_agent_actions():
        # Skip diagnostic actions — they're READ by design
        if action.tool_name in diagnostic_tools:
            continue
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
# Check 11: assertion_density (DI-4)
# ---------------------------------------------------------------------------


def _check_assertion_density(recipe_book: RecipeBook) -> list[str]:
    """DI-4: ≥40% of fixable layers must have 2+ assertions."""
    issues = []
    total_fixable = 0
    multi_assert = 0

    for flc, group, layer in _all_layers(recipe_book):
        if layer.unfixable:
            continue
        total_fixable += 1
        assertion_count = len(layer.get_assertions())
        if assertion_count >= 2:
            multi_assert += 1

    if total_fixable > 0:
        pct = multi_assert / total_fixable * 100
        if pct < 40:
            issues.append(
                f"WARNING: [DI-4 assertion density] Only {multi_assert}/{total_fixable} "
                f"fixable layers ({pct:.0f}%) have 2+ assertions. "
                f"Minimum is 40%. Add composite or multi-field assertions."
            )

    return issues


# ---------------------------------------------------------------------------
# Check 12: user_tool_diversity (DI-5)
# ---------------------------------------------------------------------------


def _check_user_tool_diversity(recipe_book: RecipeBook, env: Environment) -> list[str]:
    """DI-5: Count distinct user tools in fault atoms."""
    issues = []
    user_tool_counts: dict[str, int] = {}  # tool_name -> number of layers using it
    total_layers_with_user_action = 0

    for flc, group, layer in _all_layers(recipe_book):
        if layer.unfixable:
            continue
        user_actions = layer.get_user_actions()
        if user_actions:
            total_layers_with_user_action += 1
            for action in user_actions:
                user_tool_counts[action.tool_name] = user_tool_counts.get(action.tool_name, 0) + 1

    distinct_count = len(user_tool_counts)

    if distinct_count < 3:
        issues.append(
            f"WARNING: [DI-5 user tool diversity] Only {distinct_count} distinct "
            f"user WRITE tools in fault atoms. Minimum is 3. "
            f"Design distinct user tools per fault domain."
        )

    # Check if >50% of layers share one tool
    if total_layers_with_user_action > 0:
        for tool_name, count in user_tool_counts.items():
            pct = count / total_layers_with_user_action * 100
            if pct > 50:
                issues.append(
                    f"WARNING: [DI-5 user tool diversity] User tool '{tool_name}' "
                    f"appears in {count}/{total_layers_with_user_action} layers "
                    f"({pct:.0f}%). >50% sharing one tool is banned."
                )

    return issues


# ---------------------------------------------------------------------------
# Check 13: action_density (DI-6)
# ---------------------------------------------------------------------------


def _check_action_density(recipe_book: RecipeBook) -> list[str]:
    """DI-6: Median fault count * avg atoms/layer must be ≥6.

    Also checks for missing per-tier diagnostic atoms, which are the
    primary lever for increasing action density in Archetypes A and B.
    """
    issues = []

    for flc in recipe_book.fault_layer_configs:
        # Skip transfer/unfixable configs (they have max_faults=1)
        if flc.max_faults <= 1:
            continue

        num_groups = len(flc.groups)
        if num_groups == 0:
            continue

        # Count total atoms and diagnostic atoms across all fixable layers
        total_atoms = 0
        total_fixable_layers = 0
        total_diagnostic_atoms = 0
        tiers_with_diagnostics: set[int] = set()
        tiers_used: set[int] = set()
        for group in flc.groups:
            for layer in group.layers:
                if not layer.unfixable:
                    total_fixable_layers += 1
                    tiers_used.add(layer.gate_tier)
                    layer_atoms = len(layer.atoms) if layer.atoms else (
                        len(layer.get_actions()) + len(layer.get_user_actions())
                    )
                    total_atoms += layer_atoms
                    for atom in layer.atoms:
                        if atom.step_type == "diagnostic":
                            total_diagnostic_atoms += 1
                            tiers_with_diagnostics.add(layer.gate_tier)

        if total_fixable_layers == 0:
            continue

        avg_atoms = total_atoms / total_fixable_layers
        # Median faults ≈ min(max_faults, num_groups) / 2 rounded up
        effective_max = min(flc.max_faults, num_groups)
        median_faults = (effective_max + 1) // 2
        estimated_median_actions = median_faults * avg_atoms

        if estimated_median_actions < 6:
            fix_hint = "Increase groups or atoms/layer."
            if total_diagnostic_atoms == 0 and len(tiers_used) >= 2:
                fix_hint = (
                    "Add per-tier diagnostic atoms — each tier gets a "
                    "signature READ tool as a phase-0 diagnostic atom on "
                    "every layer at that tier. This is the primary lever "
                    "for increasing action density."
                )
            issues.append(
                f"WARNING: [DI-6 action density] Config '{flc.name}': "
                f"{num_groups} groups, ~{median_faults} median faults, "
                f"{avg_atoms:.1f} avg atoms/layer → ~{estimated_median_actions:.0f} "
                f"median actions. Minimum is 6. {fix_hint}"
            )

        # Separate check: flag configs with 0 diagnostic atoms and 5+ groups
        if total_diagnostic_atoms == 0 and num_groups >= 5:
            issues.append(
                f"WARNING: [DI-6 no diagnostics] Config '{flc.name}': "
                f"{num_groups} groups but 0 diagnostic atoms. For domains "
                f"with 5+ groups, add per-tier diagnostic atoms (one "
                f"READ tool per tier as phase-0 on every layer at that "
                f"tier) to achieve action density targets."
            )

    return issues


# ---------------------------------------------------------------------------
# Check 14a: gate_tier_consistency
# ---------------------------------------------------------------------------


def _check_gate_tier_consistency(recipe_book: RecipeBook) -> list[str]:
    """If any layer has gate_tier > 0, verify at least one layer in a different
    group has a lower tier. Otherwise the gate serves no purpose."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        # Collect (group_name, layer_name, gate_tier) tuples
        layer_tiers: list[tuple[str, str, int]] = []
        for group in flc.groups:
            for layer in group.layers:
                layer_tiers.append((group.name, layer.name, layer.gate_tier))

        # Find layers with gate_tier > 0
        gated_layers = [(gn, ln, gt) for gn, ln, gt in layer_tiers if gt > 0]
        if not gated_layers:
            continue

        # Check that some lower-tier layer exists in a different group
        for gated_group, gated_name, gated_tier in gated_layers:
            has_lower_tier_in_other_group = any(
                gt < gated_tier and gn != gated_group
                for gn, _, gt in layer_tiers
            )
            if not has_lower_tier_in_other_group:
                issues.append(
                    f"ERROR: [{gated_name}] has gate_tier={gated_tier} but no "
                    f"layer in a different group has a lower tier. The gate "
                    f"serves no purpose — remove gate_tier or add a lower-tier "
                    f"dependency in another group."
                )
    return issues


# ---------------------------------------------------------------------------
# Check 14b: phase_monotonicity
# ---------------------------------------------------------------------------


def _check_phase_monotonicity(recipe_book: RecipeBook) -> list[str]:
    """Within a layer's atoms list, phase values should be non-decreasing.
    Backward phases are likely author error."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if len(layer.atoms) < 2:
                    continue
                for i in range(1, len(layer.atoms)):
                    if layer.atoms[i].phase < layer.atoms[i - 1].phase:
                        issues.append(
                            f"WARNING: [{layer.name}] atom {i} has phase "
                            f"{layer.atoms[i].phase} < atom {i-1} phase "
                            f"{layer.atoms[i-1].phase}. Phases within a layer "
                            f"should be non-decreasing."
                        )
    return issues


# ---------------------------------------------------------------------------
# Check 14c: step_type_valid
# ---------------------------------------------------------------------------


_VALID_STEP_TYPES = {"fix", "diagnostic", "confirm"}


def _check_step_type_valid(recipe_book: RecipeBook) -> list[str]:
    """step_type must be one of 'fix', 'diagnostic', 'confirm'."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                for i, atom in enumerate(layer.atoms):
                    if atom.step_type not in _VALID_STEP_TYPES:
                        issues.append(
                            f"ERROR: [{layer.name}] atom {i} has invalid "
                            f"step_type '{atom.step_type}'. Must be one of "
                            f"{sorted(_VALID_STEP_TYPES)}."
                        )
    return issues


# ---------------------------------------------------------------------------
# Check 14d: diagnostic_is_read
# ---------------------------------------------------------------------------


def _check_diagnostic_is_read(
    env: Environment,
    recipe_book: RecipeBook,
) -> list[str]:
    """If step_type='diagnostic', verify the action's tool is a READ tool.
    Diagnostics shouldn't change state."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                for i, atom in enumerate(layer.atoms):
                    if atom.step_type != "diagnostic":
                        continue
                    toolkit = _get_toolkit_for_requestor(env, atom.fix.requestor)
                    if toolkit is None:
                        continue
                    if hasattr(toolkit, atom.fix.tool_name):
                        tool_method = toolkit.tools.get(atom.fix.tool_name)
                        if tool_method is not None:
                            tt = getattr(tool_method, TOOL_TYPE_ATTR, None)
                            if tt is not None and tt != ToolType.READ:
                                issues.append(
                                    f"WARNING: [{layer.name}] atom {i} has "
                                    f"step_type='diagnostic' but tool "
                                    f"'{atom.fix.tool_name}' is {tt.name}, "
                                    f"not READ. Diagnostics should not "
                                    f"change state."
                                )
    return issues


# ---------------------------------------------------------------------------
# Check 15: dedup collision across phases/tiers
# ---------------------------------------------------------------------------


def _check_dedup_collision(recipe_book: RecipeBook) -> list[str]:
    """Flag atoms at different phases or in layers at different gate_tiers that
    produce identical (tool_name, requestor, args_template) tuples.

    _dedup_actions collapses these to a single action, silently destroying
    check-fix-check patterns (Archetype B) or cross-tier diagnostic repetitions.
    The generated task will expect only ONE call, but the archetype requires TWO.
    """
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if len(layer.atoms) < 2:
                    continue
                # Track (tool_name, requestor, frozen_args) → list of (phase, atom_idx)
                seen: dict[tuple, list[tuple[int, int]]] = {}
                for i, atom in enumerate(layer.atoms):
                    key = (
                        atom.fix.tool_name,
                        atom.fix.requestor,
                        tuple(sorted(atom.fix.args.items())),
                    )
                    seen.setdefault(key, []).append((atom.phase, i))
                for key, occurrences in seen.items():
                    if len(occurrences) < 2:
                        continue
                    phases = [p for p, _ in occurrences]
                    if len(set(phases)) > 1:
                        # Different phases → dedup will collapse them
                        tool_name = key[0]
                        idxs = [idx for _, idx in occurrences]
                        issues.append(
                            f"ERROR: [{layer.name}] atoms {idxs} produce "
                            f"identical action '{tool_name}' at different "
                            f"phases {phases}. _dedup_actions will collapse "
                            f"them to one action, destroying the "
                            f"check-fix-check pattern. Use different args "
                            f"or tool names for repeated calls."
                        )

        # Also check across layers at different gate_tiers within same config
        # (cross-group composition can produce duplicate actions at different tiers)
        all_tier_actions: dict[tuple, list[tuple[str, int]]] = {}
        for group in flc.groups:
            for layer in group.layers:
                for atom in layer.atoms:
                    key = (
                        atom.fix.tool_name,
                        atom.fix.requestor,
                        tuple(sorted(atom.fix.args.items())),
                    )
                    all_tier_actions.setdefault(key, []).append(
                        (layer.name, layer.gate_tier)
                    )
        for key, occurrences in all_tier_actions.items():
            # Only flag cross-group (different layers) at different tiers
            unique_layers = {name for name, _ in occurrences}
            unique_tiers = {tier for _, tier in occurrences}
            if len(unique_layers) >= 2 and len(unique_tiers) >= 2:
                tool_name = key[0]
                details = ", ".join(
                    f"{name} (tier {tier})" for name, tier in occurrences
                )
                issues.append(
                    f"WARNING: [{flc.name}] action '{tool_name}' appears "
                    f"in layers at different gate_tiers: {details}. "
                    f"If these layers compose together, _dedup_actions "
                    f"will collapse them to one action. Use different "
                    f"args or tool names if the call must happen at each tier."
                )

    return issues


# ---------------------------------------------------------------------------
# Check 16: diagnostic atom with init calls
# ---------------------------------------------------------------------------


def _check_diagnostic_has_no_init(recipe_book: RecipeBook) -> list[str]:
    """Diagnostic atoms gather information — they should not have init calls
    that modify state before reading."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                for i, atom in enumerate(layer.atoms):
                    if atom.step_type == "diagnostic" and atom.init is not None:
                        issues.append(
                            f"ERROR: [{layer.name}] atom {i} has "
                            f"step_type='diagnostic' but also has init calls. "
                            f"Diagnostics should read state, not break it. "
                            f"Either remove the init or change step_type to 'fix'."
                        )
    return issues


# ---------------------------------------------------------------------------
# Check 17: confirm atom with init calls
# ---------------------------------------------------------------------------


def _check_confirm_has_no_init(recipe_book: RecipeBook) -> list[str]:
    """Confirm atoms acknowledge resolution — they should not inject faults."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                for i, atom in enumerate(layer.atoms):
                    if atom.step_type == "confirm" and atom.init is not None:
                        issues.append(
                            f"WARNING: [{layer.name}] atom {i} has "
                            f"step_type='confirm' but also has init calls. "
                            f"Confirmation atoms acknowledge resolution; "
                            f"they should not inject new faults."
                        )
    return issues


# ---------------------------------------------------------------------------
# Check 18: legacy + atoms collision
# ---------------------------------------------------------------------------


def _check_legacy_atoms_collision(recipe_book: RecipeBook) -> list[str]:
    """Warn if a layer has both atoms AND legacy flat lists — the legacy lists
    will be silently ignored."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if not layer.atoms:
                    continue
                legacy_fields = []
                if layer.actions:
                    legacy_fields.append("actions")
                if layer.user_actions:
                    legacy_fields.append("user_actions")
                if layer.init_calls:
                    legacy_fields.append("init_calls")
                # Note: assertions alongside atoms are intentionally supported
                # (get_assertions merges atom checks + layer-level assertions).
                # Only warn about init_calls, actions, and user_actions which
                # ARE silently ignored when atoms are set.
                if legacy_fields:
                    issues.append(
                        f"WARNING: [{layer.name}] has atoms AND legacy "
                        f"flat lists ({', '.join(legacy_fields)}). The atoms "
                        f"interface takes precedence — legacy lists will be "
                        f"silently ignored. Remove the legacy lists or "
                        f"migrate them into atoms."
                    )
    return issues


# ---------------------------------------------------------------------------
# Check 19: all-diagnostic layer
# ---------------------------------------------------------------------------


def _check_all_diagnostic_layer(recipe_book: RecipeBook) -> list[str]:
    """Warn if all atoms in a fixable layer are non-fix (diagnostic/confirm).
    Such a layer contributes no state changes or assertions."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if layer.unfixable or len(layer.atoms) == 0:
                    continue
                fix_count = sum(
                    1 for atom in layer.atoms if atom.step_type == "fix"
                )
                if fix_count == 0:
                    step_types = [a.step_type for a in layer.atoms]
                    issues.append(
                        f"WARNING: [{layer.name}] has {len(layer.atoms)} "
                        f"atom(s) but none with step_type='fix' "
                        f"(types: {step_types}). This layer contributes no "
                        f"state-changing actions or meaningful assertions. "
                        f"Add a fix atom or reconsider the layer design."
                    )
    return issues


# ---------------------------------------------------------------------------
# Check 20: confirm without fix in same layer
# ---------------------------------------------------------------------------


def _check_confirm_without_fix(recipe_book: RecipeBook) -> list[str]:
    """Warn if a layer has confirm atoms but no fix atoms — nothing to confirm."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if layer.unfixable or len(layer.atoms) == 0:
                    continue
                has_confirm = any(
                    a.step_type == "confirm" for a in layer.atoms
                )
                has_fix = any(a.step_type == "fix" for a in layer.atoms)
                if has_confirm and not has_fix:
                    issues.append(
                        f"WARNING: [{layer.name}] has confirm atom(s) but "
                        f"no fix atom(s). Confirmation acknowledges a "
                        f"resolution, but there's nothing to resolve in "
                        f"this layer."
                    )
    return issues


# ---------------------------------------------------------------------------
# Check 21: unfixable with gate_tier > 0
# ---------------------------------------------------------------------------


def _check_unfixable_gate_tier(recipe_book: RecipeBook) -> list[str]:
    """Warn if an unfixable layer has gate_tier > 0 — gate_tier is ignored
    for unfixable combos (they collapse to transfer_to_human)."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if layer.unfixable and layer.gate_tier > 0:
                    issues.append(
                        f"WARNING: [{layer.name}] is unfixable with "
                        f"gate_tier={layer.gate_tier}. Unfixable combos "
                        f"collapse to transfer_to_human — gate_tier is "
                        f"ignored. Set gate_tier=0 or remove it."
                    )
    return issues


# ---------------------------------------------------------------------------
# Check 22: phase gaps within a layer
# ---------------------------------------------------------------------------


def _check_phase_gaps(recipe_book: RecipeBook) -> list[str]:
    """Warn if a layer's atom phases have gaps (e.g., {0, 2} missing 1),
    which may indicate a missing atom."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if len(layer.atoms) < 2:
                    continue
                phases = sorted(set(a.phase for a in layer.atoms))
                if len(phases) < 2:
                    continue
                expected = list(range(phases[0], phases[-1] + 1))
                missing = set(expected) - set(phases)
                if missing:
                    issues.append(
                        f"WARNING: [{layer.name}] has phase gap(s): "
                        f"phases used are {phases}, missing {sorted(missing)}. "
                        f"This may indicate a missing atom."
                    )
    return issues


# ---------------------------------------------------------------------------
# Check 23: duplicate (phase, requestor) in same layer
# ---------------------------------------------------------------------------


def _check_duplicate_phase_requestor(recipe_book: RecipeBook) -> list[str]:
    """Warn if multiple fix atoms in the same layer share (phase, requestor).
    Their relative order is determined only by list position, which is fragile."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if len(layer.atoms) < 2:
                    continue
                # Only check fix atoms (diagnostics at same phase are less suspicious)
                fix_atoms = [
                    (i, a) for i, a in enumerate(layer.atoms)
                    if a.step_type == "fix"
                ]
                seen: dict[tuple, list[int]] = {}
                for i, atom in fix_atoms:
                    key = (atom.phase, atom.fix.requestor)
                    seen.setdefault(key, []).append(i)
                for key, idxs in seen.items():
                    if len(idxs) >= 2:
                        phase, requestor = key
                        issues.append(
                            f"WARNING: [{layer.name}] fix atoms {idxs} "
                            f"share (phase={phase}, requestor='{requestor}'). "
                            f"Their ordering depends on list position only. "
                            f"Assign different phases to make ordering explicit."
                        )
    return issues


# ---------------------------------------------------------------------------
# Check 24: gate_tier gaps across layers in a config
# ---------------------------------------------------------------------------


def _check_gate_tier_gaps(recipe_book: RecipeBook) -> list[str]:
    """Warn if gate_tier values across all layers in a FaultLayerConfig
    have gaps (e.g., tiers 0 and 3 with no 1 or 2)."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        tiers = set()
        for group in flc.groups:
            for layer in group.layers:
                tiers.add(layer.gate_tier)
        if len(tiers) < 2:
            continue
        sorted_tiers = sorted(tiers)
        expected = set(range(sorted_tiers[0], sorted_tiers[-1] + 1))
        missing = expected - tiers
        if missing:
            issues.append(
                f"WARNING: [{flc.name}] has gate_tier gap(s): tiers used "
                f"are {sorted_tiers}, missing {sorted(missing)}. This may "
                f"indicate missing layers at intermediate tiers."
            )
    return issues


# ---------------------------------------------------------------------------
# Check 25: diagnostic-only layer at non-zero gate_tier
# ---------------------------------------------------------------------------


def _check_diagnostic_only_at_nonzero_tier(recipe_book: RecipeBook) -> list[str]:
    """Warn if a layer at gate_tier > 0 has only diagnostic atoms and no fix
    atom at the same or higher tier exists in other layers in the same group.
    This means the gated diagnostic is a dead end — it reads info but nothing
    acts on it."""
    issues = []
    for flc in recipe_book.fault_layer_configs:
        for group in flc.groups:
            for layer in group.layers:
                if layer.gate_tier == 0 or not layer.atoms:
                    continue
                has_fix = any(a.step_type == "fix" for a in layer.atoms)
                if has_fix:
                    continue
                # All atoms are non-fix at tier > 0. Check if ANY layer
                # in ANY group at >= this tier has fix atoms.
                has_fix_at_or_above = False
                for other_group in flc.groups:
                    for other_layer in other_group.layers:
                        if other_layer is layer:
                            continue
                        if other_layer.gate_tier >= layer.gate_tier:
                            if any(a.step_type == "fix" for a in other_layer.atoms):
                                has_fix_at_or_above = True
                                break
                    if has_fix_at_or_above:
                        break
                if not has_fix_at_or_above:
                    issues.append(
                        f"WARNING: [{layer.name}] at gate_tier="
                        f"{layer.gate_tier} has only diagnostic/confirm "
                        f"atoms and no other layer at tier >= "
                        f"{layer.gate_tier} has fix atoms. This gated "
                        f"diagnostic is a dead end — it reads info but "
                        f"nothing acts on it."
                    )
    return issues


# ---------------------------------------------------------------------------
# Check 26: minimum gate_tier depth
# ---------------------------------------------------------------------------


def _check_min_gate_tier_depth(recipe_book: RecipeBook) -> list[str]:
    """Warn when max(gate_tier) < 2 for configs with 5+ groups.

    Domains with many groups but only 1-2 tiers produce flat task structures
    with low dependency chaining. For Archetypes A and B, 2-3 tiers of gated
    dependency are needed to achieve action density targets (DI-6) and ordering
    constraints (DI-3).
    """
    issues = []
    for flc in recipe_book.fault_layer_configs:
        if flc.max_faults <= 1:
            continue
        num_groups = len(flc.groups)
        if num_groups < 5:
            continue
        max_tier = 0
        for group in flc.groups:
            for layer in group.layers:
                max_tier = max(max_tier, layer.gate_tier)
        if max_tier < 2:
            issues.append(
                f"WARNING: [DI-3 tier depth] Config '{flc.name}': "
                f"{num_groups} groups but max gate_tier is only {max_tier}. "
                f"Domains with 5+ groups should use ≥3 tiers (0, 1, 2) to "
                f"create dependency chains. Add gate_tier=2 layers for "
                f"service/network-level faults and per-tier diagnostic atoms."
            )
    return issues


# ---------------------------------------------------------------------------
# Check 27: per-tier diagnostic consistency
# ---------------------------------------------------------------------------


def _check_per_tier_diagnostic_consistency(recipe_book: RecipeBook) -> list[str]:
    """Warn when some fixable layers at a tier have diagnostic atoms but
    others at the same tier don't.

    Per-tier diagnostics should be applied uniformly — if any layer at tier N
    has a phase-0 diagnostic atom, ALL fixable layers at tier N should have one.
    Incomplete coverage means some task compositions get the diagnostic and
    others don't, creating inconsistent action density.
    """
    issues = []
    for flc in recipe_book.fault_layer_configs:
        if flc.max_faults <= 1:
            continue
        # Map tier → (layers_with_diag, layers_without_diag)
        tier_diag: dict[int, tuple[list[str], list[str]]] = {}
        for group in flc.groups:
            for layer in group.layers:
                if layer.unfixable:
                    continue
                has_diag = any(
                    a.step_type == "diagnostic" for a in layer.atoms
                )
                tier = layer.gate_tier
                if tier not in tier_diag:
                    tier_diag[tier] = ([], [])
                if has_diag:
                    tier_diag[tier][0].append(layer.name)
                else:
                    tier_diag[tier][1].append(layer.name)
        for tier, (with_diag, without_diag) in sorted(tier_diag.items()):
            if with_diag and without_diag:
                issues.append(
                    f"WARNING: [per-tier diagnostic] Tier {tier} has "
                    f"inconsistent diagnostic coverage. Layers WITH "
                    f"diagnostic atoms: {with_diag}. Layers WITHOUT: "
                    f"{without_diag}. Add per-tier diagnostic atoms to "
                    f"all fixable layers at this tier for consistent "
                    f"action density."
                )
    return issues


# ---------------------------------------------------------------------------
# Check 14: cross-layer confirmation consistency
# ---------------------------------------------------------------------------


def _check_cross_layer_confirmation_consistency(
    recipe_book: RecipeBook,
) -> list[str]:
    """Flag when different fault layers share an agent fix tool but expect
    different user confirmation tools.

    Example: ``wrong_shipping_method`` and ``wrong_shipping_cost`` both use
    ``adjust_shipping_cost`` as an agent fix, but the former expects
    ``confirm_shipping_update`` while the latter expects
    ``confirm_billing_correction``.  The policy can only direct the agent to
    ONE of those confirmation tools after calling ``adjust_shipping_cost``, so
    whichever layer the agent encounters, it will instruct the wrong
    confirmation for the other layer.

    The check builds a map of agent-fix-tool → set of user-confirmation-tools
    across all layers in the same FaultLayerConfig.  If a single agent tool
    maps to multiple distinct user confirmations, that is an ERROR because
    the policy cannot disambiguate.
    """
    issues: list[str] = []

    for flc in recipe_book.fault_layer_configs:
        # Map: agent_fix_tool → { (user_confirm_tool, layer_name), ... }
        # Only tracks CROSS-LAYER pairings (within a single layer, multiple
        # user tools alongside one agent tool is a valid multi-step sequence).
        tool_to_confirmations: dict[str, set[tuple[str, str]]] = {}

        for group in flc.groups:
            for layer in group.layers:
                if layer.unfixable or not layer.atoms:
                    continue

                # Collect agent-side fix tools in this layer
                agent_tools: set[str] = set()
                user_confirms: set[str] = set()
                for atom in layer.atoms:
                    if atom.fix is None:
                        continue
                    if atom.fix.requestor != "user":
                        agent_tools.add(atom.fix.tool_name)
                    else:
                        user_confirms.add(atom.fix.tool_name)

                # For every agent fix tool in this layer, record which user
                # confirmations are expected alongside it.
                # We pair each agent tool with the "primary" user confirmation
                # for this layer — the LAST user tool (typically the
                # confirmation step after agent fixes).  If there's only one
                # user tool, that's unambiguous.
                if not user_confirms:
                    continue
                # Use all user confirms for cross-layer comparison
                for atool in agent_tools:
                    if atool not in tool_to_confirmations:
                        tool_to_confirmations[atool] = set()
                    for uconf in user_confirms:
                        tool_to_confirmations[atool].add((uconf, layer.name))

        # Check for agent tools that map to multiple distinct user
        # confirmations across DIFFERENT layers
        for agent_tool, confirm_set in tool_to_confirmations.items():
            # Group by layer to check cross-layer ambiguity
            layers_involved = {lname for _, lname in confirm_set}
            if len(layers_involved) < 2:
                # All pairings come from the same layer — multi-step
                # sequence within one layer, not a cross-layer conflict
                continue

            distinct_confirms = {uconf for uconf, _ in confirm_set}
            if len(distinct_confirms) > 1:
                details = ", ".join(
                    f"{uconf} (layer: {lname})"
                    for uconf, lname in sorted(confirm_set)
                )
                issues.append(
                    f"WARNING: [cross-layer confirmation] Config '{flc.name}': "
                    f"agent tool '{agent_tool}' appears in multiple layers that "
                    f"expect DIFFERENT user confirmations: {details}. "
                    f"The policy likely directs the agent to only ONE of these "
                    f"confirmation tools after calling '{agent_tool}', causing "
                    f"the other layer's confirmation to be missed. "
                    f"Fix: ensure the policy unambiguously routes to the correct "
                    f"confirmation, or use different agent tools per layer."
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
    """Run structural checks on authored definitions before task generation.

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

    # Difficulty invariant checks (DI-4, DI-5, DI-6)
    issues.extend(_check_assertion_density(recipe_book))
    issues.extend(_check_user_tool_diversity(recipe_book, env))
    issues.extend(_check_action_density(recipe_book))

    # Check 14: cross-layer confirmation consistency
    issues.extend(_check_cross_layer_confirmation_consistency(recipe_book))

    # Check 14a-d: archetype primitive checks
    issues.extend(_check_gate_tier_consistency(recipe_book))
    issues.extend(_check_phase_monotonicity(recipe_book))
    issues.extend(_check_step_type_valid(recipe_book))
    issues.extend(_check_diagnostic_is_read(env, recipe_book))

    # Checks 15-25: extended archetype primitive checks
    issues.extend(_check_dedup_collision(recipe_book))
    issues.extend(_check_diagnostic_has_no_init(recipe_book))
    issues.extend(_check_confirm_has_no_init(recipe_book))
    issues.extend(_check_legacy_atoms_collision(recipe_book))
    issues.extend(_check_all_diagnostic_layer(recipe_book))
    issues.extend(_check_confirm_without_fix(recipe_book))
    issues.extend(_check_unfixable_gate_tier(recipe_book))
    issues.extend(_check_phase_gaps(recipe_book))
    issues.extend(_check_duplicate_phase_requestor(recipe_book))
    issues.extend(_check_gate_tier_gaps(recipe_book))
    issues.extend(_check_diagnostic_only_at_nonzero_tier(recipe_book))

    # Checks 26-27: tier depth and diagnostic consistency
    issues.extend(_check_min_gate_tier_depth(recipe_book))
    issues.extend(_check_per_tier_diagnostic_consistency(recipe_book))

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
                if layer.gate_tier != 0:
                    lines.append(f"      gate_tier: {layer.gate_tier}")
                if atoms:
                    atom_details = []
                    for ai, atom in enumerate(atoms):
                        parts = [f"phase={atom.phase}"]
                        if atom.step_type != "fix":
                            parts.append(f"step_type='{atom.step_type}'")
                        parts.append(f"tool='{atom.fix.tool_name}'")
                        parts.append(f"requestor='{atom.fix.requestor}'")
                        if atom.init:
                            inits = atom.init if isinstance(atom.init, list) else [atom.init]
                            parts.append(f"init=[{','.join(ic.func_name for ic in inits)}]")
                        if atom.check:
                            parts.append(f"check='{atom.check.func_name}'")
                        atom_details.append(f"        atom[{ai}]: {', '.join(parts)}")
                    lines.extend(atom_details)
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

## Your 19 Checks

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

11. **DI-1 Diagnostic Disambiguation**: Count fixable layers that have a unique
    fix tool (no other layer uses that same tool). If >70% have unique tools
    (1:1 fault→tool mapping), report ERROR. Also check: are there any
    information-hiding READ tools or diagnostic tools that return computed
    results? If the agent can always pattern-match fault→tool without reasoning,
    report ERROR.

12. **DI-2 Value Computation**: For each ActionSpec on fixable layers, check if
    ALL args are either template pass-throughs (e.g. "{{entity_id}}") or
    hard-coded literals. If ZERO fix actions require the agent to compute,
    derive, or look up a value, report ERROR. Check whether the policy describes
    any computation the agent must perform.

13. **DI-3 Ordering Dependency**: Check for ordering patterns in the domain.
    Look for: (a) information-hiding READ tools that gate downstream faults,
    (b) policy instructions saying "do X before Y", (c) user action
    precondition gates. If ALL faults are completely independent with no ordering
    constraints, report ERROR.

14. **User Action Arg / Assertion Mismatch (compare_args=[] blind spot)**: For
    every FaultAtom where the fix ActionSpec has requestor="user" AND
    compare_args=[] (name-only match), examine the corresponding check
    AssertionSpec. If the assertion checks a specific argument value (e.g.,
    payment_id="{{payment_method_id}}"), then the user sim MUST provide
    that exact value for the ENV_ASSERTION to pass — even though the ACTION
    evaluator doesn't check it. Now look at the known_info_fragment: does it
    contain the template variable the assertion uses? If the user sim has no
    way to know the correct value (it's not in known_info, ticket, or
    task_instructions), the user will guess wrong (e.g., passing an order_id
    where a payment_id is expected). Report ERROR for each such mismatch.
    The fix is to either: (a) include the value in known_info_fragment, or
    (b) make the user tool ignore the arg and use a deterministic value
    (like a zero-arg tool).

15. **User Tool Input Validation**: For each user WRITE tool that takes an ID
    parameter (e.g., payment_id, order_id), check whether the tool validates
    that the ID exists in the user's DB before accepting it. If the tool
    blindly stores whatever string the user passes (e.g.,
    ``self.db.some_dict[payment_id] = True`` without checking payment_id is
    valid), it creates a silent failure mode: the tool returns success but
    the assertion checks a different key. Report WARNING for user tools that
    accept arbitrary ID strings without validation, especially when paired
    with assertions that check specific ID keys.

16. **Policy → Confirmation Routing Ambiguity**: For each agent fix tool that
    appears in a fault layer alongside a user confirmation atom, trace the
    policy path. Find every section in the policy that mentions the agent
    tool. Does EACH section direct the agent to the SAME user confirmation
    tool that the fault layer expects? If the agent tool appears in multiple
    policy sections, each followed by a different "instruct the customer to
    use their X tool" instruction, the agent will follow whichever section
    it reads first — which may not match what the fault layer expects.
    Example: ``adjust_shipping_cost`` appears in both "Shipping Configuration"
    (→ confirm_shipping_update) and "Billing Computation Rules"
    (→ confirm_billing_correction). A layer expecting confirm_billing_correction
    will fail when the agent follows the Shipping section instead.
    Report ERROR if a fault layer expects a user confirmation tool but the
    policy routes the agent to a DIFFERENT user confirmation tool after the
    corresponding agent action. Report WARNING if the agent tool appears in
    multiple policy sections with different confirmation instructions (even if
    one section matches), because the agent may follow the wrong section.

17. **Gate Tier Semantic Justification**: For every layer with gate_tier > 0,
    verify that the DOMAIN LOGIC justifies the gating. The tier-0 layer's
    resolution should genuinely unlock visibility or access to the tier-1
    layer's fault. Examples of valid gating: account is locked (tier 0) and
    booking details are wrong (tier 1, invisible until account unlocked);
    device is offline (tier 0) and app settings need sync (tier 1, impossible
    while offline). Report WARNING if the gating seems artificial — if both
    faults are independently observable and fixable, gate_tier adds false
    complexity without domain justification. Also check: does the policy
    describe ANY dependency between the gated layers? If not, the agent will
    have no reason to resolve tier-0 before tier-1.

18. **Diagnostic Atom Purpose Validation**: For every atom with
    step_type='diagnostic', verify that the diagnostic serves a genuine
    information-gathering purpose in the resolution workflow. A valid diagnostic
    reads state that the agent (or user) needs to decide what to fix or to
    verify a condition. Report WARNING if:
    (a) The diagnostic reads information that is already fully provided in
        known_info_fragment (the agent/user already knows it, no need to look
        it up).
    (b) The diagnostic output is never used by any subsequent atom — no
        downstream fix or confirm atom depends on what the diagnostic reveals.
    (c) The diagnostic is a trivial status check at the end of a sequence
        (e.g., "check_status" after all fixes) that duplicates what the
        assertion already verifies. If assertions already validate the
        end state, a trailing diagnostic adds an action requirement without
        adding reasoning complexity.

19. **Phase Coherence with Domain Workflow**: For layers using phase > 0,
    verify that the phase assignments reflect a real workflow dependency.
    Phase-0 actions should genuinely need to complete before phase-1 actions
    can succeed or make sense. Report WARNING if:
    (a) Two atoms at different phases are actually independent — swapping their
        execution order would produce identical results. Phase is being used
        as cosmetic ordering rather than encoding a real dependency.
    (b) A user atom at a later phase needs information that the agent has not
        yet communicated. For example, if a user fix at phase 1 requires
        knowing a value that the agent computes at phase 0, but the
        user_task_instructions and known_info_fragment don't mention how the
        user learns this value, the user simulator will fail.
    (c) An agent atom at phase > 0 could equally well run at phase 0 — there
        is no earlier action in the same layer whose side effects this atom
        depends on.

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
