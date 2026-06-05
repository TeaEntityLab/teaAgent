"""Issue-to-Plan Intake module for parsing and analyzing issues.

This module provides tools to parse issue text (GitHub issues, support tickets, etc.)
and extract structured information for plan generation.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from github import Auth, Github
    from github.GithubException import GithubException
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False


class IssueType(Enum):
    """Classification of issue types."""

    BUG = 'bug'
    FEATURE = 'feature'
    REFACTOR = 'refactor'
    DOCUMENTATION = 'documentation'
    PERFORMANCE = 'performance'
    SECURITY = 'security'
    UNKNOWN = 'unknown'


class AmbiguityCategory(Enum):
    """Categories of ambiguity in issue descriptions."""

    MISSING_STEPS = 'missing_steps'
    UNCLEAR_DESCRIPTION = 'unclear_description'
    MISSING_EXPECTED = 'missing_expected'
    MISSING_ACTUAL = 'missing_actual'
    VAGUE_SCOPE = 'vague_scope'
    NO_ISSUE_TYPE = 'no_issue_type'


@dataclass
class ParsedIssue:
    """Structured representation of a parsed issue."""

    title: str
    description: str
    issue_type: IssueType
    steps_to_reproduce: Optional[list[str]]
    expected_behavior: Optional[str]
    actual_behavior: Optional[str]
    affected_files: Optional[list[str]]
    affected_components: Optional[list[str]]
    priority: Optional[str]
    raw_text: str


@dataclass
class AmbiguityReport:
    """Report of ambiguity analysis."""

    score: float  # 0-100
    missing_fields: list[str]
    unclear_sections: list[str]
    confidence: float  # 0-1
    recommendations: list[str]


@dataclass
class PlanStep:
    """A single step in the plan."""

    description: str
    command: Optional[str]
    permission_mode: str
    destructive: bool


@dataclass
class PlanArtifact:
    """Generated plan artifact."""

    id: str  # UUID
    title: str
    goal: str
    approach: str
    steps: list[PlanStep]
    affected_files: list[str]
    risks: list[str]
    created_at: datetime
    ambiguity_score: float


@dataclass
class CommandSuggestion:
    """Suggested command to execute the plan."""

    command: str
    permission_mode: str
    reasoning: str
    alternatives: list[str]


@dataclass
class AcceptanceChecklist:
    """Generated acceptance checklist."""

    functional_requirements: list[str]
    edge_cases: list[str]
    testing_requirements: list[str]
    success_criteria: list[str]


class IssueParser:
    """Parses issue text into structured format."""

    def __init__(self) -> None:
        # Patterns for extracting structured information
        self._title_pattern = re.compile(r'^#\s+(.+)$|^Title:\s*(.+)$', re.MULTILINE)
        self._steps_pattern = re.compile(
            r'(?:Steps to reproduce|Reproduction steps|How to reproduce)[:\s]*\n((?:[-*]\s+.+\n?)+)',
            re.IGNORECASE,
        )
        self._expected_pattern = re.compile(
            r'(?:Expected behavior|Expected result|Expected)[:\s]*\n(.+?)(?:\n\n|\n(?:Actual|Current)|$)',
            re.IGNORECASE | re.DOTALL,
        )
        self._actual_pattern = re.compile(
            r'(?:Actual behavior|Actual result|Current behavior|Current)[:\s]*\n(.+?)(?:\n\n|\n(?:Steps|Expected|Reproduce)|$)',
            re.IGNORECASE | re.DOTALL,
        )
        self._files_pattern = re.compile(
            r'(?:Affected files|Files changed|Files)[:\s]*\n((?:[-*]\s+.+\n?)+)',
            re.IGNORECASE,
        )
        self._components_pattern = re.compile(
            r'(?:Affected components|Components|Modules)[:\s]*\n((?:[-*]\s+.+\n?)+)',
            re.IGNORECASE,
        )

    def parse(self, text: str, source: str = 'manual') -> ParsedIssue:
        """Parse issue text into structured format.

        Args:
            text: Raw issue text
            source: Source of issue (manual, github, jira, etc.)

        Returns:
            ParsedIssue with extracted fields
        """
        # Extract title
        title = self._extract_title(text) or 'Untitled Issue'

        # Extract structured sections
        steps_to_reproduce = self._extract_steps(text)
        expected_behavior = self._extract_expected(text)
        actual_behavior = self._extract_actual(text)
        affected_files = self._extract_files(text)
        affected_components = self._extract_components(text)

        # Determine issue type
        issue_type = self._classify_issue_type(text, title)

        # Extract priority from labels if present
        priority = self._extract_priority(text)

        return ParsedIssue(
            title=title,
            description=text,
            issue_type=issue_type,
            steps_to_reproduce=steps_to_reproduce,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            affected_files=affected_files,
            affected_components=affected_components,
            priority=priority,
            raw_text=text,
        )

    def extract_github_issue(self, issue_url: str) -> ParsedIssue:
        """Fetch and parse a GitHub issue from URL.

        Args:
            issue_url: GitHub issue URL

        Returns:
            ParsedIssue with extracted fields

        Raises:
            ValueError: If GitHub library is not available or token is missing
            GithubException: If GitHub API call fails
        """
        if not GITHUB_AVAILABLE:
            raise ValueError(
                'PyGithub is not installed. Install with: pip install PyGithub'
            )

        # Get GitHub token from environment
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError(
                'GITHUB_TOKEN environment variable is required for GitHub API access. '
                'Set it with: export GITHUB_TOKEN=your_token_here'
            )

        # Parse URL to extract owner/repo/issue_number
        # Expected format: https://github.com/owner/repo/issues/123
        parts = issue_url.rstrip('/').split('/')
        if len(parts) < 7 or parts[2] != 'github.com' or parts[5] != 'issues':
            raise ValueError(
                f'Invalid GitHub issue URL format: {issue_url}. '
                'Expected: https://github.com/owner/repo/issues/123'
            )

        owner = parts[3]
        repo = parts[4]
        try:
            issue_number = int(parts[6])
        except ValueError as exc:
            raise ValueError(
                f'Invalid issue number in URL: {issue_url}. '
                'Issue number must be numeric.'
            ) from exc

        try:
            # Authenticate with token
            auth = Auth.Token(token)
            g = Github(auth=auth)

            # Fetch the issue
            repo_obj = g.get_repo(f'{owner}/{repo}')
            issue_obj = repo_obj.get_issue(issue_number)

            # Build issue text from GitHub issue data
            issue_text = f'# {issue_obj.title}\n\n'
            issue_text += issue_obj.body or ''

            # Add labels as metadata
            if issue_obj.labels:
                issue_text += f'\n\nLabels: {", ".join(label.name for label in issue_obj.labels)}'

            # Parse using the existing parse method
            return self.parse(issue_text, source='github')

        except GithubException as exc:
            logger.error('GitHub API error: %s', exc)
            raise ValueError(f'Failed to fetch GitHub issue: {exc}') from exc

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract title from issue text."""
        match = self._title_pattern.search(text)
        if match:
            return match.group(1) or match.group(2)
        # First line is often the title
        lines = text.strip().split('\n')
        if lines:
            return lines[0].strip('#').strip()
        return None

    def _extract_steps(self, text: str) -> Optional[list[str]]:
        """Extract steps to reproduce from issue text."""
        match = self._steps_pattern.search(text)
        if match:
            steps_text = match.group(1)
            steps = [
                line.strip().lstrip('-*').strip()
                for line in steps_text.split('\n')
                if line.strip()
            ]
            return steps if steps else None
        return None

    def _extract_expected(self, text: str) -> Optional[str]:
        """Extract expected behavior from issue text."""
        match = self._expected_pattern.search(text)
        if match:
            return match.group(1).strip()
        # Try inline format: "Expected: value" or "Expected result: value"
        inline_match = re.search(
            r'Expected(?:\s+result)?:\s*(.+?)(?:\n|$)', text, re.IGNORECASE
        )
        if inline_match:
            return inline_match.group(1).strip()
        return None

    def _extract_actual(self, text: str) -> Optional[str]:
        """Extract actual behavior from issue text."""
        match = self._actual_pattern.search(text)
        if match:
            return match.group(1).strip()
        # Try inline format: "Actual: value", "Current: value", or "Current behavior: value"
        inline_match = re.search(
            r'(?:Actual|Current)(?:\s+(?:behavior|result))?:\s*(.+?)(?:\n|$)',
            text,
            re.IGNORECASE,
        )
        if inline_match:
            return inline_match.group(1).strip()
        return None

    def _extract_files(self, text: str) -> Optional[list[str]]:
        """Extract affected files from issue text."""
        match = self._files_pattern.search(text)
        if match:
            files_text = match.group(1)
            files = [
                line.strip().lstrip('-*').strip()
                for line in files_text.split('\n')
                if line.strip()
            ]
            return files if files else None
        return None

    def _extract_components(self, text: str) -> Optional[list[str]]:
        """Extract affected components from issue text."""
        match = self._components_pattern.search(text)
        if match:
            components_text = match.group(1)
            components = [
                line.strip().lstrip('-*').strip()
                for line in components_text.split('\n')
                if line.strip()
            ]
            return components if components else None
        return None

    def _classify_issue_type(self, text: str, title: str) -> IssueType:
        """Classify the issue type based on text content."""
        combined = (title + ' ' + text).lower()

        # Check for security indicators (highest priority due to specificity)
        security_keywords = ['security', 'vulnerability', 'exploit']
        if any(keyword in combined for keyword in security_keywords):
            return IssueType.SECURITY

        # Check for performance indicators (including optimize)
        perf_keywords = ['performance', 'slow', 'speed', 'latency', 'optimize', 'fast']
        if any(keyword in combined for keyword in perf_keywords):
            return IssueType.PERFORMANCE

        # Check for bug indicators
        bug_keywords = ['bug', 'fix', 'error', 'crash', 'broken', 'fail', 'incorrect']
        if any(keyword in combined for keyword in bug_keywords):
            return IssueType.BUG

        # Check for feature indicators
        feature_keywords = [
            'feature',
            'add',
            'implement',
            'new',
            'support',
            'enhancement',
        ]
        if any(keyword in combined for keyword in feature_keywords):
            return IssueType.FEATURE

        # Check for refactor indicators
        refactor_keywords = ['refactor', 'clean up', 'restructure', 'simplify']
        if any(keyword in combined for keyword in refactor_keywords):
            return IssueType.REFACTOR

        # Check for documentation indicators
        doc_keywords = ['documentation', 'docs', 'readme', 'comment', 'document']
        if any(keyword in combined for keyword in doc_keywords):
            return IssueType.DOCUMENTATION

        return IssueType.UNKNOWN

    def _extract_priority(self, text: str) -> Optional[str]:
        """Extract priority from issue text."""
        # Look for priority labels
        priority_pattern = re.compile(
            r'(?:Priority|priority)[:\s]*\s*(critical|high|medium|low|p0|p1|p2|p3)',
            re.IGNORECASE,
        )
        match = priority_pattern.search(text)
        if match:
            return match.group(1).lower()
        return None


