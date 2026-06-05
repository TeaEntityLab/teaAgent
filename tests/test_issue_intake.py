"""Unit tests for issue intake module."""

from datetime import datetime

import pytest

from teaagent.issue_intake import (
    AmbiguityDetector,
    ChecklistGenerator,
    CommandSuggester,
    IssueParser,
    IssueType,
    ParsedIssue,
    PlanArtifact,
    PlanGenerator,
)


@pytest.fixture
def parser():
    """Create an IssueParser instance."""
    return IssueParser()


def test_parse_simple_issue(parser):
    """Test parsing a simple issue."""
    text = 'Fix authentication bug in login module'
    parsed = parser.parse(text)

    assert parsed.title == 'Fix authentication bug in login module'
    assert parsed.description == text
    assert parsed.issue_type == IssueType.BUG
    assert parsed.raw_text == text


def test_parse_issue_with_title(parser):
    """Test parsing issue with explicit title."""
    text = """# Fix authentication bug

The login module is not validating JWT tokens correctly."""
    parsed = parser.parse(text)

    assert parsed.title == 'Fix authentication bug'
    assert parsed.issue_type == IssueType.BUG


def test_parse_issue_with_steps(parser):
    """Test parsing issue with steps to reproduce."""
    text = """# Login fails

Steps to reproduce:
- Navigate to login page
- Enter invalid credentials
- Click login button

Expected: Error message shown
Actual: Page crashes"""
    parsed = parser.parse(text)

    assert parsed.steps_to_reproduce is not None
    assert len(parsed.steps_to_reproduce) == 3
    assert 'Navigate to login page' in parsed.steps_to_reproduce
    assert parsed.expected_behavior == 'Error message shown'
    assert parsed.actual_behavior == 'Page crashes'


def test_parse_issue_with_files(parser):
    """Test parsing issue with affected files."""
    text = """# Bug in auth module

Affected files:
- src/auth/login.py
- src/auth/jwt.py

The JWT validation is broken."""
    parsed = parser.parse(text)

    assert parsed.affected_files is not None
    assert len(parsed.affected_files) == 2
    assert 'src/auth/login.py' in parsed.affected_files
    assert 'src/auth/jwt.py' in parsed.affected_files


def test_parse_issue_with_components(parser):
    """Test parsing issue with affected components."""
    text = """# Performance issue

Affected components:
- Database layer
- Cache layer

Queries are slow."""
    parsed = parser.parse(text)

    assert parsed.affected_components is not None
    assert len(parsed.affected_components) == 2
    assert 'Database layer' in parsed.affected_components


def test_classify_bug(parser):
    """Test classification of bug issues."""
    text = 'Fix authentication error in login module'
    parsed = parser.parse(text)

    assert parsed.issue_type == IssueType.BUG


def test_classify_feature(parser):
    """Test classification of feature requests."""
    text = 'Add support for OAuth2 authentication'
    parsed = parser.parse(text)

    assert parsed.issue_type == IssueType.FEATURE


def test_classify_refactor(parser):
    """Test classification of refactor requests."""
    text = 'Refactor authentication module to use dependency injection'
    parsed = parser.parse(text)

    assert parsed.issue_type == IssueType.REFACTOR


def test_classify_performance_optimize(parser):
    """Test classification of performance optimization."""
    text = 'Optimize database queries for faster login'
    parsed = parser.parse(text)

    assert parsed.issue_type == IssueType.PERFORMANCE


def test_classify_documentation(parser):
    """Test classification of documentation issues."""
    text = 'Update documentation for authentication flow'
    parsed = parser.parse(text)

    assert parsed.issue_type == IssueType.DOCUMENTATION


def test_classify_performance(parser):
    """Test classification of performance issues."""
    text = 'Database queries are slow and need improvement'
    parsed = parser.parse(text)

    assert parsed.issue_type == IssueType.PERFORMANCE


def test_classify_security(parser):
    """Test classification of security issues."""
    text = 'Security vulnerability in JWT validation allows unauthorized access'
    parsed = parser.parse(text)

    assert parsed.issue_type == IssueType.SECURITY


def test_classify_unknown(parser):
    """Test classification of unknown issue types."""
    text = 'Some random issue description'
    parsed = parser.parse(text)

    assert parsed.issue_type == IssueType.UNKNOWN


