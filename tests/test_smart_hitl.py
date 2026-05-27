from __future__ import annotations

import tempfile
import io
from pathlib import Path
from unittest.mock import patch

from teaagent.runner import ApprovalRequest
from teaagent.cli._handlers._agent import make_cli_approval_handler
from teaagent.ergonomics.approval_store import ApprovalPresetStore


def test_smart_hitl_approval_y() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        request = ApprovalRequest(
            tool_name="workspace_write_file",
            call_id="c1",
            arguments={"path": "src/foo.py"},
            reason="",
            annotations={},
        )
        with patch("builtins.input", return_value="y"), patch("sys.stderr", new_callable=io.StringIO):
            handler = make_cli_approval_handler(tmp, permission_mode="prompt")
            assert handler(request) is True


def test_smart_hitl_approval_p() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        request = ApprovalRequest(
            tool_name="workspace_write_file",
            call_id="c2",
            arguments={"path": "src/foo.py"},
            reason="",
            annotations={},
        )
        with patch("builtins.input", return_value="p"), patch("sys.stderr", new_callable=io.StringIO):
            handler = make_cli_approval_handler(tmp, permission_mode="prompt")
            assert handler(request) is True

        store = ApprovalPresetStore(tmp, readonly=True)
        grants = store.list_grants()
        assert len(grants) == 1
        assert grants[0].tool_name == "workspace_write_file"
        assert list(grants[0].path_globs) == ["src/foo.py"]
        assert grants[0].scope == "session"


def test_smart_hitl_approval_t() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        request = ApprovalRequest(
            tool_name="workspace_write_file",
            call_id="c3",
            arguments={"path": "src/foo.py"},
            reason="",
            annotations={},
        )
        with patch("builtins.input", return_value="t"), patch("sys.stderr", new_callable=io.StringIO):
            handler = make_cli_approval_handler(tmp, permission_mode="prompt")
            assert handler(request) is True

        store = ApprovalPresetStore(tmp, readonly=True)
        grants = store.list_grants()
        assert len(grants) == 1
        assert grants[0].tool_name == "workspace_write_file"
        assert not grants[0].path_globs
        assert grants[0].scope == "session"