class AmbiguityDetector:
    """Detects ambiguity in issue descriptions."""

    def __init__(self, llm_client: Optional[Any] = None):
        self._llm = llm_client

    def detect(self, issue: ParsedIssue) -> AmbiguityReport:
        """Detect ambiguity in parsed issue.

        Args:
            issue: Parsed issue to analyze

        Returns:
            AmbiguityReport with score and missing fields
        """
        missing_fields = []
        unclear_sections = []
        recommendations = []

        # Check for missing steps to reproduce
        if not issue.steps_to_reproduce:
            missing_fields.append('steps_to_reproduce')
            recommendations.append(
                'Add steps to reproduce to clarify how to trigger the issue'
            )

        # Check for missing expected behavior
        if not issue.expected_behavior:
            missing_fields.append('expected_behavior')
            recommendations.append(
                'Specify expected behavior to define success criteria'
            )

        # Check for missing actual behavior
        if not issue.actual_behavior:
            missing_fields.append('actual_behavior')
            recommendations.append(
                'Describe actual behavior to understand the current state'
            )

        # Check for vague description
        if len(issue.description) < 50:
            unclear_sections.append('description')
            recommendations.append('Provide a more detailed description of the issue')

        # Check for unknown issue type
        if issue.issue_type == IssueType.UNKNOWN:
            missing_fields.append('issue_type')
            recommendations.append(
                'Clarify the issue type (bug, feature, refactor, etc.)'
            )

        # Check for missing affected files/components
        if not issue.affected_files and not issue.affected_components:
            unclear_sections.append('scope')
            recommendations.append(
                'Specify affected files or components to narrow the scope'
            )

        # Calculate ambiguity score
        score = self._calculate_ambiguity_score(missing_fields, unclear_sections, issue)

        # Calculate confidence (inverse of ambiguity)
        confidence = 1.0 - (score / 100.0)

        return AmbiguityReport(
            score=score,
            missing_fields=missing_fields,
            unclear_sections=unclear_sections,
            confidence=confidence,
            recommendations=recommendations,
        )

    def score(self, issue: ParsedIssue) -> float:
        """Calculate ambiguity score (0-100).

        Args:
            issue: Parsed issue to analyze

        Returns:
            Ambiguity score from 0 (clear) to 100 (highly ambiguous)
        """
        report = self.detect(issue)
        return report.score

    def _calculate_ambiguity_score(
        self, missing_fields: list[str], unclear_sections: list[str], issue: ParsedIssue
    ) -> float:
        """Calculate overall ambiguity score."""
        score = 0.0

        # Weight missing fields heavily
        score += len(missing_fields) * 20

        # Weight unclear sections moderately
        score += len(unclear_sections) * 10

        # Check for vague language
        vague_words = ['some', 'sometimes', 'maybe', 'might', 'probably', 'seems']
        for word in vague_words:
            if word in issue.description.lower():
                score += 5

        # Cap at 100
        return min(score, 100.0)


