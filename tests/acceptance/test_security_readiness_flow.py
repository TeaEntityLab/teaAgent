"""Acceptance: managed agent readiness assessment."""

from __future__ import annotations

from teaagent.readiness import (
    ReadinessFinding,
    ReadinessReport,
    assess_managed_agent_readiness,
)
from teaagent.types import ToolAnnotations, ToolRegistry


def _noop_handler(args: dict) -> dict:
    return {}


class TestReadinessFinding:
    def test_create_finding(self):
        finding = ReadinessFinding(severity='error', message='missing tool')
        assert finding.severity == 'error'
        assert finding.message == 'missing tool'


class TestReadinessReport:
    def test_ready_when_no_errors(self):
        report = ReadinessReport(
            target='test',
            findings=[ReadinessFinding('warning', 'just a warning')],
        )
        assert report.ready is True

    def test_not_ready_when_errors(self):
        report = ReadinessReport(
            target='test',
            findings=[
                ReadinessFinding('warning', 'just a warning'),
                ReadinessFinding('error', 'something is broken'),
            ],
        )
        assert report.ready is False

    def test_empty_findings_is_ready(self):
        report = ReadinessReport(target='test', findings=[])
        assert report.ready is True


class TestAssessManagedAgentReadiness:
    def test_empty_registry_reports_error(self):
        registry = ToolRegistry()
        report = assess_managed_agent_readiness(
            registry=registry,
            has_external_state=True,
            has_audit_log=True,
            has_budget_limits=True,
            has_human_approval=True,
        )
        assert not report.ready
        assert any('tool' in f.message.lower() for f in report.findings)

    def test_registry_with_tool_reports_ready(self):
        registry = ToolRegistry()
        registry.register(
            name='read_tool',
            description='Reads a file',
            handler=_noop_handler,
            input_schema={'type': 'object', 'properties': {}},
            output_schema={'type': 'object'},
            annotations=ToolAnnotations(read_only=True),
        )
        report = assess_managed_agent_readiness(
            registry=registry,
            has_external_state=True,
            has_audit_log=True,
            has_budget_limits=True,
            has_human_approval=True,
        )
        assert report.ready is True

    def test_destructive_tool_without_hitl_reports_error(self):
        registry = ToolRegistry()
        registry.register(
            name='write_tool',
            description='Writes a file',
            handler=_noop_handler,
            input_schema={'type': 'object', 'properties': {}},
            output_schema={'type': 'object'},
            annotations=ToolAnnotations(destructive=True),
        )
        report = assess_managed_agent_readiness(
            registry=registry,
            has_external_state=True,
            has_audit_log=True,
            has_budget_limits=True,
            has_human_approval=False,
        )
        assert not report.ready
        assert any(
            'destructive' in f.message.lower() or 'HITL' in f.message
            for f in report.findings
        )

    def test_missing_audit_log_reports_error(self):
        registry = ToolRegistry()
        registry.register(
            name='safe_tool',
            description='Safe tool',
            handler=_noop_handler,
            input_schema={'type': 'object', 'properties': {}},
            output_schema={'type': 'object'},
            annotations=ToolAnnotations(read_only=True),
        )
        report = assess_managed_agent_readiness(
            registry=registry,
            has_external_state=True,
            has_audit_log=False,
            has_budget_limits=True,
            has_human_approval=True,
        )
        assert not report.ready
        assert any('audit' in f.message.lower() for f in report.findings)

    def test_missing_budget_reports_error(self):
        registry = ToolRegistry()
        registry.register(
            name='safe_tool',
            description='Safe tool',
            handler=_noop_handler,
            input_schema={'type': 'object', 'properties': {}},
            output_schema={'type': 'object'},
            annotations=ToolAnnotations(read_only=True),
        )
        report = assess_managed_agent_readiness(
            registry=registry,
            has_external_state=True,
            has_audit_log=True,
            has_budget_limits=False,
            has_human_approval=True,
        )
        assert not report.ready
        assert any('budget' in f.message.lower() for f in report.findings)

    def test_missing_external_state_reports_warning(self):
        registry = ToolRegistry()
        registry.register(
            name='safe_tool',
            description='Safe tool',
            handler=_noop_handler,
            input_schema={'type': 'object', 'properties': {}},
            output_schema={'type': 'object'},
            annotations=ToolAnnotations(read_only=True),
        )
        report = assess_managed_agent_readiness(
            registry=registry,
            has_external_state=False,
            has_audit_log=True,
            has_budget_limits=True,
            has_human_approval=True,
        )
        assert report.ready is True
        assert any('external state' in f.message.lower() for f in report.findings)
