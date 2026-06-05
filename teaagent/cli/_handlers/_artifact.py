from __future__ import annotations

import argparse
import json
from pathlib import Path

from teaagent.long_result_envelope import readback_artifact


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def artifact_read_command(args: argparse.Namespace) -> int:
    try:
        content = readback_artifact(
            Path(args.root),
            args.artifact_path,
            cursor=args.cursor,
            max_bytes=args.max_bytes,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        _print_json({'ok': False, 'error': str(exc)})
        return 1
    print(content)
    return 0


def artifact_list_command(args: argparse.Namespace) -> int:
    artifact_dir = Path(args.root) / '.teaagent' / 'artifacts' / 'tool-results'
    if not artifact_dir.is_dir():
        _print_json({})
        return 0

    runs: dict[str, list[dict[str, object]]] = {}
    for run_dir in sorted(artifact_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        run_id = run_dir.name
        files = []
        for artifact_file in sorted(run_dir.iterdir()):
            if not artifact_file.is_file():
                continue
            tool_call_id = artifact_file.stem
            try:
                size = artifact_file.stat().st_size
            except OSError:
                size = 0
            files.append(
                {
                    'tool_call_id': tool_call_id,
                    'path': str(artifact_file.relative_to(Path(args.root))),
                    'bytes': size,
                }
            )
        if files:
            runs[run_id] = files

    _print_json(runs)
    return 0
