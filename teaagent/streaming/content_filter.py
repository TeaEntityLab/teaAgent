from __future__ import annotations

import re
from collections.abc import Callable

_FINAL_TYPE_RE = re.compile(r'"type"\s*:\s*"final"')
_CONTENT_KEY_RE = re.compile(r'"content"\s*:\s*"')


def _decode_json_string_prefix(raw: str) -> tuple[str, int]:
    """Decode a partial JSON string value; return (text, bytes consumed in raw)."""
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == '"':
            break
        if ch != '\\':
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(raw):
            break
        esc = raw[i + 1]
        mapping = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\'}
        out.append(mapping.get(esc, esc))
        i += 2
    return ''.join(out), i


class DecisionContentStreamer:
    """Forward only user-visible ``content`` text from streamed decision JSON."""

    def __init__(self, sink: Callable[[str], None]) -> None:
        self._sink = sink
        self._buffer = ''
        self._emitted = 0
        self._content_start: int | None = None

    def feed(self, chunk: str) -> None:
        if not chunk:
            return
        self._buffer += chunk
        if self._content_start is None:
            if not _FINAL_TYPE_RE.search(self._buffer):
                return
            match = _CONTENT_KEY_RE.search(self._buffer)
            if not match:
                return
            self._content_start = match.end()
        raw = self._buffer[self._content_start :]
        decoded, _consumed = _decode_json_string_prefix(raw)
        if len(decoded) > self._emitted:
            delta = decoded[self._emitted :]
            self._emitted = len(decoded)
            if delta:
                self._sink(delta)
