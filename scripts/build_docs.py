from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def build_docs(output_dir: str = 'site') -> int:
    repo_root = Path(__file__).resolve().parent.parent
    out = repo_root / output_dir

    cmd = [
        sys.executable,
        '-m',
        'pdoc',
        '--html',
        '--output-dir',
        str(out),
        '--force',
        'teaagent',
        'teaagent.cli',
        'teaagent.graph_rag',
        'teaagent.graphqlite_store',
        'teaagent.graphqlite_production',
        'teaagent.schema_migration',
        'teaagent.rag',
        'teaagent.agentcard',
        'teaagent.openapi',
        'teaagent.budget',
        'teaagent.policy',
        'teaagent.tools',
        'teaagent.errors',
        'teaagent.audit',
        'teaagent.audit_viewer',
        'teaagent.llm',
        'teaagent.llm_conformance',
        'teaagent.managed_runtime',
        'teaagent.eval',
        'teaagent.intent',
        'teaagent.memory',
        'teaagent.mcp_http',
        'teaagent.code_mode',
        'teaagent.run_store',
        'teaagent.ultrawork',
        'teaagent.workspace_tools',
        'teaagent.oauth21',
        'teaagent.telemetry',
        'teaagent.context',
        'teaagent.heartbeat',
        'teaagent.aibom',
        'teaagent.checkpoint',
        'teaagent.runner',
        'teaagent.tui',
    ]

    result = subprocess.run(cmd, cwd=str(repo_root))
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Build TeaAgent API reference documentation.'
    )
    parser.add_argument(
        '--output-dir',
        default='site',
        help='Output directory for generated HTML. Defaults to site/.',
    )
    args = parser.parse_args()
    return build_docs(args.output_dir)


if __name__ == '__main__':
    raise SystemExit(main())