class PlanGenerator:
    """Generates plan artifacts from issues."""

    def __init__(
        self, plan_mode: Optional[Any] = None, context_gatherer: Optional[Any] = None
    ):
        self._plan_mode = plan_mode
        self._context_gatherer = context_gatherer

    def generate(self, issue: ParsedIssue, workspace_root: Path) -> PlanArtifact:
        """Generate a plan artifact from the issue.

        Args:
            issue: Parsed issue
            workspace_root: Workspace root directory

        Returns:
            PlanArtifact with generated plan
        """
        # Generate plan ID
        plan_id = uuid4().hex

        # Build goal from issue
        goal = self._build_goal(issue)

        # Build approach based on issue type
        approach = self._build_approach(issue)

        # Generate steps based on issue type and content
        steps = self._generate_steps(issue)

        # Collect affected files
        affected_files = issue.affected_files or []

        # Identify risks
        risks = self._identify_risks(issue)

        # Calculate ambiguity score
        detector = AmbiguityDetector()
        ambiguity_report = detector.detect(issue)
        ambiguity_score = ambiguity_report.score

        return PlanArtifact(
            id=plan_id,
            title=issue.title,
            goal=goal,
            approach=approach,
            steps=steps,
            affected_files=affected_files,
            risks=risks,
            created_at=datetime.now(),
            ambiguity_score=ambiguity_score,
        )

    def explore(self, issue: ParsedIssue, workspace_root: Path) -> dict[str, Any]:
        """Explore workspace to understand context (uses PlanMode).

        Args:
            issue: Parsed issue
            workspace_root: Workspace root directory

        Returns:
            Dictionary with exploration context
        """
        # Placeholder for PlanMode exploration
        # In a full implementation, this would use PlanMode to explore the workspace
        # and gather context about affected files, components, etc.

        context = {
            'workspace_root': str(workspace_root),
            'issue_type': issue.issue_type.value,
            'affected_files': issue.affected_files or [],
            'affected_components': issue.affected_components or [],
            'exploration_enabled': self._plan_mode is not None,
        }

        return context

    def _build_goal(self, issue: ParsedIssue) -> str:
        """Build goal statement from issue."""
        if issue.issue_type == IssueType.BUG:
            return f'Fix: {issue.title}'
        elif issue.issue_type == IssueType.FEATURE:
            return f'Implement: {issue.title}'
        elif issue.issue_type == IssueType.REFACTOR:
            return f'Refactor: {issue.title}'
        elif issue.issue_type == IssueType.DOCUMENTATION:
            return f'Document: {issue.title}'
        elif issue.issue_type == IssueType.PERFORMANCE:
            return f'Optimize: {issue.title}'
        elif issue.issue_type == IssueType.SECURITY:
            return f'Secure: {issue.title}'
        else:
            return f'Address: {issue.title}'

    def _build_approach(self, issue: ParsedIssue) -> str:
        """Build approach description based on issue type."""
        approaches = {
            IssueType.BUG: 'Analyze the bug, identify root cause, implement fix, and verify with tests',
            IssueType.FEATURE: 'Design feature, implement changes, add tests, and update documentation',
            IssueType.REFACTOR: 'Analyze current implementation, refactor for clarity/maintainability, ensure tests pass',
            IssueType.DOCUMENTATION: 'Review code, write comprehensive documentation, verify accuracy',
            IssueType.PERFORMANCE: 'Profile performance, identify bottlenecks, optimize, measure improvements',
            IssueType.SECURITY: 'Analyze vulnerability, implement security fix, audit for similar issues',
            IssueType.UNKNOWN: 'Analyze issue, determine appropriate approach, implement solution',
        }
        return approaches.get(issue.issue_type, approaches[IssueType.UNKNOWN])

    def _generate_steps(self, issue: ParsedIssue) -> list[PlanStep]:
        """Generate plan steps based on issue content."""
        steps = []

        # Add analysis step
        steps.append(
            PlanStep(
                description='Analyze the issue and understand requirements',
                command=None,
                permission_mode='read_only',
                destructive=False,
            )
        )

        # Add exploration step if affected files are specified
        if issue.affected_files:
            steps.append(
                PlanStep(
                    description=f'Review affected files: {", ".join(issue.affected_files)}',
                    command=None,
                    permission_mode='read_only',
                    destructive=False,
                )
            )

        # Add implementation step based on issue type
        if issue.issue_type == IssueType.BUG:
            steps.append(
                PlanStep(
                    description='Implement bug fix',
                    command=None,
                    permission_mode='prompt',
                    destructive=True,
                )
            )
        elif issue.issue_type == IssueType.FEATURE:
            steps.append(
                PlanStep(
                    description='Implement new feature',
                    command=None,
                    permission_mode='prompt',
                    destructive=True,
                )
            )
        elif issue.issue_type == IssueType.REFACTOR:
            steps.append(
                PlanStep(
                    description='Refactor code',
                    command=None,
                    permission_mode='prompt',
                    destructive=True,
                )
            )

        # Add testing step
        steps.append(
            PlanStep(
                description='Add or update tests',
                command=None,
                permission_mode='prompt',
                destructive=True,
            )
        )

        # Add verification step
        steps.append(
            PlanStep(
                description='Verify implementation meets requirements',
                command=None,
                permission_mode='read_only',
                destructive=False,
            )
        )

        return steps

    def _identify_risks(self, issue: ParsedIssue) -> list[str]:
        """Identify potential risks based on issue content."""
        risks = []

        if issue.issue_type == IssueType.BUG:
            risks.append('Fix may introduce regressions')
        elif issue.issue_type == IssueType.FEATURE:
            risks.append('New feature may affect existing functionality')
        elif issue.issue_type == IssueType.REFACTOR:
            risks.append('Refactoring may introduce subtle bugs')
        elif issue.issue_type == IssueType.PERFORMANCE:
            risks.append('Optimizations may affect code readability')
        elif issue.issue_type == IssueType.SECURITY:
            risks.append('Security fix may break existing integrations')

        if issue.affected_files:
            risks.append(f'Changes to {len(issue.affected_files)} file(s)')

        return risks


