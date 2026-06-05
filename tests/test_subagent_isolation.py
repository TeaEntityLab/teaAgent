"""Tests for subagent workspace isolation (shared vs worktree)."""

from __future__ import annotations

import subprocess
import unittest
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.runner import FinalAnswer, RunResult
from teaagent.subagents import SubagentManager
from teaagent.subagents._isolation import (
    IsolationContext,
    normalize_subagent_isolation,
    prepare_subagent_isolation,
)


def _init_git_repo(root: Path) -> None:
    subprocess.run(
        ['git', 'init', '--template='],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'TeaAgent Test'],
        cwd=root,
        check=True,
        capture_output=True,
    )
    (root / 'README.md').write_text('hello', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'README.md'], cwd=root, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'init'],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _stub_result(run_id: str = 'child-run-1') -> RunResult:
    return RunResult(
        run_id=run_id,
        final_answer=FinalAnswer(content='done'),
        iterations=1,
        tool_calls=0,
        status='completed',
    )


class SubagentIsolationTests(unittest.TestCase):
    def test_normalize_subagent_isolation_defaults_and_rejects_unknown(self) -> None:
        self.assertEqual(normalize_subagent_isolation(None), 'shared')
        self.assertEqual(normalize_subagent_isolation('worktree'), 'worktree')
        self.assertEqual(
            normalize_subagent_isolation('directory-snapshot'), 'directory-snapshot'
        )
        self.assertIsNone(normalize_subagent_isolation('invalid'))

    def test_normalize_subagent_isolation_deprecated_container_alias(self) -> None:
        # Test that 'container' is deprecated but still works via alias
        # normalize_subagent_isolation handles the alias without warning
        result = normalize_subagent_isolation('container')
        self.assertEqual(result, 'directory-snapshot')

    def test_prepare_worktree_requires_git_repository(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx, error = prepare_subagent_isolation(
                root, isolation='worktree', session_key='child-1'
            )
            self.assertIsNone(ctx)
            self.assertIn('git repository', error)

    def test_prepare_worktree_creates_and_cleans_up(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                _init_git_repo(root)
            except subprocess.CalledProcessError:
                self.skipTest('git unavailable in this environment')
            ctx, error = prepare_subagent_isolation(
                root, isolation='worktree', session_key='child-1'
            )
            if error:
                self.skipTest(error)
            assert ctx is not None
            self.assertTrue(ctx.worktree_path is not None)
            self.assertTrue(ctx.child_root.is_dir())
            marker = ctx.child_root / 'README.md'
            self.assertTrue(marker.is_file())
            ctx.cleanup()
            self.assertFalse(ctx.worktree_path.exists())

    def test_run_subagent_worktree_uses_isolated_root(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            worktree = root / '.teaagent' / 'subagent-worktrees' / 'child-1'
            worktree.mkdir(parents=True)
            config = ChatAgentConfig(root=root)
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
            )
            captured: dict[str, Path] = {}
            iso_ctx = IsolationContext(
                parent_root=root,
                child_root=worktree,
                isolation='worktree',
                worktree_path=worktree,
            )

            def capture_run(*args: object, **kwargs: object) -> RunResult:
                cfg = args[0]  # First positional arg is config
                captured['child_root'] = cfg.root  # type: ignore[attr-defined]
                return _stub_result('child-wt')

            with (
                patch(
                    'teaagent.subagents._manager.prepare_subagent_isolation',
                    return_value=(iso_ctx, ''),
                ),
                patch('teaagent.chat_agent.run_chat_agent', side_effect=capture_run),
                patch('teaagent.run_store.RunStore.logger_for_result'),
            ):
                payload = manager.run_subagent(
                    task='inspect README',
                    parent_run_id='parent-1',
                    depth=0,
                    isolation='worktree',
                )

            self.assertEqual(payload['status'], 'completed')
            self.assertEqual(payload['lineage']['isolation'], 'worktree')
            self.assertIn('worktree_path', payload['lineage'])
            self.assertEqual(captured['child_root'].resolve(), worktree.resolve())

    def test_prepare_directory_snapshot_creates_snapshot_and_cleans_up(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'app.py').write_text('print("hi")\n', encoding='utf-8')
            (root / '.teaagent').mkdir()
            (root / '.teaagent' / 'runs').mkdir()
            (root / '.teaagent' / 'runs' / 'parent.jsonl').write_text(
                'parent\n', encoding='utf-8'
            )

            ctx, error = prepare_subagent_isolation(
                root, isolation='directory-snapshot', session_key='child-1'
            )
            self.assertEqual(error, '')
            assert ctx is not None
            self.assertTrue((ctx.child_root / 'src' / 'app.py').is_file())
            self.assertFalse((ctx.child_root / '.teaagent' / 'runs').exists())
            ctx.cleanup()
            self.assertFalse(ctx.container_path.exists())

    def test_run_subagent_directory_snapshot_uses_isolated_root(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            snapshot = root / '.teaagent' / 'subagent-snapshots' / 'child-1'
            snapshot.mkdir(parents=True)
            config = ChatAgentConfig(root=root)
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
            )
            captured: dict[str, Path] = {}
            iso_ctx = IsolationContext(
                parent_root=root,
                child_root=snapshot,
                isolation='directory-snapshot',
                container_path=snapshot,
            )

            def capture_run(*args: object, **kwargs: object) -> RunResult:
                cfg = args[0]  # First positional arg is config
                captured['child_root'] = cfg.root  # type: ignore[attr-defined]
                return _stub_result('child-ds')

            with (
                patch(
                    'teaagent.subagents._manager.prepare_subagent_isolation',
                    return_value=(iso_ctx, ''),
                ),
                patch('teaagent.chat_agent.run_chat_agent', side_effect=capture_run),
                patch('teaagent.run_store.RunStore.logger_for_result'),
            ):
                payload = manager.run_subagent(
                    task='inspect app',
                    parent_run_id='parent-1',
                    depth=0,
                    isolation='directory-snapshot',
                )

            self.assertEqual(payload['status'], 'completed')
            self.assertEqual(payload['lineage']['isolation'], 'directory-snapshot')
            self.assertIn('container_path', payload['lineage'])
            self.assertEqual(captured['child_root'].resolve(), snapshot.resolve())

    def test_deprecated_container_alias_still_works(self) -> None:
        """Test that deprecated 'container' alias still works for backward compatibility."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'app.py').write_text('print("hi")\n', encoding='utf-8')
            (root / '.teaagent').mkdir()
            (root / '.teaagent' / 'runs').mkdir()
            (root / '.teaagent' / 'runs' / 'parent.jsonl').write_text(
                'parent\n', encoding='utf-8'
            )

            # Test that prepare_subagent_isolation triggers the deprecation warning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                ctx, error = prepare_subagent_isolation(
                    root, isolation='container', session_key='child-1'
                )
                # Should trigger deprecation warning
                self.assertTrue(len(w) > 0)
                self.assertTrue(issubclass(w[0].category, DeprecationWarning))
                self.assertIn('container', str(w[0].message))
                self.assertIn('directory-snapshot', str(w[0].message))

            self.assertEqual(error, '')
            assert ctx is not None
            self.assertEqual(ctx.isolation, 'directory-snapshot')
            self.assertTrue((ctx.child_root / 'src' / 'app.py').is_file())
            ctx.cleanup()
            self.assertFalse(ctx.container_path.exists())


def test_docker_isolation_with_resource_limits():
    """Test Docker isolation with CPU and memory limits."""
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _init_git_repo(root)

        # Mock Docker to be available
        with patch('subprocess.run') as mock_run:
            # First call: docker --version check
            mock_run.return_value = MagicMock(
                returncode=0, stdout='Docker version 20.10.0', stderr=''
            )

            context, error = prepare_subagent_isolation(
                root,
                isolation='docker',
                session_key='test-session',
                cpu_quota=2.0,
                memory_limit='1g',
            )

            # Should have called docker run with resource limits
            docker_calls = [
                call for call in mock_run.call_args_list if 'docker' in str(call)
            ]
            assert len(docker_calls) >= 2  # version check + run

            # Check the run command includes resource limits
            run_call = docker_calls[1]
            run_args = run_call[0][0]
            assert '--cpus' in run_args
            assert '2.0' in run_args
            assert '--memory' in run_args
            assert '1g' in run_args


def test_docker_isolation_without_resource_limits():
    """Test Docker isolation without resource limits."""
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _init_git_repo(root)

        # Mock Docker to be available
        with patch('subprocess.run') as mock_run:
            # First call: docker --version check
            mock_run.return_value = MagicMock(
                returncode=0, stdout='Docker version 20.10.0', stderr=''
            )

            context, error = prepare_subagent_isolation(
                root,
                isolation='docker',
                session_key='test-session',
            )

            # Should have called docker run without resource limits
            docker_calls = [
                call for call in mock_run.call_args_list if 'docker' in str(call)
            ]
            assert len(docker_calls) >= 2  # version check + run

            # Check the run command does not include resource limits
            run_call = docker_calls[1]
            run_args = run_call[0][0]
            assert '--cpus' not in run_args
            assert '--memory' not in run_args


def test_isolation_context_with_resource_limits():
    """Test IsolationContext includes resource limits."""
    context = IsolationContext(
        parent_root=Path('/root'),
        child_root=Path('/workspace'),
        isolation='docker',
        cpu_quota=1.5,
        memory_limit='512m',
    )

    assert context.cpu_quota == 1.5
    assert context.memory_limit == '512m'


def test_subagent_docker_container_hardened():
    """SEC-07: Docker run command must contain all required hardening flags.

    Verifies --network none, --user <nonroot>, --cap-drop ALL,
    --read-only, and --security-opt no-new-privileges are present
    so the container cannot exfiltrate data or escalate privileges.
    """
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / 'test.py').write_text('print("hello")', encoding='utf-8')

        captured_cmds: list[list[str]] = []

        def _fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            result = MagicMock()
            result.returncode = 0
            result.stdout = 'container-hardening-test\n'
            result.stderr = ''
            return result

        with patch('subprocess.run', side_effect=_fake_run):
            prepare_subagent_isolation(
                root,
                isolation='docker',
                session_key='hardening-test-001',
            )

        docker_run = next(
            (
                cmd
                for cmd in captured_cmds
                if len(cmd) > 1 and cmd[:2] == ['docker', 'run']
            ),
            None,
        )
        assert docker_run is not None, 'No docker run command was issued'

        assert '--network' in docker_run and 'none' in docker_run, (
            '--network none missing — container has unrestricted internet access'
        )
        assert '--user' in docker_run, '--user missing — container runs as root'
        user_idx = docker_run.index('--user')
        assert docker_run[user_idx + 1] != '0' and docker_run[user_idx + 1] != 'root', (
            f'--user value is {docker_run[user_idx + 1]!r} — container still runs as root'
        )
        assert '--cap-drop' in docker_run and 'ALL' in docker_run, (
            '--cap-drop ALL missing — container retains Linux capabilities'
        )
        assert '--read-only' in docker_run, (
            '--read-only missing — container filesystem is writable'
        )
        assert '--security-opt' in docker_run, '--security-opt missing'
        sec_opt_idx = docker_run.index('--security-opt')
        assert 'no-new-privileges' in docker_run[sec_opt_idx + 1], (
            '--security-opt no-new-privileges missing — setuid escalation possible'
        )


class SubagentPermissionInheritanceTests(unittest.TestCase):
    """P2-A-003: Subagent permission mode must be capped for safety."""

    def test_danger_full_access_parent_caps_child_to_workspace_write(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            worktree = root / '.teaagent' / 'subagent-worktrees' / 'child-1'
            worktree.mkdir(parents=True)
            from teaagent.policy import PermissionMode

            config = ChatAgentConfig(
                root=root, permission_mode=PermissionMode.DANGER_FULL_ACCESS
            )
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
            )
            captured_mode: list[object] = []
            iso_ctx = IsolationContext(
                parent_root=root,
                child_root=worktree,
                isolation='worktree',
                worktree_path=worktree,
            )

            def capture_run(*args: object, **kwargs: object) -> RunResult:
                cfg = args[0]
                captured_mode.append(cfg.permission_mode)  # type: ignore[attr-defined]
                return _stub_result('child-1')

            with (
                patch(
                    'teaagent.subagents._manager.prepare_subagent_isolation',
                    return_value=(iso_ctx, ''),
                ),
                patch('teaagent.chat_agent.run_chat_agent', side_effect=capture_run),
                patch('teaagent.run_store.RunStore.logger_for_result'),
            ):
                payload = manager.run_subagent(
                    task='test',
                    parent_run_id='parent-1',
                    depth=0,
                    isolation='worktree',
                )

            self.assertEqual(payload['status'], 'completed')
            child_mode = captured_mode[0]
            child_mode_str = (
                child_mode.value if hasattr(child_mode, 'value') else str(child_mode)
            )
            self.assertEqual(child_mode_str, 'workspace-write')

    def test_allow_mode_parent_caps_child_to_workspace_write(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            worktree = root / '.teaagent' / 'subagent-worktrees' / 'child-1'
            worktree.mkdir(parents=True)
            from teaagent.policy import PermissionMode

            config = ChatAgentConfig(root=root, permission_mode=PermissionMode.ALLOW)
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
            )
            captured_mode: list[object] = []
            iso_ctx = IsolationContext(
                parent_root=root,
                child_root=worktree,
                isolation='worktree',
                worktree_path=worktree,
            )

            def capture_run(*args: object, **kwargs: object) -> RunResult:
                cfg = args[0]
                captured_mode.append(cfg.permission_mode)  # type: ignore[attr-defined]
                return _stub_result('child-1')

            with (
                patch(
                    'teaagent.subagents._manager.prepare_subagent_isolation',
                    return_value=(iso_ctx, ''),
                ),
                patch('teaagent.chat_agent.run_chat_agent', side_effect=capture_run),
                patch('teaagent.run_store.RunStore.logger_for_result'),
            ):
                payload = manager.run_subagent(
                    task='test',
                    parent_run_id='parent-1',
                    depth=0,
                    isolation='worktree',
                )

            self.assertEqual(payload['status'], 'completed')
            child_mode = captured_mode[0]
            child_mode_str = (
                child_mode.value if hasattr(child_mode, 'value') else str(child_mode)
            )
            self.assertEqual(child_mode_str, 'workspace-write')

    def test_read_only_parent_does_not_elevate_child(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            worktree = root / '.teaagent' / 'subagent-worktrees' / 'child-1'
            worktree.mkdir(parents=True)
            from teaagent.policy import PermissionMode

            config = ChatAgentConfig(
                root=root, permission_mode=PermissionMode.READ_ONLY
            )
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
            )
            captured_mode: list[object] = []
            iso_ctx = IsolationContext(
                parent_root=root,
                child_root=worktree,
                isolation='worktree',
                worktree_path=worktree,
            )

            def capture_run(*args: object, **kwargs: object) -> RunResult:
                cfg = args[0]
                captured_mode.append(cfg.permission_mode)  # type: ignore[attr-defined]
                return _stub_result('child-1')

            with (
                patch(
                    'teaagent.subagents._manager.prepare_subagent_isolation',
                    return_value=(iso_ctx, ''),
                ),
                patch('teaagent.chat_agent.run_chat_agent', side_effect=capture_run),
                patch('teaagent.run_store.RunStore.logger_for_result'),
            ):
                payload = manager.run_subagent(
                    task='test',
                    parent_run_id='parent-1',
                    depth=0,
                    isolation='worktree',
                )

            self.assertEqual(payload['status'], 'completed')
            child_mode = captured_mode[0]
            child_mode_str = (
                child_mode.value if hasattr(child_mode, 'value') else str(child_mode)
            )
            self.assertEqual(child_mode_str, 'read-only')


class WorkspaceCopySecretExclusionTests(unittest.TestCase):
    """P2-A-003: workspace snapshots must exclude secret files."""

    def test_env_files_excluded_from_snapshot(self) -> None:
        from teaagent.subagents._isolation import _copy_workspace_snapshot

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.env').write_text('SECRET_KEY=abc123')
            (root / 'app.py').write_text('print("hello")')
            (root / '.teaagent').mkdir()

            dest = Path(tmp) / 'snapshot'
            _copy_workspace_snapshot(root, dest)

            self.assertFalse((dest / '.env').exists())
            self.assertTrue((dest / 'app.py').exists())

    def test_pem_files_excluded_from_snapshot(self) -> None:
        from teaagent.subagents._isolation import _copy_workspace_snapshot

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'id_rsa.pem').write_text('PRIVATE KEY')
            (root / 'app.py').write_text('print("hello")')
            (root / '.teaagent').mkdir()

            dest = Path(tmp) / 'snapshot'
            _copy_workspace_snapshot(root, dest)

            self.assertFalse((dest / 'id_rsa.pem').exists())
            self.assertTrue((dest / 'app.py').exists())

    def test_credentials_files_excluded_from_snapshot(self) -> None:
        from teaagent.subagents._isolation import _copy_workspace_snapshot

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'credentials.json').write_text('{"key":"secret"}')
            (root / 'app.py').write_text('print("hello")')
            (root / '.teaagent').mkdir()

            dest = Path(tmp) / 'snapshot'
            _copy_workspace_snapshot(root, dest)

            self.assertFalse((dest / 'credentials.json').exists())
            self.assertTrue((dest / 'app.py').exists())

    def test_ssh_dir_excluded_from_snapshot(self) -> None:
        from teaagent.subagents._isolation import _copy_workspace_snapshot

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.ssh').mkdir()
            (root / '.ssh' / 'id_rsa').write_text('PRIVATE KEY')
            (root / 'app.py').write_text('print("hello")')
            (root / '.teaagent').mkdir()

            dest = Path(tmp) / 'snapshot'
            _copy_workspace_snapshot(root, dest)

            self.assertFalse((dest / '.ssh').exists())


if __name__ == '__main__':
    unittest.main()
