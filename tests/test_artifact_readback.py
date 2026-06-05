from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


class TestArtifactReadCommand:
    def test_nonexistent_file(self, tmp_path: Path) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(
                [
                    'artifact', 'read',
                    '.teaagent/artifacts/tool-results/nope/nope.txt',
                    '--root', str(tmp_path),
                ]
            )
        assert exit_code == 1
        payload = json.loads(out.getvalue())
        assert payload['ok'] is False
        assert 'error' in payload

    def test_reads_content(self, tmp_path: Path) -> None:
        content = 'hello world artifact content'
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / 'run-001'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = artifact_dir / 'call-001.txt'
        artifact_file.write_text(content, encoding='utf-8')

        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(
                [
                    'artifact', 'read',
                    '.teaagent/artifacts/tool-results/run-001/call-001.txt',
                    '--root', str(tmp_path),
                ]
            )
        assert exit_code == 0
        assert out.getvalue().strip() == content

    def test_with_cursor(self, tmp_path: Path) -> None:
        content = 'abcdefghijklmnopqrstuvwxyz'
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / 'run-001'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = artifact_dir / 'call-offset.txt'
        artifact_file.write_text(content, encoding='utf-8')

        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(
                [
                    'artifact', 'read',
                    '.teaagent/artifacts/tool-results/run-001/call-offset.txt',
                    '--cursor', 'offset:5',
                    '--max-bytes', '10',
                    '--root', str(tmp_path),
                ]
            )
        assert exit_code == 0
        assert out.getvalue().strip() == content[5:15]

    def test_max_bytes_truncation(self, tmp_path: Path) -> None:
        content = 'x' * 2000
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / 'run-001'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = artifact_dir / 'call-maxbytes.txt'
        artifact_file.write_text(content, encoding='utf-8')

        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(
                [
                    'artifact', 'read',
                    '.teaagent/artifacts/tool-results/run-001/call-maxbytes.txt',
                    '--max-bytes', '500',
                    '--root', str(tmp_path),
                ]
            )
        assert exit_code == 0
        result = out.getvalue().strip()
        assert len(result.encode('utf-8')) == 500
        assert result.startswith('x' * 500)


class TestArtifactListCommand:
    def test_empty_when_no_artifacts(self, tmp_path: Path) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(['artifact', 'list', '--root', str(tmp_path)])
        assert exit_code == 0
        payload = json.loads(out.getvalue())
        assert payload == {}

    def test_with_files(self, tmp_path: Path) -> None:
        for run_id, calls in [
            ('run-001', {'call-a': 'aaa', 'call-b': 'bbb'}),
            ('run-002', {'call-x': 'xxxx'}),
        ]:
            artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / run_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            for call_id, content in calls.items():
                (artifact_dir / f'{call_id}.txt').write_text(content, encoding='utf-8')

        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(['artifact', 'list', '--root', str(tmp_path)])
        assert exit_code == 0
        payload = json.loads(out.getvalue())

        assert 'run-001' in payload
        assert 'run-002' in payload

        run1 = {f['tool_call_id']: f['bytes'] for f in payload['run-001']}
        assert run1['call-a'] == 3
        assert run1['call-b'] == 3

        run2 = {f['tool_call_id']: f['bytes'] for f in payload['run-002']}
        assert run2['call-x'] == 4

    def test_ignores_non_directories(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / '.teaagent' / 'artifacts' / 'tool-results'
        artifact_root.mkdir(parents=True, exist_ok=True)
        (artifact_root / 'not_a_dir.txt').write_text('junk', encoding='utf-8')

        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(['artifact', 'list', '--root', str(tmp_path)])
        assert exit_code == 0
        payload = json.loads(out.getvalue())
        assert payload == {}

    def test_ignores_non_files_in_run_dir(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / 'run-001'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / 'subdir').mkdir()
        (artifact_dir / 'real.txt').write_text('real', encoding='utf-8')

        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(['artifact', 'list', '--root', str(tmp_path)])
        assert exit_code == 0
        payload = json.loads(out.getvalue())
        assert len(payload['run-001']) == 1
        assert payload['run-001'][0]['tool_call_id'] == 'real'
