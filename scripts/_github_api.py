"""Lightweight GitHub API helpers for monitoring scripts."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_BASE = 'https://api.github.com'


def _headers() -> dict[str, str]:
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'teaagent-monitor',
    }
    token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def get_json(path: str, *, params: dict[str, str] | None = None) -> Any:
    """Fetch JSON from the GitHub REST API."""
    url = f'{API_BASE}{path}'
    if params:
        url = f'{url}?{urllib.parse.urlencode(params)}'
    request = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError as exc:
        raise RuntimeError(f'GitHub API request failed for {path}: {exc}') from exc


def get_repo(owner: str, repo: str) -> dict[str, Any]:
    return get_json(f'/repos/{owner}/{repo}')


def get_repo_stars(owner: str, repo: str) -> int:
    data = get_repo(owner, repo)
    return int(data.get('stargazers_count', 0))


def get_latest_release_tag(owner: str, repo: str) -> str | None:
    try:
        data = get_json(f'/repos/{owner}/{repo}/releases/latest')
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    tag = data.get('tag_name')
    return str(tag) if tag else None


def search_issues(
    query: str,
    *,
    per_page: int = 10,
) -> list[dict[str, Any]]:
    data = get_json('/search/issues', params={'q': query, 'per_page': str(per_page)})
    items = data.get('items', [])
    return items if isinstance(items, list) else []


def repo_from_env(var_name: str, default: str) -> tuple[str, str]:
    """Parse owner/repo from an environment variable."""
    value = os.getenv(var_name, default)
    if '/' not in value:
        raise ValueError(f'{var_name} must be owner/repo, got {value!r}')
    owner, repo = value.split('/', 1)
    return owner, repo
