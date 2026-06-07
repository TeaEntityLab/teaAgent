#!/usr/bin/env python3
"""Detect module-level circular imports in the teaagent package.

Intended as a CI/pre-commit gate.  Only considers import-from statements at
module level (not inside function/class bodies) and outside `if TYPE_CHECKING:`
blocks.  Exits 0 on clean graph; exits 1 with cycle details otherwise.

Usage: python3 scripts/check_circular_imports.py [--json]
"""

from __future__ import annotations

import ast
import os
import sys
from collections import defaultdict
from pathlib import Path


def module_level_imports(filepath: Path) -> list[str]:
    """Return teaagent.* module-level imports (filtering TYPE_CHECKING blocks)."""
    with open(filepath) as f:
        try:
            tree = ast.parse(f.read(), filename=str(filepath))
        except SyntaxError:
            return []

    result: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not node.module:
            continue
        if not node.module.startswith('teaagent.'):
            continue

        # Skip imports under ``if TYPE_CHECKING:``
        under_tc = False
        for p in ast.walk(tree):
            for child in ast.iter_child_nodes(p):
                if child is node and isinstance(p, ast.If):
                    if isinstance(p.test, ast.Name) and p.test.id == 'TYPE_CHECKING':
                        under_tc = True
                    break
        if not under_tc:
            result.append(node.module)

    return result


def build_graph(package_root: str) -> dict[str, set[str]]:
    """Build a directed adjacency graph of teaagent modules.

    Returns: {module_name: set of module_names it depends on}
    """
    graph: dict[str, set[str]] = defaultdict(set)
    for root, _dirs, files in os.walk(package_root):
        for f in files:
            if f.endswith('.py'):
                path = Path(root) / f
                modname = (
                    str(path.relative_to(Path(package_root).parent))
                    .replace('/', '.')
                    .replace('.py', '')
                )
                for imp in module_level_imports(path):
                    graph[modname].add(imp)
    return dict(graph)


def find_cycles(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Return all unique simple cycles via DFS colouring."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    for node in graph:
        if node not in color:
            color[node] = WHITE
        for dep in graph[node]:
            if dep not in color:
                color[dep] = WHITE

    all_cycles: list[tuple[str, ...]] = []

    def dfs(node: str, path: list[str]) -> list[tuple[str, ...]]:
        if color.get(node, WHITE) == GRAY:
            idx = path.index(node)
            return [tuple(path[idx:] + [node])]
        if color.get(node, WHITE) == BLACK:
            return []
        color[node] = GRAY
        path.append(node)
        result: list[tuple[str, ...]] = []
        for dep in graph.get(node, set()):
            result.extend(dfs(dep, path))
        path.pop()
        color[node] = BLACK
        return result

    for node in sorted(graph.keys()):
        if color.get(node, WHITE) == WHITE:
            all_cycles.extend(dfs(node, []))

    # Deduplicate rotated representations
    seen: set[tuple[str, ...]] = set()
    unique: list[tuple[str, ...]] = []
    for c in all_cycles:
        for i in range(len(c) - 1):
            rot = c[i:] + c[1 : i + 1]
            if rot in seen:
                break
        else:
            seen.add(c)
            unique.append(c)
    return unique


def main() -> int:
    json_output = '--json' in sys.argv
    package_root = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'teaagent'
    )

    graph = build_graph(package_root)
    cycles = find_cycles(graph)

    if not cycles:
        if json_output:
            print('{"status":"ok","cycles":0}')
        else:
            print('✓ No module-level circular imports detected.')
        return 0

    if json_output:
        import json as _json

        payload = {
            'status': 'cycles_found',
            'cycles': [{'cycle': list(c), 'length': len(c) - 1} for c in cycles],
        }
        print(_json.dumps(payload, indent=2))
    else:
        print(f'✗ Found {len(cycles)} module-level circular import(s):')
        for i, cycle in enumerate(cycles, 1):
            print(f'  Cycle {i}: {" → ".join(cycle)}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