class CommandSuggester:
    """Suggests safe commands to execute plans."""

    def __init__(self) -> None:
        pass

    def suggest(self, plan: PlanArtifact) -> CommandSuggestion:
        """Suggest a safe command to execute the plan.

        Args:
            plan: Plan artifact to execute

        Returns:
            CommandSuggestion with command and reasoning
        """
        # Determine permission mode based on ambiguity and risks
        permission_mode = self._recommend_permission_mode(plan)

        # Build command
        command = self._build_command(plan, permission_mode)

        # Build reasoning
        reasoning = self._build_reasoning(plan, permission_mode)

        # Generate alternatives
        alternatives = self._generate_alternatives(plan)

        return CommandSuggestion(
            command=command,
            permission_mode=permission_mode,
            reasoning=reasoning,
            alternatives=alternatives,
        )

    def recommend_mode(self, plan: PlanArtifact) -> str:
        """Recommend permission mode for the plan.

        Args:
            plan: Plan artifact

        Returns:
            Permission mode string
        """
        return self._recommend_permission_mode(plan)

    def _recommend_permission_mode(self, plan: PlanArtifact) -> str:
        """Recommend permission mode based on plan characteristics."""
        # High ambiguity -> read_only or prompt
        if plan.ambiguity_score > 50:
            return 'read_only'

        # Security issues -> prompt for safety
        if any('security' in risk.lower() for risk in plan.risks):
            return 'prompt'

        # Many affected files -> prompt for caution
        if len(plan.affected_files) > 5:
            return 'prompt'

        # Default to prompt for new issues
        return 'prompt'

    def _build_command(self, plan: PlanArtifact, permission_mode: str) -> str:
        """Build command to execute the plan."""
        # In a full implementation, this would construct the actual teaagent command
        # For now, return a placeholder
        return f'teaagent run --task "{plan.goal}" --permission-mode {permission_mode}'

    def _build_reasoning(self, plan: PlanArtifact, permission_mode: str) -> str:
        """Build reasoning for the permission mode recommendation."""
        reasoning_parts = []

        if plan.ambiguity_score > 50:
            reasoning_parts.append(
                f'High ambiguity score ({plan.ambiguity_score:.0f}/100) suggests read-only exploration first'
            )

        if any('security' in risk.lower() for risk in plan.risks):
            reasoning_parts.append('Security risks require careful review')

        if len(plan.affected_files) > 5:
            reasoning_parts.append(
                f'Many affected files ({len(plan.affected_files)}) warrant caution'
            )

        reasoning_parts.append(f'Recommended permission mode: {permission_mode}')

        return '. '.join(reasoning_parts)

    def _generate_alternatives(self, plan: PlanArtifact) -> list[str]:
        """Generate alternative command suggestions."""
        alternatives = []

        # Always offer read_only as an alternative
        alternatives.append(
            f'teaagent run --task "{plan.goal}" --permission-mode read_only'
        )

        # Offer plan mode for exploration
        alternatives.append(f'teaagent run --task "{plan.goal}" --permission-mode plan')

        return alternatives


