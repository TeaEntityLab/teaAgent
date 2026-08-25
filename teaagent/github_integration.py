"""GitHub Native Integration — PR creation, code review, CI status.

Tools registered via ``register_github_tools()`` follow the same
ToolRegistry pattern as workspace tools.
"""

from __future__ import annotations

import json
import os
import urllib.error
from typing import Any, Optional

from teaagent.http_utils import safe_urlopen
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools._helpers import object_schema


def _get_token() -> Optional[str]:
    return os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')


def _github_headers() -> dict[str, str]:
    token = _get_token()
    if not token:
        raise PermissionError(
            'GitHub token not found. Set GITHUB_TOKEN or GH_TOKEN environment variable.'
        )
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'teaagent',
    }


def _gh_api(
    method: str, path: str, body: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    url = f'https://api.github.com{path}'
    headers = _github_headers()
    data = json.dumps(body).encode('utf-8') if body else None
    try:
        with safe_urlopen(url, data=data, headers=headers) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        return {'error': f'HTTP {exc.code}: {detail}'}


def github_create_pr(
    repo: str,
    title: str,
    head: str,
    base: str = 'main',
    body: str = '',
    *,
    draft: bool = False,
) -> dict[str, Any]:
    """Create a pull request on *repo* (``owner/repo``) from *head* to *base*."""
    result = _gh_api(
        'POST',
        f'/repos/{repo}/pulls',
        {
            'title': title,
            'head': head,
            'base': base,
            'body': body,
            'draft': draft,
        },
    )
    if 'error' in result:
        return {'status': 'error', 'message': result['error']}
    return {
        'status': 'ok',
        'pr_number': result.get('number'),
        'pr_url': result.get('html_url', ''),
        'title': result.get('title', title),
    }


def github_list_prs(
    repo: str,
    state: str = 'open',
    *,
    limit: int = 10,
) -> dict[str, Any]:
    """List pull requests on *repo* in *state* (open/closed/all)."""
    result = _gh_api('GET', f'/repos/{repo}/pulls?state={state}&per_page={limit}')
    if isinstance(result, dict) and 'error' in result:
        return {'status': 'error', 'message': result['error']}
    if isinstance(result, list):
        return {
            'status': 'ok',
            'prs': [
                {
                    'number': pr.get('number'),
                    'title': pr.get('title', ''),
                    'url': pr.get('html_url', ''),
                    'state': pr.get('state', ''),
                    'user': pr.get('user', {}).get('login', ''),
                    'created_at': pr.get('created_at', ''),
                }
                for pr in result[:limit]
            ],
            'count': len(result[:limit]),
        }
    return {'status': 'error', 'message': 'unexpected response format'}


def github_review_pr(
    repo: str,
    pr_number: int,
    body: str,
    event: str = 'COMMENT',
) -> dict[str, Any]:
    """Submit a review on PR #*pr_number*. *event* is APPROVE/REQUEST_CHANGES/COMMENT."""
    result = _gh_api(
        'POST',
        f'/repos/{repo}/pulls/{pr_number}/reviews',
        {
            'body': body,
            'event': event,
        },
    )
    if 'error' in result:
        return {'status': 'error', 'message': result['error']}
    return {
        'status': 'ok',
        'review_id': result.get('id'),
        'state': result.get('state', event),
    }


def github_ci_status(repo: str, ref: str = 'main') -> dict[str, Any]:
    """Get combined CI status for *ref* on *repo*."""
    result = _gh_api('GET', f'/repos/{repo}/commits/{ref}/status')
    if 'error' in result:
        return {'status': 'error', 'message': result['error']}
    return {
        'status': 'ok',
        'state': result.get('state', 'unknown'),
        'total_count': result.get('total_count', 0),
        'statuses': [
            {
                'context': s.get('context', ''),
                'state': s.get('state', ''),
                'description': s.get('description', ''),
            }
            for s in result.get('statuses', [])
        ],
    }


def register_github_tools(registry: ToolRegistry) -> None:
    """Register GitHub integration tools into *registry*."""
    registry.register(
        name='github_create_pr',
        description='Create a pull request on GitHub from one branch to another.',
        input_schema=object_schema(
            {
                'repo': {
                    'type': 'string',
                    'description': 'Repository in owner/repo format.',
                },
                'title': {'type': 'string', 'description': 'Pull request title.'},
                'head': {'type': 'string', 'description': 'Source branch name.'},
                'base': {
                    'type': 'string',
                    'description': 'Target branch (default main).',
                },
                'body': {'type': 'string', 'description': 'PR body text.'},
                'draft': {'type': 'boolean', 'description': 'Create as draft PR.'},
            },
            required=['repo', 'title', 'head'],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'pr_number': 'integer',
                'pr_url': 'string',
                'title': 'string',
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(
            read_only=False,
            destructive=True,
            idempotent=False,
            external_effect=True,
        ),
        handler=lambda args: github_create_pr(
            args['repo'],
            args['title'],
            args['head'],
            base=args.get('base', 'main'),
            body=args.get('body', ''),
            draft=args.get('draft', False),
        ),
    )
    registry.register(
        name='github_list_prs',
        description='List pull requests on a GitHub repository.',
        input_schema=object_schema(
            {
                'repo': {
                    'type': 'string',
                    'description': 'Repository in owner/repo format.',
                },
                'state': {
                    'type': 'string',
                    'description': 'PR state: open, closed, or all.',
                },
                'limit': {
                    'type': 'integer',
                    'description': 'Max results (default 10).',
                },
            },
            required=['repo'],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'prs': 'array',
                'count': 'integer',
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: github_list_prs(
            args['repo'],
            state=args.get('state', 'open'),
            limit=args.get('limit', 10),
        ),
    )
    registry.register(
        name='github_review_pr',
        description='Submit a code review on a pull request.',
        input_schema=object_schema(
            {
                'repo': {
                    'type': 'string',
                    'description': 'Repository in owner/repo format.',
                },
                'pr_number': {'type': 'integer', 'description': 'Pull request number.'},
                'body': {'type': 'string', 'description': 'Review comment body.'},
                'event': {
                    'type': 'string',
                    'description': 'APPROVE, REQUEST_CHANGES, or COMMENT.',
                },
            },
            required=['repo', 'pr_number', 'body'],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'review_id': 'integer',
                'state': 'string',
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(
            read_only=False,
            destructive=True,
            idempotent=False,
            external_effect=True,
        ),
        handler=lambda args: github_review_pr(
            args['repo'],
            args['pr_number'],
            args['body'],
            event=args.get('event', 'COMMENT'),
        ),
    )
    registry.register(
        name='github_ci_status',
        description='Get the combined CI status for a branch or commit on GitHub.',
        input_schema=object_schema(
            {
                'repo': {
                    'type': 'string',
                    'description': 'Repository in owner/repo format.',
                },
                'ref': {
                    'type': 'string',
                    'description': 'Branch name or commit SHA (default main).',
                },
            },
            required=['repo'],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'state': 'string',
                'total_count': 'integer',
                'statuses': 'array',
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: github_ci_status(
            args['repo'], ref=args.get('ref', 'main')
        ),
    )
