"""Command-snippet smoke inventory (DOW-026).

Scans high-value guide docs for `teaagent` command snippets and compares them
against the curated registry in docs/governance/command-snippet-registry.md.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUTPUT = _REPO_ROOT / 'docs' / 'generated' / 'command-snippet-inventory.md'
_REGISTRY_PATH = _REPO_ROOT / 'docs' / 'governance' / 'command-snippet-registry.md'

_GUIDE_PATHS = (
    _REPO_ROOT / 'README.md',
    _REPO_ROOT / 'docs' / 'USAGE.md',
    _REPO_ROOT / 'docs' / 'cli.md',
)

_CODE_BLOCK = re.compile(r'```(?:bash|sh|shell|console)?\n(.*?)```', re.DOTALL)
_TEAAGENT_CMD = re.compile(r'^\s*(teaagent(?:\s+[^\n`#]+)?)', re.MULTILINE)
_REGISTRY_ROW = re.compile(
    r'^\|\s*`([^`]+)`\s*\|\s*(smoke|manual)\s*\|\s*([^|]+)\|',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CommandSnippet:
    command: str
    source: str
    line_hint: int


def _normalize_command(command: str) -> str:
    cleaned = ' '.join(command.strip().split())
    if '<' in cleaned or '>' in cleaned:
        return ''
    if len(cleaned) > 160:
        return ''
    return cleaned


def _extract_snippets(path: Path) -> list[CommandSnippet]:
    if not path.is_file():
        return []
    text = path.read_text(encoding='utf-8')
    snippets: list[CommandSnippet] = []
    for block in _CODE_BLOCK.finditer(text):
        block_text = block.group(1)
        block_start = block.start()
        for match in _TEAAGENT_CMD.finditer(block_text):
            command = _normalize_command(match.group(1))
            if not command or command == 'teaagent':
                continue
            if not command.startswith('teaagent '):
                continue
            line_hint = text[: block_start + match.start()].count('\n') + 1
            rel = path.relative_to(_REPO_ROOT).as_posix()
            snippets.append(
                CommandSnippet(command=command, source=rel, line_hint=line_hint)
            )
    return snippets


def _dedupe_snippets(snippets: list[CommandSnippet]) -> list[CommandSnippet]:
    seen: set[str] = set()
    unique: list[CommandSnippet] = []
    for snippet in sorted(snippets, key=lambda item: (item.command, item.source)):
        if snippet.command in seen:
            continue
        seen.add(snippet.command)
        unique.append(snippet)
    return unique


def load_registry(path: Path = _REGISTRY_PATH) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    registry: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        match = _REGISTRY_ROW.match(line.strip())
        if not match:
            continue
        command, coverage, verification = match.groups()
        registry[_normalize_command(command)] = {
            'coverage': coverage.strip().lower(),
            'verification': verification.strip(),
        }
    return registry


def _registry_match(
    command: str,
    registry: dict[str, dict[str, str]],
) -> tuple[str, dict[str, str]] | None:
    best: tuple[str, dict[str, str]] | None = None
    for prefix, entry in registry.items():
        if (command == prefix or command.startswith(f'{prefix} ')) and (
            best is None or len(prefix) > len(best[0])
        ):
            best = (prefix, entry)
    return best


def generate_command_snippet_inventory(
    *,
    repo_root: Path = _REPO_ROOT,
    output_path: Path = _DEFAULT_OUTPUT,
) -> str:
    snippets: list[CommandSnippet] = []
    for path in _GUIDE_PATHS:
        rel = path.relative_to(repo_root)
        snippets.extend(_extract_snippets(repo_root / rel))
    snippets = _dedupe_snippets(snippets)
    registry = load_registry(repo_root / _REGISTRY_PATH.relative_to(_REPO_ROOT))

    lines = [
        '# Command Snippet Inventory (Generated)',
        '',
        '> **Not current truth.** Coverage labels come from '
        '[command-snippet-registry.md](../governance/command-snippet-registry.md).',
        '',
        f'**Snippets found:** {len(snippets)}',
        '',
        'Regenerate: `python3 scripts/generate_command_snippet_inventory.py`',
        '',
        '| Command | Source | Coverage | Verification |',
        '| --- | --- | --- | --- |',
    ]
    for snippet in snippets:
        matched = _registry_match(snippet.command, registry)
        if matched:
            _, entry = matched
            coverage = entry['coverage']
            verification = entry['verification']
        else:
            coverage = 'unregistered'
            verification = 'Add prefix to command-snippet-registry.md'
        digest = hashlib.sha256(snippet.command.encode('utf-8')).hexdigest()[:8]
        source = f'`{snippet.source}:{snippet.line_hint}` ({digest})'
        lines.append(
            f'| `{snippet.command}` | {source} | {coverage} | {verification} |'
        )
    lines.append('')
    return '\n'.join(lines)


def write_command_snippet_inventory(
    *,
    repo_root: Path = _REPO_ROOT,
    output_path: Path = _DEFAULT_OUTPUT,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        generate_command_snippet_inventory(
            repo_root=repo_root, output_path=output_path
        ),
        encoding='utf-8',
    )
    return output_path


def check_command_snippet_inventory(
    *,
    repo_root: Path = _REPO_ROOT,
    output_path: Path = _DEFAULT_OUTPUT,
    registry_path: Path = _REGISTRY_PATH,
) -> list[str]:
    errors: list[str] = []
    if not output_path.is_file():
        errors.append(
            f'missing generated inventory: {output_path}; '
            'run python3 scripts/generate_command_snippet_inventory.py'
        )
        return errors

    expected = generate_command_snippet_inventory(
        repo_root=repo_root,
        output_path=output_path,
    )
    actual = output_path.read_text(encoding='utf-8')
    if actual != expected:
        errors.append(
            'docs/generated/command-snippet-inventory.md is out of date; '
            'run: python3 scripts/generate_command_snippet_inventory.py'
        )

    registry = load_registry(registry_path)
    snippets = _dedupe_snippets(
        [snippet for path in _GUIDE_PATHS for snippet in _extract_snippets(path)]
    )
    missing = [
        snippet.command
        for snippet in snippets
        if _registry_match(snippet.command, registry) is None
    ]
    if missing:
        preview = ', '.join(f'`{cmd}`' for cmd in missing[:5])
        suffix = ' ...' if len(missing) > 5 else ''
        errors.append(
            f'{len(missing)} guide command snippet(s) missing from '
            f'command-snippet-registry.md: {preview}{suffix}'
        )

    for command, entry in registry.items():
        if entry['coverage'] == 'smoke' and entry['verification'].lower() in {
            '',
            'tbd',
            'manual',
        }:
            errors.append(
                f'Smoke-marked registry command `{command}` lacks a verification path.'
            )
        if entry['coverage'] == 'smoke':
            verify_path = entry['verification'].strip('` ')
            candidate = repo_root / verify_path
            if not candidate.is_file():
                errors.append(
                    f'Smoke registry command `{command}` points to missing test '
                    f'{verify_path}.'
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate command snippet inventory.')
    parser.add_argument('--root', default='.', help='Repository root.')
    parser.add_argument(
        '--output',
        default=str(_DEFAULT_OUTPUT.relative_to(_REPO_ROOT)),
        help='Markdown output path.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Verify generated inventory and registry coverage.',
    )
    args = parser.parse_args()
    repo_root = Path(args.root).resolve()
    output_path = (repo_root / args.output).resolve()
    registry_path = repo_root / _REGISTRY_PATH.relative_to(_REPO_ROOT)

    if args.check:
        errors = check_command_snippet_inventory(
            repo_root=repo_root,
            output_path=output_path,
            registry_path=registry_path,
        )
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print('Command snippet inventory check passed.')
        return 0

    write_command_snippet_inventory(repo_root=repo_root, output_path=output_path)
    print(f'Wrote {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
