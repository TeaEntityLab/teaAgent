"""Tests for multi-tenant isolation, directory partitioning, and tool mismatch protection."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from teaagent.approval_manager import ApprovalManager
from teaagent.cli._agent_parsers import add_agent_run_arguments
from teaagent.ergonomics.background_run import BackgroundRunStore
from teaagent.errors import ToolPermissionError
from teaagent.run_store import RunStore


def test_cli_parser_tenant_id_argument() -> None:
    """Verify that --tenant-id is successfully parsed."""
    parser = argparse.ArgumentParser()
    add_agent_run_arguments(parser)
    args = parser.parse_args(['--tenant-id', 'tenant-alpha', 'openai', 'test task'])
    assert args.tenant_id == 'tenant-alpha'


def test_run_store_partitioning(tmp_path: Path) -> None:
    """Verify RunStore partitions paths based on tenant_id."""
    store_default = RunStore(tmp_path, tenant_id='default')
    assert store_default.store_dir == tmp_path / '.teaagent' / 'runs'
    assert store_default.undo_dir() == tmp_path / '.teaagent' / 'undo'

    store_alpha = RunStore(tmp_path, tenant_id='tenant-alpha')
    assert (
        store_alpha.store_dir
        == tmp_path / '.teaagent' / 'tenants' / 'tenant-alpha' / 'runs'
    )
    assert (
        store_alpha.undo_dir()
        == tmp_path / '.teaagent' / 'tenants' / 'tenant-alpha' / 'undo'
    )


def test_background_run_store_partitioning(tmp_path: Path) -> None:
    """Verify BackgroundRunStore partitions paths based on tenant_id."""
    bg_store_default = BackgroundRunStore(tmp_path, tenant_id='default')
    assert bg_store_default.dir == tmp_path / '.teaagent' / 'background'

    bg_store_alpha = BackgroundRunStore(tmp_path, tenant_id='tenant-alpha')
    assert (
        bg_store_alpha.dir
        == tmp_path / '.teaagent' / 'tenants' / 'tenant-alpha' / 'background'
    )


def test_approval_manager_tenant_mismatch(tmp_path: Path) -> None:
    """Verify ApprovalManager denies cross-tenant tool access."""
    manager_alpha = ApprovalManager(
        tenant_id='tenant-alpha',
        workspace_root=str(tmp_path),
    )

    # Accessing standard file inside workspace root is allowed
    manager_alpha.assert_allowed(
        tool_name='read_file',
        call_id='call_1',
        destructive=False,
        arguments={'path': str(tmp_path / 'safe_file.txt')},
    )

    # Accessing tenant-alpha's runs folder is allowed
    manager_alpha.assert_allowed(
        tool_name='read_file',
        call_id='call_2',
        destructive=False,
        arguments={
            'path': str(
                tmp_path
                / '.teaagent'
                / 'tenants'
                / 'tenant-alpha'
                / 'runs'
                / 'run.jsonl'
            )
        },
    )

    # Accessing tenant-beta's runs folder is denied
    with pytest.raises(ToolPermissionError) as exc_info:
        manager_alpha.assert_allowed(
            tool_name='read_file',
            call_id='call_3',
            destructive=False,
            arguments={
                'path': str(
                    tmp_path
                    / '.teaagent'
                    / 'tenants'
                    / 'tenant-beta'
                    / 'runs'
                    / 'run.jsonl'
                )
            },
        )
    assert 'Tenant mismatch' in str(exc_info.value)
    assert 'tenant-beta' in str(exc_info.value)

    # Accessing default runs folder from tenant-alpha is denied
    with pytest.raises(ToolPermissionError) as exc_info:
        manager_alpha.assert_allowed(
            tool_name='read_file',
            call_id='call_4',
            destructive=False,
            arguments={'path': str(tmp_path / '.teaagent' / 'runs' / 'run.jsonl')},
        )
    assert 'Tenant mismatch' in str(exc_info.value)
    assert 'default' in str(exc_info.value)


def test_approval_manager_default_tenant_blocks_tenant_paths(tmp_path: Path) -> None:
    """Verify that default tenant runs cannot access other tenant spaces."""
    manager_default = ApprovalManager(
        tenant_id='default',
        workspace_root=str(tmp_path),
    )

    # Accessing standard runs folder is allowed
    manager_default.assert_allowed(
        tool_name='read_file',
        call_id='call_1',
        destructive=False,
        arguments={'path': str(tmp_path / '.teaagent' / 'runs' / 'run.jsonl')},
    )

    # Accessing tenant-alpha's runs folder is denied
    with pytest.raises(ToolPermissionError) as exc_info:
        manager_default.assert_allowed(
            tool_name='read_file',
            call_id='call_2',
            destructive=False,
            arguments={
                'path': str(
                    tmp_path
                    / '.teaagent'
                    / 'tenants'
                    / 'tenant-alpha'
                    / 'runs'
                    / 'run.jsonl'
                )
            },
        )
    assert 'Tenant mismatch' in str(exc_info.value)
    assert 'tenant-alpha' in str(exc_info.value)
