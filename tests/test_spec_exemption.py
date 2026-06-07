"""Tests for risk-adaptive spec exemption system (CPP-P1-005)."""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.audit import AuditLogger
from teaagent.spec_exemption import (
    _VALID_REASONS,
    _VALID_RISK_LEVELS,
    ExemptionDetector,
    SpecExemptionReceipt,
    delete_exemption,
    grant_spec_exemption,
    load_exemption,
)


class TestSpecExemptionReceipt:
    def test_defaults(self):
        receipt = SpecExemptionReceipt(
            exemption_id='',
            reason='read_only',
            spec_requirement_waived='plan-before-write',
        )
        assert receipt.exemption_id
        assert len(receipt.exemption_id) == 32
        assert receipt.granted_at
        assert receipt.risk_level == 'low'
        assert receipt.task_description == ''
        assert receipt.changed_files == []

    def test_custom_fields(self):
        receipt = SpecExemptionReceipt(
            exemption_id='custom-id',
            reason='small_clear_task',
            spec_requirement_waived='plan-before-write',
            risk_level='medium',
            task_description='Fix a typo in README',
            changed_files=['README.md'],
        )
        assert receipt.exemption_id == 'custom-id'
        assert receipt.reason == 'small_clear_task'
        assert receipt.risk_level == 'medium'
        assert receipt.task_description == 'Fix a typo in README'
        assert receipt.changed_files == ['README.md']

    def test_invalid_reason_raises(self):
        with pytest.raises(ValueError, match='Invalid exemption reason'):
            SpecExemptionReceipt(
                exemption_id='x',
                reason='invalid_reason',
                spec_requirement_waived='plan-before-write',
            )

    def test_invalid_risk_level_raises(self):
        with pytest.raises(ValueError, match='Invalid risk_level'):
            SpecExemptionReceipt(
                exemption_id='x',
                reason='read_only',
                spec_requirement_waived='plan-before-write',
                risk_level='high',
            )

    def test_roundtrip_dict(self):
        receipt = SpecExemptionReceipt(
            exemption_id='abc123',
            reason='docs_only',
            spec_requirement_waived='plan-before-write',
            risk_level='low',
            task_description='Update docs',
            changed_files=['README.md', 'CHANGELOG.md'],
        )
        data = receipt.to_dict()
        loaded = SpecExemptionReceipt.from_dict(data)
        assert loaded.exemption_id == receipt.exemption_id
        assert loaded.reason == receipt.reason
        assert loaded.spec_requirement_waived == receipt.spec_requirement_waived
        assert loaded.risk_level == receipt.risk_level
        assert loaded.task_description == receipt.task_description
        assert loaded.changed_files == receipt.changed_files

    def test_all_valid_reasons_accepted(self):
        for reason in sorted(_VALID_REASONS):
            receipt = SpecExemptionReceipt(
                exemption_id='',
                reason=reason,
                spec_requirement_waived='plan-before-write',
            )
            assert receipt.reason == reason

    def test_all_valid_risk_levels_accepted(self):
        for level in sorted(_VALID_RISK_LEVELS):
            receipt = SpecExemptionReceipt(
                exemption_id='',
                reason='read_only',
                spec_requirement_waived='plan-before-write',
                risk_level=level,
            )
            assert receipt.risk_level == level


