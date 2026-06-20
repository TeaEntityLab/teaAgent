"""Tests for A-P0-2: silent exception sites now log at ERROR.

Each test asserts that a previously-silent ``except Exception: pass``
(or ``continue`` / ``return``) block now emits an ERROR-level log record
via the module logger instead of swallowing the exception silently.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.asset_provenance import _collect_skill_records
from teaagent.cockpit import build_control_cockpit
from teaagent.code_analysis._manager import LSPServerManager
from teaagent.context_pressure import compute_context_pressure
from teaagent.ergonomics.background_run import _get_tenant_id_from_path
from teaagent.extension_explain import _gather_hooks, _gather_mcp, _gather_plugins
from teaagent.governance.repo_map_benchmark import RepoMapBenchmarkRunner

# ── cockpit.py ──────────────────────────────────────────────────────────────


def test_cockpit_goal_spec_load_error_logged(tmp_path, caplog):
    """cockpit.py:381-382 — goal/spec load failure logs at ERROR."""
    with (
        patch(
            'teaagent.goal_record.GoalStore',
            side_effect=RuntimeError('goal store boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.cockpit'),
    ):
        state = build_control_cockpit(tmp_path)
    assert any(
        'goal/spec' in r.message and r.levelno == logging.ERROR for r in caplog.records
    ), [r.message for r in caplog.records]
    assert 'goal/spec load failed' in state.errors


def test_cockpit_context_health_error_logged(tmp_path, caplog):
    """cockpit.py:453-454 — context health failure logs at ERROR."""
    with (
        patch(
            'teaagent.context_health.compute_context_health',
            side_effect=RuntimeError('ctx health boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.cockpit'),
    ):
        state = build_control_cockpit(tmp_path)
    assert any(
        'context health' in r.message and r.levelno == logging.ERROR
        for r in caplog.records
    )
    assert 'context health computation failed' in state.errors


def test_cockpit_extension_explain_error_logged(tmp_path, caplog):
    """cockpit.py:462-463 — extension explain failure logs at ERROR."""
    with (
        patch(
            'teaagent.extension_explain.explain_extension_activation',
            side_effect=RuntimeError('ext explain boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.cockpit'),
    ):
        state = build_control_cockpit(tmp_path)
    assert any(
        'extension activation' in r.message and r.levelno == logging.ERROR
        for r in caplog.records
    )
    assert 'extension activation explain failed' in state.errors


# ── subagents/_review.py ────────────────────────────────────────────────────


def test_review_cost_ledger_error_logged(caplog):
    """subagents/_review.py:167-168 — cost ledger failure logs at ERROR."""
    from teaagent.subagents import _review

    fake_result = {
        'review': {'child_run_id': 'child-1', 'review_id': 'rev-1'},
    }
    with (
        patch('teaagent.subagents._review._run_review_patch', return_value=fake_result),
        patch(
            'teaagent.subagents._cost.build_child_cost_ledger',
            side_effect=RuntimeError('cost ledger boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.subagents._review'),
    ):
        _review.check_subagent_review(Path('.'), 'rev-1', with_cost=True)
    assert any(
        'cost ledger' in r.message and r.levelno == logging.ERROR
        for r in caplog.records
    )


# ── extension_explain.py ────────────────────────────────────────────────────


class _ExplodingAttr:
    """Object whose attribute access raises via a property."""

    _attr: str

    def __init__(self, attr: str) -> None:
        self._attr = attr

    def __getattribute__(self, name: str) -> object:
        if name == object.__getattribute__(self, '_attr'):
            raise RuntimeError(f'{name} boom')
        return object.__getattribute__(self, name)


def test_extension_gather_plugins_error_logged(caplog):
    """extension_explain.py:161-162 — plugin gather failure logs at ERROR."""
    registry = _ExplodingAttr('commands')
    with caplog.at_level(logging.ERROR, logger='teaagent.extension_explain'):
        result = _gather_plugins(registry)
    assert any(
        'plugin' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )
    assert result == []


def test_extension_gather_hooks_error_logged(caplog):
    """extension_explain.py:198-199 — hook gather failure logs at ERROR."""
    hook_registry = _ExplodingAttr('_pre_hooks')
    with caplog.at_level(logging.ERROR, logger='teaagent.extension_explain'):
        result = _gather_hooks(hook_registry)
    assert any(
        'hook' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )
    assert result == []


def test_extension_gather_mcp_error_logged(caplog):
    """extension_explain.py:234-235 — mcp gather failure logs at ERROR."""
    trust_policy = _ExplodingAttr('servers')
    with caplog.at_level(logging.ERROR, logger='teaagent.extension_explain'):
        result = _gather_mcp(trust_policy)
    assert any(
        'MCP' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )
    assert result == []


# ── context_pressure.py ─────────────────────────────────────────────────────


def test_context_pressure_pinned_files_error_logged(tmp_path, caplog):
    """context_pressure.py:131-132 — pinned file failure logs at ERROR."""
    with (
        patch(
            'teaagent.memory.pinned_file.PinnedFileStorage',
            side_effect=RuntimeError('pinned boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.context_pressure'),
    ):
        compute_context_pressure(tmp_path)
    assert any(
        'pinned files' in r.message and r.levelno == logging.ERROR
        for r in caplog.records
    )


def test_context_pressure_recent_runs_error_logged(tmp_path, caplog):
    """context_pressure.py:138-139 — recent runs failure logs at ERROR."""
    with (
        patch(
            'teaagent.context_pressure.RunStore',
            side_effect=RuntimeError('runstore boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.context_pressure'),
    ):
        compute_context_pressure(tmp_path)
    assert any(
        'recent runs' in r.message and r.levelno == logging.ERROR
        for r in caplog.records
    )


# ── ergonomics/background_run.py ────────────────────────────────────────────


class _BadFspath:
    def __fspath__(self) -> str:
        raise OSError('bad path boom')


def test_background_run_tenant_id_error_logged(caplog):
    """ergonomics/background_run.py:39-40 — tenant id failure logs at ERROR."""
    with caplog.at_level(logging.ERROR, logger='teaagent.ergonomics.background_run'):
        result = _get_tenant_id_from_path(_BadFspath())
    assert any(
        'tenant id' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )
    assert result == 'default'


# ── asset_provenance.py ─────────────────────────────────────────────────────


def test_asset_provenance_lifecycle_error_logged(caplog):
    """asset_provenance.py:135-136 — lifecycle read failure logs at ERROR."""
    from teaagent.skill_loader import (
        SkillActivationExplain,
        SkillLoadedRecord,
    )

    activation = SkillActivationExplain(
        selection_mode='none',
        selected_names=(),
        loaded=(
            SkillLoadedRecord(
                name='my-skill',
                path=Path('/tmp/skill'),
                source_dir=Path('/tmp'),
                estimated_tokens=0,
                reason='test',
            ),
        ),
        shadowed=(),
        skipped=(),
        warnings=(),
        searched_dirs=(),
        estimated_skill_tokens=0,
        index_count=0,
        write_targets={},
    )
    tracker = MagicMock()
    tracker.current_state.side_effect = RuntimeError('lifecycle boom')
    with caplog.at_level(logging.ERROR, logger='teaagent.asset_provenance'):
        records = _collect_skill_records(activation, tracker)
    assert any(
        'lifecycle' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )
    # Record still produced (graceful), with default lifecycle_state
    assert len(records) == 1


# ── governance/repo_map_benchmark.py ────────────────────────────────────────


def test_repo_map_benchmark_query_error_logged(tmp_path, caplog):
    """repo_map_benchmark.py:275-276 — query file read failure logs at ERROR."""
    runner = RepoMapBenchmarkRunner()
    # Create a file that will fail to read (patch read_text to raise)
    target = tmp_path / 'target.py'
    target.write_text('def login(): pass\n')
    with (
        patch(
            'pathlib.Path.read_text',
            side_effect=OSError('read boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.governance.repo_map_benchmark'),
    ):
        runner._execute_repo_map_query(tmp_path, 'login', {})
    assert any(
        'query' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )


def test_repo_map_benchmark_extract_functions_error_logged(tmp_path, caplog):
    """repo_map_benchmark.py:301-302 — function extraction failure logs at ERROR."""
    runner = RepoMapBenchmarkRunner()
    with (
        patch(
            'pathlib.Path.read_text',
            side_effect=OSError('read boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.governance.repo_map_benchmark'),
    ):
        result = runner._extract_functions(tmp_path, {'missing.py'})
    assert any(
        'functions' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )
    assert result == set()


def test_repo_map_benchmark_extract_classes_error_logged(tmp_path, caplog):
    """repo_map_benchmark.py:327-328 — class extraction failure logs at ERROR."""
    runner = RepoMapBenchmarkRunner()
    with (
        patch(
            'pathlib.Path.read_text',
            side_effect=OSError('read boom'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.governance.repo_map_benchmark'),
    ):
        result = runner._extract_classes(tmp_path, {'missing.py'})
    assert any(
        'classes' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )
    assert result == set()


# ── memory/file_watcher.py ──────────────────────────────────────────────────


def test_file_watcher_on_modified_error_logged(caplog):
    """memory/file_watcher.py:98-99 — modified event parse failure logs ERROR."""
    from teaagent.memory.file_watcher import FileChangeHandler

    handler = FileChangeHandler(callback=lambda p, t: None, watched_files=set())
    bad_event = MagicMock()
    bad_event.is_directory = False
    # Accessing src_path raises
    type(bad_event).src_path = property(
        lambda self: (_ for _ in ()).throw(RuntimeError('src boom'))
    )
    with caplog.at_level(logging.ERROR, logger='teaagent.memory.file_watcher'):
        handler.on_modified(bad_event)
    assert any(
        'modified' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )


def test_file_watcher_on_deleted_error_logged(caplog):
    """memory/file_watcher.py:129-130 — deleted event parse failure logs ERROR."""
    from teaagent.memory.file_watcher import FileChangeHandler

    handler = FileChangeHandler(callback=lambda p, t: None, watched_files=set())
    bad_event = MagicMock()
    bad_event.is_directory = False
    type(bad_event).src_path = property(
        lambda self: (_ for _ in ()).throw(RuntimeError('src boom'))
    )
    with caplog.at_level(logging.ERROR, logger='teaagent.memory.file_watcher'):
        handler.on_deleted(bad_event)
    assert any(
        'deleted' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )


# ── code_analysis/_manager.py ───────────────────────────────────────────────


def test_code_analysis_lsp_init_error_logged(caplog):
    """code_analysis/_manager.py:43-44 — LSP init failure logs at ERROR."""
    from teaagent.code_analysis._config import CodeAnalysisConfig
    from teaagent.code_analysis._types import LSPClient

    config = CodeAnalysisConfig(root=Path('/tmp'))
    manager = LSPServerManager(config)
    with patch('teaagent.code_analysis._manager.StdioLSPClient') as MockClient:
        instance = MagicMock(spec=LSPClient)
        instance.initialize.side_effect = RuntimeError('lsp init boom')
        MockClient.return_value = instance
        with caplog.at_level(logging.ERROR, logger='teaagent.code_analysis._manager'):
            result = manager.get_client('foo.py')
    assert any(
        'LSP client initialize' in r.message and r.levelno == logging.ERROR
        for r in caplog.records
    )
    assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-x', '-v'])
