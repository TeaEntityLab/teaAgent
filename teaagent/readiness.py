from __future__ import annotations

from dataclasses import dataclass

from teaagent.tools import ToolRegistry


@dataclass(frozen=True)
class ReadinessFinding:
    severity: str
    message: str


@dataclass(frozen=True)
class ReadinessReport:
    target: str
    findings: list[ReadinessFinding]

    @property
    def ready(self) -> bool:
        return not any(finding.severity == "error" for finding in self.findings)


def assess_managed_agent_readiness(
    *,
    registry: ToolRegistry,
    has_external_state: bool,
    has_audit_log: bool,
    has_budget_limits: bool,
    has_human_approval: bool,
) -> ReadinessReport:
    findings: list[ReadinessFinding] = []
    tool_metadata = registry.mcp_metadata()
    if not tool_metadata:
        findings.append(ReadinessFinding("error", "At least one registered tool is required."))
    for tool in tool_metadata:
        if not tool.get("description"):
            findings.append(ReadinessFinding("error", f"Tool {tool.get('name')} is missing a description."))
        annotations = tool.get("annotations", {})
        if annotations.get("destructiveHint") and not has_human_approval:
            findings.append(ReadinessFinding("error", f"Destructive tool {tool.get('name')} needs HITL."))
    if not has_external_state:
        findings.append(ReadinessFinding("warning", "Long-lived runs need external state before managed runtime migration."))
    if not has_audit_log:
        findings.append(ReadinessFinding("error", "Audit logging is required."))
    if not has_budget_limits:
        findings.append(ReadinessFinding("error", "Budget limits are required."))
    return ReadinessReport(target="managed-agent", findings=findings)