class TestGrantSpecExemption:
    def test_grant_persists_and_reloads(self, tmp_path: Path):
        receipt = grant_spec_exemption(
            reason='read_only',
            risk_level='low',
            spec_requirement='plan-before-write',
            task_description='Read-only task',
            root=tmp_path,
        )
        assert receipt.reason == 'read_only'
        assert receipt.risk_level == 'low'

        loaded = load_exemption(receipt.exemption_id, root=tmp_path)
        assert loaded.exemption_id == receipt.exemption_id
        assert loaded.reason == 'read_only'

    def test_grant_with_audit_logger(self, tmp_path: Path):
        audit_path = tmp_path / 'audit.jsonl'
        audit = AuditLogger(path=audit_path)
        receipt = grant_spec_exemption(
            reason='small_clear_task',
            risk_level='low',
            spec_requirement='plan-before-write',
            task_description='Fix typo',
            audit_logger=audit,
            root=tmp_path,
        )
        assert receipt.reason == 'small_clear_task'
        assert audit_path.is_file()
        content = audit_path.read_text(encoding='utf-8')
        assert 'spec_exemption_granted' in content

    def test_grant_with_changed_files(self, tmp_path: Path):
        receipt = grant_spec_exemption(
            reason='docs_only',
            risk_level='low',
            spec_requirement='plan-before-write',
            changed_files=['README.md'],
            root=tmp_path,
        )
        assert receipt.changed_files == ['README.md']

    def test_grant_invalid_risk_level(self):
        with pytest.raises(ValueError, match='Invalid risk_level'):
            grant_spec_exemption(
                reason='read_only',
                risk_level='high',
                spec_requirement='plan-before-write',
            )

    def test_grant_invalid_reason(self):
        with pytest.raises(ValueError, match='Invalid reason'):
            grant_spec_exemption(
                reason='bad_reason',
                risk_level='low',
                spec_requirement='plan-before-write',
            )

    def test_delete_exemption(self, tmp_path: Path):
        receipt = grant_spec_exemption(
            reason='read_only',
            risk_level='low',
            spec_requirement='plan-before-write',
            root=tmp_path,
        )
        loaded = load_exemption(receipt.exemption_id, root=tmp_path)
        assert loaded.exemption_id == receipt.exemption_id

        delete_exemption(receipt.exemption_id, root=tmp_path)
        with pytest.raises(FileNotFoundError):
            load_exemption(receipt.exemption_id, root=tmp_path)

    def test_load_nonexistent(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_exemption('nonexistent', root=tmp_path)

    def test_delete_nonexistent(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            delete_exemption('nonexistent', root=tmp_path)


class TestExemptionDetector:
    def test_read_only_permission_mode(self):
        receipt = ExemptionDetector.detect(
            task_description='Look at the code',
            changed_files=[],
            permission_mode='read-only',
        )
        assert receipt is not None
        assert receipt.reason == 'read_only'

    def test_read_only_keyword_task(self):
        receipt = ExemptionDetector.detect(
            task_description='Summarize the test suite',
            changed_files=['src/main.py'],
            permission_mode='workspace-write',
        )
        assert receipt is not None
        assert receipt.reason == 'read_only'

    def test_docs_only(self):
        receipt = ExemptionDetector.detect(
            task_description='Update documentation',
            changed_files=['README.md', 'CHANGELOG.md'],
        )
        assert receipt is not None
        assert receipt.reason == 'docs_only'

    def test_mixed_files_but_audit_keyword_grants_read_only_exemption(self):
        receipt = ExemptionDetector.detect(
            task_description='Audit docs and code together',
            changed_files=['README.md', 'src/main.py'],
        )
        assert receipt is not None
        assert receipt.reason == 'read_only'

    def test_simple_mixed_file_task_still_small_exemption(self):
        receipt = ExemptionDetector.detect(
            task_description='Simple fix for the formatting',
            changed_files=['README.md', 'src/main.py'],
        )
        assert receipt is not None
        assert receipt.reason == 'small_clear_task'

    def test_small_task_line_count(self):
        receipt = ExemptionDetector.detect(
            task_description='Change a variable name',
            changed_files=['src/main.py'],
            line_count=5,
        )
        assert receipt is not None
        assert receipt.reason == 'small_clear_task'

    def test_small_task_keyword(self):
        receipt = ExemptionDetector.detect(
            task_description='Fix typo in the comment',
            changed_files=['src/main.py'],
        )
        assert receipt is not None
        assert receipt.reason == 'small_clear_task'

    def test_single_file_change(self):
        receipt = ExemptionDetector.detect(
            task_description='Update config file',
            changed_files=['config.json'],
        )
        assert receipt is not None
        assert receipt.reason == 'small_clear_task'

    def test_known_pattern(self):
        receipt = ExemptionDetector.detect(
            task_description='Rename function getCwd to get_current_working_directory',
            changed_files=['src/utils.py', 'src/main.py'],
        )
        assert receipt is not None
        assert receipt.reason == 'known_pattern'
        assert receipt.risk_level == 'medium'

    def test_no_exemption_for_danger_mode(self):
        receipt = ExemptionDetector.detect(
            task_description='Summarize the test suite',
            changed_files=['src/main.py'],
            permission_mode='danger-full-access',
        )
        assert receipt is None

    def test_no_exemption_for_normal_task(self):
        receipt = ExemptionDetector.detect(
            task_description='Implement a new authentication system with OAuth2',
            changed_files=['src/auth.py', 'src/models.py', 'src/views.py'],
        )
        assert receipt is None

    def test_no_changed_files_no_exemption(self):
        receipt = ExemptionDetector.detect(
            task_description='Implement new feature',
            changed_files=[],
        )
        assert receipt is None

    def test_read_only_keywords_list(self):
        read_tasks = [
            'Read the configuration file',
            'Inspect the database schema',
            'Analyze the performance metrics',
            'Summarize recent changes',
            'Review the pull request',
            'Find all occurrences of the bug',
            'Search for deprecated APIs',
            'List all registered routes',
            'Show me the current settings',
            'Explore the project structure',
            'Audit security vulnerabilities',
            'Check linting errors',
            'Report compilation warnings',
        ]
        for task in read_tasks:
            receipt = ExemptionDetector.detect(
                task_description=task,
                changed_files=['src/main.py'],
            )
            assert receipt is not None, f"'{task}' should be detected as read-only"
            assert receipt.reason == 'read_only', f"'{task}' reason mismatch"

    def test_small_task_keywords_list(self):
        small_tasks = [
            'Fix typo in the error message',
            'Correct spelling of variable',
            'Format the code with ruff',
            'Fix lint warnings',
            'Add test for new endpoint',
            'Update test expectations',
            'Trivial change to config',
            'Minor formatting adjustment',
            'Simple rename of local variable',
        ]
        for task in small_tasks:
            receipt = ExemptionDetector.detect(
                task_description=task,
                changed_files=['src/main.py'],
            )
            assert receipt is not None, f"'{task}' should be detected as small task"

    def test_known_pattern_keywords_list(self):
        pattern_tasks = [
            'Rename the configuration class',
            'Refactor the database layer',
            'Extract method from the handler',
            'Extract function from main',
            'Move file to new directory',
            'Add logging to the service',
            'Add error handling for edge case',
            'Add validation to the input parser',
        ]
        for task in pattern_tasks:
            receipt = ExemptionDetector.detect(
                task_description=task,
                changed_files=['src/main.py', 'src/utils.py'],
            )
            assert receipt is not None, f"'{task}' should be detected as known pattern"
            assert receipt.reason == 'known_pattern', f"'{task}' reason mismatch"