def test_extract_priority(parser):
    """Test extraction of priority."""
    text = """# Critical bug

Priority: critical

This is a critical bug."""
    parsed = parser.parse(text)

    assert parsed.priority == 'critical'


def test_extract_priority_p0(parser):
    """Test extraction of P0 priority."""
    text = """# High priority issue

Priority: p0

This needs to be fixed."""
    parsed = parser.parse(text)

    assert parsed.priority == 'p0'


def test_parse_github_issue_placeholder(parser):
    """Test GitHub issue parsing raises ValueError when library not available."""
    # Mock the GITHUB_AVAILABLE flag to simulate library not installed
    import teaagent.issue_intake as issue_intake_module

    original_available = issue_intake_module.GITHUB_AVAILABLE
    try:
        issue_intake_module.GITHUB_AVAILABLE = False
        with pytest.raises(ValueError, match='PyGithub is not installed'):
            parser.extract_github_issue('https://github.com/user/repo/issues/123')
    finally:
        issue_intake_module.GITHUB_AVAILABLE = original_available


def test_parse_complex_issue(parser):
    """Test parsing a complex issue with all fields."""
    text = """# Fix authentication timeout

The authentication module times out after 30 seconds.

Steps to reproduce:
- Open login page
- Enter valid credentials
- Click login
- Wait for response

Expected: Login completes within 5 seconds
Actual: Login times out after 30 seconds

Affected files:
- src/auth/login.py
- src/auth/session.py

Affected components:
- Authentication service
- Session manager

Priority: high

This is blocking user login."""
    parsed = parser.parse(text)

    assert parsed.title == 'Fix authentication timeout'
    assert parsed.issue_type == IssueType.BUG
    assert len(parsed.steps_to_reproduce) == 4
    assert parsed.expected_behavior == 'Login completes within 5 seconds'
    assert parsed.actual_behavior == 'Login times out after 30 seconds'
    assert len(parsed.affected_files) == 2
    assert len(parsed.affected_components) == 2
    assert parsed.priority == 'high'


def test_parse_issue_with_alternate_section_names(parser):
    """Test parsing with alternate section name formats."""
    text = """# Bug report

Reproduction steps:
- Step 1
- Step 2

Expected result: Success
Current behavior: Failure"""
    parsed = parser.parse(text)

    assert parsed.steps_to_reproduce is not None
    assert len(parsed.steps_to_reproduce) == 2
    assert parsed.expected_behavior == 'Success'
    assert parsed.actual_behavior == 'Failure'


def test_parse_issue_missing_sections(parser):
    """Test parsing issue with missing optional sections."""
    text = 'Simple issue description'
    parsed = parser.parse(text)

    assert parsed.title == 'Simple issue description'
    assert parsed.steps_to_reproduce is None
    assert parsed.expected_behavior is None
    assert parsed.actual_behavior is None
    assert parsed.affected_files is None
    assert parsed.affected_components is None
    assert parsed.priority is None


@pytest.fixture
def ambiguity_detector():
    """Create an AmbiguityDetector instance."""
    return AmbiguityDetector(llm_client=None)


def test_ambiguity_detection_complete_issue(ambiguity_detector):
    """Test ambiguity detection for a complete issue."""
    issue = ParsedIssue(
        title='Fix authentication bug',
        description='Detailed description of the bug',
        issue_type=IssueType.BUG,
        steps_to_reproduce=['Step 1', 'Step 2'],
        expected_behavior='Expected result',
        actual_behavior='Actual result',
        affected_files=['file1.py'],
        affected_components=['auth'],
        priority='high',
        raw_text='Complete issue text',
    )

    report = ambiguity_detector.detect(issue)

    assert report.score < 30  # Should have low ambiguity
    assert len(report.missing_fields) == 0
    assert report.confidence > 0.7