class ChecklistGenerator:
    """Generates acceptance checklists from plans."""

    def __init__(self) -> None:
        pass

    def generate(self, plan: PlanArtifact) -> AcceptanceChecklist:
        """Generate an acceptance checklist from the plan.

        Args:
            plan: Plan artifact

        Returns:
            AcceptanceChecklist with functional requirements, edge cases, etc.
        """
        functional_requirements = self._generate_functional_requirements(plan)
        edge_cases = self._generate_edge_cases(plan)
        testing_requirements = self._generate_testing_requirements(plan)
        success_criteria = self._generate_success_criteria(plan)

        return AcceptanceChecklist(
            functional_requirements=functional_requirements,
            edge_cases=edge_cases,
            testing_requirements=testing_requirements,
            success_criteria=success_criteria,
        )

    def _generate_functional_requirements(self, plan: PlanArtifact) -> list[str]:
        """Generate functional requirements from plan."""
        requirements = []

        # Add goal as a requirement
        requirements.append(f'Goal: {plan.goal}')

        # Add requirements based on issue type
        if 'bug' in plan.goal.lower():
            requirements.append('Bug is fixed without introducing regressions')
        elif 'feature' in plan.goal.lower():
            requirements.append('New feature works as specified')
        elif 'refactor' in plan.goal.lower():
            requirements.append('Code is refactored while maintaining functionality')

        # Add requirements based on affected files
        if plan.affected_files:
            requirements.append(
                f'Changes to {len(plan.affected_files)} file(s) are correct'
            )

        return requirements

    def _generate_edge_cases(self, plan: PlanArtifact) -> list[str]:
        """Generate edge case considerations."""
        edge_cases = []

        # Common edge cases
        edge_cases.append('Handle empty inputs')
        edge_cases.append('Handle invalid inputs')
        edge_cases.append('Handle boundary conditions')

        # Add specific edge cases based on risks
        if any('security' in risk.lower() for risk in plan.risks):
            edge_cases.append('Handle unauthorized access attempts')
            edge_cases.append('Handle malformed security tokens')

        if any('performance' in risk.lower() for risk in plan.risks):
            edge_cases.append('Handle large data sets')
            edge_cases.append('Handle concurrent operations')

        return edge_cases

    def _generate_testing_requirements(self, plan: PlanArtifact) -> list[str]:
        """Generate testing requirements."""
        requirements = []

        # General testing requirements
        requirements.append('Unit tests for new/modified code')
        requirements.append('Integration tests for affected components')

        # Add specific testing based on plan
        if plan.affected_files:
            requirements.append(
                f'Tests for {len(plan.affected_files)} affected file(s)'
            )

        if any('security' in risk.lower() for risk in plan.risks):
            requirements.append('Security testing for vulnerabilities')

        if any('performance' in risk.lower() for risk in plan.risks):
            requirements.append('Performance benchmarks')

        return requirements

    def _generate_success_criteria(self, plan: PlanArtifact) -> list[str]:
        """Generate success criteria."""
        criteria = []

        # Add goal as success criterion
        criteria.append(f'{plan.goal} is achieved')

        # Add general success criteria
        criteria.append('All tests pass')
        criteria.append('No regressions introduced')

        # Add specific criteria based on plan
        if plan.ambiguity_score < 30:
            criteria.append('Implementation matches original issue description')

        if plan.affected_files:
            criteria.append('All affected files are correctly modified')

        return criteria
