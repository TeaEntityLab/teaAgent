"""Git write operations: commit, branch, checkout, push, pull, add."""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.tools import ToolAnnotations, ToolRateLimit, ToolRegistry


@dataclass
class GitToolConfig:
    root: Path = field(default_factory=lambda: Path('.'))


def _run_git(
    config: GitToolConfig, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', '-C', str(config.root)] + args,
        capture_output=True,
        text=True,
        check=check,
        timeout=30,
    )


def git_add(config: GitToolConfig, pathspec: str) -> dict[str, Any]:
    """Stage files matching *pathspec* (use '.' for all)."""
    result = _run_git(config, ['add', pathspec])
    return {
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'exit_code': result.returncode,
    }


def git_commit(
    config: GitToolConfig,
    message: str,
    *,
    amend: bool = False,
    no_verify: bool = False,
) -> dict[str, Any]:
    """Create a commit with *message*."""
    cmd = ['commit', '-m', message]
    if amend:
        cmd.append('--amend')
    if no_verify:
        cmd.extend(['--no-verify'])
    result = _run_git(config, cmd)
    short = ''
    if result.returncode == 0:
        with contextlib.suppress(subprocess.CalledProcessError):
            short = _run_git(config, ['log', '-1', '--format=%h']).stdout.strip()
    return {
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'exit_code': result.returncode,
        'commit_sha': short,
    }


def git_lore_commit(
    config: GitToolConfig,
    summary: str,
    why: str,
    what: str,
    *,
    session_id: Optional[str] = None,
    amend: bool = False,
    no_verify: bool = False,
) -> dict[str, Any]:
    """Create a Lore-compliant commit with structured message and OmX trailer."""
    lines = [summary, '', f'Why: {why}', f'What: {what}']
    if session_id:
        lines.extend(['', f'Session-ID: {session_id}'])
    lines.extend(['', 'Co-authored-by: OmX <omx@oh-my-codex.dev>'])
    message = '\n'.join(lines)
    return git_commit(config, message, amend=amend, no_verify=no_verify)


def git_create_branch(
    config: GitToolConfig,
    name: str,
    *,
    start_point: Optional[str] = None,
    checkout: bool = False,
) -> dict[str, Any]:
    """Create a new branch, optionally checking it out."""
    cmd: list[str] = ['checkout', '-b', name] if checkout else ['branch', name]
    if start_point:
        cmd.append(start_point)
    result = _run_git(config, cmd)
    return {
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'exit_code': result.returncode,
        'branch': name,
    }


def git_checkout(
    config: GitToolConfig,
    target: str,
    *,
    create: bool = False,
    start_point: Optional[str] = None,
) -> dict[str, Any]:
    """Switch to *target* branch (or commit/tag)."""
    if create:
        cmd = ['checkout', '-b', target]
        if start_point:
            cmd.append(start_point)
    else:
        cmd = ['checkout', target]
    result = _run_git(config, cmd)
    return {
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'exit_code': result.returncode,
        'branch': target,
    }


def git_push(
    config: GitToolConfig,
    *,
    remote: str = 'origin',
    branch: Optional[str] = None,
    force: bool = False,
    set_upstream: bool = False,
) -> dict[str, Any]:
    """Push to *remote*."""
    cmd = ['push']
    if force:
        cmd.append('--force')
    if set_upstream:
        cmd.append('-u')
    cmd.append(remote)
    if branch:
        cmd.append(branch)
    result = _run_git(config, cmd)
    return {
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'exit_code': result.returncode,
    }


def git_pull(
    config: GitToolConfig,
    *,
    remote: str = 'origin',
    branch: Optional[str] = None,
    rebase: bool = False,
) -> dict[str, Any]:
    """Pull from *remote*."""
    cmd = ['pull']
    if rebase:
        cmd.append('--rebase')
    cmd.append(remote)
    if branch:
        cmd.append(branch)
    result = _run_git(config, cmd)
    return {
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'exit_code': result.returncode,
    }