def test_ambiguity_detection_missing_steps(ambiguity_detector):
    """Test ambiguity detection for issue missing steps."""
    issue = ParsedIssue(
        title='Bug in login',
        description='Login is broken',
        issue_type=IssueType.BUG,
        steps_to_reproduce=None,
        expected_behavior='Should work',
        actual_behavior='Does not work',
        affected_files=None,
        affected_components=None,
        priority=None,
        raw_text='Incomplete issue',
    )

    report = ambiguity_detector.detect(issue)

    assert 'steps_to_reproduce' in report.missing_fields
    assert report.score >= 20
    assert any('steps' in rec.lower() for rec in report.recommendations)


def test_ambiguity_detection_missing_expected(ambiguity_detector):
    """Test ambiguity detection for issue missing expected behavior."""
    issue = ParsedIssue(
        title='Performance issue',
        description='Slow response',
        issue_type=IssueType.PERFORMANCE,
        steps_to_reproduce=['Step 1'],
        expected_behavior=None,
        actual_behavior='Takes 10 seconds',
        affected_files=None,
        affected_components=None,
        priority=None,
        raw_text='Incomplete issue',
    )

    report = ambiguity_detector.detect(issue)

    assert 'expected_behavior' in report.missing_fields
    assert any('expected' in rec.lower() for rec in report.recommendations)


def test_ambiguity_detection_missing_actual(ambiguity_detector):
    """Test ambiguity detection for issue missing actual behavior."""
    issue = ParsedIssue(
        title='Feature request',
        description='Add new feature',
        issue_type=IssueType.FEATURE,
        steps_to_reproduce=None,
        expected_behavior='Feature works',
        actual_behavior=None,
        affected_files=None,
        affected_components=None,
        priority=None,
        raw_text='Incomplete issue',
    )

    report = ambiguity_detector.detect(issue)

    assert 'actual_behavior' in report.missing_fields
    assert any('actual' in rec.lower() for rec in report.recommendations)


def test_ambiguity_detection_vague_description(ambiguity_detector):
    """Test ambiguity detection for vague description."""
    issue = ParsedIssue(
        title='Some issue',
        description='Maybe something is wrong',
        issue_type=IssueType.UNKNOWN,
        steps_to_reproduce=None,
        expected_behavior=None,
        actual_behavior=None,
        affected_files=None,
        affected_components=None,
        priority=None,
        raw_text='Vague issue',
    )

    report = ambiguity_detector.detect(issue)

    assert report.score > 50  # High ambiguity
    assert 'description' in report.unclear_sections
    assert 'issue_type' in report.missing_fields


def test_ambiguity_score_calculation(ambiguity_detector):
    """Test ambiguity score calculation."""
    # Low ambiguity
    complete_issue = ParsedIssue(
        title='Complete issue',
        description='Detailed description with lots of information',
        issue_type=IssueType.BUG,
        steps_to_reproduce=['Step 1', 'Step 2', 'Step 3'],
        expected_behavior='Expected',
        actual_behavior='Actual',
        affected_files=['file.py'],
        affected_components=['component'],
        priority='high',
        raw_text='Complete',
    )
    assert ambiguity_detector.score(complete_issue) < 30

    # High ambiguity
    vague_issue = ParsedIssue(
        title='Vague',
        description='Short',
        issue_type=IssueType.UNKNOWN,
        steps_to_reproduce=None,
        expected_behavior=None,
        actual_behavior=None,
        affected_files=None,
        affected_components=None,
        priority=None,
        raw_text='Vague',
    )
    assert ambiguity_detector.score(vague_issue) > 50


def test_ambiguity_confidence_inverse(ambiguity_detector):
    """Test that confidence is inverse of ambiguity score."""
    high_ambiguity_issue = ParsedIssue(
        title='Vague',
        description='Short',
        issue_type=IssueType.UNKNOWN,
        steps_to_reproduce=None,
        expected_behavior=None,
        actual_behavior=None,
        affected_files=None,
        affected_components=None,
        priority=None,
        raw_text='Vague',
    )

    report = ambiguity_detector.detect(high_ambiguity_issue)
    assert report.confidence < 0.5  # Low confidence for high ambiguity

    low_ambiguity_issue = ParsedIssue(
        title='Complete',
        description='Detailed description with comprehensive information',
        issue_type=IssueType.BUG,
        steps_to_reproduce=['Step 1', 'Step 2'],
        expected_behavior='Expected',
        actual_behavior='Actual',
        affected_files=['file.py'],
        affected_components=['component'],
        priority='high',
        raw_text='Complete',
    )

    report = ambiguity_detector.detect(low_ambiguity_issue)
    assert report.confidence > 0.7  # High confidence for low ambiguity


