from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from teaagent import (
    ToolRegistry,
    WorkspaceToolConfig,
    build_workspace_tool_registry,
    register_code_parse_backend,
    register_hybrid_backend,
    register_knowledge_backend,
    register_workspace_tools,
)
from teaagent.cli import main
from teaagent.errors import ToolExecutionError
from teaagent.workspace_tools import classify_shell_command_policy


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

    def test_write_file_rejects_oversized_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ToolRegistry()
            register_workspace_tools(
                registry,
                WorkspaceToolConfig(root=Path(tmp).resolve(), max_write_bytes=3),
            )

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute(
                    'workspace_write_file', {'path': 'big.txt', 'content': 'abcd'}
                )

            self.assertIn('max_write_bytes', str(ctx.exception))
            self.assertFalse((Path(tmp) / 'big.txt').exists())

    def test_apply_patch_rejects_oversized_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'file.txt').write_text('a', encoding='utf-8')
            registry = ToolRegistry()
            register_workspace_tools(
                registry,
                WorkspaceToolConfig(root=root.resolve(), max_write_bytes=3),
            )

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute(
                    'workspace_apply_patch',
                    {'path': 'file.txt', 'old': 'a', 'new': 'abcd'},
                )

            self.assertIn('max_write_bytes', str(ctx.exception))
            self.assertEqual((root / 'file.txt').read_text(encoding='utf-8'), 'a')

    def test_edit_at_hash_rejects_oversized_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'file.txt').write_text('a\n', encoding='utf-8')
            registry = ToolRegistry()
            register_workspace_tools(
                registry,
                WorkspaceToolConfig(root=root.resolve(), max_write_bytes=3),
            )
            hashed = registry.execute(
                'workspace_read_file_hashed', {'path': 'file.txt'}
            )
            line_anchor, text = hashed['content'].splitlines()[0].split('|', 1)
            line_number, hash_value = line_anchor.split('#', 1)

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute(
                    'workspace_edit_at_hash',
                    {
                        'path': 'file.txt',
                        'line': int(line_number),
                        'hash': hash_value,
                        'old': text,
                        'new': 'abcd',
                    },
                )

            self.assertIn('max_write_bytes', str(ctx.exception))
            self.assertEqual((root / 'file.txt').read_text(encoding='utf-8'), 'a\n')

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

    def test_shell_inspect_rejects_timeout_above_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ToolRegistry()
            register_workspace_tools(
                registry,
                WorkspaceToolConfig(
                    root=Path(tmp).resolve(), max_shell_timeout_seconds=2
                ),
            )

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute(
                    'workspace_run_shell_inspect',
                    {'command': 'pwd', 'timeout_seconds': 3},
                )

            self.assertIn('timeout_seconds', str(ctx.exception))

    def test_shell_inspect_rejects_oversized_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ToolRegistry()
            register_workspace_tools(
                registry,
                WorkspaceToolConfig(
                    root=Path(tmp).resolve(), max_shell_command_bytes=3
                ),
            )

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute('workspace_run_shell_inspect', {'command': 'pwd pwd'})

            self.assertIn('max_shell_command_bytes', str(ctx.exception))

    def test_shell_mutate_rejects_timeout_above_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ToolRegistry()
            register_workspace_tools(
                registry,
                WorkspaceToolConfig(
                    root=Path(tmp).resolve(), max_shell_timeout_seconds=2
                ),
            )

            with self.assertRaises(ToolExecutionError) as ctx:
                registry.execute(
                    'workspace_run_shell_mutate',
                    {'command': 'pwd', 'timeout_seconds': 3},
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

    def test_hybrid_index_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'docs').mkdir()
            (root / 'docs' / 'auth.md').write_text(
                'authentication token flow and session refresh', encoding='utf-8'
            )
            (root / 'docs' / 'billing.md').write_text(
                'billing invoice revenue tracking', encoding='utf-8'
            )
            registry = build_workspace_tool_registry(root)

            indexed = registry.execute(
                'workspace_hybrid_index',
                {'include': 'docs/*.md', 'collection': 'kb', 'clear': True},
            )
            searched = registry.execute(
                'workspace_hybrid_search',
                {'query': 'authentication token', 'collection': 'kb', 'limit': 3},
            )

            self.assertEqual(indexed['backend'], 'local')
            self.assertEqual(indexed['indexed'], 2)
            self.assertTrue((root / '.teaagent' / 'hybrid_search.sqlite3').exists())
            self.assertGreaterEqual(len(searched['hits']), 1)
            self.assertEqual(searched['hits'][0]['path'], 'docs/auth.md')

    def test_hybrid_search_supports_custom_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            class FakeBackend:
                def index(
                    self, *, root: Path, args: dict[str, object]
                ) -> dict[str, object]:
                    return {
                        'backend': 'fake',
                        'collection': str(args.get('collection', 'default')),
                        'indexed': 1,
                        'skipped': 0,
                        'include': str(args.get('include', '**/*')),
                        'database': str(root / 'fake.db'),
                    }

                def search(
                    self, *, root: Path, args: dict[str, object]
                ) -> dict[str, object]:
                    return {
                        'backend': 'fake',
                        'collection': str(args.get('collection', 'default')),
                        'query': str(args['query']),
                        'hits': [
                            {
                                'path': 'external://result',
                                'score': 1.0,
                                'lexical_score': 0.0,
                                'vector_score': 1.0,
                                'snippet': 'external backend',
                            }
                        ],
                    }

            register_hybrid_backend('fake', FakeBackend())
            indexed = registry.execute(
                'workspace_hybrid_index',
                {'backend': 'fake', 'collection': 'kb'},
            )
            searched = registry.execute(
                'workspace_hybrid_search',
                {'backend': 'fake', 'query': 'hello', 'collection': 'kb'},
            )

            self.assertEqual(indexed['backend'], 'fake')
            self.assertEqual(searched['backend'], 'fake')
            self.assertEqual(searched['hits'][0]['path'], 'external://result')

    def test_workspace_knowledge_search_auto_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            class PrimaryFail:
                def health(self, *, root: Path):
                    raise RuntimeError('down')

                def index(self, *, root: Path, args: dict[str, object]):
                    raise RuntimeError('down')

                def search(self, *, root: Path, args: dict[str, object]):
                    raise RuntimeError('down')

                def get(self, *, root: Path, args: dict[str, object]):
                    raise RuntimeError('down')

            class FallbackOk:
                def health(self, *, root: Path):
                    return {'ok': True}

                def index(self, *, root: Path, args: dict[str, object]):
                    return {'source': 'fallback', 'op': 'index'}

                def search(self, *, root: Path, args: dict[str, object]):
                    return {'source': 'fallback', 'op': 'search'}

                def get(self, *, root: Path, args: dict[str, object]):
                    return {'source': 'fallback', 'op': 'get'}

            register_knowledge_backend('primary_fail_ws', PrimaryFail())
            register_knowledge_backend('fallback_ok_ws', FallbackOk())

            result = registry.execute(
                'workspace_knowledge_search',
                {
                    'backend': 'auto',
                    'primary_backend': 'primary_fail_ws',
                    'fallback_backend': 'fallback_ok_ws',
                    'query': 'auth',
                },
            )
            payload = result['result']
            self.assertEqual(result['backend'], 'auto')
            self.assertEqual(payload['source'], 'fallback')
            self.assertTrue(payload['fallback_used'])
            self.assertIn('primary_error', payload)

    def test_workspace_code_parse_routes_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            class FakeCodeParse:
                def health(self, *, root: Path):
                    return {'ok': True}

                def overview(self, *, root: Path, args: dict[str, object]):
                    return {'kind': 'overview', 'path': args.get('path')}

                def symbols(self, *, root: Path, args: dict[str, object]):
                    return {'kind': 'symbols', 'name': args.get('name')}

                def definition(self, *, root: Path, args: dict[str, object]):
                    return {'kind': 'definition', 'name': args.get('name')}

                def references(self, *, root: Path, args: dict[str, object]):
                    return {'kind': 'references', 'name': args.get('name')}

            register_code_parse_backend('fake_code_parse_ws', FakeCodeParse())
            result = registry.execute(
                'workspace_code_parse',
                {
                    'backend': 'fake_code_parse_ws',
                    'action': 'definition',
                    'name': 'AuthService.login',
                },
            )

            self.assertEqual(result['backend'], 'fake_code_parse_ws')
            self.assertEqual(result['action'], 'definition')
            self.assertEqual(result['result']['kind'], 'definition')


