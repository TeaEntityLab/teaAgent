"""AC-NEW-24: External ecosystem compatibility flow.

As a platform engineer, I want representative external MCP/skill artifacts to
work with TeaAgent contracts, including graceful schema-error behavior.

Acceptance criteria:
- External MCP tool manifests with extra annotations are registered and callable.
- Invalid external schema declarations fail with a clear validation error.
- Skill packages with extra metadata files still load SKILL.md content.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

from teaagent.errors import ToolValidationError
from teaagent.mcp_tool_adapter import register_mcp_tools
from teaagent.skill_loader import load_skills
from teaagent.tools import ToolRegistry

_EXTERNAL_TOOLS = [
    {
        "name": "community_read_docs",
        "description": "Read project docs from an external package.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "vendorHint": "community",
        },
    },
    {
        "name": "community_bad_schema",
        "description": "Intentionally invalid schema from third-party manifest.",
        "input_schema": {
            "type": "object",
            "properties": {"payload": {"type": "unknown-type"}},
        },
        "annotations": {"destructiveHint": False},
    },
]


class _ExternalMCPHandler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        method = body.get("method", "")

        if method == "initialize":
            response = {"jsonrpc": "2.0", "id": body.get("id"), "result": {}}
            session_id = "sess-ext-1"
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"tools": _EXTERNAL_TOOLS},
            }
            session_id = self.headers.get("Mcp-Session-Id", "sess-ext-1")
        elif method == "tools/call":
            tool_name = body.get("params", {}).get("name", "")
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "content": [{"type": "text", "text": f"ok:{tool_name}"}],
                    "isError": False,
                },
            }
            session_id = self.headers.get("Mcp-Session-Id", "sess-ext-1")
        else:
            self.send_response(404)
            self.end_headers()
            return

        raw = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Mcp-Session-Id", session_id)
        self.end_headers()
        self.wfile.write(raw)

    def do_DELETE(self) -> None:
        self.send_response(204)
        self.end_headers()


def _start_external_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _ExternalMCPHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}/mcp"


def test_external_mcp_manifest_annotations_and_schema_errors() -> None:
    server, endpoint = _start_external_server()
    try:
        registry = ToolRegistry()
        names = register_mcp_tools(registry, endpoint=endpoint)

        assert set(names) == {"community_read_docs", "community_bad_schema"}
        assert registry.get("community_read_docs").annotations.read_only is True
        assert registry.get("community_read_docs").annotations.destructive is False

        ok = registry.execute("community_read_docs", {"path": "README.md"})
        assert ok["isError"] is False
        assert ok["content"][0]["text"] == "ok:community_read_docs"

        try:
            registry.execute("community_bad_schema", {"payload": "x"})
            raise AssertionError("expected ToolValidationError for invalid external schema")
        except ToolValidationError as exc:
            assert "Unsupported schema type" in str(exc)
    finally:
        server.shutdown()


def test_external_skill_package_with_extra_metadata_loads(tmp_path: Path) -> None:
    skill_dir = tmp_path / ".opencode" / "skill" / "community-style-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "# Community Skill\nPrefer deterministic checks.\n", encoding="utf-8"
    )
    (skill_dir / "metadata.json").write_text(
        json.dumps({"vendor": "community", "version": "1.0.0"}), encoding="utf-8"
    )
    (skill_dir / "README.md").write_text("extra metadata docs", encoding="utf-8")

    with patch("teaagent.skill_loader._USER_SKILL_DIR", tmp_path / ".missing-skills"):
        skills = load_skills(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "community-style-skill"
    assert "Prefer deterministic checks" in skills[0].content
