from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from teaagent import build_workspace_tool_registry
from teaagent.cli import main


class WorkspaceToolTests(unittest.TestCase):
    def test_read_list_search_and_patch_workspace_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "hello.txt").write_text("hello world\n", encoding="utf-8")
            registry = build_workspace_tool_registry(root)

            listed = registry.execute("workspace_list_files", {"pattern": "src/*.txt"})
            read = registry.execute("workspace_read_file", {"path": "src/hello.txt"})
            searched = registry.execute("workspace_search_text", {"pattern": "hello", "include": "src/*.txt"})
            patched = registry.execute(
                "workspace_apply_patch",
                {"path": "src/hello.txt", "old": "hello", "new": "hi"},
            )

            self.assertEqual(listed["files"], ["src/hello.txt"])
            self.assertEqual(read["content"], "hello world\n")
            self.assertEqual(searched["matches"][0]["line"], 1)
            self.assertEqual(patched["replacements"], 1)
            self.assertEqual((root / "src" / "hello.txt").read_text(encoding="utf-8"), "hi world\n")

    def test_write_file_can_create_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            result = registry.execute(
                "workspace_write_file",
                {"path": "nested/file.txt", "content": "ok", "create_dirs": True},
            )

            self.assertEqual(result["bytes_written"], 2)
            self.assertEqual((Path(tmp) / "nested" / "file.txt").read_text(encoding="utf-8"), "ok")

    def test_path_escape_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(Exception):
                registry.execute("workspace_read_file", {"path": "../outside.txt"})

    def test_shell_and_git_status_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            shell = registry.execute("workspace_run_shell", {"command": "pwd", "timeout_seconds": 5})
            status = registry.execute("workspace_git_status", {})

            self.assertEqual(shell["exit_code"], 0)
            self.assertIn(tmp, shell["stdout"])
            self.assertIsInstance(status["exit_code"], int)

    def test_cli_workspace_tools_outputs_metadata(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["workspace", "tools"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn("workspace_read_file", {tool["name"] for tool in payload})


if __name__ == "__main__":
    unittest.main()
