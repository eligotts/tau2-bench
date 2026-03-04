"""
Verify: tau2-specific verification functions.

These run ON TOP OF the framework verification, adding tau2-specific
checks for tool exclusivity, user confirmations, policy coverage,
and anti-patterns.
"""

from __future__ import annotations

from design.framework.verify import Severity, VerificationIssue, VerificationResult
from design.framework.world import WorldSchema
from design.legacy.tau2.faults import FaultDeclaration, FaultGroup, FaultSpace
from design.legacy.tau2.policy import PolicySpec
from design.legacy.tau2.tools import ToolAccess, ToolSuiteSpec


def verify_fault_space(
    faults: FaultSpace,
    schema: WorldSchema,
    tools: ToolSuiteSpec,
) -> VerificationResult:
    """Verify tau2-specific fault space constraints.

    Runs on top of core verify_perturbation_space, adding:
    - fix_tool exists in tool suite
    - No two groups share a fix_tool (tool exclusivity)
    - User confirmations reference existing user tools
    - Diagnostic steps reference existing READ tools
    - resolution_instruction covers all categories
    """
    issues = []

    tool_names = {t.name for t in tools.agent_tools + tools.user_tools}

    # Fix tools exist
    for group in faults.groups:
        for p in group.perturbations:
            if isinstance(p, FaultDeclaration) and p.fix_tool:
                if p.fix_tool not in tool_names:
                    issues.append(VerificationIssue(
                        Severity.ERROR, "fix_tool_exists",
                        f"Fault '{p.name}': fix_tool '{p.fix_tool}' "
                        f"not in tools",
                    ))

    # Tool exclusivity across groups
    tool_to_group: dict[str, str] = {}
    for group in faults.groups:
        for p in group.perturbations:
            if isinstance(p, FaultDeclaration) and p.fix_tool:
                if p.fix_tool in tool_to_group:
                    other = tool_to_group[p.fix_tool]
                    if other != group.name:
                        issues.append(VerificationIssue(
                            Severity.ERROR, "tool_exclusivity",
                            f"fix_tool '{p.fix_tool}' used by groups "
                            f"'{other}' AND '{group.name}'",
                            fix_hint=(
                                f"Put all faults using '{p.fix_tool}' "
                                f"in one group"
                            ),
                        ))
                tool_to_group[p.fix_tool] = group.name

    # User confirmations reference existing tools
    user_tool_names = {t.name for t in tools.user_tools}
    for group in faults.groups:
        if isinstance(group, FaultGroup) and group.user_confirmation:
            if group.user_confirmation.tool_name not in user_tool_names:
                issues.append(VerificationIssue(
                    Severity.ERROR, "user_confirm_tool_exists",
                    f"Group '{group.name}': user confirmation tool "
                    f"'{group.user_confirmation.tool_name}' not in "
                    f"user tools",
                ))

    # Diagnostics reference READ tools
    agent_read_tools = {
        t.name for t in tools.agent_tools if t.access == ToolAccess.READ
    }
    for group in faults.groups:
        if isinstance(group, FaultGroup):
            for diag in group.diagnostics:
                if diag.tool_name not in agent_read_tools:
                    issues.append(VerificationIssue(
                        Severity.ERROR, "diagnostic_tool_exists",
                        f"Group '{group.name}': diagnostic tool "
                        f"'{diag.tool_name}' not a READ tool",
                    ))

    # Resolution instruction covers all categories
    categories = {g.category for g in faults.groups if g.category}
    if faults.resolution_instruction:
        for cat in categories:
            if cat.lower() not in faults.resolution_instruction.lower():
                issues.append(VerificationIssue(
                    Severity.WARNING, "resolution_coverage",
                    f"Category '{cat}' not mentioned in "
                    f"resolution_instruction",
                ))

    # Completion fragments non-empty on fixable layers
    for group in faults.groups:
        for p in group.perturbations:
            if not p.fixed_description:
                issues.append(VerificationIssue(
                    Severity.WARNING, "completion_fragment",
                    f"Fault '{p.name}' has empty fixed_description "
                    f"(completion fragment)",
                ))

    # Group count target
    if len(faults.groups) < 4:
        issues.append(VerificationIssue(
            Severity.WARNING, "group_count",
            f"Only {len(faults.groups)} fault groups — target 8-10 "
            f"for diversity",
        ))

    return VerificationResult(
        step="fault_space_tau2",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )


def verify_policy(
    policy: PolicySpec,
    tools: ToolSuiteSpec,
    faults: FaultSpace,
) -> VerificationResult:
    """Verify policy: tool references, fault coverage, anti-patterns."""
    issues = []
    tool_names = {t.name for t in tools.agent_tools + tools.user_tools}

    for rule in policy.structured_rules:
        for tool in rule.tools_referenced:
            if tool not in tool_names:
                issues.append(VerificationIssue(
                    Severity.ERROR, "rule_tool_exists",
                    f"Rule references tool '{tool}' which doesn't exist",
                ))

    # Every fault group should have a resolution path in policy
    covered_groups: set[str] = set()
    for rule in policy.structured_rules:
        for group in faults.groups:
            for p in group.perturbations:
                if (
                    isinstance(p, FaultDeclaration)
                    and p.fix_tool in rule.tools_referenced
                ):
                    covered_groups.add(group.name)

    for group in faults.groups:
        if group.name not in covered_groups:
            issues.append(VerificationIssue(
                Severity.WARNING, "fault_resolution_coverage",
                f"Fault group '{group.name}' has no resolution path "
                f"in policy",
            ))

    # Check for prescriptive anti-patterns in prose
    if policy.prose:
        prescriptive_phrases = [
            "always call",
            "always use",
            "must always",
            "in every case",
        ]
        for phrase in prescriptive_phrases:
            if phrase.lower() in policy.prose.lower():
                issues.append(VerificationIssue(
                    Severity.WARNING, "prescriptive_antipattern",
                    f"Policy contains prescriptive phrase '{phrase}'. "
                    f"Use reactive language ('when X is wrong, do Y') "
                    f"instead.",
                ))

    return VerificationResult(
        step="policy",
        passed=not any(i.severity == Severity.ERROR for i in issues),
        issues=issues,
    )
