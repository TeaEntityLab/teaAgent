"""Remote marketplace client — fetch skills from agentskills.io compatible registries."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.http_utils import safe_urlopen


@dataclass(frozen=True)
class RemoteSkillEntry:
    name: str
    description: str
    version: str
    download_url: str
    author: str = ''
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'download_url': self.download_url,
            'author': self.author,
            'tags': list(self.tags),
        }


class MarketplaceClient:
    """Client for fetching remote marketplace registries."""

    def __init__(
        self, registry_url: str = 'https://agentskills.io/api/v1/skills'
    ) -> None:
        self._url = registry_url

    def fetch(self, *, query: str = '', limit: int = 20) -> list[RemoteSkillEntry]:
        """Fetch skills from the remote registry."""
        url = self._url
        if query:
            url += f'?q={urllib.parse.quote(query)}&limit={limit}'
        try:
            with safe_urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception:
            return []
        entries = (
            data
            if isinstance(data, list)
            else data.get('skills', data.get('entries', []))
        )
        results: list[RemoteSkillEntry] = []
        for e in entries[:limit]:
            if isinstance(e, dict) and 'name' in e:
                results.append(
                    RemoteSkillEntry(
                        name=e['name'],
                        description=e.get('description', ''),
                        version=e.get('version', '0.1.0'),
                        download_url=e.get('download_url') or e.get('url') or '',
                        author=e.get('author', ''),
                        tags=tuple(e.get('tags', [])),
                    )
                )
        return results

    def download(self, entry: RemoteSkillEntry, dest: str) -> bool:
        """Download a skill SKILL.md to *dest* path."""
        try:
            with safe_urlopen(entry.download_url, timeout=30) as resp:
                content = resp.read().decode('utf-8')
            Path(dest).write_text(content, encoding='utf-8')
            return True
        except Exception:
            return False
