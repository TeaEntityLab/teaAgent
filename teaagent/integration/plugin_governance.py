"""Plugin tool governance aligned with ToolRegistry requirements (WS5-005)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from teaagent.governance.tool_lint import ToolLintIssue, lint_registry
from teaagent.tools import ToolRegistry


@dataclass(frozen=True)
class PluginGovernanceReport:
    tool_names: list[str] = field(default_factory=list)
    issues: list[ToolLintIssue] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(issue.level == 'error' for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.level == 'error')

    def to_dict(self) -> dict[str, Any]:
        return {
            'tool_names': self.tool_names,
            'blocked': self.blocked,
            'error_count': self.error_count,
            'issues': [
                {
                    'tool_name': issue.tool_name,
                    'level': issue.level,
                    'code': issue.code,
                    'message': issue.message,
                }
                for issue in self.issues
            ],
        }


def validate_plugin_tools(
    registry: ToolRegistry,
    *,
    tool_names: list[str] | None = None,
) -> PluginGovernanceReport:
    """Lint plugin-provided tools against schema, annotation, and audit rules."""
    selected = tool_names if tool_names is not None else registry.list_tools()
    issues: list[ToolLintIssue] = []
    for name in sorted(selected):
        if name not in registry.list_tools():
            continue
        tool = registry.get(name)
        if not tool.input_schema or tool.input_schema.get('type') != 'object':
            issues.append(
                ToolLintIssue(
                    name,
                    'error',
                    'missing_input_schema',
                    'plugin tools must declare an object input_schema',
                )
            )
        if not tool.output_schema or tool.output_schema.get('type') != 'object':
            issues.append(
                ToolLintIssue(
                    name,
                    'error',
                    'missing_output_schema',
                    'plugin tools must declare an object output_schema',
                )
            )
        if not tool.description.strip():
            issues.append(
                ToolLintIssue(
                    name,
                    'error',
                    'missing_description',
                    'plugin tools must include a non-empty description',
                )
            )
        if tool.annotations.destructive and tool.annotations.read_only:
            issues.append(
                ToolLintIssue(
                    name,
                    'error',
                    'destructive_read_only',
                    'destructive tools cannot be read_only',
                )
            )
    for issue in lint_registry(registry):
        if issue.tool_name in selected:
            issues.append(issue)
    return PluginGovernanceReport(tool_names=list(selected), issues=issues)