class GitignoreAndPaginationTests(unittest.TestCase):
    def test_list_files_respects_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'keep.py').write_text('', encoding='utf-8')
            (root / 'src' / 'ignore.js').write_text('', encoding='utf-8')
            (root / 'src' / 'ignore.min.js').write_text('', encoding='utf-8')
            (root / '.gitignore').write_text('*.js\n', encoding='utf-8')
            registry = build_workspace_tool_registry(root)

            result = registry.execute('workspace_list_files', {'pattern': 'src/*'})
            files = result['files']

            self.assertIn('src/keep.py', files)
            self.assertNotIn('src/ignore.js', files)
            self.assertNotIn('src/ignore.min.js', files)

    def test_search_text_respects_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'keep.py').write_text('hello', encoding='utf-8')
            (root / 'src' / 'ignore.log').write_text('hello', encoding='utf-8')
            (root / '.gitignore').write_text('*.log\n', encoding='utf-8')
            registry = build_workspace_tool_registry(root)

            result = registry.execute(
                'workspace_search_text', {'pattern': 'hello', 'include': 'src/*'}
            )
            paths = {m['path'] for m in result['matches']}

            self.assertIn('src/keep.py', paths)
            self.assertNotIn('src/ignore.log', paths)

    def test_list_files_offset_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(5):
                (root / f'file_{i}.txt').write_text('', encoding='utf-8')
            registry = build_workspace_tool_registry(root)

            page1 = registry.execute(
                'workspace_list_files', {'pattern': '*.txt', 'limit': 2, 'offset': 0}
            )
            page2 = registry.execute(
                'workspace_list_files', {'pattern': '*.txt', 'limit': 2, 'offset': 2}
            )
            page3 = registry.execute(
                'workspace_list_files', {'pattern': '*.txt', 'limit': 2, 'offset': 4}
            )

            self.assertEqual(len(page1['files']), 2)
            self.assertEqual(len(page2['files']), 2)
            self.assertEqual(len(page3['files']), 1)
            self.assertTrue(page1['truncated'])
            self.assertTrue(page2['truncated'])
            self.assertFalse(page3['truncated'])

    def test_search_text_offset_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = 'match\n' * 5
            (root / 'data.txt').write_text(content, encoding='utf-8')
            registry = build_workspace_tool_registry(root)

            page1 = registry.execute(
                'workspace_search_text', {'pattern': 'match', 'limit': 2, 'offset': 0}
            )
            page2 = registry.execute(
                'workspace_search_text', {'pattern': 'match', 'limit': 2, 'offset': 2}
            )

            self.assertEqual(len(page1['matches']), 2)
            self.assertEqual(len(page2['matches']), 2)
            self.assertTrue(page1['truncated'])
            self.assertTrue(page2['truncated'])

    def test_agignore_also_respected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'keep.py').write_text('', encoding='utf-8')
            (root / 'skip.secret').write_text('', encoding='utf-8')
            (root / '.agignore').write_text('*.secret\n', encoding='utf-8')
            registry = build_workspace_tool_registry(root)

            result = registry.execute('workspace_list_files', {'pattern': '*'})
            files = result['files']

            self.assertIn('keep.py', files)
            self.assertNotIn('skip.secret', files)


