#!/usr/bin/env python3
"""Generate a test stub for a teaagent module."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def module_to_path(module: str) -> Path:
    parts = module.split('.')
    if parts[0] != 'teaagent':
        raise ValueError('module must start with teaagent.')
    rel = Path(*parts[1:]).with_suffix('.py')
    return Path('teaagent') / rel


def test_path_for(module: str) -> Path:
    name = module.replace('teaagent.', '').replace('.', '_')
    return Path('tests') / f'test_{name}.py'


def render_stub(module: str, source: Path) -> str:
    pkg = module.rsplit('.', 1)[0] if module.count('.') > 1 else module
    return f'''"""Tests for {module}."""

from __future__ import annotations


def test_module_imports():
    """Smoke test: module is importable."""
    __import__("{pkg}")


def test_placeholder():
    """Replace with behavior tests for {source.name}."""
    assert True
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('module', help='Module path, e.g. teaagent.health')
    parser.add_argument('--force', action='store_true', help='Overwrite existing file')
    args = parser.parse_args(argv)

    source = module_to_path(args.module)
    if not source.is_file():
        print(f'error: source not found: {source}', file=sys.stderr)
        return 1

    dest = test_path_for(args.module)
    if dest.exists() and not args.force:
        print(f'error: {dest} already exists (use --force)', file=sys.stderr)
        return 1

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_stub(args.module, source), encoding='utf-8')
    print(f'wrote {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
