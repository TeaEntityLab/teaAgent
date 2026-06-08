"""Working example: approval policy patterns.

Demonstrates:
- READ_ONLY policy (blocks all writes)
- PROMPT policy with a custom approval handler
- Path-scoped WORKSPACE_WRITE policy
- Hook-level permission guard

Run without API keys:

    python3 docs/guides/examples/approval_patterns.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.hooks import (
    HookPermissionMode,
    HookRegistry,
    permission_check_hook,
)
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.types import AuditLogger, PermissionMode, RunBudget, ToolPermissionError
from teaagent.workspace_tools import build_workspace_tool_registry

# ── helpers ──────────────────────────────────────────────────────────────────


def make_runner(
    workspace: Path,
    policy: ApprovalPolicy,
    hook_reg: HookRegistry | None = None,
) -> AgentRunner:
    registry = build_workspace_tool_registry(workspace)
    audit = AuditLogger(path=workspace / '.teaagent' / 'audit.jsonl')
    return AgentRunner(
        registry=registry,
        audit=audit,
        budget=RunBudget(max_iterations=3, max_tool_calls=2),
        approval_policy=policy,
        hook_registry=hook_reg,
    )


# ── pattern 1: read-only blocks all writes ───────────────────────────────────


def demo_read_only(workspace: Path) -> None:
    print('\n=== Pattern 1: READ_ONLY ===')
    policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
    runner = make_runner(workspace, policy)

    step = [0]

    def decide(context):
        step[0] += 1
        if step[0] == 1:
            # Attempt a write — should be blocked
            return ToolRequest(
                tool_name='workspace_write_file',
                arguments={'path': 'blocked.txt', 'content': 'this should not appear'},
            )
        return FinalAnswer(content='write was blocked as expected')

    try:
        result = runner.run(task='try to write a file', decide=decide)
        print(f'  status={result.status}')
    except ToolPermissionError as exc:
        print(f'  Blocked correctly: {exc}')


# ── pattern 2: PROMPT with custom approval handler ────────────────────────────


def demo_prompt_with_handler(workspace: Path) -> None:
    print('\n=== Pattern 2: PROMPT + custom handler ===')

    approved = []

    def my_handler(tool_name: str, arguments: dict, call_id: str) -> bool:
        # Auto-approve writes to the 'output/' directory only
        path = arguments.get('path', '')
        decision = path.startswith('output/')
        approved.append((tool_name, path, decision))
        return decision

    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        enable_jit_prompt=False,  # use handler instead of TTY
        approval_handler=my_handler,
    )
    runner = make_runner(workspace, policy)
    (workspace / 'output').mkdir(exist_ok=True)

    step = [0]

    def decide(context):
        step[0] += 1
        if step[0] == 1:
            # Write to output/ — handler will approve
            return ToolRequest(
                tool_name='workspace_write_file',
                arguments={'path': 'output/result.txt', 'content': 'ok'},
            )
        return FinalAnswer(content='done')

    result = runner.run(task='write output file', decide=decide)
    print(f'  status={result.status}')
    for tool, path, dec in approved:
        print(f'  handler: {tool} @ {path!r} → {"approved" if dec else "denied"}')


# ── pattern 3: hook-level path guard ─────────────────────────────────────────


def demo_hook_guard(workspace: Path) -> None:
    print('\n=== Pattern 3: hook-level path guard ===')

    hook_reg = HookRegistry()
    hook_reg.register_pre_hook(
        permission_check_hook(
            mode=HookPermissionMode.ASK,
            allow_patterns=frozenset({'safe/**'}),
            deny_patterns=frozenset({'secrets/**', '.env'}),
        )
    )

    policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
    runner = make_runner(workspace, policy, hook_reg=hook_reg)
    (workspace / 'safe').mkdir(exist_ok=True)

    step = [0]

    def decide(context):
        step[0] += 1
        if step[0] == 1:
            return ToolRequest(
                tool_name='workspace_write_file',
                arguments={'path': 'safe/notes.txt', 'content': 'allowed'},
            )
        return FinalAnswer(content='done')

    result = runner.run(task='write to safe directory', decide=decide)
    print(f'  status={result.status} (safe/ write allowed by hook guard)')


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)

        demo_read_only(workspace)
        demo_prompt_with_handler(workspace)
        demo_hook_guard(workspace)

    print('\nAll approval pattern demos complete.')


if __name__ == '__main__':
    main()