@pytest.fixture
def plan_generator():
    """Create a PlanGenerator instance."""
    return PlanGenerator(plan_mode=None, context_gatherer=None)


def test_plan_generator_bug(plan_generator):
    """Test plan generation for bug issue."""
    issue = ParsedIssue(
        title='Fix authentication bug',
        description='Authentication fails for valid users',
        issue_type=IssueType.BUG,
        steps_to_reproduce=['Step 1', 'Step 2'],
        expected_behavior='User can login',
        actual_behavior='Login fails',
        affected_files=['auth.py'],
        affected_components=['auth'],
        priority='high',
        raw_text='Bug issue',
    )

    from pathlib import Path

    plan = plan_generator.generate(issue, Path('/tmp/workspace'))

    assert plan.title == 'Fix authentication bug'
    assert plan.goal == 'Fix: Fix authentication bug'
    assert 'bug' in plan.approach.lower()
    assert len(plan.steps) > 0
    assert len(plan.affected_files) == 1
    assert plan.ambiguity_score >= 0


def test_plan_generator_feature(plan_generator):
    """Test plan generation for feature request."""
    issue = ParsedIssue(
        title='Add OAuth2 support',
        description='Add OAuth2 authentication',
        issue_type=IssueType.FEATURE,
        steps_to_reproduce=None,
        expected_behavior=None,
        actual_behavior=None,
        affected_files=None,
        affected_components=None,
        priority=None,
        raw_text='Feature request',
    )

    from pathlib import Path

    plan = plan_generator.generate(issue, Path('/tmp/workspace'))

    assert plan.title == 'Add OAuth2 support'
    assert plan.goal == 'Implement: Add OAuth2 support'
    assert 'feature' in plan.approach.lower() or 'implement' in plan.approach.lower()


def test_plan_generator_steps(plan_generator):
    """Test that plan includes appropriate steps."""
    issue = ParsedIssue(
        title='Bug fix',
        description='Fix bug',
        issue_type=IssueType.BUG,
        steps_to_reproduce=['Step 1'],
        expected_behavior='Expected',
        actual_behavior='Actual',
        affected_files=['file.py'],
        affected_components=None,
        priority=None,
        raw_text='Bug',
    )

    from pathlib import Path

    plan = plan_generator.generate(issue, Path('/tmp/workspace'))

    assert len(plan.steps) >= 3  # At least analyze, implement, verify
    step_descriptions = [step.description for step in plan.steps]
    assert any('analyze' in desc.lower() for desc in step_descriptions)
    assert any(
        'implement' in desc.lower() or 'fix' in desc.lower()
        for desc in step_descriptions
    )
    assert any(
        'test' in desc.lower() or 'verify' in desc.lower() for desc in step_descriptions
    )


def test_plan_generator_risks(plan_generator):
    """Test that plan identifies appropriate risks."""
    issue = ParsedIssue(
        title='Security fix',
        description='Fix security vulnerability',
        issue_type=IssueType.SECURITY,
        steps_to_reproduce=None,
        expected_behavior=None,
        actual_behavior=None,
        affected_files=['auth.py', 'session.py'],
        affected_components=None,
        priority=None,
        raw_text='Security issue',
    )

    from pathlib import Path

    plan = plan_generator.generate(issue, Path('/tmp/workspace'))

    assert len(plan.risks) > 0
    assert any('security' in risk.lower() for risk in plan.risks)
    assert any('2 file' in risk for risk in plan.risks)


def test_plan_generator_ambiguity_score(plan_generator):
    """Test that plan includes ambiguity score."""
    issue = ParsedIssue(
        title='Complete issue',
        description='Detailed description',
        issue_type=IssueType.BUG,
        steps_to_reproduce=['Step 1', 'Step 2'],
        expected_behavior='Expected',
        actual_behavior='Actual',
        affected_files=['file.py'],
        affected_components=['component'],
        priority='high',
        raw_text='Complete',
    )

    from pathlib import Path

    plan = plan_generator.generate(issue, Path('/tmp/workspace'))

    assert plan.ambiguity_score >= 0
    assert plan.ambiguity_score <= 100


