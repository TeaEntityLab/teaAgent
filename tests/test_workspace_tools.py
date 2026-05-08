from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from teaagent import build_workspace_tool_registry
from teaagent.cli import main
from teaagent.errors import ToolExecutionError


class WorkspaceToolTests(unittest.TestCase):
    def test_read_list_search_and_patch_workspace_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'hello.txt').write_text('hello world\n', encoding='utf-8')
            registry = build_workspace_tool_registry(root)

            listed = registry.execute('workspace_list_files', {'pattern': 'src/*.txt'})
            read = registry.execute('workspace_read_file', {'path': 'src/hello.txt'})
            searched = registry.execute(
                'workspace_search_text', {'pattern': 'hello', 'include': 'src/*.txt'}
            )
            patched = registry.execute(
                'workspace_apply_patch',
                {'path': 'src/hello.txt', 'old': 'hello', 'new': 'hi'},
            )

            self.assertEqual(listed['files'], ['src/hello.txt'])
            self.assertEqual(read['content'], 'hello world\n')
            self.assertEqual(searched['matches'][0]['line'], 1)
            self.assertEqual(patched['replacements'], 1)
            self.assertEqual(
                (root / 'src' / 'hello.txt').read_text(encoding='utf-8'), 'hi world\n'
            )

    def test_hash_anchored_read_and_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'note.txt').write_text('alpha\nbeta\n', encoding='utf-8')
            registry = build_workspace_tool_registry(root)

            hashed = registry.execute(
                'workspace_read_file_hashed', {'path': 'note.txt'}
            )
            first_line = hashed['content'].splitlines()[0]
            line_anchor, text = first_line.split('|', 1)
            line_number, hash_value = line_anchor.split('#', 1)
            edited = registry.execute(
                'workspace_edit_at_hash',
                {
                    'path': 'note.txt',
                    'line': int(line_number),
                    'hash': hash_value,
                    'old': text,
                    'new': 'ALPHA',
                },
            )

            self.assertEqual(edited['line'], 1)
            self.assertEqual(
                (root / 'note.txt').read_text(encoding='utf-8'), 'ALPHA\nbeta\n'
            )

    def test_hash_edit_rejects_stale_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'note.txt').write_text('alpha\n', encoding='utf-8')
            registry = build_workspace_tool_registry(root)

            with self.assertRaises(ToolExecutionError):
                registry.execute(
                    'workspace_edit_at_hash',
                    {
                        'path': 'note.txt',
                        'line': 1,
                        'hash': '00',
                        'old': 'alpha',
                        'new': 'x',
                    },
                )

    def test_write_file_can_create_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            result = registry.execute(
                'workspace_write_file',
                {'path': 'nested/file.txt', 'content': 'ok', 'create_dirs': True},
            )

            self.assertEqual(result['bytes_written'], 2)
            self.assertEqual(
                (Path(tmp) / 'nested' / 'file.txt').read_text(encoding='utf-8'), 'ok'
            )

    def test_path_escape_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError):
                registry.execute('workspace_read_file', {'path': '../outside.txt'})

    def test_read_file_rejects_negative_max_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'file.txt').write_text('content', encoding='utf-8')
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute(
                    'workspace_read_file', {'path': 'file.txt', 'max_bytes': -1}
                )
            self.assertIn('max_bytes', str(ctx.exception))

    def test_shell_and_git_status_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            shell = registry.execute(
                'workspace_run_shell_inspect', {'command': 'pwd', 'timeout_seconds': 5}
            )
            status = registry.execute('workspace_git_status', {})

            self.assertEqual(shell['exit_code'], 0)
            self.assertIn(tmp, shell['stdout'])
            self.assertIsInstance(status['exit_code'], int)

    def test_shell_inspect_uses_quoted_arguments_without_shell_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'literal $HOME.txt'
            path.write_text('ok', encoding='utf-8')
            registry = build_workspace_tool_registry(tmp)

            result = registry.execute(
                'workspace_run_shell_inspect',
                {'command': "cat 'literal $HOME.txt'", 'timeout_seconds': 5},
            )

            self.assertEqual(result['exit_code'], 0)
            self.assertEqual(result['stdout'], 'ok')

    def test_shell_inspect_rejects_mutating_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError):
                registry.execute(
                    'workspace_run_shell_inspect', {'command': 'touch x.txt'}
                )

    def test_shell_inspect_rejects_workspace_escape_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError):
                registry.execute(
                    'workspace_run_shell_inspect', {'command': 'cat /etc/passwd'}
                )

            with self.assertRaises(ToolExecutionError):
                registry.execute(
                    'workspace_run_shell_inspect', {'command': 'cat ../outside.txt'}
                )

    def test_shell_inspect_rejects_unbalanced_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError):
                registry.execute(
                    'workspace_run_shell_inspect', {'command': "cat 'unterminated"}
                )

    def test_shell_inspect_rejects_non_positive_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute(
                    'workspace_run_shell_inspect',
                    {'command': 'pwd', 'timeout_seconds': 0},
                )
            self.assertIn('timeout_seconds', str(ctx.exception))

    def test_cli_workspace_tools_outputs_metadata(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(['workspace', 'tools'])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn('workspace_read_file', {tool['name'] for tool in payload})

    def test_apply_patch_rejects_missing_old_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'file.txt').write_text('content', encoding='utf-8')
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError):
                registry.execute(
                    'workspace_apply_patch',
                    {'path': 'file.txt', 'old': 'nonexistent', 'new': 'x'},
                )

    def test_edit_at_hash_rejects_line_out_of_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'file.txt').write_text('line1\n', encoding='utf-8')
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError):
                registry.execute(
                    'workspace_edit_at_hash',
                    {
                        'path': 'file.txt',
                        'line': 99,
                        'hash': 'abc',
                        'old': 'line1',
                        'new': 'x',
                    },
                )

    def test_list_files_truncates_when_limit_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(5):
                (Path(tmp) / f'file_{i}.txt').write_text('x', encoding='utf-8')
            registry = build_workspace_tool_registry(tmp)

            result = registry.execute(
                'workspace_list_files', {'pattern': '*.txt', 'limit': 2}
            )
            self.assertEqual(len(result['files']), 2)
            self.assertTrue(result['truncated'])

    def test_list_files_rejects_non_positive_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute(
                    'workspace_list_files', {'pattern': '*.txt', 'limit': 0}
                )
            self.assertIn('limit', str(ctx.exception))

    def test_search_text_truncates_when_limit_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(5):
                (Path(tmp) / f'f_{i}.txt').write_text(
                    'searchable\n' * 3, encoding='utf-8'
                )
            registry = build_workspace_tool_registry(tmp)

            result = registry.execute(
                'workspace_search_text', {'pattern': 'searchable', 'limit': 5}
            )
            self.assertEqual(len(result['matches']), 5)
            self.assertTrue(result['truncated'])

    def test_search_text_rejects_non_positive_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute('workspace_search_text', {'pattern': 'x', 'limit': 0})
            self.assertIn('limit', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
