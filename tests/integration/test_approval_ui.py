"""IT: DiffApprovalHandler — interactive approval with diff preview.

Verifies that the handler:
- Generates a unified diff for workspace write tools.
- Returns True on 'y' input, False on 'n'.
- Re-prompts on unrecognised input.
- Shows a creation diff when the file does not yet exist.
- Works for non-write tools (shows argument summary instead of diff).
"""

from __future__ import annotations

from teaagent.approval_ui import DiffApprovalHandler
from teaagent.runner import ApprovalRequest


def _req(tool_name: str, arguments: dict, call_id: str = 'c1') -> ApprovalRequest:
    return ApprovalRequest(
        call_id=call_id,
        tool_name=tool_name,
        arguments=arguments,
        reason='requires approval',
        annotations={'read_only': False, 'destructive': True, 'idempotent': False},
    )


# ---------------------------------------------------------------------------
# Approval / denial
# ---------------------------------------------------------------------------


def test_approve_returns_true(tmp_path):
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'y', output_fn=output.append
    )
    req = _req('workspace_write_file', {'path': 'hello.txt', 'content': 'hello'})
    assert handler(req) is True


def test_deny_returns_false(tmp_path):
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'n', output_fn=output.append
    )
    req = _req('workspace_write_file', {'path': 'hello.txt', 'content': 'hello'})
    assert handler(req) is False


def test_case_insensitive_yes(tmp_path):
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'Y', output_fn=lambda _: None
    )
    req = _req('workspace_write_file', {'path': 'f.txt', 'content': 'x'})
    assert handler(req) is True


def test_case_insensitive_no(tmp_path):
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'N', output_fn=lambda _: None
    )
    req = _req('workspace_write_file', {'path': 'f.txt', 'content': 'x'})
    assert handler(req) is False


# ---------------------------------------------------------------------------
# Diff output
# ---------------------------------------------------------------------------


def test_diff_shown_for_write_tool(tmp_path):
    (tmp_path / 'greet.txt').write_text('Hello World\n', encoding='utf-8')
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'n', output_fn=output.append
    )
    req = _req(
        'workspace_write_file',
        {'path': 'greet.txt', 'content': 'Hello TeaAgent\n'},
    )
    handler(req)
    combined = '\n'.join(output)
    assert '-Hello World' in combined or '--- ' in combined
    assert '+Hello TeaAgent' in combined or '+++' in combined


def test_creation_diff_for_new_file(tmp_path):
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'n', output_fn=output.append
    )
    req = _req('workspace_write_file', {'path': 'brand_new.txt', 'content': 'new!\n'})
    handler(req)
    combined = '\n'.join(output)
    assert 'new!' in combined or '+new!' in combined


def test_non_write_tool_shows_summary(tmp_path):
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'n', output_fn=output.append
    )
    req = _req(
        'workspace_run_shell_mutate',
        {'command': 'rm -rf /tmp/test'},
    )
    handler(req)
    combined = '\n'.join(output)
    assert 'workspace_run_shell_mutate' in combined


# ---------------------------------------------------------------------------
# Invalid input re-prompts
# ---------------------------------------------------------------------------


def test_invalid_input_reprompts_then_approves(tmp_path):
    inputs = iter(['maybe', 'what', 'y'])
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path,
        input_fn=lambda _: next(inputs),
        output_fn=output.append,
        max_prompts=5,
    )
    req = _req('workspace_write_file', {'path': 'x.txt', 'content': 'x'})
    assert handler(req) is True
    assert any('y' in line.lower() or 'n' in line.lower() for line in output)


def test_max_prompts_exceeded_returns_false(tmp_path):
    handler = DiffApprovalHandler(
        tmp_path,
        input_fn=lambda _: 'what',
        output_fn=lambda _: None,
        max_prompts=3,
    )
    req = _req('workspace_write_file', {'path': 'x.txt', 'content': 'x'})
    assert handler(req) is False


# ---------------------------------------------------------------------------
# Explain mode
# ---------------------------------------------------------------------------


def test_explain_then_approve(tmp_path):
    inputs = iter(['e', 'y'])
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: next(inputs), output_fn=output.append
    )
    req = _req(
        'workspace_write_file',
        {'path': 'test.txt', 'content': 'explained content'},
    )
    assert handler(req) is True
    combined = '\n'.join(output)
    assert 'workspace_write_file' in combined or 'test.txt' in combined


# ---------------------------------------------------------------------------
# Apply-patch and edit-at-hash show diff-like output
# ---------------------------------------------------------------------------


def test_apply_patch_shows_patch_content(tmp_path):
    (tmp_path / 'src.py').write_text('x = 1\n', encoding='utf-8')
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'n', output_fn=output.append
    )
    patch = '--- a/src.py\n+++ b/src.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n'
    req = _req('workspace_apply_patch', {'path': 'src.py', 'patch': patch})
    handler(req)
    combined = '\n'.join(output)
    assert 'x = 2' in combined or 'src.py' in combined


def test_path_traversal_argument_handled(tmp_path):
    """Path traversal in arguments must not raise — just show tool summary."""
    output: list[str] = []
    handler = DiffApprovalHandler(
        tmp_path, input_fn=lambda _: 'n', output_fn=output.append
    )
    req = _req('workspace_write_file', {'path': '../../../etc/passwd', 'content': 'x'})
    result = handler(req)
    assert result is False  # denied or errored gracefully