def test_plan_generator_explore(plan_generator):
    """Test workspace exploration."""
    issue = ParsedIssue(
        title='Test issue',
        description='Test',
        issue_type=IssueType.BUG,
        steps_to_reproduce=None,
        expected_behavior=None,
        actual_behavior=None,
        affected_files=['file.py'],
        affected_components=['component'],
        priority=None,
        raw_text='Test',
    )

    from pathlib import Path

    context = plan_generator.explore(issue, Path('/tmp/workspace'))

    assert 'workspace_root' in context
    assert 'issue_type' in context
    assert context['issue_type'] == 'bug'
    assert context['affected_files'] == ['file.py']


def test_plan_step_permission_modes(plan_generator):
    """Test that plan steps have appropriate permission modes."""
    issue = ParsedIssue(
        title='Bug fix',
        description='Fix bug',
        issue_type=IssueType.BUG,
        steps_to_reproduce=['Step 1'],
        expected_behavior='Expected',
        actual_behavior='Actual',
        affected_files=['file.py'],
        affected_components=None,
        priority=None,
        raw_text='Bug',
    )

    from pathlib import Path

    plan = plan_generator.generate(issue, Path('/tmp/workspace'))

    # Check that read-only steps have read_only permission mode
    read_only_steps = [
        step for step in plan.steps if step.permission_mode == 'read_only'
    ]
    assert len(read_only_steps) > 0

    # Check that implementation steps have prompt permission mode
    prompt_steps = [step for step in plan.steps if step.permission_mode == 'prompt']
    assert len(prompt_steps) > 0

    # Check that destructive steps are marked
    destructive_steps = [step for step in plan.steps if step.destructive]
    assert len(destructive_steps) > 0


@pytest.fixture
def command_suggester():
    """Create a CommandSuggester instance."""
    return CommandSuggester()


def test_command_suggester_low_ambiguity(command_suggester):
    """Test command suggestion for low ambiguity plan."""
    plan = PlanArtifact(
        id='test-id',
        title='Simple bug fix',
        goal='Fix: Simple bug fix',
        approach='Fix the bug',
        steps=[],
        affected_files=['file.py'],
        risks=['Minor risk'],
        created_at=datetime.now(),
        ambiguity_score=10,
    )

    suggestion = command_suggester.suggest(plan)

    assert suggestion.permission_mode == 'prompt'
    assert 'teaagent run' in suggestion.command
    assert len(suggestion.alternatives) > 0
    assert 'read_only' in suggestion.alternatives[0]


def test_command_suggester_high_ambiguity(command_suggester):
    """Test command suggestion for high ambiguity plan."""
    plan = PlanArtifact(
        id='test-id',
        title='Vague issue',
        goal='Address: Vague issue',
        approach='Analyze and fix',
        steps=[],
        affected_files=[],
        risks=[],
        created_at=datetime.now(),
        ambiguity_score=80,
    )

    suggestion = command_suggester.suggest(plan)

    assert suggestion.permission_mode == 'read_only'
    assert 'ambiguity' in suggestion.reasoning.lower()


def test_command_suggester_security_risk(command_suggester):
    """Test command suggestion for security risk."""
    plan = PlanArtifact(
        id='test-id',
        title='Security fix',
        goal='Secure: Security fix',
        approach='Fix security vulnerability',
        steps=[],
        affected_files=['auth.py'],
        risks=['Security vulnerability'],
        created_at=datetime.now(),
        ambiguity_score=20,
    )

    suggestion = command_suggester.suggest(plan)

    assert suggestion.permission_mode == 'prompt'
    assert 'security' in suggestion.reasoning.lower()


def test_command_suggester_many_files(command_suggester):
    """Test command suggestion for plan with many affected files."""
    plan = PlanArtifact(
        id='test-id',
        title='Large refactor',
        goal='Refactor: Large refactor',
        approach='Refactor code',
        steps=[],
        affected_files=[f'file{i}.py' for i in range(10)],
        risks=['Refactoring risk'],
        created_at=datetime.now(),
        ambiguity_score=30,
    )

    suggestion = command_suggester.suggest(plan)

    assert suggestion.permission_mode == 'prompt'
    assert 'many' in suggestion.reasoning.lower() or '10' in suggestion.reasoning


