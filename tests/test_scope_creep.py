"""Tests for scope-creep detection tests (TASK-H5-001-05)."""

import unittest

from teaagent.scope_creep import (
    ScopeCreepDetector,
    ScopeCreepResult,
    ScopeCreepTest,
)


class TestScopeCreepTest(unittest.TestCase):
    """Test scope-creep test management."""

    def test_to_dict_and_from_dict(self):
        """Test test serialization."""
        test = ScopeCreepTest(
            test_id='creep-001',
            name='Test 1',
            allowed_actions={'read_file', 'write_file'},
            allowed_file_patterns={'*.py'},
        )

        data = test.to_dict()
        restored = ScopeCreepTest.from_dict(data)

        self.assertEqual(restored.test_id, test.test_id)
        self.assertEqual(restored.name, test.name)
        self.assertEqual(restored.allowed_actions, test.allowed_actions)


class TestScopeCreepResult(unittest.TestCase):
    """Test scope-creep result management."""

    def test_to_dict_and_from_dict(self):
        """Test result serialization."""
        result = ScopeCreepResult(
            test_id='creep-001',
            actual_actions={'read_file', 'write_file'},
            creep_score=0.15,
            passed=True,
        )

        data = result.to_dict()
        restored = ScopeCreepResult.from_dict(data)

        self.assertEqual(restored.test_id, result.test_id)
        self.assertEqual(restored.creep_score, result.creep_score)
        self.assertEqual(restored.passed, result.passed)


class TestScopeCreepDetector(unittest.TestCase):
    """Test scope-creep detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = ScopeCreepDetector()

    def test_check_action_violations_none(self):
        """Test action violation check with no violations."""
        allowed = {'read_file', 'write_file'}
        actual = {'read_file', 'write_file'}
        violations = self.detector.check_action_violations(allowed, actual)
        self.assertEqual(len(violations), 0)

    def test_check_action_violations_with_violations(self):
        """Test action violation check with violations."""
        allowed = {'read_file'}
        actual = {'read_file', 'delete_file'}
        violations = self.detector.check_action_violations(allowed, actual)
        self.assertEqual(len(violations), 1)
        self.assertIn('delete_file', violations[0])

    def test_check_domain_violations_none(self):
        """Test domain violation check with no violations."""
        allowed = {'localhost', 'api.example.com'}
        actual = {'localhost'}
        violations = self.detector.check_domain_violations(allowed, actual)
        self.assertEqual(len(violations), 0)

    def test_check_domain_violations_with_violations(self):
        """Test domain violation check with violations."""
        allowed = {'localhost'}
        actual = {'localhost', 'external-api.com'}
        violations = self.detector.check_domain_violations(allowed, actual)
        self.assertEqual(len(violations), 1)

    def test_check_file_violations_none(self):
        """Test file violation check with no violations."""
        allowed = {'*.py', '*.md'}
        actual = {'test.py', 'README.md'}
        violations = self.detector.check_file_violations(allowed, actual)
        self.assertEqual(len(violations), 0)

    def test_check_file_violations_with_violations(self):
        """Test file violation check with violations."""
        allowed = {'*.py'}
        actual = {'test.py', 'config.json'}
        violations = self.detector.check_file_violations(allowed, actual)
        self.assertEqual(len(violations), 1)
        self.assertIn('config.json', violations[0])

    def test_calculate_creep_score_no_creep(self):
        """Test creep score calculation with no creep."""
        score = self.detector.calculate_creep_score([], 10, 100, 5, 50)
        self.assertEqual(score, 0.05)  # Action score (0.025) + file score (0.025)

    def test_calculate_creep_score_high_creep(self):
        """Test creep score calculation with high creep."""
        violations = ['violation1', 'violation2', 'violation3']
        score = self.detector.calculate_creep_score(violations, 150, 100, 75, 50)
        self.assertGreater(score, 0.5)

    def test_detect_scope_creep_passed(self):
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

        result = self.detector.detect_scope_creep(test, execution_data)

        self.assertTrue(result.passed)
        self.assertEqual(len(result.violations), 0)

    def test_detect_scope_creep_failed(self):
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

        result = self.detector.detect_scope_creep(test, execution_data)

        self.assertFalse(result.passed)
        self.assertGreater(len(result.violations), 0)

    def test_create_default_scope_creep_tests(self):
        """Test creating default scope-creep tests."""
        tests = self.detector.create_default_scope_creep_tests()

        self.assertGreaterEqual(len(tests), 3)
        self.assertTrue(all(isinstance(t, ScopeCreepTest) for t in tests))

    def test_convert_to_eval_test(self):
        """Test converting scope-creep test to eval test."""
        creep_test = ScopeCreepTest(
            test_id='creep-001',
            name='Test 1',
            allowed_actions={'read_file'},
            allowed_file_patterns={'*.py'},
        )

        eval_test = self.detector.convert_to_eval_test(creep_test)

        self.assertEqual(eval_test.test_id, creep_test.test_id)
        self.assertEqual(eval_test.name, creep_test.name)
        self.assertIn('allowed_actions', eval_test.metadata)
        self.assertIn('allowed_file_patterns', eval_test.metadata)


if __name__ == '__main__':
    unittest.main()