class ShellClassifierPropertyTests(unittest.TestCase):
    INSPECT_COMMANDS = [
        'pwd',
        'ls',
        'ls -la',
        'find . -name "*.py"',
        'rg pattern',
        'rg --glob "*.py" pattern',
        'grep pattern file.txt',
        'grep -r pattern .',
        "git log --grep='>'",
        "git log --grep='|'",
        "git log --grep='&& test'",
        'git status',
        'git diff',
        'git diff --staged',
        'git log',
        'git log --oneline -5',
        'git show HEAD',
        'git branch',
        'git grep pattern',
        'git grep -n pattern -- "*.py"',
        'cat file.txt',
        'cat "file with spaces.txt"',
        'head -20 file.txt',
        'tail file.txt',
        'wc -l file.txt',
    ]

    MUTATE_COMMANDS = [
        'ls >output.txt',
        'ls >>output.txt',
        'cat file < input.txt',
        'echo one | grep two',
        'echo one && echo two',
        'echo one; echo two',
        'touch new.txt',
        'rm file.txt',
        'mkdir dir',
        'mv a.txt b.txt',
        'git checkout -b new-branch',
        'git push',
        'git commit -m "msg"',
        'python3 script.py',
        'npm install',
        'pip install pkg',
        'curl http://example.com',
        'find . -delete',
        'find . -exec rm {} ;',
        'git -c core.pager=sh log',
    ]

    def test_all_inspect_commands_classified_as_inspect(self) -> None:
        for cmd in self.INSPECT_COMMANDS:
            result = classify_shell_command_policy(cmd)
            self.assertEqual(
                result,
                'inspect',
                f'expected {cmd!r} to be inspect, got {result!r}',
            )

    def test_all_mutate_commands_classified_as_mutate(self) -> None:
        for cmd in self.MUTATE_COMMANDS:
            result = classify_shell_command_policy(cmd)
            self.assertEqual(
                result,
                'mutate',
                f'expected {cmd!r} to be mutate, got {result!r}',
            )

    def test_quoted_operators_do_not_trigger_mutate(self) -> None:
        inspect = [
            "grep '>' file.txt",
            "grep '|' file.txt",
            "grep '&&' file.txt",
            "rg ';' .",
            "git log --grep='>'",
            "git log --grep='&& git'",
        ]
        for cmd in inspect:
            self.assertEqual(
                classify_shell_command_policy(cmd),
                'inspect',
                f'quoted operator in {cmd!r} should not trigger mutate',
            )

    def test_actual_redirect_operators_trigger_mutate(self) -> None:
        mutate = [
            'ls > out.txt',
            'ls >> out.txt',
            'cat < /dev/null',
            'ls 2> err.txt',
            'ls &> all.txt',
        ]
        for cmd in mutate:
            self.assertEqual(
                classify_shell_command_policy(cmd),
                'mutate',
                f'actual redirect in {cmd!r} should trigger mutate',
            )

    def test_chained_commands_trigger_mutate(self) -> None:
        mutate = [
            'ls && pwd',
            'ls || pwd',
            'ls | wc',
            'ls ; pwd',
        ]
        for cmd in mutate:
            self.assertEqual(
                classify_shell_command_policy(cmd),
                'mutate',
                f'chain operator in {cmd!r} should trigger mutate',
            )

    def test_command_substitution_trigger_mutate(self) -> None:
        mutate = [
            'echo $(whoami)',
            'echo `whoami`',
        ]
        for cmd in mutate:
            self.assertEqual(
                classify_shell_command_policy(cmd),
                'mutate',
                f'substitution in {cmd!r} should trigger mutate',
            )

    def test_workspace_escape_paths_trigger_mutate(self) -> None:
        mutate = [
            'ls /etc/passwd',
            'cat ~/.ssh/id_rsa',
            'ls ../outside',
            'ls subdir/../../outside',
        ]
        for cmd in mutate:
            self.assertEqual(
                classify_shell_command_policy(cmd),
                'mutate',
                f'escape path in {cmd!r} should trigger mutate',
            )


if __name__ == '__main__':
    unittest.main()