def test_command_suggester_recommend_mode(command_suggester):
    """Test permission mode recommendation."""
    low_ambiguity_plan = PlanArtifact(
        id='test-id',
        title='Clear issue',
        goal='Fix: Clear issue',
        approach='Fix',
        steps=[],
        affected_files=['file.py'],
        risks=[],
        created_at=datetime.now(),
        ambiguity_score=10,
    )

    mode = command_suggester.recommend_mode(low_ambiguity_plan)
    assert mode == 'prompt'

    high_ambiguity_plan = PlanArtifact(
        id='test-id',
        title='Vague',
        goal='Address: Vague',
        approach='Analyze',
        steps=[],
        affected_files=[],
        risks=[],
        created_at=datetime.now(),
        ambiguity_score=80,
    )

    mode = command_suggester.recommend_mode(high_ambiguity_plan)
    assert mode == 'read_only'


@pytest.fixture
def checklist_generator():
    """Create a ChecklistGenerator instance."""
    return ChecklistGenerator()


def test_checklist_generator_bug(checklist_generator):
    """Test checklist generation for bug fix."""
    plan = PlanArtifact(
        id='test-id',
        title='Bug fix',
        goal='Fix: Bug fix',
        approach='Fix the bug',
        steps=[],
        affected_files=['file.py'],
        risks=['Regression risk'],
        created_at=datetime.now(),
        ambiguity_score=20,
    )

    checklist = checklist_generator.generate(plan)

    assert len(checklist.functional_requirements) > 0
    assert len(checklist.edge_cases) > 0
    assert len(checklist.testing_requirements) > 0
    assert len(checklist.success_criteria) > 0

    assert any('bug' in req.lower() for req in checklist.functional_requirements)
    assert 'All tests pass' in checklist.success_criteria


def test_checklist_generator_feature(checklist_generator):
    """Test checklist generation for feature."""
    plan = PlanArtifact(
        id='test-id',
        title='New feature',
        goal='Implement: New feature',
        approach='Implement feature',
        steps=[],
        affected_files=['file.py', 'feature.py'],
        risks=['Integration risk'],
        created_at=datetime.now(),
        ambiguity_score=30,
    )

    checklist = checklist_generator.generate(plan)

    assert any('feature' in req.lower() for req in checklist.functional_requirements)
    assert 'Unit tests' in checklist.testing_requirements[0]


def test_checklist_generator_security(checklist_generator):
    """Test checklist generation for security issue."""
    plan = PlanArtifact(
        id='test-id',
        title='Security fix',
        goal='Secure: Security fix',
        approach='Fix security',
        steps=[],
        affected_files=['auth.py'],
        risks=['Security vulnerability'],
        created_at=datetime.now(),
        ambiguity_score=20,
    )

    checklist = checklist_generator.generate(plan)

    assert any('security' in case_.lower() for case_ in checklist.edge_cases)
    assert any('security' in req.lower() for req in checklist.testing_requirements)


def test_checklist_generator_performance(checklist_generator):
    """Test checklist generation for performance issue."""
    plan = PlanArtifact(
        id='test-id',
        title='Performance fix',
        goal='Optimize: Performance fix',
        approach='Optimize performance',
        steps=[],
        affected_files=['db.py'],
        risks=['Performance regression'],
        created_at=datetime.now(),
        ambiguity_score=25,
    )

    checklist = checklist_generator.generate(plan)

    assert any('performance' in req.lower() for req in checklist.testing_requirements)


def test_checklist_generator_affected_files(checklist_generator):
    """Test that checklist includes affected files."""
    plan = PlanArtifact(
        id='test-id',
        title='Multi-file fix',
        goal='Fix: Multi-file fix',
        approach='Fix',
        steps=[],
        affected_files=['file1.py', 'file2.py', 'file3.py'],
        risks=[],
        created_at=datetime.now(),
        ambiguity_score=15,
    )

    checklist = checklist_generator.generate(plan)

    assert any('3 file' in req for req in checklist.functional_requirements)
    assert any('3' in req for req in checklist.testing_requirements)
