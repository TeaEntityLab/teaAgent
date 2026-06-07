from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any


def iter_sse_data_lines(lines: Iterator[bytes | str]) -> Iterator[str]:
    for raw_line in lines:
        line = (
            raw_line.decode('utf-8', errors='replace').strip()
            if isinstance(raw_line, bytes)
            else str(raw_line).strip()
        )
        if line.startswith('data: '):
            data = line[6:]
            if data == '[DONE]':
                break
            yield data


def consume_sse_json_chunks(
    lines: Iterator[bytes | str],
    *,
    on_data: Callable[[dict[str, Any]], None],
) -> None:
    try:
        for data in iter_sse_data_lines(lines):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
            on_data(parsed)
    finally:
        if hasattr(lines, 'close'):
            lines.close()
