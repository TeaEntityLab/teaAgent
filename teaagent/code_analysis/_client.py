from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from teaagent.code_analysis._types import CodeReference, LSPClient, LSPServerConfig


class StdioLSPClient(LSPClient):
    def __init__(
        self,
        config: LSPServerConfig,
        *,
        timeout_seconds: float = 10.0,
        popen_factory: Optional[Callable[..., subprocess.Popen[bytes]]] = None,
    ) -> None:
        self._config = config
        self._timeout_seconds = timeout_seconds
        self._popen_factory = popen_factory or subprocess.Popen
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._request_id = 0

    def initialize(self, root_uri: str) -> None:
        self._ensure_proc()
        self._request(
            'initialize',
            {
                'processId': None,
                'rootUri': root_uri,
                'capabilities': {},
                'initializationOptions': self._config.initialization_options,
            },
        )
        self._notify('initialized', {})

    def shutdown(self) -> None:
        if self._proc is None:
            return
        try:
            self._request('shutdown', {})
            self._notify('exit', {})
        except Exception:
            pass
        proc = self._proc
        self._proc = None
        if proc.poll() is None:
            proc.terminate()

    def goto_definition(self, path: str, line: int, col: int) -> list[CodeReference]:
        result = self._request(
            'textDocument/definition', self._position_params(path, line, col)
        )
        return _to_references(result)

    def find_references(self, path: str, line: int, col: int) -> list[CodeReference]:
        result = self._request(
            'textDocument/references',
            {
                **self._position_params(path, line, col),
                'context': {'includeDeclaration': True},
            },
        )
        return _to_references(result)

    def hover(self, path: str, line: int, col: int) -> Optional[str]:
        result = self._request(
            'textDocument/hover', self._position_params(path, line, col)
        )
        if not isinstance(result, dict):
            return None
        contents = result.get('contents')
        if isinstance(contents, str):
            return contents
        if isinstance(contents, dict):
            value = contents.get('value')
            return value if isinstance(value, str) else None
        if isinstance(contents, list):
            parts = []
            for item in contents:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get('value'), str):
                    parts.append(item['value'])
            return '\n'.join(parts) if parts else None
        return None

    def document_diagnostics(self, path: str) -> list[dict[str, Any]]:
        # Pull diagnostics via pull model where available.
        result = self._request(
            'textDocument/diagnostic',
            {'textDocument': {'uri': _to_uri(path)}},
        )
        if not isinstance(result, dict):
            return []
        items = result.get('items')
        return items if isinstance(items, list) else []

    def document_symbols(self, path: str) -> list[CodeReference]:
        result = self._request(
            'textDocument/documentSymbol', {'textDocument': {'uri': _to_uri(path)}}
        )
        refs: list[CodeReference] = []
        if not isinstance(result, list):
            return refs
        for item in result:
            if not isinstance(item, dict):
                continue
            name = item.get('name')
            if not isinstance(name, str):
                continue
            loc = (
                item.get('location') if isinstance(item.get('location'), dict) else None
            )
            if loc is None:
                rng = item.get('range')
                line, col = _extract_line_col(rng)
                refs.append(
                    CodeReference(
                        symbol=name,
                        file_path=path,
                        line=line,
                        column=col,
                        kind=str(item.get('kind', 'symbol')),
                        detail=str(item.get('detail', '')),
                    )
                )
                continue
            uri = loc.get('uri') if isinstance(loc.get('uri'), str) else _to_uri(path)
            line, col = _extract_line_col(loc.get('range'))
            refs.append(
                CodeReference(
                    symbol=name,
                    file_path=_from_uri(uri),
                    line=line,
                    column=col,
                    kind=str(item.get('kind', 'symbol')),
                    detail=str(item.get('detail', '')),
                )
            )
        return refs

    def _ensure_proc(self) -> None:
        if self._proc is not None:
            return
        self._proc = self._popen_factory(
            self._config.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=(self._config.env or None),
        )

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        self._ensure_proc()
        assert self._proc is not None
        self._request_id += 1
        req_id = self._request_id
        payload = {'jsonrpc': '2.0', 'id': req_id, 'method': method, 'params': params}
        self._write_payload(payload)
        while True:
            msg = self._read_payload()
            if not isinstance(msg, dict):
                continue
            if msg.get('id') == req_id:
                if 'error' in msg:
                    raise RuntimeError(f'LSP error for {method}: {msg["error"]}')
                return msg.get('result')

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._ensure_proc()
        payload = {'jsonrpc': '2.0', 'method': method, 'params': params}
        self._write_payload(payload)

    def _write_payload(self, payload: dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        body = json.dumps(payload).encode('utf-8')
        header = f'Content-Length: {len(body)}\r\n\r\n'.encode('ascii')
        self._proc.stdin.write(header + body)
        self._proc.stdin.flush()

    def _read_payload(self) -> dict[str, Any]:
        assert self._proc is not None and self._proc.stdout is not None
        length = _read_content_length(self._proc.stdout)
        body = self._proc.stdout.read(length)
        if not body:
            raise RuntimeError('LSP process closed stdout')
        return json.loads(body.decode('utf-8'))

    @staticmethod
    def _position_params(path: str, line: int, col: int) -> dict[str, Any]:
        return {
            'textDocument': {'uri': _to_uri(path)},
            'position': {'line': max(line - 1, 0), 'character': max(col - 1, 0)},
        }


def _read_content_length(stream: Any) -> int:
    length: Optional[int] = None
    while True:
        line = stream.readline()
        if not line:
            raise RuntimeError('LSP process closed before header completed')
        if line in {b'\r\n', b'\n'}:
            break
        lower = line.decode('ascii', errors='ignore').lower()
        if lower.startswith('content-length:'):
            raw = lower.split(':', 1)[1].strip()
            length = int(raw)
    if length is None:
        raise RuntimeError('missing Content-Length header in LSP response')
    return length


def _to_uri(path: str) -> str:
    p = Path(path)
    if p.is_absolute():
        return p.as_uri()
    return Path(path).resolve().as_uri()


def _from_uri(uri: str) -> str:
    if uri.startswith('file://'):
        return uri[7:]
    return uri


def _extract_line_col(range_obj: Any) -> tuple[int, int]:
    if not isinstance(range_obj, dict):
        return (1, 1)
    start = range_obj.get('start')
    if not isinstance(start, dict):
        return (1, 1)
    line = int(start.get('line', 0)) + 1
    col = int(start.get('character', 0)) + 1
    return (line, col)


def _to_references(result: Any) -> list[CodeReference]:
    refs: list[CodeReference] = []
    locations = result if isinstance(result, list) else ([result] if result else [])
    for item in locations:
        if not isinstance(item, dict):
            continue
        uri = item.get('uri')
        if not isinstance(uri, str):
            continue
        line, col = _extract_line_col(item.get('range'))
        refs.append(
            CodeReference(
                symbol='',
                file_path=_from_uri(uri),
                line=line,
                column=col,
                kind='symbol',
                detail='',
            )
        )
    return refs