def git_stash(
    config: GitToolConfig,
    *,
    message: Optional[str] = None,
    include_untracked: bool = False,
    pop: bool = False,
) -> dict[str, Any]:
    """Stash working-tree changes."""
    if pop:
        cmd = ['stash', 'pop']
    else:
        cmd = ['stash']
        if include_untracked:
            cmd.append('-u')
        if message:
            cmd.extend(['-m', message])
    result = _run_git(config, cmd)
    return {
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'exit_code': result.returncode,
    }


def _object_schema(properties: dict, required: list[str] | None = None) -> dict:
    schema: dict[str, Any] = {
        'type': 'object',
        'properties': properties,
    }
    if required:
        schema['required'] = required
    return schema


def register_git_tools(registry: ToolRegistry, config: GitToolConfig) -> None:
    """Register git write-operation tools into *registry*."""

    registry.register(
        name='git_add',
        description='Stage files matching a pathspec for the next commit. Use "." to stage all changes.',
        input_schema=_object_schema(
            {
                'pathspec': {
                    'type': 'string',
                    'description': 'File path or glob pattern (use "." for all).',
                }
            },
            required=['pathspec'],
        ),
        output_schema=_object_schema(
            {
                'stdout': {'type': 'string'},
                'stderr': {'type': 'string'},
                'exit_code': {'type': 'integer'},
            },
            required=['stdout', 'stderr', 'exit_code'],
        ),
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: git_add(config, args['pathspec']),
    )

    registry.register(
        name='git_commit',
        description='Create a new commit with the given message. Supports --amend and --no-verify.',
        input_schema=_object_schema(
            {
                'message': {'type': 'string', 'description': 'Commit message.'},
                'amend': {
                    'type': 'boolean',
                    'description': 'Amend the previous commit.',
                },
                'no_verify': {
                    'type': 'boolean',
                    'description': 'Skip pre-commit hooks.',
                },
            },
            required=['message'],
        ),
        output_schema=_object_schema(
            {
                'stdout': {'type': 'string'},
                'stderr': {'type': 'string'},
                'exit_code': {'type': 'integer'},
                'commit_sha': {'type': 'string'},
            },
            required=['stdout', 'stderr', 'exit_code', 'commit_sha'],
        ),
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: git_commit(
            config,
            args['message'],
            amend=args.get('amend', False),
            no_verify=args.get('no_verify', False),
        ),
        rate_limit=ToolRateLimit(max_calls=10, window_seconds=60.0),
    )

    registry.register(
        name='git_lore_commit',
        description='Create a Lore-compliant commit message with structured Why/What and OmX co-author trailer.',
        input_schema=_object_schema(
            {
                'summary': {
                    'type': 'string',
                    'description': 'Commit summary (first line).',
                },
                'why': {
                    'type': 'string',
                    'description': 'The rationale for this change.',
                },
                'what': {'type': 'string', 'description': 'What was actually changed.'},
                'session_id': {
                    'type': 'string',
                    'description': 'Optional session ID for traceability.',
                },
                'amend': {
                    'type': 'boolean',
                    'description': 'Amend the previous commit.',
                },
                'no_verify': {
                    'type': 'boolean',
                    'description': 'Skip pre-commit hooks.',
                },
            },
            required=['summary', 'why', 'what'],
        ),
        output_schema=_object_schema(
            {
                'stdout': {'type': 'string'},
                'stderr': {'type': 'string'},
                'exit_code': {'type': 'integer'},
                'commit_sha': {'type': 'string'},
            },
            required=['stdout', 'stderr', 'exit_code', 'commit_sha'],
        ),
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: git_lore_commit(
            config,
            args['summary'],
            args['why'],
            args['what'],
            session_id=args.get('session_id'),
            amend=args.get('amend', False),
            no_verify=args.get('no_verify', False),
        ),
        rate_limit=ToolRateLimit(max_calls=10, window_seconds=60.0),
    )

    registry.register(
        name='git_create_branch',
        description='Create a new git branch, optionally from a start point and optionally checking it out.',
        input_schema=_object_schema(
            {
                'name': {'type': 'string', 'description': 'Branch name.'},
                'start_point': {
                    'type': 'string',
                    'description': 'Branch or commit to base on.',
                },
                'checkout': {
                    'type': 'boolean',
                    'description': 'Switch to the new branch after creating it.',
                },
            },
            required=['name'],
        ),
        output_schema=_object_schema(
            {
                'stdout': {'type': 'string'},
                'stderr': {'type': 'string'},
                'exit_code': {'type': 'integer'},
                'branch': {'type': 'string'},
            },
            required=['stdout', 'stderr', 'exit_code', 'branch'],
        ),
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: git_create_branch(
            config,
            args['name'],
            start_point=args.get('start_point'),
            checkout=args.get('checkout', False),
        ),
    )

    registry.register(
        name='git_checkout',
        description='Switch to a different branch, tag, or commit. Can also create a new branch.',
        input_schema=_object_schema(
            {
                'target': {
                    'type': 'string',
                    'description': 'Branch, tag, or commit to switch to.',
                },
                'create': {
                    'type': 'boolean',
                    'description': 'Create a new branch with the target name.',
                },
                'start_point': {
                    'type': 'string',
                    'description': 'Base for new branch (only when create=true).',
                },
            },
            required=['target'],
        ),
        output_schema=_object_schema(
            {
                'stdout': {'type': 'string'},
                'stderr': {'type': 'string'},
                'exit_code': {'type': 'integer'},
                'branch': {'type': 'string'},
            },
            required=['stdout', 'stderr', 'exit_code', 'branch'],
        ),
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: git_checkout(
            config,
            args['target'],
            create=args.get('create', False),
            start_point=args.get('start_point'),
        ),
    )

    registry.register(
        name='git_push',
        description='Push commits to a remote. Supports force push and setting upstream tracking.',
        input_schema=_object_schema(
            {
                'remote': {
                    'type': 'string',
                    'description': 'Remote name (default: origin).',
                },
                'branch': {'type': 'string', 'description': 'Branch to push.'},
                'force': {
                    'type': 'boolean',
                    'description': 'Force push (use with caution).',
                },
                'set_upstream': {
                    'type': 'boolean',
                    'description': 'Set upstream tracking.',
                },
            },
        ),
        output_schema=_object_schema(
            {
                'stdout': {'type': 'string'},
                'stderr': {'type': 'string'},
                'exit_code': {'type': 'integer'},
            },
            required=['stdout', 'stderr', 'exit_code'],
        ),
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: git_push(
            config,
            remote=args.get('remote', 'origin'),
            branch=args.get('branch'),
            force=args.get('force', False),
            set_upstream=args.get('set_upstream', False),
        ),
        rate_limit=ToolRateLimit(max_calls=5, window_seconds=60.0),
    )

    registry.register(
        name='git_pull',
        description='Pull changes from a remote. Supports rebase mode.',
        input_schema=_object_schema(
            {
                'remote': {
                    'type': 'string',
                    'description': 'Remote name (default: origin).',
                },
                'branch': {'type': 'string', 'description': 'Branch to pull.'},
                'rebase': {
                    'type': 'boolean',
                    'description': 'Use rebase instead of merge.',
                },
            },
        ),
        output_schema=_object_schema(
            {
                'stdout': {'type': 'string'},
                'stderr': {'type': 'string'},
                'exit_code': {'type': 'integer'},
            },
            required=['stdout', 'stderr', 'exit_code'],
        ),
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: git_pull(
            config,
            remote=args.get('remote', 'origin'),
            branch=args.get('branch'),
            rebase=args.get('rebase', False),
        ),
    )

    registry.register(
        name='git_stash',
        description='Stash working-tree changes. Supports --include-untracked and pop.',
        input_schema=_object_schema(
            {
                'message': {'type': 'string', 'description': 'Stash message.'},
                'include_untracked': {
                    'type': 'boolean',
                    'description': 'Include untracked files.',
                },
                'pop': {'type': 'boolean', 'description': 'Pop the most recent stash.'},
            },
        ),
        output_schema=_object_schema(
            {
                'stdout': {'type': 'string'},
                'stderr': {'type': 'string'},
                'exit_code': {'type': 'integer'},
            },
            required=['stdout', 'stderr', 'exit_code'],
        ),
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: git_stash(
            config,
            message=args.get('message'),
            include_untracked=args.get('include_untracked', False),
            pop=args.get('pop', False),
        ),
    )
