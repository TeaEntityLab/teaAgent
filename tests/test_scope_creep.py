"""Tests for scope-creep detection tests (TASK-H5-001-05)."""

import pytest
from teaagent.scope_creep import (
    ScopeCreepDetector,
    ScopeCreepResult,
    ScopeCreepTest,
)


def test_to_dict_and_from_dict():
    """Test test serialization."""
    test = ScopeCreepTest(
        test_id='creep-001',
        name='Test 1',
        allowed_actions={'read_file', 'write_file'},
        allowed_file_patterns={'*.py'},
    )

    data = test.to_dict()
    restored = ScopeCreepTest.from_dict(data)

    assert restored.test_id == test.test_id
    assert restored.name == test.name
    assert restored.allowed_actions == test.allowed_actions


def test_result_to_dict_and_from_dict():
    """Test result serialization."""
    result = ScopeCreepResult(
        test_id='creep-001',
        actual_actions={'read_file', 'write_file'},
        creep_score=0.15,
        passed=True,
    )

    data = result.to_dict()
    restored = ScopeCreepResult.from_dict(data)

    assert restored.test_id == result.test_id
    assert restored.creep_score == result.creep_score
    assert restored.passed == result.passed


@pytest.fixture
def detector():
    """Fixture for ScopeCreepDetector."""
    return ScopeCreepDetector()


def test_check_action_violations_none(detector):
    """Test action violation check with no violations."""
    allowed = {'read_file', 'write_file'}
    actual = {'read_file', 'write_file'}
    violations = detector.check_action_violations(allowed, actual)
    assert len(violations) == 0


def test_check_action_violations_with_violations(detector):
    """Test action violation check with violations."""
    allowed = {'read_file'}
    actual = {'read_file', 'delete_file'}
    violations = detector.check_action_violations(allowed, actual)
    assert len(violations) == 1
    assert 'delete_file' in violations[0]


def test_check_domain_violations_none(detector):
    """Test domain violation check with no violations."""
    allowed = {'localhost', 'api.example.com'}
    actual = {'localhost'}
    violations = detector.check_domain_violations(allowed, actual)
    assert len(violations) == 0


def test_check_domain_violations_with_violations(detector):
    """Test domain violation check with violations."""
    allowed = {'localhost'}
    actual = {'localhost', 'external-api.com'}
    violations = detector.check_domain_violations(allowed, actual)
    assert len(violations) == 1


def test_check_file_violations_none(detector):
    """Test file violation check with no violations."""
    allowed = {'*.py', '*.md'}
    actual = {'test.py', 'README.md'}
    violations = detector.check_file_violations(allowed, actual)
    assert len(violations) == 0


def test_check_file_violations_with_violations(detector):
    """Test file violation check with violations."""
    allowed = {'*.py'}
    actual = {'test.py', 'config.json'}
    violations = detector.check_file_violations(allowed, actual)
    assert len(violations) == 1
    assert 'config.json' in violations[0]


def test_calculate_creep_score_no_creep(detector):
    """Test creep score calculation with no creep."""
    score = detector.calculate_creep_score([], 10, 100, 5, 50)
    assert score == 0.05  # Action score (0.025) + file score (0.025)


def test_calculate_creep_score_high_creep(detector):
    """Test creep score calculation with high creep."""
    violations = ['violation1', 'violation2', 'violation3']
    score = detector.calculate_creep_score(violations, 150, 100, 75, 50)
    assert score > 0.5


def test_detect_scope_creep_passed(detector):
    """Test scope-creep detection when passed."""
    test = ScopeCreepTest(
        test_id='creep-001',
        name='Test 1',
        allowed_actions={'read_file', 'write_file'},
        allowed_file_patterns={'*.py'},
        max_action_count=100,
        max_file_access_count=50,
    )

    execution_data = {
        'actions': ['read_file', 'write_file'],
        'domains': [],
        'files': ['test.py'],
        'action_count': 10,
        'file_access_count': 5,
    }

    result = detector.detect_scope_creep(test, execution_data)

    assert result.passed
    assert len(result.violations) == 0


def test_detect_scope_creep_failed(detector):
    """Test scope-creep detection when failed."""
    test = ScopeCreepTest(
        test_id='creep-001',
        name='Test 1',
        allowed_actions={'read_file'},
        allowed_file_patterns={'*.py'},
        max_action_count=100,
        max_file_access_count=50,
    )

    execution_data = {
        'actions': ['read_file', 'delete_file'],  # Unauthorized action
        'domains': [],
        'files': ['test.py', 'config.json'],  # Unauthorized file
        'action_count': 10,
        'file_access_count': 5,
    }

    result = detector.detect_scope_creep(test, execution_data)

    assert not result.passed
    assert len(result.violations) > 0


def test_create_default_scope_creep_tests(detector):
    """Test creating default scope-creep tests."""
    tests = detector.create_default_scope_creep_tests()

    assert len(tests) >= 3
    assert all(isinstance(t, ScopeCreepTest) for t in tests)


def test_convert_to_eval_test(detector):
    """Test converting scope-creep test to eval test."""
    creep_test = ScopeCreepTest(
        test_id='creep-001',
        name='Test 1',
        allowed_actions={'read_file'},
        allowed_file_patterns={'*.py'},
    )

    eval_test = detector.convert_to_eval_test(creep_test)

    assert eval_test.test_id == creep_test.test_id
    assert eval_test.name == creep_test.name
    assert 'allowed_actions' in eval_test.metadata
    assert 'allowed_file_patterns' in eval_test.metadata
