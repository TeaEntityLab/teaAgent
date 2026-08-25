"""EFX-002: built-in external mutations fail closed in constrained modes."""

from __future__ import annotations

from teaagent.approval.backend import (
    ApprovalRequest,
    PromptBackend,
    WorkspaceWriteBackend,
    requires_effect_escalation,
)
from teaagent.browser_tools import register_browser_tools
from teaagent.github_integration import register_github_tools
from teaagent.mcp_tool_adapter import _infer_annotations
from teaagent.policy import PermissionMode
from teaagent.tools import ToolRegistry


def _request(tool_name: str, annotations: dict[str, bool]) -> ApprovalRequest:
    return ApprovalRequest(
        call_id='c1',
        tool_name=tool_name,
        arguments={'repo': 'o/r', 'title': 't', 'head': 'b'},
        reason='test',
        annotations=annotations,
        permission_mode=PermissionMode.PROMPT,
    )


def test_github_mutating_tools_are_external_effects() -> None:
    registry = ToolRegistry()
    register_github_tools(registry)
    create_pr = registry.get('github_create_pr').annotations
    review_pr = registry.get('github_review_pr').annotations
    list_prs = registry.get('github_list_prs').annotations
    assert create_pr.destructive is True
    assert create_pr.external_effect is True
    assert create_pr.idempotent is False
    assert review_pr.destructive is True
    assert review_pr.external_effect is True
    assert list_prs.read_only is True
    assert list_prs.external_effect is False


def test_browser_mutating_tools_are_external_effects() -> None:
    registry = ToolRegistry()
    register_browser_tools(registry)
    for name in (
        'browser_click',
        'browser_fill',
        'browser_evaluate',
        'browser_navigate',
    ):
        ann = registry.get(name).annotations
        assert ann.read_only is False, name
        assert ann.destructive is True, name
        assert ann.external_effect is True, name
        assert ann.idempotent is False, name
    for name in (
        'browser_snapshot',
        'browser_screenshot',
        'browser_get_content',
    ):
        ann = registry.get(name).annotations
        assert ann.read_only is True, name
        assert ann.external_effect is False, name
        assert ann.destructive is False, name


def test_prompt_backend_does_not_auto_approve_github_create_pr() -> None:
    registry = ToolRegistry()
    register_github_tools(registry)
    ann = registry.get('github_create_pr').annotations
    decision = PromptBackend().approve(
        _request(
            'github_create_pr',
            {
                'destructive': ann.destructive,
                'read_only': ann.read_only,
                'external_effect': ann.external_effect,
            },
        )
    )
    assert decision.approved is False
    assert decision.reason_code == 'jit_required'


def test_workspace_write_denies_external_github_and_browser() -> None:
    backend = WorkspaceWriteBackend()
    github = backend.approve(
        ApprovalRequest(
            call_id='c1',
            tool_name='github_create_pr',
            arguments={'repo': 'o/r', 'title': 't', 'head': 'b'},
            reason='test',
            annotations={'destructive': True, 'external_effect': True},
            permission_mode=PermissionMode.WORKSPACE_WRITE,
        )
    )
    browser = backend.approve(
        ApprovalRequest(
            call_id='c2',
            tool_name='browser_click',
            arguments={'selector': 'button'},
            reason='test',
            annotations={'destructive': True, 'external_effect': True},
            permission_mode=PermissionMode.WORKSPACE_WRITE,
        )
    )
    assert github.approved is False
    assert browser.approved is False


def test_mcp_hints_cannot_relax_local_policy() -> None:
    ann = _infer_annotations(
        {
            'name': 'remote_echo',
            'annotations': {'readOnlyHint': True, 'destructiveHint': False},
        }
    )
    assert ann.read_only is False
    assert ann.destructive is True
    assert ann.external_effect is True
    assert ann.idempotent is False
    assert requires_effect_escalation(
        {
            'destructive': ann.destructive,
            'external_effect': ann.external_effect,
        }
    )
